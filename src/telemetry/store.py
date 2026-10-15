"""The host's authoritative local telemetry: SQLite, append-only per event.

`<workspace>/telemetry.sqlite`, separate from the state file so telemetry can
never lock or slow the Agent's own state. Every event gets a host-wide
`ingest_seq` (the cursor for streaming and backfill across runs); `sequence`
stays the per-run order allocated at the source. `runs` is a summary kept from
`run.started` and `run.completed` for the run list. Retention (owner
2026-10-08): runs older than 30 days, and the oldest runs beyond 500 MB, are
removed.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from collections.abc import Iterable, Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from telemetry.events import TelemetryEvent

RETENTION_DAYS = 30
RETENTION_BYTES = 500 * 1024 * 1024

_SCHEMA = (
    "CREATE TABLE IF NOT EXISTS events ("
    " ingest_seq INTEGER PRIMARY KEY AUTOINCREMENT, event_id TEXT NOT NULL UNIQUE,"
    " run_id TEXT NOT NULL, sequence INTEGER NOT NULL, timestamp TEXT NOT NULL,"
    " event_type TEXT NOT NULL, state TEXT, status TEXT NOT NULL, record TEXT NOT NULL)",
    "CREATE INDEX IF NOT EXISTS events_run ON events (run_id, sequence)",
    "CREATE TABLE IF NOT EXISTS runs ("
    " run_id TEXT PRIMARY KEY, run_kind TEXT, parent_run_id TEXT, trace_id TEXT,"
    " started_at TEXT, ended_at TEXT, status TEXT, strategy_id TEXT, skill_id TEXT,"
    " model_alias TEXT, summary TEXT NOT NULL DEFAULT '{}', updated_at TEXT NOT NULL)",
    "CREATE INDEX IF NOT EXISTS runs_started ON runs (started_at)",
)


class TelemetryStore:
    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(
            str(self.path), isolation_level=None, check_same_thread=False, timeout=10
        )
        # Takes effect on a new file only; lets retention give space back.
        self._conn.execute("PRAGMA auto_vacuum=INCREMENTAL")
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        for statement in _SCHEMA:
            self._conn.execute(statement)

    # -- writing ---------------------------------------------------------------

    def append(self, events: Iterable[TelemetryEvent]) -> int:
        """Store events; a duplicate `event_id` is ignored (idempotent)."""
        added = 0
        now = datetime.now(UTC).isoformat()
        with self._lock:
            self._conn.execute("BEGIN")
            try:
                for event in events:
                    cursor = self._conn.execute(
                        "INSERT OR IGNORE INTO events (event_id, run_id, sequence, timestamp,"
                        " event_type, state, status, record) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            event.event_id,
                            event.run_id,
                            event.sequence,
                            event.timestamp.astimezone(UTC).isoformat(),
                            event.event_type,
                            event.state,
                            event.status,
                            event.model_dump_json(),
                        ),
                    )
                    added += cursor.rowcount
                    if event.event_type in ("run.started", "run.completed"):
                        self._summarize(event, now)
                self._conn.execute("COMMIT")
            except BaseException:
                self._conn.execute("ROLLBACK")
                raise
        return added

    def _summarize(self, event: TelemetryEvent, now: str) -> None:
        a = event.attributes
        stamp = event.timestamp.astimezone(UTC).isoformat()
        if event.event_type == "run.started":
            self._conn.execute(
                "INSERT INTO runs (run_id, run_kind, parent_run_id, trace_id, started_at,"
                " status, strategy_id, skill_id, model_alias, updated_at)"
                " VALUES (?, ?, ?, ?, ?, 'started', ?, ?, ?, ?)"
                " ON CONFLICT(run_id) DO UPDATE SET run_kind = excluded.run_kind,"
                " parent_run_id = excluded.parent_run_id, started_at = excluded.started_at,"
                " strategy_id = excluded.strategy_id, updated_at = excluded.updated_at",
                (
                    event.run_id,
                    a.get("run_kind"),
                    a.get("parent_run_id"),
                    event.trace_id,
                    stamp,
                    a.get("strategy_id"),
                    a.get("skill_id"),
                    a.get("model_alias"),
                    now,
                ),
            )
            return
        summary = {
            k: a.get(k)
            for k in (
                "duration_ms",
                "llm_calls",
                "tool_calls",
                "input_tokens",
                "output_tokens",
                "failure_code",
                "outcome",
                "cases",
                "status_counts",
            )
            if k in a
        }
        self._conn.execute(
            "INSERT INTO runs (run_id, trace_id, ended_at, status, skill_id, summary,"
            " updated_at) VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT(run_id) DO UPDATE SET"
            " ended_at = excluded.ended_at, status = excluded.status,"
            " skill_id = COALESCE(excluded.skill_id, runs.skill_id),"
            " summary = excluded.summary, updated_at = excluded.updated_at",
            (
                event.run_id,
                event.trace_id,
                stamp,
                event.status,
                a.get("skill_id"),
                json.dumps(summary),
                now,
            ),
        )

    def prune(
        self,
        *,
        now: datetime | None = None,
        days: int = RETENTION_DAYS,
        max_bytes: int = RETENTION_BYTES,
    ) -> int:
        """Drop whole runs: older than `days`, then the oldest beyond `max_bytes`."""
        cutoff = ((now or datetime.now(UTC)) - timedelta(days=days)).isoformat()
        removed = 0
        with self._lock:
            old = [
                row[0]
                for row in self._conn.execute(
                    "SELECT run_id FROM runs WHERE COALESCE(ended_at, started_at, updated_at) < ?",
                    (cutoff,),
                )
            ]
            removed += self._drop(old)
            while self._bytes() > max_bytes:
                batch = [
                    row[0]
                    for row in self._conn.execute(
                        "SELECT run_id FROM runs ORDER BY COALESCE(started_at, updated_at)"
                        " LIMIT 200"
                    )
                ]
                if not batch:
                    break
                removed += self._drop(batch)
                self._conn.execute("PRAGMA incremental_vacuum")
        return removed

    def _drop(self, runs: list[str]) -> int:
        for run_id in runs:
            self._conn.execute("DELETE FROM events WHERE run_id = ?", (run_id,))
            self._conn.execute("DELETE FROM runs WHERE run_id = ?", (run_id,))
        return len(runs)

    def _bytes(self) -> int:
        pages = self._conn.execute("PRAGMA page_count").fetchone()[0]
        free = self._conn.execute("PRAGMA freelist_count").fetchone()[0]
        size = self._conn.execute("PRAGMA page_size").fetchone()[0]
        return int((pages - free) * size)

    # -- reading ------------------------------------------------------------------

    def runs(
        self,
        *,
        limit: int = 50,
        before: str | None = None,
        kind: str | None = None,
        status: str | None = None,
        since: str | None = None,
        until: str | None = None,
        trace_id: str | None = None,
        parent_run_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Newest first; `before` is the previous page's last `started_at|run_id`."""
        clauses, args = ["1 = 1"], []
        if before:
            started, _, run_id = before.partition("|")
            clauses.append(
                "(COALESCE(started_at, '') < ? OR (COALESCE(started_at, '') = ? AND run_id < ?))"
            )
            args += [started, started, run_id]
        for column, value in (
            ("run_kind", kind),
            ("status", status),
            ("trace_id", trace_id),
            ("parent_run_id", parent_run_id),
        ):
            if value:
                clauses.append(f"{column} = ?")
                args.append(value)
        if since:
            clauses.append("COALESCE(started_at, updated_at) >= ?")
            args.append(since)
        if until:
            clauses.append("COALESCE(started_at, updated_at) <= ?")
            args.append(until)
        with self._lock:
            rows = self._conn.execute(
                "SELECT run_id, run_kind, parent_run_id, trace_id, started_at, ended_at, status,"
                " strategy_id, skill_id, model_alias, summary FROM runs WHERE "
                + " AND ".join(clauses)
                + " ORDER BY COALESCE(started_at, '') DESC, run_id DESC LIMIT ?",
                (*args, limit),
            ).fetchall()
        keys = (
            "run_id",
            "run_kind",
            "parent_run_id",
            "trace_id",
            "started_at",
            "ended_at",
            "status",
            "strategy_id",
            "skill_id",
            "model_alias",
        )
        found = []
        for row in rows:
            item = dict(zip(keys, row[:10], strict=True))
            item.update(json.loads(row[10] or "{}"))
            item["complete"] = item["ended_at"] is not None
            found.append(item)
        return found

    def run_events(
        self, run_id: str, *, after_sequence: int = -1, limit: int = 500
    ) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT ingest_seq, record FROM events WHERE run_id = ? AND sequence > ?"
                " ORDER BY sequence LIMIT ?",
                (run_id, after_sequence, limit),
            ).fetchall()
        return [{**json.loads(record), "ingest_seq": seq} for seq, record in rows]

    def events_after(
        self,
        after_ingest_seq: int = 0,
        *,
        limit: int = 1000,
        since: str | None = None,
        until: str | None = None,
    ) -> list[dict[str, Any]]:
        """Every run's events in arrival order: the stream and its backfill."""
        clauses: list[str] = ["ingest_seq > ?"]
        args: list[Any] = [after_ingest_seq]
        if since:
            clauses.append("timestamp >= ?")
            args.append(since)
        if until:
            clauses.append("timestamp <= ?")
            args.append(until)
        with self._lock:
            rows = self._conn.execute(
                "SELECT ingest_seq, record FROM events WHERE "
                + " AND ".join(clauses)
                + " ORDER BY ingest_seq LIMIT ?",
                (*args, limit),
            ).fetchall()
        return [{**json.loads(record), "ingest_seq": seq} for seq, record in rows]

    def last_ingest_seq(self) -> int:
        with self._lock:
            row = self._conn.execute("SELECT MAX(ingest_seq) FROM events").fetchone()
        return int(row[0] or 0)

    def export(self, *, since: str | None = None, run_id: str | None = None) -> Iterator[str]:
        """JSON Lines of the contract's event objects, in arrival order."""
        cursor = 0
        while True:
            batch = (
                self.run_events(run_id, after_sequence=cursor - 1, limit=1000)
                if run_id
                else self.events_after(cursor, limit=1000, since=since)
            )
            if not batch:
                return
            for item in batch:
                item = dict(item)
                seq = item.pop("ingest_seq")
                yield json.dumps(item, ensure_ascii=False)
                cursor = (item["sequence"] + 1) if run_id else seq

    def close(self) -> None:
        with self._lock:
            self._conn.close()
