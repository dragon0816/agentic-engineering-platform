"""Deterministic workflow engine: ordered capability steps through Bridge dispatch.

Run-tracking semantics are adapted from the pinned rs_workflow_system job runner;
lineage, preserved invariants and intentional differences are recorded in
docs/PHASE_3_MIGRATION.md. The engine never imports job code: workflows are
explicitly installed manifests and every step is authorized by the Bridge.
"""

import asyncio
import functools
import hashlib
import json
import math
import uuid
from copy import deepcopy
from typing import Literal

from pydantic import JsonValue, TypeAdapter

from capabilities.runtime import CapabilityInvocation
from common.assets import (
    AssetIdentity,
    PathPart,
    RetryPolicy,
    RunInput,
    StepInput,
    WorkflowManifest,
    WorkflowStep,
)
from common.base import Contract, Text
from common.execution import (
    CapabilityResult,
    Failure,
    IdempotencyKey,
    RequestContext,
    ResumePlan,
    ResumePolicy,
    RunStatus,
    StepAttempt,
    StepState,
    StepStateRecord,
    TraceIdentifiers,
    WorkflowRun,
)
from workflow.dispatch import BridgeExecutor

MAX_RUNS_KEPT = 50
MAX_LOG_LINES = 5000
MAX_IDEMPOTENCY_KEYS = 50


class WorkflowRunSnapshot(Contract):
    """Step results carry validated outputs for the caller; log lines never do."""

    run: WorkflowRun
    log: tuple[Text, ...] = ()
    step_results: tuple[CapabilityResult, ...] = ()
    attempts: tuple[StepAttempt, ...] = ()


class InstalledWorkflows:
    """Explicit host installation; the Platform Registry is never consulted at runtime."""

    def __init__(self) -> None:
        self._workflows: dict[tuple[str, str, str], WorkflowManifest] = {}

    def register(self, manifest: WorkflowManifest) -> None:
        checked = WorkflowManifest.model_validate(manifest)
        key = checked.metadata.identity.key
        if key in self._workflows:
            raise ValueError("workflow version already installed")
        self._workflows[key] = checked

    def get(self, identity: AssetIdentity) -> WorkflowManifest | None:
        manifest = self._workflows.get(identity.key)
        return manifest.model_copy(deep=True) if manifest is not None else None


class _RunRecord:
    """Mutable run state owned by the event loop; snapshots are frozen contracts."""

    def __init__(
        self,
        workflow: AssetIdentity,
        trace: TraceIdentifiers,
        *,
        manifest: WorkflowManifest | None = None,
        arguments: dict[str, JsonValue] | None = None,
        actor: str = "",
        namespace: str = "",
        resumed_from: str | None = None,
    ) -> None:
        self.run_id = f"run-{uuid.uuid4().hex}"
        self.workflow = workflow
        self.trace = trace
        self.manifest = manifest
        self.arguments: dict[str, JsonValue] = arguments if arguments is not None else {}
        self.actor = actor
        self.namespace = namespace
        self.resumed_from = resumed_from
        # Runs are linear: once continued, the continuation is what gets resumed.
        self.continued_by: str | None = None
        self.status: RunStatus = "running"
        self.completed_steps = 0
        self.failure: Failure | None = None
        self.log: list[str] = []
        self.step_results: list[CapabilityResult] = []
        self.attempts: list[StepAttempt] = []

        self.final: WorkflowRunSnapshot | None = None

    def append_log(self, message: str) -> None:
        if len(self.log) < MAX_LOG_LINES:
            self.log.append(message)
        elif len(self.log) == MAX_LOG_LINES:
            self.log.append(f"… log truncated ({MAX_LOG_LINES} lines)")

    def snapshot(self) -> WorkflowRunSnapshot:
        if self.final is not None:
            return self.final.model_copy(deep=True)
        return WorkflowRunSnapshot(
            run=WorkflowRun(
                run_id=self.run_id,
                workflow=self.workflow,
                trace=self.trace,
                status=self.status,
                completed_steps=self.completed_steps,
                failure=self.failure,
                resumed_from=self.resumed_from,
            ),
            log=tuple(self.log),
            step_results=tuple(result.model_copy(deep=True) for result in self.step_results),
            attempts=tuple(self.attempts),
        )


