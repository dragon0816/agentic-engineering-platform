"""Portable task evidence and host-owned completion checks."""

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from agent.run_state import (
    CompletionValidator,
    TaskObservation,
    TaskRunState,
    advance_task_run,
    begin_task_run,
)
from agent.task_contract import CompletionCheck, ExpectedOutput, TaskContract
from common.assets import AssetIdentity
from common.distribution import LocalStateError
from common.execution import TraceIdentifiers
from host_runtime.state import SqliteLocalState

NOW = datetime(2026, 10, 2, tzinfo=UTC)


def task() -> TaskContract:
    return TaskContract(
        task_id="task-1",
        trace=TraceIdentifiers(trace_id="trace-1", request_id="req-1", span_id="span-1"),
        actor="engineer",
        namespace="engineering",
        objective="Create the reviewed report",
        skills=(AssetIdentity(namespace="engineering", name="report", version="1.0.0"),),
        resource_refs=("source-document",),
        expected_outputs=(
            ExpectedOutput(output_id="report", artifact_ref="report-artifact"),
        ),
        checks=(CompletionCheck(check_id="report-present", output_id="report", kind="nonempty"),),
    )


def test_task_contract_requires_exact_outputs_and_checks() -> None:
    original = task()
    assert TaskContract.model_validate_json(original.model_dump_json()) == original
    assert original.digest == TaskContract.model_validate_json(original.model_dump_json()).digest
    with pytest.raises(ValidationError, match="at least 1"):
        TaskContract.model_validate(original.model_dump() | {"checks": ()})
    with pytest.raises(ValidationError, match="unknown output"):
        TaskContract.model_validate(
            original.model_dump()
            | {"checks": ({"check_id": "unknown", "output_id": "other", "kind": "nonempty"},)}
        )
    with pytest.raises(ValidationError, match="expected_sha256"):
        CompletionCheck(check_id="digest", output_id="report", kind="sha256")
    with pytest.raises(ValidationError, match="unique"):
        TaskContract.model_validate(
            original.model_dump() | {"resource_refs": ("source-document", "source-document")}
        )


def test_task_state_has_no_objective_or_reasoning_and_validates_transitions() -> None:
    original = task()
    pending = begin_task_run(original, backend_id="gateway", now=NOW)
    assert pending.status == "pending" and pending.revision == 0
    serialized = pending.model_dump_json()
    assert "Create the reviewed report" not in serialized
    assert "source-document" not in serialized
    running = advance_task_run(pending, "running", now=NOW + timedelta(seconds=1))
    waiting = advance_task_run(
        running,
        "awaiting_validation",
        now=NOW + timedelta(seconds=2),
        artifact_refs=("report-artifact",),
    )
    assert TaskRunState.model_validate_json(waiting.model_dump_json()) == waiting
    assert waiting.revision == 2
    with pytest.raises(ValueError, match="transition"):
        advance_task_run(waiting, "running", now=NOW + timedelta(seconds=3))
    with pytest.raises(ValueError, match="append"):
        advance_task_run(
            running,
            "awaiting_validation",
            now=NOW + timedelta(seconds=2),
            artifact_refs=("report-artifact", "report-artifact"),
        )


class MemoryArtifacts:
    def __init__(self, items: dict[str, bytes]) -> None:
        self.items = items
        self.reads: list[str] = []

    def read(self, artifact_ref: str) -> bytes | None:
        self.reads.append(artifact_ref)
        return self.items.get(artifact_ref)


def test_independent_validator_rejects_claimed_success_without_real_artifact() -> None:
    original = task()
    running = advance_task_run(begin_task_run(original, "gateway", now=NOW), "running", now=NOW)
    waiting = advance_task_run(
        running, "awaiting_validation", now=NOW, artifact_refs=("report-artifact",)
    )
    missing = MemoryArtifacts({})
    report = CompletionValidator(missing).validate(original, waiting)
    assert report.status == "failed" and report.checks[0].code == "artifact_missing"
    failed = advance_task_run(waiting, "failed", now=NOW, validation=report)
    assert failed.status == "failed"
    assert missing.reads == ["report-artifact"]
    with pytest.raises(ValueError, match="passing validation"):
        advance_task_run(waiting, "validated", now=NOW, validation=report)
    with pytest.raises(ValueError, match="task digest"):
        CompletionValidator(missing).validate(
            original.model_copy(update={"objective": "Another task"}), waiting
        )


