"""The person's contact store: one SQLite file per actor on this Host.

Every scan or signature sighting is an observation that is never rewritten.
`people` holds the current view, with field-level provenance in
`field_sources`: a value the person set (`user`) is never replaced by an
automatic source, which leaves a proposal instead; an automatic value is
replaced only by evidence that is not older. Every change is a `history` row
in a change group, and `undo` replays a group backwards as a new change.
Nothing here reaches the network.
"""

from __future__ import annotations

import hashlib
import json
import re
import secrets
import sqlite3
from collections.abc import Iterator, Mapping, Sequence
from contextlib import closing, contextmanager
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from capabilities.business_cards import names, reading
from capabilities.business_cards.contracts import (
    FIELD_LABELS,
    FIELDS,
    AddResult,
    FieldChange,
    FieldName,
    HistoryItem,
    HistoryResult,
    ImportResult,
    KeptField,
    ObservationView,
    PersonRef,
    PersonView,
    ProposalView,
    Source,
    Status,
)

STORE_FOLDER = "business-cards"
DB_FILE = "cards.db"
#: Fields that say where a person sits; a change there leads the reply.
ORG_FIELDS: tuple[FieldName, ...] = (
    "company",
    "business_group",
    "division",
    "department",
    "title",
)
CONTACT_FIELDS: tuple[FieldName, ...] = ("phone", "ext", "mobile", "fax", "email")
_LABELS = FIELD_LABELS

_SCHEMA = """
CREATE TABLE IF NOT EXISTS people (
    person_id TEXT PRIMARY KEY,
    name TEXT NOT NULL DEFAULT '',
    romanised_name TEXT NOT NULL DEFAULT '',
    company TEXT NOT NULL DEFAULT '',
    company_tax_id TEXT NOT NULL DEFAULT '',
    business_group TEXT NOT NULL DEFAULT '',
    division TEXT NOT NULL DEFAULT '',
    department TEXT NOT NULL DEFAULT '',
    title TEXT NOT NULL DEFAULT '',
    honorific TEXT NOT NULL DEFAULT '',
    phone TEXT NOT NULL DEFAULT '',
    ext TEXT NOT NULL DEFAULT '',
    mobile TEXT NOT NULL DEFAULT '',
    fax TEXT NOT NULL DEFAULT '',
    email TEXT NOT NULL DEFAULT '',
    email_key TEXT NOT NULL DEFAULT '',
    address TEXT NOT NULL DEFAULT '',
    website TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'active',
    left_at TEXT NOT NULL DEFAULT '',
    status_set_by TEXT NOT NULL DEFAULT '',
    status_reason TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS people_email ON people(email_key);
CREATE TABLE IF NOT EXISTS field_sources (
    person_id TEXT NOT NULL,
    field TEXT NOT NULL,
    source TEXT NOT NULL,
    source_date TEXT NOT NULL,
    observation_id INTEGER,
    PRIMARY KEY (person_id, field)
);
CREATE TABLE IF NOT EXISTS observations (
    observation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id TEXT,
    source TEXT NOT NULL,
    source_date TEXT NOT NULL,
    source_ref TEXT NOT NULL DEFAULT '',
    fields_json TEXT NOT NULL,
    uncertain_json TEXT NOT NULL DEFAULT '[]',
    recorded_at TEXT NOT NULL,
    recorded_by TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS observations_ref ON observations(source_ref);
CREATE TABLE IF NOT EXISTS reporting_lines (
    line_id INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id TEXT NOT NULL,
    manager_id TEXT NOT NULL,
    evidence_kind TEXT NOT NULL,
    evidence_ref TEXT NOT NULL DEFAULT '',
    confidence REAL NOT NULL,
    inferred INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    created_by TEXT NOT NULL,
    removed_at TEXT,
    removed_by TEXT,
    removed_reason TEXT
);
CREATE TABLE IF NOT EXISTS history (
    history_id INTEGER PRIMARY KEY AUTOINCREMENT,
    change_id TEXT NOT NULL,
    at TEXT NOT NULL,
    actor TEXT NOT NULL,
    person_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    field TEXT NOT NULL DEFAULT '',
    old TEXT NOT NULL DEFAULT '',
    new TEXT NOT NULL DEFAULT '',
    reason TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT '',
    extra_json TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS history_change ON history(change_id);
CREATE INDEX IF NOT EXISTS history_person ON history(person_id);
CREATE TABLE IF NOT EXISTS undone (
    change_id TEXT PRIMARY KEY,
    undone_by TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS proposals (
    proposal_id INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id TEXT NOT NULL,
    field TEXT NOT NULL,
    current TEXT NOT NULL,
    proposed TEXT NOT NULL,
    source TEXT NOT NULL,
    observation_id INTEGER,
    created_at TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'open'
);
"""