def _step_label(identity: AssetIdentity) -> str:
    return f"{identity.namespace}/{identity.name}@{identity.version}"


class _MissingInput(Exception):
    """Contains no path or payload, including when converted to a failure."""


def _select(value: JsonValue, path: tuple[PathPart, ...]) -> JsonValue:
    for part in path:
        if isinstance(part, str) and isinstance(value, dict) and part in value:
            value = value[part]
        elif isinstance(part, int) and isinstance(value, list) and part < len(value):
            value = value[part]
        else:
            raise _MissingInput
    return deepcopy(value)


def _target(step: AssetIdentity | WorkflowStep) -> AssetIdentity:
    return step.capability if isinstance(step, WorkflowStep) else step


class WorkflowEngine:
    """Caller-wait timeouts never finalize a run; the driving task records the outcome."""

    def __init__(self, workflows: InstalledWorkflows, bridge: BridgeExecutor) -> None:
        self.workflows = workflows
        self.bridge = bridge
        self._runs: dict[str, _RunRecord] = {}
        self._tasks: dict[str, asyncio.Task[None]] = {}
        # Never evict a key silently: even an evicted failed run may have effects.
        # Scoped to this engine's lifetime and one event loop, not durable storage.
        self._submissions: dict[tuple[str, str, str], tuple[str, _RunRecord]] = {}

    def get(self, run_id: str) -> WorkflowRunSnapshot | None:
        """None means unknown or evicted; only the last MAX_RUNS_KEPT runs are kept."""
        record = self._runs.get(run_id)
        return record.snapshot() if record is not None else None

    async def wait(self, run_id: str) -> WorkflowRunSnapshot | None:
        """Join a run that outlived its caller-wait timeout and return its final state."""
        task = self._tasks.get(run_id)
        if task is not None:
            # Never re-raise a cancelled or failed driving task into the joiner;
            # the run record carries the outcome.
            await asyncio.wait({task})
        return self.get(run_id)

    async def execute(
        self,
        context: RequestContext,
        workflow: AssetIdentity,
        arguments: dict[str, JsonValue] | None = None,
        *,
        timeout_seconds: float = 300,
        idempotency_key: IdempotencyKey | None = None,
    ) -> WorkflowRunSnapshot:
        if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise ValueError("timeout must be finite and positive")
        checked = RequestContext.model_validate(context)
        target = AssetIdentity.model_validate(workflow)
        manifest = self.workflows.get(target)
        run_arguments = deepcopy(arguments or {})
        key = None
        signature = ""
        if idempotency_key is not None:
            token = TypeAdapter(IdempotencyKey).validate_python(idempotency_key)
            key = (checked.actor, checked.namespace, token)
            # JSON distinguishes booleans/integers and normalizes object key order.
            intent = {
                "workflow": target.model_dump(mode="json"),
                "context": checked.model_dump(mode="json", exclude={"trace"}),
                "arguments": run_arguments,
            }
            signature = hashlib.sha256(
                json.dumps(
                    intent,
                    sort_keys=True,
                    ensure_ascii=True,
                    allow_nan=False,
                    separators=(",", ":"),
                ).encode()
            ).hexdigest()
            previous = self._submissions.get(key)
            if previous is not None:
                if previous[0] != signature:
                    return self._rejected(target, checked, "idempotency_conflict", "needs_input")
                if not self._replay_allowed(checked, manifest):
                    return self._rejected(target, checked, "permission_denied", "failed")
                snapshot = await self._wait_record(previous[1], timeout_seconds)
                # Authorization may change while joining an active run.
                if not self._replay_allowed(checked, manifest):
                    return self._rejected(target, checked, "permission_denied", "failed")
                return snapshot
            if len(self._submissions) >= MAX_IDEMPOTENCY_KEYS:
                return self._rejected(target, checked, "idempotency_capacity")
        # Pre-flight failures never create a run record (no ghost runs), matching
        # the source's load-before-create order.
        if manifest is None:
            return self._rejected(target, checked, "workflow_not_installed")
        rejection = self._preflight(manifest, run_arguments)
        if rejection is not None:
            return self._rejected(target, checked, *rejection)

        record = _RunRecord(
            target,
            checked.trace,
            manifest=manifest,
            arguments=run_arguments,
            actor=checked.actor,
            namespace=checked.namespace,
        )
        if key is not None:
            # No await before reservation/task creation: duplicate submissions on
            # this event loop see this same record, even before execution starts.
            self._submissions[key] = (signature, record)
        return await self._launch(
            record,
            manifest,
            checked,
            run_arguments,
            timeout_seconds,
            opening=f"start workflow {_step_label(target)}",
        )

    async def _launch(
        self,
        record: _RunRecord,
        manifest: WorkflowManifest,
        context: RequestContext,
        arguments: dict[str, JsonValue],
        timeout_seconds: float,
        *,
        start: int = 0,
        opening: str,
    ) -> WorkflowRunSnapshot:
        self._runs[record.run_id] = record
        while len(self._runs) > MAX_RUNS_KEPT:
            # Only the record is evicted. The driving task stays strongly
            # referenced in _tasks until it finishes, or the event loop could
            # garbage-collect it mid-run and the run would never complete.
            del self._runs[next(iter(self._runs))]
        record.append_log(opening)
        task = asyncio.create_task(self._drive(record, manifest, context, arguments, start=start))
        self._tasks[record.run_id] = task
        task.add_done_callback(functools.partial(self._discard_task, record.run_id))
        return await self._wait_record(record, timeout_seconds)

    def _replay_allowed(
        self, context: RequestContext, manifest: WorkflowManifest | None, start: int = 0
    ) -> bool:
        if manifest is None:
            return False
        for step in manifest.steps[start:]:
            binding = self.bridge.installed.get(_target(step))
            if binding is None or not self.bridge.policy.authorize(context, binding.spec).allowed:
                return False
        return True

    def _preflight(
        self, manifest: WorkflowManifest, run_arguments: dict[str, JsonValue]
    ) -> tuple[str, Literal["unavailable", "needs_input"]] | None:
        """Statically checkable rejections, in the source's load-before-create order."""
        if manifest.secrets:
            return ("secret_resolution_unavailable", "unavailable")
        if not set(manifest.dependencies.local_capabilities).issubset(self.bridge.installed.names):
            return ("missing_local_capability", "unavailable")
        if any(
            service.required and service.name not in self.bridge.services
            for service in manifest.dependencies.central_services
        ):
            return ("needs_connectivity", "unavailable")
        if any(self.bridge.installed.get(_target(step)) is None for step in manifest.steps):
            return ("capability_not_installed", "unavailable")
        for step in manifest.steps:
            if isinstance(step, WorkflowStep) and step.retry.max_attempts > 1:
                binding = self.bridge.installed.get(step.capability)
                if binding is None or binding.spec.side_effect != "read":
                    return ("unsafe_retry", "unavailable")
        try:
            for step in manifest.steps:
                if isinstance(step, WorkflowStep):
                    for ref in step.inputs.values():
                        if isinstance(ref, RunInput):
                            _select(run_arguments, ref.path)
        except _MissingInput:
            return ("workflow_input_missing", "needs_input")
        return None

    def _owned(self, context: RequestContext, run_id: str) -> _RunRecord | None:
        """Unknown, evicted and other actors' runs are indistinguishable to a caller."""
        record = self._runs.get(run_id)
        if record is None or (record.actor, record.namespace) != (context.actor, context.namespace):
            return None
        return record

    def inspect(self, context: RequestContext, run_id: str) -> ResumePlan | None:
        """Classify each declared step's effect from recorded evidence only."""
        record = self._owned(RequestContext.model_validate(context), run_id)
        return self._plan(record) if record is not None else None

    def _plan(self, record: _RunRecord) -> ResumePlan:
        total = len(record.manifest.steps) if record.manifest is not None else 0
        done = record.completed_steps
        active = record.final is None
        states: list[StepStateRecord] = []
        for index in range(total):
            if index != done:
                state: StepState = "completed" if index < done else "never_started"
                states.append(StepStateRecord(step_index=index, state=state))
                continue
            # The step the run stopped at or is still executing. A handler counts
            # as run if any attempt or the terminal result says so; the caller-wait
            # overlay on a live run is not evidence of anything.
            invoked = any(a.handler_invoked for a in record.attempts if a.step_index == index)
            if index < len(record.step_results):
                result = record.step_results[index]
                invoked = invoked or result.handler_invoked
                code = result.failure.code if result.failure is not None else None
                state = "uncertain" if invoked else "never_started"
            elif active:
                code, state = None, "uncertain"
            else:
                code = record.failure.code if record.failure is not None else None
                pre_dispatch = code == "workflow_input_missing" and not invoked
                state = "never_started" if pre_dispatch else "uncertain"
            states.append(StepStateRecord(step_index=index, state=state, code=code))
        return ResumePlan(
            run_id=record.run_id,
            workflow=record.workflow,
            status="running" if active else record.status,
            steps=tuple(states),
            next_step=done if done < total else None,
        )

    async def resume(
        self,
        context: RequestContext,
        run_id: str,
        policy: ResumePolicy | None = None,
        *,
        timeout_seconds: float = 300,
    ) -> WorkflowRunSnapshot | None:
        """Continue a finished run from its first non-completed step as a new run.

        Completed steps are never repeated; their recorded results feed later
        step inputs. An uncertain-effect step is replayed only as the explicit
        policy allows. A run can be continued once; resume its continuation
        afterwards. Idempotency keys are neither consulted nor consumed.
        Returns None for unknown, evicted or other actors' runs.
        """
        if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise ValueError("timeout must be finite and positive")
        checked = RequestContext.model_validate(context)
        chosen = ResumePolicy.model_validate(policy) if policy is not None else ResumePolicy()
        record = self._owned(checked, run_id)
        if record is None:
            return None
        target = record.workflow
        manifest = record.manifest
        if record.final is None:
            return self._rejected(target, checked, "run_active")
        if record.continued_by is not None:
            return self._rejected(target, checked, "already_resumed", "needs_input")
        # The retained manifest drove this run; the fresh lookup only proves the
        # exact version is still installed.
        if manifest is None or self.workflows.get(target) is None:
            return self._rejected(target, checked, "workflow_not_installed")
        plan = self._plan(record)
        start = plan.next_step
        if start is None:
            return self._rejected(target, checked, "run_complete")
        arguments = deepcopy(record.arguments)
        rejection = self._preflight(manifest, arguments)
        if rejection is not None:
            return self._rejected(target, checked, *rejection)
        try:
            # References into completed results are checkable before a run exists.
            for step in manifest.steps[start:]:
                if isinstance(step, WorkflowStep):
                    for ref in step.inputs.values():
                        if isinstance(ref, StepInput) and ref.step_index < start:
                            _select(record.step_results[ref.step_index].data, ref.path)
        except _MissingInput:
            return self._rejected(target, checked, "workflow_input_missing", "needs_input")
        if plan.steps[start].state == "uncertain":
            binding = self.bridge.installed.get(_target(manifest.steps[start]))
            replayable = chosen.uncertain == "replay_side_effects" or (
                chosen.uncertain == "replay_read_only"
                and binding is not None
                and binding.spec.side_effect == "read"
            )
            if not replayable:
                return self._rejected(target, checked, "uncertain_side_effect", "needs_input")
        if not self._replay_allowed(checked, manifest, start):
            return self._rejected(target, checked, "permission_denied", "failed")

        resumed = _RunRecord(
            target,
            checked.trace,
            manifest=manifest,
            arguments=arguments,
            actor=checked.actor,
            namespace=checked.namespace,
            resumed_from=record.run_id,
        )
        resumed.completed_steps = start
        resumed.step_results = [
            result.model_copy(deep=True) for result in record.step_results[:start]
        ]
        # Linked before any await so a concurrent second resume sees it.
        record.continued_by = resumed.run_id
        return await self._launch(
            resumed,
            manifest,
            checked,
            arguments,
            timeout_seconds,
            start=start,
            opening=f"resume run {record.run_id} from step {start + 1}",
        )

    async def _wait_record(self, record: _RunRecord, timeout_seconds: float) -> WorkflowRunSnapshot:
        task = self._tasks.get(record.run_id)
        if task is None:
            return record.snapshot()
        done, _ = await asyncio.wait({task}, timeout=timeout_seconds)
        if not done:
            # Bounds only the caller's wait: the task keeps running and its
            # final state overwrites this one, as in the source runner.
            record.status = "failed"
            record.failure = Failure(
                code="workflow_timeout",
                message="Workflow outlived the caller wait and keeps running",
            )
            record.append_log(f"caller wait exceeded {timeout_seconds}s")
        return record.snapshot()

    def _discard_task(self, run_id: str, _task: "asyncio.Task[None]") -> None:
        self._tasks.pop(run_id, None)

    def _rejected(
        self,
        workflow: AssetIdentity,
        context: RequestContext,
        code: str,
        status: Literal["unavailable", "needs_input", "failed"] = "unavailable",
    ) -> WorkflowRunSnapshot:
        return WorkflowRunSnapshot(
            run=WorkflowRun(
                run_id=f"run-{uuid.uuid4().hex}",
                workflow=workflow,
                trace=context.trace,
                status=status,
                failure=Failure(code=code, message="Workflow was not started"),
            )
        )

    async def _drive(
        self,
        record: _RunRecord,
        manifest: WorkflowManifest,
        context: RequestContext,
        arguments: dict[str, JsonValue],
        start: int = 0,
    ) -> None:
        try:
            for index in range(start, len(manifest.steps)):
                step = manifest.steps[index]
                try:
                    inputs = (
                        {
                            name: _select(
                                arguments
                                if isinstance(ref, RunInput)
                                else record.step_results[ref.step_index].data,
                                ref.path,
                            )
                            for name, ref in step.inputs.items()
                        }
                        if isinstance(step, WorkflowStep)
                        else deepcopy(arguments)
                    )
                except _MissingInput:
                    record.status = "needs_input"
                    record.failure = Failure(
                        code="workflow_input_missing", message="Workflow input is unavailable"
                    )
                    record.append_log(f"step {index + 1} needs_input workflow_input_missing")
                    return
                result = await self._execute_step(record, index, step, context, inputs)
                record.step_results.append(result)
                code = result.failure.code if result.failure is not None else None
                record.append_log(
                    f"step {len(record.step_results)} {_step_label(_target(step))} {result.status}"
                    + (f" {code}" if code else "")
                )
                if result.status != "succeeded":
                    record.status = result.status
                    record.failure = result.failure
                    return
                record.completed_steps += 1
            record.status = "succeeded"
            record.failure = None
            record.append_log("workflow succeeded")
        except Exception:
            # Exception text may contain arguments or payloads; never record it.
            record.status = "failed"
            record.failure = Failure(code="workflow_error", message="Workflow did not complete")
        except BaseException:
            # Cancellation must still leave a final recorded state, as the
            # source's BaseException handler did, then propagate.
            record.status = "failed"
            record.failure = Failure(code="workflow_aborted", message="Workflow was interrupted")
            raise
        finally:
            if record.final is None:
                record.final = record.snapshot()

    async def _execute_step(
        self,
        record: _RunRecord,
        index: int,
        step: AssetIdentity | WorkflowStep,
        context: RequestContext,
        inputs: dict[str, JsonValue],
    ) -> CapabilityResult:
        retry = step.retry if isinstance(step, WorkflowStep) else RetryPolicy()
        for attempt in range(1, retry.max_attempts + 1):
            if retry.max_attempts > 1:
                binding = self.bridge.installed.get(_target(step))
                if binding is None or binding.spec.side_effect != "read":
                    return CapabilityResult(
                        trace=context.trace,
                        status="unavailable",
                        failure=Failure(code="unsafe_retry", message="Retry plan is unavailable"),
                    )
            result = await self.bridge.execute(
                CapabilityInvocation(
                    context=context, target=_target(step), arguments=deepcopy(inputs)
                )
            )
            failure = result.failure
            record.attempts.append(
                StepAttempt(
                    step_index=index,
                    attempt=attempt,
                    status=result.status,
                    code=failure.code if failure is not None else None,
                    handler_invoked=result.handler_invoked,
                )
            )
            if (
                failure is None
                or not failure.retryable
                or failure.code != "transient_failure"
                or attempt == retry.max_attempts
            ):
                return result
            record.append_log(f"step {index + 1} attempt {attempt} failed transient_failure; retry")
            await asyncio.sleep(retry.delay_ms / 1000)
        raise AssertionError("validated retry policy always permits an attempt")
