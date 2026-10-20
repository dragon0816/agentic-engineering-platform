"""「為什麼這樣做」 (accumulated memory M5, docs/phases/ACCUMULATED_MEMORY.md §8.5).

Each answer records what of the person's memory it used: the preferences the
Host injected (`preferences_used`, M3) and the memory items the turn's tools
read (`memory_used`): contacts a business-cards tool returned, a sync state
a harvest moved, notes the answer cites. Only references are kept
(`<space>:<kind>:<id>`), never content. Agent Web shows a small 「為什麼」
under such an answer listing them, each linked to the memory page where it
can be edited or deleted; Telegram answers `/why` for the chat's last turn.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from capabilities.business_cards.space import CONTACTS_ORG
from capabilities.business_cards.store import CardStore, CardStoreError
from memory import personal
from memory.service import MemoryServiceError

#: At most this many items a turn records (the message contract's bound).
MAX_USED = 40
_PERSON_ID = re.compile(r"^p-[0-9a-f]{6,20}$")
_NOTE_CITE = re.compile(r"\[筆記\s*(n-[0-9a-z]{4,20})\]")
_DOMAIN = re.compile(r"^[a-z0-9.-]{1,120}$")
SEARCH_NOTES = "notes__search"
CARDS_PREFIX = "cards__"
#: What Telegram's /why says when the chat has no answer that used memory.
NOTHING = "上一則回答沒有用到你的偏好或記憶。"


def _people_in(value: Any, found: list[str], depth: int = 0) -> None:
    """Person ids anywhere in a business-cards tool's result."""
    if depth > 6 or len(found) >= MAX_USED:
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if (
                key in ("person_id", "existing_person_id")
                and isinstance(item, str)
                and _PERSON_ID.fullmatch(item)
            ):
                found.append(item)
            else:
                _people_in(item, found, depth + 1)
    elif isinstance(value, list):
        for item in value:
            _people_in(item, found, depth + 1)


def _domains_in(data: Mapping[str, Any]) -> list[str]:
    harvest = data.get("harvest") if isinstance(data.get("harvest"), dict) else data
    windows = harvest.get("domains") if isinstance(harvest, dict) else None
    found = []
    for item in windows if isinstance(windows, list) else ():
        domain = item.get("domain") if isinstance(item, dict) else None
        if isinstance(domain, str) and _DOMAIN.fullmatch(domain.casefold()):
            found.append(domain.casefold())
    return found


def memory_used_in(tools: Iterable[Any], answer: str) -> tuple[str, ...]:
    """The memory items a turn's tools read, as references: contacts a
    business-cards tool returned (`contacts/org:person:<id>`), the sync
    states a harvest touched (`contacts/org:sync:<domain>`) and the notes
    the answer cites from a notes search (`personal/notes:note:<id>`)."""
    refs: list[str] = []
    searched: set[str] = set()
    for item in tools:
        host = getattr(item, "host", None)
        name = str(getattr(item, "name", ""))
        if host is None or host.status != "succeeded" or not isinstance(host.data, dict):
            continue
        if name == SEARCH_NOTES:
            for note in host.data.get("notes") or ():
                if isinstance(note, dict) and isinstance(note.get("note_id"), str):
                    searched.add(note["note_id"])
        elif name.startswith(CARDS_PREFIX):
            people: list[str] = []
            _people_in(host.data, people)
            refs.extend(f"{CONTACTS_ORG}:person:{person}" for person in people)
            refs.extend(f"{CONTACTS_ORG}:sync:{domain}" for domain in _domains_in(host.data))
    for cited in _NOTE_CITE.findall(answer or ""):
        if cited in searched:
            refs.append(f"{personal.NOTES_SPACE}:note:{cited}")
    return tuple(dict.fromkeys(refs))[:MAX_USED]


def split_ref(ref: str) -> tuple[str, str, str]:
    space, _, rest = ref.partition(":")
    kind, _, item = rest.partition(":")
    return space, kind, item


