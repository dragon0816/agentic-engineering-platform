"""Conversation feedback the Bridges upload (owner 2026-10-08).

One row per rated answer (`feedback_id`): a newer rating of the same answer
replaces the older one, and a late copy of an older rating never overwrites a
newer one. The durable store shares the registry's SQLite file; without one
the platform keeps feedback in memory, as it does every other reference.
"""

from __future__ import annotations

import sqlite3
import threading
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path

from common.sync import FeedbackRecord

_SCHEMA = (
    "CREATE TABLE IF NOT EXISTS feedback ("
    " feedback_id TEXT PRIMARY KEY, bridge_id TEXT NOT NULL, actor TEXT NOT NULL,"
    " rating TEXT NOT NULL, rated_at TEXT NOT NULL, received_at TEXT NOT NULL,"
    " record TEXT NOT NULL)"
)


class FeedbackStore:
    def __init__(self, path: Path | str | None = None) -> None:
        self._lock = threading.Lock()
        self._memory: dict[str, tuple[FeedbackRecord, str]] = {}
        self._conn: sqlite3.Connection | None = None
        if path is not None:
            self._conn = sqlite3.connect(str(path), isolation_level=None,
                                         check_same_thread=False, timeout=5)
            self._conn.execute(_SCHEMA)

    def record(self, records: Iterable[FeedbackRecord], received_at: datetime) -> tuple[str, ...]:
        """Keep each record unless a newer rating of the same answer is held.
        Every id is acknowledged: the Bridge may forget what it sent."""
        accepted: list[str] = []
        stamp = received_at.isoformat()
        with self._lock:
            for item in records:
                accepted.append(item.feedback_id)
                if self._conn is None:
                    held = self._memory.get(item.feedback_id)
                    if held is None or held[0].rated_at <= item.rated_at:
                        self._memory[item.feedback_id] = (item, stamp)
                    continue
                self._conn.execute(
                    "INSERT INTO feedback (feedback_id, bridge_id, actor, rating, rated_at,"
                    " received_at, record) VALUES (?, ?, ?, ?, ?, ?, ?)"
                    " ON CONFLICT(feedback_id) DO UPDATE SET rating = excluded.rating,"
                    " rated_at = excluded.rated_at, received_at = excluded.received_at,"
                    " record = excluded.record WHERE excluded.rated_at >= feedback.rated_at",
                    # UTC text, so the comparison above orders by time.
                    (item.feedback_id, item.bridge_id, item.actor, item.rating,
                     item.rated_at.astimezone(UTC).isoformat(), stamp,
                     item.model_dump_json()),
                )
        return tuple(accepted)

    def list(self, limit: int = 1000) -> tuple[FeedbackRecord, ...]:
        """Newest rating first."""
        with self._lock:
            if self._conn is None:
                items = sorted((held[0] for held in self._memory.values()),
                               key=lambda item: item.rated_at, reverse=True)
                return tuple(items[:limit])
            rows = self._conn.execute(
                "SELECT record FROM feedback ORDER BY rated_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return tuple(FeedbackRecord.model_validate_json(row[0]) for row in rows)

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None
