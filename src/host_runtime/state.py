"""Durable local inventory and run state on one SQLite file.

The Bridge computer owns the authoritative record of what is installed on it
and what has run there; the control plane only projects it. This is that
record: one file, one writer, every write one committed transaction, following
the checkpoint store in `workflow.checkpoints_sqlite`. It holds installed-asset
rows and compact run summaries and nothing else: no artifact bytes, no payload,
no credential, no session.
"""

import sqlite3
import threading
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from types import TracebackType
from typing import Self

from pydantic import TypeAdapter

from common.base import Symbol
from common.distribution import (
    BridgeStateSnapshot,
    InstallationPlan,
    InstalledAsset,
    LocalRunSummary,
    LocalStateError,
    verify_installation,
)
from common.enrollment import BridgeDevice

SCHEMA_VERSION = "1"
_SCHEMA = (
    "CREATE TABLE IF NOT EXISTS local_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)",
    "CREATE TABLE IF NOT EXISTS installed ("
    " namespace TEXT NOT NULL, name TEXT NOT NULL, version TEXT NOT NULL,"
    " record TEXT NOT NULL, PRIMARY KEY (namespace, name, version))",
    "CREATE TABLE IF NOT EXISTS runs ("
    " run_id TEXT PRIMARY KEY, actor TEXT NOT NULL, updated_at TEXT NOT NULL,"
    " record TEXT NOT NULL)",
)


class SqliteLocalState:
    """One process, one owning thread, one file, one device. The file records
    which Bridge it belongs to on first open and refuses another, so a state
    file cannot quietly become some other device's inventory."""

    def __init__(self, path: Path, *, bridge_id: Symbol) -> None:
        self.bridge_id = TypeAdapter(Symbol).validate_python(bridge_id)
        self._path = Path(path)
        self._conn: sqlite3.Connection | None = None
        self._lock = threading.RLock()
        try:
            self._conn = sqlite3.connect(
                self._path, isolation_level=None, timeout=0, check_same_thread=False
            )
            self._conn.execute("PRAGMA synchronous=FULL")
            with self._write() as conn:
                for statement in _SCHEMA:
                    conn.execute(statement)
                self._claim(conn, "schema_version", SCHEMA_VERSION)
                self._claim(conn, "bridge_id", self.bridge_id)
        except BaseException:
            # Never leak a half-built handle; on Windows it would pin the file.
            self.close()
            raise

    @staticmethod
    def _claim(conn: sqlite3.Connection, key: str, value: str) -> None:
        """Write a mark on a fresh file, or insist the existing one matches."""
        row = conn.execute("SELECT value FROM local_meta WHERE key = ?", (key,)).fetchone()
        if row is None:
            conn.execute("INSERT INTO local_meta (key, value) VALUES (?, ?)", (key, value))
        elif row[0] != value:
            raise LocalStateError("unavailable")

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
            raise LocalStateError("unavailable")
        return self._conn

    @contextmanager
    def _write(self) -> Iterator[sqlite3.Connection]:
        """One atomic write. Whatever happens inside, the transaction never
        stays open on the connection, and a rule that refuses leaves the file
        exactly as it was."""
        with self._lock:
            conn = self._connection()
            try:
                conn.execute("BEGIN IMMEDIATE")
            except sqlite3.Error:
                raise LocalStateError("unavailable") from None
            try:
                yield conn
            except BaseException:
                conn.execute("ROLLBACK")
                raise
            try:
                conn.execute("COMMIT")
            except sqlite3.Error:
                conn.execute("ROLLBACK")
                raise LocalStateError("unavailable") from None

    def _read(self) -> sqlite3.Connection:
        with self._lock:
            return self._connection()

    def installed(self) -> tuple[InstalledAsset, ...]:
        rows = (
            self._read()
            .execute("SELECT record FROM installed ORDER BY namespace, name, version")
            .fetchall()
        )
        return tuple(InstalledAsset.model_validate_json(row[0]) for row in rows)

    def install(
        self, plan: InstallationPlan, artifacts: Mapping[str, bytes]
    ) -> tuple[InstalledAsset, ...]:
        """Verify the whole plan, then write it in one transaction. The rule
        is `verify_installation`, shared with the in-memory reference."""
        with self._write() as conn:
            present = {
                (row[0], row[1], row[2])
                for row in conn.execute("SELECT namespace, name, version FROM installed")
            }
            added = verify_installation(
                plan, artifacts, bridge_id=self.bridge_id, installed=present
            )
            for item in added:
                conn.execute(
                    "INSERT INTO installed (namespace, name, version, record) VALUES (?, ?, ?, ?)",
                    (*item.identity.key, item.model_dump_json()),
                )
        return added

    def record_run(self, summary: LocalRunSummary) -> LocalRunSummary:
        """A run belongs to the actor who started it for as long as the record
        exists, and a record never moves backwards in time."""
        item = LocalRunSummary.model_validate(summary)
        with self._write() as conn:
            row = conn.execute(
                "SELECT record FROM runs WHERE run_id = ?", (item.run_id,)
            ).fetchone()
            if row is not None:
                stored = LocalRunSummary.model_validate_json(row[0])
                if stored.actor != item.actor:
                    raise LocalStateError("run_owner_fixed")
                if item.updated_at < stored.updated_at:
                    raise LocalStateError("run_update_stale")
            conn.execute(
                "INSERT OR REPLACE INTO runs (run_id, actor, updated_at, record)"
                " VALUES (?, ?, ?, ?)",
                (item.run_id, item.actor, item.updated_at.isoformat(), item.model_dump_json()),
            )
        return item

    def runs(self) -> tuple[LocalRunSummary, ...]:
        rows = (
            self._read().execute("SELECT record FROM runs ORDER BY updated_at, run_id").fetchall()
        )
        return tuple(LocalRunSummary.model_validate_json(row[0]) for row in rows)

    def snapshot(self, device: BridgeDevice, *, observed_at: datetime) -> BridgeStateSnapshot:
        """The authoritative state the control plane may project. The
        snapshot's own contract refuses a run newer than the observation."""
        return BridgeStateSnapshot(
            device=device,
            observed_at=observed_at,
            installed=self.installed(),
            runs=self.runs(),
        )
