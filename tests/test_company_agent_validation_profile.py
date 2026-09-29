"""The shipped Company Agent profile is self-contained, governed, and inert."""

import json
from pathlib import Path

from pypdf import PdfReader

from common.assets import WorkflowManifest, WorkflowStep
from knowledge.evolution import (
    KnowledgeCatalog,
    KnowledgeManifest,
    decision_digest,
    knowledge_digest,
    raw_digest,
)
from knowledge.vault import Vault
from validation.contracts import CompanyAgentValidationProfile

ROOT = (
    Path(__file__).resolve().parents[1]
    / "deploy/windows-preview/validation/company-agent-integration-v1"
)


def loaded() -> CompanyAgentValidationProfile:
    return CompanyAgentValidationProfile.model_validate_json(
        (ROOT / "profile.json").read_text(encoding="utf-8")
    )


def test_profile_files_are_present_and_sop_pdf_is_readable() -> None:
    profile = loaded()
    pdf = ROOT / profile.sop.pdf_path
    text = "\n".join(page.extract_text() or "" for page in PdfReader(pdf).pages)

    assert "controlled personal proof fixture reader" in text
    assert (ROOT / profile.model.responses_path).is_file()
    assert (ROOT / profile.personal_proof_fixture_path).read_text(encoding="utf-8").strip()


def test_profile_knowledge_manifest_matches_immutable_vault() -> None:
    profile = loaded()
    vault = Vault(ROOT / profile.knowledge.vault_path)
    template = json.loads(
        (ROOT / profile.knowledge.manifest_template_path).read_text(encoding="utf-8")
    )
    assert template["vault_ref"] == profile.knowledge.vault_ref_placeholder
    template["vault_ref"] = str(vault.root.resolve())
    manifest = KnowledgeManifest.model_validate(template)

    assert manifest.metadata.identity == profile.knowledge.asset
    assert manifest.metadata.lifecycle == "published"
    assert manifest.raw_sha256 == raw_digest(vault)
    assert manifest.decisions_sha256 == decision_digest(vault)
    assert manifest.content_sha256 == knowledge_digest(vault)
    catalog = KnowledgeCatalog()
    catalog.register(manifest, vault)
    assert catalog.get(profile.knowledge.asset) is not None


def test_loopback_responses_produce_a_valid_draft_and_grounded_answer() -> None:
    profile = loaded()
    responses = json.loads((ROOT / profile.model.responses_path).read_text(encoding="utf-8"))
    workflow = WorkflowManifest.model_validate(responses["workflow"]["structured_output"])

    assert responses["workflow"]["output_contract"] == "platform.workflow-manifest.v1"
    assert workflow.metadata.lifecycle == "draft"
    assert isinstance(workflow.steps[0], WorkflowStep)
    assert workflow.steps[0].capability == profile.sop.required_capabilities[0]
    assert responses["knowledge"]["question"] == profile.knowledge.question
    assert responses["knowledge"]["text"].endswith("[1].")
