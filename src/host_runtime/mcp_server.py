"""`aep-host mcp`: this Host's authoring as an MCP server over stdio.

External authoring X3 (`docs/phases/EXTERNAL_AUTHORING.md`). Claude Code,
Codex and Copilot all speak the Model Context Protocol, so one server serves
the three. It is JSON-RPC 2.0, one message per line on stdin and stdout, and
uses the standard library only: the protocol surface it needs (initialize,
ping, tools/list, tools/call) is small, and the SDK would add a web stack
this Host does not use.

The tools are `ExternalAuthoring`'s operations; `aep-host assets` calls the
same `dispatch`, so the CLI and the server never differ.
"""

from __future__ import annotations

import contextlib
import json
import sys
import threading
from collections.abc import Callable
from typing import IO, Any

from pydantic import JsonValue

from host_runtime.external_authoring import ExternalAuthoring, guarded

PROTOCOL_VERSIONS = ("2025-06-18", "2025-03-26", "2024-11-05")
INSTRUCTIONS = (
    "AEP authoring: build Workflows and Skills this AEP Host can use. Start with aep_catalog "
    "(formats, installed capabilities with input schemas, installed Workflows and Skills). "
    "Check a draft with aep_check_*, submit it with aep_submit_*, run a Workflow with test "
    "values, then ask to install it. Runs that change something, and every install, wait "
    "for the owner's approval in Agent Web; follow them with aep_status. You get statuses "
    "and codes, never the data a run read."
)

_OBJECT = {"type": "object"}
_ID = {"candidate_id": {"type": "string"}}

TOOLS: dict[str, tuple[str, dict[str, Any]]] = {
    "aep_catalog": ("The authoring formats, installed capabilities (with input schemas), "
                    "Workflows and Skills on this Host.", {"type": "object", "properties": {}}),
    "aep_list": ("Your submitted Workflow and Skill candidates and their last approval.",
                 {"type": "object", "properties": {}}),
    "aep_get": ("One submitted candidate in full.",
                {"type": "object", "properties": _ID, "required": ["candidate_id"]}),
    "aep_status": ("An approval's outcome: statuses and codes.",
                   {"type": "object", "properties": {"approval_id": {"type": "string"}},
                    "required": ["approval_id"]}),
    "aep_check_workflow": ("Check a Workflow against this Host without keeping it.",
                           {"type": "object", "properties": {"workflow": _OBJECT},
                            "required": ["workflow"]}),
    "aep_submit_workflow": ("Keep a Workflow as a candidate; pass candidate_id to revise one.",
                            {"type": "object", "properties": {
                                "title": {"type": "string"}, "workflow": _OBJECT, **_ID},
                             "required": ["title", "workflow"]}),
    "aep_run_workflow": ("Run a candidate once with test values. Read-only Workflows run now; "
                         "others wait for the owner's approval.",
                         {"type": "object", "properties": {
                             **_ID, "arguments": {"type": "object"}},
                          "required": ["candidate_id"]}),
    "aep_install_workflow": ("Ask the owner to install a Workflow candidate.",
                             {"type": "object", "properties": _ID,
                              "required": ["candidate_id"]}),
    "aep_check_skill": ("Check a Skill against this Host without keeping it.",
                        {"type": "object", "properties": {"skill": _OBJECT},
                         "required": ["skill"]}),
    "aep_submit_skill": ("Keep a Skill as a candidate; pass candidate_id to revise one.",
                         {"type": "object", "properties": {
                             "title": {"type": "string"}, "skill": _OBJECT, **_ID},
                          "required": ["title", "skill"]}),
    "aep_install_skill": ("Ask the owner to install a Skill candidate.",
                          {"type": "object", "properties": _ID, "required": ["candidate_id"]}),
}


def _object(args: dict[str, Any], key: str) -> dict[str, Any]:
    value = args.get(key)
    if isinstance(value, str):
        with contextlib.suppress(ValueError):
            value = json.loads(value)
    return value if isinstance(value, dict) else {}


