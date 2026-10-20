"""`LoanBridge`: this computer's Outlook and Edge answering the source jobs' calls.

Outlook is a fake reader and `RecordingDraftWriter`, or a fake COM object
model for the two new Outlook verbs (HTML listing, reply draft); nothing
reaches a real mailbox and nothing is ever sent. One test drives a real
headless Edge against a page this test serves itself, to check that the
source's Playwright selectors, typing and Enter work through DevTools; the
real loan portal and C4C are on the owner's checklist, not here.
"""

from __future__ import annotations

import threading
from collections.abc import Iterator, Sequence
from datetime import UTC, datetime
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from typing import Any

import pytest

from capabilities.loan_reply import process
from capabilities.loan_reply.bridge import LoanBridge
from capabilities.loan_reply.bridge_api import BridgeClientError, BridgeUnavailable
from integrations.browser import Browser, BrowserError, browser_path
from integrations.outlook_draft import (
    DraftError,
    MailDraft,
    OutlookComDraft,
    RecordingDraftWriter,
    ReplyDraft,
)
from integrations.outlook_mail import MailBody, MailError, OutlookComMailbox


class FakeMailbox:
    def __init__(self, error: str = "") -> None:
        self.error = error
        self.asked: list[tuple[str, datetime, int]] = []

    def list_bodies(self, folder: str, since: datetime, limit: int) -> Sequence[MailBody]:
        if self.error:
            raise MailError(self.error)  # type: ignore[arg-type]
        self.asked.append((folder, since, limit))
        return [
            MailBody(
                message_id="E1",
                subject="簽核通知--(x)",
                sender="workflow@rohde-schwarz.com",
                received=datetime(2026, 10, 20, 1, 0, tzinfo=UTC),
                html_body='<a href="https://p/FastView.aspx">DR26270135</a>',
            )
        ]


class FakeBrowser:
    """Records what the bridge asks of a browser."""

    def __init__(self, profile: Path, *, headless: bool = True, fail: str = "") -> None:
        self.profile = profile
        self.headless = headless
        self.fail = fail
        self.started = self.closed = 0
        self.expressions: list[str] = []
        self.navigated: list[str] = []
        self.inputs: list[tuple[str, dict[str, Any]]] = []
        self.answers: dict[str, Any] = {}
        self.navigation_error = ""

    def start(self) -> None:
        if self.fail:
            raise BrowserError(self.fail)  # type: ignore[arg-type]
        self.started += 1

    def close(self) -> None:
        self.closed += 1

    def navigate(self, url: str, *, settle_s: float = 1.0) -> None:
        if self.navigation_error:
            raise BrowserError("navigation_failed", self.navigation_error)
        self.navigated.append(url)

    def evaluate(self, expression: str) -> Any:
        self.expressions.append(expression)
        for needle, answer in self.answers.items():
            if needle in expression:
                return answer
        return True

    def screenshot(self, where: Path) -> Path:
        return where

    def page(self) -> Any:
        browser = self

        class Page:
            def call(self, method: str, **params: Any) -> dict[str, Any]:
                browser.inputs.append((method, params))
                return {}

        return Page()


def _bridge(tmp_path: Path, **kw: Any) -> tuple[LoanBridge, RecordingDraftWriter, list[Any]]:
    writer = RecordingDraftWriter()
    made: list[Any] = []

    def browser(profile: Path, *, headless: bool) -> Any:
        made.append(FakeBrowser(profile, headless=headless, fail=kw.get("fail", "")))
        return made[-1]

    bridge = LoanBridge(
        tmp_path,
        mailbox=lambda: kw.get("mailbox", FakeMailbox()),
        drafts=lambda: writer,
        replies=lambda: writer,
        browser=browser,
        headless=True,
    )
    return bridge, writer, made


# -- mail -------------------------------------------------------------------------


