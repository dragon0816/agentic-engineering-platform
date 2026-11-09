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


def _crowded_browser_data() -> dict[str, Any]:
    return {
        "page": "ROW-CHECKBOX-BODY " * 1000,
        "data": {"rows": ["PRIVATE-ROWS" * 1000]},
        "failed_action_index": 17,
        "failed_action_kind": "fill",
        "overview": {
            "controls": [
                *[
                    {
                        "tag": "input",
                        "kind": "checkbox",
                        "label": f"row-{i}",
                        "path": f"#row-{i}",
                        "state": {"type": "checkbox"},
                    }
                    for i in range(40)
                ],
                {"tag": "a", "kind": "link", "label": "Navigation", "path": "#nav"},
                {
                    "tag": "input",
                    "kind": "text",
                    "label": "Date From",
                    "path": "#from",
                    "value": "PRIVATE-INPUT",
                    "state": {
                        "type": "text",
                        "placeholder": "YYYY-MM-DD",
                        "invalid": "true",
                        "value": "PRIVATE-INPUT",
                    },
                },
                {
                    "tag": "button",
                    "kind": "button",
                    "label": "Advanced filters",
                    "path": "#filters",
                    "state": {"pressed": "false", "expanded": "true"},
                },
            ],
            "text": "PRIVATE-OVERVIEW",
            "visited_nodes": 800,
        },
    }


def test_query_fields_and_toolbar_survive_checkbox_crowding_in_trial_diagnostics(
    tmp_path: Path,
) -> None:
    chat, _ = studio(tmp_path)
    running = chat.begin_trial("owner", _candidate(chat), {"month": "2026-11"})
    chat.record_trial("owner", running, _snapshot(running, "query-failed", _crowded_browser_data()))
    task = chat.tasks.load("owner", "session-1")
    assert task is not None and task.last_trial_diagnostics is not None
    diagnostics: Any = task.last_trial_diagnostics
    controls = diagnostics["failed_steps"][0]["overview"]["controls"]
    labels = [c["label"] for c in controls]
    assert labels[:2] == ["Date From", "Advanced filters"]
    assert len(controls) <= 32
    assert controls[0]["state"]["placeholder"] == "YYYY-MM-DD"
    assert controls[0]["state"]["type"] == "text"
    assert controls[1]["state"] == {"pressed": "false", "expanded": "true"}
    encoded = json.dumps(diagnostics, ensure_ascii=False)
    assert len(encoded.encode()) <= 12000 and "PRIVATE" not in encoded
    assert "ROW-CHECKBOX-BODY" not in encoded


def test_failed_public_summary_puts_query_metadata_before_bulk_preview_and_keeps_success_shape(
    tmp_path: Path,
) -> None:
    from host_runtime.chat_authoring import summarize

    chat, _ = studio(tmp_path)
    item = _candidate(chat)
    summary: Any = summarize(_snapshot(item, "query-failed", _crowded_browser_data()))
    data = summary["steps"][0]["data"]
    assert data["failed_action_index"] == 17
    assert data["overview"]["controls"][0]["state"]["placeholder"] == "YYYY-MM-DD"
    assert data["overview"]["controls"][1]["state"]["pressed"] == "false"
    assert list(data).index("overview") < list(data).index("preview")
    assert data["truncated"] is True and isinstance(data["preview"], str)
    assert len(json.dumps(data, ensure_ascii=False).encode()) <= 12000
    success: Any = summarize(_snapshot(item, "success", {"echoed": "value"}, succeeded=True))
    assert success["steps"][0]["data"] == {"echoed": "value"}


