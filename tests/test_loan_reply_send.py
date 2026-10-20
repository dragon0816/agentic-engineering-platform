"""Sending a loan reply: one card, one person's press, one mail (owner 2026-10-20).

The consumer Workflow only drafts. With "a send card per draft" ticked, each
saved draft gets its own `ls-` card; a mail leaves only when a person presses
寄出 on that card in Agent Web. These tests drive the card store, Agent Web's
card route and form-run record, and Telegram's rendering, all with fakes:
`RecordingDraftSender` stands in for Outlook's send.
"""

from __future__ import annotations

import inspect
import time
import types
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from loan_fakes import FakeLoanHost, notice
from test_loan_reply_workflows import Host
from test_telegram_ingress import OWNER, FakeTransport, ingress, poll
from test_telegram_workflow_flow import _tap

from capabilities.loan_reply import process
from capabilities.loan_reply.contracts import SendOffer
from capabilities.loan_reply.manifest import (
    REPLY_WORKFLOW,
    SCAN_WORKFLOW,
    SEND_SPEC,
    reply_workflow,
)
from host_runtime.contracts import WorkflowLaunchRequest
from host_runtime.loan_reply_cards import LoanReplyCards
from host_runtime.web import AgentWeb
from integrations.outlook_send import RecordingDraftSender, draft_fingerprint


@pytest.fixture(autouse=True)
def _no_waiting(monkeypatch: pytest.MonkeyPatch) -> None:
    clock = types.SimpleNamespace(sleep=lambda *_a: None, monotonic=time.monotonic)
    monkeypatch.setattr(process, "time", clock)


def _offer(borrow: str, entry: str) -> SendOffer:
    return SendOffer(
        borrow_no=borrow,
        entry_id=entry,
        to=("customer@example.com",),
        subject=f"RE: {borrow}",
        body="您好，\n\n已出貨。",
        attachments=("shot.png",),
    )


def _cards(tmp_path: Path, *offers: SendOffer, now: Any = None) -> tuple[LoanReplyCards, Any]:
    fingerprints = {
        item.entry_id: draft_fingerprint(item.to, item.cc, item.subject, item.attachments)
        for item in offers
    }
    sender = RecordingDraftSender(fingerprints)
    cards = LoanReplyCards(tmp_path, sender=lambda: sender, clock=now)
    return cards, sender


def test_each_draft_has_its_own_card_and_only_a_press_sends_it(tmp_path: Path) -> None:
    cards, sender = _cards(tmp_path, _offer("DR1", "E1"), _offer("DR2", "E2"))
    first, second = cards.offer([_offer("DR1", "E1"), _offer("DR2", "E2")])
    assert first.startswith("ls-") and second.startswith("ls-") and first != second
    assert sender.sent == []  # offering sends nothing
    shown = cards.card(first)
    assert (
        shown is not None
        and shown.web_only
        and [b.action for b in shown.buttons]
        == [
            "send",
            "keep_draft",
        ]
    )
    assert "customer@example.com" in shown.preview and "已出貨" in shown.preview
    decided = cards.decide(first, "send")
    assert decided["ok"] is True and decided["code"] == "sent"
    assert sender.sent == ["E1"]  # one press, one mail; the other is untouched
    still = cards.card(second)
    assert still is not None and still.status == "pending"
    # A second press on the same card does nothing.
    again = cards.decide(first, "send")
    assert again["ok"] is False and again["code"] == "mail_sent" and sender.sent == ["E1"]
    kept = cards.decide(second, "keep_draft")
    assert kept["code"] == "kept" and sender.sent == ["E1"]


def test_there_is_no_send_all_and_no_other_action(tmp_path: Path) -> None:
    cards, sender = _cards(tmp_path, _offer("DR1", "E1"))
    (card_id,) = cards.offer([_offer("DR1", "E1")])
    for action in ("send_all", "allow_all", "approve", "cancel"):
        assert cards.decide(card_id, action)["code"] == "card_action_unknown"
    assert sender.sent == []
    assert not any("all" in name for name in dir(LoanReplyCards) if not name.startswith("_"))


