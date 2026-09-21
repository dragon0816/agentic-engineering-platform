"""Durability of the SQLite checkpoint backend: what survives a restart, what a
second writer sees, and what the caller may conclude after a failed write."""

import os
import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest
from test_checkpoints import changed, completed, failing, record, started

from common.checkpoints import RunCheckpoint
from workflow.checkpoints import StoreErrorCode
from workflow.checkpoints_sqlite import SqliteCheckpointStore


@pytest.fixture
def opened() -> Iterator[list[SqliteCheckpointStore]]:
    """Every store a test opens is closed afterwards so no file handle outlives it."""
    stores: list[SqliteCheckpointStore] = []
    yield stores
    for store in stores:
        store.close()


def suspended_parent(store: SqliteCheckpointStore) -> RunCheckpoint:
    parent = store.create(record(idempotency_key="event-1"))
    parent = store.replace(started(parent), expected_revision=0)
    parent = store.replace(completed(parent), expected_revision=1)
    return store.replace(changed(parent, status="suspended"), expected_revision=2)


def child_of(parent: RunCheckpoint) -> RunCheckpoint:
    return changed(
        parent,
        run_id="run-2",
        revision=0,
        status="running",
        resumed_from=parent.run_id,
        idempotency_key=None,
    )


def test_evidence_keys_and_links_survive_a_restart(
    tmp_path: Path, opened: list[SqliteCheckpointStore]
) -> None:
    path = tmp_path / "checkpoints.sqlite"
    with SqliteCheckpointStore(path) as store:
        parent = suspended_parent(store)
        child = store.continue_run(child_of(parent), expected_parent_revision=3)

    reopened = SqliteCheckpointStore(path)
    opened.append(reopened)
    linked = reopened.get(parent.owner, parent.run_id)
    assert linked is not None and linked.continued_by == child.run_id
    assert linked.revision == 4 and linked.steps[0].state == "completed"
    assert reopened.get(child.owner, child.run_id) == child
    assert reopened.find_key(parent.owner, "event-1") == linked
    # Persisted records count against capacity after a restart.
    small = SqliteCheckpointStore(path, capacity=2)
    opened.append(small)
    failing(lambda: small.create(record(run_id="run-3")), "capacity")
    # And a used key still points to the original run, never a new one.
    assert reopened.create(record(idempotency_key="event-1")).run_id == parent.run_id


def test_records_hold_evidence_only(tmp_path: Path) -> None:
    path = tmp_path / "checkpoints.sqlite"
    with SqliteCheckpointStore(path) as store:
        store.create(record())
    reader = sqlite3.connect(path)
    rows = reader.execute("SELECT record FROM checkpoints").fetchall()
    index = reader.execute(
        "SELECT sql FROM sqlite_master WHERE name = 'checkpoints_key'"
    ).fetchone()
    reader.close()
    assert len(rows) == 1
    # The row holds the payload reference, never an inline argument value.
    assert "payload-1" in rows[0][0] and '"value"' not in rows[0][0]
    assert RunCheckpoint.model_validate_json(rows[0][0]).arguments.ref_id == "payload-1"
    assert index is not None and "UNIQUE" in index[0]


def test_unknown_schema_version_is_refused_and_leaves_no_handle(tmp_path: Path) -> None:
    path = tmp_path / "checkpoints.sqlite"
    SqliteCheckpointStore(path).close()
    editor = sqlite3.connect(path)
    with editor:
        editor.execute("UPDATE checkpoint_meta SET value = '2' WHERE key = 'schema_version'")
    editor.close()  # the context manager commits but keeps the handle open
    failing(lambda: SqliteCheckpointStore(path), "unavailable")
    # A failed open closed its connection: on Windows the file could not move otherwise.
    os.replace(path, path.with_suffix(".moved"))


def test_second_writer_is_refused_not_waited_for(
    tmp_path: Path, opened: list[SqliteCheckpointStore]
) -> None:
    path = tmp_path / "checkpoints.sqlite"
    first, second = SqliteCheckpointStore(path), SqliteCheckpointStore(path)
    opened.extend([first, second])
    first._connection().execute("BEGIN IMMEDIATE")
    failing(lambda: second.create(record()), "unavailable")
    first._connection().execute("ROLLBACK")
    assert second.create(record()).run_id == "run-1"
    assert first.get(record().owner, "run-1") is not None


