"""Durable local schedule definitions and atomic due claims.

This store never executes a target. A later worker must submit each claim's
exact target and stable idempotency key through the resident Agent's existing
admission, Workflow engine and Bridge policy, then record the actual outcome.
"""

import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType
from typing import Literal, Self

from pydantic import TypeAdapter, ValidationError

from common.base import Symbol
from common.scheduling import (
    ScheduleDefinition,
    ScheduledRun,
    ScheduleRecord,
    claim_key,
    next_occurrence,
)

ScheduleErrorCode = Literal[
    "unavailable", "commit_unknown", "exists", "unknown", "owner_mismatch", "outcome_conflict"
]


class ScheduleStoreError(Exception):
    def __init__(self, code: ScheduleErrorCode) -> None:
        self.code = code
        super().__init__(code)


_SCHEMA = (
    "CREATE TABLE IF NOT EXISTS schedule_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)",
    "CREATE TABLE IF NOT EXISTS schedules ("
    " schedule_id TEXT PRIMARY KEY, owner TEXT NOT NULL, status TEXT NOT NULL,"
    " next_due_at TEXT NOT NULL, record TEXT NOT NULL)",
    "CREATE INDEX IF NOT EXISTS schedules_due ON schedules (status, next_due_at)",
    "CREATE TABLE IF NOT EXISTS scheduled_runs ("
    " idempotency_key TEXT PRIMARY KEY, schedule_id TEXT NOT NULL, due_at TEXT NOT NULL,"
    " status TEXT NOT NULL, record TEXT NOT NULL,"
    " UNIQUE (schedule_id, due_at))",
    "CREATE INDEX IF NOT EXISTS scheduled_runs_status ON scheduled_runs (status, due_at)",
)


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("schedule store timestamps require a timezone")
    return value.astimezone(UTC)


