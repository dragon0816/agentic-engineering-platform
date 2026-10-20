"""Contracts for the loan reply Workflows (rs_workflow_system 06 and 06b).

Producer, `engineering/rs-loan-customer-block-scan`:
`loan/scan-mail` (read) -> `loan/enqueue` (write: the local queue).

Consumer, `engineering/rs-loan-queue-reply`:
`loan/look-up` (read: the loan portal and C4C in this computer's Edge) ->
`loan/draft-replies` (write: Outlook drafts and the queue) ->
`loan/offer-send` (write: one send card per draft, only when asked).

Field names follow the Workflow parameters (snake case); the queue items and
the source job results keep the source's camel-case keys inside `dict` fields
so the queue files stay readable by the source's own tools.
"""

from __future__ import annotations

from typing import Any

from pydantic import Field

from common.base import Contract


class Verdict(Contract):
    """`ok` is None for a dry run: it changed nothing, so it has no pass or fail."""

    ok: bool | None
    summary: str


class FollowUp(Contract):
    """A Workflow the person may start next (the producer's hand-off to the
    consumer). Offered, never started: the channels draw it as a form or a
    button the person presses."""

    workflow: dict[str, str]
    label: str
    reason: str = ""


# -- producer ---------------------------------------------------------------


class ScanRequest(Contract):
    """The run's answers plus this install's Workflow settings."""

    # Per-install settings (`scope: static`).
    mail_folder: str = "Inbox"
    max_messages: int = Field(default=200, ge=1, le=2000)
    process_from: str = ""
    require_sender: bool = False
    sender_smtp: str = ""
    exclude_categories: tuple[str, ...] = ()
    # Run-time parameters.
    dry_run: bool = False
    process_from_once: str = ""

    def source_config(self) -> dict[str, Any]:
        """The source's `workflow-06.json` keys."""
        return {
            "folder": self.mail_folder or "Inbox",
            "maxMessages": self.max_messages,
            "requireSender": self.require_sender,
            "senderSmtp": self.sender_smtp,
            "excludeCategories": list(self.exclude_categories),
            "processFrom": self.process_from,
        }


class ScanStepInput(Contract):
    request: ScanRequest


class LoanScan(Contract):
    """What the inbox holds, decided but not yet written (source `loan_scan`
    in dry-run mode, without stamping the cut-off)."""

    folder: str
    max_messages: int
    process_from: str
    process_from_source: str
    stamp_needed: bool
    scanned: int
    loan_forms: int
    candidates: tuple[dict[str, Any], ...] = ()
    skipped: tuple[dict[str, Any], ...] = ()
    not_loan_forms: int = 0
    before_start: int = 0
    undated: int = 0
    window_note: str | None = None
    by_category: dict[str, int] = Field(default_factory=dict)
    by_notice: dict[str, int] = Field(default_factory=dict)
    queue: dict[str, int] = Field(default_factory=dict)
    dry_run: bool
    skipped_run: bool = False
    skip_reason: str = ""


class EnqueueStepInput(Contract):
    scan: LoanScan


class LoanEnqueued(Contract):
    enqueued: tuple[str, ...] = ()
    already_queued: tuple[str, ...] = ()
    stamped: bool = False
    queue: dict[str, int] = Field(default_factory=dict)
    dry_run: bool
    preview: str
    verdict: Verdict
    follow_up: FollowUp | None = None


# -- consumer ---------------------------------------------------------------


class ReplyRequest(Contract):
    """The run's answers plus this install's Workflow settings."""

    # Per-install settings (`scope: static`).
    alert_recipient: tuple[str, ...] = ()
    template_dir: str = ""
    portal_origin: str = "https://rstw-portal.rsint.net"
    c4c_home_url: str = ""
    loan_account: str = ""
    close_browsers_after: bool = True
    show_browser: bool = True
    settle_ms: int = Field(default=2500, ge=0, le=60_000)
    busy_timeout_ms: int = Field(default=25_000, ge=1_000, le=300_000)
    nav_timeout_ms: int = Field(default=90_000, ge=5_000, le=600_000)
    # Run-time parameters.
    dry_run: bool = False
    max_items: int = Field(default=1, ge=1, le=20)
    offer_send: bool = False


class LookUpStepInput(Contract):
    request: ReplyRequest


class LoanLookUp(Contract):
    """One queued form, read from the portal and C4C, with the message it
    should get. `error` set: the form could not be finished (a failure
    notice is drafted and the item is parked as failed)."""

    borrow_no: str
    entry_id: str = ""
    loan_url: str = ""
    category: str = ""
    outcome: str = ""
    draft_kind: str = ""
    subject: str | None = None
    body: str = ""
    customer_raw: str = ""
    customer_id: str = ""
    customer_name: str = ""
    customer_email: str = ""
    form_borrow_no: str = ""
    blocks: dict[str, Any] = Field(default_factory=dict)
    screenshot: str | None = None
    error: str = ""


class LoanLookUps(Contract):
    items: tuple[LoanLookUp, ...] = ()
    dry_run: bool
    request: ReplyRequest
    queue: dict[str, int] = Field(default_factory=dict)


class DraftStepInput(Contract):
    lookups: LoanLookUps


class DraftedMail(Contract):
    """One draft saved in Outlook, as a send card would show it."""

    borrow_no: str
    outcome: str
    draft_kind: str
    entry_id: str = ""
    to: tuple[str, ...] = ()
    cc: tuple[str, ...] = ()
    subject: str = ""
    attachments: tuple[str, ...] = ()
    body: str = ""


class LoanDrafts(Contract):
    drafted: tuple[DraftedMail, ...] = ()
    previews: tuple[LoanLookUp, ...] = ()
    failed: tuple[dict[str, str], ...] = ()
    notices: tuple[DraftedMail, ...] = ()
    skipped: tuple[dict[str, str], ...] = ()
    stopped: str = ""
    queue: dict[str, int] = Field(default_factory=dict)
    dry_run: bool
    offer_send: bool = False


class OfferStepInput(Contract):
    drafts: LoanDrafts


class LoanReplyResult(Contract):
    """The consumer's last step: what the person reads, and the send cards."""

    drafted: int
    failed: int
    send_cards: tuple[str, ...] = ()
    # Card ids the channels draw (Agent Web under the run, Telegram after it).
    action_cards: tuple[str, ...] = ()
    queue: dict[str, int] = Field(default_factory=dict)
    dry_run: bool
    preview: str
    verdict: Verdict


class SendOffer(Contract):
    """What one send card shows, for the host's card store."""

    borrow_no: str
    entry_id: str
    to: tuple[str, ...] = ()
    cc: tuple[str, ...] = ()
    subject: str = ""
    body: str = ""
    attachments: tuple[str, ...] = ()
