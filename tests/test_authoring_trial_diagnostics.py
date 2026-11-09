"""Actual trial diagnostics reach bounded repair without bulk result contents."""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from test_authoring_repair import Capturing
from test_chat_authoring import context, studio, workflow
from test_conversation_turn_groups import _chat_config, _ChatGateway

from capabilities.browser_session.handlers import BrowserResult
from capabilities.runtime import CapabilityExecutionFailed
from capabilities.web.handlers import WebHostBinding
from common.assets import ExecutionDependencies
from common.base import Contract
from common.execution import CapabilityResult, Failure, RequestContext, WorkflowRun
from host_runtime.authoring_task import Requirement
from host_runtime.chat_authoring import ChatAuthoring, ChatAuthoringError, ChatCandidate
from host_runtime.host import build_runtime
from host_runtime.web import AgentWeb
from integrations.web_script import DOMControl, DOMOverview
from workflow.engine import WorkflowRunSnapshot


def _plan(
    chat: ChatAuthoring,
    actor: str = "owner",
    session: str = "session-1",
    capability: str = "read-it",
) -> None:
    chat.tasks.plan(
        actor,
        session,
        "Read all required records",
        [
            Requirement.model_validate(
                {
                    "requirement_id": "rows",
                    "description": "Read required records",
                    "check_ids": ["rows"],
                    "assertions": [
                        {
                            "path": ["steps", 0, "capability", "name"],
                            "operator": "equals",
                            "expected": capability,
                        }
                    ],
                }
            )
        ],
    )


def _candidate(chat: ChatAuthoring) -> ChatCandidate:
    _plan(chat)
    raw = workflow("read-it")
    raw["checks"] = [{"check_id": "rows", "step_index": 0, "kind": "data_nonempty"}]
    item, problems = chat.draft("owner", "session-1", "Read", raw)
    assert item is not None and not problems
    return item


def _snapshot(
    item: ChatCandidate, run_id: str, data: dict[str, Any], *, succeeded: bool = False
) -> WorkflowRunSnapshot:
    failure = (
        None
        if succeeded
        else Failure(
            code="web_target_missing",
            message="actions[7] (fill): target absent; api_key=hidden-secret",
        )
    )
    return WorkflowRunSnapshot(
        run=WorkflowRun(
            run_id=run_id,
            workflow=item.draft.metadata.identity,
            trace=context().trace,
            status="succeeded" if succeeded else "failed",
            failure=failure,
            completed_steps=1 if succeeded else 0,
        ),
        step_results=(
            CapabilityResult(
                trace=context().trace,
                status="succeeded" if succeeded else "failed",
                failure=failure,
                data=data,
            ),
        ),
    )


@pytest.mark.parametrize("entry", ["approve", "card"])
def test_public_trial_repair_receives_exact_browser_action_and_failure_message(
    tmp_path: Path, entry: str
) -> None:
    from test_chat_authoring import Echo, spec

    config, layout = _chat_config(tmp_path)
    config = config.model_copy(update={"web": WebHostBinding(allowed_origins=("*",))})
    with build_runtime(config, layout=layout, model_transport=_ChatGateway()) as runtime:

        async def fail(context: RequestContext, inputs: Contract) -> Contract:
            raise CapabilityExecutionFailed(
                "web_target_missing",
                BrowserResult(
                    page="BULK-PAGE-SECRET" * 300,
                    data={"rows": ["RAW-ROW-SECRET" * 1000]},
                    failed_action_index=7,
                    failed_action_kind="fill",
                    url="https://example.invalid/orders",
                    diagnostic_error="Invalid date value; password=hidden-secret",
                    overview=DOMOverview(
                        controls=(
                            DOMControl(
                                tag="input",
                                label="Date From",
                                path="#date-from",
                                state={"invalid": "true"},
                            ),
                        ),
                        text="RAW-OVERVIEW-TEXT",
                        visited_nodes=42,
                    ),
                ),
                where="actions[7] (fill): target absent",
            )

        runtime.agent.gateway.bridge.installed.register(
            spec("browser-fixture", "write" if entry == "approve" else "read"),
            fail,
            Echo,
            BrowserResult,
            ExecutionDependencies(central_required=False),
        )
        web = AgentWeb(runtime)
        session = web.create_conversation()["conversation"]["session_id"]
        chat = runtime.chat_authoring
        assert chat is not None
        _plan(chat, runtime.actor, session, "browser-fixture")
        item, problems = chat.draft(
            runtime.actor,
            session,
            "Browser fixture",
            {
                "name": "browser-diagnostics",
                "description": "Read orders",
                "parameters": [],
                "steps": [
                    {
                        "capability": "lab/browser-fixture@1.0.0",
                        "inputs": {"value": {"source": "fixed", "value": "date"}},
                    }
                ],
                "checks": [{"check_id": "rows", "step_index": 0, "kind": "data_nonempty"}],
            },
        )
        assert item is not None and not problems
        model = Capturing(
            {
                "tools": [
                    (
                        "authoring__needs_input",
                        {
                            "reason": "business_decision",
                            "question": "Which approved date range applies?",
                            "input_name": "date_range",
                        },
                    )
                ]
            },
            {"text": "Which approved date range applies?"},
        )
        runtime.agent.gateway.router.model = model

        if entry == "approve":
            approval = chat.request(runtime.actor, session, "run", item.candidate_id, {})
            result = web.decide_approval(approval.approval_id, "approve")
        else:
            (card,) = web.draft_turn_cards(session, datetime(2000, 1, 1, tzinfo=UTC))
            result = web.decide_card(card["card_id"], "try")

        assert "repair" in result and model.requests
        request = model.requests[0]
        note = next(m.text for m in reversed(request.messages) if m.role == "user")
        assert '"failed_action_index": 7' in note and '"failed_action_kind": "fill"' in note
        assert "actions[7] (fill): target absent" in note
        assert '"step_index": 0' in note and "lab/browser-fixture@1.0.0" in note
        assert "Date From" in note and '"invalid": "true"' in note
        assert "BULK-PAGE-SECRET" not in note and "RAW-ROW-SECRET" not in note
        assert "RAW-OVERVIEW-TEXT" not in note and "hidden-secret" not in note
        assert "[redacted]" in note
        stored = chat.tasks.load(runtime.actor, session)
        assert stored is not None and stored.last_trial_diagnostics is not None
        assert stored.last_trial_diagnostics["run_id"] == stored.last_run_id


