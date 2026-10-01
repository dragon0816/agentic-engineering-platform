"""Restricted adapters for locally signed-in conversation CLIs."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Literal, Protocol

from pydantic import Field

from common.assets import RegistryContract
from models.contracts import ModelMessage

ConversationBackendName = Literal["gateway", "claude_code", "codex", "copilot"]
MAX_BACKEND_OUTPUT_CHARS = 16_000
MAX_BACKEND_PROMPT_CHARS = 48_000
BACKEND_TIMEOUT_SECONDS = 90


class ConversationBackendStatus(RegistryContract):
    name: ConversationBackendName
    label: str
    available: bool
    detail: str


class ConversationBackendResult(RegistryContract):
    backend: ConversationBackendName
    status: Literal["answered", "unavailable", "failed", "timeout"]
    text: str = ""
    code: str | None = None


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


class BackendSpec(RegistryContract):
    name: ConversationBackendName
    label: str
    executable: str
    arguments: tuple[str, ...] = Field(min_length=1)


SPECS = (
    BackendSpec(
        name="claude_code",
        label="Claude Code",
        executable="claude",
        arguments=(
            "--print",
            "--output-format",
            "json",
            "--no-session-persistence",
            "--safe-mode",
            "--restricted",
            "--tools",
            "",
            "--strict-mcp-config",
            "--disable-slash-commands",
            "--permission-prompts",
            "none",
        ),
    ),
    BackendSpec(
        name="codex",
        label="Codex",
        executable="codex",
        arguments=(
            "exec",
            "--json",
            "--ephemeral",
            "--ignore-user-config",
            "--ignore-rules",
            "--sandbox",
            "read-only",
            "--skip-git-repo-check",
            "--color",
            "never",
            "-",
        ),
    ),
    BackendSpec(
        name="copilot",
        label="GitHub Copilot",
        executable="copilot",
        arguments=(
            "--output-format=json",
            "--no-ask-user",
            "--available-tools=",
            "--disable-builtin-mcps",
        ),
    ),
)


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
    allowed = (
        "PATH",
        "HOME",
        "USERPROFILE",
        "APPDATA",
        "LOCALAPPDATA",
        "CODEX_HOME",
        "TEMP",
        "TMP",
        "SystemRoot",
        "ComSpec",
    )
    return {name: os.environ[name] for name in allowed if name in os.environ}


def _text_values(value: object) -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key in ("result", "text", "content", "message"):
            item = value.get(key)
            if isinstance(item, str) and item.strip():
                found.append(item.strip())
        for item in value.values():
            if isinstance(item, (dict, list)):
                found.extend(_text_values(item))
    elif isinstance(value, list):
        for item in value:
            found.extend(_text_values(item))
    return found


def _answer(output: str) -> str:
    values: list[str] = []
    try:
        values.extend(_text_values(json.loads(output)))
    except json.JSONDecodeError:
        for line in output.splitlines():
            try:
                values.extend(_text_values(json.loads(line)))
            except json.JSONDecodeError:
                continue
    if values:
        return values[-1][:MAX_BACKEND_OUTPUT_CHARS]
    stripped = output.strip()
    return stripped[:MAX_BACKEND_OUTPUT_CHARS] if stripped else ""


class LocalConversationBackends:
    """Discover fixed CLI names and run them in a blank, bounded context."""

    def __init__(
        self,
        workspace_root: Path,
        *,
        which: Callable[[str], str | None] = shutil.which,
        runner: ProcessRunner = _run_process,
    ) -> None:
        self.root = workspace_root / ".conversation-backends"
        self.root.mkdir(parents=True, exist_ok=True)
        self._which = which
        self._runner = runner
        self._specs = {item.name: item for item in SPECS}

    def statuses(self, *, gateway_available: bool) -> tuple[ConversationBackendStatus, ...]:
        rows = [
            ConversationBackendStatus(
                name="gateway",
                label="Configured LLM Gateway",
                available=gateway_available,
                detail=("Configured" if gateway_available else "Configure it in Settings"),
            )
        ]
        for spec in SPECS:
            available = self._which(spec.executable) is not None
            rows.append(
                ConversationBackendStatus(
                    name=spec.name,
                    label=spec.label,
                    available=available,
                    detail=(
                        "Local CLI found; its existing sign-in will be used"
                        if available
                        else f"{spec.executable} is not installed or not on PATH"
                    ),
                )
            )
        return tuple(rows)

    def complete(
        self,
        backend: ConversationBackendName,
        history: tuple[ModelMessage, ...],
        *,
        persona_guidance: str,
    ) -> ConversationBackendResult:
        spec = self._specs.get(backend)
        if spec is None:
            return ConversationBackendResult(
                backend=backend, status="unavailable", code="backend_not_local_cli"
            )
        executable = self._which(spec.executable)
        if executable is None:
            return ConversationBackendResult(
                backend=backend, status="unavailable", code="backend_not_installed"
            )
        prompt = self._prompt(history, persona_guidance)
        try:
            completed = self._runner(
                [executable, *spec.arguments],
                cwd=self.root,
                input=prompt,
                capture_output=True,
                text=True,
                timeout=BACKEND_TIMEOUT_SECONDS,
                check=False,
                env=_environment(),
            )
        except subprocess.TimeoutExpired:
            return ConversationBackendResult(
                backend=backend, status="timeout", code="backend_timeout"
            )
        except OSError:
            return ConversationBackendResult(
                backend=backend, status="unavailable", code="backend_start_failed"
            )
        if completed.returncode != 0:
            return ConversationBackendResult(
                backend=backend, status="failed", code="backend_failed"
            )
        answer = _answer(completed.stdout)
        if not answer:
            return ConversationBackendResult(
                backend=backend, status="failed", code="backend_empty_response"
            )
        return ConversationBackendResult(backend=backend, status="answered", text=answer)

    @staticmethod
    def _prompt(history: tuple[ModelMessage, ...], persona_guidance: str) -> str:
        policy = (
            "You are a restricted conversation backend for a Personal Engineering Agent. "
            "Answer with text only. Do not use tools, read files, execute commands, browse, "
            "modify state, or claim an action occurred. The host Agent separately validates "
            "and executes every supported tool through its Bridge."
        )
        transcript = "\n".join(
            f"{message.role}: {message.text[:4000]}" for message in history[-12:]
        )
        return (
            policy
            + "\n\nPersona controls speaking style only:\n"
            + persona_guidance[:4000]
            + "\n\nConversation:\n"
            + transcript
            + "\nassistant:"
        )[:MAX_BACKEND_PROMPT_CHARS]
