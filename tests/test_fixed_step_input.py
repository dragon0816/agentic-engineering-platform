"""A step input written into the Workflow itself (owner decision 2026-10-06).

Generated Workflows carry recorded web procedures, URLs and sheet names; before
this, a step could read only the run's arguments or an earlier step.
"""

from __future__ import annotations

import asyncio

import pytest
from test_gateway import Probe, Report, capability_spec, request, workflow_manifest

from capabilities.runtime import CapabilityGrant, InstalledCapabilities, LocalPolicy
from capabilities.workflow_author.review import rendered
from common.assets import ExecutionDependencies, WorkflowManifest
from common.base import Contract
from common.execution import RequestContext
from workflow.dispatch import BridgeExecutor
from workflow.engine import InstalledWorkflows, WorkflowEngine


class Recording:
    def __init__(self) -> None:
        self.inputs: list[Probe] = []

    async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
        self.inputs.append(Probe.model_validate(inputs))
        return Report()


def manifest_with(inputs: dict[str, object]) -> WorkflowManifest:
    data = workflow_manifest().model_dump(mode="json")
    data["steps"] = [{"capability": capability_spec().identity.model_dump(), "inputs": inputs}]
    return WorkflowManifest.model_validate(data)


def run(manifest: WorkflowManifest, arguments: dict[str, object]) -> tuple[object, Recording]:
    handler = Recording()
    installed = InstalledCapabilities()
    installed.register(
        capability_spec(), handler, Probe, Report, ExecutionDependencies(central_required=False)
    )
    bridge = BridgeExecutor(
        installed,
        LocalPolicy(
            (
                CapabilityGrant.model_validate(
                    {
                        "actor": "engineer",
                        "asset": capability_spec().identity,
                        "permissions": ["engineering.validate"],
                        "policy_refs": ["release-policy"],
                        "approval_ref": "release-approval",
                    }
                ),
            )
        ),
    )
    workflows = InstalledWorkflows()
    workflows.register(manifest)
    engine = WorkflowEngine(workflows, bridge)
    snapshot = asyncio.run(engine.execute(request("run"), manifest.metadata.identity, arguments))
    return snapshot, handler


def test_a_fixed_value_reaches_the_step_and_the_run_value_is_ignored() -> None:
    manifest = manifest_with({"args": {"source": "fixed", "value": "quick"}})
    snapshot, handler = run(manifest, {"args": "from-the-run"})
    assert snapshot.run.status == "succeeded"  # type: ignore[attr-defined]
    assert handler.inputs[0].args == "quick"


def test_fixed_and_run_inputs_mix_and_the_preview_shows_the_fixed_value() -> None:
    manifest = manifest_with({"args": {"source": "run", "path": ["mode"]}})
    snapshot, handler = run(manifest, {"mode": "deep"})
    assert handler.inputs[0].args == "deep"
    fixed = manifest_with({"args": {"source": "fixed", "value": "quick"}})
    installed = InstalledCapabilities()
    installed.register(
        capability_spec(), Recording(), Probe, Report, ExecutionDependencies(central_required=False)
    )
    assert 'args = fixed "quick"' in rendered(fixed, installed)


def test_a_credential_cannot_be_written_into_a_workflow() -> None:
    with pytest.raises(ValueError):
        manifest_with({"args": {"source": "fixed", "value": {"password": "hunter2-secret"}}})


def test_manifests_without_fixed_inputs_keep_their_bytes() -> None:
    plain = workflow_manifest()
    assert (
        plain.model_dump_json()
        == WorkflowManifest.model_validate_json(plain.model_dump_json()).model_dump_json()
    )
    assert '"fixed"' not in plain.model_dump_json()
