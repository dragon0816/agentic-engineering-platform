"""The guard stops' replies in Telegram (owner 2026-10-19). Fakes only: no Bot
API, no model, no network."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path

from test_telegram_ingress import OWNER, FakeTransport, ingress, poll, update

from agent.backend_contracts import ConversationLimits
from models.contracts import ModelRequest, ModelResponse, ModelStreamEvent, ModelToolCall


class Scripted:
    def __init__(self, script: Callable[[int], ModelResponse | list[ModelToolCall]]) -> None:
        self.script = script
        self.turns = 0

    def generate(self, request: ModelRequest) -> ModelResponse:
        self.turns += 1
        reply = self.script(self.turns)
        if isinstance(reply, list):
            return ModelResponse(
                trace=request.trace,
                model_alias=request.model_alias,
                text="",
                tool_calls=tuple(reply),
            )
        return reply.model_copy(update={"trace": request.trace, "model_alias": request.model_alias})

    def stream(self, request: ModelRequest) -> Iterator[ModelStreamEvent]:
        raise NotImplementedError


def test_a_repeat_stop_says_so_and_keeps_the_record_for_continue(tmp_path: Path) -> None:
    transport = FakeTransport([[update(1, OWNER, "do it")]])
    item, agent, _ = ingress(tmp_path, transport)
    agent.gateway.router.model = Scripted(
        lambda n: [ModelToolCall(call_id=f"c{n}", name="admin__shell", arguments={})]
    )
    delivery = poll(item).deliveries[0]
    (reply,) = transport.sent()
    assert "重複呼叫" in reply and "用了 3 次工具呼叫" in reply
    assert reply.endswith("回覆「繼續」我會接著做。")
    assert delivery.disposition == "answered"
    (history,) = item._histories.values()
    assert "[工具紀錄]" in history[-1].text and "tool_repeat_limit" in history[-1].text
    assert transport.statuses()[-1].startswith("⚠️ Stopped")


def test_a_time_stop_names_the_limit(tmp_path: Path) -> None:
    clock = {"now": 0.0}

    def script(n: int) -> list[ModelToolCall]:
        clock["now"] += 70  # each model reply takes seventy seconds
        return [ModelToolCall(call_id=f"c{n}", name="admin__probe", arguments={"n": n})]

    transport = FakeTransport([[update(1, OWNER, "do it")]])
    item, agent, _ = ingress(tmp_path, transport)
    agent.gateway.router.model = Scripted(script)
    agent.gateway.clock = lambda: clock["now"]
    agent.gateway.conversation_limits = lambda: ConversationLimits(time_limit_seconds=120)
    poll(item)
    (reply,) = transport.sent()
    assert "已用完 2 分鐘的時間上限" in reply and "回覆「繼續」我會接著做" in reply


def test_the_loop_limit_reply_is_unchanged(tmp_path: Path) -> None:
    transport = FakeTransport([[update(1, OWNER, "do it")]])
    item, agent, _ = ingress(tmp_path, transport)
    agent.gateway.router.model = Scripted(
        lambda n: [ModelToolCall(call_id=f"c{n}", name="admin__probe", arguments={"n": n})]
    )
    agent.gateway.conversation_limits = lambda: ConversationLimits(tool_calls=4)
    poll(item)
    assert transport.sent() == [
        "這個回合已用完 4 次工具呼叫，工作還沒完成；回覆「繼續」我會接著做。"
    ]
