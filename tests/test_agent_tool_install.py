"""An agent connects a fixture MCP server and uses it without a restart/card."""

import asyncio
import hashlib
import sys
from pathlib import Path
from typing import Any

import pytest
from test_mcp_servers import FAKE_SERVER, context, hub_with

from agent.gateway import HostTool, HostToolOutcome
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
            _reply(("tools__catalog", {"query": "validate-release"})),
            _reply(
                (
                    "tools__invoke",
                    {
                        "target": "engineering/validate-release@1.0.0",
                        "arguments": {"args": "fixture"},
                    },
                )
            ),
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
    existing = Handler()
    built = gateway(existing, model)
    hub = McpHub(tmp_path, built.bridge.installed, lambda: built.bridge.policy, "engineer")
    access = ToolAccess(built.bridge, mcp=hub)
    built.host_tools = access.tools
    message = "Use the installed validator, then connect and use the fixture tool"
    try:
        result = asyncio.run(
            built.converse(request(message), (ModelMessage(role="user", text=message),))
        )
        assert result.status == "answered" and len(result.tools) == 5
        assert all(item.host and item.host.status == "succeeded" for item in result.tools)
        assert existing.calls == 1
        existing_result = result.tools[1].host
        assert existing_result and result_data(existing_result)["validated"] is True
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


def test_native_turn_install_retry_reuses_the_connection_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from agent.turn_effects import turn_scope

    script = tmp_path / "fixture.py"
    script.write_text(FAKE_SERVER, encoding="utf-8")
    hub, bridge, _ = hub_with(tmp_path)
    access = ToolAccess(bridge, mcp=hub)
    saved = []
    original = hub.save

    def save(*args: Any, **kwargs: Any) -> None:
        saved.append(1)
        original(*args, **kwargs)

    monkeypatch.setattr(hub, "save", save)
    config = {
        "name": "fixture",
        "transport": "stdio",
        "command": sys.executable,
        "args": [str(script)],
        "timeout_seconds": 10,
    }
    try:
        with turn_scope():
            first = asyncio.run(access.install_mcp(context(), config))
            again = asyncio.run(access.install_mcp(context(), config))
            assert first.status == again.status == "succeeded"
            assert saved == [1]
            assert isinstance(again.data, dict) and again.data["replayed"] is True
    finally:
        hub.close()


def test_stdio_close_delivers_eof_and_redacts_fixture_stderr(tmp_path: Path) -> None:
    import time

    from integrations.mcp_client import StdioMcpClient

    marker = tmp_path / "closed.txt"
    script = tmp_path / "close_fixture.py"
    script.write_text(
        "import sys\nfrom pathlib import Path\n"
        "print('password=synthetic-mcp-only', file=sys.stderr, flush=True)\n"
        "for line in sys.stdin: pass\nPath(sys.argv[1]).write_text('closed')\n",
        encoding="utf-8",
    )
    log = tmp_path / "mcp.log"
    client = StdioMcpClient(sys.executable, (str(script), str(marker)), log=log)
    client._start()
    time.sleep(0.2)
    client.close()
    deadline = time.monotonic() + 3
    while not marker.exists() and time.monotonic() < deadline:
        time.sleep(0.02)
    assert marker.read_text() == "closed"
    assert "synthetic-mcp-only" not in log.read_text(encoding="utf-8")
    assert "[redacted]" in log.read_text(encoding="utf-8")


def test_normalized_and_truncated_mcp_names_never_dispatch_another_tool(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from capabilities.mcp import MCPCallResult

    canonical_clone = "a-b-" + hashlib.sha256(b"a.b").hexdigest()[:24]
    alias_clone = "a_b-" + hashlib.sha256(b'["fixture", "a.b"]').hexdigest()[:24]
    names = ("a.b", "a_b", "a-b", canonical_clone, alias_clone, "x" * 100 + "a", "x" * 100 + "b")

    class Client:
        calls: list[str] = []

        def list_tools_sync(self) -> list[dict[str, Any]]:
            return [{"name": name, "inputSchema": {"type": "object"}} for name in names]

        async def call_tool(self, name: str, arguments: dict[str, Any]) -> MCPCallResult:
            self.calls.append(name)
            return MCPCallResult(data={"text": name})

        def close(self) -> None:
            pass

    client = Client()
    hub, bridge, _ = hub_with(tmp_path)
    monkeypatch.setattr(hub, "_client", lambda config: client)
    from host_runtime.mcp_servers import McpServerConfig

    try:
        hub.save(
            McpServerConfig(name="fixture", transport="stdio", command="fixture"), {}, connect=False
        )
        hub.connect("fixture")
        advertised = hub.status()[0]["tools"]
        assert len({tool["capability"] for tool in advertised}) == len(names)
        tools = hub.tools(bridge)
        assert len({tool.tool.name for tool in tools}) == len(names)
        for name, tool in zip(names, tools, strict=True):

            async def invoke(selected: HostTool = tool) -> HostToolOutcome:
                return await selected.handler(context(), {})

            result = asyncio.run(invoke())
            assert result.status == "succeeded"
            assert isinstance(result.data, dict) and result.data["text"] == name
        assert client.calls == list(names)
    finally:
        hub.close()


def test_mcp_install_collision_does_not_claim_or_remove_an_existing_binding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from test_dispatch import Handler, Input, Output, spec

    from capabilities.contracts import CapabilitySpec
    from common.assets import ExecutionDependencies
    from host_runtime.mcp_servers import McpHub, McpServerConfig

    hub, bridge, _ = hub_with(tmp_path)
    identity = McpHub.identity("fixture", "echo")
    raw = spec().model_dump(mode="json")
    raw["identity"] = identity.model_dump(mode="json")
    bridge.installed.register(
        CapabilitySpec.model_validate(raw),
        Handler(),
        Input,
        Output,
        ExecutionDependencies(central_required=False),
    )
    original = bridge.installed.get(identity)

    class Client:
        def list_tools_sync(self) -> list[dict[str, Any]]:
            return [{"name": "echo", "inputSchema": {"type": "object"}}]

        def close(self) -> None:
            pass

    monkeypatch.setattr(hub, "_client", lambda config: Client())
    try:
        hub.save(
            McpServerConfig(name="fixture", transport="stdio", command="fixture"), {}, connect=False
        )
        hub.connect("fixture")
        assert hub.status()[0]["status"] == "failed"
    finally:
        hub.close()
    assert bridge.installed.get(identity) is original
