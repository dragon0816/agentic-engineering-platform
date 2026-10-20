"""Parsing rules for the loan-form mails (workflow 06).

The mail is a 簽核通知 (approval notice) for a 展示機出借申請單 (demo-unit loan
form). What makes one actionable is not its subject but a link in its body::

    <a href="https://rstw-portal.rsint.net/FastView.aspx?...accessId=<GUID>">DR26270135</a>

The anchor text is the borrow number and the href opens the form. Everything
here is a pure function over that HTML so it can be tested against saved real
mails without Outlook.

**The borrow number is not always ``DR`` + digits.** The ported script matched
``^DR\\d{6,}$``, which silently dropped two of the three form types in use.
Measured 2026-08-02 over 40 real mails: 24 matched the old pattern, **16 did
not** -- every ``DRHQ…`` (HQ) and ``DRL…`` (專用) form. They are not malformed;
they are ordinary approvals for other loan categories.
"""

from __future__ import annotations

import html as _html
import re
from dataclasses import dataclass
from collections.abc import Iterable, Mapping
from typing import Any

from capabilities.loan_reply import templates

#: ``<a href="...">text</a>``, tolerant of attributes on either side.
_ANCHOR = re.compile(r'(?is)<a\b[^>]*?href\s*=\s*"([^"]*)"[^>]*>(.*?)</a>')

#: A borrow number: ``DR`` then an optional category code then the serial.
#: Observed live: ``DR26270135`` (一般), ``DRHQ26270004`` (HQ), ``DRL26270065``
#: (專用). Anchored so a longer string containing one is not mistaken for it.
BORROW_NO = re.compile(r"^(DR[A-Z]*\d{6,})$")

#: Category codes seen in the wild, for reporting and optional filtering. An
#: unknown code is still processed -- a new loan category must not be dropped
#: just because this list has not caught up. Measured 2026-08-03 over 118 forms:
#: 一般 58, 專用 38, S 13 (nobody knew this one existed), HQ 7.
KNOWN_CATEGORIES: dict[str, str] = {
    "": "一般",
    "HQ": "HQ",
    "L": "專用",
    "S": "S",
}

#: The subject's prefix, before ``--(``. Measured over the same 118 forms:
#: 簽核通知 106, 否決 12 -- and nothing else.
APPROVAL_NOTICE = "簽核通知"
REJECTION_NOTICE = "否決"

_NOTICE_KIND = re.compile(r"^\s*(.*?)\s*--\s*\(")


def notice_kind(subject: str) -> str:
    """``簽核通知`` / ``否決`` / ``""`` when the subject has no prefix."""
    m = _NOTICE_KIND.match(subject or "")
    return m.group(1).strip() if m else ""


@dataclass(frozen=True)
class LoanMail:
    """One actionable loan-form mail."""

    entry_id: str
    borrow_no: str
    loan_url: str
    subject: str
    sender_smtp: str
    received: str | None

    @property
    def category_code(self) -> str:
        m = re.match(r"^DR([A-Z]*)\d", self.borrow_no)
        return m.group(1) if m else ""

    @property
    def category(self) -> str:
        return KNOWN_CATEGORIES.get(self.category_code, self.category_code or "?")

    @property
    def notice(self) -> str:
        return notice_kind(self.subject)

    @property
    def is_rejection(self) -> bool:
        """A 否決 notice: the form was turned down.

        Two independent reasons never to process one. It must not produce a
        "your instrument is on its way" reply, and its approval view does not
        even open -- the portal answers ``ErrorPage.aspx?errmsg=Object
        reference not set to an instance of an object``, which is what a
        rejected form looks like from the outside.
        """
        return self.notice == REJECTION_NOTICE

    def as_dict(self) -> dict[str, Any]:
        return {
            "entryId": self.entry_id,
            "borrowNo": self.borrow_no,
            "loanUrl": self.loan_url,
            "subject": self.subject,
            "senderSmtp": self.sender_smtp,
            "received": self.received,
            "categoryCode": self.category_code,
            "category": self.category,
            "notice": self.notice,
        }


def _anchor_text(inner_html: str) -> str:
    """Visible text of an anchor: tags stripped, entities decoded, collapsed."""
    text = re.sub(r"(?s)<[^>]+>", "", inner_html)
    return re.sub(r"\s+", " ", _html.unescape(text)).strip()


def normalise_href(href: str) -> str:
    """Undo the entity escaping Outlook leaves in ``href`` attributes.

    ``&amp;`` in the stored HTML would otherwise reach the browser literally and
    the portal would see one malformed parameter instead of three.
    """
    return _html.unescape(href or "").strip()


