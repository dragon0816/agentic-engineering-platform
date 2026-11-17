"""Send or discard one saved Outlook draft under the execution environment.

Normal explicit send calls and historical owner-card decisions use the same
sender. A draft-only request never calls Send. Recipients, subject and attachment
names must match the supplied fingerprint; changed drafts fail honestly. Outlook
may rewrite saved HTML, so the fingerprint does not compare the body.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Sequence
from typing import Any, Literal, Protocol

from integrations.com import apartment
from integrations.outlook_mail import OUTLOOK_PROGID, MailError, require_com

SendErrorCode = Literal[
    "draft_unknown", "draft_changed", "send_failed", "library_missing", "outlook_missing"
]


class SendError(Exception):
    def __init__(self, code: SendErrorCode) -> None:
        self.code: SendErrorCode = code
        super().__init__(code)


def draft_fingerprint(
    to: Sequence[str], cc: Sequence[str], subject: str, attachments: Sequence[str]
) -> str:
    """What must not change between the card and the send. Outlook rewrites
    a draft's HTML when it saves it, so the body is shown on the card but not
    compared; recipients, subject and attachment names are."""

    def addresses(values: Sequence[str]) -> list[str]:
        return sorted(
            part.strip().casefold()
            for value in values
            for part in value.replace(",", ";").split(";")
            if part.strip()
        )

    payload = {
        "to": addresses(to),
        "cc": addresses(cc),
        "subject": subject.strip(),
        "attachments": sorted(name.casefold() for name in attachments),
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


class DraftSender(Protocol):
    def send(self, entry_id: str, fingerprint: str) -> None: ...

    def discard(self, entry_id: str) -> None: ...


def _dispatch_outlook() -> Any:
    """The running Outlook, on the calling thread."""
    require_com()
    import win32com.client

    return win32com.client.Dispatch(OUTLOOK_PROGID)


class OutlookComDraftSender:
    """Outlook's own Send on a saved draft. **Not exercised by the test
    suite** apart from a fake dispatch; proven when the owner first sends."""

    def __init__(
        self, *, dispatch: Any | None = None, connect: Callable[[], Any] | None = None
    ) -> None:
        # `dispatch`: a ready Outlook object (tests); `connect`: how to get one
        # on the calling thread (default: Dispatch the running Outlook).
        self._dispatch = dispatch
        self._connect = connect or _dispatch_outlook

    def _call(self, work: Callable[[Any], None]) -> None:
        """`work(item)` inside a COM apartment on the calling thread; the
        Outlook object is asked for inside it and not kept."""
        code: SendErrorCode
        try:
            with apartment():
                # Caught inside the block, so no COM object outlives it.
                try:
                    return work(self._application())
                except SendError as error:
                    code = error.code
                except Exception:
                    code = "send_failed"
        except Exception:  # CoInitialize itself failed
            code = "send_failed"
        raise SendError(code)

    def _application(self) -> Any:
        if self._dispatch is not None:
            return self._dispatch
        try:
            return self._connect()
        except MailError as error:
            code: SendErrorCode = "send_failed"
            if error.code == "library_missing" or error.code == "outlook_missing":
                code = error.code
            raise SendError(code) from None
        except Exception:
            # Outlook could not be reached: nothing was sent.
            raise SendError("send_failed") from None

    @staticmethod
    def _item(application: Any, entry_id: str) -> Any:
        try:
            return application.GetNamespace("MAPI").GetItemFromID(entry_id)
        except Exception:
            raise SendError("draft_unknown") from None

    def send(self, entry_id: str, fingerprint: str) -> None:
        self._call(lambda application: self._send(application, entry_id, fingerprint))

    def _send(self, application: Any, entry_id: str, fingerprint: str) -> None:
        item = self._item(application, entry_id)
        try:
            names = [
                str(item.Attachments.Item(index + 1).FileName)
                for index in range(int(item.Attachments.Count))
            ]
            now = draft_fingerprint(
                [str(item.To or "")], [str(item.CC or "")], str(item.Subject or ""), names
            )
        except Exception:
            raise SendError("draft_unknown") from None
        if now != fingerprint:
            raise SendError("draft_changed")
        try:
            item.Send()
        except Exception:
            raise SendError("send_failed") from None

    def discard(self, entry_id: str) -> None:
        self._call(lambda application: self._discard(application, entry_id))

    def _discard(self, application: Any, entry_id: str) -> None:
        item = self._item(application, entry_id)
        try:
            item.Delete()
        except Exception:
            raise SendError("send_failed") from None


class RecordingDraftSender:
    """For tests: what would have been sent or discarded, and no Outlook."""

    def __init__(self, fingerprints: dict[str, str] | None = None) -> None:
        self.sent: list[str] = []
        self.discarded: list[str] = []
        # The fingerprint each draft has now; a test changes one to simulate
        # a person editing the draft in Outlook.
        self.fingerprints: dict[str, str] = dict(fingerprints or {})

    def send(self, entry_id: str, fingerprint: str) -> None:
        if entry_id not in self.fingerprints:
            raise SendError("draft_unknown")
        if self.fingerprints[entry_id] != fingerprint:
            raise SendError("draft_changed")
        self.sent.append(entry_id)

    def discard(self, entry_id: str) -> None:
        self.discarded.append(entry_id)
