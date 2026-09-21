"""Single-writer durable checkpoint backend on one local SQLite file.

Every write is one `BEGIN IMMEDIATE` transaction that is acknowledged only after
`COMMIT` returns; the shared transition rules in `workflow.checkpoints` decide
legality. The file location is host configuration (never inside the project),
records hold only checkpoint evidence and payload references, and nothing here
resolves payloads, enforces policy or recovers runs automatically.
"""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from common.checkpoints import CheckpointOwner, RunCheckpoint
from common.execution import IdempotencyKey, RunId
from workflow.checkpoints import (
    CheckpointStoreError,
    check_continue,
    check_create,
    check_replace,
    checked_copy,
    linked_parent,
    same_intent,
    validate_key,
    validate_owner,
    validate_run_id,
)

SCHEMA_VERSION = "1"
_SCHEMA = (
    "CREATE TABLE IF NOT EXISTS checkpoint_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)",
    "CREATE TABLE IF NOT EXISTS checkpoints ("
    " actor TEXT NOT NULL, namespace TEXT NOT NULL, run_id TEXT NOT NULL,"
    " idempotency_key TEXT, record TEXT NOT NULL,"
    " PRIMARY KEY (actor, namespace, run_id))",
    "CREATE INDEX IF NOT EXISTS checkpoints_key ON checkpoints (actor, namespace, idempotency_key)",
)


class SqliteCheckpointStore:
    """One process, one owning thread, one file. A second writer on the same file
    is refused with `unavailable` rather than waited for."""

    def __init__(self, path: Path, *, capacity: int = 50) -> None:
        if type(capacity) is not int or capacity < 1:
            raise ValueError("capacity must be a positive integer")
        self._capacity = capacity
        self._path = Path(path)
        try:
            self._conn = sqlite3.connect(self._path, isolation_level=None, timeout=0)
            self._conn.execute("PRAGMA synchronous=FULL")
            with self._write() as conn:
                for statement in _SCHEMA:
                    conn.execute(statement)
                row = conn.execute(
                    "SELECT value FROM checkpoint_meta WHERE key = 'schema_version'"
                ).fetchone()
                if row is None:
                    conn.execute(
                        "INSERT INTO checkpoint_meta (key, value) VALUES ('schema_version', ?)",
                        (SCHEMA_VERSION,),
                    )
                elif row[0] != SCHEMA_VERSION:
                    raise CheckpointStoreError("unavailable")
        except sqlite3.Error:
            raise CheckpointStoreError("unavailable") from None

    def close(self) -> None:
        self._conn.close()

    @contextmanager
    def _write(self) -> Iterator[sqlite3.Connection]:
        """One atomic write. `unavailable` means known not committed; `commit_unknown`
        means the acknowledgment was lost and the caller must read back."""
        try:
            self._conn.execute("BEGIN IMMEDIATE")
        except sqlite3.Error:
            raise CheckpointStoreError("unavailable") from None
        try:
            yield self._conn
        except CheckpointStoreError:
            self._rollback()
            raise
        except sqlite3.Error:
            self._rollback()
            raise CheckpointStoreError("unavailable") from None
        try:
            self._commit()
        except sqlite3.Error:
            # The commit may or may not have reached the file; never guess.
            self._rollback()
            raise CheckpointStoreError("commit_unknown") from None

    def _commit(self) -> None:
        self._conn.execute("COMMIT")

    def _rollback(self) -> None:
        try:
            self._conn.execute("ROLLBACK")
        except sqlite3.Error:
            pass

    @staticmethod
    def _load(row: tuple[str] | None) -> RunCheckpoint | None:
        return RunCheckpoint.model_validate_json(row[0]) if row is not None else None

    def _select(
        self, conn: sqlite3.Connection, owner: CheckpointOwner, run_id: str
    ) -> RunCheckpoint | None:
        row = conn.execute(
            "SELECT record FROM checkpoints WHERE actor = ? AND namespace = ? AND run_id = ?",
            (owner.actor, owner.namespace, run_id),
        ).fetchone()
        return self._load(row)

    def _select_key(
        self, conn: sqlite3.Connection, owner: CheckpointOwner, key: str
    ) -> RunCheckpoint | None:
        row = conn.execute(
            "SELECT record FROM checkpoints"
            " WHERE actor = ? AND namespace = ? AND idempotency_key = ?",
            (owner.actor, owner.namespace, key),
        ).fetchone()
        return self._load(row)

    def _room(self, conn: sqlite3.Connection, item: RunCheckpoint) -> None:
        if self._select(conn, item.owner, item.run_id) is not None:
            raise CheckpointStoreError("conflict")
        (count,) = conn.execute("SELECT COUNT(*) FROM checkpoints").fetchone()
        if count >= self._capacity:
            raise CheckpointStoreError("capacity")

    @staticmethod
    def _put(conn: sqlite3.Connection, item: RunCheckpoint) -> None:
        conn.execute(
            "INSERT OR REPLACE INTO checkpoints"
            " (actor, namespace, run_id, idempotency_key, record) VALUES (?, ?, ?, ?, ?)",
            (
                item.owner.actor,
                item.owner.namespace,
                item.run_id,
                item.idempotency_key,
                item.model_dump_json(),
            ),
        )

    def get(self, owner: CheckpointOwner, run_id: RunId) -> RunCheckpoint | None:
        try:
            return self._select(self._conn, validate_owner(owner), validate_run_id(run_id))
        except sqlite3.Error:
            raise CheckpointStoreError("unavailable") from None

    def find_key(self, owner: CheckpointOwner, key: IdempotencyKey) -> RunCheckpoint | None:
        try:
            return self._select_key(self._conn, validate_owner(owner), validate_key(key))
        except sqlite3.Error:
            raise CheckpointStoreError("unavailable") from None

    def create(self, checkpoint: RunCheckpoint) -> RunCheckpoint:
        item = checked_copy(checkpoint)
        check_create(item)
        with self._write() as conn:
            if item.idempotency_key is not None:
                existing = self._select_key(conn, item.owner, item.idempotency_key)
                if existing is not None:
                    if not same_intent(existing, item):
                        raise CheckpointStoreError("key_conflict")
                    return existing
            self._room(conn, item)
            self._put(conn, item)
        return item

    def replace(self, checkpoint: RunCheckpoint, *, expected_revision: int) -> RunCheckpoint:
        item = checked_copy(checkpoint)
        with self._write() as conn:
            old = self._select(conn, item.owner, item.run_id)
            if old is None:
                raise CheckpointStoreError("missing")
            check_replace(old, item, expected_revision)
            updated = item.model_copy(update={"revision": old.revision + 1})
            self._put(conn, updated)
        return updated

    def continue_run(self, child: RunCheckpoint, *, expected_parent_revision: int) -> RunCheckpoint:
        item = checked_copy(child)
        if item.resumed_from is None:
            raise CheckpointStoreError("invalid_transition")
        with self._write() as conn:
            parent = self._select(conn, item.owner, item.resumed_from)
            if parent is None:
                raise CheckpointStoreError("missing")
            check_continue(parent, item, expected_parent_revision)
            self._room(conn, item)
            self._put(conn, linked_parent(parent, item))
            self._put(conn, item)
        return item
