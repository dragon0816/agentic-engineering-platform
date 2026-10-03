"""Exact preview and approved apply assets for source Workflow 10."""

from agent.skills import SkillManifest
from capabilities.contracts import CapabilitySpec
from common.assets import AssetIdentity, WorkflowManifest

PREVIEW = AssetIdentity(namespace="engineering", name="sales-to-chipset-preview", version="1.0.0")
REPORT = AssetIdentity(namespace="engineering", name="sales-to-chipset", version="1.0.0")
SKILL = AssetIdentity(namespace="engineering", name="sales-to-chipset", version="1.0.0")

PREVIEW_SPEC = CapabilitySpec.model_validate(
    {
        "identity": {"namespace": "chipset-report", "name": "preview", "version": "1.0.0"},
        "name": "chipset_report.preview",
        "description": "Read source project lists and plan the chipset temp sheet without writing",
        "input_contract": "chipset-report.preview.input.v1",
        "output_contract": "chipset-report.preview.output.v1",
        "side_effect": "read",
        "policy": {
            "required_permissions": ["chipset-report.read"],
            "policy_refs": ["chipset-report-read-policy"],
        },
    }
)

APPLY_SPEC = CapabilitySpec.model_validate(
    {
        "identity": {"namespace": "chipset-report", "name": "apply", "version": "1.0.0"},
        "name": "chipset_report.apply",
        "description": "Replace only the chipset temp sheet from a validated preview plan",
        "input_contract": "chipset-report.apply.input.v1",
        "output_contract": "chipset-report.apply.output.v1",
        "side_effect": "write",
        "policy": {
            "risk": "medium",
            "approval_required": True,
            "required_permissions": ["excel.write"],
            "policy_refs": ["chipset-report-write-policy"],
        },
    }
)

_METADATA = {
    "owner": {"type": "team", "id": "engineering"},
    "visibility": "organization",
    "lifecycle": "published",
}


def preview_workflow() -> WorkflowManifest:
    return WorkflowManifest.model_validate(
        {
            "metadata": {"identity": PREVIEW.model_dump(), **_METADATA},
            "kind": "workflow",
            "run_alias": 10,
            "description": (
                "Preview Workflow 10's sales opportunity to chipset requirement projection. "
                "The managed sheet and temp sheet are never modified."
            ),
            "execution": {"mode": "local"},
            "dependencies": {
                "central_required": False,
                "local_capabilities": ["chipset_report.preview"],
            },
            "parameters": [
                {
                    "name": "max_rows",
                    "label": "Maximum rows per workbook",
                    "kind": "integer",
                    "minimum": 1,
                    "maximum": 50000,
                    "description": "Limit a preview without changing the host's source paths.",
                }
            ],
            "input_contract": "chipset-report.preview.input.v1",
            "output_contract": "chipset-report.preview.output.v1",
            "steps": [
                {
                    "capability": PREVIEW_SPEC.identity.model_dump(),
                    "inputs": {"request": {"source": "run"}},
                }
            ],
        }
    )


def report_workflow() -> WorkflowManifest:
    """Plan against current source rows, then write that exact plan to temp."""
    return WorkflowManifest.model_validate(
        {
            "metadata": {"identity": REPORT.model_dump(), **_METADATA},
            "kind": "workflow",
            "description": "Apply Workflow 10 to the chipset readiness workbook's temp sheet",
            "execution": {"mode": "local"},
            "dependencies": {
                "central_required": False,
                "local_capabilities": ["chipset_report.preview", "chipset_report.apply"],
            },
            "parameters": preview_workflow().parameters,
            "input_contract": "chipset-report.preview.input.v1",
            "output_contract": "chipset-report.apply.output.v1",
            "steps": [
                *preview_workflow().steps,
                {
                    "capability": APPLY_SPEC.identity.model_dump(),
                    "inputs": {"plan": {"source": "step", "step_index": 0}},
                },
            ],
        }
    )


def preview_skill() -> SkillManifest:
    return SkillManifest.model_validate(
        {
            "metadata": {"identity": SKILL.model_dump(), **_METADATA},
            "alias": "chipset",
            "instructions": (
                "Preview the sales opportunity to chipset requirement report. "
                "The source files, target workbook, header row and mapping rules "
                "come from this Host's static configuration."
            ),
            "commands": [
                {"name": "preview", "kind": "workflow", "target": PREVIEW.model_dump()},
                {"name": "apply", "kind": "workflow", "target": REPORT.model_dump()},
            ],
            "default_command": "preview",
        }
    )
