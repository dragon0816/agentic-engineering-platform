"""Reading the person's Outlook mail: search and read, nothing else (owner 2026-10-15).

`outlook.search` and `outlook.read` (`docs/phases/AGENT_MODE_BACKENDS.md`,
"Revised rules"). **Read only**: no verb here moves, flags, marks, deletes or
sends an item, and a test reads this module's source to keep it that way.
Sending is `integrations.outlook_send`, reachable only from a person's press
on a mail card.

The scope is the person's, from Settings: which folders, how many days back,
which senders and folders are never read. It is applied here, on every call,
so no caller can widen it: a message outside the scope is "not found", the
same answer as a message that does not exist.

`OutlookComMailbox` is the only part that knows Outlook (COM through
pywin32, as `integrations.outlook_draft`); tests drive `MailReader` fakes.
"""

from __future__ import annotations

import html
import logging
import re
from collections.abc import Callable, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal, Protocol, TypeVar

from pydantic import Field

from common.base import Contract
from integrations.com import apartment, progid_is_registered

_T = TypeVar("_T")
_LOG = logging.getLogger(__name__)

MailErrorCode = Literal[
    "library_missing", "outlook_missing", "folder_unknown", "message_unknown", "mail_failed"
]
OUTLOOK_PROGID = "Outlook.Application"
#: olFolderInbox, olFolderSentMail, olFolderDrafts.
_DEFAULT_FOLDERS = {"inbox": 6, "sent items": 5, "sent": 5, "drafts": 16}
#: OlObjectClass.olFolder: a MAPIFolder (the Namespace above a store root is not one).
_OL_FOLDER = 2
MAX_RESULTS = 50
MAX_BODY_CHARS = 20_000
SNIPPET_CHARS = 240


class MailError(Exception):
    """A code only: never a subject, a sender or a body."""

    def __init__(self, code: MailErrorCode) -> None:
        self.code: MailErrorCode = code
        super().__init__(code)


def _hresult(value: object) -> str | None:
    return f"0x{value & 0xFFFFFFFF:08X}" if type(value) is int else None


def log_failure(stage: str, error: BaseException) -> None:
    """A swallowed COM failure, logged so a `mail_failed` can be diagnosed
    (#233): the exception class and HRESULTs only. Never its message or
    `excepinfo` text, which can quote a subject, a sender or a folder name."""
    parts = [f"stage={stage}", f"error={type(error).__module__}.{type(error).__qualname__}"]
    hresult = _hresult(getattr(error, "hresult", None))
    if hresult is not None:
        parts.append(f"hresult={hresult}")
    args = getattr(error, "args", ())
    excepinfo = args[2] if isinstance(args, tuple) and len(args) > 2 else None
    if isinstance(excepinfo, tuple) and len(excepinfo) > 5:
        scode = _hresult(excepinfo[5])
        if scode is not None:
            parts.append(f"scode={scode}")
    _LOG.warning("Outlook mail call failed: %s", " ".join(parts))


class MailScope(Contract):
    """What the agent may read, set by the person in Settings > Agent mode."""

    folders: tuple[str, ...] = ("Inbox",)
    max_days: int = Field(default=30, ge=1, le=365)
    excluded_senders: tuple[str, ...] = ()
    excluded_folders: tuple[str, ...] = ()

    def folder_allowed(self, folder: str) -> bool:
        name = _folder_key(folder)
        if any(
            name == _folder_key(item) or name.startswith(_folder_key(item) + "/")
            for item in self.excluded_folders
        ):
            return False
        return any(
            name == _folder_key(item) or name.startswith(_folder_key(item) + "/")
            for item in self.folders
        )

    def sender_allowed(self, sender: str) -> bool:
        address = sender.strip().casefold()
        for item in self.excluded_senders:
            rule = item.strip().casefold()
            if not rule:
                continue
            if rule.startswith("@") and address.endswith(rule):
                return False
            if address == rule or (rule in address and "@" not in rule):
                return False
        return True

    def recent(self, received: datetime, now: datetime) -> bool:
        moment = received if received.tzinfo else received.replace(tzinfo=UTC)
        return moment >= now - timedelta(days=self.max_days)


def _folder_key(folder: str) -> str:
    return "/".join(part.strip().casefold() for part in re.split(r"[\\/]", folder) if part.strip())


