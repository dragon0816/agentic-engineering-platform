"""Moving one actor's business-cards `cards.db` into the Memory Service
(accumulated memory M1; docs/phases/ACCUMULATED_MEMORY.md "M1 as built").

Run once, on the first open of the store after the upgrade:

1. a byte-for-byte copy of `cards.db` is written beside it first
   (`cards.db.bak-<UTC stamp>`), taken under SQLite's shared read lock and
   checked (same SHA-256, integrity check, same row counts), unless an
   identical copy is already there;
2. in one write transaction on `memory.sqlite`, every row of the eight
   tables (people, field_sources, observations, reporting_lines, history,
   undone, proposals, candidates) is copied into the `contacts/org` space,
   ids kept, so that every reference between them (observation ids in
   provenance and proposals, line ids and change ids in history) still holds;
3. every copied row is read back and compared with the original; any
   difference, or any error, rolls the whole transaction back: no partial
   state, and `cards.db` is never written (it is opened read-only);
4. a marker in `memory.sqlite` records the source, the backup, the counts and
   the source's size, time and SHA-256, so later opens skip the migration.

After that `cards.db` is never written again. If it changes later (the
previous version of AEP was run again and stored something), the store
refuses with `memory_legacy_changed` instead of silently ignoring those
changes; see the doc for how to migrate again.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
from collections.abc import Sequence
from contextlib import closing
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from capabilities.business_cards.space import CANDIDATES, CONTACTS_ORG, LINES, PEOPLE
from common.memory import MergeRules, origin_for
from memory.service import MemoryService

MARKER = f"migrated:{CONTACTS_ORG}"
#: Every table of the business-cards store, in the order they are copied.
LEGACY_TABLES = (
    "people",
    "field_sources",
    "observations",
    "reporting_lines",
    "history",
    "undone",
    "proposals",
    "candidates",
)
BACKUP_INFIX = ".bak-"
_REASON = "migrated from cards.db"

_PEOPLE_COLUMNS = (
    "person_id",
    "name",
    "romanised_name",
    "company",
    "company_tax_id",
    "business_group",
    "division",
    "department",
    "title",
    "honorific",
    "phone",
    "ext",
    "mobile",
    "fax",
    "email",
    "email_key",
    "address",
    "website",
    "notes",
    "status",
    "left_at",
    "status_set_by",
    "status_reason",
    "created_at",
    "updated_at",
)
_LINE_COLUMNS = (
    "line_id",
    "person_id",
    "manager_id",
    "evidence_kind",
    "evidence_ref",
    "confidence",
    "inferred",
    "created_at",
    "created_by",
    "removed_at",
    "removed_by",
    "removed_reason",
)
_CANDIDATE_COLUMNS = (
    "session_key",
    "candidate_id",
    "fields_json",
    "uncertain_json",
    "message_id",
    "message_date",
    "created_at",
    "expires_at",
    "stored_person_id",
)
#: Defaults of columns an older `cards.db` may not have.
_DEFAULTS: dict[str, Any] = {"status": "active", "uncertain_json": "[]", "extra_json": "{}"}


class MigrationError(Exception):
    """The migration did not happen; `cards.db` is as it was."""

    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}" if detail else code)


@dataclass
class MigrationReport:
    source: str
    backup: str
    rows: dict[str, int] = field(default_factory=dict)
    at: str = ""


def _ro(path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=10)
    con.row_factory = sqlite3.Row
    return con


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _tables(con: sqlite3.Connection) -> dict[str, set[str]]:
    """Each table of a database with its columns."""
    names = [row[0] for row in con.execute("SELECT name FROM sqlite_master WHERE type = 'table'")]
    return {name: {row[1] for row in con.execute(f"PRAGMA table_info({name})")} for name in names}


def _counts(con: sqlite3.Connection) -> dict[str, int]:
    have = _tables(con)
    return {
        name: int(con.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0])
        for name in LEGACY_TABLES
        if name in have
    }


def backup(legacy: Path) -> Path:
    """A byte-for-byte copy of `legacy` beside it (`cards.db.bak-<stamp>`),
    taken while a read lock keeps writers out, then checked: the same
    SHA-256, SQLite's integrity check, the same row counts. An identical copy
    already there is reused. Raises `MigrationError` when the copy cannot be
    made or does not match (no partial copy is left); the original is only
    read."""
    partial: Path | None = None
    try:
        with closing(_ro(legacy)) as source:
            # A read transaction holds SQLite's shared lock: no writer can
            # commit to the file while it is hashed and copied.
            source.execute("BEGIN")
            expected = _counts(source)
            wanted = _sha256(legacy)
            for existing in sorted(legacy.parent.glob(legacy.name + BACKUP_INFIX + "*")):
                if existing.is_file() and not existing.name.endswith(".partial"):
                    if _sha256(existing) == wanted:
                        return existing
            stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
            target = legacy.with_name(f"{legacy.name}{BACKUP_INFIX}{stamp}")
            number = 1
            while target.exists():
                target = legacy.with_name(f"{legacy.name}{BACKUP_INFIX}{stamp}-{number}")
                number += 1
            partial = target.with_name(target.name + ".partial")
            shutil.copyfile(legacy, partial)
            source.rollback()
        with closing(_ro(partial)) as copy:
            verdict = copy.execute("PRAGMA integrity_check").fetchone()[0]
            got = _counts(copy)
        if _sha256(partial) != wanted or verdict != "ok" or got != expected:
            raise MigrationError("memory_backup_failed", "the copy does not match cards.db")
        os.replace(partial, target)
        return target
    except (OSError, sqlite3.Error, MigrationError) as error:
        if partial is not None:
            partial.unlink(missing_ok=True)
        if isinstance(error, MigrationError):
            raise
        raise MigrationError("memory_backup_failed", type(error).__name__) from error


def _marker(memory: MemoryService) -> dict[str, Any] | None:
    stored = memory.get_meta(MARKER)
    return None if stored is None else dict(json.loads(stored))


def check_unchanged(memory: MemoryService, legacy: Path) -> bool:
    """True when `legacy` was migrated and is as it was then; False when it
    was never migrated. `memory_legacy_changed` when it changed since."""
    marker = _marker(memory)
    if marker is None:
        return False
    if not legacy.is_file():
        return True
    stat = legacy.stat()
    if stat.st_size == marker.get("size") and stat.st_mtime_ns == marker.get("mtime_ns"):
        return True
    if _sha256(legacy) == marker.get("sha256"):
        return True
    raise MigrationError("memory_legacy_changed", str(legacy))


def migrate(
    memory: MemoryService, legacy: Path, *, rules: MergeRules, manager: str
) -> MigrationReport | None:
    """Copy `legacy` into the `contacts/org` space once (see the module
    doc); None when there is nothing to do. The space's own tables must
    exist. Raises `MigrationError`; then nothing was written."""
    if not legacy.is_file() or check_unchanged(memory, legacy):
        return None
    try:
        with memory.connect(immediate=True) as con:
            # Another process may have finished it while this one waited.
            if con.execute("SELECT 1 FROM meta WHERE key = ?", (MARKER,)).fetchone():
                return None
            if (
                con.execute(f"SELECT 1 FROM {PEOPLE} LIMIT 1").fetchone()
                or con.execute(
                    "SELECT 1 FROM observations WHERE space = ? LIMIT 1", (CONTACTS_ORG,)
                ).fetchone()
            ):
                raise MigrationError("memory_migration_target_not_empty")
            stat = legacy.stat()
            digest = _sha256(legacy)
            saved = backup(legacy)
            with closing(_ro(legacy)) as source:
                have = _tables(source)
                rows = _copy(con, source, have, rules=rules, manager=manager)
                _verify(con, source, have)
            report = MigrationReport(
                source=str(legacy),
                backup=str(saved),
                rows=rows,
                at=datetime.now(UTC).isoformat(timespec="seconds"),
            )
            con.execute(
                "INSERT INTO meta (key, value) VALUES (?, ?)",
                (
                    MARKER,
                    json.dumps(
                        {
                            "source": report.source,
                            "backup": report.backup,
                            "rows": rows,
                            "at": report.at,
                            "size": stat.st_size,
                            "mtime_ns": stat.st_mtime_ns,
                            "sha256": digest,
                        },
                        ensure_ascii=False,
                    ),
                ),
            )
            return report
    except MigrationError:
        raise
    except (OSError, sqlite3.Error, ValueError, KeyError) as error:
        raise MigrationError("memory_migration_failed", type(error).__name__) from error


def _select(
    source: sqlite3.Connection,
    have: dict[str, set[str]],
    table: str,
    columns: Sequence[str],
    order: str,
) -> list[tuple[Any, ...]]:
    """Every row of a source table as `columns`, a column the table lacks
    (an older store) as its default; no table, no rows."""
    if table not in have:
        return []
    parts = [name if name in have[table] else f"? AS {name}" for name in columns]
    defaults = [_DEFAULTS.get(name, "") for name in columns if name not in have[table]]
    query = f"SELECT {', '.join(parts)} FROM {table} ORDER BY {order}"
    return [tuple(row) for row in source.execute(query, defaults)]


_OBSERVATION = (
    "observation_id",
    "person_id",
    "source",
    "source_date",
    "source_ref",
    "fields_json",
    "uncertain_json",
    "recorded_at",
    "recorded_by",
)
_FIELD_SOURCE = ("person_id", "field", "source", "source_date", "observation_id")
_HISTORY = (
    "history_id",
    "change_id",
    "at",
    "actor",
    "person_id",
    "kind",
    "field",
    "old",
    "new",
    "reason",
    "source",
    "extra_json",
)
_UNDONE = ("change_id", "undone_by")
_PROPOSAL = (
    "proposal_id",
    "person_id",
    "field",
    "current",
    "proposed",
    "source",
    "observation_id",
    "created_at",
    "state",
)


def _copy(
    con: sqlite3.Connection,
    source: sqlite3.Connection,
    have: dict[str, set[str]],
    *,
    rules: MergeRules,
    manager: str,
) -> dict[str, int]:
    space = CONTACTS_ORG
    counts: dict[str, int] = {}
    people = _select(source, have, "people", _PEOPLE_COLUMNS, "person_id")
    marks = ",".join("?" * len(_PEOPLE_COLUMNS))
    con.executemany(f"INSERT INTO {PEOPLE} ({', '.join(_PEOPLE_COLUMNS)}) VALUES ({marks})", people)
    counts["people"] = len(people)

    observations = _select(source, have, "observations", _OBSERVATION, "observation_id")
    for item in observations:
        kind = str(item[2])
        con.execute(
            "INSERT INTO observations (observation_id, space, entity_id, claim, source_kind, "
            "trust, source_date, source_ref, fields_json, uncertain_json, recorded_at, "
            "recorded_by, contributor) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                item[0],
                space,
                item[1],
                "fields",
                kind,
                rules.trust_of(kind) or "document",
                *item[3:],
                manager,
            ),
        )
    counts["observations"] = len(observations)

    # Who set each current value and when, from the newest history row that
    # put it there (a field change, a confirmation, or the creation).
    history = _select(source, have, "history", _HISTORY, "history_id")
    setter: dict[tuple[str, str], tuple[str, str]] = {}
    for item in history:
        person, kind, name, actor, at = item[4], item[5], item[6], item[3], item[2]
        if kind in ("field", "confirm"):
            setter[(person, name)] = (actor, at)
        elif kind == "create":
            setter.setdefault((person, "*"), (actor, at))
    sources = _select(source, have, "field_sources", _FIELD_SOURCE, "person_id, field")
    for item in sources:
        person, name, kind = item[0], item[1], str(item[2])
        actor, at = setter.get((person, name)) or setter.get((person, "*")) or ("", "")
        con.execute(
            "INSERT INTO field_sources (space, entity_id, field, source_kind, source_date, "
            "observation_id, origin, set_by, set_at, reason) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                space,
                person,
                name,
                kind,
                item[3],
                item[4],
                origin_for(rules.trust_of(kind), kind),
                actor,
                at,
                _REASON,
            ),
        )
    counts["field_sources"] = len(sources)

    lines = _select(source, have, "reporting_lines", _LINE_COLUMNS, "line_id")
    marks = ",".join("?" * len(_LINE_COLUMNS))
    con.executemany(f"INSERT INTO {LINES} ({', '.join(_LINE_COLUMNS)}) VALUES ({marks})", lines)
    counts["reporting_lines"] = len(lines)

    con.executemany(
        "INSERT INTO history (history_id, space, change_id, at, actor, entity_id, kind, field, "
        "old, new, reason, source, extra_json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        [(item[0], space, *item[1:]) for item in history],
    )
    counts["history"] = len(history)

    undone = _select(source, have, "undone", _UNDONE, "change_id")
    con.executemany(
        "INSERT INTO undone (change_id, space, undone_by) VALUES (?,?,?)",
        [(item[0], space, item[1]) for item in undone],
    )
    counts["undone"] = len(undone)

    proposals = _select(source, have, "proposals", _PROPOSAL, "proposal_id")
    con.executemany(
        "INSERT INTO proposals (proposal_id, space, entity_id, field, current, proposed, "
        "source_kind, observation_id, created_at, state) VALUES (?,?,?,?,?,?,?,?,?,?)",
        [(item[0], space, *item[1:]) for item in proposals],
    )
    counts["proposals"] = len(proposals)

    candidates = _select(
        source, have, "candidates", _CANDIDATE_COLUMNS, "session_key, candidate_id"
    )
    marks = ",".join("?" * len(_CANDIDATE_COLUMNS))
    con.executemany(
        f"INSERT INTO {CANDIDATES} ({', '.join(_CANDIDATE_COLUMNS)}) VALUES ({marks})", candidates
    )
    counts["candidates"] = len(candidates)
    return counts


def _verify(con: sqlite3.Connection, source: sqlite3.Connection, have: dict[str, set[str]]) -> None:
    """Every copied row, read back in the source's shape, equals the
    original; raises `memory_migration_mismatch` otherwise."""
    space = (CONTACTS_ORG,)
    pairs: list[tuple[str, list[tuple[Any, ...]], list[tuple[Any, ...]]]] = [
        (
            "people",
            _select(source, have, "people", _PEOPLE_COLUMNS, "person_id"),
            [
                tuple(row)
                for row in con.execute(
                    f"SELECT {', '.join(_PEOPLE_COLUMNS)} FROM {PEOPLE} ORDER BY person_id"
                )
            ],
        ),
        (
            "observations",
            _select(source, have, "observations", _OBSERVATION, "observation_id"),
            [
                tuple(row)
                for row in con.execute(
                    "SELECT observation_id, entity_id, source_kind, source_date, source_ref, "
                    "fields_json, uncertain_json, recorded_at, recorded_by FROM observations "
                    "WHERE space = ? ORDER BY observation_id",
                    space,
                )
            ],
        ),
        (
            "field_sources",
            _select(source, have, "field_sources", _FIELD_SOURCE, "person_id, field"),
            [
                tuple(row)
                for row in con.execute(
                    "SELECT entity_id, field, source_kind, source_date, observation_id "
                    "FROM field_sources WHERE space = ? ORDER BY entity_id, field",
                    space,
                )
            ],
        ),
        (
            "reporting_lines",
            _select(source, have, "reporting_lines", _LINE_COLUMNS, "line_id"),
            [
                tuple(row)
                for row in con.execute(
                    f"SELECT {', '.join(_LINE_COLUMNS)} FROM {LINES} ORDER BY line_id"
                )
            ],
        ),
        (
            "history",
            _select(source, have, "history", _HISTORY, "history_id"),
            [
                tuple(row)
                for row in con.execute(
                    "SELECT history_id, change_id, at, actor, entity_id, kind, field, old, new, "
                    "reason, source, extra_json FROM history WHERE space = ? ORDER BY history_id",
                    space,
                )
            ],
        ),
        (
            "undone",
            _select(source, have, "undone", _UNDONE, "change_id"),
            [
                tuple(row)
                for row in con.execute(
                    "SELECT change_id, undone_by FROM undone WHERE space = ? ORDER BY change_id",
                    space,
                )
            ],
        ),
        (
            "proposals",
            _select(source, have, "proposals", _PROPOSAL, "proposal_id"),
            [
                tuple(row)
                for row in con.execute(
                    "SELECT proposal_id, entity_id, field, current, proposed, source_kind, "
                    "observation_id, created_at, state FROM proposals WHERE space = ? "
                    "ORDER BY proposal_id",
                    space,
                )
            ],
        ),
        (
            "candidates",
            _select(source, have, "candidates", _CANDIDATE_COLUMNS, "session_key, candidate_id"),
            [
                tuple(row)
                for row in con.execute(
                    f"SELECT {', '.join(_CANDIDATE_COLUMNS)} FROM {CANDIDATES} "
                    "ORDER BY session_key, candidate_id"
                )
            ],
        ),
    ]
    for table, original, copied in pairs:
        if original != copied:
            raise MigrationError("memory_migration_mismatch", table)
