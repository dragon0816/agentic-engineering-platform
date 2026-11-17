"""A message sent before the page can send it (acceptance F26, 2026-11-06).

Right after the page opened, Enter did nothing: the text stayed in the box and no run
started, because the conversation was not loaded yet (the backends' sign-in check can take
a minute). Here that check is slowed: Enter at once keeps the text, says why it waits, and
sends it once ready, exactly once. Stub model only.
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any

import pytest
from test_agent_web import served  # noqa: F401 - the server fixture
from test_turn_progress_web import ANSWER_TEXT, TRACE, _answered

from host_runtime.agent import LocalConversationOutcome
from host_runtime.web import AgentWebServer

ASKED = "整理一下今天的會議"


def test_enter_before_the_page_is_ready_sends_once_it_is(
    served: AgentWebServer,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from integrations.browser import Browser

    web = served.web
    checked = web.conversation_backends
    checking = threading.Event()
    release = threading.Event()

    def slow_backends() -> Any:
        checking.set()
        assert release.wait(30)
        return checked()

    monkeypatch.setattr(web, "conversation_backends", slow_backends)
    asked: list[str] = []

    async def converse(request: Any, history: Any, **_: Any) -> LocalConversationOutcome:
        asked.append(request.message)
        return LocalConversationOutcome(
            trace=TRACE, ingress="local", actor=request.actor, conversation=_answered(0)
        )

    monkeypatch.setattr(web.runtime.agent, "converse", converse)
    browser = Browser(tmp_path / "browser", timeout_s=60)
    browser.start()

    def wait(expression: str, seconds: float = 30) -> object:
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            value = browser._evaluate(expression)
            if value:
                return value
            time.sleep(0.1)
        raise AssertionError(expression)

    try:
        browser.navigate(served.address)
        wait("!!document.getElementById('message')")
        assert checking.wait(10)
        assert browser._evaluate("document.getElementById('send').disabled")
        browser._evaluate(
            f"const f = document.getElementById('message'); f.value = {json.dumps(ASKED)};"
            "f.dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter', bubbles: true}));"
            # The delayed loading notice arrives after Enter queued the message.
            "sendWait(true);"
        )
        # Not silent: the text stays and the page says it will be sent.
        note = str(wait("document.getElementById('send-wait').textContent"))
        assert "準備好後會自動送出" in note, note
        assert browser._evaluate("document.getElementById('message').value") == ASKED
        assert asked == []
        # Once ready it goes, once.
        release.set()
        wait(f"document.getElementById('log').innerText.includes({json.dumps(ANSWER_TEXT)})")
        assert asked == [ASKED]
        assert browser._evaluate("document.getElementById('message').value") == ""
        assert browser._evaluate("document.getElementById('send-wait').hidden")
    finally:
        release.set()
        browser.close()
        browser.discard_profile()
