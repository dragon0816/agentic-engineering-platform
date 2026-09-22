"""The resident Agent on a Bridge computer.

It admits before it routes, on every ingress alike, from the device's own copy
of its membership; then it hands the request to the same `Gateway` every other
caller uses, so the ingress changes where a request came from and nothing
about what may run. Every workflow run it starts is recorded in the durable
local state under the platform actor who asked, and brought to its final
state when the run outlives the caller's wait. It holds no authority of its
own: capability authorization stays in the Bridge policy, and a published
asset still executes only where it is installed.
"""

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Literal, Self

from pydantic import model_validator

from agent.gateway import Gateway
from common.base import Contract, Symbol
from common.distribution import (
    BridgeStateSnapshot,
    LocalRunSummary,
    LocalStateError,
    LocalStateErrorCode,
    RemoteWorkflowJob,
)
from common.enrollment import DeviceAdmissionCode, admit_device
from common.execution import CapabilityResult, RequestContext, RouteDecision, TraceIdentifiers
from common.local_agent import BridgeMembership, Ingress, LocalAgentRequest
from host_runtime.state import SqliteLocalState
from workflow.engine import WorkflowRunSnapshot

LocalRefusalCode = DeviceAdmissionCode | Literal["actor_not_bound", "delegation_not_allowed"]


