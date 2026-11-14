"""Read-only BI dataset overview from an explicit `bi/` folder (stdlib only).

Preparation for a BI overview feature plugin. It is not the BI service: it
never imports BI code, never rebuilds a vault projection, never syncs the
search index, never migrates a schema and never writes, creates or deletes a
file or folder. It reports what each dataset's local database says now, with
an honest status, and nothing about card content.

API
---
`read_overview(bi_root, *, limit=MAX_ROWS, timeout_seconds=1.0, deadline_seconds=5.0)
-> dict`

`bi_root` is the absolute `bi/` folder the caller chose; the reader derives no
workspace and treats no path as proof of ownership. Result::

    {"status": "ready" | "missing" | "unsupported",
     "reason": None | "redirected",          # only when status is unsupported
     "datasets": [entry, ...],               # at most `limit` (<= MAX_ROWS)
     "total": int,                           # every dataset found
     "truncated": bool,                      # total > len(datasets)
     "invalid_registrations": int}           # vault records not used

An absent `bi_root` gives `{"status": "missing", "datasets": [], "total": 0,
"truncated": False}`. Each entry::

    {"name", "kind": "local" | "vault" | "subscribed",
     "status": "ready" | "missing" | "outdated" | "corrupt" | "unsupported" | "busy",
     "reason": None | <code>, "cards": int | None, "updated": str | None,
     "schema": str | None, "dashboard": bool | None,
     "subscribed": bool, "read_only": bool, "projection": bool,
     "version": str}                         # subscribed copies only

For a ready local dataset, `name`, `cards`, `updated`, `schema`, `dashboard`,
`subscribed` and `read_only` equal `capabilities.bi_cards.service.dataset_list`.
Anything not ready carries no counts. Reasons: `name_invalid`, `redirected`,
`database_absent`, `projection_absent`, `write_in_progress`, `locked`,
`not_sqlite`, `journal_wal`, `tables_unknown`, `schema_unknown`,
`projection_version`, `projection_newer`, `version_invalid`, `unreadable`,
`deadline_exceeded`.

Read policy
-----------
- A folder or database that is a symbolic link or junction is not followed.
- A vault's `bi.sqlite` is a projection of its units, not the source of truth:
  older than `PROJECTION_VERSION` is `outdated`, never rebuilt here. The
  registry's paths are neither used nor shown; only a plain id names the local
  projection under `bi/vaults/<id>/`.
- A database with a `-journal`, `-wal` or `-shm` file beside it is `busy`: a
  write is in flight or a crash left recovery to do, which a reader may not do,
  so stale or half-written data is never reported as ready.
- The 100-byte header is checked first: not SQLite is `corrupt`; WAL mode
  (which BI never uses, and whose readers create `-shm`) is `unsupported`.
- Otherwise the file is opened `mode=ro` with `query_only`, and every count is
  read in one read transaction, so the numbers come from one consistent state.
  A writer holding the lock past `timeout_seconds` makes the dataset `busy`;
  so does SQLite refusing a read-only open (`attempt to write a readonly
  database`: recovery a reader may not do), never `corrupt`.
- One `deadline_seconds` budget (monotonic) is checked between datasets: each
  database waits at most what is left, and rows not reached in time are
  `busy` with `deadline_exceeded`, never zero; `total`/`truncated` stay exact.
  This bounds lock waits, not directory enumeration or SQLite query execution;
  the future worker request timeout remains the outer execution bound.
- A zero-length `-journal` beside a database is still refused as
  `write_in_progress` (conservative: it may be a writer between steps).
- An unknown table layout or schema reference is `unsupported`, not guessed.
"""

from __future__ import annotations

import os
import re
import sqlite3
import time
from pathlib import Path
from typing import Any

MAX_ROWS = 200
#: `capabilities.bi_cards.card_model.MODEL_VERSION`: a vault projection's `user_version`.
PROJECTION_VERSION = 14
#: `capabilities.bi_cards.store.LEGACY_SCHEMA`: the binding of a dataset with no `meta` schema.
LEGACY_SCHEMA = "bi.schema/v1.1@1.1.0"
#: `capabilities.bi_cards.schema.BI_PREFIX`: schemas the dashboard understands.
BI_PREFIX = "bi.schema/"

DB_FILE = "bi.sqlite"
SIDECARS = ("-journal", "-wal", "-shm")
RESERVED = frozenset({"schemas", "subscribed", "schema-drafts", "benchmarks", "vaults"})
VAULT_PREFIX = "vault-"
MAX_SCAN = 10_000
_DATASET = re.compile(r"^[A-Za-z0-9_-]{1,40}$")
_VAULT_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
_SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_VERSION = re.compile(r"^\d+\.\d+\.\d+$")
_SCHEMA = re.compile(r"^[^@\s]{1,120}@\d+\.\d+\.\d+$")
_MAGIC = b"SQLite format 3\x00"
#: The clock the overall deadline uses (tests replace it).
_clock = time.monotonic


