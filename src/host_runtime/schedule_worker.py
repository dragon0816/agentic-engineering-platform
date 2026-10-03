"""One-shot local schedule execution through the resident Agent's boundaries.

This worker is deliberately not started by Host construction. A trusted host
control must provide an exact per-occurrence authorization before a target may
run. Unresolved claims are never submitted again after a restart.
"""

import math
from collections.abc import Callable, Mapping
from datetime import datetime

from agent.task_contract import TaskContract
from agent.task_execution import TaskScopeError
from common.execution import ExecutionAuthorization, TraceIdentifiers
from common.local_agent import LocalWorkflowRequest
from common.scheduling import ScheduledRun, ScheduleRecord
from host_runtime.agent import LocalAgent
from host_runtime.schedules import ScheduleStoreError, SqliteScheduleStore

ScheduleAuthorizer = Callable[[ScheduleRecord, TraceIdentifiers], ExecutionAuthorization]


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
        authorizer: ScheduleAuthorizer | None = None,
        task_templates: Mapping[tuple[str, str, str], TaskContract] | None = None,
        workflow_wait_seconds: float = 1.0,
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

    def _member(self) -> str | None:
        return self.agent.membership.member()

    def _schedule(self, claim: ScheduledRun, owner: str) -> ScheduleRecord | None:
        try:
            return self.store.get(claim.schedule_id, owner=owner)
        except ScheduleStoreError as error:
            if error.code == "owner_mismatch":
                return None
            raise

    def _authorized(self, schedule: ScheduleRecord, trace: TraceIdentifiers) -> bool:
        if self.authorizer is None:
            return False
        decision = ExecutionAuthorization.model_validate(self.authorizer(schedule, trace))
        definition = schedule.definition
        return bool(
            decision.allowed
            and decision.actor == definition.owner
            and decision.asset == definition.target
            and decision.trace == trace
        )

    def _settle(
        self, claim: ScheduledRun, owner: str, status: str, code: str
    ) -> ScheduledRun:
        if status not in {"succeeded", "failed", "needs_input", "unavailable"}:
            raise ValueError("a schedule outcome must be terminal")
        # The validated ScheduledRun contract, not a model response, owns codes.
        if status == "succeeded":
            return self.store.record_outcome(
                claim.idempotency_key, owner=owner, status="succeeded", result_code=code
            )
        if status == "failed":
            return self.store.record_outcome(
                claim.idempotency_key, owner=owner, status="failed", result_code=code
            )
        if status == "needs_input":
            return self.store.record_outcome(
                claim.idempotency_key, owner=owner, status="needs_input", result_code=code
            )
        return self.store.record_outcome(
            claim.idempotency_key, owner=owner, status="unavailable", result_code=code
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

    async def poll_once(self, *, now: datetime, limit: int = 20) -> tuple[ScheduledRun, ...]:
        """Claim and attempt due occurrences for the bound member only.

        An exception after dispatch may mean that an effect already happened.
        Leave the claim open; a later tick may observe same-process completion,
        but it will never submit the claim again.
        """
        self.reconcile_pending()
        owner = self._member()
        if owner is None:
            return ()
        claims = self.store.claim_due(now=now, limit=limit, owner=owner)
        results: list[ScheduledRun] = []
        for claim in claims:
            schedule = self._schedule(claim, owner)
            if schedule is None:
                results.append(claim)
                continue
            definition = schedule.definition
            trace = _trace(claim)
            if schedule.status != "active":
                results.append(self._settle(claim, owner, "needs_input", "schedule_paused"))
                continue
            if self.agent.admit(owner, self.store.bridge_id) is not None:
                results.append(self._settle(claim, owner, "needs_input", "schedule_not_admitted"))
                continue
            try:
                approved = self._authorized(schedule, trace)
            except Exception:
                approved = False
            if not approved:
                results.append(
                    self._settle(claim, owner, "needs_input", "schedule_approval_required")
                )
                continue
            if definition.target_kind == "workflow":
                if self.agent.gateway.engine.workflows.get(definition.target) is None:
                    results.append(
                        self._settle(claim, owner, "unavailable", "workflow_not_installed")
                    )
                    continue
                try:
                    workflow_outcome = await self.agent.execute_workflow(
                        LocalWorkflowRequest(
                            actor=owner,
                            bridge_id=self.store.bridge_id,
                            workflow=definition.target,
                            arguments=dict(definition.runtime_inputs),
                            idempotency_key=claim.idempotency_key,
                            trace=trace,
                        ),
                        workflow_timeout_seconds=self.workflow_wait_seconds,
                    )
                except Exception:
                    results.append(claim)
                    continue
                if workflow_outcome.refusal is not None:
                    results.append(
                        self._settle(claim, owner, "needs_input", "schedule_not_admitted")
                    )
                elif workflow_outcome.workflow is None or workflow_outcome.unrecorded is not None:
                    results.append(claim)
                else:
                    run = workflow_outcome.workflow.run
                    if run.status in {"pending", "running"} or (
                        run.failure is not None and run.failure.code == "workflow_timeout"
                    ) or (
                        workflow_outcome.run is None
                        and self.agent.gateway.engine.get(run.run_id) is not None
                    ):
                        results.append(claim)
                    else:
                        code = run.failure.code if run.failure else "workflow_succeeded"
                        results.append(self._settle(claim, owner, run.status, code))
                continue
            # Task manifests are not installed by the current Host builder.
            # An exact trusted template must be supplied explicitly; run inputs
            # have no Task parameter contract yet, so none may be interpolated.
            template = self.task_templates.get(definition.target.key)
            if template is None:
                results.append(self._settle(claim, owner, "unavailable", "task_not_installed"))
                continue
            if definition.runtime_inputs or template.actor != owner or (
                template.namespace != definition.target.namespace
            ):
                results.append(self._settle(claim, owner, "needs_input", "task_input_unsupported"))
                continue
            task_id = _task_id(claim)
            task = template.model_copy(
                update={
                    "task_id": task_id,
                    "trace": trace,
                    "expected_outputs": tuple(
                        output.model_copy(
                            update={"artifact_ref": f"{task_id}-{output.output_id}"}
                        )
                        for output in template.expected_outputs
                    ),
                }
            )
            try:
                task_outcome = await self.agent.run_task(task, bridge_id=self.store.bridge_id)
            except TaskScopeError:
                results.append(self._settle(claim, owner, "unavailable", "task_scope_unavailable"))
                continue
            except RuntimeError as error:
                if str(error) == "task execution is not configured on this host":
                    results.append(
                        self._settle(claim, owner, "unavailable", "task_scope_unavailable")
                    )
                else:
                    results.append(claim)
                continue
            except Exception:
                results.append(claim)
                continue
            if task_outcome.refusal is not None:
                results.append(self._settle(claim, owner, "needs_input", "schedule_not_admitted"))
            elif task_outcome.execution is None:
                results.append(claim)
            else:
                execution = task_outcome.execution
                status = "succeeded" if execution.status == "validated" else (
                    "needs_input" if execution.status == "refused" else execution.status
                )
                if status == "succeeded" and execution.run is None:
                    results.append(claim)
                else:
                    results.append(
                        self._settle(claim, owner, status, execution.code or "task_validated")
                    )
        return tuple(results)
