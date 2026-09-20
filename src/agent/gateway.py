"""Platform entry point: one dispatch contract behind deterministic-first routing.

The Gateway adds no authority and holds no domain logic. Capability dispatch is
authorized by LocalPolicy inside the Bridge; workflow pre-flights belong to the
engine. Model-selected routes dispatch through exactly the same contract as
deterministic ones, so a trigger's origin never changes what may execute.
"""

import asyncio
from typing import Self

from pydantic import model_validator

from agent.routing import RequestRouter, RoutingOutcome
from capabilities.runtime import CapabilityInvocation
from common.base import Contract
from common.execution import CapabilityResult, RequestContext
from workflow.dispatch import BridgeExecutor
from workflow.engine import WorkflowEngine, WorkflowRunSnapshot


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
        self, request: RequestContext, *, workflow_timeout_seconds: float | None = None
    ) -> GatewayResult:
        context = RequestContext.model_validate(request)
        # Routing is synchronous and the model client owns blocking I/O, so it
        # must never run on the event loop where driving tasks live.
        outcome = await asyncio.to_thread(self.router.route, context)
        decision = outcome.decision
        if decision.kind == "capability" and decision.target is not None:
            result = await self.bridge.execute(
                CapabilityInvocation(
                    context=context, target=decision.target, arguments=outcome.arguments
                )
            )
            return GatewayResult(routing=outcome, capability=result)
        if decision.kind == "workflow" and decision.target is not None:
            if workflow_timeout_seconds is None:
                # The engine owns the default caller-wait timeout.
                snapshot = await self.engine.execute(context, decision.target, outcome.arguments)
            else:
                snapshot = await self.engine.execute(
                    context,
                    decision.target,
                    outcome.arguments,
                    timeout_seconds=workflow_timeout_seconds,
                )
            return GatewayResult(routing=outcome, workflow=snapshot)
        # needs_input: nothing executes. A resolved decision without a target is
        # impossible by contract and would fail GatewayResult validation loudly.
        return GatewayResult(routing=outcome)
