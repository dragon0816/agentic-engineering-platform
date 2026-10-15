"""Save one Outlook draft that a person reviews and sends themselves.

Extracted from the source workflows that each built their own draft (11, 14,
06b) so a Workflow, including one composed from natural language, uses one
governed step. There is no send: `integrations.outlook_draft` has no verb that
delivers, and sending stays a separate, per-run approved action.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable

from capabilities.contracts import CapabilitySpec
from capabilities.runtime import CapabilityRefused
from common.base import Contract, Text
from common.execution import RequestContext
from integrations import outlook_draft
from integrations.outlook_draft import DraftError, DraftWriter, MailDraft

DRAFT_SPEC = CapabilitySpec.model_validate(
    {
        "identity": {"namespace": "outlook", "name": "draft", "version": "1.0.0"},
        "name": "outlook.draft",
        "description": "Save an Outlook draft with optional attached files; never sends",
        "input_contract": "outlook.draft.input.v1",
        "output_contract": "outlook.draft.output.v1",
        # A draft changes the member's own mailbox, so it is a write that
        # needs a grant with an approval, like the weekly mail.
        "side_effect": "write",
        "policy": {
            "risk": "low",
            "approval_required": True,
            "required_permissions": ["outlook.draft"],
            "policy_refs": ["outlook-draft-policy"],
        },
    }
)


class MailDraftRequest(Contract):
    """What to draft. `skip` lets an earlier step say there is nothing to
    draft this run (no recipient, or a dry run) without a conditional step."""

    subject: str = ""
    html_body: str = ""
    # Blank addresses are dropped, as `outlook_draft.recipients` does.
    to: tuple[str, ...] = ()
    cc: tuple[str, ...] = ()
    attachments: tuple[Text, ...] = ()
    skip: bool = False
    # A covering note for something already written (Workflow 14's document):
    # a failed draft is reported in the result instead of failing the run.
    best_effort: bool = False


class MailDraftResult(Contract):
    drafted: bool
    skipped: bool = False
    to: tuple[str, ...] = ()
    cc: tuple[str, ...] = ()
    subject: str = ""
    attachments: int = 0
    entry_id: str = ""
    folder: str = ""
    # The refusal code when a best-effort draft was not saved.
    error: str = ""


class MailDraftHandler:
    """The writer is built per run, so a host without Outlook installs the
    capability and refuses at the draft rather than at start-up."""

    def __init__(self, writer: Callable[[], DraftWriter]) -> None:
        self._writer = writer

    async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
        request = MailDraftRequest.model_validate(inputs)
        if request.skip:
            return MailDraftResult(drafted=False, skipped=True)
        to = outlook_draft.recipients(request.to)
        if not to:
            raise CapabilityRefused("draft_recipient_missing")
        if not request.subject.strip() or not request.html_body.strip():
            raise CapabilityRefused("draft_content_missing")
        draft = MailDraft(
            subject=request.subject,
            html_body=request.html_body,
            to=to,
            cc=outlook_draft.recipients(request.cc),
            attachments=request.attachments,
        )
        try:
            receipt = await asyncio.to_thread(lambda: self._writer().save(draft))
        except DraftError as error:
            if request.best_effort:
                return MailDraftResult(
                    drafted=False, to=draft.to, subject=draft.subject, error=error.code
                )
            raise CapabilityRefused(error.code) from None
        return MailDraftResult(
            drafted=receipt.saved,
            to=draft.to,
            cc=draft.cc,
            subject=draft.subject,
            attachments=len(draft.attachments),
            entry_id=receipt.entry_id,
            folder=receipt.folder,
        )
