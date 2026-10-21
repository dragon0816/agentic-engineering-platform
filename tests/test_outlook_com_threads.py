"""COM is initialised on the thread that uses it (live test 2026-10-20).

After an Agent Web restart the first signature harvest worked and every later
mail call failed with `handler_error`: `Dispatch("Outlook.Application")` on a
worker of `asyncio.to_thread` raised CO_E_NOTINITIALIZED, because only the
thread that first imported pywin32 had COM initialised, and the error escaped
`OutlookComMailbox.list()` / `get()` unmapped.

The fake here behaves like COM: creating Outlook, or using it, on a thread
where COM is not initialised raises CO_E_NOTINITIALIZED, and an object made
on one thread refuses calls from another (RPC_E_WRONG_THREAD). The real
CoInitialize / CoUninitialize are replaced by a per-thread counter, so the
tests run alike with or without pywin32.
"""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from test_outlook_mail_folders import FakeNamespace, FakeOutlook

from integrations import com
from integrations.outlook_draft import DraftError, MailDraft, OutlookComDraft
from integrations.outlook_mail import MailError, OutlookComMailbox
from integrations.outlook_send import OutlookComDraftSender, SendError

NOW = datetime.now(UTC)
RPC_E_WRONG_THREAD = -2147417842


class FakeComError(Exception):
    def __init__(self, hresult: int) -> None:
        self.hresult = hresult
        super().__init__(hresult)


class Apartments:
    """COM's per-thread state, as the fake sees it."""

    def __init__(self) -> None:
        self.local = threading.local()
        self.initialised_on: set[int] = set()
        self.balanced = True

    def depth(self) -> int:
        return int(getattr(self.local, "depth", 0))

    def initialise(self) -> bool:
        self.local.depth = self.depth() + 1
        self.initialised_on.add(threading.get_ident())
        return True

    def uninitialise(self) -> None:
        if self.depth() <= 0:
            self.balanced = False
        self.local.depth = self.depth() - 1

    def require(self) -> None:
        if self.depth() <= 0:
            raise FakeComError(com.CO_E_NOTINITIALIZED)


class ThreadBound:
    """Wraps a fake COM object: usable only on the thread that made it, and
    only while COM is initialised there."""

    def __init__(self, inner: Any, apartments: Apartments) -> None:
        self._inner, self._apartments = inner, apartments
        self._thread = threading.get_ident()

    def __getattr__(self, name: str) -> Any:
        self._apartments.require()
        if threading.get_ident() != self._thread:
            raise FakeComError(RPC_E_WRONG_THREAD)
        return getattr(self._inner, name)


@pytest.fixture
def apartments(monkeypatch: pytest.MonkeyPatch) -> Iterator[Apartments]:
    state = Apartments()
    monkeypatch.setattr(com, "_co_initialize", state.initialise)
    monkeypatch.setattr(com, "_co_uninitialize", state.uninitialise)
    yield state


def _connect(namespace: FakeNamespace, apartments: Apartments) -> Callable[[], Any]:
    def connect() -> Any:
        apartments.require()  # Dispatch itself fails on an uninitialised thread
        return ThreadBound(FakeOutlook(namespace), apartments)

    return connect


def _namespace() -> FakeNamespace:
    namespace = FakeNamespace()
    namespace.mail("in-1", namespace.inbox, "lead@example.com", "Hello\n\nBest,\nLead")
    return namespace


def _on_two_workers(work: Callable[[], Any]) -> list[tuple[int, Any]]:
    """`work` on two different `asyncio.to_thread` workers at once."""
    barrier = threading.Barrier(2, timeout=5)

    def one() -> tuple[int, Any]:
        barrier.wait()  # both workers are busy, so they are two threads
        return threading.get_ident(), work()

    async def both() -> list[tuple[int, Any]]:
        return list(await asyncio.gather(asyncio.to_thread(one), asyncio.to_thread(one)))

    return asyncio.run(both())


def test_the_mailbox_works_on_two_different_worker_threads(apartments: Apartments) -> None:
    namespace = _namespace()
    box = OutlookComMailbox(connect=_connect(namespace, apartments))
    since = NOW - timedelta(days=30)
    results = _on_two_workers(lambda: [item.message_id for item in box.list("Inbox", since, 5)])
    assert results[0][0] != results[1][0]
    assert [found for _, found in results] == [["in-1"], ["in-1"]]
    # And again, one call after the other, as a second harvest would.
    got = _on_two_workers(lambda: box.get("in-1").folder)
    assert [folder for _, folder in got] == ["Inbox", "Inbox"]
    # Every initialisation was released, on the thread that made it.
    assert apartments.balanced and apartments.depth() == 0
    assert len(apartments.initialised_on) >= 2


def test_a_com_failure_is_a_mail_error_not_an_unmapped_exception(
    apartments: Apartments,
) -> None:
    def broken() -> Any:
        raise FakeComError(com.CO_E_NOTINITIALIZED)

    box = OutlookComMailbox(connect=broken)
    for call in (
        lambda: box.list("Inbox", NOW - timedelta(days=1), 5),
        lambda: box.get("in-1"),
        lambda: box.save_attachment("in-1", "a.txt", Path("unused.txt")),
    ):
        with pytest.raises(MailError) as refused:
            asyncio.run(asyncio.to_thread(call))
        assert refused.value.code == "mail_failed"
    assert apartments.balanced and apartments.depth() == 0


