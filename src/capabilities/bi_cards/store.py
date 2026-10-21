"""The BI card store: SQLite with field-level provenance (ADR-K11).

`<workspace>/bi/<dataset>/bi.sqlite`, dataset `demo` by default. Cards are
keyed by `(entity_type, canonical_key)`. Every field keeps its value, its
source (`import` with file and row, `human` with the actor, `fixture` for
the shipped demo), when, and an append-only history. An import never
overwrites a value a person set: it records a pending proposal instead. A
person's edit carries `base_version`; a stale one is refused with the
current value, who and when. A whole import can be undone; the undo is
recorded as new history rows, never by deleting old ones.

Reading never creates the database: a preview of an empty dataset leaves
the workspace byte-for-byte unchanged.
"""

from __future__ import annotations

import json
import re
import sqlite3
import uuid
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DEFAULT_DATASET = "demo"
DATASET_RE = re.compile(r"^[A-Za-z0-9_-]{1,40}$")
DB_FILE = "bi.sqlite"

SCHEMA = """
CREATE TABLE IF NOT EXISTS cards (
  id TEXT PRIMARY KEY,
  entity_type TEXT NOT NULL,
  canonical_key TEXT NOT NULL,
  name TEXT NOT NULL,
  version INTEGER NOT NULL,
  synthetic INTEGER NOT NULL DEFAULT 0,
  created TEXT NOT NULL,
  updated TEXT NOT NULL,
  created_by_import TEXT,
  UNIQUE (entity_type, canonical_key)
);
CREATE TABLE IF NOT EXISTS fields (
  card_id TEXT NOT NULL,
  field TEXT NOT NULL,
  value TEXT NOT NULL,
  kind TEXT NOT NULL,
  ref TEXT NOT NULL,
  by TEXT NOT NULL,
  at TEXT NOT NULL,
  PRIMARY KEY (card_id, field)
);
CREATE TABLE IF NOT EXISTS history (
  seq INTEGER PRIMARY KEY AUTOINCREMENT,
  card_id TEXT NOT NULL,
  field TEXT NOT NULL,
  old TEXT,
  new TEXT,
  kind TEXT NOT NULL,
  ref TEXT NOT NULL,
  by TEXT NOT NULL,
  at TEXT NOT NULL,
  import_id TEXT,
  reason TEXT,
  old_source TEXT
);
CREATE TABLE IF NOT EXISTS proposals (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  card_id TEXT NOT NULL,
  field TEXT NOT NULL,
  value TEXT NOT NULL,
  kind TEXT NOT NULL,
  ref TEXT NOT NULL,
  at TEXT NOT NULL,
  import_id TEXT,
  status TEXT NOT NULL DEFAULT 'pending'
);
CREATE TABLE IF NOT EXISTS imports (
  id TEXT PRIMARY KEY,
  filename TEXT NOT NULL,
  entity_type TEXT NOT NULL,
  at TEXT NOT NULL,
  by TEXT NOT NULL,
  undone INTEGER NOT NULL DEFAULT 0
);
"""


class BiStoreError(Exception):
    def __init__(self, code: str, message: str = "", **detail: Any) -> None:
        super().__init__(message or code)
        self.code = code
        self.message = message or code
        self.detail = detail


def now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def dataset_dir(workspace: Path, dataset: str) -> Path:
    if not DATASET_RE.match(dataset):
        raise BiStoreError("dataset_invalid", "資料集名稱只能用英數字、-、_")
    return workspace / "bi" / dataset


def datasets(workspace: Path) -> list[str]:
    root = workspace / "bi"
    if not root.is_dir():
        return []
    return sorted(p.name for p in root.iterdir() if (p / DB_FILE).is_file())


def _dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _load(text: str | None) -> Any:
    return None if text is None else json.loads(text)


@dataclass(frozen=True)
class PlannedRow:
    """One card to write, from a preview."""

    row: int
    entity_type: str
    canonical_key: str
    name: str
    values: dict[str, Any]
    synthetic: bool


@dataclass
class ApplyResult:
    import_id: str
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    proposals: int = 0


