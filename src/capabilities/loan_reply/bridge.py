"""This computer's Outlook and Edge, spoken to as the source jobs spoke to
the rs_workflow_system Bridge (AEP port).

The ported jobs (`scan`, `process`) call `email_list`, `email_draft`,
`browser_open`/`goto`/`close` and `post("/browser/...")` with the source
Bridge's payloads. `LoanBridge` answers them with AEP's own adapters:

- mail: `integrations.outlook_mail` (read, with HTML) and
  `integrations.outlook_draft` (drafts and reply drafts; **never sends**);
- browser: `integrations.browser.Browser`, one persistent profile per source
  profile name (`loan`, `c4c`) under the host workspace. **Signing in is the
  profile's**: no password is asked for, stored or typed here. The loan portal
  hands sign-in to Entra, whose account picker the job clicks (source
  behaviour); C4C signs in by SSO in its profile.

Playwright selectors the source used (`span.sapMText:text-is("Customers")`,
`text="Details"`, `... >> nth=0`) are resolved by a small page script; keys
and typed text go through DevTools input events. None of this is proven until
the owner's first run on the company PC (docs/phases/RS_WORKFLOW_MIGRATION.md).
"""

from __future__ import annotations

import html
import itertools
import json
import threading
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from capabilities.loan_reply.bridge_api import BridgeClientError, BridgeUnavailable
from integrations.browser import Browser, BrowserError
from integrations.outlook_draft import (
    DraftError,
    DraftWriter,
    MailDraft,
    ReplyDraft,
    ReplyWriter,
    recipients,
)
from integrations.outlook_mail import MailBodyLister, MailError

LogFn = Callable[[str], None]

#: Failures that say nothing about a form: the item goes back to the queue.
_UNAVAILABLE_MAIL = frozenset({"library_missing", "outlook_missing"})
_UNAVAILABLE_BROWSER = frozenset({"browser_missing", "browser_would_not_start", "profile_in_use"})
#: How often an element is looked for while a click or fill waits for it.
_POLL_S = 0.25

#: Find one element by the source's Playwright selector forms: CSS, CSS with
#: `:text-is("…")`, `text="…"`, each optionally `>> nth=N`. Exact, whitespace-
#: collapsed text; visible elements only; the innermost match for text.
_FIND = """
(sel) => {
  const norm = (x) => (x || '').replace(/\\s+/g, ' ').trim();
  let s = sel, nth = null, text = null;
  const n = s.match(/\\s*>>\\s*nth=(\\d+)\\s*$/);
  if (n) { nth = Number(n[1]); s = s.slice(0, n.index); }
  const t = s.match(/^text="(.*)"$/);
  if (t) { text = t[1]; s = '*'; }
  const ti = s.match(/^(.*):text-is\\("(.*)"\\)$/);
  if (ti) { s = ti[1] || '*'; text = ti[2]; }
  let all = [...document.querySelectorAll(s)];
  if (text !== null) {
    all = all.filter((e) => norm(e.innerText || e.textContent) === text);
    all = all.filter((e) => ![...e.children].some((c) => all.includes(c)));
  }
  all = all.filter((e) => e.offsetParent !== null || e.getClientRects().length > 0);
  const el = all[nth === null ? 0 : nth];
  if (!el) return null;
  window.__aepLoanTarget = el;
  el.scrollIntoView({block: 'center'});
  return true;
}
"""


def _call(script: str, *args: Any) -> str:
    """A page expression calling `script` (an arrow function) with `args`."""
    return f"({script})(...{json.dumps(list(args))})"


def _text_to_html(text: str) -> str:
    """The source drafted plain text; `outlook.draft` writes HTML. The words,
    lines and blank lines stay as they were."""
    return "<p>" + html.escape(text).replace("\n", "<br>") + "</p>"


def _since(value: Any) -> datetime:
    raw = str(value or "").strip()
    if not raw:
        # No bound: everything (aware, so no local conversion of 1970 is
        # needed; Windows refuses that one).
        return datetime(2000, 1, 1, tzinfo=UTC)
    moment = datetime.fromisoformat(raw)
    # The source compares naive local times; Outlook is asked in local time.
    return moment if moment.tzinfo else moment.astimezone()


