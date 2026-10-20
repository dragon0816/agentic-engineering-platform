# Vendored oracle: rs_workflow_system@896046e8 host-bridge/tests/test_loan_rules.py; only tests/loan_oracle.py REPLACEMENTS differ.
"""Parsing rules for the loan-approval mails (workflow 06).

Every number quoted here was measured against the live inbox on 2026-08-03:
400 messages, 118 of them loan forms.
"""

from __future__ import annotations

import pytest

from capabilities.loan_reply import rules

PORTAL = "https://rstw-portal.rsint.net/FastView.aspx"


def anchor(text: str, href: str = f"{PORTAL}?action=flow&amp;groupid=RSTWP&amp;accessId=abc") -> str:
    return f'<html><body><p>x</p><a href="{href}">{text}</a></body></html>'


def message(subject: str, entry_id: str = "0001") -> dict:
    return {"entryId": entry_id, "subject": subject,
            "senderEmail": "workflow@rohde-schwarz.com", "receivedTime": "2026-08-01T09:00:00"}


class TestBorrowNumber:
    """The ported rule was ``^DR\\d{6,}$`` and matched 66 of 118 forms.

    The other 52 were not malformed -- they were the HQ, 專用 and S loan
    categories, whose numbers carry a letter code between ``DR`` and the serial.
    """

    @pytest.mark.parametrize(
        "borrow_no, category",
        [
            ("DR26270135", "一般"),
            ("DRHQ26270004", "HQ"),
            ("DRL26270065", "專用"),
            ("DRS26270011", "S"),
        ],
    )
    def test_every_live_category_is_recognised(self, borrow_no, category):
        mail = rules.parse_mail(message("簽核通知--(展示機出借申請單)"), anchor(borrow_no))
        assert mail is not None, f"{borrow_no} was not recognised"
        assert mail.borrow_no == borrow_no
        assert mail.category == category

    def test_an_unknown_category_is_still_processed(self):
        """A new loan category must not vanish because this list is behind.

        `S` existed in production and nobody knew; the rule has to survive the
        next one too.
        """
        mail = rules.parse_mail(message("簽核通知--(x)"), anchor("DRZZ26270001"))
        assert mail is not None
        assert mail.category_code == "ZZ"
        assert mail.category == "ZZ"

    @pytest.mark.parametrize("text", ["DR1234", "XX26270135", "DR", "26270135", "DR-26270135"])
    def test_non_borrow_numbers_are_not_matched(self, text):
        assert rules.parse_mail(message("簽核通知--(x)"), anchor(text)) is None

    def test_a_borrow_number_embedded_in_prose_is_not_matched(self):
        """The anchor text must *be* the number, not merely contain one."""
        assert rules.parse_mail(message("x"), anchor("單號 DR26270135 請簽核")) is None


class TestLinkDetection:
    def test_both_the_href_and_the_text_must_qualify(self):
        assert rules.parse_mail(message("x"), anchor("DR26270135", "https://elsewhere/other.aspx")) is None

    def test_other_links_in_the_mail_do_not_confuse_it(self):
        body = (
            '<a href="https://intranet/help">說明</a>'
            '<a href="mailto:x@y.z">寄信</a>'
            + anchor("DR26270135")
        )
        mail = rules.parse_mail(message("x"), body)
        assert mail is not None and mail.borrow_no == "DR26270135"

    def test_entities_in_the_href_are_decoded(self):
        """Outlook stores `&amp;`; the portal needs three parameters, not one."""
        mail = rules.parse_mail(message("x"), anchor("DR26270135"))
        assert "&amp;" not in mail.loan_url
        assert mail.loan_url.count("&") == 2

    def test_a_mail_with_no_such_link_is_not_a_loan_form(self):
        """282 of 400 live messages take this path; it is the normal case."""
        assert rules.parse_mail(message("Lunch order"), "<p>no links here</p>") is None

    def test_markup_inside_the_anchor_is_stripped(self):
        body = f'<a href="{PORTAL}?a=1"><span> DR26270135 </span></a>'
        assert rules.parse_mail(message("x"), body).borrow_no == "DR26270135"


class TestNoticeKind:
    """Two kinds exist and no more: 簽核通知 106, 否決 12."""

    @pytest.mark.parametrize(
        "subject, kind",
        [
            ("簽核通知--(展示機出借申請單 - 一般  DR26270135 )   /cr/", "簽核通知"),
            ("否決--(展示機出借申請單 - 專用DRL26270035)    /cr/", "否決"),
            ("no prefix at all", ""),
        ],
    )
    def test_kind_is_read_from_the_subject(self, subject, kind):
        assert rules.notice_kind(subject) == kind

    def test_a_rejection_is_flagged(self):
        mail = rules.parse_mail(message("否決--(展示機出借申請單 - 一般DR26270148)"), anchor("DR26270148"))
        assert mail.is_rejection is True

    def test_an_approval_is_not(self):
        mail = rules.parse_mail(message("簽核通知--(展示機出借申請單)"), anchor("DR26270135"))
        assert mail.is_rejection is False

    def test_the_kind_survives_into_the_payload(self):
        mail = rules.parse_mail(message("否決--(x)"), anchor("DR26270148"))
        assert mail.as_dict()["notice"] == "否決"


class TestGates:
    def _mail(self, sender="workflow@rohde-schwarz.com", borrow="DR26270135"):
        m = message("簽核通知--(x)")
        m["senderEmail"] = sender
        return rules.parse_mail(m, anchor(borrow))

    def test_sender_gate_is_off_by_default(self):
        """The notices come from a workflow mailbox whose address differs
        between the HQ and local systems; guessing it would drop real work."""
        assert rules.accepts_sender(self._mail(sender="anyone@x.z"), "expected@y.z", require=False)

    def test_sender_gate_matches_case_insensitively(self):
        mail = self._mail(sender="Workflow@Rohde-Schwarz.com")
        assert rules.accepts_sender(mail, "workflow@rohde-schwarz.com", require=True)

    def test_sender_gate_rejects_a_mismatch(self):
        assert not rules.accepts_sender(self._mail(sender="other@x.z"), "expected@y.z", require=True)

    def test_an_empty_expectation_does_not_reject_everything(self):
        """A half-filled config must not silently drop every mail."""
        assert rules.accepts_sender(self._mail(), "", require=True)

    def test_category_filter_is_empty_by_default(self):
        assert rules.accepts_category(self._mail(borrow="DRS26270011"), [])

    def test_category_filter_excludes_by_code(self):
        assert not rules.accepts_category(self._mail(borrow="DRS26270011"), ["S"])
        assert rules.accepts_category(self._mail(borrow="DRL26270065"), ["S"])

    def test_category_filter_ignores_case_and_blanks(self):
        assert not rules.accepts_category(self._mail(borrow="DRS26270011"), ["  s  ", ""])
