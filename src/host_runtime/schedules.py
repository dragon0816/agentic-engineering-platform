"""Durable local schedule definitions, execution grants and atomic due claims.

This store never executes a target. A worker submits each claim's exact target
and stable idempotency key through the resident Agent's existing admission,
Workflow engine and Bridge policy, then records the actual outcome.

Schema version 2 adds the owner's schedule execution grants and operator
decisions (claim resolution and per-run approval). A version 1 file is
migrated in place by adding those tables; a newer file is refused.
"""

import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import TracebackType
from typing import Literal, Self

from pydantic import TypeAdapter, ValidationError

from common.base import Symbol
from common.execution import SideEffect
from common.scheduling import (
    ResolutionOutcome,
    ScheduleDefinition,
    ScheduledRun,
    ScheduleExecutionGrant,
    ScheduleGrantRecord,
    ScheduleOperatorDecision,
    ScheduleRecord,
    claim_key,
    next_occurrence,
)

ScheduleErrorCode = Literal[
    "unavailable",
    "commit_unknown",
    "exists",
    "unknown",
    "owner_mismatch",
    "outcome_conflict",
    "grant_mismatch",
    "no_grant",
    "not_claimed",
    "not_awaiting_approval",
]

SCHEMA_VERSION = "2"
#: The default bound on catching up a missed occurrence after downtime.
DEFAULT_CATCH_UP = timedelta(hours=24)
#: How many missed occurrences are stepped over to find the latest one.
_MAX_STEPS = 5000


class ScheduleStoreError(Exception):
    def __init__(self, code: ScheduleErrorCode) -> None:
        self.code = code
        super().__init__(code)


