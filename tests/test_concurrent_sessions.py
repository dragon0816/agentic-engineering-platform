"""Concurrent sessions: different sessions run in parallel, one session's
turns queue in order, and effectful Bridge work stays serialized."""

from __future__ import annotations

import asyncio
import json
import threading
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from test_conversation_turn_groups import _chat_config, _ChatGateway
from test_dispatch import Input, Output, grant, invocation, spec
from test_host_models import GatewayReply

from capabilities.runtime import InstalledCapabilities, LocalPolicy
from common.assets import ExecutionDependencies
from common.base import Contract
from common.execution import RequestContext
from host_runtime.conversations import ConversationFeedbackRequest, ConversationTurnRequest
from host_runtime.host import build_runtime
from host_runtime.web import AgentWeb
from workflow.dispatch import BridgeExecutor


class _SlowGateway(_ChatGateway):
    """Holds any request whose last user message mentions "slow"."""

    def __init__(self) -> None:
        super().__init__()
        self.entered = threading.Event()
        self.release = threading.Event()

    def send(
        self, url: str, body: bytes, headers: Mapping[str, str], timeout_s: float
    ) -> GatewayReply:
        messages = json.loads(body)["messages"]
        if "slow" in str(messages[-1].get("content")):
            self.entered.set()
            assert self.release.wait(15)
        return super().send(url, body, headers, timeout_s)


def _turn(
    web: AgentWeb, session: str, message: str, into: list[dict[str, Any]]
) -> threading.Thread:
    thread = threading.Thread(
        target=lambda: into.append(
            web.conversation_turn(ConversationTurnRequest(session_id=session, message=message))
        ),
        daemon=True,
    )
    thread.start()
    return thread


def test_a_slow_turn_does_not_block_another_session(tmp_path: Path) -> None:
    config, layout = _chat_config(tmp_path)
    transport = _SlowGateway()
    with build_runtime(config, layout=layout, model_transport=transport) as runtime:
        web = AgentWeb(runtime)
        first = web.create_conversation()["conversation"]["session_id"]
        second = web.create_conversation()["conversation"]["session_id"]
        slow: list[dict[str, Any]] = []
        thread = _turn(web, first, "slow question", slow)
        try:
            assert transport.entered.wait(10)
            started = time.monotonic()
            fast = web.conversation_turn(
                ConversationTurnRequest(session_id=second, message="fast question")
            )
            assert fast["ok"] is True and time.monotonic() - started < 10
            assert thread.is_alive()
            # Managing sessions does not wait for the running turn either.
            assert web.create_conversation()["conversation"]["session_id"]
        finally:
            transport.release.set()
            thread.join(15)
        assert slow[0]["ok"] is True


def test_one_session_runs_its_turns_in_order(tmp_path: Path) -> None:
    config, layout = _chat_config(tmp_path)
    transport = _SlowGateway()
    with build_runtime(config, layout=layout, model_transport=transport) as runtime:
        web = AgentWeb(runtime)
        session = web.create_conversation()["conversation"]["session_id"]
        results: list[dict[str, Any]] = []
        first = _turn(web, session, "slow question", results)
        assert transport.entered.wait(10)
        second = _turn(web, session, "second question", results)
        time.sleep(0.5)
        sent = [json.dumps(call["messages"]) for call in transport.calls]
        assert not any("second question" in item for item in sent)
        transport.release.set()
        first.join(15)
        second.join(15)
        messages = web.conversations(session)["selected"]["messages"]
        assert [item["text"] for item in messages] == [
            "slow question",
            "ok",
            "second question",
            "ok",
        ]


def test_rating_during_a_running_turn_survives_its_save(tmp_path: Path) -> None:
    config, layout = _chat_config(tmp_path)
    transport = _SlowGateway()
    with build_runtime(config, layout=layout, model_transport=transport) as runtime:
        web = AgentWeb(runtime)
        session = web.create_conversation()["conversation"]["session_id"]
        web.conversation_turn(ConversationTurnRequest(session_id=session, message="hello"))
        answer_id = web.conversations(session)["selected"]["messages"][1]["message_id"]
        results: list[dict[str, Any]] = []
        thread = _turn(web, session, "slow question", results)
        try:
            assert transport.entered.wait(10)
            rated = web.conversation_feedback(
                ConversationFeedbackRequest(
                    session_id=session,
                    message_id=answer_id,
                    rating="up",
                    note="clear",
                )
            )
            assert rated["ok"] is True
        finally:
            transport.release.set()
            thread.join(15)
        assert results[0]["ok"] is True
        messages = web.conversations(session)["selected"]["messages"]
        assert len(messages) == 4
        assert messages[1]["feedback"]["rating"] == "up"


# -- Bridge ---------------------------------------------------------------------


class _Overlap:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.active = 0
        self.peak = 0

    async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
        assert isinstance(inputs, Input)
        with self.lock:
            self.active += 1
            self.peak = max(self.peak, self.active)
        await asyncio.sleep(0.4)
        with self.lock:
            self.active -= 1
        return Output(count=inputs.count)


def _peak(side_effect: str) -> int:
    handler = _Overlap()
    registry = InstalledCapabilities()
    registry.register(
        spec().model_copy(update={"side_effect": side_effect}),
        handler,
        Input,
        Output,
        ExecutionDependencies(central_required=False),
    )
    bridge = BridgeExecutor(registry, LocalPolicy((grant(),)))
    results: list[Any] = []
    threads = [
        threading.Thread(target=lambda: results.append(asyncio.run(bridge.execute(invocation()))))
        for _ in range(2)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(10)
    assert [result.status for result in results] == ["succeeded", "succeeded"]
    return handler.peak


def test_bridge_serializes_effectful_calls_across_threads_but_not_reads() -> None:
    assert _peak("write") == 1
    assert _peak("external_side_effect") == 1
    assert _peak("read") == 2


def test_the_page_queues_turns_per_session_without_locking_the_input() -> None:
    from host_runtime.web_page import PAGE

    script = PAGE.split("<script>", 1)[1].split("</script>", 1)[0]
    submit = script.split('form.addEventListener("submit"', 1)[1].split("\n});\n", 1)[0]
    assert "field.disabled" not in submit and "send.disabled" not in submit
    assert "sessionChains.get(session)" in submit and ".then(run, run)" in submit
    queue = script.split("// -- Turn queues", 1)[1].split("// -- end Turn queues", 1)[0]
    for unsafe in ("innerHTML", "insertAdjacentHTML", "outerHTML"):
        assert unsafe not in queue
    assert "renderPendingTurns(record.session_id)" in script