def test_telegram_is_shown_the_card_but_cannot_press_send(tmp_path: Path) -> None:
    cards, sender = _cards(tmp_path, _offer("DR1", "E1"))
    (card_id,) = cards.offer([_offer("DR1", "E1")])
    refused = cards.decide(card_id, "send", channel="telegram")
    assert refused["code"] == "web_only" and sender.sent == []
    card = cards.card(card_id)
    assert card is not None and card.status == "pending"


def test_a_draft_edited_in_outlook_is_not_sent(tmp_path: Path) -> None:
    cards, sender = _cards(tmp_path, _offer("DR1", "E1"))
    (card_id,) = cards.offer([_offer("DR1", "E1")])
    sender.fingerprints["E1"] = "someone-changed-it"
    decided = cards.decide(card_id, "send")
    assert decided["code"] == "failed" and "已在 Outlook 被修改" in decided["message"]
    assert sender.sent == []


def test_an_unanswered_card_expires_and_nothing_is_sent(tmp_path: Path) -> None:
    moment = [datetime(2026, 10, 20, 9, tzinfo=UTC)]
    cards, sender = _cards(tmp_path, _offer("DR1", "E1"), now=lambda: moment[0])
    (card_id,) = cards.offer([_offer("DR1", "E1")])
    moment[0] += timedelta(hours=25)
    assert cards.open_cards() == []
    assert cards.decide(card_id, "send")["code"] == "mail_expired"
    assert sender.sent == []


def test_without_outlook_a_press_sends_nothing(tmp_path: Path) -> None:
    cards = LoanReplyCards(tmp_path)
    (card_id,) = cards.offer([_offer("DR1", "E1")])
    decided = cards.decide(card_id, "send")
    assert decided["code"] == "failed"


def test_the_workflow_side_and_the_web_side_share_the_cards(tmp_path: Path) -> None:
    """The offering step and Agent Web's route are separate objects on one file."""
    offering = LoanReplyCards(tmp_path)
    deciding, sender = _cards(tmp_path, _offer("DR1", "E1"))
    (card_id,) = offering.offer([_offer("DR1", "E1")])
    assert [card.card_id for card in deciding.open_cards()] == [card_id]
    deciding.decide(card_id, "send")
    shown = offering.card(card_id)
    assert shown is not None and shown.status == "sent" and sender.sent == ["E1"]


def test_the_send_is_reachable_only_from_a_cards_decision() -> None:
    from capabilities.loan_reply import handlers, manifest

    assert SEND_SPEC.side_effect == "external_side_effect"
    for module in (handlers, manifest, process):
        source = inspect.getsource(module)
        assert "outlook_send" not in source and ".send(" not in source
    decide = inspect.getsource(LoanReplyCards.decide)
    assert decide.count("self.sender().send(") == 1
    assert 'channel == "telegram"' in decide


def test_the_send_capability_is_never_installed(tmp_path: Path) -> None:
    host = Host(tmp_path, FakeLoanHost())
    try:
        installed = host.runtime.agent.gateway.bridge.installed
        assert installed.get(SEND_SPEC.identity) is None
        names = {spec.name for spec in installed.discover()}
        assert {"loan.scan-mail", "loan.draft-replies", "loan.offer-send"} <= names
        assert "loan.send-reply" not in names
    finally:
        host.close()


# -- Agent Web --------------------------------------------------------------------


def _launch(web: AgentWeb, workflow: Any, arguments: dict[str, Any], session: str) -> Any:
    return web.launch_workflow(
        WorkflowLaunchRequest(
            workflow=workflow,
            arguments=arguments,
            idempotency_key=f"web-{time.time_ns()}",
            session_id=session,
        )
    )


