"""Platform entry point: one dispatch contract behind deterministic-first routing.

The Gateway adds no authority and holds no domain logic. Capability dispatch is
authorized by LocalPolicy inside the Bridge; workflow pre-flights belong to the
engine. Model-selected routes dispatch through exactly the same contract as
deterministic ones, so a trigger's origin never changes what may execute.
"""

import asyncio
from typing import Literal, Self

from pydantic import JsonValue, TypeAdapter, model_validator

from agent.routing import RequestRouter, RoutingOutcome
from capabilities.runtime import CapabilityInvocation
from common.assets import AssetIdentity
from common.base import Contract, Symbol
from common.execution import (
    CapabilityResult,
    Failure,
    IdempotencyKey,
    RequestContext,
    ResumePlan,
    ResumePolicy,
    RunId,
)
from workflow.checkpoints import CheckpointStoreError
from workflow.dispatch import BridgeExecutor
from workflow.engine import ProgressStream, WorkflowEngine, WorkflowRunSnapshot
from workflow.journal import SuspensionConfirmation


class RunControlResult(Contract):
    """Host-triggered run control. `run_id` echoes the request; a continuation's
    own id is only in `workflow.run.run_id`.

    `source` says which evidence answered: `memory` is this process's run
    history, `journal` is the durable record that outlives it, and `unknown`
    means the run is unknown to this caller — missing, evicted, never journalled
    or owned by another actor, all indistinguishable on purpose.
    """

    action: Literal["inspect", "resume", "suspend"]
    run_id: RunId
    source: Literal["memory", "journal", "unknown"] = "unknown"
    plan: ResumePlan | None = None
    workflow: WorkflowRunSnapshot | None = None
    suspended_by: Symbol | None = None

    @model_validator(mode="after")
    def payload_matches_action(self) -> Self:
        if self.action == "inspect" and self.workflow is not None:
            raise ValueError("inspect never executes a run")
        if self.action == "resume" and (self.plan is not None or self.suspended_by is not None):
            raise ValueError("resume reports the continuation, not a plan")
        if self.action == "suspend" and self.workflow is not None:
            raise ValueError("suspend records a confirmation; it never executes a run")
        if self.suspended_by is not None and self.source != "journal":
            raise ValueError("only the durable record carries a confirmation")
        if self.source == "unknown" and (self.plan is not None or self.workflow is not None):
            raise ValueError("an unknown run has no evidence to report")
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
            snapshot = await self.execute_workflow(
                context,
                decision.target,
                outcome.arguments,
                workflow_timeout_seconds=workflow_timeout_seconds,
                workflow_idempotency_key=workflow_idempotency_key,
            )
            return GatewayResult(routing=outcome, workflow=snapshot)
        # needs_input: nothing executes. A resolved decision without a target is
        # impossible by contract and would fail GatewayResult validation loudly.
        return GatewayResult(routing=outcome)

    async def execute_workflow(
        self,
        request: RequestContext,
        workflow: AssetIdentity,
        arguments: dict[str, JsonValue] | None = None,
        *,
        workflow_timeout_seconds: float | None = None,
        workflow_idempotency_key: IdempotencyKey | None = None,
    ) -> WorkflowRunSnapshot:
        """Exact-target host entry point shared by routed workflows and integrations.

        No routing/model call and no added authority. The engine owns validation,
        execution policy, idempotency and the default caller-wait timeout.
        """
        if workflow_timeout_seconds is None:
            return await self.engine.execute(
                request, workflow, arguments, idempotency_key=workflow_idempotency_key
            )
        return await self.engine.execute(
            request,
            workflow,
            arguments,
            timeout_seconds=workflow_timeout_seconds,
            idempotency_key=workflow_idempotency_key,
        )

    def inspect(self, request: RequestContext, run_id: RunId) -> RunControlResult:
        """Classify a run's steps for its owner; never executes anything.

        The durable record answers whenever it exists, because it alone knows
        whether a run has been suspended or already continued; this process's
        own history answers for everything else. `source` says which.

        Durable reads happen on the calling thread: a host already inside an
        event loop should call this through `asyncio.to_thread`.
        """
        entry = self.engine.inspect_journal(request, run_id)
        if entry is not None:
            return RunControlResult(
                action="inspect",
                run_id=run_id,
                source="journal",
                plan=entry.plan,
                suspended_by=entry.suspended_by,
            )
        plan = self.engine.inspect(request, run_id)
        if plan is None:
            return RunControlResult(action="inspect", run_id=run_id)
        return RunControlResult(action="inspect", run_id=run_id, source="memory", plan=plan)

    def suspend(
        self, request: RequestContext, run_id: RunId, confirmation: SuspensionConfirmation
    ) -> RunControlResult:
        """Record a person's confirmation that the process owning a run is gone.

        Only a journalled run can be suspended, because only durable evidence
        outlives the process whose absence is being confirmed. A run this caller
        cannot see is `unknown`, like everywhere else; a run that is alive here
        or already suspended raises the engine's own closed code rather than a
        second vocabulary invented at this layer.

        Durable writes happen on the calling thread: a host already inside an
        event loop should call this through `asyncio.to_thread`.
        """
        try:
            entry = self.engine.suspend(request, run_id, confirmation)
        except CheckpointStoreError as error:
            if error.code != "missing":
                raise
            entry = None
        if entry is None:
            return RunControlResult(action="suspend", run_id=run_id)
        return RunControlResult(
            action="suspend",
            run_id=run_id,
            source="journal",
            plan=entry.plan,
            suspended_by=entry.suspended_by,
        )

    async def resume(
        self,
        request: RequestContext,
        run_id: RunId,
        *,
        policy: ResumePolicy | None = None,
        workflow_timeout_seconds: float | None = None,
    ) -> RunControlResult:
        """Continue a finished run through the same engine contract as routed workflows.

        A journalled run is continued through recovery, so its continuation is
        journalled too and the durable "continued once" guard is honoured; every
        other run uses the in-memory path. The policy is a host/caller option and
        is never derived from the request message or a model. Run control is not
        a Skill route, so no model-selected route can trigger it; ownership and
        authorization stay in the engine.
        """
        # Reading the durable record touches the disk under the store's lock, so
        # it never runs on the event loop the in-flight runs share.
        journalled = (
            await asyncio.to_thread(self.engine.inspect_journal, request, run_id) is not None
        )
        timeout = (
            {}
            if workflow_timeout_seconds is None
            else {"timeout_seconds": workflow_timeout_seconds}
        )
        snapshot = (
            await self.engine.recover(request, run_id, policy, **timeout)
            if journalled
            else await self.engine.resume(request, run_id, policy, **timeout)
        )
        if snapshot is None:
            return RunControlResult(action="resume", run_id=run_id)
        return RunControlResult(
            action="resume",
            run_id=run_id,
            source="journal" if journalled else "memory",
            workflow=snapshot,
        )

    def watch(self, request: RequestContext, run_id: RunId) -> ProgressStream | None:
        """Bounded progress stream for the run's owner through the same engine contract.

        None means the run is unknown to this caller. The stream carries
        identities, statuses and codes only, never payloads, and never blocks
        the run; the Gateway adds no authority.
        """
        # Malformed ids fail loudly here like inspect/resume; typos are unknown runs.
        return self.engine.watch(request, TypeAdapter(RunId).validate_python(run_id))
