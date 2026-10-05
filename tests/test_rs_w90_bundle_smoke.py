"""rs_workflow_system Workflow 90 (bundle_smoke) wrapped as a governed script tool.

Strategy WRAP: the pinned job runs unchanged; AEP adds the manifest, the
parameter declaration and Bridge policy. Characterization follows the
source behavior: the greeting defaults to `hello`, the report has five
checks and a summary `<greeting> from <host>: 5/5 checks passed`, and
`fail` makes the run fail.
"""

from __future__ import annotations

import asyncio
import hashlib
import importlib.util
import json
import shutil
import socket
from pathlib import Path
from typing import Any

import pytest
from test_host_wiring import membership_record, workspace

from capabilities.script_tools import load_script_tools
from common.execution import TraceIdentifiers
from common.local_agent import LocalWorkflowRequest
from host_runtime.host import build_runtime

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "packages/rs-workflow-system/w90-bundle-smoke"
SOURCE = Path(r"C:\Users\Chi_L\Documents\claude\n8n_workflow_system\host-bridge\jobs")
TOOL = ("engineering", "rs-bundle-smoke-tool", "1.0.0")


def _approved(manifest: dict[str, Any]) -> dict[str, Any]:
    """What the owner's publication flow would produce; a test stand-in only."""
    policy = {
        **manifest["metadata"]["technical_policy"],
        "status": "approved", "reviewer": "security-reviewer",
        "evidence": "Reviewed the pinned job and adapter.",
    }
    manifest["metadata"].update({
        "lifecycle": "published",
        "business_approval": {"status": "approved", "reviewer": "domain-owner",
                              "evidence": "Workflow 90 behavior reviewed."},
        "technical_policy": policy,
    })
    manifest["capability"]["policy"] = policy
    return manifest


def _install(layout: Any, *, approve: bool = True) -> None:
    target = layout.script_tools.joinpath(*TOOL)
    target.mkdir(parents=True)
    shutil.copy2(PACKAGE / "run.py", target / "run.py")
    shutil.copytree(PACKAGE / "vendor", target / "vendor")
    manifest = json.loads((PACKAGE / "script-tool.json").read_text(encoding="utf-8"))
    (target / "script-tool.json").write_text(
        json.dumps(_approved(manifest) if approve else manifest), encoding="utf-8"
    )
    shutil.copy2(PACKAGE / "workflow.json", layout.workflows / "rs-bundle-smoke.json")


def _grant() -> dict[str, Any]:
    return {
        "actor": "engineer",
        "asset": dict(zip(("namespace", "name", "version"), TOOL, strict=True)),
        "permissions": ["rs-workflow.bundle-smoke.execute"],
        "policy_refs": ["script-execution-policy"],
        "approval_ref": "w90-approval",
    }


def _run(runtime: Any, config: Any, arguments: dict[str, Any], key: str) -> Any:
    workflow = json.loads((PACKAGE / "workflow.json").read_text(encoding="utf-8"))
    from common.assets import AssetIdentity

    request = LocalWorkflowRequest(
        actor="engineer", bridge_id=config.device.bridge_id,
        workflow=AssetIdentity.model_validate(workflow["metadata"]["identity"]),
        arguments=arguments, idempotency_key=key,
        trace=TraceIdentifiers(trace_id=f"w90-{key}", request_id="w90", span_id="test"),
    )
    return asyncio.run(runtime.agent.execute_workflow(request))


def test_workflow_90_runs_the_pinned_job_through_bridge_policy(tmp_path: Path) -> None:
    config, layout = workspace(
        tmp_path / "granted", membership=membership_record(), grants=[_grant()],
    )
    _install(layout)
    with build_runtime(config) as runtime:
        default = _run(runtime, config, {}, "default")
        assert default.workflow is not None
        assert default.workflow.run.status == "succeeded", default.workflow.run.failure
        report = default.workflow.step_results[-1].data["result"]
        assert report["greeting"] == "hello"
        assert report["summary"] == f"hello from {socket.gethostname()}: 5/5 checks passed"
        assert len(report["checks"]) == 5 and all(item["ok"] for item in report["checks"])
        named = _run(runtime, config, {"greeting": "w90-check"}, "named")
        assert named.workflow is not None
        assert named.workflow.step_results[-1].data["result"]["greeting"] == "w90-check"
        failed = _run(runtime, config, {"fail": True}, "fail")
        assert failed.workflow is not None and failed.workflow.run.status == "failed"
        assert failed.workflow.run.failure is not None
        assert failed.workflow.run.failure.code == "script_failed"

    config, layout = workspace(tmp_path / "denied", membership=membership_record())
    _install(layout)
    with build_runtime(config) as runtime:
        denied = _run(runtime, config, {}, "denied")
        assert denied.workflow is not None and denied.workflow.run.failure is not None
        assert denied.workflow.run.failure.code == "permission_denied"


def test_the_candidate_package_is_not_installable_before_approval(tmp_path: Path) -> None:
    config, layout = workspace(tmp_path, membership=membership_record())
    _install(layout, approve=False)
    with pytest.raises(ValueError, match="published"):
        load_script_tools(layout.script_tools)


def test_vendored_job_is_byte_identical_to_the_pinned_source() -> None:
    spec = importlib.util.spec_from_file_location("w90_run", PACKAGE / "run.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for relative, digest in module.PINNED.items():
        vendored = (PACKAGE / "vendor" / relative).read_bytes()
        assert hashlib.sha256(vendored).hexdigest() == digest
        source = SOURCE / Path(relative).name
        if source.exists():
            assert source.read_bytes() == vendored


def test_committed_manifests_match_the_generator() -> None:
    spec = importlib.util.spec_from_file_location(
        "w90_build", PACKAGE / "build_manifests.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for name, model in (
        ("script-tool.json", module.tool_manifest()),
        ("workflow.json", module.workflow_manifest()),
        ("skill.json", module.skill_manifest()),
    ):
        committed = json.loads((PACKAGE / name).read_text(encoding="utf-8"))
        assert committed == model.model_dump(mode="json"), name
