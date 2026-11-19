"""Telegram feature items and proactive messages (owner consent 2026-11-19,
docs/phases/TELEGRAM_LINK_COLLECTION_ASSESSMENT_20261119.md §8).

A message that is links, files without words, a tap on a feature's button, a
feature's own slash command and a Reply reach `Feature.telegram_item` before any
model turn; anything else goes on as before. `TelegramIngress.send` reaches only
an actor in the sender map. Driven over the fake transport of the ingress tests.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from test_telegram_ingress import OWNER, STRANGER, FakeTransport, ingress, poll, update

from channels.telegram import FEATURE_TAP, link_urls, tags_only
from host_runtime.features import (
    Feature,
    FeatureSet,
    Messenger,
    TelegramAnswer,
    TelegramItem,
)

#: What the old path says to free text on a Bridge without a model.
OLD_PATH = "That could not be answered (model_unavailable)."


class Taker(Feature):
    """Takes every item it is offered (or none), recording each one."""

    name = "taker"

    def __init__(self, take: bool = True) -> None:
        self.take = take
        self.items: list[TelegramItem] = []
        self.ready: list[tuple[Messenger, Any]] = []

    def telegram_commands(self) -> tuple[tuple[str, str], ...]:
        return (("bi", "link"),)

    def telegram_item(self, item: TelegramItem, host: Any) -> TelegramAnswer | None:
        self.items.append(item)
        if not self.take:
            return None
        return TelegramAnswer(
            f"got {item.kind}",
            ((("A", "bi.t.1.0"), ("bad payload", "has space")),),
            edit=item.kind == "tap",
        )

    def telegram_ready(self, messenger: Messenger, host: Any) -> None:
        self.ready.append((messenger, host))


def tap(update_id: int, data: str, message_id: int = 77) -> dict[str, Any]:
    return {
        "update_id": update_id,
        "callback_query": {
            "id": f"cb-{update_id}",
            "from": {"id": OWNER, "is_bot": False},
            "message": {
                "message_id": message_id,
                "chat": {"id": OWNER, "type": "private"},
                "text": "pick",
            },
            "data": data,
        },
    }


def reply_to(update_id: int, text: str, quoted: str) -> dict[str, Any]:
    raw = update(update_id, OWNER, text)
    raw["message"]["reply_to_message"] = {"message_id": 5, "text": quoted}
    return raw


def captioned_file(update_id: int, caption: str | None) -> dict[str, Any]:
    raw = update(update_id, OWNER, None)
    if caption is not None:
        raw["message"]["caption"] = caption
    return raw


def setup(tmp_path: Path, batch: list[dict[str, Any]], take: bool = True) -> Any:
    transport = FakeTransport([batch])
    item, _agent, _runner = ingress(tmp_path, transport)
    feature = Taker(take)
    host = object()
    item.attach_features(FeatureSet([feature]), host)
    return item, transport, feature, host


def keyboards(transport: FakeTransport) -> list[Any]:
    return [
        payload["reply_markup"]
        for url, payload in transport.calls
        if url.endswith(("/sendMessage", "/editMessageText")) and "reply_markup" in payload
    ]


def test_link_rules() -> None:
    assert link_urls("https://example.com/a?utm_source=x") == (
        "https://example.com/a?utm_source=x",
    )
    assert link_urls("看這篇 #aidc https://example.com/a。") == ("https://example.com/a",)
    assert link_urls("這篇在說什麼？ https://example.com/a") == ()
    assert link_urls("no address here") == ()
    assert link_urls("x" * 301 + " https://example.com") == ()
    assert tags_only("") and tags_only(" #aidc #wireless ")
    assert not tags_only("summarize this #aidc")


def test_attaching_tells_the_feature_the_channel_is_up(tmp_path: Path) -> None:
    item, _transport, feature, host = setup(tmp_path, [])
    assert feature.ready == [(item, host)]


def test_a_link_message_reaches_the_feature_not_the_model(tmp_path: Path) -> None:
    item, transport, feature, _ = setup(
        tmp_path, [update(1, OWNER, "#aidc https://example.com/news")]
    )
    result = poll(item)
    assert [i.kind for i in feature.items] == ["link"]
    taken = feature.items[0]
    assert (taken.actor, taken.urls, taken.text) == (
        "engineer",
        ("https://example.com/news",),
        "#aidc https://example.com/news",
    )
    assert result.deliveries[0].disposition == "answered"
    assert transport.sent() == ["got link"]
    # The payload got the channel's prefix; an unusable one was dropped.
    assert keyboards(transport) == [
        {"inline_keyboard": [[{"text": "A", "callback_data": FEATURE_TAP + "bi.t.1.0"}]]}
    ]
    assert any(url.endswith("/sendChatAction") for url, _ in transport.calls)


def test_a_question_about_a_link_stays_a_conversation(tmp_path: Path) -> None:
    item, _transport, feature, _ = setup(
        tmp_path, [update(1, OWNER, "這篇在說什麼？ https://example.com/news")]
    )
    poll(item)
    assert feature.items == []


def test_a_file_without_words_is_an_item_and_one_with_a_request_is_not(tmp_path: Path) -> None:
    item, transport, feature, _ = setup(
        tmp_path, [captioned_file(1, None), captioned_file(2, "#aidc"), captioned_file(3, "摘要")]
    )
    poll(item)
    assert [(i.kind, i.text) for i in feature.items] == [("file", ""), ("file", "#aidc")]
    assert feature.items[0].files[0].name == "notes.txt"
    # The captioned one went the old way: this Bridge has no attachment store.
    assert transport.sent()[-1] == "這個 Bridge 不接受附件。"


def test_a_tap_on_a_feature_button_edits_the_message(tmp_path: Path) -> None:
    item, transport, feature, _ = setup(tmp_path, [tap(1, FEATURE_TAP + "bi.t.4.2")])
    poll(item)
    assert [(i.kind, i.data) for i in feature.items] == [("tap", "bi.t.4.2")]
    edits = [p for url, p in transport.calls if url.endswith("/editMessageText")]
    assert edits and edits[0]["message_id"] == 77 and edits[0]["text"] == "got tap"
    assert any(url.endswith("/answerCallbackQuery") for url, _ in transport.calls)


def test_other_buttons_are_not_feature_items(tmp_path: Path) -> None:
    item, _transport, feature, _ = setup(tmp_path, [tap(1, "run:yes")])
    poll(item)
    assert feature.items == []


def test_only_the_features_own_commands_are_items(tmp_path: Path) -> None:
    item, transport, feature, _ = setup(
        tmp_path,
        [update(1, OWNER, "/bi link aidc https://example.com"), update(2, OWNER, "/bi other x")],
    )
    poll(item)
    assert [(i.kind, i.data, i.text) for i in feature.items] == [
        ("command", "bi link", "aidc https://example.com")
    ]
    assert transport.sent()[0] == "got command"


def test_a_reply_is_offered_and_a_declined_item_goes_on_as_before(tmp_path: Path) -> None:
    item, transport, feature, _ = setup(
        tmp_path, [reply_to(1, "補充內文", "#12 只取得摘要")], take=False
    )
    result = poll(item)
    assert [(i.kind, i.quoted) for i in feature.items] == [("reply", "#12 只取得摘要")]
    # Declined: the old path answered it (this Bridge has no model).
    assert result.deliveries[0].reply == OLD_PATH
    assert transport.sent() == [OLD_PATH]


def test_an_unmapped_sender_never_reaches_a_feature(tmp_path: Path) -> None:
    item, transport, feature, _ = setup(tmp_path, [update(1, STRANGER, "https://example.com")])
    result = poll(item)
    assert feature.items == []
    assert result.deliveries[0].disposition == "unmapped_sender"
    assert transport.sent() == []


def test_without_features_a_link_is_an_ordinary_message(tmp_path: Path) -> None:
    transport = FakeTransport([[update(1, OWNER, "https://example.com/news")]])
    item, _agent, _runner = ingress(tmp_path, transport)
    poll(item)
    assert transport.sent() == [OLD_PATH]


def test_send_reaches_only_a_mapped_actor(tmp_path: Path) -> None:
    item, transport, _feature, _ = setup(tmp_path, [])
    assert item.send("engineer", "AIDC 有 3 張候選卡待審", ((("開啟", "bi.open"),),)) is True
    sent = [p for url, p in transport.calls if url.endswith("/sendMessage")]
    assert sent[-1]["chat_id"] == OWNER and sent[-1]["text"] == "AIDC 有 3 張候選卡待審"
    assert sent[-1]["reply_markup"]["inline_keyboard"][0][0]["callback_data"] == "fi:bi.open"
    before = len(transport.calls)
    assert item.send("nobody", "hello") is False
    assert item.send("engineer", "   ") is False
    assert len(transport.calls) == before