def test_the_mail_list_has_the_source_bridges_shape(tmp_path: Path) -> None:
    box = FakeMailbox()
    bridge, _writer, _made = _bridge(tmp_path, mailbox=box)
    listed = bridge.email_list(folder="Inbox", limit=50, since="2026-10-01T00:00:00")
    (message,) = listed["messages"]
    assert message["entryId"] == "E1" and message["senderEmail"] == "workflow@rohde-schwarz.com"
    assert "FastView.aspx" in message["htmlBody"]
    # Naive local time, as the source compared it.
    received = datetime.fromisoformat(message["receivedTime"])
    assert received.tzinfo is None
    assert received == datetime(2026, 10, 20, 1, 0, tzinfo=UTC).astimezone().replace(tzinfo=None)
    folder, since, limit = box.asked[0]
    assert (folder, limit) == ("Inbox", 50) and since.tzinfo is not None


def test_no_outlook_is_unavailable_and_other_mail_failures_are_errors(tmp_path: Path) -> None:
    bridge, _w, _m = _bridge(tmp_path, mailbox=FakeMailbox("outlook_missing"))
    with pytest.raises(BridgeUnavailable):
        bridge.email_list(folder="Inbox")
    bridge, _w, _m = _bridge(tmp_path, mailbox=FakeMailbox("folder_unknown"))
    with pytest.raises(BridgeClientError):
        bridge.email_list(folder="Nope")


def test_drafts_and_replies_are_saved_and_a_send_is_refused(tmp_path: Path) -> None:
    shot = tmp_path / "shot.png"
    shot.write_bytes(b"png")
    bridge, writer, _made = _bridge(tmp_path)
    saved = bridge.email_draft(
        to=["ops@example.com"], subject="C4C 找不到客戶", body="第一行\n\n<第二行>", send=False
    )
    assert saved["sent"] is False and saved["to"] == ["ops@example.com"]
    (draft,) = writer.drafts
    assert draft.html_body == "<p>第一行<br><br>&lt;第二行&gt;</p>"
    reply = bridge.post(
        "/email/reply",
        {"entryId": "E1", "body": "您好", "attachments": [{"path": str(shot)}], "send": False},
    )
    assert reply["to"] == ["sender-of-E1@example.com"] and reply["attachments"] == ["shot.png"]
    assert writer.replies[0].text_body == "您好"
    for asked in (
        lambda: bridge.email_draft(to=["a@b.c"], subject="s", body="b", send=True),
        lambda: bridge.post("/email/reply", {"entryId": "E1", "body": "x", "send": True}),
    ):
        with pytest.raises(BridgeClientError, match="SEND_REFUSED"):
            asked()
    assert len(writer.drafts) == 1 and len(writer.replies) == 1


def test_a_reply_draft_through_outlook_is_saved_and_read_back_never_sent() -> None:
    class Attachments:
        def __init__(self) -> None:
            self.files: list[str] = []

        @property
        def Count(self) -> int:  # noqa: N802 - Outlook's spelling
            return len(self.files)

        def Add(self, path: str) -> None:  # noqa: N802
            self.files.append(path)

        def Item(self, index: int) -> Any:  # noqa: N802
            return type("A", (), {"FileName": Path(self.files[index - 1]).name})()

    class Item:
        def __init__(self) -> None:
            self.Body = "> quoted original"
            self.To, self.CC, self.Subject = "Workflow System", "", "RE: 簽核通知"
            self.EntryID, self.Parent = "DRAFT-1", type("P", (), {"Name": "Drafts"})()
            self.Attachments = Attachments()
            self.saves = 0

        def Save(self) -> None:  # noqa: N802
            self.saves += 1

    reply = Item()

    class Original:
        def Reply(self) -> Item:  # noqa: N802
            return reply

    namespace = type("N", (), {"GetItemFromID": lambda self, entry: Original()})()
    outlook = type("O", (), {"GetNamespace": lambda self, name: namespace})()
    receipt = OutlookComDraft(dispatch=outlook).reply(ReplyDraft(entry_id="E1", text_body="您好"))
    assert reply.Body == "您好\r\n\r\n> quoted original"
    assert receipt.entry_id == "DRAFT-1" and receipt.to == ("Workflow System",)
    assert receipt.subject == "RE: 簽核通知" and reply.saves == 2
    assert not hasattr(reply, "sent")
    with pytest.raises(DraftError, match="attachment_missing"):
        OutlookComDraft(dispatch=outlook).reply(
            ReplyDraft(entry_id="E1", text_body="x", attachments=("C:/nope.png",))
        )
    # The draft module's own promise still holds with the new verb.
    RecordingDraftWriter().save(MailDraft(subject="s", html_body="<p>b</p>"))


