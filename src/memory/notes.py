"""The person's notes (accumulated memory M3, docs/phases/ACCUMULATED_MEMORY.md §3.9).

Free-text conclusions, ideas, meeting points kept in the Host-managed space
`personal/notes` of the actor's own memory database. A note is written only
by the person: one click on an answer in Agent Web (「存成筆記」, or
「存選取內容」 for a selection), or the press on an Agent's 「要存成筆記嗎？」
card. Each note keeps its source (conversation and message, or the
selected excerpt), tags, linked entities (`contacts/org:person:<id>`),
who made it and when; edits and deletions are history rows that undo
reverts.

Notes are never injected into a turn. They are read through `search` (the
`notes__search` tool, offered only to a Skill that declares a notes read or
when the person's message asks about earlier notes, `notes_asked`), and by
a declared reader's own code (`for_reader`, e.g. the org chart's
「相關筆記」).
"""

from __future__ import annotations

import json
import re
import secrets
import sqlite3
import unicodedata
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from typing import Any, Literal
from zoneinfo import ZoneInfo

from memory.personal import HOST_MEMORY, NOTES_SPACE
from memory.registry import AssetKey
from memory.service import (
    MemoryAccessError,
    MemoryService,
    MemoryServiceError,
    SpaceTx,
    new_change_id,
    now_iso,
)

MAX_TEXT = 20_000
MAX_TAGS = 8
MAX_TAG = 40
MAX_ENTITIES = 12
MAX_SEARCH = 20
#: How much of a note a search result carries.
EXCERPT = 600
#: The person's days (a search's date range).
LOCAL_ZONE = ZoneInfo("Asia/Taipei")

SourceKind = Literal["answer", "selection", "agent_proposal"]
Status = Literal["active", "deleted"]

#: `<space>:<kind>:<id>`, e.g. `contacts/org:person:p-1a2b3c`.
ENTITY_REF = re.compile(r"^[a-z][a-z0-9-]*/[a-z][a-z0-9-]*:[a-z][a-z_]{1,20}:[^\s]{1,120}$")

#: The person's message asks about earlier notes (owner 2026-10-20, §3.9 case 2).
NOTES_ASKED = re.compile(
    r"(?:之前|以前|上次|先前|曾經|過去)(?:有)?(?:記|存|寫)(?:過|下|了)"
    r"|記過(?:什麼|甚麼|哪些|嗎|的|那)"
    r"|有(?:沒有)?記過"
    r"|(?:我的|之前的|以前的|存的|記的|存過的|記過的)筆記"
    r"|(?:查|找|翻|搜尋|搜|看)(?:一下)?(?:我的)?筆記"
    r"|筆記(?:裡|中|上)(?:有|寫|記)"
    r"|\bwhat\s+(?:did|have)\s+I\s+(?:note|noted|written\s+down|saved)\b"
    r"|\bdid\s+I\s+(?:note|write\s+down|save)\b"
    r"|\b(?:my|earlier|previous|old|saved)\s+notes?\b"
    r"|\bI\s+(?:noted|wrote\s+down)\b",
    re.IGNORECASE,
)

_TABLE = "items"
_SCHEMA = """
CREATE TABLE IF NOT EXISTS {table} (
    note_id TEXT PRIMARY KEY,
    text TEXT NOT NULL,
    tags_json TEXT NOT NULL DEFAULT '[]',
    entities_json TEXT NOT NULL DEFAULT '[]',
    source_kind TEXT NOT NULL,
    source_session TEXT NOT NULL DEFAULT '',
    source_message TEXT NOT NULL DEFAULT '',
    excerpt_json TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'active',
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_by TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS {table}_source ON {table}(source_session, source_message);
"""


class NoteError(MemoryServiceError):
    """A refusal by code (`note_unknown`, `note_text_empty`,
    `note_entity_invalid`, `note_date_invalid`, `undo_conflict`)."""


def notes_asked(message: str) -> bool:
    """Whether the person's message refers to earlier notes (「之前有記過什麼」,
    「我的筆記」, "what did I note"): the deterministic trigger for
    `notes__search`."""
    return bool(NOTES_ASKED.search(unicodedata.normalize("NFKC", message or "")))


