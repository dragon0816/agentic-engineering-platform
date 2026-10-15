"""MCP servers added in Agent Web (owner 2026-10-08): stdio and Streamable
HTTP clients, tools bound as Bridge capabilities and granted, offered as
conversation tools, usable as Workflow steps, secrets kept out of files."""

from __future__ import annotations

import asyncio
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest
from pydantic import SecretStr
from test_agent_web import served  # noqa: F401 - the server fixture

from capabilities.runtime import CapabilityInvocation, InstalledCapabilities, LocalPolicy
from common.execution import RequestContext, TraceIdentifiers
from host_runtime.chat_authoring import ChatAuthoring
from host_runtime.mcp_servers import McpHub, McpServerConfig, secret_variable
from integrations.mcp_client import HttpMcpClient, StdioMcpClient
from workflow.dispatch import BridgeExecutor

FAKE_SERVER = r"""
import json, os, sys
TOOLS = [
    {"name": "echo", "description": "Echo text back.", "annotations": {"readOnlyHint": True},
     "inputSchema": {"type": "object", "properties": {"text": {"type": "string"}},
                     "required": ["text"]}},
    {"name": "secret_hint", "description": "Says whether the secret arrived.",
     "inputSchema": {"type": "object", "properties": {}}},
]
for line in sys.stdin:
    message = json.loads(line)
    if "id" not in message:
        continue
    method, ident = message["method"], message["id"]
    if method == "initialize":
        result = {"protocolVersion": "2025-06-18", "capabilities": {"tools": {}},
                  "serverInfo": {"name": "fake", "version": "1"}}
    elif method == "tools/list":
        result = {"tools": TOOLS}
    elif method == "tools/call":
        name, args = message["params"]["name"], message["params"]["arguments"]
        if name == "echo":
            result = {"content": [{"type": "text", "text": "echo: " + args["text"]}]}
        else:
            got = os.environ.get("FAKE_KEY") == "s3cret-value"
            result = {"content": [{"type": "text", "text": "secret ok" if got else "missing"}]}
    else:
        print(json.dumps({"jsonrpc": "2.0", "id": ident,
                          "error": {"code": -32601, "message": "nope"}}), flush=True)
        continue
    print(json.dumps({"jsonrpc": "2.0", "id": ident, "result": result}), flush=True)
"""


@pytest.fixture
def fake(tmp_path: Path) -> Path:
    script = tmp_path / "fake_mcp.py"
    script.write_text(FAKE_SERVER, encoding="utf-8")
    return script


def context() -> RequestContext:
    return RequestContext(
        trace=TraceIdentifiers(trace_id="t", request_id="r", span_id="s"),
        actor="owner",
        namespace="engineering",
        channel="local",
        message="x",
    )


def test_a_local_server_is_listed_and_called_over_stdio(fake: Path) -> None:
    client = StdioMcpClient(sys.executable, (str(fake),), timeout_seconds=20)
    try:
        tools = asyncio.run(client.list_tools())
        assert [tool.name for tool in tools] == ["echo", "secret_hint"]
        result = asyncio.run(client.call_tool("echo", {"text": "hi"}))
        assert result.data == {"text": "echo: hi"} and not result.is_error
    finally:
        client.close()


class Remote(BaseHTTPRequestHandler):
    sessions: list[str] = []

    def do_POST(self) -> None:  # noqa: N802 - base class spelling
        message = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        Remote.sessions.append(self.headers.get("Mcp-Session-Id") or "")
        if "id" not in message:
            self.send_response(202)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if message["method"] == "initialize":
            result: dict[str, Any] = {"protocolVersion": "2025-06-18", "capabilities": {}}
        elif message["method"] == "tools/list":
            result = {"tools": [{"name": "time", "inputSchema": {"type": "object"}}]}
        else:
            result = {
                "content": [{"type": "text", "text": "12:00"}],
                "structuredContent": {"hour": 12},
            }
        reply = {"jsonrpc": "2.0", "id": message["id"], "result": result}
        # Answer as an event stream, as Streamable HTTP servers may.
        body = f"event: message\ndata: {json.dumps(reply)}\n\n".encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Mcp-Session-Id", "session-42")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        return None


def test_a_remote_server_is_called_over_streamable_http() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 0), Remote)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        client = HttpMcpClient(
            f"http://127.0.0.1:{server.server_address[1]}/mcp", timeout_seconds=10
        )
        assert [t.name for t in asyncio.run(client.list_tools())] == ["time"]
        result = asyncio.run(client.call_tool("time", {}))
        assert result.data == {"text": "12:00", "structured": {"hour": 12}}
        assert Remote.sessions[0] == "" and Remote.sessions[-1] == "session-42"
    finally:
        server.shutdown()
        server.server_close()


