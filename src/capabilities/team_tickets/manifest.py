"""Installed-only read preview for source Workflow 7 on the GitHub Project."""

from agent.skills import SkillManifest
from common.assets import AssetIdentity, WorkflowManifest

PREVIEW_WORKFLOW = AssetIdentity(
    namespace="engineering", name="github-team-tickets-preview", version="1.0.0"
)
PREVIEW_SKILL = AssetIdentity(namespace="engineering", name="team-tickets", version="1.0.0")

_METADATA = {
    "owner": {"type": "team", "id": "engineering"},
    "visibility": "organization",
    "lifecycle": "published",
}


def preview_workflow() -> WorkflowManifest:
    return WorkflowManifest.model_validate(
        {
            "metadata": {"identity": PREVIEW_WORKFLOW.model_dump(), **_METADATA},
            "kind": "workflow",
            "run_alias": 7,
            "description": (
                "Read the configured GitHub Project into Workflow 7's Task and Issues "
                "column preview. No workbook is opened or written."
            ),
            "execution": {"mode": "local"},
            "dependencies": {
                "central_required": False,
                "local_capabilities": ["team_tickets.preview"],
            },
            "input_contract": "team-tickets.preview.request.v1",
            "output_contract": "team-tickets.preview.output.v1",
            "parameters": [
                {
                    "name": "max_items",
                    "label": "Maximum tickets",
                    "kind": "integer",
                    "minimum": 1,
                    "maximum": 2000,
                    "description": "Limit the number of Project issues in this preview.",
                },
                {
                    "name": "comment_count",
                    "label": "Recent comments per ticket",
                    "kind": "integer",
                    "minimum": 0,
                    "maximum": 100,
                    "description": "Show up to this many complete comments per ticket.",
                },
            ],
            "steps": [
                {
                    "capability": {
                        "namespace": "team-tickets",
                        "name": "preview",
                        "version": "1.0.0",
                    },
                    "inputs": {"request": {"source": "run"}},
                }
            ],
        }
    )


def preview_skill() -> SkillManifest:
    return SkillManifest.model_validate(
        {
            "metadata": {"identity": PREVIEW_SKILL.model_dump(), **_METADATA},
            "alias": "tickets",
            "instructions": (
                "Preview the configured GitHub Project in Workflow 7's Task and Issues "
                "format. This is read-only; missing source fields and incomplete comment "
                "threads are reported rather than silently inferred."
            ),
            "commands": [
                {"name": "preview", "kind": "workflow", "target": PREVIEW_WORKFLOW.model_dump()}
            ],
            "default_command": "preview",
        }
    )
