# Vendored oracle: rs_workflow_system@896046e8 host-bridge/tests/test_loan_process.py; only tests/loan_oracle.py REPLACEMENTS differ.
"""Workflow 06b's consumer, with both browsers and Outlook faked.

The fake dispatches on the job's own script constants (``READ_BLOCKS`` and
friends) rather than on substrings of them, so a test cannot keep passing after
the job starts asking a different question.
"""

from __future__ import annotations

import pytest

from capabilities.loan_reply import queue as q
from capabilities.loan_reply import rules
from capabilities.loan_reply import edge_session
from capabilities.loan_reply import process as loan_process
from capabilities.loan_reply.bridge_api import BridgeClientError

PORTAL = "https://rstw-portal.rsint.net"
FORM_URL = f"{PORTAL}/FlowSingle.aspx?accessId=abc"
LOGIN_URL = f"{PORTAL}/login.aspx?ReturnUrl=%2fFlowSingle.aspx"
ERROR_URL = f"{PORTAL}/ErrorPage.aspx?errmsg=Object+reference+not+set"
IDP_URL = (
    "https://login.microsoftonline.com/74bddbd9-705c-456e-aabd-99beb719a2b2"
    "/oauth2/v2.0/authorize?client_id=7671fd12&response_type=code"
)

BORROW = "DR26270135"
CUSTOMER = "130895,BTL Inc."

CFG = {
    **loan_process.DEFAULTS,
    "settleMs": 0,
    "busyTimeoutMs": 100,
    "alertRecipient": "ops@example.com",
    "closeBrowsersAfter": True,
}


class FakeBridge:
    """One object standing in for both browser sessions and Outlook.

    Both profiles share it: the job is what keeps their sessions apart, and a
    single call log makes the ordering assertions easy to read.
    """

    def __init__(
        self,
        *,
        urls=(FORM_URL,),
        fields=None,
        rows=("130895 BTL Inc.",),
        rows_seq=None,
        blocks=None,
        accounts_ready=True,
        fill_fails_once=False,
        screenshot="C:/state/loan-shots/shot.png",
        eval_races=0,
        eval_error=None,
    ):
        #: How many evals blow up with a navigation race before one succeeds.
        self.eval_races = eval_races
        self.eval_error = eval_error
        self._urls = list(urls)
        self.fields = {"客戶名稱": CUSTOMER, "E-mail": "who@example.com",
                       "單據編號": BORROW} if fields is None else fields
        self.rows = list(rows)
        #: One entry per read, for the "still rendering" case. Last one repeats.
        self.rows_seq = [list(r) for r in rows_seq] if rows_seq else None
        # Default: both labels on the page, both empty -- a genuinely clear
        # customer. `None` for a field means the label is not on the page.
        self.blocks = blocks or {"classificationDeliveryBlock": "", "deliveryBlock": ""}
        self.blocks.setdefault("erpCustomerId", "130895")
        self.accounts_ready = accounts_ready
        self.fill_fails_once = fill_fails_once
        self.screenshot = screenshot
        self.calls: list[tuple[str, dict]] = []
        self.opened: list[dict] = []
        self.closed: list[str] = []

    # -- browser --------------------------------------------------------
    def browser_open(self, **kw):
        self.opened.append(kw)
        return {"sessionId": f"s{len(self.opened)}"}

    def browser_goto(self, session_id, url, **kw):
        self.calls.append(("goto", {"url": url}))
        return {}

    def browser_close(self, session_id):
        self.closed.append(session_id)
        return {}

    # -- email ----------------------------------------------------------
    def email_draft(self, **kw):
        self.calls.append(("draft", kw))
        return {"entryId": "draft-1"}

    # -- everything else goes through post() ----------------------------
    def post(self, path, body, timeout=None):
        self.calls.append((path, body))
        if path == "/browser/eval":
            return {"result": self._eval(body["script"])}
        if path == "/browser/fill":
            if self.fill_fails_once:
                self.fill_fails_once = False
                raise BridgeClientError("TIMEOUT", "search field not visible")
            return {}
        if path == "/browser/screenshot":
            if self.screenshot is None:
                raise BridgeClientError("PATH_NOT_ALLOWED", "outside the browser roots")
            return {"path": self.screenshot}
        if path == "/email/reply":
            return {"entryId": "reply-1"}
        return {}

    def _eval(self, script):
        if self.eval_error is not None:
            raise BridgeClientError("INTERNAL", self.eval_error)
        if self.eval_races > 0:
            self.eval_races -= 1
            raise BridgeClientError(
                "INTERNAL",
                "Page.evaluate: Execution context was destroyed, most likely "
                "because of a navigation",
            )
        if script == loan_process.URL_JS:
            # The last URL repeats: a page that has settled stays put.
            return self._urls.pop(0) if len(self._urls) > 1 else self._urls[0]
        if script == loan_process.BUSY_JS:
            return False
        if script == loan_process.READ_FORM_FIELDS:
            return self.fields
        if script == loan_process.ACCOUNTS_READY:
            return {"adv": self.accounts_ready, "view": self.accounts_ready}
        if script == loan_process.RESULT_LINKS:
            if self.rows_seq is None:
                return self.rows
            return self.rows_seq.pop(0) if len(self.rows_seq) > 1 else self.rows_seq[0]
        if script == loan_process.SCROLL_TO_BLOCKS:
            return True
        if script == loan_process.READ_BLOCKS:
            return self.blocks
        raise AssertionError(f"the job ran an unexpected script: {script[:80]!r}")

    # -- assertions helpers ---------------------------------------------
    def clicked(self):
        return [b["selector"] for p, b in self.calls if p == "/browser/click"]

    def mails(self):
        return [b for p, b in self.calls if p in ("draft", "/email/reply")]


