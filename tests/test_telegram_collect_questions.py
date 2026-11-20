"""A BI collection bot also answers questions (owner 2026-11-21, docs/DECISIONS.md).

A link or a file is collected exactly as before and not answered; a plain question
(no link, no file, not a `/` command) is one conversation turn on the Host's Agent
offered only the tool the feature scopes to the bot's domain (`bi__query` with the
domain's dataset), with the domain guidance, in a session of its own
(`telegram-collect-<name>-chat-<id>`). Without the tool the person gets a clear
Chinese message, never a generic model answer. Built by the Host's own
`attach_telegram_bots` over the fake transport of the ingress tests; no socket.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

from test_telegram_ingress import OWNER, STRANGER, TOKEN, CountingCredentials, FakeTransport, update
from test_telegram_ingress import ingress as make_ingress

from agent.gateway import HostTool, HostToolOutcome
from channels.telegram import TelegramIngress
from channels.telegram_collect import (
    NO_ANSWERS,
    NO_QUERY_TOOL,
    TelegramCollector,
    attach,
    is_question,
)
from common.execution import RequestContext
from host_runtime.features import (
    Feature,
    FeatureSet,
    TelegramAnswer,
    TelegramItem,
    TelegramQuestion,
)
from host_runtime.host import attach_telegram_bots
from models.contracts import (
    ModelRequest,
    ModelResponse,
    ModelStreamEvent,
    ModelTool,
    ModelToolCall,
)

COLLECT_TOKEN = "5555555555:AAG" + "z" * 32
DATASET = "vault-aidc"


class Asking:
    """A model that calls `bi__query` once, then answers from what it returned."""

    def __init__(self) -> None:
        self.requests: list[ModelRequest] = []

    def generate(self, request: ModelRequest) -> ModelResponse:
        self.requests.append(request)
        results = [m for m in request.messages if m.role == "tool"]
        if not results:
            return ModelResponse(
                trace=request.trace,
                model_alias=request.model_alias,
                tool_calls=(
                    ModelToolCall(
                        call_id="q1",
                        name="bi__query",
                        arguments={"text": "液冷", "dataset": "demo"},
                    ),
                ),
            )
        return ModelResponse(
            trace=request.trace,
            model_alias=request.model_alias,
            text="AIDC 液冷有兩張卡片 [卡片 Trend:液冷]",
        )

    def stream(self, request: ModelRequest) -> Iterator[ModelStreamEvent]:
        raise NotImplementedError


class Domain(Feature):
    """A BI-like feature: collects items, and scopes a fake query to its dataset."""

    name = "bi-knowledge"

    def __init__(self, *, tool: bool = True) -> None:
        self.items: list[TelegramItem] = []
        self.calls: list[dict[str, Any]] = []
        self.contexts: list[RequestContext] = []
        self.tool = tool

    def telegram_item(self, item: TelegramItem, host: Any) -> TelegramAnswer | None:
        self.items.append(item)
        return TelegramAnswer(f"已收進 AIDC（{item.kind}）")

    def telegram_question(
        self, item: TelegramItem, host: Any, gateway: Any
    ) -> TelegramQuestion | TelegramAnswer | None:
        if not self.tool:
            return None

        async def query(context: RequestContext, arguments: dict[str, Any]) -> HostToolOutcome:
            self.contexts.append(context)
            self.calls.append({**arguments, "dataset": DATASET})
            return HostToolOutcome(status="succeeded", data={"cards": [{"card": "Trend:液冷"}]})

        tool = HostTool(
            ModelTool(
                name="bi__query",
                description="Search the BI knowledge cards (read only)",
                input_contract="host.bi__query.v1",
                input_schema={"type": "object", "properties": {}, "required": []},
            ),
            query,
        )
        return TelegramQuestion(tools=(tool,), guidance="Answer from the AIDC domain's BI cards.")


def collection_bot() -> dict[str, Any]:
    return {
        "name": "bi_aidc",
        "credential": {"name": "telegram_bi_aidc"},
        "feature": "bi-knowledge",
        "target": "aidc",
        "senders": [{"sender_id": OWNER, "actor": "engineer"}],
    }


def setup(
    tmp_path: Path, batch: list[dict[str, Any]], feature: Feature, *, model: Any = None
) -> tuple[TelegramCollector, FakeTransport, Asking]:
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True)
    resolver = CountingCredentials({"telegram_bot": TOKEN, "telegram_bi_aidc": COLLECT_TOKEN})
    main, agent, _ = make_ingress(
        tmp_path, FakeTransport([]), resolver=resolver, collection_bots=[collection_bot()]
    )
    asking = Asking()
    agent.gateway.router.model = model if model is not None else asking
    attach_telegram_bots(
        cast(Any, SimpleNamespace(credential_environment=dict)),
        cast(Any, SimpleNamespace(workspace_root=workspace)),
        main,
        main.config,
        resolver,
    )
    (collector,) = main.collectors
    transport = FakeTransport([batch])
    collector._transport = transport
    assert isinstance(collector.asker, TelegramIngress)
    collector.asker._transport = transport
    attach(main.collectors, FeatureSet([feature]), "host")
    return collector, transport, asking


def run(collector: TelegramCollector) -> list[tuple[int, str]]:
    return asyncio.run(collector.poll_once())


def actions(transport: FakeTransport) -> list[str]:
    return [p["action"] for url, p in transport.calls if url.endswith("/sendChatAction")]


def test_a_question_is_answered_through_the_scoped_bi_query(tmp_path: Path) -> None:
    feature = Domain()
    collector, transport, model = setup(
        tmp_path, [update(1, OWNER, "AIDC 液冷有哪些趨勢？")], feature
    )
    assert run(collector) == [(1, "answered")]
    assert transport.sent()[-1] == "AIDC 液冷有兩張卡片 [卡片 Trend:液冷]"
    # Only the scoped query was offered, with the domain guidance, and it ran scoped.
    first = model.requests[0]
    assert {tool.name for tool in first.tools} == {"bi__query"}
    assert "Answer from the AIDC domain's BI cards." in first.messages[0].text
    assert feature.calls == [{"text": "液冷", "dataset": DATASET}]
    # Nothing was collected; the answer's session is the bot's own per chat.
    assert feature.items == []
    assert feature.contexts[0].session_id == f"telegram-collect-bi_aidc-chat-{OWNER}"
    # 「正在輸入…」 while it was answered, through this bot.
    assert "typing" in actions(transport)
    assert all(COLLECT_TOKEN in url for url, _ in transport.calls)


def test_a_link_is_collected_and_not_answered(tmp_path: Path) -> None:
    feature = Domain()
    batch = [update(1, OWNER, "這篇在講液冷嗎？ https://www.threads.net/@x/post/1")]
    collector, transport, model = setup(tmp_path, batch, feature)
    assert run(collector) == [(1, "answered")]
    assert [item.kind for item in feature.items] == ["link"]
    assert transport.sent() == ["已收進 AIDC（link）"]
    assert model.requests == [] and feature.calls == []


def test_a_file_is_collected_and_not_answered(tmp_path: Path) -> None:
    feature = Domain()
    collector, transport, model = setup(tmp_path, [update(1, OWNER, None)], feature)
    assert run(collector) == [(1, "answered")]
    assert [item.kind for item in feature.items] == ["file"]
    assert transport.sent() == ["已收進 AIDC（file）"]
    assert model.requests == []


def test_commands_and_replies_to_item_messages_are_still_collected(tmp_path: Path) -> None:
    feature = Domain()
    reply = update(2, OWNER, "這是全文")
    reply["message"]["reply_to_message"] = {"message_id": 9, "text": "#1 只取得摘要"}
    collector, transport, model = setup(tmp_path, [update(1, OWNER, "/links"), reply], feature)
    assert run(collector) == [(1, "answered"), (2, "answered")]
    assert [item.kind for item in feature.items] == ["text", "reply"]
    assert model.requests == []


def test_an_unknown_sender_is_ignored(tmp_path: Path) -> None:
    feature = Domain()
    collector, transport, model = setup(tmp_path, [update(1, STRANGER, "液冷？")], feature)
    assert run(collector) == [(1, "unmapped_sender")]
    assert transport.sent() == [] and model.requests == [] and feature.items == []


def test_without_the_query_tool_the_bot_says_so_and_no_model_is_asked(tmp_path: Path) -> None:
    feature = Domain(tool=False)
    collector, transport, model = setup(tmp_path, [update(1, OWNER, "液冷有哪些趨勢？")], feature)
    assert run(collector) == [(1, "answered")]
    assert transport.sent() == [NO_QUERY_TOOL]
    assert model.requests == []


def test_without_the_conversation_path_the_bot_says_so(tmp_path: Path) -> None:
    feature = Domain()
    collector, transport, model = setup(tmp_path, [update(1, OWNER, "液冷有哪些趨勢？")], feature)
    collector.asker = None
    assert run(collector) == [(1, "answered")]
    assert transport.sent() == [NO_ANSWERS]
    assert model.requests == []


def test_what_counts_as_a_question() -> None:
    def item(kind: str, text: str, quoted: str | None = None) -> TelegramItem:
        return TelegramItem(
            feature="bi-knowledge",
            bot="bi_aidc",
            target="aidc",
            kind=kind,  # type: ignore[arg-type]
            actor="engineer",
            text=text,
            received_at=datetime.now(UTC),
            quoted=quoted,
        )

    assert is_question(item("text", "液冷有哪些趨勢？"))
    assert is_question(item("reply", "那 CPO 呢？", quoted="AIDC 液冷有兩張卡片"))
    assert not is_question(item("reply", "全文", quoted="已收進 AIDC（#12）只取得摘要"))
    assert not is_question(item("text", "/links"))
    assert not is_question(item("link", "看 https://example.com/a"))
    assert not is_question(item("file", ""))


def test_the_settings_form_says_the_bot_collects_and_answers() -> None:
    from host_runtime.web_page import PAGE

    form = PAGE.split('id="collect-form"', 1)[1].split("</form>", 1)[0]
    assert "傳連結或檔案給它就收進這個領域" in form
    assert "從這個領域的 BI 卡片回答" in form


def test_the_bot_form_sets_its_collect_time_in_the_same_save() -> None:
    from host_runtime.web_page import PAGE

    form = PAGE.split('id="collect-form"', 1)[1].split("</form>", 1)[0]
    assert '<input id="collect-time" type="time" value="18:00">' in form
    # The domain is checked before the bot is written, then the time is saved.
    assert "await collectTime({...timed, dry_run: true})" in PAGE
    assert '"/api/bi/inbox/bot-time"' in PAGE
    # The Agents table row shows the 收集時間 and the next run.
    assert '"・收集時間 " + timed.collect_at' in PAGE
