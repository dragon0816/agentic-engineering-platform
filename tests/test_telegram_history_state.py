"""The record's source and what the state offers for it (docs/phases/TELEGRAM_HISTORY.md)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from host_runtime.conversations import ConversationMessage, ConversationRecord
from host_runtime.state import SqliteLocalState

MOMENT = datetime(2026, 11, 2, 12, tzinfo=UTC)


def state(tmp_path: Path) -> SqliteLocalState:
    return SqliteLocalState(tmp_path / "state.sqlite", bridge_id="bridge-a")


def record(
    session_id: str,
    *said: str,
    actor: str = "engineer",
    at: datetime = MOMENT,
    title: str = "A title",
) -> ConversationRecord:
    messages: list[ConversationMessage] = []
    for index, text in enumerate(said):
        messages.append(
            ConversationMessage(
                message_id=f"m{index}u",
                role="user",
                text=text,
                created_at=at,
                status="submitted",
            )
        )
        messages.append(
            ConversationMessage(
                message_id=f"m{index}a",
                role="assistant",
                text="ok",
                created_at=at,
                status="answered",
            )
        )
    return ConversationRecord(
        session_id=session_id,
        actor=actor,
        title=title,
        source="telegram" if session_id.startswith("tg-") else "agent_web",
        created_at=at,
        updated_at=at,
        messages=tuple(messages),
    )


def test_a_record_written_before_the_field_reads_as_agent_web() -> None:
    old = record("conversation-a").model_dump(mode="json")
    del old["source"]
    assert ConversationRecord.model_validate(old).source == "agent_web"


def test_the_source_and_the_session_id_agree_both_ways() -> None:
    fields = {"actor": "engineer", "title": "t", "created_at": MOMENT, "updated_at": MOMENT}
    with pytest.raises(ValueError, match="telegram"):
        ConversationRecord(session_id="conversation-a", source="telegram", **fields)
    with pytest.raises(ValueError, match="telegram"):
        ConversationRecord(session_id="tg-abc-20261102-1", source="agent_web", **fields)


def test_existing_readers_get_agent_web_conversations_only(tmp_path: Path) -> None:
    with state(tmp_path) as local:
        local.create_conversation(record("conversation-a"))
        local.create_conversation(record("tg-abc-20261102-1", "hello"))
        assert [item.session_id for item in local.conversations("engineer")] == ["conversation-a"]
        assert [item.session_id for item in local.conversations("engineer", source="telegram")] == [
            "tg-abc-20261102-1"
        ]


def test_telegram_records_do_not_push_chats_out_of_the_latest_list(tmp_path: Path) -> None:
    with state(tmp_path) as local:
        local.create_conversation(record("conversation-a", at=MOMENT - timedelta(days=9)))
        for day in range(3):
            local.create_conversation(record(f"tg-abc-2026110{day}-1", at=MOMENT))
        assert [item.session_id for item in local.conversations("engineer", limit=1)] == [
            "conversation-a"
        ]


def test_the_latest_conversation_under_a_prefix_is_this_actors(tmp_path: Path) -> None:
    with state(tmp_path) as local:
        local.create_conversation(record("tg-abc-20261101-1", at=MOMENT - timedelta(days=1)))
        local.create_conversation(record("tg-abc-20261102-1"))
        local.create_conversation(record("tg-def-20261103-1", at=MOMENT + timedelta(days=1)))
        local.create_conversation(
            record("tg-abc-20261104-1", actor="tester", at=MOMENT + timedelta(days=2))
        )
        found = local.latest_conversation("engineer", "tg-abc-")
        assert found is not None and found.session_id == "tg-abc-20261102-1"
        assert local.latest_conversation("engineer", "tg-none-") is None


def test_search_finds_message_text_and_titles_of_this_actor_in_both_sources(
    tmp_path: Path,
) -> None:
    with state(tmp_path) as local:
        local.create_conversation(record("conversation-a", "量測 CMX500 的頻段"))
        local.create_conversation(
            record("tg-abc-20261102-1", "另一個 cmx500 問題", at=MOMENT + timedelta(hours=1))
        )
        local.create_conversation(record("conversation-b", "unrelated", title="CMX500 plan"))
        local.create_conversation(record("conversation-c", "cmx500", actor="tester"))
        assert {item.session_id for item in local.search_conversations("engineer", "CMX500")} == {
            "conversation-a",
            "conversation-b",
            "tg-abc-20261102-1",
        }
        newest = local.search_conversations("engineer", "cmx500")[0]
        assert newest.session_id == "tg-abc-20261102-1"
        # Chinese matches as a substring.
        assert [item.session_id for item in local.search_conversations("engineer", "頻段")] == [
            "conversation-a"
        ]


def test_search_looks_at_text_not_at_the_records_json_and_takes_wildcards_literally(
    tmp_path: Path,
) -> None:
    with state(tmp_path) as local:
        local.create_conversation(record("conversation-a", "100% done_now"))
        local.create_conversation(record("conversation-b", "nothing to see"))
        # Words only the stored JSON contains.
        assert local.search_conversations("engineer", "message_id") == ()
        assert local.search_conversations("engineer", "submitted") == ()
        assert len(local.search_conversations("engineer", "%")) == 1
        assert len(local.search_conversations("engineer", "e_n")) == 1
        assert local.search_conversations("engineer", "n_w") == ()


def test_search_is_bounded(tmp_path: Path) -> None:
    with state(tmp_path) as local:
        for index in range(4):
            local.create_conversation(record(f"conversation-{index}", "same words"))
        assert len(local.search_conversations("engineer", "same", limit=2)) == 2


def test_a_host_key_is_made_once_and_survives_a_reopen(tmp_path: Path) -> None:
    with state(tmp_path) as local:
        first = local.host_key("telegram_history")
        assert len(first) == 32 and local.host_key("telegram_history") == first
        assert local.host_key("another") != first
    with state(tmp_path) as reopened:
        assert reopened.host_key("telegram_history") == first
