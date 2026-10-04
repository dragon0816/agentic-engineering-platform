"""Local schedule execution through the resident Agent's boundaries.

This worker is deliberately not started by Host construction. A trusted host
control must provide an exact per-occurrence authorization before a target may
run. Unresolved claims are never submitted again after a restart.

Regardless of which authorizer is supplied, a target that can reach an
`external_side_effect` capability never runs without a per-run human
approval: its occurrence waits as `awaiting_approval` until the owner
approves or denies it.
"""

import math
from collections.abc import Callable, Mapping
from datetime import datetime, timedelta
from typing import Literal, cast

from agent.task_contract import TaskContract
from agent.task_execution import TaskScopeError
from common.assets import WorkflowManifest
from common.execution import ExecutionAuthorization, SideEffect, TraceIdentifiers
from common.local_agent import LocalWorkflowRequest
from common.scheduling import ScheduledRun, ScheduleRecord, max_side_effect
from common.workflow_parameters import WorkflowParameterError, validate_run_parameters
from host_runtime.agent import LocalAgent
from host_runtime.schedule_policy import (
    UNAVAILABLE_CODES,
    ScheduleDecider,
    ScheduleDecision,
    target_capabilities,
)
from host_runtime.schedules import DEFAULT_CATCH_UP, ScheduleStoreError, SqliteScheduleStore

#: A plain authorizer: (schedule, trace) -> authorization. An object with a
#: `decide(schedule, trace, *, run_approved, now)` method is preferred and
#: reports why it refused (see `host_runtime.schedule_policy`).
ScheduleAuthorizer = Callable[[ScheduleRecord, TraceIdentifiers], ExecutionAuthorization]

Terminal = Literal["succeeded", "failed", "needs_input", "unavailable"]


def _trace(claim: ScheduledRun) -> TraceIdentifiers:
    digest = claim.idempotency_key.removeprefix("schedule:")
    return TraceIdentifiers(
        trace_id=f"schedule-{digest[:32]}",
        request_id=f"schedule-request-{digest[:32]}",
        span_id=f"schedule-span-{digest[:32]}",
    )


def _task_id(claim: ScheduledRun) -> str:
    return f"scheduled-{claim.idempotency_key.removeprefix('schedule:')[:48]}"


