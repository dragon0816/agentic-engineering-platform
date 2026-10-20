"""The person's contact store: the `contacts/org` memory space of one actor
(docs/phases/BUSINESS_CARDS.md §2; docs/phases/ACCUMULATED_MEMORY.md M1).

Every scan or signature sighting is an observation that is never rewritten,
and so is every statement the person makes (an edit, a confirmation, a
departure, a reporting line): a `user` observation. `people` holds the
current view, with field-level provenance: a value the person set (`user`)
is never replaced by an automatic source, which leaves a proposal instead;
an automatic value is replaced only by evidence that is not older (the
space's merge rules, `space.MERGE_RULES`). Every change is a `history` row in
a change group, and `undo` replays a group backwards as a new change.

The observations, provenance, history, undo, proposals and external ids are
the Memory Service's generic facilities (`memory.service`); this store keeps
what is particular to business cards: who a reading is, the honorific and
unified-business-number handling, company spellings, reporting lines and
the chart's data. The space lives in `<workspace>/memory/<actor-key>/
memory.sqlite`; an actor's earlier `business-cards/<actor-key>/cards.db` is
moved there once (`migration`). Nothing here reaches the network.
"""

from __future__ import annotations

import json
import secrets
import sqlite3
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import closing, contextmanager
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from capabilities.business_cards import migration, names, reading
from capabilities.business_cards.contracts import (
    FIELD_LABELS,
    FIELDS,
    KIND_LABELS,
    MATCH_LABELS,
    SOURCE_LABELS,
    STATUS_LABELS,
    AddResult,
    EmailDiffers,
    FieldChange,
    FieldName,
    HistoryItem,
    HistoryResult,
    ImportResult,
    KeptField,
    KeptReason,
    MatchSummary,
    ObservationView,
    PersonRef,
    PersonView,
    ProposalView,
    Source,
    Status,
    ToConfirm,
)
from capabilities.business_cards.manifest import CARDS_SKILL
from capabilities.business_cards.space import (
    CANDIDATES,
    CONTACTS_ORG,
    LINES,
    MERGE_RULES,
    PEOPLE,
    REPORTING_LINE,
    SPACE_SCHEMA,
    default_registry,
)
from common.assets import AssetIdentity
from memory.registry import MemoryRegistry, asset_label
from memory.service import (
    MemoryService,
    MemoryServiceError,
    SpaceTx,
    actor_key,
    new_change_id,
)

STORE_FOLDER = "business-cards"
#: The store before accumulated memory M1; moved into the Memory Service once.
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
#: How long a harvest's candidates can be stored by id.
CANDIDATE_TTL = timedelta(hours=1)
ALL_CANDIDATES = "all"
_LABELS = FIELD_LABELS
#: Times are shown to the person in this zone.
LOCAL_ZONE = ZoneInfo("Asia/Taipei")


