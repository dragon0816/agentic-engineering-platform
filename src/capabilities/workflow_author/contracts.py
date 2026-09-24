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

from pydantic import Field, model_validator

from common.assets import WorkflowManifest
from common.base import Contract, Slug, Symbol, Text

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
    # Bounded, because rule 15 says a loop is bounded and surfaces a
    # structured failure rather than spinning. Each attempt is one model call
    # and the failed one's problems are handed back for the next.
    max_attempts: int = Field(default=3, ge=1, le=5, strict=True)


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

    @model_validator(mode="after")
    def a_draft_or_a_reason(self) -> Self:
        if (self.manifest is None) == (self.refusal is None):
            raise ValueError("a draft carries a manifest or the reason there is none")
        if self.manifest is not None and self.manifest.metadata.lifecycle != "draft":
            raise ValueError("a drafted workflow is a draft, whatever it says of itself")
        return self
