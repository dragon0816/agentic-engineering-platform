"""Platform entry point: one dispatch contract behind deterministic-first routing.

The Gateway adds no authority and holds no domain logic. Capability dispatch is
authorized by LocalPolicy inside the Bridge; workflow pre-flights belong to the
engine. Model-selected routes dispatch through exactly the same contract as
deterministic ones, so a trigger's origin never changes what may execute.
"""

import asyncio
from typing import Annotated, Literal, Self

from pydantic import StringConstraints, model_validator

from agent.routing import RequestRouter, RoutingOutcome
from capabilities.runtime import CapabilityInvocation
from common.base import Contract
from common.execution import (
    CapabilityResult,
    Failure,
    IdempotencyKey,
    RequestContext,
    ResumePlan,
    ResumePolicy,
)
from workflow.dispatch import BridgeExecutor
from workflow.engine import WorkflowEngine, WorkflowRunSnapshot

# Lenient on purpose: a mistyped id is "unknown to this caller", not a crash.
RunId = Annotated[str, StringConstraints(strict=True, min_length=1, max_length=128)]


class RunControlResult(Contract):
    """Host-triggered run control. Both payload fields None means the run is
    unknown to this caller (missing, evicted or owned by another actor)."""

    action: Literal["inspect", "resume"]
    run_id: RunId
    plan: ResumePlan | None = None
    workflow: WorkflowRunSnapshot | None = None

    @model_validator(mode="after")
    def payload_matches_action(self) -> Self:
        if self.action == "inspect" and self.workflow is not None:
            raise ValueError("inspect never executes a run")
        if self.action == "resume" and self.plan is not None:
            raise ValueError("resume reports the continuation, not a plan")
        return self


class GatewayResult(Contract):
    routing: RoutingOutcome
    capability: CapabilityResult | None = None
    workflow: WorkflowRunSnapshot | None = None

    @model_validator(mode="after")
    def execution_matches_decision(self) -> Self:
        matches = {
            "capability": self.capability is not None and self.workflow is None,
            "workflow": self.workflow is not None and self.capability is None,
            "needs_input": self.capability is None and self.workflow is None,
        }
        if not matches.get(self.routing.decision.kind, False):
            raise ValueError("execution results must match the routing decision")
        return self


class Gateway:
    def __init__(self, router: RequestRouter, bridge: BridgeExecutor, engine: WorkflowEngine):
        self.router = router
        self.bridge = bridge
        self.engine = engine

    async def handle(
        self,
        request: RequestContext,
        *,
        workflow_timeout_seconds: float | None = None,
        workflow_idempotency_key: IdempotencyKey | None = None,
    ) -> GatewayResult:
        context = RequestContext.model_validate(request)
        # Routing is synchronous and the model client owns blocking I/O, so it
        # must never run on the event loop where driving tasks live.
        outcome = await asyncio.to_thread(self.router.route, context)
        decision = outcome.decision
        if decision.kind == "capability" and decision.target is not None:
            if workflow_idempotency_key is not None:
                return GatewayResult(
                    routing=outcome,
                    capability=CapabilityResult(
                        trace=context.trace,
                        status="unavailable",
                        failure=Failure(
                            code="idempotency_not_supported",
                            message="Idempotency keys require a workflow route",
                        ),
                    ),
                )
            result = await self.bridge.execute(
                CapabilityInvocation(
                    context=context, target=decision.target, arguments=outcome.arguments
                )
            )
            return GatewayResult(routing=outcome, capability=result)
        if decision.kind == "workflow" and decision.target is not None:
            if workflow_timeout_seconds is None:
                # The engine owns the default caller-wait timeout.
                snapshot = await self.engine.execute(
                    context,
                    decision.target,
                    outcome.arguments,
                    idempotency_key=workflow_idempotency_key,
                )
            else:
                snapshot = await self.engine.execute(
                    context,
                    decision.target,
                    outcome.arguments,
                    timeout_seconds=workflow_timeout_seconds,
                    idempotency_key=workflow_idempotency_key,
                )
            return GatewayResult(routing=outcome, workflow=snapshot)
        # needs_input: nothing executes. A resolved decision without a target is
        # impossible by contract and would fail GatewayResult validation loudly.
        return GatewayResult(routing=outcome)

    async def inspect(self, request: RequestContext, run_id: RunId) -> RunControlResult:
        """Classify a retained run's steps for its owner; never executes anything."""
        context = RequestContext.model_validate(request)
        checked = RunControlResult(action="inspect", run_id=run_id)
        return checked.model_copy(update={"plan": self.engine.inspect(context, checked.run_id)})

    async def resume(
        self,
        request: RequestContext,
        run_id: RunId,
        *,
        policy: ResumePolicy | None = None,
        workflow_timeout_seconds: float | None = None,
    ) -> RunControlResult:
        """Continue a finished run through the same engine contract as routed workflows.

        The policy is a host/caller option and is never derived from the request
        message or a model. Run control is not a Skill route, so no model-selected
        route can trigger it; ownership and authorization stay in the engine.
        """
        context = RequestContext.model_validate(request)
        checked = RunControlResult(action="resume", run_id=run_id)
        if workflow_timeout_seconds is None:
            # The engine owns the default caller-wait timeout.
            snapshot = await self.engine.resume(context, checked.run_id, policy)
        else:
            snapshot = await self.engine.resume(
                context, checked.run_id, policy, timeout_seconds=workflow_timeout_seconds
            )
        return checked.model_copy(update={"workflow": snapshot})
