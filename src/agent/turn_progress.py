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

#: Recent tool lines kept for display; the count covers every call.
MAX_RECENT_TOOLS = 8
#: Harness runs kept for display (the newest is shown).
MAX_HARNESS_RUNS = 6
MAX_NAME_CHARS = 80

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


def _name(value: str) -> str:
    return str(value or "")[:MAX_NAME_CHARS]


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
    _tools: deque[_Tool] = field(default_factory=lambda: deque(maxlen=MAX_RECENT_TOOLS))
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
            return {
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
    counts = []
    if snapshot.get("tool_cap"):
        counts.append(f"工具 {snapshot['tool_count']}/{snapshot['tool_cap']}")
    elapsed = _clock_text(int(snapshot.get("elapsed_s") or 0))
    limit = snapshot.get("time_limit_s")
    counts.append(f"{elapsed} / {_clock_text(int(limit))}" if limit else elapsed)
    lines.append(" · ".join(counts))
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