class LocalAgentOutcome(Contract):
    """What the resident Agent did with one request.

    A refusal carries its code and nothing else, because nothing else
    happened. A workflow result without a `run` is a pre-flight rejection the
    engine answered without starting anything, unless `unrecorded` says the
    run did start and its record could not be written: that is reported, not
    raised, because the workflow's outcome is what the caller needs most."""

    trace: TraceIdentifiers
    ingress: Ingress
    actor: Symbol
    # Who asked, when the machine ran the work for somebody not bound to it.
    on_behalf_of: Symbol | None = None
    refusal: LocalRefusalCode | None = None
    decision: RouteDecision | None = None
    capability: CapabilityResult | None = None
    workflow: WorkflowRunSnapshot | None = None
    run: LocalRunSummary | None = None
    unrecorded: LocalStateErrorCode | None = None

    @model_validator(mode="after")
    def refusal_is_the_whole_story(self) -> Self:
        happened = (self.decision, self.capability, self.workflow, self.run, self.unrecorded)
        if self.refusal is not None and any(item is not None for item in happened):
            raise ValueError("a refused request routed nothing and ran nothing")
        if self.capability is not None and self.workflow is not None:
            raise ValueError("one request runs one capability or one workflow")
        if self.run is not None:
            if self.workflow is None or self.run.run_id != self.workflow.run.run_id:
                raise ValueError("a run record belongs to the workflow result beside it")
            if self.unrecorded is not None:
                raise ValueError("a run is recorded or its record failed, not both")
        if self.unrecorded is not None and self.workflow is None:
            raise ValueError("only a workflow that ran can have gone unrecorded")
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
        self._settling: set[asyncio.Task[None]] = set()

    def admit(
        self, actor: str, bridge_id: str, on_behalf_of: str | None = None
    ) -> LocalRefusalCode | None:
        """The membership rule, the same for a local operator, a polled job
        and a Telegram sender. The device half is `admit_device`, shared with
        the control plane; the binding half reads this device's own copy.

        Only the acting member is admitted. Who asked is recorded and never
        weighed, except for one refusal: a company workstation accepts only
        its one bound owner, and work done on somebody else's behalf is not
        that, so it is refused outright rather than attributed."""
        refused = admit_device(self.membership.device, actor=actor, bridge_id=bridge_id)
        if refused is not None:
            return refused
        if self.membership.binding_for(actor) is None:
            return "actor_not_bound"
        if on_behalf_of is not None and self.membership.device.device_kind == "company_workstation":
            return "delegation_not_allowed"
        return None

    async def handle(
        self, request: LocalAgentRequest, *, workflow_timeout_seconds: float | None = None
    ) -> LocalAgentOutcome:
        """Route a message through the Gateway: deterministic first, the Bridge
        policy on every dispatch, the engine on every workflow."""
        item = LocalAgentRequest.model_validate(request)
        refusal = self.admit(item.actor, item.bridge_id, item.on_behalf_of)
        if refusal is not None:
            return LocalAgentOutcome(
                trace=item.trace,
                ingress=item.ingress,
                actor=item.actor,
                on_behalf_of=item.on_behalf_of,
                refusal=refusal,
            )
        context = RequestContext(
            trace=item.trace,
            actor=item.actor,
            namespace=item.namespace,
            message=item.message,
            channel=item.ingress,
            session_id=item.session_id,
        )
        result = await self.gateway.handle(
            context, workflow_timeout_seconds=workflow_timeout_seconds
        )
        run, unrecorded = await self._record(item.actor, item.on_behalf_of, result.workflow)
        return LocalAgentOutcome(
            trace=item.trace,
            ingress=item.ingress,
            actor=item.actor,
            on_behalf_of=item.on_behalf_of,
            decision=result.routing.decision,
            capability=result.capability,
            workflow=result.workflow,
            run=run,
            unrecorded=unrecorded,
        )

    async def execute(
        self, job: RemoteWorkflowJob, *, workflow_timeout_seconds: float | None = None
    ) -> LocalAgentOutcome:
        """Run a remote job's exact workflow: no routing and no model. The
        job id is the idempotency key, so a job delivered twice joins the run
        it already started rather than starting another. The engine answers
        for what is installed here; its pre-flight rejection comes back as a
        workflow result that started nothing. The job's authorization is the
        control plane's decision; the Bridge policy still decides each step."""
        item = RemoteWorkflowJob.model_validate(job)
        refusal = self.admit(item.actor, item.bridge_id)
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
        snapshot = await self.gateway.execute_workflow(
            context,
            item.workflow,
            dict(item.arguments),
            workflow_timeout_seconds=workflow_timeout_seconds,
            workflow_idempotency_key=item.job_id,
        )
        run, unrecorded = await self._record(item.actor, None, snapshot)
        return LocalAgentOutcome(
            trace=item.trace,
            ingress=item.ingress,
            actor=item.actor,
            workflow=snapshot,
            run=run,
            unrecorded=unrecorded,
        )

    async def _record(
        self, actor: str, on_behalf_of: str | None, snapshot: WorkflowRunSnapshot | None
    ) -> tuple[LocalRunSummary | None, LocalStateErrorCode | None]:
        """Record a run the engine actually started. A pre-flight rejection
        carries a run id that names no run, and recording it would project a
        ghost onto the control plane. A run that outlived the caller's wait is
        recorded as it stands and settled to its final state in the background."""
        if snapshot is None or self.gateway.engine.get(snapshot.run.run_id) is None:
            return None, None
        try:
            run = await self._write(actor, on_behalf_of, snapshot)
        except LocalStateError as error:
            return None, error.code
        failure = snapshot.run.failure
        if failure is not None and failure.code == "workflow_timeout":
            task = asyncio.create_task(self._settle(actor, on_behalf_of, snapshot.run.run_id))
            self._settling.add(task)
            task.add_done_callback(self._settling.discard)
        return run, None

    async def _write(
        self, actor: str, on_behalf_of: str | None, snapshot: WorkflowRunSnapshot
    ) -> LocalRunSummary:
        summary = LocalRunSummary(
            run_id=snapshot.run.run_id,
            actor=actor,
            on_behalf_of=on_behalf_of,
            workflow=snapshot.run.workflow,
            status=snapshot.run.status,
            updated_at=self._clock(),
        )
        # A durable write touches the disk under the store's lock, so it never
        # runs on the event loop the in-flight runs share.
        return await asyncio.to_thread(self.state.record_run, summary)

    async def _settle(self, actor: str, on_behalf_of: str | None, run_id: str) -> None:
        """Join a run that outlived its caller's wait and record where it
        ended. A record that cannot be written is left as it stands: the
        engine still holds the truth, and `settled()` reports nothing."""
        final = await self.gateway.engine.wait(run_id)
        if final is None:
            return
        try:
            await self._write(actor, on_behalf_of, final)
        except LocalStateError:
            return

    async def settled(self) -> None:
        """Wait for every background settlement started by this Agent. A host
        calls this before reading the state as final, and before shutdown."""
        pending = tuple(self._settling)
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)

    def runs(self) -> tuple[LocalRunSummary, ...]:
        return self.state.runs()

    def snapshot(self, *, observed_at: datetime) -> BridgeStateSnapshot:
        """The authoritative state of this Bridge, for the control plane to
        project and for the operator to read locally."""
        return self.state.snapshot(self.membership.device, observed_at=observed_at)
