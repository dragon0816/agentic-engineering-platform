"""Retention: finished durable history may be retired, and a retired idempotency
key can never execute again. Shared over both store backends."""

import asyncio
import itertools
import sqlite3
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from test_checkpoints import (
    StoreFactory,
    changed,
    completed,
    failing,
    payload,
    record,
    started,
    suspended,
)
from test_engine import context
from test_engine_recovery import FailOnce, Stuck, confirmation
from test_gateway_journal import JournalledHost, start

from common.checkpoints import RunCheckpoint
from common.execution import RequestContext, ResumePolicy
from workflow.checkpoints import CheckpointStore, CheckpointStoreError, MemoryCheckpointStore
from workflow.checkpoints_sqlite import SCHEMA_VERSION, SqliteCheckpointStore


@pytest.fixture(params=["memory", "sqlite"])
def make_store(request: pytest.FixtureRequest, tmp_path: Path) -> Iterator[StoreFactory]:
    counter = itertools.count()
    opened: list[SqliteCheckpointStore] = []

    def factory(*, capacity: int = 50) -> CheckpointStore:
        if request.param == "memory":
            return MemoryCheckpointStore(capacity=capacity)
        store = SqliteCheckpointStore(
            tmp_path / f"checkpoints-{next(counter)}.sqlite", capacity=capacity
        )
        opened.append(store)
        return store

    yield factory
    for store in opened:
        store.close()


def finished(store: CheckpointStore, **changes: Any) -> RunCheckpoint:
    """Every step completed and the run succeeded, one legal transition per write."""
    item = store.create(record(**changes))
    item = store.replace(started(item), expected_revision=0)
    item = store.replace(completed(item), expected_revision=1)
    second_started = changed(
        item, steps=[item.steps[0].model_dump(), {"step_index": 1, "state": "started"}]
    )
    item = store.replace(second_started, expected_revision=2)
    done = changed(
        item,
        status="succeeded",
        steps=[
            item.steps[0].model_dump(),
            {"step_index": 1, "state": "completed", "result": payload().model_dump()},
        ],
    )
    return store.replace(done, expected_revision=3)


def continued(store: CheckpointStore) -> tuple[RunCheckpoint, RunCheckpoint]:
    parent = store.create(record(idempotency_key="event-1"))
    parent = store.replace(suspended(parent), expected_revision=0)
    child = changed(
        parent,
        run_id="run-2",
        revision=0,
        status="running",
        suspended_by=None,
        resumed_from=parent.run_id,
        idempotency_key=None,
    )
    child = store.continue_run(child, expected_parent_revision=1)
    linked = store.get(parent.owner, parent.run_id)
    assert linked is not None and linked.continued_by == child.run_id
    return linked, child


def test_a_succeeded_run_can_be_retired_and_frees_its_slot(make_store: StoreFactory) -> None:
    store = make_store(capacity=1)
    item = finished(store)
    assert item.status == "succeeded"
    failing(lambda: store.create(record(run_id="run-2")), "capacity")
    retired = store.retire(item.owner, item.run_id)
    assert retired == item
    assert store.get(item.owner, item.run_id) is None
    assert store.create(record(run_id="run-2")).run_id == "run-2"


def test_a_retired_key_never_executes_again(make_store: StoreFactory) -> None:
    store = make_store(capacity=1)
    item = finished(store, idempotency_key="release-1")
    store.retire(item.owner, item.run_id)
    # The key is gone from lookups but still bound: neither the same nor a
    # different intent may start a run under it, and the slot it held is free.
    assert store.find_key(item.owner, "release-1") is None
    failing(
        lambda: store.create(record(run_id="run-2", idempotency_key="release-1")), "key_retired"
    )
    different = record(run_id="run-2", idempotency_key="release-1", runtime_contract="workflow.v2")
    failing(lambda: store.create(different), "key_retired")
    assert store.create(record(run_id="run-3")).run_id == "run-3"


def test_a_running_record_is_never_history(make_store: StoreFactory) -> None:
    store = make_store()
    running = store.create(record())
    failing(lambda: store.retire(running.owner, running.run_id), "invalid_transition")
    failing(lambda: store.retire(running.owner, "run-unknown"), "missing")
    other = running.owner.model_copy(update={"actor": "someone-else"})
    failing(lambda: store.retire(other, running.run_id), "missing")
    assert store.get(running.owner, running.run_id) == running


def test_a_suspended_run_may_be_given_up_on(make_store: StoreFactory) -> None:
    """The person who confirmed the process gone may also decide not to continue."""
    store = make_store(capacity=1)
    waiting = store.create(record(idempotency_key="event-1"))
    waiting = store.replace(suspended(waiting), expected_revision=0)
    retired = store.retire(waiting.owner, waiting.run_id)
    assert retired.status == "suspended" and retired.continued_by is None
    assert store.get(waiting.owner, waiting.run_id) is None
    failing(lambda: store.create(record(run_id="run-2", idempotency_key="event-1")), "key_retired")
    assert store.create(record(run_id="run-2")).run_id == "run-2"


