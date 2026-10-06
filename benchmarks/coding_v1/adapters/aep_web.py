"""Adapter to the AEP Agent through its existing entry point: Agent Web chat.

Each task gets a new conversation session (POST /api/conversations) and the
prompt is sent as a normal chat turn (POST /api/conversations/turn), the same
path a person uses in the browser. The full reply, including the Gateway's
record of every tool the model called, is kept as the task's trace.
"""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[3]


def agent_web() -> tuple[str, str]:
    """The newest Agent Web started from this repository: (base URL, token)."""
    logs = sorted((REPO / ".scratch").glob("agent-web-*.out.log"), key=lambda p: p.stat().st_mtime)
    for log in reversed(logs):
        found = re.search(r"(http://127\.0\.0\.1:\d+)/\?token=(\S+)", log.read_text(encoding="utf-8"))
        if found:
            return found.group(1), found.group(2)
    raise RuntimeError("no running Agent Web found under .scratch/")


class AgentWebSession:
    def __init__(self, base: str, token: str, timeout_s: float) -> None:
        self.base, self.token, self.timeout_s = base, token, timeout_s
        self.session_id: str | None = None
        self.exchanges: list[dict[str, Any]] = []

    def _call(self, path: str, body: dict[str, Any] | None = None,
              timeout: float | None = None) -> tuple[int, dict[str, Any]]:
        request = urllib.request.Request(
            self.base + path, data=None if body is None else json.dumps(body).encode("utf-8"),
            headers={"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"},
            method="GET" if body is None else "POST")
        try:
            with urllib.request.urlopen(request, timeout=timeout or 60) as reply:
                return reply.status, json.loads(reply.read() or b"{}")
        except urllib.error.HTTPError as error:
            return error.code, json.loads(error.read() or b"{}")

    def commands(self) -> Any:
        return self._call("/api/commands")[1]

    def start(self) -> str:
        _status, created = self._call("/api/conversations", {})
        session = created.get("session_id") or (created.get("conversation") or {}).get("session_id")
        if not session:
            raise RuntimeError(f"could not open a conversation: {created}")
        self.session_id = session
        return session

    def send(self, message: str, timeout_s: float) -> dict[str, Any]:
        started = time.monotonic()
        try:
            status, reply = self._call("/api/conversations/turn",
                                       {"session_id": self.session_id, "message": message},
                                       timeout=timeout_s)
            timed_out = False
        except (TimeoutError, urllib.error.URLError) as error:
            status, reply, timed_out = 0, {"error": f"{type(error).__name__}: {error}"}, True
        exchange = {"sent": message, "http_status": status, "seconds": round(time.monotonic() - started, 3),
                    "timed_out": timed_out, "reply": reply}
        self.exchanges.append(exchange)
        return exchange


def answer_text(exchange: dict[str, Any]) -> str:
    answer = (exchange.get("reply") or {}).get("answer") or {}
    return str(answer.get("answer") or "")


def tools_of(exchange: dict[str, Any]) -> list[dict[str, Any]]:
    """The Gateway's own record of each tool the model called this turn."""
    answer = (exchange.get("reply") or {}).get("answer") or {}
    convo = ((answer.get("outcome") or {}).get("conversation")) or {}
    out = []
    for tool in convo.get("tools") or []:
        capability = tool.get("capability") or {}
        workflow = tool.get("workflow") or {}
        run = workflow.get("run") or {}
        failure = tool.get("failure") or capability.get("failure") or run.get("failure") or {}
        out.append({
            "name": tool.get("name"),
            "target": (tool.get("decision") or {}).get("target"),
            "status": capability.get("status") or run.get("status") or ("refused" if tool.get("failure") else None),
            "failure": failure.get("code"),
            "workflow_run_id": run.get("run_id"),
        })
    return out


def model_turns(exchange: dict[str, Any]) -> int | None:
    answer = (exchange.get("reply") or {}).get("answer") or {}
    convo = ((answer.get("outcome") or {}).get("conversation")) or {}
    value = convo.get("model_turns")
    return value if isinstance(value, int) else None
