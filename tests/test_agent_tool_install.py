"""An agent connects a fixture MCP server and uses it without a restart/card."""

import asyncio
import sys
from pathlib import Path
from typing import Any

import pytest
from test_mcp_servers import FAKE_SERVER, context, hub_with

from agent.gateway import HostToolOutcome
from host_runtime.tool_access import ToolAccess


def result_data(outcome: HostToolOutcome) -> dict[str, Any]:
    assert isinstance(outcome.data, dict)
    result = outcome.data["result"]
    assert isinstance(result, dict)
    return result


def test_agent_connects_and_invokes_in_the_same_session(tmp_path: Path) -> None:
    script = tmp_path / "fixture.py"
    script.write_text(FAKE_SERVER, encoding="utf-8")
    hub, bridge, stored = hub_with(tmp_path)
    access = ToolAccess(bridge, mcp=hub)
    try:
        installed = asyncio.run(
            access.install_mcp(
                context(),
                {
                    "name": "fixture",
                    "transport": "stdio",
                    "command": sys.executable,
                    "args": [str(script)],
                    "timeout_seconds": 10,
                },
            )
        )
        assert installed.status == "succeeded"
        assert stored == {}
        target = "mcp-fixture/echo@1.0.0"
        assert access.catalog(query="mcp-fixture echo")["total"] == 1
        result = asyncio.run(access.invoke(context(), target, {"text": "same-session"}))
        assert result.status == "succeeded"
        assert isinstance(result.data, dict)
        assert result_data(result)["text"] == "echo: same-session"
        binding = bridge.installed.get(hub.identity("fixture", "echo"))
        assert binding and not binding.spec.policy.approval_required
        assert binding.spec.policy.policy_refs == ()
        assert not list(tmp_path.rglob("ap-*.json"))
    finally:
        hub.close()


def test_mcp_replacement_refreshes_schema_and_disable_removes_stale_tool(tmp_path: Path) -> None:
    script = tmp_path / "fixture.py"
    script.write_text(FAKE_SERVER, encoding="utf-8")
    hub, bridge, _ = hub_with(tmp_path)
    access = ToolAccess(bridge, mcp=hub)
    config = {
        "name": "fixture",
        "transport": "stdio",
        "command": sys.executable,
        "args": [str(script)],
        "timeout_seconds": 10,
    }
    try:
        first = asyncio.run(access.install_mcp(context(), config))
        assert first.status == "succeeded"
        script.write_text(
            FAKE_SERVER.replace('"text": {"type": "string"}', '"word": {"type": "string"}').replace(
                '["text"]', '["word"]'
            ),
            encoding="utf-8",
        )
        second = asyncio.run(access.install_mcp(context(), config))
        assert second.status == "succeeded"
        described = access.describe("mcp-fixture/echo@1.0.0")
        assert "word" in described["tool"]["input_schema"]["properties"]
        assert "text" not in described["tool"]["input_schema"]["properties"]
        result = asyncio.run(access.invoke(context(), "mcp-fixture/echo@1.0.0", {"word": "fresh"}))
        assert result.status == "succeeded"
        disabled = asyncio.run(access.install_mcp(context(), {**config, "enabled": False}))
        assert disabled.status == "succeeded"
        assert access.catalog(query="mcp-fixture")["total"] == 0
    finally:
        hub.close()


@pytest.mark.parametrize(
    "config",
    [
        {"name": "bad", "transport": "stdio", "command": "aep-nonexistent-fixture-executable-2030"},
        {"name": "bad", "transport": "unsupported"},
    ],
)
def test_installation_failures_are_not_success(tmp_path: Path, config: dict[str, str]) -> None:
    hub, bridge, _ = hub_with(tmp_path)
    try:
        result = asyncio.run(ToolAccess(bridge, mcp=hub).install_mcp(context(), config))
        assert result.status == "failed" and result.failure
        assert not list(tmp_path.rglob("ap-*.json"))
    finally:
        hub.close()


