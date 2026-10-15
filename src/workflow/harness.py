"""Workflow execution on the shared Harness (unification U3, owner 2026-10-09).

The engine stays the executor: its journal, checkpoints and recovery are not
reimplemented here. The adapter runs it as the `execute` stage and validates
the run as the Host sees it: every step succeeded, and every output check the
Workflow declares holds. A Workflow is never retried as a whole (it may have
side effects); a step's own transient read retry stays inside the engine.
"""

from __future__ import annotations

import fnmatch
import hashlib
from contextlib import nullcontext
from typing import Any

import telemetry.recorder as telemetry
from agent.harness_plan import build_plan
from agent.harness_run import HarnessCheckResult
from agent.harness_runner import HarnessActionFailure, run_harness_async
from agent.skills import SkillHarnessGuidance
from common.assets import AssetIdentity, WorkflowManifest, WorkflowOutputCheck
from common.execution import Failure, RequestContext
from workflow.engine import WorkflowEngine, WorkflowRunSnapshot

STEPS_CHECK = "steps_succeeded"


def _files(data: Any) -> list[dict[str, Any]]:
    files = data.get("files") if isinstance(data, dict) else None
    return [item for item in files if isinstance(item, dict)] if isinstance(files, list) else []


def output_check(check: WorkflowOutputCheck, snapshot: WorkflowRunSnapshot) -> bool:
    if check.step_index >= len(snapshot.step_results):
        return False
    data = snapshot.step_results[check.step_index].data
    if check.kind == "data_nonempty":
        return data not in (None, "", [], {})
    matching = [
        item
        for item in _files(data)
        if check.pattern is None
        or fnmatch.fnmatch(
            str(item.get("path", "")).replace("\\", "/").rsplit("/", 1)[-1], check.pattern
        )
    ]
    if check.kind == "file_exists":
        return bool(matching)
    return any(int(item.get("bytes") or 0) > 0 for item in matching)


class WorkflowActions:
    def __init__(
        self,
        engine: WorkflowEngine,
        context: RequestContext,
        manifest: WorkflowManifest,
        arguments: dict[str, Any] | None,
        options: dict[str, Any],
    ) -> None:
        self.engine, self.context, self.manifest = engine, context, manifest
        self.arguments, self.options = arguments, options
        self.snapshot: WorkflowRunSnapshot | None = None

    async def execute(self) -> str:
        self.snapshot = await self.engine.execute(
            self.context, self.manifest.metadata.identity, self.arguments, **self.options
        )
        if self.snapshot.run.status == "needs_input":
            failure = self.snapshot.run.failure
            raise HarnessActionFailure(
                failure.code if failure else "workflow_input_missing", needs_input=True
            )
        return self.snapshot.run.run_id

    def validate(self) -> tuple[HarnessCheckResult, ...]:
        assert self.snapshot is not None
        run = self.snapshot.run
        results = [
            HarnessCheckResult(
                check_id=STEPS_CHECK,
                status="passed" if run.status == "succeeded" else "failed",
                evidence_ref=run.run_id,
            )
        ]
        for check in self.manifest.checks:
            passed = run.status == "succeeded" and output_check(check, self.snapshot)
            results.append(
                HarnessCheckResult(
                    check_id=check.check_id,
                    status="passed" if passed else "failed",
                    evidence_ref=run.run_id,
                )
            )
        return tuple(results)


async def run_workflow_checked(
    engine: WorkflowEngine,
    context: RequestContext,
    identity: AssetIdentity,
    arguments: dict[str, Any] | None,
    *,
    timeout_seconds: float | None = None,
    idempotency_key: str | None = None,
) -> WorkflowRunSnapshot:
    """Run an installed Workflow through the shared Harness. A run whose steps
    succeeded but whose output checks fail is reported as failed with
    `workflow_output_check_failed`; anything else is the engine's snapshot."""
    options: dict[str, Any] = {}
    if timeout_seconds is not None:
        options["timeout_seconds"] = timeout_seconds
    if idempotency_key is not None:
        options["idempotency_key"] = idempotency_key
    manifest = engine.workflows.get(identity)
    if manifest is None:
        return await engine.execute(context, identity, arguments, **options)
    actions = WorkflowActions(engine, context, manifest, arguments, options)
    plan = build_plan(
        task_id="workflow-"
        + hashlib.sha256(
            f"{identity.namespace}/{identity.name}@{identity.version}".encode()
        ).hexdigest()[:12],
        task_sha256=hashlib.sha256(manifest.model_dump_json().encode()).hexdigest(),
        domain="workflow",
        skill=identity,
        # A failed output check is a failed run, never a question to the person.
        guidance=SkillHarnessGuidance(domains=("workflow",), fallback="stop"),
        host_checks=(STEPS_CHECK, *(check.check_id for check in manifest.checks)),
        max_retries=0,
    )
    current = telemetry.current_run()
    opened = (
        telemetry.run(
            "workflow_run",
            trace_id=context.trace.trace_id,
            attributes={
                "workflow_id": f"{identity.namespace}/{identity.name}@{identity.version}",
                "steps": len(manifest.steps),
            },
        )
        if current is None or current.kind != "workflow_run"
        else nullcontext()
    )
    with opened:
        run = await run_harness_async(plan, actions)
        snapshot = actions.snapshot
        if snapshot is None:
            return await engine.execute(context, identity, arguments, **options)
        telemetry.set_run(workflow_run_id=snapshot.run.run_id, outcome=snapshot.run.status)
        if run.phase == "failed" and snapshot.run.status == "succeeded":
            failed = [c.check_id for c in run.checks if c.status == "failed"]
            telemetry.set_run(status="failed", failure_code="workflow_output_check_failed")
            return snapshot.model_copy(
                update={
                    "run": snapshot.run.model_copy(
                        update={
                            "status": "failed",
                            "failure": Failure(
                                code="workflow_output_check_failed",
                                message="Output checks failed: " + ", ".join(failed),
                            ),
                        }
                    )
                }
            )
        if snapshot.run.status != "succeeded":
            telemetry.set_run(status="failed")
        return snapshot
