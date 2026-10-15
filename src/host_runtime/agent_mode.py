"""Agent mode for the Claude Code and Copilot conversation backends (owner 2026-10-15).

`docs/phases/AGENT_MODE_BACKENDS.md` ("Revised rules"). A conversation's
coding agent runs in its own working folder with AEP's skills and MCP
servers; whatever it may not do on its own reaches the person as an
approval card in that conversation:

- files inside the working folder (and the read-only folders a person
  added): free;
- files outside: Allow / Allow this folder for this conversation / Deny;
- shell commands: always a card with the full command and its folder;
  Allow for this conversation remembers the program;
- network tools and anything else unknown: a card;
- credentials and protected settings (`common.agent_guard`): refused, even
  when allowed;
- an unanswered card is Deny after ten minutes.

The backend learns the answer through the relay it supports: Claude Code
calls the `permission` tool of the `aep-agent` MCP server below
(`--permission-prompt-tool`), Copilot asks over the Agent Client Protocol
(`host_runtime.acp_client`). Both block until the person answers.

Every request is written to `agent-mode/audit.jsonl` (secrets redacted); every
card and every refusal is a Task row, and each agent turn is one more. The
cards are `pm-` records in a `CardStore` and `AgentWeb.decide_card` sends
their buttons here. Telegram never decides one: these backends are text-only
there.
"""

from __future__ import annotations

import hmac
import json
import secrets
import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Protocol

from common.action_cards import ActionCard, CardButton
from common.agent_guard import (
    AgentRequest,
    Grants,
    GuardPlaces,
    folder_refusal,
    inside,
    judge,
    resolved,
)
from common.assets import REDACTED, SECRET_PATTERN
from common.base import Symbol
from host_runtime.agent_mode_settings import (
    AGENT_BACKENDS,
    RELAY_BACKENDS,
    TEXT_ONLY_REASON,
    AgentModeSettings,
    AgentModeStore,
)
from host_runtime.card_store import CardStore, PendingRecord, new_card_id

CARD_PREFIX = "pm"
CARD_MINUTES = 10
AUDIT_FILE = "agent-mode/audit.jsonl"
CARDS_FILE = "agent-mode/cards.json"
LABELS = {"claude_code": "Claude Code", "codex": "Codex", "copilot": "GitHub Copilot"}
PERMISSION_TOOL = "permission"
SERVER = "aep-agent"
#: Claude Code tools that never touch a file, a command or the network.
QUIET_TOOLS = frozenset({"TodoWrite", "Task", "Agent", "Skill", "ExitPlanMode",
                         "EnterPlanMode", "TaskCreate", "TaskUpdate", "TaskList",
                         "TaskGet", "ToolSearch", "SendUserMessage", "AskUserQuestion"})
STATUS_LABELS = {
    "pending": "Waiting for your answer",
    "allowed": "Allowed",
    "allowed_session": "Allowed for this conversation",
    "denied": "Denied",
    "expired": "No answer in 10 minutes: denied",
}


def redact(text: str) -> str:
    return SECRET_PATTERN.sub(REDACTED, text)


class AgentCard(PendingRecord):
    """One question to the person: a permission, a Knowledge write, a first mail read."""

    kind: Symbol = "permission"
    session_id: str
    run_id: str = ""
    backend: str = ""
    tool: str = ""
    request_kind: str = "other"
    title: str = ""
    paths: tuple[str, ...] = ()
    command: str = ""
    folder: str = ""
    preview: str = ""
    reason: str = ""
    # What "… for this conversation" remembers (a folder, a program, a tool).
    scope: str = ""
    task_id: str = ""
    outcome: str = ""
    outcome_ok: bool | None = None
    channel: str = ""


@dataclass
class AgentRun:
    """One backend process answering one turn of one conversation."""

    run_id: str
    token: str
    session_id: str
    backend: str
    folder: Path
    read_roots: tuple[Path, ...]
    started: datetime
    task_id: str = ""
    cards: list[str] = field(default_factory=list)
    free: list[str] = field(default_factory=list)
    refused: list[str] = field(default_factory=list)
    # An ACP tool call id -> the card that asked for it, for its outcome.
    tool_cards: dict[str, str] = field(default_factory=dict)


class TaskSink(Protocol):
    def start(self, kind: str, title: str, where: str = "") -> str: ...

    def finish(self, task_id: str, status: Any, summary: str = "") -> None: ...


class KnowledgeSteps(Protocol):
    def pipeline_call(self, step: str, arguments: dict[str, Any]) -> dict[str, Any]: ...

    def start_benchmark(self, sandbox_id: str, sets: list[str]) -> dict[str, Any]: ...

    def benchmark_status(self, sandbox_id: str) -> dict[str, Any]: ...

    def knowledge_pipeline(self) -> dict[str, Any]: ...