def test_validator_checks_bytes_and_stale_results_cannot_finalize() -> None:
    original = task()
    waiting = advance_task_run(
        advance_task_run(begin_task_run(original, "gateway", now=NOW), "running", now=NOW),
        "awaiting_validation",
        now=NOW,
        artifact_refs=("report-artifact",),
    )
    reader = MemoryArtifacts({"report-artifact": b"report contents"})
    report = CompletionValidator(reader).validate(original, waiting)
    assert report.status == "passed" and report.checks[0].observed_sha256 is not None
    done = advance_task_run(waiting, "validated", now=NOW, validation=report)
    assert done.status == "validated" and done.validation == report
    with pytest.raises(ValueError, match="transition"):
        advance_task_run(done, "running", now=NOW)
    stale = report.model_copy(update={"run_revision": report.run_revision - 1})
    with pytest.raises(ValueError, match="revision"):
        advance_task_run(waiting, "validated", now=NOW, validation=stale)
    digest_check = CompletionCheck(
        check_id="report-digest",
        output_id="report",
        kind="sha256",
        expected_sha256="0" * 64,
    )
    wrong = original.model_copy(update={"checks": (digest_check,)})
    wrong_waiting = waiting.model_copy(update={"task_sha256": wrong.digest})
    assert CompletionValidator(reader).validate(wrong, wrong_waiting).checks[0].code == (
        "artifact_digest_mismatch"
    )


def test_local_task_state_survives_restart_and_rejects_stale_or_forged_updates(
    tmp_path: Path,
) -> None:
    path = tmp_path / "state.sqlite"
    original = task()
    pending = begin_task_run(original, "gateway", now=NOW)
    with SqliteLocalState(path, bridge_id="bridge-company") as state:
        state.create_task_run(pending)
        running = advance_task_run(pending, "running", now=NOW + timedelta(seconds=1))
        state.save_task_run(running)
        with pytest.raises(LocalStateError, match="task_update_stale"):
            state.save_task_run(pending)
        with pytest.raises(LocalStateError, match="task_owner_fixed"):
            state.save_task_run(running.model_copy(update={"actor": "other", "revision": 2}))
        forged = running.model_copy(
            update={"revision": 2, "status": "validated", "updated_at": NOW + timedelta(seconds=2)}
        )
        with pytest.raises(ValidationError):
            state.save_task_run(forged)
    with SqliteLocalState(path, bridge_id="bridge-company") as reopened:
        assert reopened.task_run("task-1", "engineer") == running
        assert reopened.task_run("task-1", "other") is None
        assert reopened.task_runs("engineer") == (running,)
        waiting = advance_task_run(
            running,
            "awaiting_validation",
            now=NOW + timedelta(seconds=2),
            artifact_refs=("report-artifact",),
            observations=(TaskObservation(sequence=0, code="backend_finished"),),
        )
        reopened.save_task_run(waiting)
        assert reopened.task_run("task-1", "engineer") == waiting
        report = CompletionValidator(MemoryArtifacts({"report-artifact": b"report"})).validate(
            original, waiting
        )
        validated = advance_task_run(
            waiting, "validated", now=NOW + timedelta(seconds=3), validation=report
        )
        reopened.save_task_run(validated)
        assert reopened.task_run("task-1", "engineer") == validated
    assert b"Create the reviewed report" not in path.read_bytes()


def test_version_four_local_state_migrates_additively(tmp_path: Path) -> None:
    path = tmp_path / "old.sqlite"
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE local_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        connection.executemany(
            "INSERT INTO local_meta (key, value) VALUES (?, ?)",
            (("bridge_id", "bridge-company"), ("schema_version", "4")),
        )
    with SqliteLocalState(path, bridge_id="bridge-company") as state:
        assert state.task_runs("engineer") == ()
        state.create_task_run(begin_task_run(task(), "gateway", now=NOW))
    with sqlite3.connect(path) as connection:
        assert connection.execute(
            "SELECT value FROM local_meta WHERE key = 'schema_version'"
        ).fetchone() == ("5",)
