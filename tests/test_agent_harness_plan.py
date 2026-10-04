"""One shared Skill-driven plan shape across Knowledge, Workflow and Coding."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from agent.harness_plan import AgentHarnessPlan, plan_task
from agent.skills import SkillHarnessGuidance, SkillManifest
from agent.task_contract import (
    CompletionCheck,
    ExpectedOutput,
    TaskContract,
    TaskExecutionConstraints,
)
from common.assets import AssetIdentity
from common.execution import TraceIdentifiers

FIXTURES = Path(__file__).parent / "fixtures" / "harness_skills"


def _skill(name: str) -> SkillManifest:
    return SkillManifest.model_validate_json((FIXTURES / name).read_text(encoding="utf-8"))


def _task(skill: SkillManifest, *, max_retries: int = 1) -> TaskContract:
    return TaskContract(
        task_id="task-harness-test",
        trace=TraceIdentifiers(trace_id="trace-1", request_id="request-1", span_id="plan"),
        actor="engineer",
        namespace=skill.metadata.identity.namespace,
        objective="Complete the selected task with checked evidence",
        skills=(skill.metadata.identity,),
        allowed_capabilities=(
            AssetIdentity(namespace="test-capability", name="read", version="1.0.0"),
        ),
        expected_outputs=(ExpectedOutput(output_id="answer", artifact_ref="answer-1"),),
        checks=(CompletionCheck(check_id="host-check", output_id="answer", kind="nonempty"),),
        constraints=TaskExecutionConstraints(max_retries=max_retries),
    )


@pytest.mark.parametrize(
    ("filename", "domain", "stages", "evidence", "fallback"),
    (
        (
            "knowledge-evidence.json", "knowledge",
            ("collect_context", "execute", "validate"),
            ("raw_citations", "unresolved_gaps"), "needs_input",
        ),
        (
            "workflow-check.json", "workflow", ("execute", "validate"),
            ("workflow_run", "artifact_check"), "stop",
        ),
        (
            "coding-verify.json", "coding",
            ("collect_context", "execute", "validate"),
            ("new_test", "regression_test"), "retry",
        ),
    ),
)
def test_skill_guidance_plans_all_three_domains_without_granting_capabilities(
    filename: str,
    domain: str,
    stages: tuple[str, ...],
    evidence: tuple[str, ...],
    fallback: str,
) -> None:
    skill = _skill(filename)
    task = _task(skill)
    plan = plan_task(task, skill, domain)  # type: ignore[arg-type]
    assert plan.stages == stages
    assert plan.skill_evidence == evidence
    assert plan.fallback == fallback
    assert plan.host_checks == ("host-check",)
    assert plan.requested_capabilities == task.allowed_capabilities
    assert plan.task_sha256 == task.digest
    assert AgentHarnessPlan.model_validate(plan.model_dump(mode="json")) == plan
    changed = plan.model_dump(mode="json")
    changed["stages"] = ["execute"]
    with pytest.raises(ValidationError):
        AgentHarnessPlan.model_validate(changed)


def test_skill_cannot_widen_task_scope_or_force_retry_past_host_budget() -> None:
    skill = _skill("coding-verify.json")
    task = _task(skill, max_retries=0)
    plan = plan_task(task, skill, "coding")
    assert plan.retry_budget == 0
    assert plan.fallback == "needs_input"
    assert plan.requested_capabilities == task.allowed_capabilities
    with pytest.raises(ValueError, match="not declared"):
        plan_task(task.model_copy(update={"skills": ()}), skill, "coding")
    with pytest.raises(ValueError, match="does not support"):
        plan_task(task, skill, "workflow")


def test_skill_guidance_rejects_duplicate_domains_and_unbounded_retry() -> None:
    with pytest.raises(ValidationError):
        SkillHarnessGuidance(domains=("knowledge", "knowledge"))
    with pytest.raises(ValidationError):
        SkillHarnessGuidance(domains=("coding",), fallback="retry", max_retries=0)
