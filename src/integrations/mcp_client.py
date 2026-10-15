"""MCP clients for the Bridge: a local command over stdio, or a remote server
over Streamable HTTP (owner 2026-10-08).

Each normalizes the protocol into `capabilities.mcp.MCPClient`: initialize
once, list tools, call a tool. Requests on one server go one at a time.
Nothing here decides what a tool may do; the host binds each tool as a Bridge
capability under the owner's grants.
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import threading
import urllib.error
import urllib.request
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from pydantic import JsonValue

from capabilities.mcp import MCPCallResult, MCPTool

PROTOCOL_VERSION = "2025-06-18"
CLIENT_INFO = {"name": "aep-bridge", "version": "1"}
MAX_RESULT_CHARS = 60_000


class McpError(Exception):
    """A stable code and a message with no secret in it."""

    def __init__(self, code: str, message: str = "") -> None:
        self.code = code
        super().__init__(message or code)


def _result(raw: dict[str, Any]) -> MCPCallResult:
    """A tool's answer as data the model and a Workflow can read."""
    found = raw.get("content")
    content: list[Any] = found if isinstance(found, list) else []
    texts = [
        item.get("text", "")
        for item in content
        if isinstance(item, dict) and item.get("type") == "text"
    ]
    others = [
        {k: v for k, v in item.items() if k != "data"}
        for item in content
        if isinstance(item, dict) and item.get("type") != "text"
    ]
    data: dict[str, JsonValue] = {"text": "\n".join(texts)[:MAX_RESULT_CHARS]}
    if others:
        data["other_content"] = json.loads(json.dumps(others[:20], default=str))
    if raw.get("structuredContent") is not None:
        data["structured"] = raw["structuredContent"]
    return MCPCallResult(data=data, is_error=bool(raw.get("isError")))


def _tools(raw: dict[str, Any]) -> list[dict[str, Any]]:
    tools = raw.get("tools")
    return [item for item in tools if isinstance(item, dict)] if isinstance(tools, list) else []


class _Session:
    """What both transports share: ids, the handshake, the tool calls."""

    def __init__(self, timeout_seconds: float) -> None:
        self.timeout_seconds = timeout_seconds
        self._lock = threading.Lock()
        self._next_id = 0
        self._ready = False
        self.server_info: dict[str, Any] = {}
        self.listed: list[dict[str, Any]] = []

    def _request(self, method: str, params: dict[str, Any] | None) -> dict[str, Any]:
        raise NotImplementedError

    def _notify(self, method: str) -> None:
        raise NotImplementedError

    def _id(self) -> int:
        self._next_id += 1
        return self._next_id

    def _ensure(self) -> None:
        if self._ready:
            return
        answer = self._request(
            "initialize",
            {"protocolVersion": PROTOCOL_VERSION, "capabilities": {}, "clientInfo": CLIENT_INFO},
        )
        self.server_info = answer.get("serverInfo") or {}
        self._notify("notifications/initialized")
        self._ready = True

    def list_tools_sync(self) -> list[dict[str, Any]]:
        with self._lock:
            self._ensure()
            found: list[dict[str, Any]] = []
            cursor: str | None = None
            for _ in range(20):
                answer = self._request("tools/list", {"cursor": cursor} if cursor else {})
                found.extend(_tools(answer))
                cursor = answer.get("nextCursor")
                if not cursor:
                    break
            self.listed = found
            return found

    def call_sync(self, name: str, arguments: dict[str, JsonValue]) -> MCPCallResult:
        with self._lock:
            self._ensure()
            return _result(self._request("tools/call", {"name": name, "arguments": arguments}))

    async def list_tools(self) -> tuple[MCPTool, ...]:
        raw = await asyncio.to_thread(self.list_tools_sync)
        return tuple(
            MCPTool(
                name=str(item.get("name")),
                description=str(item.get("description") or ""),
                input_schema=item.get("inputSchema") or {},
            )
            for item in raw
            if item.get("name")
        )

    async def call_tool(self, name: str, arguments: dict[str, JsonValue]) -> MCPCallResult:
        return await asyncio.to_thread(self.call_sync, name, arguments)

    def close(self) -> None:
        self._ready = False