class MailSummary(Contract):
    message_id: str
    folder: str
    sender: str
    to: str = ""
    subject: str = ""
    received: datetime
    attachments: tuple[str, ...] = ()
    snippet: str = ""


class MailMessage(MailSummary):
    cc: str = ""
    body: str = ""


class MailBody(Contract):
    """One message with its HTML, for a Workflow that parses links out of
    mail (the loan approval notices, rs_workflow_system 06). Read only, like
    everything here; the Workflow's own settings name the folder."""

    message_id: str
    subject: str = ""
    sender: str = ""
    received: datetime
    body: str = ""
    html_body: str = ""


class MailBodyLister(Protocol):
    """Newest first, received at or after `since`, at most `limit`."""

    def list_bodies(self, folder: str, since: datetime, limit: int) -> Sequence[MailBody]: ...


class MailReader(Protocol):
    """The raw mailbox, before the scope: tests give a fake."""

    def list(self, folder: str, since: datetime, limit: int) -> Sequence[MailSummary]: ...

    def get(self, message_id: str) -> MailMessage: ...

    def save_attachment(self, message_id: str, name: str, target: Path) -> Path: ...


def search(
    reader: MailReader,
    scope: MailScope,
    *,
    query: str = "",
    sender: str = "",
    folder: str = "",
    days: int | None = None,
    limit: int = 20,
    now: datetime | None = None,
) -> list[MailSummary]:
    """Messages in scope, newest first, whose subject, sender or snippet
    contain `query` and whose sender contains `sender`."""
    now = now or datetime.now(UTC)
    days = scope.max_days if days is None else max(1, min(int(days), scope.max_days))
    since = now - timedelta(days=days)
    folders = [folder] if folder else list(scope.folders)
    if folder and not scope.folder_allowed(folder):
        raise MailError("folder_unknown")
    limit = max(1, min(int(limit), MAX_RESULTS))
    words = query.casefold().split()
    found: list[MailSummary] = []
    for name in folders:
        if not scope.folder_allowed(name):
            continue
        for item in reader.list(name, since, MAX_RESULTS * 4):
            if not scope.folder_allowed(item.folder) or not scope.sender_allowed(item.sender):
                continue
            if not scope.recent(item.received, now) or item.received < since:
                continue
            text = f"{item.subject} {item.sender} {item.snippet}".casefold()
            if words and not all(word in text for word in words):
                continue
            if sender and sender.casefold() not in item.sender.casefold():
                continue
            found.append(item)
    found.sort(key=lambda item: item.received, reverse=True)
    return found[:limit]


def read(
    reader: MailReader, scope: MailScope, message_id: str, now: datetime | None = None
) -> MailMessage:
    """One message in scope, or `message_unknown` (also for one outside it)."""
    now = now or datetime.now(UTC)
    message = reader.get(message_id)
    if (
        not scope.folder_allowed(message.folder)
        or not scope.sender_allowed(message.sender)
        or not scope.recent(message.received, now)
    ):
        raise MailError("message_unknown")
    return message.model_copy(update={"body": message.body[:MAX_BODY_CHARS]})


def safe_file_name(name: str) -> str:
    cleaned = re.sub(r"[<>:\"/\\|?*\x00-\x1f]", "_", name).strip(" .")
    return (cleaned or "attachment")[:120]


def require_com() -> None:
    try:
        import win32com.client  # noqa: F401 - the adapter's own import
    except ImportError:
        raise MailError("library_missing") from None
    if not progid_is_registered(OUTLOOK_PROGID):
        raise MailError("outlook_missing")


def _text(value: Any) -> str:
    return "" if value is None else str(value)