def hub_with(tmp_path: Path) -> tuple[McpHub, BridgeExecutor, dict[str, str]]:
    installed = InstalledCapabilities()
    bridge = BridgeExecutor(installed, LocalPolicy(()))
    stored: dict[str, str] = {}
    hub = McpHub(
        tmp_path / "ws",
        installed,
        lambda: bridge.policy,
        "owner",
        store_secret=lambda name, value: stored.__setitem__(name, value),
    )
    (tmp_path / "ws").mkdir()
    return hub, bridge, stored


def test_adding_a_server_grants_its_tools_to_conversations_and_workflows(
    tmp_path: Path,
    fake: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hub, bridge, stored = hub_with(tmp_path)
    monkeypatch.delenv(secret_variable("fake", "FAKE_KEY"), raising=False)
    config = McpServerConfig(
        name="fake",
        transport="stdio",
        command=sys.executable,
        args=(str(fake),),
        secret_env=("FAKE_KEY",),
        timeout_seconds=20,
    )
    try:
        hub.save(config, {"FAKE_KEY": SecretStr("s3cret-value")})
        for _ in range(200):
            if hub.status()[0]["status"] != "connecting":
                break
            threading.Event().wait(0.05)
        (shown,) = hub.status()
        assert shown["status"] == "connected", shown["error"]
        assert [t["capability"] for t in shown["tools"]] == [
            "mcp-fake/echo@1.0.0",
            "mcp-fake/secret-hint@1.0.0",
        ]
        assert shown["secrets_present"] == {"FAKE_KEY": True}
        assert stored == {"AEP_MCP_FAKE_FAKE_KEY": "s3cret-value"}
        assert "s3cret-value" not in (tmp_path / "ws" / "mcp-servers.json").read_text()

        tools = {tool.tool.name: tool for tool in hub.tools(bridge)}
        assert set(tools) == {"mcp__fake__echo", "mcp__fake__secret_hint"}
        said = asyncio.run(tools["mcp__fake__echo"].handler(context(), {"text": "你好"}))
        assert said.status == "succeeded" and said.data["text"] == "echo: 你好"
        secret = asyncio.run(tools["mcp__fake__secret_hint"].handler(context(), {}))
        assert secret.data["text"] == "secret ok"  # write tool, granted by adding the server

        # The same tool as a Workflow step: drafting finds it installed.
        chat = ChatAuthoring(
            tmp_path / "chat",
            bridge=lambda: bridge,
            namespace="engineering",
            workflows_dir=tmp_path / "wf",
            grants_file=tmp_path / "g.json",
        )
        item, problems = chat.draft(
            "owner",
            None,
            "Echo",
            {
                "name": "echo-it",
                "description": "Echo.",
                "parameters": [],
                "steps": [
                    {
                        "capability": "mcp-fake/echo@1.0.0",
                        "inputs": {"text": {"source": "fixed", "value": "step"}},
                    }
                ],
            },
        )
        assert problems == [] and item is not None and chat.read_only(item.draft)

        hub.delete("fake")
        assert hub.tools(bridge) == [] and hub.status() == []
        gone = asyncio.run(
            bridge.execute(
                CapabilityInvocation(
                    context=context(),
                    target=McpHub.identity("fake", "echo"),
                    arguments={"text": "x"},
                )
            )
        )
        assert gone.status != "succeeded"
    finally:
        hub.close()


def test_a_server_that_cannot_start_is_a_status_not_a_crash(tmp_path: Path) -> None:
    hub, bridge, _ = hub_with(tmp_path)
    hub.save(
        McpServerConfig(name="broken", transport="stdio", command="definitely-not-a-command-aep"),
        {},
    )
    for _ in range(100):
        if hub.status()[0]["status"] != "connecting":
            break
        threading.Event().wait(0.05)
    (shown,) = hub.status()
    assert shown["status"] == "failed" and "mcp_start_failed" in shown["error"]
    assert hub.tools(bridge) == []


def test_settings_refuse_secrets_in_plain_fields() -> None:
    with pytest.raises(ValueError):
        McpServerConfig(
            name="x", transport="http", url="https://h/mcp", headers={"Authorization": "Bearer abc"}
        )
    with pytest.raises(ValueError):
        McpServerConfig(name="x", transport="http", url="ftp://h")
    with pytest.raises(ValueError):
        McpServerConfig(name="x", transport="stdio", command="")


def test_the_settings_page_lists_and_validates_mcp_servers(served: Any) -> None:  # noqa: F811
    from test_agent_web import base, fetch

    from host_runtime.web_page import PAGE

    url, token = base(served), served.token
    assert fetch(url + "/api/mcp", token=token).json() == {"servers": []}
    assert fetch(url + "/api/mcp").status == 401
    refused = fetch(
        url + "/api/mcp/save",
        token=token,
        body={"config": {"name": "x", "transport": "http", "url": "ftp://nowhere"}},
    )
    assert refused.status == 409 and refused.json()["code"] == "mcp_settings_invalid"
    assert 'id="mcp-form"' in PAGE and '"/api/mcp/" + action' in PAGE
