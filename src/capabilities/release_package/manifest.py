"""Installed read-only Workflow 13 preview and its explicit Skill command."""

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
