"""The owner's Telegram turns are stored for reading (docs/phases/TELEGRAM_HISTORY.md).

Over the fake Bot API of `test_telegram_ingress` with stub models: no socket,
no bot token and no real model. What the model receives does not change.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from test_host_wiring import host_json, ready
from test_telegram_attachments import FileTransport, Seeing, message
from test_telegram_ingress import OWNER, TESTER, FakeTransport, ingress, poll, update
from test_telegram_reply_context import Recording, replying
from test_telegram_settings import Store, _update
from test_telegram_workflow_flow import _install, _tap

from channels.telegram import TelegramIngress
from common.distribution import LocalStateError
from host_runtime.agent import LocalAgent
from host_runtime.attachments import AttachmentStore
from host_runtime.conversations import MAX_STORED_MESSAGES, ConversationRecord
from host_runtime.host import build_runtime
from host_runtime.telegram_history import TelegramHistory
from host_runtime.telegram_settings import TOKEN_VARIABLE
from host_runtime.web import AgentWeb

NOON = datetime(2026, 11, 2, 12, tzinfo=UTC)
#: A chat id no id, title or text could contain by chance.
BIG_CHAT = 7654321987654


class Clock:
    """A second passes on each reading, so two records never tie on time."""

    def __init__(self, now: datetime = NOON) -> None:
        self.now = now

    def __call__(self) -> datetime:
        self.now += timedelta(seconds=1)
        return self.now


def storing(
    tmp_path: Path, transport: FakeTransport, **changes: Any
) -> tuple[TelegramIngress, LocalAgent, Clock, Recording]:
    item, agent, _ = ingress(tmp_path, transport, **changes)
    clock = Clock()
    item.history = TelegramHistory(agent.state, "engineer", clock=clock)
    model = Recording("好的，收到")
    agent.gateway.router.model = model
    return item, agent, clock, model


def records(agent: LocalAgent, actor: str = "engineer") -> list[ConversationRecord]:
    return list(reversed(agent.state.conversations(actor, source="telegram")))


def test_the_owners_turn_is_stored_as_a_telegram_record_with_no_raw_chat_id(
    tmp_path: Path,
) -> None:
    transport = FakeTransport([[update(1, OWNER, "第一個問題", chat=BIG_CHAT)]])
    item, agent, _, _ = storing(tmp_path, transport)
    assert poll(item).deliveries[0].disposition == "answered"
    (record,) = records(agent)
    assert record.source == "telegram" and record.actor == "engineer"
    assert record.title == "第一個問題"
    assert [(m.role, m.text, m.status) for m in record.messages] == [
        ("user", "第一個問題", "submitted"),
        ("assistant", "好的，收到", "answered"),
    ]
    assert str(BIG_CHAT) not in record.model_dump_json()


def test_what_the_model_receives_is_the_same_with_and_without_the_store(tmp_path: Path) -> None:
    def talk(root: Path, store: bool) -> tuple[list[list[str]], list[str]]:
        words = [[update(n, OWNER, f"message {n}")] for n in range(1, 10)]
        transport = FakeTransport(words)
        item, agent, _ = ingress(root, transport)
        if store:
            item.history = TelegramHistory(agent.state, "engineer", clock=Clock())
        model = Recording()
        agent.gateway.router.model = model
        for _ in words:
            poll(item)
        seen = [
            [m.text for m in request.messages if m.role != "system"] for request in model.requests
        ]
        (history,) = item._histories.values()
        return seen, [m.text for m in history]

    assert talk(tmp_path / "with", True) == talk(tmp_path / "without", False)


def test_a_restart_gives_the_model_nothing_back_and_the_day_continues(tmp_path: Path) -> None:
    transport = FakeTransport([[update(1, OWNER, "before the restart")]])
    item, agent, clock, _ = storing(tmp_path, transport)
    poll(item)
    agent.state.close()

    again = FakeTransport([[update(2, OWNER, "after the restart")]])
    restarted, agent2, _ = ingress(tmp_path, again)
    restarted.history = TelegramHistory(agent2.state, "engineer", clock=clock)
    model = Recording()
    agent2.gateway.router.model = model
    poll(restarted)

    assert "before the restart" not in model.said()
    (record,) = records(agent2)
    assert [m.text for m in record.messages if m.role == "user"] == [
        "before the restart",
        "after the restart",
    ]


def test_other_allowed_senders_and_strangers_are_not_stored(tmp_path: Path) -> None:
    transport = FakeTransport([[update(1, TESTER, "the tester's words")], [update(2, 999, "hi")]])
    item, agent, _, _ = storing(tmp_path, transport)
    poll(item)
    poll(item)
    assert records(agent) == [] and records(agent, "tester") == []


def test_a_shared_workstations_employees_are_not_stored(tmp_path: Path) -> None:
    transport = FakeTransport([[update(1, TESTER, "the tester's words")]])
    item, agent, _ = ingress(
        tmp_path,
        transport,
        "shared_test_workstation",
        senders=[{"sender_id": TESTER, "actor": "tester"}],
    )
    item.history = TelegramHistory(agent.state, "shared-bot", clock=Clock())
    agent.gateway.router.model = Recording()
    poll(item)
    assert agent.state.conversations("shared-bot", source="telegram") == ()
    assert agent.state.conversations("tester", source="telegram") == ()


def test_a_quote_reaches_the_model_and_not_the_record(tmp_path: Path) -> None:
    transport = FakeTransport(
        [[replying(1, "再跑一次", {"text": "someone else's words", "from": {"id": TESTER}})]]
    )
    item, agent, _, model = storing(tmp_path, transport)
    poll(item)
    assert "someone else's words" in model.said()
    stored = records(agent)[0].model_dump_json()
    assert "someone else's words" not in stored and "再跑一次" in stored


def test_failure_text_stays_out_and_the_turn_is_marked_failed(tmp_path: Path) -> None:
    transport = FakeTransport([[update(1, OWNER, "幫我整理")]])
    item, agent, _, _ = storing(tmp_path, transport)
    agent.gateway.router.model = Recording(failures=1)
    item.explain_failure = lambda failure: "the long explanation of the failure"
    delivery = poll(item).deliveries[0]
    assert delivery.reply == "the long explanation of the failure"
    (record,) = records(agent)
    answer = record.messages[1]
    assert answer.status == "failed" and answer.text.startswith("（上一輪沒有完成：")
    stored = record.model_dump_json()
    assert "long explanation" not in stored and "the gateway is not running" not in stored
    assert answer.text == item._histories[(OWNER, OWNER)][-1].text


def test_a_credential_bearing_message_is_not_stored(tmp_path: Path) -> None:
    transport = FakeTransport([[update(1, OWNER, "shipment.run password: hunter2")]])
    item, agent, _, _ = storing(tmp_path, transport)
    poll(item)
    assert records(agent) == []


def test_credential_shaped_text_in_an_answer_is_cut_from_the_record(tmp_path: Path) -> None:
    transport = FakeTransport([[update(1, OWNER, "what does the doc say")]])
    item, agent, _, _ = storing(tmp_path, transport)
    agent.gateway.router.model = Recording("It says Authorization: Bearer abc123def456ghi789")
    poll(item)
    assert "abc123def456ghi789" not in records(agent)[0].model_dump_json()


def test_a_workflow_flow_keeps_its_note_and_result_and_not_the_answers(tmp_path: Path) -> None:
    transport = FakeTransport([[update(1, OWNER, "幫我執行 release-validation-form")]])
    item, agent, _, _ = storing(tmp_path, transport)
    _install(agent, [{"name": "package", "label": "Mode", "kind": "text", "required": True}])
    poll(item)
    transport.batches.append([update(2, OWNER, "an-answer-to-the-question")])
    poll(item)
    transport.batches.append([_tap(3, OWNER, "run:yes", transport)])
    assert poll(item).deliveries[0].disposition == "routed"
    stored = "\n".join(record.model_dump_json() for record in records(agent))
    assert "幫我執行 release-validation-form" in stored
    assert "【執行】release-validation-form" in stored
    assert "an-answer-to-the-question" not in stored


def test_commands_that_never_reach_the_history_are_not_stored(tmp_path: Path) -> None:
    transport = FakeTransport([[update(1, OWNER, "/help")], [update(2, OWNER, "/status")]])
    item, agent, _, _ = storing(tmp_path, transport)
    poll(item)
    poll(item)
    assert item._histories == {} and records(agent) == []


def test_a_new_day_starts_a_new_record_and_nothing_is_lost(tmp_path: Path) -> None:
    transport = FakeTransport([[update(1, OWNER, "today")], [update(2, OWNER, "tomorrow")]])
    item, agent, clock, _ = storing(tmp_path, transport)
    poll(item)
    clock.now += timedelta(days=1)
    poll(item)
    first, second = records(agent)
    assert first.session_id != second.session_id
    assert first.messages[0].text == "today" and second.messages[0].text == "tomorrow"


def test_a_full_record_rolls_over_and_keeps_every_message(tmp_path: Path) -> None:
    turns = MAX_STORED_MESSAGES // 2 + 1
    words = [[update(n, OWNER, f"message {n}")] for n in range(1, turns + 1)]
    item, agent, _, _ = storing(tmp_path, FakeTransport(words))
    for _ in words:
        poll(item)
    first, second = records(agent)
    assert len(first.messages) == MAX_STORED_MESSAGES and len(second.messages) == 2
    said = [m.text for r in (first, second) for m in r.messages if m.role == "user"]
    assert said == [f"message {n}" for n in range(1, turns + 1)]


def test_new_starts_a_new_record_and_deletes_none(tmp_path: Path) -> None:
    transport = FakeTransport(
        [
            [update(1, OWNER, "before")],
            [update(2, OWNER, "/new")],
            [update(3, OWNER, "/new")],
            [update(4, OWNER, "after")],
        ]
    )
    item, agent, _, model = storing(tmp_path, transport)
    poll(item)
    assert poll(item).deliveries[0].reply == "Started a fresh conversation."
    assert item._histories == {}
    assert len(records(agent)) == 1
    poll(item)
    poll(item)
    first, second = records(agent)
    assert first.messages[0].text == "before" and second.messages[0].text == "after"
    assert "before" not in model.said()


def test_new_keeps_the_owners_files_and_still_clears_another_senders(tmp_path: Path) -> None:
    def document(number: int, sender: int) -> dict[str, Any]:
        return message(
            number, sender, document={"file_id": "doc1", "file_name": "a.txt", "file_size": 1}
        )

    transport = FileTransport(
        [
            [document(1, OWNER)],
            [update(2, OWNER, "/new")],
            [document(3, TESTER)],
            [update(4, TESTER, "/new")],
        ],
        {"doc1": b"x"},
    )
    item, agent, _ = ingress(tmp_path, transport)
    item.attachments = AttachmentStore(tmp_path / "workspace")
    item.history = TelegramHistory(agent.state, "engineer", clock=Clock())
    agent.gateway.router.model = Seeing()
    root = tmp_path / "workspace" / "attachments"

    poll(item)
    assert len(list(root.iterdir())) == 1
    poll(item)
    assert len(list(root.iterdir())) == 1, "the stored record lists the owner's file"
    poll(item)
    assert len(list(root.iterdir())) == 2
    poll(item)
    assert len(list(root.iterdir())) == 1, "another sender's /new works as it did"


def test_an_attached_file_is_listed_by_name_and_path_and_its_content_is_not_stored(
    tmp_path: Path,
) -> None:
    transport = FileTransport(
        [
            [
                message(
                    1,
                    OWNER,
                    caption="看這個",
                    document={"file_id": "doc1", "file_name": "a.txt", "file_size": 7},
                )
            ]
        ],
        {"doc1": b"unique-file-words"},
    )
    item, agent, _ = ingress(tmp_path, transport)
    item.attachments = AttachmentStore(tmp_path / "workspace")
    item.history = TelegramHistory(agent.state, "engineer", clock=Clock())
    agent.gateway.router.model = Seeing()
    poll(item)
    (record,) = records(agent)
    asked = record.messages[0]
    assert asked.text == "看這個"
    (listed,) = asked.attachments
    assert listed["filename"] == "a.txt" and listed["kind"] == "text"
    assert Path(listed["path"]).is_file()
    assert "unique-file-words" not in record.model_dump_json()
    # The model's history keeps its listing as before.
    (history,) = item._histories.values()
    assert "[附件]" in history[0].text


def test_a_record_deleted_meanwhile_is_not_written_back(tmp_path: Path) -> None:
    transport = FakeTransport([[update(1, OWNER, "first")], [update(2, OWNER, "second")]])
    item, agent, _, _ = storing(tmp_path, transport)
    poll(item)
    (gone,) = records(agent)
    assert agent.state.delete_conversation(gone.session_id, "engineer")
    poll(item)
    (record,) = records(agent)
    assert record.session_id != gone.session_id
    assert [m.text for m in record.messages if m.role == "user"] == ["second"]


def test_a_record_that_vanishes_between_the_read_and_the_write_starts_anew(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    transport = FakeTransport([[update(1, OWNER, "first")], [update(2, OWNER, "second")]])
    item, agent, _, _ = storing(tmp_path, transport)
    poll(item)
    state = agent.state
    real = state.save_conversation

    def deleted_first(record: ConversationRecord) -> ConversationRecord:
        state.delete_conversation(record.session_id, record.actor)
        return real(record)

    monkeypatch.setattr(state, "save_conversation", deleted_first)
    poll(item)
    (record,) = records(agent)
    assert [m.text for m in record.messages if m.role == "user"] == ["second"]


def test_the_id_is_stable_for_a_chat_and_differs_between_chats(tmp_path: Path) -> None:
    transport = FakeTransport(
        [[update(1, OWNER, "one")], [update(2, OWNER, "other chat", chat=BIG_CHAT)]]
    )
    item, agent, clock, _ = storing(tmp_path, transport)
    poll(item)
    poll(item)
    first, second = records(agent)
    assert first.session_id.split("-")[1] != second.session_id.split("-")[1]
    # A later day of the first chat keeps its id.
    clock.now += timedelta(days=1)
    transport.batches.append([update(3, OWNER, "next day")])
    poll(item)
    third = next(r for r in records(agent) if r.messages[0].text == "next day")
    assert third.session_id.split("-")[1] == first.session_id.split("-")[1]


def test_a_store_that_fails_never_fails_the_turn(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    transport = FakeTransport([[update(1, OWNER, "private words", chat=BIG_CHAT)]])
    item, agent, _, _ = storing(tmp_path, transport)

    def refuse(_: ConversationRecord) -> ConversationRecord:
        raise LocalStateError("unavailable")

    monkeypatch.setattr(agent.state, "create_conversation", refuse)
    with caplog.at_level(logging.WARNING):
        delivery = poll(item).deliveries[0]
    assert delivery.reply == "好的，收到" and delivery.failure is None
    assert len(item._histories[(BIG_CHAT, OWNER)]) == 2
    assert "LocalStateError" in caplog.text
    assert "private words" not in caplog.text and str(BIG_CHAT) not in caplog.text


def test_saving_the_settings_keeps_the_store(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(TOKEN_VARIABLE, raising=False)
    config, layout = ready(tmp_path)
    path = host_json(tmp_path, config)
    with build_runtime(config, layout=layout) as runtime:
        assert runtime.telegram_history is not None
        assert runtime.telegram_history.actor == runtime.actor
        web = AgentWeb(runtime, config_path=path)
        web.user_environment = Store()
        monkeypatch.setattr(web, "start_telegram", lambda: None)  # no network in tests
        assert web.update_telegram_settings(_update())["ok"] is True
        assert runtime.telegram is not None
        assert runtime.telegram.history is runtime.telegram_history