class CardStoreError(Exception):
    """A refusal a person can act on, by code; never carries the data."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def store_dir(workspace_root: Path, actor: str) -> Path:
    """The actor's business-cards folder: the charts drawn, and the
    `cards.db` of before M1 with its backup."""
    return workspace_root / STORE_FOLDER / actor_key(actor)


def _clock() -> datetime:
    return datetime.now(UTC)


def _now() -> str:
    return _clock().isoformat(timespec="seconds")


def _same(a: str, b: str) -> bool:
    return " ".join(a.split()).casefold() == " ".join(b.split()).casefold()


#: Numbers compared by digits and extension, not by how they are written.
NUMBER_FIELDS = frozenset({"phone", "fax", "mobile"})


def _same_value(name: str, a: str, b: str) -> bool:
    """Whether two values of a field are the same: a number that differs only
    in formatting ("(03) 666-7799", "03 666 7799", "+886 3 666 7799") is."""
    if _same(a, b):
        return True
    if name in NUMBER_FIELDS:
        key = names.phone_key(a)
        return bool(key) and key == names.phone_key(b)
    return False


def _same_as(name: str) -> Callable[[str, str], bool]:
    return lambda a, b: _same_value(name, a, b)


#: Fields where a shorter reading can be a real change (副總經理 → 總經理 is a
#: promotion), or that have their own rules (notes are appended; an email is
#: the person's key).
_ANY_CHANGE = frozenset({"title", "notes", "email"})


def _less_complete(new: str, current: str) -> bool:
    """Whether `new` is a strict prefix or substring of `current` (spaces and
    case ignored): an automatic reading that lost part of the stored value."""
    short, full = " ".join(new.split()).casefold(), " ".join(current.split()).casefold()
    return bool(short) and short != full and short in full


def _elsewhere(row: Mapping[str, Any] | sqlite3.Row, values: Mapping[str, str]) -> bool:
    """Whether a reading places the person somewhere else than the stored
    row: both have a department and they differ, or both a division and they
    differ."""
    for level in ("department", "division"):
        stored, read = str(row[level] or "").strip(), str(values.get(level, "")).strip()
        if stored and read and not _same(stored, read):
            return True
    return False


def _describe(values: Mapping[str, str]) -> str:
    place = values.get("department") or values.get("division") or values.get("business_group")
    return "".join(part for part in (place or "", values.get("title") or "") if part)


@dataclass
class _Company:
    """One company as stored: its spellings, how many people each has, and
    its aliases (romanised short names, mail / web domains)."""

    name: str
    people: int = 0
    aliases: set[str] = field(default_factory=set)
    counts: dict[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.counts.setdefault(self.name, self.people)

    @property
    def spellings(self) -> tuple[str, ...]:
        return tuple(self.counts)

    def absorb(self, other: _Company) -> None:
        for name, count in other.counts.items():
            self.counts[name] = self.counts.get(name, 0) + count
        self.aliases |= other.aliases

    def canonical(self) -> str:
        """The spelling most people carry; on a tie the longest (the full
        legal name)."""
        return max(self.counts, key=lambda name: (self.counts[name], len(name)))


@dataclass
class _Merge:
    changes: list[FieldChange] = field(default_factory=list)
    kept: list[KeptField] = field(default_factory=list)


#: Why a merge rule kept a stored value, as a result names it.
_KEPT_REASONS: dict[str, KeptReason] = {
    "user_set": "user_set",
    "older_evidence": "older_evidence",
    "uncertain": "uncertain",
    "lower_trust": "lower_trust",
}


class CardStore:
    """One actor's contacts: the `contacts/org` space opened for the
    business-cards Skill. Opened per call; SQLite serialises writers."""

    def __init__(
        self,
        memory: MemoryService,
        *,
        legacy: Path | None = None,
        asset: AssetIdentity = CARDS_SKILL,
    ) -> None:
        self.memory = memory
        self.path = memory.path
        self.legacy = legacy
        try:
            self._space = memory.space(CONTACTS_ORG, asset=asset)
            with self._space.transaction() as tx:
                if self._space.role == "manager":
                    con = tx.con
                    con.executescript(SPACE_SCHEMA)
                    # A store from before a field existed gains its column.
                    have = {row["name"] for row in con.execute(f"PRAGMA table_info({PEOPLE})")}
                    for name in FIELDS:
                        if name not in have:
                            con.execute(
                                f"ALTER TABLE {PEOPLE} ADD COLUMN {name} TEXT NOT NULL DEFAULT ''"
                            )
            if legacy is not None and self._space.role == "manager":
                migration.migrate(
                    memory, legacy, rules=MERGE_RULES, manager=asset_label(self._space.asset)
                )
        except migration.MigrationError as error:
            raise CardStoreError(error.code) from error
        except MemoryServiceError as error:
            raise CardStoreError(error.code) from error

    @classmethod
    def for_actor(
        cls, workspace_root: Path, actor: str, registry: MemoryRegistry | None = None
    ) -> CardStore:
        """The actor's store in the Memory Service; `registry` is the Host's
        (the shipped business-cards declaration when none is given)."""
        memory = MemoryService.for_actor(
            workspace_root, actor, registry if registry is not None else default_registry()
        )
        return cls(memory, legacy=store_dir(workspace_root, actor) / DB_FILE)

    @contextmanager
    def _connect(self) -> Iterator[SpaceTx]:
        """One transaction on the space; a Memory Service refusal becomes the
        store's own, by code."""
        try:
            with self._space.transaction() as tx:
                yield tx
        except MemoryServiceError as error:
            raise CardStoreError(error.code) from error

    # -- lookups -------------------------------------------------------

    @staticmethod
    def _people(tx: SpaceTx) -> list[sqlite3.Row]:
        return list(tx.con.execute(f"SELECT * FROM {PEOPLE} ORDER BY created_at, person_id"))

    @staticmethod
    def _person(tx: SpaceTx, person_id: str) -> sqlite3.Row | None:
        found: sqlite3.Row | None = tx.con.execute(
            f"SELECT * FROM {PEOPLE} WHERE person_id = ?", (person_id,)
        ).fetchone()
        return found

    def _match(
        self, tx: SpaceTx, values: Mapping[str, str], source_ref: str = ""
    ) -> tuple[sqlite3.Row | None, str | None]:
        """Who a reading is (DECISIONS 2026-10-20 "How a card finds its person"):

        1. the same card image (`sha256:` ref) as an earlier observation: the
           person that observation was stored as;
        2. the same email (case-insensitive);
        3. the same name (local or romanised) at the same company. A different
           email does not make it someone else, unless their place differs too
           (both have a department, or a division, and they differ): two
           namesakes at one company are told apart only that way.
        """
        if source_ref.startswith("sha256:"):
            for seen in tx.observations(source_ref=source_ref, newest_first=True):
                row = None if seen.entity_id is None else self._person(tx, seen.entity_id)
                if row is not None:
                    return row, "image"
        email = names.email_key(values.get("email", ""))
        if email:
            row = tx.con.execute(f"SELECT * FROM {PEOPLE} WHERE email_key = ?", (email,)).fetchone()
            if row is not None:
                return row, "email"
        name, company = values.get("name", ""), values.get("company", "")
        romanised = values.get("romanised_name", "")
        if not (name or romanised) or not company:
            return None, None
        found: list[tuple[int, sqlite3.Row, str]] = []
        for row in self._people(tx):
            if not names.same_company(row["company"], company):
                continue
            other_email = bool(email and row["email_key"] and row["email_key"] != email)
            if other_email and _elsewhere(row, values):
                continue
            if name and names.same_name(row["name"], name):
                found.append((0 + 2 * other_email, row, "name_company"))
            elif (name and names.same_name(row["romanised_name"], name)) or (
                romanised
                and (
                    names.same_name(row["name"], romanised)
                    or names.same_name(row["romanised_name"], romanised)
                )
            ):
                found.append((1 + 2 * other_email, row, "romanised_name"))
        if not found:
            return None, None
        found.sort(key=lambda item: item[0])
        return found[0][1], found[0][2]

    def _companies(self, tx: SpaceTx) -> list[_Company]:
        """The stored companies, each spelling joined with the others that are
        the same company: the same name without legal suffixes, or the same
        alias (a romanised short name, or an email or website domain other
        than a public mail service)."""
        spellings: dict[str, _Company] = {}
        for row in self._people(tx):
            company = row["company"].strip()
            if not company:
                continue
            item = spellings.setdefault(company, _Company(company))
            item.people += 1
            item.aliases |= names.short_names(company)
            for value in (row["email"], row["website"]):
                alias = names.domain_alias(value) if value else ""
                if alias:
                    item.aliases.add(alias)
        groups: list[_Company] = []
        for item in spellings.values():
            joined = [
                group
                for group in groups
                if any(names.same_company(item.name, other) for other in group.spellings)
                or item.aliases & group.aliases
            ]
            merged = _Company(item.name, people=item.people, aliases=set(item.aliases))
            for group in joined:
                groups.remove(group)
                merged.absorb(group)
            groups.append(merged)
        return groups

    def _company_group(self, tx: SpaceTx, query: str) -> _Company | None:
        """The one stored company a query names, or None (unknown or
        ambiguous): by name without legal suffixes, then alias, then an
        unambiguous part of a name."""
        key = names.company_key(query)
        if not key:
            return None
        groups = self._companies(tx)

        def by_name(group: _Company) -> bool:
            return any(names.company_key(name) == key for name in group.spellings)

        def by_alias(group: _Company) -> bool:
            return key in group.aliases

        def by_part(group: _Company) -> bool:
            return len(key) >= 2 and any(key in names.company_key(name) for name in group.spellings)

        tests: tuple[Callable[[_Company], bool], ...] = (by_name, by_alias, by_part)
        for test in tests:
            hits = [group for group in groups if test(group)]
            if len(hits) == 1:
                return hits[0]
            if hits:
                return None
        return None

    def resolve_company(self, query: str) -> str:
        """The stored company a query names ("WNC", "啟碁" -> 啟碁科技股份有限公司),
        or "" when none or more than one."""
        with self._connect() as tx:
            group = self._company_group(tx, query)
            return "" if group is None else group.canonical()

    def _in_company(self, tx: SpaceTx, query: str) -> tuple[Callable[[sqlite3.Row], bool], str]:
        """Who belongs to the company a query names, and its canonical name;
        an unresolved query falls back to comparing names."""
        group = self._company_group(tx, query)
        if group is None:
            return (lambda row: names.same_company(row["company"], query)), ""
        members = set(group.spellings)
        return (lambda row: row["company"].strip() in members), group.canonical()

    def _resolve(self, tx: SpaceTx, ref: PersonRef) -> sqlite3.Row:
        if ref.person_id:
            row = self._person(tx, ref.person_id)
            if row is None:
                raise CardStoreError("person_unknown")
            return row
        if not ref.name.strip():
            raise CardStoreError("person_unspecified")
        hits = [
            row
            for row in self._people(tx)
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

    @staticmethod
    def _manager(tx: SpaceTx, person_id: str) -> sqlite3.Row | None:
        found: sqlite3.Row | None = tx.con.execute(
            f"SELECT l.*, p.name AS manager_name FROM {LINES} l "
            f"JOIN {PEOPLE} p ON p.person_id = l.manager_id "
            "WHERE l.person_id = ? AND l.removed_at IS NULL ORDER BY l.line_id DESC LIMIT 1",
            (person_id,),
        ).fetchone()
        return found

    def _needs(self, tx: SpaceTx, person_id: str) -> tuple[FieldName, ...]:
        """Fields any reading of this person flagged as uncertain that hold a
        value the person has not confirmed or set (source `user`), and fields
        with an open proposal (a reading that differs from the person's own
        value, or another email), whatever their source."""
        flagged: set[str] = set()
        for item in tx.observations(person_id):
            flagged.update(item.uncertain)
        sources = tx.provenance(person_id)
        proposed = {item["field"] for item in tx.proposals(person_id, limit=10_000)}
        return tuple(
            name
            for name in FIELDS
            if name in proposed
            or (name in flagged and name in sources and sources[name]["source_kind"] != "user")
        )

    def _open_proposals(
        self, tx: SpaceTx, person_id: str | None, limit: int = 200
    ) -> list[ProposalView]:
        """Open proposals, oldest first: one person's, or everyone's. `current`
        is the value stored now."""
        rows = tx.con.execute(
            "SELECT pr.proposal_id, pr.entity_id AS person_id, pr.field, pr.current, "
            "pr.proposed, pr.source_kind AS source, pr.observation_id, pr.created_at, p.* "
            f"FROM proposals pr JOIN {PEOPLE} p ON p.person_id = pr.entity_id "
            "WHERE pr.space = ? AND pr.state = 'open' AND (? IS NULL OR pr.entity_id = ?) "
            "ORDER BY pr.proposal_id LIMIT ?",
            (CONTACTS_ORG, person_id, person_id, limit),
        ).fetchall()
        found: list[ProposalView] = []
        for row in rows:
            name = row["field"]
            found.append(
                ProposalView(
                    field=name,
                    current=str(row[name]) if name in FIELDS else row["current"],
                    proposed=row["proposed"],
                    source=row["source"],
                    source_label=SOURCE_LABELS.get(row["source"], row["source"]),
                    proposal_id=row["proposal_id"],
                    observation_id=row["observation_id"],
                    person_id=row["person_id"],
                    name=row["name"],
                    company=row["company"],
                    created_at=row["created_at"],
                )
            )
        return found

    def proposals(self, ref: PersonRef | None, *, limit: int) -> tuple[list[ProposalView], str]:
        """Open proposals (one person's, or everyone's) and a sentence for the
        reply."""
        with self._connect() as tx:
            person_id = None if ref is None else self._resolve(tx, ref)["person_id"]
            found = self._open_proposals(tx, person_id, limit)
            return found, proposals_note(found)

    @staticmethod
    def _sighting_sources(tx: SpaceTx, person_id: str) -> list[sqlite3.Row]:
        """Source kind and date of each sighting of a person (not the
        person's own statements, which provenance names) and of each current
        value's provenance."""
        return list(
            tx.con.execute(
                "SELECT source_kind, source_date FROM observations WHERE space = ? "
                "AND entity_id = ? AND claim = 'fields' AND trust != 'user_stated' "
                "AND retracted_by = '' "
                "UNION ALL SELECT source_kind, source_date FROM field_sources "
                "WHERE space = ? AND entity_id = ?",
                (CONTACTS_ORG, person_id, CONTACTS_ORG, person_id),
            )
        )

    def _view(self, tx: SpaceTx, row: sqlite3.Row) -> PersonView:
        person_id = row["person_id"]
        sources = sorted({item["source_kind"] for item in self._sighting_sources(tx, person_id)})
        line = self._manager(tx, person_id)
        proposals = len(tx.proposals(person_id, limit=10_000))
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
            needs_confirmation=self._needs(tx, person_id),
            updated_at=row["updated_at"],
            status_label=STATUS_LABELS.get(row["status"], row["status"]),
            updated_at_local=local_time(row["updated_at"]),
        )

    # -- history -------------------------------------------------------

    def _set_field(
        self,
        tx: SpaceTx,
        change_id: str,
        actor: str,
        person: sqlite3.Row,
        name: FieldName,
        value: str,
        *,
        source: str,
        source_date: str,
        observation_id: int | None,
        reason: str,
        previous: sqlite3.Row | None,
        closed_proposals: Sequence[Mapping[str, Any]] = (),
        origin: str | None = None,
    ) -> FieldChange:
        person_id = person["person_id"]
        old = person[name]
        tx.con.execute(f"UPDATE {PEOPLE} SET {name} = ? WHERE person_id = ?", (value, person_id))
        if name == "email":
            tx.con.execute(
                f"UPDATE {PEOPLE} SET email_key = ? WHERE person_id = ?",
                (names.email_key(value), person_id),
            )
        tx.set_provenance(
            person_id,
            name,
            source_kind=source,
            source_date=source_date,
            observation_id=observation_id,
            set_by=actor,
            reason=reason,
            origin=origin,
        )
        tx.record(
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
                **tx.provenance_extra(previous),
                "closed_proposals": [dict(item) for item in closed_proposals],
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
        with self._connect() as tx:
            return self._add(
                tx,
                values,
                source=source,
                source_date=source_date,
                source_ref=source_ref,
                uncertain=uncertain,
                actor=actor,
            )

    def _add(
        self,
        tx: SpaceTx,
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
        row, matched_by = self._match(tx, clean, source_ref)
        differs: EmailDiffers | None = None
        stored_email = "" if row is None else row["email"]
        if (
            row is not None
            and clean["email"]
            and stored_email
            and names.email_key(stored_email) != names.email_key(clean["email"])
        ):
            # Matched by the image or by name + company, with another email:
            # one of the two readings is wrong. The stored email stays; unless
            # the person set or confirmed it, it needs confirmation (kept with
            # this observation's uncertain fields).
            differs = EmailDiffers(stored=stored_email, read=clean["email"])
            email_source = tx.provenance(row["person_id"]).get("email")
            if email_source is None or email_source["source_kind"] != "user":
                unsure = tuple(dict.fromkeys((*unsure, "email")))
        change_id = new_change_id()
        person_id = f"p-{secrets.token_hex(5)}" if row is None else row["person_id"]
        observation_id = tx.add_observation(
            person_id,
            clean,
            source_kind=source,
            source_date=when,
            source_ref=source_ref,
            uncertain=unsure,
            recorded_by=actor,
            change_id=change_id,
        )
        if row is None:
            stamp = _now()
            tx.con.execute(
                f"INSERT INTO {PEOPLE} (person_id, created_at, updated_at) VALUES (?,?,?)",
                (person_id, stamp, stamp),
            )
            tx.record(
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
                    tx.con.execute(
                        f"UPDATE {PEOPLE} SET {name} = ? WHERE person_id = ?",
                        (clean[name], person_id),
                    )
                    tx.set_provenance(
                        person_id,
                        name,
                        source_kind=source,
                        source_date=when,
                        observation_id=observation_id,
                        set_by=actor,
                    )
            tx.con.execute(
                f"UPDATE {PEOPLE} SET email_key = ? WHERE person_id = ?",
                (names.email_key(clean["email"]), person_id),
            )
            needs = self._needs(tx, person_id)
            return AddResult(
                person_id=person_id,
                name=clean["name"],
                company=clean["company"],
                outcome="created",
                existed=False,
                match=_match_summary(
                    "new", person_id, clean["name"], clean["company"], needs=needs
                ),
                uncertain=unsure,
                needs_confirmation=needs,
                to_confirm=self._to_confirm(tx, person_id, unsure),
                observation_id=observation_id,
                change_id=change_id,
            )
        merge = self._merge(
            tx,
            change_id,
            actor,
            row,
            clean,
            source=source,
            when=when,
            observation_id=observation_id,
            uncertain=unsure,
            email_differs=differs is not None,
        )
        moved = self._tidy_notes(tx, change_id, actor, person_id)
        if moved is not None:
            merge.changes.append(moved)
        if merge.changes:
            tx.con.execute(
                f"UPDATE {PEOPLE} SET updated_at = ? WHERE person_id = ?", (_now(), person_id)
            )
        fresh = self._person(tx, person_id)
        assert fresh is not None
        needs = self._needs(tx, person_id)
        return AddResult(
            person_id=person_id,
            name=fresh["name"],
            company=fresh["company"],
            outcome="updated" if merge.changes else "unchanged",
            existed=True,
            matched_by=matched_by,
            match=_match_summary(
                matched_by or "name_company",
                person_id,
                fresh["name"],
                fresh["company"],
                changed=[c.field for c in merge.changes if not _same(c.old, c.new)],
                kept=[k.field for k in merge.kept],
                needs=needs,
            ),
            changes=tuple(merge.changes),
            kept=tuple(merge.kept),
            uncertain=unsure,
            needs_confirmation=needs,
            to_confirm=self._to_confirm(tx, person_id, unsure),
            email_differs=differs,
            proposals=tuple(self._open_proposals(tx, person_id)),
            status=fresh["status"],
            summary=_summary(row, merge),
            observation_id=observation_id,
            change_id=change_id
            if merge.changes
            or any(item.reason in ("user_set", "email_differs") for item in merge.kept)
            else None,
        )

    def _merge(
        self,
        tx: SpaceTx,
        change_id: str,
        actor: str,
        row: sqlite3.Row,
        clean: dict[str, str],
        *,
        source: Source,
        when: str,
        observation_id: int,
        uncertain: Sequence[FieldName],
        email_differs: bool = False,
    ) -> _Merge:
        """A reading merged into the person: first what is particular to
        business cards (another spelling of the same company or name, a
        differing email, appended notes, a partial reading), then the space's
        merge rule (`SpaceTx.decide`): the person's own value is kept and the
        reading proposed; an uncertain or older reading is kept out."""
        merge = _Merge()
        person_id = row["person_id"]
        sources = tx.provenance(person_id)
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
            if not new or _same_value(name, current, new):
                continue
            # Another spelling of the same company or name (a legal suffix,
            # a romanisation) is not a change.
            if name == "company" and names.same_company(current, new):
                continue
            if name == "name" and names.same_name(current, new):
                continue
            previous = sources.get(name)
            user_set = previous is not None and previous["source_kind"] == "user"
            if name == "email" and email_differs and not user_set:
                # Never replaced automatically: a proposal, and the email needs
                # confirmation (a user-set email takes the user_set path below).
                merge.kept.append(
                    KeptField(field=name, current=current, offered=new, reason="email_differs")
                )
                self._propose(
                    tx, change_id, actor, person_id, name, current, new, source, observation_id
                )
                continue
            if name == "notes" and current:
                if new.casefold() in current.casefold():
                    continue
                new = f"{current}\n{new}"
            elif current and name not in _ANY_CHANGE and _less_complete(new, current):
                # "Connectivity & Solutions" after "Connectivity & Solutions
                # 事業群", "研展處" after "研展處 I": a partial reading, not a
                # conflict, even with the person's own value.
                merge.kept.append(
                    KeptField(field=name, current=current, offered=new, reason="less_complete")
                )
                continue
            else:
                # The space's rule: the person's own (set or confirmed) value,
                # also one they emptied, is never replaced by a scan, sure or
                # not; the reading is a proposal and the field needs
                # confirmation (third live test 2026-10-20). An uncertain or
                # older reading never replaces a value.
                verdict = tx.decide(
                    name,
                    current=current,
                    current_source=previous,
                    offered=new,
                    offered_kind=source,
                    offered_date=when,
                    uncertain=name in uncertain,
                    same=_same_as(name),
                )
                if verdict.action != "take":
                    reason = _KEPT_REASONS.get(verdict.reason, "uncertain")
                    merge.kept.append(
                        KeptField(
                            field=name,
                            current=current,
                            offered=new,
                            reason=reason,
                        )
                    )
                    if verdict.action == "propose":
                        self._propose(
                            tx,
                            change_id,
                            actor,
                            person_id,
                            name,
                            current,
                            new,
                            source,
                            observation_id,
                        )
                    continue
            merge.changes.append(
                self._set_field(
                    tx,
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

    def _tidy_notes(
        self, tx: SpaceTx, change_id: str, actor: str, person_id: str
    ) -> FieldChange | None:
        """A 「統一編號：…」 mention in the notes of the number now stored in
        `company_tax_id` (a note from before the field existed) is taken out
        of the notes, keeping the notes' source; recorded in history."""
        row = self._person(tx, person_id)
        assert row is not None
        tidied = reading.without_tax_id(row["notes"], row["company_tax_id"])
        if tidied == row["notes"]:
            return None
        previous = tx.provenance(person_id).get("notes")
        return self._set_field(
            tx,
            change_id,
            actor,
            row,
            "notes",
            tidied,
            source=previous["source_kind"] if previous is not None else "card",
            source_date=previous["source_date"] if previous is not None else _now()[:10],
            observation_id=previous["observation_id"] if previous is not None else None,
            reason="統一編號 moved to company_tax_id",
            previous=previous,
            origin=previous["origin"] or None if previous is not None else None,
        )

    def _propose(
        self,
        tx: SpaceTx,
        change_id: str,
        actor: str,
        person_id: str,
        name: str,
        current: str,
        new: str,
        source: str,
        observation_id: int,
    ) -> None:
        """An offered value that was not taken, kept as an open proposal; the
        same value already open is not proposed again."""
        tx.propose(
            change_id,
            actor,
            person_id,
            name,
            current,
            new,
            source_kind=source,
            observation_id=observation_id,
            same=_same_as(name),
        )

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
        accept: Sequence[FieldName] = (),
        outcome: EditOutcome | None = None,
    ) -> tuple[sqlite3.Row, list[FieldChange], list[FieldName], str | None]:
        """The person's own values (source `user`), the fields they say are
        right as stored, the fields they say are wrong (emptied, and kept
        empty) and the fields whose open proposal they take ("用新的").
        Re-stating the stored value confirms it and rejects the field's open
        proposals; the proposed value accepts them. What the person said is
        one `user` observation. `outcome`, when given, is filled with what
        happened to the proposals."""
        result = outcome if outcome is not None else EditOutcome()
        with self._connect() as tx:
            row = self._resolve(tx, ref)
            person_id = row["person_id"]
            change_id = new_change_id()
            sources = tx.provenance(person_id)
            needs = set(self._needs(tx, person_id))
            wanted = {name: str(values.get(name, "")).strip() for name in FIELDS}
            for name in dict.fromkeys(accept):
                newest = tx.proposals(person_id, field_name=name, newest_first=True, limit=1)
                if not newest:
                    raise CardStoreError("proposal_unknown")
                wanted[name] = newest[0]["proposed"]
            # What the person's words do to each field, decided on the store
            # as it was: a value set (or emptied), or the stored one confirmed.
            plan: list[tuple[FieldName, bool, str, list[sqlite3.Row]]] = []
            for name in FIELDS:
                new = wanted[name]
                emptied = name in clear and not new and bool(row[name])
                open_rows = tx.proposals(person_id, field_name=name, limit=10_000)
                if emptied or (new and not _same_value(name, row[name], new)):
                    plan.append((name, True, new, open_rows))
                    continue
                asked = name in confirm or (bool(new) and name in needs)
                previous = sources.get(name)
                if not asked or previous is None:
                    continue
                if not open_rows and (not row[name] or previous["source_kind"] == "user"):
                    if row[name] and name in confirm:
                        result.already_confirmed.append(name)
                    continue
                plan.append((name, False, row[name], open_rows))
            observation_id = (
                tx.add_observation(
                    person_id,
                    {name: value for name, _, value, _ in plan},
                    source_kind="user",
                    source_date=date.today().isoformat(),
                    recorded_by=actor,
                    change_id=change_id,
                )
                if plan
                else None
            )
            changes: list[FieldChange] = []
            confirmed: list[FieldName] = []
            today = date.today().isoformat()
            for name, setting, new, open_rows in plan:
                if setting:
                    closed = [
                        {
                            "id": item["proposal_id"],
                            "state": "accepted"
                            if new and _same_value(name, item["proposed"], new)
                            else "rejected",
                        }
                        for item in open_rows
                    ]
                    changes.append(
                        self._set_field(
                            tx,
                            change_id,
                            actor,
                            row,
                            name,
                            new,
                            source="user",
                            source_date=today,
                            observation_id=observation_id,
                            reason=reason or "set by the person",
                            previous=sources.get(name),
                            closed_proposals=closed,
                        )
                    )
                    for item in closed:
                        tx.set_proposal_state(int(item["id"]), str(item["state"]), actor=actor)
                    if any(item["state"] == "accepted" for item in closed):
                        result.accepted.append(name)
                    elif closed:
                        result.rejected.append(name)
                    continue
                # The stored value is right: kept as the person's own, and any
                # open proposal for the field is rejected.
                previous = sources[name]
                rejected = [item["proposal_id"] for item in open_rows]
                for proposal_id in rejected:
                    tx.set_proposal_state(int(proposal_id), "rejected", actor=actor)
                tx.set_provenance(
                    person_id,
                    name,
                    source_kind="user",
                    source_date=today,
                    observation_id=observation_id,
                    set_by=actor,
                    reason=reason or "confirmed by the person",
                )
                tx.record(
                    change_id,
                    actor,
                    person_id,
                    "confirm",
                    field_name=name,
                    old=row[name],
                    new=row[name],
                    reason=reason or "confirmed by the person",
                    source="user",
                    extra={**tx.provenance_extra(previous), "rejected_proposals": rejected},
                )
                confirmed.append(name)
                if rejected:
                    result.rejected.append(name)
            moved = self._tidy_notes(tx, change_id, actor, person_id)
            if moved is not None:
                changes.append(moved)
            if changes or confirmed:
                tx.con.execute(
                    f"UPDATE {PEOPLE} SET updated_at = ? WHERE person_id = ?",
                    (_now(), person_id),
                )
            fresh = self._person(tx, person_id)
            assert fresh is not None
            return fresh, changes, confirmed, change_id if changes or confirmed else None

    def needs_confirmation(self, person_id: str) -> tuple[FieldName, ...]:
        with self._connect() as tx:
            return self._needs(tx, person_id)

    def to_confirm(self, person_id: str, also: Sequence[FieldName] = ()) -> tuple[ToConfirm, ...]:
        with self._connect() as tx:
            return self._to_confirm(tx, person_id, also)

    def _to_confirm(
        self, tx: SpaceTx, person_id: str, also: Sequence[FieldName] = ()
    ) -> tuple[ToConfirm, ...]:
        """The fields to ask about (still to confirm, and `also`), each with
        the value stored now."""
        row = self._person(tx, person_id)
        if row is None:
            return ()
        wanted = set(self._needs(tx, person_id)) | set(also)
        return tuple(ToConfirm(field=name, stored=row[name]) for name in FIELDS if name in wanted)

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
        with self._connect() as tx:
            row = self._resolve(tx, ref)
            old = row["status"]
            left_at = (effective or date.today()).isoformat() if status == "left" else ""
            if old == status and row["left_at"] == left_at:
                return row, old, status, None
            change_id = new_change_id()
            tx.add_observation(
                row["person_id"],
                {"status": status, "left_at": left_at, "reason": reason},
                source_kind="user",
                source_date=date.today().isoformat(),
                recorded_by=actor,
                change_id=change_id,
                claim="status",
            )
            tx.con.execute(
                f"UPDATE {PEOPLE} SET status = ?, left_at = ?, status_set_by = ?, "
                "status_reason = ?, updated_at = ? WHERE person_id = ?",
                (status, left_at, actor, reason, _now(), row["person_id"]),
            )
            tx.record(
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
            fresh = self._person(tx, row["person_id"])
            assert fresh is not None
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
        """A reporting line with its evidence, kept as an observation. It is
        solid only on the person's word or explicit evidence (the space's
        rule); any other line is an inference, drawn dashed."""
        with self._connect() as tx:
            row = self._resolve(tx, person)
            boss = self._resolve(tx, manager)
            if row["person_id"] == boss["person_id"]:
                raise CardStoreError("line_to_self")
            if self._reaches(tx, boss["person_id"], row["person_id"]):
                raise CardStoreError("line_cycle")
            inferred = inferred or not tx.solid(REPORTING_LINE, evidence_kind)
            change_id = new_change_id()
            observation_id = tx.add_observation(
                row["person_id"],
                {"relation": REPORTING_LINE, "manager_id": boss["person_id"]},
                source_kind=evidence_kind,
                source_date=date.today().isoformat(),
                source_ref=evidence_ref,
                recorded_by=actor,
                change_id=change_id,
                claim="relation",
            )
            current = self._manager(tx, row["person_id"])
            if current is not None:
                self._remove_line(tx, change_id, actor, current, "replaced by a new line")
            cursor = tx.con.execute(
                f"INSERT INTO {LINES} (person_id, manager_id, evidence_kind, evidence_ref, "
                "confidence, inferred, created_at, created_by, observation_id) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    row["person_id"],
                    boss["person_id"],
                    evidence_kind,
                    evidence_ref,
                    confidence,
                    1 if inferred else 0,
                    _now(),
                    actor,
                    observation_id,
                ),
            )
            tx.record(
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

    def _reaches(self, tx: SpaceTx, start: str, target: str) -> bool:
        """Whether `start`'s chain of managers reaches `target`."""
        seen: set[str] = set()
        node = start
        while node not in seen:
            seen.add(node)
            if node == target:
                return True
            line = self._manager(tx, node)
            if line is None:
                return False
            node = line["manager_id"]
        return False

    def _remove_line(
        self, tx: SpaceTx, change_id: str, actor: str, line: sqlite3.Row, reason: str
    ) -> None:
        tx.con.execute(
            f"UPDATE {LINES} SET removed_at = ?, removed_by = ?, removed_reason = ? "
            "WHERE line_id = ?",
            (_now(), actor, reason, line["line_id"]),
        )
        tx.record(
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
        with self._connect() as tx:
            row = self._resolve(tx, person)
            current = self._manager(tx, row["person_id"])
            if current is None:
                return row, None, None
            change_id = new_change_id()
            tx.add_observation(
                row["person_id"],
                {
                    "relation": REPORTING_LINE,
                    "manager_id": "",
                    "removed_line": str(current["line_id"]),
                },
                source_kind="user",
                source_date=date.today().isoformat(),
                recorded_by=actor,
                change_id=change_id,
                claim="relation",
            )
            self._remove_line(tx, change_id, actor, current, reason or "removed by the person")
            return row, current, change_id

    # -- undo ----------------------------------------------------------

    def undo(self, change_id: str, *, actor: str) -> tuple[list[HistoryItem], str | None]:
        """Revert one change group, newest row first, as a new change. Refused
        when a later change touched the same values (`undo_conflict`)."""

        def create(tx: SpaceTx, item: sqlite3.Row, extra: dict[str, Any], new: str) -> bool:
            pid = item["entity_id"]
            if self._person(tx, pid) is None:
                return False
            if tx.changed_since(pid, change_id):
                raise CardStoreError("undo_conflict")
            tx.con.execute(f"DELETE FROM {PEOPLE} WHERE person_id = ?", (pid,))
            tx.forget_entity(pid, new)
            tx.con.execute(
                f"UPDATE {LINES} SET removed_at = ?, removed_by = ?, "
                "removed_reason = 'undo' WHERE (person_id = ? OR manager_id = ?) "
                "AND removed_at IS NULL",
                (_now(), actor, pid, pid),
            )
            tx.record(new, actor, pid, "delete", old=item["new"], reason=f"undo {change_id}")
            return True

        def field_row(tx: SpaceTx, item: sqlite3.Row, extra: dict[str, Any], new: str) -> bool:
            pid, name = item["entity_id"], item["field"]
            person = self._person(tx, pid)
            if person is None or not _same(person[name], item["new"]):
                raise CardStoreError("undo_conflict")
            tx.con.execute(
                f"UPDATE {PEOPLE} SET {name} = ?, updated_at = ? WHERE person_id = ?",
                (item["old"], _now(), pid),
            )
            if name == "email":
                tx.con.execute(
                    f"UPDATE {PEOPLE} SET email_key = ? WHERE person_id = ?",
                    (names.email_key(item["old"]), pid),
                )
            tx.restore_provenance(pid, name, extra)
            tx.reopen([entry["id"] for entry in extra.get("closed_proposals") or ()])
            tx.record(
                new,
                actor,
                pid,
                "field",
                field_name=name,
                old=item["new"],
                new=item["old"],
                reason=f"undo {change_id}",
                source="user",
            )
            return True

        def status(tx: SpaceTx, item: sqlite3.Row, extra: dict[str, Any], new: str) -> bool:
            pid = item["entity_id"]
            person = self._person(tx, pid)
            if person is None or person["status"] != item["new"]:
                raise CardStoreError("undo_conflict")
            tx.con.execute(
                f"UPDATE {PEOPLE} SET status = ?, left_at = ?, status_set_by = ?, "
                "status_reason = ?, updated_at = ? WHERE person_id = ?",
                (
                    item["old"],
                    extra.get("prev_left_at") or "",
                    extra.get("prev_set_by") or "",
                    extra.get("prev_reason") or "",
                    _now(),
                    pid,
                ),
            )
            tx.record(
                new,
                actor,
                pid,
                "status",
                field_name="status",
                old=item["new"],
                new=item["old"],
                reason=f"undo {change_id}",
                source="user",
            )
            return True

        def line_add(tx: SpaceTx, item: sqlite3.Row, extra: dict[str, Any], new: str) -> bool:
            tx.con.execute(
                f"UPDATE {LINES} SET removed_at = ?, removed_by = ?, "
                "removed_reason = ? WHERE line_id = ? AND removed_at IS NULL",
                (_now(), actor, f"undo {change_id}", extra.get("line_id")),
            )
            tx.record(
                new,
                actor,
                item["entity_id"],
                "line_remove",
                field_name="manager",
                old=item["new"],
                reason=f"undo {change_id}",
                source="user",
                extra={"line_id": extra.get("line_id")},
            )
            return True

        def line_remove(tx: SpaceTx, item: sqlite3.Row, extra: dict[str, Any], new: str) -> bool:
            tx.con.execute(
                f"UPDATE {LINES} SET removed_at = NULL, removed_by = NULL, "
                "removed_reason = NULL WHERE line_id = ?",
                (extra.get("line_id"),),
            )
            tx.record(
                new,
                actor,
                item["entity_id"],
                "line_add",
                field_name="manager",
                new=item["old"],
                reason=f"undo {change_id}",
                source="user",
                extra={"line_id": extra.get("line_id")},
            )
            return True

        def confirm(tx: SpaceTx, item: sqlite3.Row, extra: dict[str, Any], new: str) -> bool:
            pid = item["entity_id"]
            if self._person(tx, pid) is None:
                return False
            tx.restore_provenance(pid, item["field"], extra, fallback_kind="card")
            tx.reopen(extra.get("rejected_proposals") or ())
            tx.record(
                new,
                actor,
                pid,
                "unconfirm",
                field_name=item["field"],
                old=item["new"],
                new=item["new"],
                reason=f"undo {change_id}",
                source=extra.get("prev_source") or "",
            )
            return True

        handlers = {
            "create": create,
            "field": field_row,
            "status": status,
            "line_add": line_add,
            "line_remove": line_remove,
            "confirm": confirm,
        }
        with self._connect() as tx:
            rows, new_change = tx.undo(change_id, actor=actor, handlers=handlers)
            return [_history_item(item) for item in rows], new_change

    # -- reading -------------------------------------------------------

    def find(self, query: str, *, status: str, limit: int) -> tuple[list[PersonView], int]:
        words = names.search_text(query).split()
        romanised = names.name_keys(query)
        with self._connect() as tx:
            group = self._company_group(tx, query)
            members = set() if group is None else set(group.spellings)
            hits = []
            for row in self._people(tx):
                if status != "any" and row["status"] != status:
                    continue
                if row["company"].strip() in members:
                    hits.append(row)
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
            return [self._view(tx, row) for row in hits[:limit]], len(hits)

    def list_people(
        self, *, company: str, source: str, status: str, limit: int
    ) -> tuple[list[PersonView], int]:
        with self._connect() as tx:
            member, _ = self._in_company(tx, company)
            hits = []
            for row in self._people(tx):
                if status != "any" and row["status"] != status:
                    continue
                if company and not member(row):
                    continue
                if source and not any(
                    item["source_kind"] == source
                    for item in self._sighting_sources(tx, row["person_id"])
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
            return [self._view(tx, row) for row in hits[:limit]], len(hits)

    def history(self, ref: PersonRef, *, limit: int) -> HistoryResult:
        """A person's changes and sightings; the person's own statements
        are in the changes, not among the sightings."""
        with self._connect() as tx:
            row = self._resolve(tx, ref)
            pid = row["person_id"]
            items = [_history_item(item) for item in tx.history(pid, limit=limit)]
            observations = [
                ObservationView(
                    observation_id=item["observation_id"],
                    source=item["source_kind"],
                    source_date=item["source_date"],
                    source_ref=item["source_ref"],
                    uncertain=tuple(json.loads(item["uncertain_json"] or "[]")),
                    source_label=SOURCE_LABELS.get(item["source_kind"], item["source_kind"]),
                )
                for item in tx.con.execute(
                    "SELECT * FROM observations WHERE space = ? AND entity_id = ? "
                    "AND claim = 'fields' AND trust != 'user_stated' AND retracted_by = '' "
                    "ORDER BY observation_id DESC LIMIT ?",
                    (CONTACTS_ORG, pid, limit),
                )
            ]
            proposals = self._open_proposals(tx, pid)
            return HistoryResult(
                person=self._view(tx, row),
                history=tuple(items),
                observations=tuple(observations),
                proposals=tuple(proposals),
            )

    def view(self, person_id: str) -> PersonView:
        with self._connect() as tx:
            row = self._person(tx, person_id)
            if row is None:
                raise CardStoreError("person_unknown")
            return self._view(tx, row)

    def preview(self, values: Mapping[str, str]) -> tuple[str, tuple[FieldName, ...]]:
        """Who these fields would merge into and which fields would change;
        nothing is written."""
        clean: dict[str, str] = {name: str(values.get(name, "")).strip() for name in FIELDS}
        with self._connect() as tx:
            row, _ = self._match(tx, clean)
            if row is None:
                return "", ()
            return row["person_id"], tuple(
                name
                for name in FIELDS
                if clean[name] and not _same_value(name, row[name], clean[name])
            )

    def chart_data(
        self, company: str, *, include_left: bool
    ) -> tuple[list[sqlite3.Row], list[sqlite3.Row], int]:
        """People of a company (and how many who left were left out) and the
        active lines between them."""
        with self._connect() as tx:
            member, _ = self._in_company(tx, company)
            everyone = [row for row in self._people(tx) if member(row)]
            shown = [row for row in everyone if include_left or row["status"] != "left"]
            ids = {row["person_id"] for row in shown}
            lines = [
                line
                for line in tx.con.execute(
                    f"SELECT * FROM {LINES} WHERE removed_at IS NULL ORDER BY line_id"
                )
                if line["person_id"] in ids and line["manager_id"] in ids
            ]
            return shown, lines, len(everyone) - len(shown)

    def sources_seen(self, person_ids: Sequence[str]) -> dict[str, list[tuple[str, str]]]:
        """Each person's sources with the latest evidence date of each
        (observations and field provenance), newest first: the interactive
        chart's person card lists them."""
        found: dict[str, list[tuple[str, str]]] = {}
        with self._connect() as tx:
            for person_id in person_ids:
                latest: dict[str, str] = {}
                for item in self._sighting_sources(tx, person_id):
                    seen = str(item["source_date"] or "")
                    if seen > latest.get(item["source_kind"], ""):
                        latest[item["source_kind"]] = seen
                    latest.setdefault(item["source_kind"], seen)
                found[person_id] = sorted(latest.items(), key=lambda pair: pair[1], reverse=True)
        return found

    def uncertain_now(self, person_ids: Sequence[str]) -> dict[str, list[str]]:
        """Each person's fields still to confirm: flagged by any reading and
        neither confirmed nor set by the person."""
        found: dict[str, list[str]] = {}
        with self._connect() as tx:
            for person_id in person_ids:
                needs = self._needs(tx, person_id)
                if needs:
                    found[person_id] = list(needs)
        return found

    # -- signature candidates -----------------------------------------

    def keep_candidates(
        self, session_key: str, candidates: Sequence[Mapping[str, Any]]
    ) -> tuple[list[str], str]:
        """A harvest's candidates for this conversation, replacing its earlier
        set, with short ids ("s1", ...) in order, and when they expire. Each
        keeps fields, uncertain, message id and date; never a body. Expired
        candidates of any conversation are removed."""
        now = _clock()
        expires = (now + CANDIDATE_TTL).isoformat(timespec="seconds")
        ids: list[str] = []
        with self._connect() as tx:
            con = tx.con
            con.execute(f"DELETE FROM {CANDIDATES} WHERE expires_at <= ?", (_iso(now),))
            con.execute(f"DELETE FROM {CANDIDATES} WHERE session_key = ?", (session_key,))
            for number, item in enumerate(candidates, 1):
                candidate_id = f"s{number}"
                con.execute(
                    f"INSERT INTO {CANDIDATES} (session_key, candidate_id, fields_json, "
                    "uncertain_json, message_id, message_date, created_at, expires_at) "
                    "VALUES (?,?,?,?,?,?,?,?)",
                    (
                        session_key,
                        candidate_id,
                        json.dumps(
                            {name: str(item.get(name, "")) for name in FIELDS}, ensure_ascii=False
                        ),
                        json.dumps(list(item.get("uncertain", ()))),
                        str(item["message_id"]),
                        str(item["message_date"]),
                        _iso(now),
                        expires,
                    ),
                )
                ids.append(candidate_id)
        return ids, expires

    def store_candidates(
        self, session_key: str, wanted: Sequence[str], *, actor: str
    ) -> tuple[list[AddResult], list[str], list[str], list[str]]:
        """This conversation's candidates by id (or `all`), stored with source
        `email_signature`, their message id and date, oldest first. Returns
        the results, and which ids were stored, already stored or unknown.
        `candidates_expired` when the conversation has none left."""
        now = _iso(_clock())
        with self._connect() as tx:
            rows = {
                row["candidate_id"]: row
                for row in tx.con.execute(
                    f"SELECT * FROM {CANDIDATES} WHERE session_key = ? AND expires_at > ?",
                    (session_key, now),
                )
            }
            if not rows:
                raise CardStoreError("candidates_expired")
            asked = [item.strip() for item in wanted if item.strip()]
            if any(item.casefold() == ALL_CANDIDATES for item in asked):
                asked = list(rows)
            chosen = [rows[item] for item in dict.fromkeys(asked) if item in rows]
            unknown = [item for item in dict.fromkeys(asked) if item not in rows]
            already = [row["candidate_id"] for row in chosen if row["stored_person_id"]]
            pending = sorted(
                (row for row in chosen if not row["stored_person_id"]),
                key=lambda row: (row["message_date"], row["candidate_id"]),
            )
            results: list[AddResult] = []
            for row in pending:
                result = self._add(
                    tx,
                    json.loads(row["fields_json"]),
                    source="email_signature",
                    source_date=date.fromisoformat(row["message_date"]),
                    source_ref=row["message_id"],
                    uncertain=[u for u in json.loads(row["uncertain_json"]) if u in FIELDS],
                    actor=actor,
                )
                tx.con.execute(
                    f"UPDATE {CANDIDATES} SET stored_person_id = ? "
                    "WHERE session_key = ? AND candidate_id = ?",
                    (result.person_id, session_key, row["candidate_id"]),
                )
                results.append(result)
            return results, [row["candidate_id"] for row in pending], already, unknown

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
        with self._connect() as tx:
            for item in rows:
                keys = item.keys()
                ref = f"hermes-cards:{item['id']}"
                if tx.observations(source_ref=ref, claim=None, limit=1):
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
                        tx,
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


@dataclass
class EditOutcome:
    """What an edit did to the open proposals, and what was asked to be
    confirmed that already was the person's own value."""

    accepted: list[FieldName] = field(default_factory=list)
    rejected: list[FieldName] = field(default_factory=list)
    already_confirmed: list[FieldName] = field(default_factory=list)


def proposals_note(found: Sequence[ProposalView]) -> str:
    """One sentence about the open proposals, for the reply."""
    if not found:
        return "目前沒有待確認的項目。"
    items = "；".join(
        f"{item.name} 的 {item.label}（名片夾：{item.current or '（空白）'}；"
        f"這次讀到：{item.proposed}）"
        for item in found
    )
    return (
        f"目前有 {len(found)} 項待確認：{items}。"
        "說「<姓名> 的 <欄位> 正確」保留名片夾的值，或說「用新的」改成讀到的值。"
    )


def _iso(moment: datetime) -> str:
    return moment.isoformat(timespec="seconds")


def local_time(value: str) -> str:
    """An ISO instant as Asia/Taipei time to the minute ("2026-10-20 14:03");
    the text unchanged when it is not a time."""
    try:
        moment = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return value
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return moment.astimezone(LOCAL_ZONE).strftime("%Y-%m-%d %H:%M")


#: Names of the non-field values a history row can carry.
_ROW_FIELDS = {"status": "在職狀態", "manager": "主管"}


def _history_item(row: sqlite3.Row) -> HistoryItem:
    kind, name = row["kind"], row["field"]

    def display(value: str) -> str:
        return STATUS_LABELS.get(value, value) if name == "status" else value

    return HistoryItem(
        change_id=row["change_id"],
        at=row["at"],
        actor=row["actor"],
        kind=kind,
        field=name,
        old=row["old"],
        new=row["new"],
        reason=row["reason"],
        source=row["source"],
        at_local=local_time(row["at"]),
        kind_label=KIND_LABELS.get(kind, kind),
        field_label=_LABELS.get(name) or _ROW_FIELDS.get(name, name),
        source_label=SOURCE_LABELS.get(row["source"], row["source"]),
        old_display=display(row["old"]),
        new_display=display(row["new"]),
    )


def undo_note(reverted: Sequence[HistoryItem]) -> str:
    """One sentence about what an undo reverted, without change ids."""
    if not reverted:
        return "這個變更沒有需要復原的內容。"
    parts = "、".join(
        item.kind_label
        if not item.field_label or item.field_label == item.kind_label
        else f"{item.kind_label}（{item.field_label}）"
        for item in reverted
    )
    return f"已復原 {len(reverted)} 項：{parts}。"


def _match_summary(
    by: str,
    person_id: str,
    name: str,
    company: str,
    *,
    changed: Sequence[str] = (),
    kept: Sequence[str] = (),
    needs: Sequence[str] = (),
) -> MatchSummary:
    """Whom a reading was stored as, with the sentence the reply opens with."""
    who = f"{name}（{company}）" if company else name
    label = MATCH_LABELS.get(by, by)
    lead = f"已新增聯絡人 {who}。" if by == "new" else f"已對到既有聯絡人 {who}，依{label}比對。"
    return MatchSummary.model_validate(
        {
            "by": by,
            "by_label": label,
            "person_id": person_id,
            "name": name,
            "company": company,
            "lead": lead,
            "changed": [_LABELS[item] for item in dict.fromkeys(changed)],
            "kept": [_LABELS[item] for item in dict.fromkeys(kept)],
            "needs_confirmation": [_LABELS[item] for item in dict.fromkeys(needs)],
        }
    )


def _summary(before: sqlite3.Row, merge: _Merge) -> str:
    """The sentence a reply leads with when the person was already on file:
    what changed, then each value read that differs from the person's own
    (or another email), kept and asked about."""
    differ = [
        f"這次讀到的{_LABELS[item.field]}（{item.offered}）和名片夾裡的"
        f"（{item.current or '空白'}）不同"
        for item in merge.kept
        if item.reason in ("user_set", "email_differs")
    ]
    note = "；".join(differ) + "，已保留原本的，請確認哪一個正確。" if differ else ""
    return _changes_sentence(before, merge) + note


def _changes_sentence(before: sqlite3.Row, merge: _Merge) -> str:
    """Only what changed: never 「上次是X，現在是X」 (live re-test 2026-10-20)."""
    changes = [c for c in merge.changes if not _same(c.old, c.new)]
    if not changes:
        return "已在名片夾中，資料沒有變。" if not merge.kept else ""
    changed = {change.field for change in changes}
    parts: list[str] = []
    if changed & set(ORG_FIELDS):
        old: dict[str, str] = {name: before[name] for name in ORG_FIELDS}
        new = dict(old)
        for change in changes:
            new[change.field] = change.new
        was, now = old["company"] + _describe(old), new["company"] + _describe(new)
        if "company" in changed:
            parts.append(f"上次是{was}, 現在是{now}")
        elif not _same(_describe(old), _describe(new)):
            parts.append(f"上次是{_describe(old) or '（未標示）'}, 現在是{_describe(new)}")
        else:
            # The department and title read the same: name the field itself.
            parts.extend(
                f"{_LABELS[c.field]}：上次是{c.old or '（未標示）'}，現在是{c.new or '（空白）'}"
                for c in changes
                if c.field in ORG_FIELDS
            )
    other = [c for c in changes if c.field not in ORG_FIELDS and c.field != "notes"]
    if other:
        # Never a dangling 也 when nothing came before (third live test 2026-10-20).
        listed = "、".join(_LABELS[c.field] for c in other)
        parts.append(f"{listed} 也更新了" if parts else f"更新了{listed}")
    return "；".join(parts) + "。" if parts else ""
