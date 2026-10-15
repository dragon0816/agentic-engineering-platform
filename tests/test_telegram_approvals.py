"""Approval buttons in Telegram (CONVERSATIONAL_AUTHORING A5, G4)."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import cast

from test_chat_authoring import studio, workflow
from test_telegram_ingress import OWNER, FakeTransport, ingress, poll
from test_telegram_workflow_flow import _tap

from common.local_agent import LocalAgentRequest


def _request(actor: str, session_id: str) -> LocalAgentRequest:
    """Only the actor and session the approval buttons read."""
    return cast(LocalAgentRequest, SimpleNamespace(actor=actor, session_id=session_id))


def test_the_owner_approves_with_a_button_and_the_run_happens_once(tmp_path: Path) -> None:
    transport = FakeTransport([])
    item, _agent, _runner = ingress(tmp_path, transport)
    chat, recorder = studio(tmp_path)
    item.approvals = chat
    actor = item.config.actor_for(OWNER)
    assert actor is not None
    acting, _ = item._acting(actor)
    session = f"telegram-chat-{OWNER}"
    candidate, problems = chat.draft(acting, session, "Echo", workflow("write-it"))
    assert candidate is not None and not problems
    asked = chat.request(acting, session, "run", candidate.candidate_id, {"month": "2026-09"})

    buttons = item._approval_buttons(_request(acting, session))
    assert buttons == (
        (
            (f"核准執行 {asked.workflow}"[:60], f"approve:{asked.approval_id}"),
            ("拒絕", f"reject:{asked.approval_id}"),
        ),
    )
    assert recorder.calls == []

    transport.batches.append([_tap(2, OWNER, f"approve:{asked.approval_id}")])
    done = poll(item).deliveries[0]
    assert "已核准並執行" in (done.reply or "") and recorder.calls == ["2026-09"]
    transport.batches.append([_tap(3, OWNER, f"approve:{asked.approval_id}")])
    again = poll(item).deliveries[0]
    assert "already decided" in (again.reply or "") and recorder.calls == ["2026-09"]
    assert item._approval_buttons(_request(acting, session)) == ()
