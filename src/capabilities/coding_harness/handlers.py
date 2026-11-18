"""Bridge-installed coding Harness capability."""

from pathlib import Path

from capabilities.contracts import CapabilitySpec
from capabilities.runtime import CapabilityTaskFailed
from common.base import Contract
from common.execution import RequestContext
from harness.contracts import CodingHarnessRequest, CodingHarnessResult
from harness.runtime import CodingHarness
from harness.thread_operations import run_tracked_thread

CODING_HARNESS_SPEC = CapabilitySpec.model_validate(
    {
        "identity": {"namespace": "coding-harness", "name": "run", "version": "1.0.0"},
        "name": "coding_harness.run",
        "description": "Plan, change, validate and boundedly repair one workspace artifact",
        "input_contract": "coding-harness.run.input.v1",
        "output_contract": "coding-harness.run.output.v1",
        "side_effect": "write",
        "policy": {
            "risk": "medium",
            "approval_required": True,
            "required_permissions": ["coding-harness.run"],
            "policy_refs": ["coding-harness-workspace-policy"],
        },
    }
)


class CodingHarnessHandler:
    def __init__(self, harness: CodingHarness) -> None:
        self.harness = harness

    async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
        request = CodingHarnessRequest.model_validate(inputs)

        def execute() -> CodingHarnessResult:
            result = self.harness.run(context.trace, request)
            if result.status != "validated":
                code = (
                    result.failure.code
                    if result.failure is not None
                    else "coding_validation_failed"
                )
                raise CapabilityTaskFailed(code, result, needs_input=result.status == "needs_input")
            return result

        return await run_tracked_thread(Path(request.workspace.root), execute)
