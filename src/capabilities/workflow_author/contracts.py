"""What drafting a Workflow from an SOP takes and produces.

The lifecycle this serves is the architecture's own
(`docs/ARCHITECTURE.md`, "Capability learning is not unrestricted
self-modification"):

    experience -> candidate -> **draft** -> validation/evaluation
               -> human review -> published

This stops at `draft` and cannot go further. What comes back is a manifest
somebody reads, not a capability anything may run: nothing here installs,
publishes or executes, and the drafted manifest's lifecycle is `draft` or it
is refused.

The output carries a `WorkflowManifest`, which is a platform contract, and no
model response, no prompt and no provider name. What produced the draft is
recorded as attempts and problems in words, so a reader can see what the
model got wrong without the platform's contracts learning anything about
models.
"""

from __future__ import annotations

from typing import Literal, Self

from pydantic import Field, JsonValue, StrictBool, model_validator

from common.assets import AssetIdentity, WorkflowManifest, reject_embedded_secrets
from common.base import Contract, Sha256, Slug, Symbol, Text
from common.execution import TraceIdentifiers

#: Why a draft did not happen, or did not survive being checked.
DraftRefusalCode = Literal[
    # This host has no model, so there is nothing to draft with.
    "model_not_configured",
    # The gateway did not answer, or answered with a failure.
    "model_unavailable",
    # Every attempt produced something that would not run here, and the
    # problems of the last one are in `attempts`.
    "draft_unusable",
    # The SOP said nothing this host could act on.
    "nothing_to_draft",
]


class DraftAttempt(Contract):
    """One try, and what was wrong with it.

    Kept because a draft that failed four times for the same reason is
    telling somebody something: usually that the step it keeps reaching for
    is not installed on this machine.
    """

    attempt: int = Field(ge=1, strict=True)
    problems: tuple[Text, ...] = ()
    # Whether this attempt produced a manifest that parsed and checked out.
    accepted: bool = False


class DraftWorkflowRequest(Contract):
    """The SOP, and where the drafted Workflow would live.

    `sop` is the procedure in whatever words its author wrote. Nothing is
    parsed out of it here: turning a procedure into steps is the judgement
    this capability exists to apply, and a platform that pre-chewed it would
    be deciding the answer.
    """

    sop: Text = Field(min_length=1)
    namespace: Slug
    name: Symbol | None = None
    # The user's executable acceptance expectation. These are exact identities,
    # not prose inferred a second time by the model. A plausible draft that
    # silently omits one is unusable.
    required_capabilities: tuple[AssetIdentity, ...] = ()
    # Bounded, because rule 15 says a loop is bounded and surfaces a
    # structured failure rather than spinning. Each attempt is one model call
    # and the failed one's problems are handed back for the next.
    max_attempts: int = Field(default=3, ge=1, le=5, strict=True)

    @model_validator(mode="after")
    def required_capability_identities_are_unique(self) -> Self:
        keys = [identity.key for identity in self.required_capabilities]
        if len(keys) != len(set(keys)):
            raise ValueError("required capabilities must have unique scoped identities")
        return self


class WorkflowDraft(Contract):
    """A Workflow somebody may read, and nothing may run yet.

    `manifest` absent with no refusal is impossible: either a draft survived
    checking or something is named as the reason it did not.
    """

    manifest: WorkflowManifest | None = None
    refusal: DraftRefusalCode | None = None
    attempts: tuple[DraftAttempt, ...] = ()
    # What was offered to the draft: naming it is what makes "it keeps asking
    # for a capability this machine does not have" readable rather than a
    # mystery.
    available: tuple[Symbol, ...] = ()
    preview: str = ""
    # Echoed so an ingress can prove the SOP and acceptance expectations that
    # reached the drafter are the ones the user supplied.
    request: DraftWorkflowRequest | None = None

    @model_validator(mode="after")
    def a_draft_or_a_reason(self) -> Self:
        if (self.manifest is None) == (self.refusal is None):
            raise ValueError("a draft carries a manifest or the reason there is none")
        if self.manifest is not None and self.manifest.metadata.lifecycle != "draft":
            raise ValueError("a drafted workflow is a draft, whatever it says of itself")
        return self


class WorkflowFixture(Contract):
    """Representative run input and the externally expected final output."""

    arguments: dict[Symbol, JsonValue]
    expected_output: JsonValue

    @model_validator(mode="after")
    def contains_no_credentials(self) -> Self:
        reject_embedded_secrets(self.model_dump(mode="json"))
        return self


class WorkflowAcceptanceRequest(Contract):
    """The three inputs the product test keeps separate."""

    draft: DraftWorkflowRequest
    fixture: WorkflowFixture


class WorkflowValidationEvidence(Contract):
    """External evidence; the model cannot set or grade this result."""

    trace: TraceIdentifiers
    manifest_sha256: Sha256
    status: Literal["passed", "failed"]
    code: Symbol | None = None
    run_id: Symbol | None = None
    completed_steps: int = Field(default=0, ge=0, strict=True)
    dispatched: tuple[AssetIdentity, ...] = ()
    expected_output: JsonValue
    observed_output: JsonValue = None
    deterministic: StrictBool = True

    @model_validator(mode="after")
    def result_is_consistent(self) -> Self:
        if (self.status == "passed") == (self.code is not None):
            raise ValueError("a failed validation names its code; a pass has none")
        if self.status == "passed" and self.run_id is None:
            raise ValueError("a passed validation names the run that proved it")
        if self.status == "passed" and self.expected_output != self.observed_output:
            raise ValueError("a passed validation has matching expected and observed output")
        if self.status == "passed" and not self.deterministic:
            raise ValueError("a passed validation is deterministic")
        reject_embedded_secrets(self.model_dump(mode="json"))
        return self


class WorkflowAcceptanceOutcome(Contract):
    """What the Personal Agent returns for one SOP acceptance request."""

    trace: TraceIdentifiers
    draft: WorkflowDraft | None = None
    validation: WorkflowValidationEvidence | None = None
    refusal: Symbol | None = None

    @model_validator(mode="after")
    def one_outcome(self) -> Self:
        if self.refusal is not None and self.validation is not None:
            raise ValueError("a refused request has no validation")
        if self.draft is None and self.refusal is None:
            raise ValueError("an outcome carries a draft or a refusal")
        if self.validation is not None and (self.draft is None or self.draft.manifest is None):
            raise ValueError("only a manifest can have validation evidence")
        if self.validation is not None and self.validation.trace != self.trace:
            raise ValueError("validation evidence belongs to the outcome trace")
        return self
