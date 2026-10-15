"""A minimal Agent Client Protocol client for Copilot's agent mode (owner 2026-10-15).

`copilot --acp` speaks ACP (JSON-RPC 2.0, one message per line on stdio).
Agent Web is the client: it starts a session in the conversation's working
folder with AEP's MCP servers, sends the prompt, collects the answer text and
answers every `session/request_permission` through the person's card
(`AgentMode.acp_permission`). This is the permission relay for Copilot; the
`-p` mode has none, which is why the text-only backend stays as it was.

Only what agent mode needs: no file-system or terminal capability is offered
to the agent (it uses its own tools, and each of those asks), and "allow
always" is never chosen, so nothing persists in the person's Copilot
configuration; "for this conversation" is remembered by AEP instead.
"""

from __future__ import annotations

import json
import queue
import subprocess
import threading
import time
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import IO, Any, Protocol

PROTOCOL_VERSION = 1


class AcpError(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class AcpProcess(Protocol):
    stdin: IO[str] | None
    stdout: IO[str] | None

    def poll(self) -> int | None: ...

    def kill(self) -> None: ...

    def wait(self, timeout: float | None = None) -> int: ...


AcpLauncher = Callable[[list[str], Path, Mapping[str, str]], AcpProcess]


def launch(argv: list[str], cwd: Path, env: Mapping[str, str]) -> AcpProcess:
    return subprocess.Popen(  # noqa: S603 - argv is built from fixed flags
        argv,
        cwd=cwd,
        env=dict(env),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )


def choose(options: list[dict[str, Any]], allowed: bool) -> dict[str, Any]:
    """The option a decision maps to: allow once / reject once, never "always"."""
    wanted = ("allow_once",) if allowed else ("reject_once", "reject_always")
    for kind in wanted:
        for option in options:
            if option.get("kind") == kind and option.get("optionId"):
                return {"outcome": {"outcome": "selected", "optionId": option["optionId"]}}
    return {"outcome": {"outcome": "cancelled"}}


class AcpSession:
    def __init__(
        self,
        process: AcpProcess,
        *,
        deadline_s: float,
        on_permission: Callable[[dict[str, Any]], bool],
        on_tool_update: Callable[[str, str], None] | None = None,
    ) -> None:
        self.process = process
        self.deadline = time.monotonic() + deadline_s
        self.on_permission = on_permission
        self.on_tool_update = on_tool_update
        self._messages: queue.Queue[dict[str, Any] | None] = queue.Queue()
        self._next = 0
        self.text: list[str] = []
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self) -> None:
        stream = self.process.stdout
        if stream is None:
            self._messages.put(None)
            return
        for line in stream:
            line = line.strip()
            if not line:
                continue
            try:
                message = json.loads(line)
            except ValueError:
                continue
            if isinstance(message, dict):
                self._messages.put(message)
        self._messages.put(None)

    def _send(self, message: dict[str, Any]) -> None:
        stream = self.process.stdin
        if stream is None:
            raise AcpError("backend_start_failed")
        try:
            stream.write(json.dumps({"jsonrpc": "2.0", **message}, ensure_ascii=False) + "\n")
            stream.flush()
        except (OSError, ValueError):
            raise AcpError("backend_failed") from None

    def request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        self._next += 1
        ident = self._next
        self._send({"id": ident, "method": method, "params": params})
        while True:
            remaining = self.deadline - time.monotonic()
            if remaining <= 0:
                raise AcpError("backend_timeout")
            try:
                message = self._messages.get(timeout=remaining)
            except queue.Empty:
                raise AcpError("backend_timeout") from None
            if message is None:
                raise AcpError("backend_failed")
            if message.get("id") == ident and "method" not in message:
                if "error" in message:
                    error = message.get("error") or {}
                    text = str(error.get("message") or "").casefold()
                    raise AcpError(
                        "backend_authentication_failed"
                        if "auth" in text or "login" in text
                        else "backend_failed"
                    )
                result = message.get("result")
                return result if isinstance(result, dict) else {}
            self._handle(message)

    def _handle(self, message: dict[str, Any]) -> None:
        method = message.get("method")
        given = message.get("params")
        params: dict[str, Any] = given if isinstance(given, dict) else {}
        if "id" in message and method:
            if method == "session/request_permission":
                listed = params.get("options")
                options: list[dict[str, Any]] = (
                    [item for item in listed if isinstance(item, dict)]
                    if isinstance(listed, list)
                    else []
                )
                try:
                    allowed = bool(self.on_permission(params))
                except Exception:  # noqa: BLE001 - an error never allows
                    allowed = False
                self._send({"id": message["id"], "result": choose(options, allowed)})
            else:
                self._send(
                    {
                        "id": message["id"],
                        "error": {"code": -32601, "message": f"not offered: {method}"},
                    }
                )
            return
        if method == "session/update":
            raw = params.get("update")
            update: dict[str, Any] = raw if isinstance(raw, dict) else {}
            kind = update.get("sessionUpdate")
            if kind == "agent_message_chunk":
                content = update.get("content")
                if isinstance(content, dict) and content.get("type") == "text":
                    self.text.append(str(content.get("text") or ""))
            elif kind == "tool_call_update" and self.on_tool_update is not None:
                status = str(update.get("status") or "")
                if status in ("completed", "failed"):
                    self.on_tool_update(str(update.get("toolCallId") or ""), status)

    def close(self) -> None:
        try:
            if self.process.stdin is not None:
                self.process.stdin.close()
        except OSError:
            pass
        try:
            self.process.wait(timeout=5)
        except Exception:  # noqa: BLE001 - it is going away either way
            self.process.kill()


def prompt_turn(
    process: AcpProcess,
    *,
    cwd: Path,
    mcp_servers: list[dict[str, Any]],
    prompt: str,
    deadline_s: float,
    on_permission: Callable[[dict[str, Any]], bool],
    on_tool_update: Callable[[str, str], None] | None = None,
) -> str:
    """One ACP session, one prompt; the agent's answer text."""
    session = AcpSession(
        process, deadline_s=deadline_s, on_permission=on_permission, on_tool_update=on_tool_update
    )
    try:
        session.request(
            "initialize",
            {
                "protocolVersion": PROTOCOL_VERSION,
                "clientCapabilities": {
                    "fs": {"readTextFile": False, "writeTextFile": False},
                    "terminal": False,
                },
            },
        )
        created = session.request("session/new", {"cwd": str(cwd), "mcpServers": mcp_servers})
        session_id = str(created.get("sessionId") or "")
        if not session_id:
            raise AcpError("backend_failed")
        session.request(
            "session/prompt",
            {"sessionId": session_id, "prompt": [{"type": "text", "text": prompt}]},
        )
        return "".join(session.text).strip()
    finally:
        session.close()
