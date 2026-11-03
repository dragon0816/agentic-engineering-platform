"""The BI card store: SQLite with field-level provenance (ADR-K11).

`<workspace>/bi/<dataset>/bi.sqlite`, dataset `demo` by default. Cards are
keyed by `(entity_type, canonical_key)`. Every field keeps its value, its
source (`import` with file and row, `human` with the actor, `fixture` for
the shipped demo), when, and an append-only history. An import never
overwrites a value a person set: it records a pending proposal instead. A
person's edit carries `base_version`; a stale one is refused with the
current value, who and when. A whole import can be undone; the undo is
recorded as new history rows, never by deleting old ones.

Each dataset is bound to one schema (`meta.schema`, `<schema_id>@<version>`),
chosen when it is created (owner 2026-10-21); since 2026-10-27 it moves only
to another version of the same schema id, through `upgrade_schema`. A dataset
from before the binding existed has no `meta` row and is read as
`LEGACY_SCHEMA`; its next write records that binding.

Reading never creates the database: a preview of an empty dataset leaves
the workspace byte-for-byte unchanged.

A reviewed ingest run (BI ingest phase 1, owner 2026-10-27) is written by
`commit_run`: all or nothing, refused when a matched card moved on since the
review, keyed by the run id (`imports.run_id`) so a retried commit writes
nothing twice, and with each value's evidence in `evidence`.

After every write the dataset's search index (`search_index.py`, BI vault
V3, its own file `search.sqlite`) is brought up to date; it is a cache, so
a failure there never fails the write.

A dataset subscribed from the shared platform (BI dataset sharing slice 1,
owner 2026-10-22) is named `<namespace>/<name>` and lives under
`<workspace>/bi/subscribed/<namespace>__<name>/`; `subscription.json` there
names the installed version, whose `<version>/bi.sqlite` is opened read
only. Every write to it is refused as `dataset_read_only`.

A vault (BI vaults phase V4, `docs/phases/BI_VAULT.md` §3, §4) registered on
this PC in `<workspace>/bi/vaults/registry.json` is the dataset
`vault-<vault id>`, kept under `<workspace>/bi/vaults/<vault id>/`. Its
`bi.sqlite` is rebuilt from the vault's shared change files: every write goes
through `vault.capture`, which turns it into one change file and applies that
file, so the local database is always a function of the files. Every other
dataset is written exactly as before.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import uuid
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from capabilities.bi_cards.schema import widen_value

DEFAULT_DATASET = "demo"
DATASET_RE = re.compile(r"^[A-Za-z0-9_-]{1,40}$")
DB_FILE = "bi.sqlite"
#: The binding of a dataset created before per-dataset schemas, or implicitly
#: by an import or the demo load: the shipped `bi.schema/v1.1`.
LEGACY_SCHEMA = "bi.schema/v1.1@1.1.0"
#: `<workspace>/bi/schemas/` holds installed schema files and
#: `<workspace>/bi/subscribed/` the subscribed datasets, so no dataset may use them.
SUBSCRIBED_DIR = "subscribed"
#: `<workspace>/bi/vaults/` holds the registry and each vault's local copy.
VAULTS_DIR = "vaults"
#: A registered vault is the dataset `vault-<vault id>`.
VAULT_PREFIX = "vault-"
VAULT_REGISTRY = "registry.json"
#: `schema-drafts` and `benchmarks` hold schema drafts and benchmark reports
#: (BI ingest, 2026-10-28).
RESERVED_DATASETS = {"schemas", SUBSCRIBED_DIR, "schema-drafts", "benchmarks", VAULTS_DIR}
#: A subscribed dataset as the platform names it: `<namespace>/<name>`.
SUBSCRIBED_RE = re.compile(r"^([a-z0-9]+(?:-[a-z0-9]+)*)/([a-z0-9]+(?:-[a-z0-9]+)*)$")
SUBSCRIPTION_FILE = "subscription.json"
READ_ONLY_MESSAGE = "這是從 Shared Platform 訂閱的資料集，唯讀；要修改請請發佈者更新"

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
CREATE TABLE IF NOT EXISTS meta (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS imports (
  id TEXT PRIMARY KEY,
  filename TEXT NOT NULL,
  entity_type TEXT NOT NULL,
  at TEXT NOT NULL,
  by TEXT NOT NULL,
  undone INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS evidence (
  seq INTEGER PRIMARY KEY AUTOINCREMENT,
  card_id TEXT NOT NULL,
  field TEXT NOT NULL,
  run_id TEXT NOT NULL,
  source_id TEXT NOT NULL,
  source_name TEXT NOT NULL,
  locator TEXT NOT NULL,
  excerpt TEXT NOT NULL,
  basis TEXT NOT NULL,
  at TEXT NOT NULL,
  reference_id TEXT NOT NULL DEFAULT '',
  stance TEXT NOT NULL DEFAULT 'supports',
  reference_at TEXT,
  reference_time_basis TEXT
);
CREATE TABLE IF NOT EXISTS relations (
  relation_id TEXT PRIMARY KEY,
  from_card_id TEXT NOT NULL,
  relation_type TEXT NOT NULL,
  to_card_id TEXT NOT NULL,
  status TEXT NOT NULL,
  origin TEXT NOT NULL,
  source_field TEXT,
  scope TEXT,
  note TEXT,
  by TEXT,
  at TEXT
);
CREATE INDEX IF NOT EXISTS relations_from ON relations (from_card_id, relation_type);
CREATE INDEX IF NOT EXISTS relations_to ON relations (to_card_id, relation_type);
CREATE TABLE IF NOT EXISTS relation_evidence (
  evidence_link_id TEXT PRIMARY KEY,
  relation_id TEXT NOT NULL,
  basis_card_id TEXT NOT NULL,
  reference_id TEXT NOT NULL,
  stance TEXT NOT NULL,
  assessment TEXT,
  by TEXT,
  at TEXT
);
CREATE INDEX IF NOT EXISTS relation_evidence_relation ON relation_evidence (relation_id);
CREATE TABLE IF NOT EXISTS field_states (
  card_id TEXT NOT NULL,
  field TEXT NOT NULL,
  state TEXT NOT NULL,
  reason TEXT,
  raw TEXT,
  origin TEXT NOT NULL,
  ref TEXT,
  by TEXT,
  at TEXT,
  PRIMARY KEY (card_id, field)
);
CREATE TABLE IF NOT EXISTS card_names (
  card_id TEXT NOT NULL,
  name TEXT NOT NULL,
  kind TEXT NOT NULL,
  PRIMARY KEY (card_id, name, kind)
);
CREATE TABLE IF NOT EXISTS card_app_folders (
  card_id TEXT NOT NULL,
  application TEXT NOT NULL,
  PRIMARY KEY (card_id, application)
);
"""
#: Evidence columns added by the card model, for a database older than `SCHEMA`.
EVIDENCE_COLUMNS = {
    "reference_id": "TEXT NOT NULL DEFAULT ''",
    "stance": "TEXT NOT NULL DEFAULT 'supports'",
    "reference_at": "TEXT",
    "reference_time_basis": "TEXT",
}


