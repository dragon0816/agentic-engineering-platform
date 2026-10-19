"""Outlook's folder paths: `list` and `get` name a message's folder the same way.

Live test 2026-10-20: every Inbox message failed signature harvesting with
`message_unknown`. `list("Inbox")` labelled the message `Inbox`, but `get()`
walked up the folder tree into the store root (`<mailbox>/Inbox`), because the
Namespace above the root also has `Folders`; the scope check in
`outlook_mail.read` then refused it. The fakes here mirror Outlook's object
model (Application > Namespace > store root > Inbox), which the earlier
`MailReader` fakes did not: they returned consistent folders by construction.

The live check at the end runs only where Outlook is already running; it is
read only and compares folder strings, never a subject or a body.
"""

from __future__ import annotations

import asyncio
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from test_agent_mail import _call, _mail, _press
from test_business_cards_capabilities import BODY, SignatureModel, _bridge, _run

from capabilities.mail_read.handlers import MailReadHandler, MailReadRequest
from common.execution import RequestContext, TraceIdentifiers
from integrations import outlook_mail
from integrations.outlook_mail import MailError, MailScope, OutlookComMailbox

NOW = datetime.now(UTC)
OL_NAMESPACE, OL_FOLDER, OL_MAIL = 1, 2, 43


class FakeItems:
    def __init__(self, items: list[Any]) -> None:
        self.items = items
        self._at = 0

    def Sort(self, key: str, descending: bool) -> None:  # noqa: N802 - Outlook's spelling
        self.items.sort(key=lambda item: item.ReceivedTime, reverse=descending)

    def Restrict(self, text: str) -> FakeItems:  # noqa: N802
        return FakeItems(list(self.items))

    def GetFirst(self) -> Any:  # noqa: N802
        self._at = 0
        return self.GetNext()

    def GetNext(self) -> Any:  # noqa: N802
        if self._at >= len(self.items):
            return None
        self._at += 1
        return self.items[self._at - 1]


class FakeFolders:
    def __init__(self) -> None:
        self.by_name: dict[str, FakeFolder] = {}

    def Item(self, name: str) -> FakeFolder:  # noqa: N802
        return self.by_name[name]


class FakeFolder:
    Class = OL_FOLDER

    def __init__(self, name: str, parent: Any, entry: str) -> None:
        self.Name, self.Parent, self.EntryID = name, parent, entry
        self.Folders = FakeFolders()
        self.Items = FakeItems([])
        parent.Folders.by_name[name] = self

    def add(self, name: str) -> FakeFolder:
        return FakeFolder(name, self, f"{self.EntryID}/{name}")


class FakeAttachments:
    Count = 0


class FakeMailItem:
    Class = OL_MAIL

    def __init__(self, entry: str, folder: FakeFolder, sender: str, body: str, days: int) -> None:
        self.EntryID, self.Parent = entry, folder
        self.SenderEmailAddress, self.To, self.CC = sender, "me@example.com", ""
        self.Subject, self.Body = "weekly sync", body
        self.ReceivedTime = NOW - timedelta(days=days)
        self.Attachments = FakeAttachments()
        folder.Items.items.append(self)


class FakeNamespace:
    """MAPI: the Namespace has `Folders` (the stores) but is no folder."""

    Class = OL_NAMESPACE

    def __init__(self, *, inbox_name: str = "Inbox") -> None:
        self.Folders = FakeFolders()
        self.root = FakeFolder("me@example.com", self, "root")
        self.inbox = self.root.add(inbox_name)
        self.sent = self.root.add("Sent Items")
        self.drafts = self.root.add("Drafts")
        self.items: dict[str, FakeMailItem] = {}

    def GetDefaultFolder(self, number: int) -> FakeFolder:  # noqa: N802
        return {6: self.inbox, 5: self.sent, 16: self.drafts}[number]

    def GetItemFromID(self, entry: str) -> FakeMailItem:  # noqa: N802
        return self.items[entry]

    def mail(
        self, entry: str, folder: FakeFolder, sender: str, body: str = "", days: int = 1
    ) -> None:
        self.items[entry] = FakeMailItem(entry, folder, sender, body or f"body {entry}", days)


class FakeOutlook:
    Class = 0  # olApplication

    def __init__(self, namespace: FakeNamespace) -> None:
        self.namespace = namespace

    def GetNamespace(self, name: str) -> FakeNamespace:  # noqa: N802
        return self.namespace


def _outlook(*, inbox_name: str = "Inbox") -> tuple[FakeNamespace, OutlookComMailbox]:
    namespace = FakeNamespace(inbox_name=inbox_name)
    projects = namespace.inbox.add("Projects")
    archive = namespace.root.add("Archive")
    other_store = FakeFolder("Shared PST", namespace, "pst")
    other_inbox = other_store.add("Inbox")
    namespace.mail("in-1", namespace.inbox, "lead@example.com", BODY_ONE)
    namespace.mail("in-2", projects, "lead@example.com")
    namespace.mail("ar-1", archive, "lead@example.com")
    namespace.mail("pst-1", other_inbox, "lead@example.com")
    return namespace, OutlookComMailbox(dispatch=FakeOutlook(namespace))