class CardStoreError(Exception):
    """A refusal a person can act on, by code; never carries the data."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def actor_key(actor: str) -> str:
    """A file-safe folder name for one actor; a hash keeps two actors apart
    even when their safe names coincide."""
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", actor)[:40] or "actor"
    return f"{safe}-{hashlib.sha256(actor.encode('utf-8')).hexdigest()[:8]}"


def store_dir(workspace_root: Path, actor: str) -> Path:
    return workspace_root / STORE_FOLDER / actor_key(actor)


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _new_change() -> str:
    return f"c-{datetime.now(UTC):%Y%m%d%H%M%S}-{secrets.token_hex(3)}"


def _same(a: str, b: str) -> bool:
    return " ".join(a.split()).casefold() == " ".join(b.split()).casefold()


def _describe(values: Mapping[str, str]) -> str:
    place = values.get("department") or values.get("division") or values.get("business_group")
    return "".join(part for part in (place or "", values.get("title") or "") if part)


@dataclass
class _Merge:
    changes: list[FieldChange] = field(default_factory=list)
    kept: list[KeptField] = field(default_factory=list)


class CardStore:
    """One actor's store. Opened per call; SQLite serialises writers."""

    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as con:
            con.executescript(_SCHEMA)
            # A store from before a field existed gains its column.
            have = {row["name"] for row in con.execute("PRAGMA table_info(people)")}
            for name in FIELDS:
                if name not in have:
                    con.execute(f"ALTER TABLE people ADD COLUMN {name} TEXT NOT NULL DEFAULT ''")

    @classmethod
    def for_actor(cls, workspace_root: Path, actor: str) -> CardStore:
        return cls(store_dir(workspace_root, actor) / DB_FILE)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        with closing(sqlite3.connect(self.path, timeout=10)) as con:
            con.row_factory = sqlite3.Row
            with con:
                yield con

    # -- lookups -------------------------------------------------------

    @staticmethod
    def _people(con: sqlite3.Connection) -> list[sqlite3.Row]:
        return list(con.execute("SELECT * FROM people ORDER BY created_at, person_id"))

    def _match(
        self, con: sqlite3.Connection, values: Mapping[str, str]
    ) -> tuple[sqlite3.Row | None, str | None]:
        email = names.email_key(values.get("email", ""))
        if email:
            row = con.execute("SELECT * FROM people WHERE email_key = ?", (email,)).fetchone()
            if row is not None:
                return row, "email"
        name, company = values.get("name", ""), values.get("company", "")
        romanised = values.get("romanised_name", "")
        if not (name or romanised) or not company:
            return None, None
        found: list[tuple[int, sqlite3.Row, str]] = []
        for row in self._people(con):
            if not names.same_company(row["company"], company):
                continue
            if email and row["email_key"] and row["email_key"] != email:
                continue
            if name and names.same_name(row["name"], name):
                found.append((0, row, "name_company"))
            elif (name and names.same_name(row["romanised_name"], name)) or (
                romanised
                and (
                    names.same_name(row["name"], romanised)
                    or names.same_name(row["romanised_name"], romanised)
                )
            ):
                found.append((1, row, "romanised_name"))
        if not found:
            return None, None
        found.sort(key=lambda item: item[0])
        return found[0][1], found[0][2]

    def _resolve(self, con: sqlite3.Connection, ref: PersonRef) -> sqlite3.Row:
        if ref.person_id:
            row = con.execute(
                "SELECT * FROM people WHERE person_id = ?", (ref.person_id,)
            ).fetchone()
            if row is None:
                raise CardStoreError("person_unknown")
            return row  # type: ignore[no-any-return]
        if not ref.name.strip():
            raise CardStoreError("person_unspecified")
        hits = [
            row
            for row in self._people(con)
            if (
                names.same_name(row["name"], ref.name)
                or names.same_name(row["romanised_name"], ref.name)
            )
            and (not ref.company or names.same_company(row["company"], ref.company))
        ]
        if not hits:
            raise CardStoreError("person_unknown")
        if len(hits) > 1:
            raise CardStoreError("person_ambiguous")
        return hits[0]

    def _sources(self, con: sqlite3.Connection, person_id: str) -> dict[str, sqlite3.Row]:
        return {
            row["field"]: row
            for row in con.execute("SELECT * FROM field_sources WHERE person_id = ?", (person_id,))
        }

    def _manager(self, con: sqlite3.Connection, person_id: str) -> sqlite3.Row | None:
        found: sqlite3.Row | None = con.execute(
            "SELECT l.*, p.name AS manager_name FROM reporting_lines l "
            "JOIN people p ON p.person_id = l.manager_id "
            "WHERE l.person_id = ? AND l.removed_at IS NULL ORDER BY l.line_id DESC LIMIT 1",
            (person_id,),
        ).fetchone()
        return found

    def _needs(self, con: sqlite3.Connection, person_id: str) -> tuple[FieldName, ...]:
        """Fields any reading of this person flagged as uncertain that hold a
        value the person has not confirmed or set (source `user`)."""
        flagged: set[str] = set()
        for item in con.execute(
            "SELECT uncertain_json FROM observations WHERE person_id = ?", (person_id,)
        ):
            flagged.update(json.loads(item["uncertain_json"] or "[]"))
        sources = self._sources(con, person_id)
        return tuple(
            name
            for name in FIELDS
            if name in flagged and name in sources and sources[name]["source"] != "user"
        )

    def _view(self, con: sqlite3.Connection, row: sqlite3.Row) -> PersonView:
        person_id = row["person_id"]
        sources = sorted(
            {
                item["source"]
                for item in con.execute(
                    "SELECT DISTINCT source FROM observations WHERE person_id = ?", (person_id,)
                )
            }
            | {item["source"] for item in self._sources(con, person_id).values()}
        )
        line = self._manager(con, person_id)
        proposals = con.execute(
            "SELECT COUNT(*) FROM proposals WHERE person_id = ? AND state = 'open'", (person_id,)
        ).fetchone()[0]
        return PersonView(
            **{name: row[name] for name in FIELDS},
            person_id=person_id,
            status=row["status"],
            left_at=row["left_at"],
            status_reason=row["status_reason"],
            status_set_by=row["status_set_by"],
            sources=tuple(sources),
            manager="" if line is None else line["manager_name"],
            manager_line="" if line is None else ("inferred" if line["inferred"] else "evidenced"),
            open_proposals=int(proposals),
            needs_confirmation=self._needs(con, person_id),
            updated_at=row["updated_at"],
        )

    # -- history -------------------------------------------------------

    @staticmethod
    def _record(
        con: sqlite3.Connection,
        change_id: str,
        actor: str,
        person_id: str,
        kind: str,
        *,
        field_name: str = "",
        old: str = "",
        new: str = "",
        reason: str = "",
        source: str = "",
        extra: Mapping[str, Any] | None = None,
    ) -> None:
        con.execute(
            "INSERT INTO history (change_id, at, actor, person_id, kind, field, old, new, "
            "reason, source, extra_json) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                change_id,
                _now(),
                actor,
                person_id,
                kind,
                field_name,
                old,
                new,
                reason,
                source,
                json.dumps(dict(extra or {}), ensure_ascii=False),
            ),
        )

    def _set_field(
        self,
        con: sqlite3.Connection,
        change_id: str,
        actor: str,
        person: sqlite3.Row,
        name: FieldName,
        value: str,
        *,
        source: Source,
        source_date: str,
        observation_id: int | None,
        reason: str,
        previous: sqlite3.Row | None,
    ) -> FieldChange:
        person_id = person["person_id"]
        old = person[name]
        con.execute(f"UPDATE people SET {name} = ? WHERE person_id = ?", (value, person_id))
        if name == "email":
            con.execute(
                "UPDATE people SET email_key = ? WHERE person_id = ?",
                (names.email_key(value), person_id),
            )
        con.execute(
            "INSERT OR REPLACE INTO field_sources VALUES (?,?,?,?,?)",
            (person_id, name, source, source_date, observation_id),
        )
        self._record(
            con,
            change_id,
            actor,
            person_id,
            "field",
            field_name=name,
            old=old,
            new=value,
            reason=reason,
            source=source,
            extra={
                "prev_source": None if previous is None else previous["source"],
                "prev_date": None if previous is None else previous["source_date"],
                "prev_observation": None if previous is None else previous["observation_id"],
            },
        )
        return FieldChange(field=name, old=old, new=value)

    # -- adding --------------------------------------------------------

    def add(
        self,
        values: Mapping[str, str],
        *,
        source: Source,
        source_date: date,
        source_ref: str,
        uncertain: Sequence[FieldName],
        actor: str,
    ) -> AddResult:
        """One scan or sighting: kept as an observation, merged into the person."""
        with self._connect() as con:
            return self._add(
                con,
                values,
                source=source,
                source_date=source_date,
                source_ref=source_ref,
                uncertain=uncertain,
                actor=actor,
            )

    def _add(
        self,
        con: sqlite3.Connection,
        values: Mapping[str, str],
        *,
        source: Source,
        source_date: date,
        source_ref: str,
        uncertain: Sequence[FieldName],
        actor: str,
    ) -> AddResult:
        clean = reading.tidy({name: str(values.get(name, "")).strip() for name in FIELDS})
        if not clean["name"] and not clean["romanised_name"] and not clean["email"]:
            raise CardStoreError("card_without_name")
        if not clean["name"]:
            clean["name"] = clean["romanised_name"] or clean["email"]
        unsure = tuple(dict.fromkeys(uncertain))
        when = source_date.isoformat()
        row, matched_by = self._match(con, clean)
        cursor = con.execute(
            "INSERT INTO observations (person_id, source, source_date, source_ref, fields_json, "
            "uncertain_json, recorded_at, recorded_by) VALUES (?,?,?,?,?,?,?,?)",
            (
                None if row is None else row["person_id"],
                source,
                when,
                source_ref,
                json.dumps(clean, ensure_ascii=False),
                json.dumps(list(unsure)),
                _now(),
                actor,
            ),
        )
        observation_id = int(cursor.lastrowid or 0)
        change_id = _new_change()
        if row is None:
            person_id = f"p-{secrets.token_hex(5)}"
            stamp = _now()
            con.execute(
                "INSERT INTO people (person_id, created_at, updated_at) VALUES (?,?,?)",
                (person_id, stamp, stamp),
            )
            con.execute(
                "UPDATE observations SET person_id = ? WHERE observation_id = ?",
                (person_id, observation_id),
            )
            self._record(
                con,
                change_id,
                actor,
                person_id,
                "create",
                new=clean["name"],
                source=source,
                extra={"observation_id": observation_id},
            )
            for name in FIELDS:
                if clean[name]:
                    con.execute(
                        f"UPDATE people SET {name} = ? WHERE person_id = ?",
                        (clean[name], person_id),
                    )
                    con.execute(
                        "INSERT OR REPLACE INTO field_sources VALUES (?,?,?,?,?)",
                        (person_id, name, source, when, observation_id),
                    )
            con.execute(
                "UPDATE people SET email_key = ? WHERE person_id = ?",
                (names.email_key(clean["email"]), person_id),
            )
            return AddResult(
                person_id=person_id,
                name=clean["name"],
                company=clean["company"],
                outcome="created",
                existed=False,
                uncertain=unsure,
                needs_confirmation=self._needs(con, person_id),
                observation_id=observation_id,
                change_id=change_id,
            )
        merge = self._merge(
            con,
            change_id,
            actor,
            row,
            clean,
            source=source,
            when=when,
            observation_id=observation_id,
            uncertain=unsure,
        )
        if merge.changes:
            con.execute(
                "UPDATE people SET updated_at = ? WHERE person_id = ?", (_now(), row["person_id"])
            )
        fresh = con.execute(
            "SELECT * FROM people WHERE person_id = ?", (row["person_id"],)
        ).fetchone()
        return AddResult(
            person_id=row["person_id"],
            name=fresh["name"],
            company=fresh["company"],
            outcome="updated" if merge.changes else "unchanged",
            existed=True,
            matched_by=matched_by,
            changes=tuple(merge.changes),
            kept=tuple(merge.kept),
            uncertain=unsure,
            needs_confirmation=self._needs(con, row["person_id"]),
            status=fresh["status"],
            summary=_summary(row, merge),
            observation_id=observation_id,
            change_id=change_id
            if merge.changes or any(item.reason == "user_set" for item in merge.kept)
            else None,
        )

    def _merge(
        self,
        con: sqlite3.Connection,
        change_id: str,
        actor: str,
        row: sqlite3.Row,
        clean: dict[str, str],
        *,
        source: Source,
        when: str,
        observation_id: int,
        uncertain: Sequence[FieldName],
    ) -> _Merge:
        merge = _Merge()
        person_id = row["person_id"]
        sources = self._sources(con, person_id)
        offered = dict(clean)
        # A romanised name in the name slot (an English signature) is the
        # person's romanised name, not a new name.
        if offered["name"] and names.has_cjk(row["name"]) and not names.has_cjk(offered["name"]):
            if not offered["romanised_name"]:
                offered["romanised_name"] = offered["name"]
            offered["name"] = ""
        for name in FIELDS:
            new = offered[name]
            current = row[name]
            if not new or _same(current, new):
                continue
            # Another spelling of the same company or name (a legal suffix,
            # a romanisation) is not a change.
            if name == "company" and names.same_company(current, new):
                continue
            if name == "name" and names.same_name(current, new):
                continue
            previous = sources.get(name)
            if name == "notes" and current:
                if new.casefold() in current.casefold():
                    continue
                new = f"{current}\n{new}"
            elif current and name in uncertain:
                merge.kept.append(
                    KeptField(field=name, current=current, offered=new, reason="uncertain")
                )
                continue
            elif previous is not None and previous["source"] == "user":
                # Also a value the person emptied: a scan does not refill it.
                merge.kept.append(
                    KeptField(field=name, current=current, offered=new, reason="user_set")
                )
                con.execute(
                    "INSERT INTO proposals (person_id, field, current, proposed, source, "
                    "observation_id, created_at) VALUES (?,?,?,?,?,?,?)",
                    (person_id, name, current, new, source, observation_id, _now()),
                )
                self._record(
                    con,
                    change_id,
                    actor,
                    person_id,
                    "proposal",
                    field_name=name,
                    old=current,
                    new=new,
                    source=source,
                    reason="your value is kept; the new one is a proposal",
                )
                continue
            elif current and previous is not None and when < previous["source_date"]:
                merge.kept.append(
                    KeptField(field=name, current=current, offered=new, reason="older_evidence")
                )
                continue
            merge.changes.append(
                self._set_field(
                    con,
                    change_id,
                    actor,
                    row,
                    name,
                    new,
                    source=source,
                    source_date=when,
                    observation_id=observation_id,
                    reason=f"{source} {when}",
                    previous=previous,
                )
            )
        return merge

    # -- the person's own edits ----------------------------------------

    def edit(
        self,
        ref: PersonRef,
        values: Mapping[str, str],
        *,
        actor: str,
        reason: str,
        confirm: Sequence[FieldName] = (),
        clear: Sequence[FieldName] = (),
    ) -> tuple[sqlite3.Row, list[FieldChange], list[FieldName], str | None]:
        """The person's own values (source `user`), the fields they say are
        right as stored, and the fields they say are wrong (emptied, and kept
        empty). Re-stating the stored value confirms it."""
        with self._connect() as con:
            row = self._resolve(con, ref)
            change_id = _new_change()
            sources = self._sources(con, row["person_id"])
            needs = set(self._needs(con, row["person_id"]))
            changes: list[FieldChange] = []
            confirmed: list[FieldName] = []
            today = date.today().isoformat()
            for name in FIELDS:
                new = str(values.get(name, "")).strip()
                emptied = name in clear and not new and bool(row[name])
                if emptied or (new and not _same(row[name], new)):
                    changes.append(
                        self._set_field(
                            con,
                            change_id,
                            actor,
                            row,
                            name,
                            new,
                            source="user",
                            source_date=today,
                            observation_id=None,
                            reason=reason or "set by the person",
                            previous=sources.get(name),
                        )
                    )
                    con.execute(
                        "UPDATE proposals SET state = 'resolved' WHERE person_id = ? AND field = ? "
                        "AND state = 'open'",
                        (row["person_id"], name),
                    )
                    continue
                asked = name in confirm or (bool(new) and name in needs)
                previous = sources.get(name)
                if not asked or not row[name] or previous is None:
                    continue
                if previous["source"] == "user":
                    continue
                con.execute(
                    "INSERT OR REPLACE INTO field_sources VALUES (?,?,?,?,?)",
                    (row["person_id"], name, "user", today, None),
                )
                self._record(
                    con,
                    change_id,
                    actor,
                    row["person_id"],
                    "confirm",
                    field_name=name,
                    old=row[name],
                    new=row[name],
                    reason=reason or "confirmed by the person",
                    source="user",
                    extra={
                        "prev_source": previous["source"],
                        "prev_date": previous["source_date"],
                        "prev_observation": previous["observation_id"],
                    },
                )
                confirmed.append(name)
            if changes or confirmed:
                con.execute(
                    "UPDATE people SET updated_at = ? WHERE person_id = ?",
                    (_now(), row["person_id"]),
                )
            fresh = con.execute(
                "SELECT * FROM people WHERE person_id = ?", (row["person_id"],)
            ).fetchone()
            return fresh, changes, confirmed, change_id if changes or confirmed else None

    def needs_confirmation(self, person_id: str) -> tuple[FieldName, ...]:
        with self._connect() as con:
            return self._needs(con, person_id)

    # -- status and reporting lines -----------------------------------

    def set_status(
        self,
        ref: PersonRef,
        status: Status,
        *,
        actor: str,
        reason: str,
        effective: date | None,
    ) -> tuple[sqlite3.Row, str, str, str | None]:
        """A departure (or return) the person stated; recorded and undoable.
        `actor` is who said it, as the Host knows them (actor and channel)."""
        with self._connect() as con:
            row = self._resolve(con, ref)
            old = row["status"]
            left_at = (effective or date.today()).isoformat() if status == "left" else ""
            if old == status and row["left_at"] == left_at:
                return row, old, status, None
            change_id = _new_change()
            con.execute(
                "UPDATE people SET status = ?, left_at = ?, status_set_by = ?, status_reason = ?, "
                "updated_at = ? WHERE person_id = ?",
                (status, left_at, actor, reason, _now(), row["person_id"]),
            )
            self._record(
                con,
                change_id,
                actor,
                row["person_id"],
                "status",
                field_name="status",
                old=old,
                new=status,
                reason=reason,
                source="user",
                extra={
                    "prev_left_at": row["left_at"],
                    "prev_set_by": row["status_set_by"],
                    "prev_reason": row["status_reason"],
                    "left_at": left_at,
                },
            )
            fresh = con.execute(
                "SELECT * FROM people WHERE person_id = ?", (row["person_id"],)
            ).fetchone()
            return fresh, old, status, change_id

    def set_line(
        self,
        person: PersonRef,
        manager: PersonRef,
        *,
        evidence_kind: str,
        evidence_ref: str,
        confidence: float,
        inferred: bool,
        actor: str,
    ) -> tuple[sqlite3.Row, sqlite3.Row, bool, str]:
        with self._connect() as con:
            row = self._resolve(con, person)
            boss = self._resolve(con, manager)
            if row["person_id"] == boss["person_id"]:
                raise CardStoreError("line_to_self")
            if self._reaches(con, boss["person_id"], row["person_id"]):
                raise CardStoreError("line_cycle")
            change_id = _new_change()
            current = self._manager(con, row["person_id"])
            if current is not None:
                self._remove_line(con, change_id, actor, current, "replaced by a new line")
            cursor = con.execute(
                "INSERT INTO reporting_lines (person_id, manager_id, evidence_kind, evidence_ref, "
                "confidence, inferred, created_at, created_by) VALUES (?,?,?,?,?,?,?,?)",
                (
                    row["person_id"],
                    boss["person_id"],
                    evidence_kind,
                    evidence_ref,
                    confidence,
                    1 if inferred else 0,
                    _now(),
                    actor,
                ),
            )
            self._record(
                con,
                change_id,
                actor,
                row["person_id"],
                "line_add",
                field_name="manager",
                new=boss["name"],
                source=evidence_kind,
                reason=evidence_ref,
                extra={"line_id": int(cursor.lastrowid or 0), "inferred": inferred},
            )
            return row, boss, current is not None, change_id

    def _reaches(self, con: sqlite3.Connection, start: str, target: str) -> bool:
        """Whether `start`'s chain of managers reaches `target`."""
        seen: set[str] = set()
        node = start
        while node not in seen:
            seen.add(node)
            if node == target:
                return True
            line = self._manager(con, node)
            if line is None:
                return False
            node = line["manager_id"]
        return False

    def _remove_line(
        self, con: sqlite3.Connection, change_id: str, actor: str, line: sqlite3.Row, reason: str
    ) -> None:
        con.execute(
            "UPDATE reporting_lines SET removed_at = ?, removed_by = ?, removed_reason = ? "
            "WHERE line_id = ?",
            (_now(), actor, reason, line["line_id"]),
        )
        self._record(
            con,
            change_id,
            actor,
            line["person_id"],
            "line_remove",
            field_name="manager",
            old=line["manager_name"],
            reason=reason,
            source="user",
            extra={"line_id": line["line_id"]},
        )

    def remove_line(
        self, person: PersonRef, *, actor: str, reason: str
    ) -> tuple[sqlite3.Row, sqlite3.Row | None, str | None]:
        with self._connect() as con:
            row = self._resolve(con, person)
            current = self._manager(con, row["person_id"])
            if current is None:
                return row, None, None
            change_id = _new_change()
            self._remove_line(con, change_id, actor, current, reason or "removed by the person")
            return row, current, change_id

    # -- undo ----------------------------------------------------------

    def undo(self, change_id: str, *, actor: str) -> tuple[list[HistoryItem], str | None]:
        """Revert one change group, newest row first, as a new change. Refused
        when a later change touched the same values (`undo_conflict`)."""
        with self._connect() as con:
            rows = list(
                con.execute(
                    "SELECT * FROM history WHERE change_id = ? ORDER BY history_id DESC",
                    (change_id,),
                )
            )
            if not rows:
                raise CardStoreError("change_unknown")
            if con.execute("SELECT 1 FROM undone WHERE change_id = ?", (change_id,)).fetchone():
                raise CardStoreError("change_already_undone")
            new_change = _new_change()
            reverted: list[HistoryItem] = []
            for item in rows:
                extra = json.loads(item["extra_json"] or "{}")
                person = con.execute(
                    "SELECT * FROM people WHERE person_id = ?", (item["person_id"],)
                ).fetchone()
                kind = item["kind"]
                if kind == "create":
                    if person is None:
                        continue
                    later = con.execute(
                        "SELECT 1 FROM history WHERE person_id = ? AND change_id != ? "
                        "AND change_id NOT IN (SELECT change_id FROM undone) "
                        "AND change_id NOT IN (SELECT undone_by FROM undone) LIMIT 1",
                        (item["person_id"], change_id),
                    ).fetchone()
                    if later is not None:
                        raise CardStoreError("undo_conflict")
                    pid = item["person_id"]
                    for table in ("people", "field_sources", "observations", "proposals"):
                        con.execute(f"DELETE FROM {table} WHERE person_id = ?", (pid,))
                    con.execute(
                        "UPDATE reporting_lines SET removed_at = ?, removed_by = ?, "
                        "removed_reason = 'undo' WHERE (person_id = ? OR manager_id = ?) "
                        "AND removed_at IS NULL",
                        (_now(), actor, pid, pid),
                    )
                    self._record(
                        con,
                        new_change,
                        actor,
                        pid,
                        "delete",
                        old=item["new"],
                        reason=f"undo {change_id}",
                    )
                elif kind == "field":
                    if person is None:
                        raise CardStoreError("undo_conflict")
                    name = item["field"]
                    if not _same(person[name], item["new"]):
                        raise CardStoreError("undo_conflict")
                    con.execute(
                        f"UPDATE people SET {name} = ?, updated_at = ? WHERE person_id = ?",
                        (item["old"], _now(), item["person_id"]),
                    )
                    if name == "email":
                        con.execute(
                            "UPDATE people SET email_key = ? WHERE person_id = ?",
                            (names.email_key(item["old"]), item["person_id"]),
                        )
                    if extra.get("prev_source"):
                        con.execute(
                            "INSERT OR REPLACE INTO field_sources VALUES (?,?,?,?,?)",
                            (
                                item["person_id"],
                                name,
                                extra["prev_source"],
                                extra.get("prev_date") or "",
                                extra.get("prev_observation"),
                            ),
                        )
                    else:
                        con.execute(
                            "DELETE FROM field_sources WHERE person_id = ? AND field = ?",
                            (item["person_id"], name),
                        )
                    self._record(
                        con,
                        new_change,
                        actor,
                        item["person_id"],
                        "field",
                        field_name=name,
                        old=item["new"],
                        new=item["old"],
                        reason=f"undo {change_id}",
                        source="user",
                    )
                elif kind == "status":
                    if person is None or person["status"] != item["new"]:
                        raise CardStoreError("undo_conflict")
                    con.execute(
                        "UPDATE people SET status = ?, left_at = ?, status_set_by = ?, "
                        "status_reason = ?, updated_at = ? WHERE person_id = ?",
                        (
                            item["old"],
                            extra.get("prev_left_at") or "",
                            extra.get("prev_set_by") or "",
                            extra.get("prev_reason") or "",
                            _now(),
                            item["person_id"],
                        ),
                    )
                    self._record(
                        con,
                        new_change,
                        actor,
                        item["person_id"],
                        "status",
                        field_name="status",
                        old=item["new"],
                        new=item["old"],
                        reason=f"undo {change_id}",
                        source="user",
                    )
                elif kind == "line_add":
                    con.execute(
                        "UPDATE reporting_lines SET removed_at = ?, removed_by = ?, "
                        "removed_reason = ? WHERE line_id = ? AND removed_at IS NULL",
                        (_now(), actor, f"undo {change_id}", extra.get("line_id")),
                    )
                    self._record(
                        con,
                        new_change,
                        actor,
                        item["person_id"],
                        "line_remove",
                        field_name="manager",
                        old=item["new"],
                        reason=f"undo {change_id}",
                        source="user",
                        extra={"line_id": extra.get("line_id")},
                    )
                elif kind == "line_remove":
                    con.execute(
                        "UPDATE reporting_lines SET removed_at = NULL, removed_by = NULL, "
                        "removed_reason = NULL WHERE line_id = ?",
                        (extra.get("line_id"),),
                    )
                    self._record(
                        con,
                        new_change,
                        actor,
                        item["person_id"],
                        "line_add",
                        field_name="manager",
                        new=item["old"],
                        reason=f"undo {change_id}",
                        source="user",
                        extra={"line_id": extra.get("line_id")},
                    )
                elif kind == "confirm":
                    if person is None:
                        continue
                    con.execute(
                        "INSERT OR REPLACE INTO field_sources VALUES (?,?,?,?,?)",
                        (
                            item["person_id"],
                            item["field"],
                            extra.get("prev_source") or "card",
                            extra.get("prev_date") or "",
                            extra.get("prev_observation"),
                        ),
                    )
                    self._record(
                        con,
                        new_change,
                        actor,
                        item["person_id"],
                        "unconfirm",
                        field_name=item["field"],
                        old=item["new"],
                        new=item["new"],
                        reason=f"undo {change_id}",
                        source=extra.get("prev_source") or "",
                    )
                elif kind == "proposal":
                    con.execute(
                        "UPDATE proposals SET state = 'dismissed' "
                        "WHERE person_id = ? AND field = ? AND proposed = ? AND state = 'open'",
                        (item["person_id"], item["field"], item["new"]),
                    )
                else:
                    continue
                reverted.append(_history_item(item))
            con.execute(
                "INSERT INTO undone (change_id, undone_by) VALUES (?, ?)", (change_id, new_change)
            )
            return reverted, new_change

    # -- reading -------------------------------------------------------

    def find(self, query: str, *, status: str, limit: int) -> tuple[list[PersonView], int]:
        words = names.search_text(query).split()
        romanised = names.name_keys(query)
        with self._connect() as con:
            hits = []
            for row in self._people(con):
                if status != "any" and row["status"] != status:
                    continue
                text = names.search_text(
                    *(row[name] for name in FIELDS if name not in ("address", "notes"))
                )
                if all(word in text for word in words) or (
                    romanised
                    and (
                        romanised & names.name_keys(row["name"])
                        or romanised & names.name_keys(row["romanised_name"])
                    )
                ):
                    hits.append(row)
            return [self._view(con, row) for row in hits[:limit]], len(hits)

    def list_people(
        self, *, company: str, source: str, status: str, limit: int
    ) -> tuple[list[PersonView], int]:
        with self._connect() as con:
            hits = []
            for row in self._people(con):
                if status != "any" and row["status"] != status:
                    continue
                if company and not names.same_company(row["company"], company):
                    continue
                if (
                    source
                    and not con.execute(
                        "SELECT 1 FROM observations WHERE person_id = ? AND source = ? "
                        "UNION SELECT 1 FROM field_sources WHERE person_id = ? AND source = ? "
                        "LIMIT 1",
                        (row["person_id"], source, row["person_id"], source),
                    ).fetchone()
                ):
                    continue
                hits.append(row)
            hits.sort(
                key=lambda r: (
                    r["company"],
                    r["business_group"],
                    r["division"],
                    r["department"],
                    r["name"],
                )
            )
            return [self._view(con, row) for row in hits[:limit]], len(hits)

    def history(self, ref: PersonRef, *, limit: int) -> HistoryResult:
        with self._connect() as con:
            row = self._resolve(con, ref)
            pid = row["person_id"]
            items = [
                _history_item(item)
                for item in con.execute(
                    "SELECT * FROM history WHERE person_id = ? ORDER BY history_id DESC LIMIT ?",
                    (pid, limit),
                )
            ]
            observations = [
                ObservationView(
                    observation_id=item["observation_id"],
                    source=item["source"],
                    source_date=item["source_date"],
                    source_ref=item["source_ref"],
                    uncertain=tuple(json.loads(item["uncertain_json"] or "[]")),
                )
                for item in con.execute(
                    "SELECT * FROM observations WHERE person_id = ? ORDER BY observation_id DESC "
                    "LIMIT ?",
                    (pid, limit),
                )
            ]
            proposals = [
                ProposalView(
                    field=item["field"],
                    current=item["current"],
                    proposed=item["proposed"],
                    source=item["source"],
                )
                for item in con.execute(
                    "SELECT * FROM proposals WHERE person_id = ? AND state = 'open'", (pid,)
                )
            ]
            return HistoryResult(
                person=self._view(con, row),
                history=tuple(items),
                observations=tuple(observations),
                proposals=tuple(proposals),
            )

    def view(self, person_id: str) -> PersonView:
        with self._connect() as con:
            row = con.execute("SELECT * FROM people WHERE person_id = ?", (person_id,)).fetchone()
            if row is None:
                raise CardStoreError("person_unknown")
            return self._view(con, row)

    def preview(self, values: Mapping[str, str]) -> tuple[str, tuple[FieldName, ...]]:
        """Who these fields would merge into and which fields would change;
        nothing is written."""
        clean: dict[str, str] = {name: str(values.get(name, "")).strip() for name in FIELDS}
        with self._connect() as con:
            row, _ = self._match(con, clean)
            if row is None:
                return "", ()
            return row["person_id"], tuple(
                name for name in FIELDS if clean[name] and not _same(row[name], clean[name])
            )

    def chart_data(
        self, company: str, *, include_left: bool
    ) -> tuple[list[sqlite3.Row], list[sqlite3.Row], int]:
        """People of a company (and how many who left were left out) and the
        active lines between them."""
        with self._connect() as con:
            everyone = [
                row for row in self._people(con) if names.same_company(row["company"], company)
            ]
            shown = [row for row in everyone if include_left or row["status"] != "left"]
            ids = {row["person_id"] for row in shown}
            lines = [
                line
                for line in con.execute(
                    "SELECT * FROM reporting_lines WHERE removed_at IS NULL ORDER BY line_id"
                )
                if line["person_id"] in ids and line["manager_id"] in ids
            ]
            return shown, lines, len(everyone) - len(shown)

    def uncertain_now(self, person_ids: Sequence[str]) -> dict[str, list[str]]:
        """Each person's fields still to confirm: flagged by any reading and
        neither confirmed nor set by the person."""
        found: dict[str, list[str]] = {}
        with self._connect() as con:
            for person_id in person_ids:
                needs = self._needs(con, person_id)
                if needs:
                    found[person_id] = list(needs)
        return found

    # -- the Hermes store ----------------------------------------------

    def import_hermes(self, source: Path, *, actor: str) -> ImportResult:
        """Every row of a Hermes `cards.db` as a `card` observation with its
        own date, oldest first; a row already imported is skipped."""
        if not source.is_file():
            return ImportResult(found=False, source=str(source))
        uri = source.resolve().as_uri() + "?mode=ro"
        with closing(sqlite3.connect(uri, uri=True)) as old:
            old.row_factory = sqlite3.Row
            try:
                rows = list(old.execute("SELECT * FROM cards ORDER BY captured_at, id"))
            except sqlite3.DatabaseError as error:
                raise CardStoreError("import_unreadable") from error
        imported = already = created = updated = 0
        with self._connect() as con:
            for item in rows:
                keys = item.keys()
                ref = f"hermes-cards:{item['id']}"
                if con.execute(
                    "SELECT 1 FROM observations WHERE source_ref = ?", (ref,)
                ).fetchone():
                    already += 1
                    continue
                values: dict[str, str] = {
                    name: str(item[name] or "") if name in keys else "" for name in FIELDS
                }
                try:
                    unsure = [u for u in json.loads(item["uncertain"] or "[]") if u in FIELDS]
                except (TypeError, ValueError):
                    unsure = []
                try:
                    when = datetime.fromisoformat(str(item["captured_at"])).date()
                except ValueError:
                    when = date.today()
                try:
                    result = self._add(
                        con,
                        values,
                        source="card",
                        source_date=when,
                        source_ref=ref,
                        uncertain=unsure,
                        actor=actor,
                    )
                except CardStoreError:
                    continue
                imported += 1
                if result.outcome == "created":
                    created += 1
                elif result.outcome == "updated":
                    updated += 1
        return ImportResult(
            found=True,
            rows=len(rows),
            imported=imported,
            already=already,
            people_created=created,
            people_updated=updated,
            source=str(source),
        )


