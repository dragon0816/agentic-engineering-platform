"""The staging store of a BI dataset: sources, ingest runs and candidates.

BI ingest phase 1 (`docs/phases/BI_INGEST.md` §4, owner 2026-10-27). Trial
runs, extraction and review write only here, in
`<workspace>/bi/<dataset>/staging.sqlite`, and the source copies under
`<dataset>/sources/`; the dataset's cards (`bi.sqlite`) change only when a
reviewed run is committed (`BiStore.commit_run`). A subscribed dataset
refuses every write, as its cards do.

A source is a controlled copy of what the person gave: the bytes are kept
once per content hash and the person's own file is never moved or changed.
A run fixes what produced it (schema, method, model) so it can be traced
later. Candidates are stored whole, as JSON, with their review state and the
person's edits.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import re
import sqlite3
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path, PurePath
from typing import Any

from capabilities.bi_cards import schema_versions
from capabilities.bi_cards.store import BiStore, BiStoreError, now

STAGING_FILE = "staging.sqlite"
SOURCES_DIR = "sources"
#: The data classes a source may carry (`models.data_approval.approved_classes`).
CLASSIFICATIONS = ("UNCLASSIFIED", "INTERNAL", "CONFIDENTIAL", "RESTRICTED")
DEFAULT_CLASSIFICATION = "INTERNAL"
TABLE_TYPES = {
    ".csv": "text/csv",
    ".tsv": "text/tab-separated-values",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}
TEXT_TYPES = {".txt": "text/plain", ".md": "text/markdown"}
MAX_RUNS_LISTED = 100
RUN_KINDS = ("trial", "ingest")

SCHEMA = """
CREATE TABLE IF NOT EXISTS sources (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  sha256 TEXT NOT NULL UNIQUE,
  media_type TEXT NOT NULL,
  size INTEGER NOT NULL,
  origin TEXT NOT NULL,
  stored TEXT NOT NULL,
  classification TEXT NOT NULL,
  by TEXT NOT NULL,
  at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS runs (
  id TEXT PRIMARY KEY,
  kind TEXT NOT NULL,
  status TEXT NOT NULL,
  method_ref TEXT,
  schema_ref TEXT NOT NULL,
  model TEXT,
  source_ids TEXT NOT NULL,
  by TEXT NOT NULL,
  at TEXT NOT NULL,
  finished TEXT,
  error TEXT,
  commit_result TEXT
);
CREATE TABLE IF NOT EXISTS candidates (
  run_id TEXT NOT NULL,
  id TEXT NOT NULL,
  seq INTEGER NOT NULL,
  body TEXT NOT NULL,
  PRIMARY KEY (run_id, id)
);
CREATE TABLE IF NOT EXISTS run_layouts (
  run_id TEXT PRIMARY KEY,
  body TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS recipes (
  id TEXT NOT NULL,
  name TEXT NOT NULL,
  version INTEGER NOT NULL,
  body TEXT NOT NULL,
  by TEXT NOT NULL,
  at TEXT NOT NULL,
  PRIMARY KEY (id, version)
);
"""


def parse_kind(name: str) -> str:
    """How a source is read: `table`, `text` or `unsupported`. An Excel
    workbook is a table source since phase 3 (read through a recipe); a
    Markdown report stays text, which a recipe can also read for its tables."""
    suffix = PurePath(name).suffix.lower()
    if suffix in TABLE_TYPES:
        return "table"
    if suffix in TEXT_TYPES:
        return "text"
    return "unsupported"


def _media_type(name: str, given: Any) -> str:
    if isinstance(given, str) and re.fullmatch(r"[\w.+-]+/[\w.+-]+", given.strip()):
        return given.strip()
    suffix = PurePath(name).suffix.lower()
    return TABLE_TYPES.get(suffix) or TEXT_TYPES.get(suffix) or "application/octet-stream"


def _dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


class Staging:
    """Sources, runs and candidates of one dataset."""

    def __init__(self, workspace: Path, dataset: str) -> None:
        self.store = BiStore(workspace, dataset)
        self.dataset = dataset
        self.dir = self.store.dir
        self.path = self.dir / STAGING_FILE

    @property
    def exists(self) -> bool:
        return self.path.is_file()

    @contextmanager
    def _db(self, *, write: bool = False) -> Iterator[sqlite3.Connection]:
        if write:
            self.store.refuse_write()
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

    # -- sources ----------------------------------------------------------

    def add_source(
        self,
        name: Any,
        *,
        text: Any = None,
        content_base64: Any = None,
        media_type: Any = None,
        classification: Any = None,
        actor: str,
    ) -> dict[str, Any]:
        """Keep a copy of an uploaded source; the same bytes are kept once."""
        self.store.refuse_write()
        label = str(name or "").strip()
        if not label or len(label) > 200 or PurePath(label).name != label or "\\" in label:
            raise BiStoreError("source_name_invalid", "來源檔名必須是 1–200 字、不含資料夾的檔名")
        if isinstance(text, str) and text:
            data = text.encode("utf-8")
        elif isinstance(content_base64, str) and content_base64:
            try:
                data = base64.b64decode(content_base64, validate=True)
            except (binascii.Error, ValueError) as error:
                raise BiStoreError("source_base64_invalid", "檔案內容不是有效的 base64") from error
        else:
            raise BiStoreError("source_missing", "沒有來源內容")
        if not data:
            raise BiStoreError("source_missing", "來源是空的")
        level = str(classification or DEFAULT_CLASSIFICATION).upper()
        if level not in CLASSIFICATIONS:
            allowed = ", ".join(CLASSIFICATIONS)
            raise BiStoreError("classification_invalid", f"機密等級只能是 {allowed}")
        digest = hashlib.sha256(data).hexdigest()
        with self._db(write=True) as db:
            found = db.execute("SELECT * FROM sources WHERE sha256 = ?", (digest,)).fetchone()
            if found is not None:
                return {**self._source(found), "already": True}
            suffix = PurePath(label).suffix.lower()
            if not re.fullmatch(r"\.\w{1,8}", suffix):
                suffix = ""
            stored = f"{SOURCES_DIR}/{digest}{suffix}"
            target = self.dir / stored
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_name(f".{target.name}.{uuid.uuid4().hex[:8]}.tmp")
            temporary.write_bytes(data)
            schema_versions.replace(temporary, target)
            source_id = uuid.uuid4().hex[:12]
            db.execute(
                "INSERT INTO sources (id, name, sha256, media_type, size, origin, stored, "
                "classification, by, at) VALUES (?, ?, ?, ?, ?, 'upload', ?, ?, ?, ?)",
                (
                    source_id,
                    label,
                    digest,
                    _media_type(label, media_type),
                    len(data),
                    stored,
                    level,
                    actor,
                    now(),
                ),
            )
            row = db.execute("SELECT * FROM sources WHERE id = ?", (source_id,)).fetchone()
        return {**self._source(row), "already": False}

    @staticmethod
    def _source(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "name": row["name"],
            "sha256": row["sha256"],
            "media_type": row["media_type"],
            "size": row["size"],
            "origin": row["origin"],
            "classification": row["classification"],
            "at": row["at"],
            "by": row["by"],
            "parse": parse_kind(row["name"]),
        }

    def sources(self) -> list[dict[str, Any]]:
        if not self.exists:
            return []
        with self._db() as db:
            rows = db.execute("SELECT * FROM sources ORDER BY at DESC, rowid DESC").fetchall()
        return [self._source(r) for r in rows]

    def source(self, source_id: str) -> dict[str, Any] | None:
        if not self.exists:
            return None
        with self._db() as db:
            row = db.execute("SELECT * FROM sources WHERE id = ?", (source_id,)).fetchone()
        return None if row is None else self._source(row)

    def source_bytes(self, source_id: str) -> bytes:
        if not self.exists:
            raise BiStoreError("source_unknown", "找不到這個來源")
        with self._db() as db:
            row = db.execute("SELECT stored FROM sources WHERE id = ?", (source_id,)).fetchone()
        if row is None:
            raise BiStoreError("source_unknown", "找不到這個來源")
        return (self.dir / str(row["stored"])).read_bytes()

    # -- runs -------------------------------------------------------------

    def create_run(
        self,
        *,
        kind: str,
        schema_ref: str,
        source_ids: list[str],
        actor: str,
        method_ref: str | None = None,
        model: str | None = None,
    ) -> str:
        if kind not in RUN_KINDS:
            raise BiStoreError("run_kind_invalid", "kind 只能是 trial 或 ingest")
        run_id = uuid.uuid4().hex[:12]
        with self._db(write=True) as db:
            db.execute(
                "INSERT INTO runs (id, kind, status, method_ref, schema_ref, model, source_ids, "
                "by, at) VALUES (?, ?, 'queued', ?, ?, ?, ?, ?, ?)",
                (run_id, kind, method_ref, schema_ref, model, _dump(source_ids), actor, now()),
            )
        return run_id

    def set_status(
        self,
        run_id: str,
        status: str,
        *,
        error: str | None = None,
        commit_result: dict[str, Any] | None = None,
    ) -> None:
        finished = (
            now() if status in ("review", "partial", "committed", "cancelled", "failed") else None
        )
        with self._db(write=True) as db:
            db.execute(
                "UPDATE runs SET status = ?, finished = COALESCE(?, finished), "
                "error = COALESCE(?, error), commit_result = COALESCE(?, commit_result) "
                "WHERE id = ?",
                (
                    status,
                    finished,
                    error,
                    None if commit_result is None else _dump(commit_result),
                    run_id,
                ),
            )

    def run_row(self, run_id: str) -> dict[str, Any] | None:
        if not self.exists:
            return None
        with self._db() as db:
            row = db.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        return None if row is None else self._run(row)

    def run_rows(self) -> list[dict[str, Any]]:
        if not self.exists:
            return []
        with self._db() as db:
            rows = db.execute(
                "SELECT * FROM runs ORDER BY at DESC, rowid DESC LIMIT ?", (MAX_RUNS_LISTED,)
            ).fetchall()
        return [self._run(r) for r in rows]

    @staticmethod
    def _run(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "kind": row["kind"],
            "status": row["status"],
            "method_ref": row["method_ref"],
            "schema_ref": row["schema_ref"],
            "model": row["model"],
            "source_ids": json.loads(row["source_ids"]),
            "by": row["by"],
            "at": row["at"],
            "finished": row["finished"],
            "error": row["error"],
            "commit": None if row["commit_result"] is None else json.loads(row["commit_result"]),
        }

    # -- candidates -------------------------------------------------------

    def put_candidates(self, run_id: str, candidates: list[dict[str, Any]]) -> None:
        """Store (or replace) candidates, keeping their order."""
        with self._db(write=True) as db:
            for seq, candidate in enumerate(candidates):
                db.execute(
                    "INSERT OR REPLACE INTO candidates (run_id, id, seq, body) VALUES "
                    "(?, ?, COALESCE((SELECT seq FROM candidates WHERE run_id = ? AND id = ?), ?), "
                    "?)",
                    (run_id, candidate["id"], run_id, candidate["id"], seq, _dump(candidate)),
                )

    def candidates(self, run_id: str) -> list[dict[str, Any]]:
        if not self.exists:
            return []
        with self._db() as db:
            rows = db.execute(
                "SELECT body FROM candidates WHERE run_id = ? ORDER BY seq", (run_id,)
            ).fetchall()
        return [json.loads(r["body"]) for r in rows]

    # -- run layout (the rule path's tables and passes) -------------------

    def put_layout(self, run_id: str, layout: dict[str, Any]) -> None:
        with self._db(write=True) as db:
            db.execute(
                "INSERT OR REPLACE INTO run_layouts (run_id, body) VALUES (?, ?)",
                (run_id, _dump(layout)),
            )

    def layout(self, run_id: str) -> dict[str, Any] | None:
        if not self.exists:
            return None
        with self._db() as db:
            if not _has_table(db, "run_layouts"):
                return None
            row = db.execute("SELECT body FROM run_layouts WHERE run_id = ?", (run_id,)).fetchone()
        return None if row is None else dict(json.loads(row["body"]))

    # -- recipes (BI ingest phase 3) ---------------------------------------

    def save_recipe(self, body: dict[str, Any], *, actor: str) -> dict[str, Any]:
        """Save a validated recipe: a new name gets an id, the same name the
        next version. The same content as the latest version is not saved
        again (`already`), so saving twice does not invent a version."""
        name = str(body["name"])
        with self._db(write=True) as db:
            latest = db.execute(
                "SELECT * FROM recipes WHERE name = ? ORDER BY version DESC LIMIT 1", (name,)
            ).fetchone()
            if latest is not None and json.loads(latest["body"]) == body:
                return {**self._recipe(latest), "already": True}
            recipe_id = uuid.uuid4().hex[:12] if latest is None else str(latest["id"])
            version = 1 if latest is None else int(latest["version"]) + 1
            db.execute(
                "INSERT INTO recipes (id, name, version, body, by, at) VALUES (?, ?, ?, ?, ?, ?)",
                (recipe_id, name, version, _dump(body), actor, now()),
            )
            row = db.execute(
                "SELECT * FROM recipes WHERE id = ? AND version = ?", (recipe_id, version)
            ).fetchone()
        return {**self._recipe(row), "already": False}

    @staticmethod
    def _recipe(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "name": row["name"],
            "version": int(row["version"]),
            "recipe": json.loads(row["body"]),
            "by": row["by"],
            "at": row["at"],
        }

    def recipes(self) -> list[dict[str, Any]]:
        """The latest version of every recipe, newest first."""
        if not self.exists:
            return []
        with self._db() as db:
            if not _has_table(db, "recipes"):
                return []
            rows = db.execute(
                "SELECT r.* FROM recipes r WHERE r.version = "
                "(SELECT MAX(version) FROM recipes WHERE id = r.id) "
                "ORDER BY r.at DESC, r.rowid DESC"
            ).fetchall()
        return [self._recipe(r) for r in rows]

    def recipe_versions(self, recipe_id: str) -> list[dict[str, Any]]:
        """Every version of one recipe, newest first (empty: unknown)."""
        if not self.exists:
            return []
        with self._db() as db:
            if not _has_table(db, "recipes"):
                return []
            rows = db.execute(
                "SELECT * FROM recipes WHERE id = ? ORDER BY version DESC", (recipe_id,)
            ).fetchall()
        return [self._recipe(r) for r in rows]


def _has_table(db: sqlite3.Connection, name: str) -> bool:
    """A staging store written before phase 3 lacks the newer tables until
    its next write; reading it must not fail."""
    found = db.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (name,)
    ).fetchone()
    return found is not None