BODY_ONE = BODY.format(name="王小明", title="協理", ext="312")


def test_list_and_get_name_the_same_folder() -> None:
    _, box = _outlook()
    since = NOW - timedelta(days=30)
    listed = box.list("Inbox", since, 10)
    assert [(item.message_id, item.folder) for item in listed] == [("in-1", "Inbox")]
    assert box.get("in-1").folder == "Inbox"
    assert box.list("Inbox/Projects", since, 10)[0].folder == box.get("in-2").folder
    assert box.get("in-2").folder == "Inbox/Projects"
    assert box.get("ar-1").folder == "Archive"


def test_a_localised_inbox_is_still_the_inbox() -> None:
    """A Chinese Outlook names the Inbox 收件匣; the scope says Inbox."""
    _, box = _outlook(inbox_name="收件匣")
    assert box.get("in-1").folder == "Inbox"
    assert box.get("in-2").folder == "Inbox/Projects"


def test_read_accepts_an_inbox_message_and_keeps_other_stores_out() -> None:
    _, box = _outlook()
    scope = MailScope(folders=("Inbox",), max_days=30)
    assert outlook_mail.read(box, scope, "in-1").message_id == "in-1"
    assert outlook_mail.read(box, scope, "in-2").folder == "Inbox/Projects"
    # Another store's Inbox is not the person's Inbox: the path names the store.
    assert box.get("pst-1").folder == "Shared PST/Inbox"
    for outside in ("pst-1", "ar-1"):
        with pytest.raises(MailError) as refused:
            outlook_mail.read(box, scope, outside)
        assert refused.value.code == "message_unknown"


def _context() -> RequestContext:
    return RequestContext(
        trace=TraceIdentifiers(trace_id="t", request_id="r", span_id="s"),
        actor="engineer",
        namespace="engineering",
        channel="local",
        message="m",
    )


def test_the_outlook_read_capability_reads_an_inbox_message() -> None:
    _, box = _outlook()
    scope = MailScope(folders=("Inbox",), max_days=30)
    read = asyncio.run(
        MailReadHandler(lambda: box, lambda: scope)(_context(), MailReadRequest(message_id="in-1"))
    )
    assert read.folder == "Inbox"  # type: ignore[attr-defined]


def test_agent_mode_reads_an_inbox_message(tmp_path: Path) -> None:
    mode, _, mail, _, _, _ = _mail(tmp_path)
    _, box = _outlook()
    mail._reader = lambda: box
    run = mode.begin("s1", "claude_code")
    presser = _press(mode.open_cards, "allow_session")
    found = _call(mode, run, "outlook_search", {})
    presser.join()
    # Outlook lists a folder's own items; a subfolder is read by its id.
    assert [item["message_id"] for item in found["messages"]] == ["in-1"]
    read = _call(mode, run, "outlook_read", {"message_id": "in-1"})
    assert read["ok"], read
    assert read["message"]["folder"] == "Inbox"
    nested = _call(mode, run, "outlook_read", {"message_id": "in-2"})
    assert nested["ok"] and nested["message"]["folder"] == "Inbox/Projects"
    assert _call(mode, run, "outlook_read", {"message_id": "pst-1"})["code"] == "message_unknown"


def test_signature_harvest_reads_inbox_mail_through_outlook(tmp_path: Path) -> None:
    namespace, box = _outlook()
    namespace.mail(
        "in-3",
        namespace.inbox,
        "lee@example.com",
        BODY.format(name="李大華", title="工程師", ext="1"),
    )
    bridge = _bridge(tmp_path, mail=box, model=SignatureModel())  # type: ignore[arg-type]
    harvested = _run(bridge, "harvest-signatures", {"domain": "example.com"})
    assert harvested.status == "succeeded", harvested.failure
    assert {item["name"] for item in harvested.data["candidates"]} == {"王小明", "李大華"}
    assert harvested.data["skipped"] == []


def _outlook_running() -> Any:
    if sys.platform != "win32":
        return None
    try:
        import win32com.client

        return win32com.client.GetActiveObject("Outlook.Application")
    except Exception:
        return None


@pytest.mark.skipif(_outlook_running() is None, reason="Outlook is not running on this computer")
def test_live_outlook_list_and_get_agree_on_the_inbox_folder() -> None:
    """Read only, against the real Outlook: one Inbox message's folder from
    `list` and from `get`. Only the folder strings are compared; the
    subject and body are never printed."""
    box = OutlookComMailbox(dispatch=_outlook_running())
    listed = box.list("Inbox", NOW - timedelta(days=365), 1)
    if not listed:
        pytest.skip("the Inbox has no message in the last year")
    got = box.get(listed[0].message_id)
    assert (listed[0].folder, got.folder) == ("Inbox", "Inbox")