def _history_item(row: sqlite3.Row) -> HistoryItem:
    return HistoryItem(
        change_id=row["change_id"],
        at=row["at"],
        actor=row["actor"],
        kind=row["kind"],
        field=row["field"],
        old=row["old"],
        new=row["new"],
        reason=row["reason"],
        source=row["source"],
    )


def _summary(before: sqlite3.Row, merge: _Merge) -> str:
    """The sentence a reply leads with when the person was already on file."""
    if not merge.changes:
        return "已在名片夾中，資料沒有變。" if not merge.kept else ""
    changed = {change.field for change in merge.changes}
    parts: list[str] = []
    if changed & set(ORG_FIELDS):
        old: dict[str, str] = {name: before[name] for name in ORG_FIELDS}
        new = dict(old)
        for change in merge.changes:
            new[change.field] = change.new
        if "company" in changed:
            parts.append(
                f"上次是{old['company']}{_describe(old)}, 現在是{new['company']}{_describe(new)}"
            )
        else:
            parts.append(f"上次是{_describe(old) or '（未標示）'}, 現在是{_describe(new)}")
    other = [c for c in merge.changes if c.field not in ORG_FIELDS and c.field != "notes"]
    if other:
        parts.append("、".join(_LABELS[c.field] for c in other) + " 也更新了")
    return "；".join(parts) + "。" if parts else ""
