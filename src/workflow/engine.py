"""Deterministic workflow engine: ordered capability steps through Bridge dispatch.

Run-tracking semantics are adapted from the pinned rs_workflow_system job runner;
lineage, preserved invariants and intentional differences are recorded in
docs/PHASE_3_MIGRATION.md. The engine never imports job code: workflows are
explicitly installed manifests and every step is authorized by the Bridge.
"""

import asyncio
import math
import uuid

from pydantic import JsonValue

from capabilities.runtime import CapabilityInvocation
from common.assets import AssetIdentity, WorkflowManifest
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
        return self._workflows.get(identity.key)


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

    def append_log(self, message: str) -> None:
        if len(self.log) < MAX_LOG_LINES:
            self.log.append(message)
        elif len(self.log) == MAX_LOG_LINES:
            self.log.append(f"… log truncated ({MAX_LOG_LINES} lines)")

    def snapshot(self) -> WorkflowRunSnapshot:
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
            step_results=tuple(self.step_results),
        )


def _step_label(identity: AssetIdentity) -> str:
    return f"{identity.namespace}/{identity.name}@{identity.version}"


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
            await task
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
        # Pre-flight failures never create a run record (no ghost runs).
        if manifest is None:
            return self._rejected(target, checked, "workflow_not_installed")
        if manifest.secrets:
            return self._rejected(target, checked, "secret_resolution_unavailable")
        if any(
            service.required and service.name not in self.bridge.services
            for service in manifest.dependencies.central_services
        ):
            return self._rejected(target, checked, "needs_connectivity")

        record = _RunRecord(target, checked.trace)
        self._runs[record.run_id] = record
        while len(self._runs) > MAX_RUNS_KEPT:
            evicted = next(iter(self._runs))
            del self._runs[evicted]
            self._tasks.pop(evicted, None)
        record.append_log(f"start workflow {_step_label(target)}")
        task = asyncio.create_task(self._drive(record, manifest, checked, dict(arguments or {})))
        self._tasks[record.run_id] = task
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

    def _rejected(
        self, workflow: AssetIdentity, context: RequestContext, code: str
    ) -> WorkflowRunSnapshot:
        record = _RunRecord(workflow, context.trace)
        record.status = "unavailable"
        record.failure = Failure(code=code, message="Workflow was not started")
        return record.snapshot()

    async def _drive(
        self,
        record: _RunRecord,
        manifest: WorkflowManifest,
        context: RequestContext,
        arguments: dict[str, JsonValue],
    ) -> None:
        try:
            for step in manifest.steps:
                result = await self.bridge.execute(
                    CapabilityInvocation(context=context, target=step, arguments=arguments)
                )
                record.step_results.append(result)
                code = result.failure.code if result.failure is not None else None
                record.append_log(
                    f"step {len(record.step_results)} {_step_label(step)} {result.status}"
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
