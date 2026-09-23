"""The Skill and the Workflow that run the weekly report's preview.

Shipped as contracts so a host, a test and the Registry all take the same
manifests; `host_runtime.assets.export_assets` writes them as the JSON files
a workspace or a publisher takes. Pure data: nothing here touches a file.
"""

from agent.skills import SkillManifest
from common.assets import AssetIdentity, WorkflowManifest

PREVIEW_WORKFLOW = AssetIdentity(
    namespace="engineering", name="jira-weekly-report-preview", version="1.0.0"
)
REPORT_WORKFLOW = AssetIdentity(namespace="engineering", name="jira-weekly-report", version="1.0.0")
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
                "Preview the GTM weekly report: the week's tracked items planned against the "
                "workbook's scratch sheet, with nothing written"
            ),
            "execution": {"mode": "local"},
            # Named so the engine refuses the run before its first step on a
            # host that lacks any of them, rather than failing at step 1.
            "dependencies": {"central_required": False, "local_capabilities": _PLAN_CAPABILITIES},
            "input_contract": "engineering.jira-weekly-report.request.v1",
            "output_contract": "weekly-report.plan.output.v1",
            "steps": _plan_steps(),
        }
    )


#: The four steps a preview runs, which the full report runs before it
#: writes. Named once so the two manifests cannot drift apart.
def _plan_steps() -> list[dict[str, object]]:
    return [
        {
            "capability": {
                "namespace": "weekly-report",
                "name": "resolve-window",
                "version": "1.0.0",
            },
            "inputs": {"request": {"source": "run"}},
        },
        {
            "capability": {"namespace": "github", "name": "search-project", "version": "1.0.0"},
            "inputs": {
                "since": {"source": "step", "step_index": 0, "path": ["since"]},
                "until": {"source": "step", "step_index": 0, "path": ["until"]},
                "max_issues": {"source": "step", "step_index": 0, "path": ["max_issues"]},
            },
        },
        {
            "capability": {"namespace": "excel", "name": "read-scratch-sheet", "version": "1.0.0"},
            "inputs": {"week": {"source": "step", "step_index": 0, "path": ["week"]}},
        },
        {
            "capability": {"namespace": "weekly-report", "name": "plan", "version": "1.0.0"},
            "inputs": {
                "window": {"source": "step", "step_index": 0},
                "issues": {"source": "step", "step_index": 1, "path": ["items"]},
                "capped": {"source": "step", "step_index": 1, "path": ["capped"]},
                "truncated_threads": {
                    "source": "step",
                    "step_index": 1,
                    "path": ["truncated"],
                },
                "sheet": {"source": "step", "step_index": 2},
            },
        },
    ]


_PLAN_CAPABILITIES = [
    "weekly_report.resolve_window",
    "github.search_project",
    "excel.read_scratch_sheet",
    "weekly_report.plan",
]


def report_workflow() -> WorkflowManifest:
    """The preview's four steps, then the write. Kept as its own asset so a
    member can be given the dry run alone."""
    return WorkflowManifest.model_validate(
        {
            "metadata": {"identity": REPORT_WORKFLOW.model_dump(), **_METADATA},
            "kind": "workflow",
            "description": (
                "The GTM weekly report: the week's tracked items planned against the workbook's "
                "scratch sheet and written into it"
            ),
            "execution": {"mode": "local"},
            "dependencies": {
                "central_required": False,
                "local_capabilities": [*_PLAN_CAPABILITIES, "weekly_report.apply"],
            },
            "input_contract": "engineering.jira-weekly-report.request.v1",
            "output_contract": "weekly-report.apply.output.v1",
            "steps": [
                *_plan_steps(),
                {
                    "capability": {
                        "namespace": "weekly-report",
                        "name": "apply",
                        "version": "1.0.0",
                    },
                    "inputs": {"plan": {"source": "step", "step_index": 3}},
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
                "such as 2026_31W; `weekly apply` writes the same plan into the workbook."
            ),
            "commands": [
                {"name": "preview", "kind": "workflow", "target": PREVIEW_WORKFLOW.model_dump()},
                {"name": "apply", "kind": "workflow", "target": REPORT_WORKFLOW.model_dump()},
            ],
            # A preview by default: writing the workbook is asked for.
            "default_command": "preview",
        }
    )
