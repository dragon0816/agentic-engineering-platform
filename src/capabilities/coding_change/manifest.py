"""Coding on the Bridge: the capability, the Workflow people run, the Skill.

The Workflow is the person-facing shape: its parameters give the Agent a tool
schema, Telegram a question flow and Agent Web a form. The capability does
the work under the host's `coding` binding; nothing here names a path.
"""

from agent.skills import SkillManifest
from capabilities.contracts import CapabilitySpec
from common.assets import AssetIdentity, WorkflowManifest

WORKFLOW = AssetIdentity(namespace="engineering", name="coding-change", version="1.0.0")
SKILL = AssetIdentity(namespace="engineering", name="coding", version="1.4.0")
RUN_WORKFLOW = AssetIdentity(namespace="engineering", name="run-python", version="1.0.0")
REPOSITORIES_FUNCTION = "coding.repositories"

CHANGE_SPEC = CapabilitySpec.model_validate(
    {
        "identity": {"namespace": "coding", "name": "change", "version": "1.0.0"},
        "name": "coding.change",
        "description": (
            "Change one file in a configured repository until its tests pass, in a "
            "separate git worktree; never commits"
        ),
        "input_contract": "coding.change.input.v1",
        "output_contract": "coding.change.output.v1",
        "side_effect": "write",
        "policy": {
            "risk": "medium",
            "approval_required": True,
            "required_permissions": ["coding.change"],
            "policy_refs": ["coding-restricted-execution-policy"],
        },
    }
)

_METADATA = {
    "owner": {"type": "team", "id": "engineering"},
    "visibility": "organization",
    "lifecycle": "published",
}

_PARAMETERS = [
    {"name": "repository", "label": "Which repository?", "kind": "select", "required": True,
     "choices_source": f"fn:{REPOSITORIES_FUNCTION}", "order": 10},
    {"name": "requirement", "label": "What should change?", "kind": "text", "required": True,
     "order": 20, "help": "Describe the behaviour the tests expect, in a sentence or two."},
    {"name": "file", "label": "Which file may be changed?", "kind": "text", "required": True,
     "order": 30, "examples": ["src/practice/durations.py"],
     "help": "Path inside the repository. Test files can never be changed."},
    {"name": "tests", "label": "Which tests say it is done?", "kind": "text_list",
     "required": True, "order": 40, "examples": ["tests/test_durations.py"],
     "help": "Existing pytest files or node ids, one per line. The whole test folder "
             "also runs as the regression check."},
    {"name": "max_repairs", "label": "How many repair attempts?", "kind": "integer",
     "default": 2, "minimum": 0, "maximum": 3, "order": 50},
]


def coding_workflow() -> WorkflowManifest:
    return WorkflowManifest.model_validate(
        {
            "metadata": {"identity": WORKFLOW.model_dump(), **_METADATA},
            "kind": "workflow",
            "description": (
                "Change one file in a configured repository with the Gateway model until the "
                "named tests and the whole test folder pass. Generated code runs restricted "
                "(low integrity, no network, one process); the change stays in a separate "
                "git worktree for review and is never committed."
            ),
            "execution": {"mode": "local"},
            "dependencies": {
                "central_required": False,
                "local_capabilities": [CHANGE_SPEC.name],
            },
            "parameters": _PARAMETERS,
            "progress_steps": [
                {"id": "change", "title": "Plan, change, test and repair"},
            ],
            "input_contract": "engineering.coding-change.input.v1",
            "output_contract": "coding.change.output.v1",
            "steps": [
                {"capability": CHANGE_SPEC.identity.model_dump(),
                 "inputs": {"request": {"source": "run"}}},
            ],
        }
    )


def run_python_workflow() -> WorkflowManifest:
    from capabilities.coding_change.run_python import RUN_SPEC

    return WorkflowManifest.model_validate(
        {
            "metadata": {"identity": RUN_WORKFLOW.model_dump(), **_METADATA},
            "kind": "workflow",
            "description": (
                "Run one Python script for a task the person asked for, in a task workspace "
                "folder they named. The script reads the workspace and writes only to its "
                "output folder; the result shows the exit code, what it printed and the "
                "output files, so a failing script can be fixed and run again."
            ),
            "execution": {"mode": "local"},
            "dependencies": {"central_required": False, "local_capabilities": [RUN_SPEC.name]},
            "parameters": [
                {"name": "workspace", "label": "Which task workspace folder?", "kind": "text",
                 "required": True, "order": 10,
                 "help": "The absolute folder the person named; it holds input/ and output/."},
                {"name": "script", "label": "The complete Python script", "kind": "text",
                 "required": True, "order": 20,
                 "help": "Python 3.12 with openpyxl. Relative paths resolve from the workspace. "
                         "Print what you need to check. Never write credentials literally."},
            ],
            "input_contract": "engineering.run-python.input.v1",
            "output_contract": "coding.run-python.output.v1",
            "steps": [
                {"capability": RUN_SPEC.identity.model_dump(),
                 "inputs": {"request": {"source": "run"}}},
            ],
        }
    )


def coding_skill() -> SkillManifest:
    return SkillManifest.model_validate(
        {
            "metadata": {"identity": SKILL.model_dump(), **_METADATA},
            "alias": "coding",
            "selector_hint": (
                "write and run a program on local files in a task folder 寫程式處理本機檔案; "
                "change code in a repository until pytest passes"
            ),
            "instructions": (
                "Use only when the person asks you to process local files or to write and run a "
                "program in a folder they name, or to change code in a configured repository. "
                "Never use it to answer a question, to look something up in Knowledge, or for "
                "work an installed Workflow already does. `run`: first run a short script that "
                "prints what the inputs really are (file names, headers, sample rows, page "
                "markup), then write a complete Python script for the task and run it in the "
                "named workspace. Before answering, run a check that reopens every output file "
                "and confirms each requirement the person stated (file and column names, value "
                "types such as text IDs and numeric values, placeholders for missing data, row "
                "counts); keep the source's column names unless told otherwise. Check from the "
                "saved outputs: a limit the person set on requests to a service counts for the "
                "whole conversation, so do not request it again to verify. Fix and run again "
                "until every requirement holds, then say what was checked. Outputs go to the "
                "workspace's output folder and input files are never changed. A system the "
                "person signs in to or operates (an enterprise web system, a desktop "
                "application) is used through browser__operate or desktop__operate, never "
                "fetched or read by a script; a script works on what those tools saved. "
                "A Workflow for "
                "this platform, or a run on the platform runtime, is not this tool's job: draft "
                "and run it with the authoring tools; a workflow file a script writes is not a "
                "platform Workflow. `change`: "
                "change one file in a configured repository against existing pytest tests; "
                "never committed."
            ),
            "commands": [
                {"name": "change", "kind": "workflow", "target": WORKFLOW.model_dump()},
                {"name": "run", "kind": "workflow", "target": RUN_WORKFLOW.model_dump()},
            ],
            "default_command": "change",
        }
    )
