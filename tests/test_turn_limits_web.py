"""The guard stops' replies in Agent Web and the per-turn limits as Settings
(owner 2026-10-19). Fakes only: no model, no Gateway, no network."""

from __future__ import annotations

from typing import Any

import pytest
from test_agent_web import base, fetch, served  # noqa: F401 - the server fixture

from agent.gateway import ConversationToolExecution, GatewayConversationResult
from common.execution import Failure, TraceIdentifiers
from host_runtime.agent import LocalConversationOutcome
from host_runtime.conversation_context import ConversationContextSettings
from host_runtime.web import AgentWebServer

TRACE = TraceIdentifiers(trace_id="trace-1", request_id="request-1", span_id="span-1")


def _session(url: str, token: str) -> str:
    created = fetch(url + "/api/conversations", token=token, body={}).json()
    session_id: str = created["conversation"]["session_id"]
    return session_id


def _stopped(code: str, tools: int) -> GatewayConversationResult:
    return GatewayConversationResult(
        trace=TRACE,
        status="needs_input",
        text="x",
        model_turns=tools,
        tools=tuple(
            ConversationToolExecution(
                call_id=f"c{index}",
                name="files__read",
                failure=Failure(code="not_found", message="no"),
            )
            for index in range(tools)
        ),
        failure=Failure(code=code, message="stopped"),
    )


@pytest.mark.parametrize(
    ("code", "words"),
    [
        ("tool_loop_limit", ["已用完 4 次工具呼叫", "回覆「繼續」我會接著做"]),
        ("tool_repeat_limit", ["重複呼叫", "用了 4 次工具呼叫", "回覆「繼續」我會接著做"]),
        ("turn_time_limit", ["已用完 30 分鐘的時間上限", "回覆「繼續」我會接著做"]),
    ],
)
def test_a_guard_stop_says_what_happened_and_keeps_the_record(
    served: AgentWebServer,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
    code: str,
    words: list[str],
) -> None:
    async def converse(request: Any, history: Any, **_: Any) -> LocalConversationOutcome:
        return LocalConversationOutcome(
            trace=TRACE, ingress="local", actor=request.actor, conversation=_stopped(code, 4)
        )

    monkeypatch.setattr(served.web.runtime.agent, "converse", converse)
    url, token = base(served), served.token
    session_id = _session(url, token)
    reply = fetch(
        url + "/api/conversations/turn",
        token=token,
        body={"session_id": session_id, "message": "請整理九月訂單"},
    ).json()
    answer = reply["answer"]["answer"]
    for expected in words:
        assert expected in answer, (expected, answer)
    assert "目前做到的步驟已記錄在這段對話中" in answer
    stored = reply["conversation"]["messages"][-1]
    assert code in stored["tool_summary"]


def test_the_limits_are_settings_with_defaults_and_bounds(
    served: AgentWebServer,  # noqa: F811
) -> None:
    url, token = base(served), served.token
    settings = fetch(url + "/api/settings", token=token).json()
    assert settings["context"]["tool_call_limit"] == 150
    assert settings["context"]["turn_time_limit_minutes"] == 30
    saved = fetch(
        url + "/api/settings/context",
        token=token,
        body={
            "recent_messages": 12,
            "history_budget_bytes": 48_000,
            "tool_call_limit": 40,
            "turn_time_limit_minutes": 10,
        },
    ).json()
    assert saved["context"]["tool_call_limit"] == 40
    limits = served.web.conversation_context.limits()
    assert limits.tool_calls == 40 and limits.time_limit_seconds == 600
    for field, bad in (("tool_call_limit", 151), ("tool_call_limit", 0)):
        refused = fetch(
            url + "/api/settings/context",
            token=token,
            body={"recent_messages": 12, "history_budget_bytes": 48_000, field: bad},
        )
        assert refused.status == 400
    assert served.web.conversation_context.limits().tool_calls == 40
    # A settings file from before the limits keeps loading, with the defaults.
    old = ConversationContextSettings.model_validate(
        {"recent_messages": 12, "history_budget_bytes": 48_000}
    )
    assert old.limits().tool_calls == 150 and old.limits().time_limit_seconds == 1800