def test_a_continued_parent_is_history_once_its_child_exists(make_store: StoreFactory) -> None:
    store = make_store()
    parent, child = continued(store)
    retired = store.retire(parent.owner, parent.run_id)
    assert retired.continued_by == child.run_id
    assert store.get(parent.owner, parent.run_id) is None
    # The child's evidence and its link back are untouched; the parent's key is bound.
    kept = store.get(child.owner, child.run_id)
    assert kept == child and kept.resumed_from == parent.run_id
    failing(lambda: store.create(record(run_id="run-3", idempotency_key="event-1")), "key_retired")
    # The child cannot be retired while it is still running.
    failing(lambda: store.retire(child.owner, child.run_id), "invalid_transition")


def test_tombstones_and_schema_survive_a_restart(tmp_path: Path) -> None:
    path = tmp_path / "checkpoints.sqlite"
    with SqliteCheckpointStore(path, capacity=1) as store:
        item = finished(store, idempotency_key="release-1")
        store.retire(item.owner, item.run_id)
    with SqliteCheckpointStore(path, capacity=1) as store:
        failing(
            lambda: store.create(record(run_id="run-2", idempotency_key="release-1")),
            "key_retired",
        )
        assert store.create(record(run_id="run-2")).run_id == "run-2"
    with sqlite3.connect(path) as editor:
        (version,) = editor.execute(
            "SELECT value FROM checkpoint_meta WHERE key = 'schema_version'"
        ).fetchone()
        assert version == SCHEMA_VERSION == "2"


def test_a_version_one_file_is_migrated_in_place(tmp_path: Path) -> None:
    path = tmp_path / "checkpoints.sqlite"
    with SqliteCheckpointStore(path) as store:
        item = finished(store, idempotency_key="release-1")
    with sqlite3.connect(path) as editor:
        # What a slice-10 store left behind: no tombstone table or trigger, version 1.
        editor.execute("DROP TRIGGER checkpoints_refuse_retired_key")
        editor.execute("DROP TABLE retired_keys")
        editor.execute("UPDATE checkpoint_meta SET value = '1' WHERE key = 'schema_version'")
    with SqliteCheckpointStore(path) as store:
        assert store.get(item.owner, item.run_id) == item
        store.retire(item.owner, item.run_id)
        failing(
            lambda: store.create(record(run_id="run-2", idempotency_key="release-1")),
            "key_retired",
        )
    with sqlite3.connect(path) as editor:
        (version,) = editor.execute(
            "SELECT value FROM checkpoint_meta WHERE key = 'schema_version'"
        ).fetchone()
        assert version == "2"


def test_the_database_itself_refuses_a_retired_key(tmp_path: Path) -> None:
    path = tmp_path / "checkpoints.sqlite"
    with SqliteCheckpointStore(path) as store:
        item = finished(store, idempotency_key="release-1")
        store.retire(item.owner, item.run_id)
        fresh = record(run_id="run-2", idempotency_key="release-1")
        # Bypass the store: a write path that forgets the tombstone probe still fails.
        with pytest.raises(sqlite3.IntegrityError, match="key_retired"):
            store._connection().execute(
                "INSERT INTO checkpoints (actor, namespace, run_id, idempotency_key, record)"
                " VALUES (?, ?, ?, ?, ?)",
                (
                    fresh.owner.actor,
                    fresh.owner.namespace,
                    fresh.run_id,
                    fresh.idempotency_key,
                    fresh.model_dump_json(),
                ),
            )
        assert store.get(fresh.owner, fresh.run_id) is None


def test_a_retire_that_fails_to_commit_leaves_the_record(tmp_path: Path) -> None:
    path = tmp_path / "checkpoints.sqlite"
    with SqliteCheckpointStore(path) as store:
        item = finished(store, idempotency_key="release-1")
        original = store._commit

        def broken() -> None:
            raise sqlite3.OperationalError("database is locked")

        store._commit = broken  # type: ignore[method-assign]
        # An error without SQLite's "definitely not committed" name is ambiguous,
        # so the store says so; the caller reads back and finds the record kept.
        failing(lambda: store.retire(item.owner, item.run_id), "commit_unknown")
        store._commit = original  # type: ignore[method-assign]
        assert store.get(item.owner, item.run_id) == item
        assert store.find_key(item.owner, "release-1") == item


@pytest.fixture
def host(tmp_path: Path) -> Any:
    made: list[JournalledHost] = []

    def factory(**changes: Any) -> JournalledHost:
        built = JournalledHost(tmp_path, **changes)
        made.append(built)
        return built

    yield factory
    for built in made:
        built.close()


