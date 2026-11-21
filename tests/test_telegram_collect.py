"""Collection bots beside the conversation bot (owner consent 2026-11-20, one bot per BI
domain; docs/DECISIONS.md).

Each collection bot polls on its own with its own cursor; what a mapped sender sends it
(a link, words, a file, a Reply) reaches the configured feature's `telegram_item` and
never a model; an unmapped sender is ignored; `send` reaches only that bot's mapped
senders. The conversation bot is configured and behaves as before. Over the fake
transport of the ingress tests; no socket is opened.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError
from test_telegram_ingress import (
    OWNER,
    STRANGER,
    TOKEN,
    CountingCredentials,
    FakeTransport,
    config,
    ingress,
    poll,
    update,
)

from channels.telegram import TelegramCollectionBot, TelegramIngressConfig
from channels.telegram_collect import NOT_CONNECTED, TelegramBots, TelegramCollector, attach
from host_runtime.features import (
    Feature,
    FeatureSet,
    Messenger,
    TelegramAnswer,
    TelegramItem,
)
from host_runtime.state import SqliteLocalState

OTHER_TOKEN = "9876543210:AAF" + "y" * 32


class Collecting(Feature):
    name = "bi-knowledge"

    def __init__(self) -> None:
        self.items: list[TelegramItem] = []
        self.ready: list[tuple[Messenger, Any]] = []

    def telegram_item(self, item: TelegramItem, host: Any) -> TelegramAnswer | None:
        self.items.append(item)
        return TelegramAnswer(f"已收進 {item.target}（{item.kind}）")

    def telegram_ready(self, messenger: Messenger, host: Any) -> None:
        self.ready.append((messenger, host))


def bot_config(name: str = "bi_aidc", **changes: Any) -> TelegramCollectionBot:
    return TelegramCollectionBot.model_validate(
        {
            "name": name,
            "credential": {"name": f"telegram_{name}"},
            "feature": "bi-knowledge",
            "target": "aidc",
            "senders": [{"sender_id": OWNER, "actor": "engineer"}],
            **changes,
        }
    )


def message(update_id: int, text: str | None, sender: int = OWNER) -> dict[str, Any]:
    return update(update_id, sender, text)


def collector(
    tmp_path: Path, batches: list[list[dict[str, Any]]], name: str = "bi_aidc"
) -> TelegramCollector:
    tmp_path.mkdir(parents=True, exist_ok=True)
    state = SqliteLocalState(tmp_path / f"{name}.sqlite", bridge_id="bridge-company")
    return TelegramCollector(
        bot_config(name),
        state,
        CountingCredentials({f"telegram_{name}": OTHER_TOKEN}),
        transport=FakeTransport(batches),
    )


def wire(item: TelegramCollector) -> FakeTransport:
    """The fake transport a test collector was built with."""
    transport = item._transport
    assert isinstance(transport, FakeTransport)
    return transport


def run(item: TelegramCollector) -> list[tuple[int, str]]:
    return asyncio.run(item.poll_once())


def test_the_config_keeps_the_conversation_bot_and_adds_collection_bots() -> None:
    plain = config()
    assert plain.collection_bots == ()
    added = config(collection_bots=[bot_config().model_dump(mode="json")])
    assert added.credential.name == "telegram_bot"
    assert added.collection_bots[0].name == "bi_aidc"
    with pytest.raises(ValidationError):  # one token per bot
        config(collection_bots=[bot_config(credential={"name": "telegram_bot"}).model_dump()])
    with pytest.raises(ValidationError):  # one name per bot
        config(collection_bots=[bot_config().model_dump(), bot_config().model_dump()])
    with pytest.raises(ValidationError):  # a pasted token is refused
        TelegramIngressConfig.model_validate(
            {
                **plain.model_dump(mode="json"),
                "collection_bots": [{**bot_config().model_dump(mode="json"), "target": TOKEN}],
            }
        )


def test_links_files_commands_and_item_replies_go_to_the_feature(tmp_path: Path) -> None:
    # Plain words are a question since owner 2026-11-21: test_telegram_collect_questions.
    feature = Collecting()
    raw_reply = message(3, "補充文字")
    raw_reply["message"]["reply_to_message"] = {"message_id": 9, "text": "#1 只取得摘要"}
    bot = collector(
        tmp_path,
        [
            [
                message(1, "看這篇 https://example.com/a"),
                message(2, "/links"),
                raw_reply,
                message(4, None),
            ]
        ],
    )
    attach([bot], FeatureSet([feature]), "host")
    assert run(bot) == [(1, "answered"), (2, "answered"), (3, "answered"), (4, "answered")]
    kinds = [(i.kind, i.bot, i.target, i.actor) for i in feature.items]
    assert kinds == [
        ("link", "bi_aidc", "aidc", "engineer"),
        ("text", "bi_aidc", "aidc", "engineer"),
        ("reply", "bi_aidc", "aidc", "engineer"),
        ("file", "bi_aidc", "aidc", "engineer"),
    ]
    assert feature.items[0].urls == ("https://example.com/a",)
    assert feature.items[2].quoted == "#1 只取得摘要"
    assert wire(bot).sent()[0] == "已收進 aidc（link）"
    # Its own cursor, on its own channel.
    assert bot.state.cursor("telegram-collect.bi_aidc") == 5


def test_an_unknown_sender_is_ignored(tmp_path: Path) -> None:
    feature = Collecting()
    bot = collector(tmp_path, [[message(1, "https://example.com/a", sender=STRANGER)]])
    attach([bot], FeatureSet([feature]), None)
    assert run(bot) == [(1, "unmapped_sender")]
    assert feature.items == [] and wire(bot).sent() == []
    assert STRANGER in bot.unmapped


def test_without_its_feature_the_bot_says_so_and_no_model_is_asked(tmp_path: Path) -> None:
    bot = collector(tmp_path, [[message(1, "https://example.com/a")]])
    attach([bot], FeatureSet([]), None)
    assert run(bot) == [(1, "answered")]
    assert wire(bot).sent() == [NOT_CONNECTED]


def test_two_bots_poll_independently(tmp_path: Path) -> None:
    feature = Collecting()
    aidc = collector(tmp_path, [[message(1, "a https://example.com/1")], []], "bi_aidc")
    wireless = collector(tmp_path, [[message(7, "b https://example.com/2")]], "bi_wireless")
    attach([aidc, wireless], FeatureSet([feature]), None)
    assert run(wireless) == [(7, "answered")]
    assert run(aidc) == [(1, "answered")]
    assert [i.bot for i in feature.items] == ["bi_wireless", "bi_aidc"]
    assert aidc.state.cursor(aidc.channel) == 2
    assert wireless.state.cursor(wireless.channel) == 8
    # Each bot calls the Bot API with its own token.
    assert all(f"/bot{OTHER_TOKEN}/" in url for url, _ in wire(aidc).calls)
    assert feature.ready[0][0].bots()[1].name == "bi_wireless"


def test_send_reaches_only_that_bots_mapped_senders(tmp_path: Path) -> None:
    bot = collector(tmp_path, [])
    bots = TelegramBots([bot])
    assert bots.send("bi_aidc", "engineer", "AIDC 有 3 張候選卡待審") is True
    sent = [p for url, p in wire(bot).calls if url.endswith("/sendMessage")]
    assert sent == [{"chat_id": OWNER, "text": "AIDC 有 3 張候選卡待審"}]
    assert bots.send("bi_aidc", "tester", "x") is False  # not this bot's sender
    assert bots.send("bi_other", "engineer", "x") is False  # no such bot
    assert len(wire(bot).calls) == 1


def test_the_conversation_bot_is_untouched_by_collection_bots(tmp_path: Path) -> None:
    transport = FakeTransport([[update(1, OWNER, "https://example.com/news")]])
    item, _agent, _runner = ingress(
        tmp_path, transport, collection_bots=[bot_config().model_dump(mode="json")]
    )
    poll(item)
    # The link is an ordinary message there (no model on this Bridge).
    assert transport.sent() == ["That could not be answered (model_unavailable)."]
    assert item.collectors == []  # only the host builds and starts them


def test_settings_keep_collection_bots_and_the_host_builds_only_mapped_ones(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import json

    from test_host_wiring import host_json, ready
    from test_telegram_settings import Store, _update

    from host_runtime.contracts import CompanyHostConfiguration
    from host_runtime.host import build_runtime
    from host_runtime.telegram_settings import TOKEN_VARIABLE, apply_telegram_settings

    monkeypatch.setenv(TOKEN_VARIABLE, TOKEN)
    config, layout = ready(tmp_path)
    path = host_json(tmp_path, config)
    apply_telegram_settings(path, layout, _update(), store=Store())
    written = json.loads(layout.telegram.read_text(encoding="utf-8"))
    assert "collection_bots" not in written  # a host without them writes what it did
    written["collection_bots"] = [
        bot_config().model_dump(mode="json"),
        bot_config("bi_wireless").model_dump(mode="json"),
    ]
    layout.telegram.write_text(json.dumps(written), encoding="utf-8")
    # Saving the conversation bot's settings again keeps them.
    apply_telegram_settings(path, layout, _update(token=None), store=Store())
    kept = json.loads(layout.telegram.read_text(encoding="utf-8"))
    assert [b["name"] for b in kept["collection_bots"]] == ["bi_aidc", "bi_wireless"]
    assert OTHER_TOKEN not in layout.telegram.read_text(encoding="utf-8")
    # Only a bot whose token name the host maps is built; the conversation bot is.
    host = CompanyHostConfiguration.model_validate_json(path.read_text(encoding="utf-8-sig"))
    mapped = host.model_dump(mode="json")
    mapped["credentials"].append(
        {"secret": "telegram_bi_aidc", "environment_variable": "AEP_TELEGRAM_BI_AIDC"}
    )
    path.write_text(json.dumps(mapped), encoding="utf-8")
    final = CompanyHostConfiguration.model_validate(mapped)
    with build_runtime(final, layout=layout) as runtime:
        assert runtime.telegram is not None
        assert [c.name for c in runtime.telegram.collectors] == ["bi_aidc"]
