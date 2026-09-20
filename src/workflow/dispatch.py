"""Local Bridge dispatch: authorization and validation precede every handler call."""

import asyncio
import math
from typing import Literal

from pydantic import ValidationError

from capabilities.runtime import (
    CapabilityInvocation,
    InstalledCapabilities,
    LocalPolicy,
    TransientCapabilityError,
)
from common.assets import AssetIdentity
from common.base import Contract, Symbol
from common.execution import CapabilityResult, Failure, TraceIdentifiers


class ExecutionEvent(Contract):
    trace: TraceIdentifiers
    asset: AssetIdentity
    status: Literal["succeeded", "failed", "needs_input", "unavailable"]
    code: Symbol | None = None


class BridgeExecutor:
    """No retry or process isolation. Handlers must honor asynchronous cancellation."""

    def __init__(
        self,
        installed: InstalledCapabilities,
        policy: LocalPolicy | None = None,
        *,
        services: frozenset[str] = frozenset(),
        timeout_seconds: float = 30,
    ) -> None:
        if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise ValueError("timeout must be finite and positive")
        self.installed = installed
        self.policy = policy if policy is not None else LocalPolicy()
        self.services = services
        self.timeout_seconds = timeout_seconds
        self._events: list[ExecutionEvent] = []

    @property
    def events(self) -> tuple[ExecutionEvent, ...]:
        return tuple(self._events)

    def _finish(self, call: CapabilityInvocation, result: CapabilityResult) -> CapabilityResult:
        self._events.append(
            ExecutionEvent(
                trace=call.context.trace,
                asset=call.target,
                status=result.status,
                code=result.failure.code if result.failure else None,
            )
        )
        return result

    def _failure(
        self,
        call: CapabilityInvocation,
        code: str,
        *,
        unavailable: bool = False,
        retryable: bool = False,
    ) -> CapabilityResult:
        return self._finish(
            call,
            CapabilityResult(
                trace=call.context.trace,
                status="unavailable" if unavailable else "failed",
                failure=Failure(
                    code=code, message="Capability invocation did not complete", retryable=retryable
                ),
            ),
        )

    async def execute(self, invocation: CapabilityInvocation) -> CapabilityResult:
        call = CapabilityInvocation.model_validate(invocation)
        binding = self.installed.get(call.target)
        if binding is None:
            return self._failure(call, "capability_not_installed", unavailable=True)
        authorization = self.policy.authorize(call.context, binding.spec)
        if not authorization.allowed:
            return self._failure(call, "permission_denied")
        dependencies = binding.dependencies
        if not set(dependencies.local_capabilities).issubset(self.installed.names):
            return self._failure(call, "missing_local_capability", unavailable=True)
        if any(
            service.required and service.name not in self.services
            for service in dependencies.central_services
        ):
            return self._failure(call, "needs_connectivity", unavailable=True)
        if binding.secrets:
            return self._failure(call, "secret_resolution_unavailable", unavailable=True)
        try:
            inputs = binding.input_model.model_validate(call.arguments, strict=True)
        except ValidationError:
            return self._failure(call, "invalid_input")
        try:
            output = await asyncio.wait_for(
                binding.handler(call.context, inputs), self.timeout_seconds
            )
        except TimeoutError:
            return self._failure(call, "timeout")
        except TransientCapabilityError:
            return self._failure(
                call, "transient_failure", retryable=binding.spec.side_effect == "read"
            )
        except Exception:
            # Exception text may contain credentials or input data; never trace it.
            return self._failure(call, "handler_error")
        try:
            checked = binding.output_model.model_validate(output, strict=True)
            result = CapabilityResult(
                trace=call.context.trace, status="succeeded", data=checked.model_dump(mode="json")
            )
        except (ValidationError, TypeError, ValueError):
            return self._failure(call, "invalid_output")
        return self._finish(call, result)