class LoanBridge:
    """One per host; browsers stay open between runs only when the Workflow
    setting says so (`close_browsers_after: false`)."""

    def __init__(
        self,
        workspace: Path,
        *,
        mailbox: Callable[[], MailBodyLister],
        drafts: Callable[[], DraftWriter],
        replies: Callable[[], ReplyWriter],
        browser: Callable[..., Browser] = Browser,
        headless: bool = False,
    ) -> None:
        self.workspace = workspace
        self._mailbox = mailbox
        self._drafts = drafts
        self._replies = replies
        self._browser = browser
        self.headless = headless
        self._browsers: dict[str, Browser] = {}
        self._sessions: dict[str, str] = {}
        self._numbers = itertools.count(1)
        self._lock = threading.RLock()

    # -- mail ---------------------------------------------------------------

    def email_list(self, **kw: Any) -> dict[str, Any]:
        folder = str(kw.get("folder") or "Inbox")
        limit = int(kw.get("limit") or 200)
        try:
            found = self._mailbox().list_bodies(folder, _since(kw.get("since")), limit)
        except MailError as error:
            if error.code in _UNAVAILABLE_MAIL:
                raise BridgeUnavailable(error.code) from None
            raise BridgeClientError(error.code.upper(), error.code) from None
        return {
            "messages": [
                {
                    "entryId": item.message_id,
                    "subject": item.subject,
                    "senderEmail": item.sender,
                    # Naive local time, as the source Bridge listed it.
                    "receivedTime": item.received.astimezone()
                    .replace(tzinfo=None)
                    .isoformat(timespec="seconds"),
                    "body": item.body,
                    "htmlBody": item.html_body,
                }
                for item in found
            ]
        }

    def email_draft(self, **kw: Any) -> dict[str, Any]:
        if kw.get("send"):
            raise BridgeClientError("SEND_REFUSED", "this host only saves drafts")
        to = recipients([str(item) for item in kw.get("to") or []])
        subject = str(kw.get("subject") or "")
        body = str(kw.get("body") or "")
        attachments = tuple(
            str(item["path"]) for item in kw.get("attachments") or [] if item.get("path")
        )
        try:
            receipt = self._drafts().save(
                MailDraft(
                    subject=subject or "(no subject)",
                    html_body=_text_to_html(body or " "),
                    to=to,
                    attachments=attachments,
                )
            )
        except DraftError as error:
            raise self._mail_failure(error) from None
        return {
            "entryId": receipt.entry_id,
            "saved": receipt.saved,
            "sent": False,
            "folder": receipt.folder,
            "to": list(to),
            "cc": [],
            "subject": subject,
            "attachments": [Path(path).name for path in attachments],
        }

    def _reply(self, body: dict[str, Any]) -> dict[str, Any]:
        if body.get("send"):
            raise BridgeClientError("SEND_REFUSED", "this host only saves drafts")
        attachments = tuple(
            str(item["path"]) for item in body.get("attachments") or [] if item.get("path")
        )
        try:
            receipt = self._replies().reply(
                ReplyDraft(
                    entry_id=str(body.get("entryId") or ""),
                    text_body=str(body.get("body") or " "),
                    attachments=attachments,
                )
            )
        except DraftError as error:
            raise self._mail_failure(error) from None
        return {
            "entryId": receipt.entry_id,
            "saved": receipt.saved,
            "sent": False,
            "folder": receipt.folder,
            "inReplyTo": str(body.get("entryId") or ""),
            "to": list(receipt.to),
            "cc": list(receipt.cc),
            "subject": receipt.subject,
            "attachments": list(receipt.attachments),
        }

    @staticmethod
    def _mail_failure(error: DraftError) -> Exception:
        if error.code in _UNAVAILABLE_MAIL:
            return BridgeUnavailable(error.code)
        return BridgeClientError(error.code.upper(), error.code)

    # -- browser ------------------------------------------------------------

    def profile_dir(self, profile: str) -> Path:
        return self.workspace / "loan-reply" / "edge" / profile

    def open_profile(
        self,
        profile: str,
        url: str | None,
        *,
        ready_title: str | None = None,
        ready_timeout: float = 120.0,
        log: LogFn | None = None,
    ) -> None:
        with self._lock:
            browser = self._browsers.get(profile)
            if browser is None:
                browser = self._browser(self.profile_dir(profile), headless=self.headless)
                try:
                    browser.start()
                except BrowserError as error:
                    raise self._browser_failure(error) from None
                self._browsers[profile] = browser
        if url:
            self._navigate(browser, url)
        if ready_title:
            end = time.monotonic() + ready_timeout
            while time.monotonic() < end:
                if ready_title in str(self._evaluate(browser, "document.title") or ""):
                    return
                time.sleep(1.0)
            if log is not None:
                log(f"[loan]   {profile}: the page never showed {ready_title!r}; continuing")

    def close_profile(self, profile: str) -> None:
        with self._lock:
            browser = self._browsers.pop(profile, None)
            for session in [key for key, name in self._sessions.items() if name == profile]:
                del self._sessions[session]
        if browser is not None:
            browser.close()

    def close(self) -> None:
        for profile in list(self._browsers):
            self.close_profile(profile)

    def browser_open(self, **kw: Any) -> dict[str, Any]:
        profile = str(kw.get("profile") or "")
        with self._lock:
            if profile not in self._browsers:
                self.open_profile(profile, None)
            session = f"{profile}-{next(self._numbers)}"
            self._sessions[session] = profile
        return {"sessionId": session}

    def browser_close(self, session_id: str) -> dict[str, Any]:
        with self._lock:
            self._sessions.pop(session_id, None)
        return {}

    def browser_goto(self, session_id: str, url: str, **kw: Any) -> dict[str, Any]:
        self._navigate(self._session(session_id), url)
        return {}

    def _session(self, session_id: str) -> Browser:
        with self._lock:
            profile = self._sessions.get(session_id)
            browser = self._browsers.get(profile or "")
        if browser is None:
            raise BridgeClientError("SESSION_UNKNOWN", f"no browser session {session_id}")
        return browser

    def post(self, path: str, body: dict[str, Any], timeout: int | None = None) -> Any:
        if path == "/email/reply":
            return self._reply(body)
        browser = self._session(str(body.get("sessionId") or ""))
        timeout_s = float(body.get("timeoutMs") or 15000) / 1000
        if path == "/browser/eval":
            script = str(body.get("script") or "")
            return {"result": self._evaluate(browser, _call(script, *body.get("args") or []))}
        if path == "/browser/click":
            self._find(browser, str(body.get("selector") or ""), timeout_s)
            self._evaluate(browser, "(() => { window.__aepLoanTarget.click(); return true; })()")
            return {}
        if path == "/browser/fill":
            self._find(browser, str(body.get("selector") or ""), timeout_s)
            self._evaluate(
                browser,
                "(() => { const e = window.__aepLoanTarget; e.focus();"
                " if (e.select) e.select(); return true; })()",
            )
            self._input(browser, "Input.insertText", text=str(body.get("value") or ""))
            return {}
        if path == "/browser/press":
            self._find(browser, str(body.get("selector") or ""), timeout_s)
            self._evaluate(browser, "(() => { window.__aepLoanTarget.focus(); return true; })()")
            key = str(body.get("value") or "")
            code = 13 if key == "Enter" else 0
            for kind in ("keyDown", "keyUp"):
                self._input(
                    browser,
                    "Input.dispatchKeyEvent",
                    type=kind,
                    key=key,
                    code=key,
                    windowsVirtualKeyCode=code,
                    nativeVirtualKeyCode=code,
                )
            return {}
        if path == "/browser/wait":
            end = time.monotonic() + timeout_s
            while time.monotonic() < end:
                if self._evaluate(browser, "document.readyState") == "complete":
                    return {}
                time.sleep(_POLL_S)
            raise BridgeClientError("TIMEOUT", "the page did not finish loading")
        if path == "/browser/screenshot":
            where = Path(str(body.get("path") or "")) if body.get("path") else None
            if where is None:
                stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
                where = self.workspace / "loan-reply" / "loan-shots" / f"shot-{stamp}.png"
            try:
                written = browser.screenshot(where)
            except BrowserError as error:
                raise self._browser_failure(error) from None
            return {"path": str(written)}
        raise BridgeClientError("NOT_FOUND", f"{path} is not served here")

    def _find(self, browser: Browser, selector: str, timeout_s: float) -> None:
        end = time.monotonic() + timeout_s
        while True:
            if self._evaluate(browser, _call(_FIND, selector)):
                return
            if time.monotonic() >= end:
                raise BridgeClientError("TIMEOUT", f"no visible element for {selector}")
            time.sleep(_POLL_S)

    def _navigate(self, browser: Browser, url: str) -> None:
        try:
            browser.navigate(url, settle_s=0.5)
        except BrowserError as error:
            if error.code == "navigation_failed":
                # The source retries an aborted navigation on Playwright's
                # wording; keep the browser's own reason in the message.
                raise BridgeClientError("INTERNAL", f"Page.goto: {error.detail}") from None
            raise self._browser_failure(error) from None

    def _evaluate(self, browser: Browser, expression: str) -> Any:
        try:
            return browser.evaluate(expression)
        except BrowserError as error:
            if error.code in ("browser_lost", "navigation_failed"):
                # A page replaced under a running script reads as a lost page;
                # the source waits that out as a navigation race.
                raise BridgeClientError(
                    "INTERNAL", f"Execution context was destroyed ({error.code})"
                ) from None
            raise self._browser_failure(error) from None

    @staticmethod
    def _input(browser: Browser, method: str, **params: Any) -> None:
        try:
            browser.page().call(method, **params)
        except BrowserError as error:
            raise BridgeClientError(error.code.upper(), error.code) from None
        except Exception as error:  # noqa: BLE001 - the DevTools socket went away
            raise BridgeClientError("INTERNAL", type(error).__name__) from None

    @staticmethod
    def _browser_failure(error: BrowserError) -> Exception:
        if error.code in _UNAVAILABLE_BROWSER:
            return BridgeUnavailable(error.code)
        return BridgeClientError(error.code.upper(), error.detail or error.code)
