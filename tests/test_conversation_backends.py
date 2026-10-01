"""Restricted local CLI conversation backend contracts and process boundary."""

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from host_runtime.conversation_backends import (
    AUTH_STATUS_TIMEOUT_SECONDS,
    BACKEND_TIMEOUT_SECONDS,
    MAX_BACKEND_OUTPUT_CHARS,
    LocalConversationBackends,
)
from models.contracts import ModelMessage


class Runner:
    def __init__(self, stdout: str = "", *, returncode: int = 0, timeout: bool = False) -> None:
        self.stdout = stdout
        self.returncode = returncode
        self.timeout = timeout
        self.calls: list[tuple[list[str], dict[str, Any]]] = []

    def __call__(self, argv: list[str], **kwargs: Any) -> Any:
        self.calls.append((argv, kwargs))
        if self.timeout:
            raise subprocess.TimeoutExpired(argv, kwargs["timeout"])
        return SimpleNamespace(returncode=self.returncode, stdout=self.stdout, stderr="ignored")


class LoginProcess:
    def __init__(self, returncode: int | None = None) -> None:
        self.returncode = returncode

    def poll(self) -> int | None:
        return self.returncode


class LoginLauncher:
    def __init__(self, process: LoginProcess) -> None:
        self.process = process
        self.calls: list[tuple[list[str], dict[str, Any]]] = []

    def __call__(self, argv: list[str], **kwargs: Any) -> LoginProcess:
        self.calls.append((argv, kwargs))
        return self.process


def installed(name: str) -> str | None:
    return f"C:/fixed/{name}.exe" if name in {"claude", "codex"} else None


def history() -> tuple[ModelMessage, ...]:
    return (ModelMessage(role="user", text="What can you help with?"),)


def test_status_reports_only_fixed_local_cli_names(tmp_path: Path) -> None:
    backends = LocalConversationBackends(tmp_path, which=installed)
    statuses = {item.name: item for item in backends.statuses(gateway_available=False)}
    assert statuses["gateway"].available is False
    assert statuses["claude_code"].selectable is True
    assert statuses["codex"].selectable is True
    assert statuses["copilot"].available is False
    assert statuses["copilot"].selectable is False
    assert statuses["copilot"].action == "install"


def test_signed_out_backend_launches_only_its_fixed_login_command(tmp_path: Path) -> None:
    status_runner = Runner(returncode=1)
    process = LoginProcess()
    launcher = LoginLauncher(process)
    backends = LocalConversationBackends(
        tmp_path,
        which=installed,
        status_runner=status_runner,
        authentication_launcher=launcher,
    )
    before = {item.name: item for item in backends.statuses(gateway_available=False)}
    assert before["codex"].selectable is True
    assert before["codex"].available is False
    assert before["codex"].authentication == "required"
    assert status_runner.calls[0][0] == ["C:/fixed/codex.exe", "login", "status"]
    assert status_runner.calls[0][1]["timeout"] == AUTH_STATUS_TIMEOUT_SECONDS

    started = backends.authenticate("codex")
    assert started == {"ok": True, "backend": "codex", "status": "started"}
    assert launcher.calls[0][0] == ["C:/fixed/codex.exe", "login"]
    assert launcher.calls[0][1]["cwd"] == tmp_path / ".conversation-backends"
    pending = {item.name: item for item in backends.statuses(gateway_available=False)}
    assert pending["codex"].authentication == "pending"

    process.returncode = 0
    ready = {item.name: item for item in backends.statuses(gateway_available=False)}
    assert ready["codex"].available is True
    assert ready["codex"].authentication == "ready"


def test_gateway_configuration_and_credential_readiness_are_separate(tmp_path: Path) -> None:
    statuses = {
        item.name: item
        for item in LocalConversationBackends(tmp_path, which=lambda _name: None).statuses(
            gateway_configured=True,
            gateway_available=False,
        )
    }
    assert statuses["gateway"].selectable is True
    assert statuses["gateway"].available is False
    assert statuses["gateway"].authentication == "required"
    assert statuses["gateway"].action == "configure"


def test_claude_uses_stdin_fixed_restrictions_and_blank_working_root(tmp_path: Path) -> None:
    runner = Runner(json.dumps({"result": "A bounded answer."}))
    backends = LocalConversationBackends(tmp_path, which=installed, runner=runner)
    result = backends.complete("claude_code", history(), persona_guidance="Speak plainly.")
    argv, call = runner.calls[0]
    assert result.status == "answered" and result.text == "A bounded answer."
    assert argv[0] == "C:/fixed/claude.exe"
    assert "--restricted" in argv and "--tools" in argv
    assert "What can you help with?" not in argv
    assert "Do not use tools" in call["input"]
    assert call["cwd"] == tmp_path / ".conversation-backends"
    assert call["timeout"] == BACKEND_TIMEOUT_SECONDS
    assert "GITHUB_TOKEN" not in call["env"]


def test_codex_jsonl_is_reduced_to_final_text_and_output_is_bounded(tmp_path: Path) -> None:
    stdout = "\n".join(
        (
            json.dumps({"type": "thread.started", "thread_id": "ignored"}),
            json.dumps(
                {
                    "type": "item.completed",
                    "item": {"type": "agent_message", "text": "x" * 20_000},
                }
            ),
        )
    )
    runner = Runner(stdout)
    result = LocalConversationBackends(tmp_path, which=installed, runner=runner).complete(
        "codex", history(), persona_guidance="Be concise."
    )
    argv, _call = runner.calls[0]
    assert result.status == "answered" and len(result.text) == MAX_BACKEND_OUTPUT_CHARS
    assert argv[1:3] == ["exec", "--json"]
    assert "--sandbox" in argv and "read-only" in argv
    assert "--ephemeral" in argv and "--ignore-user-config" in argv


def test_timeout_and_missing_cli_are_typed_without_stderr_leaks(tmp_path: Path) -> None:
    timed = LocalConversationBackends(tmp_path, which=installed, runner=Runner(timeout=True))
    timeout = timed.complete("claude_code", history(), persona_guidance="Plain.")
    assert timeout.status == "timeout" and timeout.code == "backend_timeout"
    missing = timed.complete("copilot", history(), persona_guidance="Plain.")
    assert missing.status == "unavailable" and missing.code == "backend_not_installed"


def test_authentication_failure_is_typed_and_marks_backend_unavailable(tmp_path: Path) -> None:
    runner = Runner(
        json.dumps(
            {
                "is_error": True,
                "api_error_status": 403,
                "result": "provider-specific detail must not travel",
            }
        ),
        returncode=1,
    )
    backends = LocalConversationBackends(tmp_path, which=installed, runner=runner)
    failed = backends.complete("claude_code", history(), persona_guidance="Plain.")
    assert failed.status == "failed" and failed.code == "backend_authentication_failed"
    status = {item.name: item for item in backends.statuses(gateway_available=False)}
    assert status["claude_code"].available is False
    assert "sign in" in status["claude_code"].detail.lower()