@pytest.fixture(autouse=True)
def _no_waiting(monkeypatch):
    monkeypatch.setattr(loan_process.time, "sleep", lambda *_a: None)


@pytest.fixture
def stub_edge(monkeypatch):
    """Replace the managed-Edge lifecycle; records what the job asked for."""
    log: dict[str, list] = {"open": [], "close": [], "release": []}
    monkeypatch.setattr(
        loan_process.edge_session, "open_session",
        lambda b, profile, port, url, lg, **kw: (
            log["open"].append((profile, port, url, kw.get("ready_title"))),
            {"leaseId": f"lease-{profile}"},
        )[1],
    )
    monkeypatch.setattr(
        loan_process.edge_session, "close_session",
        lambda b, profile, port, **kw: log["close"].append((profile, kw.get("lease_id"))),
    )
    monkeypatch.setattr(
        loan_process.edge_session, "release_lease",
        lambda profile, lease: log["release"].append((profile, lease)),
    )
    return log


def _page(bridge, settle=0.0):
    return loan_process._Page(bridge, "s1", lambda _m: None, settle)


def _enqueue(tmp_path, monkeypatch, **extra):
    monkeypatch.setattr(q, "QUEUE_ROOT", tmp_path)
    q.enqueue({"borrowNo": BORROW, "loanUrl": FORM_URL, "entryId": "mail-1",
               "category": "一般", **extra}, tmp_path)


def _run(monkeypatch, bridge, cfg=None, **params):
    monkeypatch.setattr(loan_process, "_bridge", lambda: bridge)
    return loan_process.run({"_config": {**CFG, **(cfg or {})}, **params}, log=lambda _m: None)


# ---------------------------------------------------------------------------
# Flow 1 -- the loan portal
# ---------------------------------------------------------------------------


