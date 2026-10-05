"""Regenerate this package's manifests from AEP contracts.

Run from the repository root:
    .venv/Scripts/python packages/rs-workflow-system/w90-bundle-smoke/build_manifests.py

The script-tool manifest is a candidate: lifecycle `validated` with business
and technical approval pending. The owner approves it through the normal
publication flow before a Host can install it; nothing here grants execution.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "src"))

from agent.skills import SkillManifest  # noqa: E402
from capabilities.script_tools import ScriptToolManifest  # noqa: E402
from common.assets import WorkflowManifest  # noqa: E402

TOOL = {"namespace": "engineering", "name": "rs-bundle-smoke-tool", "version": "1.0.0"}
WORKFLOW = {"namespace": "engineering", "name": "rs-bundle-smoke", "version": "1.0.0"}
SKILL = {"namespace": "engineering", "name": "rs-bundle-smoke-skill", "version": "1.0.0"}
OWNER = {"type": "team", "id": "engineering"}
POLICY = {
    "status": "pending",
    "risk": "low",
    "approval_required": True,
    "required_permissions": ["rs-workflow.bundle-smoke.execute"],
    "policy_refs": ["script-execution-policy"],
    "assessment": "manual",
}
CANDIDATE = {"visibility": "private", "lifecycle": "validated", "owner": OWNER}


def tool_manifest() -> ScriptToolManifest:
    digest = hashlib.sha256((HERE / "run.py").read_bytes()).hexdigest()
    return ScriptToolManifest.model_validate({
        "metadata": {"identity": TOOL, **CANDIDATE, "technical_policy": POLICY},
        "description": (
            "rs_workflow_system Workflow 90 bundle smoke test, carried unchanged: reports "
            "what this computer can see and touches nothing."
        ),
        "runtime": "python",
        "entrypoint": "run.py",
        "sha256": digest,
        "timeout_seconds": 30,
        "capability": {
            "identity": TOOL,
            "name": "rs_workflow.bundle_smoke",
            "description": "Run the pinned bundle_smoke job and return its report.",
            "input_contract": "engineering.script-tool.input.v1",
            "output_contract": "engineering.script-tool.output.v1",
            "side_effect": "execute",
            "policy": POLICY,
        },
        "dependencies": {"central_required": False},
    })


def workflow_manifest() -> WorkflowManifest:
    return WorkflowManifest.model_validate({
        "metadata": {"identity": WORKFLOW, **CANDIDATE},
        "kind": "workflow",
        "run_alias": 90,
        "description": (
            "Workflow 90: prove an installed bundle landed and can run. No Excel, Outlook, "
            "browser or file writes."
        ),
        "execution": {"mode": "local"},
        "dependencies": {
            "central_required": False,
            "local_capabilities": ["rs_workflow.bundle_smoke"],
        },
        "parameters": [
            {"name": "greeting", "label": "Greeting", "kind": "text", "order": 10,
             "help": "Text echoed back, so you can tell one run from another.",
             "examples": ["hello"]},
            {"name": "fail", "label": "Fail on purpose", "kind": "boolean", "order": 20,
             "default": False,
             "help": "Raise on purpose, to see how a failing run is reported end to end."},
        ],
        "progress_steps": [{"id": "smoke", "title": "Run the bundle checks"}],
        "input_contract": "engineering.rs-bundle-smoke.input.v1",
        "output_contract": "engineering.script-tool.output.v1",
        "steps": [
            {"capability": TOOL, "inputs": {"arguments": {"source": "run"}}},
        ],
    })


def skill_manifest() -> SkillManifest:
    return SkillManifest.model_validate({
        "metadata": {"identity": SKILL, **CANDIDATE},
        "alias": "smoke",
        "instructions": "Run Workflow 90 to check that this computer's bundle runs.",
        "commands": [{"name": "run", "kind": "workflow", "target": WORKFLOW}],
        "default_command": "run",
    })


def main() -> None:
    for name, model in (
        ("script-tool.json", tool_manifest()),
        ("workflow.json", workflow_manifest()),
        ("skill.json", skill_manifest()),
    ):
        (HERE / name).write_text(
            json.dumps(model.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
