"""Negative composition gates: invocation, task outcome and failure evidence."""

import asyncio
from pathlib import Path

import pytest
from test_dispatch import Input, Output, invocation, spec
from test_product_e2e_03 import (
    COMMAND,
    FIXTURE,
    TRACE,
    ScriptedAuthor,
    request_for,
    resident,
    workspace,
)
from test_run_python import handler as python_handler
from test_run_python import requires_win32, task

from capabilities.coding_change.manifest import run_python_workflow
from capabilities.coding_change.run_python import (
    RUN_SPEC,
    RunPythonHandler,
    RunPythonRequest,
    RunPythonResult,
    RunPythonStepInput,
)
from capabilities.mcp import MCPCallResult
from capabilities.runtime import (
    CapabilityGrant,
    CapabilityTaskFailed,
    InstalledCapabilities,
    LocalPolicy,
)
from capabilities.workflow_author.contracts import DraftWorkflowRequest, WorkflowDraft
from capabilities.workflow_author.handlers import DRAFT_SPEC, DraftWorkflowHandler
from channels.telegram import _describe
from common.assets import ExecutionDependencies, WorkflowManifest
from common.base import Contract
from common.execution import CapabilityResult, Failure, RouteDecision
from common.local_agent import LocalAgentRequest
from harness.contracts import CodingHarnessRequest, CodingHarnessResult, HarnessPlan, PlannedChange
from host_runtime.agent import LocalAgentOutcome
from host_runtime.answers import readable
from host_runtime.cli import _outcome_text
from workflow.dispatch import BridgeExecutor
from workflow.engine import InstalledWorkflows, WorkflowEngine


def policy_for(installed: InstalledCapabilities) -> LocalPolicy:
    return LocalPolicy(
        tuple(
            CapabilityGrant(
                actor="engineer",
                asset=item.identity,
                permissions=item.policy.required_permissions,
                policy_refs=item.policy.policy_refs,
                approval_ref="approved-inert-fixture",
            )
            for item in installed.discover()
        )
    )


def test_exhausted_coding_repair_is_failed_through_the_resident_path(tmp_path: Path) -> None:
    asked = request_for(workspace(tmp_path), repairs=0)
    agent, bridge, _model = resident(tmp_path, asked, ScriptedAuthor())
    try:
        outcome = asyncio.run(
            agent.handle(
                LocalAgentRequest(
                    ingress="local",
                    actor="engineer",
                    bridge_id="bridge-company",
                    namespace="engineering",
                    message=FIXTURE["requirement"],
                    trace=TRACE,
                )
            )
        )
    finally:
        agent.state.close()
    assert outcome.capability is not None
    assert outcome.capability.status == "failed"
    assert outcome.capability.failure is not None
    assert outcome.capability.failure.code == "repair_budget_exceeded"
    assert isinstance(outcome.capability.data, dict)
    evidence = CodingHarnessResult.model_validate(outcome.capability.data)
    assert evidence.commands[-1].status == "failed"
    assert bridge.events[-1].status == "failed"


