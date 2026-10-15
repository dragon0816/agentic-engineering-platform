"""`aep-host assistant-mcp`: AEP's assistant tools for a coding agent, over stdio.

Owner 2026-10-15: Claude Code, Codex and Copilot must be able to use AEP's
Knowledge and installed Workflows by default. Agent Web serves those tools at
`POST /mcp` (`assistant_tools.py`), but its port can change between starts
and its token lives in the workspace. So the agent's configuration names this
small bridge instead of a URL: it answers `initialize` and `tools/list` itself
and forwards each `tools/call` to the running Agent Web, reading the address
(`agent-web.json`) and the assistant token (`assistant-mcp-token`) at call
time. No token is ever written into an agent's configuration, and a restart
of Agent Web needs nothing from the agent. When Agent Web is not running the
tool says so; the bridge does not start it.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import IO, Any
from urllib.parse import urlparse

from host_runtime.assistant_tools import INSTRUCTIONS, PROTOCOL_VERSIONS, TOKEN_FILE, TOOLS
from host_runtime.launcher import read_record

CALL_TIMEOUT_SECONDS = 300
NOT_RUNNING = (
    "AEP Agent Web is not running on this computer, so AEP's Knowledge and Workflows are not "
    "reachable. Ask the person to open it (the 'AEP Agent' shortcut, or `aep-host open "
    "--config <host.json>`), then try again. Do not answer from memory instead.")

Post = Callable[[str, bytes, dict[str, str], float], bytes]


def _post(url: str, body: bytes, headers: dict[str, str], timeout: float) -> bytes:
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - loopback
        return bytes(response.read())


def endpoint(workspace: Path) -> tuple[str, str] | None:
    """(MCP URL, token) of the Agent Web running for this workspace, or None."""
    record = read_record(workspace)
    if record is None:
        return None
    parsed = urlparse(str(record["address"]))
    if parsed.hostname not in ("127.0.0.1", "localhost", "::1") or parsed.port is None:
        return None
    try:
        token = (workspace / TOKEN_FILE).read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if not token:
        return None
    return f"http://127.0.0.1:{parsed.port}/mcp", token


class Bridge:
    def __init__(self, workspace: Path, version: str, post: Post = _post) -> None:
        self.workspace = workspace
        self.version = version
        self._post = post

    def _tool_error(self, ident: Any, text: str) -> dict[str, Any]:
        return _result(ident, {"content": [{"type": "text", "text": text}],
                               "structuredContent": {"ok": False, "code": "agent_web_unavailable"},
                               "isError": True})

    def handle(self, message: dict[str, Any]) -> dict[str, Any] | None:
        method = message.get("method")
        ident = message.get("id")
        params = message.get("params") or {}
        if ident is None:
            return None
        if method == "initialize":
            asked = str(params.get("protocolVersion") or "")
            return _result(ident, {
                "protocolVersion": asked if asked in PROTOCOL_VERSIONS else PROTOCOL_VERSIONS[0],
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "aep-assistant", "version": self.version},
                "instructions": INSTRUCTIONS,
            })
        if method == "ping":
            return _result(ident, {})
        if method == "tools/list":
            return _result(ident, {"tools": [
                {"name": name, "description": text, "inputSchema": schema}
                for name, (text, schema) in TOOLS.items()]})
        if method == "tools/call":
            found = endpoint(self.workspace)
            if found is None:
                return self._tool_error(ident, NOT_RUNNING)
            url, token = found
            body = json.dumps(message, ensure_ascii=False).encode("utf-8")
            try:
                raw = self._post(url, body, {"Content-Type": "application/json",
                                             "Authorization": f"Bearer {token}"},
                                 CALL_TIMEOUT_SECONDS)
                reply = json.loads(raw)
            except (urllib.error.URLError, OSError, ValueError):
                return self._tool_error(ident, NOT_RUNNING)
            return reply if isinstance(reply, dict) else self._tool_error(ident, NOT_RUNNING)
        return {"jsonrpc": "2.0", "id": ident,
                "error": {"code": -32601, "message": f"method not found: {method}"}}

    def serve(self, source: IO[bytes], sink: IO[bytes]) -> None:
        for raw in source:
            line = raw.strip()
            if not line:
                continue
            reply: dict[str, Any] | None
            try:
                message = json.loads(line)
            except ValueError:
                reply = {"jsonrpc": "2.0", "id": None,
                         "error": {"code": -32700, "message": "parse error"}}
            else:
                reply = self.handle(message) if isinstance(message, dict) else {
                    "jsonrpc": "2.0", "id": None,
                    "error": {"code": -32600, "message": "invalid request"}}
            if reply is not None:
                sink.write((json.dumps(reply, ensure_ascii=False) + "\n").encode("utf-8"))
                sink.flush()


def _result(ident: Any, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": ident, "result": result}
