"""The Agent Web memory page's routes (accumulated memory M4).

docs/phases/ACCUMULATED_MEMORY.md §6, §3.6, §3.9 and §15: 待確認 across
spaces (保留原值 / 改用新值, recorded as `<actor> via web`), preferences
(edit through the M3 conflict check, delete, undo), notes (edit, tags,
links, Markdown export, delete, undo), the spaces with their counts and an
orphan flag, sync reset and restore, a space's JSON export and its deletion
with a history row without content. Every route acts only in the signed-in
actor's database, and no model tool reaches any of it. Synthetic people,
fake model, no network.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, date, datetime, timedelta
from typing import Any

from test_business_cards_conversation import Conversation
from test_business_cards_conversation import web as web  # noqa: F401 - the fixture

from capabilities.business_cards.contracts import PersonRef
from capabilities.business_cards.space import CONTACTS_ORG
from capabilities.business_cards.store import CardStore
from common.execution import RequestContext, TraceIdentifiers
from host_runtime.conversations import ConversationMessage, ConversationRecord
from host_runtime.memory_page import GET_ROUTES, POST_ROUTES
from host_runtime.web import AgentWeb
from memory.personal import NOTES_SPACE, PREFERENCES_SPACE

Web = tuple[AgentWeb, Conversation]
SCOPE = "skill:engineering/business-cards"
CARD = {
    "name": "王小明",
    "romanised_name": "Hsiao-Ming Wang",
    "company": "範例科技股份有限公司",
    "department": "射頻部",
    "title": "經理",
    "email": "hm.wang@example.com",
}
IMAGE = "sha256:" + "ab" * 32
IMAGE_NEW = "sha256:" + "cd" * 32


def _get(agent_web: AgentWeb, path: str, **query: str) -> dict[str, Any]:
    return agent_web.memory_page.get(path, query)


def _post(agent_web: AgentWeb, path: str, **body: Any) -> dict[str, Any]:
    return agent_web.memory_page.post(path, body)


def _proposal(agent_web: AgentWeb, actor: str | None = None) -> tuple[CardStore, str]:
    """A contact whose confirmed email a new card reads differently: one
    open proposal (the business-cards rule of 2026-10-20)."""
    from host_runtime.memory_spaces import registry

    layout = agent_web.runtime.layout
    store = CardStore.for_actor(
        layout.workspace_root, actor or agent_web.runtime.actor, registry(layout)
    )
    first = store.add(
        CARD,
        source="card",
        source_date=date(2026, 1, 10),
        source_ref=IMAGE,
        uncertain=(),
        actor="seed",
    )
    store.edit(PersonRef(person_id=first.person_id), {}, actor="seed", reason="", confirm=["email"])
    store.add(
        {**CARD, "email": "hm.wamg@example.com"},
        source="card",
        source_date=date(2026, 2, 1),
        source_ref=IMAGE_NEW,
        uncertain=("email",),
        actor="seed",
    )
    return store, first.person_id


# -- 待確認 -------------------------------------------------------------------------


def test_open_proposals_are_listed_with_their_evidence(web: Web) -> None:  # noqa: F811
    agent_web, _ = web
    _, person_id = _proposal(agent_web)
    overview = _get(agent_web, "/api/memory/overview")
    assert overview["ok"] and overview["actor"] == agent_web.runtime.actor
    (item,) = overview["proposals"]
    assert item["space"] == CONTACTS_ORG and item["space_label"] == "聯絡人與組織"
    assert item["entity_label"] == "王小明（範例科技股份有限公司）"
    assert (item["field"], item["field_label"]) == ("email", "Email")
    assert (item["current"], item["proposed"]) == ("hm.wang@example.com", "hm.wamg@example.com")
    assert (item["source"], item["source_label"]) == ("card", "名片")
    assert item["evidence_date"] == "2026-02-01" and item["evidence_ref"] == IMAGE_NEW
    assert item["actions"] == ["keep", "accept"] and item["person_id"] == person_id


def test_accept_takes_the_new_value_as_the_actor_via_web(web: Web) -> None:  # noqa: F811
    agent_web, _ = web
    store, person_id = _proposal(agent_web)
    (item,) = _get(agent_web, "/api/memory/overview")["proposals"]
    done = _post(
        agent_web,
        "/api/memory/proposals/decide",
        space=CONTACTS_ORG,
        proposal_id=item["proposal_id"],
        action="accept",
    )
    assert done["ok"] and done["message"] == "已改用新值。" and done["undo"]
    assert store.view(person_id).email == "hm.wamg@example.com"
    assert _get(agent_web, "/api/memory/overview")["proposals"] == []
    history = store.history(PersonRef(person_id=person_id), limit=20).history
    mine = [entry for entry in history if entry.change_id == done["change_id"]]
    assert {entry.actor for entry in mine} == {f"{agent_web.runtime.actor} via web"}
    with sqlite3.connect(store.path) as con:
        state, decided_by = con.execute(
            "SELECT state, decided_by FROM proposals WHERE proposal_id = ?",
            (item["proposal_id"],),
        ).fetchone()
    assert (state, decided_by) == ("accepted", f"{agent_web.runtime.actor} via web")
    # Deciding again is refused; 復原 takes it back and the proposal reopens.
    again = _post(
        agent_web,
        "/api/memory/proposals/decide",
        space=CONTACTS_ORG,
        proposal_id=item["proposal_id"],
        action="accept",
    )
    assert again["code"] == "proposal_closed"
    undone = _post(
        agent_web, "/api/memory/proposals/undo", space=CONTACTS_ORG, change_id=done["change_id"]
    )
    assert undone["ok"] and store.view(person_id).email == "hm.wang@example.com"
    assert len(_get(agent_web, "/api/memory/overview")["proposals"]) == 1


def test_keep_confirms_the_stored_value_and_rejects_the_proposal(web: Web) -> None:  # noqa: F811
    agent_web, _ = web
    store, person_id = _proposal(agent_web)
    (item,) = _get(agent_web, "/api/memory/overview")["proposals"]
    done = _post(
        agent_web,
        "/api/memory/proposals/decide",
        space=CONTACTS_ORG,
        proposal_id=item["proposal_id"],
        action="keep",
    )
    assert done["ok"] and done["message"] == "已保留原值。"
    assert store.view(person_id).email == "hm.wang@example.com"
    assert store.view(person_id).needs_confirmation == ()
    history = store.history(PersonRef(person_id=person_id), limit=20).history
    confirm = [entry for entry in history if entry.change_id == done["change_id"]]
    assert [(entry.kind, entry.field, entry.actor) for entry in confirm] == [
        ("confirm", "email", f"{agent_web.runtime.actor} via web")
    ]
    with sqlite3.connect(store.path) as con:
        (state,) = con.execute(
            "SELECT state FROM proposals WHERE proposal_id = ?", (item["proposal_id"],)
        ).fetchone()
    assert state == "rejected"


def test_a_proposal_in_another_space_can_be_kept_but_not_taken(web: Web) -> None:  # noqa: F811
    """A space without a page adapter: 保留原值 closes the proposal (rejected,
    with a history row); 改用新值 is not offered."""
    agent_web, _ = web
    service = agent_web.memory_page.service()
    with service.owned(NOTES_SPACE).transaction(immediate=True) as tx:
        tx.propose(
            "c-test",
            "seed",
            "n-1",
            "text",
            "舊的",
            "新的",
            source_kind="agent",
            observation_id=None,
        )
    (item,) = _get(agent_web, "/api/memory/overview")["proposals"]
    assert item["space"] == NOTES_SPACE and item["actions"] == ["keep"]
    refused = _post(
        agent_web,
        "/api/memory/proposals/decide",
        space=NOTES_SPACE,
        proposal_id=item["proposal_id"],
        action="accept",
    )
    assert refused["code"] == "proposal_accept_unsupported"
    kept = _post(
        agent_web,
        "/api/memory/proposals/decide",
        space=NOTES_SPACE,
        proposal_id=item["proposal_id"],
        action="keep",
    )
    assert kept["ok"]
    assert service.proposal(NOTES_SPACE, item["proposal_id"])["state"] == "rejected"  # type: ignore[index]
    with service.owned(NOTES_SPACE).transaction() as tx:
        (row,) = tx.history(change_id=kept["change_id"])
    assert (row["kind"], row["actor"]) == (
        "proposal_rejected",
        f"{agent_web.runtime.actor} via web",
    )
    # A wrong space, id or action names nothing.
    assert (
        _post(
            agent_web,
            "/api/memory/proposals/decide",
            space=CONTACTS_ORG,
            proposal_id=item["proposal_id"],
            action="keep",
        )["code"]
        == "proposal_unknown"
    )
    assert (
        _post(agent_web, "/api/memory/proposals/decide", space=NOTES_SPACE, action="drop")["code"]
        == "proposal_action_unknown"
    )


# -- 偏好 -----------------------------------------------------------------------


def test_preferences_are_grouped_by_skill_with_their_source_and_uses(web: Web) -> None:  # noqa: F811
    agent_web, _ = web
    prefs = agent_web.personal_memory.preferences(agent_web.runtime.actor)
    saved, _ = prefs.save(
        SCOPE,
        "執行時不需要問是否包含在職人員",
        actor=f"{agent_web.runtime.actor} via web",
        scope_label="名片／組織圖",
        source_session="s-1",
        source_message="m-q",
    )
    now = datetime.now(UTC)
    agent_web.runtime.state.create_conversation(
        ConversationRecord(
            session_id="s-1",
            actor=agent_web.runtime.actor,
            title="WNC 組織圖",
            created_at=now,
            updated_at=now + timedelta(seconds=1),
            messages=(
                ConversationMessage(
                    message_id="m-q", role="user", text="WNC", created_at=now, status="submitted"
                ),
                ConversationMessage(
                    message_id="m-a",
                    role="assistant",
                    text="好",
                    created_at=now + timedelta(seconds=1),
                    status="answered",
                    preferences_used=(saved.preference_id,),
                ),
            ),
        )
    )
    (group,) = _get(agent_web, "/api/memory/overview")["preferences"]
    assert (group["scope"], group["label"]) == (SCOPE, "名片／組織圖")
    (item,) = group["items"]
    assert item["preference_id"] == saved.preference_id
    assert (item["source_session"], item["source_message"]) == ("s-1", "m-q")
    assert item["used_count"] == 1 and item["used"][0]["message_id"] == "m-a"


def test_a_preference_edit_goes_through_the_conflict_check_and_undoes(web: Web) -> None:  # noqa: F811
    agent_web, _ = web
    prefs = agent_web.personal_memory.preferences(agent_web.runtime.actor)
    first, _ = prefs.save(SCOPE, "組織圖用英文名", actor="seed")
    other, _ = prefs.save(SCOPE, "執行時不需要問是否包含在職人員", actor="seed")
    # Edited into the same rule as another: refused.
    same = _post(agent_web, "/api/memory/preferences/edit", id=first.preference_id, text=other.text)
    assert same["code"] == "preference_duplicate"
    # Edited into the opposite of another: asked first, both shown.
    opposite = "執行時要問是否包含在職人員"
    asked = _post(agent_web, "/api/memory/preferences/edit", id=first.preference_id, text=opposite)
    assert asked["code"] == "preference_conflict"
    assert asked["conflicts"] == [{"preference_id": other.preference_id, "text": other.text}]
    assert prefs.get(first.preference_id).text == "組織圖用英文名"  # type: ignore[union-attr]
    # 取代舊的: one change; the other becomes replaced.
    done = _post(
        agent_web,
        "/api/memory/preferences/edit",
        id=first.preference_id,
        text=opposite,
        resolve="replace",
        replace=[other.preference_id],
    )
    assert done["ok"] and done["preference"]["text"] == opposite
    assert prefs.get(other.preference_id).status == "replaced"  # type: ignore[union-attr]
    (row, *_rest) = [
        item
        for item in prefs.history(first.preference_id)
        if item["change_id"] == done["change_id"]
    ]
    assert (row["kind"], row["actor"]) == ("preference_edit", f"{agent_web.runtime.actor} via web")
    # One 復原 puts both back.
    undone = agent_web.personal_memory.route(
        "/api/memory/undo", {"kind": "preference", "change_id": done["change_id"]}
    )
    assert undone["ok"]
    assert prefs.get(first.preference_id).text == "組織圖用英文名"  # type: ignore[union-attr]
    assert prefs.get(other.preference_id).status == "active"  # type: ignore[union-attr]
    # 兩條都留 keeps the contradiction on purpose.
    both = _post(
        agent_web,
        "/api/memory/preferences/edit",
        id=first.preference_id,
        text=opposite,
        resolve="keep_both",
    )
    assert both["ok"] and len(prefs.listed()) == 2


def test_a_preference_delete_and_undo_from_the_page(web: Web) -> None:  # noqa: F811
    agent_web, _ = web
    prefs = agent_web.personal_memory.preferences(agent_web.runtime.actor)
    saved, _ = prefs.save(SCOPE, "組織圖用英文名", actor="seed")
    deleted = agent_web.personal_memory.route(
        "/api/memory/delete", {"kind": "preference", "id": saved.preference_id}
    )
    assert deleted["ok"] and _get(agent_web, "/api/memory/overview")["preferences"] == []
    agent_web.personal_memory.route(
        "/api/memory/undo", {"kind": "preference", "change_id": deleted["change_id"]}
    )
    assert [g["scope"] for g in _get(agent_web, "/api/memory/overview")["preferences"]] == [SCOPE]


# -- 筆記 -----------------------------------------------------------------------


def test_note_edit_tags_links_export_delete_and_undo(web: Web) -> None:  # noqa: F811
    agent_web, _ = web
    _, person_id = _proposal(agent_web)
    notes = agent_web.personal_memory.notes(agent_web.runtime.actor)
    note, _ = notes.save(
        "WNC 的 RF 主管是王小明",
        actor="seed",
        source_kind="answer",
        source_session="s-9",
        source_message="a-9",
    )
    other, _ = notes.save("另一則", actor="seed", source_kind="answer", tags=["雜項"])
    who = f"{agent_web.runtime.actor} via web"
    edited = _post(agent_web, "/api/memory/notes/edit", id=note.note_id, text="**RF** 主管：王小明")
    assert edited["ok"]
    tagged = _post(agent_web, "/api/memory/notes/edit", id=note.note_id, tags=["#WNC", "RF"])
    linked = _post(
        agent_web,
        "/api/memory/notes/edit",
        id=note.note_id,
        entities=[f"contacts/org:person:{person_id}"],
    )
    assert tagged["ok"] and linked["ok"]
    now = notes.get(note.note_id)
    assert now is not None and now.text == "**RF** 主管：王小明"
    assert now.tags == ("WNC", "RF") and now.entities == (f"contacts/org:person:{person_id}",)
    assert now.updated_by == who
    listed = _get(agent_web, "/api/memory/overview")["notes"]
    assert listed["tags"] == ["RF", "WNC", "雜項"]
    assert listed["entities"] == {
        f"contacts/org:person:{person_id}": "王小明（範例科技股份有限公司）"
    }
    assert {item["note_id"] for item in listed["notes"]} == {note.note_id, other.note_id}
    # A bad link is refused; nothing changes.
    bad = _post(agent_web, "/api/memory/notes/edit", id=note.note_id, entities=["王小明"])
    assert bad["code"] == "note_entity_invalid"
    # Unlink, then 復原 the unlink.
    unlinked = _post(agent_web, "/api/memory/notes/edit", id=note.note_id, entities=[])
    assert notes.get(note.note_id).entities == ()  # type: ignore[union-attr]
    agent_web.personal_memory.route(
        "/api/memory/undo", {"kind": "note", "change_id": unlinked["change_id"]}
    )
    assert notes.get(note.note_id).entities == (f"contacts/org:person:{person_id}",)  # type: ignore[union-attr]
    # Markdown export of the selection.
    exported = _get(agent_web, "/api/memory/notes/export", ids=note.note_id)
    assert exported["ok"] and exported["count"] == 1
    assert exported["filename"].startswith("notes-") and exported["filename"].endswith(".md")
    markdown = exported["markdown"]
    assert markdown.startswith("# 筆記匯出")
    assert f"## {note.note_id}" in markdown and "**RF** 主管：王小明" in markdown
    assert "標籤：WNC、RF" in markdown and "關聯：王小明（範例科技股份有限公司）" in markdown
    assert "來源：對話 s-9，訊息 a-9" in markdown and other.note_id not in markdown
    assert _get(agent_web, "/api/memory/notes/export")["count"] == 2
    # Delete and 復原.
    deleted = agent_web.personal_memory.route(
        "/api/memory/delete", {"kind": "note", "id": note.note_id}
    )
    assert [n.note_id for n in notes.listed()] == [other.note_id]
    agent_web.personal_memory.route(
        "/api/memory/undo", {"kind": "note", "change_id": deleted["change_id"]}
    )
    assert len(notes.listed()) == 2


# -- 資料 -----------------------------------------------------------------------


def test_spaces_are_listed_with_counts_and_an_orphan_is_flagged(web: Web) -> None:  # noqa: F811
    agent_web, _ = web
    _proposal(agent_web)
    agent_web.personal_memory.notes(agent_web.runtime.actor).save(
        "一則", actor="seed", source_kind="answer"
    )
    service = agent_web.memory_page.service()
    # A space whose manager is no longer installed here: its row stays.
    with service.connect() as con:
        con.execute(
            "INSERT INTO spaces (space, manager, table_prefix, declaration_json, rules_json, "
            "registered_at, updated_at) SELECT 'projects/readiness', 'gone/readiness', "
            "'projects_readiness__', REPLACE(declaration_json, 'personal/notes', "
            "'projects/readiness'), rules_json, registered_at, updated_at FROM spaces "
            "WHERE space = 'personal/notes'"
        )
    spaces = {item["space"]: item for item in _get(agent_web, "/api/memory/overview")["spaces"]}
    assert set(spaces) == {CONTACTS_ORG, NOTES_SPACE, PREFERENCES_SPACE, "projects/readiness"}
    contacts = spaces[CONTACTS_ORG]
    assert contacts["manager"] == "engineering/business-cards"
    assert contacts["manager_label"] == "名片／組織圖" and contacts["manager_state"] == "on"
    assert contacts["orphan"] is False and contacts["view"] == "people"
    assert contacts["kinds"] == ["entities", "sync_state"]
    assert contacts["sensitivity_label"] == "機密" and contacts["retention_label"] == "保留到刪除"
    people = {item["name"]: item["count"] for item in contacts["counts"]}
    assert people["people"] == 1 and contacts["open_proposals"] == 1
    assert contacts["observations"] >= 2 and contacts["last_updated"]
    assert spaces[NOTES_SPACE]["counts"] == [{"name": "items", "label": "筆記", "count": 1}]
    assert spaces[NOTES_SPACE]["manager_state"] == "host"
    assert spaces["projects/readiness"]["orphan"] is True
    assert spaces["projects/readiness"]["manager_state"] == "missing"


def test_the_contacts_view_lists_people_by_status_with_their_history(web: Web) -> None:  # noqa: F811
    agent_web, _ = web
    store, person_id = _proposal(agent_web)
    second = store.add(
        {"name": "李大華", "company": "範例科技股份有限公司", "email": "dh.lee@example.com"},
        source="card",
        source_date=date(2026, 1, 11),
        source_ref="",
        uncertain=(),
        actor="seed",
    )
    store.set_status(
        PersonRef(person_id=second.person_id), "left", actor="seed", reason="離職", effective=None
    )
    everyone = _get(agent_web, "/api/memory/people")
    assert everyone["total"] == 2
    current = _get(agent_web, "/api/memory/people", status="active")
    assert [p["name"] for p in current["people"]] == ["王小明"]
    gone = _get(agent_web, "/api/memory/people", status="left")
    assert [(p["name"], p["status_label"]) for p in gone["people"]] == [("李大華", "已離職")]
    assert [p["name"] for p in _get(agent_web, "/api/memory/people", q="王小明")["people"]] == [
        "王小明"
    ]
    history = _get(agent_web, "/api/memory/person", person_id=person_id)
    assert history["ok"] and history["person"]["name"] == "王小明"
    assert history["history"] and len(history["proposals"]) == 1
    assert _get(agent_web, "/api/memory/person", person_id="p-nobody")["code"] == "person_unknown"


# -- 同步進度 ---------------------------------------------------------------------


def test_sync_reset_asks_nothing_server_side_and_restore_puts_it_back(web: Web) -> None:  # noqa: F811
    agent_web, _ = web
    service = agent_web.memory_page.service()
    agent_web.memory_page.cards()
    space = service.owned(CONTACTS_ORG)
    space.advance_sync(
        "mail:Inbox",
        "wnc.com.tw",
        last_message_date="2026-10-19T08:00:00+00:00",
        message_ids=["m-1"],
        extractor_version="sig-3",
        actor="seed via web",
    )
    (row,) = _get(agent_web, "/api/memory/overview")["sync"]
    assert (row["space"], row["source"], row["key"]) == (CONTACTS_ORG, "mail:Inbox", "wnc.com.tw")
    assert row["state"]["extractor_version"] == "sig-3" and row["state"]["updated_by"]
    assert row["can_reset"] and not row["can_restore"]
    # Nothing to restore before a reset.
    assert (
        _post(
            agent_web,
            "/api/memory/sync/restore",
            space=CONTACTS_ORG,
            source="mail:Inbox",
            key="wnc.com.tw",
        )["code"]
        == "sync_nothing_to_restore"
    )
    reset = _post(
        agent_web,
        "/api/memory/sync/reset",
        space=CONTACTS_ORG,
        source="mail:Inbox",
        key="wnc.com.tw",
    )
    assert reset["ok"] and space.sync_state("mail:Inbox", "wnc.com.tw") is None
    (row,) = _get(agent_web, "/api/memory/overview")["sync"]
    assert row["state"] is None and row["can_restore"] and not row["can_reset"]
    assert row["latest"]["actor"] == f"{agent_web.runtime.actor} via web"
    restored = _post(
        agent_web,
        "/api/memory/sync/restore",
        space=CONTACTS_ORG,
        source="mail:Inbox",
        key="wnc.com.tw",
    )
    assert restored["ok"]
    back = space.sync_state("mail:Inbox", "wnc.com.tw")
    assert back is not None and back.last_message_ids == ("m-1",)
    assert back.updated_by == f"{agent_web.runtime.actor} via web"
    assert (
        _post(agent_web, "/api/memory/sync/reset", space=CONTACTS_ORG, source="x", key="y")["code"]
        == "sync_unknown"
    )
    assert (
        _post(agent_web, "/api/memory/sync/reset", space=NOTES_SPACE, source="x", key="y")["code"]
        == "memory_kind_not_declared"
    )


# -- 紀錄: export and delete ---------------------------------------------------------


def test_a_space_exports_as_json(web: Web) -> None:  # noqa: F811
    agent_web, _ = web
    _proposal(agent_web)
    exported = _get(agent_web, "/api/memory/export", space=CONTACTS_ORG)
    assert exported["ok"] and exported["filename"].startswith("memory-contacts-org-")
    data = exported["data"]
    assert data["format"] == "aep-memory-space-export/1" and data["space"] == CONTACTS_ORG
    assert [p["name"] for p in data["tables"]["people"]] == ["王小明"]
    assert len(data["shared"]["proposals"]) == 1 and data["shared"]["observations"]
    assert json.loads(json.dumps(data, ensure_ascii=False, default=str))["space"] == CONTACTS_ORG
    assert _get(agent_web, "/api/memory/export", space="nope/space")["code"] == (
        "memory_space_unknown"
    )


def test_a_space_delete_needs_its_name_and_leaves_a_row_without_content(web: Web) -> None:  # noqa: F811
    agent_web, _ = web
    store, _ = _proposal(agent_web)
    notes = agent_web.personal_memory.notes(agent_web.runtime.actor)
    notes.save("留著", actor="seed", source_kind="answer")
    unconfirmed = _post(agent_web, "/api/memory/space/delete", space=CONTACTS_ORG)
    assert unconfirmed["code"] == "space_delete_unconfirmed"
    done = _post(agent_web, "/api/memory/space/delete", space=CONTACTS_ORG, confirm=CONTACTS_ORG)
    assert done["ok"] and done["counts"]["people"] == 1 and done["counts"]["observations"] >= 2
    overview = _get(agent_web, "/api/memory/overview")
    assert overview["proposals"] == []
    (deletion,) = overview["deletions"]
    assert deletion["space"] == CONTACTS_ORG and deletion["label"] == "聯絡人與組織"
    assert deletion["actor"] == f"{agent_web.runtime.actor} via web"
    assert deletion["counts"]["people"] == 1
    assert "王小明" not in json.dumps(deletion, ensure_ascii=False)
    with sqlite3.connect(store.path) as con:
        assert con.execute(
            "SELECT COUNT(*) FROM observations WHERE space = ?", (CONTACTS_ORG,)
        ).fetchone() == (0,)
        # The append-only guard is back for everyone else.
        assert con.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE name = 'observations_never_deleted'"
        ).fetchone() == (1,)
        assert "王小明" not in json.dumps(
            con.execute("SELECT * FROM space_deletions").fetchall(), ensure_ascii=False
        )
    # The other spaces keep their data; the store still works (and is empty).
    assert [n.text for n in notes.listed()] == ["留著"]
    assert store.list_people(company="", source="", status="any", limit=10) == ([], 0)


def test_the_records_section_shows_the_existing_retention(web: Web) -> None:  # noqa: F811
    agent_web, _ = web
    records = _get(agent_web, "/api/memory/overview")["records"]
    assert records["conversations"]["max_messages"] == 100
    assert records["runs"] == {"days": 30, "max_mb": 500}
    assert records["experience"]["retention_days"] == 30


# -- access -----------------------------------------------------------------------


def test_another_actors_memory_is_never_reached_even_by_id(web: Web) -> None:  # noqa: F811
    agent_web, _ = web
    _, person_id = _proposal(agent_web, actor="bob")
    bob_notes = agent_web.personal_memory.notes("bob")
    note, _ = bob_notes.save("bob 的筆記", actor="bob via web", source_kind="answer")
    bob_prefs = agent_web.personal_memory.preferences("bob")
    pref, _ = bob_prefs.save(SCOPE, "組織圖用英文名", actor="bob via web")
    assert agent_web.runtime.actor != "bob"
    overview = _get(agent_web, "/api/memory/overview")
    assert overview["proposals"] == [] and overview["preferences"] == []
    assert overview["notes"]["notes"] == []
    assert _get(agent_web, "/api/memory/person", person_id=person_id)["code"] == "person_unknown"
    assert _get(agent_web, "/api/memory/people", q="王小明")["people"] == []
    assert (
        _post(
            agent_web,
            "/api/memory/proposals/decide",
            space=CONTACTS_ORG,
            proposal_id=1,
            action="accept",
        )["code"]
        == "proposal_unknown"
    )
    assert (
        _post(agent_web, "/api/memory/notes/edit", id=note.note_id, text="改掉")["code"]
        == "note_unknown"
    )
    assert (
        _post(agent_web, "/api/memory/preferences/edit", id=pref.preference_id, text="改掉")["code"]
        == "preference_unknown"
    )
    assert agent_web.personal_memory.route(
        "/api/memory/delete", {"kind": "note", "id": note.note_id}
    )["code"] == ("note_unknown")
    assert (
        "bob 的筆記"
        not in _get(agent_web, "/api/memory/notes/export", ids=note.note_id)["markdown"]
    )
    exported = _get(agent_web, "/api/memory/export", space=NOTES_SPACE)
    assert exported["data"]["tables"]["items"] == []
    _post(agent_web, "/api/memory/space/delete", space=NOTES_SPACE, confirm=NOTES_SPACE)
    assert [n.text for n in bob_notes.listed()] == ["bob 的筆記"]
    assert bob_notes.get(note.note_id) is not None and bob_prefs.listed()


def test_no_model_tool_reaches_the_memory_page(web: Web) -> None:  # noqa: F811
    """The page's routes are Agent Web only: no Host tool, no Bridge tool and
    no turn tool is named after them or calls them."""
    agent_web, _ = web
    host_tools = agent_web.runtime.agent.gateway.host_tools
    assert host_tools is not None
    names = {item.tool.name for item in host_tools()}
    context = RequestContext(
        trace=TraceIdentifiers(trace_id="t1", request_id="r1", span_id="s1"),
        actor=agent_web.runtime.actor,
        namespace="engineering",
        channel="local",
        message="之前有記過什麼？",
        session_id="s-tools",
    )
    turn = agent_web.personal_memory.turn(context, ())
    names |= {item.tool.name for item in turn.tools}
    assert {name for name in names if name.startswith(("memory__", "notes__"))} <= {
        "memory__propose_preference",
        "memory__propose_note",
        "notes__search",
    }
    words = ("export", "delete", "reset", "restore", "decide", "edit", "overview", "space")
    for name in names:
        if name.startswith(("memory__", "notes__")):
            assert not any(word in name for word in words), name
    for route in (*GET_ROUTES, *POST_ROUTES):
        assert route.startswith("/api/memory/")
        assert route.rsplit("/", 1)[1] not in names
