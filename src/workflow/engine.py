"""Deterministic workflow engine: ordered capability steps through Bridge dispatch.

Run-tracking semantics are adapted from the pinned rs_workflow_system job runner;
lineage, preserved invariants and intentional differences are recorded in
docs/PHASE_3_MIGRATION.md. The engine never imports job code: workflows are
explicitly installed manifests and every step is authorized by the Bridge.
"""

import asyncio
import functools
import math
import uuid
from copy import deepcopy
from typing import Literal

from pydantic import JsonValue

from capabilities.runtime import CapabilityInvocation
from common.assets import AssetIdentity, PathPart, RunInput, WorkflowManifest, WorkflowStep
from common.base import Contract, Text
from common.execution import (
    CapabilityResult,
    Failure,
    RequestContext,
    RunStatus,
    TraceIdentifiers,
    WorkflowRun,
)
from workflow.dispatch import BridgeExecutor

MAX_RUNS_KEPT = 50
MAX_LOG_LINES = 5000


class WorkflowRunSnapshot(Contract):
    """Step results carry validated outputs for the caller; log lines never do."""

    run: WorkflowRun
    log: tuple[Text, ...] = ()
    step_results: tuple[CapabilityResult, ...] = ()


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

    def __init__(self, workflow: AssetIdentity, trace: TraceIdentifiers) -> None:
        self.run_id = f"run-{uuid.uuid4().hex}"
        self.workflow = workflow
        self.trace = trace
        self.status: RunStatus = "running"
        self.completed_steps = 0
        self.failure: Failure | None = None
        self.log: list[str] = []
        self.step_results: list[CapabilityResult] = []

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
            ),
            log=tuple(self.log),
            step_results=tuple(result.model_copy(deep=True) for result in self.step_results),
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
    ) -> WorkflowRunSnapshot:
        if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise ValueError("timeout must be finite and positive")
        checked = RequestContext.model_validate(context)
        target = AssetIdentity.model_validate(workflow)
        manifest = self.workflows.get(target)
        # Pre-flight failures never create a run record (no ghost runs), matching
        # the source's load-before-create order.
        if manifest is None:
            return self._rejected(target, checked, "workflow_not_installed")
        if manifest.secrets:
            return self._rejected(target, checked, "secret_resolution_unavailable")
        if not set(manifest.dependencies.local_capabilities).issubset(self.bridge.installed.names):
            return self._rejected(target, checked, "missing_local_capability")
        if any(
            service.required and service.name not in self.bridge.services
            for service in manifest.dependencies.central_services
        ):
            return self._rejected(target, checked, "needs_connectivity")
        if any(self.bridge.installed.get(_target(step)) is None for step in manifest.steps):
            return self._rejected(target, checked, "capability_not_installed")

        run_arguments = deepcopy(arguments or {})
        try:
            for step in manifest.steps:
                if isinstance(step, WorkflowStep):
                    for ref in step.inputs.values():
                        if isinstance(ref, RunInput):
                            _select(run_arguments, ref.path)
        except _MissingInput:
            return self._rejected(target, checked, "workflow_input_missing", "needs_input")

        record = _RunRecord(target, checked.trace)
        self._runs[record.run_id] = record
        while len(self._runs) > MAX_RUNS_KEPT:
            # Only the record is evicted. The driving task stays strongly
            # referenced in _tasks until it finishes, or the event loop could
            # garbage-collect it mid-run and the run would never complete.
            del self._runs[next(iter(self._runs))]
        record.append_log(f"start workflow {_step_label(target)}")
        task = asyncio.create_task(self._drive(record, manifest, checked, run_arguments))
        self._tasks[record.run_id] = task
        task.add_done_callback(functools.partial(self._discard_task, record.run_id))
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
        status: Literal["unavailable", "needs_input"] = "unavailable",
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
    ) -> None:
        try:
            for index, step in enumerate(manifest.steps):
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
                result = await self.bridge.execute(
                    CapabilityInvocation(context=context, target=_target(step), arguments=inputs)
                )
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