def test_agent_web_shows_the_hand_off_form_and_one_card_per_draft(tmp_path: Path) -> None:
    fake = FakeLoanHost(messages=[notice("DR26270135"), notice("DR26270136")])
    host = Host(tmp_path, fake)
    try:
        web = AgentWeb(host.runtime)
        sender = RecordingDraftSender()
        web.loan_cards.sender = lambda: sender
        session = web.create_conversation()["conversation"]["session_id"]
        scanned = _launch(web, SCAN_WORKFLOW, {}, session)
        assert scanned["ok"] is True and "排入佇列 2 筆" in scanned["answer"]
        form = scanned["message"]["workflow_form"]
        assert form["workflow"]["name"] == "rs-loan-queue-reply"
        assert form["origin"] == "follow_up" and form["missing_settings"] == []
        assert "不會自動執行" in form["message"]
        assert fake.replies == []  # the hand-off ran nothing

        replied = _launch(web, REPLY_WORKFLOW, {"max_items": 2, "offer_send": True}, session)
        cards = replied["message"]["action_cards"]
        assert len(cards) == 2 and all(card["card_id"].startswith("ls-") for card in cards)
        assert {card["status"] for card in cards} == {"pending"}
        listed = [card["card_id"] for card in web.cards()["cards"]]
        assert {card["card_id"] for card in cards} <= set(listed)
        # The person sends one: one mail. Nothing else is sent.
        sender.fingerprints = {
            "reply-1": web.loan_cards.store.get(cards[0]["card_id"]).fingerprint,  # type: ignore[union-attr]
            "reply-2": web.loan_cards.store.get(cards[1]["card_id"]).fingerprint,  # type: ignore[union-attr]
        }
        first = web.decide_card(cards[0]["card_id"], "send")
        assert first["code"] == "sent" and sender.sent == ["reply-1"]
        refused = web.decide_card(cards[1]["card_id"], "send", channel="telegram")
        assert refused["code"] == "web_only" and sender.sent == ["reply-1"]
        # The conversation shows the card as it is now.
        record = web.conversations(session)["selected"]
        answer = record["messages"][-1]
        assert [card["status"] for card in answer["action_cards"]] == ["sent", "pending"]
    finally:
        host.close()


# -- Telegram -------------------------------------------------------------------


class _Cards:
    def __init__(self, cards: LoanReplyCards) -> None:
        self._cards = cards

    def card(self, card_id: str) -> dict[str, Any] | None:
        found = self._cards.card(card_id)
        return None if found is None else found.model_dump(mode="json")


def test_telegram_summarises_the_drafts_draws_the_cards_and_offers_the_reply(
    tmp_path: Path,
) -> None:
    fake = FakeLoanHost(messages=[notice("DR26270135")])
    host = Host(tmp_path / "host", fake)
    try:
        scanned = host.run(SCAN_WORKFLOW, {}, "scan")
        replied = host.run(REPLY_WORKFLOW, {"offer_send": True}, "reply")
        transport = FakeTransport([])
        item, _agent, _ = ingress(tmp_path / "tg", transport)
        item.cards = _Cards(LoanReplyCards(host.layout.workspace_root))

        texts, buttons = item._run_extras(scanned)
        assert "排入佇列 1 筆：DR26270135" in texts[0]
        assert buttons == (
            (("處理佇列中的 1 筆（建立回信草稿）", "/run engineering/rs-loan-queue-reply"),),
        )

        texts, buttons = item._run_extras(replied)
        assert "建立了 1 封草稿" in texts[0] and "可出貨回信" in texts[0]
        assert "寄出借用單 DR26270135 的回信？" in texts[1]
        assert "Open in Agent Web" in texts[1]  # pressed in Agent Web only
        assert buttons == ()  # no Send button in Telegram
    finally:
        host.close()


def test_the_hand_off_button_opens_the_reply_question_flow(tmp_path: Path) -> None:
    transport = FakeTransport([[_tap(1, OWNER, "/run engineering/rs-loan-queue-reply")]])
    item, agent, _ = ingress(tmp_path, transport)
    agent.gateway.engine.workflows.register(reply_workflow())
    agent.gateway.engine.settings_provider = lambda _manifest: {}
    delivery = poll(item).deliveries[0]
    assert delivery.disposition == "answered"
    assert "只試跑" in (delivery.reply or "")
    assert item._flows  # waiting for the person's answers; nothing ran