def dispatch(authoring: ExternalAuthoring, name: str, args: dict[str, Any]) -> dict[str, JsonValue]:
    ident = str(args.get("candidate_id") or "")
    revise = ident or None
    title = str(args.get("title") or "")
    calls: dict[str, Callable[[], dict[str, JsonValue]]] = {
        "aep_catalog": authoring.catalog,
        "aep_list": authoring.list,
        "aep_get": lambda: authoring.get(ident),
        "aep_status": lambda: authoring.status(str(args.get("approval_id") or "")),
        "aep_check_workflow": lambda: authoring.check_workflow(_object(args, "workflow")),
        "aep_submit_workflow": lambda: authoring.submit_workflow(
            _object(args, "workflow"), title, revise),
        "aep_run_workflow": lambda: authoring.run_workflow(ident, _object(args, "arguments")),
        "aep_install_workflow": lambda: authoring.install_workflow(ident),
        "aep_check_skill": lambda: authoring.check_skill(_object(args, "skill")),
        "aep_submit_skill": lambda: authoring.submit_skill(_object(args, "skill"), title, revise),
        "aep_install_skill": lambda: authoring.install_skill(ident),
    }
    if name not in calls:
        return {"ok": False, "code": "tool_unknown"}
    return guarded(calls[name])


class Server:
    def __init__(self, factory: Callable[[], ExternalAuthoring], version: str) -> None:
        self._factory = factory
        self._authoring: ExternalAuthoring | None = None
        self._failure: str | None = None
        self._building = threading.Lock()
        self.version = version

    def warm(self) -> None:
        """Assemble the Host now: it takes tens of seconds, and a client's
        first tool call should not wait for all of it."""
        threading.Thread(target=self._ready, daemon=True).start()

    def _ready(self) -> ExternalAuthoring | None:
        with self._building:
            if self._authoring is None and self._failure is None:
                try:
                    self._authoring = self._factory()
                except Exception as error:  # noqa: BLE001 - reported as a code, no values
                    self._failure = str(getattr(error, "code", None) or type(error).__name__)
            return self._authoring

    def _call(self, name: str, args: dict[str, Any]) -> dict[str, JsonValue]:
        authoring = self._ready()
        if authoring is None:
            return {"ok": False, "code": f"host_unavailable:{self._failure}"}
        try:
            return dispatch(authoring, name, args)
        except Exception as error:  # noqa: BLE001 - a tool error, never a crash
            return {"ok": False, "code": f"failed:{type(error).__name__}"}

    def handle(self, message: dict[str, Any]) -> dict[str, Any] | None:
        method = message.get("method")
        ident = message.get("id")
        params = message.get("params") or {}
        if ident is None:
            return None  # a notification, such as notifications/initialized
        if method == "initialize":
            self.warm()
            asked = str(params.get("protocolVersion") or "")
            return _result(ident, {
                "protocolVersion": asked if asked in PROTOCOL_VERSIONS else PROTOCOL_VERSIONS[0],
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "aep", "version": self.version},
                "instructions": INSTRUCTIONS,
            })
        if method == "ping":
            return _result(ident, {})
        if method == "tools/list":
            return _result(ident, {"tools": [
                {"name": name, "description": text, "inputSchema": schema}
                for name, (text, schema) in TOOLS.items()]})
        if method == "tools/call":
            name = str(params.get("name") or "")
            if name not in TOOLS:
                return _error(ident, -32602, f"unknown tool {name}")
            arguments = params.get("arguments")
            outcome = self._call(name, arguments if isinstance(arguments, dict) else {})
            return _result(ident, {
                "content": [{"type": "text",
                             "text": json.dumps(outcome, ensure_ascii=False, indent=1)}],
                "structuredContent": outcome,
                "isError": outcome.get("ok") is False and "problems" not in outcome,
            })
        return _error(ident, -32601, f"method not found: {method}")

    def serve(self, source: IO[bytes], sink: IO[bytes]) -> None:
        for raw in source:
            line = raw.strip()
            if not line:
                continue
            try:
                message = json.loads(line)
            except ValueError:
                reply: dict[str, Any] | None = _error(None, -32700, "parse error")
            else:
                if not isinstance(message, dict):
                    reply = _error(None, -32600, "invalid request")
                else:
                    # Nothing a capability prints may corrupt the protocol stream.
                    with contextlib.redirect_stdout(sys.stderr):
                        reply = self.handle(message)
            if reply is not None:
                sink.write((json.dumps(reply, ensure_ascii=False) + "\n").encode("utf-8"))
                sink.flush()


def _result(ident: Any, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": ident, "result": result}


def _error(ident: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": ident, "error": {"code": code, "message": message}}
