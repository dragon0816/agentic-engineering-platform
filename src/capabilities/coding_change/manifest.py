"""Coding on the Bridge: the capability, the Workflow people run, the Skill.

The Workflow is the person-facing shape: its parameters give the Agent a tool
schema, Telegram a question flow and Agent Web a form. The capability does
the work under the host's `coding` binding; nothing here names a path.
"""

from agent.skills import SkillManifest
from capabilities.contracts import CapabilitySpec
from common.assets import AssetIdentity, WorkflowManifest

WORKFLOW = AssetIdentity(namespace="engineering", name="coding-change", version="1.0.0")
SKILL = AssetIdentity(namespace="engineering", name="coding", version="1.0.0")
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


def coding_skill() -> SkillManifest:
    return SkillManifest.model_validate(
        {
            "metadata": {"identity": SKILL.model_dump(), **_METADATA},
            "alias": "coding",
            "selector_hint": (
                "change code 改程式 fix implement function in a repository until pytest passes"
            ),
            "instructions": (
                "Change code in a configured repository: one file, judged by existing pytest "
                "tests the person names. Ask for the repository, what should change, the file "
                "and the tests if they are not clear. Report the diff and the worktree; the "
                "change is never committed."
            ),
            "commands": [{"name": "change", "kind": "workflow", "target": WORKFLOW.model_dump()}],
            "default_command": "change",
        }
    )
