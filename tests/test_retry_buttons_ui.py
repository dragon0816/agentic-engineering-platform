"""The 重試 buttons in a real browser (acceptance F20, 2026-11-06).

A chat turn whose model service answers 503 shows the Chinese explanation and 重試 under
the newest answer; pressing it sends the same question again, and the answer that comes
back takes its place. A BI AI panel whose last turn failed shows 重試, which puts the
person's request back (without the working domain's line) and sends it. Stub model only.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import pytest
from test_agent_web import served  # noqa: F401 - the server fixture
from test_turn_progress_web import ANSWER_TEXT, TRACE, _answered

from agent.gateway import GatewayConversationResult
from common.execution import Failure
from host_runtime.agent import LocalConversationOutcome
from host_runtime.web import AgentWebServer

DOWN = Failure(
    code="model_http_error",
    message="503: litellm.ServiceUnavailableError: Hosted_vllmException - <html>…",
    retryable=True,
)


def test_both_retry_buttons_send_the_request_again(
    served: AgentWebServer,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from integrations.browser import Browser

    asked: list[str] = []

    async def converse(request: Any, history: Any, **_: Any) -> LocalConversationOutcome:
        asked.append(request.message)
        result = (
            GatewayConversationResult(
                trace=TRACE,
                status="failed",
                text="The configured model could not answer this turn.",
                model_turns=1,
                failure=DOWN,
            )
            if len(asked) == 1
            else _answered(0)
        )
        return LocalConversationOutcome(
            trace=TRACE, ingress="local", actor=request.actor, conversation=result
        )

    monkeypatch.setattr(served.web.runtime.agent, "converse", converse)
    browser = Browser(tmp_path / "browser", timeout_s=60)
    browser.start()

    def wait(expression: str, seconds: float = 30) -> object:
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            value = browser._evaluate(expression)
            if value:
                return value
            time.sleep(0.2)
        raise AssertionError(expression)

    try:
        browser.navigate(served.address)
        wait('!document.getElementById("send").disabled')
        browser._evaluate(
            'document.getElementById("message").value = "整理今天的會議";'
            'document.getElementById("send").click()'
        )
        wait("!!document.querySelector('#log .retry-turn')")
        shown = str(browser._evaluate("document.getElementById('log').innerText"))
        assert "公司的模型服務現在沒有回應" in shown and "HTTP 503" in shown, shown
        browser._evaluate("document.querySelector('#log .retry-turn').click()")
        wait(f"document.getElementById('log').innerText.includes({json.dumps(ANSWER_TEXT)})")
        assert asked == ["整理今天的會議", "整理今天的會議"]
        # Only the newest answer can be retried, and it no longer failed.
        assert browser._evaluate("document.querySelectorAll('#log .retry-turn').length") == 0

        # The BI AI panel: its last turn failed, so 重試 puts the request back and sends it.
        session = {
            "turns": [
                {"role": "user", "text": "工作領域：aidc（來源資料夾 x）\n\n電源廠要建 Account"},
                {"role": "assistant", "sent": {}, "error": {"message": "模型太久沒有回應（逾時）"}},
            ]
        }
        browser._evaluate(
            "window.__sent = 0;"
            "document.getElementById('bi-ai-send').addEventListener('click',"
            " () => { window.__sent += 1; }, {capture: true});"
            f"biBuildSessionLog('bi-ai-log', {json.dumps(session)}, () => [])"
        )
        assert browser._evaluate(
            "[...document.querySelectorAll('#bi-ai-log button')]"
            ".some((b) => b.textContent === '重試')"
        )
        browser._evaluate(
            "[...document.querySelectorAll('#bi-ai-log button')]"
            ".find((b) => b.textContent === '重試').click()"
        )
        assert (
            browser._evaluate("document.getElementById('bi-ai-msg').value") == "電源廠要建 Account"
        )
        assert browser._evaluate("window.__sent") == 1
    finally:
        browser.close()
        browser.discard_profile()