@pytest.mark.parametrize(
    ("exit_code", "timed_out", "expected_status", "expected_code"),
    [
        (0, False, "succeeded", None),
        (1, False, "failed", "python_execution_failed"),
        (None, True, "failed", "python_execution_timeout"),
        (None, False, "failed", "python_execution_unknown"),
    ],
)
def test_process_failure_stops_the_workflow_and_retains_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    exit_code: int | None,
    timed_out: bool,
    expected_status: str,
    expected_code: str | None,
) -> None:
    result = RunPythonResult(
        exit_code=exit_code,
        timed_out=timed_out,
        output="synthetic execution evidence",
        files=(),
        script_path=".aep-run/run-001/script.py",
    )

    def controlled_run(
        self: RunPythonHandler, request: RunPythonRequest, arguments: object = None
    ) -> RunPythonResult:
        return result

    monkeypatch.setattr(RunPythonHandler, "run", controlled_run)
    installed = InstalledCapabilities()
    installed.register(
        RUN_SPEC,
        python_handler(tmp_path),
        RunPythonStepInput,
        RunPythonResult,
        ExecutionDependencies(central_required=False),
    )
    calls: list[str] = []

    async def sentinel(context: object, inputs: Contract) -> Contract:
        calls.append("executed")
        return Output(count=1)

    installed.register(
        spec(), sentinel, Input, Output, ExecutionDependencies(central_required=False)
    )
    document = run_python_workflow().model_dump(mode="json")
    document["steps"].append(
        {
            "capability": spec().identity.model_dump(mode="json"),
            "inputs": {"count": {"source": "fixed", "value": 1}},
        }
    )
    workflows = InstalledWorkflows()
    manifest = WorkflowManifest.model_validate(document)
    workflows.register(manifest)
    bridge = BridgeExecutor(installed, policy_for(installed))
    snapshot = asyncio.run(
        WorkflowEngine(workflows, bridge).execute(
            invocation().context,
            manifest.metadata.identity,
            {"workspace": str(tmp_path), "script": "raise SystemExit(1)"},
        )
    )
    assert snapshot.run.status == expected_status
    first = snapshot.step_results[0]
    assert isinstance(first.data, dict)
    assert first.data["exit_code"] == exit_code
    assert first.data["timed_out"] is timed_out
    assert first.data["output"] == "synthetic execution evidence"
    assert calls == (["executed"] if expected_status == "succeeded" else [])
    if expected_code:
        assert snapshot.run.failure is not None
        assert snapshot.run.failure.code == expected_code
        assert not snapshot.run.failure.retryable


def test_diagnostic_negative_data_is_still_successful_invocation() -> None:
    class Diagnostic(Contract):
        outcome: str = "not_found"
        exit_code: int = 1

    async def diagnose(context: object, inputs: Contract) -> Contract:
        return Diagnostic()

    installed = InstalledCapabilities()
    installed.register(
        spec(), diagnose, Input, Diagnostic, ExecutionDependencies(central_required=False)
    )
    result = asyncio.run(BridgeExecutor(installed, policy_for(installed)).execute(invocation()))
    assert result.status == "succeeded"
    assert result.data == {"outcome": "not_found", "exit_code": 1}


def test_installed_draft_refusal_is_shown_without_echoing_the_request() -> None:
    installed = InstalledCapabilities()
    installed.register(
        DRAFT_SPEC,
        DraftWorkflowHandler(installed),
        DraftWorkflowRequest,
        WorkflowDraft,
        ExecutionDependencies(central_required=False),
    )
    call = invocation().model_copy(
        update={
            "target": DRAFT_SPEC.identity,
            "arguments": {"sop": "private procedure never echoed", "namespace": "sample"},
        }
    )
    result = asyncio.run(BridgeExecutor(installed, policy_for(installed)).execute(call))
    outcome = LocalAgentOutcome(
        trace=call.context.trace,
        ingress="local",
        actor="engineer",
        capability=result,
        decision=RouteDecision(kind="capability", target=DRAFT_SPEC.identity, reason="matched"),
    )
    for render in (readable, _outcome_text, _describe):
        text = render(outcome)
        assert "model_not_configured" in text
        assert "private procedure never echoed" not in text
    assert "no model configured" in readable(outcome)


def test_capability_failure_code_and_uncertain_timeout_are_visible_on_every_surface() -> None:
    outcome = LocalAgentOutcome(
        trace=TRACE,
        ingress="local",
        actor="engineer",
        decision=RouteDecision(kind="capability", target=RUN_SPEC.identity, reason="matched"),
        capability=CapabilityResult(
            trace=TRACE,
            status="failed",
            handler_invoked=True,
            failure=Failure(code="timeout", message="wait expired"),
            warnings=("operation_id=operation-" + "a" * 32, "secret=do-not-display"),
        ),
    )
    for render in (readable, _outcome_text, _describe):
        text = render(outcome)
        assert "timeout" in text
        assert "may still be running" in text
        assert "operation_id=operation-" + "a" * 32 in text
        assert "do-not-display" not in text