#: Knowledge pipeline steps an agent may run: reads free, writes carded.
#: Never merge, push, publish, adopt or discard: those stay on the Knowledge page.
KNOWLEDGE_READS = ("sandbox-list", "sandbox-contents", "drop-folders", "question-sets",
                   "lint", "ingest-plan", "file-read", "plan-page", "skill-guide")
KNOWLEDGE_WRITES = ("sandbox-create", "pull", "drop-add", "convert", "ingest-apply")


class AgentMode:
    def __init__(self, workspace_root: Path, *, host_json: Path | None,
                 tasks: Callable[[], TaskSink], coding_roots: Callable[[], tuple[str, ...]],
                 knowledge: KnowledgeSteps | None = None, timeout_s: float | None = None,
                 places: GuardPlaces | None = None,
                 clock: Callable[[], datetime] | None = None) -> None:
        self.workspace_root = workspace_root
        self.store = AgentModeStore(workspace_root)
        self.places = places or GuardPlaces.current(host_json=host_json,
                                                    workspace_root=workspace_root)
        self.cards = CardStore(workspace_root / CARDS_FILE, AgentCard, keep=400, clock=clock)
        self.tasks = tasks
        self.coding_roots = coding_roots
        self.knowledge = knowledge
        self.timeout_s = CARD_MINUTES * 60.0 if timeout_s is None else timeout_s
        self._events: dict[str, threading.Event] = {}
        self._runs: dict[str, AgentRun] = {}
        self._audit_lock = threading.Lock()
        # Set by AgentWeb: the mail tools (host_runtime.agent_mail.AgentMail).
        self.mail: Any = None
        # Skill folders the agent reads from (AEP's read-only skills).
        self.skill_roots: tuple[Path, ...] = ()

    # -- settings ------------------------------------------------------------

    def settings(self) -> dict[str, Any]:
        settings = self.store.load()
        return {"ok": True, "settings": settings.model_dump(mode="json"),
                "default_root": str(self.default_root(settings)),
                "coding_roots": list(self.coding_roots()),
                "backends": [{"name": name, "label": LABELS[name],
                              "relay": name in RELAY_BACKENDS,
                              "enabled": settings.enabled(name),
                              "note": TEXT_ONLY_REASON.get(name, "")}
                             for name in AGENT_BACKENDS]}

    def save_settings(self, body: dict[str, Any]) -> dict[str, Any]:
        try:
            settings = AgentModeSettings.model_validate(
                {**self.store.load().model_dump(mode="json"), **body})
        except ValueError:
            return {"ok": False, "code": "agent_mode_settings_invalid",
                    "message": "Those Agent mode settings are not valid."}
        if settings.codex:
            return {"ok": False, "code": "agent_mode_unsupported",
                    "message": TEXT_ONLY_REASON["codex"]}
        if settings.default_root:
            problem = self._root_problem(Path(settings.default_root))
            if problem is not None:
                return {"ok": False, "code": "agent_folder_refused", "message": problem}
        self.store.save(settings)
        return self.settings()

    def default_root(self, settings: AgentModeSettings | None = None) -> Path:
        settings = settings or self.store.load()
        return (Path(settings.default_root) if settings.default_root
                else self.store.sessions_root)

    def enabled(self, backend: str) -> bool:
        return self.store.load().enabled(backend)

    def _root_problem(self, folder: Path) -> str | None:
        """A working folder lies under workspace\\agent-sessions or a coding
        workspace root, and is neither protected nor holding a protected place."""
        if not folder.is_absolute():
            return "Give a full folder path."
        target = resolved(folder)
        roots = [self.store.sessions_root, *map(Path, self.coding_roots())]
        if not any(inside(target, root) for root in roots):
            listed = "; ".join(str(root) for root in roots)
            return f"A working folder must be under one of: {listed}."
        return folder_refusal(target, self.places)

    # -- each conversation's folders ----------------------------------------

    def working_folder(self, session_id: str) -> Path:
        state = self.store.session(session_id)
        folder = Path(state.folder) if state.folder else self.default_root() / session_id
        folder.mkdir(parents=True, exist_ok=True)
        return resolved(folder)

    def session_view(self, session_id: str) -> dict[str, Any]:
        state = self.store.session(session_id)
        settings = self.store.load()
        return {"ok": True, "session_id": session_id,
                "folder": str(Path(state.folder) if state.folder
                              else self.default_root(settings) / session_id),
                "read_folders": list(state.read_folders),
                "grants": Grants.from_json(state.grants).as_json(),
                "mail_read": state.mail_read,
                "backends": {name: settings.enabled(name) for name in AGENT_BACKENDS},
                "notes": dict(TEXT_ONLY_REASON)}

    def set_session(self, session_id: str, folder: str,
                    read_folders: list[str]) -> dict[str, Any]:
        state = self.store.session(session_id)
        folder = folder.strip()
        if folder:
            problem = self._root_problem(Path(folder))
            if problem is not None:
                return {"ok": False, "code": "agent_folder_refused", "message": problem}
        cleaned: list[str] = []
        for item in read_folders:
            text = str(item).strip()
            if not text:
                continue
            path = Path(text)
            if not path.is_absolute() or not path.is_dir():
                return {"ok": False, "code": "read_folder_missing",
                        "message": f"{text} is not a folder on this computer."}
            problem = folder_refusal(path, self.places)
            if problem is not None:
                return {"ok": False, "code": "agent_folder_refused", "message": problem}
            cleaned.append(str(resolved(path)))
        if len(cleaned) > 20:
            return {"ok": False, "code": "read_folders_too_many",
                    "message": "At most 20 read-only folders."}
        self.store.save_session(session_id, state.model_copy(update={
            "folder": str(resolved(Path(folder))) if folder else "",
            "read_folders": tuple(dict.fromkeys(cleaned))}))
        self.audit({"session": session_id, "event": "folders", "folder": folder,
                    "read_folders": cleaned})
        return self.session_view(session_id)

    def forget(self, session_id: str) -> None:
        self.store.forget(session_id)

    # -- runs ----------------------------------------------------------------

    def begin(self, session_id: str, backend: str) -> AgentRun:
        state = self.store.session(session_id)
        run = AgentRun(run_id=f"run-{uuid.uuid4().hex[:12]}", token=secrets.token_urlsafe(32),
                       session_id=session_id, backend=backend,
                       folder=self.working_folder(session_id),
                       read_roots=tuple(Path(item) for item in state.read_folders)
                       + self.skill_roots,
                       started=datetime.now(UTC))
        run.task_id = self.tasks().start(
            "agent_turn", f"{LABELS.get(backend, backend)} agent turn in {run.folder}",
            session_id)
        self._runs[run.run_id] = run
        return run

    def finish(self, run: AgentRun, status: str, note: str = "") -> list[dict[str, Any]]:
        """End a run; the cards it showed, as they are now, for the answer."""
        self._runs.pop(run.run_id, None)
        parts = [f"{len(run.cards)} asked", f"{len(run.refused)} refused",
                 f"{len(run.free)} free"]
        if run.free:
            parts.append("free: " + ", ".join(run.free[:6]))
        summary = redact("; ".join(parts) + (f" ({note})" if note else ""))
        self.tasks().finish(run.task_id, "succeeded" if status == "answered" else "failed",
                            summary)
        drawn = [self.mail.card(card_id) if card_id.startswith("ml-") and self.mail
                 else self.card(card_id) for card_id in run.cards]
        return [item.model_dump(mode="json") for item in drawn if item is not None]

    def run_for_token(self, token: str) -> AgentRun | None:
        for run in list(self._runs.values()):
            if hmac.compare_digest(run.token, token):
                return run
        return None

    # -- audit ---------------------------------------------------------------

    def audit(self, entry: dict[str, Any]) -> None:
        line = redact(json.dumps({"at": datetime.now(UTC).isoformat(timespec="seconds"),
                                  **entry}, ensure_ascii=False, default=str))
        path = self.workspace_root / AUDIT_FILE
        with self._audit_lock:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")

    # -- a request -----------------------------------------------------------

    def grants(self, session_id: str) -> Grants:
        return Grants.from_json(self.store.session(session_id).grants)

    def request(self, run: AgentRun, request: AgentRequest,
                *, kind: str = "permission") -> tuple[bool, str]:
        """Decide one request: free, refused, or the person's answer to a card."""
        verdict = judge(request, folder=run.folder, read_roots=run.read_roots,
                        grants=self.grants(run.session_id), places=self.places)
        target = request.command or ", ".join(request.paths) or request.tool
        self.audit({"session": run.session_id, "run": run.run_id, "backend": run.backend,
                    "tool": request.tool, "kind": request.kind, "target": target,
                    "decision": verdict.decision, "note": verdict.message})
        if verdict.decision == "free":
            run.free.append(redact(f"{request.tool} {target}")[:120])
            return True, ""
        if verdict.decision == "refuse":
            run.refused.append(target)
            task = self.tasks().start("agent_permission",
                                      redact(f"Refused {request.tool}: {target}")[:160],
                                      run.session_id)
            self.tasks().finish(task, "failed", redact(verdict.message))
            return False, verdict.message
        return self.ask(run, request, scope=verdict.scope, kind=kind)

    def ask(self, run: AgentRun, request: AgentRequest, *, scope: str = "",
            kind: str = "permission", title: str = "") -> tuple[bool, str]:
        """Show a card and wait for the person's press or the timeout."""
        now = self.cards.now()
        record = AgentCard(
            card_id=new_card_id(CARD_PREFIX), kind=kind, created_at=now,
            expires_at=now + timedelta(seconds=self.timeout_s), session_id=run.session_id,
            run_id=run.run_id, backend=run.backend, tool=request.tool,
            request_kind=request.kind, title=title or _title(request),
            paths=tuple(redact(item) for item in request.paths),
            command=redact(request.command), folder=request.folder or str(run.folder),
            preview=redact(request.preview)[:12_000], reason=redact(request.reason)[:1_000],
            scope=scope)
        event = threading.Event()
        self._events[record.card_id] = event
        task = self.tasks().start("agent_permission", redact(record.title)[:160],
                                  run.session_id)
        self.tasks().finish(task, "needs_input", "Waiting: " + redact(
            record.command or ", ".join(record.paths) or record.tool)[:200])
        self.cards.put(record.model_copy(update={"task_id": task}))
        run.cards.append(record.card_id)
        try:
            event.wait(self.timeout_s)
        finally:
            self._events.pop(record.card_id, None)
        with self.cards.lock:
            current = self.cards.get(record.card_id)
            if current is not None and current.status == "pending":
                current = self._settle(current, "expired", "Denied: no answer in time.",
                                       False)
        if current is None:
            return False, "The request was not answered."
        allowed = current.status in ("allowed", "allowed_session")
        return allowed, ("" if allowed else
                         "The person did not allow this"
                         + (" (no answer within 10 minutes)" if current.status == "expired"
                            else "") + ". Do not try another way to do the same thing.")

    # -- cards ---------------------------------------------------------------

    def _settle(self, record: AgentCard, status: str, outcome: str,
                ok: bool | None, channel: str = "") -> AgentCard:
        settled = record.model_copy(update={
            "status": status, "outcome": outcome[:2_000], "outcome_ok": ok,
            "decided_at": self.cards.now(), "channel": channel})
        self.cards.put(settled)
        if record.task_id:
            self.tasks().finish(record.task_id,
                                "succeeded" if status.startswith("allowed") else "stopped",
                                f"{STATUS_LABELS.get(status, status)}: " + redact(
                                    record.command or ", ".join(record.paths)
                                    or record.tool)[:200])
        self.audit({"session": record.session_id, "run": record.run_id,
                    "card": record.card_id, "decision": status, "channel": channel})
        event = self._events.get(record.card_id)
        if event is not None:
            event.set()
        return settled

    def _current(self, card_id: str) -> AgentCard | None:
        record = self.cards.get(card_id)
        if record is not None and record.status == "pending" and (
                self.cards.expired(record) or record.card_id not in self._events):
            # Past its time, or its run is gone (a restart): it can only deny.
            record = self._settle(record, "expired", "Denied: no answer in time.", False)
        return record

    def card(self, card_id: str) -> ActionCard | None:
        with self.cards.lock:
            record = self._current(card_id)
        return None if record is None else draw(record)

    def open_cards(self, session_id: str | None = None) -> list[ActionCard]:
        with self.cards.lock:
            found = [self._current(item.card_id) for item in self.cards.records()
                     if item.status == "pending"
                     and (session_id is None or item.session_id == session_id)]
        return [draw(item) for item in found if item is not None and item.status == "pending"]

    def record(self, card_id: str) -> AgentCard | None:
        return self.cards.get(card_id)

    def decide(self, card_id: str, action: str, *, channel: str = "local") -> dict[str, Any]:
        if channel == "telegram":
            card = self.card(card_id)
            return {"ok": False, "code": "web_only",
                    "message": "Agent-mode cards are answered in Agent Web only.",
                    **({"card": card.model_dump(mode="json")} if card else {})}
        with self.cards.lock:
            record = self._current(card_id)
            if record is None:
                return {"ok": False, "code": "card_unknown",
                        "message": "That card is unknown here."}
            if record.status != "pending":
                return {"ok": False, "code": f"permission_{record.status}",
                        "message": STATUS_LABELS.get(record.status, record.status),
                        "card": draw(record).model_dump(mode="json")}
            actions = {button.action for button in draw(record).buttons}
            if action not in actions:
                return {"ok": False, "code": "card_action_unknown",
                        "message": "That button is not on this card."}
            if action == "deny":
                record = self._settle(record, "denied", "Denied.", False, channel)
            elif action == "allow":
                record = self._settle(record, "allowed", "Allowed once.", True, channel)
            else:
                self._remember(record)
                record = self._settle(record, "allowed_session",
                                      "Allowed for this conversation"
                                      + (f": {record.scope}" if record.scope else "") + ".",
                                      True, channel)
        return {"ok": True, "code": record.status, "message": record.outcome,
                "card": draw(record).model_dump(mode="json")}

    def _remember(self, record: AgentCard) -> None:
        state = self.store.session(record.session_id)
        if record.kind == "mail_read":
            self.store.save_session(record.session_id,
                                    state.model_copy(update={"mail_read": True}))
            return
        grants = Grants.from_json(state.grants)
        if record.request_kind == "command":
            grants.programs.add(record.scope)
        elif record.request_kind == "write":
            grants.write_folders.add(record.scope)
        elif record.request_kind == "read":
            grants.read_folders.add(record.scope)
        else:
            grants.tools.add(record.scope)
        self.store.save_session(record.session_id,
                                state.model_copy(update={"grants": grants.as_json()}))

    # -- Claude Code's permission prompt ------------------------------------

    def claude_permission(self, run: AgentRun, arguments: dict[str, Any]) -> dict[str, Any]:
        """`--permission-prompt-tool`: `{tool_name, input}` in, `{behavior, …}` out."""
        name = str(arguments.get("tool_name") or "")
        given = arguments.get("input")
        payload: dict[str, Any] = given if isinstance(given, dict) else {}
        if name in QUIET_TOOLS or name.startswith(f"mcp__{SERVER}__") \
                or name.startswith(("mcp__aep__", "mcp__aep-assistant__")):
            return {"behavior": "allow", "updatedInput": payload}
        allowed, message = self.request(run, claude_request(name, payload, run.folder))
        if allowed:
            return {"behavior": "allow", "updatedInput": payload}
        return {"behavior": "deny", "message": message or "Denied."}

    # -- Copilot's permission request over ACP --------------------------------

    def acp_permission(self, run: AgentRun, params: dict[str, Any]) -> bool:
        call = params.get("toolCall")
        call = call if isinstance(call, dict) else {}
        request = acp_request(call, run.folder)
        before = len(run.cards)
        allowed, _message = self.request(run, request)
        if len(run.cards) > before and call.get("toolCallId"):
            run.tool_cards[str(call["toolCallId"])] = run.cards[-1]
        return allowed

    def tool_outcome(self, run: AgentRun, tool_call_id: str, status: str) -> None:
        """A carded tool call finished: its Task row says how."""
        card_id = run.tool_cards.pop(tool_call_id, None)
        record = self.cards.get(card_id) if card_id else None
        if record is None or not record.task_id:
            return
        self.tasks().finish(record.task_id,
                            "succeeded" if status == "completed" else "failed",
                            f"{STATUS_LABELS.get(record.status, record.status)}, then "
                            f"{status}: " + redact(record.command or ", ".join(record.paths)
                                                   or record.tool)[:200])
        self.audit({"session": run.session_id, "run": run.run_id, "card": card_id,
                    "outcome": status})

    # -- the aep-agent MCP server -------------------------------------------

    def tools(self, run: AgentRun) -> dict[str, tuple[str, dict[str, Any]]]:
        listed = dict(MCP_TOOLS)
        if run.backend != "claude_code":
            listed.pop(PERMISSION_TOOL)
        return listed

    def mcp(self, run: AgentRun, message: dict[str, Any]) -> dict[str, Any] | None:
        method, ident = message.get("method"), message.get("id")
        params = message.get("params") or {}
        if ident is None:
            return None
        if method == "initialize":
            return _result(ident, {"protocolVersion": str(params.get("protocolVersion")
                                                          or "2025-06-18"),
                                   "capabilities": {"tools": {"listChanged": False}},
                                   "serverInfo": {"name": SERVER, "version": "agent-mode-1"},
                                   "instructions": INSTRUCTIONS})
        if method == "ping":
            return _result(ident, {})
        tools = self.tools(run)
        if method == "tools/list":
            return _result(ident, {"tools": [
                {"name": name, "description": text, "inputSchema": schema}
                for name, (text, schema) in tools.items()]})
        if method == "tools/call":
            name = str(params.get("name") or "")
            if name not in tools:
                return {"jsonrpc": "2.0", "id": ident,
                        "error": {"code": -32602, "message": f"unknown tool {name}"}}
            given = params.get("arguments")
            arguments = given if isinstance(given, dict) else {}
            try:
                outcome = self.call(run, name, arguments)
            except Exception as error:  # noqa: BLE001 - a tool error, never a crash
                outcome = {"ok": False, "code": f"failed:{type(error).__name__}"}
            if name == PERMISSION_TOOL:
                # Claude Code reads the decision from the text content.
                return _result(ident, {"content": [{"type": "text",
                                                    "text": json.dumps(outcome)}]})
            return _result(ident, {
                "content": [{"type": "text", "text": json.dumps(outcome, ensure_ascii=False,
                                                                default=str)}],
                "isError": outcome.get("ok") is False})
        return {"jsonrpc": "2.0", "id": ident,
                "error": {"code": -32601, "message": f"method not found: {method}"}}

    def call(self, run: AgentRun, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if name == PERMISSION_TOOL:
            return self.claude_permission(run, arguments)
        if name.startswith("outlook_"):
            if self.mail is None:
                return {"ok": False, "code": "mail_unavailable"}
            return dict(getattr(self.mail, name[len("outlook_"):])(run, arguments))
        if name.startswith("knowledge_"):
            return self.knowledge_call(run, name, arguments)
        return {"ok": False, "code": "unknown_tool"}

    # -- Knowledge pipeline as tools ------------------------------------------

    def knowledge_call(self, run: AgentRun, name: str,
                       arguments: dict[str, Any]) -> dict[str, Any]:
        if self.knowledge is None or not self.knowledge.knowledge_pipeline().get("enabled"):
            return {"ok": False, "code": "knowledge_pipeline_disabled"}
        if name == "knowledge_sandboxes":
            listed = self.knowledge.pipeline_call("sandbox-list", {})
            return {**listed, "bases": self.knowledge.knowledge_pipeline().get("bases", [])}
        if name == "knowledge_questions_status":
            return self.knowledge.benchmark_status(str(arguments.get("sandbox_id") or ""))
        if name == "knowledge_run_questions":
            sandbox = str(arguments.get("sandbox_id") or "")
            sets = [str(item) for item in arguments.get("sets") or [] if str(item)]
            allowed, message = self._knowledge_card(
                run, "run-questions", {"sandbox_id": sandbox, "sets": sets})
            if not allowed:
                return {"ok": False, "code": "not_allowed", "message": message}
            return self.knowledge.start_benchmark(sandbox, sets)
        if name == "knowledge_step":
            step = str(arguments.get("step") or "")
            given = arguments.get("arguments")
            step_arguments = given if isinstance(given, dict) else {}
            if step not in KNOWLEDGE_READS + KNOWLEDGE_WRITES:
                return {"ok": False, "code": "step_not_offered",
                        "message": "Merge, push and publish stay on the Knowledge page."}
            dry = step == "convert" and step_arguments.get("mode", "dry_run") != "apply"
            if step in KNOWLEDGE_WRITES and not dry:
                allowed, message = self._knowledge_card(run, step, step_arguments)
                if not allowed:
                    return {"ok": False, "code": "not_allowed", "message": message}
            return self.knowledge.pipeline_call(step, step_arguments)
        return {"ok": False, "code": "unknown_tool"}

    def _knowledge_card(self, run: AgentRun, step: str,
                        arguments: dict[str, Any]) -> tuple[bool, str]:
        tool = f"knowledge:{step}"
        if tool in self.grants(run.session_id).tools:
            run.free.append(tool)
            self.audit({"session": run.session_id, "run": run.run_id, "tool": tool,
                        "decision": "free", "note": "allowed for this conversation"})
            return True, ""
        request = AgentRequest(kind="other", tool=tool, folder=str(run.folder),
                               preview=json.dumps(arguments, ensure_ascii=False, indent=1))
        self.audit({"session": run.session_id, "run": run.run_id, "tool": tool,
                    "decision": "card"})
        return self.ask(run, request, scope=tool, kind="knowledge",
                        title=f"Knowledge: {step.replace('-', ' ')} in a sandbox")

    def mail_read_card(self, run: AgentRun, scope_text: str) -> tuple[bool, str]:
        """The first mail read of a conversation asks once."""
        if self.store.session(run.session_id).mail_read:
            return True, ""
        request = AgentRequest(kind="other", tool="outlook.read", folder=str(run.folder),
                               preview=scope_text)
        self.audit({"session": run.session_id, "run": run.run_id, "tool": "outlook.read",
                    "decision": "card"})
        return self.ask(run, request, scope="outlook.read", kind="mail_read",
                        title="Read your email in this conversation")


def _result(ident: Any, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": ident, "result": result}


def _title(request: AgentRequest) -> str:
    if request.kind == "command":
        return "Run a command"
    if request.kind == "write":
        return "Change a file outside the conversation's folder"
    if request.kind == "read":
        return "Read outside the conversation's folder"
    if request.kind == "network":
        return f"Use the network ({request.tool})"
    return f"Use {request.tool}"


def draw(record: AgentCard) -> ActionCard:
    """The card a person sees for a record."""
    allow = CardButton(action="allow", label="Allow", style="primary")
    deny = CardButton(action="deny", label="Deny", style="danger")
    effects: list[str] = []
    buttons: tuple[CardButton, ...]
    if record.kind == "mail_read":
        buttons = (CardButton(action="allow_session", label="Allow for this conversation",
                              style="primary"), deny)
        effects.append("The agent may then search and read mail in this scope until the "
                       "conversation ends; attachments it saves go into its folder.")
    elif not record.scope:
        buttons = (allow, deny)
    else:
        if record.request_kind == "command":
            label = f"Allow {record.scope} for this conversation"
            effects.append(f"Allow for this conversation lets the agent run any {record.scope} "
                           "command until the conversation ends (each is still checked).")
        elif record.request_kind in ("read", "write"):
            label = "Allow this folder for this conversation"
            verb = "change" if record.request_kind == "write" else "read"
            effects.append(f"That lets the agent {verb} anything in {record.scope} until the "
                           "conversation ends.")
        else:
            label = "Allow for this conversation"
        buttons = (allow, CardButton(action="allow_session", label=label[:60]), deny)
    lines: list[str] = []
    if record.command:
        lines += ["Command:", record.command, "", "Folder:", record.folder]
    elif record.paths:
        lines += ["Path:" if len(record.paths) == 1 else "Paths:", *record.paths]
    if record.preview:
        lines += (["", record.preview] if lines else [record.preview])
    tool_line = "" if record.kind == "mail_read" else f"{record.tool} · "
    return ActionCard(
        card_id=record.card_id, kind="agent_permission", title=record.title[:160],
        preview="\n".join(lines)[:20_000], reason=record.reason[:1_000],
        effects=tuple(effects), buttons=buttons, status=record.status,
        status_label=(tool_line + STATUS_LABELS.get(record.status, record.status))[:200],
        outcome=record.outcome, outcome_ok=record.outcome_ok, expires_at=record.expires_at,
        web_only=True, message="The agent is waiting for your answer in Agent Web.")


def _text(value: Any) -> str:
    return value if isinstance(value, str) else ""


def claude_request(name: str, payload: dict[str, Any], folder: Path) -> AgentRequest:
    """A Claude Code tool call in AEP's terms."""
    if name in ("Bash", "PowerShell", "BashOutput", "KillShell", "Monitor"):
        return AgentRequest(kind="command", tool=name, command=_text(payload.get("command")),
                            folder=str(folder), reason=_text(payload.get("description")))
    if name in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
        path = _text(payload.get("file_path")) or _text(payload.get("notebook_path"))
        if name == "Write":
            preview = _text(payload.get("content"))[:4_000]
        elif name == "Edit":
            preview = ("- " + _text(payload.get("old_string")).replace("\n", "\n- ")
                       + "\n+ " + _text(payload.get("new_string")).replace("\n", "\n+ "))
        elif name == "MultiEdit":
            listed = payload.get("edits")
            edits: list[Any] = listed if isinstance(listed, list) else []
            preview = "\n\n".join(
                "- " + _text(item.get("old_string")) + "\n+ " + _text(item.get("new_string"))
                for item in edits if isinstance(item, dict))
        else:
            preview = _text(payload.get("new_source"))[:4_000]
        return AgentRequest(kind="write", tool=name, paths=(path,) if path else (),
                            preview=preview[:6_000])
    if name in ("Read", "NotebookRead", "Glob", "Grep", "LS"):
        path = (_text(payload.get("file_path")) or _text(payload.get("notebook_path"))
                or _text(payload.get("path")))
        return AgentRequest(kind="read", tool=name, paths=(path,) if path else (str(folder),),
                            preview=_text(payload.get("pattern"))[:400])
    if name in ("WebFetch", "WebSearch"):
        return AgentRequest(kind="network", tool=name,
                            preview=_text(payload.get("url")) or _text(payload.get("query")))
    return AgentRequest(kind="other", tool=name or "unknown",
                        preview=json.dumps(payload, ensure_ascii=False, default=str)[:2_000])


def acp_request(call: dict[str, Any], folder: Path) -> AgentRequest:
    """A Copilot (ACP) tool call in AEP's terms: kind, locations, raw input."""
    kind = _text(call.get("kind")) or "other"
    given = call.get("rawInput")
    raw: dict[str, Any] = given if isinstance(given, dict) else {}
    title = _text(call.get("title")) or kind
    paths = [_text(item.get("path")) for item in call.get("locations") or []
             if isinstance(item, dict) and _text(item.get("path"))]
    for key in ("path", "file_path", "filePath", "file", "target"):
        if _text(raw.get(key)) and _text(raw.get(key)) not in paths:
            paths.append(_text(raw.get(key)))
    if kind == "execute" or _text(raw.get("command")):
        command = _text(raw.get("command")) or title
        return AgentRequest(kind="command", tool="shell", command=command,
                            folder=_text(raw.get("cwd")) or str(folder),
                            reason=_text(raw.get("description")))
    if kind in ("edit", "delete", "move"):
        preview = ""
        content = call.get("content")
        for item in content if isinstance(content, list) else []:
            if isinstance(item, dict) and item.get("type") == "diff":
                preview += f"- {_text(item.get('oldText'))}\n+ {_text(item.get('newText'))}\n"
        return AgentRequest(kind="write", tool=kind, paths=tuple(paths),
                            preview=(preview or title)[:6_000])
    if kind in ("read", "search"):
        return AgentRequest(kind="read", tool=kind, paths=tuple(paths) or (str(folder),),
                            preview=title)
    if kind == "fetch":
        return AgentRequest(kind="network", tool="fetch",
                            preview=_text(raw.get("url")) or title)
    return AgentRequest(kind="other", tool=title[:60] or "other",
                        preview=json.dumps(raw, ensure_ascii=False, default=str)[:2_000])


INSTRUCTIONS = (
    "AEP agent-mode tools. Mail: outlook_search and outlook_read read the person's Outlook "
    "mail within the scope they set (the first read in a conversation asks them once); "
    "outlook_draft saves a draft and shows the person a card with Send / Keep as draft / "
    "Cancel: only their press sends it, every message on its own. Knowledge pipeline: "
    "knowledge_sandboxes, knowledge_step (sandbox create, pull, convert, ingest plan/apply "
    "in a sandbox; writes ask the person), knowledge_run_questions. Push to the vault, "
    "merge and publish stay on the Knowledge page. Credentials and protected settings are "
    "never touched, even when asked.")
_S = {"type": "string"}
MCP_TOOLS: dict[str, tuple[str, dict[str, Any]]] = {
    PERMISSION_TOOL: (
        "Answers this agent's permission prompts through the person in Agent Web "
        "(used by the CLI itself; not for the model).",
        {"type": "object", "properties": {"tool_name": _S, "input": {"type": "object"},
                                          "tool_use_id": _S},
         "required": ["tool_name", "input"]}),
    "outlook_search": (
        "Search the person's Outlook mail (read only) within their scope: words in subject, "
        "sender or text; optional sender, folder, days back, limit (max 50). Returns ids.",
        {"type": "object", "properties": {"query": _S, "sender": _S, "folder": _S,
                                          "days": {"type": "integer"},
                                          "limit": {"type": "integer"}}}),
    "outlook_read": (
        "Read one message by its id (read only). save_attachments: true saves its "
        "attachments into this conversation's folder and returns their paths.",
        {"type": "object", "properties": {"message_id": _S,
                                          "save_attachments": {"type": "boolean"}},
         "required": ["message_id"]}),
    "outlook_draft": (
        "Save an Outlook draft and ask the person: the card shows to, cc, subject, body and "
        "attachments with Send / Keep as draft / Cancel. Waits for their press and returns "
        "what happened. Attachments are files in this conversation's folder.",
        {"type": "object", "properties": {
            "to": {"type": "array", "items": _S}, "cc": {"type": "array", "items": _S},
            "subject": _S, "body": _S, "attachments": {"type": "array", "items": _S}},
         "required": ["to", "subject", "body"]}),
    "knowledge_sandboxes": (
        "List personal Knowledge sandboxes and the base vaults one can be made from.",
        {"type": "object", "properties": {}}),
    "knowledge_step": (
        "Run one Knowledge pipeline step in a personal sandbox. Reads: sandbox-list, "
        "sandbox-contents {sandbox_id}, drop-folders {base}, question-sets {sandbox_id}, "
        "lint {sandbox_id}, ingest-plan {sandbox_id, raw_ref}, file-read {sandbox_id, path}, "
        "plan-page {sandbox_id, plan_id, path}, skill-guide. Writes (the person is asked): "
        "sandbox-create {base, label, scope?}, pull {sandbox_id, folders[]}, drop-add "
        "{sandbox_id, name, ...}, convert {sandbox_id, paths[], mode: dry_run|apply}, "
        "ingest-apply {sandbox_id, plan_id}.",
        {"type": "object", "properties": {
            "step": {"type": "string", "enum": [*KNOWLEDGE_READS, *KNOWLEDGE_WRITES]},
            "arguments": {"type": "object"}}, "required": ["step"]}),
    "knowledge_run_questions": (
        "Run test question sets against a sandbox in the background (the person is asked); "
        "then poll knowledge_questions_status.",
        {"type": "object", "properties": {"sandbox_id": _S,
                                          "sets": {"type": "array", "items": _S}},
         "required": ["sandbox_id", "sets"]}),
    "knowledge_questions_status": (
        "The latest test-question run of a sandbox.",
        {"type": "object", "properties": {"sandbox_id": _S}, "required": ["sandbox_id"]}),
}
