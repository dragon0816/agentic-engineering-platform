"""Fail-closed classification and approval of text sent to a backend."""

from collections.abc import Iterable
from typing import Literal, Self

from pydantic import Field, StrictBool, model_validator

from agent.backend_contracts import BackendProfile
from common.base import Contract, Symbol, Text

DataClass = Literal["PUBLIC", "INTERNAL", "CONFIDENTIAL", "UNCLASSIFIED"]
MaterialOrigin = Literal[
    "user", "history", "persona", "skill", "knowledge", "tool", "attachment", "system"
]

# Unknown is never treated as PUBLIC, even when the known material is PUBLIC.
_PRECEDENCE: dict[DataClass, int] = {
    "PUBLIC": 0,
    "INTERNAL": 1,
    "CONFIDENTIAL": 2,
    "UNCLASSIFIED": 3,
}


class ContextMaterial(Contract):
    """One actual outbound text item plus its host-verified classification."""

    material_id: Symbol
    origin: MaterialOrigin
    classification: DataClass = "UNCLASSIFIED"
    classified_by: Symbol | None = None
    text: str = Field(min_length=1, repr=False)

    @model_validator(mode="after")
    def explicit_classification_has_provenance(self) -> Self:
        if self.classification == "PUBLIC" and self.classified_by is None:
            raise ValueError("PUBLIC requires an explicit classifier")
        if self.classification in {"INTERNAL", "CONFIDENTIAL"} and self.classified_by is None:
            raise ValueError("classified material requires an explicit classifier")
        if self.classification == "UNCLASSIFIED" and self.classified_by is not None:
            raise ValueError("unclassified material has no classifier")
        return self


class OutboundContext(Contract):
    """Complete list of text items to be serialized to one backend request."""

    materials: tuple[ContextMaterial, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_sources(self) -> Self:
        ids = [item.material_id for item in self.materials]
        if len(ids) != len(set(ids)):
            raise ValueError("unique material IDs are required")
        return self

    @property
    def effective_classification(self) -> DataClass:
        return max((item.classification for item in self.materials), key=_PRECEDENCE.__getitem__)


class BackendDataApproval(Contract):
    """Host-admin approval for one internal backend and explicit data classes."""

    backend_id: Symbol
    approved_classes: tuple[DataClass, ...] = Field(min_length=1)
    approval_ref: Text
    internal_gateway: StrictBool

    @model_validator(mode="after")
    def approved_internal_gateway_only(self) -> Self:
        if not self.internal_gateway:
            raise ValueError("internal Gateway approval requires an internal Gateway")
        if len(self.approved_classes) != len(set(self.approved_classes)):
            raise ValueError("approved classes must be unique")
        return self


class BackendDataDecision(Contract):
    """Audit metadata only; never contains outbound content."""

    backend_id: Symbol
    allowed: StrictBool
    code: Literal[
        "eligible",
        "context_missing",
        "native_requires_public",
        "gateway_not_approved",
        "class_not_approved",
    ]
    effective_classification: DataClass | None = None
    material_ids: tuple[Symbol, ...] = ()
    approval_ref: Text | None = None

    @model_validator(mode="after")
    def consistent_decision(self) -> Self:
        if self.allowed != (self.code == "eligible"):
            raise ValueError("only an eligible decision allows dispatch")
        return self


class DataPolicy:
    """Native backends get PUBLIC only; Gateway needs explicit host approval."""

    def __init__(self, approvals: Iterable[BackendDataApproval]) -> None:
        self._approvals: dict[str, BackendDataApproval] = {}
        for approval in approvals:
            if approval.backend_id in self._approvals:
                raise ValueError(f"duplicate Gateway approval: {approval.backend_id}")
            self._approvals[approval.backend_id] = approval

    def decide(
        self, backend: BackendProfile, context: OutboundContext | None
    ) -> BackendDataDecision:
        if context is None:
            return BackendDataDecision(
                backend_id=backend.backend_id, allowed=False, code="context_missing"
            )
        common = {
            "backend_id": backend.backend_id,
            "effective_classification": context.effective_classification,
            "material_ids": tuple(item.material_id for item in context.materials),
        }
        if backend.kind == "agent":
            allowed = all(item.classification == "PUBLIC" for item in context.materials)
            return BackendDataDecision(
                **common,
                allowed=allowed,
                code="eligible" if allowed else "native_requires_public",
            )
        approval = self._approvals.get(backend.backend_id)
        if approval is None:
            return BackendDataDecision(**common, allowed=False, code="gateway_not_approved")
        if any(item.classification not in approval.approved_classes for item in context.materials):
            return BackendDataDecision(
                **common,
                allowed=False,
                code="class_not_approved",
                approval_ref=approval.approval_ref,
            )
        return BackendDataDecision(
            **common, allowed=True, code="eligible", approval_ref=approval.approval_ref
        )