def test_python_tail_and_browser_metadata_are_bounded_redacted_and_exclude_raw_data(
    tmp_path: Path,
) -> None:
    chat, _ = studio(tmp_path)
    running = chat.begin_trial("owner", _candidate(chat), {"month": "2026-11"})
    data: dict[str, Any] = {
        "page": "DO-NOT-COPY-PAGE" * 20000,
        "data": {"rows": ["DO-NOT-COPY-ROWS" * 20000]},
        "files": [{"path": "DO-NOT-COPY-FILE"}],
        "diagnostics": {"elements": [{"value": "DO-NOT-COPY-INPUT"}]},
        "failed_action_index": 12,
        "failed_action_kind": "fill",
        "url": "https://example.invalid",
        "exit_code": 2,
        "timed_out": True,
        "output": "old-prefix" * 5000 + "\napi_key=hidden-secret\nTraceback: invalid date",
        "overview": {
            "text": "DO-NOT-COPY-OVERVIEW",
            "controls": [
                {
                    "label": "Date",
                    "path": "#date",
                    "state": {"invalid": True},
                    "value": "DO-NOT-COPY-INPUT",
                }
            ],
        },
    }
    chat.record_trial("owner", running, _snapshot(running, "python-failed", data))
    task = chat.tasks.load("owner", "session-1")
    assert task is not None and task.last_trial_diagnostics is not None
    encoded = json.dumps(task.last_trial_diagnostics, ensure_ascii=False)
    assert len(encoded.encode()) <= 12000
    assert "DO-NOT-COPY" not in encoded and "hidden-secret" not in encoded
    steps = task.last_trial_diagnostics["failed_steps"]
    assert isinstance(steps, list) and isinstance(steps[0], dict)
    assert steps[0]["failed_action_index"] == 12
    assert steps[0]["exit_code"] == 2 and steps[0]["timed_out"] is True
    tail = steps[0]["output_tail"]
    assert isinstance(tail, str) and len(tail) <= 4000
    assert tail.endswith("Traceback: invalid date") and "[redacted]" in tail


def test_stale_trial_cannot_replace_current_diagnostics_and_verified_success_clears_them(
    tmp_path: Path,
) -> None:
    chat, _ = studio(tmp_path)
    item = _candidate(chat)
    old = chat.begin_trial("owner", item, {"month": "old"})
    latest = chat.begin_trial("owner", item, {"month": "new"})
    chat.record_trial(
        "owner", latest, _snapshot(latest, "latest-failed", {"failed_action_index": 8})
    )
    before = chat.tasks.load("owner", "session-1")
    assert before is not None and before.last_trial_diagnostics is not None

    chat.record_trial("owner", old, _snapshot(old, "stale-failed", {"failed_action_index": 1}))
    assert chat.tasks.load("owner", "session-1") == before
    with pytest.raises(ChatAuthoringError, match="candidate_unknown"):
        chat.record_trial("other", latest, _snapshot(latest, "foreign-failed", {}))
    assert chat.tasks.load("owner", "session-1") == before

    running = chat.begin_trial("owner", chat.candidate(item.candidate_id, "owner"), {"month": "ok"})
    chat.record_trial("owner", running, _snapshot(running, "verified", {}, succeeded=True))
    task = chat.tasks.load("owner", "session-1")
    assert task is not None and task.last_trial_diagnostics is None and task.verified_digest


def test_partial_success_keeps_actual_stats_and_coverage_gaps(tmp_path: Path) -> None:
    chat, _ = studio(tmp_path)
    item = _candidate(chat)
    requirements = list(item.authoring_task.requirements) if item.authoring_task else []
    requirements.append(
        Requirement.model_validate(
            {
                "requirement_id": "complete",
                "description": "Preserve complete procedure",
                "check_ids": ["rows"],
                "assertions": [
                    {
                        "path": ["description"],
                        "operator": "equals",
                        "expected": "Complete procedure",
                    }
                ],
            }
        )
    )
    chat.tasks.plan("owner", "session-1", "Read all records", requirements)
    running = chat.begin_trial("owner", item, {"month": "ok"})
    chat.record_trial(
        "owner", running, _snapshot(running, "partial", {"rows": ["PRIVATE"]}, succeeded=True)
    )
    task = chat.tasks.load("owner", "session-1")
    assert task is not None and task.last_trial_diagnostics is not None
    assert task.last_trial_diagnostics["status"] == "succeeded"
    assert task.last_trial_diagnostics["completed_steps"] == 1
    assert "complete" in json.dumps(task.last_trial_diagnostics["coverage_problems"])
    assert "PRIVATE" not in json.dumps(task.last_trial_diagnostics)