def test_html_listing_reads_the_smtp_sender_of_an_exchange_mail() -> None:
    class Item:
        Class = 43
        EntryID, Subject, Body = "E1", "簽核通知--(x)", "text"
        HTMLBody = '<a href="https://p/FastView.aspx">DR26270135</a>'
        SenderEmailType = "EX"
        SenderEmailAddress = "/O=EXCHANGELABS/OU=X/CN=RECIPIENTS/CN=WORKFLOW"
        ReceivedTime = datetime(2026, 10, 20, 9, tzinfo=UTC)
        PropertyAccessor = type(
            "PA", (), {"GetProperty": lambda self, tag: "workflow@rohde-schwarz.com"}
        )()

    class Restricted:
        def __init__(self) -> None:
            self.items = [Item()]

        def GetFirst(self) -> Any:  # noqa: N802
            return self.items.pop(0) if self.items else None

        def GetNext(self) -> Any:  # noqa: N802
            return self.items.pop(0) if self.items else None

    class Items:
        def Sort(self, *_a: Any) -> None:  # noqa: N802
            return None

        def Restrict(self, _filter: str) -> Restricted:  # noqa: N802
            return Restricted()

    inbox = type("F", (), {"Items": Items()})()
    namespace = type("N", (), {"GetDefaultFolder": lambda self, number: inbox})()
    outlook = type("O", (), {"GetNamespace": lambda self, name: namespace})()
    (found,) = OutlookComMailbox(dispatch=outlook).list_bodies(
        "Inbox", datetime(2026, 10, 1, tzinfo=UTC), 10
    )
    assert found.sender == "workflow@rohde-schwarz.com"
    assert found.html_body.startswith("<a href=")


# -- browser ------------------------------------------------------------------------


def test_one_browser_per_profile_and_the_sign_in_is_the_profiles(tmp_path: Path) -> None:
    bridge, _w, made = _bridge(tmp_path)
    bridge.open_profile("loan", None)
    first = bridge.browser_open(profile="loan", connectCdpUrl="http://127.0.0.1:9223")
    second = bridge.browser_open(profile="loan")
    assert first["sessionId"] != second["sessionId"] and len(made) == 1
    assert made[0].profile == tmp_path / "loan-reply" / "edge" / "loan" and made[0].headless
    bridge.browser_goto(first["sessionId"], "https://rstw-portal.rsint.net/FlowSingle.aspx")
    assert made[0].navigated == ["https://rstw-portal.rsint.net/FlowSingle.aspx"]
    bridge.close_profile("loan")
    assert made[0].closed == 1
    with pytest.raises(BridgeClientError):
        bridge.browser_goto(first["sessionId"], "https://x")


def test_a_missing_browser_hands_back_and_an_aborted_navigation_reads_as_a_race(
    tmp_path: Path,
) -> None:
    bridge, _w, _made = _bridge(tmp_path, fail="browser_missing")
    with pytest.raises(BridgeUnavailable):
        bridge.open_profile("c4c", None)
    bridge, _w, made = _bridge(tmp_path)
    session = bridge.browser_open(profile="loan")["sessionId"]
    made[0].navigation_error = "net::ERR_ABORTED"
    with pytest.raises(BridgeClientError) as raised:
        bridge.browser_goto(session, "https://rstw-portal.rsint.net/FastView.aspx")
    assert process.is_navigation_race(raised.value)


