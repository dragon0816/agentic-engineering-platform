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

import logging
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, Literal, Protocol

from common.base import Contract, Text
from integrations.com import apartment, progid_is_registered

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
    # Files attached as themselves (a generated document), not shown inline.
    attachments: tuple[Text, ...] = ()


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


class ReplyDraft(Contract):
    """A reply to a mail already in Outlook, saved as a draft (the loan
    Workflow's answer on the approval notice, rs_workflow_system 06b). The
    text goes above the quoted original, as the source Bridge's `/email/reply`
    wrote it; Outlook chooses the recipients from the original."""

    entry_id: Text
    text_body: Text
    attachments: tuple[Text, ...] = ()


class ReplyReceipt(DraftReceipt):
    """The saved reply as Outlook made it: who it goes to and its subject are
    read back, so a later send card shows (and checks) what is really there."""

    to: tuple[str, ...] = ()
    cc: tuple[str, ...] = ()
    subject: str = ""
    attachments: tuple[str, ...] = ()


class ReplyWriter(Protocol):
    """Saving a reply as a draft, and no verb that delivers."""

    def reply(self, draft: ReplyDraft) -> ReplyReceipt: ...


def _addresses(value: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in value.replace(",", ";").split(";") if part.strip())


class RecordingDraftWriter:
    """Every draft it was asked to save, and no Outlook. This is what the
    tests drive, and what a host without Outlook could use to see the mail."""

    def __init__(self) -> None:
        self.drafts: list[MailDraft] = []
        self.replies: list[ReplyDraft] = []

    def save(self, draft: MailDraft) -> DraftReceipt:
        checked = MailDraft.model_validate(draft)
        _require_files(checked)
        self.drafts.append(checked)
        return DraftReceipt(saved=True, entry_id=f"recorded-{len(self.drafts)}", folder="recorded")

    def reply(self, draft: ReplyDraft) -> ReplyReceipt:
        checked = ReplyDraft.model_validate(draft)
        if any(not Path(path).is_file() for path in checked.attachments):
            raise DraftError("attachment_missing")
        self.replies.append(checked)
        return ReplyReceipt(
            saved=True,
            entry_id=f"recorded-reply-{len(self.replies)}",
            folder="recorded",
            to=(f"sender-of-{checked.entry_id}@example.com",),
            subject=f"RE: {checked.entry_id}",
            attachments=tuple(Path(path).name for path in checked.attachments),
        )


def _require_files(draft: MailDraft) -> None:
    paths = [image.path for image in draft.images] + list(draft.attachments)
    if any(not Path(path).is_file() for path in paths):
        raise DraftError("attachment_missing")


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


def _dispatch_outlook() -> Any:
    """The running Outlook, on the calling thread. Outlook is a
    single-instance application: `DispatchEx` would be answered by the running
    copy anyway, and asking for the running one is what the object model
    documents."""
    require_com()
    import win32com.client

    return win32com.client.Dispatch(OUTLOOK_PROGID)


def _log_draft_failure(stage: str, error: BaseException) -> None:
    """Fixed operation and numeric HRESULTs only; never COM exception text."""
    parts = ["stage=" + stage]
    hresult = getattr(error, "hresult", None)
    if type(hresult) is int:
        parts.append(f"hresult=0x{hresult & 0xFFFFFFFF:08X}")
    args = getattr(error, "args", ())
    info = args[2] if isinstance(args, tuple) and len(args) > 2 else None
    if isinstance(info, tuple) and len(info) > 5 and type(info[5]) is int:
        parts.append(f"scode=0x{info[5] & 0xFFFFFFFF:08X}")
    logging.getLogger(__name__).warning("Outlook draft failed: %s", " ".join(parts))


