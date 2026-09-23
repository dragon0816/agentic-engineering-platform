"""The Skill and the Workflow that run the weekly report's preview.

Shipped as contracts so a host, a test and the Registry all take the same
manifests; `aep-host export-assets` writes them as the JSON files a workspace
or a publisher takes.
"""

import json
from pathlib import Path

from agent.skills import SkillManifest
from common.assets import AssetIdentity, WorkflowManifest
from host_runtime.workspace import write_atomically

PREVIEW_WORKFLOW = AssetIdentity(
    namespace="engineering", name="jira-weekly-report-preview", version="1.0.0"
)
WEEKLY_SKILL = AssetIdentity(namespace="engineering", name="weekly-report", version="1.0.0")

_METADATA = {
    "owner": {"type": "team", "id": "engineering"},
    "visibility": "organization",
    "lifecycle": "published",
}


def preview_workflow() -> WorkflowManifest:
    """Resolve the week, fetch the week's issues, read the scratch sheet,
    plan. Every step is a read; the run's arguments are the request."""
    return WorkflowManifest.model_validate(
        {
            "metadata": {"identity": PREVIEW_WORKFLOW.model_dump(), **_METADATA},
            "kind": "workflow",
            "description": (
                "Preview the GTM weekly report: the week's Jira issues planned against the "
                "workbook's scratch sheet, with nothing written"
            ),
            "execution": {"mode": "local"},
            "dependencies": {"central_required": False},
            "input_contract": "engineering.jira-weekly-report.request.v1",
            "output_contract": "weekly-report.plan.output.v1",
            "steps": [
                {
                    "capability": {
                        "namespace": "weekly-report",
                        "name": "resolve-window",
                        "version": "1.0.0",
                    },
                    "inputs": {"request": {"source": "run"}},
                },
                {
                    "capability": {"namespace": "jira", "name": "search", "version": "1.0.0"},
                    "inputs": {
                        "jql": {"source": "step", "step_index": 0, "path": ["jql"]},
                        "max_issues": {"source": "step", "step_index": 0, "path": ["max_issues"]},
                    },
                },
                {
                    "capability": {
                        "namespace": "excel",
                        "name": "read-scratch-sheet",
                        "version": "1.0.0",
                    },
                    "inputs": {"week": {"source": "step", "step_index": 0, "path": ["week"]}},
                },
                {
                    "capability": {
                        "namespace": "weekly-report",
                        "name": "plan",
                        "version": "1.0.0",
                    },
                    "inputs": {
                        "window": {"source": "step", "step_index": 0},
                        "issues": {"source": "step", "step_index": 1, "path": ["issues"]},
                        "sheet": {"source": "step", "step_index": 2},
                    },
                },
            ],
        }
    )


def weekly_skill() -> SkillManifest:
    """`weekly.preview` from a local operator or `/weekly preview` from
    Telegram; the request is whatever follows the command."""
    return SkillManifest.model_validate(
        {
            "metadata": {"identity": WEEKLY_SKILL.model_dump(), **_METADATA},
            "alias": "weekly",
            "instructions": (
                "Preview the GTM weekly report for the current week, or for a named week "
                "such as 2026_31W."
            ),
            "commands": [
                {"name": "preview", "kind": "workflow", "target": PREVIEW_WORKFLOW.model_dump()}
            ],
            "default_command": "preview",
        }
    )


def export_assets(directory: Path) -> tuple[Path, ...]:
    """Write the shipped manifests where a workspace or a publisher reads
    them: `skills/` and `workflows/` under `directory`."""
    written: list[Path] = []
    for folder, manifest in (
        ("skills", weekly_skill()),
        ("workflows", preview_workflow()),
    ):
        identity = manifest.metadata.identity
        path = (
            directory / folder / f"{identity.namespace}__{identity.name}__{identity.version}.json"
        )
        payload = json.dumps(manifest.model_dump(mode="json"), indent=2, ensure_ascii=False)
        write_atomically(path, payload.encode("utf-8") + b"\n")
        written.append(path)
    return tuple(written)
