"""The Agent's task list: Workflows and background jobs, newest 50 (owner, 2026-10-13)."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import pytest
from test_agent_web import base, fetch
from test_knowledge_pipeline_web import _step, served_pipeline  # noqa: F401 - fixture

from host_runtime.tasks import MAX_TASKS, TaskLog, task_list, workflow_tasks
from host_runtime.web import AgentWebServer
from host_runtime.web_page import PAGE


def test_jobs_are_recorded_and_a_restart_marks_running_ones_interrupted(tmp_path: Path) -> None:
    log = TaskLog(tmp_path)
    log.tracked("convert", "Convert 2 original(s)", "sb-1", lambda: ("succeeded", "2 written"))()

    def broken() -> Any:
        raise OSError("disk full")

    log.tracked("push", "Push to rs-k", "sb-1", broken)()
    left = log.start("benchmark", "Benchmark market", "sb-1")
    statuses = {t.title: (t.status, t.summary) for t in log.records()}
    assert statuses["Convert 2 original(s)"] == ("succeeded", "2 written")
    assert statuses["Push to rs-k"] == ("failed", "OSError: disk full")
    reloaded = {t.task_id: t.status for t in TaskLog(tmp_path).records()}
    assert reloaded[left] == "interrupted"


def test_a_busy_file_is_retried_and_never_fails_the_job(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"n": 0}
    real = Path.replace

    def flaky(self: Path, target: Any) -> Path:
        calls["n"] += 1
        if calls["n"] <= 2:
            raise PermissionError("held by a scanner")
        return real(self, target)

    monkeypatch.setattr(Path, "replace", flaky)
    log = TaskLog(tmp_path)
    log.start("preview", "Preview 1")
    assert calls["n"] == 3 and len(TaskLog(tmp_path).records()) == 1
    monkeypatch.setattr(Path, "replace", lambda self, target: (_ for _ in ()).throw(
        PermissionError("always")))
    log.start("preview", "Preview 2")  # not saved, but no error and still listed
    assert len(log.records()) == 2


def test_only_the_newest_fifty_are_kept(tmp_path: Path) -> None:
    log = TaskLog(tmp_path)
    for number in range(MAX_TASKS + 5):
        log.start("preview", f"Preview {number}")
    assert len(TaskLog(tmp_path).records()) == MAX_TASKS


class _Store:
    def runs(self, *, kind: str, limit: int) -> list[dict[str, Any]]:
        assert kind == "workflow_run"
        return [
            {"run_id": "run-1", "started_at": "2026-10-13T01:00:00+00:00", "ended_at": None,
             "complete": False, "status": "running", "outcome": None, "duration_ms": None},
            {"run_id": "run-2", "started_at": "2026-10-12T23:35:38+00:00",
             "ended_at": "2026-10-12T23:36:45+00:00", "complete": True, "status": "failed",
             "outcome": "failed", "duration_ms": 67087.1, "tool_calls": 6},
        ]

    def run_events(self, run_id: str, limit: int) -> list[dict[str, Any]]:
        return [{"attributes": {"workflow_id": "engineering/sde-weekly-report@1.0.0"}}]


def test_workflow_runs_come_from_telemetry_and_merge_newest_first(tmp_path: Path) -> None:
    found = workflow_tasks(_Store())
    assert [(t.title, t.status) for t in found] == [
        ("engineering/sde-weekly-report@1.0.0", "running"),
        ("engineering/sde-weekly-report@1.0.0", "failed")]
    assert found[1].summary == "6 steps"
    log = TaskLog(tmp_path)
    log.start("convert", "Convert 1 original(s)")
    listed = task_list(log, _Store())
    assert [t["kind"] for t in listed["tasks"]][1:] == ["workflow", "workflow"]
    assert listed["counts"] == {"running": 2, "failed": 1}


def test_a_convert_from_the_page_appears_in_the_task_list(
    served_pipeline: tuple[AgentWebServer, Path],  # noqa: F811 - fixture
) -> None:
    server, _ = served_pipeline
    made = _step(server, "sandbox-create", {"base": "k-test", "label": "tasks"})
    sandbox = made["data"]["sandbox_id"]
    assert _step(server, "drop-add", {"sandbox_id": sandbox, "name": "a.txt",
                                      "data_base64": "aGVsbG8K"})["ok"]
    assert json.loads(fetch(base(server) + "/api/knowledge/convert/start", token=server.token,
                            body={"sandbox_id": sandbox, "mode": "dry_run"}).body)["ok"]
    deadline = time.monotonic() + 30
    while True:
        tasks = json.loads(fetch(base(server) + "/api/tasks", token=server.token).body)["tasks"]
        if (tasks and tasks[0]["status"] != "running") or time.monotonic() > deadline:
            break
        time.sleep(0.2)
    assert tasks[0]["kind"] == "preview" and tasks[0]["status"] == "succeeded"
    assert tasks[0]["summary"] == "1 of 1 originals: 1 written" and tasks[0]["where"] == sandbox
    assert fetch(base(server) + "/api/tasks").status == 401


def test_the_page_has_a_tasks_tab() -> None:
    for hook in ('id="nav-tasks"', 'id="panel-tasks"', "/api/tasks", "loadTasks",
                 'id="task-counts"'):
        assert hook in PAGE
