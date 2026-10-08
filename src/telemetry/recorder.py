"""Emitting harness events without slowing or failing the harness.

`emit` builds a small dict and `put_nowait`s it on a bounded queue; a writer
thread validates, sanitizes and stores batches. A full queue drops the event
and counts it; nothing here ever raises into the caller. Without `configure`
(tests, one-off commands) every call is a no-op.

Runs and spans live in context variables, which `asyncio.to_thread` and new
asyncio tasks copy, so a model call or a Bridge capability made inside a
conversation turn lands in that turn's run under the right parent span.
"""

from __future__ import annotations

import atexit
import contextvars
import hashlib
import itertools
import json
import logging
import queue
import threading
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from telemetry.events import SCHEMA_VERSION, TelemetryEvent, sanitize
from telemetry.store import TelemetryStore

QUEUE_LIMIT = 20_000
BATCH = 500
PRUNE_EVERY_SECONDS = 600.0
_log = logging.getLogger(__name__)


@dataclass
class RunContext:
    run_id: str
    kind: str
    trace_id: str
    span_id: str
    parent_run_id: str | None = None
    # The span in the parent run this run was started from (a Workflow
    # started by a conversation tool nests under that tool's span).
    parent_span_id: str | None = None
    _counter: Iterator[int] = field(default_factory=itertools.count)
    _lock: threading.Lock = field(default_factory=threading.Lock)
    started: float = field(default_factory=time.perf_counter)
    status: str = "succeeded"
    attributes: dict[str, Any] = field(default_factory=dict)
    totals: dict[str, int] = field(default_factory=lambda: {
        "llm_calls": 0, "tool_calls": 0, "input_tokens": 0, "output_tokens": 0,
        "token_reports": 0})

    def next_sequence(self) -> int:
        with self._lock:
            return next(self._counter)


_run: contextvars.ContextVar[RunContext | None] = contextvars.ContextVar("aep_run", default=None)
_span: contextvars.ContextVar[str | None] = contextvars.ContextVar("aep_span", default=None)
_state: contextvars.ContextVar[str | None] = contextvars.ContextVar("aep_state", default=None)


class Recorder:
    def __init__(self, store: TelemetryStore, strategy: dict[str, Any]) -> None:
        self.store = store
        self.strategy = strategy
        self.strategy_id = strategy_id(strategy)
        self.queue: queue.Queue[dict[str, Any] | None] = queue.Queue(maxsize=QUEUE_LIMIT)
        self.dropped = 0
        self.rejected = 0
        self.written = 0
        self._thread = threading.Thread(target=self._write, name="telemetry-writer",
                                        daemon=True)
        self._thread.start()

    def put(self, raw: dict[str, Any]) -> None:
        try:
            self.queue.put_nowait(raw)
        except queue.Full:
            self.dropped += 1

    def _write(self) -> None:
        last_prune = 0.0
        while True:
            first = self.queue.get()
            if first is None:
                return
            batch = [first]
            while len(batch) < BATCH:
                try:
                    item = self.queue.get_nowait()
                except queue.Empty:
                    break
                if item is None:
                    self._store(batch)
                    return
                batch.append(item)
            self._store(batch)
            if time.monotonic() - last_prune > PRUNE_EVERY_SECONDS:
                last_prune = time.monotonic()
                try:
                    self.store.prune()
                except Exception:  # noqa: BLE001 - telemetry never fails the host
                    _log.debug("telemetry prune failed", exc_info=True)

    def _store(self, batch: list[dict[str, Any]]) -> None:
        events = []
        for raw in batch:
            try:
                raw["attributes"] = sanitize(raw.get("attributes") or {})
                events.append(TelemetryEvent.model_validate(raw))
            except Exception:  # noqa: BLE001 - a malformed event is dropped, not raised
                self.rejected += 1
        try:
            self.written += self.store.append(events)
        except Exception:  # noqa: BLE001 - a locked or full disk drops the batch
            self.dropped += len(events)
            _log.debug("telemetry write failed", exc_info=True)

    def flush(self, timeout: float = 2.0) -> None:
        deadline = time.monotonic() + timeout
        while not self.queue.empty() and time.monotonic() < deadline:
            time.sleep(0.01)
        time.sleep(0.02)

    def close(self, timeout: float = 2.0) -> None:
        self.flush(timeout)
        try:
            self.queue.put_nowait(None)
        except queue.Full:
            pass
        self._thread.join(timeout)

    def health(self) -> dict[str, Any]:
        return {"schema_version": SCHEMA_VERSION, "queue_depth": self.queue.qsize(),
                "queue_limit": QUEUE_LIMIT, "dropped": self.dropped, "rejected": self.rejected,
                "written": self.written, "strategy_id": self.strategy_id,
                "strategy": self.strategy, "store": str(self.store.path)}


_recorder: Recorder | None = None


def strategy_id(components: dict[str, Any]) -> str:
    text = json.dumps(components, sort_keys=True, default=str)
    return "st-" + hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def configure(store: TelemetryStore, strategy: dict[str, Any]) -> Recorder:
    """Start recording for this process (idempotent: the first store wins)."""
    global _recorder
    if _recorder is None:
        _recorder = Recorder(store, strategy)
        atexit.register(_recorder.close)
    return _recorder


def recorder() -> Recorder | None:
    return _recorder


