"""Telegram's one status message for a running turn (owner 2026-10-19).
Fakes only: no Bot API, no model, no network."""

from __future__ import annotations

from pathlib import Path

from test_telegram_ingress import OWNER, STATUS_MARK, FakeTransport, ingress, poll, update
from test_telegram_turn_limits import Scripted

from models.contracts import ModelResponse, ModelToolCall


def _text(text: str) -> ModelResponse:
    from common.execution import TraceIdentifiers

    return ModelResponse(
        trace=TraceIdentifiers(trace_id="x", request_id="x", span_id="x"),
        model_alias="routing",
        text=text,
    )


def _status_sends(transport: FakeTransport) -> list[str]:
    return [
        payload["text"]
        for url, payload in transport.calls
        if url.endswith("/sendMessage") and payload["text"].startswith(STATUS_MARK)
    ]


def test_a_long_turn_edits_one_status_message_a_few_times(tmp_path: Path) -> None:
    """Twenty tool events in a burst become one status message and a bounded
    number of edits, all of the same message: never a stream of messages."""

    def script(n: int) -> ModelResponse | list[ModelToolCall]:
        if n > 10:
            return _text("All ten checks ran.")
        return [
            ModelToolCall(call_id=f"a{n}", name="shipment__run", arguments={}),
            ModelToolCall(call_id=f"b{n}", name="admin__probe", arguments={"n": n}),
        ]

    transport = FakeTransport([[update(1, OWNER, "run the checks ten times")]])
    item, agent, _ = ingress(tmp_path, transport)
    agent.gateway.router.model = Scripted(script)
    delivery = poll(item).deliveries[0]
    assert delivery.disposition == "answered" and delivery.replied
    assert transport.sent() == ["All ten checks ran."]
    assert len(_status_sends(transport)) == 1
    edits = [payload for url, payload in transport.calls if url.endswith("/editMessageText")]
    assert edits and {payload["message_id"] for payload in edits} == {1}
    # The first edit is immediate; later ones wait for the refresh period, and
    # the burst took far less than one: the first edit and the final one.
    assert len(edits) <= 3, [payload["text"] for payload in edits]
    statuses = transport.statuses()
    assert any("工具 " in text and "/150" in text and "/ 30:00" in text for text in statuses)
    assert statuses[-1].startswith("✅ Done after")
    assert all("run the checks" not in text for text in statuses)
