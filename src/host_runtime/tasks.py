"""The Agent's task list: Workflows and background jobs, newest first (owner 2026-10-13).

Two sources make one list:

- background jobs Agent Web starts (convert, preview, re-ingest, benchmark, push,
  experience review) record themselves in `tasks.json` in the workspace when they
  start and when they end; one still marked running after a restart is shown as
  interrupted;
- Workflow runs come from telemetry, so a run a conversation, a schedule or the
  Workflows page started is listed the same way.

Ordinary conversation turns are not tasks (owner's choice). The list keeps the
newest `MAX_TASKS`.
"""

from __future__ import annotations

import json
import threading
import time
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from common.base import Contract

TASKS_FILE = "tasks.json"
REPLACE_ATTEMPTS = 6
MAX_TASKS = 50
TaskStatus = Literal["running", "succeeded", "failed", "needs_input", "stopped", "interrupted"]


class TaskRecord(Contract):
    task_id: str
    kind: str
    title: str
    status: TaskStatus = "running"
    started: str
    ended: str | None = None
    summary: str = ""
    # Where it ran: a sandbox, or the run id behind a Workflow.
    where: str = ""


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


class TaskLog:
    """Background jobs, persisted so the list survives an Agent Web restart."""

    def __init__(self, workspace: Path) -> None:
        self.path = workspace / TASKS_FILE
        self._lock = threading.Lock()
        self._tasks: dict[str, TaskRecord] = {}
        if self.path.is_file():
            try:
                stored = json.loads(self.path.read_text(encoding="utf-8"))
                for item in stored if isinstance(stored, list) else []:
                    record = TaskRecord.model_validate(item)
                    if record.status == "running":  # this process did not start it
                        record = record.model_copy(update={"status": "interrupted"})
                    self._tasks[record.task_id] = record
            except (OSError, ValueError):
                self._tasks = {}

    def _save(self) -> None:
        newest = sorted(self._tasks.values(), key=lambda t: t.started, reverse=True)[:MAX_TASKS]
        self._tasks = {t.task_id: t for t in newest}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        text = json.dumps([t.model_dump(mode="json") for t in newest], ensure_ascii=False,
                          indent=1)
        # On Windows a scanner or indexer may hold the file for a moment; a few
        # retries cover that, and a record that still cannot be saved stays in
        # memory rather than failing the job it describes.
        for attempt in range(REPLACE_ATTEMPTS):
            try:
                temporary.write_text(text, encoding="utf-8")
                temporary.replace(self.path)
                return
            except PermissionError:
                time.sleep(0.05 * (attempt + 1))

    def start(self, kind: str, title: str, where: str = "") -> str:
        task_id = f"task-{uuid.uuid4().hex[:10]}"
        with self._lock:
            self._tasks[task_id] = TaskRecord(task_id=task_id, kind=kind, title=title,
                                              started=_now(), where=where)
            self._save()
        return task_id

    def finish(self, task_id: str, status: TaskStatus, summary: str = "") -> None:
        with self._lock:
            record = self._tasks.get(task_id)
            if record is None:
                return
            self._tasks[task_id] = record.model_copy(update={
                "status": status, "summary": summary[:300], "ended": _now()})
            self._save()

    def tracked(self, kind: str, title: str, where: str,
                work: Callable[[], tuple[TaskStatus, str]]) -> Callable[[], None]:
        """`work` wrapped so its task is recorded when it starts and ends; for a
        thread target. `work` returns the final status and a one-line summary."""
        task_id = self.start(kind, title, where)

        def run() -> None:
            try:
                status, summary = work()
            except Exception as failure:  # noqa: BLE001 - the list must show it ended
                status, summary = "failed", f"{type(failure).__name__}: {failure}"
            self.finish(task_id, status, summary)

        return run

    def records(self) -> list[TaskRecord]:
        with self._lock:
            return list(self._tasks.values())


def workflow_tasks(store: Any, limit: int = MAX_TASKS) -> list[TaskRecord]:
    """Workflow runs from telemetry, named by the Workflow they ran."""
    found = []
    for run in store.runs(kind="workflow_run", limit=limit):
        events = store.run_events(run["run_id"], limit=1)
        attributes = (events[0].get("attributes") or {}) if events else {}
        workflow = str(attributes.get("workflow_id") or "Workflow")
        outcome = str(run.get("outcome") or "")
        if not run.get("complete"):
            status: TaskStatus = "running"
        elif outcome == "needs_input":
            status = "needs_input"
        else:
            status = "succeeded" if run.get("status") == "succeeded" else "failed"
        found.append(TaskRecord(
            task_id=run["run_id"], kind="workflow", title=workflow, status=status,
            started=str(run.get("started_at") or ""), ended=run.get("ended_at"),
            summary=(f"{run.get('tool_calls') or 0} steps"
                     + (f", {outcome}" if outcome and outcome not in ("succeeded", "failed")
                        else "")),
            where=run["run_id"]))
    return found


def task_list(log: TaskLog, store: Any | None, limit: int = MAX_TASKS) -> dict[str, Any]:
    tasks = log.records() + (workflow_tasks(store, limit) if store is not None else [])
    newest = sorted(tasks, key=lambda t: t.started, reverse=True)[:limit]
    counts: dict[str, int] = {}
    for task in newest:
        counts[task.status] = counts.get(task.status, 0) + 1
    return {"ok": True, "tasks": [t.model_dump(mode="json") for t in newest], "counts": counts}