def find_loan_link(body_html: str) -> tuple[str, str] | None:
    """``(borrow_no, loan_url)`` from the first FastView anchor, or ``None``.

    The FastView check is on the href and the borrow-number check on the link
    text; both must hold. A mail can carry other links (footers, signatures),
    so the pair is what identifies the real one.
    """
    for href, inner in _ANCHOR.findall(body_html or ""):
        if "fastview.aspx" not in href.lower():
            continue
        m = BORROW_NO.match(_anchor_text(inner))
        if m:
            return m.group(1), normalise_href(href)
    return None


def parse_mail(
    message: Mapping[str, Any],
    body_html: str,
) -> LoanMail | None:
    """Turn one Outlook message into a :class:`LoanMail`, or ``None``.

    ``None`` means "not a loan form" -- the ordinary case for most of an inbox,
    not an error.
    """
    found = find_loan_link(body_html)
    if not found:
        return None
    borrow_no, loan_url = found
    return LoanMail(
        entry_id=str(message.get("entryId") or ""),
        borrow_no=borrow_no,
        loan_url=loan_url,
        subject=str(message.get("subject") or ""),
        sender_smtp=str(message.get("senderEmail") or message.get("sender") or ""),
        # `/email/list` calls it receivedTime; `inspect_item` uses receivedAt.
        # Accept either so the parser works against both shapes.
        received=message.get("receivedTime") or message.get("receivedAt"),
    )


def accepts_sender(mail: LoanMail, expected: str | None, require: bool) -> bool:
    """Whether the sender gate lets this mail through.

    Off by default: the approval notices arrive from a workflow mailbox whose
    address differs between the HQ and local systems, and rejecting on a guess
    would drop real work silently.
    """
    if not require:
        return True
    if not expected:
        return True
    return mail.sender_smtp.strip().lower() == expected.strip().lower()


# ---------------------------------------------------------------------------
# What the portal and C4C say, and what to write back
# ---------------------------------------------------------------------------

#: The loan form writes the customer as ``<id>,<name>``, e.g. ``130895,BTL Inc.``
#: (read from field ``combosvw-1025-inputEl`` on 2026-08-03). Both separators
#: appear in the wild.
_CUSTOMER_SPLIT = re.compile(r"[,，]")


def split_customer(raw: str) -> tuple[str, str]:
    """``"130895,BTL Inc."`` -> ``("130895", "BTL Inc.")``.

    Returns ``("", raw)`` when there is no separator, so a form filled in some
    other shape still carries its text forward instead of silently becoming an
    empty id.
    """
    parts = _CUSTOMER_SPLIT.split(raw or "", 1)
    if len(parts) == 2:
        return parts[0].strip(), parts[1].strip()
    return "", (raw or "").strip()


@dataclass(frozen=True)
class BlockStatus:
    """What C4C says about a customer's delivery blocks."""

    found: bool
    classification_delivery_block: str = ""
    delivery_block: str = ""
    reason: str = ""

    @property
    def blocked(self) -> bool:
        """Either field carrying any value means blocked.

        Deliberately "any value", not a comparison against a known list: a block
        code nobody has seen before still means the customer cannot receive an
        instrument, and treating it as clear would send exactly the wrong reply.
        """
        return bool(
            (self.classification_delivery_block or "").strip()
            or (self.delivery_block or "").strip()
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "found": self.found,
            "blocked": self.blocked if self.found else None,
            "classificationDeliveryBlock": self.classification_delivery_block,
            "deliveryBlock": self.delivery_block,
            "reason": self.reason,
        }


#: Re-exported so existing callers and tests keep working; the text itself now
#: lives in `_loan_templates`, which is what an installation can override.
SIGNATURE = templates.SIGNATURE
NO_VALUE = templates.NO_VALUE

TemplateError = templates.TemplateError


def reply_context(borrow_no: str, **extra: Any) -> dict[str, Any]:
    """The values every message template can use.

    Built in one place so a template that works in one message does not fail in
    another because that call site happened to pass fewer things.
    """
    ctx: dict[str, Any] = {
        "borrowNo": borrow_no,
        "borrowNoOrUnknown": borrow_no or "(未知單號)",
        "signature": SIGNATURE,
        "category": "",
        "customerRaw": "",
        "customerId": "",
        "customerName": "",
        "customerEmail": "",
        "loanUrl": "",
    }
    ctx.update({k: v for k, v in extra.items() if v is not None})
    return ctx


