"""Installed-only read preview for source Workflow 7 on company Jira."""

from agent.skills import SkillManifest
from common.assets import AssetIdentity, WorkflowManifest

PREVIEW_WORKFLOW = AssetIdentity(
    namespace="engineering", name="jira-team-tickets-preview", version="1.0.0"
)
PREVIEW_SKILL = AssetIdentity(namespace="engineering", name="team-tickets", version="2.0.0")

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
                "Read the configured company Jira project into Workflow 7's Task and Issues "
                "column preview. No workbook is opened or written."
            ),
            "execution": {"mode": "local"},
            "dependencies": {
                "central_required": False,
                "local_capabilities": ["team_tickets.jira_preview"],
            },
            "input_contract": "team-tickets.jira-preview.request.v1",
            "output_contract": "team-tickets.jira-preview.output.v1",
            "parameters": [
                {
                    "name": "max_items",
                    "label": "Maximum tickets",
                    "kind": "integer",
                    "minimum": 1,
                    "maximum": 2000,
                    "description": "Limit the number of Jira issues in this preview.",
                },
                {
                    "name": "comment_count",
                    "label": "Recent comments per ticket",
                    "kind": "integer",
                    "minimum": 0,
                    "maximum": 100,
                    "description": "Show up to this many newest comments per ticket.",
                },
                {
                    "name": "extra_jql",
                    "label": "Additional Jira filter",
                    "kind": "text",
                    "description": (
                        "Optional JQL clause combined with the configured project and reporters."
                    ),
                },
            ],
            "steps": [
                {
                    "capability": {
                        "namespace": "team-tickets",
                        "name": "jira-preview",
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
                "Preview the configured company Jira project in Workflow 7's Task and "
                "Issues format. This is read-only and reports per-ticket comment failures."
            ),
            "commands": [
                {"name": "preview", "kind": "workflow", "target": PREVIEW_WORKFLOW.model_dump()}
            ],
            "default_command": "preview",
        }
    )
