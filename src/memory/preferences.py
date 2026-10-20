"""The person's preferences (accumulated memory M3, docs/phases/ACCUMULATED_MEMORY.md §5).

A preference is a rule the person said about how a Skill should work
(「執行時不需要問是否包含在職人員」), saved only when they press 存成偏好 on
the Agent's card. It lives in the Host-managed space `personal/preferences`
of the actor's own memory database, scoped to a Skill (`skill:<ns>/<name>`)
or to a memory space (`space:<space>`). The Host injects a scope's active
preferences into a turn whose Skills include that scope.

History and undo are the Memory Service's (`history` rows grouped by change
id, `SpaceTx.undo` with this module's handlers). The conflict check at save
is deterministic: the same subject with the opposite polarity (decided
2026-10-21, docs/DECISIONS.md "Accumulated memory M3").
"""

from __future__ import annotations

import difflib
import re
import secrets
import sqlite3
import unicodedata
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal

from memory.personal import HOST_MEMORY, PREFERENCES_SPACE
from memory.service import (
    MemoryService,
    MemoryServiceError,
    SpaceTx,
    new_change_id,
    now_iso,
)

MAX_TEXT = 300
MAX_SUBJECT = 120
#: Two subjects this alike (after normalisation) are the same subject.
SAME_SUBJECT = 0.8

Polarity = Literal["positive", "negative"]
Status = Literal["active", "removed", "replaced"]

_TABLE = "items"
_SCHEMA = """
CREATE TABLE IF NOT EXISTS {table} (
    preference_id TEXT PRIMARY KEY,
    scope TEXT NOT NULL,
    scope_label TEXT NOT NULL DEFAULT '',
    text TEXT NOT NULL,
    subject TEXT NOT NULL DEFAULT '',
    polarity TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    source_session TEXT NOT NULL DEFAULT '',
    source_message TEXT NOT NULL DEFAULT '',
    proposed_by TEXT NOT NULL DEFAULT '',
    replaced_by TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS {table}_scope ON {table}(scope, status);
CREATE TABLE IF NOT EXISTS {uses} (
    preference_id TEXT PRIMARY KEY,
    last_used_at TEXT NOT NULL,
    uses INTEGER NOT NULL DEFAULT 0
);
"""
#: When an answer last carried a preference (M5: the health check's unused
#: preferences, whichever channel the answer went to). Ids and times only.
_USES = "uses"

_SCOPE = re.compile(
    r"^(?:skill:[a-z0-9][a-z0-9_.-]*/[a-z0-9][a-z0-9_.-]*"
    r"|space:[a-z][a-z0-9-]*(?:/[a-z][a-z0-9-]*){1,2})$"
)
#: Words that turn a rule into "do not". A lone 別 counts only where it is
#: not part of a word (特別, 分別, 區別, 個別, 類別, 級別, 識別, 辨別, 告別).
_NEGATION = re.compile(
    r"不需要|不必要|不用|不要|不需|不必|不再|不會|無需|無須|毋須|禁止|免問|勿"
    r"|(?<![特分區個類級識辨告性差])別"
    r"|\bnever\b|\bdon'?t\b|\bdo not\b|\bdoesn'?t\b|\bdoes not\b|\bno need\b"
    r"|\bskip\b|\bwithout\b|\bstop\b|\bno longer\b",
    re.IGNORECASE,
)
#: Words that say "do", or when, and carry no subject: left out of it.
_FILLER = re.compile(
    r"以後|之後|往後|今後|從現在起|每次|一律|總是|永遠|都要|需要|必須|一定|請|都|要"
    r"|\balways\b|\bplease\b|\bmust\b|\bshould\b|\bfrom now on\b|\bany ?more\b",
    re.IGNORECASE,
)


class PreferenceError(MemoryServiceError):
    """A refusal by code (`preference_unknown`, `preference_scope_invalid`,
    `preference_text_empty`, `preference_duplicate`, `undo_conflict`)."""


@dataclass(frozen=True)
class Preference:
    preference_id: str
    scope: str
    scope_label: str
    text: str
    subject: str
    polarity: Polarity
    status: Status
    created_by: str
    created_at: str
    updated_at: str
    source_session: str
    source_message: str
    proposed_by: str
    replaced_by: str

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> Preference:
        return cls(**{name: row[name] for name in cls.__dataclass_fields__})

    def as_dict(self) -> dict[str, str]:
        return {name: getattr(self, name) for name in self.__dataclass_fields__}


