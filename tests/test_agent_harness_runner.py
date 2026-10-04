"""The same bounded runner drives Knowledge, Workflow and Coding actions."""

from pathlib import Path

import pytest

from agent.harness_plan import AgentHarnessPlan, plan_task
from agent.harness_run import HarnessCheckResult
from agent.harness_runner import HarnessActionFailure, run_harness
from agent.skills import HarnessDomain, SkillManifest
from agent.task_contract import (
    CompletionCheck,
    ExpectedOutput,
    TaskContract,
    TaskExecutionConstraints,
)
from common.assets import AssetIdentity
from common.execution import TraceIdentifiers

FIXTURES = Path(__file__).parent / "fixtures" / "harness_skills"


class RecordedActions:
    def __init__(self, *, fail_first_check: bool = False) -> None:
        self.calls: list[str] = []
        self.fail_first_check = fail_first_check

    def collect_context(self) -> str:
        self.calls.append("context")
        return "context-record"

    def execute(self) -> str:
        self.calls.append("execute")
        return "execution-record"

    def validate(self) -> tuple[HarnessCheckResult, ...]:
        self.calls.append("validate")
        status = (
            "failed" if self.fail_first_check and self.calls.count("validate") == 1
            else "passed"
        )
        return (
            HarnessCheckResult(
                check_id="host-check", status=status, evidence_ref="check-record"
            ),
        )


def _plan(filename: str, domain: HarnessDomain) -> AgentHarnessPlan:
    skill = SkillManifest.model_validate_json((FIXTURES / filename).read_text(encoding="utf-8"))
    task = TaskContract(
        task_id="task-runner-test",
        trace=TraceIdentifiers(trace_id="trace-1", request_id="request-1", span_id="run"),
        actor="engineer",
        namespace=skill.metadata.identity.namespace,
        objective="Complete with Host checks",
        skills=(skill.metadata.identity,),
        allowed_capabilities=(AssetIdentity(namespace="test", name="read", version="1.0.0"),),
        expected_outputs=(ExpectedOutput(output_id="answer", artifact_ref="answer-1"),),
        checks=(CompletionCheck(check_id="host-check", output_id="answer", kind="nonempty"),),
        constraints=TaskExecutionConstraints(max_retries=1),
    )
    return plan_task(task, skill, domain)


@pytest.mark.parametrize(
    ("filename", "domain", "expected"),
    (
        ("knowledge-evidence.json", "knowledge", ["context", "execute", "validate"]),
        ("workflow-check.json", "workflow", ["execute", "validate"]),
        ("coding-verify.json", "coding", ["context", "execute", "validate"]),
    ),
)
def test_runner_uses_one_state_machine_for_all_domains(
    filename: str, domain: HarnessDomain, expected: list[str]
) -> None:
    actions = RecordedActions()
    run = run_harness(_plan(filename, domain), actions)
    assert run.phase == "validated"
    assert actions.calls == expected
    assert run.events[-1].kind == "validated"


def test_runner_retries_only_within_skill_and_task_budget() -> None:
    actions = RecordedActions(fail_first_check=True)
    run = run_harness(_plan("coding-verify.json", "coding"), actions)
    assert run.phase == "validated"
    assert run.retry_count == 1
    assert actions.calls == ["context", "execute", "validate"] * 2


def test_runner_preserves_typed_adapter_stop() -> None:
    class RefusedActions(RecordedActions):
        def execute(self) -> str:
            raise HarnessActionFailure("permission_denied")

    run = run_harness(_plan("workflow-check.json", "workflow"), RefusedActions())
    assert run.phase == "failed"
    assert run.failure_code == "permission_denied"
    assert all(event.kind != "validated" for event in run.events)
