"""Restricted local CLI conversation backend contracts and process boundary."""

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from agent.data_policy import ContextMaterial, OutboundContext
from host_runtime.conversation_backends import (
    AUTH_STATUS_TIMEOUT_SECONDS,
    BACKEND_TIMEOUT_SECONDS,
    MAX_BACKEND_OUTPUT_CHARS,
    AgentLaunch,
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


def public_context(messages: tuple[ModelMessage, ...], persona_guidance: str) -> OutboundContext:
    materials = [
        ContextMaterial(
            material_id=f"message-{index}",
            origin="history",
            classification="PUBLIC",
            classified_by="engineer",
            text=message.text,
        )
        for index, message in enumerate(messages)
    ]
    if persona_guidance:
        materials.append(
            ContextMaterial(
                material_id="persona-1",
                origin="persona",
                classification="PUBLIC",
                classified_by="engineer",
                text=persona_guidance,
            )
        )
    return OutboundContext(materials=tuple(materials))


def test_selected_native_model_is_validated_and_forwarded(tmp_path: Path) -> None:
    runner = Runner('{"result":"answer"}')
    backends = LocalConversationBackends(tmp_path, which=installed, runner=runner)
    backends.available_models = lambda backend: {"ok": True, "models": ["fixture-native"]}  # type: ignore[method-assign]
    for backend in ("codex", "claude_code"):
        result = backends.complete(
            backend,
            history(),
            persona_guidance="",
            outbound=public_context(history(), ""),
            model="fixture-native",
        )
        assert result.status == "answered"
        argv = runner.calls[-1][0]
        assert argv[argv.index("--model") + 1] == "fixture-native"
        before = len(runner.calls)
        result = backends.complete(
            backend,
            history(),
            persona_guidance="",
            outbound=public_context(history(), ""),
            model="--bad",
        )
        assert result.code == "model_not_approved"
        assert len(runner.calls) == before


def test_selected_claude_agent_model_preserves_native_it_permission_settings(
    tmp_path: Path,
) -> None:
    runner = Runner('{"result":"answer"}')
    backends = LocalConversationBackends(tmp_path, which=installed, runner=runner)
    backends.available_models = lambda backend: {"ok": True, "models": ["fixture-native"]}  # type: ignore[method-assign]
    result = backends.complete(
        "claude_code",
        history(),
        persona_guidance="",
        outbound=public_context(history(), ""),
        model="fixture-native",
        agent=AgentLaunch(folder=tmp_path, servers={}, on_permission=lambda _: False),
    )
    assert result.status == "answered"
    argv = runner.calls[-1][0]
    assert argv[argv.index("--model") + 1] == "fixture-native"
    assert "--permission-mode" not in argv
    assert "--permission-prompts" not in argv
    assert "--permission-prompt-tool" not in argv
    assert "--dangerously-skip-permissions" not in argv


def test_native_catalog_missing_signed_out_and_cached(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    missing = LocalConversationBackends(tmp_path, which=lambda _: None)
    assert missing.available_models("codex")["code"] == "backend_not_installed"
    signed_out = LocalConversationBackends(
        tmp_path, which=installed, status_runner=Runner(returncode=1)
    )
    assert signed_out.available_models("codex")["code"] == "backend_authentication_required"
    calls: list[str] = []

    def metadata(backend: str, *_: Any) -> dict[str, Any]:
        calls.append(backend)
        return {"ok": True, "models": [backend + "-m"]}

    monkeypatch.setattr("host_runtime.conversation_backends.discover", metadata)
    ready = LocalConversationBackends(tmp_path, which=installed, status_runner=Runner())
    assert ready.available_models("codex")["models"] == ["codex-m"]
    assert ready.available_models("codex")["models"] == ["codex-m"]
    assert calls == ["codex"]


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


def test_claude_uses_stdin_without_aep_tool_restrictions(tmp_path: Path) -> None:
    runner = Runner(json.dumps({"result": "A bounded answer."}))
    backends = LocalConversationBackends(tmp_path, which=installed, runner=runner)
    result = backends.complete(
        "claude_code",
        history(),
        persona_guidance="Speak plainly.",
        outbound=public_context(history(), "Speak plainly."),
    )
    argv, call = runner.calls[0]
    assert result.status == "answered" and result.text == "A bounded answer."
    assert argv[0] == "C:/fixed/claude.exe"
    assert "--restricted" not in argv and "--tools" not in argv
    assert "What can you help with?" not in argv
    assert "Return real results" in call["input"]
    assert call["cwd"] == tmp_path / ".conversation-backends"
    assert call["timeout"] == BACKEND_TIMEOUT_SECONDS
    assert "Persona controls speaking style only" in call["input"]


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
        "codex",
        history(),
        persona_guidance="Be concise.",
        outbound=public_context(history(), "Be concise."),
    )
    argv, _call = runner.calls[0]
    assert result.status == "answered" and len(result.text) == MAX_BACKEND_OUTPUT_CHARS
    assert argv[1:3] == ["exec", "--json"]
    assert "--sandbox" not in argv and "read-only" not in argv
    assert "--ephemeral" in argv and "--ignore-user-config" not in argv


def test_timeout_and_missing_cli_are_typed_without_stderr_leaks(tmp_path: Path) -> None:
    timed = LocalConversationBackends(tmp_path, which=installed, runner=Runner(timeout=True))
    timeout = timed.complete(
        "claude_code",
        history(),
        persona_guidance="Plain.",
        outbound=public_context(history(), "Plain."),
    )
    assert timeout.status == "timeout" and timeout.code == "backend_timeout"
    missing = timed.complete(
        "copilot",
        history(),
        persona_guidance="Plain.",
        outbound=public_context(history(), "Plain."),
    )
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
    failed = backends.complete(
        "claude_code",
        history(),
        persona_guidance="Plain.",
        outbound=public_context(history(), "Plain."),
    )
    assert failed.status == "failed" and failed.code == "backend_authentication_failed"
    status = {item.name: item for item in backends.statuses(gateway_available=False)}
    assert status["claude_code"].available is False
    assert "sign in" in status["claude_code"].detail.lower()


def test_unclassified_or_incomplete_context_never_reaches_cli(tmp_path: Path) -> None:
    runner = Runner(json.dumps({"result": "Should never be returned."}))
    backends = LocalConversationBackends(tmp_path, which=installed, runner=runner)
    missing = backends.complete("claude_code", history(), persona_guidance="Private persona")
    assert missing.status == "unavailable" and missing.code == "context_missing"
    incomplete = OutboundContext(
        materials=(
            ContextMaterial(
                material_id="message-1",
                origin="history",
                classification="PUBLIC",
                classified_by="engineer",
                text=history()[0].text,
            ),
        )
    )
    mismatch = backends.complete(
        "claude_code", history(), persona_guidance="Private persona", outbound=incomplete
    )
    assert mismatch.code == "context_mismatch"
    unclassified = OutboundContext(
        materials=(
            ContextMaterial(material_id="message-1", origin="history", text=history()[0].text),
            ContextMaterial(material_id="persona-1", origin="persona", text="Private persona"),
        )
    )
    denied = backends.complete(
        "claude_code", history(), persona_guidance="Private persona", outbound=unclassified
    )
    assert denied.code == "native_requires_public"
    assert runner.calls == []


def test_a_chinese_cli_answer_is_read_as_utf8_not_the_console_code_page(tmp_path: Path) -> None:
    """2026-10-08: a cp950 reader thread failed on a CLI's UTF-8 answer and the
    turn crashed with stdout None."""
    import sys

    from host_runtime.conversation_backends import _answer, _run_process

    done = _run_process(
        [sys.executable, "-c", "import sys; sys.stdout.buffer.write('答案\u00a0完成'.encode())"],
        cwd=tmp_path,
        input="",
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
        env=dict(__import__("os").environ),
    )
    assert done.stdout == "答案 完成"
    assert _answer(None) == ""


def test_copilot_agent_gets_aep_tools_without_excluding_it_tools(
    tmp_path: Path,
) -> None:
    from host_runtime.conversation_backends import AGENT_MCP_FILE, AGENT_TIMEOUT_SECONDS

    def with_copilot(name: str) -> str | None:
        return "C:/fixed/copilot.exe" if name == "copilot" else installed(name)

    runner = Runner(json.dumps({"result": "CMX500 needs option KM606 (wiki/entities/x.md)."}))
    backends = LocalConversationBackends(tmp_path, which=with_copilot, runner=runner)
    context = public_context(history(), "Speak plainly.")
    early = backends.complete(
        "copilot_agent", history(), persona_guidance="Speak plainly.", outbound=context
    )
    # Without a running Agent Web there are no tools to give it.
    assert (early.status, early.code) == ("unavailable", "assistant_tools_unavailable")
    backends.agent_mcp = ("http://127.0.0.1:5000/mcp", "assistant-token")
    result = backends.complete(
        "copilot_agent", history(), persona_guidance="Speak plainly.", outbound=context
    )
    argv, call = runner.calls[0]
    assert result.status == "answered" and "KM606" in result.text
    assert not any(arg.startswith(("--allow-tool", "--deny-tool")) for arg in argv)
    assert "--disable-builtin-mcps" not in argv
    config_arg = argv[argv.index("--additional-mcp-config") + 1]
    config = json.loads(
        (tmp_path / ".conversation-backends" / AGENT_MCP_FILE).read_text(encoding="utf-8")
    )
    servers = config["mcpServers"]
    assert config_arg.startswith("@") and servers["aep-assistant"]["url"].endswith("/mcp")
    assert servers["aep-assistant"]["headers"]["Authorization"] == "Bearer assistant-token"
    # The authoring tools come from the same Agent Web, with the same token.
    assert servers["aep"]["url"] == "http://127.0.0.1:5000/mcp/authoring"
    assert servers["aep"]["headers"] == servers["aep-assistant"]["headers"]
    assert "aep-assistant" in servers
    # AEP's skills are in the agent's trusted working folder.
    root = tmp_path / ".conversation-backends"
    assert argv[argv.index("--add-dir") + 1] == str(root)
    for name in ("aep-workflow-creator", "aep-skill-creator", "aep-knowledge"):
        assert (root / ".github" / "skills" / name / "SKILL.md").is_file()
    assert "aep-workflow-creator" in call["input"]
    assert "aep_knowledge_search" in call["input"] and "Do not use tools" not in call["input"]
    assert call["timeout"] == AGENT_TIMEOUT_SECONDS
    statuses = {item.name: item for item in backends.statuses(gateway_available=True)}
    # Listed for the person to choose; like copilot, it asks for a sign-in first.
    assert statuses["copilot_agent"].selectable is True
    assert statuses["copilot_agent"].action == "authenticate"


def test_backends_keep_it_configuration_and_builtin_tool_discovery() -> None:
    """The user-level AEP setup (agent_setup.py) is for the person's own sessions.
    The text-only chat backends stay tool-less (2026-10-02 backend rule): they
    ignore user MCP servers and settings; only the Copilot agent mode gets
    AEP's tools and skills, passed explicitly."""
    from host_runtime.conversation_backends import SPECS

    arguments = {spec.name: spec.arguments for spec in SPECS}
    assert {"--strict-mcp-config", "--restricted", "--safe-mode", "--tools"}.isdisjoint(
        arguments["claude_code"]
    )
    assert "--ignore-user-config" not in arguments["codex"]
    assert "--sandbox" not in arguments["codex"]
    assert "--available-tools=" not in arguments["copilot"]