class ScheduleWorker:
    """Poll once, never silently replay an ambiguous claim.

    Workflow execution uses LocalAgent.execute_workflow, which checks device
    membership, exact installation, Workflow preflight and Bridge grants. Task
    execution requires a host-supplied exact template; GatewayTaskExecutor then
    enforces approved data egress, read-only tool scope and output validation.
    The authorizer is a separate trusted execution decision, not a property of
    the schedule definition or a published asset.
    """

    def __init__(
        self,
        store: SqliteScheduleStore,
        agent: LocalAgent,
        *,
        authorizer: ScheduleAuthorizer | ScheduleDecider | None = None,
        task_templates: Mapping[tuple[str, str, str], TaskContract] | None = None,
        workflow_wait_seconds: float = 1.0,
        catch_up: timedelta = DEFAULT_CATCH_UP,
    ) -> None:
        if not math.isfinite(workflow_wait_seconds) or workflow_wait_seconds <= 0:
            raise ValueError("workflow wait must be finite and positive")
        self.store = store
        self.agent = agent
        self.authorizer = authorizer
        self.task_templates = {
            key: TaskContract.model_validate(value)
            for key, value in (task_templates or {}).items()
        }
        self.workflow_wait_seconds = workflow_wait_seconds
        self.catch_up = catch_up

    def _member(self) -> str | None:
        return self.agent.membership.member()

    def _schedule(self, claim: ScheduledRun, owner: str) -> ScheduleRecord | None:
        try:
            return self.store.get(claim.schedule_id, owner=owner)
        except ScheduleStoreError as error:
            if error.code == "owner_mismatch":
                return None
            raise

    def _decide(
        self,
        schedule: ScheduleRecord,
        trace: TraceIdentifiers,
        *,
        run_approved: bool,
        now: datetime,
    ) -> ScheduleDecision:
        """The authorizer's decision, then the worker's own invariants."""
        definition = schedule.definition
        decision = ScheduleDecision(code="schedule_approval_required")
        decide = getattr(self.authorizer, "decide", None)
        try:
            if callable(decide):
                decision = ScheduleDecision.model_validate(
                    decide(schedule, trace, run_approved=run_approved, now=now)
                )
            elif callable(self.authorizer):
                legacy = ExecutionAuthorization.model_validate(self.authorizer(schedule, trace))
                if legacy.allowed:
                    decision = ScheduleDecision(
                        allowed=True, code="schedule_authorized", authorization=legacy
                    )
        except Exception:  # noqa: BLE001 - a failing authorizer authorizes nothing
            decision = ScheduleDecision(code="schedule_approval_required")
        if not decision.allowed:
            return decision
        authorization = decision.authorization
        if not (
            authorization.actor == definition.owner
            and authorization.asset == definition.target
            and authorization.trace == trace
        ):
            return ScheduleDecision(code="schedule_approval_required")
        specs = target_capabilities(
            self.agent, definition.target_kind, definition.target, self.task_templates
        )
        if isinstance(specs, str):
            return ScheduleDecision(code=specs)
        effect = max_side_effect(spec.side_effect for spec in specs)
        if effect == "external_side_effect" and not run_approved:
            return ScheduleDecision(
                code="run_approval_required", side_effect=effect, approval_required=True
            )
        return decision.model_copy(update={"side_effect": effect})

    def _settle(
        self,
        claim: ScheduledRun,
        owner: str,
        status: str,
        code: str,
        side_effect: SideEffect | None = None,
    ) -> ScheduledRun:
        if status not in {"succeeded", "failed", "needs_input", "unavailable"}:
            raise ValueError("a schedule outcome must be terminal")
        terminal = cast(Terminal, status)
        # The validated ScheduledRun contract, not a model response, owns codes.
        return self.store.record_outcome(
            claim.idempotency_key,
            owner=owner,
            status=terminal,
            result_code=code,
            side_effect=side_effect,
        )

    def reconcile_pending(self) -> tuple[ScheduledRun, ...]:
        """Observe same-process runs or durable Task results, without dispatch.

        A Workflow submission from an earlier process cannot currently be
        identified by its idempotency key in the durable run ledger. Such a
        claim remains open for operator reconciliation; it is never replayed.
        """
        owner = self._member()
        if owner is None:
            return ()
        settled: list[ScheduledRun] = []
        for claim in self.store.pending_claims():
            schedule = self._schedule(claim, owner)
            if schedule is None:
                continue
            definition = schedule.definition
            if definition.target_kind == "workflow":
                observed = self.agent.gateway.engine.submitted(
                    owner, definition.target.namespace, claim.idempotency_key
                )
                if observed is None or observed.run.status in {"pending", "running"}:
                    continue
                # A finished engine run whose Host state was not recorded is
                # still uncertain to the schedule ledger. Never claim success
                # from engine memory alone.
                recorded = next(
                    (
                        run
                        for run in self.agent.state.runs()
                        if run.run_id == observed.run.run_id
                    ),
                    None,
                )
                if recorded is None or recorded.status != observed.run.status:
                    continue
                settled.append(
                    self._settle(
                        claim,
                        owner,
                        observed.run.status,
                        observed.run.failure.code
                        if observed.run.failure is not None
                        else "workflow_succeeded",
                    )
                )
            else:
                record = self.agent.state.task_run(_task_id(claim), owner)
                if record is None or record.status in {"pending", "running", "awaiting_validation"}:
                    continue
                status = "succeeded" if record.status == "validated" else record.status
                code = "task_validated" if status == "succeeded" else f"task_{status}"
                settled.append(self._settle(claim, owner, status, code))
        return tuple(settled)

    async def poll_once(
        self, *, now: datetime, limit: int = 20, catch_up: timedelta | None = None
    ) -> tuple[ScheduledRun, ...]:
        """Claim and attempt due occurrences for the bound member only.

        An exception after dispatch may mean that an effect already happened.
        Leave the claim open; a later tick may observe same-process completion,
        but it will never submit the claim again.
        """
        self.reconcile_pending()
        owner = self._member()
        if owner is None:
            return ()
        claims = self.store.claim_due(
            now=now,
            limit=limit,
            owner=owner,
            catch_up=self.catch_up if catch_up is None else catch_up,
        )
        results: list[ScheduledRun] = []
        for claim in claims:
            results.append(await self._attempt(claim, owner, run_approved=False, now=now))
        return tuple(results)

    async def run_approved(
        self, key: str, *, decided_by: str, now: datetime, note: str | None = None
    ) -> ScheduledRun:
        """Dispatch one occurrence a person approved, through every check again.

        The approval reopens the occurrence as a claim first, so a crash after
        dispatch leaves it blocked for operator resolution, never replayed.
        """
        owner = self._member()
        if owner is None or decided_by != owner:
            raise ScheduleStoreError("owner_mismatch")
        claim = self.store.approve_run(key, owner=owner, decided_by=decided_by, now=now, note=note)
        return await self._attempt(claim, owner, run_approved=True, now=now)

    async def _attempt(
        self, claim: ScheduledRun, owner: str, *, run_approved: bool, now: datetime
    ) -> ScheduledRun:
        schedule = self._schedule(claim, owner)
        if schedule is None:
            return claim
        definition = schedule.definition
        trace = _trace(claim)
        if schedule.status != "active":
            return self._settle(claim, owner, "needs_input", "schedule_paused")
        if self.agent.admit(owner, self.store.bridge_id) is not None:
            return self._settle(claim, owner, "needs_input", "schedule_not_admitted")
        decision = self._decide(schedule, trace, run_approved=run_approved, now=now)
        if decision.approval_required and decision.side_effect is not None:
            return self.store.await_approval(
                claim.idempotency_key, owner=owner, side_effect=decision.side_effect
            )
        if not decision.allowed:
            status = "unavailable" if decision.code in UNAVAILABLE_CODES else "needs_input"
            return self._settle(claim, owner, status, decision.code, decision.side_effect)
        effect = decision.side_effect
        if definition.target_kind == "workflow":
            return await self._run_workflow(claim, owner, schedule, trace, effect)
        return await self._run_task(claim, owner, schedule, trace, effect)

    async def _run_workflow(
        self,
        claim: ScheduledRun,
        owner: str,
        schedule: ScheduleRecord,
        trace: TraceIdentifiers,
        effect: SideEffect | None,
    ) -> ScheduledRun:
        definition = schedule.definition
        manifest: WorkflowManifest | None = self.agent.gateway.engine.workflows.get(
            definition.target
        )
        if manifest is None:
            return self._settle(claim, owner, "unavailable", "workflow_not_installed", effect)
        try:
            arguments = validate_run_parameters(manifest, dict(definition.runtime_inputs))
        except WorkflowParameterError:
            return self._settle(claim, owner, "needs_input", "workflow_parameters_invalid", effect)
        try:
            workflow_outcome = await self.agent.execute_workflow(
                LocalWorkflowRequest(
                    actor=owner,
                    bridge_id=self.store.bridge_id,
                    workflow=definition.target,
                    arguments=arguments,
                    idempotency_key=claim.idempotency_key,
                    trace=trace,
                ),
                workflow_timeout_seconds=self.workflow_wait_seconds,
            )
        except Exception:  # noqa: BLE001 - an effect may have happened; leave it open
            return claim
        if workflow_outcome.refusal is not None:
            return self._settle(claim, owner, "needs_input", "schedule_not_admitted", effect)
        if workflow_outcome.workflow is None or workflow_outcome.unrecorded is not None:
            return claim
        run = workflow_outcome.workflow.run
        if (
            run.status in {"pending", "running"}
            or (run.failure is not None and run.failure.code == "workflow_timeout")
            or (
                workflow_outcome.run is None
                and self.agent.gateway.engine.get(run.run_id) is not None
            )
        ):
            return claim
        code = run.failure.code if run.failure else "workflow_succeeded"
        return self._settle(claim, owner, run.status, code, effect)

    async def _run_task(
        self,
        claim: ScheduledRun,
        owner: str,
        schedule: ScheduleRecord,
        trace: TraceIdentifiers,
        effect: SideEffect | None,
    ) -> ScheduledRun:
        definition = schedule.definition
        # An exact installed template (host_runtime.agent_tasks) is required;
        # templates declare no runtime parameters yet, so none are interpolated.
        template = self.task_templates.get(definition.target.key)
        if template is None:
            return self._settle(claim, owner, "unavailable", "task_not_installed", effect)
        if definition.runtime_inputs or template.actor != owner or (
            template.namespace != definition.target.namespace
        ):
            return self._settle(claim, owner, "needs_input", "task_input_unsupported", effect)
        task_id = _task_id(claim)
        task = template.model_copy(
            update={
                "task_id": task_id,
                "trace": trace,
                "expected_outputs": tuple(
                    output.model_copy(update={"artifact_ref": f"{task_id}-{output.output_id}"})
                    for output in template.expected_outputs
                ),
            }
        )
        try:
            task_outcome = await self.agent.run_task(task, bridge_id=self.store.bridge_id)
        except TaskScopeError:
            return self._settle(claim, owner, "unavailable", "task_scope_unavailable", effect)
        except RuntimeError as error:
            if str(error) == "task execution is not configured on this host":
                return self._settle(claim, owner, "unavailable", "task_scope_unavailable", effect)
            return claim
        except Exception:  # noqa: BLE001 - an effect may have happened; leave it open
            return claim
        if task_outcome.refusal is not None:
            return self._settle(claim, owner, "needs_input", "schedule_not_admitted", effect)
        if task_outcome.execution is None:
            return claim
        execution = task_outcome.execution
        status = "succeeded" if execution.status == "validated" else (
            "needs_input" if execution.status == "refused" else execution.status
        )
        if status == "succeeded" and execution.run is None:
            return claim
        return self._settle(claim, owner, status, execution.code or "task_validated", effect)