class TestReadLoanForm:
    def test_reads_the_labelled_fields(self):
        b = FakeBridge()
        fields = loan_process.read_loan_form(_page(b), FORM_URL, lambda _m: None)
        assert fields["客戶名稱"] == CUSTOMER
        assert fields["單據編號"] == BORROW

    def test_a_lapsed_session_is_signed_in_and_the_form_still_loads(self):
        """The login URL carries `ReturnUrl=%2fFlowSingle.aspx`.

        A substring test over the whole URL therefore reads the sign-in page as
        the form itself and starts hunting for fields that are not there.
        """
        b = FakeBridge(urls=[LOGIN_URL, FORM_URL])
        loan_process.read_loan_form(_page(b), FORM_URL, lambda _m: None)
        assert loan_process.LOGIN_BUTTON in b.clicked()

    def test_the_account_picker_is_clicked_through(self):
        """Signing in is two clicks and no typing: 登入, then the account tile.

        The machine is domain-joined, so Entra offers a picker rather than a
        password prompt -- and a run that stops there stops silently, with the
        browser sitting on a page nobody is watching.
        """
        b = FakeBridge(urls=[LOGIN_URL, IDP_URL, FORM_URL])
        loan_process.read_loan_form(_page(b), FORM_URL, lambda _m: None)
        assert b.clicked() == [loan_process.LOGIN_BUTTON, loan_process.ACCOUNT_TILE]

    def test_a_named_account_is_picked_by_address(self):
        b = FakeBridge(urls=[IDP_URL, FORM_URL])
        loan_process.read_loan_form(_page(b), FORM_URL, lambda _m: None, "leo.chi@example.com")
        assert b.clicked() == ['div.table[role="button"][data-test-id="leo.chi@example.com"]']

    def test_the_default_tile_skips_use_another_account(self):
        """`#otherTile` carries no `data-test-id`; requiring it is what keeps
        the job off the "Use another account" tile, which leads to a password
        prompt nobody can answer."""
        assert "data-test-id]" in loan_process.ACCOUNT_TILE
        assert loan_process.ACCOUNT_TILE.endswith("nth=0")  # page.click is strict

    @pytest.mark.parametrize(
        "url, expected",
        [
            (LOGIN_URL, "login.aspx"),
            (FORM_URL, "flowsingle.aspx"),
            (ERROR_URL, "errorpage.aspx"),
            (f"{PORTAL}/FlowSingle.aspx#top", "flowsingle.aspx"),
        ],
    )
    def test_the_page_is_identified_by_its_path_not_its_query(self, url, expected):
        assert loan_process.page_name(url) == expected

    def test_the_error_page_is_reported_as_a_refusal_not_a_timeout(self):
        """A rejected form answers with a null-reference error page.

        Distinguished from "slow" on purpose: the two need opposite responses,
        and twelve pointless retries would hide the reason.
        """
        b = FakeBridge(urls=[ERROR_URL])
        with pytest.raises(loan_process.JobError, match="refused"):
            loan_process.read_loan_form(_page(b), FORM_URL, lambda _m: None)
        assert loan_process.LOGIN_BUTTON not in b.clicked()

    def test_a_form_without_the_customer_field_is_an_error_not_an_empty_result(self):
        b = FakeBridge(fields={"單據編號": BORROW})
        with pytest.raises(loan_process.JobError, match="客戶名稱"):
            loan_process.read_loan_form(_page(b), FORM_URL, lambda _m: None)

    def test_a_page_that_never_arrives_names_where_it_stopped(self):
        b = FakeBridge(urls=[f"{PORTAL}/Default.aspx"])
        with pytest.raises(loan_process.JobError, match="Default.aspx"):
            loan_process.read_loan_form(_page(b), FORM_URL, lambda _m: None)


# ---------------------------------------------------------------------------
# Flow 2 -- C4C
# ---------------------------------------------------------------------------


class TestReadDeliveryBlocks:
    def _read(self, bridge):
        return loan_process.read_delivery_blocks(_page(bridge), "130895", CFG, lambda _m: None)

    def test_a_customer_with_a_block_is_blocked(self):
        b = FakeBridge(blocks={"classificationDeliveryBlock": "Z1 Credit",
                               "deliveryBlock": ""})
        status = self._read(b)
        assert status.found and status.blocked
        assert status.classification_delivery_block == "Z1 Credit"

    def test_a_customer_with_neither_field_set_is_clear(self):
        status = self._read(FakeBridge())
        assert status.found is True and status.blocked is False

    def test_missing_fields_are_unreadable_not_clear(self):
        """The single most dangerous confusion in this job.

        An empty field means "not blocked". A *missing* field means nobody read
        anything -- most likely a C4C layout change. Treating the second as the
        first would tell every customer their instrument is on its way, and the
        run would look completely healthy while doing it.
        """
        b = FakeBridge(blocks={"classificationDeliveryBlock": None, "deliveryBlock": None,
                               "erpCustomerId": "130895"})
        status = self._read(b)
        assert status.found is False
        assert status.reason == rules.REASON_FIELDS_UNREADABLE

    def test_one_missing_field_is_enough_to_stop(self):
        b = FakeBridge(blocks={"classificationDeliveryBlock": "", "deliveryBlock": None,
                               "erpCustomerId": "130895"})
        assert self._read(b).found is False

    def test_opening_the_wrong_account_is_refused(self):
        """The search matches on more than the id -- five rows for one number is
        normal -- so the row that opened has to be the one asked for."""
        b = FakeBridge(blocks={"classificationDeliveryBlock": "Z1", "deliveryBlock": "",
                               "erpCustomerId": "999999"})
        status = self._read(b)
        assert status.found is False and status.reason == rules.REASON_WRONG_ACCOUNT
        assert status.blocked is False  # must not leak the wrong customer's block

    def test_the_reader_script_reports_a_missing_label_as_null(self):
        """A guard on the browser-side script, which these fakes cannot execute.

        Everything else here drives `read_delivery_blocks` with the script's
        *output* stubbed, so nothing in this file would notice the script itself
        starting to return "" for a label that is not on the page -- and that is
        precisely the change that would make every customer read as unblocked.
        The behaviour was verified live on 2026-08-03 (customer 115776: values
        for 30 other fields, "" for these two); this pins the intent.
        """
        assert "if (!labelEl) return null;" in loan_process.READ_BLOCKS

    def test_an_account_page_without_the_id_field_is_still_read(self):
        """Not every page exposes ERP Customer ID; its absence is not a mismatch."""
        b = FakeBridge(blocks={"classificationDeliveryBlock": "Z1", "deliveryBlock": "",
                               "erpCustomerId": None})
        assert self._read(b).found is True

    def test_no_search_result_is_not_found_rather_than_clear(self):
        """The distinction the whole reply hangs on.

        "C4C returned nothing" is not evidence that delivery is unblocked, so it
        must not produce the shipping reply.
        """
        status = self._read(FakeBridge(rows=[]))
        assert status.found is False
        assert status.blocked is False  # never consulted, but must not read as clear

    def test_a_list_that_is_still_rendering_is_read_again(self):
        """The difference between "no such customer" and "not painted yet".

        Both look like an empty result list. Reporting the first when it was
        really the second sends an internal "C4C 找不到客戶" notice for a customer
        that is right there, and the real answer -- blocked or not -- is lost.
        """
        b = FakeBridge(rows_seq=[[], ["130895 BTL Inc."]],
                       blocks={"classificationDeliveryBlock": "Z1", "deliveryBlock": ""})
        status = self._read(b)
        assert status.found is True and status.blocked is True

    def test_the_search_box_is_opened_when_filling_it_fails(self):
        b = FakeBridge(fill_fails_once=True)
        self._read(b)
        assert loan_process.SEARCH_BUTTON in b.clicked()

    def test_the_customer_id_is_searched_as_a_wildcard(self):
        b = FakeBridge()
        self._read(b)
        fills = [body["value"] for p, body in b.calls if p == "/browser/fill"]
        assert fills == ["*130895*"]

    def test_a_shell_that_never_shows_the_list_is_an_error(self):
        b = FakeBridge(accounts_ready=False)
        with pytest.raises(loan_process.JobError, match="Accounts list"):
            self._read(b)

    def test_navigation_uses_the_route_that_was_proven_to_work(self):
        b = FakeBridge(accounts_ready=False)
        with pytest.raises(loan_process.JobError):
            self._read(b)
        assert loan_process.NAV_CUSTOMERS in b.clicked()
        assert loan_process.NAV_ACCOUNTS in b.clicked()


