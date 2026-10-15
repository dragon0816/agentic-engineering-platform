"""Send, or discard, one Outlook draft a person just reviewed (owner 2026-10-15).

The only module in this repository that delivers a mail. It is reached from
one place: the decision of a mail card (`host_runtime.agent_mail`), after a
person pressed **Send** on that one message in Agent Web. There is no
conversation-wide allow and no tool, route or Workflow step that calls it;
a test checks the source tree for that.

What is sent is the draft the card showed: the item is found by its Outlook
id and its recipients, subject and attachment names are compared with what
the card showed before anything is sent. If the person edited the draft in
Outlook meanwhile, nothing is sent and the card says to send it from Outlook.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from typing import Any, Literal, Protocol

from integrations.outlook_mail import OUTLOOK_PROGID, MailError, require_com

SendErrorCode = Literal["draft_unknown", "draft_changed", "send_failed",
                        "library_missing", "outlook_missing"]


class SendError(Exception):
    def __init__(self, code: SendErrorCode) -> None:
        self.code: SendErrorCode = code
        super().__init__(code)


def draft_fingerprint(to: Sequence[str], cc: Sequence[str], subject: str,
                      attachments: Sequence[str]) -> str:
    """What must not change between the card and the send. Outlook rewrites
    a draft's HTML when it saves it, so the body is shown on the card but not
    compared; recipients, subject and attachment names are."""

    def addresses(values: Sequence[str]) -> list[str]:
        return sorted(part.strip().casefold() for value in values
                      for part in value.replace(",", ";").split(";") if part.strip())

    payload = {"to": addresses(to), "cc": addresses(cc), "subject": subject.strip(),
               "attachments": sorted(name.casefold() for name in attachments)}
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


class DraftSender(Protocol):
    def send(self, entry_id: str, fingerprint: str) -> None: ...

    def discard(self, entry_id: str) -> None: ...


class OutlookComDraftSender:
    """Outlook's own Send on a saved draft. **Not exercised by the test
    suite** apart from a fake dispatch; proven when the owner first sends."""

    def __init__(self, *, dispatch: Any | None = None) -> None:
        self._dispatch = dispatch

    def _item(self, entry_id: str) -> Any:
        if self._dispatch is None:
            try:
                require_com()
            except MailError as error:
                raise SendError(error.code if error.code in ("library_missing",
                                                             "outlook_missing")
                                else "send_failed") from None
            import win32com.client

            self._dispatch = win32com.client.Dispatch(OUTLOOK_PROGID)
        try:
            return self._dispatch.GetNamespace("MAPI").GetItemFromID(entry_id)
        except Exception:
            raise SendError("draft_unknown") from None

    def send(self, entry_id: str, fingerprint: str) -> None:
        item = self._item(entry_id)
        try:
            names = [str(item.Attachments.Item(index + 1).FileName)
                     for index in range(int(item.Attachments.Count))]
            now = draft_fingerprint([str(item.To or "")], [str(item.CC or "")],
                                    str(item.Subject or ""), names)
        except Exception:
            raise SendError("draft_unknown") from None
        if now != fingerprint:
            raise SendError("draft_changed")
        try:
            item.Send()
        except Exception:
            raise SendError("send_failed") from None

    def discard(self, entry_id: str) -> None:
        item = self._item(entry_id)
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
