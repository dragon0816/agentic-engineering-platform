"""Bounded out-of-process Bridge Extension activation and JSON-lines IPC."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import venv
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from pathlib import Path, PurePosixPath
from threading import Lock
from time import monotonic
from typing import Literal, Protocol, Self

from pydantic import Field, JsonValue, model_validator

from capabilities.contracts import CapabilitySpec
from common.assets import AssetIdentity
from common.base import Contract, Symbol, Text
from extensions.contracts import BridgeExtensionManifest
from extensions.package import PortableExtensionPackage, StagedExtension

PROTOCOL: Literal["aep-extension-jsonl/v1"] = "aep-extension-jsonl/v1"
_PREPARED = ".aep-prepared.json"


class ExtensionRequest(Contract):
    protocol: Literal["aep-extension-jsonl/v1"] = PROTOCOL
    request_id: Symbol
    operation: Literal["health", "invoke", "shutdown"]
    capability: AssetIdentity | None = None
    arguments: dict[str, JsonValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def operation_shape(self) -> Self:
        if self.operation == "invoke" and self.capability is None:
            raise ValueError("extension invocation requires an exact capability")
        if self.operation != "invoke" and (self.capability is not None or self.arguments):
            raise ValueError("extension control requests do not carry capability arguments")
        return self


class ExtensionResponse(Contract):
    protocol: Literal["aep-extension-jsonl/v1"] = PROTOCOL
    request_id: Symbol
    status: Literal["healthy", "succeeded", "refused", "failed"]
    capabilities: tuple[AssetIdentity, ...] = ()
    data: JsonValue = None
    code: Symbol | None = None

    @model_validator(mode="after")
    def response_shape(self) -> Self:
        if self.status == "healthy":
            if not self.capabilities or self.code is not None:
                raise ValueError("healthy response declares capabilities and no error")
        elif self.capabilities:
            raise ValueError("only health responses declare capabilities")
        if (self.status in {"refused", "failed"}) != (self.code is not None):
            raise ValueError("extension failure status and code must agree")
        return self


class ExtensionActivationApproval(Contract):
    approval_id: Symbol
    actor: Symbol
    device_id: Symbol
    device_kind: Literal["company_workstation", "shared_test_computer"]
    extension: AssetIdentity
    policy_ref: Text


class ExtensionActivationRecord(Contract):
    extension: AssetIdentity
    state: Literal["active", "refused", "unhealthy", "rolled_back", "disabled"]
    code: Symbol | None = None
    advertised_capabilities: tuple[AssetIdentity, ...] = ()

    @model_validator(mode="after")
    def state_shape(self) -> Self:
        if (self.state == "active") != (self.code is None):
            raise ValueError("only active records omit a result code")
        if self.state not in {"active", "rolled_back"} and self.advertised_capabilities:
            raise ValueError("inactive extensions cannot advertise capabilities")
        return self


class ExtensionProcessSession(Protocol):
    def exchange(self, request: ExtensionRequest, timeout_seconds: int) -> ExtensionResponse: ...

    def poll(self) -> int | None: ...

    def close(self) -> None: ...


class ExtensionProcessFactory(Protocol):
    def start(
        self, staged: StagedExtension, manifest: BridgeExtensionManifest
    ) -> ExtensionProcessSession: ...


class JsonLineSubprocessSession:
    """One subprocess with one synchronized request/reply JSON-lines stream."""

    def __init__(self, process: subprocess.Popen[str]) -> None:
        if process.stdin is None or process.stdout is None:
            raise ValueError("extension process requires standard input and output")
        self._process = process
        self._lock = Lock()

    def exchange(self, request: ExtensionRequest, timeout_seconds: int) -> ExtensionResponse:
        if self._process.poll() is not None:
            raise RuntimeError("extension process is not running")
        assert self._process.stdin is not None
        assert self._process.stdout is not None
        with self._lock:
            self._process.stdin.write(request.model_dump_json() + "\n")
            self._process.stdin.flush()
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(self._process.stdout.readline)
                try:
                    line = future.result(timeout=timeout_seconds)
                except FutureTimeout:
                    self.close()
                    raise TimeoutError("extension response timed out") from None
            if not line:
                raise RuntimeError("extension process closed its response stream")
            response = ExtensionResponse.model_validate_json(line)
            if response.request_id != request.request_id:
                raise RuntimeError("extension response request identity mismatch")
            return response

    def poll(self) -> int | None:
        return self._process.poll()

    def close(self) -> None:
        if self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait(timeout=2)


class SubprocessExtensionFactory:
    """Launch only the fixed interpreter prepared inside an exact staged version."""

    @staticmethod
    def _prepare(staged: StagedExtension) -> None:
        root = Path(staged.root).resolve()
        environment = root / ".venv"
        marker = environment / _PREPARED
        if marker.is_file():
            try:
                record = json.loads(marker.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                record = {}
            if record == {"content_sha256": staged.content_sha256}:
                return
        if environment.exists():
            shutil.rmtree(environment)
        try:
            venv.EnvBuilder(with_pip=True, clear=False).create(environment)
            interpreter = environment / "Scripts" / "python.exe"
            wheels = sorted((root / "wheels").glob("*.whl"))
            if not wheels:
                raise ValueError("extension package has no offline wheels")
            subprocess.run(
                [
                    str(interpreter),
                    "-I",
                    "-m",
                    "pip",
                    "install",
                    "--disable-pip-version-check",
                    "--no-index",
                    "--no-deps",
                    *map(str, wheels),
                ],
                cwd=root,
                env={
                    **{
                        key: value
                        for key in ("SystemRoot", "WINDIR", "TEMP", "TMP")
                        if (value := os.environ.get(key)) is not None
                    },
                    "PIP_NO_INDEX": "1",
                    "PYTHONNOUSERSITE": "1",
                },
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=120,
                check=True,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            marker.write_text(
                json.dumps({"content_sha256": staged.content_sha256}), encoding="utf-8"
            )
        except (OSError, subprocess.SubprocessError, ValueError):
            if environment.exists():
                shutil.rmtree(environment)
            raise ValueError("extension isolated environment preparation failed") from None

    def start(
        self, staged: StagedExtension, manifest: BridgeExtensionManifest
    ) -> ExtensionProcessSession:
        root = Path(staged.root).resolve()
        self._prepare(staged)
        interpreter = root / ".venv" / "Scripts" / "python.exe"
        if not interpreter.is_file():
            raise ValueError("extension isolated environment is not prepared")
        environment = {
            key: value
            for key in ("SystemRoot", "WINDIR", "TEMP", "TMP")
            if (value := os.environ.get(key)) is not None
        }
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        process = subprocess.Popen(
            [str(interpreter), "-I", "-m", manifest.process.module],
            cwd=root,
            env=environment,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            bufsize=1,
            creationflags=flags,
        )
        return JsonLineSubprocessSession(process)


class ExtensionInvocationError(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class _Active:
    def __init__(
        self,
        staged: StagedExtension,
        manifest: BridgeExtensionManifest,
        approval: ExtensionActivationApproval,
        session: ExtensionProcessSession,
    ) -> None:
        self.staged = staged
        self.manifest = manifest
        self.approval = approval
        self.session = session


class ExtensionManager:
    """Activate exact versions and expose only a healthy process's declarations."""

    def __init__(
        self,
        *,
        device_id: str,
        device_kind: Literal["company_workstation", "shared_test_computer"],
        factory: ExtensionProcessFactory,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        self.device_id = device_id
        self.device_kind = device_kind
        self._factory = factory
        self._clock = clock
        self._active: _Active | None = None
        self._previous: _Active | None = None
        self._crashes: dict[tuple[str, str, str], list[float]] = {}
        self._record: ExtensionActivationRecord | None = None

    @staticmethod
    def _load(staged: StagedExtension) -> BridgeExtensionManifest:
        root = Path(staged.root)
        if not root.is_absolute() or not root.is_dir():
            raise ValueError("staged extension root is unavailable")
        package = PortableExtensionPackage.model_validate_json((root / "package.json").read_bytes())
        if package.identity != staged.identity or package.content_sha256 != staged.content_sha256:
            raise ValueError("staged extension identity or digest changed")
        for item in package.files:
            path = root / PurePosixPath(item.path)
            if not path.is_file() or path.read_bytes() != item.raw:
                raise ValueError("staged extension files changed")
        return package.manifest

    def _approve(
        self, manifest: BridgeExtensionManifest, approval: ExtensionActivationApproval
    ) -> None:
        if (
            approval.extension != manifest.metadata.identity
            or approval.device_id != self.device_id
            or approval.device_kind != self.device_kind
            or approval.policy_ref not in manifest.metadata.technical_policy.policy_refs
        ):
            raise ValueError("extension activation approval does not match this device and policy")

    @staticmethod
    def _health(
        session: ExtensionProcessSession, manifest: BridgeExtensionManifest
    ) -> ExtensionResponse:
        response = session.exchange(
            ExtensionRequest(request_id="extension-health", operation="health"),
            manifest.health.startup_timeout_seconds,
        )
        expected = tuple(item.identity for item in manifest.capabilities)
        if response.status != "healthy" or response.capabilities != expected:
            raise RuntimeError("extension health declaration mismatch")
        return response

    def activate(
        self, staged: StagedExtension, approval: ExtensionActivationApproval
    ) -> ExtensionActivationRecord:
        manifest = self._load(staged)
        self._approve(manifest, approval)
        key = manifest.metadata.identity.key
        now = self._clock()
        window = manifest.health.crash_window_seconds
        recent = [stamp for stamp in self._crashes.get(key, ()) if now - stamp <= window]
        self._crashes[key] = recent
        if len(recent) >= manifest.health.max_crashes:
            self._record = ExtensionActivationRecord(
                extension=manifest.metadata.identity,
                state="disabled",
                code="extension_crash_limit",
            )
            return self._record
        try:
            candidate = self._factory.start(staged, manifest)
            self._health(candidate, manifest)
        except (OSError, RuntimeError, TimeoutError, ValueError):
            if "candidate" in locals():
                candidate.close()
            if self._active is not None:
                self._record = ExtensionActivationRecord(
                    extension=self._active.manifest.metadata.identity,
                    state="rolled_back",
                    code="extension_activation_failed",
                    advertised_capabilities=tuple(
                        item.identity for item in self._active.manifest.capabilities
                    ),
                )
                return self._record
            self._record = ExtensionActivationRecord(
                extension=manifest.metadata.identity,
                state="unhealthy",
                code="extension_activation_failed",
            )
            return self._record
        old = self._active
        self._active = _Active(staged, manifest, approval, candidate)
        self._previous = old
        self._record = ExtensionActivationRecord(
            extension=manifest.metadata.identity,
            state="active",
            advertised_capabilities=tuple(item.identity for item in manifest.capabilities),
        )
        if old is not None:
            old.session.close()
        return self._record

    @property
    def advertised_capabilities(self) -> tuple[CapabilitySpec, ...]:
        if self._active is None or self._record is None:
            return ()
        if self._record.state not in {"active", "rolled_back"}:
            return ()
        if self._active.session.poll() is not None:
            self._record = ExtensionActivationRecord(
                extension=self._active.manifest.metadata.identity,
                state="unhealthy",
                code="extension_process_exited",
            )
            return ()
        return self._active.manifest.capabilities

    def invoke(
        self, capability: AssetIdentity, arguments: dict[str, JsonValue], *, request_id: str
    ) -> JsonValue:
        active = self._active
        if active is None or capability.key not in {
            item.identity.key for item in self.advertised_capabilities
        }:
            raise ExtensionInvocationError("extension_capability_unavailable")
        try:
            response = active.session.exchange(
                ExtensionRequest(
                    request_id=request_id,
                    operation="invoke",
                    capability=capability,
                    arguments=arguments,
                ),
                active.manifest.health.request_timeout_seconds,
            )
        except (OSError, RuntimeError, TimeoutError, ValueError):
            self._record_crash(active)
            raise ExtensionInvocationError("extension_process_failure") from None
        if response.status != "succeeded":
            raise ExtensionInvocationError(response.code or "extension_invocation_failed")
        return response.data

    def _record_crash(self, failed: _Active) -> None:
        now = self._clock()
        window = failed.manifest.health.crash_window_seconds
        key = failed.manifest.metadata.identity.key
        recent = [stamp for stamp in self._crashes.get(key, ()) if now - stamp <= window]
        recent.append(now)
        self._crashes[key] = recent
        failed.session.close()
        self._active = None
        self._record = ExtensionActivationRecord(
            extension=failed.manifest.metadata.identity,
            state=(
                "disabled" if len(recent) >= failed.manifest.health.max_crashes else "unhealthy"
            ),
            code="extension_process_failure",
        )
        if self._previous is not None and "health_failure" in failed.manifest.rollback.automatic_on:
            previous = self._previous
            try:
                session = self._factory.start(previous.staged, previous.manifest)
                self._health(session, previous.manifest)
            except (OSError, RuntimeError, TimeoutError, ValueError):
                if "session" in locals():
                    session.close()
                return
            self._active = _Active(previous.staged, previous.manifest, previous.approval, session)
            self._previous = None
            self._record = ExtensionActivationRecord(
                extension=previous.manifest.metadata.identity,
                state="rolled_back",
                code="extension_health_rollback",
                advertised_capabilities=tuple(
                    item.identity for item in previous.manifest.capabilities
                ),
            )

    @property
    def record(self) -> ExtensionActivationRecord | None:
        return self._record

    def close(self) -> None:
        if self._active is not None:
            self._active.session.close()
        self._active = None
