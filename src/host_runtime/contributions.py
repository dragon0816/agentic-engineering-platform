"""Local, governed drafts captured from Personal Agent conversations."""

from datetime import datetime
from typing import Literal, Self

from pydantic import Field, model_validator

from common.assets import (
    AssetIdentity,
    BusinessApproval,
    Owner,
    RegistryContract,
    TechnicalPolicy,
)
from common.base import Slug, Symbol, Text
from common.execution import TraceIdentifiers


class ConversationExcerpt(RegistryContract):
    """An immutable excerpt copied into a draft as reproducible evidence."""

    message_id: Symbol
    role: Literal["user", "assistant"]
    text: Text
    trace: TraceIdentifiers | None = None

    @model_validator(mode="after")
    def assistant_trace_only(self) -> Self:
        if self.role == "user" and self.trace is not None:
            raise ValueError("user conversation evidence carries no result trace")
        return self


class ContributionDraftCreateRequest(RegistryContract):
    """What a browser may ask to capture; governance fields are deliberately absent."""

    session_id: Symbol
    request_kind: Literal["improvement", "new_capability"]
    target: AssetIdentity | None = None
    candidate_kind: Literal["skill", "workflow"] | None = None
    proposed_name: Slug | None = None
    summary: Text
    expected_behavior: Text
    actual_behavior: Text
    acceptance_criteria: tuple[Text, ...] = Field(min_length=1, max_length=10)

    @model_validator(mode="after")
    def one_kind_of_request(self) -> Self:
        if self.request_kind == "improvement":
            if (
                self.target is None
                or self.candidate_kind is not None
                or self.proposed_name is not None
            ):
                raise ValueError("an improvement names one exact installed target")
        elif self.target is not None or self.candidate_kind is None or self.proposed_name is None:
            raise ValueError("a new capability names a Skill or Workflow proposal")
        return self


class ContributionDraft(RegistryContract):
    """An inert local request. It is not an asset manifest or publication decision."""

    draft_id: Symbol
    request_kind: Literal["improvement", "new_capability"]
    actor: Symbol
    namespace: Slug
    owner: Owner
    asset_kind: Literal["skill", "workflow", "knowledge"]
    target: AssetIdentity | None = None
    proposed_name: Slug | None = None
    summary: Text
    expected_behavior: Text
    actual_behavior: Text
    acceptance_criteria: tuple[Text, ...] = Field(min_length=1, max_length=10)
    source_session_id: Symbol
    evidence: tuple[ConversationExcerpt, ...] = Field(min_length=1, max_length=20)
    created_at: datetime
    lifecycle: Literal["draft"] = "draft"
    business_approval: BusinessApproval = BusinessApproval()
    technical_policy: TechnicalPolicy = TechnicalPolicy()
    publishable: Literal[False] = False

    @model_validator(mode="after")
    def governed_draft(self) -> Self:
        if self.business_approval.status != "pending":
            raise ValueError("a captured draft has not received business approval")
        if self.technical_policy.status != "pending":
            raise ValueError("a captured draft has not received technical policy approval")
        if self.request_kind == "improvement":
            if self.target is None or self.proposed_name is not None:
                raise ValueError("an improvement draft retains one exact target")
            if self.target.namespace != self.namespace:
                raise ValueError("an improvement draft retains the target namespace")
        elif (
            self.target is not None
            or self.proposed_name is None
            or self.asset_kind not in {"skill", "workflow"}
        ):
            raise ValueError("a new capability draft is an unpublished Skill or Workflow proposal")
        return self
