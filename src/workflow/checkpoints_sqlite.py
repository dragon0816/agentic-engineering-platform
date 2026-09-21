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
from types import TracebackType
from typing import Self

from pydantic import ValidationError

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
    # The database, not only the application, refuses a second binding of a key.
    "CREATE UNIQUE INDEX IF NOT EXISTS checkpoints_key"
    " ON checkpoints (actor, namespace, idempotency_key) WHERE idempotency_key IS NOT NULL",
)
# Commit outcomes SQLite reports as definitely not committed; anything else is ambiguous.
_NOT_COMMITTED = frozenset({"SQLITE_BUSY", "SQLITE_LOCKED"})


class SqliteCheckpointStore:
    """One process, one owning thread, one file. A second writer on the same file
    is refused with `unavailable` rather than waited for."""

    def __init__(self, path: Path, *, capacity: int = 50) -> None:
        if type(capacity) is not int or capacity < 1:
            raise ValueError("capacity must be a positive integer")
        self._capacity = capacity
        self._path = Path(path)
        self._conn: sqlite3.Connection | None = None
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
        except BaseException:
            # Never leak a half-built handle; on Windows it would pin the file.
            self.close()
            raise

    def close(self) -> None:
        conn, self._conn = self._conn, None
        if conn is not None:
            conn.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def _connection(self) -> sqlite3.Connection:
        if self._conn is None:
            raise CheckpointStoreError("unavailable")
        return self._conn

    @contextmanager
    def _write(self) -> Iterator[sqlite3.Connection]:
        """One atomic write. `unavailable` means known not committed; `commit_unknown`
        means the acknowledgment was lost and the caller must read back. Whatever
        happens inside, the transaction never stays open on the connection."""
        conn = self._connection()
        try:
            conn.execute("BEGIN IMMEDIATE")
        except sqlite3.Error:
            raise CheckpointStoreError("unavailable") from None
        try:
            yield conn
        except BaseException as error:
            self._rollback()
            if isinstance(error, CheckpointStoreError):
                raise
            if isinstance(error, sqlite3.IntegrityError):
                raise CheckpointStoreError("conflict") from None
            if isinstance(error, sqlite3.Error):
                raise CheckpointStoreError("unavailable") from None
            raise
        try:
            self._commit()
        except sqlite3.Error as error:
            self._rollback()
            if getattr(error, "sqlite_errorname", "") in _NOT_COMMITTED:
                raise CheckpointStoreError("unavailable") from None
            # The commit may or may not have reached the file; never guess.
            raise CheckpointStoreError("commit_unknown") from None

    def _commit(self) -> None:
        self._connection().execute("COMMIT")

    def _rollback(self) -> None:
        try:
            if self._conn is not None and self._conn.in_transaction:
                self._conn.execute("ROLLBACK")
        except sqlite3.Error:
            pass

    @staticmethod
    def _load(row: tuple[str] | None) -> RunCheckpoint | None:
        if row is None:
            return None
        try:
            return RunCheckpoint.model_validate_json(row[0])
        except ValidationError:
            # An undecodable record is unusable evidence; fail closed, never guess.
            raise CheckpointStoreError("unavailable") from None

    @staticmethod
    def _select(
        conn: sqlite3.Connection, owner: CheckpointOwner, run_id: str
    ) -> RunCheckpoint | None:
        row = conn.execute(
            "SELECT record FROM checkpoints WHERE actor = ? AND namespace = ? AND run_id = ?",
            (owner.actor, owner.namespace, run_id),
        ).fetchone()
        return SqliteCheckpointStore._load(row)

    @staticmethod
    def _select_key(
        conn: sqlite3.Connection, owner: CheckpointOwner, key: str
    ) -> RunCheckpoint | None:
        row = conn.execute(
            "SELECT record FROM checkpoints"
            " WHERE actor = ? AND namespace = ? AND idempotency_key = ?",
            (owner.actor, owner.namespace, key),
        ).fetchone()
        return SqliteCheckpointStore._load(row)

    def _room(self, conn: sqlite3.Connection, item: RunCheckpoint) -> None:
        exists = conn.execute(
            "SELECT 1 FROM checkpoints WHERE actor = ? AND namespace = ? AND run_id = ?",
            (item.owner.actor, item.owner.namespace, item.run_id),
        ).fetchone()
        if exists is not None:
            raise CheckpointStoreError("conflict")
        (count,) = conn.execute("SELECT COUNT(*) FROM checkpoints").fetchone()
        if count >= self._capacity:
            raise CheckpointStoreError("capacity")

    @staticmethod
    def _insert(conn: sqlite3.Connection, item: RunCheckpoint) -> None:
        conn.execute(
            "INSERT INTO checkpoints (actor, namespace, run_id, idempotency_key, record)"
            " VALUES (?, ?, ?, ?, ?)",
            (
                item.owner.actor,
                item.owner.namespace,
                item.run_id,
                item.idempotency_key,
                item.model_dump_json(),
            ),
        )

    @staticmethod
    def _update(conn: sqlite3.Connection, item: RunCheckpoint) -> None:
        changed = conn.execute(
            "UPDATE checkpoints SET record = ? WHERE actor = ? AND namespace = ? AND run_id = ?",
            (item.model_dump_json(), item.owner.actor, item.owner.namespace, item.run_id),
        ).rowcount
        if changed != 1:
            raise CheckpointStoreError("missing")

    def get(self, owner: CheckpointOwner, run_id: RunId) -> RunCheckpoint | None:
        try:
            return self._select(self._connection(), validate_owner(owner), validate_run_id(run_id))
        except sqlite3.Error:
            raise CheckpointStoreError("unavailable") from None

    def find_key(self, owner: CheckpointOwner, key: IdempotencyKey) -> RunCheckpoint | None:
        try:
            return self._select_key(self._connection(), validate_owner(owner), validate_key(key))
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
            self._insert(conn, item)
        return item

    def replace(self, checkpoint: RunCheckpoint, *, expected_revision: int) -> RunCheckpoint:
        item = checked_copy(checkpoint)
        with self._write() as conn:
            old = self._select(conn, item.owner, item.run_id)
            if old is None:
                raise CheckpointStoreError("missing")
            check_replace(old, item, expected_revision)
            updated = item.model_copy(update={"revision": old.revision + 1})
            self._update(conn, updated)
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
            self._update(conn, linked_parent(parent, item))
            self._insert(conn, item)
        return item
