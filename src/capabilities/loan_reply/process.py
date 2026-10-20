"""Process queued loan forms: portal -> C4C -> draft reply (workflow 06b).

Consumer half of the loan flow. Claims an item off the queue that `loan_scan`
fills, reads the customer off the approval form, asks C4C whether that customer
has a delivery block, captures a screenshot as evidence, and leaves a **draft**
reply on the original mail.

Never sends. The reply is customer-facing and asserts something about their
order, which is exactly the kind of mail a human should read before it goes out
(same reasoning as the other mail jobs).

Selectors are not inherited on faith. Both flows were driven against the live
systems on 2026-08-03 and every selector below was observed working:

* the loan form's fields live in a ``wakeup.ashx`` iframe, **not** the
  ``billform.aspx`` the ported script expected;
* C4C is reached with ``span.sapMText:text-is("Customers")`` then
  ``a:text-is("Accounts")`` -- the ported script's own route, which worked first
  try once it was actually tried.

The two profiles are opened through `jobs.edge_session`, so this job takes the
same leases workflow 03 does and the two cannot close a browser out from under
each other.

AEP port (2026-10-20): the browsers and Outlook are the host's own
(`LoanBridge`), passed to `run` with the queue folder; `process_one` is split
into `look_up` and `draft_reply` so the Workflow `engineering/rs-loan-queue-reply`
can run them as separate steps. See SOURCE.md for every difference.
"""

from __future__ import annotations

import datetime as _dt
import json
import sys
import time
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from capabilities.loan_reply import edge_session, queue, rules, templates
from capabilities.loan_reply.bridge_api import Bridge, BridgeClientError

REPO_ROOT = queue.REPO_ROOT

LogFn = Callable[[str], None]

DEFAULT_CONFIG = REPO_ROOT / "config" / "workflow-06.json"
#: AEP: beside the queue folder, as the source's `state/loan-shots` was.
SHOT_FOLDER = "loan-shots"

C4C_HOME = (
    "https://my334772-sso.crm.ondemand.com/sap/ap/ui/repository/SAP_UI/HTML5/newclient.html"
)

DEFAULTS: dict[str, Any] = {
    "loanProfile": "loan",
    "loanPort": None,       # None -> edge_session.PROFILE_PORTS
    "loanAccount": "",      # "" -> whichever account Entra lists first
    "c4cProfile": "c4c",
    "c4cPort": None,
    "c4cHomeUrl": C4C_HOME,
    "settleMs": 2500,
    "busyTimeoutMs": 25000,
    "navTimeoutMs": 90000,
    "alertRecipient": "",
    "closeBrowsersAfter": True,
    # Where editable mail text is looked for. Empty = config/loan-templates.
    # A missing directory is normal and means "use the built-in wording".
    "templateDir": "",
}

# How this job may be spread across machines (D66).
# Works through the queue in this machine's own state/ directory. Event-
# driven runs are pinned by 06; a scheduled sweep is per machine.

PARAMS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "config": {"type": "string"},
        "dryRun": {
            "type": "boolean",
            "default": False,
            "description": (
                "Read both systems but write no draft. Does not claim the item "
                "either, so a dry run is repeatable."
            ),
        },
        "maxItems": {
            "type": ["integer", "null"],
            "default": 1,
            "description": "How many queued forms to process in one run.",
        },
    },
}


class JobError(RuntimeError):
    """Anything the caller should see as a failed run."""


def load_config(path: Path | str | None) -> dict[str, Any]:
    cfg = dict(DEFAULTS)
    p = queue.resolve_config(path, DEFAULT_CONFIG)
    if p.is_file():
        raw = json.loads(p.read_text(encoding="utf-8-sig"))
        cfg.update({k: v for k, v in raw.items() if not str(k).startswith("//")})
    elif path:
        raise FileNotFoundError(f"config not found: {p}")
    return cfg


# ---------------------------------------------------------------------------
# A thin page wrapper over the Bridge browser API
# ---------------------------------------------------------------------------

#: SAPUI5 signals "still working" with three different classes. The first probe
#: of C4C watched only `.sapUiLocalBusyIndicator`, concluded the page was
#: permanently busy, and sent the whole approach down the wrong path.
BUSY_JS = (
    "() => !!document.querySelector("
    "'.sapUiLocalBusyIndicator,.sapMBusyIndicator,.sapUiBusy')"
)

URL_JS = "() => location.href"