def add_missing_columns(connection: sqlite3.Connection) -> None:
    """Bring an older database's tables up to `SCHEMA`, which only adds tables."""
    columns = {r[1] for r in connection.execute("PRAGMA table_info(imports)")}
    if "run_id" not in columns:  # a dataset from before ingest runs
        connection.execute("ALTER TABLE imports ADD COLUMN run_id TEXT")
    columns = {r[1] for r in connection.execute("PRAGMA table_info(evidence)")}
    for name, definition in EVIDENCE_COLUMNS.items():
        if name not in columns:
            connection.execute(f"ALTER TABLE evidence ADD COLUMN {name} {definition}")


class BiStoreError(Exception):
    def __init__(self, code: str, message: str = "", **detail: Any) -> None:
        super().__init__(message or code)
        self.code = code
        self.message = message or code
        self.detail = detail


def now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def is_subscribed(dataset: str) -> bool:
    return SUBSCRIBED_RE.match(dataset) is not None


def subscribed_root(workspace: Path, dataset: str) -> Path:
    """`<workspace>/bi/subscribed/<namespace>__<name>/` of a `<namespace>/<name>`."""
    match = SUBSCRIBED_RE.match(dataset)
    if match is None:
        raise BiStoreError("dataset_invalid", "訂閱的資料集名稱是 <namespace>/<name>")
    namespace, name = match.groups()
    return workspace / "bi" / SUBSCRIBED_DIR / f"{namespace}__{name}"


def subscription_record(workspace: Path, dataset: str) -> dict[str, Any] | None:
    """The subscription's `subscription.json`; None when not subscribed."""
    path = subscribed_root(workspace, dataset) / SUBSCRIPTION_FILE
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return record if isinstance(record, dict) else None


def subscribed_datasets(workspace: Path) -> list[str]:
    """Every subscribed `<namespace>/<name>` with an installed version."""
    root = workspace / "bi" / SUBSCRIBED_DIR
    if not root.is_dir():
        return []
    found = []
    for folder in sorted(root.iterdir()):
        namespace, separator, name = folder.name.partition("__")
        dataset = f"{namespace}/{name}"
        if not separator or not is_subscribed(dataset):
            continue
        record = subscription_record(workspace, dataset)
        if record is not None and isinstance(record.get("version"), str):
            found.append(dataset)
    return found


def vault_registry(workspace: Path) -> list[dict[str, Any]]:
    """The vaults this PC uses: `[{"id", "path", "author", ...}]` (empty when none)."""
    path = workspace / "bi" / VAULTS_DIR / VAULT_REGISTRY
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    items = record.get("vaults") if isinstance(record, dict) else None
    if not isinstance(items, list):
        return []
    return [i for i in items if isinstance(i, dict) and isinstance(i.get("id"), str)]


def card_id_for(entity_type: str, canonical_key: str) -> str:
    """A vault card's id: the same on every PC."""
    digest = hashlib.sha256(f"{entity_type}\0{canonical_key}".encode()).hexdigest()
    return digest[:12]


def vault_of(workspace: Path, dataset: str) -> str | None:
    """The vault id of a `vault-<id>` dataset registered on this PC; None otherwise."""
    if not dataset.startswith(VAULT_PREFIX):
        return None
    vault_id = dataset[len(VAULT_PREFIX) :]
    if any(item["id"] == vault_id for item in vault_registry(workspace)):
        return vault_id
    return None


