"""Typed Bridge adapter for OS command execution under the actual host account."""

from capabilities.contracts import CapabilitySpec
from capabilities.runtime import CapabilityExecutionFailed, CapabilityRefused, InstalledCapabilities
from common.assets import ExecutionDependencies
from common.base import Contract
from common.execution import RequestContext
from integrations.process_execution import (
    CommandRequest,
    CommandResult,
    ProcessStartError,
    run_command,
)

SPEC = CapabilitySpec.model_validate(
    {
        "identity": {"namespace": "system", "name": "run-command", "version": "1.0.0"},
        "name": "system.run_command",
        "description": (
            "Execute an argv command under the host OS account, including package installers. "
            "No shell interpolation. Returns actual exit code and bounded output; "
            "OS/service permissions apply."
        ),
        "input_contract": "system.run-command.input.v1",
        "output_contract": "system.run-command.output.v1",
        "side_effect": "execute",
        "policy": {"approval_required": False, "required_permissions": [], "policy_refs": []},
    }
)


async def execute(context: RequestContext, inputs: Contract) -> Contract:
    request = CommandRequest.model_validate(inputs)
    try:
        result = await run_command(request)
    except ProcessStartError as error:
        raise CapabilityRefused(error.code) from None
    if result.timed_out or result.exit_code != 0:
        raise CapabilityExecutionFailed(
            "command_timeout" if result.timed_out else "command_failed", result
        )
    return result


def register(installed: InstalledCapabilities) -> None:
    installed.register(
        SPEC,
        execute,
        CommandRequest,
        CommandResult,
        ExecutionDependencies(central_required=False),
        timeout_seconds=1810,
    )
