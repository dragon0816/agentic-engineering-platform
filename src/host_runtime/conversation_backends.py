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

from agent.backend_contracts import BackendProfile
from agent.data_policy import DataPolicy, OutboundContext
from common.assets import RegistryContract
from models.contracts import ModelMessage

ConversationBackendName = Literal["gateway", "claude_code", "codex", "copilot"]
ConversationBackendAuthentication = Literal[
    "ready", "required", "pending", "unavailable", "not_applicable"
]
MAX_BACKEND_OUTPUT_CHARS = 16_000
MAX_BACKEND_PROMPT_CHARS = 48_000
BACKEND_TIMEOUT_SECONDS = 90
AUTH_STATUS_TIMEOUT_SECONDS = 10


class ConversationBackendStatus(RegistryContract):
    name: ConversationBackendName
    label: str
    available: bool
    selectable: bool
    authentication: ConversationBackendAuthentication
    action: Literal["none", "authenticate", "configure", "install"]
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


class AuthenticationProcess(Protocol):
    def poll(self) -> int | None: ...


class AuthenticationLauncher(Protocol):
    def __call__(
        self,
        argv: list[str],
        *,
        cwd: Path,
        env: Mapping[str, str],
    ) -> AuthenticationProcess: ...


class BackendSpec(RegistryContract):
    name: ConversationBackendName
    label: str
    executable: str
    arguments: tuple[str, ...] = Field(min_length=1)
    authentication_arguments: tuple[str, ...] = Field(min_length=1)
    authentication_status_arguments: tuple[str, ...] = ()


SPECS = (
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
        authentication_arguments=("login",),
        authentication_status_arguments=("login", "status"),
    ),
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
        authentication_arguments=("auth", "login"),
        authentication_status_arguments=("auth", "status"),
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
        authentication_arguments=("login",),
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
    # UTF-8, never the console code page: a Chinese answer from a CLI crashed
    # the cp950 reader thread and left stdout None (2026-10-08 log).
    return subprocess.run(
        argv,
        cwd=cwd,
        input=input,
        capture_output=capture_output,
        text=text,
        encoding="utf-8" if text else None,
        errors="replace" if text else None,
        timeout=timeout,
        check=check,
        env=env,
    )


