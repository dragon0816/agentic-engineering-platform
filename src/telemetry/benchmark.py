"""Benchmark progress and results as telemetry (owner 2026-10-10).

A benchmark runner is its own process, so it writes straight to the Host's
`telemetry.sqlite` (WAL, idempotent by `event_id`). Agent Web's read API and
WebSocket stream poll that store, so Atlas sees benchmark events live and can
replay them like any other run.

- `benchmark_run`: one per runner invocation. `run.started` carries the suite,
  the run label and the Agent Web strategy; `benchmark.case_started` and
  `benchmark.case_completed` follow per case; `run.completed` carries the case
  count and status counts.
- `benchmark_grading`: a later grading pass (knowledge_v1 reference grading).
  Its `parent_run_id` is the graded benchmark run, and it emits
  `benchmark.case_graded` per case.

`aep_trace_ids` on a case links it to the AEP runs that answered it
(`GET /api/v1/telemetry/runs?trace_id=…`). Attributes are metadata only, and
`sanitize` drops content-like keys, so no question or answer text is stored.
A telemetry failure never stops a benchmark.
"""

from __future__ import annotations

import json
import os
import threading
import urllib.request
import uuid
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from telemetry.events import TelemetryEvent, sanitize
from telemetry.store import TelemetryStore

DEFAULT_HOST_JSON = Path(os.path.expandvars(
    r"%LOCALAPPDATA%\AgenticEngineeringPlatform\preview-0.1.0\host.json"))
STORE_FILE = "telemetry.sqlite"


def store_path(host_json: Path = DEFAULT_HOST_JSON) -> Path | None:
    """The Host's telemetry store, or None when telemetry is off or unknown."""
    try:
        host = json.loads(host_json.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None
    root = host.get("workspace_root") or (host.get("layout") or {}).get("workspace_root")
    workspace = Path(os.path.expandvars(str(root))) if root else host_json.parent / "workspace"
    try:
        settings = json.loads((workspace / "telemetry.json").read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        settings = {}
    if isinstance(settings, dict) and settings.get("enabled") is False:
        return None
    return workspace / STORE_FILE


def agent_strategy(base: str | None) -> dict[str, Any]:
    """Agent Web's current strategy (`/api/v1/telemetry/health`), if reachable."""
    if not base:
        return {}
    try:
        with urllib.request.urlopen(  # noqa: S310 - loopback Agent Web address
                base.rstrip("/") + "/api/v1/telemetry/health", timeout=5) as reply:
            health = json.loads(reply.read().decode("utf-8"))
    except (OSError, ValueError):
        return {}
    strategy = health.get("strategy") if isinstance(health.get("strategy"), dict) else {}
    return {"strategy_id": health.get("strategy_id"), "aep_build": strategy.get("build"),
            "skills_digest": strategy.get("skills_digest"),
            "strategy_label": strategy.get("strategy_label")}


def trace_ids(exchanges: list[dict[str, Any]] | dict[str, Any]) -> list[str]:
    """The AEP trace ids of Agent Web chat exchanges, in order, without repeats."""
    found: list[str] = []
    for exchange in exchanges if isinstance(exchanges, list) else [exchanges]:
        reply = exchange.get("reply") if isinstance(exchange, dict) else None
        answer = (reply or {}).get("answer") if isinstance(reply, dict) else None
        outcome = (answer or {}).get("outcome") if isinstance(answer, dict) else None
        trace = (outcome or {}).get("trace") if isinstance(outcome, dict) else None
        ident = (trace or {}).get("trace_id") if isinstance(trace, dict) else None
        if isinstance(ident, str) and ident not in found:
            found.append(ident)
    return found


class BenchmarkTelemetry:
    """Emits one benchmark (or grading) run; every method is safe to call when
    the store is unavailable."""

    def __init__(self, suite: str, label: str, *, kind: str = "benchmark_run",
                 parent_run_id: str | None = None, store: TelemetryStore | None = None,
                 host_json: Path = DEFAULT_HOST_JSON) -> None:
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
        prefix = "bench" if kind == "benchmark_run" else "grade"
        self.run_id = f"{prefix}-{suite}-{label}-{stamp}-{uuid.uuid4().hex[:6]}"
        self.trace_id = f"trace-{self.run_id}"
        self.suite, self.label, self.kind, self.parent_run_id = suite, label, kind, parent_run_id
        self.sequence = 0
        self._lock = threading.Lock()  # runners may finish cases on worker threads
        self.statuses: Counter[str] = Counter()
        self.started: datetime | None = None
        self.store = store
        if self.store is None:
            path = store_path(host_json)
            try:
                self.store = TelemetryStore(path) if path is not None else None
            except Exception:  # noqa: BLE001 - telemetry never stops a benchmark
                self.store = None

    def _emit(self, event_type: str, status: str, attributes: dict[str, Any]) -> None:
        with self._lock:
            self._emit_locked(event_type, status, attributes)

    def _emit_locked(self, event_type: str, status: str, attributes: dict[str, Any]) -> None:
        if self.store is None:
            return
        try:
            event = TelemetryEvent(
                event_id=uuid.uuid4().hex, run_id=self.run_id, trace_id=self.trace_id,
                span_id=f"span-{self.run_id}", sequence=self.sequence,
                timestamp=datetime.now(UTC), event_type=event_type, status=status,
                state=self.kind, attributes=sanitize(attributes))
            self.store.append([event])
            self.sequence += 1
        except Exception:  # noqa: BLE001 - telemetry never stops a benchmark
            return

    def start(self, *, cases: int, strategy: dict[str, Any] | None = None,
              **attributes: Any) -> None:
        self.started = datetime.now(UTC)
        self._emit("run.started", "started", {
            "run_kind": self.kind, "parent_run_id": self.parent_run_id, "suite": self.suite,
            "label": self.label, "cases": cases, **(strategy or {}), **attributes})

    def case_started(self, case_id: str, **attributes: Any) -> None:
        self._emit("benchmark.case_started", "started", {"case_id": case_id, **attributes})

    def case_completed(self, case_id: str, status: str, **attributes: Any) -> None:
        """`status` is the benchmark's own verdict (PASS, FAIL, ...)."""
        with self._lock:
            self.statuses[status] += 1
        event_type = "benchmark.case_graded" if self.kind == "benchmark_grading" \
            else "benchmark.case_completed"
        self._emit(event_type, "succeeded" if status == "PASS" else "failed",
                   {"case_id": case_id, "verdict": status, **attributes})

    def finish(self, **attributes: Any) -> None:
        duration = (int((datetime.now(UTC) - self.started).total_seconds() * 1000)
                    if self.started else None)
        self._emit("run.completed", "succeeded", {
            "cases": sum(self.statuses.values()), "status_counts": dict(self.statuses),
            "duration_ms": duration, "outcome": "completed", **attributes})
        if self.store is not None:
            try:
                self.store.close()
            except Exception:  # noqa: BLE001
                pass
            self.store = None
