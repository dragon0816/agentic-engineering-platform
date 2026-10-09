"""Workflow execution on the shared Harness (unification U3, owner 2026-10-09):
the engine runs, the Host checks that every step succeeded and that the
Workflow's declared outputs exist."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from pydantic import JsonValue

from capabilities.contracts import CapabilitySpec
from capabilities.runtime import CapabilityGrant, InstalledCapabilities, LocalPolicy
from common.assets import ExecutionDependencies, WorkflowManifest
from common.base import Contract
from common.execution import RequestContext, TraceIdentifiers
from workflow.dispatch import BridgeExecutor
from workflow.engine import InstalledWorkflows, WorkflowEngine
from workflow.harness import run_workflow_checked


class In(Contract):
    size: int = 0


class Out(Contract):
    files: list[dict[str, JsonValue]]


async def writer(context: RequestContext, inputs: Contract) -> Contract:
    size = In.model_validate(inputs).size
    return Out(files=[{"path": "output/report.xlsx", "bytes": size}])


SPEC = CapabilitySpec.model_validate({
    "identity": {"namespace": "lab", "name": "make", "version": "1.0.0"},
    "name": "lab.make", "description": "make", "input_contract": "lab.make.in.v1",
    "output_contract": "lab.make.out.v1", "side_effect": "read",
    "policy": {"risk": "low", "required_permissions": ["lab.make"], "policy_refs": ["p"],
               "approval_required": False}})


def engine_with(checks: list[dict[str, Any]]) -> tuple[WorkflowEngine, WorkflowManifest]:
    installed = InstalledCapabilities()
    installed.register(SPEC, writer, In, Out, ExecutionDependencies(central_required=False))
    grant = CapabilityGrant(actor="owner", asset=SPEC.identity, permissions=("lab.make",),
                            policy_refs=("p",))
    manifest = WorkflowManifest.model_validate({
        "metadata": {"identity": {"namespace": "engineering", "name": "make-report",
                                  "version": "1.0.0"},
                     "owner": {"type": "user", "id": "owner"}, "visibility": "private",
                     "lifecycle": "published"},
        "description": "Make a report.", "execution": {"mode": "local"},
        "dependencies": {"central_required": False, "local_capabilities": ["lab.make"]},
        "parameters": [{"name": "size", "label": "size", "kind": "integer"}],
        "input_contract": "x.in.v1", "output_contract": "x.out.v1",
        "steps": [{"capability": SPEC.identity.model_dump(),
                   "inputs": {"size": {"source": "run", "path": ["size"]}}}],
        "checks": checks})
    workflows = InstalledWorkflows()
    workflows.register(manifest)
    return WorkflowEngine(workflows, BridgeExecutor(installed, LocalPolicy((grant,)))), manifest


def context() -> RequestContext:
    return RequestContext(trace=TraceIdentifiers(trace_id="t", request_id="r", span_id="s"),
                          actor="owner", namespace="engineering", channel="local", message="x")


def test_a_run_counts_only_when_its_declared_output_exists() -> None:
    engine, manifest = engine_with([{"check_id": "report_written", "step_index": 0,
                                     "kind": "files_nonempty", "pattern": "*.xlsx"}])
    identity = manifest.metadata.identity
    good = asyncio.run(run_workflow_checked(engine, context(), identity, {"size": 10}))
    assert good.run.status == "succeeded"
    empty = asyncio.run(run_workflow_checked(engine, context(), identity, {"size": 0}))
    assert empty.run.status == "failed"
    assert empty.run.failure is not None
    assert empty.run.failure.code == "workflow_output_check_failed"
    assert "report_written" in empty.run.failure.message


def test_a_workflow_without_checks_keeps_its_digest_and_behaviour(tmp_path: Path) -> None:
    engine, manifest = engine_with([])
    assert "checks" not in manifest.model_dump(mode="json")
    done = asyncio.run(run_workflow_checked(engine, context(), manifest.metadata.identity,
                                            {"size": 0}))
    assert done.run.status == "succeeded"