def _launch_authentication(
    argv: list[str],
    *,
    cwd: Path,
    env: Mapping[str, str],
) -> AuthenticationProcess:
    """Launch only a fixed login command in a visible local console."""

    creationflags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0) if os.name == "nt" else 0
    return subprocess.Popen(  # noqa: S603 - argv comes only from fixed BackendSpec values
        argv,
        cwd=cwd,
        env=env,
        stdin=None,
        stdout=None,
        stderr=None,
        start_new_session=os.name != "nt",
        creationflags=creationflags,
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


def _answer(output: str | None) -> str:
    values: list[str] = []
    output = output or ""
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


def _error_code(output: str) -> str:
    objects: list[object] = []
    try:
        objects.append(json.loads(output))
    except json.JSONDecodeError:
        for line in output.splitlines():
            try:
                objects.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    def authentication_failure(value: object) -> bool:
        if isinstance(value, dict):
            if value.get("api_error_status") in (401, 403):
                return True
            return any(authentication_failure(item) for item in value.values())
        if isinstance(value, list):
            return any(authentication_failure(item) for item in value)
        return False

    return (
        "backend_authentication_failed"
        if any(authentication_failure(item) for item in objects)
        else "backend_failed"
    )


class LocalConversationBackends:
    """Discover fixed CLI names and run them in a blank, bounded context."""

    def __init__(
        self,
        workspace_root: Path,
        *,
        which: Callable[[str], str | None] = shutil.which,
        runner: ProcessRunner = _run_process,
        status_runner: ProcessRunner | None = None,
        authentication_launcher: AuthenticationLauncher = _launch_authentication,
    ) -> None:
        self.root = workspace_root / ".conversation-backends"
        self.root.mkdir(parents=True, exist_ok=True)
        self._which = which
        self._runner = runner
        self._status_runner = runner if status_runner is None else status_runner
        self._authentication_launcher = authentication_launcher
        self._specs = {item.name: item for item in SPECS}
        self._unavailable: dict[ConversationBackendName, str] = {}
        self._authentication_processes: dict[ConversationBackendName, AuthenticationProcess] = {}
        self._authenticated_this_run: set[ConversationBackendName] = set()

    def _authentication(
        self, spec: BackendSpec, executable: str
    ) -> ConversationBackendAuthentication:
        process = self._authentication_processes.get(spec.name)
        if process is not None:
            finished = process.poll()
            if finished is None:
                return "pending"
            del self._authentication_processes[spec.name]
            if finished == 0:
                self._authenticated_this_run.add(spec.name)
                self._unavailable.pop(spec.name, None)
                return "ready"
            return "required"
        if spec.name in self._authenticated_this_run:
            return "ready"
        if self._unavailable.get(spec.name) == "backend_authentication_failed":
            return "required"
        if not spec.authentication_status_arguments:
            return "required"
        try:
            completed = self._status_runner(
                [executable, *spec.authentication_status_arguments],
                cwd=self.root,
                input="",
                capture_output=True,
                text=True,
                timeout=AUTH_STATUS_TIMEOUT_SECONDS,
                check=False,
                env=_environment(),
            )
        except (OSError, subprocess.TimeoutExpired):
            return "required"
        return "ready" if completed.returncode == 0 else "required"

    def statuses(
        self,
        *,
        gateway_available: bool,
        gateway_configured: bool | None = None,
        gateway_issue: str | None = None,
    ) -> tuple[ConversationBackendStatus, ...]:
        configured = gateway_available if gateway_configured is None else gateway_configured
        rows = [
            ConversationBackendStatus(
                name="gateway",
                label="Configured LLM Gateway",
                available=gateway_available,
                selectable=configured,
                authentication=(
                    "ready" if gateway_available else ("required" if configured else "unavailable")
                ),
                action=("none" if gateway_available else "configure"),
                detail=(
                    "Configured and ready"
                    if gateway_available
                    else (
                        gateway_issue or "Configured; its mapped credential is unavailable"
                        if configured
                        else "Configure it in Settings"
                    )
                ),
            )
        ]
        for spec in SPECS:
            failure = self._unavailable.get(spec.name)
            executable = self._which(spec.executable)
            authentication = (
                "unavailable" if executable is None else self._authentication(spec, executable)
            )
            available = executable is not None and authentication == "ready" and failure is None
            rows.append(
                ConversationBackendStatus(
                    name=spec.name,
                    label=spec.label,
                    available=available,
                    selectable=executable is not None,
                    authentication=authentication,
                    action=(
                        "install"
                        if executable is None
                        else ("none" if authentication == "ready" else "authenticate")
                    ),
                    detail=(
                        "Local CLI found and signed in"
                        if available
                        else (
                            f"{spec.executable} authentication is in progress"
                            if authentication == "pending"
                            else (
                                "Sign in to this local CLI"
                                if executable is not None
                                else f"{spec.executable} is not installed or not on PATH"
                            )
                        )
                    ),
                )
            )
        return tuple(rows)

    def authenticate(self, backend: ConversationBackendName) -> dict[str, object]:
        """Start one fixed official CLI login flow after an explicit UI action."""

        spec = self._specs.get(backend)
        if spec is None:
            return {"ok": False, "backend": backend, "code": "backend_authentication_unsupported"}
        executable = self._which(spec.executable)
        if executable is None:
            return {"ok": False, "backend": backend, "code": "backend_not_installed"}
        authentication = self._authentication(spec, executable)
        if authentication == "ready":
            return {"ok": True, "backend": backend, "status": "ready"}
        if authentication == "pending":
            return {"ok": True, "backend": backend, "status": "pending"}
        try:
            process = self._authentication_launcher(
                [executable, *spec.authentication_arguments],
                cwd=self.root,
                env=_environment(),
            )
        except OSError:
            return {"ok": False, "backend": backend, "code": "backend_authentication_failed"}
        self._authentication_processes[backend] = process
        return {"ok": True, "backend": backend, "status": "started"}

    def complete(
        self,
        backend: ConversationBackendName,
        history: tuple[ModelMessage, ...],
        *,
        persona_guidance: str,
        outbound: OutboundContext | None = None,
        max_history_messages: int = 12,
    ) -> ConversationBackendResult:
        spec = self._specs.get(backend)
        if spec is None:
            return ConversationBackendResult(
                backend=backend, status="unavailable", code="backend_not_local_cli"
            )
        if outbound is not None:
            expected = [("history", message.text) for message in history]
            if persona_guidance:
                expected.append(("persona", persona_guidance))
            actual = [(item.origin, item.text) for item in outbound.materials]
            if (
                actual != expected
                or any(message.images or message.tool_calls for message in history)
            ):
                return ConversationBackendResult(
                    backend=backend, status="unavailable", code="context_mismatch"
                )
        decision = DataPolicy(()).decide(
            BackendProfile(backend_id=backend, kind="agent", harness="native"), outbound
        )
        if not decision.allowed:
            return ConversationBackendResult(
                backend=backend, status="unavailable", code=decision.code
            )
        executable = self._which(spec.executable)
        if executable is None:
            return ConversationBackendResult(
                backend=backend, status="unavailable", code="backend_not_installed"
            )
        if isinstance(max_history_messages, bool) or not 1 <= max_history_messages <= 40:
            raise ValueError("conversation supports one to forty history messages")
        prompt = self._prompt(history, persona_guidance, max_history_messages)
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
            code = _error_code(completed.stdout)
            if code == "backend_authentication_failed":
                self._unavailable[backend] = code
            return ConversationBackendResult(backend=backend, status="failed", code=code)
        answer = _answer(completed.stdout)
        if not answer:
            return ConversationBackendResult(
                backend=backend, status="failed", code="backend_empty_response"
            )
        return ConversationBackendResult(backend=backend, status="answered", text=answer)

    @staticmethod
    def _prompt(
        history: tuple[ModelMessage, ...], persona_guidance: str, max_history_messages: int = 12
    ) -> str:
        policy = (
            "You are a restricted conversation backend for a Personal Engineering Agent. "
            "Answer with text only. Do not use tools, read files, execute commands, browse, "
            "modify state, or claim an action occurred. The host Agent separately validates "
            "and executes every supported tool through its Bridge."
        )
        prefix = (
            policy
            + "\n\nPersona controls speaking style only:\n"
            + persona_guidance[:4000]
            + "\n\nConversation:\n"
        )
        suffix = "\nassistant:"
        remaining = MAX_BACKEND_PROMPT_CHARS - len(prefix) - len(suffix)
        selected: list[str] = []
        for message in reversed(history[-max_history_messages:]):
            line = f"{message.role}: {message.text[:4000]}"
            size = len(line) + (1 if selected else 0)
            if size > remaining:
                break
            selected.append(line)
            remaining -= size
        return prefix + "\n".join(reversed(selected)) + suffix
