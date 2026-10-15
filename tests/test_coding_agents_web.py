"""Agent Web side of the default coding agent setup (owner 2026-10-15):
the assistant bridge, the authoring tools at `/mcp/authoring`, and the
Settings "Coding agents" card. Temporary homes only."""

from __future__ import annotations

import io
import json
import os
import time
from pathlib import Path
from typing import Any

import pytest
from test_agent_web import base, fetch
from test_assistant_tools import served  # noqa: F401 - the fixture
from test_chat_workflow_forms_web import _browser_missing

from host_runtime import assistant_tools
from host_runtime.agent_setup import Environment, status
from host_runtime.assistant_bridge import NOT_RUNNING, Bridge
from host_runtime.launcher import write_record
from host_runtime.web import AgentWebServer


def _call(name: str, arguments: dict[str, Any] | None = None, ident: int = 3) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": ident,
        "method": "tools/call",
        "params": {"name": name, "arguments": arguments or {}},
    }


def test_the_bridge_answers_alone_and_says_when_agent_web_is_not_running(
    tmp_path: Path,
) -> None:
    bridge = Bridge(tmp_path, "test")
    source = io.BytesIO(
        b"\n".join(
            json.dumps(m).encode()
            for m in (
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {"protocolVersion": "2025-06-18"},
                },
                {"jsonrpc": "2.0", "method": "notifications/initialized"},
                {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
                _call("aep_knowledge_search", {"query": "CMX500"}),
            )
        )
        + b"\n"
    )
    sink = io.BytesIO()
    bridge.serve(source, sink)
    replies = [json.loads(line) for line in sink.getvalue().splitlines()]
    assert [r["id"] for r in replies] == [1, 2, 3]
    assert replies[0]["result"]["serverInfo"]["name"] == "aep-assistant"
    assert {t["name"] for t in replies[1]["result"]["tools"]} == set(assistant_tools.TOOLS)
    assert replies[2]["result"]["isError"] is True
    assert replies[2]["result"]["content"][0]["text"] == NOT_RUNNING


def test_the_bridge_reads_the_address_and_token_at_call_time(tmp_path: Path) -> None:
    seen: list[tuple[str, dict[str, str]]] = []

    def post(url: str, body: bytes, headers: dict[str, str], timeout: float) -> bytes:
        seen.append((url, headers))
        message = json.loads(body)
        return json.dumps(
            {
                "jsonrpc": "2.0",
                "id": message["id"],
                "result": {"content": [], "structuredContent": {"ok": True}},
            }
        ).encode()

    bridge = Bridge(tmp_path, "test", post=post)
    (tmp_path / assistant_tools.TOKEN_FILE).write_text("t" * 40, encoding="utf-8")
    write_record(tmp_path, "http://127.0.0.1:50001/?token=session", 50001)
    answered = bridge.handle(_call("aep_workflows"))
    assert answered is not None
    assert answered["result"]["structuredContent"] == {"ok": True}
    # Agent Web restarted on another port: the next call follows it.
    write_record(tmp_path, "http://127.0.0.1:50002/?token=other", 50002)
    bridge.handle(_call("aep_workflows"))
    assert [url for url, _ in seen] == ["http://127.0.0.1:50001/mcp", "http://127.0.0.1:50002/mcp"]
    assert seen[0][1]["Authorization"] == "Bearer " + "t" * 40
    # Never anywhere but the loopback address.
    write_record(tmp_path, "http://10.0.0.5:50003/?token=x", 50003)
    failed = bridge.handle(_call("aep_workflows"))
    assert failed is not None
    assert failed["result"]["isError"] is True


def test_the_bridge_reaches_a_real_agent_web(served: AgentWebServer) -> None:  # noqa: F811
    workspace = served.web.runtime.layout.workspace_root
    served.web.assistant_token  # noqa: B018 - Agent Web keeps its token in the workspace
    write_record(workspace, served.address, served.server_address[1])
    reply = Bridge(workspace, "test").handle(_call("aep_workflows"))
    assert reply is not None
    listed = reply["result"]["structuredContent"]["workflows"]
    assert listed and {"workflow", "read_only", "parameters"} <= set(listed[0])


def test_agent_web_serves_the_authoring_tools_with_the_assistant_token(
    served: AgentWebServer,  # noqa: F811
) -> None:
    url = base(served) + "/mcp/authoring"
    listing = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
    assert fetch(url, token=None, body=listing).status == 401
    token = served.web.assistant_token
    tools = json.loads(fetch(url, token=token, body=listing).body)["result"]["tools"]
    assert {"aep_catalog", "aep_capability", "aep_workflow_format", "aep_check_workflow"} <= {
        t["name"] for t in tools
    }
    catalog = json.loads(fetch(url, token=token, body=_call("aep_catalog")).body)
    content = catalog["result"]["structuredContent"]
    assert content["actor"] and isinstance(content["capabilities"], list)