def blocked_reply(borrow_no: str, status: BlockStatus, **extra: Any) -> str:
    """The customer-facing reply when delivery is blocked.

    An empty block field renders as NO_VALUE rather than as nothing: "配送限制："
    followed by a blank reads like a bug in the mail, and the screenshot is
    where the real answer is anyway.
    """
    ctx = reply_context(borrow_no, **extra)
    ctx["classificationDeliveryBlock"] = (
        (status.classification_delivery_block or "").strip() or NO_VALUE)
    ctx["deliveryBlock"] = (status.delivery_block or "").strip() or NO_VALUE
    return templates.render("blocked-reply", ctx, extra.get("templateDir"))


def shipping_reply(borrow_no: str, **extra: Any) -> str:
    return templates.render(
        "shipping-reply", reply_context(borrow_no, **extra), extra.get("templateDir"))


#: Why a C4C lookup produced no answer. Each is a *different* thing to go and
#: check, so they are kept apart rather than flattened into one "not found".
REASON_NO_ACCOUNT = "no-account-matched-in-c4c"
REASON_FIELDS_UNREADABLE = "delivery-block-fields-not-readable"
REASON_WRONG_ACCOUNT = "wrong-account-opened"

_REASON_TEXT = {
    REASON_NO_ACCOUNT: (
        "此 customerId 在 C4C Accounts 搜尋不到，無法查詢 Delivery Block。\n"
        "請確認出借系統上的客戶編號是否正確、或該客戶是否尚未建在 C4C。"
    ),
    REASON_FIELDS_UNREADABLE: (
        "已開啟 C4C 帳戶頁面，但頁面上找不到 Classification Delivery Block / "
        "Delivery Block 這兩個欄位，因此無法判斷是否被 block。\n"
        "常見原因是 C4C 版面調整。這種情況一律不自動回信 —— 讀不到不等於沒有限制。"
    ),
    REASON_WRONG_ACCOUNT: (
        "搜尋結果開啟的帳戶，其 ERP Customer ID 與單據上的 customerId 不一致，已中止。\n"
        "自動回信有可能寄出別的客戶的狀態，所以這裡寧可停下來。"
    ),
}

_REASON_SUBJECT = {
    REASON_NO_ACCOUNT: "C4C 找不到客戶",
    REASON_FIELDS_UNREADABLE: "C4C 讀不到 Delivery Block 欄位",
    REASON_WRONG_ACCOUNT: "C4C 開到不符的帳戶",
}


def customer_not_found_notice(
    borrow_no: str, customer_raw: str, customer_id: str, loan_url: str,
    reason: str = "", **extra: Any
) -> tuple[str, str]:
    """Internal notice when C4C gave no usable answer about this customer.

    A separate outcome from "not blocked" on purpose: without a reading there is
    no evidence either way, and replying "on its way" would assert something
    nobody checked.
    """
    ctx = reply_context(borrow_no, customerRaw=customer_raw, customerId=customer_id,
                        loanUrl=loan_url, **extra)
    ctx["reason"] = reason
    ctx["reasonHeadline"] = _REASON_SUBJECT.get(reason, _REASON_SUBJECT[REASON_NO_ACCOUNT])
    ctx["reasonDetail"] = _REASON_TEXT.get(reason, _REASON_TEXT[REASON_NO_ACCOUNT])
    where = extra.get("templateDir")
    return (templates.render("customer-not-found-subject", ctx, where),
            templates.render("customer-not-found-body", ctx, where))


def failure_notice(borrow_no: str, loan_url: str, error: str,
                   **extra: Any) -> tuple[str, str, list[str]]:
    """The internal notice for a form the automation could not finish.

    Returns ``(subject, body, warnings)``. Unlike the other messages this one
    tolerates a broken override and falls back to the built-in text, because
    this is the notice that *reports* a broken template -- if it could fail the
    same way, the one message able to explain the problem would be the one
    message that never gets written.
    """
    ctx = reply_context(borrow_no, loanUrl=loan_url, error=error, **extra)
    where = extra.get("templateDir")
    subject, w1 = templates.render_or_default("failure-subject", ctx, where)
    body, w2 = templates.render_or_default("failure-body", ctx, where)
    return subject, body, [w for w in (w1, w2) if w]


def accepts_category(mail: LoanMail, exclude: Iterable[str] | None) -> bool:
    """Whether the category filter lets this mail through.

    Empty/absent means "every category", which is the point of widening the
    borrow-number pattern in the first place.
    """
    blocked = {c.strip().upper() for c in (exclude or []) if str(c).strip()}
    return mail.category_code.upper() not in blocked