# ---------------------------------------------------------------------------
# run() end to end
# ---------------------------------------------------------------------------


class TestRun:
    def test_a_blocked_customer_gets_the_block_reply_with_the_screenshot(
        self, monkeypatch, tmp_path, stub_edge
    ):
        _enqueue(tmp_path, monkeypatch)
        b = FakeBridge(blocks={"classificationDeliveryBlock": "Z1 Credit",
                               "deliveryBlock": "01"})
        out = _run(monkeypatch, b)

        assert out["processed"] == 1 and out["outcomes"]["blocked"] == 1
        (mail,) = b.mails()
        assert mail["entryId"] == "mail-1"
        assert "Z1 Credit" in mail["body"] and "01" in mail["body"]
        assert mail["attachments"] == [{"path": b.screenshot}]
        assert q.counts(tmp_path) == {"pending": 0, "claimed": 0, "done": 1, "failed": 0}

    def test_a_clear_customer_gets_the_shipping_reply(self, monkeypatch, tmp_path, stub_edge):
        _enqueue(tmp_path, monkeypatch)
        b = FakeBridge()
        out = _run(monkeypatch, b)
        assert out["outcomes"]["shipping"] == 1
        assert "配送中" in b.mails()[0]["body"]

    def test_an_unknown_customer_gets_an_internal_notice_not_a_reply(
        self, monkeypatch, tmp_path, stub_edge
    ):
        _enqueue(tmp_path, monkeypatch)
        b = FakeBridge(rows=[])
        out = _run(monkeypatch, b)

        assert out["outcomes"]["customer-not-found"] == 1
        (mail,) = b.mails()
        assert "entryId" not in mail                      # a new mail, not a reply
        assert mail["to"] == ["ops@example.com"]
        assert "130895" in mail["subject"]

    def test_no_mail_is_ever_sent(self, monkeypatch, tmp_path, stub_edge):
        """Every path drafts. Purview aside, the reply is customer-facing."""
        for blocks, rows in (
            ({"classificationDeliveryBlock": "Z1", "deliveryBlock": ""}, ["x"]),
            (None, ["x"]),
            (None, []),
        ):
            _enqueue(tmp_path, monkeypatch)
            b = FakeBridge(blocks=blocks, rows=rows)
            _run(monkeypatch, b)
            assert [m["send"] for m in b.mails()] == [False]
            for state in q.STATES:
                for f in q.state_dir(state, tmp_path).glob("*.json"):
                    f.unlink()

    def test_a_failure_drafts_a_notice_and_parks_the_item_as_failed(
        self, monkeypatch, tmp_path, stub_edge
    ):
        """Failed, not back to pending.

        Requeueing would redraft the same notice every few minutes; a form that
        broke needs a person, once.
        """
        _enqueue(tmp_path, monkeypatch)
        b = FakeBridge(fields={"單據編號": BORROW})  # no 客戶名稱
        out = _run(monkeypatch, b)

        assert out["processed"] == 0 and out["failed"] == 1
        assert q.counts(tmp_path)["failed"] == 1 and q.counts(tmp_path)["pending"] == 0
        (mail,) = b.mails()
        assert "自動化失敗" in mail["subject"] and mail["send"] is False

    def test_an_unreachable_bridge_hands_the_item_back_instead_of_failing_it(
        self, monkeypatch, tmp_path, stub_edge
    ):
        """A Bridge that is not running says nothing about the form.

        Marking it `failed` would need a human to clear a form that was never
        even looked at -- and the failure notice needs the same Bridge, so it
        would not be written either. Hit for real on 2026-08-03.
        """
        _enqueue(tmp_path, monkeypatch)
        b = FakeBridge()

        def refuse(*_a, **_kw):
            raise ConnectionError("Failed to establish a new connection: refused")

        monkeypatch.setattr(b, "browser_goto", refuse)
        monkeypatch.setattr(loan_process, "_bridge", lambda: b)

        with pytest.raises(loan_process.JobError, match="most likely not running"):
            loan_process.run({"_config": CFG}, log=lambda _m: None)

        assert q.counts(tmp_path)["pending"] == 1
        assert q.counts(tmp_path)["failed"] == 0 and q.counts(tmp_path)["claimed"] == 0

    def test_a_second_item_is_not_burned_when_the_bridge_disappears(
        self, monkeypatch, tmp_path, stub_edge
    ):
        monkeypatch.setattr(q, "QUEUE_ROOT", tmp_path)
        for n in ("DR26270149", "DR26270150"):
            q.enqueue({"borrowNo": n, "loanUrl": FORM_URL, "entryId": f"m-{n}"}, tmp_path)
        b = FakeBridge()
        monkeypatch.setattr(b, "browser_goto", lambda *a, **k: (_ for _ in ()).throw(
            ConnectionError("refused")))
        monkeypatch.setattr(loan_process, "_bridge", lambda: b)

        with pytest.raises(loan_process.JobError):
            loan_process.run({"_config": CFG, "maxItems": 2}, log=lambda _m: None)
        # Both still queued: the run stopped instead of working through them.
        assert q.counts(tmp_path)["pending"] == 2

    def test_an_edited_template_changes_the_mail_that_is_drafted(
        self, monkeypatch, tmp_path, stub_edge
    ):
        """The whole point of the feature, checked where it actually lands.

        Rendering in isolation proves the substitution works; this proves the
        edited file reaches Outlook -- that the job passes its config's
        templateDir through and does not quietly use the built-in wording.
        """
        tpl = tmp_path / "tpl"
        tpl.mkdir()
        (tpl / "shipping-reply.txt").write_text(
            "Dear {customerName}, order {borrowNo} ({category}) is on its way.",
            encoding="utf-8")
        _enqueue(tmp_path, monkeypatch)
        b = FakeBridge()
        _run(monkeypatch, b, cfg={"templateDir": str(tpl)})

        (mail,) = b.mails()
        assert mail["body"] == "Dear BTL Inc., order DR26270135 (一般) is on its way."

    def test_a_broken_template_stops_the_run_and_keeps_the_form_queued(
        self, monkeypatch, tmp_path, stub_edge
    ):
        """A typo in a template is not the form's fault.

        It also fails identically for every other form, so marking this one
        `failed` would make a human clear a form that was fine, and carrying on
        would draft one identical notice per queued form. Same shape as an
        unreachable Bridge, so it gets the same treatment.
        """
        tpl = tmp_path / "tpl"
        tpl.mkdir()
        (tpl / "shipping-reply.txt").write_text("訂單 {borrowNumber}", encoding="utf-8")
        _enqueue(tmp_path, monkeypatch)
        b = FakeBridge()
        monkeypatch.setattr(loan_process, "_bridge", lambda: b)

        with pytest.raises(loan_process.JobError) as exc:
            loan_process.run({"_config": {**CFG, "templateDir": str(tpl)}},
                             log=lambda _m: None)

        assert "borrowNumber" in str(exc.value)
        assert "delete it to return to the built-in text" in str(exc.value)
        assert q.counts(tmp_path)["pending"] == 1   # handed back, not failed
        assert q.counts(tmp_path)["failed"] == 0
        assert b.mails() == []                      # nothing reached the customer

    def test_a_second_consumer_skips_instead_of_failing(self, monkeypatch, tmp_path,
                                                        stub_edge):
        """A run that finds another in progress is not a failure.

        The run that got there first works through the same queue and will pick
        up whatever this one would have. Reporting failure would turn every
        burst of arriving mail into a red workflow, which teaches people to stop
        reading them.
        """
        _enqueue(tmp_path, monkeypatch)
        held = q.acquire_run_lock("loan_process", tmp_path)
        try:
            b = FakeBridge()
            out = _run(monkeypatch, b)
        finally:
            held.release()

        assert out["skipped"] is True
        assert out["processed"] == 0
        assert out["failed"] == 0              # skipped is not failed
        assert "already in progress" in out["skipReason"]
        assert stub_edge["open"] == []         # no browser was started
        assert b.mails() == []
        assert q.counts(tmp_path)["pending"] == 1   # the form is untouched

    def test_a_normal_run_is_not_marked_skipped(self, monkeypatch, tmp_path, stub_edge):
        _enqueue(tmp_path, monkeypatch)
        out = _run(monkeypatch, FakeBridge())
        assert out["skipped"] is False and out["processed"] == 1

    def test_the_lock_is_released_so_the_next_run_can_start(self, monkeypatch, tmp_path,
                                                            stub_edge):
        _enqueue(tmp_path, monkeypatch)
        _run(monkeypatch, FakeBridge())
        # Would raise RunLockBusy if the finished run still held it.
        q.acquire_run_lock("loan_process", tmp_path).release()

    def test_the_lock_is_released_even_when_the_run_fails(self, monkeypatch, tmp_path,
                                                          stub_edge):
        """Otherwise one failure blocks every run for the next twenty minutes."""
        _enqueue(tmp_path, monkeypatch)
        b = FakeBridge()
        monkeypatch.setattr(b, "browser_goto", lambda *a, **k: (_ for _ in ()).throw(
            ConnectionError("refused")))
        monkeypatch.setattr(loan_process, "_bridge", lambda: b)
        with pytest.raises(loan_process.JobError):
            loan_process.run({"_config": CFG}, log=lambda _m: None)
        q.acquire_run_lock("loan_process", tmp_path).release()

    def test_an_empty_queue_opens_no_browser(self, monkeypatch, tmp_path, stub_edge):
        monkeypatch.setattr(q, "QUEUE_ROOT", tmp_path)
        b = FakeBridge()
        out = _run(monkeypatch, b)
        assert out["processed"] == 0
        assert stub_edge["open"] == [] and b.opened == []

    def test_a_dry_run_writes_no_draft_and_leaves_the_item_queued(
        self, monkeypatch, tmp_path, stub_edge
    ):
        _enqueue(tmp_path, monkeypatch)
        b = FakeBridge(blocks={"classificationDeliveryBlock": "Z1", "deliveryBlock": ""})
        out = _run(monkeypatch, b, dryRun=True)

        assert out["processed"] == 1 and out["items"][0]["outcome"] == "blocked"
        assert b.mails() == []
        assert q.counts(tmp_path)["pending"] == 1
        assert "Z1" in out["items"][0]["bodyPreview"]

    def test_both_profiles_are_opened_and_closed_with_their_own_lease(
        self, monkeypatch, tmp_path, stub_edge
    ):
        _enqueue(tmp_path, monkeypatch)
        _run(monkeypatch, FakeBridge())
        assert [(p, port) for p, port, _u, _t in stub_edge["open"]] == [
            ("loan", 9223), ("c4c", 9222)
        ]
        assert sorted(stub_edge["close"]) == [("c4c", "lease-c4c"), ("loan", "lease-loan")]

    def test_c4c_waits_for_the_app_to_render_before_it_is_driven(
        self, monkeypatch, tmp_path, stub_edge
    ):
        """A live CDP port is not a driveable page.

        Measured: for about a minute after Edge starts, the C4C tab still
        carries its own URL as its title and every click times out. So C4C is
        opened *on* its home page with a ready title to wait for. The portal has
        neither -- each item navigates to its own form URL and polls there.
        """
        _enqueue(tmp_path, monkeypatch)
        _run(monkeypatch, FakeBridge())
        opened = {p: (url, title) for p, _port, url, title in stub_edge["open"]}
        assert opened["c4c"] == (CFG["c4cHomeUrl"], "SAP Cloud for Customer")
        assert opened["loan"] == (None, None)

    def test_one_wedged_item_does_not_take_the_rest_of_the_run_with_it(
        self, monkeypatch, tmp_path, stub_edge
    ):
        """A timed-out browser op leaves the session unusable.

        Without dropping it, item 2 inherits item 1's wedged session and a
        five-item run turns into five failures -- which is what the first live
        run actually did.
        """
        monkeypatch.setattr(q, "QUEUE_ROOT", tmp_path)
        for n in ("DR26270148", "DR26270149"):
            q.enqueue({"borrowNo": n, "loanUrl": FORM_URL, "entryId": f"mail-{n}"}, tmp_path)

        b = FakeBridge(urls=[ERROR_URL, FORM_URL])  # first item refuses, second is fine
        out = _run(monkeypatch, b, maxItems=2)

        assert out["failed"] == 1 and out["processed"] == 1
        # Item 2 drives a *new* session on the portal, not item 1's.
        assert [o["profile"] for o in b.opened].count("loan") == 2
        # The browser itself was started once -- only the session was replaced,
        # so recovery costs a reconnect rather than another 30-60s Edge start.
        assert [p for p, _port, _u, _t in stub_edge["open"]].count("loan") == 1

    def test_keeping_the_browsers_open_still_releases_the_leases(
        self, monkeypatch, tmp_path, stub_edge
    ):
        """Otherwise workflow 03 could not close the browser until the TTL."""
        _enqueue(tmp_path, monkeypatch)
        _run(monkeypatch, FakeBridge(), cfg={"closeBrowsersAfter": False})
        assert stub_edge["close"] == []
        assert sorted(stub_edge["release"]) == [("c4c", "lease-c4c"), ("loan", "lease-loan")]

    def test_a_failed_screenshot_does_not_lose_the_answer(
        self, monkeypatch, tmp_path, stub_edge
    ):
        _enqueue(tmp_path, monkeypatch)
        b = FakeBridge(screenshot=None,
                       blocks={"classificationDeliveryBlock": "Z1", "deliveryBlock": ""})
        out = _run(monkeypatch, b)
        assert out["outcomes"]["blocked"] == 1
        assert b.mails()[0]["attachments"] == []

    def test_the_c4c_lookup_runs_after_the_form_is_read(self, monkeypatch, tmp_path, stub_edge):
        """Ordering matters: the customer id comes off the form."""
        _enqueue(tmp_path, monkeypatch)
        b = FakeBridge()
        _run(monkeypatch, b)
        gotos = [body["url"] for p, body in b.calls if p == "goto"]
        assert gotos == [FORM_URL, CFG["c4cHomeUrl"]]


