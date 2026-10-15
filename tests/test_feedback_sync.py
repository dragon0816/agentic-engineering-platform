"""Conversation feedback reaches the Shared Platform (owner 2026-10-08).

A rating is queued with its question and answer in the same transaction that
keeps it, waits while the platform cannot be reached, and leaves the outbox
only when the platform acknowledges it.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from test_platform_transport import BRIDGE, Platform, client, platform, server  # noqa: F401

from common.execution import TraceIdentifiers
from common.sync import FeedbackRecord, FeedbackRequest
from control_plane.feedback import FeedbackStore
from control_plane.http import ControlPlaneServer
from control_plane.service import ServiceError
from host_runtime.conversations import ConversationMessage, ConversationRecord, MessageFeedback
from host_runtime.feedback_sync import FeedbackSync, feedback_id
from host_runtime.state import SqliteLocalState
from host_runtime.sync import FeedbackOutcome

NOW = datetime(2026, 10, 8, 9, 0, tzinfo=UTC)


def conversation(state: SqliteLocalState) -> ConversationRecord:
    record = ConversationRecord(
        session_id="session-1",
        actor="engineer",
        title="stock",
        created_at=NOW,
        updated_at=NOW,
        messages=(
            ConversationMessage(
                message_id="m1",
                role="user",
                text="2330 最新股價？",
                created_at=NOW,
                status="submitted",
            ),
            ConversationMessage(
                message_id="m2",
                role="assistant",
                text="2,565 元",
                created_at=NOW,
                status="answered",
                tool_summary="browser__operate yahoo",
                trace=TraceIdentifiers(trace_id="t1", request_id="r1", span_id="s1"),
            ),
        ),
    )
    state.create_conversation(record)
    return record


def rate(state: SqliteLocalState, rating: str, minutes: int = 0, note: str | None = None) -> None:
    state.set_message_feedback(
        "session-1",
        "engineer",
        "m2",
        MessageFeedback(rating=rating, note=note, updated_at=NOW + timedelta(minutes=minutes)),  # type: ignore[arg-type]
        queue=True,
    )


def test_a_rating_is_queued_with_its_question_and_answer_and_replaced_when_rated_again(
    tmp_path: Path,
) -> None:
    state = SqliteLocalState(tmp_path / "state.sqlite", bridge_id=BRIDGE)
    conversation(state)
    rate(state, "down", note="少了日期")
    (queued,) = state.queued_feedback(10)
    assert (queued.rating, queued.note, queued.question, queued.answer) == (
        "down",
        "少了日期",
        "2330 最新股價？",
        "2,565 元",
    )
    assert queued.tools == "browser__operate yahoo" and queued.trace_id == "t1"
    assert queued.feedback_id == feedback_id(BRIDGE, "session-1", "m2")
    rate(state, "up", minutes=1)
    assert [item.rating for item in state.queued_feedback(10)] == ["up"]
    # A rating without queue (older code paths) is kept but not uploaded.
    state.set_message_feedback(
        "session-1", "engineer", "m2", MessageFeedback(rating="neutral", updated_at=NOW)
    )
    assert [item.rating for item in state.queued_feedback(10)] == ["up"]
    state.close()


class FakePlatform:
    def __init__(self, outcomes: list[FeedbackOutcome]) -> None:
        self.outcomes = outcomes
        self.sent: list[tuple[FeedbackRecord, ...]] = []

    async def feedback(self, records: tuple[FeedbackRecord, ...]) -> FeedbackOutcome:
        self.sent.append(records)
        outcome = self.outcomes.pop(0)
        if outcome.status == "answered" and not outcome.accepted:
            return outcome.model_copy(update={"accepted": tuple(r.feedback_id for r in records)})
        return outcome


def test_feedback_waits_while_the_platform_is_away_and_goes_once_it_answers(
    tmp_path: Path,
) -> None:
    state = SqliteLocalState(tmp_path / "state.sqlite", bridge_id=BRIDGE)
    conversation(state)
    rate(state, "down")
    assert FeedbackSync(state, lambda: None).flush() == 0  # no platform configured
    away = FakePlatform([FeedbackOutcome(status="unreachable")])
    sync = FeedbackSync(state, lambda: away)
    assert sync.flush() == 0 and sync.last_outcome.startswith("waiting")
    assert state.feedback_backlog() == 1
    back = FakePlatform([FeedbackOutcome(status="answered")])
    assert FeedbackSync(state, lambda: back).flush() == 1
    assert state.feedback_backlog() == 0 and back.sent[0][0].rating == "down"
    state.close()


def test_the_loop_sends_soon_after_a_rating(tmp_path: Path) -> None:
    state = SqliteLocalState(tmp_path / "state.sqlite", bridge_id=BRIDGE)
    conversation(state)
    up = FakePlatform([FeedbackOutcome(status="answered") for _ in range(5)])
    sync = FeedbackSync(state, lambda: up, interval_seconds=30)
    sync.start()
    try:
        rate(state, "up")
        sync.soon()
        for _ in range(100):
            if state.feedback_backlog() == 0 and up.sent:
                break
            asyncio.run(asyncio.sleep(0.05))
        assert state.feedback_backlog() == 0
    finally:
        sync.stop()
        state.close()


def record(rating: str = "up", minutes: int = 0, bridge: str = BRIDGE) -> FeedbackRecord:
    return FeedbackRecord(
        feedback_id=feedback_id(bridge, "session-1", "m2"),
        bridge_id=bridge,
        actor="engineer",
        session_id="session-1",
        message_id="m2",
        rating=rating,  # type: ignore[arg-type]
        question="q",
        answer="a",
        answered_at=NOW,
        rated_at=NOW + timedelta(minutes=minutes),
    )


@pytest.mark.parametrize("durable", [False, True])
def test_the_platform_keeps_the_newest_rating_of_each_answer(
    tmp_path: Path,
    durable: bool,
) -> None:
    store = FeedbackStore(tmp_path / "registry.sqlite" if durable else None)
    store.record([record("down", 5)], NOW)
    store.record([record("up", 1)], NOW)  # a late copy of an older rating
    assert [item.rating for item in store.list()] == ["down"]
    store.record([record("neutral", 9)], NOW)
    assert [item.rating for item in store.list()] == ["neutral"]
    store.close()


def test_a_bridge_uploads_only_its_own_feedback_over_the_wire(
    platform: Platform,
    server: ControlPlaneServer,  # noqa: F811
) -> None:
    base = f"http://127.0.0.1:{server.server_address[1]}"
    bridge = client(platform, base)
    outcome: Any = asyncio.run(bridge.feedback((record("down"),)))
    assert outcome.status == "answered" and outcome.accepted == (record().feedback_id,)
    assert [item.rating for item in platform.service.feedback_store.list()] == ["down"]
    token = platform.company_token
    with pytest.raises(ServiceError) as mismatch:
        platform.service.feedback(
            token.grant.token_id,
            token.secret,
            FeedbackRequest(records=(record(bridge="bridge-shared"),)),
        )
    assert mismatch.value.code == "device_mismatch"
