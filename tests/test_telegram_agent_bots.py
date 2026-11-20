"""Telegram bots bound to persistent sub-agents (owner consent 2026-11-20,
docs/DECISIONS.md "Sidebar sections and agents bound to Telegram bots").

Two bots on one Host: the conversation bot feeds the main agent exactly as before;
an agent bot feeds its sub-agent's own conversation — the model request offers only
that agent's Skill tools and carries its purpose — and the reply goes back through
that bot. Each bot keeps its own cursor and sessions; an unknown sender is ignored;
a collection bot keeps collecting. Built by the Host's own `attach_telegram_bots`,
over the fake transport of the ingress tests; no socket is opened.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

from test_telegram_collect import OTHER_TOKEN, Collecting
from test_telegram_ingress import (
    OWNER,
    STRANGER,
    TOKEN,
    CountingCredentials,
    FakeTransport,
    ingress,
    poll,
    update,
)

from channels.telegram import (
    AGENT_BOT_COMMANDS,
    AGENT_BOT_GONE,
    TELEGRAM_CHANNEL,
    TelegramIngress,
)
from channels.telegram_collect import attach
from host_runtime.features import FeatureSet
from host_runtime.host import attach_telegram_bots
from host_runtime.persistent_agents import AgentStore, PersistentAgent
from host_runtime.telegram_history import TelegramHistory
from models.contracts import ModelRequest, ModelResponse, ModelStreamEvent

SHIPMENT = "engineering/shipment-skill@1.0.0"
COLLECT_TOKEN = "5555555555:AAG" + "z" * 32


class Recording:
    """A model that answers and keeps what each request offered."""

    def __init__(self) -> None:
        self.requests: list[ModelRequest] = []

    def generate(self, request: ModelRequest) -> ModelResponse:
        self.requests.append(request)
        return ModelResponse(
            trace=request.trace, model_alias=request.model_alias, text="Answer from the model"
        )

    def stream(self, request: ModelRequest) -> Iterator[ModelStreamEvent]:
        raise NotImplementedError

    def tools(self, index: int = -1) -> set[str]:
        return {tool.name for tool in self.requests[index].tools}

    def system(self, index: int = -1) -> str:
        return self.requests[index].messages[0].text


def agent_bot(**changes: Any) -> dict[str, Any]:
    return {
        "name": "agent-sales",
        "credential": {"name": "telegram_agent_sales"},
        "agent": "sales",
        "senders": [{"sender_id": OWNER, "actor": "engineer"}],
        **changes,
    }


def collection_bot() -> dict[str, Any]:
    return {
        "name": "bi_aidc",
        "credential": {"name": "telegram_bi_aidc"},
        "feature": "bi-knowledge",
        "target": "aidc",
        "senders": [{"sender_id": OWNER, "actor": "engineer"}],
    }


def two_bots(
    tmp_path: Path, main: list[list[dict[str, Any]]], own: list[list[dict[str, Any]]], **bot: Any
) -> tuple[TelegramIngress, TelegramIngress, Recording]:
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True)
    AgentStore(workspace).save(
        PersistentAgent(
            id="sales", name="Sales", purpose="Answer shipment questions.", skills=(SHIPMENT,)
        )
    )
    resolver = CountingCredentials(
        {
            "telegram_bot": TOKEN,
            "telegram_agent_sales": OTHER_TOKEN,
            "telegram_bi_aidc": COLLECT_TOKEN,
        }
    )
    item, agent, _ = ingress(
        tmp_path,
        FakeTransport(main),
        resolver=resolver,
        agent_bots=[agent_bot(**bot)],
        collection_bots=[collection_bot()],
    )
    item.history = TelegramHistory(agent.state, "engineer")
    model = Recording()
    agent.gateway.router.model = model
    attach_telegram_bots(
        cast(Any, SimpleNamespace(credential_environment=dict)),
        cast(Any, SimpleNamespace(workspace_root=workspace)),
        item,
        item.config,
        resolver,
    )
    (own_bot,) = item.agent_bots
    own_bot._transport = FakeTransport(own)
    return item, own_bot, model


def wire(item: TelegramIngress) -> FakeTransport:
    transport = item._transport
    assert isinstance(transport, FakeTransport)
    return transport


def test_the_conversation_bot_still_feeds_the_main_agent(tmp_path: Path) -> None:
    main, own, model = two_bots(tmp_path, [[update(1, OWNER, "hello main")]], [])
    delivery = poll(main).deliveries[0]
    assert delivery.disposition == "answered"
    assert "Answer from the model" in (delivery.reply or "")
    # Every installed Skill tool, and no sub-agent role.
    assert {"shipment__run", "release__check"} <= model.tools()
    assert '"Sales"' not in model.system()
    assert wire(main).sent() and not wire(own).calls
    (record,) = main.agent.state.conversations("engineer", source="telegram")
    assert record.agent is None
    assert main.agent.state.cursor(TELEGRAM_CHANNEL) == 2


def test_an_agent_bot_feeds_its_agents_own_conversation_and_replies_through_itself(
    tmp_path: Path,
) -> None:
    main, own, model = two_bots(tmp_path, [], [[update(7, OWNER, "where is my shipment?")]])
    delivery = poll(own).deliveries[0]
    assert delivery.disposition == "answered"
    # The model request is the sub-agent's: its Skill's tools only, its purpose.
    assert model.tools() == {"shipment__run"}
    assert 'You are "Sales"' in model.system()
    assert "Answer shipment questions." in model.system()
    # The reply went out through the agent bot (its own token), not the main bot.
    assert any("Answer from the model" in text for text in wire(own).sent())
    assert all(OTHER_TOKEN in url for url, _ in wire(own).calls)
    assert not wire(main).calls
    # Its own conversation, owned by the agent, apart from the main bot's.
    (record,) = main.agent.state.conversations("engineer", source="telegram")
    assert record.agent == "sales"
    assert own._session(OWNER) != main._session(OWNER)
    # Its own durable cursor; the conversation bot's is untouched.
    assert main.agent.state.cursor("telegram-agent.agent-sales") == 8
    assert main.agent.state.cursor(TELEGRAM_CHANNEL) is None


def test_an_unknown_sender_to_an_agent_bot_is_ignored(tmp_path: Path) -> None:
    main, own, model = two_bots(tmp_path, [], [[update(3, STRANGER, "hi")]])
    delivery = poll(own).deliveries[0]
    assert delivery.disposition == "unmapped_sender" and delivery.reply is None
    assert not model.requests
    assert not [url for url, _ in wire(own).calls if url.endswith("/sendMessage")]
    assert STRANGER in own.unmapped


def test_an_agent_bot_converses_only(tmp_path: Path) -> None:
    main, own, model = two_bots(tmp_path, [], [[update(4, OWNER, "/run shipment")]])
    delivery = poll(own).deliveries[0]
    assert delivery.reply == AGENT_BOT_COMMANDS
    assert not model.requests


def test_a_deleted_agent_is_said_and_never_answered_as_the_main_agent(tmp_path: Path) -> None:
    main, own, model = two_bots(tmp_path, [], [[update(5, OWNER, "still there?")]])
    assert own.agent_store.delete("sales")
    delivery = poll(own).deliveries[0]
    assert delivery.reply == AGENT_BOT_GONE
    assert not model.requests


def test_a_bot_switched_off_or_without_its_agent_is_not_polled(tmp_path: Path) -> None:
    main, _, _ = two_bots(tmp_path / "a", [], [])
    off = main.config.model_copy(
        update={"agent_bots": (main.config.agent_bots[0].model_copy(update={"enabled": False}),)}
    )
    attach_telegram_bots(
        cast(Any, SimpleNamespace(credential_environment=dict)),
        cast(Any, SimpleNamespace(workspace_root=tmp_path / "a" / "workspace")),
        main,
        off,
        main._resolver,
    )
    assert main.agent_bots == []
    orphan = main.config.model_copy(
        update={"agent_bots": (main.config.agent_bots[0].model_copy(update={"agent": "gone"}),)}
    )
    attach_telegram_bots(
        cast(Any, SimpleNamespace(credential_environment=dict)),
        cast(Any, SimpleNamespace(workspace_root=tmp_path / "a" / "workspace")),
        main,
        orphan,
        main._resolver,
    )
    assert main.agent_bots == []


def test_a_restart_check_sees_an_agent_bots_running_turn(tmp_path: Path) -> None:
    main, own, _ = two_bots(tmp_path, [], [])
    assert main.activity() == []
    own._busy[(OWNER, OWNER)] = datetime.now(UTC)
    (item,) = main.activity()
    assert item["kind"] == "telegram_turn" and item["agent"] == "sales"


def test_the_collection_bot_still_collects_beside_the_agent_bot(tmp_path: Path) -> None:
    main, own, _ = two_bots(tmp_path, [], [])
    (collector,) = main.collectors
    collector._transport = FakeTransport([[update(9, OWNER, "看這篇 https://example.com/a")]])
    feature = Collecting()
    attach(main.collectors, FeatureSet([feature]), "host")
    assert asyncio.run(collector.poll_once()) == [(9, "answered")]
    assert [(i.kind, i.target) for i in feature.items] == [("link", "aidc")]
