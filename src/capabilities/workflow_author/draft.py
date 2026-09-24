"""Asking a model for a Workflow, and refusing to accept a bad one.

The loop is bounded and small (rule 15: *"Agent loops are bounded and must
surface a structured failure/needs-input result rather than spin
indefinitely"*). It is not a coding harness and does not want to be: no tool
is offered, nothing is read from disk, nothing is written, and each turn is
one request and one answer. What makes it work is not the loop but the check
between the turns -- a draft that would not run here comes back with the
reasons, in the words a person would use, and the next turn is given them.

Everything about the model stays on this side of the contract: the platform's
output is a `WorkflowManifest` and a list of problems, and never a response,
a prompt or a provider's name.
"""

from __future__ import annotations

import json
from collections.abc import Callable

from capabilities.runtime import InstalledCapabilities
from capabilities.workflow_author import review
from capabilities.workflow_author.contracts import (
    DraftAttempt,
    DraftWorkflowRequest,
    WorkflowDraft,
)
from common.execution import TraceIdentifiers
from models.contracts import ModelClient, ModelMessage, ModelRequest, ModelRequirements

#: What the drafter is told it is doing. Every constraint here is one the
#: check on the other side actually enforces, so nothing in it is a wish.
INSTRUCTIONS = """\
You turn a written procedure into one Workflow this machine can run.

A Workflow is a JSON document with `metadata`, `description`, `execution`, \
`dependencies`, `input_contract`, `output_contract` and `steps`.

Rules, each of which is checked and will be handed back to you if broken:

- Every step names a capability from the list you are given, by its exact \
namespace, name and version. You may not invent one. If the procedure needs \
something that is not in the list, leave that part out and say so in the \
description, rather than naming a capability that does not exist.
- Every input you give a step must be one of that capability's own inputs, \
and every required input must be given.
- An input comes from the run (`{"source": "run", "path": []}`) or from an \
earlier step (`{"source": "step", "step_index": 0, "path": ["field"]}`). A \
step may only reference steps before it.
- `dependencies.local_capabilities` lists the `name` of every capability the \
steps use.
- `metadata.lifecycle` is "draft". You are drafting, not publishing.
- `metadata.identity.namespace` is the namespace you are given.
- Put the procedure's own intent in `description`, in one or two sentences.

Order the steps so that each has what it needs. Prefer fewer steps that use \
what is installed over more steps that assume something is not.\
"""


def _prompt(
    request: DraftWorkflowRequest, installed: InstalledCapabilities, problems: tuple[str, ...]
) -> tuple[ModelMessage, ...]:
    catalogue = json.dumps(review.catalogue(installed), indent=1, ensure_ascii=False, default=str)
    asked = [
        f"Namespace: {request.namespace}",
        f"Suggested name: {request.name}" if request.name else "Choose a short kebab-case name.",
        "",
        "Capabilities installed on this machine:",
        catalogue,
        "",
        "The procedure:",
        request.sop,
    ]
    if request.required_capabilities:
        asked.extend(
            [
                "",
                "Acceptance requires every one of these exact capabilities to appear:",
                *(
                    f"- {item.namespace}/{item.name}@{item.version}"
                    for item in request.required_capabilities
                ),
            ]
        )
    if problems:
        asked.extend(
            [
                "",
                "Your previous draft would not run here. Fix exactly these and "
                "return the whole document again:",
                *(f"- {problem}" for problem in problems),
            ]
        )
    return (
        ModelMessage(role="system", text=INSTRUCTIONS),
        ModelMessage(role="user", text="\n".join(asked)),
    )


def draft_workflow(
    request: DraftWorkflowRequest,
    installed: InstalledCapabilities,
    *,
    model: ModelClient | None,
    model_alias: str,
    trace: TraceIdentifiers,
    local_only: bool = False,
    ask: Callable[[ModelRequest], object] | None = None,
) -> WorkflowDraft:
    """Draft, check, and try again with the reasons, up to the bound asked for.

    A host with no model refuses by name rather than by absence: the
    capability is installed either way, so that the answer to "why can I not
    draft" is a sentence and not a missing command.
    """
    available = review.names(installed)
    if model is None:
        return WorkflowDraft(
            refusal="model_not_configured",
            available=available,
            request=request,
            preview=(
                "This machine has no model configured, so there is nothing to draft "
                "with. `doctor` says the same, and host.json's `models` is where one "
                "is named."
            ),
        )
    if not available:
        return WorkflowDraft(
            refusal="nothing_to_draft",
            available=(),
            request=request,
            preview=(
                "Nothing is installed on this machine, so every Workflow drafted for it "
                "would name a capability it does not have."
            ),
        )
    send = ask if ask is not None else model.generate
    attempts: list[DraftAttempt] = []
    problems: tuple[str, ...] = ()
    for number in range(1, request.max_attempts + 1):
        asked = ModelRequest(
            trace=trace,
            model_alias=model_alias,
            messages=_prompt(request, installed, problems),
            requirements=ModelRequirements(
                reasoning="high", structured_output=True, local_only=local_only
            ),
            output_contract="platform.workflow-manifest.v1",
            max_output_tokens=4096,
        )
        try:
            response = send(asked)
        except Exception:  # noqa: BLE001 - a provider failure is an answer here
            return WorkflowDraft(
                refusal="model_unavailable",
                attempts=tuple(attempts),
                available=available,
                request=request,
                preview="The model could not be reached, so nothing was drafted.",
            )
        failure = getattr(response, "failure", None)
        structured = getattr(response, "structured_output", None)
        if failure is not None or structured is None:
            return WorkflowDraft(
                refusal="model_unavailable",
                attempts=tuple(attempts),
                available=available,
                request=request,
                preview="The model did not return a document, so nothing was drafted.",
            )
        manifest, problems = review.review(
            structured,
            installed,
            namespace=request.namespace,
            required_capabilities=request.required_capabilities,
        )
        attempts.append(
            DraftAttempt(attempt=number, problems=problems, accepted=manifest is not None)
        )
        if manifest is not None:
            return WorkflowDraft(
                manifest=manifest,
                attempts=tuple(attempts),
                available=available,
                preview=review.rendered(manifest, installed),
                request=request,
            )
    return WorkflowDraft(
        refusal="draft_unusable",
        attempts=tuple(attempts),
        available=available,
        preview=_why_not(attempts, available),
        request=request,
    )


def _why_not(attempts: list[DraftAttempt], available: tuple[str, ...]) -> str:
    """What to show when every attempt failed.

    The last attempt's problems, and what this machine does have -- because
    the usual reason a draft keeps failing is that the procedure needs
    something nobody has installed, and that is worth saying outright rather
    than leaving in a list of validation errors.
    """
    last = attempts[-1].problems if attempts else ()
    lines = [f"{len(attempts)} attempt(s), none of which would run on this machine.", ""]
    lines.extend(f"- {problem}" for problem in last)
    lines.extend(
        [
            "",
            "Installed here: " + (", ".join(available) or "nothing"),
            "",
            "If the procedure needs something that is not in that list, no drafting "
            "will produce it: the capability has to be built and installed first.",
        ]
    )
    return "\n".join(lines)
