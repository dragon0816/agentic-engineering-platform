"""Outbound data trust is decided before any backend receives a payload."""

import pytest
from pydantic import ValidationError

from agent.backend_contracts import BackendProfile
from agent.data_policy import (
    BackendDataApproval,
    ContextMaterial,
    DataPolicy,
    OutboundContext,
)


def material(
    material_id: str, classification: str = "UNCLASSIFIED", text: str = "private content"
) -> ContextMaterial:
    return ContextMaterial.model_validate(
        {
            "material_id": material_id,
            "origin": "history",
            "classification": classification,
            "classified_by": "engineer" if classification != "UNCLASSIFIED" else None,
            "text": text,
        }
    )


def profile(kind: str = "agent", backend_id: str = "codex") -> BackendProfile:
    return BackendProfile.model_validate(
        {
            "backend_id": backend_id,
            "kind": kind,
            "harness": "native" if kind == "agent" else "aep",
        }
    )


def approval(*classes: str) -> BackendDataApproval:
    return BackendDataApproval.model_validate(
        {
            "backend_id": "gateway",
            "approved_classes": classes,
            "approval_ref": "policy/internal-gateway-1",
            "internal_gateway": True,
        }
    )


def test_public_native_requires_every_material_to_be_explicitly_labeled() -> None:
    policy = DataPolicy(())
    native = profile()
    public = OutboundContext(materials=(material("user-1", "PUBLIC"),))
    assert policy.decide(native, public).allowed
    mixed = OutboundContext(
        materials=(material("user-1", "PUBLIC"), material("skill-1", "INTERNAL"))
    )
    assert policy.decide(native, mixed).code == "native_requires_public"
    assert policy.decide(native, OutboundContext(materials=(material("old-1"),))).code == (
        "native_requires_public"
    )
    with pytest.raises(ValidationError, match="PUBLIC requires an explicit classifier"):
        ContextMaterial(
            material_id="forged", origin="user", classification="PUBLIC", text="hello"
        )
    with pytest.raises(ValidationError, match="unique material IDs"):
        OutboundContext(materials=(material("same"), material("same")))


def test_internal_gateway_needs_explicit_approval_for_every_class() -> None:
    gateway = profile("model", "gateway")
    context = OutboundContext(
        materials=(material("one"), material("two", "CONFIDENTIAL"))
    )
    assert DataPolicy(()).decide(gateway, context).code == "gateway_not_approved"
    assert DataPolicy((approval("UNCLASSIFIED"),)).decide(gateway, context).code == (
        "class_not_approved"
    )
    approved = DataPolicy((approval("UNCLASSIFIED", "CONFIDENTIAL"),)).decide(
        gateway, context
    )
    assert approved.allowed and approved.approval_ref == "policy/internal-gateway-1"
    assert approved.effective_classification == "UNCLASSIFIED"
    with pytest.raises(ValidationError, match="internal Gateway approval"):
        BackendDataApproval(
            backend_id="gateway",
            approved_classes=("UNCLASSIFIED",),
            approval_ref="policy/fake",
            internal_gateway=False,
        )


def test_missing_context_is_denied_without_content_in_the_decision() -> None:
    decision = DataPolicy(()).decide(profile(), None)
    assert not decision.allowed and decision.code == "context_missing"
    assert decision.material_ids == ()
