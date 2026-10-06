"""Approval buttons in Agent Web (CONVERSATIONAL_AUTHORING A5, G4).

The Agent can only ask; the owner's request with the page token decides,
and the decision and its result are added to the conversation as a turn.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from test_agent_web import base, fetch, served  # noqa: F401 - the server fixture
from test_chat_authoring import draft, studio

from common.execution import RequestContext, TraceIdentifiers
from host_runtime.web import AgentWebServer
from host_runtime.web_page import PAGE


def test_the_owner_decides_over_http_and_the_result_joins_the_conversation(
    served: AgentWebServer, tmp_path: Path  # noqa: F811
) -> None:
    chat, recorder = studio(tmp_path)
    served.web.runtime.chat_authoring = chat
    url, token = base(served), served.token
    session = fetch(url + "/api/conversations", token=token, body={}).json()
    session_id = session["conversation"]["session_id"]
    candidate = draft(chat, "write-it").data["candidate_id"]
    run = next(t for t in chat.tools() if t.tool.name == "authoring__run_workflow")
    context = RequestContext(
        trace=TraceIdentifiers(trace_id="t", request_id="r", span_id="s"),
        actor=served.web.runtime.actor, namespace="engineering", channel="local",
        session_id=session_id, message="run",
    )
    # The Agent asked as this actor; the stored candidate belongs to "owner",
    # so re-draft it for the served actor.
    chat_candidate = chat.candidate(candidate, "owner")
    chat._save_candidate(chat_candidate.model_copy(update={"actor": served.web.runtime.actor}))
    asked = asyncio.run(run.handler(context, {"candidate_id": candidate,
                                              "arguments": {"month": "2026-09"}}))
    assert asked.status == "awaiting_approval" and recorder.calls == []

    listed = fetch(url + "/api/approvals?session_id=" + session_id, token=token).json()
    (pending,) = listed["approvals"]
    assert pending["approval_id"] == asked.data["approval_id"]
    unauthenticated = fetch(url + "/api/approvals/decide",
                            body={"approval_id": pending["approval_id"], "decision": "approve"})
    assert unauthenticated.status == 401 and recorder.calls == []

    decided = fetch(url + "/api/approvals/decide", token=token,
                    body={"approval_id": pending["approval_id"], "decision": "approve"}).json()
    assert decided["ok"] and decided["approval"]["status"] == "approved"
    assert recorder.calls == ["2026-09"] and "已核准並執行" in decided["text"]
    shown = fetch(url + "/api/conversations?session_id=" + session_id, token=token).json()
    messages = shown["selected"]["messages"]
    assert [m["role"] for m in messages[-2:]] == ["user", "assistant"]
    assert messages[-2]["text"].startswith("【核准】")
    again = fetch(url + "/api/approvals/decide", token=token,
                  body={"approval_id": pending["approval_id"], "decision": "approve"})
    assert again.status == 409 and again.json()["code"] == "approval_already_decided"
    assert fetch(url + "/api/approvals?session_id=" + session_id,
                 token=token).json()["approvals"] == []
    assert "approval-card" in PAGE and "/api/approvals/decide" in PAGE