class MemoryWhy:
    """What one answer used, for the person: Agent Web's 「為什麼」 list and
    Telegram's /why. Reads the actor's own memory only."""

    def __init__(self, web: Any) -> None:
        self.web = web

    def explain(
        self, actor: str, preferences_used: Sequence[str], memory_used: Sequence[str]
    ) -> dict[str, Any]:
        """Each item with a label and where on the memory page it is
        (`tab`, `id`); an item since deleted says so."""
        memory = self.web.personal_memory
        items: list[dict[str, Any]] = []
        try:
            prefs = memory.preferences(actor)
        except MemoryServiceError:
            prefs = None
        for preference_id in preferences_used:
            found = prefs.get(str(preference_id)) if prefs is not None else None
            items.append(
                {
                    "kind": "preference",
                    "id": str(preference_id),
                    "label": found.text if found is not None else str(preference_id),
                    "detail": (found.scope_label or found.scope) if found is not None else "",
                    "gone": found is None or found.status != "active",
                    "tab": "preferences",
                }
            )
        cards: CardStore | None = None
        notes = None
        for ref in memory_used:
            space, kind, item = split_ref(str(ref))
            entry: dict[str, Any] = {"kind": kind, "id": item, "label": item, "detail": ""}
            if space == CONTACTS_ORG and kind == "person":
                if cards is None:
                    cards = self._cards(actor)
                entry["tab"] = "data"
                try:
                    if cards is None:
                        raise CardStoreError("person_unknown")
                    person = cards.view(item)
                    entry["label"] = person.name or person.romanised_name
                    entry["detail"] = " · ".join(
                        part for part in (person.company, person.department, person.title) if part
                    )
                    entry["gone"] = False
                except CardStoreError:
                    entry["gone"] = True
            elif space == CONTACTS_ORG and kind == "sync":
                entry.update(tab="sync", label=item, detail="整理進度", gone=False)
            elif space == personal.NOTES_SPACE and kind == "note":
                if notes is None:
                    notes = memory.notes(actor)
                found = notes.get(item)
                entry["tab"] = "notes"
                entry["gone"] = found is None or found.status != "active"
                if found is not None:
                    entry["label"] = " ".join(found.text.split())[:60]
                    entry["detail"] = item
            else:
                continue
            items.append(entry)
        return {"ok": True, "items": items}

    def _cards(self, actor: str) -> CardStore | None:
        from host_runtime.memory_spaces import registry

        layout = self.web.runtime.layout
        try:
            return CardStore.for_actor(layout.workspace_root, actor, registry(layout))
        except CardStoreError:
            return None

    def for_message(self, session_id: str, message_id: str) -> dict[str, Any]:
        """Agent Web: one stored answer of the signed-in actor."""
        actor = str(self.web.runtime.actor)
        record = self.web.runtime.state.conversation(session_id, actor)
        message = next(
            (
                item
                for item in (record.messages if record is not None else ())
                if item.message_id == message_id and item.role == "assistant"
            ),
            None,
        )
        if message is None:
            return {"ok": False, "code": "message_unknown", "message": "找不到這則回答"}
        return self.explain(actor, message.preferences_used, message.memory_used)

    def text(self, actor: str, preferences_used: Sequence[str], memory_used: Sequence[str]) -> str:
        """Telegram's /why: what the last answer used, and where to change it."""
        listed = self.explain(actor, preferences_used, memory_used)["items"]
        if not listed:
            return NOTHING
        heads = {
            "preference": "偏好",
            "person": "聯絡人",
            "sync": "整理進度",
            "note": "筆記",
        }
        lines = ["上一則回答用到："]
        for item in listed:
            detail = f"（{item['detail']}）" if item.get("detail") else ""
            gone = "（已刪除）" if item.get("gone") else ""
            lines.append(
                f"- {heads.get(item['kind'], item['kind'])}：{item['label']}{detail}{gone}"
            )
        lines.append("要修改或刪除，請到 Agent Web 的「記憶」頁。")
        return "\n".join(lines)

    def remember(self, actor: str, preferences_used: Sequence[str], at: str | None = None) -> None:
        """An answer carried these preferences: when each was last used (the
        health check's unused preferences). Never fails the turn."""
        if not preferences_used:
            return
        try:
            self.web.personal_memory.preferences(actor).mark_used(preferences_used, at=at)
        except (MemoryServiceError, OSError):
            return
