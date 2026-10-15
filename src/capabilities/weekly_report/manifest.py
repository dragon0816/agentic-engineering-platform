"""The Skill and the Workflow that run Workflow 11, the SDE weekly report.

One Workflow does what source Workflow 11 does in one trigger: read the
board, plan, write the workbook and save the mail draft. The read-only
preview manifest stays defined for the marketplace's read-only default
candidate (`host_runtime.default_candidates`); it is not shipped.

Shipped as contracts so a host, a test and the Registry all take the same
manifests; `host_runtime.assets.export_assets` writes them as the JSON files
a workspace or a publisher takes. Pure data: nothing here touches a file.
"""

from typing import Any

from agent.skills import SkillManifest
from common.assets import AssetIdentity, WorkflowManifest

PREVIEW_WORKFLOW = AssetIdentity(
    namespace="engineering", name="jira-weekly-report-preview", version="1.0.0"
)
WEEKLY_WORKFLOW = AssetIdentity(namespace="engineering", name="sde-weekly-report", version="1.0.0")
WEEKLY_SKILL = AssetIdentity(namespace="engineering", name="weekly-report", version="2.0.0")

_METADATA = {
    "owner": {"type": "team", "id": "engineering"},
    "visibility": "organization",
    "lifecycle": "published",
}

_RUN_PARAMETERS: list[dict[str, Any]] = [
    {
        "name": "week",
        "label": "Report week",
        "kind": "text",
        "description": "Weekly sheet name, for example 2026_40W.",
    },
    {
        "name": "since",
        "label": "From date",
        "kind": "date",
        "description": "Optional start of the reporting window.",
    },
    {
        "name": "until",
        "label": "Through date",
        "kind": "date",
        "description": "Optional end of the reporting window.",
    },
    {
        "name": "max_issues",
        "label": "Maximum issues",
        "kind": "integer",
        "minimum": 1,
        "description": "Limit the number of Project items read.",
    },
    {
        "name": "args",
        "label": "Advanced arguments",
        "kind": "text",
        "description": "Optional command-style fields, such as since=2026-09-28 max=50.",
    },
]


def preview_workflow() -> WorkflowManifest:
    """Resolve the week, fetch the week's issues, read the scratch sheet,
    plan. Every step is a read; the run's arguments are the request."""
    return WorkflowManifest.model_validate(
        {
            "metadata": {"identity": PREVIEW_WORKFLOW.model_dump(), **_METADATA},
            "kind": "workflow",
            "run_alias": 11,
            "parameters": _RUN_PARAMETERS,
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


def _weekly_steps() -> list[dict[str, object]]:
    """The preview's four steps, with the board read given the precise
    window and the comment start (source `startTime`/`endTime`)."""
    steps = _plan_steps()
    search = dict(steps[1])
    search["inputs"] = {
        **dict(search["inputs"]),  # type: ignore[call-overload]
        **{
            name: {"source": "step", "step_index": 0, "path": [name]}
            for name in ("comment_since", "start_time", "end_time")
        },
    }
    steps[1] = search
    return steps


_WEEKLY_PARAMETERS: list[dict[str, Any]] = [
    {
        "name": "dry_run",
        "label": "Dry run: show the plan only",
        "kind": "boolean",
        "default": False,
        "order": 5,
        "help": "Plan the week and show it; the workbook and the mail are not touched.",
    },
    *[
        {**item, "order": 10 * (index + 1)}
        for index, item in enumerate(_RUN_PARAMETERS)
        if item["name"] != "args"
    ],
    {
        "name": "start_time",
        "label": "Window start (date or time)",
        "kind": "text",
        "order": 45,
        "help": "Optional precise start, e.g. 2026-09-21 or 2026-09-21T09:00; "
        "times without an offset are Taiwan time.",
    },
    {
        "name": "end_time",
        "label": "Window end (date or time)",
        "kind": "text",
        "order": 46,
        "help": "Optional precise end; a date alone means the end of that day.",
    },
    {
        "name": "draft_mail",
        "label": "Save the weekly mail draft",
        "kind": "boolean",
        "default": True,
        "order": 70,
        "help": "After writing the workbook, save the week's mail as an Outlook draft "
        "(never sent).",
    },
    {**_RUN_PARAMETERS[-1], "order": 90, "channels": ["telegram", "agent"]},
]


_PLAN_CAPABILITIES = [
    "weekly_report.resolve_window",
    "github.search_project",
    "excel.read_scratch_sheet",
    "weekly_report.plan",
]


def weekly_report_workflow() -> WorkflowManifest:
    """Source Workflow 11 as one run: read the GitHub board, plan against the
    scratch sheet, write it, then save the week's mail as a draft (never
    sent). `dry_run` stops at the plan; `draft_mail` turns the draft off."""
    return WorkflowManifest.model_validate(
        {
            "metadata": {"identity": WEEKLY_WORKFLOW.model_dump(), **_METADATA},
            "kind": "workflow",
            "run_alias": 11,
            "parameters": _WEEKLY_PARAMETERS,
            "description": (
                "Workflow 11, the SDE weekly report: the week's GitHub board items planned "
                "against the workbook's scratch sheet, written into it, and the week's mail "
                "saved as a draft nobody has sent. A dry run shows the plan and writes nothing."
            ),
            "execution": {"mode": "local"},
            "dependencies": {
                "central_required": False,
                "local_capabilities": [
                    *_PLAN_CAPABILITIES,
                    "weekly_report.apply",
                    "weekly_report.mail",
                ],
            },
            "progress_steps": [
                {"id": "fetch", "title": "Read the week's items from the GitHub board"},
                {"id": "open", "title": "Read the weekly report workbook"},
                {"id": "plan", "title": "Plan new and updated rows and comment blocks"},
                {"id": "apply", "title": "Write the weekly report temp sheet"},
                {"id": "mail", "title": "Save the weekly mail draft", "optional": True},
            ],
            "input_contract": "engineering.sde-weekly-report.request.v1",
            "output_contract": "weekly-report.mail.output.v1",
            "steps": [
                *_weekly_steps(),
                {
                    "capability": {
                        "namespace": "weekly-report",
                        "name": "apply",
                        "version": "1.0.0",
                    },
                    "inputs": {
                        "plan": {"source": "step", "step_index": 3},
                        "skip": {"source": "step", "step_index": 0, "path": ["dry_run"]},
                    },
                },
                {
                    "capability": {
                        "namespace": "weekly-report",
                        "name": "mail",
                        "version": "1.0.0",
                    },
                    "inputs": {
                        "window": {"source": "step", "step_index": 0},
                        "issues": {"source": "step", "step_index": 1, "path": ["items"]},
                    },
                },
            ],
        }
    )


def weekly_skill() -> SkillManifest:
    """`weekly` from a local operator or `/weekly` from Telegram; the request
    is whatever follows the command."""
    return SkillManifest.model_validate(
        {
            "metadata": {"identity": WEEKLY_SKILL.model_dump(), **_METADATA},
            "alias": "weekly",
            "selector_hint": (
                "SDE weekly report 週報: GitHub board items into the weekly Excel sheet "
                "and mail draft"
            ),
            "instructions": (
                "Run the SDE weekly report (Workflow 11) for the current week, or for a named "
                "week such as 2026_31W: it reads the GitHub board, writes the workbook's scratch "
                "sheet and saves the week's mail as a draft. Offer dry_run to see the plan first."
            ),
            "commands": [
                {"name": "run", "kind": "workflow", "target": WEEKLY_WORKFLOW.model_dump()},
            ],
            "default_command": "run",
        }
    )
