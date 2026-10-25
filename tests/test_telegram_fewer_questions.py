"""Fewer questions in a Workflow run (owner, Telegram, 2026-10-25).

「幫我執行 43W SDE weekly report」 opened the question flow and asked the report
week the message already named, and the 9 inputs one by one; then a button
of an earlier question answered the new one. Now values stated in the request
are read from the Workflow's declaration and never asked, optional inputs
keep their defaults, only missing required inputs are asked, one card lists
every value, and a tap or Reply on an earlier question is never taken as an
answer to another one. Through the ingress over the
fake Bot API of `test_telegram_ingress`; no socket is opened. Reading the
values themselves is tested in `test_run_prefill.py`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from evaluation_runner import release_workflow
from test_run_prefill import SDE_FIELDS, TODAY
from test_telegram_ingress import OWNER, FakeTransport, ingress, poll, update
from test_telegram_reply_context import Recording, replying
from test_telegram_workflow_flow import _tap

from channels.telegram import ENDED_FLOW, RESTARTED_FLOW, STALE_TAP_REPLY
from common import run_prefill
from common.assets import WorkflowManifest

# -- through the Telegram ingress -------------------------------------------------


def _install(agent: Any, fields: list[dict[str, Any]] | None = None) -> WorkflowManifest:
    data = release_workflow().model_dump(mode="json")
    data["metadata"]["identity"]["name"] = "sde-weekly-report"
    data["run_alias"] = 9
    data["parameters"] = fields if fields is not None else SDE_FIELDS
    manifest = WorkflowManifest.model_validate(data)
    agent.gateway.engine.workflows.register(manifest)
    return manifest


@pytest.fixture
def fixed_today(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(run_prefill, "_today", lambda: TODAY)


def test_the_owners_request_asks_nothing_and_shows_one_card(
    tmp_path: Path, fixed_today: None
) -> None:
    transport = FakeTransport([[update(1, OWNER, "幫我執行 43W SDE weekly report")]])
    item, agent, _ = ingress(tmp_path, transport)
    _install(agent)
    card = poll(item).deliveries[0]
    text = card.reply or ""
    assert text.startswith("執行 sde-weekly-report？")
    assert "- Report week：2026_43W（從你的訊息）" in text
    assert "- Save the weekly mail draft：是（預設）" in text
    assert "未填（不使用）：" in text and "Dry run: show the plan only、From date" in text
    assert "(1/" not in text  # no question was asked
    assert card.buttons == ((("確認執行", "run:yes"), ("修改", "run:edit")),)
    # A typed change shows the card again.
    transport.batches.append([update(2, OWNER, "dry run 改成是")])
    changed = poll(item).deliveries[0].reply or ""
    assert "已改：Dry run: show the plan only = 是" in changed
    assert "- Dry run: show the plan only：是\n" in changed
    transport.batches.append([update(3, OWNER, "From date 2026-10-19")])
    assert "- From date：2026-10-19" in (poll(item).deliveries[0].reply or "")
    # Confirming runs it, with the values on the card.
    transport.batches.append([_tap(4, OWNER, "run:yes", transport)])
    ran = poll(item).deliveries[0]
    assert ran.disposition in ("routed", "refused") and ran.outcome is not None
    assert not item._flows


def test_a_missing_required_value_is_the_only_question(tmp_path: Path, fixed_today: None) -> None:
    fields = [
        *SDE_FIELDS,
        {"name": "repo", "label": "Repository", "kind": "text", "required": True},
    ]
    transport = FakeTransport([[update(1, OWNER, "幫我執行 43W SDE weekly report")]])
    item, agent, _ = ingress(tmp_path, transport)
    _install(agent, fields)
    asked = poll(item).deliveries[0].reply or ""
    assert asked.startswith("已從你的訊息帶入：Report week = 2026_43W\n")
    assert "sde-weekly-report (1/1)" in asked and "Repository *" in asked
    transport.batches.append([update(2, OWNER, "owner/repo")])
    card = poll(item).deliveries[0].reply or ""
    assert "- Repository：owner/repo" in card and "（從你的訊息）" in card


def test_a_button_of_an_earlier_question_is_not_taken_as_the_answer(tmp_path: Path) -> None:
    fields = [
        {"name": "go", "label": "Go ahead", "kind": "boolean", "required": True},
        {"name": "since", "label": "From date", "kind": "date", "required": True},
    ]
    transport = FakeTransport([[update(1, OWNER, "/run sde-weekly-report")]])
    item, agent, _ = ingress(tmp_path, transport)
    _install(agent, fields)
    first = poll(item).deliveries[0]
    assert "Go ahead *" in (first.reply or "") and first.buttons == (
        (("Yes", "yes"), ("No", "no")),
    )
    question = next(iter(item._flows.values())).prompt_message_id
    assert question is not None
    # A Yes under an older message (here the one before the question) does nothing.
    stale = _tap(2, OWNER, "yes")
    stale["callback_query"]["message"]["message_id"] = question - 1
    transport.batches.append([stale])
    refused = poll(item).deliveries[0]
    assert (refused.reply or "").startswith(STALE_TAP_REPLY) and "Go ahead *" in (
        refused.reply or ""
    )
    state = next(iter(item._flows.values()))
    assert "go" not in state.answers and state.fields[state.index].name == "go"
    # The question's own button is taken, and the next question waits.
    transport.batches.append([_tap(3, OWNER, "yes", transport)])
    following = poll(item).deliveries[0]
    assert "From date *" in (following.reply or "") and state.answers == {"go": True}
    assert not [d for d in poll(item).deliveries]  # nothing else arrives by itself


def test_a_reply_to_a_question_whose_flow_is_gone_starts_it_again(tmp_path: Path) -> None:
    """After the 12:48 restart the owner replied 2026_43W on the old 「(2/9)
    Report week」 question; it never answers some other question."""
    old_question = "sde-weekly-report (2/9)\nReport week\nWeekly sheet name, for example 2026_40W."
    transport = FakeTransport(
        [[replying(1, "2026_43W", {"from": {"id": 42, "is_bot": True}, "text": old_question})]]
    )
    item, agent, _ = ingress(tmp_path, transport)
    _install(agent)
    model = Recording()
    agent.gateway.router.model = model
    restarted = poll(item).deliveries[0]
    text = restarted.reply or ""
    assert text.startswith(RESTARTED_FLOW)
    assert "- Report week：2026_43W（從你的訊息）" in text
    assert model.requests == []  # handled without the model
    # A tap under a question of a flow that is gone is said to be over.
    transport.batches.append([_tap(2, OWNER, "run:yes", transport)])
    item._flows.clear()
    ended = poll(item).deliveries[0]
    assert ended.reply == ENDED_FLOW and model.requests == []