class FakeDraftItem:
    def __init__(self) -> None:
        self.Subject = self.HTMLBody = self.To = self.CC = ""
        self.EntryID = "draft-1"
        self.Parent = type("P", (), {"Name": "Drafts"})()
        self.saved = self.sent = False

    def Save(self) -> None:  # noqa: N802 - Outlook's spelling
        self.saved = True

    def Send(self) -> None:  # noqa: N802
        self.sent = True

    @property
    def Attachments(self) -> Any:  # noqa: N802
        return type("A", (), {"Count": 0})()


class FakeDraftOutlook:
    def __init__(self, item: FakeDraftItem) -> None:
        self.item = item

    def CreateItem(self, kind: int) -> FakeDraftItem:  # noqa: N802
        return self.item

    def GetNamespace(self, name: str) -> Any:  # noqa: N802
        item = self.item
        return type("N", (), {"GetItemFromID": lambda self, entry: item})()


def test_the_draft_writer_and_sender_initialise_com_on_their_thread(
    apartments: Apartments,
) -> None:
    from integrations.outlook_send import draft_fingerprint

    item = FakeDraftItem()

    def connect() -> Any:
        apartments.require()
        return ThreadBound(FakeDraftOutlook(item), apartments)

    writer = OutlookComDraft(connect=connect)
    draft = MailDraft(subject="Weekly", html_body="<p>hi</p>")
    receipts = _on_two_workers(lambda: writer.save(draft).saved)
    assert [saved for _, saved in receipts] == [True, True]
    sender = OutlookComDraftSender(connect=connect)
    fingerprint = draft_fingerprint([""], [""], "Weekly", [])
    asyncio.run(asyncio.to_thread(sender.send, "draft-1", fingerprint))
    assert item.sent
    assert apartments.balanced and apartments.depth() == 0

    def broken() -> Any:
        raise FakeComError(com.CO_E_NOTINITIALIZED)

    with pytest.raises(DraftError) as draft_refused:
        asyncio.run(asyncio.to_thread(OutlookComDraft(connect=broken).save, draft))
    assert draft_refused.value.code == "draft_failed"
    with pytest.raises(SendError) as send_refused:
        asyncio.run(
            asyncio.to_thread(OutlookComDraftSender(connect=broken).send, "draft-1", fingerprint)
        )
    assert send_refused.value.code == "send_failed"


def test_nested_apartments_initialise_once(apartments: Apartments) -> None:
    with com.apartment():
        with com.apartment():
            assert apartments.depth() == 1
        assert apartments.depth() == 1
    assert apartments.depth() == 0 and apartments.balanced


def test_the_excel_run_is_wrapped_in_an_apartment(apartments: Apartments) -> None:
    """The workbook writer holds Excel for a whole run on one worker thread;
    the run is inside one apartment."""
    from capabilities.weekly_report import handlers as weekly

    seen: list[int] = []

    class Handler(weekly.ApplyHandler):
        def __init__(self) -> None:  # no settings needed for this check
            pass

        def _apply(self, plan: Any) -> Any:
            seen.append(apartments.depth())
            return plan

    marker: Any = object()
    assert asyncio.run(asyncio.to_thread(Handler()._apply_in_apartment, marker)) is marker
    assert seen == [1] and apartments.depth() == 0


class FakeComErrorWithText(Exception):
    """As pywintypes.com_error: (hresult, strerror, excepinfo, argerror)."""

    def __init__(self, hresult: int, scode: int) -> None:
        self.hresult = hresult
        excepinfo = (0, "Microsoft Outlook", "Subject: Q3 salary review", None, 0, scode)
        super().__init__(hresult, "Exception occurred.", excepinfo, None)


def test_a_swallowed_com_failure_is_logged_without_mail_content(
    apartments: Apartments, caplog: pytest.LogCaptureFixture
) -> None:
    """#233: a transient `mail_failed` names the exception class and HRESULTs."""
    namespace = _namespace()

    def failing(_: Any) -> Any:
        raise FakeComErrorWithText(-2147352567, -2147221233)

    box = OutlookComMailbox(connect=_connect(namespace, apartments))
    with caplog.at_level("WARNING", logger="integrations.outlook_mail"):
        with pytest.raises(MailError) as refused:
            box._call(failing)
    assert refused.value.code == "mail_failed"
    (record,) = [item for item in caplog.records if item.name == "integrations.outlook_mail"]
    logged = record.getMessage()
    assert record.levelname == "WARNING"
    assert "FakeComErrorWithText" in logged and "stage=call" in logged
    assert "hresult=0x80020009" in logged and "scode=0x8004010F" in logged
    assert "salary" not in logged and "Subject" not in logged and "Exception occurred" not in logged


def test_a_failed_connect_is_logged_once(
    apartments: Apartments, caplog: pytest.LogCaptureFixture
) -> None:
    def broken() -> Any:
        raise FakeComError(com.CO_E_NOTINITIALIZED)

    with caplog.at_level("WARNING", logger="integrations.outlook_mail"):
        with pytest.raises(MailError):
            OutlookComMailbox(connect=broken).get("in-1")
    logged = [item.getMessage() for item in caplog.records]
    assert len(logged) == 1 and "stage=connect" in logged[0] and "FakeComError" in logged[0]