class TestNavigationRace:
    """Pressing 登入 hands over to the IdP, and the next thing the job does is
    read `location.href`. The page moving mid-script is the normal case here."""

    def test_a_navigation_race_is_waited_out_not_reported_as_a_failure(self):
        b = FakeBridge(eval_races=2)
        assert loan_process._Page(b, "s1", lambda _m: None, 0).url() == FORM_URL

    def test_a_race_that_never_settles_is_still_an_error(self):
        b = FakeBridge(eval_races=99)
        with pytest.raises(BridgeClientError):
            loan_process._Page(b, "s1", lambda _m: None, 0).url()

    def test_a_redirect_that_aborts_our_navigation_is_retried(self):
        """`Page.goto: net::ERR_ABORTED` on the loan portal.

        Hit on a manual run of workflow 06b (2026-08-04): the portal redirected
        while Playwright was still waiting on the navigation it had started, and
        the whole form was marked failed over a page that loads fine on the next
        try.
        """
        b = FakeBridge()
        calls = {"n": 0}

        def flaky(session_id, url, **kw):
            calls["n"] += 1
            if calls["n"] == 1:
                raise BridgeClientError(
                    "INTERNAL", "Page.goto: net::ERR_ABORTED; maybe frame was detached?")
            b.calls.append(("goto", {"url": url}))

        b.browser_goto = flaky
        loan_process._Page(b, "s1", lambda _m: None, 0).goto(FORM_URL)
        assert calls["n"] == 2

    def test_a_goto_failure_that_is_not_a_race_is_raised_at_once(self):
        b = FakeBridge()

        def refuse(session_id, url, **kw):
            raise BridgeClientError("TIMEOUT", "Page.goto: Timeout 90000ms exceeded")

        b.browser_goto = refuse
        with pytest.raises(BridgeClientError, match="Timeout"):
            loan_process._Page(b, "s1", lambda _m: None, 0).goto(FORM_URL)

    def test_any_other_error_is_raised_immediately(self):
        b = FakeBridge(eval_error="ReferenceError: foo is not defined")
        with pytest.raises(BridgeClientError, match="ReferenceError"):
            loan_process._Page(b, "s1", lambda _m: None, 0).url()
        # One attempt, not four: retrying a genuine script error just wastes
        # eight seconds before reporting the same thing.
        assert len([1 for p, _ in b.calls if p == "/browser/eval"]) == 1


