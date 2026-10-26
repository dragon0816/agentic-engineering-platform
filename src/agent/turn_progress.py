"""Live, content-free progress of one running conversation turn (owner 2026-10-19).

A channel opens a `TurnProgress` around a turn and sets `TURN_PROGRESS`; the
Gateway tool loop and the shared Harness runner report into it. It records only
names, phases, counts, statuses and durations: never arguments, tool results or
answer text. It is presentation, not policy: nothing here can change a turn.

Context variables are copied by `asyncio.to_thread` and new asyncio tasks, so a
Harness run inside a tool call reports into the turn that started it.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from collections.abc import Callable
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from common.assets import REDACTED, SECRET_PATTERN

#: Recent tool lines kept for display; the count covers every call.
MAX_RECENT_TOOLS = 8
#: Harness runs kept for display (the newest is shown).
MAX_HARNESS_RUNS = 6
MAX_NAME_CHARS = 80
#: How much of a delegation's objective its progress line shows.
MAX_OBJECTIVE_CHARS = 60
#: Sub-agent lines kept for one turn (three run per turn; refused ones never show).
MAX_DELEGATION_LINES = 6

_DOMAIN_LABELS = {
    "knowledge": "Knowledge",
    "workflow": "Workflow",
    "coding": "Coding",
    "conversation": "對話檢查",
}
_STAGE_LABELS = {
    "plan": "規劃",
    "collect_context": "查資料",
    "execute": "執行",
    "validate": "驗收",
}
_PHASE_STAGE = {"collecting": "collect_context", "executing": "execute", "validating": "validate"}
_TERMINAL = {"validated", "failed", "needs_input"}
#: A `DelegationResult.status` as a sub-agent line shows it.
_DELEGATION_STATUS = {
    "succeeded": "done",
    "done": "done",
    "needs_input": "needs_input",
    "awaiting_approval": "awaiting_approval",
    "failed": "failed",
}
_DELEGATION_LABELS = {
    "running": "執行中",
    "done": "完成",
    "needs_input": "需要資訊",
    "awaiting_approval": "等待確認",
    "failed": "失敗",
}


def _name(value: str) -> str:
    return str(value or "")[:MAX_NAME_CHARS]


def short_objective(text: str) -> str:
    """A delegation's objective as its progress line shows it: one line,
    credential-shaped text cut out, at most `MAX_OBJECTIVE_CHARS`."""
    flat = " ".join(SECRET_PATTERN.sub(REDACTED, str(text or "")).split())
    if len(flat) <= MAX_OBJECTIVE_CHARS:
        return flat
    return flat[: MAX_OBJECTIVE_CHARS - 1].rstrip() + "…"


def profile_label(key: str) -> str:
    """`namespace/name@version` -> `namespace/name` (the line's name)."""
    return _name(str(key or "").partition("@")[0])


@dataclass
class _Tool:
    name: str
    started: float
    status: str = "running"
    duration_s: float | None = None


@dataclass
class _Harness:
    domain: str
    stages: tuple[str, ...]
    phase: str
    retry: int = 0
    done: bool = False
    #: The stage the run was in when it ended (None: it never reached one).
    ended_in: str | None = None


@dataclass
class TurnProgress:
    """One running turn. Thread-safe: the Web thread reads, the turn writes."""

    turn_id: str
    session_id: str = ""
    owner: str = ""
    backend: str = "gateway"
    tool_cap: int | None = None
    time_limit_s: int | None = None
    clock: Callable[[], float] = time.monotonic
    started: float = 0.0
    tool_count: int = 0
    #: Delegated sub-agents running under this turn now (multi-agent V1).
    delegations_running: int = 0
    _tools: deque[_Tool] = field(default_factory=lambda: deque(maxlen=MAX_RECENT_TOOLS))
    #: The sub-agents this turn started (`delegation_started`), in order.
    _delegations: deque[SubAgentProgress] = field(
        default_factory=lambda: deque(maxlen=MAX_DELEGATION_LINES)
    )
    _harness: deque[_Harness] = field(default_factory=lambda: deque(maxlen=MAX_HARNESS_RUNS))
    _lock: threading.Lock = field(default_factory=threading.Lock)
    #: Called (no arguments, from the writing thread) after every change, so a
    #: channel can redraw on change instead of on a timer (Telegram).
    listener: Callable[[], None] | None = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        if not self.started:
            self.started = self.clock()

    # -- writers ---------------------------------------------------------------

    def _notify(self) -> None:
        listener = self.listener
        if listener is None:
            return
        try:
            listener()
        except Exception:  # noqa: BLE001 - display cannot change the turn
            pass

    def set_limits(self, tool_cap: int | None, time_limit_s: int | None) -> None:
        with self._lock:
            self.tool_cap, self.time_limit_s = tool_cap, time_limit_s
        self._notify()

    def begin_pass(self) -> None:
        """A new pass of the tool loop (the conversation check's retry): the
        cap applies per pass, so the count starts again."""
        with self._lock:
            self.tool_count = 0
        self._notify()

    def tool_started(self, name: str) -> None:
        with self._lock:
            self.tool_count += 1
            self._tools.append(_Tool(name=_name(name), started=self.clock()))
        self._notify()

    def tool_finished(self, name: str, status: str) -> None:
        with self._lock:
            for tool in reversed(self._tools):
                if tool.name == _name(name) and tool.status == "running":
                    tool.status = status
                    tool.duration_s = round(self.clock() - tool.started, 1)
                    break
        self._notify()

    def delegation_changed(self, delta: int) -> None:
        """A delegated sub-agent started (+1) or ended (-1) under this turn."""
        with self._lock:
            self.delegations_running = max(0, self.delegations_running + delta)
        self._notify()

    def delegation_started(
        self, profile: str, objective: str, *, read_only: bool = True
    ) -> SubAgentProgress:
        """A delegated sub-agent started under this turn (multi-agent V1): its
        own line. Set the returned progress as `TURN_PROGRESS` for the sub-run,
        so its tool calls and limits count on its line (not the parent's), and
        call its `finish` with the result's status when it ends."""
        with self._lock:
            index = len(self._delegations) + 1
            child = SubAgentProgress(
                turn_id=f"{self.turn_id}.d{index}",
                session_id=self.session_id,
                owner=self.owner,
                backend=self.backend,
                clock=self.clock,
                listener=self._notify,
                profile=profile_label(profile),
                objective=short_objective(objective),
                read_only=read_only,
                index=index,
            )
            self._delegations.append(child)
        self._notify()
        return child

    def harness_phase(self, domain: str, stages: tuple[str, ...], phase: str, retry: int) -> None:
        """A Harness run entered `phase` (an `AgentHarnessRun` phase name)."""
        with self._lock:
            # Harness runs nest (a Knowledge tool inside the conversation's
            # own check): the open run of the same domain is this one.
            current = next(
                (run for run in reversed(self._harness) if run.domain == domain and not run.done),
                None,
            )
            if current is None:
                current = _Harness(domain=_name(domain), stages=tuple(stages), phase=phase)
                self._harness.append(current)
            if phase in _TERMINAL and not current.done:
                current.ended_in = _PHASE_STAGE.get(current.phase)
            current.phase, current.retry = phase, retry
            current.done = phase in _TERMINAL
        self._notify()

    def agent_tool(self, name: str, status: str) -> None:
        """A native agent's tool request (agent mode): `waiting` while its card
        waits for the person, then how it was decided."""
        with self._lock:
            if status != "waiting":
                for tool in reversed(self._tools):
                    if tool.name == _name(name) and tool.status == "waiting":
                        tool.status = status
                        tool.duration_s = round(self.clock() - tool.started, 1)
                        break
                else:
                    self._agent_line(name, status)
            else:
                self._agent_line(name, status)
        self._notify()

    def _agent_line(self, name: str, status: str) -> None:
        self.tool_count += 1
        line = _Tool(name=_name(name), started=self.clock(), status=status)
        if status != "waiting":
            line.duration_s = 0.0
        self._tools.append(line)

    # -- readers ---------------------------------------------------------------

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            now = self.clock()
            active = [run for run in self._harness if not run.done]
            shown = active[-1] if active else (self._harness[-1] if self._harness else None)
            view: dict[str, Any] = {
                "turn_id": self.turn_id,
                "backend": self.backend,
                "elapsed_s": max(0, int(now - self.started)),
                "time_limit_s": self.time_limit_s,
                "tool_count": self.tool_count,
                "tool_cap": self.tool_cap,
                "tools": [
                    {
                        "name": tool.name,
                        "status": tool.status,
                        "duration_s": (
                            tool.duration_s
                            if tool.duration_s is not None
                            else round(now - tool.started, 1)
                        ),
                    }
                    for tool in self._tools
                ],
                "harness": None if shown is None else _harness_view(shown),
            }
            children = list(self._delegations)
            counted = self.delegations_running
        # Multi-agent V1: only while a sub-agent runs (absent otherwise). The
        # count is the core's own counter or the running lines, whichever is
        # larger, so a caller reporting both is not counted twice.
        running = max(counted, sum(1 for child in children if child.status == "running"))
        if running:
            view["delegations_running"] = running
        # One line per sub-agent this turn started (absent when none did).
        if children:
            view["delegations"] = [child.line() for child in children]
        return view


@dataclass
class SubAgentProgress(TurnProgress):
    """One delegated sub-agent's line under its parent turn (multi-agent V1).

    The sub-run reports into it as into any turn (tool calls, its limits); it
    keeps its own count for the whole sub-run and tells the parent's listener
    of every change. Its name, a short objective, a status, the count and the
    time are shown; never arguments, tool results or the answer."""

    profile: str = ""
    objective: str = ""
    read_only: bool = True
    index: int = 0
    status: str = "running"
    ended: float | None = None

    def begin_pass(self) -> None:
        """The sub-run's whole tool count is shown, across its passes."""

    def delegation_changed(self, delta: int) -> None:
        """Depth 1: a sub-agent never delegates."""

    def delegation_started(
        self, profile: str, objective: str, *, read_only: bool = True
    ) -> SubAgentProgress:
        raise RuntimeError("a sub-agent cannot delegate (depth 1)")

    def finish(self, status: str) -> None:
        """The sub-run ended with `status` (a `DelegationResult.status`)."""
        with self._lock:
            if self.ended is None:
                self.ended = self.clock()
            self.status = _DELEGATION_STATUS.get(status, "failed")
        self._notify()

    def line(self) -> dict[str, Any]:
        with self._lock:
            end = self.ended if self.ended is not None else self.clock()
            return {
                "index": self.index,
                "profile": self.profile,
                "objective": self.objective,
                "status": self.status,
                "label": _DELEGATION_LABELS.get(self.status, self.status),
                "read_only": self.read_only,
                "tool_count": self.tool_count,
                "tool_cap": self.tool_cap,
                "elapsed_s": max(0, int(end - self.started)),
            }


def _harness_view(run: _Harness) -> dict[str, Any]:
    current = _PHASE_STAGE.get(run.phase)
    order = ("plan", *run.stages)
    reached = order.index(current) if current in order else len(order)
    if run.done and run.phase != "validated":
        # The run ended without passing its checks: the stage it was in is
        # failed (or stopped, waiting for the person); later ones never ran.
        reached = order.index(run.ended_in) if run.ended_in in order else len(order) - 1
    steps = []
    for index, stage in enumerate(order):
        if run.done and run.phase == "validated":
            state = "done"
        elif run.done:
            ended = "stopped" if run.phase == "needs_input" else "failed"
            state = "done" if index < reached else ended if index == reached else "waiting"
        elif index < reached:
            state = "done"
        elif index == reached:
            state = "active"
        else:
            state = "waiting"
        steps.append({"stage": stage, "label": _STAGE_LABELS[stage], "state": state})
    return {
        "domain": run.domain,
        "label": _DOMAIN_LABELS.get(run.domain, run.domain),
        "phase": run.phase,
        "retry": run.retry,
        "done": run.done,
        "steps": steps,
    }


def _clock_text(seconds: int | None) -> str:
    if seconds is None:
        return ""
    return f"{seconds // 60}:{seconds % 60:02d}"


def compact_lines(snapshot: dict[str, Any]) -> list[str]:
    """The compact text a chat channel shows (Telegram): the Harness stepper and
    the count and time against their limits. Names and numbers only."""
    lines: list[str] = []
    harness = snapshot.get("harness")
    if isinstance(harness, dict):
        marks = "①②③④⑤"
        parts = []
        for index, step in enumerate(harness["steps"]):
            label = step["label"]
            if step["state"] == "active" and harness["retry"] and step["stage"] != "plan":
                label += f"（第 {harness['retry'] + 1} 輪）"
            suffix = {"done": " ✓", "active": "…", "failed": " ✗", "stopped": " ⏸"}.get(
                step["state"], ""
            )
            parts.append(f"{marks[index]} {label}{suffix}")
        lines.append(f"{harness['label']}：" + " ".join(parts))
    lines.extend(delegation_lines(snapshot))
    counts = []
    if snapshot.get("tool_cap"):
        counts.append(f"工具 {snapshot['tool_count']}/{snapshot['tool_cap']}")
    elapsed = _clock_text(int(snapshot.get("elapsed_s") or 0))
    limit = snapshot.get("time_limit_s")
    counts.append(f"{elapsed} / {_clock_text(int(limit))}" if limit else elapsed)
    lines.append(" · ".join(counts))
    return lines


_DELEGATION_MARKS = {
    "running": "⏳",
    "done": "✓",
    "needs_input": "⏸",
    "awaiting_approval": "⏸",
    "failed": "✗",
}


def delegation_lines(snapshot: dict[str, Any]) -> list[str]:
    """The sub-agent lines of a chat channel's status (Telegram): one per
    sub-agent with its name, status, tool count and time, then its objective."""
    shown = snapshot.get("delegations")
    if not isinstance(shown, list) or not shown:
        return []
    running = sum(1 for item in shown if item.get("status") == "running")
    lines = [f"子代理（{running} 個執行中）：" if running else "子代理："]
    for item in shown:
        tools = f"工具 {item.get('tool_count', 0)}"
        if item.get("tool_cap"):
            tools += f"/{item['tool_cap']}"
        mark = _DELEGATION_MARKS.get(str(item.get("status")), "·")
        lines.append(
            f"{mark} {item.get('profile', '')}：{item.get('label', '')} · {tools} · "
            f"{_clock_text(int(item.get('elapsed_s') or 0))}"
        )
        if item.get("objective"):
            lines.append(f"   {item['objective']}")
    return lines


TURN_PROGRESS: ContextVar[TurnProgress | None] = ContextVar("aep_turn_progress", default=None)


def current() -> TurnProgress | None:
    return TURN_PROGRESS.get()


def report(action: Callable[[TurnProgress], None]) -> None:
    """Apply `action` to the running turn's progress, if any. Never raises:
    progress display cannot change the answer."""
    progress = TURN_PROGRESS.get()
    if progress is None:
        return
    try:
        action(progress)
    except Exception:  # noqa: BLE001 - see above
        pass


class TurnProgressBoard:
    """The running turns of one Host, by session (memory only)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._turns: dict[str, TurnProgress] = {}
        self._began: dict[str, datetime] = {}

    def begin(self, progress: TurnProgress) -> TurnProgress:
        with self._lock:
            self._turns[progress.session_id] = progress
            self._began[progress.session_id] = datetime.now(UTC)
        return progress

    def end(self, progress: TurnProgress) -> None:
        with self._lock:
            if self._turns.get(progress.session_id) is progress:
                del self._turns[progress.session_id]
                self._began.pop(progress.session_id, None)

    def running(self) -> list[datetime]:
        """When each running turn began (the activity read; no content)."""
        with self._lock:
            return [self._began[session] for session in self._turns if session in self._began]

    def running_turns(self) -> list[tuple[datetime, int]]:
        """When each running turn began and how many delegated sub-agents run
        under it now (multi-agent V1), read together."""
        with self._lock:
            return [
                (self._began[session], progress.delegations_running)
                for session, progress in self._turns.items()
                if session in self._began
            ]

    def get(self, session_id: str) -> TurnProgress | None:
        with self._lock:
            return self._turns.get(session_id)

    def read(self, session_id: str, owner: str) -> dict[str, Any] | None:
        """The session's running turn, only for the actor that started it."""
        with self._lock:
            progress = self._turns.get(session_id)
        if progress is None or progress.owner != owner:
            return None
        return progress.snapshot()