def _linked(path: Path) -> bool:
    junction = getattr(path, "is_junction", None)
    return path.is_symlink() or (junction is not None and bool(junction()))


def _entries(folder: Path) -> list[Path]:
    found: list[Path] = []
    try:
        with os.scandir(folder) as scan:
            for entry in scan:
                found.append(Path(entry.path))
                if len(found) >= MAX_SCAN:
                    break
    except OSError:
        return []
    return sorted(found, key=lambda p: p.name)


def _read_json(path: Path) -> Any:
    import json

    try:
        if _linked(path) or not path.is_file():
            return None
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


class _Candidate:
    def __init__(
        self,
        name: str,
        kind: str,
        folders: tuple[Path, ...],
        database: Path,
        *,
        version: str | None = None,
        schema: str | None = None,
        problem: str | None = None,
    ) -> None:
        self.name = name
        self.kind = kind
        self.folders = folders
        self.database = database
        self.version = version
        self.schema = schema
        self.problem = problem


def _local(bi_root: Path) -> list[_Candidate]:
    found: list[_Candidate] = []
    for path in _entries(bi_root):
        if path.name.lower() in RESERVED:
            continue
        if _linked(path):
            found.append(_Candidate(path.name, "local", (path,), path / DB_FILE))
            continue
        database = path / DB_FILE
        if path.is_dir() and (_linked(database) or database.is_file()):
            found.append(_Candidate(path.name, "local", (path,), database))
    return found


def _vaults(bi_root: Path) -> tuple[list[_Candidate], int]:
    folder = bi_root / "vaults"
    if _linked(folder):
        return [], 0
    record = _read_json(folder / "registry.json")
    items = record.get("vaults") if isinstance(record, dict) else None
    if not isinstance(items, list):
        return [], 0
    found: list[_Candidate] = []
    seen: set[str] = set()
    invalid = 0
    for item in items[:MAX_SCAN]:
        vault_id = item.get("id") if isinstance(item, dict) else None
        if not isinstance(vault_id, str) or not _VAULT_ID.match(vault_id) or vault_id in seen:
            invalid += 1
            continue
        seen.add(vault_id)
        home = folder / vault_id
        found.append(_Candidate(VAULT_PREFIX + vault_id, "vault", (folder, home), home / DB_FILE))
    return found, invalid


def _subscribed(bi_root: Path) -> list[_Candidate]:
    folder = bi_root / "subscribed"
    if _linked(folder) or not folder.is_dir():
        return []
    found: list[_Candidate] = []
    for root in _entries(folder):
        namespace, separator, name = root.name.partition("__")
        if not separator or not _SLUG.match(namespace) or not _SLUG.match(name):
            continue
        dataset = f"{namespace}/{name}"
        if _linked(root):
            found.append(_Candidate(dataset, "subscribed", (folder, root), root / DB_FILE))
            continue
        record = _read_json(root / "subscription.json")
        if not isinstance(record, dict) or not isinstance(record.get("version"), str):
            continue
        version = record["version"]
        raw = record.get("schema")
        # Like the subscription entry: an empty schema falls back to the database's.
        schema = raw if isinstance(raw, str) and raw else None
        if not _VERSION.match(version):
            found.append(
                _Candidate(
                    dataset,
                    "subscribed",
                    (folder, root),
                    root / "none" / DB_FILE,
                    version=version,
                    problem="version_invalid",
                )
            )
            continue
        found.append(
            _Candidate(
                dataset,
                "subscribed",
                (folder, root, root / version),
                root / version / DB_FILE,
                version=version,
                schema=schema,
            )
        )
    return found


def _entry(candidate: _Candidate, status: str, reason: str | None) -> dict[str, Any]:
    subscribed = candidate.kind == "subscribed"
    entry: dict[str, Any] = {
        "name": candidate.name,
        "kind": candidate.kind,
        "status": status,
        "reason": reason,
        "cards": None,
        "updated": None,
        "schema": None,
        "dashboard": None,
        "subscribed": subscribed,
        "read_only": subscribed,
        "projection": candidate.kind == "vault",
    }
    if subscribed:
        entry["version"] = candidate.version
    return entry


def _header_problem(database: Path) -> str | None:
    try:
        with database.open("rb") as handle:
            header = handle.read(100)
    except OSError:
        return "unreadable"
    if len(header) < 100 or not header.startswith(_MAGIC):
        return "not_sqlite"
    if header[18] == 2 or header[19] == 2:
        return "journal_wal"
    return None


