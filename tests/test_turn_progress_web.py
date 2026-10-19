"""The running turn's live progress in Agent Web and the guard stops' replies
(owner 2026-10-19). Fakes only: no model, no Gateway, no network."""

from __future__ import annotations

import json
import os
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from test_agent_web import base, fetch, served  # noqa: F401 - the server fixture

from agent import turn_progress
from agent.gateway import ConversationToolExecution, GatewayConversationResult, HostToolOutcome
from common.execution import TraceIdentifiers
from host_runtime.agent import LocalConversationOutcome
from host_runtime.web import AgentWebServer

TRACE = TraceIdentifiers(trace_id="trace-1", request_id="request-1", span_id="span-1")
SECRET_ARGUMENT = "argument-marker-7f3"
ANSWER_TEXT = "answer-marker-c41"
SHOTS = Path(__file__).resolve().parents[1] / ".scratch" / "turn-progress-ui"


def _answered(tools: int = 2) -> GatewayConversationResult:
    return GatewayConversationResult(
        trace=TRACE,
        status="answered",
        text=ANSWER_TEXT,
        model_turns=tools + 1,
        tools=tuple(
            ConversationToolExecution(
                call_id=f"c{index}",
                name="files__read",
                arguments={"path": SECRET_ARGUMENT},
                host=HostToolOutcome(status="succeeded", data={"text": "x"}),
            )
            for index in range(tools)
        ),
    )


def _running_turn(release: threading.Event, *, elapsed: int = 0) -> Callable[..., Any]:
    """A turn that reports progress the way the Gateway and a Harness do,
    then waits until the test releases it."""

    async def converse(request: Any, history: Any, **_: Any) -> LocalConversationOutcome:
        import asyncio

        progress = turn_progress.current()
        assert progress is not None, "the turn runs with its progress set"
        progress.started -= elapsed
        progress.set_limits(150, 1800)
        progress.harness_phase(
            "knowledge", ("collect_context", "execute", "validate"), "collecting", 0
        )
        progress.harness_phase(
            "knowledge", ("collect_context", "execute", "validate"), "executing", 0
        )
        progress.harness_phase(
            "knowledge", ("collect_context", "execute", "validate"), "validating", 0
        )
        progress.harness_phase(
            "knowledge", ("collect_context", "execute", "validate"), "collecting", 1
        )
        for index in range(12):
            name = "knowledge__vault" if index % 3 == 0 else "files__read"
            progress.tool_started(name)
            progress.tool_finished(name, "failed" if index == 4 else "succeeded")
        progress.tool_started("excel__read_workbook_with_a_rather_long_tool_name")
        await asyncio.to_thread(release.wait, 60)
        return LocalConversationOutcome(
            trace=TRACE, ingress="local", actor=request.actor, conversation=_answered()
        )

    return converse


def _session(url: str, token: str) -> str:
    created = fetch(url + "/api/conversations", token=token, body={}).json()
    session_id: str = created["conversation"]["session_id"]
    return session_id


def _progress(url: str, token: str, session_id: str) -> Any:
    return fetch(url + "/api/conversations/progress?session_id=" + session_id, token=token).json()


def _wait_for(read: Callable[[], Any], seconds: float = 20) -> Any:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        value = read()
        if value:
            return value
        time.sleep(0.05)
    raise AssertionError("timed out")