#: Playwright's wording when the document is swapped underneath a running
#: script. Matched on text because the Bridge flattens it to an INTERNAL error.
#: Both flows navigate as a *result* of what they do -- pressing 登入 hands over
#: to the IdP, and the very next thing this job does is read `location.href` --
#: so the race is the normal case here, not an exceptional one. Same list as
#: `c4c_tickets_by_creator`.
_NAVIGATION_RACE_MARKERS = (
    "execution context was destroyed",
    "most likely because of a navigation",
    "target closed",
    "frame was detached",
    # goto's version of the same thing: the portal issues its own redirect while
    # Playwright is still driving the first navigation, and the aborted request
    # surfaces as ERR_ABORTED. Seen on a manual run of workflow 06b, 2026-08-04:
    # "Page.goto: net::ERR_ABORTED; maybe frame was detached?" against
    # FastView.aspx -- the page the retry then loaded perfectly well.
    "err_aborted",
)
_EVAL_RETRIES = 4
_EVAL_RETRY_DELAY_S = 2.0


def is_navigation_race(exc: Exception) -> bool:
    text = str(exc).lower()
    return any(marker in text for marker in _NAVIGATION_RACE_MARKERS)


class _Page:
    """Just enough of a page object for these two flows.

    Same shape as the wrapper in `c4c_tickets_by_creator`: the Bridge speaks
    HTTP, and the flows read better as `page.click(...)` than as bare posts.
    """

    def __init__(self, bridge: Bridge, session_id: str, log: LogFn, settle_sec: float):
        self.b = bridge
        self.sid = session_id
        self.log = log
        self.settle_sec = settle_sec

    def goto(self, url: str, timeout_ms: int = 90000) -> None:
        """Navigate, tolerating a redirect that aborts our own navigation.

        Both sites redirect on entry, so the request Playwright is waiting on
        can be cancelled by the very page it asked for. Retried for the same
        reason `eval` is: it says nothing about whether the target is reachable.
        """
        last: BridgeClientError | None = None
        for attempt in range(_EVAL_RETRIES):
            try:
                self.b.browser_goto(
                    self.sid, url, waitUntil="domcontentloaded", timeoutMs=timeout_ms
                )
                return
            except BridgeClientError as exc:
                if not is_navigation_race(exc):
                    raise
                last = exc
                self.log(
                    f"[loan]   navigation was aborted by a redirect; retrying "
                    f"({attempt + 1}/{_EVAL_RETRIES})"
                )
                self._wait_for_load()
                time.sleep(_EVAL_RETRY_DELAY_S)
        raise last if last else RuntimeError("goto failed without an error")

    def eval(self, script: str, *args: Any) -> Any:
        """Evaluate in the page, waiting out a navigation rather than failing.

        A destroyed execution context means the page moved while the script was
        in flight -- which says nothing about whether the job can continue. Only
        a race is retried; every other error is raised at once.
        """
        last: BridgeClientError | None = None
        for attempt in range(_EVAL_RETRIES):
            try:
                return self.b.post(
                    "/browser/eval",
                    {"sessionId": self.sid, "script": script, "args": list(args)},
                ).get("result")
            except BridgeClientError as exc:
                if not is_navigation_race(exc):
                    raise
                last = exc
                self.log(
                    f"[loan]   the page navigated mid-script; retrying "
                    f"({attempt + 1}/{_EVAL_RETRIES})"
                )
                self._wait_for_load()
                time.sleep(_EVAL_RETRY_DELAY_S)
        raise last if last else RuntimeError("eval failed without an error")

    def _wait_for_load(self, timeout_ms: int = 30000) -> None:
        try:
            self.b.post(
                "/browser/wait",
                {"sessionId": self.sid, "loadState": "load", "timeoutMs": timeout_ms},
            )
        except BridgeClientError as exc:
            self.log(f"[loan]   load-state wait was inconclusive: {str(exc)[:80]}")

    def click(self, selector: str, timeout_ms: int = 15000, optional: bool = False) -> bool:
        try:
            self.b.post(
                "/browser/click",
                {"sessionId": self.sid, "selector": selector, "timeoutMs": timeout_ms},
            )
            return True
        except BridgeClientError as exc:
            if optional:
                self.log(f"[loan]   optional click {selector} skipped: {str(exc)[:80]}")
                return False
            raise

    def fill(self, selector: str, value: str, timeout_ms: int = 15000) -> None:
        self.b.post(
            "/browser/fill",
            {"sessionId": self.sid, "selector": selector, "value": value,
             "timeoutMs": timeout_ms},
        )

    def press(self, selector: str, key: str, timeout_ms: int = 15000) -> None:
        # The router calls this field `value`, not `key`.
        self.b.post(
            "/browser/press",
            {"sessionId": self.sid, "selector": selector, "value": key,
             "timeoutMs": timeout_ms},
        )

    def url(self) -> str:
        return str(self.eval(URL_JS) or "")

    def busy_gone(self, timeout_ms: int) -> bool:
        end = time.monotonic() + timeout_ms / 1000
        while time.monotonic() < end:
            if not self.eval(BUSY_JS):
                return True
            time.sleep(1)
        return False

    def settle(self) -> None:
        time.sleep(self.settle_sec)

    def screenshot(self, path: Path) -> str | None:
        """Capture evidence. Returns the file written, or ``None``.

        Falls back to the Bridge's own screenshot directory if ours is outside
        the configured browser roots, and gives up quietly after that: the
        screenshot supports the answer, and losing it must not cost a lookup
        that already succeeded.
        """
        for body in ({"path": str(path)}, {}):
            try:
                if "path" in body:
                    path.parent.mkdir(parents=True, exist_ok=True)
                data = self.b.post(
                    "/browser/screenshot",
                    {"sessionId": self.sid, "fullPage": True, **body},
                )
                return str(data.get("path") or "") or None
            except BridgeClientError as exc:
                where = body.get("path", "the Bridge's default directory")
                self.log(f"[loan]   screenshot to {where} failed: {exc}")
        return None