def _status_of(reason: str) -> str:
    return {
        "name_invalid": "unsupported",
        "redirected": "unsupported",
        "database_absent": "missing",
        "projection_absent": "missing",
        "write_in_progress": "busy",
        "locked": "busy",
        "not_sqlite": "corrupt",
        "unreadable": "corrupt",
        "journal_wal": "unsupported",
        "tables_unknown": "unsupported",
        "schema_unknown": "unsupported",
        "projection_version": "outdated",
        "projection_newer": "unsupported",
        "version_invalid": "unsupported",
        "deadline_exceeded": "busy",
    }[reason]


def _read(candidate: _Candidate, timeout_seconds: float) -> dict[str, Any]:
    def refused(reason: str) -> dict[str, Any]:
        return _entry(candidate, _status_of(reason), reason)

    if candidate.problem is not None:
        return refused(candidate.problem)
    if any(_linked(folder) for folder in candidate.folders) or _linked(candidate.database):
        return refused("redirected")
    if candidate.kind == "local" and not _DATASET.match(candidate.name):
        return refused("name_invalid")
    if not candidate.database.is_file():
        return refused("projection_absent" if candidate.kind == "vault" else "database_absent")
    if any(candidate.database.with_name(DB_FILE + suffix).exists() for suffix in SIDECARS):
        return refused("write_in_progress")
    problem = _header_problem(candidate.database)
    if problem is not None:
        return refused(problem)
    try:
        values = _query(candidate, timeout_seconds)
    except sqlite3.DatabaseError as error:
        text = str(error).lower()
        if "locked" in text or "busy" in text or "readonly" in text:
            return refused("locked")
        return refused("not_sqlite" if "not a database" in text else "unreadable")
    if isinstance(values, str):
        return refused(values)
    cards, updated, schema = values
    entry = _entry(candidate, "ready", None)
    entry.update(
        cards=cards, updated=updated, schema=schema, dashboard=schema.startswith(BI_PREFIX)
    )
    return entry


def _query(candidate: _Candidate, timeout_seconds: float) -> tuple[int, str | None, str] | str:
    uri = candidate.database.resolve().as_uri() + "?mode=ro"
    connection = sqlite3.connect(uri, uri=True, timeout=timeout_seconds, isolation_level=None)
    try:
        connection.execute("PRAGMA query_only = ON")
        connection.execute("BEGIN")
        try:
            tables = {
                str(row[0])
                for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
            }
            if "cards" not in tables:
                return "tables_unknown"
            columns = {str(row[1]) for row in connection.execute("PRAGMA table_info(cards)")}
            if "updated" not in columns:
                return "tables_unknown"
            if candidate.kind == "vault":
                version = int(connection.execute("PRAGMA user_version").fetchone()[0])
                if version < PROJECTION_VERSION:
                    return "projection_version"
                if version > PROJECTION_VERSION:
                    return "projection_newer"
            schema = candidate.schema
            if schema is None:
                schema = LEGACY_SCHEMA
                if "meta" in tables:
                    row = connection.execute(
                        "SELECT value FROM meta WHERE key = 'schema'"
                    ).fetchone()
                    if row is not None:
                        schema = str(row[0])
            if not _SCHEMA.match(schema):
                return "schema_unknown"
            count, latest = connection.execute(
                "SELECT COUNT(*), MAX(updated) FROM cards"
            ).fetchone()
        finally:
            connection.execute("COMMIT")
    finally:
        connection.close()
    return int(count), (str(latest) if latest else None), schema


def read_overview(
    bi_root: Path,
    *,
    limit: int = MAX_ROWS,
    timeout_seconds: float = 1.0,
    deadline_seconds: float = 5.0,
) -> dict[str, Any]:
    """The overview of every dataset under `bi_root` (see the module docstring)."""
    root = Path(bi_root)
    if not root.is_absolute():
        raise ValueError("bi_root must be an absolute folder")
    if not deadline_seconds > 0 or not timeout_seconds > 0:
        raise ValueError("timeout and deadline are positive seconds")
    if not 1 <= limit <= MAX_ROWS:
        raise ValueError(f"limit is between 1 and {MAX_ROWS}")
    if _linked(root):
        return {
            "status": "unsupported",
            "reason": "redirected",
            "datasets": [],
            "total": 0,
            "truncated": False,
            "invalid_registrations": 0,
        }
    if not root.is_dir():
        return {"status": "missing", "datasets": [], "total": 0, "truncated": False}
    vaults, invalid = _vaults(root)
    candidates = sorted([*_local(root), *vaults], key=lambda c: c.name) + _subscribed(root)
    started = _clock()
    shown: list[dict[str, Any]] = []
    for candidate in candidates[:limit]:
        remaining = deadline_seconds - (_clock() - started)
        if remaining <= 0:
            shown.append(_entry(candidate, "busy", "deadline_exceeded"))
            continue
        shown.append(_read(candidate, min(timeout_seconds, remaining)))
    return {
        "status": "ready",
        "reason": None,
        "datasets": shown,
        "total": len(candidates),
        "truncated": len(candidates) > len(shown),
        "invalid_registrations": invalid,
    }