def test_the_progress_route_shows_a_running_turn_to_its_session_only(
    served: AgentWebServer,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    release = threading.Event()
    monkeypatch.setattr(served.web.runtime.agent, "converse", _running_turn(release))
    url, token = base(served), served.token
    session_id, other = _session(url, token), _session(url, token)
    assert _progress(url, token, session_id) == {"ok": True, "progress": None}
    finished: list[Any] = []
    turn = threading.Thread(
        target=lambda: finished.append(
            fetch(
                url + "/api/conversations/turn",
                token=token,
                body={"session_id": session_id, "message": "請整理九月訂單 " + SECRET_ARGUMENT},
            ).json()
        )
    )
    turn.start()
    try:
        shown = _wait_for(
            lambda: (
                (_progress(url, token, session_id)["progress"] or {}).get("tool_count") == 13
                and _progress(url, token, session_id)["progress"]
            )
        )
        assert shown["backend"] == "gateway"
        assert shown["tool_cap"] == 150 and shown["time_limit_s"] == 1800
        harness = shown["harness"]
        assert harness["domain"] == "knowledge" and harness["retry"] == 1
        assert [step["state"] for step in harness["steps"]] == [
            "done",
            "active",
            "waiting",
            "waiting",
        ]
        tools = shown["tools"]
        assert len(tools) == 8  # the recent lines; the count covers all
        assert tools[-1]["status"] == "running"
        assert {tool["status"] for tool in tools[:-1]} <= {"succeeded", "failed"}
        # Names, phases, counts and status only.
        dumped = json.dumps(shown, ensure_ascii=False)
        assert SECRET_ARGUMENT not in dumped and "九月" not in dumped
        assert ANSWER_TEXT not in dumped
        # Another session, and a session of nobody, show nothing.
        assert _progress(url, token, other)["progress"] is None
        assert _progress(url, token, "session-unknown")["progress"] is None
        # Without the page token there is no progress at all.
        assert fetch(url + "/api/conversations/progress?session_id=" + session_id).status == 401
    finally:
        release.set()
        turn.join(timeout=30)
    assert finished and finished[0]["answer"]["answer"].startswith(ANSWER_TEXT)
    # The turn ended: its progress is gone.
    assert _progress(url, token, session_id) == {"ok": True, "progress": None}


def test_the_progress_board_is_owned_by_the_actor_that_started_the_turn(
    served: AgentWebServer,  # noqa: F811
) -> None:
    web = served.web
    progress = turn_progress.TurnProgress(turn_id="t", session_id="s-1", owner="somebody-else")
    web.turn_progress.begin(progress)
    try:
        assert web.conversation_progress("s-1") == {"ok": True, "progress": None}
    finally:
        web.turn_progress.end(progress)


def test_an_agent_mode_tool_request_joins_the_running_turn(
    served: AgentWebServer,  # noqa: F811
) -> None:
    web = served.web
    progress = turn_progress.TurnProgress(
        turn_id="t", session_id="s-2", owner=web.runtime.actor, backend="claude_code"
    )
    web.turn_progress.begin(progress)
    try:
        assert web.agent_mode.observer is not None
        web.agent_mode.observer("s-2", "Bash", "waiting")
        web.agent_mode.observer("s-2", "Bash", "allowed")
        web.agent_mode.observer("s-2", "Write", "refused")
        web.agent_mode.observer("s-3", "Read", "allowed")  # another session: ignored
        shown = web.conversation_progress("s-2")["progress"]
        assert shown["tool_count"] == 2 and shown["tool_cap"] is None
        assert [(tool["name"], tool["status"]) for tool in shown["tools"]] == [
            ("Bash", "allowed"),
            ("Write", "refused"),
        ]
    finally:
        web.turn_progress.end(progress)


# -- the progress view in a real browser ----------------------------------------------------


def _browser_missing() -> bool:
    from integrations.browser import browser_path

    return browser_path() is None


@pytest.mark.skipif(_browser_missing(), reason="no Chromium browser is installed")
def test_the_progress_view_replaces_working_in_a_real_browser(
    served: AgentWebServer,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from integrations.browser import Browser

    release = threading.Event()
    monkeypatch.setattr(served.web.runtime.agent, "converse", _running_turn(release, elapsed=185))
    browser = Browser(tmp_path / "browser", timeout_s=60)
    browser.start()
    shots = Path(os.environ.get("AEP_UI_SHOTS") or SHOTS)
    shots.mkdir(parents=True, exist_ok=True)

    def wait(expression: str, seconds: float = 30) -> object:
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            value = browser._evaluate(expression)
            if value:
                return value
            time.sleep(0.2)
        raise AssertionError(expression)

    def no_side_scroll() -> None:
        assert not browser._evaluate(
            "document.documentElement.scrollWidth > document.documentElement.clientWidth"
        )

    box = ".turn-progress"
    try:
        browser.navigate(served.address)
        wait('!document.getElementById("send").disabled')
        browser._evaluate(
            'document.getElementById("message").value = "請整理九月訂單";'
            'document.getElementById("send").click()'
        )
        wait(f"!!document.querySelector({json.dumps(box)})")
        wait(f'document.querySelector("{box} .tp-meter").textContent.startsWith("工具 13/150")')
        shown = str(browser._evaluate(f"document.querySelector({json.dumps(box)}).innerText"))
        for words in (
            "Knowledge：查資料（第 2 輪）…",
            "① 規劃 ✓",
            "② 查資料（第 2 輪）…",
            "③ 執行",
            "④ 驗收",
            "excel__read_workbook_with_a_rather_long_tool_name",
            "工具 13/150 · 3:0",
            "/ 30:00",
        ):
            assert words in shown, (words, shown)
        assert "working…" not in shown
        assert (
            browser._evaluate(
                f'document.querySelector("{box} .tp-status").getAttribute("aria-live")'
            )
            == "polite"
        )
        # Only the four most recent tool lines are drawn.
        assert browser._evaluate(f'document.querySelectorAll("{box} .tp-tools li").length') == 4
        # The view holds no buttons, so no touch target to size.
        assert browser._evaluate(f'document.querySelectorAll("{box} button").length') == 0
        no_side_scroll()
        browser.screenshot(shots / "turn-progress-light.png")
        light = browser._evaluate(
            f"getComputedStyle(document.querySelector({json.dumps(box)})).backgroundColor"
        )
        browser.page().call(
            "Emulation.setEmulatedMedia",
            features=[{"name": "prefers-color-scheme", "value": "dark"}],
        )
        dark = browser._evaluate(
            f"getComputedStyle(document.querySelector({json.dumps(box)})).backgroundColor"
        )
        assert light != dark, (light, dark)
        no_side_scroll()
        browser.screenshot(shots / "turn-progress-dark.png")
        browser.page().call(
            "Emulation.setDeviceMetricsOverride",
            width=390,
            height=844,
            deviceScaleFactor=1,
            mobile=True,
        )
        time.sleep(1.5)  # a poll redraws at the narrow width
        browser._evaluate(
            f"document.querySelector({json.dumps(box)}).scrollIntoView({{block: 'center'}})"
        )
        no_side_scroll()
        width = browser._evaluate(
            f"document.querySelector({json.dumps(box)}).getBoundingClientRect().right"
        )
        assert isinstance(width, int | float) and width <= 390, width
        browser.screenshot(shots / "turn-progress-narrow-dark.png")
        # The turn finishes: polling stops and the answer replaces the view.
        release.set()
        wait(f"!document.querySelector({json.dumps(box)})")
        wait(f"document.getElementById('log').innerText.includes({json.dumps(ANSWER_TEXT)})")
        browser.screenshot(shots / "turn-progress-answered.png")
    finally:
        release.set()
        browser.close()
        browser.discard_profile()
