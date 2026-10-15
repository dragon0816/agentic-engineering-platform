"""Conversation feedback, kept until the Shared Platform has it (owner 2026-10-08).

A rating in Agent Web is written to the conversation and, in the same local
transaction, to the `feedback_outbox` table: the rating, its reason, the
question and the answer, the tools used. A background loop sends what is
queued to the platform's `feedback` operation; a record leaves the outbox only
when the platform acknowledges it. Without a platform, or while it cannot be
reached, records wait and go once it answers. Rating the same answer again
replaces its queued record.

Only ratings made from this release on are queued (owner decision): earlier
ratings were given without knowing they would leave the machine.
"""

from __future__ import annotations

import asyncio
import hashlib
import threading
from collections.abc import Callable
from typing import Any

from common.sync import MAX_FEEDBACK_BATCH, MAX_FEEDBACK_TEXT, FeedbackRecord
from host_runtime.conversations import ConversationRecord

SYNC_INTERVAL_SECONDS = 60.0


def feedback_id(bridge_id: str, session_id: str, message_id: str) -> str:
    """One id per rated answer, the same on every rating of it."""
    joined = f"{bridge_id}\n{session_id}\n{message_id}".encode()
    return "fb-" + hashlib.sha256(joined).hexdigest()[:32]


def feedback_record(bridge_id: str, record: ConversationRecord, message_id: str) -> FeedbackRecord:
    """The rated answer with the question it answered."""
    messages = record.messages
    index = next(i for i, item in enumerate(messages) if item.message_id == message_id)
    answer = messages[index]
    if answer.feedback is None:
        raise ValueError("the answer has no feedback")
    question = next((item for item in reversed(messages[:index]) if item.role == "user"), None)
    return FeedbackRecord(
        feedback_id=feedback_id(bridge_id, record.session_id, message_id),
        bridge_id=bridge_id,
        actor=record.actor,
        session_id=record.session_id,
        message_id=message_id,
        rating=answer.feedback.rating,
        note=answer.feedback.note,
        question="" if question is None else question.text[:MAX_FEEDBACK_TEXT],
        answer=answer.text[:MAX_FEEDBACK_TEXT],
        tools=None if answer.tool_summary is None else answer.tool_summary[:4000],
        backend=record.backend,
        data_classification=record.data_classification,
        trace_id=None if answer.trace is None else answer.trace.trace_id,
        answered_at=answer.created_at,
        rated_at=answer.feedback.updated_at,
    )


class FeedbackSync:
    """Sends the outbox to the platform: every interval, and soon after a rating."""

    def __init__(
        self,
        state: Any,
        platform: Callable[[], Any | None],
        *,
        interval_seconds: float = SYNC_INTERVAL_SECONDS,
    ) -> None:
        self.state = state
        self._platform = platform
        self.interval_seconds = interval_seconds
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.last_outcome = "not run"

    def flush(self) -> int:
        """Send what is queued; returns how many the platform acknowledged."""
        platform = self._platform()
        if platform is None:
            self.last_outcome = "no platform configured"
            return 0
        sent = 0
        while True:
            queued = self.state.queued_feedback(MAX_FEEDBACK_BATCH)
            if not queued:
                break
            outcome = asyncio.run(platform.feedback(tuple(queued)))
            if outcome.status != "answered":
                code = outcome.failure.code if outcome.failure is not None else outcome.status
                self.state.feedback_attempted([item.feedback_id for item in queued], code)
                self.last_outcome = f"waiting: {code}"
                return sent
            self.state.feedback_delivered(queued, outcome.accepted)
            sent += len(outcome.accepted)
            if len(outcome.accepted) < len(queued):
                break  # what was not acknowledged waits for the next round
        self.last_outcome = f"sent {sent}"
        return sent

    def soon(self) -> None:
        self._wake.set()

    def start(self) -> None:
        if self._thread is not None:
            return

        def loop() -> None:
            while not self._stop.is_set():
                try:
                    self.flush()
                except Exception as error:  # noqa: BLE001 - the loop must survive
                    self.last_outcome = f"error: {type(error).__name__}"
                self._wake.wait(self.interval_seconds)
                self._wake.clear()

        self._thread = threading.Thread(target=loop, name="feedback-sync", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 2.0) -> None:
        self._stop.set()
        self._wake.set()
        if self._thread is not None:
            self._thread.join(timeout)
            self._thread = None