# ---------------------------------------------------------------------------
# The managed browsers
# ---------------------------------------------------------------------------


class _Edge:
    """One managed Edge profile, opened on first use and closed once.

    Lazy on purpose: a run that finds an empty queue must not start a browser,
    and most runs find an empty queue.
    """

    def __init__(self, bridge: Bridge, profile: str, port: Any, cfg: Mapping[str, Any],
                 log: LogFn, *, start_url: str | None = None):
        self.b = bridge
        self.profile = profile
        self.port = edge_session.resolve_port(profile, port)
        self.cfg = cfg
        self.log = log
        self.start_url = start_url
        self._page: _Page | None = None
        self._lease: str | None = None

    def page(self) -> _Page:
        if self._page is not None:
            return self._page
        if self._lease is None:
            self.log(
                f"[loan] opening the managed Edge for profile {self.profile!r} "
                f"on port {self.port}"
            )
            # Wait for the *app*, not just for CDP. A live debugging port is not
            # a driveable page: measured against C4C, every click timed out for
            # a minute after the browser started while the tab still carried its
            # own URL as its title. `PROFILE_READY_TITLES` is where that wait is
            # defined per profile -- an entry means "wait for this", no entry
            # means the profile has nothing worth waiting for.
            opened = edge_session.open_session(
                self.b, self.profile, self.port, self.start_url, self.log,
                ready_title=edge_session.PROFILE_READY_TITLES.get(self.profile),
                owner="loan_process",
            )
            self._lease = str(opened.get("leaseId") or "") or None
        sid = self.b.browser_open(
            profile=self.profile,
            connectCdpUrl=f"http://127.0.0.1:{self.port}",
            timeoutMs=int(self.cfg.get("navTimeoutMs") or 90000),
        )["sessionId"]
        self._page = _Page(
            self.b, sid, self.log, float(self.cfg.get("settleMs") or 2500) / 1000
        )
        return self._page

    def drop_session(self) -> None:
        """Discard the driving session, keeping the browser and the lease.

        A timed-out browser operation leaves the session wedged -- the Bridge's
        own error says as much -- and every later item inherits it. Without this
        one bad form turns a five-item run into five failures.
        """
        page, self._page = self._page, None
        if page is not None:
            _suppress(lambda: self.b.browser_close(page.sid))

    def close(self, close_browser: bool) -> None:
        self.drop_session()
        if self._lease is None:
            return
        lease, self._lease = self._lease, None
        if not close_browser:
            # Still release the lease. Holding it would stop workflow 03 from
            # ever closing the browser, for as long as the TTL lasts.
            _suppress(lambda: edge_session.release_lease(self.profile, lease))
            return
        _suppress(lambda: edge_session.close_session(
            self.b, self.profile, self.port, force=False, grace_sec=10,
            log=self.log, lease_id=lease,
        ))


