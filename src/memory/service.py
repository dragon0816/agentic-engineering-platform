"""The Memory Service: one SQLite file per actor on this Host
(docs/phases/ACCUMULATED_MEMORY.md §3.2–§3.5).

`<workspace>/memory/<actor-key>/memory.sqlite` holds every space of one
actor: the registry of spaces, and the facilities every space shares,
extracted from the business-cards store where they were proven:

- `observations`: append-only claims (source kind, source ref, date, trust
  class). A trigger refuses any delete and any update other than retracting
  one (an undone statement, an entity whose creation was undone);
- `field_sources`: the provenance of each current value (ADR-K11);
- `history` in change groups, `undone`, and `undo` that replays a group
  backwards as a new change;
- `proposals`: offered values the merge rules did not take;
- `external_ids`: the mapping of other systems' ids to entities (§3.8.4);
- `sync_state` (M2, §3.3): how far each source was processed for a key, for a
  space that declares the `sync_state` kind, with `sync_history` rows for
  every advance, reset and restore.

A space's own tables (a manager's current-value view, its relationships)
are named after the space (`contacts_org__people`). Access goes through a
`MemorySpace` handle opened for one asset: reads need a reader declaration,
writes a contributor declaration, and the manager alone reaches the space's
own tables. Who made a change (`set_by`, `recorded_by`, `actor`) is always
what the Host knows from the request (`<actor> via <channel>`), never a model
argument. Nothing here reaches the network.
"""

from __future__ import annotations

import hashlib
import json
import re
import secrets
import sqlite3
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import closing, contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from common.assets import AssetIdentity
from common.memory import (
    MAX_SYNC_IDS,
    Decision,
    FieldProvenance,
    MemoryRole,
    MemorySpaceDeclaration,
    MergeRules,
    SpaceSummary,
    SyncHistoryEntry,
    SyncState,
    origin_for,
)
from memory import merge
from memory.registry import AssetKey, MemoryRegistry, asset_key, asset_label