def test_one_conversation_installs_discovers_and_invokes_without_restart(tmp_path: Path) -> None:
    from test_gateway import Handler, gateway, request
    from test_turn_effects import Scripted, _reply

    from host_runtime.mcp_servers import McpHub
    from models.contracts import ModelMessage

    script = tmp_path / "fixture.py"
    script.write_text(FAKE_SERVER, encoding="utf-8")
    model = Scripted(
        [
            _reply(
                (
                    "tools__install_mcp",
                    {
                        "config": {
                            "name": "fixture",
                            "transport": "stdio",
                            "command": sys.executable,
                            "args": [str(script)],
                            "timeout_seconds": 10,
                        }
                    },
                )
            ),
            _reply(("tools__catalog", {"query": "mcp-fixture echo"})),
            _reply(
                (
                    "tools__invoke",
                    {"target": "mcp-fixture/echo@1.0.0", "arguments": {"text": "one-turn"}},
                )
            ),
            _reply(text="fixture completed"),
        ]
    )
    built = gateway(Handler(), model)
    hub = McpHub(tmp_path, built.bridge.installed, lambda: built.bridge.policy, "engineer")
    access = ToolAccess(built.bridge, mcp=hub)
    built.host_tools = access.tools
    message = "Install and use the fixture tool"
    try:
        result = asyncio.run(
            built.converse(request(message), (ModelMessage(role="user", text=message),))
        )
        assert result.status == "answered" and len(result.tools) == 3
        assert all(item.host and item.host.status == "succeeded" for item in result.tools)
        final = result.tools[-1].host
        assert final and result_data(final)["text"] == "echo: one-turn"
        assert not list(tmp_path.rglob("ap-*.json"))
    finally:
        hub.close()


def test_mcp_error_result_is_a_failed_execution_with_real_diagnostics(tmp_path: Path) -> None:
    script = tmp_path / "fixture.py"
    script.write_text(
        FAKE_SERVER.replace('"text": "echo: " + args["text"]', '"text": "fixture failure"').replace(
            'result = {"content": [{"type": "text", "text": "fixture failure"}]}',
            'result = {"isError": True, "content": [{"type": "text", "text": "fixture failure"}]}',
        ),
        encoding="utf-8",
    )
    hub, bridge, _ = hub_with(tmp_path)
    access = ToolAccess(bridge, mcp=hub)
    try:
        installed = asyncio.run(
            access.install_mcp(
                context(),
                {
                    "name": "fixture",
                    "transport": "stdio",
                    "command": sys.executable,
                    "args": [str(script)],
                    "timeout_seconds": 10,
                },
            )
        )
        assert installed.status == "succeeded"
        result = asyncio.run(access.invoke(context(), "mcp-fixture/echo@1.0.0", {"text": "unused"}))
        assert (
            result.status == "failed" and result.failure and result.failure.code == "mcp_tool_error"
        )
        assert result_data(result)["text"] == "fixture failure"
    finally:
        hub.close()


def test_agent_connects_http_and_invokes_the_same_bridge_target(tmp_path: Path) -> None:
    import threading
    from http.server import ThreadingHTTPServer

    from test_mcp_servers import Remote

    server = ThreadingHTTPServer(("127.0.0.1", 0), Remote)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    hub, bridge, _ = hub_with(tmp_path)
    access = ToolAccess(bridge, mcp=hub)
    try:
        connected = asyncio.run(
            access.install_mcp(
                context(),
                {
                    "name": "remote",
                    "transport": "http",
                    "url": f"http://127.0.0.1:{server.server_address[1]}/mcp",
                },
            )
        )
        assert connected.status == "succeeded"
        outcome = asyncio.run(access.invoke(context(), "mcp-remote/time@1.0.0", {}))
        assert outcome.status == "succeeded"
        assert result_data(outcome)["structured"] == {"hour": 12}
    finally:
        hub.close()
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
