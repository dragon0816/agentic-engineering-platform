"""The person's preferences (accumulated memory M3, docs/phases/ACCUMULATED_MEMORY.md §5).

Owner 2026-10-20: a rule the person states in chat is saved only when they
press 存成偏好 on the Agent's card (「按一下才存」); there is no model tool
that saves one. A contradiction with an active preference of the same scope
is asked about first, both shown. While the Skill is in use, the Host gives
the model its active preferences (bounded, labelled as the person's) and
records which ones on the answer. The claim check and the guidance steer
「規則我已改成」 toward a proposal. Real Host, fake model, no network.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from test_business_cards_conversation import Conversation, _turn
from test_business_cards_conversation import web as web  # noqa: F401 - the fixture

from agent.conversation_harness import check_answer
from agent.gateway import ConversationToolExecution, HostToolOutcome
from capabilities.business_cards.manifest import CARDS_SKILL
from common.action_cards import CARD_KEY, ActionCard, telegram_card
from common.execution import RequestContext, TraceIdentifiers
from host_runtime.personal_memory import (
    MAX_INJECTED,
    MAX_INJECTED_CHARS,
    PROPOSE_NOTE,
    PROPOSE_PREFERENCE,
    SEARCH_NOTES,
)
from host_runtime.web import AgentWeb
from memory.preferences import Preferences, polarity, subject

CARDS_SCOPE = "skill:engineering/business-cards"
RULE = "執行時不需要問是否包含在職人員"
OPPOSITE = "執行時要問是否包含在職人員"
Web = tuple[AgentWeb, Conversation]


def _prefs(agent_web: AgentWeb) -> Preferences:
    return agent_web.personal_memory.preferences(agent_web.runtime.actor)


def _session(agent_web: AgentWeb) -> str:
    return str(agent_web.create_conversation()["conversation"]["session_id"])


def _propose(agent_web: AgentWeb, model: Conversation, session: str, rule: str) -> dict[str, Any]:
    model.then(
        {"tools": [(PROPOSE_PREFERENCE, {"rule": rule, "skill": "cards"})]},
        {"text": "這次就不問了；要記成偏好請按下面的「存成偏好」。"},
    )
    replied = _turn(agent_web, session, f"{rule}，以後都這樣")
    card = replied["answer"][CARD_KEY]
    assert card["status"] == "pending", card
    return dict(card)


def _stored(agent_web: AgentWeb, session: str) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = agent_web.conversations(session)["selected"]["messages"]
    return messages


# -- the deterministic conflict check -------------------------------------------


def test_polarity_and_subject_are_deterministic() -> None:
    assert polarity(RULE) == "negative" and polarity(OPPOSITE) == "positive"
    assert subject(RULE) == subject(OPPOSITE) == "執行時問是否包含在職人員"
    assert polarity("以後都別問我要不要包含離職人員") == "negative"
    # 別 inside a word is not a negation.
    assert polarity("特別注意 email 的拼字") == "positive"
    assert polarity("分別列出各部門") == "positive"
    assert polarity("Don't ask about current staff") == "negative"
    assert polarity("Always ask about current staff") == "positive"
    assert subject("Don't ask about current staff") == subject("Always ask about current staff")


def test_the_check_finds_duplicates_and_contradictions_in_the_same_scope_only(
    web: Web,  # noqa: F811
) -> None:
    agent_web, _ = web
    prefs = _prefs(agent_web)
    prefs.save(CARDS_SCOPE, RULE, actor="engineer via web", scope_label="名片／組織圖")
    found = prefs.check(CARDS_SCOPE, OPPOSITE)
    assert [item.text for item in found.conflicts] == [RULE] and not found.duplicates
    again = prefs.check(CARDS_SCOPE, RULE + "。")
    assert [item.text for item in again.duplicates] == [RULE] and not again.conflicts
    assert prefs.check("skill:engineering/other", OPPOSITE).conflicts == ()
    assert prefs.check(CARDS_SCOPE, "組織圖用英文名").conflicts == ()


# -- the proposal card: nothing is saved without the press ---------------------------


def test_a_proposal_is_a_card_and_nothing_is_saved_without_the_press(web: Web) -> None:  # noqa: F811
    agent_web, model = web
    session = _session(agent_web)
    card = _propose(agent_web, model, session, RULE)
    assert card["title"] == "要把這條記成『名片／組織圖』的偏好嗎？"
    assert card["preview"] == RULE and card["ends_turn"] is False
    assert [(b["action"], b["label"]) for b in card["buttons"]] == [
        ("save", "存成偏好"),
        ("decline", "不用"),
    ]
    # The turn went on: the model's own answer is the text, the card under it.
    answer = _stored(agent_web, session)[-1]
    assert (
        answer["text"].startswith("這次就不問了") and answer[CARD_KEY]["card_id"] == card["card_id"]
    )
    assert len(model.requests) == 2
    # Nothing saved, and no model tool saves one.
    assert _prefs(agent_web).listed(include_inactive=True) == []
    offered = {tool.name for tool in model.requests[0].tools}
    assert PROPOSE_PREFERENCE in offered
    assert not any("save" in name and "preference" in name for name in offered)
    # 不用: still nothing.
    declined = agent_web.decide_card(card["card_id"], "decline")
    assert declined["ok"] and declined["card"]["status"] == "declined"
    assert _prefs(agent_web).listed(include_inactive=True) == []
    # The same card cannot be pressed again.
    assert agent_web.decide_card(card["card_id"], "save")["ok"] is False


def test_the_press_saves_it_with_its_source_and_history(web: Web) -> None:  # noqa: F811
    agent_web, model = web
    session = _session(agent_web)
    card = _propose(agent_web, model, session, RULE)
    assert card in agent_web.cards(session)["cards"]
    saved = agent_web.decide_card(card["card_id"], "save")
    assert saved["ok"] and saved["card"]["status"] == "saved"
    assert "之後使用『名片／組織圖』時會自動套用" in saved["card"]["outcome"]
    (item,) = _prefs(agent_web).listed()
    asked, answered = _stored(agent_web, session)[-2:]
    assert (item.scope, item.scope_label, item.text) == (CARDS_SCOPE, "名片／組織圖", RULE)
    assert item.created_by == f"{agent_web.runtime.actor} via web"
    assert (item.source_session, item.source_message) == (session, asked["message_id"])
    assert item.polarity == "negative" and item.proposed_by == "agent"
    (row,) = _prefs(agent_web).history(item.preference_id)
    assert (row["kind"], row["new"], row["actor"]) == ("preference_add", RULE, item.created_by)
    # The conversation keeps the card as decided, and the outcome for the model.
    assert answered[CARD_KEY]["status"] == "saved"
    assert f"[card {card['card_id']}] 已儲存" in answered["tool_summary"]
    # Proposing it again is refused: it is saved already.
    model.then({"tools": [(PROPOSE_PREFERENCE, {"rule": RULE, "skill": "cards"})]}, {"text": "ok"})
    _turn(agent_web, session, RULE)
    assert "preference_already_saved" in model.tool_results()[0]


def test_undo_takes_a_saved_preference_back(web: Web) -> None:  # noqa: F811
    agent_web, model = web
    session = _session(agent_web)
    card = _propose(agent_web, model, session, RULE)
    change = agent_web.decide_card(card["card_id"], "save")["card"]
    record = agent_web.personal_memory.store.get(change["card_id"])
    assert record is not None and record.change_id
    undone = agent_web.personal_memory.route(
        "/api/memory/undo", {"kind": "preference", "change_id": record.change_id}
    )
    assert undone["ok"] and undone["reverted"] == 1
    assert _prefs(agent_web).listed() == []
    (item,) = _prefs(agent_web).listed(include_inactive=True)
    assert item.status == "removed"
    again = agent_web.personal_memory.route(
        "/api/memory/undo", {"kind": "preference", "change_id": record.change_id}
    )
    assert again["code"] == "change_already_undone"
    # Removing is undoable too.
    other, _ = _prefs(agent_web).save(CARDS_SCOPE, "組織圖用英文名", actor="engineer via web")
    removed = agent_web.personal_memory.route(
        "/api/memory/delete", {"kind": "preference", "id": other.preference_id}
    )
    assert removed["ok"] and _prefs(agent_web).listed() == []
    agent_web.personal_memory.route(
        "/api/memory/undo", {"kind": "preference", "change_id": removed["change_id"]}
    )
    assert [item.text for item in _prefs(agent_web).listed()] == ["組織圖用英文名"]


def test_a_contradiction_at_save_asks_first_with_both_shown(web: Web) -> None:  # noqa: F811
    agent_web, model = web
    session = _session(agent_web)
    first = _propose(agent_web, model, session, RULE)
    agent_web.decide_card(first["card_id"], "save")
    (old,) = _prefs(agent_web).listed()
    card = _propose(agent_web, model, session, OPPOSITE)
    asked = agent_web.decide_card(card["card_id"], "save")
    assert asked["ok"] is False and asked["code"] == "preference_conflict"
    shown = asked["card"]
    assert shown["status"] == "pending" and "矛盾" in shown["title"]
    assert [(r["before"], r["after"]) for r in shown["rows"]] == [(RULE, OPPOSITE)]
    assert [b["action"] for b in shown["buttons"]] == ["replace", "keep_both", "decline"]
    # Nothing saved yet; the old one still applies.
    assert [item.text for item in _prefs(agent_web).listed()] == [RULE]
    assert agent_web.decide_card(card["card_id"], "save")["code"] == "card_action_unknown"
    replaced = agent_web.decide_card(card["card_id"], "replace")
    assert replaced["ok"] and f"取代了 {old.preference_id}" in replaced["card"]["outcome"]
    assert [item.text for item in _prefs(agent_web).listed()] == [OPPOSITE]
    stale = _prefs(agent_web).get(old.preference_id)
    assert stale is not None and stale.status == "replaced"
    # One undo brings the old one back and takes the new one away.
    record = agent_web.personal_memory.store.get(card["card_id"])
    assert record is not None
    _prefs(agent_web).undo(record.change_id, actor="engineer via web")
    assert [item.text for item in _prefs(agent_web).listed()] == [RULE]
    # 兩條都留 keeps both.
    third = _propose(agent_web, model, session, OPPOSITE)
    agent_web.decide_card(third["card_id"], "save")
    kept = agent_web.decide_card(third["card_id"], "keep_both")
    assert kept["ok"] and sorted(i.text for i in _prefs(agent_web).listed()) == sorted(
        [RULE, OPPOSITE]
    )


# -- applying: the Skill's preferences reach the model, bounded ---------------------


def test_injection_only_for_the_matching_scope_and_bounded(web: Web) -> None:  # noqa: F811
    agent_web, model = web
    prefs = _prefs(agent_web)
    mine, _ = prefs.save(CARDS_SCOPE, RULE, actor="engineer via web", scope_label="名片／組織圖")
    prefs.save("skill:engineering/other", "週報用英文寫", actor="engineer via web")
    session = _session(agent_web)
    model.then({"text": "好的"})
    replied = _turn(agent_web, session, "WNC 組織圖")
    system = model.requests[0].messages[0].text
    assert "The person's saved preferences" in system
    assert f"- [{mine.preference_id}] 名片／組織圖: {RULE}" in system
    assert "週報用英文寫" not in system
    assert replied["answer"]["preferences_used"] == [mine.preference_id]
    # Many preferences: at most MAX_INJECTED lines and MAX_INJECTED_CHARS.
    for number in range(30):
        prefs.save(CARDS_SCOPE, f"組織圖第{number}號規則" + "說明" * 20, actor="engineer via web")
    model.then({"text": "好的"})
    _turn(agent_web, session, "WNC 組織圖")
    system = model.requests[-1].messages[0].text
    lines = [line for line in system.splitlines() if line.startswith("- [p-")]
    assert 1 <= len(lines) <= MAX_INJECTED
    assert sum(len(line) for line in lines) <= MAX_INJECTED_CHARS
    # The Skill switched off: no scope in use, nothing injected.
    agent_web.runtime.agent.gateway.router.commands.skills.remove(CARDS_SKILL)
    model.then({"text": "好的"})
    replied = _turn(agent_web, session, "WNC 組織圖")
    assert "The person's saved preferences" not in model.requests[-1].messages[0].text
    assert "preferences_used" not in replied["answer"]


def test_the_preferences_used_are_recorded_on_the_turn(web: Web) -> None:  # noqa: F811
    agent_web, model = web
    mine, _ = _prefs(agent_web).save(CARDS_SCOPE, RULE, actor="engineer via web")
    session = _session(agent_web)
    model.then({"tools": [("cards__list", {})]}, {"text": "名片夾目前沒有人。"})
    _turn(agent_web, session, "列出名片")
    asked, answered = _stored(agent_web, session)
    assert answered["preferences_used"] == [mine.preference_id]
    assert asked["preferences_used"] == []


# -- the claim check and the guidance lead to a proposal ---------------------------


def _done(name: str, data: Any = None) -> ConversationToolExecution:
    return ConversationToolExecution(
        call_id="c1", name=name, host=HostToolOutcome(status="succeeded", data=data)
    )


def test_a_proposal_alone_never_backs_a_claim_that_the_rule_is_saved() -> None:
    proposed = _done(PROPOSE_PREFERENCE, {CARD_KEY: {"card_id": "mm-000000000000"}})
    checks, reasons = check_answer("規則我已改成：執行時不再詢問。", (proposed,), ())
    assert checks[0].status == "failed" and "memory__propose_preference" in reasons[0]
    note = _done(PROPOSE_NOTE)
    assert check_answer("我已記住這個偏好。", (note,), ())[0][0].status == "failed"
    # Saying it is only proposed is fine.
    assert check_answer("要保存請按「存成偏好」。", (proposed,), ())[0][0].status == "passed"


def test_the_claim_check_and_the_guidance_lead_to_a_proposal(web: Web) -> None:  # noqa: F811
    agent_web, model = web
    session = _session(agent_web)
    model.then(
        {"tools": [("cards__list", {})]},
        {"text": "好的，規則我已改成：執行時不再詢問是否包含在職人員。"},
        {"tools": [(PROPOSE_PREFERENCE, {"rule": RULE, "skill": "cards"})]},
        {"text": "這次不問了；這條還沒保存，按下面的「存成偏好」才會記住。"},
    )
    replied = _turn(agent_web, session, RULE)
    answer = replied["answer"]
    assert answer["answer"].startswith("這次不問了") and "系統檢查" not in answer["answer"]
    assert answer[CARD_KEY]["title"] == "要把這條記成『名片／組織圖』的偏好嗎？"
    system = model.requests[0].messages[0].text
    assert "memory__propose_preference" in system and "never say it is saved" in system
    retry = model.requests[2].messages[-1].text
    assert retry.startswith("[Host check failed]") and "memory__propose_preference" in retry
    assert _prefs(agent_web).listed() == []


# -- Telegram ---------------------------------------------------------------------


def test_telegram_shows_the_answer_and_the_card_and_a_tap_saves_it(
    web: Web,  # noqa: F811
    tmp_path: Path,
) -> None:
    from test_chat_workflow_forms_telegram import _Scripted
    from test_telegram_ingress import OWNER, FakeTransport, ingress, poll, update
    from test_telegram_workflow_flow import _tap

    agent_web, _ = web
    transport = FakeTransport([[update(1, OWNER, RULE)]])
    item, agent, _ = ingress(tmp_path / "bot", transport)
    agent.gateway.turn_memory = agent_web.personal_memory.turn
    item.cards = agent_web
    agent.gateway.router.model = _Scripted(
        {"tools": [(PROPOSE_PREFERENCE, {"rule": RULE, "skill": "cards"})]},
        {"text": "這次不問了。"},
    )
    delivery = poll(item).deliveries[0]
    reply = delivery.reply or ""
    assert reply.startswith("這次不問了。") and "要把這條記成『名片／組織圖』的偏好嗎？" in reply
    [row] = delivery.buttons
    assert [label for label, _ in row] == ["存成偏好", "不用"]
    transport.batches.append([_tap(2, OWNER, row[0][1])])
    tapped = poll(item).deliveries[0]
    assert "✅ 已儲存" in (tapped.reply or "") and tapped.buttons == ()
    card_id = row[0][1].split(":")[1]
    record = agent_web.personal_memory.store.get(card_id)
    assert record is not None and record.session_id == "telegram-chat-111"
    (saved,) = agent_web.personal_memory.preferences(record.actor).listed()
    assert saved.text == RULE and saved.created_by == f"{record.actor} via telegram"


def test_the_card_draws_in_telegram_with_its_buttons() -> None:
    from datetime import UTC, datetime, timedelta

    from host_runtime.personal_memory import MemoryCard, draw

    now = datetime.now(UTC)
    record = MemoryCard(
        card_id="mm-0123456789ab",
        kind="preference",
        created_at=now,
        expires_at=now + timedelta(hours=1),
        actor="engineer",
        scope=CARDS_SCOPE,
        scope_label="名片／組織圖",
        text=RULE,
    )
    text, buttons = telegram_card(draw(record))
    assert text.startswith("要把這條記成『名片／組織圖』的偏好嗎？") and RULE in text
    assert buttons == (
        (("存成偏好", "card:mm-0123456789ab:save"), ("不用", "card:mm-0123456789ab:decline")),
    )
    assert ActionCard.model_validate(draw(record).model_dump(mode="json")).ends_turn is False


def test_no_person_no_proposal_tools_and_search_only_when_allowed(web: Web) -> None:  # noqa: F811
    agent_web, _ = web
    memory = agent_web.personal_memory
    skills = tuple(
        item
        for item in agent_web.runtime.agent.gateway.router.commands.skills.manifests()
        if item.metadata.identity.name != "business-cards"
    )

    def context(message: str, session: str | None) -> RequestContext:
        return RequestContext(
            trace=TraceIdentifiers(trace_id="t", request_id="r", span_id="s"),
            actor="engineer",
            namespace="engineering",
            channel="test",
            message=message,
            session_id=session,
        )

    names = {tool.tool.name for tool in memory.turn(context("hi", None), skills).tools}
    assert names == set()
    names = {tool.tool.name for tool in memory.turn(context("hi", "s-1"), skills).tools}
    assert names == {PROPOSE_PREFERENCE, PROPOSE_NOTE}
    asked = memory.turn(context("我之前有記過什麼關於 WNC 的？", "s-1"), skills)
    assert SEARCH_NOTES in {tool.tool.name for tool in asked.tools}
    assert asyncio.run(_offered_search(memory, skills)) is False


async def _offered_search(memory: Any, skills: Any) -> bool:
    context = RequestContext(
        trace=TraceIdentifiers(trace_id="t", request_id="r", span_id="s"),
        actor="engineer",
        namespace="engineering",
        channel="test",
        message="WNC 組織圖",
        session_id="s-1",
    )
    found = await asyncio.to_thread(memory.turn, context, skills)
    return SEARCH_NOTES in {tool.tool.name for tool in found.tools}


def test_the_effects_text_follows_the_rule_direction() -> None:
    """#233: a rule to ask must not read 「不再詢問」."""
    from host_runtime.personal_memory import preference_effect

    assert preference_effect("名片／組織圖", RULE).endswith("不再詢問。")
    to_ask = preference_effect("名片／組織圖", "每次都先問我是否包含在職人員")
    assert "不再詢問" not in to_ask and to_ask.endswith("照這條先問你。")
    assert preference_effect("Mail", "Always ask before sending").endswith("照這條先問你。")
    plain = preference_effect("名片／組織圖", "一律包含在職人員")
    assert plain == "之後使用『名片／組織圖』時會自動套用這條規則。"


def test_a_card_for_a_rule_to_ask_says_it_will_ask(web: Web) -> None:  # noqa: F811
    agent_web, model = web
    session = _session(agent_web)
    card = _propose(agent_web, model, session, "每次都先問我是否包含在職人員")
    assert card["effects"] == ["之後使用『名片／組織圖』時會自動套用，照這條先問你。"]
    saved = agent_web.decide_card(card["card_id"], "save")
    assert "不再詢問" not in saved["card"]["outcome"]
    assert "照這條先問你" in saved["card"]["outcome"]