def test_the_gateway_retires_finished_history_only(host: Any) -> None:
    built = host()
    gateway = built.restart()
    done = start(gateway, built)
    assert done.run.status == "succeeded"
    retired = gateway.retire(context(), done.run.run_id)
    assert retired.action == "retire" and retired.source == "journal"
    assert retired.plan is not None and retired.plan.status == "succeeded"
    # Gone from the durable record; this process's own history is unaffected.
    assert gateway.inspect(context(), done.run.run_id).source == "memory"
    assert built.restart().inspect(context(), done.run.run_id).source == "unknown"
    # Unknown to this caller, and unknown for another owner, look the same.
    assert gateway.retire(context(), done.run.run_id).source == "unknown"
    assert gateway.retire(context(), "run-does-not-exist").source == "unknown"


def test_a_failed_run_leaves_without_running_again(host: Any) -> None:
    """suspend, then retire: the path for a run that failed for good."""
    built = host()
    gateway = built.restart(FailOnce())
    run_id = start(gateway, built).run.run_id
    # Failed, but its durable record is still `running`: not history yet.
    with pytest.raises(CheckpointStoreError, match="invalid_transition"):
        gateway.retire(context(), run_id)
    calls = len(built.handler.calls)
    gateway.suspend(context(), run_id, confirmation(note="not worth continuing"))
    gone = gateway.retire(context(), run_id)
    assert gone.source == "journal" and gone.suspended_by == "leo"
    assert built.restart().inspect(context(), run_id).source == "unknown"
    assert len(built.handler.calls) == calls


def test_a_continued_run_and_its_parent_are_both_retirable(host: Any) -> None:
    built = host()
    gateway = built.restart(FailOnce())
    run_id = start(gateway, built).run.run_id
    gateway.suspend(context(), run_id, confirmation())
    resumed = asyncio.run(
        gateway.resume(context(), run_id, policy=ResumePolicy(uncertain="replay_read_only"))
    )
    assert resumed.workflow is not None and resumed.workflow.run.status == "succeeded"
    # Continued, the parent is history; its confirmation goes with it.
    parent = gateway.retire(context(), run_id)
    assert parent.source == "journal" and parent.suspended_by == "leo"
    assert gateway.retire(context(), resumed.workflow.run.run_id).source == "journal"


def test_another_owner_cannot_learn_that_a_run_is_alive(host: Any) -> None:
    async def scenario() -> None:
        built = host()
        gateway = built.restart(Stuck())
        started_run = await gateway.execute_workflow(
            context(), built.workflow.metadata.identity, {"count": 1}, workflow_timeout_seconds=0.01
        )
        other = RequestContext(
            trace=context().trace,
            actor="someone-else",
            namespace=context().namespace,
            channel="test",
            message="retire",
        )
        try:
            # Alive, but this caller may not learn even that.
            assert gateway.retire(other, started_run.run.run_id).source == "unknown"
        finally:
            gateway.engine._tasks[started_run.run.run_id].cancel()
            await gateway.engine.wait(started_run.run.run_id)

    asyncio.run(scenario())


def test_a_retired_run_is_an_ordinary_run_for_the_rest_of_the_process(host: Any) -> None:
    built = host()
    gateway = built.restart()
    done = start(gateway, built)
    gateway.retire(context(), done.run.run_id)
    # No dead end: the in-memory path answers, and never points back at recovery.
    resumed = asyncio.run(gateway.resume(context(), done.run.run_id))
    assert resumed.source == "memory"
    assert resumed.workflow is not None and resumed.workflow.run.failure is not None
    assert resumed.workflow.run.failure.code != "use_recovery"


def test_a_live_run_cannot_be_retired(host: Any) -> None:
    async def scenario() -> None:
        built = host()
        gateway = built.restart(Stuck())
        started_run = await gateway.execute_workflow(
            context(), built.workflow.metadata.identity, {"count": 1}, workflow_timeout_seconds=0.01
        )
        try:
            with pytest.raises(CheckpointStoreError, match="invalid_transition"):
                gateway.retire(context(), started_run.run.run_id)
        finally:
            gateway.engine._tasks[started_run.run.run_id].cancel()
            await gateway.engine.wait(started_run.run.run_id)

    asyncio.run(scenario())


def test_a_retired_key_is_refused_through_the_engine(host: Any) -> None:
    built = host()
    gateway = built.restart()
    done = asyncio.run(
        gateway.execute_workflow(
            context(),
            built.workflow.metadata.identity,
            {"count": 1},
            workflow_timeout_seconds=10,
            workflow_idempotency_key="release-1",
        )
    )
    assert done.run.status == "succeeded"
    gateway.retire(context(), done.run.run_id)
    calls = len(built.handler.calls)
    again = asyncio.run(
        built.restart().execute_workflow(
            context(),
            built.workflow.metadata.identity,
            {"count": 1},
            workflow_timeout_seconds=10,
            workflow_idempotency_key="release-1",
        )
    )
    assert again.run.failure is not None
    assert again.run.failure.code == "checkpoint_key_retired"
    assert len(built.handler.calls) == calls


def test_an_unjournalled_engine_has_nothing_to_retire(host: Any) -> None:
    built = host(journalled=False)
    gateway = built.restart()
    done = start(gateway, built)
    assert gateway.retire(context(), done.run.run_id).source == "unknown"
    assert gateway.inspect(context(), done.run.run_id).source == "memory"