def test_large_control_hints_trim_from_end_without_removing_query_overview(tmp_path: Path) -> None:
    from host_runtime.chat_authoring import summarize

    chat, _ = studio(tmp_path)
    item = _candidate(chat)
    data = _crowded_browser_data()
    data["overview"]["controls"] += [
        {
            "tag": "input",
            "kind": "text",
            "label": "界" * 80,
            "path": "界" * 200,
            "state": {
                "placeholder": "界" * 80,
                "type": "text",
                "pressed": "false",
                "expanded": "false",
                "invalid": "false",
            },
        }
        for _ in range(40)
    ]
    running = chat.begin_trial("owner", item, {"month": "2026-11"})
    snapshot = _snapshot(running, "large-query-failed", data)
    chat.record_trial("owner", running, snapshot)
    task = chat.tasks.load("owner", "session-1")
    assert task is not None and task.last_trial_diagnostics is not None
    diagnostics: Any = task.last_trial_diagnostics
    overview = diagnostics["failed_steps"][0]["overview"]
    assert overview["controls"][0]["label"] == "Date From"
    assert 0 < len(overview["controls"]) < 32 and overview["controls_truncated"] is True
    assert len(json.dumps(diagnostics, ensure_ascii=False).encode()) <= 12000
    summary: Any = summarize(snapshot)
    overview = summary["steps"][0]["data"]["overview"]
    assert overview["controls"][0]["label"] == "Date From"
    assert len(json.dumps(summary["steps"][0]["data"], ensure_ascii=False).encode()) <= 12000


def test_typed_nested_target_failure_reaches_public_repair_and_owner_context(
    tmp_path: Path,
) -> None:
    from test_chat_authoring import context

    from capabilities.browser_session.handlers import SPEC, BrowserRequest

    config, layout = _chat_config(tmp_path)
    with build_runtime(config, layout=layout, model_transport=_ChatGateway()) as runtime:

        async def fail(context: RequestContext, inputs: Contract) -> Contract:
            request = BrowserRequest.model_validate(inputs)
            assert request.actions[0].do == "read_table"
            failure = BrowserResult(
                failed_action_index=0,
                failed_action_kind="read_table",
                failed_target_field="pagination.current",
            )
            raise CapabilityExecutionFailed(
                "web_target_missing", failure, where="actions[0] (read_table) pagination.current"
            )

        runtime.agent.gateway.bridge.installed.register(
            SPEC, fail, BrowserRequest, BrowserResult, ExecutionDependencies(central_required=False)
        )
        web = AgentWeb(runtime)
        session = web.create_conversation()["conversation"]["session_id"]
        chat = runtime.chat_authoring
        assert chat is not None
        _plan(chat, runtime.actor, session, "operate")
        item, problems = chat.draft(
            runtime.actor,
            session,
            "Orders",
            {
                "name": "nested-pagination-target",
                "description": "Read orders",
                "parameters": [],
                "steps": [
                    {
                        "capability": "browser/operate@1.0.0",
                        "inputs": {
                            "actions": {
                                "source": "fixed",
                                "value": [
                                    {
                                        "do": "read_table",
                                        "table": "#orders",
                                        "save_as": "orders",
                                        "pagination": {
                                            "current": {"css": "#current"},
                                            "total": {"css": "#total"},
                                            "next": {"css": "#next"},
                                        },
                                    }
                                ],
                            }
                        },
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
                            "question": "Which approved order scope applies?",
                            "input_name": "order_scope",
                        },
                    )
                ]
            },
            {"text": "Which approved order scope applies?"},
        )
        runtime.agent.gateway.router.model = model
        approval = chat.request(runtime.actor, session, "run", item.candidate_id, {})

        result = web.decide_approval(approval.approval_id, "approve")

        step = result["approval"]["result"]["steps"][0]
        assert step["data"]["failed_target_field"] == "pagination.current"
        assert "repair" in result and model.requests
        note = next(m.text for m in reversed(model.requests[0].messages) if m.role == "user")
        assert '"failed_target_field": "pagination.current"' in note
        ctx = context().model_copy(update={"actor": runtime.actor, "session_id": session})
        guidance = chat.task_context(ctx)
        compact = json.loads(guidance.splitlines()[1])
        assert compact[0]["failed_step"]["failed_target_field"] == "pagination.current"
