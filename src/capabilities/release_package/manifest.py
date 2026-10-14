"""Installed read-only Workflow 13 preview and its explicit Skill command."""

from typing import Any

from agent.skills import SkillManifest
from capabilities.contracts import CapabilitySpec
from common.assets import AssetIdentity, WorkflowManifest

PREVIEW = AssetIdentity(namespace="engineering", name="release-package-preview", version="1.0.0")
ISOLATED_APPLY = AssetIdentity(
    namespace="engineering", name="release-package-apply-isolated", version="1.0.0"
)
SKILL = AssetIdentity(namespace="engineering", name="release-package-guide", version="1.0.0")

PREVIEW_SPEC = CapabilitySpec.model_validate(
    {
        "identity": {"namespace": "release-package", "name": "preview", "version": "1.0.0"},
        "name": "release_package.preview",
        "description": "Read the checked-out release branch and preview its package files",
        "input_contract": "release-package.preview.input.v1",
        "output_contract": "release-package.preview.output.v1",
        "side_effect": "read",
        "policy": {
            "required_permissions": ["release-package.preview"],
            "policy_refs": ["release-package-preview-policy"],
        },
    }
)

ISOLATED_APPLY_SPEC = CapabilitySpec.model_validate(
    {
        "identity": {"namespace": "release-package", "name": "apply-isolated", "version": "1.0.0"},
        "name": "release_package.apply_isolated",
        "description": "Prepare source Workflow 13 files in an explicitly isolated Git checkout",
        "input_contract": "release-package.apply-isolated.input.v1",
        "output_contract": "release-package.apply-isolated.output.v1",
        "side_effect": "write",
        "policy": {
            "required_permissions": ["release-package.apply-isolated"],
            "policy_refs": ["release-package-isolated-write-policy"],
            "approval_required": True,
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
            "run_alias": 13,
            "description": (
                "Preview Workflow 13 from an existing checked-out release branch. "
                "No files are written, and no Git, commit or push command runs."
            ),
            "execution": {"mode": "local"},
            "dependencies": {
                "central_required": False,
                "local_capabilities": [PREVIEW_SPEC.name],
            },
            "parameters": [
                {"name": "checkout_path", "label": "Release checkout", "kind": "text",
                 "scope": "static", "required": True,
                 "description": "Existing local release Git checkout."},
                {"name": "inbox_path", "label": "Input inbox", "kind": "text", "scope": "static",
                 "required": True, "description": "Folder containing selected local files."},
                {"name": "companyName", "label": "Company", "kind": "text", "required": True},
                {"name": "chipsetId", "label": "Chipset", "kind": "text", "required": True},
                {"name": "info", "label": "Branch tag", "kind": "text"},
                {"name": "cmpKtOption", "label": "CMP KT option", "kind": "select",
                 "required": True, "options": ["KT160", "KT161"]},
                {"name": "chipsetVersion", "label": "Published chipset version", "kind": "text",
                 "required": True,
                 "description": "Explicit version until published lookup is integrated."},
                {"name": "generalTestcaseVersion", "label": "General testcase version",
                 "kind": "text", "required": True},
                {"name": "releaseVersion", "label": "Release version override", "kind": "text",
                 "description": "Leave empty to increment the checked-out branch's VERSION."},
                {"name": "notes", "label": "Release notes", "kind": "text"},
                {"name": "suffix", "label": "Installer suffix", "kind": "text"},
            ],
            "input_contract": "release-package.preview.input.v1",
            "output_contract": "release-package.preview.output.v1",
            "steps": [
                {
                    "capability": PREVIEW_SPEC.identity.model_dump(),
                    "inputs": {
                        "request": {"source": "run"},
                        "checkout_path": {"source": "run", "path": ["checkout_path"]},
                        "inbox_path": {"source": "run", "path": ["inbox_path"]},
                    },
                }
            ],
        }
    )


def preview_skill() -> SkillManifest:
    return SkillManifest.model_validate(
        {
            "metadata": {"identity": SKILL.model_dump(), **_METADATA},
            "alias": "release",
            "instructions": (
                "Preview Workflow 13's branch, pinned dependencies and release.yaml. "
                "The checked-out branch and input inbox are configured by this Host. "
                "This command never prepares, commits or pushes a release."
            ),
            "commands": [{"name": "preview", "kind": "workflow", "target": PREVIEW.model_dump()}],
            "default_command": "preview",
        }
    )


def isolated_apply_workflow() -> WorkflowManifest:
    """Exact identity only; isolation and write approval are checked at the Bridge."""
    parameters = [item.model_dump(mode="json") for item in preview_workflow().parameters]
    parameters.append(
        {
            "name": "allowed_root",
            "label": "Explicit isolated root",
            "kind": "text",
            "scope": "static",
            "required": True,
            "description": "Must carry the AEP isolated-release marker and a no-remote checkout.",
        }
    )
    return WorkflowManifest.model_validate(
        {
            "metadata": {"identity": ISOLATED_APPLY.model_dump(), **_METADATA},
            "kind": "workflow",
            "description": (
                "Prepare Workflow 13 files in an explicitly marked isolated checkout. "
                "No Git command, commit, network call or push is performed."
            ),
            "execution": {"mode": "local"},
            "dependencies": {
                "central_required": False,
                "local_capabilities": [ISOLATED_APPLY_SPEC.name],
            },
            "parameters": parameters,
            "input_contract": "release-package.apply-isolated.input.v1",
            "output_contract": "release-package.apply-isolated.output.v1",
            "steps": [
                {
                    "capability": ISOLATED_APPLY_SPEC.identity.model_dump(),
                    "inputs": {
                        "request": {"source": "run"},
                        "checkout_path": {"source": "run", "path": ["checkout_path"]},
                        "inbox_path": {"source": "run", "path": ["inbox_path"]},
                        "allowed_root": {"source": "run", "path": ["allowed_root"]},
                    },
                }
            ],
        }
    )


# -- the release run up to the commit (owner 2026-10-08) -----------------------

PREPARE = AssetIdentity(namespace="engineering", name="release-package-prepare", version="1.0.0")
COMMIT = AssetIdentity(namespace="engineering", name="release-package-commit", version="1.0.0")
PUSH = AssetIdentity(namespace="engineering", name="release-package-push", version="1.0.0")

PREPARE_SPEC = CapabilitySpec.model_validate(
    {
        "identity": {"namespace": "release-package", "name": "prepare", "version": "1.0.0"},
        "name": "release_package.prepare",
        "description": "Resolve the chipset version, check out or create the release branch and "
                       "write the package files; never commits",
        "input_contract": "release-package.prepare.input.v1",
        "output_contract": "release-package.prepare.output.v1",
        "side_effect": "write",
        "policy": {
            "required_permissions": ["release-package.prepare"],
            "policy_refs": ["release-package-isolated-write-policy"],
            "approval_required": True,
        },
    }
)

COMMIT_SPEC = CapabilitySpec.model_validate(
    {
        "identity": {"namespace": "release-package", "name": "commit", "version": "1.0.0"},
        "name": "release_package.commit",
        "description": "Commit exactly the release that was prepared and reviewed; never pushes",
        "input_contract": "release-package.commit.input.v1",
        "output_contract": "release-package.commit.output.v1",
        "side_effect": "write",
        "policy": {
            "required_permissions": ["release-package.commit"],
            "policy_refs": ["release-package-isolated-write-policy"],
            "approval_required": True,
        },
    }
)

# Workflow 13 push (owner 2026-10-14): its own approved run, after the commit.
PUSH_SPEC = CapabilitySpec.model_validate(
    {
        "identity": {"namespace": "release-package", "name": "push", "version": "1.0.0"},
        "name": "release_package.push",
        "description": "Push exactly the release commit that was made and reviewed; never "
                       "forced",
        "input_contract": "release-package.push.input.v1",
        "output_contract": "release-package.push.output.v1",
        "side_effect": "external_side_effect",
        "policy": {
            "risk": "high",
            "required_permissions": ["release-package.push"],
            "policy_refs": ["release-package-push-policy"],
            "approval_required": True,
        },
    }
)

_RUN_SETTINGS: list[dict[str, Any]] = [
    {"name": "release_repo_url", "label": "Release repository", "kind": "text",
     "scope": "static", "required": True,
     "description": "A local repository inside the isolated root, or the GitLab clone URL "
                    "(https or ssh, no token in it) when remote_release is on."},
    {"name": "remote_release", "label": "Use the real release repository (GitLab)",
     "kind": "boolean", "scope": "static", "default": False,
     "description": "Off: only a local repository inside the isolated root is accepted."},
    {"name": "template_branch", "label": "Template branch", "kind": "text", "scope": "static",
     "default": "template"},
    {"name": "work_root", "label": "Working copy folder", "kind": "text", "scope": "static",
     "required": True},
    {"name": "inbox_path", "label": "Input inbox", "kind": "text", "scope": "static",
     "required": True},
    {"name": "allowed_root", "label": "Isolated root", "kind": "text", "scope": "static",
     "required": True, "description": "Must carry the AEP isolated-release marker; the "
                                      "working copy and inbox must be inside it."},
    {"name": "artifactory_base_url", "label": "Published package index", "kind": "text",
     "scope": "static", "description": "PEP 503 simple-index root, for the chipset version."},
    {"name": "readiness_base_url", "label": "Readiness table", "kind": "text", "scope": "static",
     "description": "Fallback chipset version lookup (Workflow 12's table)."},
]
_SETTING_INPUTS = {item["name"]: {"source": "run", "path": [item["name"]]}
                   for item in _RUN_SETTINGS}


def prepare_workflow() -> WorkflowManifest:
    return WorkflowManifest.model_validate(
        {
            "metadata": {"identity": PREPARE.model_dump(), **_METADATA},
            "kind": "workflow",
            "description": (
                "Workflow 13, step 1: resolve the chipset version, check out or create the "
                "customer release branch, and write requirements.txt, the chosen files and "
                "release.yaml. Shows what a commit would contain; never commits or pushes."
            ),
            "execution": {"mode": "local"},
            "dependencies": {"central_required": False,
                             "local_capabilities": [PREPARE_SPEC.name]},
            "parameters": [
                *_RUN_SETTINGS,
                {"name": "companyName", "label": "Which company is this release for?",
                 "kind": "text", "required": True, "examples": ["Foxconn"], "order": 10,
                 "group": "identity"},
                {"name": "chipsetId", "label": "Which chipset or licence id?", "kind": "text",
                 "required": True, "examples": ["kt326"], "order": 20, "group": "identity"},
                {"name": "chipsetVersion", "label": "Which version of it?", "kind": "text",
                 "description": "Empty: the newest published release.", "order": 25},
                {"name": "info", "label": "Any extra tag for the branch name?", "kind": "text",
                 "examples": ["demo"], "order": 30, "group": "identity"},
                {"name": "cmpKtOption", "label": "Which CMP_KT_OPTION?", "kind": "select",
                 "required": True, "options": ["KT160", "KT161"], "order": 40},
                {"name": "generalTestcaseVersion", "label": "Which general testcase version?",
                 "kind": "text", "required": True, "examples": ["v3.0.17"], "order": 50},
                {"name": "notes", "label": "What changed in this release?", "kind": "text",
                 "order": 60},
                {"name": "testPlans", "label": "Test plan files (.json) in the inbox",
                 "kind": "text_list", "order": 70},
                {"name": "configurations", "label": "Configuration files (.yaml) in the inbox",
                 "kind": "text_list", "order": 80},
                {"name": "overlays", "label": "Overlay files in the inbox", "kind": "text_list",
                 "order": 90},
                {"name": "suffix", "label": "SUFFIX in release.yaml (KT160 only)",
                 "kind": "text", "order": 100},
                {"name": "releaseVersion", "label": "VERSION override", "kind": "text",
                 "description": "Empty: one more than the branch already has.", "order": 110},
                {"name": "dryRun", "label": "Dry run (the commit step will refuse)",
                 "kind": "boolean", "default": False, "order": 120},
            ],
            "input_contract": "release-package.prepare.input.v1",
            "output_contract": "release-package.prepare.output.v1",
            "steps": [{"capability": PREPARE_SPEC.identity.model_dump(),
                       "inputs": {"request": {"source": "run"}, **_SETTING_INPUTS}}],
        }
    )


def commit_workflow() -> WorkflowManifest:
    return WorkflowManifest.model_validate(
        {
            "metadata": {"identity": COMMIT.model_dump(), **_METADATA},
            "kind": "workflow",
            "description": (
                "Workflow 13, step 2: commit the release that was prepared and reviewed. "
                "Refuses if anything changed since; never pushes."
            ),
            "execution": {"mode": "local"},
            "dependencies": {"central_required": False,
                             "local_capabilities": [COMMIT_SPEC.name]},
            "parameters": [
                *_RUN_SETTINGS,
                {"name": "branch", "label": "Which prepared branch?", "kind": "text",
                 "required": True, "order": 10},
                {"name": "fingerprint", "label": "The fingerprint the prepare step showed",
                 "kind": "text", "required": True, "order": 20, "min_length": 12},
            ],
            "input_contract": "release-package.commit.input.v1",
            "output_contract": "release-package.commit.output.v1",
            "steps": [{"capability": COMMIT_SPEC.identity.model_dump(),
                       "inputs": {"branch": {"source": "run", "path": ["branch"]},
                                  "fingerprint": {"source": "run", "path": ["fingerprint"]},
                                  **_SETTING_INPUTS}}],
        }
    )


def push_workflow() -> WorkflowManifest:
    return WorkflowManifest.model_validate(
        {
            "metadata": {"identity": PUSH.model_dump(), **_METADATA},
            "kind": "workflow",
            "description": (
                "Workflow 13, step 3: push the release commit that was made and reviewed "
                "to the release repository (git push -u origin <branch>, never forced). "
                "Refuses if anything changed since the commit."
            ),
            "execution": {"mode": "local"},
            "dependencies": {"central_required": False,
                             "local_capabilities": [PUSH_SPEC.name]},
            "parameters": [
                *_RUN_SETTINGS,
                {"name": "branch", "label": "Which committed branch?", "kind": "text",
                 "required": True, "order": 10},
                {"name": "commit", "label": "The commit id the commit step showed",
                 "kind": "text", "required": True, "order": 20, "min_length": 7},
            ],
            "input_contract": "release-package.push.input.v1",
            "output_contract": "release-package.push.output.v1",
            "steps": [{"capability": PUSH_SPEC.identity.model_dump(),
                       "inputs": {"branch": {"source": "run", "path": ["branch"]},
                                  "commit": {"source": "run", "path": ["commit"]},
                                  **_SETTING_INPUTS}}],
        }
    )
