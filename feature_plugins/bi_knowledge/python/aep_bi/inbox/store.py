"""The inbox's own SQLite file, beside the BI stores and never inside one.

    <workspace>/bi/inbox/inbox.sqlite     items, picks, results, defaults, settings, claims
    <workspace>/bi/inbox/files/           files sent to the bot, as received
    <workspace>/bi/inbox/raw/             pages as fetched, before they become sources

An item is one link or one file a person sent (`batch` groups those of one message),
or a text a person added to an item that only had a summary (`parent`). A pick is a
domain chosen for an item (`by`: `person`, `tag`, `default` or `ai`). A result is one
item processed in one domain: inserted once, as the claim (AGENTS rule 21), so an item
is processed at most once per domain however often a schedule fires. Withdrawn is
final. A domain is `<vault id>:<home>`.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

INBOX_DIR = "inbox"
DB_FILE = "inbox.sqlite"

#: An item's states. `queued` waits for its domains' collect time; `done` every pick
#: processed; `needs_text` nothing usable was fetched; `unassigned` (未分類) untapped
#: at processing time without a confident suggestion; `withdrawn` final.
QUEUED, DONE, NEEDS_TEXT, UNASSIGNED, WITHDRAWN = (
    "queued",
    "done",
    "needs_text",
    "unassigned",
    "withdrawn",
)
STATUS_WORDS = {
    QUEUED: "待處理",
    DONE: "已處理",
    NEEDS_TEXT: "需要補文字",
    UNASSIGNED: "未分類",
    WITHDRAWN: "已撤回",
}
#: A result's states (one item in one domain).
PROCESSING, REVIEW, DUPLICATE, FAILED, SUMMARY = (
    "processing",
    "review",
    "duplicate",
    "failed",
    "summary",
)
RESULT_WORDS = {
    PROCESSING: "處理中",
    REVIEW: "已轉換，待審",
    DUPLICATE: "重複，略過",
    FAILED: "失敗",
    SUMMARY: "只取得摘要，待審",
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  batch INTEGER,
  parent INTEGER,
  kind TEXT NOT NULL,
  actor TEXT NOT NULL,
  sender_name TEXT NOT NULL DEFAULT '',
  received_at TEXT NOT NULL,
  url TEXT, norm_url TEXT,
  note TEXT NOT NULL DEFAULT '',
  file_name TEXT, file_path TEXT, file_sha256 TEXT,
  title TEXT NOT NULL DEFAULT '', summary TEXT NOT NULL DEFAULT '',
  suggested TEXT, confidence REAL,
  offered TEXT NOT NULL DEFAULT '[]',
  status TEXT NOT NULL,
  status_at TEXT NOT NULL,
  code TEXT, raw_path TEXT, fetched_at TEXT, fetch_method TEXT, http_status INTEGER,
  final_url TEXT, content_sha256 TEXT, summary_only INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS picks (
  item INTEGER NOT NULL, domain TEXT NOT NULL, by TEXT NOT NULL, at TEXT NOT NULL,
  PRIMARY KEY (item, domain)
);
CREATE TABLE IF NOT EXISTS results (
  item INTEGER NOT NULL, domain TEXT NOT NULL, status TEXT NOT NULL, at TEXT NOT NULL,
  source_id TEXT, run_id TEXT, code TEXT, message TEXT,
  PRIMARY KEY (item, domain)
);
CREATE TABLE IF NOT EXISTS seen (
  domain TEXT NOT NULL, norm_url TEXT NOT NULL, content_sha256 TEXT NOT NULL, item INTEGER,
  PRIMARY KEY (domain, norm_url, content_sha256)
);
CREATE TABLE IF NOT EXISTS defaults (actor TEXT PRIMARY KEY, domain TEXT NOT NULL, at TEXT);
CREATE TABLE IF NOT EXISTS recent (
  actor TEXT NOT NULL, domain TEXT NOT NULL, at TEXT NOT NULL, PRIMARY KEY (actor, domain)
);
CREATE TABLE IF NOT EXISTS settings (
  domain TEXT PRIMARY KEY, enabled INTEGER NOT NULL, collect_at TEXT, review_at TEXT,
  saved_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS claims (key TEXT PRIMARY KEY, at TEXT NOT NULL);
"""