@dataclass(frozen=True)
class Note:
    note_id: str
    text: str
    tags: tuple[str, ...]
    entities: tuple[str, ...]
    source_kind: str
    source_session: str
    source_message: str
    excerpt: dict[str, Any] | None
    status: Status
    created_by: str
    created_at: str
    updated_by: str
    updated_at: str

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> Note:
        return cls(
            note_id=row["note_id"],
            text=row["text"],
            tags=tuple(json.loads(row["tags_json"] or "[]")),
            entities=tuple(json.loads(row["entities_json"] or "[]")),
            source_kind=row["source_kind"],
            source_session=row["source_session"],
            source_message=row["source_message"],
            excerpt=json.loads(row["excerpt_json"]) if row["excerpt_json"] else None,
            status=row["status"],
            created_by=row["created_by"],
            created_at=row["created_at"],
            updated_by=row["updated_by"],
            updated_at=row["updated_at"],
        )

    def as_dict(self, *, excerpt_only: bool = False) -> dict[str, Any]:
        text = self.text
        if excerpt_only and len(text) > EXCERPT:
            text = text[:EXCERPT].rstrip() + "…"
        return {
            "note_id": self.note_id,
            "text": text,
            "tags": list(self.tags),
            "entities": list(self.entities),
            "source": {
                "kind": self.source_kind,
                "conversation": self.source_session,
                "message": self.source_message,
                **({"excerpt": self.excerpt} if self.excerpt else {}),
            },
            "status": self.status,
            "created_by": self.created_by,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


def clean_tags(tags: Iterable[str]) -> tuple[str, ...]:
    found: list[str] = []
    for tag in tags:
        flat = " ".join(unicodedata.normalize("NFKC", str(tag)).split()).lstrip("#")[:MAX_TAG]
        if flat and flat.casefold() not in {item.casefold() for item in found}:
            found.append(flat)
    return tuple(found[:MAX_TAGS])


def clean_entities(entities: Iterable[str]) -> tuple[str, ...]:
    found: list[str] = []
    for item in entities:
        ref = str(item).strip()
        if not ENTITY_REF.fullmatch(ref):
            raise NoteError("note_entity_invalid")
        if ref not in found:
            found.append(ref)
    return tuple(found[:MAX_ENTITIES])


def _text(text: str) -> str:
    kept = (text or "").strip()
    if not kept:
        raise NoteError("note_text_empty")
    return kept[:MAX_TEXT]


def _new_id() -> str:
    return f"n-{secrets.token_hex(5)}"


def _day(value: str, *, end: bool) -> str:
    """`YYYY-MM-DD`, a day in Asia/Taipei, as the UTC ISO bound of that day
    (stored stamps are UTC ISO and compare as text)."""
    if not value:
        return ""
    try:
        day = date.fromisoformat(value.strip())
    except ValueError:
        raise NoteError("note_date_invalid") from None
    moment = datetime.combine(day, time.max if end else time.min, LOCAL_ZONE)
    return moment.astimezone(UTC).isoformat(timespec="seconds")


class Notes:
    """One actor's notes, in the Host-managed space."""

    def __init__(self, service: MemoryService) -> None:
        self.service = service
        self._space = service.space(NOTES_SPACE, asset=HOST_MEMORY)
        with self._space.transaction() as tx:
            tx.con.executescript(_SCHEMA.format(table=tx.table(_TABLE)))

    # -- reads -----------------------------------------------------------

    def _rows(self, tx: SpaceTx, where: str = "", args: Sequence[Any] = ()) -> list[Note]:
        query = f"SELECT * FROM {tx.table(_TABLE)}"
        if where:
            query += f" WHERE {where}"
        query += " ORDER BY created_at DESC, note_id"
        return [Note.from_row(row) for row in tx.con.execute(query, tuple(args))]

    def get(self, note_id: str) -> Note | None:
        with self._space.transaction() as tx:
            found = self._rows(tx, "note_id = ?", (note_id,))
        return found[0] if found else None

    def listed(self, *, include_deleted: bool = False, limit: int = 500) -> list[Note]:
        """Newest first."""
        with self._space.transaction() as tx:
            found = self._rows(tx, "" if include_deleted else "status = 'active'")
        return found[:limit]

    def from_source(self, session: str, message: str, text: str) -> Note | None:
        """An active note already saved with this text from this message."""
        with self._space.transaction() as tx:
            for note in self._rows(
                tx,
                "status = 'active' AND source_session = ? AND source_message = ?",
                (session, message),
            ):
                if note.text == text.strip():
                    return note
        return None

    def search(
        self,
        *,
        text: str = "",
        tag: str = "",
        entity: str = "",
        since: str = "",
        until: str = "",
        limit: int = 10,
    ) -> list[Note]:
        """Active notes matching all the filters given, newest first: words
        of `text` (each must appear, case-insensitive), a tag, a linked
        entity, a creation date range (`YYYY-MM-DD`, inclusive)."""
        start, end = _day(since, end=False), _day(until, end=True)
        words = [_fold(word) for word in (text or "").split() if word.strip()]
        wanted_tag = _fold(tag.lstrip("#")) if tag else ""
        found: list[Note] = []
        for note in self.listed(limit=10_000):
            if start and note.created_at < start:
                continue
            if end and note.created_at > end:
                continue
            if entity and entity.strip() not in note.entities:
                continue
            if wanted_tag and wanted_tag not in {_fold(item) for item in note.tags}:
                continue
            haystack = _fold(" ".join((note.text, *note.tags)))
            if any(word not in haystack for word in words):
                continue
            found.append(note)
            if len(found) >= max(1, min(limit, MAX_SEARCH)):
                break
        return found

    def linked(self, refs: Iterable[str]) -> dict[str, list[Note]]:
        """Active notes linked to each entity ref, newest first."""
        wanted = set(refs)
        found: dict[str, list[Note]] = {}
        if not wanted:
            return found
        for note in self.listed(limit=10_000):
            for ref in note.entities:
                if ref in wanted:
                    found.setdefault(ref, []).append(note)
        return found

    def history(self, note_id: str | None = None) -> list[sqlite3.Row]:
        with self._space.transaction() as tx:
            return tx.history(note_id)

    # -- writes ----------------------------------------------------------

    def save(
        self,
        text: str,
        *,
        actor: str,
        source_kind: SourceKind,
        source_session: str = "",
        source_message: str = "",
        excerpt: Mapping[str, Any] | None = None,
        tags: Iterable[str] = (),
        entities: Iterable[str] = (),
    ) -> tuple[Note, str]:
        """Save one note as one change; returns it and the change id."""
        stamp = now_iso()
        note = Note(
            note_id=_new_id(),
            text=_text(text),
            tags=clean_tags(tags),
            entities=clean_entities(entities),
            source_kind=source_kind,
            source_session=source_session[:200],
            source_message=source_message[:200],
            excerpt=dict(excerpt) if excerpt else None,
            status="active",
            created_by=actor,
            created_at=stamp,
            updated_by=actor,
            updated_at=stamp,
        )
        change = new_change_id()
        with self._space.transaction(immediate=True) as tx:
            tx.con.execute(
                f"INSERT INTO {tx.table(_TABLE)} (note_id, text, tags_json, entities_json, "
                "source_kind, source_session, source_message, excerpt_json, status, created_by, "
                "created_at, updated_by, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    note.note_id,
                    note.text,
                    json.dumps(list(note.tags), ensure_ascii=False),
                    json.dumps(list(note.entities), ensure_ascii=False),
                    note.source_kind,
                    note.source_session,
                    note.source_message,
                    json.dumps(note.excerpt, ensure_ascii=False) if note.excerpt else "",
                    note.status,
                    note.created_by,
                    note.created_at,
                    note.updated_by,
                    note.updated_at,
                ),
            )
            tx.record(
                change,
                actor,
                note.note_id,
                "note_add",
                new=note.text[:2_000],
                source="user",
                reason=f"saved from {source_kind}",
            )
        return note, change

    def update(
        self,
        note_id: str,
        *,
        actor: str,
        text: str | None = None,
        tags: Iterable[str] | None = None,
        entities: Iterable[str] | None = None,
    ) -> str:
        """Change a note's text, tags or links as one change (the values
        before are kept in history, so undo restores them)."""
        change = new_change_id()
        with self._space.transaction(immediate=True) as tx:
            found = self._rows(tx, "note_id = ? AND status = 'active'", (note_id,))
            if not found:
                raise NoteError("note_unknown")
            old = found[0]
            new_text = old.text if text is None else _text(text)
            new_tags = old.tags if tags is None else clean_tags(tags)
            new_entities = old.entities if entities is None else clean_entities(entities)
            _write(tx, note_id, new_text, new_tags, new_entities, actor)
            tx.record(
                change,
                actor,
                note_id,
                "note_update",
                old=old.text[:2_000],
                new=new_text[:2_000],
                extra={
                    "old": {
                        "text": old.text,
                        "tags": list(old.tags),
                        "entities": list(old.entities),
                    }
                },
            )
        return change

    def delete(self, note_id: str, *, actor: str) -> str:
        """Delete a note (kept as `deleted`, undoable)."""
        change = new_change_id()
        with self._space.transaction(immediate=True) as tx:
            found = self._rows(tx, "note_id = ? AND status = 'active'", (note_id,))
            if not found:
                raise NoteError("note_unknown")
            _status(tx, note_id, "deleted", actor)
            tx.record(change, actor, note_id, "note_delete", old=found[0].text[:2_000])
        return change

    def undo(self, change_id: str, *, actor: str) -> tuple[int, str]:
        """Revert one change as a new change; refused (`undo_conflict`) when
        a later change touched the same note."""
        with self._space.transaction(immediate=True) as tx:
            for row in tx.history(change_id=change_id, limit=1_000):
                if tx.changed_after(row["entity_id"], change_id):
                    raise NoteError("undo_conflict")
            reverted, new_change = tx.undo(change_id, actor=actor, handlers=_HANDLERS)
        return len(reverted), new_change


