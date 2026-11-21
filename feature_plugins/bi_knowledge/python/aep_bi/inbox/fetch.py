"""Fetching a shared link: HTTP first, the local headless browser only behind a switch.

A page is read over HTTP with this PC's proxy settings (the company proxy is
legitimate), a time limit and a size limit; a refusal is reported with its real
HTTP status or error, never worked around. Threads and Instagram serve a shared
post's `og:` meta to a plain request and render the rest by script; Instagram
often answers with its login page instead. `login_page` recognises that, and the
caller may then try `browser_fetch` (the existing `integrations.browser` Edge
profile, `docs/phases/TELEGRAM_LINK_COLLECTION_ASSESSMENT_20261119.md` §5/§8),
which is off unless the owner turns it on after testing real links. An X (Twitter)
post is read from its public no-login endpoints instead (`aep_bi.inbox.xpost`).
"""

from __future__ import annotations

import hashlib
import re
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from aep_bi.cards import html_markdown

#: D9 of the assessment: a page at most 5 MB, 30 seconds.
MAX_PAGE_BYTES = 5 * 1024 * 1024
TIMEOUT_S = 30.0
#: The quick read for the reply's title line: smaller and sooner.
PREVIEW_BYTES = 512 * 1024
PREVIEW_TIMEOUT_S = 6.0
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AEP-BI-Inbox/1.0"
#: Query parameters that only track who shared a link.
_TRACKING = re.compile(
    r"^(utm_[a-z_]+|fbclid|gclid|igsh|igshid|mibextid|si|ref_src|ref|xmt|_ga|mc_cid|mc_eid)$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Fetched:
    """One fetch. `body` is the page as served; `status` its HTTP status (None when
    no answer came); `code` names a failure."""

    url: str
    final_url: str
    status: int | None
    body: bytes
    content_type: str
    method: str  # http | browser
    code: str | None = None

    @property
    def ok(self) -> bool:
        return self.code is None and self.status == 200 and bool(self.body)

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.body).hexdigest()


#: How a page is fetched: (url, byte limit, seconds) -> Fetched. Tests give their own.
Fetcher = Callable[[str, int, float], Fetched]


def normalize(url: str) -> str:
    """The address without what only says who shared it: tracking parameters, the
    fragment, a trailing slash, the case of the scheme and host. An X post becomes
    `https://x.com/<handle>/status/<id>` whatever host (twitter.com, mobile., www.) and
    share parameters (`s`, `t`, ...) it came with."""
    from aep_bi.inbox import xpost

    post = xpost.status_of(url.strip())
    if post is not None:
        return xpost.post_url(*post)
    parts = urllib.parse.urlsplit(url.strip())
    query = [
        (key, value)
        for key, value in urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
        if not _TRACKING.match(key)
    ]
    path = parts.path.rstrip("/") or "/"
    return urllib.parse.urlunsplit(
        (
            parts.scheme.lower(),
            parts.netloc.lower(),
            path,
            urllib.parse.urlencode(query),
            "",
        )
    )


def platform(url: str) -> str:
    """`threads`, `instagram`, `x` (x.com, twitter.com and their subdomains, and X's
    shortener t.co until it is expanded) or `web`."""
    from aep_bi.inbox import xpost

    host = urllib.parse.urlsplit(url).netloc.lower().split(":")[0]
    if xpost.is_x(url) or xpost.is_short(url):
        return "x"
    if host.endswith(("threads.net", "threads.com")):
        return "threads"
    if host.endswith(("instagram.com", "instagr.am")):
        return "instagram"
    return "web"


_LOGIN_MARKS = (
    "/accounts/login",
    'id="loginForm"',
    "login_form",
    'name="password"',
    "Log in • Instagram",
    "Login • Instagram",
    "登入 • Instagram",
)


def login_page(fetched: Fetched) -> bool:
    """Whether a social site answered with its login wall instead of the post: a
    redirect to a login address, or a login form with no `og:description`."""
    path = urllib.parse.urlsplit(fetched.final_url).path.lower().rstrip("/")
    if "/accounts/login" in path or path.endswith("/login"):
        return True
    text = html_markdown.decode(fetched.body[:300_000])
    page = html_markdown.read(text)
    marked = any(mark in text for mark in _LOGIN_MARKS)
    return marked and not page.description


def http_fetch(url: str, limit: int = MAX_PAGE_BYTES, timeout_s: float = TIMEOUT_S) -> Fetched:
    """GET the page at `url` with this PC's proxy settings; never raises."""
    return _get(url, limit, timeout_s, "text/html,application/xhtml+xml;q=0.9,*/*;q=0.5")


def api_fetch(url: str, limit: int = MAX_PAGE_BYTES, timeout_s: float = TIMEOUT_S) -> Fetched:
    """GET a public JSON answer (X's syndication and oEmbed endpoints) the same way;
    only a JSON answer counts."""
    return _get(url, limit, timeout_s, "application/json", json_only=True)


def _get(url: str, limit: int, timeout_s: float, accept: str, json_only: bool = False) -> Fetched:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": accept,
            "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as answer:  # noqa: S310 - http(s) only
            body = answer.read(limit + 1)
            final = answer.geturl()
            kind = answer.headers.get("Content-Type", "")
            status = answer.status
    except urllib.error.HTTPError as error:
        return Fetched(url, url, error.code, b"", "", "http", f"http_{error.code}")
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as error:
        reason = getattr(error, "reason", error)
        return Fetched(url, url, None, b"", "", "http", f"fetch_failed:{type(reason).__name__}")
    if len(body) > limit:
        return Fetched(url, final, status, b"", kind, "http", "page_too_large")
    if json_only:
        if "json" not in kind.lower():
            return Fetched(url, final, status, b"", kind, "http", "not_json")
        return Fetched(url, final, status, body, kind, "http")
    if kind and "html" not in kind.lower() and "xml" not in kind.lower():
        return Fetched(url, final, status, b"", kind, "http", "not_a_page")
    return Fetched(url, final, status, body, kind, "http")


def browser_fetch(url: str, profile: Path, timeout_s: float = TIMEOUT_S) -> Fetched:
    """The page as the local headless Edge renders it, in BI's own browser profile;
    the browser is always closed again. Used only when the owner turned it on."""
    from integrations.browser import Browser, BrowserError

    try:
        with Browser(profile, headless=True, timeout_s=timeout_s) as browser:
            browser.navigate(url, settle_s=2.0)
            html = browser.evaluate("document.documentElement.outerHTML")
            final = browser.evaluate("location.href")
    except BrowserError as error:
        return Fetched(url, url, None, b"", "", "browser", f"browser_{error.code}")
    except Exception as error:  # noqa: BLE001 - reported, never raised into the schedule
        return Fetched(url, url, None, b"", "", "browser", f"browser_failed:{type(error).__name__}")
    body = str(html or "").encode("utf-8")
    return Fetched(url, str(final or url), 200, body, "text/html; charset=utf-8", "browser")
