"""The Agent Web memory page (accumulated memory M4).

docs/phases/ACCUMULATED_MEMORY.md §6 (the sections 待確認, 偏好, 資料, 同步進度,
紀錄) and §3.9 (筆記). Every route acts for the signed-in actor only, in that
actor's own memory database (`memory/<actor-key>/memory.sqlite`): an id from
another actor's database names nothing here. Each change is recorded as
`<actor> via web`. No model tool reaches any of this; the routes sit behind
the page token like every other Agent Web route.

What it reuses: the Memory Service (M1, M2: proposals, sync state and its
history), the business-cards store for the `contacts/org` decisions (the
same `edit` the chat uses for 「email 正確」 and 「用新的」) and its people
and history, and the M3 preferences and notes. What it adds: an overview of
every space, the person's own export and deletion of a space (§3.6; the
deletion leaves a row without content), a preference edit through the M3
conflict check, and a note edit, tag and link from the page.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from capabilities.business_cards.contracts import (
    FIELD_LABELS,
    FIELDS,
    SOURCE_LABELS,
    PersonRef,
)
from capabilities.business_cards.space import CONTACTS_ORG
from capabilities.business_cards.store import DB_FILE as CARDS_DB
from capabilities.business_cards.store import CardStore, CardStoreError, store_dir
from host_runtime.conversations import MAX_STORED_MESSAGES
from host_runtime.memory_spaces import one_scan
from memory import personal
from memory.notes import ENTITY_REF, Note, NoteError, Notes, clean_tags
from memory.preferences import Preference, PreferenceConflict, Preferences
from memory.service import MemoryService, MemoryServiceError, new_change_id
from telemetry.store import RETENTION_BYTES, RETENTION_DAYS

LOCAL_ZONE = ZoneInfo("Asia/Taipei")
HOST_MANAGER = "host/memory"
#: How a space, its manager, its kinds and its retention are named.
SPACE_LABELS = {
    CONTACTS_ORG: "聯絡人與組織",
    personal.PREFERENCES_SPACE: "偏好",
    personal.NOTES_SPACE: "筆記",
}
MANAGER_LABELS = {
    "engineering/business-cards": "名片／組織圖",
    HOST_MANAGER: "Agent（內建）",
}
KIND_LABELS = {
    "entities": "實體",
    "sync_state": "同步進度",
    "preferences": "偏好",
    "notes": "筆記",
    "facts": "事實",
}
SENSITIVITY_LABELS = {
    "PUBLIC": "公開",
    "INTERNAL": "內部",
    "CONFIDENTIAL": "機密",
    "RESTRICTED": "限閱",
}
TABLE_LABELS = {
    CONTACTS_ORG: {"people": "聯絡人", "reporting_lines": "匯報線", "candidates": "候選"},
    personal.PREFERENCES_SPACE: {"items": "偏好"},
    personal.NOTES_SPACE: {"items": "筆記"},
}
#: The overview's sections, in the order they are built; `only=` names some.
SECTIONS = (
    "proposals",
    "preferences",
    "notes",
    "spaces",
    "sync",
    "records",
    "deletions",
    "health",
)
#: A proposal decision on the page: keep the stored value, or take the new one.
DECISIONS = ("keep", "accept")
#: What a refusal means, for the person.
MESSAGES = {
    "memory_space_unknown": "找不到這個記憶空間",
    "proposal_unknown": "找不到這個待確認項目",
    "proposal_closed": "這個項目已經處理過了",
    "proposal_action_unknown": "只能「保留原值」或「改用新值」",
    "proposal_accept_unsupported": "這個空間的待確認項目只能在這裡保留原值",
    "preference_unknown": "找不到這條偏好（可能已刪除）",
    "preference_unchanged": "內容沒有改變",
    "preference_text_empty": "偏好不能是空的",
    "preference_duplicate": "已經有一條相同的偏好",
    "preference_conflict": "這條和同一個 Skill 既有的偏好矛盾，請選一個做法",
    "note_unknown": "找不到這則筆記（可能已刪除）",
    "note_text_empty": "筆記不能是空的",
    "note_entity_invalid": "關聯的對象格式不對",
    "note_tags_invalid": "標籤格式不對",
    "person_unknown": "找不到這位聯絡人",
    "sync_unknown": "找不到這個同步進度",
    "sync_history_unknown": "找不到上次的重設紀錄",
    "sync_nothing_to_restore": "最近一次不是重設，沒有可復原的",
    "memory_kind_not_declared": "這個空間沒有同步進度",
    "space_delete_unconfirmed": "請輸入空間名稱確認刪除",
    "change_unknown": "找不到這次變更",
    "change_already_undone": "這次變更已經復原過了",
    "undo_conflict": "之後還有其他變更動到同一筆，不能直接復原",
    "memory_route_unknown": "沒有這個功能",
}

#: GET and POST routes of the page (besides M3's notes and preferences lists,
#: `/api/memory/delete` and `/api/memory/undo`).
GET_ROUTES = (
    "/api/memory/overview",
    "/api/memory/people",
    "/api/memory/person",
    "/api/memory/export",
    "/api/memory/notes/export",
    # M5: what one answer used (「為什麼」).
    "/api/memory/why",
)
POST_ROUTES = (
    "/api/memory/proposals/decide",
    "/api/memory/proposals/undo",
    "/api/memory/preferences/edit",
    "/api/memory/notes/edit",
    "/api/memory/sync/reset",
    "/api/memory/sync/restore",
    "/api/memory/space/delete",
    # M5: the memory health check (「立即檢查」, a finding's press, settings).
    "/api/memory/health/run",
    "/api/memory/health/decide",
    # 復原 of a finding's fix, which reopens the finding (#233).
    "/api/memory/health/undo",
    "/api/memory/health/settings",
)


def _refused(code: str) -> dict[str, Any]:
    return {"ok": False, "code": code, "message": MESSAGES.get(code, code)}


def local_time(value: str) -> str:
    """`2026-10-21 14:03` in Asia/Taipei, from a stored UTC ISO stamp."""
    if not value:
        return ""
    try:
        moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return value
    if moment.tzinfo is None:
        return moment.strftime("%Y-%m-%d %H:%M")
    return moment.astimezone(LOCAL_ZONE).strftime("%Y-%m-%d %H:%M")


def retention_label(value: str | None) -> str:
    if not value or value == "until_deleted":
        return "保留到刪除"
    units = {"D": "天", "M": "個月", "Y": "年"}
    number, unit = value[1:-1], value[-1:]
    return f"{number} {units.get(unit, unit)}" if number.isdigit() else value


def _scope_label(scope: str, saved: str) -> str:
    if saved:
        return saved
    kind, _, name = scope.partition(":")
    if kind == "skill":
        return MANAGER_LABELS.get(name, name)
    return SPACE_LABELS.get(name, name)


class MemoryPage:
    """The memory page's routes for one Agent Web (its signed-in actor)."""

    def __init__(self, web: Any) -> None:
        self.web = web

    # -- the actor's stores ---------------------------------------------

    @property
    def actor(self) -> str:
        return str(self.web.runtime.actor)

    @property
    def who(self) -> str:
        return f"{self.actor} via web"

    def service(self) -> MemoryService:
        service: MemoryService = self.web.personal_memory.service(self.actor)
        return service

    def cards(self, service: MemoryService | None = None) -> CardStore:
        """The actor's `contacts/org` store, on `service` when given."""
        layout = self.web.runtime.layout
        if service is None:
            from host_runtime.memory_spaces import registry

            return CardStore.for_actor(layout.workspace_root, self.actor, registry(layout))
        return CardStore(service, legacy=store_dir(layout.workspace_root, self.actor) / CARDS_DB)

    # -- GET --------------------------------------------------------------

    def get(self, path: str, query: Mapping[str, str]) -> dict[str, Any]:
        handlers: dict[str, Callable[[], dict[str, Any]]] = {
            "/api/memory/overview": lambda: self.overview(
                [item for item in query.get("only", "").split(",") if item]
            ),
            "/api/memory/people": lambda: self.people(
                query.get("q", ""), query.get("status", "any")
            ),
            "/api/memory/person": lambda: self.person(query.get("person_id", "")),
            "/api/memory/export": lambda: self.export(query.get("space", "")),
            "/api/memory/notes/export": lambda: self.export_notes(
                [item for item in query.get("ids", "").split(",") if item]
            ),
            "/api/memory/why": lambda: self.web.memory_why.for_message(
                query.get("session_id", ""), query.get("message_id", "")
            ),
        }
        handler = handlers.get(path)
        if handler is None:
            return _refused("memory_route_unknown")
        try:
            # One look at the installed manifests and one connection to the
            # actor's database for the whole request (B3).
            with one_scan(self.web.runtime.layout), self.service().session():
                return handler()
        except CardStoreError as error:
            return _refused(error.code)
        except MemoryServiceError as error:
            return _refused(error.code)

    def overview(self, only: Sequence[str] = ()) -> dict[str, Any]:
        """Everything the page shows, in one answer; with `only`, just those
        sections (the page refreshes what an action changed; B3)."""
        wanted = {item for item in only if item in SECTIONS} or set(SECTIONS)
        service = self.service()
        # Opening the stores creates their tables, so the counts are complete.
        # Every store shares the one service (and, inside `get`, its one
        # connection).
        preferences: list[Preference] = []
        notes: list[Note] = []
        if wanted & {"preferences", "spaces"}:
            preferences = Preferences(service).listed()
        if wanted & {"notes", "spaces"}:
            notes = Notes(service).listed()
        cards: CardStore | None = None
        if wanted & {"proposals", "notes", "spaces"}:
            try:
                cards = self.cards(service)
            except CardStoreError:
                cards = None
        conversations: list[Any] = []
        if wanted & {"preferences", "records"}:
            conversations = self._conversations()
        builders: dict[str, Callable[[], Any]] = {
            "proposals": lambda: self._proposals(service, cards),
            "preferences": lambda: self._preferences(preferences, conversations),
            "notes": lambda: self._notes(notes, cards),
            "spaces": lambda: self._spaces(service, cards, len(preferences), len(notes)),
            "sync": lambda: self._sync(service),
            "records": lambda: self._records(conversations),
            "deletions": lambda: [
                {**item, "at_local": local_time(item["at"]), "label": self._space_label(item)}
                for item in service.deletions()
            ],
            # M5: the health check's open findings, its settings and last run.
            "health": lambda: self.web.memory_health.overview(self.actor),
        }
        answer: dict[str, Any] = {"ok": True, "actor": self.actor}
        for name in SECTIONS:
            if name in wanted:
                answer[name] = builders[name]()
        return answer

    def _conversations(self) -> list[Any]:
        """The actor's latest 100 conversations, read once per overview."""
        try:
            return list(self.web.runtime.state.conversations(self.actor, limit=100))
        except (AttributeError, ValueError):
            return []

    @staticmethod
    def _space_label(item: Mapping[str, Any]) -> str:
        return SPACE_LABELS.get(str(item["space"]), str(item["space"]))

    def _proposals(self, service: MemoryService, cards: CardStore | None) -> list[dict[str, Any]]:
        people: dict[int, Any] = {}
        if cards is not None:
            listed, _ = cards.proposals(None, limit=200)
            people = {item.proposal_id: item for item in listed}
        found: list[dict[str, Any]] = []
        for row in service.open_proposals():
            space = str(row["space"])
            contact = people.get(int(row["proposal_id"])) if space == CONTACTS_ORG else None
            evidence = str(row.get("evidence_kind") or row["source_kind"])
            item: dict[str, Any] = {
                "space": space,
                "space_label": SPACE_LABELS.get(space, space),
                "proposal_id": row["proposal_id"],
                "entity_id": row["entity_id"],
                "entity_label": row["entity_id"],
                "field": row["field"],
                "field_label": row["field"],
                "current": row["current"],
                "proposed": row["proposed"],
                "source": evidence,
                "source_label": evidence,
                "evidence_date": row.get("evidence_date") or "",
                "evidence_ref": row.get("evidence_ref") or "",
                "created_at": row["created_at"],
                "created_at_local": local_time(str(row["created_at"])),
                "actions": ["keep"],
                "person_id": "",
            }
            if space == CONTACTS_ORG:
                item["field_label"] = FIELD_LABELS.get(str(row["field"]), row["field"])
                item["source_label"] = SOURCE_LABELS.get(evidence, evidence)
                if contact is not None:
                    company = f"（{contact.company}）" if contact.company else ""
                    item["entity_label"] = f"{contact.name}{company}"
                    item["current"] = contact.current
                    item["person_id"] = contact.person_id
                if row["field"] in FIELDS:
                    item["actions"] = ["keep", "accept"]
            found.append(item)
        return found

    @staticmethod
    def _used(records: Sequence[Any]) -> dict[str, list[dict[str, str]]]:
        """Which answers carried each preference (`preferences_used`), the
        newest first, from the actor's latest 100 conversations."""
        used: dict[str, list[dict[str, str]]] = {}
        for record in records:
            for message in record.messages:
                for preference_id in getattr(message, "preferences_used", ()) or ():
                    used.setdefault(str(preference_id), []).append(
                        {
                            "session_id": record.session_id,
                            "message_id": message.message_id,
                            "title": record.title,
                            "at": message.created_at.isoformat(),
                        }
                    )
        for items in used.values():
            items.sort(key=lambda entry: entry["at"], reverse=True)
        return used

    def _preferences(
        self, listed: list[Preference], conversations: Sequence[Any]
    ) -> list[dict[str, Any]]:
        used = self._used(conversations)
        groups: dict[str, dict[str, Any]] = {}
        for item in listed:
            group = groups.setdefault(
                item.scope,
                {"scope": item.scope, "label": _scope_label(item.scope, item.scope_label)},
            )
            uses = used.get(item.preference_id, [])
            group.setdefault("items", []).append(
                {
                    **item.as_dict(),
                    "created_at_local": local_time(item.created_at),
                    "updated_at_local": local_time(item.updated_at),
                    "used_count": len(uses),
                    "used": [{**entry, "at_local": local_time(entry["at"])} for entry in uses[:5]],
                }
            )
        return sorted(groups.values(), key=lambda group: str(group["label"]))

    def _entity_labels(self, refs: set[str], cards: CardStore | None) -> dict[str, str]:
        labels: dict[str, str] = {}
        for ref in sorted(refs):
            space, _, rest = ref.partition(":")
            kind, _, entity = rest.partition(":")
            label = ref
            if space == CONTACTS_ORG and kind == "person" and cards is not None:
                try:
                    person = cards.view(entity)
                    company = f"（{person.company}）" if person.company else ""
                    label = f"{person.name or person.romanised_name}{company}"
                except CardStoreError:
                    label = f"{entity}（已不在聯絡人中）"
            labels[ref] = label
        return labels

    def _notes(self, listed: list[Note], cards: CardStore | None) -> dict[str, Any]:
        tags: dict[str, str] = {}
        refs: set[str] = set()
        for note in listed:
            for tag in note.tags:
                tags.setdefault(tag.casefold(), tag)
            refs.update(note.entities)
        return {
            "notes": [
                {
                    **note.as_dict(),
                    "created_at_local": local_time(note.created_at),
                    "updated_at_local": local_time(note.updated_at),
                }
                for note in listed
            ],
            "tags": sorted(tags.values(), key=str.casefold),
            "entities": self._entity_labels(refs, cards),
        }

    def _spaces(
        self, service: MemoryService, cards: CardStore | None, preferences: int, notes: int
    ) -> list[dict[str, Any]]:
        from host_runtime.memory_spaces import manager_states

        states = manager_states(self.web.runtime.layout)
        found: list[dict[str, Any]] = []
        for item in service.overview():
            summary = item["summary"]
            declaration = summary.declaration
            manager = summary.manager
            state = "host" if manager == HOST_MANAGER else states.get(manager, "missing")
            labels = TABLE_LABELS.get(summary.space, {})
            counts = [
                {"name": name, "label": labels.get(name, name), "count": count}
                for name, count in item["tables"].items()
            ]
            if summary.space == personal.PREFERENCES_SPACE:
                counts = [{"name": "items", "label": "使用中的偏好", "count": preferences}]
            elif summary.space == personal.NOTES_SPACE:
                counts = [{"name": "items", "label": "筆記", "count": notes}]
            found.append(
                {
                    "space": summary.space,
                    "label": SPACE_LABELS.get(summary.space, summary.space),
                    "manager": manager,
                    "manager_label": MANAGER_LABELS.get(manager, manager),
                    "manager_state": state,
                    "orphan": state == "missing",
                    "kinds": list(declaration.kinds),
                    "kind_labels": [KIND_LABELS.get(kind, kind) for kind in declaration.kinds],
                    "sensitivity": declaration.sensitivity,
                    "sensitivity_label": SENSITIVITY_LABELS.get(
                        str(declaration.sensitivity), str(declaration.sensitivity)
                    ),
                    "retention": declaration.retention,
                    "retention_label": retention_label(declaration.retention),
                    "counts": counts,
                    "observations": item["observations"],
                    "open_proposals": item["open_proposals"],
                    "sync_states": item["sync_states"],
                    "last_updated": item["last_updated"],
                    "last_updated_local": local_time(item["last_updated"]),
                    "view": "people" if summary.space == CONTACTS_ORG and cards else "",
                }
            )
        return found

    def _sync(self, service: MemoryService) -> list[dict[str, Any]]:
        found: list[dict[str, Any]] = []
        for item in service.sync_overview():
            state = item["state"]
            latest = item["latest"]
            found.append(
                {
                    "space": item["space"],
                    "space_label": SPACE_LABELS.get(item["space"], item["space"]),
                    "source": item["source"],
                    "key": item["key"],
                    "state": None
                    if state is None
                    else {
                        "last_message_date": state.last_message_date,
                        "last_message_date_local": local_time(state.last_message_date),
                        "extractor_version": state.extractor_version,
                        "updated_at": state.updated_at,
                        "updated_at_local": local_time(state.updated_at),
                        "updated_by": state.updated_by,
                    },
                    "latest": None
                    if latest is None
                    else {
                        "history_id": latest.history_id,
                        "action": latest.action,
                        "at_local": local_time(latest.at),
                        "actor": latest.actor,
                    },
                    "can_reset": state is not None,
                    "can_restore": latest is not None and latest.action == "reset",
                }
            )
        return found

    def _records(self, conversations: Sequence[Any]) -> dict[str, Any]:
        from host_runtime.experience import load_settings

        return {
            "conversations": {
                "count": len(conversations),
                "max_messages": MAX_STORED_MESSAGES,
                "retention_label": "保留到你刪除",
            },
            "runs": {"days": RETENTION_DAYS, "max_mb": RETENTION_BYTES // (1024 * 1024)},
            "experience": {
                "retention_days": load_settings(
                    self.web.runtime.layout.workspace_root
                ).retention_days
            },
        }

    def people(self, query: str, status: str) -> dict[str, Any]:
        """`contacts/org`'s own view: people, by search and 在職/已離職."""
        wanted = status if status in ("active", "left") else "any"
        store = self.cards()
        if query.strip():
            found, total = store.find(query.strip()[:120], status=wanted, limit=200)
        else:
            found, total = store.list_people(company="", source="", status=wanted, limit=200)
        return {
            "ok": True,
            "total": total,
            "people": [
                {
                    "person_id": item.person_id,
                    "name": item.name,
                    "romanised_name": item.romanised_name,
                    "company": item.company,
                    "department": item.department,
                    "title": item.title,
                    "email": item.email,
                    "status": item.status,
                    "status_label": item.status_label,
                    "open_proposals": item.open_proposals,
                    "updated_at_local": item.updated_at_local,
                }
                for item in found
            ],
        }

    def person(self, person_id: str) -> dict[str, Any]:
        """One person's history (changes, sightings, open proposals)."""
        if not person_id:
            return _refused("person_unknown")
        result = self.cards().history(PersonRef(person_id=person_id[:40]), limit=100)
        return {"ok": True, **result.model_dump(mode="json")}

    def export(self, space: str) -> dict[str, Any]:
        data = self.service().export_space(space)
        stamp = datetime.now(LOCAL_ZONE).strftime("%Y%m%d-%H%M")
        return {
            "ok": True,
            "filename": f"memory-{space.replace('/', '-')}-{stamp}.json",
            "data": data,
        }

    def export_notes(self, ids: list[str]) -> dict[str, Any]:
        """The chosen notes (all active ones when none is named) as Markdown."""
        notes = self.web.personal_memory.notes(self.actor).listed()
        if ids:
            wanted = set(ids)
            notes = [note for note in notes if note.note_id in wanted]
        try:
            cards: CardStore | None = self.cards()
        except CardStoreError:
            cards = None
        labels = self._entity_labels({ref for note in notes for ref in note.entities}, cards)
        now = datetime.now(LOCAL_ZONE)
        lines = [f"# 筆記匯出（{now:%Y-%m-%d %H:%M}）", ""]
        for note in notes:
            lines.append(f"## {note.note_id} · {local_time(note.created_at)}")
            lines.append("")
            if note.tags:
                lines.append("標籤：" + "、".join(note.tags))
            if note.entities:
                lines.append("關聯：" + "、".join(labels.get(ref, ref) for ref in note.entities))
            if note.source_session:
                lines.append(f"來源：對話 {note.source_session}，訊息 {note.source_message}")
            lines.extend(("", note.text.strip(), ""))
        return {
            "ok": True,
            "count": len(notes),
            "filename": f"notes-{now:%Y%m%d-%H%M}.md",
            "markdown": "\n".join(lines).rstrip() + "\n",
        }

    # -- POST -------------------------------------------------------------

    def post(self, path: str, body: Mapping[str, Any]) -> dict[str, Any]:
        handlers: dict[str, Callable[[Mapping[str, Any]], dict[str, Any]]] = {
            "/api/memory/proposals/decide": self.decide,
            "/api/memory/proposals/undo": self.undo_decision,
            "/api/memory/preferences/edit": self.edit_preference,
            "/api/memory/notes/edit": self.edit_note,
            "/api/memory/sync/reset": self.reset_sync,
            "/api/memory/sync/restore": self.restore_sync,
            "/api/memory/space/delete": self.delete_space,
            "/api/memory/health/run": lambda _body: self.web.memory_health.check_now(self.actor),
            "/api/memory/health/decide": lambda body: self.web.memory_health.decide(
                self.actor, body
            ),
            "/api/memory/health/undo": lambda body: self.web.memory_health.undo(self.actor, body),
            "/api/memory/health/settings": lambda body: self.web.memory_health.update_settings(
                self.actor, body
            ),
        }
        handler = handlers.get(path)
        if handler is None:
            return _refused("memory_route_unknown")
        try:
            with one_scan(self.web.runtime.layout), self.service().session():
                return handler(body)
        except PreferenceConflict as conflict:
            return {
                **_refused("preference_conflict"),
                "conflicts": [
                    {"preference_id": item.preference_id, "text": item.text}
                    for item in conflict.conflicts
                ],
            }
        except CardStoreError as error:
            return _refused(error.code)
        except MemoryServiceError as error:
            return _refused(error.code)

    def decide(self, body: Mapping[str, Any]) -> dict[str, Any]:
        """保留原值 (`keep`) or 改用新值 (`accept`) for one open proposal."""
        space = str(body.get("space") or "")
        action = str(body.get("action") or "")
        if action not in DECISIONS:
            return _refused("proposal_action_unknown")
        try:
            proposal_id = int(body.get("proposal_id") or 0)
        except (TypeError, ValueError):
            return _refused("proposal_unknown")
        service = self.service()
        row = service.proposal(space, proposal_id) if space else None
        if row is None:
            return _refused("proposal_unknown")
        if row["state"] != "open":
            return _refused("proposal_closed")
        field = str(row["field"])
        if space == CONTACTS_ORG and field in FIELDS:
            ref = PersonRef(person_id=str(row["entity_id"]))
            store = self.cards()
            if action == "keep":
                _, _, _, change = store.edit(
                    ref, {}, actor=self.who, reason="kept on the memory page", confirm=[field]
                )
                message = "已保留原值。"
            else:
                _, _, _, change = store.edit(
                    ref,
                    {field: str(row["proposed"])},
                    actor=self.who,
                    reason="taken on the memory page",
                )
                message = "已改用新值。"
            still = service.proposal(space, proposal_id)
            if still is not None and still["state"] == "open":
                # Nothing for the store to change (the value already is the
                # one decided): the proposal is closed all the same.
                self._close(service, row, "rejected" if action == "keep" else "accepted")
            return {"ok": True, "change_id": change, "undo": bool(change), "message": message}
        if action == "accept":
            return _refused("proposal_accept_unsupported")
        # Another space: the stored value stays and the proposal is closed;
        # its manager's own view is not touched.
        change = self._close(service, row, "rejected")
        return {"ok": True, "change_id": change, "undo": False, "message": "已保留原值。"}

    def _close(self, service: MemoryService, row: Mapping[str, Any], state: str) -> str:
        """Close one proposal as the person decided, with a history row."""
        change = new_change_id()
        with service.owned(str(row["space"])).transaction(immediate=True) as tx:
            tx.set_proposal_state(int(row["proposal_id"]), state, actor=self.who)
            tx.record(
                change,
                self.who,
                str(row["entity_id"]),
                f"proposal_{state}",
                field_name=str(row["field"]),
                old=str(row["proposed"]),
                new=str(row["current"]),
                reason="decided on the memory page",
                extra={"proposal_id": row["proposal_id"]},
            )
        return change

    def undo_decision(self, body: Mapping[str, Any]) -> dict[str, Any]:
        """復原 a `contacts/org` decision made on the page (the store's undo)."""
        change = str(body.get("change_id") or "")
        if str(body.get("space") or CONTACTS_ORG) != CONTACTS_ORG or not change:
            return _refused("change_unknown")
        reverted, _ = self.cards().undo(change, actor=self.who)
        return {"ok": True, "reverted": len(reverted), "message": "已復原。"}

    def edit_preference(self, body: Mapping[str, Any]) -> dict[str, Any]:
        """New wording for a preference, through the M3 conflict check; on a
        contradiction the page asks 取代舊的 (`replace`) or 兩條都留
        (`keep_both`) and sends again."""
        resolve = str(body.get("resolve") or "")
        replace = tuple(str(item) for item in body.get("replace") or ()) if resolve else ()
        edited, change = self.web.personal_memory.preferences(self.actor).edit(
            str(body.get("id") or ""),
            str(body.get("text") or ""),
            actor=self.who,
            replace=replace if resolve == "replace" else (),
            keep_conflicts=resolve == "keep_both",
        )
        return {
            "ok": True,
            "preference": edited.as_dict(),
            "change_id": change,
            "message": "已修改，可以復原。",
        }

    def edit_note(self, body: Mapping[str, Any]) -> dict[str, Any]:
        """A note's text (Markdown), tags or linked entities; only what the
        body names changes."""
        note_id = str(body.get("id") or "")
        text = body.get("text")
        tags = body.get("tags")
        entities = body.get("entities")
        if tags is not None and not isinstance(tags, list):
            return _refused("note_tags_invalid")
        if entities is not None:
            if not isinstance(entities, list) or not all(
                isinstance(item, str) and ENTITY_REF.fullmatch(item.strip()) for item in entities
            ):
                return _refused("note_entity_invalid")
        try:
            change = self.web.personal_memory.notes(self.actor).update(
                note_id,
                actor=self.who,
                text=None if text is None else str(text),
                tags=None if tags is None else clean_tags(str(item) for item in tags),
                entities=None if entities is None else [str(item) for item in entities],
            )
        except NoteError as error:
            return _refused(error.code)
        return {"ok": True, "change_id": change, "message": "已儲存，可以復原。"}

    def reset_sync(self, body: Mapping[str, Any]) -> dict[str, Any]:
        """重新整理: forget how far a source was read for a key (the page asked
        first); the next pass reads the full scope. 復原上次重設 puts it back."""
        space, source, key = (str(body.get(name) or "") for name in ("space", "source", "key"))
        old = (
            self.service()
            .owned(space)
            .reset_sync(source, key, actor=self.who, reason="reset on the memory page")
        )
        if old is None:
            return _refused("sync_unknown")
        return {"ok": True, "message": "已重設：下次會從頭整理。可以「復原上次重設」。"}

    def restore_sync(self, body: Mapping[str, Any]) -> dict[str, Any]:
        """復原上次重設: the latest history row of that source and key must be
        a reset; the state before it comes back."""
        space, source, key = (str(body.get(name) or "") for name in ("space", "source", "key"))
        owned = self.service().owned(space)
        with owned.transaction() as tx:
            latest = tx.sync_history(source, key, limit=1)
        if not latest:
            return _refused("sync_history_unknown")
        if latest[0].action != "reset":
            return _refused("sync_nothing_to_restore")
        owned.restore_sync(latest[0].history_id, actor=self.who)
        return {"ok": True, "message": "已復原上次重設。"}

    def delete_space(self, body: Mapping[str, Any]) -> dict[str, Any]:
        """Delete one space's data. The page asks first; the body repeats the
        space's name (`confirm`), so a stray request deletes nothing."""
        space = str(body.get("space") or "")
        if not space or str(body.get("confirm") or "") != space:
            return _refused("space_delete_unconfirmed")
        counts = self.service().delete_space(
            space, actor=self.who, reason="deleted on the memory page"
        )
        removed = sum(counts.values())
        return {
            "ok": True,
            "counts": counts,
            "message": f"已刪除『{SPACE_LABELS.get(space, space)}』的資料（{removed} 筆）。"
            "刪除紀錄只留時間與筆數，不留內容。",
        }
