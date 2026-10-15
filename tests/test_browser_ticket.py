"""One-click sign-in from Agent Web to the Member Portal (owner 2026-10-15,
`docs/phases/PLATFORM_OVERVIEW.md` "One-click sign-in from Agent Web").

A member session (the Personal Agent's) obtains a single-use browser sign-in
ticket valid for at most 60 seconds; the portal page redeems it once at
`sign-in/ticket` for a normal browser login and session. Tickets are stored
as fingerprints only, refused for disabled members, and never accepted from a
query string.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import astuple
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from test_asset_access import _browser_missing
from test_capability_shelf import _published
from test_member_publish import _signed_in
from test_shared_platform_app import request

from control_plane.app import SharedPlatformApplication
from control_plane.member_page import PAGE
from control_plane.member_ticket import (
    TICKET_LOGIN_LABEL,
    TICKET_METHOD,
    TICKET_TTL,
    BrowserTickets,
)

NOW = datetime(2026, 10, 15, 9, 0, tzinfo=UTC)


def _app(tmp_path: Path, moment: list[datetime]) -> SharedPlatformApplication:
    return SharedPlatformApplication.empty(
        administrators=("platform-admin",),
        registry_path=tmp_path / "registry.sqlite",
        clock=lambda: moment[0],
    )


def _url(app: SharedPlatformApplication, operation: str) -> str:
    return app.member_base_url + "/v1/member/" + operation


def _ticket(app: SharedPlatformApplication, session: str) -> str:
    status, reply = request(_url(app, "browser-ticket"), authorization=session, body={})
    assert status == 200, reply
    assert set(reply) == {"ticket", "expires_at"}
    return str(reply["ticket"])


def _redeem(app: SharedPlatformApplication, ticket: str) -> tuple[int, dict[str, Any]]:
    return request(_url(app, "sign-in/ticket"), authorization=f"Ticket {ticket}", method="POST")


def test_a_ticket_needs_a_member_session_and_signs_a_browser_in_once(tmp_path: Path) -> None:
    moment = [NOW]
    with _app(tmp_path, moment) as app:
        leo = _signed_in(app, "leo", "member")
        # No session, a login instead of a session, or a fake session: refused.
        assert request(_url(app, "browser-ticket"), body={})[0] == 401
        assert request(_url(app, "browser-ticket"), authorization="Login a:b", body={})[0] == 401
        assert (
            request(_url(app, "browser-ticket"), authorization="Bearer s-1:nope", body={})[0] == 401
        )
        assert (
            request(_url(app, "browser-ticket"), authorization=leo, body={"actor": "root"})[1][
                "code"
            ]
            == "invalid_request"
        )

        status, issued = request(_url(app, "browser-ticket"), authorization=leo, body={})
        assert status == 200
        ticket = issued["ticket"]
        assert ticket.startswith("ticket-") and len(ticket.partition(":")[2]) >= 40
        expires = datetime.fromisoformat(issued["expires_at"])
        assert expires - NOW == TICKET_TTL <= timedelta(seconds=60)

        status, signed = _redeem(app, ticket)
        assert status == 200, signed
        assert set(signed) == {"session", "login", "expires_at"}
        browser = f"Bearer {signed['session']}"
        status, me = request(_url(app, "me"), authorization=browser, body={})
        assert status == 200 and me["actor"] == "leo"
        # The same browser login a password sign-in gives, renewable.
        status, renewed = request(
            _url(app, "session"), method="POST", authorization=f"Login {signed['login']}"
        )
        assert status == 200 and renewed["session"]
        [login] = [
            g for g in app.state.logins.active("leo", now=NOW) if g.label == TICKET_LOGIN_LABEL
        ]
        assert login.login_id == signed["login"].partition(":")[0]
        session_id, _, session_secret = signed["session"].partition(":")
        assert (
            app.state.sessions.authenticate(session_id, session_secret, now=NOW).method
            == TICKET_METHOD
        )

        # Single use: the same ticket again is refused.
        status, again = _redeem(app, ticket)
        assert (status, again["code"]) == (409, "ticket_used")
        # A made-up or tampered ticket.
        assert _redeem(app, "ticket-0000000000000000:" + "x" * 43)[1]["code"] == (
            "authentication_failed"
        )
        fresh = _ticket(app, leo)
        assert _redeem(app, fresh.partition(":")[0] + ":" + "y" * 43)[1]["code"] == (
            "authentication_failed"
        )
        assert _redeem(app, fresh)[0] == 200
        assert (
            request(_url(app, "sign-in/ticket"), method="POST", authorization="Bearer " + fresh)[1][
                "code"
            ]
            == "authentication_failed"
        )


def test_a_ticket_expires_after_a_minute(tmp_path: Path) -> None:
    moment = [NOW]
    with _app(tmp_path, moment) as app:
        leo = _signed_in(app, "leo", "member")
        inside, late = _ticket(app, leo), _ticket(app, leo)
        moment[0] = NOW + timedelta(seconds=59)
        assert _redeem(app, inside)[0] == 200
        moment[0] = NOW + timedelta(seconds=60)
        status, refused = _redeem(app, late)
        assert (status, refused["code"]) == (401, "ticket_expired")
        # And it is used up by that attempt.
        assert _redeem(app, late)[1]["code"] == "ticket_used"
    with pytest.raises(ValueError):
        BrowserTickets(ttl=timedelta(seconds=61))


def test_a_disabled_member_gets_no_ticket_and_cannot_redeem_one(tmp_path: Path) -> None:
    moment = [NOW]
    with _app(tmp_path, moment) as app:
        leo = _signed_in(app, "leo", "member")
        before = _ticket(app, leo)
        app.state.enrollment.disable_user("platform-admin", "leo")
        status, refused = request(_url(app, "browser-ticket"), authorization=leo, body={})
        assert (status, refused["code"]) == (403, "actor_disabled")
        status, refused = _redeem(app, before)
        assert (status, refused["code"]) == (403, "actor_disabled")
        assert not [
            g for g in app.state.logins.active("leo", now=NOW) if g.label == TICKET_LOGIN_LABEL
        ]


def test_tickets_are_stored_as_fingerprints_and_never_read_from_a_query(
    tmp_path: Path,
    capfd: pytest.CaptureFixture[str],
) -> None:
    moment = [NOW]
    with _app(tmp_path, moment) as app:
        leo = _signed_in(app, "leo", "member")
        ticket = _ticket(app, leo)
        ticket_id, _, secret = ticket.partition(":")
        [grant] = app.member_server.tickets.grants()
        assert grant.ticket_id == ticket_id and grant.actor == "leo"
        assert grant.fingerprint == hashlib.sha256(secret.encode()).hexdigest()
        assert secret not in repr(grant)
        assert secret not in json.dumps([str(value) for value in astuple(grant)])
        # Nothing durable: the identity database never holds a ticket.
        raw = (tmp_path / "registry.sqlite").read_bytes()
        assert secret.encode() not in raw and ticket_id.encode() not in raw

        # A ticket in a query string is not a route, and is not used up.
        for path in (f"sign-in/ticket?ticket={ticket}", f"browser-ticket?ticket={ticket}"):
            status, refused = request(
                _url(app, path), method="POST", authorization=f"Ticket {ticket}"
            )
            assert (status, refused["code"]) == (404, "invalid_request")
        status, refused = request(app.member_base_url + f"/?ticket={ticket}")
        assert status == 404
        assert _redeem(app, ticket)[0] == 200
        captured = capfd.readouterr()
        assert secret not in captured.out + captured.err


def test_a_new_ticket_sign_in_replaces_the_earlier_one(tmp_path: Path) -> None:
    moment = [NOW]
    with _app(tmp_path, moment) as app:
        leo = _signed_in(app, "leo", "member")
        first = _redeem(app, _ticket(app, leo))[1]
        second = _redeem(app, _ticket(app, leo))[1]
        assert (
            request(_url(app, "session"), method="POST", authorization=f"Login {first['login']}")[0]
            != 200
        )
        assert (
            request(_url(app, "session"), method="POST", authorization=f"Login {second['login']}")[
                0
            ]
            == 200
        )
        # The Personal Agent's and other browsers' logins are untouched.
        labels = [g.label for g in app.state.logins.active("leo", now=NOW)]
        assert labels.count(TICKET_LOGIN_LABEL) == 1
        # At most five open tickets per member are kept.
        for _ in range(8):
            _ticket(app, leo)
        assert len(app.member_server.tickets.grants()) <= 5


def test_the_portal_page_redeems_the_ticket_and_drops_the_fragment() -> None:
    for hook in (
        'fragment.get("ticket")',
        '"/v1/member/sign-in/ticket"',
        "Ticket ${code}",
        "signInWithTicket",
        'p.get("ticket")',
        'fragment.get("asset")',
        "openAskedAsset",
        'history.replaceState(null,"",location.pathname)',
        "ticket_expired",
        "ticket_used",
    ):
        assert hook in PAGE, hook
    # The fragment is dropped before anything else runs.
    assert PAGE.index("history.replaceState(null") < PAGE.index("async function api(")


@pytest.mark.skipif(_browser_missing(), reason="no Chromium browser is installed")
def test_a_ticket_signs_the_browser_in_on_the_asked_tab_and_asset(tmp_path: Path) -> None:
    from integrations.browser import Browser

    platform = SharedPlatformApplication.empty(
        administrators=("platform-admin",), registry_path=tmp_path / "registry.sqlite"
    )
    with platform as app:
        _published(app)
        engineer = _signed_in(app, "engineer", "member")
        browser = Browser(tmp_path / "browser", timeout_s=60)
        browser.start()

        def js(code: str) -> Any:
            return browser._evaluate(code)

        def until(check: Any, seconds: float = 20) -> None:
            deadline = time.monotonic() + seconds
            while not check() and time.monotonic() < deadline:
                time.sleep(0.2)
            assert check()

        try:
            ticket = _ticket(app, engineer)
            browser.navigate(
                app.member_base_url
                + f"/#ticket={ticket}&bridge=bridge-x&tab=marketplace"
                + "&asset=lab/weekly-check@1.0.0"
            )
            until(lambda: js('document.getElementById("actor").textContent') == "engineer")
            assert "ticket" not in str(js("location.href"))
            assert js('!document.getElementById("panel-marketplace").hidden') is True
            until(
                lambda: (
                    "Run parameters"
                    in str(js('document.getElementById("detail-content").textContent'))
                )
            )
            assert js('document.getElementById("detail-title").textContent') == ("lab/weekly-check")
            width = js('document.getElementById("asset-detail").getBoundingClientRect().width')
            assert float(width) > 300
            assert str(js('localStorage.getItem("aep.marketplace.login.v1")')).startswith("login-")
            # The same ticket again: used up; this browser stays signed in by
            # its stored login.
            js("localStorage.clear(); 0")
            browser.navigate("about:blank")
            browser.navigate(app.member_base_url + f"/#ticket={ticket}")
            until(
                lambda: (
                    "already used"
                    in str(js('document.getElementById("sign-in-status").textContent'))
                )
            )
            assert "ticket" not in str(js("location.href"))
        finally:
            browser.close()
            browser.discard_profile()
