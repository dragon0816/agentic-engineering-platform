"""One bounded state machine rejects unsupported completion in every domain."""

import pytest
from pydantic import ValidationError
from test_agent_harness_plan import _skill, _task

from agent.harness_plan import plan_task
from agent.harness_run import (
    AgentHarnessRun,
    HarnessCheckResult,
    observe_context,
    observe_execution,
    start_harness,
    stop_harness,
    validate_run,
)
from agent.skills import HarnessDomain


@pytest.mark.parametrize(
    ("filename", "domain"),
    (
        ("knowledge-evidence.json", "knowledge"),
        ("workflow-check.json", "workflow"),
        ("coding-verify.json", "coding"),
    ),
)
def test_all_domains_need_observed_execution_and_independent_host_checks(
    filename: str, domain: HarnessDomain
) -> None:
    skill = _skill(filename)
    run = start_harness(plan_task(_task(skill), skill, domain))
    if run.phase == "collecting":
        run = observe_context(run, "context-source-1")
    assert run.phase == "executing"
    with pytest.raises(ValueError, match="validation is not expected"):
        validate_run(
            run,
            (
                HarnessCheckResult(
                    check_id="host-check", status="passed", evidence_ref="validator-1"
                ),
            ),
        )
    run = observe_execution(run, "execution-result-1")
    with pytest.raises(ValueError, match="each Host check"):
        validate_run(run, ())
    validated = validate_run(
        run,
        (HarnessCheckResult(check_id="host-check", status="passed", evidence_ref="validator-1"),),
    )
    assert validated.phase == "validated"
    assert [event.sequence for event in validated.events] == list(range(len(validated.events)))
    assert AgentHarnessRun.model_validate(validated.model_dump(mode="json")) == validated
    with pytest.raises(ValueError, match="terminal"):
        stop_harness(validated, "late_error", needs_input=False)


def test_knowledge_gap_needs_input_and_workflow_failure_stops() -> None:
    knowledge = _skill("knowledge-evidence.json")
    asking = start_harness(plan_task(_task(knowledge), knowledge, "knowledge"))
    gap = stop_harness(asking, "raw_evidence_missing", needs_input=True)
    assert gap.phase == "needs_input" and gap.failure_code == "raw_evidence_missing"

    workflow = _skill("workflow-check.json")
    run = start_harness(plan_task(_task(workflow), workflow, "workflow"))
    run = observe_execution(run, "workflow-run-1")
    failed = validate_run(
        run,
        (
            HarnessCheckResult(
                check_id="host-check", status="failed", evidence_ref="check-report-1"
            ),
        ),
    )
    assert failed.phase == "failed" and failed.failure_code == "host_check_failed"
    assert failed.checks[0].status == "failed"
    forged = failed.model_dump(mode="json")
    forged["phase"] = "validated"
    with pytest.raises(ValidationError):
        AgentHarnessRun.model_validate(forged)


def test_coding_retry_is_bounded_and_failure_never_turns_into_success() -> None:
    coding = _skill("coding-verify.json")
    run = start_harness(plan_task(_task(coding), coding, "coding"))
    run = observe_context(run, "workspace-snapshot-1")
    run = observe_execution(run, "candidate-1")
    failure = (
        HarnessCheckResult(check_id="host-check", status="failed", evidence_ref="test-failure-1"),
    )
    retry = validate_run(run, failure)
    assert retry.phase == "collecting" and retry.retry_count == 1
    assert retry.checks == ()
    retry = observe_context(retry, "workspace-snapshot-2")
    retry = observe_execution(retry, "candidate-2")
    exhausted = validate_run(retry, failure)
    assert exhausted.phase == "failed" and exhausted.retry_count == 1
    with pytest.raises(ValueError, match="not expected"):
        observe_execution(exhausted, "candidate-3")


def test_a_repair_retry_keeps_its_context_and_an_adapter_names_the_exhaustion() -> None:
    """Harness unification U1 (owner 2026-10-09): a coding repair executes
    again without replanning; when repairs run out the adapter's code ends it."""
    from agent.harness_plan import build_plan
    from agent.skills import SkillHarnessGuidance
    from common.assets import AssetIdentity

    plan = build_plan(
        task_id="coding-1",
        task_sha256="0" * 64,
        domain="coding",
        skill=AssetIdentity(namespace="engineering", name="coding", version="1.7.0"),
        guidance=SkillHarnessGuidance(domains=("coding",), fallback="retry", max_retries=2),
        host_checks=("tests_new", "tests_suite"),
        max_retries=1,
        retry_from="execute",
        exhausted_code="repair_budget_exceeded",
    )
    assert plan.retry_budget == 1 and plan.stages[0] == "collect_context"
    failed = (
        HarnessCheckResult(check_id="tests_new", status="failed", evidence_ref="t1"),
        HarnessCheckResult(check_id="tests_suite", status="passed", evidence_ref="t2"),
    )
    run = observe_execution(observe_context(start_harness(plan), "plan"), "change-1")
    run = validate_run(run, failed)
    assert run.phase == "executing" and run.retry_count == 1  # no second plan
    run = validate_run(observe_execution(run, "change-2"), failed)
    assert run.phase == "failed" and run.failure_code == "repair_budget_exceeded"


def test_a_host_budget_caps_what_a_skill_asks_for() -> None:
    from agent.harness_plan import build_plan
    from agent.skills import SkillHarnessGuidance
    from common.assets import AssetIdentity

    plan = build_plan(
        task_id="w",
        task_sha256="0" * 64,
        domain="workflow",
        skill=AssetIdentity(namespace="engineering", name="x", version="1.0.0"),
        guidance=SkillHarnessGuidance(domains=("workflow",), fallback="retry", max_retries=3),
        host_checks=("steps_succeeded",),
        max_retries=0,
    )
    assert plan.retry_budget == 0 and plan.fallback == "needs_input"
    assert plan.stages == ("execute", "validate")
