"""The owner's Telegram conversations, stored for reading in Agent Web
(docs/phases/TELEGRAM_HISTORY.md).

A copy for the person: the model keeps receiving the ingress's in-memory
history and is never given these records. A record is one local day of one
chat, or less: a full record, a new day and `/new` each start another, so
nothing is dropped. The session id holds an opaque id of the chat, never the
chat's own id.
"""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from common.base import Symbol
from common.distribution import LocalStateError
from host_runtime.conversations import (
    MAX_STORED_MESSAGES,
    TELEGRAM_SESSION_PREFIX,
    ConversationMessage,
    ConversationRecord,
)
from host_runtime.state import SqliteLocalState

MAX_TITLE_CHARS = 72


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class StoredTurn:
    """One question and its answer: the page reads pairs."""

    said: str
    answer: str
    status: Literal["answered", "failed"] = "answered"
    tool_summary: str | None = None
    files: Sequence[dict[str, str]] = ()


class TelegramHistory:
    """One person's stored chats: `actor` is the only one kept here."""

    def __init__(
        self,
        state: SqliteLocalState,
        actor: Symbol,
        *,
        clock: Callable[[], datetime] = _now,
        agent: str | None = None,
    ) -> None:
        self.state = state
        self.actor = actor
        # The persistent sub-agent whose bot these chats came through (owner
        # consent 2026-11-20); None: the main agent's conversation bot.
        self.agent = agent
        self._clock = clock
        self._key: str | None = None
        # Chats whose next turn starts a record, after `/new`. Memory only: a
        # restart before that turn joins it to the day's record, losing nothing.
        self._fresh: set[tuple[int, int]] = set()

    def _prefix(self, chat_id: int, sender_id: int) -> str:
        if self._key is None:
            self._key = self.state.host_key("telegram_history")
        # The main bot's records keep their ids; an agent bot's chats are apart.
        chat = (
            f"{chat_id}:{sender_id}"
            if self.agent is None
            else f"{self.agent}:{chat_id}:{sender_id}"
        )
        digest = hashlib.sha256(f"{self._key}:{chat}".encode()).hexdigest()
        return f"{TELEGRAM_SESSION_PREFIX}{digest[:16]}-"

    def start_new(self, chat_id: int, sender_id: int) -> None:
        self._fresh.add((chat_id, sender_id))

    def add_turn(self, chat_id: int, sender_id: int, turn: StoredTurn) -> None:
        key = (chat_id, sender_id)
        prefix = self._prefix(chat_id, sender_id)
        now = self._clock()
        day = now.astimezone().strftime("%Y%m%d")
        latest = None if key in self._fresh else self.state.latest_conversation(self.actor, prefix)
        if (
            latest is not None
            and latest.session_id.startswith(f"{prefix}{day}-")
            and len(latest.messages) + 2 <= MAX_STORED_MESSAGES
        ):
            try:
                self.state.save_conversation(_with_turn(latest, now, turn))
                return
            except LocalStateError as error:
                if error.code != "conversation_unknown":
                    raise
                # Deleted in Agent Web a moment ago: this turn starts anew.
        said = turn.said
        empty = ConversationRecord(
            session_id=f"{prefix}{day}-{uuid.uuid4().hex[:8]}",
            actor=self.actor,
            title=said[:MAX_TITLE_CHARS] + ("…" if len(said) > MAX_TITLE_CHARS else ""),
            source="telegram",
            agent=self.agent,
            created_at=now,
            updated_at=now,
        )
        self.state.create_conversation(_with_turn(empty, now, turn))
        self._fresh.discard(key)


def _with_turn(record: ConversationRecord, now: datetime, turn: StoredTurn) -> ConversationRecord:
    moment = max(now, record.updated_at)
    return ConversationRecord.model_validate(
        record.model_copy(
            update={
                "updated_at": moment,
                "messages": (
                    *record.messages,
                    ConversationMessage(
                        message_id=f"message-{uuid.uuid4().hex}",
                        role="user",
                        text=turn.said,
                        created_at=moment,
                        status="submitted",
                        attachments=tuple(turn.files),
                    ),
                    ConversationMessage(
                        message_id=f"message-{uuid.uuid4().hex}",
                        role="assistant",
                        text=turn.answer,
                        created_at=moment,
                        status=turn.status,
                        tool_summary=turn.tool_summary,
                    ),
                ),
            }
        ).model_dump()
    )
