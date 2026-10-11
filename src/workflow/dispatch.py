"""Local Bridge dispatch: authorization and validation precede every handler call."""

import asyncio
import json
import math
import threading
from contextlib import nullcontext
from typing import Literal

from pydantic import ValidationError

import telemetry.recorder as telemetry
from capabilities.runtime import (
    CapabilityInvocation,
    CapabilityRefused,
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
        # Requests may run concurrently on separate threads (one event loop
        # each). Anything that can change a shared resource (a workbook, a
        # draft, a release) and every workflow run is serialized here; reads
        # run in parallel. Reentrant, so a workflow's own write steps on the
        # same thread do not wait for themselves.
        self.exclusive = threading.RLock()

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
        invoked: bool = False,
        message: str = "Capability invocation did not complete",
    ) -> CapabilityResult:
        return self._finish(
            call,
            CapabilityResult(
                trace=call.context.trace,
                status="unavailable" if unavailable else "failed",
                failure=Failure(code=code, message=message, retryable=retryable),
                handler_invoked=invoked,
            ),
        )

    async def execute(self, invocation: CapabilityInvocation) -> CapabilityResult:
        """Every capability call, as a Bridge-layer `tool.completed` span."""
        target = getattr(invocation, "target", None)
        tool_id = None if target is None else (
            f"{target.namespace}/{target.name}@{target.version}")
        telemetry.note_tool()
        with telemetry.span("capability", attributes={"tool_id": tool_id, "layer": "bridge"},
                            completed="tool.completed") as step:
            result = await self._execute(invocation)
            if result.status != "succeeded":
                step.update(status="failed", outcome=result.status,
                            failure_code=None if result.failure is None
                            else result.failure.code)
            return result

    async def _execute(self, invocation: CapabilityInvocation) -> CapabilityResult:
        call = CapabilityInvocation.model_validate(invocation)
        binding = self.installed.get(call.target)
        if binding is None:
            return self._failure(call, "capability_not_installed", unavailable=True)
        confirm = getattr(self.policy, "confirmation_needed", None)
        if confirm is not None and confirm(binding.spec, call.origin):
            return self._failure(call, "approval_required")
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
            # Strict against JSON: a step's arguments are what an earlier
            # step's output serialized to, so a list is a tuple and an ISO
            # string is a date, while "1" is still not an integer.
            inputs = binding.input_model.model_validate_json(
                json.dumps(call.arguments), strict=True
            )
        except ValidationError as error:
            # Where and what kind, never the value: the caller (often a model
            # drafting a Workflow) can fix its input without the input being
            # echoed into traces.
            return self._failure(call, "invalid_input", message=_where_invalid(error))
        except (TypeError, ValueError):
            return self._failure(call, "invalid_input")
        guard = nullcontext() if binding.spec.side_effect == "read" else self.exclusive
        try:
            with guard:
                output = await asyncio.wait_for(
                    binding.handler(call.context, inputs), self.timeout_seconds
                )
        except TimeoutError:
            return self._failure(call, "timeout", invoked=True)
        except CapabilityRefused as refusal:
            # The handler named why; only the code, and where in the request, travel.
            if refusal.where:
                return self._failure(call, refusal.code, invoked=True,
                                     message=f"Refused at {refusal.where}")
            return self._failure(call, refusal.code, invoked=True)
        except TransientCapabilityError:
            return self._failure(
                call,
                "transient_failure",
                retryable=binding.spec.side_effect == "read",
                invoked=True,
            )
        except ValueError:
            # A handler that raises ValueError is refusing what it was given:
            # the input, or the thing the input pointed it at. Its text may
            # quote either, so only the code travels.
            return self._failure(call, "invalid_input", invoked=True)
        except Exception:
            # Exception text may contain credentials or input data; never trace it.
            return self._failure(call, "handler_error", invoked=True)
        try:
            checked = binding.output_model.model_validate(output, strict=True)
            result = CapabilityResult(
                trace=call.context.trace,
                status="succeeded",
                data=checked.model_dump(mode="json"),
                handler_invoked=True,
            )
        except (ValidationError, TypeError, ValueError):
            return self._failure(call, "invalid_output", invoked=True)
        return self._finish(call, result)


def _where_invalid(error: ValidationError) -> str:
    places = [
        f"{'.'.join(str(part) for part in item['loc']) or 'input'}: {item['type']}"
        for item in error.errors()[:6]
    ]
    return "Invalid input at " + "; ".join(places)
