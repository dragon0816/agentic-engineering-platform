"""The resident Agent on a Bridge computer.

It admits before it routes, on every ingress alike, from the device's own copy
of its membership; then it hands the request to the same `Gateway` every other
caller uses, so the ingress changes where a request came from and nothing
about what may run. Every workflow it starts is recorded in the durable local
state under the platform actor who asked. It holds no authority of its own:
capability authorization stays in the Bridge policy, and a published asset
still executes only where it is installed.
"""

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Literal, Self

from pydantic import model_validator

from agent.gateway import Gateway
from common.base import Contract, Symbol
from common.distribution import BridgeStateSnapshot, LocalRunSummary, RemoteWorkflowJob
from common.execution import CapabilityResult, RequestContext, RouteDecision, TraceIdentifiers
from common.local_agent import BridgeMembership, Ingress, LocalAgentRequest
from host_runtime.state import SqliteLocalState
from workflow.engine import WorkflowRunSnapshot

LocalRefusalCode = Literal[
    "device_mismatch",
    "device_disabled",
    "company_owner_required",
    "actor_not_bound",
    "workflow_not_installed",
]


class LocalAgentOutcome(Contract):
    """What the resident Agent did with one request. A refusal carries its
    code and nothing else, because nothing else happened."""

    trace: TraceIdentifiers
    ingress: Ingress
    actor: Symbol
    refusal: LocalRefusalCode | None = None
    decision: RouteDecision | None = None
    capability: CapabilityResult | None = None
    workflow: WorkflowRunSnapshot | None = None
    run: LocalRunSummary | None = None

    @model_validator(mode="after")
    def refusal_is_the_whole_story(self) -> Self:
        happened = (self.decision, self.capability, self.workflow, self.run)
        if self.refusal is not None and any(item is not None for item in happened):
            raise ValueError("a refused request routed nothing and ran nothing")
        if (self.workflow is None) != (self.run is None):
            raise ValueError("every workflow the agent started is recorded, and only those")
        if self.capability is not None and self.workflow is not None:
            raise ValueError("one request runs one capability or one workflow")
        return self


class LocalAgent:
    def __init__(
        self,
        membership: BridgeMembership,
        gateway: Gateway,
        state: SqliteLocalState,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.membership = BridgeMembership.model_validate(membership)
        self.gateway = gateway
        self.state = state
        self._clock = clock if clock is not None else lambda: datetime.now(UTC)

    def admit(self, actor: str, bridge_id: str) -> LocalRefusalCode | None:
        """The membership rule, the same for a local operator, a polled job
        and a Telegram sender: this device, active, and an actor it is bound
        to, who on a company workstation is its registered owner."""
        device = self.membership.device
        if bridge_id != device.bridge_id:
            return "device_mismatch"
        if device.status != "active":
            return "device_disabled"
        if device.device_kind == "company_workstation" and actor != device.registered_by:
            return "company_owner_required"
        if self.membership.binding_for(actor) is None:
            return "actor_not_bound"
        return None

    async def handle(self, request: LocalAgentRequest) -> LocalAgentOutcome:
        """Route a message through the Gateway: deterministic first, the Bridge
        policy on every dispatch, the engine on every workflow."""
        item = LocalAgentRequest.model_validate(request)
        refusal = self.admit(item.actor, item.bridge_id)
        if refusal is not None:
            return LocalAgentOutcome(
                trace=item.trace, ingress=item.ingress, actor=item.actor, refusal=refusal
            )
        context = RequestContext(
            trace=item.trace,
            actor=item.actor,
            namespace=item.namespace,
            message=item.message,
            channel=item.ingress,
            session_id=item.session_id,
        )
        result = await self.gateway.handle(context)
        run = await self._record(item.actor, result.workflow)
        return LocalAgentOutcome(
            trace=item.trace,
            ingress=item.ingress,
            actor=item.actor,
            decision=result.routing.decision,
            capability=result.capability,
            workflow=result.workflow,
            run=run,
        )

    async def execute(self, job: RemoteWorkflowJob) -> LocalAgentOutcome:
        """Run a remote job's exact workflow: no routing, no model, and only
        a workflow installed on this Bridge. The job's authorization is the
        control plane's decision; the Bridge policy still decides each step."""
        item = RemoteWorkflowJob.model_validate(job)
        refusal = self.admit(item.actor, item.bridge_id)
        if refusal is None and self.gateway.engine.workflows.get(item.workflow) is None:
            refusal = "workflow_not_installed"
        if refusal is not None:
            return LocalAgentOutcome(
                trace=item.trace, ingress=item.ingress, actor=item.actor, refusal=refusal
            )
        context = RequestContext(
            trace=item.trace,
            actor=item.actor,
            namespace=item.workflow.namespace,
            message=f"remote job {item.job_id}",
            channel=item.ingress,
        )
        snapshot = await self.gateway.execute_workflow(context, item.workflow, dict(item.arguments))
        run = await self._record(item.actor, snapshot)
        return LocalAgentOutcome(
            trace=item.trace, ingress=item.ingress, actor=item.actor, workflow=snapshot, run=run
        )

    async def _record(
        self, actor: str, snapshot: WorkflowRunSnapshot | None
    ) -> LocalRunSummary | None:
        if snapshot is None:
            return None
        summary = LocalRunSummary(
            run_id=snapshot.run.run_id,
            actor=actor,
            workflow=snapshot.run.workflow,
            status=snapshot.run.status,
            updated_at=self._clock(),
        )
        # A durable write touches the disk under the store's lock, so it never
        # runs on the event loop the in-flight runs share.
        return await asyncio.to_thread(self.state.record_run, summary)

    def runs(self) -> tuple[LocalRunSummary, ...]:
        return self.state.runs()

    def snapshot(self, *, observed_at: datetime) -> BridgeStateSnapshot:
        """The authoritative state of this Bridge, for the control plane to
        project and for the operator to read locally."""
        return self.state.snapshot(self.membership.device, observed_at=observed_at)