def for_reader(
    service: MemoryService, reader: AssetKey, refs: Iterable[str]
) -> dict[str, list[Note]]:
    """Notes linked to these entities, for an asset that declared a read of
    `personal/notes` (`memory_read_not_declared` otherwise): the manager's
    API for its readers, who never reach its tables."""
    if service.registry.role(NOTES_SPACE, reader) is None:
        raise MemoryAccessError("memory_read_not_declared")
    return Notes(service).linked(refs)


def _fold(text: str) -> str:
    return unicodedata.normalize("NFKC", text or "").casefold().strip()


def _write(
    tx: SpaceTx,
    note_id: str,
    text: str,
    tags: Sequence[str],
    entities: Sequence[str],
    actor: str,
) -> None:
    tx.con.execute(
        f"UPDATE {tx.table(_TABLE)} SET text = ?, tags_json = ?, entities_json = ?, "
        "updated_by = ?, updated_at = ? WHERE note_id = ?",
        (
            text,
            json.dumps(list(tags), ensure_ascii=False),
            json.dumps(list(entities), ensure_ascii=False),
            actor,
            now_iso(),
            note_id,
        ),
    )


def _status(tx: SpaceTx, note_id: str, status: str, actor: str) -> bool:
    return (
        tx.con.execute(
            f"UPDATE {tx.table(_TABLE)} SET status = ?, updated_by = ?, updated_at = ? "
            "WHERE note_id = ?",
            (status, actor, now_iso(), note_id),
        ).rowcount
        > 0
    )


def _undo_add(tx: SpaceTx, row: sqlite3.Row, extra: Mapping[str, Any], change: str) -> bool:
    return _status(tx, row["entity_id"], "deleted", f"undo {row['change_id']}")


def _undo_delete(tx: SpaceTx, row: sqlite3.Row, extra: Mapping[str, Any], change: str) -> bool:
    return _status(tx, row["entity_id"], "active", f"undo {row['change_id']}")


def _undo_update(tx: SpaceTx, row: sqlite3.Row, extra: Mapping[str, Any], change: str) -> bool:
    old = extra.get("old") or {}
    _write(
        tx,
        row["entity_id"],
        str(old.get("text") or row["old"]),
        tuple(old.get("tags") or ()),
        tuple(old.get("entities") or ()),
        f"undo {row['change_id']}",
    )
    return True


_HANDLERS = {"note_add": _undo_add, "note_delete": _undo_delete, "note_update": _undo_update}
