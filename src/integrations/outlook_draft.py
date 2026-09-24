"""The weekly mail as a draft in Outlook, and nothing further.

**This never sends.** No call that delivers a mail appears anywhere below,
and a test reads this module's own source to assert that none ever does,
because the failure it would cause is a mail about the team's work arriving
in the whole team's inbox with nobody having read it first. A draft is the
deliverable: a person opens it, reads it, and presses send, or does not.

That is also why the mail is written this way rather than over SMTP. Sending
would need a mailbox credential on the workstation and would put the platform
one bug away from mailing a department. Outlook's own draft folder needs no
credential, uses the identity already signed in, and stops at the point where
a person is required.

The protocol is what `capabilities.weekly_report` speaks; `OutlookComDraft`
is the one thing that knows about Outlook, so the choice of COM is reversible
by writing another adapter and nothing else.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any, Literal, Protocol

from common.base import Contract, Text
from integrations.com import progid_is_registered

DraftErrorCode = Literal[
    "library_missing",
    "outlook_missing",
    "attachment_missing",
    "draft_failed",
]

#: What Outlook registers itself as.
OUTLOOK_PROGID = "Outlook.Application"
#: olMailItem, the argument to `CreateItem`.
_MAIL_ITEM = 0
#: PR_ATTACH_CONTENT_ID. An inline image is referenced from the HTML as
#: `cid:something`, and this is the property that gives an attachment that
#: name. Without it the picture is an attachment at the bottom and the body
#: shows a broken image.
_CONTENT_ID = "http://schemas.microsoft.com/mapi/proptag/0x3712001F"
#: PR_ATTACHMENT_HIDDEN. An inline picture should not also be listed as a
#: file to open.
_HIDDEN = "http://schemas.microsoft.com/mapi/proptag/0x7FFE000B"


class DraftError(Exception):
    """The code is the whole message: no subject, recipient, body or path is
    echoed, because every one of them carries the team's own data."""

    def __init__(self, code: DraftErrorCode) -> None:
        self.code: DraftErrorCode = code
        super().__init__(code)


class InlineImage(Contract):
    """A picture the body refers to as `cid:<cid>`."""

    cid: Text
    path: Text


class MailDraft(Contract):
    """One draft. Recipients are addresses as typed into Outlook, resolved by
    Outlook and never looked up here: reading an address book through COM is
    what raises the security prompt this design avoids."""

    subject: Text
    html_body: Text
    to: tuple[Text, ...] = ()
    cc: tuple[Text, ...] = ()
    images: tuple[InlineImage, ...] = ()


class DraftReceipt(Contract):
    """What a saved draft leaves behind. `entry_id` is Outlook's own
    identifier for the item, which is how a person or a later run finds the
    draft again; it is not a secret and carries no content."""

    saved: bool = False
    entry_id: str = ""
    folder: str = ""


class DraftWriter(Protocol):
    """What the capability needs. Saving, and no verb that delivers."""

    def save(self, draft: MailDraft) -> DraftReceipt: ...


class RecordingDraftWriter:
    """Every draft it was asked to save, and no Outlook. This is what the
    tests drive, and what a host without Outlook could use to see the mail."""

    def __init__(self) -> None:
        self.drafts: list[MailDraft] = []

    def save(self, draft: MailDraft) -> DraftReceipt:
        checked = MailDraft.model_validate(draft)
        for image in checked.images:
            if not Path(image.path).is_file():
                raise DraftError("attachment_missing")
        self.drafts.append(checked)
        return DraftReceipt(saved=True, entry_id=f"recorded-{len(self.drafts)}", folder="recorded")


def require_com() -> None:
    """Which of the two missing things is missing, told apart before anything
    is started.

    `library_missing` is this installation: the COM bridge is not installed,
    which on a source checkout means the `windows` extra. `outlook_missing`
    is the machine: Outlook itself is not there. The preview bundle always
    carries the bridge, so an importable `win32com` says nothing at all about
    Outlook.
    """
    try:
        import win32com.client  # noqa: F401 - the adapter's own import
    except ImportError:
        raise DraftError("library_missing") from None
    if not progid_is_registered(OUTLOOK_PROGID):
        raise DraftError("outlook_missing")


class OutlookComDraft:
    """The draft through Outlook itself, on the Windows machine that has it.

    **Not exercised by the test suite.** There is no Outlook in CI and none
    on a Linux runner, so every test drives `RecordingDraftWriter` instead.
    This adapter is written to the documented Outlook object model and is
    unproven until the owner runs it on a company machine, which
    `docs/TASKS.md` records beside the Excel adapter's identical caveat.
    """

    def __init__(self, *, dispatch: Any | None = None) -> None:
        self._dispatch = dispatch

    def _application(self) -> Any:
        if self._dispatch is not None:
            return self._dispatch
        require_com()
        import win32com.client

        # Outlook is a single-instance application: `DispatchEx` would be
        # answered by the running copy anyway, and asking for the running one
        # is what the object model documents.
        return win32com.client.Dispatch(OUTLOOK_PROGID)

    def save(self, draft: MailDraft) -> DraftReceipt:
        checked = MailDraft.model_validate(draft)
        # Checked before Outlook is touched: a missing picture should not
        # leave a half-built item in somebody's drafts.
        for image in checked.images:
            if not Path(image.path).is_file():
                raise DraftError("attachment_missing")
        application = self._application()
        try:
            item = application.CreateItem(_MAIL_ITEM)
            item.Subject = checked.subject
            item.HTMLBody = checked.html_body
            if checked.to:
                item.To = "; ".join(checked.to)
            if checked.cc:
                item.CC = "; ".join(checked.cc)
            for image in checked.images:
                attached = item.Attachments.Add(str(Path(image.path).resolve()))
                accessor = attached.PropertyAccessor
                accessor.SetProperty(_CONTENT_ID, image.cid)
                accessor.SetProperty(_HIDDEN, True)
            item.Save()
            return DraftReceipt(
                saved=True,
                entry_id=str(item.EntryID or ""),
                folder=str(getattr(item.Parent, "Name", "") or ""),
            )
        except DraftError:
            raise
        except Exception:
            # Whatever COM raised is not re-raised: its message can carry the
            # subject line and the recipients.
            raise DraftError("draft_failed") from None


def images_for(
    chart: bytes | None, directory: Path, *, cid: str = "effort-chart"
) -> tuple[
    tuple[InlineImage, ...],
    str,
]:
    """Write the chart beside the draft and say what the body should refer to.

    Returns no image and an empty cid when there is no chart, which is the
    week where nothing was worked on: `build_html` then leaves the picture
    out and keeps every number.
    """
    if not chart:
        return (), ""
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{cid}.png"
    path.write_bytes(chart)
    return (InlineImage(cid=cid, path=str(path)),), cid


def recipients(values: Sequence[str]) -> tuple[Text, ...]:
    """Addresses as given, emptied of blanks. Not validated here: what an
    address may look like is Outlook's rule, and a host that guessed wrong
    would refuse a draft nobody had asked it to judge."""
    return tuple(value.strip() for value in values if value.strip())