_LOCK = threading.Lock()


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


@dataclass(frozen=True)
class Setting:
    domain: str
    enabled: bool
    collect_at: str | None
    review_at: str | None
    saved_at: str


class Inbox:
    """One workspace's inbox. Every write is one transaction under a process lock."""

    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace
        self.dir = workspace / "bi" / INBOX_DIR
        self.path = self.dir / DB_FILE

    @contextmanager
    def _db(self) -> Iterator[sqlite3.Connection]:
        self.dir.mkdir(parents=True, exist_ok=True)
        with _LOCK:
            db = sqlite3.connect(self.path, timeout=30)
            db.row_factory = sqlite3.Row
            try:
                db.executescript(SCHEMA)
                yield db
                db.commit()
            finally:
                db.close()

    # -- items -------------------------------------------------------------------------------

    def add(self, *, kind: str, actor: str, **values: Any) -> int:
        stamp = now()
        fields = {
            "kind": kind,
            "actor": actor,
            "received_at": values.pop("received_at", stamp),
            "status": QUEUED,
            "status_at": stamp,
            **values,
        }
        if "offered" in fields:
            fields["offered"] = json.dumps(list(fields["offered"]), ensure_ascii=False)
        names = ", ".join(fields)
        marks = ", ".join("?" for _ in fields)
        with self._db() as db:
            cursor = db.execute(
                f"INSERT INTO items ({names}) VALUES ({marks})", tuple(fields.values())
            )
            item_id = int(cursor.lastrowid or 0)
            if fields.get("batch") is None:
                db.execute("UPDATE items SET batch = ? WHERE id = ?", (item_id, item_id))
        return item_id

    def update(self, item_id: int, **values: Any) -> None:
        if "offered" in values:
            values["offered"] = json.dumps(list(values["offered"]), ensure_ascii=False)
        if "status" in values:
            values["status_at"] = now()
        sets = ", ".join(f"{name} = ?" for name in values)
        with self._db() as db:
            db.execute(f"UPDATE items SET {sets} WHERE id = ?", (*values.values(), item_id))

    @staticmethod
    def _row(row: sqlite3.Row) -> dict[str, Any]:
        item = dict(row)
        item["offered"] = json.loads(item.get("offered") or "[]")
        item["summary_only"] = bool(item.get("summary_only"))
        return item

    def item(self, item_id: int) -> dict[str, Any] | None:
        with self._db() as db:
            row = db.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
        return None if row is None else self._row(row)

    def batch(self, item_id: int) -> list[dict[str, Any]]:
        """The items sent in one message with `item_id` (itself included)."""
        with self._db() as db:
            rows = db.execute(
                "SELECT * FROM items WHERE batch = (SELECT batch FROM items WHERE id = ?) "
                "ORDER BY id",
                (item_id,),
            ).fetchall()
        return [self._row(row) for row in rows]

    def items(
        self, *, actor: str | None = None, statuses: Sequence[str] = (), limit: int = 200
    ) -> list[dict[str, Any]]:
        where, args = ["1 = 1"], []
        if actor is not None:
            where.append("actor = ?")
            args.append(actor)
        if statuses:
            where.append(f"status IN ({', '.join('?' for _ in statuses)})")
            args.extend(statuses)
        with self._db() as db:
            rows = db.execute(
                f"SELECT * FROM items WHERE {' AND '.join(where)} ORDER BY id DESC LIMIT ?",
                (*args, limit),
            ).fetchall()
        return [self._row(row) for row in rows]

    def active_url(self, norm_url: str) -> dict[str, Any] | None:
        """An earlier item of this address still waiting (queued or 未分類). One already
        processed does not count: a page sent again later is fetched again, and kept
        only when its content changed (`seen_before`)."""
        with self._db() as db:
            row = db.execute(
                "SELECT * FROM items WHERE norm_url = ? AND status IN (?, ?) ORDER BY id LIMIT 1",
                (norm_url, QUEUED, UNASSIGNED),
            ).fetchone()
        return None if row is None else self._row(row)

    def withdraw(self, item_id: int, actor: str) -> str:
        """`withdrawn`, or why not: `unknown`, `not_yours`, `already` (withdrawn
        before), `processed` (a domain already took it). Checked and written in one
        transaction, so a schedule can never take an item being withdrawn."""
        with self._db() as db:
            row = db.execute("SELECT actor, status FROM items WHERE id = ?", (item_id,)).fetchone()
            if row is None:
                return "unknown"
            if row["actor"] != actor:
                return "not_yours"
            if row["status"] == WITHDRAWN:
                return "already"
            taken = db.execute("SELECT 1 FROM results WHERE item = ?", (item_id,)).fetchone()
            if taken is not None or row["status"] == DONE:
                return "processed"
            db.execute(
                "UPDATE items SET status = ?, status_at = ? WHERE id = ?",
                (WITHDRAWN, now(), item_id),
            )
        return WITHDRAWN

    # -- picks ---------------------------------------------------------------------------------

    def picks(self, item_id: int) -> list[dict[str, Any]]:
        with self._db() as db:
            rows = db.execute(
                "SELECT * FROM picks WHERE item = ? ORDER BY at, domain", (item_id,)
            ).fetchall()
        return [dict(row) for row in rows]

    def pick(self, item_id: int, domain: str, by: str) -> bool:
        """Choose `domain` for an item; False when it was already chosen."""
        with self._db() as db:
            cursor = db.execute(
                "INSERT OR IGNORE INTO picks (item, domain, by, at) VALUES (?, ?, ?, ?)",
                (item_id, domain, by, now()),
            )
            added = cursor.rowcount == 1
            if added:
                db.execute(
                    "UPDATE items SET status = ?, status_at = ? WHERE id = ? AND status = ?",
                    (QUEUED, now(), item_id, UNASSIGNED),
                )
        return added

    def unpick(self, item_id: int, domain: str) -> bool:
        """Take a domain back; False once that domain processed the item."""
        with self._db() as db:
            taken = db.execute(
                "SELECT 1 FROM results WHERE item = ? AND domain = ?", (item_id, domain)
            ).fetchone()
            if taken is not None:
                return False
            db.execute("DELETE FROM picks WHERE item = ? AND domain = ?", (item_id, domain))
        return True

    def note_recent(self, actor: str, domain: str) -> None:
        with self._db() as db:
            db.execute(
                "INSERT INTO recent (actor, domain, at) VALUES (?, ?, ?) "
                "ON CONFLICT (actor, domain) DO UPDATE SET at = excluded.at",
                (actor, domain, now()),
            )

    def recent(self, actor: str, limit: int = 3) -> list[str]:
        with self._db() as db:
            rows = db.execute(
                "SELECT domain FROM recent WHERE actor = ? ORDER BY at DESC LIMIT ?",
                (actor, limit),
            ).fetchall()
        return [str(row["domain"]) for row in rows]

    def set_default(self, actor: str, domain: str | None) -> None:
        with self._db() as db:
            if domain is None:
                db.execute("DELETE FROM defaults WHERE actor = ?", (actor,))
            else:
                db.execute(
                    "INSERT INTO defaults (actor, domain, at) VALUES (?, ?, ?) "
                    "ON CONFLICT (actor) DO UPDATE SET domain = excluded.domain, at = excluded.at",
                    (actor, domain, now()),
                )

    def default(self, actor: str) -> str | None:
        with self._db() as db:
            row = db.execute("SELECT domain FROM defaults WHERE actor = ?", (actor,)).fetchone()
        return None if row is None else str(row["domain"])

    # -- processing ----------------------------------------------------------------------------

    def due(self, domain: str) -> list[dict[str, Any]]:
        """Queued items picked for `domain` that it has not processed, oldest first."""
        with self._db() as db:
            rows = db.execute(
                "SELECT items.* FROM items JOIN picks ON picks.item = items.id "
                "WHERE picks.domain = ? AND items.status = ? AND NOT EXISTS "
                "(SELECT 1 FROM results WHERE results.item = items.id AND results.domain = ?) "
                "ORDER BY items.id",
                (domain, QUEUED, domain),
            ).fetchall()
        return [self._row(row) for row in rows]

    def untapped(self) -> list[dict[str, Any]]:
        """Queued items nobody chose a domain for."""
        with self._db() as db:
            rows = db.execute(
                "SELECT * FROM items WHERE status = ? AND NOT EXISTS "
                "(SELECT 1 FROM picks WHERE picks.item = items.id) ORDER BY id",
                (QUEUED,),
            ).fetchall()
        return [self._row(row) for row in rows]

    def claim(self, item_id: int, domain: str) -> bool:
        """Take an item for processing in a domain: True exactly once, and never for an
        item that is not queued any more (withdrawn, say)."""
        with self._db() as db:
            row = db.execute("SELECT status FROM items WHERE id = ?", (item_id,)).fetchone()
            if row is None or row["status"] != QUEUED:
                return False
            cursor = db.execute(
                "INSERT OR IGNORE INTO results (item, domain, status, at) VALUES (?, ?, ?, ?)",
                (item_id, domain, PROCESSING, now()),
            )
            return cursor.rowcount == 1

    def finish(self, item_id: int, domain: str, status: str, **values: Any) -> None:
        sets = ", ".join(["status = ?", "at = ?", *(f"{name} = ?" for name in values)])
        with self._db() as db:
            db.execute(
                f"UPDATE results SET {sets} WHERE item = ? AND domain = ?",
                (status, now(), *values.values(), item_id, domain),
            )
            left = db.execute(
                "SELECT COUNT(*) FROM picks WHERE item = ? AND NOT EXISTS (SELECT 1 FROM "
                "results WHERE results.item = picks.item AND results.domain = picks.domain "
                "AND results.status != ?)",
                (item_id, PROCESSING),
            ).fetchone()[0]
            if not left:
                db.execute(
                    "UPDATE items SET status = ?, status_at = ? WHERE id = ? AND status = ?",
                    (DONE, now(), item_id, QUEUED),
                )

    def results(
        self, *, item_id: int | None = None, domain: str | None = None, run_id: str | None = None
    ) -> list[dict[str, Any]]:
        where, args = ["1 = 1"], []
        for column, value in (("item", item_id), ("domain", domain), ("run_id", run_id)):
            if value is not None:
                where.append(f"{column} = ?")
                args.append(value)
        with self._db() as db:
            rows = db.execute(
                f"SELECT * FROM results WHERE {' AND '.join(where)} ORDER BY item, domain", args
            ).fetchall()
        return [dict(row) for row in rows]

    def seen_before(self, domain: str, norm_url: str, digest: str, item_id: int) -> int | None:
        """The item that already brought this address with this content into `domain`;
        None (and this one is recorded) when it is new there."""
        with self._db() as db:
            row = db.execute(
                "SELECT item FROM seen WHERE domain = ? AND norm_url = ? AND content_sha256 = ?",
                (domain, norm_url, digest),
            ).fetchone()
            if row is not None and row["item"] != item_id:
                return int(row["item"])
            db.execute(
                "INSERT OR IGNORE INTO seen (domain, norm_url, content_sha256, item) "
                "VALUES (?, ?, ?, ?)",
                (domain, norm_url, digest, item_id),
            )
        return None

    # -- settings and schedule claims ------------------------------------------------------------

    def settings(self) -> dict[str, Setting]:
        with self._db() as db:
            rows = db.execute("SELECT * FROM settings").fetchall()
        return {
            str(row["domain"]): Setting(
                str(row["domain"]),
                bool(row["enabled"]),
                row["collect_at"],
                row["review_at"],
                str(row["saved_at"]),
            )
            for row in rows
        }

    def save_setting(
        self, domain: str, *, enabled: bool, collect_at: str | None, review_at: str | None
    ) -> Setting:
        stamp = now()
        with self._db() as db:
            db.execute(
                "INSERT INTO settings (domain, enabled, collect_at, review_at, saved_at) "
                "VALUES (?, ?, ?, ?, ?) ON CONFLICT (domain) DO UPDATE SET "
                "enabled = excluded.enabled, collect_at = excluded.collect_at, "
                "review_at = excluded.review_at, saved_at = excluded.saved_at",
                (domain, int(enabled), collect_at, review_at, stamp),
            )
        return Setting(domain, enabled, collect_at, review_at, stamp)

    def claim_occurrence(self, key: str) -> bool:
        """True exactly once per key (a domain's collect or review at one time)."""
        with self._db() as db:
            cursor = db.execute(
                "INSERT OR IGNORE INTO claims (key, at) VALUES (?, ?)", (key, now())
            )
            return cursor.rowcount == 1