@dataclass(frozen=True)
class Check:
    """What saving `text` in a scope would meet: the same rule already
    saved (`duplicates`), or the opposite rule (`conflicts`)."""

    duplicates: tuple[Preference, ...] = ()
    conflicts: tuple[Preference, ...] = ()


class PreferenceConflict(MemoryServiceError):
    """Saving would contradict active preferences; nothing was saved."""

    def __init__(self, conflicts: Sequence[Preference]) -> None:
        super().__init__("preference_conflict")
        self.conflicts = tuple(conflicts)


def normalise(text: str) -> str:
    """The rule as kept: NFKC, one line, trimmed, at most `MAX_TEXT`."""
    flat = " ".join(unicodedata.normalize("NFKC", text or "").split())
    return flat.strip(" 。.!！")[:MAX_TEXT]


def _folded(text: str) -> str:
    return unicodedata.normalize("NFKC", text or "").replace("’", "'").casefold()


def _bare(text: str) -> str:
    """No spaces, punctuation or apostrophes: what is compared."""
    return "".join(ch for ch in _folded(text) if ch.isalnum())


def polarity(text: str) -> Polarity:
    """`negative` when the rule says not to do something (不需要, 不用, 別,
    never, don't …), else `positive`."""
    return "negative" if _NEGATION.search(_folded(text)) else "positive"


def subject(text: str) -> str:
    """What the rule is about: the text without its negation and filler
    words (「執行時不需要問是否包含在職人員」 -> 「執行時問是否包含在職人員」)."""
    return _bare(_FILLER.sub(" ", _NEGATION.sub(" ", _folded(text))))


def same_subject(left: str, right: str) -> bool:
    if not left or not right:
        return False
    if left == right:
        return True
    return difflib.SequenceMatcher(None, left, right).ratio() >= SAME_SUBJECT


def check_scope(scope: str) -> str:
    if not _SCOPE.fullmatch(scope or ""):
        raise PreferenceError("preference_scope_invalid")
    return scope


def _new_id() -> str:
    return f"p-{secrets.token_hex(5)}"


