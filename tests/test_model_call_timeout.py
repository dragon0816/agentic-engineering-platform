"""One model call's timeout, and what the person reads when it runs out (acceptance F16/F20,
2026-11-06).

With the company model backend down, one call held a BI AI turn for 6 and then 10 minutes
whatever the turn's budget, since a turn's clock is checked only between calls. The chat and
the BI AI sessions now give one call `call_timeout_seconds` (default 180), drafting and
extraction keep `batch_timeout_seconds` (default 600), both in host.json `models`. Here a
server that accepts and never answers, and the Chinese replies with 重試.
"""

from __future__ import annotations

import socket
import threading
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError
from test_host_models import binding, configured, endpoint

from capabilities.bi_cards import sessions
from common.execution import TraceIdentifiers
from host_runtime.contracts import ModelBinding
from host_runtime.gateway_link import timeout_reply
from host_runtime.host import build_runtime
from models.catalog import ModelEndpoint
from models.contracts import ModelMessage, ModelRequest, ModelRequirements
from models.openai_compatible import OpenAICompatible


@pytest.fixture
def hanging() -> Iterator[str]:
    """A loopback server that accepts every connection and never answers."""
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen(8)
    held: list[socket.socket] = []
    stop = threading.Event()

    def accept() -> None:
        server.settimeout(0.2)
        while not stop.is_set():
            try:
                held.append(server.accept()[0])
            except OSError:
                continue

    thread = threading.Thread(target=accept, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.getsockname()[1]}/v1"
    stop.set()
    thread.join(2)
    for connection in held:
        connection.close()
    server.close()


def _request() -> ModelRequest:
    return ModelRequest(
        trace=TraceIdentifiers(trace_id="trace-t", request_id="request-t", span_id="span-t"),
        model_alias="company",
        messages=(ModelMessage(role="user", text="hi"),),
        requirements=ModelRequirements(),
    )


def test_the_defaults_are_180_for_the_conversation_and_600_for_batch_work() -> None:
    chosen = ModelBinding.model_validate(binding())
    assert (chosen.call_timeout_seconds, chosen.batch_timeout_seconds) == (180, 600)
    tuned = ModelBinding.model_validate(binding(call_timeout_seconds=90))
    assert tuned.call_timeout_seconds == 90
    for wrong in (0, 5, 4000, "180"):
        with pytest.raises(ValidationError):
            ModelBinding.model_validate(binding(call_timeout_seconds=wrong))


def test_a_call_to_a_server_that_never_answers_fails_model_timeout(hanging: str) -> None:
    client = OpenAICompatible(
        ModelEndpoint.model_validate(endpoint(base_url=hanging, credential=None)),
        credential=None,
        transport=None,
        timeout_s=0.5,
    )
    started = time.monotonic()
    answer = client.generate(_request())
    assert answer.failure is not None and answer.failure.code == "model_timeout"
    assert time.monotonic() - started < 5


def test_the_host_gives_chat_and_drafting_their_own_timeouts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AEP_LLM_TOKEN", "fixture-not-a-secret")
    config, layout = configured(tmp_path, call_timeout_seconds=90, batch_timeout_seconds=900)
    with build_runtime(config, layout=layout) as runtime:
        router = runtime.agent.gateway.router
        approved: Any = router.model  # ApprovedModelClient -> SelectableModelClient
        chat = approved.client
        assert chat.base.timeout_s == 90
        from capabilities.workflow_author.handlers import DRAFT_SPEC

        drafting: Any = runtime.agent.gateway.bridge.installed.get(DRAFT_SPEC.identity)
        assert drafting.handler.model.client.base.timeout_s == 900
        # Trial runs inside a BI AI turn use the conversation's client and its timeout.
        from capabilities.bi_cards.ai_runs import AiRuntime
        from host_runtime import bi_harness

        extraction = AiRuntime(model=lambda: None, background=lambda _t, work: work())
        tried: Any = bi_harness.turn_ai(runtime.agent.gateway, extraction).model()
        assert tried[0] is router.model
        assert approved.client.base.timeout_s == 90
        # Both follow the models the page approves, set on the chat's switch only.
        chat.approved = lambda: ["gpt-5.4-mini"]
        assert list(drafting.handler.model.client.approved()) == ["gpt-5.4-mini"]


def test_a_timed_out_turn_is_told_in_chinese_with_retry() -> None:
    reply = timeout_reply(ModelBinding.model_validate(binding()))
    assert reply.startswith("模型 3 分鐘內沒有回應") and "重試" in reply
    assert "model_timeout" not in reply
    odd = timeout_reply(ModelBinding.model_validate(binding(call_timeout_seconds=90)))
    assert "90 秒" in odd
    said = sessions.STOPPED["model_timeout"]
    assert "重試" in said and "model_timeout" not in said