def test_settings_lists_installs_and_removes_for_a_coding_agent(
    served: AgentWebServer,  # noqa: F811
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    environment = Environment(
        home, {}, which=lambda n: "C:/bin/claude.exe" if n == "claude" else None
    )
    served.web.agent_environment = environment  # type: ignore[attr-defined]
    listed = json.loads(fetch(base(served) + "/api/coding-agents", token=served.token).body)
    agents = {a["agent"]: a for a in listed["agents"]}
    assert agents["claude-code"]["detected"] and not agents["codex"]["detected"]
    assert not agents["claude-code"]["installed"]
    # Without the host.json path there is nothing to point the servers at.
    refused = fetch(
        base(served) + "/api/coding-agents/install",
        token=served.token,
        body={"agent": "claude-code"},
    )
    assert refused.status == 409
    served.web.config_path = tmp_path / "host.json"
    done = json.loads(
        fetch(
            base(served) + "/api/coding-agents/install",
            token=served.token,
            body={"agent": "claude-code"},
        ).body
    )
    assert done["ok"] and "Claude Code: installed/updated" in done["lines"]
    assert status("claude-code", environment)["current"]
    assert (
        fetch(
            base(served) + "/api/coding-agents/install",
            token=served.token,
            body={"agent": "nobody"},
        ).status
        == 409
    )
    removed = json.loads(
        fetch(
            base(served) + "/api/coding-agents/remove",
            token=served.token,
            body={"agent": "claude-code"},
        ).body
    )
    assert removed["ok"] and not status("claude-code", environment)["installed"]


@pytest.mark.skipif(_browser_missing(), reason="no Chromium browser is installed")
def test_the_coding_agents_card_renders_in_a_real_browser(
    served: AgentWebServer,  # noqa: F811
    tmp_path: Path,
) -> None:
    from integrations.browser import Browser

    home = tmp_path / "home"
    home.mkdir()
    served.web.agent_environment = Environment(  # type: ignore[attr-defined]
        home, {}, which=lambda n: "C:/bin/x.exe" if n in ("claude", "copilot") else None
    )
    served.web.config_path = tmp_path / "host.json"
    browser = Browser(tmp_path / "browser", timeout_s=60)
    browser.start()

    def wait(expression: str, seconds: float = 30) -> object:
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            value = browser._evaluate(expression)
            if value:
                return value
            time.sleep(0.2)
        raise AssertionError(expression)

    def measure(selector: str) -> list[int]:
        size: list[int] = json.loads(
            str(
                browser._evaluate(
                    "JSON.stringify((() => { const r = document.querySelector("
                    + json.dumps(selector)
                    + ").getBoundingClientRect();"
                    " return [Math.round(r.width), Math.round(r.height)]; })())"
                )
            )
        )
        return size

    try:
        browser.navigate(served.address)
        wait('!!document.getElementById("nav-settings")')
        browser._evaluate('document.getElementById("nav-settings").click()')
        wait('document.querySelectorAll("#coding-agents .approval-card").length === 3')
        width, height = measure("#coding-agents-card")
        assert width >= 280 and height >= 300, (width, height)
        card = '#coding-agents [data-agent="claude-code"]'
        assert "found on this computer" in str(
            browser._evaluate(f"document.querySelector({json.dumps(card)}).innerText")
        )
        button = card + " button.go"
        assert (
            browser._evaluate(f"document.querySelector({json.dumps(button)}).innerText")
            == "Install"
        )
        bw, bh = measure(button)
        assert bw >= 44 and bh >= 28, (bw, bh)
        browser._evaluate(f"document.querySelector({json.dumps(button)}).click()")
        wait(
            'document.getElementById("coding-agents-result").innerText'
            '.includes("Claude Code: installed/updated")'
        )
        wait(f'document.querySelector({json.dumps(button)}).innerText === "Reinstall"')
        assert (home / ".claude" / "skills" / "aep-knowledge" / "SKILL.md").is_file()
        print(f"coding agents card {width}x{height}, Install {bw}x{bh}")
        shots = os.environ.get("AEP_UI_SHOTS")
        if shots:
            browser.screenshot(Path(shots) / "coding-agents-card.png")
    finally:
        browser.close()
        browser.discard_profile()


def test_the_bridge_starts_even_when_host_json_is_unreadable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from host_runtime.cli import main

    source = io.BytesIO(
        (
            json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
            + "\n"
            + json.dumps(_call("aep_workflows"))
            + "\n"
        ).encode()
    )
    sink = io.BytesIO()
    monkeypatch.setattr("sys.stdin", type("In", (), {"buffer": source})())
    monkeypatch.setattr("sys.stdout", type("Out", (), {"buffer": sink})())
    assert main(["assistant-mcp", "--config", str(tmp_path / "missing.json")]) == 0
    listed, called = [json.loads(line) for line in sink.getvalue().splitlines()]
    assert listed["result"]["tools"]
    assert (
        called["result"]["isError"] and "cannot be read" in called["result"]["content"][0]["text"]
    )