class StdioMcpClient(_Session):
    """A local MCP server: one long-lived process, JSON-RPC lines on stdio."""

    def __init__(
        self,
        command: str,
        args: tuple[str, ...],
        *,
        env: Mapping[str, str] | None = None,
        cwd: str | None = None,
        timeout_seconds: float = 60.0,
        log: Path | None = None,
    ) -> None:
        super().__init__(timeout_seconds)
        self.command, self.args = command, args
        self.env = dict(env or {})
        self.cwd = cwd
        self.log = log
        self._process: subprocess.Popen[bytes] | None = None
        self._replies: dict[int, dict[str, Any]] = {}
        self._arrived = threading.Condition()

    def _start(self) -> subprocess.Popen[bytes]:
        if self._process is not None and self._process.poll() is None:
            return self._process
        self._ready = False
        executable = shutil.which(self.command) or self.command
        stderr: Any = subprocess.DEVNULL
        if self.log is not None:
            self.log.parent.mkdir(parents=True, exist_ok=True)
            stderr = self.log.open("ab")
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        try:
            process = subprocess.Popen(
                [executable, *self.args],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=stderr,
                cwd=self.cwd,
                env={**os.environ, **self.env},
                creationflags=flags,
            )
        except OSError as error:
            raise McpError(
                "mcp_start_failed", f"could not start {self.command}: {type(error).__name__}"
            ) from None
        self._process = process
        threading.Thread(target=self._read, args=(process,), daemon=True).start()
        return process

    def _read(self, process: subprocess.Popen[bytes]) -> None:
        assert process.stdout is not None
        for raw in process.stdout:
            try:
                message = json.loads(raw)
            except ValueError:
                continue  # a server that prints logs to stdout
            if (
                isinstance(message, dict)
                and isinstance(message.get("id"), int)
                and ("result" in message or "error" in message)
            ):
                with self._arrived:
                    self._replies[message["id"]] = message
                    self._arrived.notify_all()
        with self._arrived:
            self._arrived.notify_all()

    def _send(self, message: dict[str, Any]) -> None:
        process = self._start()
        assert process.stdin is not None
        try:
            process.stdin.write(json.dumps(message).encode("utf-8") + b"\n")
            process.stdin.flush()
        except OSError:
            raise McpError("mcp_server_exited", "the MCP server stopped") from None

    def _request(self, method: str, params: dict[str, Any] | None) -> dict[str, Any]:
        ident = self._id()
        self._send(
            {
                "jsonrpc": "2.0",
                "id": ident,
                "method": method,
                **({"params": params} if params is not None else {}),
            }
        )
        with self._arrived:
            done = self._arrived.wait_for(
                lambda: (
                    ident in self._replies
                    or (self._process is not None and self._process.poll() is not None)
                ),
                timeout=self.timeout_seconds,
            )
            reply = self._replies.pop(ident, None)
        if reply is None:
            raise McpError(
                "mcp_timeout" if not done else "mcp_server_exited", f"no answer to {method}"
            )
        if "error" in reply:
            error = reply["error"] if isinstance(reply["error"], dict) else {}
            raise McpError("mcp_error", str(error.get("message") or "the server refused")[:300])
        result = reply.get("result")
        return result if isinstance(result, dict) else {}

    def _notify(self, method: str) -> None:
        self._send({"jsonrpc": "2.0", "method": method})

    def close(self) -> None:
        super().close()
        process, self._process = self._process, None
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()


class HttpMcpClient(_Session):
    """A remote MCP server over Streamable HTTP: each request is one POST,
    answered as JSON or as an event stream carrying the reply."""

    def __init__(
        self, url: str, *, headers: Mapping[str, str] | None = None, timeout_seconds: float = 60.0
    ) -> None:
        super().__init__(timeout_seconds)
        self.url = url
        self.headers = dict(headers or {})
        self._session_id: str | None = None

    def _post(self, message: dict[str, Any]) -> tuple[int, str, bytes, Mapping[str, str]]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            **self.headers,
        }
        if self._ready:
            headers["MCP-Protocol-Version"] = PROTOCOL_VERSION
        if self._session_id:
            headers["Mcp-Session-Id"] = self._session_id
        request = urllib.request.Request(
            self.url, data=json.dumps(message).encode("utf-8"), headers=headers, method="POST"
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:  # noqa: S310 - configured URL
                return (
                    response.status,
                    response.headers.get("Content-Type", ""),
                    response.read(),
                    dict(response.headers),
                )
        except urllib.error.HTTPError as error:
            if error.code == 404 and self._session_id:
                self._session_id, self._ready = None, False  # the session expired
            raise McpError("mcp_http_error", f"the MCP server answered {error.code}") from None
        except (urllib.error.URLError, OSError, TimeoutError) as error:
            raise McpError(
                "mcp_unreachable", f"cannot reach the MCP server ({type(error).__name__})"
            ) from None

    def _request(self, method: str, params: dict[str, Any] | None) -> dict[str, Any]:
        ident = self._id()
        _, kind, body, headers = self._post(
            {
                "jsonrpc": "2.0",
                "id": ident,
                "method": method,
                **({"params": params} if params is not None else {}),
            }
        )
        session = next((v for k, v in headers.items() if k.lower() == "mcp-session-id"), None)
        if session:
            self._session_id = session
        reply: dict[str, Any] | None = None
        if "text/event-stream" in kind:
            for line in body.decode("utf-8", "replace").splitlines():
                if not line.startswith("data:"):
                    continue
                try:
                    event = json.loads(line[5:].strip())
                except ValueError:
                    continue
                if isinstance(event, dict) and event.get("id") == ident:
                    reply = event
        else:
            try:
                parsed = json.loads(body or b"{}")
            except ValueError:
                parsed = None
            reply = parsed if isinstance(parsed, dict) else None
        if reply is None:
            raise McpError("mcp_bad_reply", f"no usable answer to {method}")
        if "error" in reply:
            error = reply["error"] if isinstance(reply["error"], dict) else {}
            raise McpError("mcp_error", str(error.get("message") or "the server refused")[:300])
        result = reply.get("result")
        return result if isinstance(result, dict) else {}

    def _notify(self, method: str) -> None:
        try:
            self._post({"jsonrpc": "2.0", "method": method})
        except McpError:
            pass  # a server that does not acknowledge notifications still works