class Preferences:
    """One actor's preferences, in the Host-managed space."""

    def __init__(self, service: MemoryService) -> None:
        self.service = service
        self._space = service.space(PREFERENCES_SPACE, asset=HOST_MEMORY)
        with self._space.transaction() as tx:
            tx.con.executescript(_SCHEMA.format(table=tx.table(_TABLE), uses=tx.table(_USES)))

    # -- reads -----------------------------------------------------------

    def _rows(self, tx: SpaceTx, where: str = "", args: Sequence[Any] = ()) -> list[Preference]:
        query = f"SELECT * FROM {tx.table(_TABLE)}"
        if where:
            query += f" WHERE {where}"
        query += " ORDER BY created_at DESC, preference_id"
        return [Preference.from_row(row) for row in tx.con.execute(query, tuple(args))]

    def get(self, preference_id: str) -> Preference | None:
        with self._space.transaction() as tx:
            found = self._rows(tx, "preference_id = ?", (preference_id,))
        return found[0] if found else None

    def listed(
        self, *, scope: str | None = None, include_inactive: bool = False
    ) -> list[Preference]:
        """Newest first."""
        where, args = [], []
        if scope is not None:
            where.append("scope = ?")
            args.append(scope)
        if not include_inactive:
            where.append("status = 'active'")
        with self._space.transaction() as tx:
            return self._rows(tx, " AND ".join(where), args)

    def active(self, scopes: Iterable[str]) -> list[Preference]:
        """The active preferences of these scopes, newest first."""
        wanted = sorted(set(scopes))
        if not wanted:
            return []
        marks = ",".join("?" for _ in wanted)
        with self._space.transaction() as tx:
            return self._rows(tx, f"status = 'active' AND scope IN ({marks})", wanted)

    def check(self, scope: str, text: str, given_subject: str = "") -> Check:
        """The deterministic conflict check: an active preference of the same
        scope about the same subject is a duplicate (same polarity) or a
        conflict (opposite polarity). The subject is compared as derived from
        both texts and, when the proposal named one, as given."""
        mine = subject(text)
        mine_given = _bare(given_subject)
        sign = polarity(text)
        duplicates: list[Preference] = []
        conflicts: list[Preference] = []
        for item in self.listed(scope=check_scope(scope)):
            about = same_subject(mine, subject(item.text)) or (
                bool(mine_given) and mine_given == _bare(item.subject)
            )
            if not about:
                continue
            (duplicates if polarity(item.text) == sign else conflicts).append(item)
        return Check(duplicates=tuple(duplicates), conflicts=tuple(conflicts))

    # -- writes ----------------------------------------------------------

    def save(
        self,
        scope: str,
        text: str,
        *,
        actor: str,
        scope_label: str = "",
        given_subject: str = "",
        source_session: str = "",
        source_message: str = "",
        proposed_by: str = "",
        replace: Sequence[str] = (),
        keep_conflicts: bool = False,
    ) -> tuple[Preference, str]:
        """Save one preference as one change; returns it and the change id.

        A conflict not named in `replace` refuses (`PreferenceConflict`)
        unless `keep_conflicts`; the preferences in `replace` become
        `replaced` in the same change, so one undo brings them back."""
        rule = normalise(text)
        if not rule:
            raise PreferenceError("preference_text_empty")
        check_scope(scope)
        found = self.check(scope, rule, given_subject)
        open_conflicts = [item for item in found.conflicts if item.preference_id not in replace]
        if open_conflicts and not keep_conflicts:
            raise PreferenceConflict(open_conflicts)
        change = new_change_id()
        stamp = now_iso()
        made = Preference(
            preference_id=_new_id(),
            scope=scope,
            scope_label=scope_label[:120],
            text=rule,
            subject=normalise(given_subject)[:MAX_SUBJECT],
            polarity=polarity(rule),
            status="active",
            created_by=actor,
            created_at=stamp,
            updated_at=stamp,
            source_session=source_session[:200],
            source_message=source_message[:200],
            proposed_by=proposed_by[:120],
            replaced_by="",
        )
        with self._space.transaction(immediate=True) as tx:
            table = tx.table(_TABLE)
            values = made.as_dict()
            columns = ", ".join(values)
            tx.con.execute(
                f"INSERT INTO {table} ({columns}) VALUES ({','.join('?' for _ in values)})",
                tuple(values.values()),
            )
            tx.record(
                change,
                actor,
                made.preference_id,
                "preference_add",
                new=rule,
                source="user",
                reason=f"saved from {source_session or 'a conversation'}",
                extra={"scope": scope},
            )
            for old_id in replace:
                old = self._rows(tx, "preference_id = ? AND status = 'active'", (old_id,))
                if not old:
                    continue
                tx.con.execute(
                    f"UPDATE {table} SET status = 'replaced', replaced_by = ?, updated_at = ? "
                    "WHERE preference_id = ?",
                    (made.preference_id, stamp, old_id),
                )
                tx.record(
                    change,
                    actor,
                    old_id,
                    "preference_replace",
                    old=old[0].text,
                    new=rule,
                    reason=f"replaced by {made.preference_id}",
                )
        return made, change

    def edit(
        self,
        preference_id: str,
        text: str,
        *,
        actor: str,
        replace: Sequence[str] = (),
        keep_conflicts: bool = False,
    ) -> tuple[Preference, str]:
        """Change an active preference's wording (the memory page, M4), as one
        change: the same deterministic check as a save, against the other
        active preferences of its scope. The same rule already saved refuses
        (`preference_duplicate`); a contradiction refuses
        (`PreferenceConflict`) unless named in `replace` (they become
        `replaced` in the same change) or `keep_conflicts`. Undo puts the
        words back."""
        rule = normalise(text)
        if not rule:
            raise PreferenceError("preference_text_empty")
        current = self.get(preference_id)
        if current is None or current.status != "active":
            raise PreferenceError("preference_unknown")
        if rule == current.text:
            raise PreferenceError("preference_unchanged")
        found = self.check(current.scope, rule)
        others = [item for item in found.duplicates if item.preference_id != preference_id]
        if others:
            raise PreferenceError("preference_duplicate")
        open_conflicts = [
            item
            for item in found.conflicts
            if item.preference_id != preference_id and item.preference_id not in replace
        ]
        if open_conflicts and not keep_conflicts:
            raise PreferenceConflict(open_conflicts)
        change = new_change_id()
        stamp = now_iso()
        with self._space.transaction(immediate=True) as tx:
            table = tx.table(_TABLE)
            tx.con.execute(
                f"UPDATE {table} SET text = ?, polarity = ?, subject = '', updated_at = ? "
                "WHERE preference_id = ?",
                (rule, polarity(rule), stamp, preference_id),
            )
            tx.record(
                change,
                actor,
                preference_id,
                "preference_edit",
                old=current.text,
                new=rule,
                source="user",
                reason="edited by the person",
                extra={"old": {"text": current.text, "subject": current.subject}},
            )
            for old_id in replace:
                if old_id == preference_id:
                    continue
                old = self._rows(tx, "preference_id = ? AND status = 'active'", (old_id,))
                if not old:
                    continue
                tx.con.execute(
                    f"UPDATE {table} SET status = 'replaced', replaced_by = ?, updated_at = ? "
                    "WHERE preference_id = ?",
                    (preference_id, stamp, old_id),
                )
                tx.record(
                    change,
                    actor,
                    old_id,
                    "preference_replace",
                    old=old[0].text,
                    new=rule,
                    reason=f"replaced by {preference_id}",
                )
        edited = self.get(preference_id)
        assert edited is not None
        return edited, change

    def remove(self, preference_id: str, *, actor: str, reason: str = "") -> str:
        """Stop applying one preference (kept, status `removed`); undoable."""
        change = new_change_id()
        with self._space.transaction(immediate=True) as tx:
            found = self._rows(tx, "preference_id = ? AND status = 'active'", (preference_id,))
            if not found:
                raise PreferenceError("preference_unknown")
            tx.con.execute(
                f"UPDATE {tx.table(_TABLE)} SET status = 'removed', updated_at = ? "
                "WHERE preference_id = ?",
                (now_iso(), preference_id),
            )
            tx.record(
                change,
                actor,
                preference_id,
                "preference_remove",
                old=found[0].text,
                reason=reason or "removed by the person",
            )
        return change

    def mark_used(self, preference_ids: Iterable[str], *, at: str | None = None) -> None:
        """An answer carried these preferences (M5); ids and the time only."""
        wanted = sorted(set(preference_ids))
        if not wanted:
            return
        stamp = at or now_iso()
        with self._space.transaction(immediate=True) as tx:
            for preference_id in wanted:
                tx.con.execute(
                    f"INSERT INTO {tx.table(_USES)} (preference_id, last_used_at, uses) "
                    "VALUES (?, ?, 1) ON CONFLICT(preference_id) DO UPDATE SET "
                    "last_used_at = MAX(last_used_at, excluded.last_used_at), uses = uses + 1",
                    (preference_id, stamp),
                )

    def last_used(self) -> dict[str, str]:
        """Each preference's latest use an answer recorded (`mark_used`)."""
        with self._space.transaction() as tx:
            return {
                str(row["preference_id"]): str(row["last_used_at"])
                for row in tx.con.execute(f"SELECT * FROM {tx.table(_USES)}")
            }

    def history(self, preference_id: str | None = None) -> list[sqlite3.Row]:
        with self._space.transaction() as tx:
            return tx.history(preference_id)

    def undo(self, change_id: str, *, actor: str) -> tuple[int, str]:
        """Revert one change (a save, a replace, a removal) as a new change;
        refused (`undo_conflict`) when a later change touched the same
        preference."""
        with self._space.transaction(immediate=True) as tx:
            for row in tx.history(change_id=change_id, limit=1_000):
                if tx.changed_after(row["entity_id"], change_id):
                    raise PreferenceError("undo_conflict")
            reverted, new_change = tx.undo(change_id, actor=actor, handlers=_HANDLERS)
        return len(reverted), new_change


