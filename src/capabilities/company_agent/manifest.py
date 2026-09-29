"""Installed asset manifests for the Company Bridge agent-integration proof."""

from agent.skills import SkillManifest
from capabilities.contracts import CapabilitySpec
from capabilities.knowledge_query.handlers import KNOWLEDGE_QUERY_SPEC
from capabilities.workflow_author.handlers import DRAFT_SPEC
from common.assets import AssetIdentity, WorkflowManifest

_META = {
    "owner": {"type": "team", "id": "engineering"},
    "visibility": "team",
    "lifecycle": "published",
}

PERSONAL_PROOF = AssetIdentity(namespace="company-agent", name="personal-proof", version="1.0.0")
PERSONAL_PROOF_FIXTURE_READ = AssetIdentity(
    namespace="company-agent", name="personal-proof-fixture-read", version="1.0.0"
)


def personal_proof_fixture_read_spec() -> CapabilitySpec:
    """The one read capability the deployment proof may receive a grant for.

    Its handler is wired only to the Hermes-owned fixture directory. This is
    deliberately a distinct asset from general `filesystem/read-file`, so a
    proof grant cannot be re-used to read the rest of the Bridge workspace.
    """
    return CapabilitySpec.model_validate(
        {
            "identity": PERSONAL_PROOF_FIXTURE_READ.model_dump(),
            "name": "company-agent.personal-proof.fixture-read",
            "description": "Read only the controlled personal-proof fixture",
            "input_contract": "filesystem.read-file.input.v1",
            "output_contract": "filesystem.read-file.output.v1",
            "side_effect": "read",
            "policy": {
                "required_permissions": ["filesystem.read"],
                "policy_refs": ["personal-proof-fixture-read-policy"],
            },
        }
    )


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
                "local_capabilities": [personal_proof_fixture_read_spec().name],
            },
            "input_contract": "company-agent.personal-proof.input.v1",
            "output_contract": "filesystem.read-file.output.v1",
            "steps": [
                {
                    "capability": personal_proof_fixture_read_spec().identity.model_dump(),
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
