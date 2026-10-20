"""Memory quality on Agent Web and Telegram (accumulated memory M5).

A real Host and Agent Web with a fake model: the memory page's 「立即檢查」 and
a finding's presses (merge, 已離職, stop a preference; each undoable), the
settings, per-actor isolation, the nightly job's report and telemetry
(counts only), and 「為什麼」: what each answer used, recorded per turn by
reference, listed with links on the page and by `/why` in Telegram.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from test_business_cards_conversation import Conversation, _turn
from test_business_cards_conversation import web as web  # noqa: F401 - the fixture

import telemetry.recorder as telemetry
from capabilities.business_cards.contracts import PersonRef
from host_runtime.experience_review import REVIEWS_DIR
from host_runtime.memory_why import NOTHING
from host_runtime.personal_memory import SEARCH_NOTES
from host_runtime.web import AgentWeb
from models.contracts import ModelRequest, ModelResponse

Web = tuple[AgentWeb, Conversation]
SCOPE = "skill:engineering/business-cards"
COMPANY = "範例科技股份有限公司"


class _Internal:
    """The internal model for the contradiction question: records what it
    was asked, answers rules 1 and 2."""

    def __init__(self) -> None:
        self.requests: list[ModelRequest] = []

    def generate(self, request: ModelRequest) -> ModelResponse:
        self.requests.append(request)
        return ModelResponse(
            trace=request.trace,
            model_alias=request.model_alias,
            structured_output={"pairs": [{"a": 1, "b": 2, "why": "一個要英文，一個要中文"}]},
        )

    def stream(self, request: ModelRequest) -> Any:
        raise NotImplementedError


def _seed(agent_web: AgentWeb) -> dict[str, str]:
    store = agent_web.memory_page.cards()

    def add(name: str, when: date, **values: str) -> str:
        fields = {"name": name, "company": COMPANY, "title": "經理", **values}
        return store.add(
            fields, source="card", source_date=when, source_ref="", uncertain=(), actor="seed"
        ).person_id

    first = add("王小明", date(2026, 9, 1), email="hm@a.example", department="射頻部")
    second = add("王小明", date(2026, 9, 2), email="hm@b.example", department="業務部")
    old = add("陳久久", date(2024, 1, 5), email="chen@a.example")
    prefs = agent_web.personal_memory.preferences(agent_web.runtime.actor)
    a, _ = prefs.save(SCOPE, "回覆一律用英文", actor="seed", scope_label="名片／組織圖")
    b, _ = prefs.save(SCOPE, "信件內容請寫中文", actor="seed", scope_label="名片／組織圖")
    return {
        "first": first,
        "second": second,
        "old": old,
        "a": a.preference_id,
        "b": b.preference_id,
    }


def _findings(agent_web: AgentWeb) -> dict[str, list[dict[str, Any]]]:
    overview = agent_web.memory_page.get("/api/memory/overview", {})
    found: dict[str, list[dict[str, Any]]] = {}
    for item in overview["health"]["findings"]:
        found.setdefault(item["kind"], []).append(item)
    return found


def _press(agent_web: AgentWeb, item: dict[str, Any], action: str) -> dict[str, Any]:
    reply: dict[str, Any] = agent_web.memory_page.post(
        "/api/memory/health/decide", {"finding_id": item["finding_id"], "action": action}
    )
    return reply


def test_check_now_cards_and_presses_with_undo(web: Web) -> None:  # noqa: F811
    agent_web, _ = web
    seeded = _seed(agent_web)
    internal = _Internal()
    agent_web.memory_health.model_source = lambda: (internal, "company")
    store = agent_web.memory_page.cards()

    ran = agent_web.memory_page.post("/api/memory/health/run", {})
    assert ran["ok"] and "檢查完成" in ran["message"], ran
    # One structured, bounded question with the rule texts only.
    (asked,) = internal.requests
    assert asked.output_contract == "memory_health_contradictions"
    assert asked.requirements.structured_output and asked.max_output_tokens <= 500
    shown = asked.messages[1].text
    assert "回覆一律用英文" in shown and "信件內容請寫中文" in shown and "2. " in shown
    assert "王小明" not in shown
    found = _findings(agent_web)
    assert set(found) >= {"duplicate", "stale", "contradiction"}
    # A distinct type on the page, with its actions and links.
    duplicate = found["duplicate"][0]
    assert duplicate["kind_label"] == "可能重複" and duplicate["title"].startswith("可能是同一個人")
    assert [a["action"] for a in duplicate["actions"]] == ["merge", "dismiss"]
    assert {link["person_id"] for link in duplicate["links"]} == {
        seeded["first"],
        seeded["second"],
    }
    stale = next(i for i in found["stale"] if i["links"][0]["person_id"] == seeded["old"])
    assert stale["title"] == "陳久久 是否仍在職？"
    # Nothing was changed by the check.
    assert len(store.list_people(company="", source="", status="any", limit=50)[0]) == 3

    # 合併 (undoable through the page's contacts undo).
    merged = _press(agent_web, duplicate, "merge")
    assert merged["ok"] and merged["undo"]["kind"] == "contacts", merged
    assert len(store.list_people(company="", source="", status="any", limit=50)[0]) == 2
    undone = agent_web.memory_page.post(
        "/api/memory/proposals/undo",
        {"space": "contacts/org", "change_id": merged["undo"]["change_id"]},
    )
    assert undone["ok"], undone
    assert len(store.list_people(company="", source="", status="any", limit=50)[0]) == 3
    assert _press(agent_web, duplicate, "merge")["code"] == "finding_closed"

    # 已離職, then undo.
    left = _press(agent_web, stale, "left")
    assert left["ok"] and store.view(seeded["old"]).status == "left"
    history = store.history(PersonRef(person_id=seeded["old"]), limit=3).history
    assert history[0].actor == f"{agent_web.runtime.actor} via web"
    agent_web.memory_page.post(
        "/api/memory/proposals/undo",
        {"space": "contacts/org", "change_id": left["undo"]["change_id"]},
    )
    assert store.view(seeded["old"]).status == "active"

    # 停用第 1 條, then undo through the M3 route.
    contradiction = found["contradiction"][0]
    assert _press(agent_web, contradiction, "nonsense")["code"] == "finding_action_unknown"
    stopped = _press(agent_web, contradiction, "remove_a")
    prefs = agent_web.personal_memory.preferences(agent_web.runtime.actor)
    removed = contradiction["pairs"][0][1]
    assert stopped["ok"] and removed not in [p.text for p in prefs.listed()]
    back = agent_web.personal_memory.route(
        "/api/memory/undo", {"kind": "preference", "change_id": stopped["undo"]["change_id"]}
    )
    assert back["ok"], back
    assert removed in [p.text for p in prefs.listed()]


def test_settings_round_trip_off_means_no_model_call_and_actors_apart(web: Web) -> None:  # noqa: F811
    agent_web, _ = web
    _seed(agent_web)
    internal = _Internal()
    agent_web.memory_health.model_source = lambda: (internal, "company")
    saved = agent_web.memory_page.post(
        "/api/memory/health/settings",
        {"enabled": False, "freshness_months": 18, "unused_days": 30},
    )
    assert saved["ok"], saved
    overview = agent_web.memory_page.get("/api/memory/overview", {})
    assert overview["health"]["settings"] == {
        "enabled": False,
        "freshness_months": 18,
        "unused_days": 30,
    }
    assert overview["health"]["rule_periods"] == ["P12M"]
    off = agent_web.memory_page.post("/api/memory/health/run", {})
    assert off["code"] == "health_off"
    agent_web.memory_health.run_all()
    assert internal.requests == [] and overview["health"]["findings"] == []
    wrong = agent_web.memory_page.post("/api/memory/health/settings", {"unused_days": 0})
    assert wrong["code"] == "health_settings_invalid"

    # Another actor's findings are theirs alone.
    agent_web.memory_page.post("/api/memory/health/settings", {"enabled": True})
    agent_web.memory_page.post("/api/memory/health/run", {})
    mine = _findings(agent_web)["duplicate"][0]
    other = agent_web.memory_health.decide("someone-else", {"finding_id": mine["finding_id"]})
    assert other["code"] == "finding_unknown"
    assert agent_web.memory_health.overview("someone-else")["findings"] == []


def test_the_nightly_job_reports_counts_only(
    web: Web,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    agent_web, _ = web
    _seed(agent_web)
    agent_web.memory_health.model_source = lambda: None
    emitted: list[tuple[str, dict[str, Any]]] = []
    monkeypatch.setattr(
        telemetry,
        "emit",
        lambda event, **kw: emitted.append((event, dict(kw.get("attributes") or {}))),
    )
    night = datetime.now().astimezone().replace(hour=3, minute=0)
    agent_web.nightly_tick(night)
    folder = agent_web.runtime.layout.workspace_root / REVIEWS_DIR
    (report,) = folder.glob("review-*.json")
    data = json.loads(report.read_text(encoding="utf-8"))
    health = data["memory_health"]
    assert health["checked"] >= 1 and health["found"]["duplicate"] == 1
    assert health["model"] == {"unavailable": 1} and health["model_calls"] == 0
    markdown = report.with_suffix(".md").read_text(encoding="utf-8")
    assert "## Memory health" in markdown and "王小明" not in markdown
    assert "王小明" not in report.read_text(encoding="utf-8")
    (checked,) = [attrs for event, attrs in emitted if event == "memory.health_checked"]
    assert checked["found_duplicate"] == 1 and checked["model"] == "unavailable"
    assert all(
        isinstance(value, bool | int) or value in ("unavailable",) for value in checked.values()
    )
    # Once a night.
    agent_web.nightly_tick(night + timedelta(minutes=30))
    assert len(list(folder.glob("review-*.json"))) == 1
    # Before 02:00 nothing runs.
    agent_web.nightly_tick(night.replace(hour=1) + timedelta(days=1))
    assert len(list(folder.glob("review-*.json"))) == 1


# -- 「為什麼」 ------------------------------------------------------------------------


def test_each_answer_records_what_it_used_and_the_page_lists_it(web: Web) -> None:  # noqa: F811
    agent_web, model = web
    actor = agent_web.runtime.actor
    prefs = agent_web.personal_memory.preferences(actor)
    rule, _ = prefs.save(SCOPE, "組織圖不用問是否含離職", actor="seed", scope_label="名片／組織圖")
    note, _ = agent_web.personal_memory.notes(actor).save(
        "WNC 的 RF 主管是王小明", actor="seed", source_kind="answer", tags=["WNC"]
    )
    session = agent_web.create_conversation()["conversation"]["session_id"]
    model.then(
        {
            "tools": [
                (
                    "cards__add_card",
                    {"name": "王小明", "company": COMPANY, "email": "hm@a.example"},
                ),
                (SEARCH_NOTES, {"query": "RF"}),
            ]
        },
        {"text": f"已存王小明。你之前記過 [筆記 {note.note_id}]。"},
    )
    replied = _turn(agent_web, session, "存這張名片；我之前有記過 RF 的什麼？")
    answer = replied["answer"]
    assert answer["preferences_used"] == [rule.preference_id]
    person = agent_web.memory_page.cards().find("王小明", status="any", limit=5)[0][0].person_id
    assert f"contacts/org:person:{person}" in answer["memory_used"]
    assert f"personal/notes:note:{note.note_id}" in answer["memory_used"]
    asked, stored = agent_web.conversations(session)["selected"]["messages"]
    assert stored["memory_used"] == answer["memory_used"] and asked["memory_used"] == []
    # References only: no names, no note text.
    assert "王小明" not in json.dumps(stored["memory_used"], ensure_ascii=False)
    # When the preference was last used is recorded (unused preferences).
    assert rule.preference_id in prefs.last_used()

    why = agent_web.memory_page.get(
        "/api/memory/why", {"session_id": session, "message_id": stored["message_id"]}
    )
    assert why["ok"], why
    shown = {(item["kind"], item["id"]): item for item in why["items"]}
    assert shown[("preference", rule.preference_id)]["label"] == "組織圖不用問是否含離職"
    assert shown[("preference", rule.preference_id)]["tab"] == "preferences"
    assert shown[("person", person)]["label"] == "王小明"
    assert shown[("note", note.note_id)]["tab"] == "notes"
    # Deleted since: still listed, marked gone.
    prefs.remove(rule.preference_id, actor="seed")
    again = agent_web.memory_why.for_message(session, stored["message_id"])
    assert next(i for i in again["items"] if i["kind"] == "preference")["gone"] is True
    unknown = agent_web.memory_page.get(
        "/api/memory/why", {"session_id": session, "message_id": "nope"}
    )
    assert unknown["code"] == "message_unknown"


def test_telegram_why_answers_for_the_last_turn(
    web: Web,  # noqa: F811
    tmp_path: Path,
) -> None:
    from test_chat_workflow_forms_telegram import _Scripted
    from test_telegram_ingress import OWNER, FakeTransport, ingress, poll, update

    agent_web, _ = web
    transport = FakeTransport([[update(1, OWNER, "/why")]])
    item, agent, _ = ingress(tmp_path / "bot", transport)
    agent.gateway.turn_memory = agent_web.personal_memory.turn
    item.cards = agent_web
    assert poll(item).deliveries[0].reply == NOTHING
    actor, _ = item._acting(item.config.actor_for(OWNER) or "")
    note, _ = agent_web.personal_memory.notes(actor).save(
        "EXN 樣品延後到 11 月", actor="seed", source_kind="answer"
    )
    agent.gateway.router.model = _Scripted(
        {"tools": [(SEARCH_NOTES, {"query": "樣品"})]},
        {"text": f"你之前記過：EXN 樣品延後到 11 月 [筆記 {note.note_id}]。"},
    )
    transport.batches.append([update(2, OWNER, "我之前有記過樣品的什麼？")])
    assert "樣品" in (poll(item).deliveries[0].reply or "")
    transport.batches.append([update(3, OWNER, "/why")])
    reply = poll(item).deliveries[0].reply or ""
    assert reply.startswith("上一則回答用到：")
    assert "筆記：EXN 樣品延後到 11 月" in reply and "Agent Web 的「記憶」頁" in reply
    assert "/why" in item_help()


def item_help() -> str:
    from channels.telegram import HELP

    return HELP


def test_the_page_has_the_health_cards_settings_and_why() -> None:
    from host_runtime.web_page import PAGE

    for hook in (
        'id="mem-health-run"',
        'id="mem-health-list"',
        '"/api/memory/health/run"',
        '"/api/memory/health/decide"',
        '"/api/memory/health/settings"',
        "function whyButton(messageId)",
        '"/api/memory/why?session_id="',
        "function memGoto(item)",
        "mem-health-tag",
    ):
        assert hook in PAGE, hook