class TestConfigPaths:
    """One config file, found the same way by both halves of the flow."""

    def test_the_documented_cli_form_resolves_from_host_bridge(self, monkeypatch, tmp_path):
        """CLAUDE.md documents `--config ..\\config\\workflow-06.json`.

        Resolved against the repo root alone that points above the repo, and the
        job dies with "config not found" for a file that is right there.
        """
        (tmp_path / "config").mkdir()
        cfg = tmp_path / "config" / "workflow-06.json"
        cfg.write_text('{"alertRecipient": "x@example.com"}', encoding="utf-8")
        (tmp_path / "host-bridge").mkdir()
        monkeypatch.chdir(tmp_path / "host-bridge")

        assert loan_process.load_config("../config/workflow-06.json")["alertRecipient"] == (
            "x@example.com"
        )

    def test_both_halves_resolve_the_same_path(self, monkeypatch, tmp_path):
        from capabilities.loan_reply import scan as loan_scan

        (tmp_path / "config").mkdir()
        (tmp_path / "config" / "workflow-06.json").write_text("{}", encoding="utf-8")
        monkeypatch.chdir(tmp_path)
        assert q.resolve_config("config/workflow-06.json", loan_process.DEFAULT_CONFIG) == (
            q.resolve_config("config/workflow-06.json", loan_scan.DEFAULT_CONFIG)
        )

    def test_a_named_config_that_does_not_exist_is_an_error_not_silent_defaults(self):
        with pytest.raises(FileNotFoundError):
            loan_process.load_config("config/no-such-file.json")


