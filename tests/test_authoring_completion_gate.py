"""An authoring answer must reach a proved trial or an explicit waiting state."""

from typing import Literal

import pytest
from pydantic import JsonValue

from agent.conversation_harness import check_reuse
from agent.gateway import ConversationToolExecution, HostToolOutcome


def _tool(
    name: str,
    data: dict[str, JsonValue],
    status: Literal["succeeded", "failed", "awaiting_approval"] = "succeeded",
) -> ConversationToolExecution:
    return ConversationToolExecution(
        call_id="call", name=name, host=HostToolOutcome(status=status, data=data)
    )


def _draft(candidate: str = "current", digest: str = "new") -> ConversationToolExecution:
    return _tool(
        "authoring__draft_workflow",
        {"trial_required": True, "candidate_id": candidate, "digest": digest},
    )


def _run(
    candidate: str = "current", digest: str = "new", *, pending: bool = False
) -> ConversationToolExecution:
    return _tool(
        "authoring__run_workflow",
        {"candidate_id": candidate, "digest": digest, "status": "succeeded"},
        "awaiting_approval" if pending else "succeeded",
    )


def test_guarded_draft_alone_requires_actual_trial() -> None:
    check, reason = check_reuse("Please build this workflow", (_draft(),), True)
    assert check.status == "failed"
    assert reason is not None
    assert "authoring__run_workflow" in reason
    assert "current" in reason and "new" in reason
    assert "navigation" in reason


def test_patch_alone_requires_its_current_exact_trial() -> None:
    patch = _draft().model_copy(update={"name": "authoring__patch_workflow"})
    check, reason = check_reuse("Repair the Workflow", (_run(digest="old"), patch), True)
    assert check.status == "failed" and reason is not None
    assert check_reuse("Repair", (patch, _run()), True)[0].status == "passed"


@pytest.mark.parametrize("pending", [False, True])
def test_current_exact_trial_or_its_approval_allows_response(pending: bool) -> None:
    check, reason = check_reuse("Build it", (_draft(), _run(pending=pending)), True)
    assert check.status == "passed" and reason is None


@pytest.mark.parametrize(
    "proof",
    [
        {"verified": False},
        {"verified": False, "coverage_problems": []},
        {"coverage_problems": ["all_rows: missing pagination"]},
        {"verified": True, "coverage_problems": ["all_rows: missing pagination"]},
    ],
)
def test_partial_success_of_exact_candidate_does_not_complete_authoring(
    proof: dict[str, JsonValue],
) -> None:
    trial = _tool(
        "authoring__run_workflow",
        {
            "candidate_id": "current",
            "digest": "new",
            "status": "succeeded",
            **proof,
        },
    )
    check, reason = check_reuse("Build it", (_draft(), trial), True)
    assert check.status == "failed"
    assert reason is not None


def test_verified_current_trial_completes_authoring() -> None:
    trial = _tool(
        "authoring__run_workflow",
        {
            "candidate_id": "current",
            "digest": "new",
            "status": "succeeded",
            "verified": True,
            "coverage_problems": [],
        },
    )
    assert check_reuse("Build it", (_draft(), trial), True)[0].status == "passed"


@pytest.mark.parametrize("status", ["succeeded", "failed", "awaiting_approval"])
def test_guarded_draft_can_pause_only_for_successful_structured_business_question(
    status: Literal["succeeded", "failed", "awaiting_approval"],
) -> None:
    question = _tool(
        "authoring__needs_input",
        {
            "status": "needs_input",
            "reason": "business_decision",
            "question": "Which reporting currency should be used?",
        },
        status,
    )
    check, _ = check_reuse("Build it", (_draft(), question), True)
    assert check.status == ("passed" if status == "succeeded" else "failed")


@pytest.mark.parametrize("pending", [False, True])
def test_partial_draft_can_wait_for_approval_but_partial_success_is_not_completion(
    pending: bool,
) -> None:
    draft = _tool(
        "authoring__draft_workflow",
        {
            "trial_required": True,
            "candidate_id": "current",
            "digest": "new",
            "coverage_complete": False,
        },
    )
    check, _ = check_reuse("Build it", (draft, _run(pending=pending)), True)
    assert check.status == ("passed" if pending else "failed")


@pytest.mark.parametrize(
    "trial",
    [
        _run("other"),
        _run(digest="old"),
        _run("other", pending=True),
        _run(digest="old", pending=True),
        _tool("authoring__run_workflow", {"candidate_id": "current", "status": "succeeded"}),
        _tool(
            "authoring__run_workflow",
            {"candidate_id": "current", "digest": "new", "status": "failed"},
        ),
        _tool(
            "authoring__run_workflow",
            {"candidate_id": "current", "digest": "new", "status": "succeeded"},
            "failed",
        ),
    ],
)
def test_wrong_or_failed_trial_does_not_complete_guarded_draft(
    trial: ConversationToolExecution,
) -> None:
    assert check_reuse("Build it", (_draft(), trial), True)[0].status == "failed"


def test_new_revision_invalidates_earlier_successful_trial() -> None:
    tools = (_draft(digest="old"), _run(digest="old"), _draft())
    assert check_reuse("Build it", tools, True)[0].status == "failed"


def test_legacy_draft_keeps_existing_completion_behavior() -> None:
    tools = (_tool("coding__run", {}), _tool("authoring__draft_workflow", {}))
    assert check_reuse("Make it reusable", tools, True)[0].status == "passed"


def test_plan_alone_cannot_complete_authoring() -> None:
    check, reason = check_reuse("Build it", (_tool("authoring__plan_workflow", {}),), True)
    assert check.status == "failed"
    assert reason is not None and "authoring__needs_input" in reason


@pytest.mark.parametrize(
    "reason",
    [
        "business_decision",
        "missing_resource",
        "authentication_required",
        "capability_gap",
        "repair_limit",
    ],
)
def test_plan_can_wait_for_structured_missing_input(reason: str) -> None:
    tools = (
        _tool("authoring__plan_workflow", {}),
        _tool(
            "authoring__needs_input",
            {
                "status": "needs_input",
                "reason": reason,
                "question": "Which approved business scope applies?",
            },
        ),
    )
    assert check_reuse("Build it", tools, True)[0].status == "passed"


@pytest.mark.parametrize(
    "data",
    [
        {},
        {"status": "needs_input"},
        {"status": "needs_input", "reason": "business_decision", "question": ""},
        {
            "status": "needs_input",
            "reason": "technical_navigation",
            "question": "Click all pages yourself",
        },
    ],
)
def test_plan_does_not_accept_unstructured_or_technical_deferral(
    data: dict[str, JsonValue],
) -> None:
    tools = (_tool("authoring__plan_workflow", {}), _tool("authoring__needs_input", data))
    assert check_reuse("Build it", tools, True)[0].status == "failed"


def test_plan_can_wait_for_actual_approval() -> None:
    tools = (
        _tool("authoring__plan_workflow", {}),
        _tool("browser__operate", {"approval_id": "approval"}, "awaiting_approval"),
    )
    assert check_reuse("Build it", tools, True)[0].status == "passed"
