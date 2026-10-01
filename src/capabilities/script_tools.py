"""Governed script capabilities loaded from exact, hash-verified packages."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import shutil
import subprocess
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Literal, Protocol, Self

from pydantic import Field, JsonValue, field_validator, model_validator

from capabilities.contracts import CapabilitySpec
from capabilities.runtime import CapabilityRefused
from common.assets import (
    AssetMetadata,
    ExecutionDependencies,
    RegistryContract,
    SecretRef,
)
from common.base import Contract, Sha256, Text
from common.execution import RequestContext

MAX_SCRIPT_BYTES = 1024 * 1024
MAX_SCRIPT_OUTPUT_CHARS = 16_000


class ScriptToolInput(Contract):
    arguments: dict[str, JsonValue] = Field(default_factory=dict)


class ScriptToolOutput(Contract):
    result: JsonValue


class ScriptToolManifest(RegistryContract):
    """An atomic process tool. A Skill may reference it but cannot execute it."""

    metadata: AssetMetadata
    description: Text
    runtime: Literal["python", "powershell"]
    entrypoint: Text
    sha256: Sha256
    timeout_seconds: int = Field(default=30, ge=1, le=120, strict=True)
    capability: CapabilitySpec
    dependencies: ExecutionDependencies = ExecutionDependencies(central_required=False)
    secrets: tuple[SecretRef, ...] = ()

    @field_validator("entrypoint")
    @classmethod
    def package_relative_entrypoint(cls, value: str) -> str:
        path = PurePosixPath(value)
        if (
            path.is_absolute()
            or "\\" in value
            or not path.parts
            or any(part in {"", ".", ".."} for part in path.parts)
        ):
            raise ValueError("script entrypoint must be a normalized package-relative path")
        return value

    @model_validator(mode="after")
    def governed_atomic_process(self) -> Self:
        if self.capability.identity != self.metadata.identity:
            raise ValueError("script metadata and capability must name the same exact version")
        if self.capability.side_effect != "execute":
            raise ValueError("a script tool must declare the execute side effect")
        if self.capability.policy != self.metadata.technical_policy:
            raise ValueError("script distribution and execution technical policy must match")
        if self.runtime == "python" and not self.entrypoint.endswith(".py"):
            raise ValueError("a Python script tool must name a .py entrypoint")
        if self.runtime == "powershell" and not self.entrypoint.endswith(".ps1"):
            raise ValueError("a PowerShell script tool must name a .ps1 entrypoint")
        if len({item.name for item in self.secrets}) != len(self.secrets):
            raise ValueError("script secret requirements must be unique")
        return self


@dataclass(frozen=True)
class InstalledScriptTool:
    manifest: ScriptToolManifest
    package_root: Path
    entrypoint: Path


class ProcessResult(Protocol):
    returncode: int
    stdout: str
    stderr: str


class ProcessRunner(Protocol):
    def __call__(
        self,
        argv: list[str],
        *,
        cwd: Path,
        input: str,
        capture_output: bool,
        text: bool,
        timeout: int,
        check: bool,
        env: Mapping[str, str],
    ) -> ProcessResult: ...


def _run_process(
    argv: list[str],
    *,
    cwd: Path,
    input: str,
    capture_output: bool,
    text: bool,
    timeout: int,
    check: bool,
    env: Mapping[str, str],
) -> ProcessResult:
    return subprocess.run(
        argv,
        cwd=cwd,
        input=input,
        capture_output=capture_output,
        text=text,
        timeout=timeout,
        check=check,
        env=env,
    )


def _environment() -> dict[str, str]:
    names = (
        "PATH",
        "PATHEXT",
        "HOME",
        "USERPROFILE",
        "APPDATA",
        "LOCALAPPDATA",
        "TEMP",
        "TMP",
        "SystemRoot",
        "WINDIR",
        "ComSpec",
    )
    return {name: os.environ[name] for name in names if name in os.environ}


def _checked_entrypoint(package_root: Path, manifest: ScriptToolManifest) -> Path:
    root = package_root.resolve()
    candidate = root / PurePosixPath(manifest.entrypoint)
    if candidate.is_symlink():
        raise ValueError("script entrypoint is not a regular package file")
    target = candidate.resolve()
    try:
        target.relative_to(root)
    except ValueError:
        raise ValueError("script entrypoint escapes its package") from None
    if not target.is_file() or target.is_symlink():
        raise ValueError("script entrypoint is not a regular package file")
    payload = target.read_bytes()
    if len(payload) > MAX_SCRIPT_BYTES:
        raise ValueError("script entrypoint exceeds the package limit")
    if hashlib.sha256(payload).hexdigest() != manifest.sha256:
        raise ValueError("script entrypoint digest does not match")
    return target


def load_script_tools(root: Path) -> tuple[InstalledScriptTool, ...]:
    """Load published package layouts and verify governance before registration."""
    if not root.is_dir():
        return ()
    installed: list[InstalledScriptTool] = []
    identities: set[tuple[str, str, str]] = set()
    for path in sorted(root.glob("*/*/*/script-tool.json")):
        manifest = ScriptToolManifest.model_validate_json(path.read_text(encoding="utf-8-sig"))
        identity = manifest.metadata.identity
        expected = root / identity.namespace / identity.name / identity.version
        if path.parent.resolve() != expected.resolve():
            raise ValueError("script package path does not match its identity")
        if manifest.metadata.lifecycle != "published":
            raise ValueError("only published script tools may be installed")
        if manifest.metadata.business_approval.status != "approved":
            raise ValueError("installed script tools require business approval")
        if manifest.metadata.technical_policy.status != "approved":
            raise ValueError("installed script tools require technical approval")
        if identity.key in identities:
            raise ValueError("script tool version is installed more than once")
        identities.add(identity.key)
        installed.append(
            InstalledScriptTool(
                manifest=manifest,
                package_root=path.parent.resolve(),
                entrypoint=_checked_entrypoint(path.parent, manifest),
            )
        )
    return tuple(installed)


class ScriptToolHandler:
    """Execute one fixed package file with JSON-only I/O and no shell."""

    def __init__(
        self,
        installed: InstalledScriptTool,
        *,
        runner: ProcessRunner = _run_process,
        which: Callable[[str], str | None] = shutil.which,
        python_executable: Path | None = None,
    ) -> None:
        self.installed = installed
        self._runner = runner
        self._which = which
        self._python = (python_executable or Path(sys.executable)).resolve()

    def _argv(self, entrypoint: Path) -> list[str]:
        if self.installed.manifest.runtime == "python":
            return [str(self._python), "-I", "-S", str(entrypoint)]
        executable = self._which("pwsh") or self._which("powershell")
        if executable is None:
            raise CapabilityRefused("script_runtime_unavailable")
        return [
            str(Path(executable).resolve()),
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-File",
            str(entrypoint),
        ]

    def _execute(self, inputs: ScriptToolInput) -> ScriptToolOutput:
        try:
            entrypoint = _checked_entrypoint(
                self.installed.package_root, self.installed.manifest
            )
        except (OSError, ValueError):
            raise CapabilityRefused("script_integrity_failed") from None
        try:
            completed = self._runner(
                self._argv(entrypoint),
                cwd=self.installed.package_root,
                input=json.dumps(inputs.arguments, ensure_ascii=False),
                capture_output=True,
                text=True,
                timeout=self.installed.manifest.timeout_seconds,
                check=False,
                env=_environment(),
            )
        except subprocess.TimeoutExpired:
            raise CapabilityRefused("script_timeout") from None
        except OSError:
            raise CapabilityRefused("script_start_failed") from None
        if completed.returncode != 0:
            raise CapabilityRefused("script_failed")
        if len(completed.stdout) > MAX_SCRIPT_OUTPUT_CHARS:
            raise CapabilityRefused("script_output_too_large")
        try:
            value = json.loads(completed.stdout)
        except (json.JSONDecodeError, TypeError):
            raise CapabilityRefused("script_invalid_output") from None
        return ScriptToolOutput(result=value)

    async def __call__(
        self, context: RequestContext, inputs: Contract
    ) -> ScriptToolOutput:
        del context
        checked = ScriptToolInput.model_validate(inputs)
        return await asyncio.to_thread(self._execute, checked)