_META = "CREATE TABLE IF NOT EXISTS schedule_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
_SCHEMA = (
    "CREATE TABLE IF NOT EXISTS schedules ("
    " schedule_id TEXT PRIMARY KEY, owner TEXT NOT NULL, status TEXT NOT NULL,"
    " next_due_at TEXT NOT NULL, record TEXT NOT NULL)",
    "CREATE INDEX IF NOT EXISTS schedules_due ON schedules (status, next_due_at)",
    "CREATE TABLE IF NOT EXISTS scheduled_runs ("
    " idempotency_key TEXT PRIMARY KEY, schedule_id TEXT NOT NULL, due_at TEXT NOT NULL,"
    " status TEXT NOT NULL, record TEXT NOT NULL,"
    " UNIQUE (schedule_id, due_at))",
    "CREATE INDEX IF NOT EXISTS scheduled_runs_status ON scheduled_runs (status, due_at)",
    # Version 2: the owner's execution grants (kept after revocation for audit)
    # and operator decisions on individual occurrences.
    "CREATE TABLE IF NOT EXISTS schedule_grants ("
    " grant_seq INTEGER PRIMARY KEY AUTOINCREMENT, schedule_id TEXT NOT NULL,"
    " owner TEXT NOT NULL, active INTEGER NOT NULL, record TEXT NOT NULL)",
    "CREATE INDEX IF NOT EXISTS schedule_grants_active ON schedule_grants (schedule_id, active)",
    "CREATE TABLE IF NOT EXISTS schedule_decisions ("
    " decision_seq INTEGER PRIMARY KEY AUTOINCREMENT, idempotency_key TEXT NOT NULL,"
    " schedule_id TEXT NOT NULL, record TEXT NOT NULL)",
    "CREATE INDEX IF NOT EXISTS schedule_decisions_run ON schedule_decisions (schedule_id)",
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
                conn.execute(_META)
                version = conn.execute(
                    "SELECT value FROM schedule_meta WHERE key = 'schema_version'"
                ).fetchone()
                if version is not None and version[0] not in {"1", SCHEMA_VERSION}:
                    # A newer file: its rules are not ours to guess.
                    raise ScheduleStoreError("unavailable")
                for statement in _SCHEMA:
                    conn.execute(statement)
                if version is None:
                    conn.execute(
                        "INSERT INTO schedule_meta (key, value) VALUES ('schema_version', ?)",
                        (SCHEMA_VERSION,),
                    )
                elif version[0] != SCHEMA_VERSION:
                    conn.execute(
                        "UPDATE schedule_meta SET value = ? WHERE key = 'schema_version'",
                        (SCHEMA_VERSION,),
                    )
                row = conn.execute(
                    "SELECT value FROM schedule_meta WHERE key = 'bridge_id'"
                ).fetchone()
                if row is None:
                    conn.execute(
                        "INSERT INTO schedule_meta (key, value) VALUES ('bridge_id', ?)",
                        (self.bridge_id,),
                    )
                elif row[0] != self.bridge_id:
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

    # -- helpers ---------------------------------------------------------

    @staticmethod
    def _insert_run(conn: sqlite3.Connection, run: ScheduledRun) -> None:
        conn.execute(
            "INSERT INTO scheduled_runs"
            " (idempotency_key, schedule_id, due_at, status, record)"
            " VALUES (?, ?, ?, ?, ?)",
            (
                run.idempotency_key,
                run.schedule_id,
                run.due_at.isoformat(),
                run.status,
                run.model_dump_json(),
            ),
        )

    @staticmethod
    def _update_run(conn: sqlite3.Connection, run: ScheduledRun) -> None:
        conn.execute(
            "UPDATE scheduled_runs SET status = ?, record = ? WHERE idempotency_key = ?",
            (run.status, run.model_dump_json(), run.idempotency_key),
        )

    @staticmethod
    def _owned_run(conn: sqlite3.Connection, key: str, owner: str) -> ScheduledRun:
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
        return ScheduledRun.model_validate_json(row[0])

    @staticmethod
    def _owned_schedule(
        conn: sqlite3.Connection, schedule_id: str, owner: str
    ) -> ScheduleRecord:
        row = conn.execute(
            "SELECT owner, record FROM schedules WHERE schedule_id = ?", (schedule_id,)
        ).fetchone()
        if row is None:
            raise ScheduleStoreError("unknown")
        if row[0] != owner:
            raise ScheduleStoreError("owner_mismatch")
        return ScheduleRecord.model_validate_json(row[1])

    @staticmethod
    def _decide(conn: sqlite3.Connection, decision: ScheduleOperatorDecision) -> None:
        conn.execute(
            "INSERT INTO schedule_decisions (idempotency_key, schedule_id, record)"
            " VALUES (?, ?, ?)",
            (decision.idempotency_key, decision.schedule_id, decision.model_dump_json()),
        )

    # -- definitions -----------------------------------------------------

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
                return self._owned_schedule(self._connection(), schedule_id, owner)
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
            old = self._owned_schedule(conn, schedule_id, owner)
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

    # -- occurrences -----------------------------------------------------

    def claim_due(
        self,
        *,
        now: datetime,
        limit: int = 20,
        owner: str | None = None,
        catch_up: timedelta = DEFAULT_CATCH_UP,
    ) -> tuple[ScheduledRun, ...]:
        """Claim due work for one member, withholding unresolved prior claims.

        A previous attempt may have caused an external effect before its outcome
        was recorded. Later occurrences must wait for explicit reconciliation.

        Missed occurrences are caught up once: only the latest occurrence no
        older than `catch_up` is claimed, and older ones are skipped. When
        every missed occurrence is older than that, nothing is claimed and the
        latest missed one is recorded as `schedule_missed`. Claiming a new
        occurrence supersedes an older one still awaiting per-run approval.
        """
        point = _utc(now)
        if type(limit) is not int or not 1 <= limit <= 50:
            raise ValueError("claim limit must be 1..50")
        if not timedelta(minutes=1) <= catch_up <= timedelta(days=14):
            raise ValueError("catch-up window must be 1 minute..14 days")
        window_start = point - catch_up
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
                recurrence = schedule.definition.recurrence
                latest = schedule.next_due_at
                for _ in range(_MAX_STEPS):
                    following = next_occurrence(recurrence, after=latest)
                    if following > point:
                        break
                    latest = following
                next_due = next_occurrence(recurrence, after=latest)
                advanced = ScheduleRecord(
                    definition=schedule.definition,
                    status="active",
                    next_due_at=next_due,
                )
                conn.execute(
                    "UPDATE schedules SET next_due_at = ?, record = ? WHERE schedule_id = ?",
                    (next_due.isoformat(), advanced.model_dump_json(), schedule_id),
                )
                if latest < window_start:
                    self._insert_run(
                        conn,
                        ScheduledRun(
                            schedule_id=schedule_id,
                            due_at=latest,
                            idempotency_key=claim_key(schedule_id, latest),
                            claimed_at=point,
                            status="unavailable",
                            result_code="schedule_missed",
                        ),
                    )
                    continue
                self._supersede_approvals(conn, schedule_id)
                claim = ScheduledRun(
                    schedule_id=schedule_id,
                    due_at=latest,
                    idempotency_key=claim_key(schedule_id, latest),
                    claimed_at=point,
                    status="claimed",
                )
                self._insert_run(conn, claim)
                claimed.append(claim)
        return tuple(claimed)

    def _supersede_approvals(self, conn: sqlite3.Connection, schedule_id: str) -> None:
        """At most one occurrence of a schedule waits for a human at a time."""
        rows = conn.execute(
            "SELECT record FROM scheduled_runs"
            " WHERE schedule_id = ? AND status = 'awaiting_approval'",
            (schedule_id,),
        ).fetchall()
        for (json_run,) in rows:
            old = ScheduledRun.model_validate_json(json_run)
            self._update_run(
                conn,
                ScheduledRun.model_validate(
                    {
                        **old.model_dump(),
                        "status": "needs_input",
                        "result_code": "run_approval_superseded",
                    }
                ),
            )

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
        side_effect: SideEffect | None = None,
    ) -> ScheduledRun:
        with self._write() as conn:
            old = self._owned_run(conn, key, owner)
            if old.status != "claimed":
                if old.status == status and old.result_code == result_code:
                    return old
                raise ScheduleStoreError("outcome_conflict")
            outcome = ScheduledRun.model_validate(
                {
                    **old.model_dump(),
                    "status": status,
                    "result_code": result_code,
                    "side_effect": side_effect if side_effect is not None else old.side_effect,
                }
            )
            self._update_run(conn, outcome)
            return outcome

    def history(
        self, schedule_id: str, *, owner: str, limit: int = 50
    ) -> tuple[ScheduledRun, ...]:
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("history limit must be 1..100")
        with self._lock:
            try:
                conn = self._connection()
                self._owned_schedule(conn, schedule_id, owner)
                rows = conn.execute(
                    "SELECT record FROM scheduled_runs WHERE schedule_id = ?"
                    " ORDER BY due_at DESC LIMIT ?",
                    (schedule_id, limit),
                ).fetchall()
                return tuple(ScheduledRun.model_validate_json(item[0]) for item in rows)
            except (sqlite3.Error, ValidationError):
                raise ScheduleStoreError("unavailable") from None

    def run(self, key: str, *, owner: str) -> ScheduledRun:
        with self._lock:
            try:
                return self._owned_run(self._connection(), key, owner)
            except (sqlite3.Error, ValidationError):
                raise ScheduleStoreError("unavailable") from None

    def awaiting_approval(self, *, owner: str) -> tuple[ScheduledRun, ...]:
        with self._lock:
            try:
                rows = self._connection().execute(
                    "SELECT r.record FROM scheduled_runs AS r"
                    " JOIN schedules AS s ON s.schedule_id = r.schedule_id"
                    " WHERE r.status = 'awaiting_approval' AND s.owner = ?"
                    " ORDER BY r.due_at, r.schedule_id",
                    (owner,),
                ).fetchall()
                return tuple(ScheduledRun.model_validate_json(row[0]) for row in rows)
            except (sqlite3.Error, ValidationError):
                raise ScheduleStoreError("unavailable") from None

    def await_approval(
        self, key: str, *, owner: str, side_effect: SideEffect
    ) -> ScheduledRun:
        """A claim that dispatched nothing now waits for a per-run decision.

        It no longer blocks the schedule, because nothing uncertain happened.
        """
        with self._write() as conn:
            old = self._owned_run(conn, key, owner)
            if old.status == "awaiting_approval":
                return old
            if old.status != "claimed":
                raise ScheduleStoreError("not_claimed")
            waiting = ScheduledRun.model_validate(
                {
                    **old.model_dump(),
                    "status": "awaiting_approval",
                    "result_code": "run_approval_required",
                    "side_effect": side_effect,
                }
            )
            self._update_run(conn, waiting)
            return waiting

    def approve_run(
        self, key: str, *, owner: str, decided_by: str, now: datetime, note: str | None = None
    ) -> ScheduledRun:
        """Turn an approved occurrence back into an open claim for dispatch.

        Being a claim again, it blocks the schedule until its outcome is
        recorded, and it is never replayed after a restart.
        """
        point = _utc(now)
        with self._write() as conn:
            old = self._owned_run(conn, key, owner)
            if old.status != "awaiting_approval":
                raise ScheduleStoreError("not_awaiting_approval")
            if conn.execute(
                "SELECT 1 FROM scheduled_runs WHERE schedule_id = ? AND status = 'claimed'",
                (old.schedule_id,),
            ).fetchone():
                raise ScheduleStoreError("outcome_conflict")
            self._decide(
                conn,
                ScheduleOperatorDecision(
                    idempotency_key=key,
                    schedule_id=old.schedule_id,
                    kind="approve",
                    outcome="approved",
                    decided_by=decided_by,
                    decided_at=point,
                    note=note,
                ),
            )
            claim = ScheduledRun.model_validate(
                {
                    **old.model_dump(),
                    "status": "claimed",
                    "result_code": None,
                    "claimed_at": point,
                }
            )
            self._update_run(conn, claim)
            return claim

    def deny_run(
        self, key: str, *, owner: str, decided_by: str, now: datetime, note: str | None = None
    ) -> ScheduledRun:
        point = _utc(now)
        with self._write() as conn:
            old = self._owned_run(conn, key, owner)
            if old.status != "awaiting_approval":
                raise ScheduleStoreError("not_awaiting_approval")
            self._decide(
                conn,
                ScheduleOperatorDecision(
                    idempotency_key=key,
                    schedule_id=old.schedule_id,
                    kind="deny",
                    outcome="denied",
                    decided_by=decided_by,
                    decided_at=point,
                    note=note,
                ),
            )
            denied = ScheduledRun.model_validate(
                {**old.model_dump(), "status": "needs_input", "result_code": "run_approval_denied"}
            )
            self._update_run(conn, denied)
            return denied

    def resolve(
        self,
        key: str,
        *,
        owner: str,
        outcome: ResolutionOutcome,
        decided_by: str,
        now: datetime,
        note: str | None = None,
    ) -> ScheduledRun:
        """Record what a person established about an uncertain claim.

        Nothing is dispatched. The decision is kept beside the run, and the
        schedule's later occurrences are released.
        """
        point = _utc(now)
        resolutions: dict[str, tuple[str, str]] = {
            "succeeded": ("succeeded", "operator_resolved_succeeded"),
            "failed": ("failed", "operator_resolved_failed"),
            "not_run": ("needs_input", "operator_resolved_not_run"),
        }
        status, code = resolutions[outcome]
        with self._write() as conn:
            old = self._owned_run(conn, key, owner)
            if old.status != "claimed":
                raise ScheduleStoreError("not_claimed")
            self._decide(
                conn,
                ScheduleOperatorDecision(
                    idempotency_key=key,
                    schedule_id=old.schedule_id,
                    kind="resolve",
                    outcome=outcome,
                    decided_by=decided_by,
                    decided_at=point,
                    note=note,
                ),
            )
            resolved = ScheduledRun.model_validate(
                {**old.model_dump(), "status": status, "result_code": code}
            )
            self._update_run(conn, resolved)
            return resolved

    def decisions(
        self, schedule_id: str, *, owner: str, limit: int = 50
    ) -> tuple[ScheduleOperatorDecision, ...]:
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("decision limit must be 1..100")
        with self._lock:
            try:
                conn = self._connection()
                self._owned_schedule(conn, schedule_id, owner)
                rows = conn.execute(
                    "SELECT record FROM schedule_decisions WHERE schedule_id = ?"
                    " ORDER BY decision_seq DESC LIMIT ?",
                    (schedule_id, limit),
                ).fetchall()
                return tuple(ScheduleOperatorDecision.model_validate_json(r[0]) for r in rows)
            except (sqlite3.Error, ValidationError):
                raise ScheduleStoreError("unavailable") from None

    # -- execution grants ------------------------------------------------

    def grant(self, grant: ScheduleExecutionGrant) -> ScheduleGrantRecord:
        """Save the owner's grant for the schedule's current exact target.

        A previous active grant is revoked by the same person at the same time.
        """
        item = ScheduleExecutionGrant.model_validate(grant)
        with self._write() as conn:
            schedule = self._owned_schedule(conn, item.schedule_id, item.owner)
            if not item.covers(schedule.definition):
                raise ScheduleStoreError("grant_mismatch")
            self._revoke_active(conn, item.schedule_id, item.approved_by, item.approved_at)
            record = ScheduleGrantRecord(grant=item)
            conn.execute(
                "INSERT INTO schedule_grants (schedule_id, owner, active, record)"
                " VALUES (?, ?, 1, ?)",
                (item.schedule_id, item.owner, record.model_dump_json()),
            )
            return record

    @staticmethod
    def _revoke_active(
        conn: sqlite3.Connection, schedule_id: str, by: str, at: datetime
    ) -> ScheduleGrantRecord | None:
        row = conn.execute(
            "SELECT grant_seq, record FROM schedule_grants"
            " WHERE schedule_id = ? AND active = 1",
            (schedule_id,),
        ).fetchone()
        if row is None:
            return None
        old = ScheduleGrantRecord.model_validate_json(row[1])
        revoked = ScheduleGrantRecord(grant=old.grant, revoked_at=_utc(at), revoked_by=by)
        conn.execute(
            "UPDATE schedule_grants SET active = 0, record = ? WHERE grant_seq = ?",
            (revoked.model_dump_json(), row[0]),
        )
        return revoked

    def revoke(
        self, schedule_id: str, *, owner: str, revoked_by: str, now: datetime
    ) -> ScheduleGrantRecord:
        with self._write() as conn:
            self._owned_schedule(conn, schedule_id, owner)
            revoked = self._revoke_active(conn, schedule_id, revoked_by, now)
            if revoked is None:
                raise ScheduleStoreError("no_grant")
            return revoked

    def active_grant(self, schedule_id: str, *, owner: str) -> ScheduleGrantRecord | None:
        with self._lock:
            try:
                conn = self._connection()
                self._owned_schedule(conn, schedule_id, owner)
                row = conn.execute(
                    "SELECT record FROM schedule_grants WHERE schedule_id = ? AND active = 1",
                    (schedule_id,),
                ).fetchone()
                return None if row is None else ScheduleGrantRecord.model_validate_json(row[0])
            except (sqlite3.Error, ValidationError):
                raise ScheduleStoreError("unavailable") from None

    def grant_history(
        self, schedule_id: str, *, owner: str
    ) -> tuple[ScheduleGrantRecord, ...]:
        with self._lock:
            try:
                conn = self._connection()
                self._owned_schedule(conn, schedule_id, owner)
                rows = conn.execute(
                    "SELECT record FROM schedule_grants WHERE schedule_id = ?"
                    " ORDER BY grant_seq DESC LIMIT 50",
                    (schedule_id,),
                ).fetchall()
                return tuple(ScheduleGrantRecord.model_validate_json(r[0]) for r in rows)
            except (sqlite3.Error, ValidationError):
                raise ScheduleStoreError("unavailable") from None