def dataset_dir(workspace: Path, dataset: str) -> Path:
    if is_subscribed(dataset):
        record = subscription_record(workspace, dataset) or {}
        version = str(record.get("version") or "")
        root = subscribed_root(workspace, dataset)
        # An unknown version reads as an empty, missing dataset.
        return root / version if re.fullmatch(r"\d+\.\d+\.\d+", version) else root / "none"
    if not DATASET_RE.match(dataset):
        raise BiStoreError("dataset_invalid", "資料集名稱只能用英數字、-、_，最多 40 個字")
    vault_id = vault_of(workspace, dataset)
    if vault_id is not None:
        return workspace / "bi" / VAULTS_DIR / vault_id
    if dataset.lower() in RESERVED_DATASETS:
        raise BiStoreError("dataset_invalid", f"「{dataset}」是保留名稱，請換一個資料集名稱")
    return workspace / "bi" / dataset


def datasets(workspace: Path) -> list[str]:
    root = workspace / "bi"
    if not root.is_dir():
        return []
    found = [
        p.name
        for p in root.iterdir()
        if p.name.lower() not in RESERVED_DATASETS and (p / DB_FILE).is_file()
    ]
    for item in vault_registry(workspace):
        if (root / VAULTS_DIR / item["id"] / DB_FILE).is_file():
            found.append(VAULT_PREFIX + item["id"])
    return sorted(found)


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
    #: The source of every value; `<file>#row<n>` when empty (Case A).
    ref: str = ""
    #: Fields that become a proposal for review instead of being written (the
    #: card-page import's merge, `page_import.merge_rows`).
    propose: frozenset[str] = frozenset()
    #: Evidence per field: `{field: [{"source_id", "source_name", "locator",
    #: "excerpt", "basis"}]}`, recorded for the values written.
    evidence: dict[str, list[dict[str, Any]]] = field(default_factory=dict)


class CardsChanged(BiStoreError):
    """A commit refused because cards moved on since the review."""

    def __init__(self, cards: list[dict[str, Any]]) -> None:
        super().__init__(
            "cards_changed",
            "有卡片在審核後被修改或新增，沒有寫入任何資料；請重新檢查後再確認",
            cards=cards,
        )


@dataclass
class ApplyResult:
    import_id: str
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    proposals: int = 0