class TestProfilePorts:
    def test_the_two_profiles_do_not_share_a_debugging_port(self):
        """One port per profile, or the second attach lands in the first browser."""
        assert edge_session.PROFILE_PORTS["loan"] != edge_session.PROFILE_PORTS["c4c"]


class TestReplyWording:
    """The bodies came from the original workflow; keep them recognisable."""

    def test_a_block_reply_names_both_fields(self):
        body = rules.blocked_reply(BORROW, rules.BlockStatus(True, "Z1 Credit", "01"))
        assert "Classification Delivery Block" in body and "Delivery Block" in body
        assert BORROW in body and rules.SIGNATURE in body

    @staticmethod
    def _field(body: str, english_label: str) -> str:
        """The value on the line carrying `english_label`.

        Located by the English label because the Chinese ones are substrings of
        each other -- "配送限制" also matches "分類配送限制".
        """
        line = next(ln for ln in body.splitlines() if english_label in ln)
        return line.split("：", 1)[1].strip()

    @pytest.mark.parametrize(
        "cls_block, dlv_block",
        [
            ("Z1 Credit", ""),   # only Delivery Block is empty
            ("", "01"),          # only Classification Delivery Block is empty
        ],
    )
    def test_each_empty_field_falls_back_independently(self, cls_block, dlv_block):
        """Checked per field, not "somewhere in the body".

        A single `NO_VALUE in body` assertion passes as long as *either* field
        falls back, so it would not notice one of them starting to render as a
        bare colon followed by nothing.
        """
        body = rules.blocked_reply(BORROW, rules.BlockStatus(True, cls_block, dlv_block))
        got_cls = self._field(body, "Classification Delivery Block")
        got_dlv = self._field(body, "(Delivery Block)")
        assert got_cls == (cls_block or rules.NO_VALUE)
        assert got_dlv == (dlv_block or rules.NO_VALUE)

    @pytest.mark.parametrize(
        "reason, marker",
        [
            (rules.REASON_NO_ACCOUNT, "搜尋不到"),
            (rules.REASON_FIELDS_UNREADABLE, "讀不到不等於沒有限制"),
            (rules.REASON_WRONG_ACCOUNT, "不一致"),
        ],
    )
    def test_each_failure_reason_says_what_to_go_and_check(self, reason, marker):
        """Three different things to investigate; one shared wording would send
        the reader to the wrong place twice out of three."""
        subject, body = rules.customer_not_found_notice(
            BORROW, CUSTOMER, "130895", FORM_URL, reason
        )
        assert marker in body
        assert BORROW in subject
