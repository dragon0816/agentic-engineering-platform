"""Accumulated memory M2: the incremental signature harvest and the org chart
that reads new mail first (docs/phases/ACCUMULATED_MEMORY.md §4, §10.1).

The second harvest of a domain reads only mail newer than the last one
(minus an overlap window, de-duplicated by message id); mail already
observed is skipped; the mail scope caps the window; a partial failure moves
the state only as far as was processed; an extractor change or 「重新整理」
reads the full scope again and says so. The org chart harvests first and
returns new people as candidates to confirm, never stored. Fake mailbox and
fake models only: no real mail.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from test_business_cards_capabilities import (
    BODY,
    NOW,
    FakeMail,
    FlakyMail,
    SignatureModel,
    _bridge,
    _message,
    _run,
)
from test_business_cards_conversation import Conversation, _turn, web  # noqa: F401

from capabilities.business_cards import harvest, signatures
from capabilities.business_cards.handlers import CHART_SPEC, NO_DOMAIN_NOTE
from capabilities.business_cards.manifest import CARDS_SKILL, PROCEDURE
from capabilities.business_cards.store import CardStore
from host_runtime.business_cards_tools import CHART_TOOL, TOOLS
from host_runtime.web import AgentWeb
from integrations.outlook_mail import MailError, MailScope, MailSummary
from models.contracts import ModelRequest, ModelResponse, ModelStreamEvent

SCOPE = MailScope(max_days=180)


def _mail() -> FakeMail:
    return FakeMail(
        [
            _message(
                "m-wang",
                "Wang <hm.wang@example.com>",
                BODY.format(name="王小明", title="協理", ext="1"),
            ),
            _message(
                "m-lee",
                "lee@example.com",
                BODY.format(name="李大華", title="工程師", ext="2"),
                days_ago=3,
            ),
        ]
    )


def _add(mail: FakeMail, message_id: str, sender: str, name: str, *, hours_ago: float) -> None:
    item = _message(message_id, sender, BODY.format(name=name, title="經理", ext="7"))
    mail.messages[message_id] = item.model_copy(
        update={"received": NOW - timedelta(hours=hours_ago)}
    )


def _day(moment: datetime) -> str:
    return harvest.local_day(moment)


def _handler(bridge: Any, name: str) -> Any:
    spec = next(item for item in bridge.installed.discover() if item.identity.name == name)
    return bridge.installed.get(spec.identity).handler


def _sync_history(tmp_path: Path) -> list[Any]:
    space = _store(tmp_path).memory.space("contacts/org", asset=CARDS_SKILL)
    return space.sync_history("mail:Inbox", "example.com")


def _store(tmp_path: Path) -> CardStore:
    return CardStore.for_actor(tmp_path / "workspace", "alice")


def test_the_second_harvest_reads_only_newer_mail(tmp_path: Path) -> None:
    mail = _mail()
    bridge = _bridge(tmp_path, mail=mail, scope=SCOPE, model=SignatureModel())
    first = _run(bridge, "harvest-signatures", {"domain": "example.com"}).data
    assert first["scan_note"].startswith("首次整理（收件匣 180 天內）：掃描 2 封")
    assert sorted(c["name"] for c in first["candidates"]) == ["李大華", "王小明"]
    (window,) = first["domains"]
    assert (window["domain"], window["source"], window["mode"]) == (
        "example.com",
        "mail:Inbox",
        "first",
    )
    # The state is the newest message processed.
    newest = NOW - timedelta(days=1)
    assert datetime.fromisoformat(window["synced_to"]) == newest
    assert _run(bridge, "store-candidates", {"candidate_ids": ["all"]}).status == "succeeded"

    _add(mail, "m-chen", "chen@example.com", "陳新", hours_ago=2)
    opened = len(mail.opened)
    second = _run(bridge, "harvest-signatures", {"domain": "example.com"}).data
    assert mail.opened[opened:] == ["m-chen"]  # only the new message was opened
    assert [c["name"] for c in second["candidates"]] == ["陳新"]
    assert second["domains"][0]["mode"] == "incremental"
    assert second["scan_note"].startswith(f"從 {_day(newest)} 之後的新信：掃描 2 封")
    # m-wang falls in the overlap window and is skipped by its id.
    assert second["already_seen"] == 1 and "1 封先前已整理過，略過" in second["scan_note"]
    # The mailbox was asked only for the last few days, not the whole scope.
    assert NOW - mail.listed[-1][1] < timedelta(days=4)
    state = _store(tmp_path).sync_state("mail:Inbox", "example.com")
    assert state is not None and state.extractor_version == signatures.EXTRACTOR_VERSION
    assert "m-chen" in state.last_message_ids and state.updated_by == "alice via local"


def test_the_overlap_reads_a_late_message_once_and_never_reproposes_a_declined_one(
    tmp_path: Path,
) -> None:
    mail = _mail()
    bridge = _bridge(tmp_path, mail=mail, scope=SCOPE, model=SignatureModel())
    first = _run(bridge, "harvest-signatures", {"domain": "example.com"}).data
    assert len(first["candidates"]) == 2  # the person stores none of them
    # A message that reached the folder late, dated before the last one.
    _add(mail, "m-late", "late@example.com", "晚到", hours_ago=30)
    opened = len(mail.opened)
    second = _run(bridge, "harvest-signatures", {"domain": "example.com"}).data
    assert mail.opened[opened:] == ["m-late"]
    assert [c["name"] for c in second["candidates"]] == ["晚到"]
    assert second["already_seen"] == 1  # m-wang: processed last time, declined
    third = _run(bridge, "harvest-signatures", {"domain": "example.com"}).data
    assert third["candidates"] == [] and "no new people" in third["note"]
    assert third["already_seen"] == 2  # m-wang and m-late, by id
    # Nothing new: the earlier candidates of this conversation stay storable.
    stored = _run(bridge, "store-candidates", {"candidate_ids": ["all"]})
    assert stored.status == "succeeded" and stored.data["stored"] == ["s1"]


def test_a_message_already_observed_is_skipped_and_counted(tmp_path: Path) -> None:
    mail = _mail()
    bridge = _bridge(tmp_path, mail=mail, scope=SCOPE, model=SignatureModel())
    added = _run(
        bridge,
        "add-from-signature",
        {
            "entries": [
                {
                    "name": "王小明",
                    "company": "範例科技",
                    "email": "hm.wang@example.com",
                    "message_id": "m-wang",
                    "message_date": (NOW - timedelta(days=1)).date().isoformat(),
                }
            ]
        },
    )
    assert added.status == "succeeded"
    data = _run(bridge, "harvest-signatures", {"domain": "example.com"}).data
    assert mail.opened == ["m-lee"]
    assert [c["name"] for c in data["candidates"]] == ["李大華"]
    assert data["already_seen"] == 1 and "1 封先前已整理過，略過" in data["scan_note"]


def test_the_mail_scope_caps_the_window(tmp_path: Path) -> None:
    mail = FakeMail(
        [
            _message(
                "old",
                "a@example.com",
                BODY.format(name="老信", title="經理", ext="1"),
                days_ago=100,
            )
        ]
    )
    scope = {"value": SCOPE}
    bridge = _bridge(tmp_path, mail=mail, model=SignatureModel())
    # The bridge reads the scope at each call; the person narrows it later.
    handler: Any = _handler(bridge, "harvest-signatures")
    handler._scope = lambda: scope["value"]
    first = _run(bridge, "harvest-signatures", {"domain": "example.com"}).data
    assert [c["name"] for c in first["candidates"]] == ["老信"]
    scope["value"] = MailScope(max_days=30)
    second = _run(bridge, "harvest-signatures", {"domain": "example.com"}).data
    assert second["domains"][0]["mode"] == "incremental"
    assert "（讀信設定只到 30 天內）" in second["scan_note"]
    # The incremental window would start 101 days back; the scope caps it at 30.
    assert NOW - mail.listed[-1][1] <= timedelta(days=30, minutes=1)
    since = datetime.fromisoformat(second["domains"][0]["since"])
    assert since >= NOW - timedelta(days=30, minutes=1)


class _Recovering(FlakyMail):
    def __init__(self, *args: Any) -> None:
        super().__init__(*args)
        self.broken = True

    def get(self, message_id: str) -> Any:
        if message_id == "bad" and not self.broken:
            self.opened.append(message_id)
            return self.messages[message_id]
        return super().get(message_id)


def test_a_partial_failure_moves_the_state_only_to_the_last_full_date(tmp_path: Path) -> None:
    mail = _Recovering(
        [
            _message("ok1", "a@example.com", BODY.format(name="王小明", title="協理", ext="1")),
            _message(
                "bad",
                "x@example.com",
                BODY.format(name="讀不到", title="經理", ext="9"),
                days_ago=2,
            ),
            _message(
                "ok2",
                "b@example.com",
                BODY.format(name="李大華", title="工程師", ext="2"),
                days_ago=3,
            ),
        ]
    )
    bridge = _bridge(tmp_path, mail=mail, scope=SCOPE, model=SignatureModel())
    first = _run(bridge, "harvest-signatures", {"domain": "example.com"}).data
    assert sorted(c["name"] for c in first["candidates"]) == ["李大華", "王小明"]
    assert first["skipped"] == [{"code": "message_unknown", "count": 1}]
    synced = datetime.fromisoformat(first["domains"][0]["synced_to"])
    # Just before the unreadable message, not the newest one read.
    assert synced < NOW - timedelta(days=2) and synced > NOW - timedelta(days=2, seconds=1)
    assert f"整理進度只更新到 {_day(synced)}" in first["scan_note"]
    mail.broken = False
    opened = len(mail.opened)
    second = _run(bridge, "harvest-signatures", {"domain": "example.com"}).data
    assert mail.opened[opened:] == ["bad"]  # read now; the others are skipped by id
    assert [c["name"] for c in second["candidates"]] == ["讀不到"]
    assert datetime.fromisoformat(second["domains"][0]["synced_to"]) == NOW - timedelta(days=1)


def _people_with(response: ModelResponse, **extra: str) -> ModelResponse:
    data: Any = response.structured_output
    people = [{**item, **extra} for item in data["people"]]
    return response.model_copy(update={"structured_output": {"people": people}})


class _BetterReader(SignatureModel):
    """A new extractor: reads the department too."""

    def generate(self, request: ModelRequest) -> ModelResponse:
        return _people_with(super().generate(request), department="射頻部")


def test_an_extractor_change_reads_the_full_scope_again_and_says_why(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    mail = _mail()
    bridge = _bridge(tmp_path, mail=mail, scope=SCOPE, model=SignatureModel())
    _run(bridge, "harvest-signatures", {"domain": "example.com"})
    assert _run(bridge, "store-candidates", {"candidate_ids": ["all"]}).status == "succeeded"
    unchanged = _run(bridge, "harvest-signatures", {"domain": "example.com"}).data
    assert unchanged["candidates"] == []

    monkeypatch.setattr(signatures, "EXTRACTOR_VERSION", "signature.test-2")
    handler: Any = _handler(bridge, "harvest-signatures")
    handler.model = _BetterReader()
    opened = len(mail.opened)
    data = _run(bridge, "harvest-signatures", {"domain": "example.com"}).data
    assert data["scan_note"].startswith(
        "簽名檔擷取規則已更新，這次重新整理全部範圍內的信（收件匣 180 天內）："
    )
    assert data["domains"][0]["mode"] == "extractor"
    # The stored people's mail is read again with the new rules ...
    assert sorted(mail.opened[opened:]) == ["m-lee", "m-wang"]
    # ... and proposed again only because the new reading changes them.
    assert {c["name"]: c["would_change"] for c in data["candidates"]} == {
        "王小明": ["department"],
        "李大華": ["department"],
    }
    assert all(c["existing_person_id"] for c in data["candidates"])
    history = _sync_history(tmp_path)
    assert history[0].action == "advance" and history[1].action == "reset"
    assert "extractor version changed" in history[1].reason
    state = _store(tmp_path).sync_state("mail:Inbox", "example.com")
    assert state is not None and state.extractor_version == "signature.test-2"
    # With the same extractor, nothing is read again.
    handler.model = _BetterReader()
    opened = len(mail.opened)
    _run(bridge, "harvest-signatures", {"domain": "example.com"})
    assert mail.opened[opened:] == []


def test_a_manual_full_re_harvest_resets_and_reads_the_whole_scope(tmp_path: Path) -> None:
    mail = _mail()
    bridge = _bridge(tmp_path, mail=mail, scope=SCOPE, model=SignatureModel())
    _run(bridge, "harvest-signatures", {"domain": "example.com"})
    _run(bridge, "store-candidates", {"candidate_ids": ["s1"]})  # one stored, one declined
    # 「重新整理 範例科技 的簽名檔」: by the company as the person says it.
    data = _run(bridge, "harvest-signatures", {"company": "範例科技", "full": True}).data
    assert data["scan_note"].startswith("重新整理（收件匣 180 天內）：")
    assert data["domains"][0]["mode"] == "reset"
    # The declined one is proposed again; the stored one is skipped as observed.
    assert len(data["candidates"]) == 1 and data["already_seen"] == 1
    history = _sync_history(tmp_path)
    assert [entry.action for entry in history] == ["advance", "reset", "advance"]
    assert history[1].reason == "manual full re-harvest"
    refused = _run(bridge, "harvest-signatures", {"company": "無此公司"})
    assert refused.failure is not None and refused.failure.code == "company_has_no_domain"
    assert "full" in PROCEDURE and "重新整理" in PROCEDURE


# -- the org chart reads new mail first ----------------------------------


class _Down(FakeMail):
    def list(self, folder: str, since: datetime, limit: int) -> list[MailSummary]:
        raise MailError("outlook_missing")


def _chart(bridge: Any, company: str, harvest_first: bool = True) -> Any:
    return _run(bridge, "org-chart", {"company": company, "harvest_first": harvest_first})


def test_the_chart_harvests_first_and_new_people_wait_for_confirmation(tmp_path: Path) -> None:
    mail = _mail()
    bridge = _bridge(tmp_path, mail=mail, scope=SCOPE, model=SignatureModel())
    card = {
        "name": "王小明",
        "company": "範例科技",
        "title": "協理",
        "email": "hm.wang@example.com",
    }
    assert _run(bridge, "add-card", card).status == "succeeded"
    drawn = _chart(bridge, "範例科技")
    assert drawn.status == "succeeded", drawn.failure
    data = drawn.data
    assert data["people"] == 1  # only who is stored
    found = data["harvest"]
    assert found["domains"][0]["domain"] == "example.com"
    # 王小明 is stored and his signature adds nothing: already there, not proposed.
    assert [c["name"] for c in found["candidates"]] == ["李大華"]
    assert [p["name"] for p in found["already_stored_people"]] == ["王小明"]
    assert "NOT on the chart yet" in found["note"] and "harvest_first false" in found["note"]
    # Never stored by the chart.
    assert _run(bridge, "find", {"query": "李大華"}).data["total"] == 0
    stored = _run(bridge, "store-candidates", {"candidate_ids": ["all"]})
    assert stored.status == "succeeded"
    redrawn = _chart(bridge, "範例科技", harvest_first=False).data
    assert redrawn["people"] == 2 and redrawn["harvest"] is None
    # Asked again: only new mail; there is none.
    opened = len(mail.opened)
    again = _chart(bridge, "範例科技").data
    assert mail.opened[opened:] == [] and again["harvest"]["candidates"] == []
    assert again["people"] == 2


def test_the_chart_without_a_known_domain_or_mail_is_still_drawn(tmp_path: Path) -> None:
    bridge = _bridge(tmp_path, mail=_Down(()), scope=SCOPE, model=SignatureModel())
    assert (
        _run(bridge, "add-card", {"name": "甲", "company": "無網域公司", "title": "經理"}).status
        == "succeeded"
    )
    no_domain = _chart(bridge, "無網域公司").data
    assert no_domain["people"] == 1 and no_domain["attach"]
    assert no_domain["harvest"] is None and no_domain["harvest_note"] == NO_DOMAIN_NOTE
    card = {"name": "乙", "company": "範例科技", "email": "b@example.com"}
    assert _run(bridge, "add-card", card).status == "succeeded"
    down = _chart(bridge, "範例科技").data
    assert down["people"] == 1 and down["attach"]
    assert (
        "這次沒有先整理新信" in down["harvest_note"] and "outlook_missing" in down["harvest_note"]
    )
    assert _store(tmp_path).sync_state("mail:Inbox", "example.com") is None  # nothing moved
    no_model = _bridge(tmp_path / "m", mail=_mail(), scope=SCOPE)
    assert _run(no_model, "add-card", card).status == "succeeded"
    assert "model_not_configured" in _chart(no_model, "範例科技").data["harvest_note"]


def test_the_tool_and_the_procedure_ask_for_the_harvest_first() -> None:
    schema = next(schema for name, _, _, schema in TOOLS if name == CHART_TOOL)
    assert schema["properties"]["harvest_first"]["type"] == "boolean"
    harvest_schema = next(s for name, _, _, s in TOOLS if name == "cards__harvest_signatures")
    assert {"company", "full"} <= set(harvest_schema["properties"])
    assert "harvest_first true" in PROCEDURE and "harvest_note" in PROCEDURE


# -- a conversation ---------------------------------------------------------


class _WncReader(SignatureModel):
    def generate(self, request: ModelRequest) -> ModelResponse:
        return _people_with(super().generate(request), company="WNC 啟碁科技")

    def stream(self, request: ModelRequest) -> Iterator[ModelStreamEvent]:
        raise NotImplementedError


def _host(data: str) -> dict[str, Any]:
    found: Any = json.loads(data)["host"]
    assert found["status"] == "succeeded", found
    result: dict[str, Any] = found["data"]
    return result


def test_a_conversation_harvests_on_the_chart_and_reads_only_new_mail_the_second_time(
    web: tuple[AgentWeb, Conversation],  # noqa: F811
) -> None:
    agent_web, model = web
    gateway = agent_web.runtime.agent.gateway
    installed = gateway.bridge.installed.get(CHART_SPEC.identity)
    assert installed is not None
    charter: Any = installed.handler
    mail = FakeMail(
        [
            _message(
                "w1", "Amy <amy.chen@wnc.com.tw>", BODY.format(name="陳艾米", title="經理", ext="1")
            ),
            _message(
                "w2",
                "bob.lin@wnc.com.tw",
                BODY.format(name="林柏", title="工程師", ext="2"),
                days_ago=3,
            ),
        ]
    )
    charter._reader = lambda: mail
    charter._scope = lambda: SCOPE
    charter.model = _WncReader()
    session = agent_web.create_conversation()["conversation"]["session_id"]
    model.then(
        {
            "tools": [
                (
                    "cards__add_card",
                    {
                        "name": "范仁杰",
                        "company": "WNC 啟碁科技",
                        "title": "處長",
                        "email": "rj.fan@wnc.com.tw",
                    },
                )
            ]
        },
        {"text": "已新增 范仁杰。"},
    )
    assert _turn(agent_web, session, "存這張名片")["ok"]

    # 「WNC 組織圖」: the Host reads the new mail first.
    model.then(
        {"tools": [(CHART_TOOL, {"company": "WNC", "harvest_first": True})]},
        {"text": "組織圖如下。信件裡有 2 位新聯絡人：s1 陳艾米 經理、s2 林柏 工程師，要存嗎？"},
    )
    assert _turn(agent_web, session, "WNC 組織圖")["ok"]
    first = _host(model.tool_results()[-1])
    assert first["people"] == 1 and first["company"] == "WNC 啟碁科技"
    assert first["harvest"]["scan_note"].startswith("首次整理（收件匣 180 天內）")
    assert [(c["candidate_id"], c["name"]) for c in first["harvest"]["candidates"]] == [
        ("s1", "陳艾米"),
        ("s2", "林柏"),
    ]
    assert sorted(mail.opened) == ["w1", "w2"]

    # 「都存進去」 → stored, then the chart redrawn without reading mail.
    model.then(
        {
            "tools": [
                ("cards__store_candidates", {"candidate_ids": ["all"]}),
                (CHART_TOOL, {"company": "WNC", "harvest_first": False}),
            ]
        },
        {"text": "已存 2 位，組織圖已更新。"},
    )
    assert _turn(agent_web, session, "都存進去")["ok"]
    stored, redrawn = (_host(text) for text in model.tool_results()[-2:])
    assert sorted(stored["stored"]) == ["s1", "s2"]
    assert redrawn["people"] == 3 and redrawn["harvest"] is None
    assert sorted(mail.opened) == ["w1", "w2"]

    # One new message; the second 「WNC 組織圖」 reads only it.
    _add(mail, "w3", "kai.wu@wnc.com.tw", "吳凱", hours_ago=1)
    model.then(
        {"tools": [(CHART_TOOL, {"company": "WNC", "harvest_first": True})]},
        {"text": "組織圖如下。新信裡有 1 位新聯絡人：s1 吳凱 經理，要存嗎？"},
    )
    assert _turn(agent_web, session, "WNC 組織圖")["ok"]
    second = _host(model.tool_results()[-1])
    assert sorted(mail.opened) == ["w1", "w2", "w3"]
    assert second["harvest"]["domains"][0]["mode"] == "incremental"
    assert second["harvest"]["scan_note"].startswith("從 ")
    assert [c["name"] for c in second["harvest"]["candidates"]] == ["吳凱"]
    assert second["people"] == 3 and second["attach"]
    assert agent_web.approvals(session)["approvals"] == []


def test_a_stored_person_with_nothing_new_is_not_proposed_again(tmp_path: Path) -> None:
    """Live check 2026-10-21 (WNC): a first harvest proposed a person who was
    already stored (same email, would_change empty) as a new candidate."""
    mail = _mail()
    bridge = _bridge(tmp_path, mail=mail, scope=SCOPE, model=SignatureModel())
    card = {
        "name": "王小明",
        "company": "範例科技",
        "title": "協理",
        "email": "hm.wang@example.com",
    }
    added = _run(bridge, "add-card", card).data
    first = _run(bridge, "harvest-signatures", {"domain": "example.com"}).data
    assert [c["name"] for c in first["candidates"]] == ["李大華"]
    assert first["already_stored"] == 1
    (known,) = first["already_stored_people"]
    assert known["person_id"] == added["person_id"] and known["name"] == "王小明"
    assert known["email"] == "hm.wang@example.com"
    assert "1 位已在通訊錄、沒有新資料，不列為候選" in first["scan_note"]
    assert "2 封有簽名檔" in first["scan_note"]
    assert "already_stored_people are ALREADY in the contacts" in first["note"]
    # Storing "all" stores only the new person; the known one is untouched.
    assert _run(bridge, "store-candidates", {"candidate_ids": ["all"]}).status == "succeeded"
    assert _run(bridge, "find", {"query": "李大華"}).data["total"] == 1
    assert _run(bridge, "find", {"query": "王小明"}).data["total"] == 1
    assert "already_stored_people" in PROCEDURE


def test_a_stored_person_whose_signature_changes_something_is_still_proposed(
    tmp_path: Path,
) -> None:
    mail = _mail()
    bridge = _bridge(tmp_path, mail=mail, scope=SCOPE, model=SignatureModel())
    card = {
        "name": "王小明",
        "company": "範例科技",
        "title": "經理",
        "email": "hm.wang@example.com",
    }
    added = _run(bridge, "add-card", card).data
    data = _run(bridge, "harvest-signatures", {"domain": "example.com"}).data
    proposed = {c["name"]: c for c in data["candidates"]}
    assert proposed["王小明"]["existing_person_id"] == added["person_id"]
    assert "title" in proposed["王小明"]["would_change"]
    assert data["already_stored"] == 0 and data["already_stored_people"] == []
    assert "已在通訊錄" not in data["scan_note"]