class OutlookComDraft:
    """The draft through Outlook itself, on the Windows machine that has it.

    **Not exercised by the test suite.** There is no Outlook in CI and none
    on a Linux runner, so every test drives `RecordingDraftWriter` instead.
    This adapter is written to the documented Outlook object model and is
    unproven until the owner runs it on a company machine, which
    `docs/TASKS.md` records beside the Excel adapter's identical caveat.
    """

    def __init__(
        self, *, dispatch: Any | None = None, connect: Callable[[], Any] | None = None
    ) -> None:
        # `dispatch`: a ready Outlook object (tests); `connect`: how to get one
        # on the calling thread (default: Dispatch the running Outlook).
        self._dispatch = dispatch
        self._connect = connect or _dispatch_outlook

    def save(self, draft: MailDraft) -> DraftReceipt:
        """Inside a COM apartment on the calling thread (any worker thread);
        the Outlook object is asked for inside it and not kept."""
        checked = MailDraft.model_validate(draft)
        # Checked before Outlook is touched: a missing picture should not
        # leave a half-built item in somebody's drafts.
        _require_files(checked)
        code: DraftErrorCode
        try:
            with apartment():
                # Caught inside the block, so no COM object outlives it.
                try:
                    return self._save(checked)
                except DraftError as error:
                    code = error.code
                except Exception as error:
                    _log_draft_failure("adapter", error)
                    code = "draft_failed"
        except Exception as error:  # CoInitialize itself failed
            _log_draft_failure("apartment", error)
            code = "draft_failed"
        raise DraftError(code)

    def _save(self, checked: MailDraft) -> DraftReceipt:
        stage = "connect"
        try:
            application = self._dispatch if self._dispatch is not None else self._connect()
            stage = "create_item"
            item = application.CreateItem(_MAIL_ITEM)
            stage = "content"
            item.Subject = checked.subject
            item.HTMLBody = checked.html_body
            if checked.to:
                item.To = "; ".join(checked.to)
            if checked.cc:
                item.CC = "; ".join(checked.cc)
            stage = "attachments"
            for image in checked.images:
                attached = item.Attachments.Add(str(Path(image.path).resolve()))
                accessor = attached.PropertyAccessor
                stage = "inline_properties"
                accessor.SetProperty(_CONTENT_ID, image.cid)
                accessor.SetProperty(_HIDDEN, True)
            for path in checked.attachments:
                item.Attachments.Add(str(Path(path).resolve()))
            stage = "save"
            item.Save()
            stage = "receipt"
            return DraftReceipt(
                saved=True,
                entry_id=str(item.EntryID or ""),
                folder=str(getattr(item.Parent, "Name", "") or ""),
            )
        except DraftError:
            raise
        except Exception as error:
            _log_draft_failure(stage, error)
            # Whatever COM raised is not re-raised: its message can carry the
            # subject line and the recipients.
            raise DraftError("draft_failed") from None

    def reply(self, draft: ReplyDraft) -> ReplyReceipt:
        """A reply to `entry_id` saved in Drafts (`ReplyWriter`), inside a COM
        apartment on the calling thread like `save`. **Not exercised by the
        test suite** beyond a fake object model; proven on the company PC."""
        checked = ReplyDraft.model_validate(draft)
        if any(not Path(path).is_file() for path in checked.attachments):
            raise DraftError("attachment_missing")
        code: DraftErrorCode
        try:
            with apartment():
                try:
                    return self._reply(checked)
                except DraftError as error:
                    code = error.code
                except Exception:
                    code = "draft_failed"
        except Exception:  # CoInitialize itself failed
            code = "draft_failed"
        raise DraftError(code)

    def _reply(self, checked: ReplyDraft) -> ReplyReceipt:
        try:
            application = self._dispatch if self._dispatch is not None else self._connect()
            original = application.GetNamespace("MAPI").GetItemFromID(checked.entry_id)
            item = original.Reply()
            # Plain text above the quoted original (the source's text_body path).
            item.Body = checked.text_body + "\r\n\r\n" + str(item.Body or "")
            item.Save()
            for path in checked.attachments:
                item.Attachments.Add(str(Path(path).resolve()))
            item.Save()
            names = tuple(
                str(item.Attachments.Item(index + 1).FileName)
                for index in range(int(item.Attachments.Count))
            )
            return ReplyReceipt(
                saved=True,
                entry_id=str(item.EntryID or ""),
                folder=str(getattr(item.Parent, "Name", "") or ""),
                to=_addresses(str(item.To or "")),
                cc=_addresses(str(item.CC or "")),
                subject=str(item.Subject or ""),
                attachments=names,
            )
        except DraftError:
            raise
        except Exception:
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
