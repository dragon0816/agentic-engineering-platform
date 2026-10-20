"""The person's notes (accumulated memory M3, docs/phases/ACCUMULATED_MEMORY.md §3.9).

Owner 2026-10-20: one click in chat saves an answer (「存成筆記」) or a
selection of it (「存選取內容」); the Agent may propose a note at most once
per conversation, saved only by the press; notes are never injected and are
searched (`notes__search`) only by a Skill that declares a notes read or
when the person asks about earlier notes; results cite note ids; notes
linked to a contact show on that person's card in the HTML org chart.
History, undo and per-actor isolation as in M1. Fake model, no network.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest
from test_business_cards_capabilities import _bridge, _people, _run
from test_business_cards_conversation import Conversation, _turn
from test_business_cards_conversation import web as web  # noqa: F401 - the fixture

from capabilities.business_cards.manifest import CARDS_SKILL
from capabilities.business_cards.space import default_registry
from common.action_cards import CARD_KEY
from common.execution import RequestContext, TraceIdentifiers
from host_runtime.conversations import ConversationMessage, ConversationRecord
from host_runtime.personal_memory import PROPOSE_NOTE, SEARCH_NOTES, MemoryRefused, excerpt_range
from host_runtime.web import AgentWeb
from memory.notes import NoteError, Notes, for_reader, notes_asked
from memory.personal import NOTES_SPACE
from memory.service import MemoryAccessError, MemoryService

Web = tuple[AgentWeb, Conversation]
ANSWER = "## 結論\n\n**WNC** 的 RF 主管是 *王小明*，下週二要再確認 BOM。\n\n- 樣品 10/30 到\n"


def _seed(agent_web: AgentWeb, text: str = ANSWER) -> tuple[str, str, str]:
    """A stored conversation with one answer: (session, question id, answer id)."""
    from datetime import UTC, datetime, timedelta

    now = datetime.now(UTC)
    session = f"notes-{now.timestamp()}"
    agent_web.runtime.state.create_conversation(
        ConversationRecord(
            session_id=session,
            actor=agent_web.runtime.actor,
            title="notes",
            created_at=now,
            updated_at=now + timedelta(seconds=1),
            messages=(
                ConversationMessage(
                    message_id="q-1",
                    role="user",
                    text="WNC 的 RF 主管是誰？",
                    created_at=now,
                    status="submitted",
                ),
                ConversationMessage(
                    message_id="a-1",
                    role="assistant",
                    text=text,
                    created_at=now + timedelta(seconds=1),
                    status="answered",
                ),
            ),
        )
    )
    return session, "q-1", "a-1"


def _notes(agent_web: AgentWeb, actor: str | None = None) -> Notes:
    return agent_web.personal_memory.notes(actor or agent_web.runtime.actor)


def _save(agent_web: AgentWeb, **body: Any) -> dict[str, Any]:
    return agent_web.personal_memory.route("/api/memory/notes/save", body)


# -- one click in Agent Web ---------------------------------------------------------


def test_one_click_saves_the_answer_with_its_source_and_history(web: Web) -> None:  # noqa: F811
    agent_web, _ = web
    session, _asked, answer = _seed(agent_web)
    saved = _save(agent_web, session_id=session, message_id=answer)
    assert saved["ok"] and saved["already"] is False
    note = saved["note"]
    assert (
        note["text"] == ANSWER.strip() and saved["message"] == f"已存成筆記（{note['note_id']}）。"
    )
    assert note["source"] == {"kind": "answer", "conversation": session, "message": answer}
    assert note["created_by"] == f"{agent_web.runtime.actor} via web"
    (row,) = _notes(agent_web).history(note["note_id"])
    assert row["kind"] == "note_add" and row["change_id"] == saved["change_id"]
    # Twice is once.
    again = _save(agent_web, session_id=session, message_id=answer)
    assert again["ok"] and again["already"] and again["note"]["note_id"] == note["note_id"]
    assert len(_notes(agent_web).listed()) == 1
    # Only an answer of this person's conversation.
    assert _save(agent_web, session_id=session, message_id="q-1")["code"] == "message_unknown"
    assert _save(agent_web, session_id="nope", message_id=answer)["code"] == (
        "conversation_unknown"
    )


def test_a_selection_is_saved_with_its_range_and_must_be_in_the_answer(web: Web) -> None:  # noqa: F811
    agent_web, _ = web
    session, _asked, answer = _seed(agent_web)
    # As the page renders it: no Markdown marks.
    picked = "WNC 的 RF 主管是 王小明"
    saved = _save(agent_web, session_id=session, message_id=answer, selection=picked)
    assert saved["ok"], saved
    note = saved["note"]
    assert note["text"] == picked and note["source"]["kind"] == "selection"
    start, end = note["source"]["excerpt"]["start"], note["source"]["excerpt"]["end"]
    assert ANSWER[start:end] == "WNC** 的 RF 主管是 *王小明"
    refused = _save(agent_web, session_id=session, message_id=answer, selection="不在回答裡的字")
    assert refused["ok"] is False and refused["code"] == "selection_not_in_answer"
    assert refused["message"] == "選取的內容不在這則回答裡"
    assert excerpt_range("abc", "  ") is None


# -- the Agent's proposal: once per conversation, saved only by the press -------------


def test_the_agent_proposes_a_note_once_per_conversation(web: Web) -> None:  # noqa: F811
    agent_web, model = web
    session = agent_web.create_conversation()["conversation"]["session_id"]
    proposal = {
        "text": "WNC 的 RF 主管是王小明；10/30 收樣品。",
        "tags": ["WNC", "#樣品", "wnc"],
        "entities": ["contacts/org:person:p-1"],
    }
    model.then({"tools": [(PROPOSE_NOTE, proposal)]}, {"text": "整理好了。"})
    replied = _turn(agent_web, session, "整理一下 WNC 的重點")
    card = replied["answer"][CARD_KEY]
    assert card["title"] == "要存成筆記嗎？" and "標籤：WNC、樣品" in card["preview"]
    assert [b["label"] for b in card["buttons"]] == ["存成筆記", "不用"]
    assert replied["answer"]["answer"] == "整理好了。"
    assert _notes(agent_web).listed() == []
    # The next turn of the same conversation: no longer offered ...
    model.then({"tools": [(PROPOSE_NOTE, {"text": "again"})]}, {"text": "ok"})
    _turn(agent_web, session, "再整理一次")
    assert PROPOSE_NOTE not in {tool.name for tool in model.requests[-2].tools}
    assert "not offered" in model.tool_results()[0]
    # ... and refused by the Host if reached anyway (another request).
    later = RequestContext(
        trace=TraceIdentifiers(trace_id="t9", request_id="r9", span_id="s9"),
        actor=agent_web.runtime.actor,
        namespace="engineering",
        channel="local",
        message="x",
        session_id=session,
    )
    with pytest.raises(MemoryRefused) as refused:
        agent_web.personal_memory.propose_note(later, {"text": "again"})
    assert refused.value.code == "note_already_proposed"
    # Another conversation may propose one.
    other = agent_web.create_conversation()["conversation"]["session_id"]
    model.then({"tools": [(PROPOSE_NOTE, {"text": "另一則"})]}, {"text": "ok"})
    assert _turn(agent_web, other, "整理")["answer"][CARD_KEY]["status"] == "pending"
    # The press saves it, with the answer that showed it as its source.
    saved = agent_web.decide_card(card["card_id"], "save")
    assert saved["ok"] and saved["card"]["status"] == "saved"
    (note,) = _notes(agent_web).listed()
    answer = agent_web.conversations(session)["selected"]["messages"][1]
    assert (note.source_kind, note.source_session, note.source_message) == (
        "agent_proposal",
        session,
        answer["message_id"],
    )
    assert note.tags == ("WNC", "樣品") and note.entities == ("contacts/org:person:p-1",)
    assert note.created_by == f"{agent_web.runtime.actor} via web"


def test_the_host_checks_retry_gets_the_same_card_not_a_refusal(web: Web) -> None:  # noqa: F811
    agent_web, model = web
    session = agent_web.create_conversation()["conversation"]["session_id"]
    model.then(
        {"tools": [(PROPOSE_NOTE, {"text": "結論 A"})]},
        {"text": "好，我已記下這個結論。"},  # a false claim: the Host retries
        {"tools": [(PROPOSE_NOTE, {"text": "結論 A"})]},
        {"text": "要保存請按「存成筆記」。"},
    )
    replied = _turn(agent_web, session, "記一下結論")
    first = model.requests[1].messages
    assert replied["answer"]["answer"] == "要保存請按「存成筆記」。"
    assert replied["answer"][CARD_KEY]["status"] == "pending"
    assert len(agent_web.personal_memory.store.records()) == 1, first


# -- searching: only when declared or asked; citations --------------------------------


def test_the_trigger_phrases() -> None:
    for asked in (
        "我之前有記過什麼關於 WNC 的？",
        "之前記過 BOM 的事嗎",
        "我記過的筆記裡有沒有樣品日期",
        "查一下我的筆記",
        "有沒有記過王小明的分機",
        "What did I note about WNC?",
        "did I write down the sample date?",
        "search my notes for BOM",
    ):
        assert notes_asked(asked), asked
    for plain in (
        "WNC 組織圖",
        "幫我存成筆記",
        "記得幫我寄信",
        "write a note to Alice",
        "notebook 規格",
    ):
        assert not notes_asked(plain), plain


def test_search_is_offered_only_with_a_declaration_or_the_trigger(web: Web) -> None:  # noqa: F811
    agent_web, model = web
    session = agent_web.create_conversation()["conversation"]["session_id"]
    # The business-cards Skill declares a notes read (the org chart's 相關筆記).
    model.then({"text": "ok"})
    _turn(agent_web, session, "WNC 組織圖")
    assert SEARCH_NOTES in {tool.name for tool in model.requests[-1].tools}
    # Switched off: no Skill in use declares it; only the person's words bring it.
    agent_web.runtime.agent.gateway.router.commands.skills.remove(CARDS_SKILL)
    model.then({"text": "ok"})
    _turn(agent_web, session, "WNC 組織圖")
    assert SEARCH_NOTES not in {tool.name for tool in model.requests[-1].tools}
    assert "notes__search" not in model.requests[-1].messages[0].text
    model.then({"text": "ok"})
    _turn(agent_web, session, "我之前有記過什麼關於 WNC 的？")
    assert SEARCH_NOTES in {tool.name for tool in model.requests[-1].tools}
    # Never injected: the note's text is not in the prompt.
    _notes(agent_web).save("BOM 下週二確認", actor="engineer via web", source_kind="answer")
    model.then({"text": "ok"})
    _turn(agent_web, session, "WNC 組織圖")
    assert all("BOM 下週二確認" not in message.text for message in model.requests[-1].messages)


def test_search_results_cite_note_ids(web: Web) -> None:  # noqa: F811
    agent_web, model = web
    notes = _notes(agent_web)
    first, _ = notes.save(
        "WNC 的 RF 主管是王小明", actor="a via web", source_kind="answer", tags=["WNC"]
    )
    notes.save("EXN 樣品延後", actor="a via web", source_kind="answer", tags=["EXN"])
    session = agent_web.create_conversation()["conversation"]["session_id"]
    model.then(
        {"tools": [(SEARCH_NOTES, {"query": "RF", "tag": "wnc"})]},
        {"text": f"你之前記過：WNC 的 RF 主管是王小明 [筆記 {first.note_id}]。"},
    )
    replied = _turn(agent_web, session, "我之前有記過 WNC 的什麼？")
    found = json.loads(model.tool_results()[0])["host"]["data"]
    (hit,) = found["notes"]
    assert hit["note_id"] == first.note_id and hit["cite"] == f"[筆記 {first.note_id}]"
    assert "Cite each note" in found["note"]
    assert f"[筆記 {first.note_id}]" in replied["answer"]["answer"]
    assert "cite every note you use as [筆記 <note_id>]" in model.requests[0].messages[0].text
    # Filters: entity and dates.
    assert notes.search(entity="contacts/org:person:none") == []
    assert [n.note_id for n in notes.search(since="2000-01-01", until="2999-12-31", text="RF")] == [
        first.note_id
    ]
    assert notes.search(until="2000-01-01") == []
    with pytest.raises(NoteError):
        notes.search(since="10/21")


# -- the org chart shows linked notes -----------------------------------------------


def test_linked_notes_show_on_the_person_card_in_the_html_chart(tmp_path: Path) -> None:
    bridge = _bridge(tmp_path / "cards")
    _people(bridge)
    found = _run(bridge, "find", {"query": "王小明"}).data
    person = found["people"][0]["person_id"]
    memory = MemoryService.for_actor(tmp_path / "cards" / "workspace", "alice", default_registry())
    notes = Notes(memory)
    note, _ = notes.save(
        "王小明說 <b>下週二</b> 確認 BOM",
        actor="alice via web",
        source_kind="answer",
        entities=[f"contacts/org:person:{person}"],
    )
    notes.save("沒有關聯的筆記", actor="alice via web", source_kind="answer")
    drawn = _run(bridge, "org-chart", {"company": "範例科技", "format": "html"}).data
    page = Path(drawn["html_path"]).read_text(encoding="utf-8")
    block = re.search(r'<script type="application/json" id="chart-data">(.*?)</script>', page)
    assert block is not None
    data = json.loads(block.group(1))
    by_id = {item["id"]: item for item in data["people"]}
    (shown,) = by_id[person]["notes"]
    assert shown["id"] == note.note_id and shown["text"] == "王小明說 <b>下週二</b> 確認 BOM"
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", shown["date"])
    assert all(not item["notes"] for pid, item in by_id.items() if pid != person)
    assert "<b>下週二</b>" not in page  # escaped in the data block
    assert "相關筆記" in page
    # Another actor's chart never shows alice's notes.
    _run(bridge, "add-card", {"name": "王小明", "company": "範例科技"}, actor="bob")
    theirs = _run(bridge, "org-chart", {"company": "範例科技", "format": "html"}, actor="bob")
    assert "下週二" not in Path(theirs.data["html_path"]).read_text(encoding="utf-8")


def test_only_a_declared_reader_reads_the_notes(tmp_path: Path) -> None:
    memory = MemoryService.for_actor(tmp_path, "alice", default_registry())
    Notes(memory).save("x", actor="a", source_kind="answer", entities=["contacts/org:person:p"])
    assert for_reader(memory, (CARDS_SKILL.namespace, CARDS_SKILL.name), ["contacts/org:person:p"])
    with pytest.raises(MemoryAccessError):
        for_reader(memory, ("engineering", "stranger"), ["contacts/org:person:p"])
    assert memory.registry.role(NOTES_SPACE, ("host", "memory")) == "manager"


# -- history, undo, isolation --------------------------------------------------------


def test_history_and_undo_of_edits_and_deletions(web: Web) -> None:  # noqa: F811
    agent_web, _ = web
    notes = _notes(agent_web)
    note, added = notes.save("初稿", actor="a via web", source_kind="answer", tags=["x"])
    edited = notes.update(note.note_id, actor="a via web", text="改過", tags=["y"])
    # The save cannot be undone under the later edit.
    with pytest.raises(NoteError) as refused:
        notes.undo(added, actor="a via web")
    assert refused.value.code == "undo_conflict"
    notes.undo(edited, actor="a via web")
    back = notes.get(note.note_id)
    assert back is not None and (back.text, back.tags) == ("初稿", ("x",))
    deleted = agent_web.personal_memory.route(
        "/api/memory/delete", {"kind": "note", "id": note.note_id}
    )
    assert deleted["ok"] and notes.listed() == []
    undone = agent_web.personal_memory.route(
        "/api/memory/undo", {"kind": "note", "change_id": deleted["change_id"]}
    )
    assert undone["ok"] and [n.note_id for n in notes.listed()] == [note.note_id]
    kinds = [row["kind"] for row in notes.history(note.note_id)]
    assert kinds == ["note_delete", "note_update", "note_add"]
    assert agent_web.personal_memory.route(
        "/api/memory/undo", {"kind": "mail", "change_id": "c"}
    ) == {"ok": False, "code": "memory_kind_unknown", "message": "只能復原筆記或偏好的變更"}
    listed = agent_web.personal_memory.listed("notes")
    assert [item["note_id"] for item in listed["notes"]] == [note.note_id]


def test_each_actor_has_their_own_notes_and_preferences(web: Web) -> None:  # noqa: F811
    agent_web, _ = web
    memory = agent_web.personal_memory
    memory.notes("alice").save("alice 的筆記", actor="alice via web", source_kind="answer")
    memory.preferences("alice").save(
        "skill:engineering/business-cards", "組織圖用英文名", actor="alice via web"
    )
    assert memory.notes("bob").listed() == [] and memory.notes("bob").search(text="alice") == []
    assert memory.preferences("bob").listed() == []
    assert memory.service("alice").path != memory.service("bob").path
    assert [n.text for n in memory.notes("alice").listed()] == ["alice 的筆記"]