MEMORY_FOLDER = "memory"
DB_FILE = "memory.sqlite"
SCHEMA_VERSION = "1"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS spaces (
    space TEXT PRIMARY KEY,
    manager TEXT NOT NULL,
    table_prefix TEXT NOT NULL UNIQUE,
    declaration_json TEXT NOT NULL,
    rules_json TEXT NOT NULL,
    registered_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS observations (
    observation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    space TEXT NOT NULL,
    entity_id TEXT,
    claim TEXT NOT NULL DEFAULT 'fields',
    source_kind TEXT NOT NULL,
    trust TEXT NOT NULL,
    source_date TEXT NOT NULL,
    source_ref TEXT NOT NULL DEFAULT '',
    fields_json TEXT NOT NULL,
    uncertain_json TEXT NOT NULL DEFAULT '[]',
    recorded_at TEXT NOT NULL,
    recorded_by TEXT NOT NULL,
    contributor TEXT NOT NULL DEFAULT '',
    change_id TEXT NOT NULL DEFAULT '',
    retracted_by TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS observations_entity ON observations(space, entity_id);
CREATE INDEX IF NOT EXISTS observations_ref ON observations(space, source_ref);
CREATE TRIGGER IF NOT EXISTS observations_never_deleted BEFORE DELETE ON observations
BEGIN
    SELECT RAISE(ABORT, 'memory_observation_append_only');
END;
CREATE TRIGGER IF NOT EXISTS observations_only_retracted BEFORE UPDATE ON observations
WHEN NOT (
    OLD.retracted_by = '' AND NEW.retracted_by <> ''
    AND NEW.observation_id = OLD.observation_id AND NEW.space = OLD.space
    AND NEW.entity_id IS OLD.entity_id AND NEW.claim = OLD.claim
    AND NEW.source_kind = OLD.source_kind AND NEW.trust = OLD.trust
    AND NEW.source_date = OLD.source_date AND NEW.source_ref = OLD.source_ref
    AND NEW.fields_json = OLD.fields_json AND NEW.uncertain_json = OLD.uncertain_json
    AND NEW.recorded_at = OLD.recorded_at AND NEW.recorded_by = OLD.recorded_by
    AND NEW.contributor = OLD.contributor AND NEW.change_id = OLD.change_id
)
BEGIN
    SELECT RAISE(ABORT, 'memory_observation_append_only');
END;
CREATE TABLE IF NOT EXISTS field_sources (
    space TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    field TEXT NOT NULL,
    source_kind TEXT NOT NULL,
    source_date TEXT NOT NULL,
    observation_id INTEGER,
    origin TEXT NOT NULL DEFAULT '',
    set_by TEXT NOT NULL DEFAULT '',
    set_at TEXT NOT NULL DEFAULT '',
    reason TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (space, entity_id, field)
);
CREATE TABLE IF NOT EXISTS history (
    history_id INTEGER PRIMARY KEY AUTOINCREMENT,
    space TEXT NOT NULL,
    change_id TEXT NOT NULL,
    at TEXT NOT NULL,
    actor TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    field TEXT NOT NULL DEFAULT '',
    old TEXT NOT NULL DEFAULT '',
    new TEXT NOT NULL DEFAULT '',
    reason TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT '',
    extra_json TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS history_change ON history(change_id);
CREATE INDEX IF NOT EXISTS history_entity ON history(space, entity_id);
CREATE TABLE IF NOT EXISTS undone (
    change_id TEXT PRIMARY KEY,
    space TEXT NOT NULL,
    undone_by TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS proposals (
    proposal_id INTEGER PRIMARY KEY AUTOINCREMENT,
    space TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    field TEXT NOT NULL,
    current TEXT NOT NULL,
    proposed TEXT NOT NULL,
    source_kind TEXT NOT NULL,
    observation_id INTEGER,
    created_at TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'open',
    decided_at TEXT NOT NULL DEFAULT '',
    decided_by TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS proposals_entity ON proposals(space, entity_id, state);
CREATE TABLE IF NOT EXISTS external_ids (
    space TEXT NOT NULL,
    system TEXT NOT NULL,
    external_id TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    created_by TEXT NOT NULL,
    PRIMARY KEY (space, system, external_id)
);
CREATE INDEX IF NOT EXISTS external_ids_entity ON external_ids(space, entity_id);
CREATE TABLE IF NOT EXISTS sync_state (
    space TEXT NOT NULL,
    source TEXT NOT NULL,
    key TEXT NOT NULL,
    last_message_date TEXT NOT NULL,
    last_message_ids_json TEXT NOT NULL DEFAULT '[]',
    extractor_version TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL,
    updated_by TEXT NOT NULL,
    PRIMARY KEY (space, source, key)
);
CREATE TABLE IF NOT EXISTS sync_history (
    history_id INTEGER PRIMARY KEY AUTOINCREMENT,
    space TEXT NOT NULL,
    source TEXT NOT NULL,
    key TEXT NOT NULL,
    action TEXT NOT NULL,
    at TEXT NOT NULL,
    actor TEXT NOT NULL,
    reason TEXT NOT NULL DEFAULT '',
    old_json TEXT,
    new_json TEXT
);
CREATE INDEX IF NOT EXISTS sync_history_key ON sync_history(space, source, key);
"""

#: States a proposal moves between; `open` until the person decides.
PROPOSAL_STATES = frozenset({"open", "accepted", "rejected", "dismissed"})
_TABLE = re.compile(r"^[a-z][a-z0-9_]*$")


class MemoryServiceError(Exception):
    """A refusal by code; never carries the data."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class MemoryAccessError(MemoryServiceError):
    """An asset reached a space it did not declare (or not for this)."""


def actor_key(actor: str) -> str:
    """A file-safe folder name for one actor; a hash keeps two actors apart
    even when their safe names coincide."""
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", actor)[:40] or "actor"
    return f"{safe}-{hashlib.sha256(actor.encode('utf-8')).hexdigest()[:8]}"


def memory_path(workspace_root: Path, actor: str) -> Path:
    return workspace_root / MEMORY_FOLDER / actor_key(actor) / DB_FILE


def table_prefix(space: str) -> str:
    """`contacts/org` -> `contacts_org__`."""
    return re.sub(r"[^a-z0-9]", "_", space) + "__"


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def new_change_id() -> str:
    return f"c-{datetime.now(UTC):%Y%m%d%H%M%S}-{secrets.token_hex(3)}"


@dataclass(frozen=True)
class Observation:
    """One claim as stored."""

    observation_id: int
    entity_id: str | None
    claim: str
    source_kind: str
    trust: str
    source_date: str
    source_ref: str
    fields: Mapping[str, str]
    uncertain: tuple[str, ...]
    recorded_at: str
    recorded_by: str
    contributor: str
    change_id: str
    retracted_by: str

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> Observation:
        return cls(
            observation_id=int(row["observation_id"]),
            entity_id=row["entity_id"],
            claim=row["claim"],
            source_kind=row["source_kind"],
            trust=row["trust"],
            source_date=row["source_date"],
            source_ref=row["source_ref"],
            fields=json.loads(row["fields_json"] or "{}"),
            uncertain=tuple(json.loads(row["uncertain_json"] or "[]")),
            recorded_at=row["recorded_at"],
            recorded_by=row["recorded_by"],
            contributor=row["contributor"],
            change_id=row["change_id"],
            retracted_by=row["retracted_by"],
        )


#: Reverts one history row inside `SpaceTx.undo`: (transaction, row, its
#: extra, the new change id) -> whether the row counts as reverted.
UndoHandler = Callable[["SpaceTx", sqlite3.Row, dict[str, Any], str], bool]


class SpaceTx:
    """One space inside one transaction, for one asset's role."""

    def __init__(
        self,
        con: sqlite3.Connection,
        summary: SpaceSummary,
        asset: AssetKey,
        role: MemoryRole,
    ) -> None:
        self._con = con
        self.summary = summary
        self.space = summary.space
        self.rules = summary.rules
        self.asset = asset
        self.role = role

    # -- access ----------------------------------------------------------

    def _need(self, needed: MemoryRole) -> None:
        rank = {"reader": 1, "contributor": 2, "manager": 3}
        if rank[self.role] < rank[needed]:
            code = {
                "reader": "memory_read_not_declared",
                "contributor": "memory_write_not_declared",
                "manager": "memory_manager_only",
            }[needed]
            raise MemoryAccessError(code)

    @property
    def con(self) -> sqlite3.Connection:
        """The connection, for the manager's own tables (`table`)."""
        self._need("manager")
        return self._con

    def table(self, name: str) -> str:
        """The name of one of the manager's own tables in this space."""
        self._need("manager")
        if not _TABLE.fullmatch(name):
            raise MemoryServiceError("memory_table_name")
        return self.summary.table_prefix + name

    # -- observations -----------------------------------------------------

    def add_observation(
        self,
        entity_id: str | None,
        fields: Mapping[str, str],
        *,
        source_kind: str,
        source_date: str,
        recorded_by: str,
        source_ref: str = "",
        uncertain: Sequence[str] = (),
        change_id: str = "",
        claim: str = "fields",
    ) -> int:
        """A claim, appended; never rewritten. `source_kind` must be one the
        space's merge rules know (its trust class comes from them)."""
        self._need("contributor")
        trust = self.rules.trust_of(source_kind)
        if trust is None:
            raise MemoryServiceError("memory_source_unknown")
        cursor = self._con.execute(
            "INSERT INTO observations (space, entity_id, claim, source_kind, trust, source_date, "
            "source_ref, fields_json, uncertain_json, recorded_at, recorded_by, contributor, "
            "change_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                self.space,
                entity_id,
                claim,
                source_kind,
                trust,
                source_date,
                source_ref,
                json.dumps(dict(fields), ensure_ascii=False),
                json.dumps(list(uncertain)),
                now_iso(),
                recorded_by,
                asset_label(self.asset),
                change_id,
            ),
        )
        return int(cursor.lastrowid or 0)

    def observations(
        self,
        entity_id: str | None = None,
        *,
        source_ref: str | None = None,
        claim: str | None = "fields",
        include_retracted: bool = False,
        newest_first: bool = False,
        limit: int = 10_000,
    ) -> list[Observation]:
        self._need("reader")
        where, args = ["space = ?"], [self.space]
        if entity_id is not None:
            where.append("entity_id = ?")
            args.append(entity_id)
        if source_ref is not None:
            where.append("source_ref = ?")
            args.append(source_ref)
        if claim is not None:
            where.append("claim = ?")
            args.append(claim)
        if not include_retracted:
            where.append("retracted_by = ''")
        order = "DESC" if newest_first else "ASC"
        rows = self._con.execute(
            f"SELECT * FROM observations WHERE {' AND '.join(where)} "
            f"ORDER BY observation_id {order} LIMIT ?",
            (*args, limit),
        )
        return [Observation.from_row(row) for row in rows]

    def retract(self, observation_ids: Sequence[int], change_id: str) -> int:
        """Withdraw claims (their content stays); returns how many."""
        self._need("manager")
        count = 0
        for observation_id in observation_ids:
            count += self._con.execute(
                "UPDATE observations SET retracted_by = ? WHERE space = ? AND observation_id = ? "
                "AND retracted_by = ''",
                (change_id, self.space, observation_id),
            ).rowcount
        return count

    def retract_statements(self, change_id: str, by: str) -> int:
        """Withdraw the person's own statements recorded in one change."""
        self._need("contributor")
        return self._con.execute(
            "UPDATE observations SET retracted_by = ? WHERE space = ? AND change_id = ? "
            "AND trust = 'user_stated' AND retracted_by = ''",
            (by, self.space, change_id),
        ).rowcount

    # -- provenance -------------------------------------------------------

    def provenance(self, entity_id: str) -> dict[str, sqlite3.Row]:
        """Each field's provenance row (`source_kind`, `source_date`,
        `observation_id`, `origin`, `set_by`, `set_at`, `reason`)."""
        self._need("reader")
        return {
            row["field"]: row
            for row in self._con.execute(
                "SELECT * FROM field_sources WHERE space = ? AND entity_id = ?",
                (self.space, entity_id),
            )
        }

    def field_provenance(self, entity_id: str) -> dict[str, FieldProvenance]:
        return {
            name: FieldProvenance(
                field=name,
                source_kind=row["source_kind"],
                source_date=row["source_date"],
                observation_id=row["observation_id"],
                origin=row["origin"],
                set_by=row["set_by"],
                set_at=row["set_at"],
                reason=row["reason"],
            )
            for name, row in self.provenance(entity_id).items()
        }

    def set_provenance(
        self,
        entity_id: str,
        field_name: str,
        *,
        source_kind: str,
        source_date: str,
        observation_id: int | None,
        set_by: str,
        reason: str = "",
        origin: str | None = None,
        set_at: str | None = None,
    ) -> None:
        """Where a current value came from; the manager writes it when its
        merge puts a value in place."""
        self._need("manager")
        self._con.execute(
            "INSERT OR REPLACE INTO field_sources (space, entity_id, field, source_kind, "
            "source_date, observation_id, origin, set_by, set_at, reason) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                self.space,
                entity_id,
                field_name,
                source_kind,
                source_date,
                observation_id,
                origin or origin_for(self.rules.trust_of(source_kind), source_kind),
                set_by,
                set_at or now_iso(),
                reason,
            ),
        )

    def drop_provenance(self, entity_id: str, field_name: str | None = None) -> None:
        self._need("manager")
        if field_name is None:
            self._con.execute(
                "DELETE FROM field_sources WHERE space = ? AND entity_id = ?",
                (self.space, entity_id),
            )
        else:
            self._con.execute(
                "DELETE FROM field_sources WHERE space = ? AND entity_id = ? AND field = ?",
                (self.space, entity_id, field_name),
            )

    @staticmethod
    def provenance_extra(previous: sqlite3.Row | None) -> dict[str, Any]:
        """What a history row keeps of the provenance it replaced, for undo."""
        if previous is None:
            return {"prev_source": None, "prev_date": None, "prev_observation": None}
        extra: dict[str, Any] = {
            "prev_source": previous["source_kind"],
            "prev_date": previous["source_date"],
            "prev_observation": previous["observation_id"],
        }
        for name in ("origin", "set_by", "set_at", "reason"):
            extra[f"prev_{name}"] = previous[name]
        return extra

    def restore_provenance(
        self,
        entity_id: str,
        field_name: str,
        extra: Mapping[str, Any],
        *,
        fallback_kind: str | None = None,
    ) -> None:
        """Put back the provenance a history row replaced (`provenance_extra`),
        or drop it when there was none (`fallback_kind` keeps one instead)."""
        kind = extra.get("prev_source") or fallback_kind
        if not kind:
            self.drop_provenance(entity_id, field_name)
            return
        self.set_provenance(
            entity_id,
            field_name,
            source_kind=kind,
            source_date=extra.get("prev_date") or "",
            observation_id=extra.get("prev_observation"),
            set_by=extra.get("prev_set_by") or "",
            reason=extra.get("prev_reason") or "",
            origin=extra.get("prev_origin") or None,
            set_at=extra.get("prev_set_at") or "",
        )

    # -- merge rules ------------------------------------------------------

    def decide(
        self,
        field_name: str,
        *,
        current: str,
        current_source: sqlite3.Row | None,
        offered: str,
        offered_kind: str,
        offered_date: str,
        uncertain: bool = False,
        same: Callable[[str, str], bool] = merge.same_text,
        novel: bool = False,
    ) -> Decision:
        """The space's merge rule for one offered value (`merge.decide`);
        `novel`: an undated source whose identity was never observed for the
        entity before."""
        self._need("reader")
        return merge.decide(
            self.rules,
            field_name,
            current=current,
            current_kind=None if current_source is None else current_source["source_kind"],
            current_date="" if current_source is None else current_source["source_date"],
            offered=offered,
            offered_kind=offered_kind,
            offered_date=offered_date,
            uncertain=uncertain,
            same=same,
            novel=novel,
        )

    def resolve(self, entity_id: str) -> merge.Resolution:
        """Current values from the entity's claims by the merge rules alone,
        for a space without a manager's view of its own."""
        return merge.resolve(self.rules, self.observations(entity_id))

    def solid(self, relation: str, evidence_kind: str) -> bool:
        """Whether a relationship with this evidence is drawn solid."""
        rule = self.rules.relation(relation)
        return rule is not None and evidence_kind in rule.solid_evidence

    # -- history ----------------------------------------------------------

    def record(
        self,
        change_id: str,
        actor: str,
        entity_id: str,
        kind: str,
        *,
        field_name: str = "",
        old: str = "",
        new: str = "",
        reason: str = "",
        source: str = "",
        extra: Mapping[str, Any] | None = None,
    ) -> None:
        self._need("contributor")
        self._con.execute(
            "INSERT INTO history (space, change_id, at, actor, entity_id, kind, field, old, new, "
            "reason, source, extra_json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                self.space,
                change_id,
                now_iso(),
                actor,
                entity_id,
                kind,
                field_name,
                old,
                new,
                reason,
                source,
                json.dumps(dict(extra or {}), ensure_ascii=False),
            ),
        )

    def history(
        self, entity_id: str | None = None, *, change_id: str | None = None, limit: int = 200
    ) -> list[sqlite3.Row]:
        """History rows, newest first: one entity's, or one change's."""
        self._need("reader")
        where, args = ["space = ?"], [self.space]
        if entity_id is not None:
            where.append("entity_id = ?")
            args.append(entity_id)
        if change_id is not None:
            where.append("change_id = ?")
            args.append(change_id)
        return list(
            self._con.execute(
                f"SELECT * FROM history WHERE {' AND '.join(where)} "
                "ORDER BY history_id DESC LIMIT ?",
                (*args, limit),
            )
        )

    def changed_since(self, entity_id: str, change_id: str) -> bool:
        """Whether a change other than `change_id` (and not undone, nor an
        undo) touched the entity."""
        self._need("reader")
        row = self._con.execute(
            "SELECT 1 FROM history WHERE space = ? AND entity_id = ? AND change_id != ? "
            "AND change_id NOT IN (SELECT change_id FROM undone) "
            "AND change_id NOT IN (SELECT undone_by FROM undone) LIMIT 1",
            (self.space, entity_id, change_id),
        ).fetchone()
        return row is not None

    def undo(
        self, change_id: str, *, actor: str, handlers: Mapping[str, UndoHandler]
    ) -> tuple[list[sqlite3.Row], str]:
        """Revert one change group, newest row first, as a new change: each
        row by the handler for its kind (the manager's), `proposal` rows by
        dismissing the proposal; the person's statements recorded in the
        change are retracted. A handler refuses by raising; then nothing is
        reverted. `change_unknown`, `change_already_undone`."""
        self._need("contributor")
        rows = self.history(change_id=change_id, limit=10_000)
        if not rows:
            raise MemoryServiceError("change_unknown")
        if self._con.execute("SELECT 1 FROM undone WHERE change_id = ?", (change_id,)).fetchone():
            raise MemoryServiceError("change_already_undone")
        new_change = new_change_id()
        reverted: list[sqlite3.Row] = []
        for item in rows:
            extra = json.loads(item["extra_json"] or "{}")
            handler = handlers.get(item["kind"])
            if handler is None and item["kind"] == "proposal":
                handler = _dismiss_proposal
            if handler is not None and handler(self, item, extra, new_change):
                reverted.append(item)
        self.retract_statements(change_id, new_change)
        self._con.execute(
            "INSERT INTO undone (change_id, space, undone_by) VALUES (?, ?, ?)",
            (change_id, self.space, new_change),
        )
        return reverted, new_change

    # -- proposals --------------------------------------------------------

    def propose(
        self,
        change_id: str,
        actor: str,
        entity_id: str,
        field_name: str,
        current: str,
        proposed: str,
        *,
        source_kind: str,
        observation_id: int | None,
        same: Callable[[str, str], bool] = merge.same_text,
    ) -> bool:
        """An offered value that was not taken, kept as an open proposal and
        recorded in history; the same value already open is not proposed
        again (False)."""
        self._need("contributor")
        for item in self._con.execute(
            "SELECT proposed FROM proposals WHERE space = ? AND entity_id = ? AND field = ? "
            "AND state = 'open'",
            (self.space, entity_id, field_name),
        ):
            if same(item["proposed"], proposed):
                return False
        self._con.execute(
            "INSERT INTO proposals (space, entity_id, field, current, proposed, source_kind, "
            "observation_id, created_at) VALUES (?,?,?,?,?,?,?,?)",
            (
                self.space,
                entity_id,
                field_name,
                current,
                proposed,
                source_kind,
                observation_id,
                now_iso(),
            ),
        )
        self.record(
            change_id,
            actor,
            entity_id,
            "proposal",
            field_name=field_name,
            old=current,
            new=proposed,
            source=source_kind,
            reason="the stored value is kept; the new one is a proposal",
        )
        return True

    def proposals(
        self,
        entity_id: str | None = None,
        *,
        field_name: str | None = None,
        state: str | None = "open",
        newest_first: bool = False,
        limit: int = 200,
    ) -> list[sqlite3.Row]:
        self._need("reader")
        where, args = ["space = ?"], [self.space]
        if entity_id is not None:
            where.append("entity_id = ?")
            args.append(entity_id)
        if field_name is not None:
            where.append("field = ?")
            args.append(field_name)
        if state is not None:
            where.append("state = ?")
            args.append(state)
        order = "DESC" if newest_first else "ASC"
        return list(
            self._con.execute(
                f"SELECT * FROM proposals WHERE {' AND '.join(where)} "
                f"ORDER BY proposal_id {order} LIMIT ?",
                (*args, limit),
            )
        )

    def set_proposal_state(self, proposal_id: int, state: str, *, actor: str) -> None:
        """Accept, reject, dismiss or reopen one proposal (the person's
        decision, or an undo)."""
        self._need("contributor")
        if state not in PROPOSAL_STATES:
            raise MemoryServiceError("proposal_state_unknown")
        decided = ("", "") if state == "open" else (now_iso(), actor)
        self._con.execute(
            "UPDATE proposals SET state = ?, decided_at = ?, decided_by = ? "
            "WHERE space = ? AND proposal_id = ?",
            (state, *decided, self.space, proposal_id),
        )

    def reopen(self, proposal_ids: Sequence[int]) -> None:
        for proposal_id in proposal_ids:
            self.set_proposal_state(int(proposal_id), "open", actor="")

    # -- entities and external ids -----------------------------------------

    def forget_entity(self, entity_id: str, change_id: str) -> None:
        """An entity whose creation was undone: its claims are retracted, its
        provenance, proposals and external ids go."""
        self._need("manager")
        self._con.execute(
            "UPDATE observations SET retracted_by = ? WHERE space = ? AND entity_id = ? "
            "AND retracted_by = ''",
            (change_id, self.space, entity_id),
        )
        for table in ("field_sources", "proposals", "external_ids"):
            self._con.execute(
                f"DELETE FROM {table} WHERE space = ? AND entity_id = ?", (self.space, entity_id)
            )

    def map_external_id(self, entity_id: str, system: str, external_id: str, *, actor: str) -> bool:
        """Map another system's id to an entity; False when it is already
        mapped (to this entity). `external_id_taken` when another one has it."""
        self._need("contributor")
        held = self.entity_for_external_id(system, external_id)
        if held is not None:
            if held != entity_id:
                raise MemoryServiceError("external_id_taken")
            return False
        self._con.execute(
            "INSERT INTO external_ids (space, system, external_id, entity_id, created_at, "
            "created_by) VALUES (?,?,?,?,?,?)",
            (self.space, system, external_id.strip(), entity_id, now_iso(), actor),
        )
        return True

    def entity_for_external_id(self, system: str, external_id: str) -> str | None:
        self._need("reader")
        row = self._con.execute(
            "SELECT entity_id FROM external_ids WHERE space = ? AND system = ? AND external_id = ?",
            (self.space, system, external_id.strip()),
        ).fetchone()
        return None if row is None else str(row["entity_id"])

    def external_ids(self, entity_id: str) -> dict[str, list[str]]:
        self._need("reader")
        found: dict[str, list[str]] = {}
        for row in self._con.execute(
            "SELECT system, external_id FROM external_ids WHERE space = ? AND entity_id = ? "
            "ORDER BY system, external_id",
            (self.space, entity_id),
        ):
            found.setdefault(row["system"], []).append(row["external_id"])
        return found

    def auto_merge(
        self,
        identities: Mapping[str, str],
        *,
        by_identity: Callable[[str, str], str | None],
        possible: Callable[[], Sequence[str]] = lambda: (),
    ) -> merge.AutoMerge:
        """Whether a contribution from another source joins an entity by
        itself (§10.7; `merge.auto_merge`)."""
        self._need("reader")
        return merge.auto_merge(
            self.rules,
            identities,
            by_identity=by_identity,
            by_external_id=self.entity_for_external_id,
            possible=possible,
        )

    # -- sync state (M2) ---------------------------------------------------

    def _need_sync(self, needed: MemoryRole) -> None:
        """Sync state is for a space that declares the `sync_state` kind."""
        self._need(needed)
        if "sync_state" not in self.summary.declaration.kinds:
            raise MemoryAccessError("memory_kind_not_declared")

    def _sync_row(self, source: str, key: str) -> sqlite3.Row | None:
        found: sqlite3.Row | None = self._con.execute(
            "SELECT * FROM sync_state WHERE space = ? AND source = ? AND key = ?",
            (self.space, source, key),
        ).fetchone()
        return found

    def sync_state(self, source: str, key: str) -> SyncState | None:
        """How far `source` was processed for `key`, or None (never, or reset)."""
        self._need_sync("reader")
        row = self._sync_row(source, key)
        return None if row is None else _sync_state(row)

    def sync_states(self, source: str | None = None) -> list[SyncState]:
        self._need_sync("reader")
        where, args = ["space = ?"], [self.space]
        if source is not None:
            where.append("source = ?")
            args.append(source)
        rows = self._con.execute(
            f"SELECT * FROM sync_state WHERE {' AND '.join(where)} ORDER BY source, key", args
        )
        return [_sync_state(row) for row in rows]

    def advance_sync(
        self,
        source: str,
        key: str,
        *,
        last_message_date: str,
        message_ids: Sequence[str],
        extractor_version: str,
        actor: str,
        reason: str = "",
    ) -> SyncState:
        """Move the state forward after a successful pass: never backwards
        (`sync_state_backwards`), and never across an extractor change without
        a reset first (`sync_extractor_changed`). On the same date the ids
        join the earlier ones; the newest `MAX_SYNC_IDS` are kept. A history
        row records the change."""
        self._need_sync("contributor")
        if not source.strip() or not key.strip():
            raise MemoryServiceError("sync_state_unnamed")
        moment = _moment(last_message_date)
        old_row = self._sync_row(source, key)
        old = None if old_row is None else _sync_state(old_row)
        ids = list(dict.fromkeys(item for item in message_ids if item))
        if old is not None:
            if old.extractor_version != extractor_version:
                raise MemoryServiceError("sync_extractor_changed")
            if moment < _moment(old.last_message_date):
                raise MemoryServiceError("sync_state_backwards")
            ids = list(dict.fromkeys([*ids, *old.last_message_ids]))
        new = SyncState(
            space=self.space,
            source=source,
            key=key,
            last_message_date=moment.isoformat(),
            last_message_ids=tuple(ids[:MAX_SYNC_IDS]),
            extractor_version=extractor_version,
            updated_at=now_iso(),
            updated_by=actor,
        )
        self._write_sync(new)
        self._sync_record(source, key, "advance", actor=actor, reason=reason, old=old, new=new)
        return new

    def reset_sync(self, source: str, key: str, *, actor: str, reason: str) -> SyncState | None:
        """Forget how far `source` was processed for `key`: the next pass
        reads the full scope. The state before is kept in history (it can be
        restored); returns it, or None when there was none."""
        self._need_sync("contributor")
        old_row = self._sync_row(source, key)
        old = None if old_row is None else _sync_state(old_row)
        self._con.execute(
            "DELETE FROM sync_state WHERE space = ? AND source = ? AND key = ?",
            (self.space, source, key),
        )
        self._sync_record(source, key, "reset", actor=actor, reason=reason, old=old, new=None)
        return old

    def restore_sync(self, history_id: int, *, actor: str) -> SyncState | None:
        """Put back the state one history row replaced (undoing a reset or an
        advance), as a new history row. `sync_history_unknown`."""
        self._need_sync("contributor")
        row = self._con.execute(
            "SELECT * FROM sync_history WHERE space = ? AND history_id = ?",
            (self.space, history_id),
        ).fetchone()
        if row is None:
            raise MemoryServiceError("sync_history_unknown")
        entry = _sync_entry(row)
        current_row = self._sync_row(entry.source, entry.key)
        current = None if current_row is None else _sync_state(current_row)
        if entry.old is None:
            self._con.execute(
                "DELETE FROM sync_state WHERE space = ? AND source = ? AND key = ?",
                (self.space, entry.source, entry.key),
            )
            restored = None
        else:
            restored = entry.old.model_copy(update={"updated_at": now_iso(), "updated_by": actor})
            self._write_sync(restored)
        self._sync_record(
            entry.source,
            entry.key,
            "restore",
            actor=actor,
            reason=f"restore history {history_id}",
            old=current,
            new=restored,
        )
        return restored

    def sync_history(
        self, source: str | None = None, key: str | None = None, *, limit: int = 50
    ) -> list[SyncHistoryEntry]:
        """Advances, resets and restores, newest first."""
        self._need_sync("reader")
        where, args = ["space = ?"], [self.space]
        if source is not None:
            where.append("source = ?")
            args.append(source)
        if key is not None:
            where.append("key = ?")
            args.append(key)
        rows = self._con.execute(
            f"SELECT * FROM sync_history WHERE {' AND '.join(where)} "
            "ORDER BY history_id DESC LIMIT ?",
            (*args, limit),
        )
        return [_sync_entry(row) for row in rows]

    def _write_sync(self, state: SyncState) -> None:
        self._con.execute(
            "INSERT OR REPLACE INTO sync_state (space, source, key, last_message_date, "
            "last_message_ids_json, extractor_version, updated_at, updated_by) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (
                self.space,
                state.source,
                state.key,
                state.last_message_date,
                json.dumps(list(state.last_message_ids), ensure_ascii=False),
                state.extractor_version,
                state.updated_at,
                state.updated_by,
            ),
        )

    def _sync_record(
        self,
        source: str,
        key: str,
        action: str,
        *,
        actor: str,
        reason: str,
        old: SyncState | None,
        new: SyncState | None,
    ) -> None:
        self._con.execute(
            "INSERT INTO sync_history (space, source, key, action, at, actor, reason, old_json, "
            "new_json) VALUES (?,?,?,?,?,?,?,?,?)",
            (
                self.space,
                source,
                key,
                action,
                now_iso(),
                actor,
                reason,
                None if old is None else old.model_dump_json(),
                None if new is None else new.model_dump_json(),
            ),
        )


def _moment(value: str) -> datetime:
    """An ISO date or time as an aware UTC moment (`sync_date_invalid`)."""
    try:
        moment = datetime.fromisoformat(value.strip())
    except ValueError:
        raise MemoryServiceError("sync_date_invalid") from None
    return moment.replace(tzinfo=UTC) if moment.tzinfo is None else moment.astimezone(UTC)


def _sync_state(row: sqlite3.Row) -> SyncState:
    return SyncState(
        space=row["space"],
        source=row["source"],
        key=row["key"],
        last_message_date=row["last_message_date"],
        last_message_ids=tuple(json.loads(row["last_message_ids_json"] or "[]")),
        extractor_version=row["extractor_version"],
        updated_at=row["updated_at"],
        updated_by=row["updated_by"],
    )


def _sync_entry(row: sqlite3.Row) -> SyncHistoryEntry:
    return SyncHistoryEntry(
        history_id=int(row["history_id"]),
        space=row["space"],
        source=row["source"],
        key=row["key"],
        action=row["action"],
        at=row["at"],
        actor=row["actor"],
        reason=row["reason"],
        old=None if row["old_json"] is None else SyncState.model_validate_json(row["old_json"]),
        new=None if row["new_json"] is None else SyncState.model_validate_json(row["new_json"]),
    )


def _dismiss_proposal(tx: SpaceTx, item: sqlite3.Row, extra: dict[str, Any], change: str) -> bool:
    for row in tx.proposals(item["entity_id"], field_name=item["field"]):
        if row["proposed"] == item["new"]:
            tx.set_proposal_state(
                int(row["proposal_id"]), "dismissed", actor=f"undo {item['change_id']}"
            )
    return True


class MemorySpace:
    """A space opened for one asset; every call is one transaction."""

    def __init__(
        self, service: MemoryService, summary: SpaceSummary, asset: AssetKey, role: MemoryRole
    ) -> None:
        self.service = service
        self.summary = summary
        self.asset = asset
        self.role = role

    @property
    def name(self) -> str:
        return self.summary.space

    @property
    def rules(self) -> MergeRules:
        return self.summary.rules

    @contextmanager
    def transaction(self, *, immediate: bool = False) -> Iterator[SpaceTx]:
        with self.service.connect(immediate=immediate) as con:
            yield SpaceTx(con, self.summary, self.asset, self.role)

    def add_observation(
        self,
        entity_id: str | None,
        fields: Mapping[str, str],
        *,
        source_kind: str,
        source_date: str,
        recorded_by: str,
        source_ref: str = "",
        uncertain: Sequence[str] = (),
    ) -> int:
        with self.transaction() as tx:
            return tx.add_observation(
                entity_id,
                fields,
                source_kind=source_kind,
                source_date=source_date,
                recorded_by=recorded_by,
                source_ref=source_ref,
                uncertain=uncertain,
            )

    def observations(self, entity_id: str | None = None) -> list[Observation]:
        with self.transaction() as tx:
            return tx.observations(entity_id)

    def resolve(self, entity_id: str) -> merge.Resolution:
        with self.transaction() as tx:
            return tx.resolve(entity_id)

    def history(self, entity_id: str | None = None, *, limit: int = 200) -> list[sqlite3.Row]:
        with self.transaction() as tx:
            return tx.history(entity_id, limit=limit)

    def proposals(self, entity_id: str | None = None) -> list[sqlite3.Row]:
        with self.transaction() as tx:
            return tx.proposals(entity_id)

    def undo(
        self, change_id: str, *, actor: str, handlers: Mapping[str, UndoHandler] | None = None
    ) -> tuple[list[sqlite3.Row], str]:
        with self.transaction() as tx:
            return tx.undo(change_id, actor=actor, handlers=handlers or {})

    def map_external_id(self, entity_id: str, system: str, external_id: str, *, actor: str) -> bool:
        with self.transaction() as tx:
            return tx.map_external_id(entity_id, system, external_id, actor=actor)

    def entity_for_external_id(self, system: str, external_id: str) -> str | None:
        with self.transaction() as tx:
            return tx.entity_for_external_id(system, external_id)

    def sync_state(self, source: str, key: str) -> SyncState | None:
        with self.transaction() as tx:
            return tx.sync_state(source, key)

    def sync_states(self, source: str | None = None) -> list[SyncState]:
        with self.transaction() as tx:
            return tx.sync_states(source)

    def advance_sync(
        self,
        source: str,
        key: str,
        *,
        last_message_date: str,
        message_ids: Sequence[str],
        extractor_version: str,
        actor: str,
        reason: str = "",
    ) -> SyncState:
        with self.transaction(immediate=True) as tx:
            return tx.advance_sync(
                source,
                key,
                last_message_date=last_message_date,
                message_ids=message_ids,
                extractor_version=extractor_version,
                actor=actor,
                reason=reason,
            )

    def reset_sync(self, source: str, key: str, *, actor: str, reason: str) -> SyncState | None:
        with self.transaction(immediate=True) as tx:
            return tx.reset_sync(source, key, actor=actor, reason=reason)

    def restore_sync(self, history_id: int, *, actor: str) -> SyncState | None:
        with self.transaction(immediate=True) as tx:
            return tx.restore_sync(history_id, actor=actor)

    def sync_history(
        self, source: str | None = None, key: str | None = None, *, limit: int = 50
    ) -> list[SyncHistoryEntry]:
        with self.transaction() as tx:
            return tx.sync_history(source, key, limit=limit)


class MemoryService:
    """One actor's memory database, with the spaces the registry knows."""

    def __init__(self, path: Path, registry: MemoryRegistry) -> None:
        self.path = path
        self.registry = registry
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as con:
            con.executescript(_SCHEMA)
            con.execute(
                "INSERT OR IGNORE INTO meta (key, value) VALUES ('schema_version', ?)",
                (SCHEMA_VERSION,),
            )
        for manager, declaration, rules in registry.managed():
            if rules is not None:
                self.register_space(declaration, manager=manager, rules=rules)

    @classmethod
    def for_actor(cls, workspace_root: Path, actor: str, registry: MemoryRegistry) -> MemoryService:
        return cls(memory_path(workspace_root, actor), registry)

    @contextmanager
    def connect(self, *, immediate: bool = False) -> Iterator[sqlite3.Connection]:
        """One transaction: committed on success, rolled back on any error.
        `immediate` takes the write lock at once."""
        with closing(sqlite3.connect(self.path, timeout=10)) as con:
            con.row_factory = sqlite3.Row
            with con:
                if immediate:
                    con.execute("BEGIN IMMEDIATE")
                yield con

    def register_space(
        self,
        declaration: MemorySpaceDeclaration,
        *,
        manager: AssetIdentity | AssetKey,
        rules: MergeRules,
    ) -> SpaceSummary:
        """The registry row of a managed space: its declaration and merge
        rules as data, written when new or changed."""
        key = asset_key(manager)
        if declaration.role != "manager":
            raise MemoryServiceError("memory_not_the_manager")
        if self.registry.role(declaration.space, key) != "manager":
            raise MemoryAccessError("memory_not_the_manager")
        if rules.rules_id != declaration.merge_rules:
            raise MemoryServiceError("memory_rules_mismatch")
        summary = SpaceSummary(
            space=declaration.space,
            manager=asset_label(key),
            table_prefix=table_prefix(declaration.space),
            declaration=declaration,
            rules=rules,
        )
        with self.connect() as con:
            row = con.execute(
                "SELECT * FROM spaces WHERE space = ?", (declaration.space,)
            ).fetchone()
            payload = (
                summary.manager,
                declaration.model_dump_json(),
                rules.model_dump_json(),
            )
            if row is None:
                stamp = now_iso()
                con.execute(
                    "INSERT INTO spaces (space, manager, table_prefix, declaration_json, "
                    "rules_json, registered_at, updated_at) VALUES (?,?,?,?,?,?,?)",
                    (
                        declaration.space,
                        payload[0],
                        summary.table_prefix,
                        *payload[1:],
                        stamp,
                        stamp,
                    ),
                )
            elif (row["manager"], row["declaration_json"], row["rules_json"]) != payload:
                con.execute(
                    "UPDATE spaces SET manager = ?, declaration_json = ?, rules_json = ?, "
                    "updated_at = ? WHERE space = ?",
                    (*payload, now_iso(), declaration.space),
                )
        return summary

    def spaces(self) -> tuple[SpaceSummary, ...]:
        with self.connect() as con:
            rows = list(con.execute("SELECT * FROM spaces ORDER BY space"))
        return tuple(_summary(row) for row in rows)

    def space(self, space: str, *, asset: AssetIdentity | AssetKey) -> MemorySpace:
        """The space opened for one asset, as its declaration allows:
        `memory_space_not_declared` when it declared nothing for the space,
        `memory_space_unknown` when no manager registered it."""
        key = asset_key(asset)
        role = self.registry.role(space, key)
        if role is None:
            raise MemoryAccessError("memory_space_not_declared")
        with self.connect() as con:
            row = con.execute("SELECT * FROM spaces WHERE space = ?", (space,)).fetchone()
        if row is None:
            raise MemoryServiceError("memory_space_unknown")
        return MemorySpace(self, _summary(row), key, role)

    def get_meta(self, key: str) -> str | None:
        with self.connect() as con:
            row = con.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return None if row is None else str(row["value"])


def _summary(row: sqlite3.Row) -> SpaceSummary:
    return SpaceSummary(
        space=row["space"],
        manager=row["manager"],
        table_prefix=row["table_prefix"],
        declaration=MemorySpaceDeclaration.model_validate_json(row["declaration_json"]),
        rules=MergeRules.model_validate_json(row["rules_json"]),
    )
