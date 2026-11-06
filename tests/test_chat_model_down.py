"""A chat turn when the company model service is down (acceptance F20, 2026-11-06).

The gateway answered 503 in about 21 s, but the page took about 4 minutes to say so, gave no
cause and no 重試. Here a model that answers 503 at once: the turn asks it once, the reply says
in Chinese that the model service is not answering, and the answer is marked failed so the
page offers 重試.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from typing import Any

from test_business_cards_conversation import _turn, web  # noqa: F401 - fixture

from common.execution import Failure
from models import wire
from models.contracts import ModelRequest, ModelResponse, ModelStreamEvent


class Down:
    """The gateway when its upstream is not serving: 503 with an HTML page, at once."""

    def __init__(self) -> None:
        self.calls = 0

    def generate(self, request: ModelRequest) -> ModelResponse:
        self.calls += 1
        return wire.failed_response(
            request,
            Failure(
                code="model_http_error",
                message="503: litellm.ServiceUnavailableError: Hosted_vllmException - <html>…",
                retryable=True,
            ),
        )

    def stream(self, request: ModelRequest) -> Iterator[ModelStreamEvent]:
        raise NotImplementedError


def test_a_503_reaches_the_person_at_once_in_chinese(web: Any) -> None:  # noqa: F811
    agent_web, _ = web
    down = Down()
    agent_web.runtime.agent.gateway.router.model = down
    session = agent_web.create_conversation()["conversation"]["session_id"]
    started = time.monotonic()
    replied = _turn(agent_web, session, "整理一下今天的會議")
    assert time.monotonic() - started < 30
    assert down.calls <= 2, down.calls
    answer = replied["answer"]["answer"]
    assert "模型服務" in answer and "重試" in answer, answer
    assert "503" in answer  # the cause, for whoever helps
    assert replied["answer"]["status"] == "failed"  # the page offers 重試 on it