def _set_status(tx: SpaceTx, preference_id: str, status: str, replaced_by: str = "") -> bool:
    return (
        tx.con.execute(
            f"UPDATE {tx.table(_TABLE)} SET status = ?, replaced_by = ?, updated_at = ? "
            "WHERE preference_id = ?",
            (status, replaced_by, now_iso(), preference_id),
        ).rowcount
        > 0
    )


def _undo_add(tx: SpaceTx, row: sqlite3.Row, extra: Mapping[str, Any], change: str) -> bool:
    return _set_status(tx, row["entity_id"], "removed")


def _undo_back(tx: SpaceTx, row: sqlite3.Row, extra: Mapping[str, Any], change: str) -> bool:
    return _set_status(tx, row["entity_id"], "active")


def _undo_edit(tx: SpaceTx, row: sqlite3.Row, extra: Mapping[str, Any], change: str) -> bool:
    old = extra.get("old") or {}
    words = str(old.get("text") or row["old"])
    return (
        tx.con.execute(
            f"UPDATE {tx.table(_TABLE)} SET text = ?, polarity = ?, subject = ?, updated_at = ? "
            "WHERE preference_id = ?",
            (words, polarity(words), str(old.get("subject") or ""), now_iso(), row["entity_id"]),
        ).rowcount
        > 0
    )


_HANDLERS = {
    "preference_add": _undo_add,
    "preference_edit": _undo_edit,
    "preference_replace": _undo_back,
    "preference_remove": _undo_back,
}
