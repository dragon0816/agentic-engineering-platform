"""Tool records carried across conversation turns (owner decision 2026-10-07)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError
from test_agent_web import base, fetch, served  # noqa: F401 - the server fixture

from agent.gateway import ConversationToolExecution, GatewayConversationResult, HostToolOutcome
from common.execution import Failure, TraceIdentifiers
from host_runtime.agent import LocalConversationOutcome
from host_runtime.conversations import ConversationMessage
from host_runtime.turn_summary import tool_summary
from host_runtime.web import AgentWebServer, with_tools

TRACE = TraceIdentifiers(trace_id="trace-1", request_id="request-1", span_id="span-1")


def result(**changes: Any) -> GatewayConversationResult:
    tools = (
        ConversationToolExecution(
            call_id="c1",
            name="browser__operate",
            host=HostToolOutcome(
                status="succeeded",
                data={
                    "url": "http://site/orders",
                    "downloads": ["d.csv"],
                    "page": "SECRET PAGE TEXT " * 50,
                    "data": {"rows": [1]},
                },
            ),
        ),
        ConversationToolExecution(
            call_id="c2",
            name="authoring__run_workflow",
            host=HostToolOutcome(
                status="awaiting_approval", data={"approval_id": "ap-1", "summary": "x"}
            ),
        ),
        ConversationToolExecution(
            call_id="c3",
            name="admin__shell",
            failure=Failure(code="uninstalled_tool", message="no"),
        ),
    )
    return GatewayConversationResult.model_validate(
        {
            "trace": TRACE,
            "status": "needs_input",
            "text": "x",
            "model_turns": 4,
            "tools": tools,
            "failure": Failure(code="tool_loop_limit", message="stopped"),
            **changes,
        }
    )


def test_the_summary_keeps_what_a_continuation_needs_and_no_page_text() -> None:
    text = tool_summary(result())
    assert text is not None
    assert "browser__operate: succeeded" in text and "d.csv" in text and '"read": ["rows"]' in text
    assert "ap-1" in text and "uninstalled_tool" in text and "tool_loop_limit" in text
    assert "SECRET PAGE TEXT" not in text
    assert tool_summary(result(tools=(), failure=None, status="answered")) is None


def test_only_an_answer_carries_a_record_and_the_model_reads_it_with_the_text() -> None:
    now = datetime.now(UTC)
    answer = ConversationMessage(
        message_id="m2",
        role="assistant",
        text="done",
        created_at=now,
        status="answered",
        tool_summary="- coding__run: succeeded",
    )
    assert with_tools(answer) == "done\n\n[工具紀錄]\n- coding__run: succeeded"
    with pytest.raises(ValidationError):
        ConversationMessage(
            message_id="m1",
            role="user",
            text="hi",
            created_at=now,
            status="submitted",
            tool_summary="x",
        )


def test_a_stopped_turn_says_so_and_the_next_turn_sees_what_was_done(
    served: AgentWebServer,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[Any] = []

    async def converse(request: Any, history: Any, **_: Any) -> LocalConversationOutcome:
        seen.append(history)
        return LocalConversationOutcome(
            trace=TRACE, ingress="local", actor=request.actor, conversation=result()
        )

    monkeypatch.setattr(served.web.runtime.agent, "converse", converse)
    url, token = base(served), served.token
    session = fetch(url + "/api/conversations", token=token, body={}).json()
    session_id = session["conversation"]["session_id"]
    first = fetch(
        url + "/api/conversations/turn",
        token=token,
        body={"session_id": session_id, "message": "請整理九月訂單"},
    ).json()
    assert "回覆「繼續」" in first["answer"]["answer"]
    stored = first["conversation"]["messages"][-1]
    assert "authoring__run_workflow" in stored["tool_summary"]
    fetch(
        url + "/api/conversations/turn",
        token=token,
        body={"session_id": session_id, "message": "繼續"},
    )
    previous = [m.text for m in seen[1] if m.role == "assistant"]
    assert previous and "[工具紀錄]" in previous[-1] and "ap-1" in previous[-1]


def test_credential_shaped_text_is_redacted_not_refused() -> None:
    """coding_v1 fix-run-010 T09: a reply quoting a document's header line."""
    now = datetime.now(UTC)
    answer = ConversationMessage(
        message_id="m2",
        role="assistant",
        created_at=now,
        status="answered",
        text="SOP 第 3 步：以 Authorization: Bearer abc.def-123 呼叫 GET /data",
        tool_summary="- coding__run: api_key=sk-live-1",
    )
    assert "abc.def-123" not in answer.text and "[redacted]" in answer.text
    assert answer.tool_summary is not None and "sk-live-1" not in answer.tool_summary
    question = ConversationMessage(
        message_id="m1",
        role="user",
        created_at=now,
        status="submitted",
        text="password: hunter2 能用嗎",
    )
    assert "hunter2" not in question.text


def test_a_reply_quoting_a_bearer_header_still_answers_the_turn(
    served: AgentWebServer,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    quoted = "登入後以 header Authorization: Bearer <token> 呼叫 GET /data。"

    async def converse(request: Any, history: Any, **_: Any) -> LocalConversationOutcome:
        return LocalConversationOutcome(
            trace=TRACE,
            ingress="local",
            actor=request.actor,
            conversation=result(tools=(), failure=None, status="answered", text=quoted),
        )

    monkeypatch.setattr(served.web.runtime.agent, "converse", converse)
    url, token = base(served), served.token
    session = fetch(url + "/api/conversations", token=token, body={}).json()
    turn = fetch(
        url + "/api/conversations/turn",
        token=token,
        body={
            "session_id": session["conversation"]["session_id"],
            "message": "SOP 怎麼呼叫 /data？",
        },
    ).json()
    stored = turn["conversation"]["messages"][-1]
    assert stored["status"] == "answered"
    assert "GET /data" in stored["text"] and "[redacted]" in stored["text"]