def reset() -> None:
    """Stop recording (tests)."""
    global _recorder
    if _recorder is not None:
        _recorder.close()
    _recorder = None


def current_run() -> RunContext | None:
    return _run.get()


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:16]}"


def emit(event_type: str, *, status: str = "succeeded", state: str | None = None,
         attributes: dict[str, Any] | None = None, span_id: str | None = None,
         parent_span_id: str | None = None, run: RunContext | None = None) -> None:
    """Record one event in the current run. Never raises; no run, no event."""
    target = run or _run.get()
    if _recorder is None or target is None:
        return
    try:
        _recorder.put({
            "schema_version": SCHEMA_VERSION, "event_id": uuid.uuid4().hex,
            "run_id": target.run_id, "trace_id": target.trace_id,
            # A point event is its own operation, under the current span.
            "span_id": span_id or _new_id("span"),
            "parent_span_id": parent_span_id if span_id else (_span.get() or target.span_id),
            "sequence": target.next_sequence(),
            "timestamp": datetime.now(UTC).isoformat(),
            "event_type": event_type, "state": state if state is not None else _state.get(),
            "status": status, "attributes": attributes or {}})
    except Exception:  # noqa: BLE001 - telemetry never fails the harness
        _log.debug("telemetry emit failed", exc_info=True)


@contextmanager
def run(kind: str, *, trace_id: str | None = None, run_id: str | None = None,
        attributes: dict[str, Any] | None = None) -> Iterator[RunContext | None]:
    """A Harness run: `run.started`, then `run.completed` with its outcome."""
    if _recorder is None:
        yield None
        return
    parent = _run.get()
    context = RunContext(
        run_id=run_id or _new_id("run"), kind=kind,
        trace_id=trace_id or (parent.trace_id if parent else _new_id("trace")),
        span_id=_new_id("span"), parent_run_id=None if parent is None else parent.run_id,
        parent_span_id=None if parent is None else (_span.get() or parent.span_id),
        attributes=dict(attributes or {}))
    run_token = _run.set(context)
    span_token = _span.set(context.span_id)
    state_token = _state.set(None)
    emit("run.started", status="started", span_id=context.span_id,
         parent_span_id=context.parent_span_id, attributes={
        "run_kind": kind, "parent_run_id": context.parent_run_id,
        "strategy_id": _recorder.strategy_id, **_recorder.strategy, **context.attributes})
    try:
        yield context
    except BaseException as error:
        context.status = "cancelled" if isinstance(error, KeyboardInterrupt) else "failed"
        context.attributes.setdefault("failure_code", type(error).__name__)
        raise
    finally:
        totals = context.totals
        emit("run.completed", status=context.status, span_id=context.span_id,
             parent_span_id=context.parent_span_id, attributes={
            "run_kind": kind, "duration_ms": round((time.perf_counter() - context.started)
                                                   * 1000, 1),
            "llm_calls": totals["llm_calls"], "tool_calls": totals["tool_calls"],
            # Missing usage is not zero: sums only cover calls that reported it.
            "input_tokens": totals["input_tokens"] if totals["token_reports"] else None,
            "output_tokens": totals["output_tokens"] if totals["token_reports"] else None,
            "token_reports": totals["token_reports"], **context.attributes})
        _state.reset(state_token)
        _span.reset(span_token)
        _run.reset(run_token)


@contextmanager
def span(state: str, *, attributes: dict[str, Any] | None = None,
         completed: str | None = None) -> Iterator[dict[str, Any]]:
    """`state.entered` … `state.exited` (or `completed`, e.g. `tool.completed`),
    with duration and status. The yielded dict collects end attributes; set
    `status` in it to record a failure without raising."""
    run_context = _run.get()
    end: dict[str, Any] = {}
    if _recorder is None or run_context is None:
        yield end
        return
    parent = _span.get() or run_context.span_id
    own = _new_id("span")
    started = time.perf_counter()
    emit("state.entered", status="started", state=state, span_id=own, parent_span_id=parent,
         attributes=attributes)
    span_token, state_token = _span.set(own), _state.set(state)
    status = "succeeded"
    try:
        yield end
        status = str(end.pop("status", "succeeded"))
    except BaseException as error:
        status = "failed"
        end.setdefault("failure_code", type(error).__name__)
        raise
    finally:
        _span.reset(span_token)
        _state.reset(state_token)
        emit(completed or "state.exited", status=status, state=state, span_id=own,
             parent_span_id=parent, attributes={
                 **(attributes or {}), **end,
                 "duration_ms": round((time.perf_counter() - started) * 1000, 1)})


def note_llm(input_tokens: int | None, output_tokens: int | None) -> None:
    run_context = _run.get()
    if run_context is None:
        return
    run_context.totals["llm_calls"] += 1
    if input_tokens or output_tokens:
        run_context.totals["token_reports"] += 1
        run_context.totals["input_tokens"] += int(input_tokens or 0)
        run_context.totals["output_tokens"] += int(output_tokens or 0)


def note_tool() -> None:
    run_context = _run.get()
    if run_context is not None:
        run_context.totals["tool_calls"] += 1


def set_run(**attributes: Any) -> None:
    """Attributes the run's `run.completed` should carry (outcome, skill_id…)."""
    run_context = _run.get()
    if run_context is not None:
        status = attributes.pop("status", None)
        if status:
            run_context.status = str(status)
        run_context.attributes.update(attributes)