def _suppress(fn: Callable[[], Any]) -> None:
    """Run teardown, reporting but swallowing its errors.

    Swallowed so a failed cleanup cannot mask the real outcome; reported so it
    does not vanish either.
    """
    try:
        fn()
    except Exception as exc:  # noqa: BLE001
        print(f"[loan] teardown: {exc}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Flow 1 -- the loan portal
# ---------------------------------------------------------------------------

#: Reads every filled, labelled input across same-origin frames. The fields sit
#: in a `wakeup.ashx` iframe on the same host, so `contentDocument` reaches them
#: and this job needs no frame support in the Bridge. By label rather than by
#: control id on purpose: the ids are ExtJS sequence numbers
#: (`combosvw-1025-inputEl`) that shift whenever the form's controls change.
READ_FORM_FIELDS = """() => {
  const norm = t => (t || '').replace(/\\s+/g, ' ').replace(/[:：]\\s*$/, '').trim();
  const out = {};
  const visit = (doc) => {
    let els = [];
    try {
      els = [...doc.querySelectorAll('input[type=text], input:not([type]), textarea, select')]
        .filter(e => e.offsetParent && (e.value || '').trim());
    } catch (e) { return; }
    for (const inp of els) {
      let label = '', node = inp, guard = 0;
      while (node && guard < 6 && !label) {
        const prev = node.previousElementSibling;
        if (prev) {
          const t = norm(prev.innerText || prev.textContent);
          if (t && t.length <= 20) { label = t; break; }
        }
        node = node.parentElement; guard++;
      }
      if (label && !(label in out)) out[label] = (inp.value || '').trim();
    }
    let frames = [];
    try { frames = [...doc.querySelectorAll('iframe')]; } catch (e) { return; }
    for (const f of frames) {
      try { if (f.contentDocument) visit(f.contentDocument); } catch (e) {}
    }
  };
  visit(document);
  return out;
}"""

FIELD_CUSTOMER = "客戶名稱"
FIELD_EMAIL = "E-mail"
FIELD_BORROW_NO = "單據編號"

LOGIN_BUTTON = "#btnLogin"
FORM_PAGE = "flowsingle.aspx"
LOGIN_PAGE = "login.aspx"
ERROR_PAGE = "errorpage.aspx"

#: The portal hands sign-in to Entra, which shows an account picker rather than
#: a password prompt -- the machine is domain-joined, so choosing the account is
#: the whole of it.
IDP_HOST = "login.microsoftonline.com"

#: One tile per remembered account. `data-test-id` carries the address; the
#: "Use another account" tile is `#otherTile` and has no `data-test-id`, so
#: requiring the attribute is what keeps this off it. `nth=0` because
#: `page.click` is strict and a second remembered account would otherwise turn
#: a working sign-in into an error. Observed 2026-08-03.
ACCOUNT_TILE = 'div.table[role="button"][data-test-id] >> nth=0'

#: How many times to look at the URL before giving up. Times `settleMs`, so the
#: default is ~50s -- enough for the IdP round trip, which is the slow part.
NAV_ATTEMPTS = 20


def account_tile(address: str) -> str:
    """The picker tile for ``address``, or the first remembered account."""
    if not address:
        return ACCOUNT_TILE
    return f'div.table[role="button"][data-test-id="{address}"]'


def page_name(url: str) -> str:
    """The lowercased last path segment of ``url``, without the query string.

    Matching on the whole URL does not work here: the portal's sign-in page is
    ``/login.aspx?ReturnUrl=%2fFlowSingle.aspx``, so a substring test for the
    form's name matches the *login* page too and the job would read fields off
    a form that never opened.
    """
    path = (url or "").split("#", 1)[0].split("?", 1)[0]
    return path.rsplit("/", 1)[-1].lower()


def read_loan_form(page: _Page, loan_url: str, log: LogFn, account: str = "") -> dict[str, str]:
    """Open the approval form and return its labelled fields.

    The portal keeps its own session, separate from C4C's. When it has lapsed,
    signing in is two clicks and no typing: `登入` on the portal's own page, then
    the account tile Entra offers. Neither is the normal path -- usually the
    profile is signed in already and the first URL check passes.
    """
    page.goto(loan_url)
    for _ in range(NAV_ATTEMPTS):
        page.settle()
        full = page.url()
        name = page_name(full)
        if name == FORM_PAGE:
            break
        if name == ERROR_PAGE:
            # A rejected form answers with a null-reference error page. The
            # scanner drops 否決 notices before they are ever queued, so landing
            # here means the form changed state after it was enqueued.
            raise JobError(f"the portal refused to open this form: {full[:160]}")
        if name == LOGIN_PAGE:
            log("[loan]   portal session has lapsed; pressing 登入")
            page.click(LOGIN_BUTTON, optional=True)
        elif IDP_HOST in full.lower():
            log(f"[loan]   choosing the account tile {account or '(the first one)'}")
            page.click(account_tile(account), optional=True)
    else:
        raise JobError(f"never reached the approval form; stopped at {page.url()[:160]}")

    fields: dict[str, str] = {}
    for _ in range(8):
        fields = page.eval(READ_FORM_FIELDS) or {}
        if (fields.get(FIELD_CUSTOMER) or "").strip():
            return fields
        time.sleep(2)
    raise JobError(
        f"the form loaded but {FIELD_CUSTOMER} never appeared. The portal renders "
        f"its fields asynchronously, so a slow load looks exactly like this. "
        f"Labels seen: {sorted(fields)[:8]}"
    )


# ---------------------------------------------------------------------------
# Flow 2 -- C4C delivery blocks
# ---------------------------------------------------------------------------

#: Two controls that exist only once the Accounts list is really up. Better than
#: checking the URL, which C4C rewrites long before the list renders.
ACCOUNTS_READY = """() => ({
  adv: !!document.querySelector('button[title="Advanced Search"]'),
  view: !!document.querySelector('button[title="Select View"]')
})"""

RESULT_LINKS = """() => [...document.querySelectorAll('[id$="-listUl-body"] a')]
    .map(e => (e.innerText || '').trim()).filter(t => t)"""

SCROLL_TO_BLOCKS = """() => {
  const el = [...document.querySelectorAll('.sapMLabel, span')]
      .find(e => (e.innerText || '').trim() === 'Classification Delivery Block');
  if (el) el.scrollIntoView({block: 'center'});
  return !!el;
}"""

#: The label sits in a <BDI> inside a `.sapMLabel` span, and its value in the
#: same form-element container -- so the value is whatever that container holds
#: beyond the label text itself.
#:
#: **`null` and `""` mean different things.** `null` is "the label is not on
#: this page"; `""` is "the label is there and the field is empty". Collapsing
#: them is the worst bug this job could have: an empty read would then be
#: indistinguishable from a C4C layout change, and every customer would be told
#: their instrument is on its way. Verified 2026-08-03 against customer 115776,
#: where the same reader returns values for 30 other fields on the page and ""
#: for these two -- so that customer really is unblocked.
READ_BLOCKS = """() => {
  const norm = t => (t || '').replace(/\\s+/g, ' ').trim();
  const getVal = (label) => {
    const cands = [...document.querySelectorAll('.sapMLabel, span, label, bdi')];
    const labelEl = cands.find(e => norm(e.innerText) === label && e.offsetParent);
    if (!labelEl) return null;
    let box = labelEl.parentElement, guard = 0;
    while (box && guard < 4) {
      const t = norm(box.innerText);
      if (t !== label && t.startsWith(label)) return t.slice(label.length).trim();
      box = box.parentElement; guard++;
    }
    return '';
  };
  return {
    classificationDeliveryBlock: getVal('Classification Delivery Block'),
    deliveryBlock: getVal('Delivery Block'),
    erpCustomerId: getVal('ERP Customer ID')
  };
}"""

NAV_CUSTOMERS = 'span.sapMText:text-is("Customers")'
NAV_ACCOUNTS = 'a:text-is("Accounts")'
SEARCH_BUTTON = 'button[title="Search"]'
SEARCH_FIELD = '[id$="-searchField-I"]'
FIRST_RESULT = '[id$="-listUl-body"] a'
DETAILS_TAB = 'text="Details"'


def open_accounts(page: _Page, cfg: Mapping[str, Any], busy_ms: int) -> None:
    """Navigate C4C's shell to the Accounts list."""
    page.goto(str(cfg.get("c4cHomeUrl") or C4C_HOME), int(cfg.get("navTimeoutMs") or 90000))
    page.busy_gone(busy_ms)
    page.settle()

    for _ in range(3):
        ready = page.eval(ACCOUNTS_READY) or {}
        if ready.get("adv") and ready.get("view"):
            return
        page.click(NAV_CUSTOMERS, optional=True)
        time.sleep(1.5)
        page.click(NAV_ACCOUNTS, optional=True)
        page.busy_gone(busy_ms)
        page.settle()
    raise JobError(
        "could not reach the C4C Accounts list -- the shell rendered but "
        "Customers -> Accounts never produced the list's own controls"
    )


def read_delivery_blocks(
    page: _Page, customer_id: str, cfg: Mapping[str, Any], log: LogFn
) -> rules.BlockStatus:
    """Look the customer up in C4C and read both delivery-block fields."""
    busy_ms = int(cfg.get("busyTimeoutMs") or 25000)
    open_accounts(page, cfg, busy_ms)

    try:
        page.fill(SEARCH_FIELD, f"*{customer_id}*")
    except BridgeClientError:
        # The search box stays collapsed behind the magnifier until it is
        # pressed, and which of the two states the list opens in varies.
        page.click(SEARCH_BUTTON, optional=True)
        time.sleep(1.5)
        page.fill(SEARCH_FIELD, f"*{customer_id}*")
    page.press(SEARCH_FIELD, "Enter")
    page.busy_gone(busy_ms)
    page.settle()

    rows = page.eval(RESULT_LINKS) or []
    if not rows:
        # One retry before concluding there is no such customer: an empty first
        # read is usually the list still rendering, and "no result" must never
        # be mistaken for "no block".
        time.sleep(3)
        rows = page.eval(RESULT_LINKS) or []
    if not rows:
        log(f"[loan]   C4C has no account matching {customer_id}")
        return rules.BlockStatus(found=False, reason=rules.REASON_NO_ACCOUNT)
    log(f"[loan]   C4C matched {len(rows)} row(s); first = {rows[0]!r}")

    page.click(FIRST_RESULT)
    page.busy_gone(busy_ms)
    page.settle()
    page.click(DETAILS_TAB, optional=True)
    page.busy_gone(busy_ms)
    page.settle()

    # SAPUI5 renders this section lazily, so keep the longest value seen across
    # attempts rather than trusting whatever the first read returned. `None`
    # stays None until a read actually finds the label.
    keys = ("classificationDeliveryBlock", "deliveryBlock", "erpCustomerId")
    best: dict[str, str | None] = dict.fromkeys(keys)
    for _ in range(5):
        page.eval(SCROLL_TO_BLOCKS)
        time.sleep(1.8)
        got = page.eval(READ_BLOCKS) or {}
        for key in keys:
            value = got.get(key)
            if value is None:
                continue
            if best[key] is None or len(str(value)) > len(str(best[key])):
                best[key] = str(value)
        if all(best[k] is not None for k in keys) and (
            best["classificationDeliveryBlock"] or best["deliveryBlock"]
        ):
            break

    missing = [k for k in ("classificationDeliveryBlock", "deliveryBlock") if best[k] is None]
    if missing:
        # Not "unblocked". Nobody read anything, so there is nothing to assert.
        log(f"[loan]   WARN the C4C page has no {', '.join(missing)} field")
        return rules.BlockStatus(found=False, reason=rules.REASON_FIELDS_UNREADABLE)

    opened = (best["erpCustomerId"] or "").strip()
    if opened and opened != customer_id:
        # The search matches on more than the id -- 5 rows for one number is
        # normal -- so confirm the row that opened is the one asked for before
        # saying anything about it.
        log(f"[loan]   WARN opened ERP Customer ID {opened!r}, expected {customer_id!r}")
        return rules.BlockStatus(found=False, reason=rules.REASON_WRONG_ACCOUNT)

    return rules.BlockStatus(
        found=True,
        classification_delivery_block=best["classificationDeliveryBlock"] or "",
        delivery_block=best["deliveryBlock"] or "",
    )


# ---------------------------------------------------------------------------
# One item, end to end
# ---------------------------------------------------------------------------


def _attachments(path: str | None) -> list[dict[str, str]]:
    return [{"path": path}] if path else []


def process_one(
    bridge: Bridge,
    item: queue.QueueItem,
    cfg: Mapping[str, Any],
    loan_edge: _Edge,
    c4c_edge: _Edge,
    log: LogFn,
    dry_run: bool,
) -> dict[str, Any]:
    result, subject, body = look_up(item, cfg, loan_edge, c4c_edge, log)
    if dry_run:
        result["draft"] = None
        result["bodyPreview"] = body
        return result
    result["draft"] = draft_reply(bridge, result, subject, body, cfg)
    return result


def look_up(
    item: queue.QueueItem,
    cfg: Mapping[str, Any],
    loan_edge: _Edge,
    c4c_edge: _Edge,
    log: LogFn,
) -> tuple[dict[str, Any], str | None, str]:
    """Steps 1-3 of `process_one`: the form, C4C, and which message to write.
    Returns the result, the subject (``None`` for a reply on the original
    mail) and the body. Writes nothing but the screenshot (AEP split)."""
    payload = item.payload
    borrow_no = str(payload.get("borrowNo") or item.borrow_no)
    loan_url = str(payload.get("loanUrl") or "")
    entry_id = str(payload.get("entryId") or "")
    stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    result: dict[str, Any] = {
        "borrowNo": borrow_no,
        "entryId": entry_id,
        "loanUrl": loan_url,
        "category": payload.get("category"),
    }

    # -- 1. the loan portal: who is the customer? --------------------------
    fields = read_loan_form(loan_edge.page(), loan_url, log, str(cfg.get("loanAccount") or ""))
    customer_raw = fields.get(FIELD_CUSTOMER, "")
    customer_id, customer_name = rules.split_customer(customer_raw)
    result.update(
        customerRaw=customer_raw,
        customerId=customer_id,
        customerName=customer_name,
        customerEmail=fields.get(FIELD_EMAIL, ""),
        formBorrowNo=fields.get(FIELD_BORROW_NO, ""),
    )
    log(f"[loan] {borrow_no}: {FIELD_CUSTOMER}={customer_raw!r} -> customerId={customer_id!r}")
    if not customer_id:
        raise JobError(
            f"no customer id in {FIELD_CUSTOMER} {customer_raw!r} -- the form writes "
            "it as '<id>,<name>', so this one was filled in some other shape"
        )
    if result["formBorrowNo"] and result["formBorrowNo"] != borrow_no:
        # Worth saying out loud: it means the queued mail and the page it opened
        # disagree about which form this is.
        log(f"[loan]   WARN the form says {FIELD_BORROW_NO}={result['formBorrowNo']!r}, "
            f"the mail said {borrow_no!r}")

    # -- 2. C4C: is that customer blocked? ---------------------------------
    c4c_page = c4c_edge.page()
    status = read_delivery_blocks(c4c_page, customer_id, cfg, log)
    shots = Path(cfg.get("shotDir") or queue.QUEUE_ROOT.parent / SHOT_FOLDER)
    shot = c4c_page.screenshot(shots / f"{borrow_no}_{stamp}.png")
    result["blocks"] = status.as_dict()
    result["screenshot"] = shot

    # -- 3. the reply ------------------------------------------------------
    # Everything the templates may refer to, whichever message is chosen. Built
    # once so a placeholder that works in one reply cannot be missing from
    # another purely because of which branch produced it.
    fields_for_template = {
        "templateDir": cfg.get("templateDir"),
        "category": payload.get("category") or "",
        "customerRaw": customer_raw,
        "customerId": customer_id,
        "customerName": customer_name,
        "customerEmail": result["customerEmail"],
        "loanUrl": loan_url,
    }
    if not status.found:
        subject, body = rules.customer_not_found_notice(
            borrow_no, customer_raw, customer_id, loan_url, status.reason,
            **{k: v for k, v in fields_for_template.items()
               if k not in ("customerRaw", "customerId", "loanUrl")},
        )
        result.update(outcome="customer-not-found", draftKind="internal-notice")
    elif status.blocked:
        subject, body = None, rules.blocked_reply(borrow_no, status, **fields_for_template)
        result.update(outcome="blocked", draftKind="reply")
    else:
        subject, body = None, rules.shipping_reply(borrow_no, **fields_for_template)
        result.update(outcome="shipping", draftKind="reply")
    log(f"[loan] {borrow_no}: {result['outcome']}")
    return result, subject, body


def draft_reply(
    bridge: Bridge,
    result: Mapping[str, Any],
    subject: str | None,
    body: str,
    cfg: Mapping[str, Any],
) -> Any:
    """Step 4 of `process_one`: the draft, never sent (AEP split)."""
    entry_id = str(result.get("entryId") or "")
    shot = result.get("screenshot")
    if subject is None:
        if not entry_id:
            raise JobError("the queued item carries no entryId, so there is no mail to reply to")
        return bridge.post("/email/reply", {
            "entryId": entry_id,
            "body": body,
            "attachments": _attachments(shot),
            "send": False,
        })
    return bridge.email_draft(
        to=[cfg["alertRecipient"]] if cfg.get("alertRecipient") else [],
        subject=subject,
        body=body,
        attachments=_attachments(shot),
        send=False,
    )


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------

#: Bridge client methods this job needs. Checked up front because the failure
#: mode is otherwise a bare AttributeError out of a stale Bridge process, which
#: reads like a bug in this file (see the same note in edge_session).
REQUIRED_BRIDGE_METHODS = ("email_draft", "browser_open", "browser_goto", "browser_close")


def _bridge() -> Bridge:
    # The source built its HTTP Bridge client here. In AEP the host passes
    # its `LoanBridge` to `run`; there is no default.
    raise JobError("no browser or Outlook: the AEP Workflow passes the host's LoanBridge")


def _check_bridge(b: Bridge) -> Bridge:
    missing = [m for m in REQUIRED_BRIDGE_METHODS if not hasattr(b, m)]
    if missing:
        raise JobError(
            "the running Bridge process predates this job: its copy of "
            f"jobs/_bridge_client.py has no {', '.join(missing)}. Restart the "
            "Bridge (Ctrl-C in its window, then run-bridge.ps1)."
        )
    return b


def run(params: Mapping[str, Any] | None = None, log: LogFn | None = None, *,
        bridge: Bridge | None = None, root: Path | None = None) -> dict[str, Any]:
    p = dict(params or {})
    say: LogFn = log or (lambda _m: None)
    cfg = p.pop("_config", None) or load_config(p.get("config"))
    if root is not None and not cfg.get("shotDir"):
        cfg = {**cfg, "shotDir": str(root.parent / SHOT_FOLDER)}
    dry_run = bool(p.get("dryRun", False))
    max_items = max(1, int(p.get("maxItems") or 1))

    bridge = _check_bridge(bridge if bridge is not None else _bridge())
    loan_edge = _Edge(bridge, str(cfg["loanProfile"]), cfg.get("loanPort"), cfg, say)
    # C4C is opened *on* its home page so the ready-title wait has something to
    # watch; the portal is not, because each item navigates to its own form URL.
    c4c_edge = _Edge(bridge, str(cfg["c4cProfile"]), cfg.get("c4cPort"), cfg, say,
                     start_url=str(cfg.get("c4cHomeUrl") or C4C_HOME))

    # One consumer at a time. Two would each open their own Edge session on the
    # same profile -- untested, and it doubles what the portal sees from this
    # machine. Overlap became likely once an arriving mail can trigger a run
    # rather than only a ten-minute tick.
    #
    # Taken here, after everything that can fail while preparing: a lock held
    # across a raising _bridge() would block every run until its TTL over a
    # problem that has nothing to do with concurrency.
    try:
        run_lock = queue.acquire_run_lock(
            "loan_process", root, owner=str(p.get("workflowName") or ""))
    except queue.RunLockBusy as busy:
        # Not a failure. The run that got here first is working through the same
        # queue and will pick up whatever this one would have. Reporting success
        # with nothing processed is the honest answer -- failing the workflow on
        # every burst of arriving mail would teach people to ignore it.
        say(f"[loan] {busy}")
        return {
            "processed": 0, "failed": 0, "skipped": True, "skipReason": str(busy),
            "outcomes": {k: 0 for k in ("blocked", "shipping", "customer-not-found")},
            "items": [], "failures": [], "queue": queue.counts(root), "dryRun": dry_run,
        }

    processed: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    # A dry run reads the queue without claiming, so it can be repeated.
    peek = iter(list(queue.iter_pending(root))[:max_items]) if dry_run else None

    try:
        for _ in range(max_items):
            item = next(peek, None) if peek is not None else queue.claim_one(root)
            if item is None:
                break
            say(f"[loan] {'inspecting' if dry_run else 'claimed'} {item.borrow_no}")
            try:
                outcome = process_one(bridge, item, cfg, loan_edge, c4c_edge, say, dry_run)
            except (ConnectionError, templates.TemplateError) as exc:
                # Neither is this form's fault, and neither gets better on the
                # next one: an unreachable Bridge stays unreachable, and a
                # template with a typo in it fails identically for every form.
                # So hand the item back and stop, rather than burning the queue
                # marking healthy forms as failed and drafting one identical
                # notice per form.
                if not dry_run:
                    queue.requeue(item, root)
                if isinstance(exc, templates.TemplateError):
                    why = f"a mail template cannot be used: {exc}"
                    fix = "Fix the .txt file (or delete it to return to the built-in text)"
                else:
                    why = ("the browser or Outlook is not answering, so it is most likely "
                           f"not running ({exc})")
                    fix = "Check that Edge and Outlook start on this computer"
                raise JobError(
                    f"stopped after {len(processed)} item(s): {why}. "
                    f"{item.borrow_no} has been put back in the queue and nothing "
                    f"was marked failed. {fix} and run again."
                ) from exc
            except (JobError, BridgeClientError) as exc:
                say(f"[loan] {item.borrow_no} FAILED: {exc}")
                failures.append({"borrowNo": item.borrow_no, "error": str(exc)})
                # Start the next item from a fresh session on both sides. One
                # item's wedged browser must not be inherited by the rest.
                loan_edge.drop_session()
                c4c_edge.drop_session()
                if dry_run:
                    continue
                draft_failure_notice(bridge, item.borrow_no,
                                     str(item.payload.get("loanUrl") or ""), str(exc), cfg, say)
                # 'failed', not back to 'pending': a form that failed needs a
                # human to look at it, and an automatic retry would just draft
                # the same notice again every few minutes.
                queue.finish(item, "failed", {"error": str(exc)}, root)
                continue
            processed.append(outcome)
            if not dry_run:
                queue.finish(item, "done", outcome, root)
    finally:
        close_after = bool(cfg.get("closeBrowsersAfter", True))
        loan_edge.close(close_after)
        c4c_edge.close(close_after)
        # Released here rather than at the end of the happy path: an exception
        # on the way out would otherwise leave the lock until its TTL, blocking
        # every run for the next twenty minutes over a failure that is already
        # being reported.
        run_lock.release()

    return {
        "processed": len(processed),
        "failed": len(failures),
        "skipped": False,
        "outcomes": {
            kind: sum(1 for r in processed if r.get("outcome") == kind)
            for kind in ("blocked", "shipping", "customer-not-found")
        },
        "items": processed,
        "failures": failures,
        "queue": queue.counts(root),
        "dryRun": dry_run,
    }


def draft_failure_notice(bridge: Bridge, borrow_no: str, loan_url: str, error: str,
                         cfg: Mapping[str, Any], say: LogFn) -> Any:
    """The internal notice for a form that could not be finished, drafted
    best effort (the source's inline block, named for the AEP draft step).
    Returns what the draft call returned, or ``None`` when it failed."""
    subject, body, warnings = rules.failure_notice(
        borrow_no, loan_url, error, templateDir=cfg.get("templateDir"),
    )
    for w in warnings:
        say(f"[loan]   WARN {w}")
    drafted: list[Any] = []
    _suppress(lambda: drafted.append(bridge.email_draft(
        to=[cfg["alertRecipient"]] if cfg.get("alertRecipient") else [],
        subject=subject, body=body, send=False,
    )))
    return drafted[0] if drafted else None