def test_scripts_run_with_their_arguments_and_selectors_wait_for_the_element(
    tmp_path: Path,
) -> None:
    bridge, _w, made = _bridge(tmp_path)
    session = bridge.browser_open(profile="c4c")["sessionId"]
    browser = made[0]
    browser.answers = {"location.href": "https://x/FlowSingle.aspx"}
    got = bridge.post("/browser/eval", {"sessionId": session, "script": process.URL_JS, "args": []})
    assert got == {"result": "https://x/FlowSingle.aspx"}
    assert browser.expressions[-1] == f"({process.URL_JS})(...[])"
    bridge.post(
        "/browser/fill",
        {"sessionId": session, "selector": process.SEARCH_FIELD, "value": "*130895*"},
    )
    bridge.post(
        "/browser/press", {"sessionId": session, "selector": process.SEARCH_FIELD, "value": "Enter"}
    )
    assert ("Input.insertText", {"text": "*130895*"}) in browser.inputs
    keys = [
        params["type"] for method, params in browser.inputs if method == "Input.dispatchKeyEvent"
    ]
    assert keys == ["keyDown", "keyUp"]
    browser.answers = {"__aepLoanTarget = el": None}
    with pytest.raises(BridgeClientError, match="TIMEOUT"):
        bridge.post("/browser/click", {"sessionId": session, "selector": "#nope", "timeoutMs": 1})


HAVE_BROWSER = browser_path() is not None

PAGE = """<!doctype html><html><head><meta charset="utf-8"><title>Fake C4C</title></head><body>
<div><span class="sapMText">Customers</span></div>
<a href="#" onclick="document.title='accounts';return false">Accounts</a>
<a href="#" onclick="document.title='first';return false">Row</a>
<a href="#" onclick="document.title='second';return false">Row</a>
<div><span>客戶名稱：</span><input type="text" value="130895,BTL Inc."></div>
<input id="x-searchField-I"
  onkeydown="if(event.key==='Enter'){document.title='searched:'+this.value}">
<div><button onclick="document.title='details'"><span>Details</span></button></div>
</body></html>"""


@pytest.fixture
def served(tmp_path: Path) -> Iterator[str]:
    (tmp_path / "site").mkdir()
    (tmp_path / "site" / "c4c.html").write_text(PAGE, encoding="utf-8")
    directory = str(tmp_path / "site")

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args: object, **kwargs: object) -> None:
            super().__init__(*args, directory=directory, **kwargs)  # type: ignore[arg-type]

        def log_message(self, *args: object) -> None:
            return None

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}/c4c.html"
    finally:
        server.shutdown()
        server.server_close()


@pytest.mark.skipif(not HAVE_BROWSER, reason="no Chromium browser is installed on this machine")
def test_the_source_selectors_work_in_a_real_browser(tmp_path: Path, served: str) -> None:
    def browser(profile: Path, *, headless: bool) -> Browser:
        return Browser(profile, headless=True, timeout_s=60)

    writer = RecordingDraftWriter()
    bridge = LoanBridge(
        tmp_path / "ws",
        mailbox=lambda: FakeMailbox(),
        drafts=lambda: writer,
        replies=lambda: writer,
        browser=browser,
        headless=True,
    )
    try:
        bridge.open_profile("c4c", served)
        session = bridge.browser_open(profile="c4c")["sessionId"]
        page = process._Page(bridge, session, lambda _m: None, 0)

        def title() -> str:
            return str(page.eval("() => document.title"))

        page.click(process.NAV_ACCOUNTS)
        assert title() == "accounts"
        page.click('a:text-is("Row") >> nth=1')
        assert title() == "second"
        page.click(process.DETAILS_TAB)
        assert title() == "details"
        page.fill(process.SEARCH_FIELD, "*130895*")
        page.press(process.SEARCH_FIELD, "Enter")
        assert title() == "searched:*130895*"
        assert page.click(process.NAV_CUSTOMERS) is True
        fields = page.eval(process.READ_FORM_FIELDS)
        assert fields["客戶名稱"] == "130895,BTL Inc."
        shot = page.screenshot(tmp_path / "shots" / "s.png")
        assert shot is not None and Path(shot).is_file()
    finally:
        bridge.close()