def _when(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    return datetime.fromtimestamp(0, UTC)


def _plain(body: str) -> str:
    return html.unescape(re.sub(r"\s+\n", "\n", body)).strip()


#: PR_SENDER_SMTP_ADDRESS: an Exchange sender's SMTP address, where
#: `SenderEmailAddress` is the X.500 form (`/O=EXCHANGELABS/...`).
_SENDER_SMTP = "http://schemas.microsoft.com/mapi/proptag/0x5D01001F"


def _smtp_sender(item: Any) -> str:
    """The sender's SMTP address when Outlook has one, else what it shows."""
    raw = _text(getattr(item, "SenderEmailAddress", ""))
    if _text(getattr(item, "SenderEmailType", "")).upper() != "EX":
        return raw
    try:
        smtp = _text(item.PropertyAccessor.GetProperty(_SENDER_SMTP))
    except Exception:  # noqa: BLE001 - the X.500 form is still an identity
        smtp = ""
    return smtp or raw


def _dispatch_outlook() -> Any:
    """The running Outlook (single instance), on the calling thread."""
    require_com()
    import win32com.client

    return win32com.client.Dispatch(OUTLOOK_PROGID)


class OutlookComMailbox:
    """Outlook's own items through COM, on the machine that has Outlook.

    Every call initialises COM on its own thread (`integrations.com.apartment`)
    and asks for Outlook inside it, so it works from any worker thread
    (`asyncio.to_thread`); no COM object is kept between calls. Whatever COM
    raises becomes a `MailError` code.

    The tests drive a `MailReader` fake and this adapter with a fake object
    model; a guarded live test reads folder strings from the real Outlook."""

    def __init__(
        self, *, dispatch: Any | None = None, connect: Callable[[], Any] | None = None
    ) -> None:
        # `dispatch`: a ready Outlook object (tests); `connect`: how to get one
        # on the calling thread (default: Dispatch the running Outlook).
        self._dispatch = dispatch
        self._connect = connect or _dispatch_outlook

    def _call(self, work: Callable[[Any], _T]) -> _T:
        """`work(namespace)` inside a COM apartment on this thread, with every
        COM failure mapped to a code."""
        code: MailErrorCode
        try:
            with apartment():
                # The failure is caught inside the block, so its traceback, and
                # the COM objects its frames hold, are gone before COM is
                # released on this thread.
                try:
                    return self._in_apartment(work)
                except MailError as error:
                    code = error.code
                except Exception as error:
                    log_failure("call", error)
                    code = "mail_failed"
        except Exception as error:  # CoInitialize itself failed
            log_failure("apartment", error)
            code = "mail_failed"
        raise MailError(code)

    def _in_apartment(self, work: Callable[[Any], _T]) -> _T:
        try:
            application = self._dispatch if self._dispatch is not None else self._connect()
            namespace = application.GetNamespace("MAPI")
        except MailError:
            raise
        except Exception as error:
            log_failure("connect", error)
            raise MailError("mail_failed") from None
        return work(namespace)

    def _folder(self, namespace: Any, path: str) -> Any:
        parts = [part for part in re.split(r"[\\/]", path) if part.strip()]
        if not parts:
            raise MailError("folder_unknown")
        default = _DEFAULT_FOLDERS.get(parts[0].strip().casefold())
        try:
            folder = namespace.GetDefaultFolder(default) if default is not None else None
            if folder is None:
                folder = namespace.GetDefaultFolder(6).Parent.Folders.Item(parts[0])
            for part in parts[1:]:
                folder = folder.Folders.Item(part)
        except MailError:
            raise
        except Exception:
            raise MailError("folder_unknown") from None
        return folder

    @staticmethod
    def _folder_path(namespace: Any, item: Any) -> str:
        """The item's folder as `list` names it: relative to the default
        store's root, the default folders by their canonical names (`Inbox`
        also when Outlook calls it 收件匣). A folder of another store keeps
        that store's name in front, so it never matches a scope entry.

        The walk stops at a store root: a folder whose parent is not a
        folder (the Namespace has `Folders` too, which is how the store root
        once crept into the path; live test 2026-10-20)."""
        canonical: dict[str, str] = {}
        root_id = ""
        for name, number in (("Inbox", 6), ("Sent Items", 5), ("Drafts", 16)):
            try:
                default = namespace.GetDefaultFolder(number)
            except Exception:
                continue
            canonical[_text(getattr(default, "EntryID", ""))] = name
            if not root_id:
                root_id = _text(getattr(getattr(default, "Parent", None), "EntryID", ""))
        canonical.pop("", None)
        names: list[str] = []
        folder = getattr(item, "Parent", None)
        for _ in range(16):
            if getattr(folder, "Class", None) != _OL_FOLDER:
                break
            entry = _text(getattr(folder, "EntryID", ""))
            if root_id and entry == root_id:
                break
            if entry in canonical:
                names.append(canonical[entry])
                break
            names.append(_text(getattr(folder, "Name", "")))
            if getattr(getattr(folder, "Parent", None), "Class", None) != _OL_FOLDER:
                # The root of a store other than the default one: kept.
                break
            folder = getattr(folder, "Parent", None)
        return "/".join(reversed([name for name in names if name]))

    def _summary(self, item: Any, folder: str) -> MailSummary:
        attachments = tuple(
            _text(item.Attachments.Item(index + 1).FileName)
            for index in range(int(getattr(item.Attachments, "Count", 0)))
        )
        return MailSummary(
            message_id=_text(item.EntryID),
            folder=folder,
            sender=_text(getattr(item, "SenderEmailAddress", "")),
            to=_text(getattr(item, "To", "")),
            subject=_text(getattr(item, "Subject", "")),
            received=_when(getattr(item, "ReceivedTime", None)),
            attachments=attachments,
            snippet=_plain(_text(getattr(item, "Body", "")))[:SNIPPET_CHARS],
        )

    def _list(self, namespace: Any, folder: str, since: datetime, limit: int) -> list[MailSummary]:
        target = self._folder(namespace, folder)
        try:
            items = target.Items
            items.Sort("[ReceivedTime]", True)
            stamp = since.astimezone().strftime("%m/%d/%Y %I:%M %p")
            restricted = items.Restrict(f"[ReceivedTime] >= '{stamp}'")
            found: list[MailSummary] = []
            item = restricted.GetFirst()
            while item is not None and len(found) < limit:
                if getattr(item, "Class", 43) == 43:  # olMail
                    found.append(self._summary(item, folder))
                item = restricted.GetNext()
            return found
        except MailError:
            raise
        except Exception:
            raise MailError("mail_failed") from None

    def list(self, folder: str, since: datetime, limit: int) -> list[MailSummary]:
        return self._call(lambda namespace: self._list(namespace, folder, since, limit))

    def list_bodies(self, folder: str, since: datetime, limit: int) -> Sequence[MailBody]:
        """Messages with their HTML (`MailBodyLister`), newest first. An item
        that cannot be read is left out rather than ending the list, as the
        source Bridge's `/email/list` did."""
        return self._call(lambda namespace: self._list_bodies(namespace, folder, since, limit))

    def _list_bodies(
        self, namespace: Any, folder: str, since: datetime, limit: int
    ) -> Sequence[MailBody]:
        target = self._folder(namespace, folder)
        try:
            items = target.Items
            items.Sort("[ReceivedTime]", True)
            stamp = since.astimezone().strftime("%m/%d/%Y %I:%M %p")
            restricted = items.Restrict(f"[ReceivedTime] >= '{stamp}'")
            found: list[MailBody] = []
            item = restricted.GetFirst()
            while item is not None and len(found) < limit:
                if getattr(item, "Class", 43) == 43:  # olMail
                    try:
                        found.append(
                            MailBody(
                                message_id=_text(item.EntryID),
                                subject=_text(getattr(item, "Subject", "")),
                                sender=_smtp_sender(item),
                                received=_when(getattr(item, "ReceivedTime", None)),
                                body=_text(getattr(item, "Body", "")),
                                html_body=_text(getattr(item, "HTMLBody", "")),
                            )
                        )
                    except Exception:  # noqa: BLE001 - one unreadable item is skipped
                        pass
                item = restricted.GetNext()
            return found
        except MailError:
            raise
        except Exception:
            raise MailError("mail_failed") from None

    def get(self, message_id: str) -> MailMessage:
        return self._call(lambda namespace: self._get(namespace, message_id))

    def _get(self, namespace: Any, message_id: str) -> MailMessage:
        try:
            item = namespace.GetItemFromID(message_id)
        except Exception:
            raise MailError("message_unknown") from None
        try:
            summary = self._summary(item, self._folder_path(namespace, item))
            return MailMessage(
                **summary.model_dump(),
                cc=_text(getattr(item, "CC", "")),
                body=_plain(_text(getattr(item, "Body", ""))),
            )
        except Exception:
            raise MailError("mail_failed") from None

    def save_attachment(self, message_id: str, name: str, target: Path) -> Path:
        return self._call(lambda namespace: self._save(namespace, message_id, name, target))

    @staticmethod
    def _save(namespace: Any, message_id: str, name: str, target: Path) -> Path:
        try:
            item = namespace.GetItemFromID(message_id)
            for index in range(int(item.Attachments.Count)):
                attachment = item.Attachments.Item(index + 1)
                if _text(attachment.FileName) == name:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    attachment.SaveAsFile(str(target))
                    return target
        except Exception:
            raise MailError("mail_failed") from None
        raise MailError("message_unknown")