class BiStore:
    def __init__(
        self, workspace: Path, dataset: str = DEFAULT_DATASET, *, view: Path | None = None
    ) -> None:
        self.workspace = workspace
        self.dataset = dataset
        #: A read-only copy of the dataset in folder `view` (a vault's
        #: published version, `vault.reading_store`); never written.
        self.view = view
        self.dir = view if view is not None else dataset_dir(workspace, dataset)
        self.path = self.dir / DB_FILE
        #: A subscribed copy: readable, never written here.
        self.read_only = is_subscribed(dataset) or view is not None
        #: A vault's id: its writes become commits (`vault.capture`).
        self.vault_id = None if self.read_only else vault_of(workspace, dataset)
        if self.vault_id is not None:
            from capabilities.bi_cards import vault

            vault.ensure_current(self)

    @property
    def exists(self) -> bool:
        return self.path.is_file()

    def scratch_copy(self, folder: Path) -> BiStore:
        """A writable copy of these cards in `folder`, to see the effect of
        something without keeping it (`BI_BUILD_FLOW.md` §6): writes to it are
        never commits and never reach this dataset."""
        folder.mkdir(parents=True, exist_ok=True)
        with (
            sqlite3.connect(f"file:{self.path}?mode=ro", uri=True) as source,
            sqlite3.connect(folder / DB_FILE) as target,
        ):
            source.backup(target)
        source.close()
        target.close()
        copy = BiStore(self.workspace, self.dataset, view=folder)
        copy.read_only = False
        return copy

    def refuse_write(self) -> None:
        if self.read_only:
            raise BiStoreError("dataset_read_only", READ_ONLY_MESSAGE)

    @contextmanager
    def _db(self, *, write: bool = False) -> Iterator[sqlite3.Connection]:
        if write and self.vault_id is not None:
            # A vault: the write is captured as one change file and applied
            # from it; nothing is committed on this connection.
            from capabilities.bi_cards import vault

            with vault.capture(self) as captured:
                yield captured
            return
        if write:
            self.refuse_write()
            self.dir.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(
            self.path if write else f"file:{self.path}?mode=ro", uri=not write
        )
        connection.row_factory = sqlite3.Row
        try:
            if write:
                connection.executescript(SCHEMA)
                add_missing_columns(connection)
                # A dataset written before the binding existed keeps v1.1.
                connection.execute(
                    "INSERT OR IGNORE INTO meta (key, value) VALUES ('schema', ?)",
                    (LEGACY_SCHEMA,),
                )
            yield connection
            if write:
                connection.commit()
        finally:
            connection.close()
        if write:
            # Keep the search index current (BI vault V3). It is a cache in
            # its own file: a failure there never fails this write.
            from capabilities.bi_cards import search_index

            search_index.sync_quietly(self)

    # -- the schema binding ---------------------------------------------

    def schema_ref(self) -> str:
        """The dataset's schema (`<id>@<version>`); `LEGACY_SCHEMA` when unbound."""
        if not self.exists:
            return LEGACY_SCHEMA
        with self._db() as db:
            try:
                row = db.execute("SELECT value FROM meta WHERE key = 'schema'").fetchone()
            except sqlite3.OperationalError:  # a dataset from before the binding
                return LEGACY_SCHEMA
        return str(row[0]) if row else LEGACY_SCHEMA

    def create(self, schema_ref: str) -> None:
        """A new, empty dataset bound to `schema_ref`; an existing one is refused
        (its schema cannot be changed after creation)."""
        self.refuse_write()
        if self.exists:
            current = self.schema_ref()
            raise BiStoreError(
                "dataset_exists",
                f"資料集「{self.dataset}」已經存在（schema {current}），不能更換 schema 成別的；"
                "同一個 schema 的新版本請用「升級 schema」，別的 schema 請用新的名稱另建資料集",
                schema=current,
            )
        with self._db(write=True) as db:
            db.execute(
                "INSERT OR REPLACE INTO meta (key, value) VALUES ('schema', ?)", (schema_ref,)
            )

    # -- reading --------------------------------------------------------

    def card_rows(self) -> list[sqlite3.Row]:
        if not self.exists:
            return []
        with self._db() as db:
            return list(db.execute("SELECT * FROM cards ORDER BY entity_type, canonical_key"))

    def relations(self, card_id: str) -> list[dict[str, Any]]:
        """A card's relations both ways, a rejected one left out, with their evidence."""
        if not self.exists:
            return []
        with self._db() as db:
            if not db.execute("SELECT 1 FROM sqlite_master WHERE name = 'relations'").fetchone():
                return []  # a dataset not written since the card model
            rows = db.execute(
                "SELECT r.*, c.name AS other_name, c.entity_type AS other_type, "
                "CASE WHEN r.from_card_id = ? THEN 'out' ELSE 'in' END AS direction "
                "FROM relations r JOIN cards c ON c.id = "
                "CASE WHEN r.from_card_id = ? THEN r.to_card_id ELSE r.from_card_id END "
                "WHERE (r.from_card_id = ? OR r.to_card_id = ?) AND r.status != 'rejected' "
                "ORDER BY r.relation_type, c.name",
                (card_id, card_id, card_id, card_id),
            ).fetchall()
            evidence: dict[str, list[dict[str, Any]]] = {}
            for r in db.execute(
                "SELECT relation_id, basis_card_id, reference_id, stance FROM relation_evidence "
                "WHERE relation_id IN (SELECT relation_id FROM relations "
                "WHERE from_card_id = ? OR to_card_id = ?)",
                (card_id, card_id),
            ):
                evidence.setdefault(r["relation_id"], []).append(
                    {k: r[k] for k in ("basis_card_id", "reference_id", "stance")}
                )
        return [
            {
                "relation_id": r["relation_id"],
                "type": r["relation_type"],
                "direction": r["direction"],
                "other_id": r["to_card_id"] if r["direction"] == "out" else r["from_card_id"],
                "other_name": r["other_name"],
                "other_type": r["other_type"],
                "status": r["status"],
                "origin": r["origin"],
                "source_field": r["source_field"],
                "scope": r["scope"],
                "note": r["note"],
                "evidence": evidence.get(r["relation_id"], []),
            }
            for r in rows
        ]

    def other_names(self) -> list[tuple[str, str]]:
        """(card id, name) of every alias and former name in `card_names`."""
        if not self.exists:
            return []
        with self._db() as db:
            if not db.execute("SELECT 1 FROM sqlite_master WHERE name = 'card_names'").fetchone():
                return []  # a dataset not written since the card model
            return [
                (str(r["card_id"]), str(r["name"]))
                for r in db.execute("SELECT card_id, name FROM card_names")
            ]

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
                    "id": r["id"],
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
            self._write(db, rows, result, filename=filename, actor=actor, kind=kind, at=at)
        return result

    def committed_run(self, run_id: str) -> str | None:
        """The import id an ingest run was committed as; None when it was not."""
        if not self.exists:
            return None
        with self._db() as db:
            columns = {r[1] for r in db.execute("PRAGMA table_info(imports)")}
            if "run_id" not in columns:
                return None
            row = db.execute("SELECT id FROM imports WHERE run_id = ?", (run_id,)).fetchone()
        return None if row is None else str(row[0])

    def commit_run(
        self,
        run_id: str,
        rows: Sequence[tuple[PlannedRow, str, int | None]],
        *,
        filename: str,
        actor: str,
    ) -> ApplyResult:
        """Write a reviewed run in one transaction. Each row carries its
        candidate id and the card version the review saw (None: no card then).
        Any card that moved on refuses the whole commit as `cards_changed`;
        nothing is written."""
        at = now()
        result = ApplyResult(import_id=uuid.uuid4().hex[:12])
        with self._db(write=True) as db:
            earlier = db.execute("SELECT id FROM imports WHERE run_id = ?", (run_id,)).fetchone()
            if earlier is not None:
                raise BiStoreError("run_committed", "這次執行已經寫入過了", import_id=earlier[0])
            moved = []
            for planned, candidate_id, version in rows:
                card = db.execute(
                    "SELECT id, version FROM cards WHERE entity_type = ? AND canonical_key = ?",
                    (planned.entity_type, planned.canonical_key),
                ).fetchone()
                current = None if card is None else int(card["version"])
                if current != version:
                    moved.append(
                        {
                            "candidate_id": candidate_id,
                            "card_id": None if card is None else card["id"],
                            "name": planned.name,
                            "expected": version,
                            "current": current,
                        }
                    )
            if moved:
                raise CardsChanged(moved)
            planned_rows = [planned for planned, _, _ in rows]
            types = sorted({planned.entity_type for planned in planned_rows})
            db.execute(
                "INSERT INTO imports (id, filename, entity_type, at, by, run_id) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (result.import_id, filename, ",".join(types), at, actor, run_id),
            )
            self._write(
                db, planned_rows, result, filename=filename, actor=actor, kind="import", at=at
            )
            for planned in planned_rows:
                card = db.execute(
                    "SELECT id FROM cards WHERE entity_type = ? AND canonical_key = ?",
                    (planned.entity_type, planned.canonical_key),
                ).fetchone()
                stored = {
                    r["field"]: r["value"]
                    for r in db.execute("SELECT * FROM fields WHERE card_id = ?", (card["id"],))
                }
                for name, items in planned.evidence.items():
                    if stored.get(name) != _dump(planned.values.get(name)):
                        continue  # kept a person's value: the evidence is in the proposal
                    for item in items:
                        db.execute(
                            "INSERT INTO evidence (card_id, field, run_id, source_id, "
                            "source_name, locator, excerpt, basis, at) "
                            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                            (
                                card["id"],
                                name,
                                run_id,
                                str(item.get("source_id") or ""),
                                str(item.get("source_name") or ""),
                                _dump(item.get("locator") or {}),
                                str(item.get("excerpt") or ""),
                                str(item.get("basis") or "fact"),
                                at,
                            ),
                        )
        return result

    def _write(
        self,
        db: sqlite3.Connection,
        rows: Sequence[PlannedRow],
        result: ApplyResult,
        *,
        filename: str,
        actor: str,
        kind: str,
        at: str,
    ) -> None:
        """Upsert `rows` into an open write transaction (`apply`, `commit_run`)."""
        for planned in rows:
            ref = planned.ref or f"{filename}#row{planned.row}"
            existing = db.execute(
                "SELECT * FROM cards WHERE entity_type = ? AND canonical_key = ?",
                (planned.entity_type, planned.canonical_key),
            ).fetchone()
            if existing is None:
                # A vault's card has the same id on every PC (knowledge repositories R2).
                card_id = (
                    card_id_for(planned.entity_type, planned.canonical_key)
                    if self.vault_id is not None
                    else uuid.uuid4().hex[:12]
                )
                if db.execute("SELECT 1 FROM cards WHERE id = ?", (card_id,)).fetchone():
                    # A former name hashes to the renamed card's id. Imports resolve
                    # one first (`names`), so only a caller that did not gets here.
                    raise BiStoreError(
                        "name_is_former", f"「{planned.name}」是另一張卡片以前的名字"
                    )
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
                if name in planned.propose or (stored is not None and stored["kind"] == "human"):
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

    def fact_evidence(self) -> set[tuple[str, str]]:
        """Every (card id, field) with evidence marked as fact (coverage)."""
        if not self.exists:
            return set()
        with self._db() as db:
            try:
                rows = db.execute(
                    "SELECT DISTINCT card_id, field FROM evidence WHERE basis = 'fact'"
                )
                return {(r["card_id"], r["field"]) for r in rows}
            except sqlite3.OperationalError:  # a dataset from before ingest runs
                return set()

    def fact_excerpts(self) -> dict[tuple[str, str], list[str]]:
        """Every fact excerpt per (card id, field), for the quality checks (V13)."""
        if not self.exists:
            return {}
        found: dict[tuple[str, str], list[str]] = {}
        with self._db() as db:
            try:
                rows = db.execute(
                    "SELECT card_id, field, excerpt FROM evidence WHERE basis = 'fact' ORDER BY seq"
                )
                for r in rows:
                    found.setdefault((r["card_id"], r["field"]), []).append(str(r["excerpt"]))
            except sqlite3.OperationalError:  # a dataset from before ingest runs
                return {}
        return found

    def evidence(self, card_id: str) -> list[dict[str, Any]]:
        """The evidence recorded for a card's values, newest first."""
        if not self.exists:
            return []
        with self._db() as db:
            try:
                rows = list(
                    db.execute(
                        "SELECT * FROM evidence WHERE card_id = ? ORDER BY seq DESC", (card_id,)
                    )
                )
            except sqlite3.OperationalError:  # a dataset from before ingest runs
                return []
        return [
            {
                "field": r["field"],
                "run_id": r["run_id"],
                "source_id": r["source_id"],
                "source_name": r["source_name"],
                "locator": _load(r["locator"]),
                "excerpt": r["excerpt"],
                "basis": r["basis"],
                "at": r["at"],
            }
            for r in rows
        ]

    def proposal(self, card_id: str, proposal_id: int) -> dict[str, Any] | None:
        """One pending proposal of a card; None when unknown or closed."""
        if not self.exists:
            return None
        with self._db() as db:
            row = db.execute(
                "SELECT * FROM proposals WHERE id = ? AND card_id = ? AND status = 'pending'",
                (proposal_id, card_id),
            ).fetchone()
        if row is None:
            return None
        return {"id": row["id"], "field": row["field"], "value": _load(row["value"])}

    def reject_proposal(self, card_id: str, proposal_id: int) -> bool:
        """Close one pending proposal without touching the card."""
        self.refuse_write()
        if not self.exists:
            return False
        with self._db(write=True) as db:
            changed = db.execute(
                "UPDATE proposals SET status = 'rejected' WHERE id = ? AND card_id = ? "
                "AND status = 'pending'",
                (proposal_id, card_id),
            ).rowcount
        return bool(changed)

    def change_marker(self) -> str:
        """Moves whenever the cards change: every write adds history or a card."""
        if not self.exists:
            return "empty"
        with self._db() as db:
            return self._marker(db)

    @staticmethod
    def _marker(db: sqlite3.Connection) -> str:
        seq = db.execute("SELECT COALESCE(MAX(seq), 0) FROM history").fetchone()[0]
        count, versions = db.execute(
            "SELECT COUNT(*), COALESCE(SUM(version), 0) FROM cards"
        ).fetchone()
        return f"{seq}:{count}:{versions}"

    def upgrade_schema(
        self,
        from_ref: str,
        to_ref: str,
        renames: dict[str, dict[str, str]],
        *,
        marker: str,
        actor: str,
        totals: dict[str, int],
        widenings: dict[str, dict[str, str]] | None = None,
    ) -> int:
        """Bind the dataset to another version of its schema in one
        transaction (BI ingest §5.3): refused as `preview_stale` when the
        cards changed since `marker`; values move only for the declared
        renames (a `migration` history row each), and a widened field's value
        becomes its list or decimal form (`{type: {field: new kind}}`, BI vault
        V9; a `migration` history row each); every other value stays as it is.
        Returns how many values moved or were widened."""

        self.refuse_write()
        at = now()
        moved = 0
        with self._db(write=True) as db:
            # The meta write in `_db` already holds the write lock from here on.
            if self._marker(db) != marker:
                raise BiStoreError("preview_stale", "資料集在預覽後有變動，請重新預覽")
            row = db.execute("SELECT value FROM meta WHERE key = 'schema'").fetchone()
            if row is None or str(row[0]) != from_ref:
                raise BiStoreError("preview_stale", "資料集的 schema 已經改變，請重新預覽")
            for type_name, fields in renames.items():
                for old, new in fields.items():
                    rows = db.execute(
                        "SELECT f.* FROM fields f JOIN cards c ON c.id = f.card_id "
                        "WHERE c.entity_type = ? AND f.field = ?",
                        (type_name, old),
                    ).fetchall()
                    for item in rows:
                        taken = db.execute(
                            "SELECT 1 FROM fields WHERE card_id = ? AND field = ?",
                            (item["card_id"], new),
                        ).fetchone()
                        if taken is not None:
                            continue  # the card already has the new field: keep both
                        db.execute(
                            "UPDATE fields SET field = ? WHERE card_id = ? AND field = ?",
                            (new, item["card_id"], old),
                        )
                        for name, before, after in (
                            (old, item["value"], None),
                            (new, None, item["value"]),
                        ):
                            db.execute(
                                "INSERT INTO history (card_id, field, old, new, kind, ref, by, at, "
                                "reason) VALUES (?, ?, ?, ?, 'migration', ?, ?, ?, ?)",
                                (
                                    item["card_id"],
                                    name,
                                    before,
                                    after,
                                    f"schema:{to_ref}",
                                    actor,
                                    at,
                                    f"schema 升級：{old} 改名為 {new}",
                                ),
                            )
                        db.execute(
                            "UPDATE cards SET version = version + 1, updated = ? WHERE id = ?",
                            (at, item["card_id"]),
                        )
                        moved += 1
            for type_name, fields in (widenings or {}).items():
                for name, new_kind in fields.items():
                    rows = db.execute(
                        "SELECT f.* FROM fields f JOIN cards c ON c.id = f.card_id "
                        "WHERE c.entity_type = ? AND f.field = ?",
                        (type_name, name),
                    ).fetchall()
                    for item in rows:
                        after = _dump(widen_value(_load(item["value"]), new_kind))
                        if after == item["value"]:
                            continue
                        db.execute(
                            "UPDATE fields SET value = ? WHERE card_id = ? AND field = ?",
                            (after, item["card_id"], name),
                        )
                        db.execute(
                            "INSERT INTO history (card_id, field, old, new, kind, ref, by, at, "
                            "reason) VALUES (?, ?, ?, ?, 'migration', ?, ?, ?, ?)",
                            (
                                item["card_id"],
                                name,
                                item["value"],
                                after,
                                f"schema:{to_ref}",
                                actor,
                                at,
                                f"schema 升級：{name} 放寬為 {new_kind}",
                            ),
                        )
                        db.execute(
                            "UPDATE cards SET version = version + 1, updated = ? WHERE id = ?",
                            (at, item["card_id"]),
                        )
                        moved += 1
            past = db.execute("SELECT value FROM meta WHERE key = 'schema_history'").fetchone()
            log = json.loads(past[0]) if past else []
            log.append(
                {"from": from_ref, "to": to_ref, "by": actor, "at": at, "moved": moved, **totals}
            )
            db.execute(
                "INSERT OR REPLACE INTO meta (key, value) VALUES ('schema_history', ?)",
                (_dump(log),),
            )
            db.execute("UPDATE meta SET value = ? WHERE key = 'schema'", (to_ref,))
        return moved

    def meta_value(self, key: str) -> str | None:
        """One `meta` value as stored; None when absent or no database."""
        if not self.exists:
            return None
        with self._db() as db:
            try:
                row = db.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
            except sqlite3.OperationalError:  # a dataset from before the schema binding
                return None
        return None if row is None else str(row[0])

    def set_meta_value(self, key: str, value: str, *, base: str | None) -> None:
        """Write one `meta` value made from `base` (what the caller read); in a
        vault the write becomes a change file. A different current value is
        409 `meta_stale`, nothing written."""
        self.refuse_write()
        with self._db(write=True) as db:
            row = db.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
            if (None if row is None else str(row[0])) != base:
                raise BiStoreError("meta_stale", "設定已被別人改過，請重新讀取後再改")
            db.execute("INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)", (key, value))

    def delete_meta_value(self, key: str, *, base: str) -> None:
        """Remove one `meta` value the caller read as `base` (else 409 `meta_stale`)."""
        self.refuse_write()
        with self._db(write=True) as db:
            row = db.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
            if (None if row is None else str(row[0])) != base:
                raise BiStoreError("meta_stale", "設定已被別人改過，請重新讀取後再改")
            db.execute("DELETE FROM meta WHERE key = ?", (key,))

    def schema_history(self) -> list[dict[str, Any]]:
        if not self.exists:
            return []
        with self._db() as db:
            row = db.execute("SELECT value FROM meta WHERE key = 'schema_history'").fetchone()
        return list(json.loads(row[0])) if row else []

    @staticmethod
    def _write_person_value(
        db: sqlite3.Connection,
        card_id: str,
        field: str,
        value: Any,
        stored: sqlite3.Row | None,
        actor: str,
        at: str,
        reason: str,
        *,
        ref: str | None = None,
        import_id: str | None = None,
    ) -> None:
        """A person's value, its history row, and the proposals it settles."""
        new = _dump(value)
        ref = ref or f"agent-web:{actor}"
        old_source = (
            None if stored is None else _dump({k: stored[k] for k in ("kind", "ref", "by", "at")})
        )
        if value is None:
            db.execute("DELETE FROM fields WHERE card_id = ? AND field = ?", (card_id, field))
        else:
            db.execute(
                "INSERT OR REPLACE INTO fields (card_id, field, value, kind, ref, by, at) "
                "VALUES (?, ?, ?, 'human', ?, ?, ?)",
                (card_id, field, new, ref, actor, at),
            )
        db.execute(
            "INSERT INTO history (card_id, field, old, new, kind, ref, by, at, import_id, "
            "reason, old_source) VALUES (?, ?, ?, ?, 'human', ?, ?, ?, ?, ?, ?)",
            (
                card_id,
                field,
                None if stored is None else stored["value"],
                None if value is None else new,
                ref,
                actor,
                at,
                import_id,
                reason,
                old_source,
            ),
        )
        db.execute(
            "UPDATE proposals SET status = 'superseded' WHERE card_id = ? AND field = ? "
            "AND status = 'pending'",
            (card_id, field),
        )

    def rename_card(
        self,
        card_id: str,
        *,
        key: str,
        name: str,
        values: dict[str, Any],
        alias: bool,
        base_version: int,
        actor: str,
        reason: str,
    ) -> int:
        """Rename a vault's card: its id stays and the old key stays reserved for
        it, so an import of the old name lands here (`BI_CARD_MODEL.md` §3.1).
        `values` are the naming fields; `alias`, whether the type has `aliases`.
        Returns the new version, or `base_version` when nothing changes."""
        at = now()
        with self._db(write=True) as db:
            card = db.execute("SELECT * FROM cards WHERE id = ?", (card_id,)).fetchone()
            if card is None:
                raise BiStoreError("card_unknown", "找不到這張卡片")
            if int(card["version"]) != int(base_version):
                raise BiStoreError(
                    "stale_edit",
                    "這張卡片在你開啟後已被修改，請重新載入",
                    version=int(card["version"]),
                )
            old_key, old_name = str(card["canonical_key"]), str(card["name"])
            if key == old_key:
                return int(card["version"])
            kind = str(card["entity_type"])
            taken = db.execute(
                "SELECT name FROM cards WHERE id != ? AND entity_type = ? AND "
                "(canonical_key = ? OR id = ? OR id IN (SELECT card_id FROM card_names "
                "WHERE kind = 'former' AND name = ?))",
                (card_id, kind, key, card_id_for(kind, key), key),
            ).fetchone()
            if taken is not None:
                raise BiStoreError(
                    "name_taken",
                    f"「{name}」已經是另一張卡片「{taken['name']}」的名字",
                    card=taken["name"],
                )
            db.execute(
                "DELETE FROM card_names WHERE card_id = ? AND name = ? AND kind = 'former'",
                (card_id, key),
            )
            db.execute(
                "INSERT OR IGNORE INTO card_names (card_id, name, kind) VALUES (?, ?, 'former')",
                (card_id, old_key),
            )
            stored = {
                r["field"]: r
                for r in db.execute("SELECT * FROM fields WHERE card_id = ?", (card_id,))
            }
            if alias:
                held = _load(stored["aliases"]["value"]) if "aliases" in stored else []
                held = held if isinstance(held, list) else [held]
                kept = [a for a in held if str(a).strip().lower() != name.strip().lower()]
                if old_name not in kept:
                    kept.append(old_name)
                if kept != held:
                    values = {**values, "aliases": kept}
            for field, value in values.items():
                row = stored.get(field)
                if row is None or row["value"] != _dump(value):
                    self._write_person_value(db, card_id, field, value, row, actor, at, reason)
            version = int(card["version"]) + 1
            db.execute(
                "UPDATE cards SET canonical_key = ?, name = ?, version = ?, updated = ? "
                "WHERE id = ?",
                (key, name, version, at, card_id),
            )
            return version

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
        """A person's value, internally: accepting a proposal, or a migration they
        confirmed. Refused as `stale_edit` when the card moved on.

        Returns the card's new version. The current value again (compared as
        stored JSON, as an import compares) is no change (owner 2026-10-24):
        nothing is written and the version returned is `base_version`."""
        self.refuse_write()
        if not self.exists:
            raise BiStoreError("card_unknown", "找不到這張卡片")
        with self._db(write=True) as db:
            return self._write_field(
                db,
                card_id,
                field,
                value,
                base_version=base_version,
                actor=actor,
                reason=reason,
                ref=f"agent-web:{actor}",
                at=now(),
            )

    def correct(
        self,
        card_id: str,
        field: str,
        value: Any,
        *,
        base_version: int,
        actor: str,
        reason: str,
        ref: str,
        run_id: str,
        evidence: Mapping[str, Any],
    ) -> tuple[int, str]:
        """Write a correction note's value with its evidence, in one transaction. It
        is an import of one value, so a vault commits it at once and it can be undone.
        The caller has already turned away a note that changes nothing."""
        self.refuse_write()
        at = now()
        import_id = uuid.uuid4().hex[:12]
        with self._db(write=True) as db:
            card = db.execute("SELECT * FROM cards WHERE id = ?", (card_id,)).fetchone()
            if card is None:
                raise BiStoreError("card_unknown", "找不到這張卡片")
            db.execute(
                "INSERT INTO imports (id, filename, entity_type, at, by, run_id) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (import_id, ref, card["entity_type"], at, actor, run_id),
            )
            version = self._write_field(
                db,
                card_id,
                field,
                value,
                base_version=base_version,
                actor=actor,
                reason=reason,
                ref=ref,
                at=at,
                import_id=import_id,
            )
            db.execute(
                "INSERT INTO evidence (card_id, field, run_id, source_id, source_name, "
                "locator, excerpt, basis, at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    card_id,
                    field,
                    run_id,
                    str(evidence.get("source_id") or ""),
                    str(evidence.get("source_name") or ""),
                    _dump(evidence.get("locator") or {}),
                    str(evidence.get("excerpt") or ""),
                    str(evidence.get("basis") or "human"),
                    at,
                ),
            )
            return version, import_id

    def refuse_moved(self, card_id: str, field: str, base_version: int) -> None:
        """`stale_edit` when the card is no longer at the version the person saw."""
        with self._db() as db:
            card = db.execute("SELECT * FROM cards WHERE id = ?", (card_id,)).fetchone()
            if card is None:
                raise BiStoreError("card_unknown", "找不到這張卡片")
            self._refuse_stale(db, card, field, base_version)

    def first_home(self, card_id: str) -> str | None:
        """The first home a card has evidence from (`card_app_folders`), if any."""
        with self._db() as db:
            if not db.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'card_app_folders'"
            ).fetchone():
                return None  # a dataset not written since the card model
            row = db.execute(
                "SELECT application FROM card_app_folders WHERE card_id = ? "
                "ORDER BY application LIMIT 1",
                (card_id,),
            ).fetchone()
            return None if row is None else str(row[0])

    def _refuse_stale(
        self, db: sqlite3.Connection, card: sqlite3.Row, field: str, base_version: int
    ) -> None:
        if int(card["version"]) == int(base_version):
            return
        stored = db.execute(
            "SELECT * FROM fields WHERE card_id = ? AND field = ?", (card["id"], field)
        ).fetchone()
        last = db.execute(
            "SELECT by, at FROM history WHERE card_id = ? ORDER BY seq DESC LIMIT 1",
            (card["id"],),
        ).fetchone()
        raise BiStoreError(
            "stale_edit",
            "這張卡片在你開啟後已被修改，請重新載入",
            current=None if stored is None else _load(stored["value"]),
            by=(stored["by"] if stored is not None else (last["by"] if last else "")),
            at=(stored["at"] if stored is not None else (last["at"] if last else "")),
            version=int(card["version"]),
        )

    def _write_field(
        self,
        db: sqlite3.Connection,
        card_id: str,
        field: str,
        value: Any,
        *,
        base_version: int,
        actor: str,
        reason: str,
        ref: str,
        at: str,
        import_id: str | None = None,
    ) -> int:
        card = db.execute("SELECT * FROM cards WHERE id = ?", (card_id,)).fetchone()
        if card is None:
            raise BiStoreError("card_unknown", "找不到這張卡片")
        self._refuse_stale(db, card, field, base_version)
        stored = db.execute(
            "SELECT * FROM fields WHERE card_id = ? AND field = ?", (card_id, field)
        ).fetchone()
        new = _dump(value)
        if (stored is None and value is None) or (
            stored is not None and value is not None and stored["value"] == new
        ):
            return int(card["version"])
        self._write_person_value(
            db, card_id, field, value, stored, actor, at, reason, ref=ref, import_id=import_id
        )
        version = int(card["version"]) + 1
        db.execute("UPDATE cards SET version = ?, updated = ? WHERE id = ?", (version, at, card_id))
        return version

    def undo_import(self, import_id: str, *, actor: str) -> None:
        """Undo a whole import: restore each field it changed (unless a person
        changed it since), drop its proposals, and remove the cards it created
        that nothing else has written."""
        self.refuse_write()
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
