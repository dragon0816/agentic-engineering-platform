"""Installed asset manifests for the Company Bridge agent-integration proof."""

from agent.skills import SkillManifest
from capabilities.files import READ_FILE_SPEC
from capabilities.knowledge_query.handlers import KNOWLEDGE_QUERY_SPEC
from capabilities.workflow_author.handlers import DRAFT_SPEC
from common.assets import AssetIdentity, WorkflowManifest

_META = {
    "owner": {"type": "team", "id": "engineering"},
    "visibility": "team",
    "lifecycle": "published",
}

PERSONAL_PROOF = AssetIdentity(namespace="company-agent", name="personal-proof", version="1.0.0")


def workflow_author_skill() -> SkillManifest:
    return SkillManifest.model_validate(
        {
            "metadata": {
                "identity": {
                    "namespace": "company-agent",
                    "name": "workflow-author",
                    "version": "1.0.0",
                },
                **_META,
            },
            "alias": "workflow",
            "instructions": (
                "Draft a candidate workflow from one local SOP or SOP PDF. "
                "Drafting never installs, publishes, or executes it."
            ),
            "commands": [
                {"name": "draft", "kind": "capability", "target": DRAFT_SPEC.identity.model_dump()}
            ],
            "default_command": "draft",
        }
    )


def knowledge_skill() -> SkillManifest:
    return SkillManifest.model_validate(
        {
            "metadata": {
                "identity": {
                    "namespace": "company-agent",
                    "name": "knowledge-query",
                    "version": "1.0.0",
                },
                **_META,
            },
            "alias": "knowledge",
            "instructions": (
                "Ask one exact installed published Knowledge version. "
                "Answers require Raw citations."
            ),
            "commands": [
                {
                    "name": "ask",
                    "kind": "capability",
                    "target": KNOWLEDGE_QUERY_SPEC.identity.model_dump(),
                }
            ],
            "default_command": "ask",
        }
    )


def personal_proof_workflow() -> WorkflowManifest:
    return WorkflowManifest.model_validate(
        {
            "metadata": {"identity": PERSONAL_PROOF.model_dump(), **_META},
            "kind": "workflow",
            "description": (
                "Read a controlled local proof fixture; no external or write side effect."
            ),
            "execution": {"mode": "local"},
            "dependencies": {
                "central_required": False,
                "local_capabilities": [READ_FILE_SPEC.name],
            },
            "input_contract": "company-agent.personal-proof.input.v1",
            "output_contract": "filesystem.read-file.output.v1",
            "steps": [
                {
                    "capability": READ_FILE_SPEC.identity.model_dump(),
                    "inputs": {"path": {"source": "run", "path": ["args"]}},
                }
            ],
        }
    )


def personal_proof_skill() -> SkillManifest:
    return SkillManifest.model_validate(
        {
            "metadata": {
                "identity": {
                    "namespace": "company-agent",
                    "name": "personal-proof",
                    "version": "1.0.0",
                },
                **_META,
            },
            "alias": "personal",
            "instructions": (
                "Run the installed, side-effect-free local proof workflow "
                "against a controlled fixture."
            ),
            "commands": [
                {"name": "proof", "kind": "workflow", "target": PERSONAL_PROOF.model_dump()}
            ],
            "default_command": "proof",
        }
    )
