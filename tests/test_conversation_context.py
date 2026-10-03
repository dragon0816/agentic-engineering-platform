"""The user-controlled context budget bounds only the conversation transcript."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from host_runtime.conversation_context import (
    ConversationContextSettings,
    ConversationContextStore,
    prepare_history,
)
from models.contracts import ModelMessage


def test_context_settings_persist_and_reject_out_of_range_values(tmp_path: Path) -> None:
    store = ConversationContextStore(tmp_path)
    assert store.load() == ConversationContextSettings()
    changed = ConversationContextSettings(recent_messages=3, history_budget_bytes=8_000)
    assert store.save(changed) == changed
    assert ConversationContextStore(tmp_path).load() == changed
    with pytest.raises(ValidationError):
        ConversationContextSettings(recent_messages=41)
    with pytest.raises(ValidationError):
        ConversationContextSettings(history_budget_bytes=3_999)


def test_context_keeps_current_message_and_only_recent_complete_history() -> None:
    settings = ConversationContextSettings(recent_messages=3, history_budget_bytes=4_000)
    history = tuple(
        ModelMessage(role="user" if index % 2 == 0 else "assistant", text=str(index) * 1_500)
        for index in range(5)
    )
    selected = prepare_history(history, settings)
    assert [item.text[:1] for item in selected] == ["3", "4"]
    assert sum(len(item.text.encode("utf-8")) for item in selected) <= 4_000


def test_current_message_is_not_silently_truncated() -> None:
    settings = ConversationContextSettings(recent_messages=1, history_budget_bytes=4_000)
    with pytest.raises(ValueError, match="current_message_too_large"):
        prepare_history((ModelMessage(role="user", text="你" * 1_500),), settings)


def test_one_recent_message_sends_no_previous_session_text() -> None:
    settings = ConversationContextSettings(recent_messages=1)
    selected = prepare_history(
        (
            ModelMessage(role="user", text="previous private detail"),
            ModelMessage(role="assistant", text="previous answer"),
            ModelMessage(role="user", text="current question"),
        ),
        settings,
    )
    assert [item.text for item in selected] == ["current question"]