def test_explicit_mcp_error_is_not_misdiagnosed_as_invalid_input() -> None:
    from test_mcp import FakeMCP, install

    class BrokenTool(FakeMCP):
        async def call_tool(self, name: str, arguments: object) -> MCPCallResult:
            return MCPCallResult(data={"message": "password=do-not-publish"}, is_error=True)

    installed = install(BrokenTool())
    result = asyncio.run(BridgeExecutor(installed, policy_for(installed)).execute(invocation()))
    assert result.status == "failed"
    assert result.failure is not None and result.failure.code == "mcp_tool_failed"
    assert not result.failure.retryable
    assert "do-not-publish" not in result.model_dump_json()


def test_a_task_cannot_publish_failure_evidence_outside_its_output_contract() -> None:
    class WrongOutput(Contract):
        private: str = "private-data-not-in-the-output-contract"

    async def failed(context: object, inputs: Contract) -> Contract:
        raise CapabilityTaskFailed("task_failed", WrongOutput())

    installed = InstalledCapabilities()
    installed.register(spec(), failed, Input, Output, ExecutionDependencies(central_required=False))
    result = asyncio.run(BridgeExecutor(installed, policy_for(installed)).execute(invocation()))
    assert result.failure is not None and result.failure.code == "invalid_output"
    assert result.data is None
    assert "private-data" not in result.model_dump_json()


def test_coding_needs_input_survives_the_bridge_without_workspace_mutation(tmp_path: Path) -> None:
    class DisallowedPlan(ScriptedAuthor):
        def plan(self, request: CodingHarnessRequest) -> HarnessPlan:
            return HarnessPlan(
                summary="An undeclared command requires a changed request",
                changes=(PlannedChange(path=request.artifact_path, purpose="fixture"),),
                validation_commands=(COMMAND + ".undeclared",),
            )

    root = workspace(tmp_path)
    before = (root / "transform.json").read_bytes()
    asked = request_for(root)
    agent, _bridge, _model = resident(tmp_path, asked, DisallowedPlan())
    try:
        outcome = asyncio.run(
            agent.handle(
                LocalAgentRequest(
                    ingress="local",
                    actor="engineer",
                    bridge_id="bridge-company",
                    namespace="engineering",
                    message=FIXTURE["requirement"],
                    trace=TRACE,
                )
            )
        )
    finally:
        agent.state.close()
    assert outcome.capability is not None and outcome.capability.status == "needs_input"
    assert outcome.capability.failure is not None
    assert outcome.capability.failure.code == "plan_command_not_allowed"
    assert (root / "transform.json").read_bytes() == before


@requires_win32
def test_real_restricted_python_exit_one_cannot_complete_an_excel_workflow(tmp_path: Path) -> None:
    root = task(tmp_path)
    installed = InstalledCapabilities()
    installed.register(
        RUN_SPEC,
        python_handler(tmp_path / "tasks"),
        RunPythonStepInput,
        RunPythonResult,
        ExecutionDependencies(central_required=False),
    )
    workflows = InstalledWorkflows()
    manifest = run_python_workflow()
    workflows.register(manifest)
    bridge = BridgeExecutor(installed, policy_for(installed))
    snapshot = asyncio.run(
        WorkflowEngine(workflows, bridge).execute(
            invocation().context,
            manifest.metadata.identity,
            {"workspace": str(root), "script": "print('synthetic failure'); raise SystemExit(1)"},
        )
    )
    assert snapshot.run.status == "failed"
    assert snapshot.run.completed_steps == 0
    assert snapshot.run.failure is not None
    assert snapshot.run.failure.code == "python_execution_failed"
    evidence = RunPythonResult.model_validate(snapshot.step_results[0].data)
    assert evidence.exit_code == 1
    assert "synthetic failure" in evidence.output
    assert not tuple((root / "output").glob("*.xlsx"))
