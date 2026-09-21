"""Durability of the SQLite checkpoint backend: what survives a restart, what a
second writer sees, and what the caller may conclude after a failed write."""

import sqlite3
from pathlib import Path

import pytest
from test_checkpoints import changed, completed, failing, record, started

from common.checkpoints import RunCheckpoint
from workflow.checkpoints_sqlite import SqliteCheckpointStore


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


def test_evidence_keys_and_links_survive_a_restart(tmp_path: Path) -> None:
    path = tmp_path / "checkpoints.sqlite"
    store = SqliteCheckpointStore(path)
    parent = suspended_parent(store)
    child = store.continue_run(child_of(parent), expected_parent_revision=3)
    store.close()

    reopened = SqliteCheckpointStore(path)
    linked = reopened.get(parent.owner, parent.run_id)
    assert linked is not None and linked.continued_by == child.run_id
    assert linked.revision == 4 and linked.steps[0].state == "completed"
    assert reopened.get(child.owner, child.run_id) == child
    assert reopened.find_key(parent.owner, "event-1") == linked
    # Persisted records count against capacity after a restart.
    failing(
        lambda: SqliteCheckpointStore(path, capacity=2).create(record(run_id="run-3")), "capacity"
    )
    # And a used key still points to the original run, never a new one.
    assert reopened.create(record(idempotency_key="event-1")).run_id == parent.run_id


def test_records_hold_evidence_only(tmp_path: Path) -> None:
    path = tmp_path / "checkpoints.sqlite"
    store = SqliteCheckpointStore(path)
    store.create(record())
    store.close()
    rows = sqlite3.connect(path).execute("SELECT record FROM checkpoints").fetchall()
    assert len(rows) == 1
    # The row holds the payload reference, never an inline argument value.
    assert "payload-1" in rows[0][0] and '"value"' not in rows[0][0]
    assert RunCheckpoint.model_validate_json(rows[0][0]).arguments.ref_id == "payload-1"


def test_unknown_schema_version_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "checkpoints.sqlite"
    SqliteCheckpointStore(path).close()
    with sqlite3.connect(path) as conn:
        conn.execute("UPDATE checkpoint_meta SET value = '2' WHERE key = 'schema_version'")
    failing(lambda: SqliteCheckpointStore(path), "unavailable")


def test_second_writer_is_refused_not_waited_for(tmp_path: Path) -> None:
    path = tmp_path / "checkpoints.sqlite"
    first = SqliteCheckpointStore(path)
    second = SqliteCheckpointStore(path)
    first._conn.execute("BEGIN IMMEDIATE")
    failing(lambda: second.create(record()), "unavailable")
    first._conn.execute("ROLLBACK")
    assert second.create(record()).run_id == "run-1"
    assert first.get(record().owner, "run-1") is not None


def test_invalid_capacity_and_closed_store(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        SqliteCheckpointStore(tmp_path / "x.sqlite", capacity=0)
    store = SqliteCheckpointStore(tmp_path / "checkpoints.sqlite")
    store.close()
    failing(lambda: store.get(record().owner, "run-1"), "unavailable")
    failing(lambda: store.create(record()), "unavailable")


class Armed(SqliteCheckpointStore):
    """Fault injection is armed after construction so the schema setup still commits."""

    armed = False


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


@pytest.mark.parametrize(
    ("store_type", "committed"), [(FailBeforeCommit, False), (FailAfterCommit, True)]
)
def test_commit_unknown_means_read_back(
    tmp_path: Path, store_type: type[Armed], committed: bool
) -> None:
    path = tmp_path / "checkpoints.sqlite"
    parent = suspended_parent(SqliteCheckpointStore(path))
    flaky = store_type(path)
    flaky.armed = True
    failing(
        lambda: flaky.continue_run(child_of(parent), expected_parent_revision=3), "commit_unknown"
    )
    # Reading back from a fresh handle is the only way to learn what happened.
    reopened = SqliteCheckpointStore(path)
    linked = reopened.get(parent.owner, parent.run_id)
    assert linked is not None
    assert (linked.continued_by == "run-2") is committed
    assert (reopened.get(parent.owner, "run-2") is not None) is committed
    # The store itself is usable again either way.
    if not committed:
        assert flaky.get(parent.owner, parent.run_id) == parent


class FailMidTransaction(SqliteCheckpointStore):
    puts = 0

    @staticmethod
    def _put(conn: sqlite3.Connection, item: RunCheckpoint) -> None:
        FailMidTransaction.puts += 1
        if FailMidTransaction.puts == 2:
            raise sqlite3.OperationalError("database or disk is full")
        SqliteCheckpointStore._put(conn, item)


def test_failure_inside_a_transaction_writes_nothing(tmp_path: Path) -> None:
    path = tmp_path / "checkpoints.sqlite"
    parent = suspended_parent(SqliteCheckpointStore(path))
    flaky = FailMidTransaction(path)
    FailMidTransaction.puts = 0
    failing(lambda: flaky.continue_run(child_of(parent), expected_parent_revision=3), "unavailable")
    reopened = SqliteCheckpointStore(path)
    assert reopened.get(parent.owner, parent.run_id) == parent
    assert reopened.get(parent.owner, "run-2") is None
    # unavailable means known not committed: the same write may simply be retried.
    assert flaky.continue_run(child_of(parent), expected_parent_revision=3).run_id == "run-2"
