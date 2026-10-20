"""A fake of this computer's Outlook, loan portal and C4C for the loan Workflows.

Shaped like the source tests' `FakeBridge` (tests/test_loan_process_source.py):
page scripts are answered by identity with the job's own constants, so a test
cannot keep passing after the job asks a different question. Nothing here
opens a browser, reads a mailbox, saves a draft or sends anything.
"""

from __future__ import annotations

from typing import Any

from capabilities.loan_reply import process
from capabilities.loan_reply.bridge_api import BridgeClientError, BridgeUnavailable

PORTAL = "https://rstw-portal.rsint.net"
FORM_URL = f"{PORTAL}/FlowSingle.aspx?accessId=abc"
CUSTOMER = "130895,BTL Inc."


def notice(
    borrow: str,
    *,
    entry: str = "",
    kind: str = "簽核通知",
    received: str = "2026-10-20T09:00:00",
    href: str = "",
) -> dict[str, Any]:
    """One message as `email_list` returns it, carrying a FastView link."""
    link = href or f"{PORTAL}/FastView.aspx?action=flow&amp;accessId={borrow}"
    return {
        "entryId": entry or f"mail-{borrow}",
        "subject": f"{kind}--(展示機出借申請單 - 一般 {borrow} )",
        "senderEmail": "workflow@rohde-schwarz.com",
        "receivedTime": received,
        "htmlBody": f'<p>x</p><a href="{link}">{borrow}</a>',
        "body": "",
    }


class FakeLoanHost:
    """Outlook (list, draft, reply) and two browser profiles, recorded."""

    def __init__(
        self,
        *,
        messages: list[dict[str, Any]] | None = None,
        customer: str = CUSTOMER,
        rows: tuple[str, ...] = ("130895 BTL Inc.",),
        blocks: dict[str, Any] | None = None,
        urls: tuple[str, ...] = (FORM_URL,),
        outlook: bool = True,
        browser: bool = True,
    ) -> None:
        self.messages = messages or []
        self.fields = {"客戶名稱": customer, "E-mail": "who@example.com"}
        self.rows = list(rows)
        self.blocks = blocks or {"classificationDeliveryBlock": "", "deliveryBlock": ""}
        self.blocks.setdefault("erpCustomerId", "130895")
        self._urls = list(urls)
        self.outlook = outlook
        self.browser = browser
        self.headless = False
        self.listed: list[dict[str, Any]] = []
        self.drafts: list[dict[str, Any]] = []
        self.replies: list[dict[str, Any]] = []
        self.gotos: list[str] = []
        self.opened_profiles: list[str] = []
        self.closed_profiles: list[str] = []
        self.sent: list[Any] = []

    # -- mail ---------------------------------------------------------------
    def email_list(self, **kw: Any) -> dict[str, Any]:
        if not self.outlook:
            raise BridgeUnavailable("outlook_missing")
        self.listed.append(kw)
        return {"messages": self.messages}

    def email_draft(self, **kw: Any) -> dict[str, Any]:
        if not self.outlook:
            raise BridgeUnavailable("outlook_missing")
        assert kw.get("send") is False, "the job asked to send"
        self.drafts.append(kw)
        return {
            "entryId": f"draft-{len(self.drafts)}",
            "to": list(kw.get("to") or []),
            "subject": kw.get("subject") or "",
            "attachments": [],
        }

    # -- browser ------------------------------------------------------------
    def open_profile(self, profile: str, url: str | None, **_kw: Any) -> None:
        if not self.browser:
            raise BridgeUnavailable("browser_missing")
        self.opened_profiles.append(profile)

    def close_profile(self, profile: str) -> None:
        self.closed_profiles.append(profile)

    def browser_open(self, **kw: Any) -> dict[str, Any]:
        return {"sessionId": f"{kw.get('profile')}-1"}

    def browser_goto(self, session_id: str, url: str, **_kw: Any) -> dict[str, Any]:
        self.gotos.append(url)
        return {}

    def browser_close(self, session_id: str) -> dict[str, Any]:
        return {}

    def post(self, path: str, body: dict[str, Any], timeout: int | None = None) -> Any:
        if path == "/email/reply":
            if not self.outlook:
                raise BridgeUnavailable("outlook_missing")
            assert body.get("send") is False, "the job asked to send"
            self.replies.append(body)
            return {
                "entryId": f"reply-{len(self.replies)}",
                "to": ["workflow@rohde-schwarz.com"],
                "cc": [],
                "subject": f"RE: 簽核通知 {body['entryId']}",
                "attachments": [p["path"].rsplit("/", 1)[-1] for p in body["attachments"]],
            }
        if path == "/browser/eval":
            return {"result": self._eval(body["script"])}
        if path == "/browser/screenshot":
            return {"path": "C:/shots/shot.png"}
        return {}

    def _eval(self, script: str) -> Any:
        if script == process.URL_JS:
            return self._urls.pop(0) if len(self._urls) > 1 else self._urls[0]
        if script == process.BUSY_JS:
            return False
        if script == process.READ_FORM_FIELDS:
            return self.fields
        if script == process.ACCOUNTS_READY:
            return {"adv": True, "view": True}
        if script == process.RESULT_LINKS:
            return self.rows
        if script == process.SCROLL_TO_BLOCKS:
            return True
        if script == process.READ_BLOCKS:
            return self.blocks
        raise BridgeClientError("INTERNAL", f"unexpected script {script[:40]!r}")