class BiStore:
    def __init__(self, workspace: Path, dataset: str = DEFAULT_DATASET) -> None:
        self.dataset = dataset
        self.dir = dataset_dir(workspace, dataset)
        self.path = self.dir / DB_FILE

    @property
    def exists(self) -> bool:
        return self.path.is_file()

    @contextmanager
    def _db(self, *, write: bool = False) -> Iterator[sqlite3.Connection]:
        if write:
            self.dir.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(
            self.path if write else f"file:{self.path}?mode=ro", uri=not write
        )
        connection.row_factory = sqlite3.Row
        try:
            if write:
                connection.executescript(SCHEMA)
            yield connection
            if write:
                connection.commit()
        finally:
            connection.close()

    # -- reading --------------------------------------------------------

    def card_rows(self) -> list[sqlite3.Row]:
        if not self.exists:
            return []
        with self._db() as db:
            return list(db.execute("SELECT * FROM cards ORDER BY entity_type, canonical_key"))

    def find(self, entity_type: str, canonical_key: str) -> sqlite3.Row | None:
        if not self.exists:
            return None
        with self._db() as db:
            row: sqlite3.Row | None = db.execute(
                "SELECT * FROM cards WHERE entity_type = ? AND canonical_key = ?",
                (entity_type, canonical_key),
            ).fetchone()
            return row

    def card(self, card_id: str) -> sqlite3.Row | None:
        if not self.exists:
            return None
        with self._db() as db:
            row: sqlite3.Row | None = db.execute(
                "SELECT * FROM cards WHERE id = ?", (card_id,)
            ).fetchone()
            return row

    def fields(self, card_id: str) -> dict[str, dict[str, Any]]:
        if not self.exists:
            return {}
        with self._db() as db:
            return {
                r["field"]: {
                    "value": _load(r["value"]),
                    "kind": r["kind"],
                    "ref": r["ref"],
                    "by": r["by"],
                    "at": r["at"],
                }
                for r in db.execute("SELECT * FROM fields WHERE card_id = ?", (card_id,))
            }

    def all_fields(self) -> dict[str, dict[str, dict[str, Any]]]:
        """Every card's fields at once (dashboard, search)."""
        result: dict[str, dict[str, dict[str, Any]]] = {}
        if not self.exists:
            return result
        with self._db() as db:
            for r in db.execute("SELECT * FROM fields"):
                result.setdefault(r["card_id"], {})[r["field"]] = {
                    "value": _load(r["value"]),
                    "kind": r["kind"],
                    "ref": r["ref"],
                    "by": r["by"],
                    "at": r["at"],
                }
        return result

    def history(self, card_id: str) -> list[dict[str, Any]]:
        if not self.exists:
            return []
        with self._db() as db:
            return [
                {
                    "field": r["field"],
                    "old": _load(r["old"]),
                    "new": _load(r["new"]),
                    "source": {"kind": r["kind"], "ref": r["ref"]},
                    "at": r["at"],
                    "by": r["by"],
                    "reason": r["reason"] or "",
                }
                for r in db.execute(
                    "SELECT * FROM history WHERE card_id = ? ORDER BY seq", (card_id,)
                )
            ]

    def history_counts(self, card_id: str) -> dict[str, int]:
        if not self.exists:
            return {}
        with self._db() as db:
            return {
                r[0]: r[1]
                for r in db.execute(
                    "SELECT field, COUNT(*) FROM history WHERE card_id = ? GROUP BY field",
                    (card_id,),
                )
            }

    def proposals(self, card_id: str) -> list[dict[str, Any]]:
        if not self.exists:
            return []
        with self._db() as db:
            return [
                {
                    "field": r["field"],
                    "value": _load(r["value"]),
                    "source": {"kind": r["kind"], "ref": r["ref"], "at": r["at"]},
                }
                for r in db.execute(
                    "SELECT * FROM proposals WHERE card_id = ? AND status = 'pending' ORDER BY id",
                    (card_id,),
                )
            ]

    def last_updated(self) -> str | None:
        if not self.exists:
            return None
        with self._db() as db:
            row = db.execute("SELECT MAX(updated) FROM cards").fetchone()
            return str(row[0]) if row and row[0] else None

    # -- writing --------------------------------------------------------

    def apply(
        self,
        rows: Sequence[PlannedRow],
        *,
        filename: str,
        entity_type: str,
        actor: str,
        kind: str = "import",
    ) -> ApplyResult:
        """Write a previewed import: idempotent by (entity_type, canonical_key)."""
        result = ApplyResult(import_id=uuid.uuid4().hex[:12])
        at = now()
        with self._db(write=True) as db:
            db.execute(
                "INSERT INTO imports (id, filename, entity_type, at, by) VALUES (?, ?, ?, ?, ?)",
                (result.import_id, filename, entity_type, at, actor),
            )
            for planned in rows:
                ref = f"{filename}#row{planned.row}"
                existing = db.execute(
                    "SELECT * FROM cards WHERE entity_type = ? AND canonical_key = ?",
                    (planned.entity_type, planned.canonical_key),
                ).fetchone()
                if existing is None:
                    card_id = uuid.uuid4().hex[:12]
                    db.execute(
                        "INSERT INTO cards (id, entity_type, canonical_key, name, version, "
                        "synthetic, created, updated, created_by_import) "
                        "VALUES (?, ?, ?, ?, 1, ?, ?, ?, ?)",
                        (
                            card_id,
                            planned.entity_type,
                            planned.canonical_key,
                            planned.name,
                            int(planned.synthetic),
                            at,
                            at,
                            result.import_id,
                        ),
                    )
                    created = True
                else:
                    card_id = existing["id"]
                    created = False
                    if planned.synthetic and not existing["synthetic"]:
                        db.execute("UPDATE cards SET synthetic = 1 WHERE id = ?", (card_id,))
                changed = False
                current = {
                    r["field"]: r
                    for r in db.execute("SELECT * FROM fields WHERE card_id = ?", (card_id,))
                }
                for name, value in planned.values.items():
                    if value is None:
                        continue
                    stored = current.get(name)
                    new = _dump(value)
                    if stored is not None and stored["value"] == new:
                        continue
                    if stored is not None and stored["kind"] == "human":
                        pending = db.execute(
                            "SELECT 1 FROM proposals WHERE card_id = ? AND field = ? AND "
                            "value = ? AND status = 'pending'",
                            (card_id, name, new),
                        ).fetchone()
                        if pending is None:
                            db.execute(
                                "INSERT INTO proposals (card_id, field, value, kind, ref, at, "
                                "import_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
                                (card_id, name, new, kind, ref, at, result.import_id),
                            )
                            result.proposals += 1
                        continue
                    old_source = (
                        None
                        if stored is None
                        else _dump({k: stored[k] for k in ("kind", "ref", "by", "at")})
                    )
                    db.execute(
                        "INSERT OR REPLACE INTO fields (card_id, field, value, kind, ref, by, at) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (card_id, name, new, kind, ref, actor, at),
                    )
                    db.execute(
                        "INSERT INTO history (card_id, field, old, new, kind, ref, by, at, "
                        "import_id, old_source) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            card_id,
                            name,
                            None if stored is None else stored["value"],
                            new,
                            kind,
                            ref,
                            actor,
                            at,
                            result.import_id,
                            old_source,
                        ),
                    )
                    changed = True
                if created:
                    result.created += 1
                elif changed:
                    db.execute(
                        "UPDATE cards SET version = version + 1, updated = ? WHERE id = ?",
                        (at, card_id),
                    )
                    result.updated += 1
                else:
                    result.unchanged += 1
        return result

    def set_field(
        self,
        card_id: str,
        field: str,
        value: Any,
        *,
        base_version: int,
        actor: str,
        reason: str = "",
    ) -> int:
        """A person's edit; refused as `stale_edit` when the card moved on."""
        at = now()
        if not self.exists:
            raise BiStoreError("card_unknown", "找不到這張卡片")
        with self._db(write=True) as db:
            card = db.execute("SELECT * FROM cards WHERE id = ?", (card_id,)).fetchone()
            if card is None:
                raise BiStoreError("card_unknown", "找不到這張卡片")
            stored = db.execute(
                "SELECT * FROM fields WHERE card_id = ? AND field = ?", (card_id, field)
            ).fetchone()
            if int(card["version"]) != int(base_version):
                last = db.execute(
                    "SELECT by, at FROM history WHERE card_id = ? ORDER BY seq DESC LIMIT 1",
                    (card_id,),
                ).fetchone()
                raise BiStoreError(
                    "stale_edit",
                    "這張卡片在你開啟後已被修改，請重新載入",
                    current=None if stored is None else _load(stored["value"]),
                    by=(stored["by"] if stored is not None else (last["by"] if last else "")),
                    at=(stored["at"] if stored is not None else (last["at"] if last else "")),
                    version=int(card["version"]),
                )
            new = _dump(value)
            old_source = (
                None
                if stored is None
                else _dump({k: stored[k] for k in ("kind", "ref", "by", "at")})
            )
            if value is None:
                db.execute("DELETE FROM fields WHERE card_id = ? AND field = ?", (card_id, field))
            else:
                db.execute(
                    "INSERT OR REPLACE INTO fields (card_id, field, value, kind, ref, by, at) "
                    "VALUES (?, ?, ?, 'human', ?, ?, ?)",
                    (card_id, field, new, f"agent-web:{actor}", actor, at),
                )
            db.execute(
                "INSERT INTO history (card_id, field, old, new, kind, ref, by, at, reason, "
                "old_source) VALUES (?, ?, ?, ?, 'human', ?, ?, ?, ?, ?)",
                (
                    card_id,
                    field,
                    None if stored is None else stored["value"],
                    None if value is None else new,
                    f"agent-web:{actor}",
                    actor,
                    at,
                    reason,
                    old_source,
                ),
            )
            db.execute(
                "UPDATE proposals SET status = 'superseded' WHERE card_id = ? AND field = ? "
                "AND status = 'pending'",
                (card_id, field),
            )
            version = int(card["version"]) + 1
            db.execute(
                "UPDATE cards SET version = ?, updated = ? WHERE id = ?", (version, at, card_id)
            )
            return version

    def undo_import(self, import_id: str, *, actor: str) -> None:
        """Undo a whole import: restore each field it changed (unless a person
        changed it since), drop its proposals, and remove the cards it created
        that nothing else has written."""
        if not self.exists:
            raise BiStoreError("import_unknown", "找不到這次匯入")
        at = now()
        with self._db(write=True) as db:
            record = db.execute("SELECT * FROM imports WHERE id = ?", (import_id,)).fetchone()
            if record is None:
                raise BiStoreError("import_unknown", "找不到這次匯入")
            if record["undone"]:
                raise BiStoreError("import_already_undone", "這次匯入已經復原過了")
            changes = list(
                db.execute(
                    "SELECT * FROM history WHERE import_id = ? ORDER BY seq DESC", (import_id,)
                )
            )
            touched: set[str] = set()
            for change in changes:
                later = db.execute(
                    "SELECT 1 FROM history WHERE card_id = ? AND field = ? AND seq > ? AND "
                    "(import_id IS NULL OR import_id != ?)",
                    (change["card_id"], change["field"], change["seq"], import_id),
                ).fetchone()
                if later is not None:
                    continue  # someone changed it since: keep theirs
                touched.add(change["card_id"])
                if change["old"] is None:
                    db.execute(
                        "DELETE FROM fields WHERE card_id = ? AND field = ?",
                        (change["card_id"], change["field"]),
                    )
                else:
                    source = _load(change["old_source"]) or {}
                    db.execute(
                        "INSERT OR REPLACE INTO fields (card_id, field, value, kind, ref, by, at) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (
                            change["card_id"],
                            change["field"],
                            change["old"],
                            source.get("kind", "import"),
                            source.get("ref", ""),
                            source.get("by", ""),
                            source.get("at", at),
                        ),
                    )
                db.execute(
                    "INSERT INTO history (card_id, field, old, new, kind, ref, by, at, reason) "
                    "VALUES (?, ?, ?, ?, 'undo', ?, ?, ?, ?)",
                    (
                        change["card_id"],
                        change["field"],
                        change["new"],
                        change["old"],
                        f"undo:{import_id}",
                        actor,
                        at,
                        "復原整批匯入",
                    ),
                )
            db.execute(
                "UPDATE proposals SET status = 'withdrawn' WHERE import_id = ? AND "
                "status = 'pending'",
                (import_id,),
            )
            for card in db.execute(
                "SELECT id FROM cards WHERE created_by_import = ?", (import_id,)
            ).fetchall():
                left = db.execute(
                    "SELECT COUNT(*) FROM fields WHERE card_id = ?", (card["id"],)
                ).fetchone()[0]
                if left == 0:
                    db.execute("DELETE FROM cards WHERE id = ?", (card["id"],))
                    touched.discard(card["id"])
            for card_id in touched:
                db.execute(
                    "UPDATE cards SET version = version + 1, updated = ? WHERE id = ?",
                    (at, card_id),
                )
            db.execute("UPDATE imports SET undone = 1 WHERE id = ?", (import_id,))
