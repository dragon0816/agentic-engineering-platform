import asyncio
from pathlib import Path

import pytest
from test_chat_authoring import call, context, studio, workflow

from agent.gateway import GatewayConversationResult, HostToolOutcome
from host_runtime.authoring_task import Requirement


def test_resident_draft_cannot_skip_the_requirement_plan(tmp_path: Path) -> None:
    chat, _ = studio(tmp_path)
    chat.autonomy_required = True
    tool = next(t for t in chat.tools() if t.tool.name == "authoring__draft_workflow")

    async def invoke() -> HostToolOutcome:
        return await tool.handler(context(), {"title": "test", "workflow": workflow("read-it")})

    outcome = asyncio.run(invoke())
    assert outcome.status == "failed"
    assert outcome.failure is not None
    assert outcome.failure.code == "authoring_plan_required"


def test_verified_status_requires_successful_current_digest_trial(tmp_path: Path) -> None:
    chat, _ = studio(tmp_path)
    chat.tasks.plan(
        "owner",
        "session-1",
        "Echo the month",
        [
            Requirement(
                requirement_id="echo",
                description="Echo the month",
                check_ids=("echoed",),
                assertions=(
                    {
                        "path": ["steps", 0, "capability", "name"],
                        "operator": "equals",
                        "expected": "read-it",
                    },
                ),
            )
        ],
    )
    raw = workflow("read-it")
    raw["checks"] = [{"check_id": "echoed", "step_index": 0, "kind": "data_nonempty"}]
    item, problems = chat.draft("owner", "session-1", "Echo", raw)
    assert not problems and item is not None
    assert chat.readiness(item)["verified"] is False
    assert (
        chat.execute("owner", item, {"month": "2026-11"}, "approved-run")["status"] == "succeeded"
    )
    current = chat.candidate(item.candidate_id, "owner")
    installed = chat.install(current, "owner")
    assert installed["installed_as"] and installed["verified"] is True


def test_incomplete_prototype_installs_with_explicit_unverified_quality(
    tmp_path: Path,
) -> None:
    chat, _ = studio(tmp_path)
    chat.tasks.plan(
        "owner",
        "session-1",
        "Read all pages",
        [
            Requirement(
                requirement_id="all",
                description="Read all pages",
                check_ids=("rows",),
                assertions=(
                    {
                        "path": ["steps", "*", "inputs", "actions", "value", "*", "pagination"],
                        "operator": "present",
                    },
                ),
            )
        ],
    )
    item, problems = chat.draft("owner", "session-1", "bad", workflow("read-it"))
    assert not problems and item is not None
    assert item.authoring_task is not None
    assert item.authoring_task.requirements[0].requirement_id == "all"
    assert "all" in str(chat.readiness(item)["coverage_problems"])
    result = chat.execute("owner", item, {"month": "2026-11"}, "approved-prototype")
    assert result["status"] == "succeeded"
    assert result["verified"] is False and result["coverage_complete"] is False
    current = chat.candidate(item.candidate_id, "owner")
    assert current.authoring_task is not None
    assert current.authoring_task.verified_digest is None
    assert current.authoring_task.repair_attempts == 1
    installed = chat.install(current, "owner")
    assert installed["installed_as"] and installed["verified"] is False
    assert isinstance(installed["quality"], dict)
    assert installed["quality"]["coverage_complete"] is False
    assert installed["quality"]["coverage_problems"]


def test_observed_sop_creates_unfinished_task_before_model_answers(tmp_path: Path) -> None:
    chat, _ = studio(tmp_path)
    chat.tasks.observe("owner", "session-1", "Please make a workflow from this SOP")
    ctx = context().model_copy(update={"message": "Please make a workflow from this SOP"})
    assert "Persistent Workflow" in chat.task_context(ctx)
    result = GatewayConversationResult(
        trace=ctx.trace, status="answered", text="Ready", model_turns=1
    )
    assert chat.completion_problem(ctx, result) is not None
    # A technical handoff cannot satisfy the persistent completion gate.
    rejected = call(
        chat,
        "authoring__needs_input",
        {"reason": "capability_gap", "question": "Please provide the CSS selector"},
    )
    assert rejected.status == "failed"
    assert chat.completion_problem(ctx, result) is not None
    # A real business choice explicitly pauses the task.
    accepted = call(
        chat,
        "authoring__needs_input",
        {"reason": "business_decision", "question": "Which reporting currency should be used?"},
    )
    assert accepted.status == "succeeded"
    assert chat.completion_problem(ctx, result) is None
    chat.tasks.observe("owner", "session-1", "Use EUR")
    assert chat.completion_problem(ctx, result) is not None


def test_cannot_claim_repair_limit_before_attempting_repairs(tmp_path: Path) -> None:
    chat, _ = studio(tmp_path)
    chat.tasks.plan("owner", "session-1", "Task", [])
    outcome = call(
        chat,
        "authoring__needs_input",
        {"reason": "repair_limit", "question": "Repair budget exhausted"},
    )
    assert outcome.status == "failed"
    assert outcome.failure is not None
    assert outcome.failure.code == "authoring_repair_remaining"


@pytest.mark.parametrize("input_name", [None, "owner_mapping"])
def test_supplied_workbook_cannot_be_reasked_before_first_draft(
    tmp_path: Path, input_name: str | None
) -> None:
    chat, _ = studio(tmp_path)
    source = tmp_path / "Sales name and Dept.xlsx"
    source.write_bytes(b"supplied")
    chat.tasks.observe(
        "owner", "session-1", "Use this lookup", ({"filename": source.name, "path": str(source)},)
    )
    chat.tasks.plan("owner", "session-1", "Build from SOP", [])
    args = {"reason": "missing_resource", "question": "請提供Excel對照表"}
    if input_name:
        args["input_name"] = input_name
    result = call(chat, "authoring__needs_input", args)
    assert result.status == "failed"
    task = chat.tasks.load("owner", "session-1")
    assert task is not None and task.question is None
    result = call(
        chat,
        "authoring__needs_input",
        {
            **args,
            "input_name": "owner_mapping",
            "resource_name": source.name,
        },
    )
    assert result.status == "failed"