def test_invalid_capacity_and_closed_store(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        SqliteCheckpointStore(tmp_path / "x.sqlite", capacity=0)
    store = SqliteCheckpointStore(tmp_path / "checkpoints.sqlite")
    store.close()
    store.close()
    failing(lambda: store.get(record().owner, "run-1"), "unavailable")
    failing(lambda: store.create(record()), "unavailable")


def test_undecodable_record_fails_closed_without_wedging_the_store(
    tmp_path: Path, opened: list[SqliteCheckpointStore]
) -> None:
    path = tmp_path / "checkpoints.sqlite"
    store = SqliteCheckpointStore(path)
    opened.append(store)
    item = store.create(record())
    editor = sqlite3.connect(path)
    with editor:
        editor.execute("UPDATE checkpoints SET record = '{\"bad\": 1}' WHERE run_id = 'run-1'")
    editor.close()
    failing(lambda: store.get(item.owner, item.run_id), "unavailable")
    failing(lambda: store.replace(started(item), expected_revision=0), "unavailable")
    # The failed write rolled back: the store and the file remain usable.
    assert store.create(record(run_id="run-2")).run_id == "run-2"
    with SqliteCheckpointStore(path) as other:
        assert other.get(item.owner, "run-2") is not None


class Armed(SqliteCheckpointStore):
    """Fault injection is armed after construction so the schema setup still commits."""

    armed = False


class Busy(sqlite3.OperationalError):
    sqlite_errorname = "SQLITE_BUSY"


class FailBeforeCommit(Armed):
    def _commit(self) -> None:
        if self.armed:
            raise sqlite3.OperationalError("disk I/O error")
        super()._commit()


class FailAfterCommit(Armed):
    def _commit(self) -> None:
        super()._commit()
        if self.armed:
            raise sqlite3.OperationalError("acknowledgment lost")


class BusyAtCommit(Armed):
    def _commit(self) -> None:
        if self.armed:
            raise Busy("database is locked")
        super()._commit()


@pytest.mark.parametrize(
    ("store_type", "code", "committed"),
    [
        (FailBeforeCommit, "commit_unknown", False),
        (FailAfterCommit, "commit_unknown", True),
        (BusyAtCommit, "unavailable", False),
    ],
)
def test_commit_outcomes_are_classified(
    tmp_path: Path,
    opened: list[SqliteCheckpointStore],
    store_type: type[Armed],
    code: StoreErrorCode,
    committed: bool,
) -> None:
    path = tmp_path / "checkpoints.sqlite"
    with SqliteCheckpointStore(path) as setup:
        parent = suspended_parent(setup)
    flaky = store_type(path)
    opened.append(flaky)
    flaky.armed = True
    failing(lambda: flaky.continue_run(child_of(parent), expected_parent_revision=3), code)
    # Reading back from a fresh handle is the only way to learn what happened.
    reopened = SqliteCheckpointStore(path)
    opened.append(reopened)
    linked = reopened.get(parent.owner, parent.run_id)
    assert linked is not None
    assert (linked.continued_by == "run-2") is committed
    assert (reopened.get(parent.owner, "run-2") is not None) is committed
    if not committed:
        # Known non-commit or a rolled-back attempt: the store itself is still usable.
        flaky.armed = False
        assert flaky.continue_run(child_of(parent), expected_parent_revision=3).run_id == "run-2"


class FailMidTransaction(SqliteCheckpointStore):
    puts = 0

    @staticmethod
    def _insert(conn: sqlite3.Connection, item: RunCheckpoint) -> None:
        FailMidTransaction.puts += 1
        if FailMidTransaction.puts == 1:
            raise sqlite3.OperationalError("database or disk is full")
        SqliteCheckpointStore._insert(conn, item)


def test_failure_inside_a_transaction_writes_nothing(
    tmp_path: Path, opened: list[SqliteCheckpointStore]
) -> None:
    path = tmp_path / "checkpoints.sqlite"
    with SqliteCheckpointStore(path) as setup:
        parent = suspended_parent(setup)
    flaky = FailMidTransaction(path)
    opened.append(flaky)
    FailMidTransaction.puts = 0
    # The parent link is written before the child insert fails; both must vanish.
    failing(lambda: flaky.continue_run(child_of(parent), expected_parent_revision=3), "unavailable")
    with SqliteCheckpointStore(path) as reopened:
        assert reopened.get(parent.owner, parent.run_id) == parent
        assert reopened.get(parent.owner, "run-2") is None
    # unavailable means known not committed: the same write may simply be retried.
    assert flaky.continue_run(child_of(parent), expected_parent_revision=3).run_id == "run-2"
