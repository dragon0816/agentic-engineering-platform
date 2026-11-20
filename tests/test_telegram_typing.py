"""Telegram's own activity indicator while AEP handles a message (owner
2026-11-20: 「正在輸入…」 under the bot's name, so a running request is plain).

`sendChatAction` starts as soon as a mapped sender's update is accepted, is
repeated while the turn runs, and stops before the reply, after a failure too;
a failing call never changes the reply. Agent bots get it as the conversation
bot does; a collection bot only when an item takes noticeable time; a stranger
never. Presentation only. Over the fake transport of the ingress tests.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

from test_telegram_agent_bots import two_bots
from test_telegram_collect import Collecting, collector
from test_telegram_ingress import (
    OWNER,
    STATUS_MARK,
    STRANGER,
    FakeReply,
    FakeTransport,
    ingress,
    poll,
    update,
)

from channels.telegram import TelegramIngress
from channels.telegram_collect import attach
from host_runtime.features import FeatureSet, TelegramAnswer, TelegramItem
from models.contracts import ModelRequest, ModelResponse, ModelStreamEvent

#: Long enough for several indicator repeats at the test interval.
SLOW_S = 0.45
INTERVAL_S = 0.1


class Slow:
    """A model that takes `SLOW_S` to answer."""

    def __init__(self, text: str = "Answer from the model") -> None:
        self.text = text

    def generate(self, request: ModelRequest) -> ModelResponse:
        time.sleep(SLOW_S)
        return ModelResponse(trace=request.trace, model_alias=request.model_alias, text=self.text)

    def stream(self, request: ModelRequest) -> Iterator[ModelStreamEvent]:
        raise NotImplementedError


def methods(transport: FakeTransport) -> list[str]:
    return [url.rsplit("/", 1)[-1] for url, _ in transport.calls]


def actions(transport: FakeTransport) -> list[dict[str, Any]]:
    return [payload for url, payload in transport.calls if url.endswith("/sendChatAction")]


def reply_index(transport: FakeTransport, text: str) -> int:
    """Where the reply (not a status message) was sent among the calls."""
    return next(
        index
        for index, (url, payload) in enumerate(transport.calls)
        if url.endswith("/sendMessage")
        and not payload["text"].startswith(STATUS_MARK)
        and text in payload["text"]
    )


def slow_ingress(tmp_path: Path, transport: FakeTransport) -> TelegramIngress:
    item, agent, _ = ingress(tmp_path, transport)
    agent.gateway.router.model = Slow()
    item.chat_action_interval_s = INTERVAL_S
    return item


def assert_no_leak(transport: FakeTransport) -> None:
    """Nothing keeps sending once the poll returned."""
    before = len(actions(transport))
    time.sleep(INTERVAL_S * 3)
    assert len(actions(transport)) == before


def test_typing_starts_at_once_repeats_and_stops_before_the_reply(tmp_path: Path) -> None:
    transport = FakeTransport([[update(1, OWNER, "hello")]])
    item = slow_ingress(tmp_path, transport)
    delivery = poll(item).deliveries[0]
    assert delivery.disposition == "answered" and delivery.replied
    sent = actions(transport)
    assert len(sent) >= 2  # repeated while the slow turn ran
    assert all(payload == {"chat_id": OWNER, "action": "typing"} for payload in sent)
    called = methods(transport)
    # Started as soon as the update was accepted: the first call after getUpdates
    # or right behind the "working on it" message, before the model answered.
    assert called.index("sendChatAction") <= 2
    # None after the reply: Telegram would show "typing…" again for 5 s.
    last_action = max(i for i, name in enumerate(called) if name == "sendChatAction")
    assert last_action < reply_index(transport, "Answer from the model")
    assert transport.sent() == ["Answer from the model"]
    assert_no_leak(transport)


def test_typing_stops_after_a_failed_turn(tmp_path: Path) -> None:
    transport = FakeTransport([[update(1, OWNER, "hello")]])
    item = slow_ingress(tmp_path, transport)

    async def broken(_update: Any) -> Any:
        await asyncio.sleep(SLOW_S)
        raise RuntimeError("boom")

    item._deliver = broken  # type: ignore[method-assign,assignment]
    delivery = poll(item).deliveries[0]
    assert delivery.disposition == "failed" and delivery.replied
    assert len(actions(transport)) >= 2
    called = methods(transport)
    last_action = max(i for i, name in enumerate(called) if name == "sendChatAction")
    assert last_action < reply_index(transport, "could not be handled")
    assert_no_leak(transport)


class RefusingActions(FakeTransport):
    """Every `sendChatAction` raises (or, with `status`, is refused)."""

    def __init__(self, *args: Any, status: int | None = None, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.action_status = status

    def send(
        self, url: str, body: bytes, headers: Mapping[str, str], timeout_s: float
    ) -> FakeReply:
        if url.endswith("/sendChatAction"):
            super().send(url, body, headers, timeout_s)
            if self.action_status is None:
                raise TimeoutError("the Bot API did not answer")
            return FakeReply(self.action_status, {"ok": False, "description": "Bad Request"})
        return super().send(url, body, headers, timeout_s)


def test_a_failing_chat_action_changes_nothing_about_the_reply(tmp_path: Path) -> None:
    for number, status in enumerate((None, 400)):
        transport = RefusingActions([[update(1, OWNER, "hello")]], status=status)
        item = slow_ingress(tmp_path / f"run-{number}", transport)
        delivery = poll(item).deliveries[0]
        assert delivery.disposition == "answered" and delivery.replied
        assert delivery.reply == "Answer from the model"
        assert transport.sent() == ["Answer from the model"]
        assert len(actions(transport)) >= 2  # kept trying, never retried at once


def test_a_stranger_gets_no_indicator(tmp_path: Path) -> None:
    transport = FakeTransport([[update(1, STRANGER, "hello")]])
    item = slow_ingress(tmp_path, transport)
    assert poll(item).deliveries[0].disposition == "unmapped_sender"
    assert methods(transport) == ["getUpdates"]


def test_an_agent_bot_shows_typing_through_its_own_bot(tmp_path: Path) -> None:
    main, own, _model = two_bots(tmp_path, [], [[update(1, OWNER, "hello agent")]])
    own.agent.gateway.router.model = Slow("Answer from the agent")
    own.chat_action_interval_s = INTERVAL_S
    delivery = poll(own).deliveries[0]
    assert delivery.disposition == "answered" and delivery.replied
    transport = own._transport
    assert isinstance(transport, FakeTransport)
    assert len(actions(transport)) >= 2
    called = methods(transport)
    last_action = max(i for i, name in enumerate(called) if name == "sendChatAction")
    assert last_action < reply_index(transport, "Answer from the agent")
    main_transport = main._transport
    assert isinstance(main_transport, FakeTransport)
    assert actions(main_transport) == []
    assert_no_leak(transport)


class SlowCollecting(Collecting):
    def telegram_item(self, item: TelegramItem, host: Any) -> TelegramAnswer | None:
        time.sleep(SLOW_S)
        return super().telegram_item(item, host)


def test_a_collection_bot_shows_typing_only_when_an_item_takes_long(tmp_path: Path) -> None:
    quick = collector(tmp_path / "quick", [[update(1, OWNER, "展場筆記")]])
    attach([quick], FeatureSet([Collecting()]), None)
    quick.chat_action_delay_s = INTERVAL_S * 2
    assert asyncio.run(quick.poll_once()) == [(1, "answered")]
    quick_wire = quick._transport
    assert isinstance(quick_wire, FakeTransport)
    assert actions(quick_wire) == []  # the immediate 「已收進」 needs none

    slow = collector(tmp_path / "slow", [[update(1, OWNER, "展場筆記")]])
    attach([slow], FeatureSet([SlowCollecting()]), None)
    slow.chat_action_delay_s = INTERVAL_S
    slow.chat_action_interval_s = INTERVAL_S
    assert asyncio.run(slow.poll_once()) == [(1, "answered")]
    slow_wire = slow._transport
    assert isinstance(slow_wire, FakeTransport)
    assert actions(slow_wire) and actions(slow_wire)[0] == {"chat_id": OWNER, "action": "typing"}
    called = methods(slow_wire)
    assert called[-1] == "sendMessage"
    assert max(i for i, name in enumerate(called) if name == "sendChatAction") < len(called) - 1
    assert slow_wire.sent() == ["已收進 aidc（text）"]
