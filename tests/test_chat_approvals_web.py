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


def test_external_submissions_wait_in_their_own_list_with_the_whole_draft(
    served: AgentWebServer, tmp_path: Path  # noqa: F811
) -> None:
    from test_external_authoring import desk, skill

    from host_runtime.external_authoring import ExternalAuthoring

    authoring, _ = desk(tmp_path)
    actor = served.web.runtime.actor
    served.web.runtime.chat_authoring = authoring.chat
    external = ExternalAuthoring(authoring.chat, actor, "claude-code")
    submitted = external.submit_skill(skill(), "Echo helper")
    asked = external.install_skill(str(submitted["candidate_id"]))
    url, token = base(served), served.token
    (item,) = fetch(url + "/api/approvals/external", token=token).json()["approvals"]
    assert item["source"] == "external:claude-code" and item["kind"] == "install_skill"
    assert "When asked to echo a month" in item["detail"]
    assert fetch(url + "/api/approvals/external").status == 401
    decided = fetch(url + "/api/approvals/decide", token=token,
                    body={"approval_id": asked["approval_id"], "decision": "approve"}).json()
    assert decided["ok"] and "已核准安裝 Skill" in decided["text"]
    assert (tmp_path / "skills" / "engineering__echo-helper__1.0.0.json").is_file()
    assert fetch(url + "/api/approvals/external", token=token).json()["approvals"] == []
    assert 'id="external-approvals"' in PAGE and "/api/approvals/external" in PAGE


def test_the_owner_sees_drafts_not_yet_installed_and_installs_or_deletes_them(
    served: AgentWebServer, tmp_path: Path  # noqa: F811
) -> None:
    """Owner 2026-10-08: a Workflow that was only run once never shows up as
    installed; the draft list shows it, and Install is the owner's approval."""
    from test_external_authoring import desk, skill, workflow

    from host_runtime.external_authoring import ExternalAuthoring

    authoring, recorder = desk(tmp_path)
    actor = served.web.runtime.actor
    served.web.runtime.chat_authoring = authoring.chat
    mine = ExternalAuthoring(authoring.chat, actor, "codex")
    wf = mine.submit_workflow(workflow("write-it"), "Echo")
    sk = mine.submit_skill(skill(), "Echo helper")
    ran = mine.run_workflow(str(wf["candidate_id"]), {"month": "09"})
    authoring.chat.decide(str(ran["approval_id"]), actor, True)
    url, token = base(served), served.token
    listed = fetch(url + "/api/drafts", token=token).json()["drafts"]
    assert {d["kind"] for d in listed} == {"workflow", "skill"}
    (shown,) = [d for d in listed if d["kind"] == "workflow"]
    assert shown["steps"] == ["lab/write-it@1.0.0"] and shown["last_run"]["result"] == "succeeded"
    assert fetch(url + "/api/drafts").status == 401

    installed = fetch(url + "/api/drafts/install", token=token,
                      body={"candidate_id": wf["candidate_id"]}).json()
    assert installed["ok"] and installed["installed_as"] == "engineering/echo-month@1.0.0"
    assert (tmp_path / "workflows" / "engineering__echo-month__1.0.0.json").is_file()
    asked = mine.install_skill(str(sk["candidate_id"]))
    deleted = fetch(url + "/api/drafts/delete", token=token,
                    body={"candidate_id": sk["candidate_id"]}).json()
    assert deleted["ok"]
    assert fetch(url + "/api/drafts", token=token).json()["drafts"] == []
    assert authoring.chat.approval(str(asked["approval_id"]), actor).status == "rejected"
    unknown = fetch(url + "/api/drafts/install", token=token, body={"candidate_id": "wf-x"})
    assert unknown.status == 409 and unknown.json()["code"] == "candidate_unknown"
    assert recorder.calls == ["09"]
