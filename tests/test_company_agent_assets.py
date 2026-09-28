"""The bounded Company Bridge proof assets are explicit, published routes."""

from capabilities.company_agent.manifest import (
    PERSONAL_PROOF,
    knowledge_skill,
    personal_proof_skill,
    personal_proof_workflow,
    workflow_author_skill,
)
from capabilities.files import READ_FILE_SPEC
from capabilities.knowledge_query.handlers import KNOWLEDGE_QUERY_SPEC
from capabilities.workflow_author.handlers import DRAFT_SPEC
from host_runtime.assets import shipped


def test_company_agent_assets_expose_exact_deterministic_routes() -> None:
    workflow = workflow_author_skill()
    knowledge = knowledge_skill()
    personal = personal_proof_skill()
    assert workflow.commands[0].target == DRAFT_SPEC.identity
    assert knowledge.commands[0].target == KNOWLEDGE_QUERY_SPEC.identity
    assert personal.commands[0].target == PERSONAL_PROOF
    proof = personal_proof_workflow()
    assert proof.steps[0].capability == READ_FILE_SPEC.identity
    assert proof.dependencies.central_required is False


def test_company_agent_assets_ship_with_the_host_bundle() -> None:
    identities = {item.metadata.identity for item in shipped()}
    assert workflow_author_skill().metadata.identity in identities
    assert knowledge_skill().metadata.identity in identities
    assert personal_proof_skill().metadata.identity in identities
    assert PERSONAL_PROOF in identities
