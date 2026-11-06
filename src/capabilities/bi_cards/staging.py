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

Since BI vault phase V2 (`docs/phases/BI_VAULT.md` §5) every source also has
Markdown revisions: revision 1 is the conversion made when the source is
added (`convert.py`), each person's edit is a new revision, and a revision is
never changed. The text is a file `markdown/<source id>/rev-<n>.md` beside
the original copy; who, when, why and its hash are in the table `markdown`.
A source that cannot be converted is still kept with the reason
(`conversions`) and converted again when next needed; a PDF without any
text is refused. A run records the revision it read (`runs.markdown_rev`).
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import re
import shutil
import sqlite3
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path, PurePath
from typing import Any, BinaryIO

from capabilities.bi_cards import convert, schema_versions, vault_sources
from capabilities.bi_cards.store import BiStore, BiStoreError, now
from knowledge.repo.repository import RepoError

STAGING_FILE = "staging.sqlite"
SOURCES_DIR = "sources"
#: The data classes a source may carry (`models.data_approval.approved_classes`).
CLASSIFICATIONS = ("UNCLASSIFIED", "INTERNAL", "CONFIDENTIAL", "RESTRICTED")
DEFAULT_CLASSIFICATION = "INTERNAL"
TABLE_TYPES = {
    ".csv": "text/csv",
    ".tsv": "text/tab-separated-values",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".xlsm": "application/vnd.ms-excel.sheet.macroEnabled.12",
}
#: Read as text by the AI path (documents through their Markdown, BI vault V2).
TEXT_TYPES = {
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".markdown": "text/markdown",
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}
MARKDOWN_DIR = "markdown"
MAX_RUNS_LISTED = 100
#: A `stored` value naming a file in the vault's repository folder, not here: a
#: colleague's source is read through, with no second copy.
REPOSITORY_FILE = "repo:"
UPLOAD_CHUNK_BYTES = 1 << 20
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
CREATE TABLE IF NOT EXISTS markdown (
  source_id TEXT NOT NULL,
  rev INTEGER NOT NULL,
  origin TEXT NOT NULL,
  note TEXT NOT NULL,
  converter TEXT,
  sha256 TEXT NOT NULL,
  chars INTEGER NOT NULL,
  lines INTEGER NOT NULL,
  stored TEXT NOT NULL,
  by TEXT NOT NULL,
  at TEXT NOT NULL,
  PRIMARY KEY (source_id, rev)
);
CREATE TABLE IF NOT EXISTS conversions (
  source_id TEXT PRIMARY KEY,
  code TEXT NOT NULL,
  message TEXT NOT NULL,
  at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
  id TEXT PRIMARY KEY,
  kind TEXT NOT NULL,
  target_ref TEXT NOT NULL,
  body TEXT NOT NULL,
  model TEXT,
  by TEXT NOT NULL,
  at TEXT NOT NULL,
  updated TEXT NOT NULL
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
                columns = {r[1] for r in connection.execute("PRAGMA table_info(runs)")}
                if "markdown_rev" not in columns:  # a store from before BI vault V2
                    connection.execute("ALTER TABLE runs ADD COLUMN markdown_rev INTEGER")
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
        folder: Any = None,
        actor: str,
    ) -> dict[str, Any]:
        """Keep a copy of an uploaded source; the same bytes are kept once. In a
        vault it is also staged for the shared folder, in `folder`."""
        label, level = self.checked_upload(name, classification)
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
        digest = hashlib.sha256(data).hexdigest()
        known = self._source_by_digest(digest)
        if known is not None:
            return {**known, "already": True}
        self._refuse_withdrawn(digest)
        temporary = self._temporary()
        try:
            temporary.write_bytes(data)
            return self._keep(label, level, digest, temporary, media_type, folder, actor)
        finally:
            temporary.unlink(missing_ok=True)

    def checked_upload(self, name: Any, classification: Any) -> tuple[str, str]:
        """A source's file name and classification, before any of it is read."""
        self.store.refuse_write()
        label = str(name or "").strip()
        if not label or len(label) > 200 or PurePath(label).name != label or "\\" in label:
            raise BiStoreError("source_name_invalid", "來源檔名必須是 1–200 字、不含資料夾的檔名")
        level = str(classification or DEFAULT_CLASSIFICATION).upper()
        if level not in CLASSIFICATIONS:
            allowed = ", ".join(CLASSIFICATIONS)
            raise BiStoreError("classification_invalid", f"機密等級只能是 {allowed}")
        return label, level

    def add_source_stream(
        self,
        label: str,
        level: str,
        stream: BinaryIO,
        length: int,
        *,
        media_type: Any = None,
        folder: Any = None,
        actor: str,
    ) -> dict[str, Any]:
        """Like `add_source` for a file of any size (owner 2026-11-03): the bytes go
        to disk as they arrive and are hashed on the way, never held whole. Only a
        format that is converted to Markdown is read back whole, by the converter."""
        if length <= 0:
            raise BiStoreError("source_missing", "來源是空的")
        temporary = self._temporary()
        digest = hashlib.sha256()
        left = length
        try:
            with temporary.open("wb") as handle:
                while left > 0:
                    chunk = stream.read(min(UPLOAD_CHUNK_BYTES, left))
                    if not chunk:
                        raise BiStoreError("source_incomplete", "檔案沒有傳完，請再加入一次")
                    handle.write(chunk)
                    digest.update(chunk)
                    left -= len(chunk)
            known = self._source_by_digest(digest.hexdigest())
            if known is not None:
                return {**known, "already": True}
            self._refuse_withdrawn(digest.hexdigest())
            return self._keep(
                label, level, digest.hexdigest(), temporary, media_type, folder, actor
            )
        finally:
            temporary.unlink(missing_ok=True)

    def _temporary(self) -> Path:
        self.dir.mkdir(parents=True, exist_ok=True)
        return self.dir / f".upload-{uuid.uuid4().hex[:12]}.tmp"

    def _keep(
        self,
        label: str,
        level: str,
        digest: str,
        temporary: Path,
        media_type: Any,
        folder: Any,
        actor: str,
    ) -> dict[str, Any]:
        """Keep a received file (moved from `temporary`) and its Markdown."""
        size = temporary.stat().st_size
        # Converted before anything is kept: a PDF without text is refused.
        markdown: str | None = None
        failure: BiStoreError | None = None
        if convert.kind(label) is not None:
            try:
                markdown = convert.convert(label, temporary.read_bytes())
            except BiStoreError as error:
                if error.code == "source_no_text":
                    raise
                failure = error
        with self._db(write=True) as db:
            found = db.execute("SELECT id FROM sources WHERE sha256 = ?", (digest,)).fetchone()
            if found is not None:  # the same bytes added at the same moment
                return {**(self.source(str(found["id"])) or {}), "already": True}
            suffix = PurePath(label).suffix.lower()
            if not re.fullmatch(r"\.\w{1,8}", suffix):
                suffix = ""
            stored = f"{SOURCES_DIR}/{digest}{suffix}"
            target = self.dir / stored
            target.parent.mkdir(parents=True, exist_ok=True)
            schema_versions.replace(temporary, target)
            source_id = (
                vault_sources.stable_id(digest)
                if self.store.vault_id is not None
                else uuid.uuid4().hex[:12]
            )
            db.execute(
                "INSERT INTO sources (id, name, sha256, media_type, size, origin, stored, "
                "classification, by, at) VALUES (?, ?, ?, ?, ?, 'upload', ?, ?, ?, ?)",
                (
                    source_id,
                    label,
                    digest,
                    _media_type(label, media_type),
                    size,
                    stored,
                    level,
                    actor,
                    now(),
                ),
            )
            if markdown is not None:
                self._insert_markdown(
                    db,
                    source_id,
                    1,
                    markdown,
                    origin="conversion",
                    note="轉檔",
                    converter=convert.CONVERTER,
                    actor=actor,
                )
            elif failure is not None:
                self._record_failure(db, source_id, failure)
        if markdown is not None:
            from capabilities.bi_cards import search_index  # its passages (BI vault V3)

            search_index.sync_quietly(self.store)
        self._share(source_id, folder)
        return {**(self.source(source_id) or {}), "already": False}

    def _vault_repo(self) -> Any:
        """This vault's repository; None for a dataset only on this PC, or while
        its shared folder is out of reach (the source stays here until `share`)."""
        if self.store.vault_id is None:
            return None
        from capabilities.bi_cards import vault  # it imports this module's readers

        try:
            target = vault.Vault(self.store.workspace, self.store.vault_id)
        except BiStoreError:
            return None
        return target.repo if target.reachable else None

    def _refuse_withdrawn(self, digest: str) -> None:
        repo = self._vault_repo()
        if repo is not None:
            vault_sources.refuse_withdrawn(repo, digest)

    def purge_withdrawn(self, shas: set[str]) -> int:
        """Remove withdrawn sources from this PC (design §5): the row, the stored
        copies and passages; a run's candidates not yet written; a written run
        stays, with its excerpts blanked."""
        if not self.exists:
            return 0
        with self._db() as db:
            rows = [
                row
                for row in db.execute("SELECT id, sha256, stored FROM sources").fetchall()
                if str(row["sha256"]) in shas
            ]
        if not rows:
            return 0
        with self._db(write=True) as db:
            for row in rows:
                source_id = str(row["id"])
                revisions = db.execute(
                    "SELECT stored FROM markdown WHERE source_id = ?", (source_id,)
                ).fetchall()
                for stored in [row["stored"], *(r["stored"] for r in revisions)]:
                    if not str(stored).startswith(REPOSITORY_FILE):
                        (self.dir / str(stored)).unlink(missing_ok=True)
                db.execute("DELETE FROM markdown WHERE source_id = ?", (source_id,))
                db.execute("DELETE FROM conversions WHERE source_id = ?", (source_id,))
                db.execute("DELETE FROM sources WHERE id = ?", (source_id,))
                self._purge_runs(db, source_id)
        from capabilities.bi_cards import search_index  # its passages (BI vault V3)

        search_index.sync_quietly(self.store)
        return len(rows)

    @staticmethod
    def _purge_runs(db: sqlite3.Connection, source_id: str) -> None:
        for run in db.execute("SELECT id, status, source_ids FROM runs").fetchall():
            if source_id not in json.loads(run["source_ids"]):
                continue
            db.execute("DELETE FROM run_layouts WHERE run_id = ?", (run["id"],))
            if run["status"] != "committed":
                db.execute("DELETE FROM candidates WHERE run_id = ?", (run["id"],))
                db.execute(
                    "UPDATE runs SET status = 'failed', error = ?, finished = ? WHERE id = ?",
                    ("來源已撤回", now(), run["id"]),
                )
                continue
            for row in db.execute(
                "SELECT id, body FROM candidates WHERE run_id = ?", (run["id"],)
            ).fetchall():
                body = json.loads(row["body"])
                for field in body.get("fields") or ():
                    for proof in field.get("evidence") or ():
                        proof["excerpt"] = ""
                db.execute(
                    "UPDATE candidates SET body = ? WHERE run_id = ? AND id = ?",
                    (_dump(body), run["id"], row["id"]),
                )

    def _share(self, source_id: str, folder: Any) -> None:
        repo = self._vault_repo()
        if repo is None:
            return
        try:
            with repo.lock:
                vault_sources.stage_source(repo, self, source_id, folder)
        except RepoError as failure:
            raise BiStoreError(failure.code, failure.message) from None

    def _file(self, stored: str) -> Path:
        if not stored.startswith(REPOSITORY_FILE):
            return self.dir / stored
        repo = self._vault_repo()
        if repo is None:
            raise BiStoreError("source_unreachable", "讀不到共用資料夾，這個來源現在不能開")
        return Path(repo.folder) / stored[len(REPOSITORY_FILE) :]

    def _read(self, stored: str) -> bytes:
        try:
            return self._file(stored).read_bytes()
        except OSError:
            raise BiStoreError(
                "source_unreadable",
                "現在讀不到這個來源；確認 OneDrive 已同步，並設為一律保留在此裝置上",
            ) from None

    def sync_from_units(self, units: list[dict[str, Any]]) -> dict[str, int]:
        """Make what the repository says about its sources true here: a source
        or revision this PC lacks gets a row reading through to the repository
        file; a source read through that is no longer there goes. What this PC
        added itself, its runs and its sessions stay as they are."""
        if not units and not self.exists:
            return {"added": 0, "removed": 0}
        if self.exists and self._in_step_with(units):
            # Every sync comes here: no write lock when there is nothing to write.
            return {"added": 0, "removed": 0}
        added, removed = 0, 0
        changed = False
        with self._db(write=True) as db:
            present = {str(r["sha256"]): str(r["id"]) for r in db.execute("SELECT * FROM sources")}
            for unit in units:
                source_id = present.get(str(unit["sha256"]))
                if source_id is None:
                    source_id = str(unit["id"])
                    db.execute(
                        "INSERT INTO sources (id, name, sha256, media_type, size, origin, stored, "
                        "classification, by, at) VALUES (?, ?, ?, ?, ?, 'repository', ?, ?, ?, ?)",
                        (
                            source_id,
                            unit["name"],
                            unit["sha256"],
                            unit.get("media_type") or _media_type(str(unit["name"]), None),
                            unit["bytes"],
                            REPOSITORY_FILE + str(unit["file"]),
                            unit.get("classification") or DEFAULT_CLASSIFICATION,
                            unit.get("by") or "",
                            unit.get("at") or now(),
                        ),
                    )
                    added += 1
                    changed = True
                changed = self._sync_revisions(db, source_id, unit) or changed
            kept = {str(unit["sha256"]) for unit in units}
            for row in db.execute(
                "SELECT id, sha256 FROM sources WHERE stored LIKE ?", (REPOSITORY_FILE + "%",)
            ).fetchall():
                if str(row["sha256"]) not in kept:
                    db.execute("DELETE FROM markdown WHERE source_id = ?", (row["id"],))
                    db.execute("DELETE FROM sources WHERE id = ?", (row["id"],))
                    removed += 1
                    changed = True
        if changed:
            from capabilities.bi_cards import search_index  # its passages (BI vault V3)

            search_index.sync_quietly(self.store)
        return {"added": added, "removed": removed}

    def _in_step_with(self, units: list[dict[str, Any]]) -> bool:
        with self._db() as db:
            if not _has_table(db, "markdown"):
                return not units
            present = {str(r["sha256"]): str(r["id"]) for r in db.execute("SELECT * FROM sources")}
            revisions = {
                (str(r["source_id"]), int(r["rev"])): str(r["sha256"])
                for r in db.execute("SELECT source_id, rev, sha256 FROM markdown")
            }
            through = {
                str(r["sha256"])
                for r in db.execute(
                    "SELECT sha256 FROM sources WHERE stored LIKE ?", (REPOSITORY_FILE + "%",)
                )
            }
        kept = {str(unit["sha256"]) for unit in units}
        return (
            through <= kept
            and kept <= set(present)
            and all(
                revisions.get((present[str(unit["sha256"])], int(item["rev"]))) == item["sha256"]
                for unit in units
                for item in unit.get("markdown") or ()
            )
        )

    @staticmethod
    def _sync_revisions(db: sqlite3.Connection, source_id: str, unit: dict[str, Any]) -> bool:
        """The revisions the unit names, as this source's rows. The unit decides:
        a revision a conflict settled the other way takes the repository's text."""
        changed = False
        for item in unit.get("markdown") or ():
            rev = int(item["rev"])
            row = db.execute(
                "SELECT sha256 FROM markdown WHERE source_id = ? AND rev = ?", (source_id, rev)
            ).fetchone()
            if row is not None and row["sha256"] == item["sha256"]:
                continue
            db.execute(
                "INSERT OR REPLACE INTO markdown (source_id, rev, origin, note, converter, sha256, "
                "chars, lines, stored, by, at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    source_id,
                    rev,
                    item["origin"],
                    item["note"],
                    item.get("converter"),
                    item["sha256"],
                    item["chars"],
                    item["lines"],
                    REPOSITORY_FILE + str(item["file"]),
                    item["by"],
                    item["at"],
                ),
            )
            db.execute("DELETE FROM conversions WHERE source_id = ?", (source_id,))
            changed = True
        return changed

    def stored_file(self, source_id: str) -> Path:
        with self._db() as db:
            row = db.execute("SELECT stored FROM sources WHERE id = ?", (source_id,)).fetchone()
        if row is None:
            raise BiStoreError("source_unknown", "找不到這個來源")
        return self._file(str(row["stored"]))

    def markdown_file(self, source_id: str, rev: int) -> Path:
        with self._db() as db:
            row = db.execute(
                "SELECT stored FROM markdown WHERE source_id = ? AND rev = ?", (source_id, rev)
            ).fetchone()
        if row is None:
            raise BiStoreError("markdown_rev_unknown", f"這個來源沒有第 {rev} 版 Markdown")
        return self._file(str(row["stored"]))

    def copy_sources_from(self, other: Staging) -> dict[str, int]:
        """Copy `other`'s sources here with their files, Markdown revisions and
        conversion failures, under the same ids (converting a dataset to a vault,
        `docs/phases/BI_BUILD_FLOW.md` §4). Runs and sessions stay with `other`. A
        source whose file is gone is skipped and counted."""
        if not other.exists:
            return {"copied": 0, "skipped": 0}
        with other._db() as db:
            sources = db.execute("SELECT * FROM sources ORDER BY rowid").fetchall()
            revisions = (
                db.execute("SELECT * FROM markdown ORDER BY source_id, rev").fetchall()
                if _has_table(db, "markdown")
                else []
            )
            failures = (
                db.execute("SELECT * FROM conversions").fetchall()
                if _has_table(db, "conversions")
                else []
            )
        copied, skipped = 0, 0
        with self._db(write=True) as db:
            for row in sources:
                files = [row["stored"]] + [
                    r["stored"] for r in revisions if r["source_id"] == row["id"]
                ]
                if not all((other.dir / str(name)).is_file() for name in files):
                    skipped += 1
                    continue
                for name in files:
                    target = self.dir / str(name)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(other.dir / str(name), target)
                db.execute(
                    f"INSERT INTO sources ({', '.join(row.keys())}) "
                    f"VALUES ({', '.join('?' for _ in row.keys())})",
                    tuple(row),
                )
                for revision in (r for r in revisions if r["source_id"] == row["id"]):
                    db.execute(
                        f"INSERT INTO markdown ({', '.join(revision.keys())}) "
                        f"VALUES ({', '.join('?' for _ in revision.keys())})",
                        tuple(revision),
                    )
                for failure in (f for f in failures if f["source_id"] == row["id"]):
                    db.execute(
                        f"INSERT INTO conversions ({', '.join(failure.keys())}) "
                        f"VALUES ({', '.join('?' for _ in failure.keys())})",
                        tuple(failure),
                    )
                copied += 1
        if copied:
            from capabilities.bi_cards import search_index  # its passages (BI vault V3)

            search_index.sync_quietly(self.store)
        return {"copied": copied, "skipped": skipped}

    def _source_by_digest(self, digest: str) -> dict[str, Any] | None:
        if not self.exists:
            return None
        with self._db() as db:
            row = db.execute("SELECT id FROM sources WHERE sha256 = ?", (digest,)).fetchone()
        return None if row is None else self.source(str(row["id"]))

    @staticmethod
    def _source(row: sqlite3.Row, db: sqlite3.Connection | None = None) -> dict[str, Any]:
        rev, failure = 0, None
        if db is not None and _has_table(db, "markdown"):
            rev = int(
                db.execute(
                    "SELECT COALESCE(MAX(rev), 0) FROM markdown WHERE source_id = ?", (row["id"],)
                ).fetchone()[0]
            )
            found = db.execute(
                "SELECT code, message FROM conversions WHERE source_id = ?", (row["id"],)
            ).fetchone()
            if found is not None and not rev:
                failure = {"code": found["code"], "message": found["message"]}
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
            # BI vault V2: the current Markdown revision (0: not converted
            # yet) and why the last conversion failed, if it did.
            "format": convert.kind(row["name"]),
            "markdown_rev": rev,
            "convert_error": failure,
        }

    def sources(self) -> list[dict[str, Any]]:
        if not self.exists:
            return []
        with self._db() as db:
            rows = db.execute("SELECT * FROM sources ORDER BY at DESC, rowid DESC").fetchall()
            return [self._source(r, db) for r in rows]

    def source(self, source_id: str) -> dict[str, Any] | None:
        if not self.exists:
            return None
        with self._db() as db:
            row = db.execute("SELECT * FROM sources WHERE id = ?", (source_id,)).fetchone()
            return None if row is None else self._source(row, db)

    def stored_paths(self) -> dict[str, str]:
        """Each source's stored file, for reading many without a query each."""
        if not self.exists:
            return {}
        with self._db() as db:
            return {r["id"]: str(r["stored"]) for r in db.execute("SELECT id, stored FROM sources")}

    def read_stored(self, stored: str) -> bytes:
        return self._read(stored)

    def source_bytes(self, source_id: str) -> bytes:
        if not self.exists:
            raise BiStoreError("source_unknown", "找不到這個來源")
        with self._db() as db:
            row = db.execute("SELECT stored FROM sources WHERE id = ?", (source_id,)).fetchone()
        if row is None:
            raise BiStoreError("source_unknown", "找不到這個來源")
        return self._read(str(row["stored"]))

    # -- Markdown revisions (BI vault V2) -----------------------------------

    def _insert_markdown(
        self,
        db: sqlite3.Connection,
        source_id: str,
        rev: int,
        text: str,
        *,
        origin: str,
        note: str,
        converter: str | None,
        actor: str,
    ) -> None:
        stored = f"{MARKDOWN_DIR}/{source_id}/rev-{rev}.md"
        target = self.dir / stored
        target.parent.mkdir(parents=True, exist_ok=True)
        data = text.encode("utf-8")
        temporary = target.with_name(f".{target.name}.{uuid.uuid4().hex[:8]}.tmp")
        temporary.write_bytes(data)
        schema_versions.replace(temporary, target)
        db.execute(
            "INSERT INTO markdown (source_id, rev, origin, note, converter, sha256, chars, lines, "
            "stored, by, at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                source_id,
                rev,
                origin,
                note,
                converter,
                hashlib.sha256(data).hexdigest(),
                len(text),
                len(text.split("\n")) if text else 0,
                stored,
                actor,
                now(),
            ),
        )
        db.execute("DELETE FROM conversions WHERE source_id = ?", (source_id,))

    @staticmethod
    def _record_failure(db: sqlite3.Connection, source_id: str, error: BiStoreError) -> None:
        db.execute(
            "INSERT OR REPLACE INTO conversions (source_id, code, message, at) VALUES (?, ?, ?, ?)",
            (source_id, error.code, error.message, now()),
        )

    def record_conversion_failure(self, source_id: str, error: BiStoreError) -> None:
        with self._db(write=True) as db:
            self._record_failure(db, source_id, error)

    @staticmethod
    def _revision(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "rev": int(row["rev"]),
            "origin": row["origin"],
            "note": row["note"],
            "converter": row["converter"],
            "sha256": row["sha256"],
            "chars": int(row["chars"]),
            "lines": int(row["lines"]),
            "by": row["by"],
            "at": row["at"],
        }

    def markdown_revisions(self, source_id: str) -> list[dict[str, Any]]:
        """Every Markdown revision of a source, newest first (empty: none yet)."""
        if not self.exists:
            return []
        with self._db() as db:
            if not _has_table(db, "markdown"):
                return []
            rows = db.execute(
                "SELECT * FROM markdown WHERE source_id = ? ORDER BY rev DESC", (source_id,)
            ).fetchall()
        return [self._revision(r) for r in rows]

    def markdown_text(self, source_id: str, rev: int) -> str:
        if not self.exists:
            raise BiStoreError("markdown_rev_unknown", "找不到這個 Markdown 版本")
        with self._db() as db:
            row = (
                db.execute(
                    "SELECT stored FROM markdown WHERE source_id = ? AND rev = ?",
                    (source_id, rev),
                ).fetchone()
                if _has_table(db, "markdown")
                else None
            )
        if row is None:
            raise BiStoreError("markdown_rev_unknown", f"這個來源沒有第 {rev} 版 Markdown")
        return self._read(str(row["stored"])).decode("utf-8")

    def add_markdown(
        self,
        source_id: str,
        text: str,
        *,
        origin: str,
        note: str,
        actor: str,
        base_rev: int | None,
        converter: str | None = None,
    ) -> tuple[dict[str, Any], bool]:
        """Save the next revision: (its record, False). The same text as the
        current revision saves nothing: (the current record, True). A
        `base_rev` that is not the current revision is `markdown_stale`."""
        with self._db(write=True) as db:
            db.execute("BEGIN IMMEDIATE")  # the check and the insert see one state
            current = db.execute(
                "SELECT * FROM markdown WHERE source_id = ? ORDER BY rev DESC LIMIT 1",
                (source_id,),
            ).fetchone()
            current_rev = 0 if current is None else int(current["rev"])
            if base_rev is not None and base_rev != current_rev:
                raise BiStoreError(
                    "markdown_stale",
                    f"這份 Markdown 在你開啟後已存成第 {current_rev} 版，請重新載入後再修改",
                    current_rev=current_rev,
                )
            digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
            if current is not None and current["sha256"] == digest:
                return self._revision(current), True
            self._insert_markdown(
                db,
                source_id,
                current_rev + 1,
                text,
                origin=origin,
                note=note,
                converter=converter,
                actor=actor,
            )
            row = db.execute(
                "SELECT * FROM markdown WHERE source_id = ? AND rev = ?",
                (source_id, current_rev + 1),
            ).fetchone()
        repo = self._vault_repo()
        if repo is not None:
            try:
                with repo.lock:
                    vault_sources.stage_revision(repo, self, source_id, current_rev + 1)
            except RepoError as failure:
                raise BiStoreError(failure.code, failure.message) from None
        return self._revision(row), False

    def markdown_sources(self) -> list[tuple[str, int]]:
        """(source id, current revision) of every source that has Markdown."""
        if not self.exists:
            return []
        with self._db() as db:
            if not _has_table(db, "markdown"):
                return []
            rows = db.execute(
                "SELECT source_id, MAX(rev) AS rev FROM markdown GROUP BY source_id"
            ).fetchall()
        return [(str(r["source_id"]), int(r["rev"])) for r in rows]

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
        markdown_rev: int | None = None,
    ) -> str:
        if kind not in RUN_KINDS:
            raise BiStoreError("run_kind_invalid", "kind 只能是 trial 或 ingest")
        run_id = uuid.uuid4().hex[:12]
        with self._db(write=True) as db:
            db.execute(
                "INSERT INTO runs (id, kind, status, method_ref, schema_ref, model, source_ids, "
                "by, at, markdown_rev) VALUES (?, ?, 'queued', ?, ?, ?, ?, ?, ?, ?)",
                (
                    run_id,
                    kind,
                    method_ref,
                    schema_ref,
                    model,
                    _dump(source_ids),
                    actor,
                    now(),
                    markdown_rev,
                ),
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
            # The Markdown revision the run read (BI vault V2; None before V2).
            "markdown_rev": row["markdown_rev"] if "markdown_rev" in row.keys() else None,
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

    # -- AI design sessions (BI ingest phases 5 and 6) ---------------------

    def create_session(
        self, *, kind: str, target_ref: str, actor: str, new: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        session_id = uuid.uuid4().hex[:12]
        at = now()
        body: dict[str, Any] = {"turns": [], "goal": "", "source_ids": []}
        if new is not None:
            # What the session creates once the person applies a draft (F16).
            body["new"] = new
        with self._db(write=True) as db:
            db.execute(
                "INSERT INTO sessions (id, kind, target_ref, body, model, by, at, updated) "
                "VALUES (?, ?, ?, ?, NULL, ?, ?, ?)",
                (session_id, kind, target_ref, _dump(body), actor, at, at),
            )
        found = self.session(session_id)
        assert found is not None
        return found

    def put_session(self, session: dict[str, Any]) -> None:
        body = {k: session[k] for k in ("turns", "goal", "source_ids", "new") if k in session}
        with self._db(write=True) as db:
            db.execute(
                "UPDATE sessions SET body = ?, model = ?, updated = ? WHERE id = ?",
                (_dump(body), session.get("model"), now(), session["id"]),
            )

    @staticmethod
    def _session(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "kind": row["kind"],
            "target_ref": row["target_ref"],
            "model": row["model"],
            "by": row["by"],
            "at": row["at"],
            "updated": row["updated"],
            **json.loads(row["body"]),
        }

    def session(self, session_id: str) -> dict[str, Any] | None:
        if not self.exists:
            return None
        with self._db() as db:
            if not _has_table(db, "sessions"):
                return None
            row = db.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
        return None if row is None else self._session(row)

    def sessions(self, target_ref: str | None = None) -> list[dict[str, Any]]:
        """Sessions newest first, optionally of one target."""
        if not self.exists:
            return []
        with self._db() as db:
            if not _has_table(db, "sessions"):
                return []
            rows = db.execute(
                "SELECT * FROM sessions WHERE ? IS NULL OR target_ref = ? "
                "ORDER BY updated DESC, rowid DESC",
                (target_ref, target_ref),
            ).fetchall()
        return [self._session(r) for r in rows]


def _has_table(db: sqlite3.Connection, name: str) -> bool:
    """A staging store written before phase 3 lacks the newer tables until
    its next write; reading it must not fail."""
    found = db.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (name,)
    ).fetchone()
    return found is not None