class SqliteScheduleStore:
    """One Host-owned SQLite file; due advancement and claim insert are atomic."""

    def __init__(self, path: Path, *, bridge_id: Symbol) -> None:
        self.bridge_id = TypeAdapter(Symbol).validate_python(bridge_id)
        self._conn: sqlite3.Connection | None = None
        self._lock = threading.RLock()
        try:
            self._conn = sqlite3.connect(
                Path(path), isolation_level=None, timeout=0, check_same_thread=False
            )
            self._conn.execute("PRAGMA synchronous=FULL")
            with self._write() as conn:
                for statement in _SCHEMA:
                    conn.execute(statement)
                for key, value in (("schema_version", "1"), ("bridge_id", self.bridge_id)):
                    row = conn.execute(
                        "SELECT value FROM schedule_meta WHERE key = ?", (key,)
                    ).fetchone()
                    if row is None:
                        conn.execute(
                            "INSERT INTO schedule_meta (key, value) VALUES (?, ?)",
                            (key, value),
                        )
                    elif row[0] != value:
                        raise ScheduleStoreError("unavailable")
        except BaseException as error:
            self.close()
            if isinstance(error, sqlite3.Error):
                raise ScheduleStoreError("unavailable") from None
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
            raise ScheduleStoreError("unavailable")
        return self._conn

    @contextmanager
    def _write(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            conn = self._connection()
            try:
                conn.execute("BEGIN IMMEDIATE")
            except sqlite3.Error:
                raise ScheduleStoreError("unavailable") from None
            try:
                yield conn
            except BaseException as error:
                if conn.in_transaction:
                    conn.execute("ROLLBACK")
                if isinstance(error, sqlite3.Error):
                    raise ScheduleStoreError("unavailable") from None
                raise
            try:
                conn.execute("COMMIT")
            except sqlite3.Error as error:
                if conn.in_transaction:
                    conn.execute("ROLLBACK")
                if getattr(error, "sqlite_errorname", "") in {"SQLITE_BUSY", "SQLITE_LOCKED"}:
                    raise ScheduleStoreError("unavailable") from None
                raise ScheduleStoreError("commit_unknown") from None

    def create(self, definition: ScheduleDefinition, *, now: datetime) -> ScheduleRecord:
        item = ScheduleDefinition.model_validate(definition)
        due = next_occurrence(item.recurrence, after=_utc(now), inclusive=True)
        record = ScheduleRecord(
            definition=item,
            status=item.initial_status,
            next_due_at=due,
        )
        with self._write() as conn:
            if conn.execute(
                "SELECT 1 FROM schedules WHERE schedule_id = ?", (item.schedule_id,)
            ).fetchone():
                raise ScheduleStoreError("exists")
            conn.execute(
                "INSERT INTO schedules (schedule_id, owner, status, next_due_at, record)"
                " VALUES (?, ?, ?, ?, ?)",
                (
                    item.schedule_id,
                    item.owner,
                    record.status,
                    due.isoformat(),
                    record.model_dump_json(),
                ),
            )
        return record

    def get(self, schedule_id: str, *, owner: str) -> ScheduleRecord:
        with self._lock:
            try:
                row = self._connection().execute(
                    "SELECT owner, record FROM schedules WHERE schedule_id = ?", (schedule_id,)
                ).fetchone()
                if row is None:
                    raise ScheduleStoreError("unknown")
                if row[0] != owner:
                    raise ScheduleStoreError("owner_mismatch")
                return ScheduleRecord.model_validate_json(row[1])
            except (sqlite3.Error, ValidationError):
                raise ScheduleStoreError("unavailable") from None

    def list(self, *, owner: str) -> tuple[ScheduleRecord, ...]:
        with self._lock:
            try:
                rows = self._connection().execute(
                    "SELECT record FROM schedules WHERE owner = ? ORDER BY schedule_id", (owner,)
                ).fetchall()
                return tuple(ScheduleRecord.model_validate_json(row[0]) for row in rows)
            except (sqlite3.Error, ValidationError):
                raise ScheduleStoreError("unavailable") from None

    def set_active(
        self, schedule_id: str, *, owner: str, active: bool, now: datetime
    ) -> ScheduleRecord:
        point = _utc(now)
        with self._write() as conn:
            row = conn.execute(
                "SELECT owner, record FROM schedules WHERE schedule_id = ?", (schedule_id,)
            ).fetchone()
            if row is None:
                raise ScheduleStoreError("unknown")
            if row[0] != owner:
                raise ScheduleStoreError("owner_mismatch")
            old = ScheduleRecord.model_validate_json(row[1])
            if (old.status == "active") == active:
                return old
            # Paused occurrences are skipped; a resume starts from now.
            due = (
                next_occurrence(old.definition.recurrence, after=point, inclusive=True)
                if active
                else old.next_due_at
            )
            updated = ScheduleRecord(
                definition=old.definition,
                status="active" if active else "paused",
                next_due_at=due,
            )
            conn.execute(
                "UPDATE schedules SET status = ?, next_due_at = ?, record = ?"
                " WHERE schedule_id = ?",
                (updated.status, due.isoformat(), updated.model_dump_json(), schedule_id),
            )
            return updated

    def claim_due(
        self, *, now: datetime, limit: int = 20, owner: str | None = None
    ) -> tuple[ScheduledRun, ...]:
        """Claim due work for one member, withholding unresolved prior claims.

        A previous attempt may have caused an external effect before its outcome
        was recorded. Later occurrences must wait for explicit reconciliation.
        """
        point = _utc(now)
        if type(limit) is not int or not 1 <= limit <= 50:
            raise ValueError("claim limit must be 1..50")
        claimed: list[ScheduledRun] = []
        with self._write() as conn:
            rows = conn.execute(
                "SELECT s.schedule_id, s.record FROM schedules AS s"
                " WHERE s.status = 'active' AND s.next_due_at <= ?"
                " AND (? IS NULL OR s.owner = ?)"
                " AND NOT EXISTS (SELECT 1 FROM scheduled_runs AS r"
                " WHERE r.schedule_id = s.schedule_id AND r.status = 'claimed')"
                " ORDER BY s.next_due_at, s.schedule_id LIMIT ?",
                (point.isoformat(), owner, owner, limit),
            ).fetchall()
            for schedule_id, json_record in rows:
                schedule = ScheduleRecord.model_validate_json(json_record)
                due = schedule.next_due_at
                claim = ScheduledRun(
                    schedule_id=schedule_id,
                    due_at=due,
                    idempotency_key=claim_key(schedule_id, due),
                    claimed_at=point,
                    status="claimed",
                )
                next_due = next_occurrence(schedule.definition.recurrence, after=due)
                advanced = ScheduleRecord(
                    definition=schedule.definition,
                    status="active",
                    next_due_at=next_due,
                )
                conn.execute(
                    "INSERT INTO scheduled_runs"
                    " (idempotency_key, schedule_id, due_at, status, record)"
                    " VALUES (?, ?, ?, ?, ?)",
                    (
                        claim.idempotency_key,
                        schedule_id,
                        due.isoformat(),
                        claim.status,
                        claim.model_dump_json(),
                    ),
                )
                conn.execute(
                    "UPDATE schedules SET next_due_at = ?, record = ? WHERE schedule_id = ?",
                    (next_due.isoformat(), advanced.model_dump_json(), schedule_id),
                )
                claimed.append(claim)
        return tuple(claimed)

    def pending_claims(self) -> tuple[ScheduledRun, ...]:
        """Outstanding claims survive restart; a worker must reconcile before retry."""
        with self._lock:
            try:
                rows = self._connection().execute(
                    "SELECT record FROM scheduled_runs WHERE status = 'claimed'"
                    " ORDER BY due_at, schedule_id"
                ).fetchall()
                return tuple(ScheduledRun.model_validate_json(row[0]) for row in rows)
            except (sqlite3.Error, ValidationError):
                raise ScheduleStoreError("unavailable") from None

    def record_outcome(
        self,
        key: str,
        *,
        owner: str,
        status: Literal["succeeded", "failed", "needs_input", "unavailable"],
        result_code: Symbol,
    ) -> ScheduledRun:
        with self._write() as conn:
            row = conn.execute(
                "SELECT r.record, s.owner FROM scheduled_runs AS r"
                " JOIN schedules AS s ON s.schedule_id = r.schedule_id"
                " WHERE r.idempotency_key = ?",
                (key,),
            ).fetchone()
            if row is None:
                raise ScheduleStoreError("unknown")
            if row[1] != owner:
                raise ScheduleStoreError("owner_mismatch")
            old = ScheduledRun.model_validate_json(row[0])
            if old.status != "claimed":
                if old.status == status and old.result_code == result_code:
                    return old
                raise ScheduleStoreError("outcome_conflict")
            outcome = ScheduledRun.model_validate(
                {**old.model_dump(), "status": status, "result_code": result_code}
            )
            conn.execute(
                "UPDATE scheduled_runs SET status = ?, record = ? WHERE idempotency_key = ?",
                (status, outcome.model_dump_json(), key),
            )
            return outcome

    def history(
        self, schedule_id: str, *, owner: str, limit: int = 50
    ) -> tuple[ScheduledRun, ...]:
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("history limit must be 1..100")
        with self._lock:
            try:
                conn = self._connection()
                row = conn.execute(
                    "SELECT owner FROM schedules WHERE schedule_id = ?", (schedule_id,)
                ).fetchone()
                if row is None:
                    raise ScheduleStoreError("unknown")
                if row[0] != owner:
                    raise ScheduleStoreError("owner_mismatch")
                rows = conn.execute(
                    "SELECT record FROM scheduled_runs WHERE schedule_id = ?"
                    " ORDER BY due_at DESC LIMIT ?",
                    (schedule_id, limit),
                ).fetchall()
                return tuple(ScheduledRun.model_validate_json(item[0]) for item in rows)
            except (sqlite3.Error, ValidationError):
                raise ScheduleStoreError("unavailable") from None
