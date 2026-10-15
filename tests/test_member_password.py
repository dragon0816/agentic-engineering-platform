"""Account and password sign-in for the Member Portal (owner 2026-10-15,
`docs/phases/PASSWORD_SIGN_IN.md`)."""

from __future__ import annotations

import json
import logging
import re
import sqlite3
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from test_asset_access import _browser_missing
from test_shared_platform_app import request

from common.enrollment import Invitation
from control_plane.app import SharedPlatformApplication
from control_plane.member_page import PAGE
from control_plane.member_password import (
    COMMON_PASSWORDS,
    DEFAULT_COST,
    FailureLimiter,
    MemberPasswords,
    PasswordCost,
    PasswordError,
    hash_password,
    password_problem,
    verify_password,
)

NOW = datetime(2026, 10, 15, 9, 0, tzinfo=UTC)
# The real cost is slow on purpose; tests use a small one (the record keeps
# the cost it was made with, so verification follows it either way).
FAST = PasswordCost(n=2**10, r=8, p=1)
GOOD = "lantern orchard pebble 42"
OTHER = "violet harbor tram 1987"


def _app(tmp_path: Path, moment: list[datetime]) -> SharedPlatformApplication:
    app = SharedPlatformApplication.empty(
        administrators=("platform-admin",),
        registry_path=tmp_path / "registry.sqlite",
        clock=lambda: moment[0],
    )
    fast = MemberPasswords(storage=app.state.identity_storage, cost=FAST)
    app.state.passwords = fast
    app.member_server.passwords = fast
    return app


def _invite(app: SharedPlatformApplication, actor: str, role: str = "member") -> str:
    proof = app.issue_invitation(
        Invitation(
            invitation_id=f"invite-{actor}", actor=actor, issued_by="platform-admin", role=role
        ),
        expires_at=app.member_service.now() + timedelta(days=1),
    )
    return proof.bearer


def _join(app: SharedPlatformApplication, actor: str, password: str | None = GOOD,
          role: str = "member") -> dict[str, Any]:
    """Accept an invitation, setting a password in the same step."""
    status, reply = request(
        app.member_base_url + "/v1/member/sign-in",
        authorization=f"Invitation {_invite(app, actor, role)}",
        body={"password": password} if password is not None else None,
        method="POST",
    )
    assert status == 200, reply
    return reply


def _password(app: SharedPlatformApplication, account: str, password: str) -> tuple[int, dict]:
    return request(
        app.member_base_url + "/v1/member/sign-in/password",
        body={"account": account, "password": password},
    )


def _url(app: SharedPlatformApplication, operation: str) -> str:
    return app.member_base_url + "/v1/member/" + operation


# -- Hashing and policy -------------------------------------------------------


def test_scrypt_hash_is_salted_slow_and_verifies_in_constant_time() -> None:
    first = hash_password("leo", GOOD, cost=FAST, now=NOW, set_by="self")
    second = hash_password("leo", GOOD, cost=FAST, now=NOW, set_by="self")
    assert first.salt != second.salt and first.digest != second.digest
    assert verify_password(first, GOOD) and verify_password(second, GOOD)
    assert not verify_password(first, OTHER)
    assert not verify_password(first, GOOD + " ")
    assert GOOD not in first.model_dump_json()
    assert (first.algorithm, first.n, first.r, first.p) == ("scrypt", FAST.n, FAST.r, FAST.p)
    # The default cost is the slow one: 32 MiB of scrypt memory.
    assert 128 * DEFAULT_COST.r * DEFAULT_COST.n >= 32 * 1024 * 1024
    with pytest.raises(ValueError):
        PasswordCost(n=1000, r=8, p=1)
    source = Path("src/control_plane/member_password.py").read_text(encoding="utf-8")
    assert "hmac.compare_digest(actual" in source


def test_policy_needs_twelve_characters_and_refuses_name_common_and_repeated() -> None:
    assert password_problem("leo.chi", "short pass") == "too_short"
    assert password_problem("leo.chi", "x" * 257) == "too_long"
    assert password_problem("leo.chi", "my Leo.Chi password") == "contains_account"
    assert password_problem("leo.chi", "leochi-is-my-name") == "contains_account"
    assert password_problem("leo.chi", "Password1234") == "too_common"
    assert password_problem("leo.chi", "aaaaaaaaaaaaaa") == "repeated"
    assert all(len(item) >= 12 for item in COMMON_PASSWORDS)
    assert password_problem("leo.chi", GOOD) is None
    assert password_problem("leo.chi", "four words make a passphrase") is None


def test_failure_limiter_locks_a_key_and_releases_it_after_the_lockout() -> None:
    limiter = FailureLimiter()
    for _ in range(4):
        limiter.fail("account:leo", 5, NOW)
    assert not limiter.locked("account:leo", NOW)
    limiter.fail("account:leo", 5, NOW)
    assert limiter.locked("account:leo", NOW + timedelta(minutes=14))
    assert not limiter.locked("account:leo", NOW + timedelta(minutes=15))
    # Failures older than the window are forgotten.
    for minute in range(0, 80, 16):
        limiter.fail("account:anna", 5, NOW + timedelta(minutes=minute))
    assert not limiter.locked("account:anna", NOW + timedelta(minutes=80))


# -- Sign-in over HTTP --------------------------------------------------------


def test_invitation_sets_the_password_then_account_and_password_sign_in(tmp_path: Path) -> None:
    moment = [NOW]
    with _app(tmp_path, moment) as app:
        invitation = _invite(app, "leo")
        # Checking the link uses nothing up and says whose it is.
        status, checked = request(_url(app, "sign-in/check"),
                                  authorization=f"Invitation {invitation}", method="POST")
        assert status == 200
        assert checked["purpose"] == "invitation" and checked["actor"] == "leo"
        assert checked["password_set"] is False
        # A rejected password does not use up the invitation.
        status, refused = request(_url(app, "sign-in"), authorization=f"Invitation {invitation}",
                                  body={"password": "leo-password-1"})
        assert status == 400 and refused["code"] == "password_rejected"
        assert refused["reason"] == "contains_account" and "leo-password-1" not in str(refused)
        status, joined = request(_url(app, "sign-in"), authorization=f"Invitation {invitation}",
                                 body={"password": GOOD})
        assert status == 200 and set(joined) == {"session", "login", "expires_at"}
        assert app.state.passwords.record("leo").set_by == "invitation"  # type: ignore[union-attr]
        # The invitation is single use.
        status, again = request(_url(app, "sign-in"), authorization=f"Invitation {invitation}",
                                body={"password": GOOD})
        assert (status, again) == (409, {"code": "invitation_used"})

        status, signed = _password(app, "leo", GOOD)
        assert status == 200 and set(signed) == {"session", "login", "expires_at"}
        status, me = request(_url(app, "me"), authorization=f"Bearer {signed['session']}", body={})
        assert status == 200 and me["actor"] == "leo"
        # The stored login renews the session as an invitation's does.
        status, renewed = request(_url(app, "session"), authorization=f"Login {signed['login']}",
                                  method="POST")
        assert status == 200 and "session" in renewed
        # An empty invitation body still signs in (automation, older pages).
        bare = _join(app, "anna", password=None)
        status, _ = request(_url(app, "me"), authorization=f"Bearer {bare['session']}", body={})
        assert status == 200


def test_every_failure_is_the_same_and_too_many_lock_the_account(tmp_path: Path) -> None:
    moment = [NOW]
    with _app(tmp_path, moment) as app:
        _join(app, "leo")
        _join(app, "anna", password=None)  # a member without a password
        _join(app, "dora")
        app.state.enrollment.disable_user("platform-admin", "dora")
        uniform = (401, {"code": "authentication_failed"})
        assert _password(app, "nobody", GOOD) == uniform
        assert _password(app, "anna", GOOD) == uniform
        assert _password(app, "dora", GOOD) == uniform  # disabled
        assert _password(app, "not a name!", GOOD) == uniform
        assert _password(app, "leo", OTHER) == uniform
        status, missing = request(_url(app, "sign-in/password"), body={"account": "leo"})
        assert (status, missing) == (400, {"code": "invalid_request"})

        for _ in range(4):
            assert _password(app, "leo", OTHER) == uniform
        # Five failures for leo: even the right password is refused now.
        assert _password(app, "leo", GOOD) == uniform
        moment[0] = NOW + timedelta(minutes=16)
        assert _password(app, "leo", GOOD)[0] == 200


def test_too_many_failures_from_one_address_lock_that_address(tmp_path: Path) -> None:
    moment = [NOW]
    with _app(tmp_path, moment) as app:
        _join(app, "leo")
        for index in range(20):
            assert _password(app, f"guess{index}", OTHER)[0] == 401
        # The address is locked: the right password of another account fails.
        assert _password(app, "leo", GOOD) == (401, {"code": "authentication_failed"})
        moment[0] = NOW + timedelta(minutes=16)
        assert _password(app, "leo", GOOD)[0] == 200


def test_a_member_sets_a_password_once_and_changes_it_with_the_current_one(
    tmp_path: Path,
) -> None:
    moment = [NOW]
    with _app(tmp_path, moment) as app:
        joined = _join(app, "anna", password=None)
        session = f"Bearer {joined['session']}"
        status, state = request(_url(app, "password/status"), authorization=session, body={})
        assert (status, state) == (200, {"password_set": False, "set_at": None})
        status, refused = request(_url(app, "password/change"), authorization=session,
                                  body={"current_password": GOOD, "new_password": OTHER})
        assert (status, refused) == (409, {"code": "password_not_set"})
        status, weak = request(_url(app, "password/set"), authorization=session,
                               body={"password": "too short"})
        assert status == 400 and weak["reason"] == "too_short"
        status, done = request(_url(app, "password/set"), authorization=session,
                               body={"password": GOOD})
        assert (status, done) == (200, {"password_set": True})
        status, again = request(_url(app, "password/set"), authorization=session,
                                body={"password": OTHER})
        assert (status, again) == (409, {"code": "password_already_set"})
        assert _password(app, "anna", GOOD)[0] == 200

        # A second browser and the Personal Agent login.
        other_browser = _password(app, "anna", GOOD)[1]
        status, agent = request(_url(app, "logins/issue-agent"), authorization=session, body={})
        assert status == 200

        status, wrong = request(_url(app, "password/change"), authorization=session,
                                body={"current_password": OTHER, "new_password": OTHER})
        assert (status, wrong) == (401, {"code": "authentication_failed"})
        status, changed = request(_url(app, "password/change"), authorization=session,
                                  body={"current_password": GOOD, "new_password": OTHER})
        assert status == 200 and set(changed) == {"session", "login", "expires_at"}
        # The other browser and every old session are signed out; the Agent
        # login and the new login of this browser work.
        assert request(_url(app, "session"), authorization=f"Login {other_browser['login']}",
                       method="POST")[0] == 401
        assert request(_url(app, "me"), authorization=session, body={})[0] == 401
        assert request(_url(app, "session"), authorization=f"Login {agent['login']}",
                       method="POST")[0] == 200
        assert request(_url(app, "session"), authorization=f"Login {changed['login']}",
                       method="POST")[0] == 200
        assert _password(app, "anna", GOOD)[0] == 401
        assert _password(app, "anna", OTHER)[0] == 200


def test_reset_link_is_single_use_expires_and_revokes_browser_logins(tmp_path: Path) -> None:
    moment = [NOW]
    with _app(tmp_path, moment) as app:
        admin = f"Bearer {_join(app, 'root', role='platform_admin')['session']}"
        leo = _join(app, "leo")
        leo_session = f"Bearer {leo['session']}"
        status, agent = request(_url(app, "logins/issue-agent"), authorization=leo_session,
                                body={})
        assert status == 200

        # Members cannot issue reset links or sign others out.
        for operation, body in (("admin/members/password-reset", {"actor": "root"}),
                                ("admin/members/sign-out", {"actor": "root"}),
                                ("admin/members/credentials", {})):
            assert request(_url(app, operation), authorization=leo_session, body=body) == (
                403, {"code": "not_administrator"})
        assert request(_url(app, "admin/members/password-reset"), authorization=admin,
                       body={"actor": "nobody"}) == (403, {"code": "actor_unknown"})
        assert request(_url(app, "admin/members/password-reset"), authorization=admin,
                       body={"actor": "leo", "valid_for_minutes": 0})[0] == 400

        status, first = request(_url(app, "admin/members/password-reset"), authorization=admin,
                                body={"actor": "leo", "valid_for_minutes": 30})
        assert status == 200 and first["url"].startswith(app.member_base_url + "/#reset=reset-")
        status, link = request(_url(app, "admin/members/password-reset"), authorization=admin,
                               body={"actor": "leo"})
        assert status == 200
        old_code = first["url"].split("#reset=", 1)[1]
        code = link["url"].split("#reset=", 1)[1]
        # A newer link replaces the earlier one.
        assert request(_url(app, "sign-in/check"), authorization=f"Reset {old_code}",
                       method="POST") == (401, {"code": "reset_link_revoked"})
        status, checked = request(_url(app, "sign-in/check"), authorization=f"Reset {code}",
                                  method="POST")
        assert status == 200 and checked["purpose"] == "reset" and checked["actor"] == "leo"
        status, overview = request(_url(app, "admin/members/credentials"), authorization=admin,
                                   body={})
        row = next(item for item in overview["members"] if item["actor"] == "leo")
        assert row["password_set"] is True and row["reset_link_expires_at"] is not None
        assert row["active_logins"] == 2  # this browser and the Agent

        wrong = code[:-4] + "AAAA"
        assert request(_url(app, "password/reset"), authorization=f"Reset {wrong}",
                       body={"password": OTHER}) == (401, {"code": "authentication_failed"})
        status, weak = request(_url(app, "password/reset"), authorization=f"Reset {code}",
                               body={"password": "password1234"})
        assert status == 400 and weak["reason"] == "too_common"
        status, reset = request(_url(app, "password/reset"), authorization=f"Reset {code}",
                                body={"password": OTHER})
        assert status == 200 and set(reset) == {"session", "login", "expires_at"}
        assert request(_url(app, "password/reset"), authorization=f"Reset {code}",
                       body={"password": OTHER}) == (409, {"code": "reset_link_used"})
        # Old browser login and session are gone; the Agent login stays.
        assert request(_url(app, "session"), authorization=f"Login {leo['login']}",
                       method="POST")[0] == 401
        assert request(_url(app, "me"), authorization=leo_session, body={})[0] == 401
        assert request(_url(app, "session"), authorization=f"Login {agent['login']}",
                       method="POST")[0] == 200
        assert _password(app, "leo", OTHER)[0] == 200

        # Expiry.
        status, late = request(_url(app, "admin/members/password-reset"), authorization=admin,
                               body={"actor": "leo", "valid_for_minutes": 5})
        moment[0] = NOW + timedelta(minutes=6)
        late_code = late["url"].split("#reset=", 1)[1]
        assert request(_url(app, "password/reset"), authorization=f"Reset {late_code}",
                       body={"password": GOOD}) == (401, {"code": "reset_link_expired"})


def test_a_disabled_member_cannot_reset_or_renew_and_force_sign_out_ends_everything(
    tmp_path: Path,
) -> None:
    moment = [NOW]
    with _app(tmp_path, moment) as app:
        admin = f"Bearer {_join(app, 'root', role='platform_admin')['session']}"
        leo = _join(app, "leo")
        status, agent = request(_url(app, "logins/issue-agent"),
                                authorization=f"Bearer {leo['session']}", body={})
        assert status == 200
        status, out = request(_url(app, "admin/members/sign-out"), authorization=admin,
                              body={"actor": "leo"})
        assert (status, out) == (200, {"actor": "leo", "logins_revoked": 2,
                                       "sessions_revoked": 1})
        # Force sign-out revokes the Personal Agent login too.
        for login in (leo["login"], agent["login"]):
            assert request(_url(app, "session"), authorization=f"Login {login}",
                           method="POST")[0] == 401
        assert _password(app, "leo", GOOD)[0] == 200  # the password still works

        signed = _password(app, "leo", GOOD)[1]
        status, link = request(_url(app, "admin/members/password-reset"), authorization=admin,
                               body={"actor": "leo"})
        app.state.enrollment.disable_user("platform-admin", "leo")
        code = link["url"].split("#reset=", 1)[1]
        assert request(_url(app, "password/reset"), authorization=f"Reset {code}",
                       body={"password": OTHER}) == (401, {"code": "authentication_failed"})
        assert request(_url(app, "session"), authorization=f"Login {signed['login']}",
                       method="POST") == (403, {"code": "actor_disabled"})
        assert _password(app, "leo", GOOD) == (401, {"code": "authentication_failed"})
        # The link was not used up by the refused attempt.
        assert app.state.passwords.pending_reset("leo", moment[0]) is not None


def test_passwords_survive_a_restart_and_are_never_stored_returned_or_logged(
    tmp_path: Path, caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG)
    moment = [NOW]
    replies: list[Any] = []
    with _app(tmp_path, moment) as app:
        replies.append(_join(app, "leo"))
        admin_reply = _join(app, "root", role="platform_admin")
        replies.append(admin_reply)
        admin = f"Bearer {admin_reply['session']}"
        replies.append(_password(app, "leo", GOOD))
        replies.append(_password(app, "leo", OTHER))
        replies.append(request(_url(app, "admin/members/credentials"), authorization=admin,
                               body={}))
        replies.append(request(_url(app, "sign-in"), authorization="Invitation x:y",
                               body={"password": OTHER}))
    stored = (tmp_path / "registry.sqlite").read_bytes()
    with sqlite3.connect(tmp_path / "registry.sqlite") as connection:
        rows = connection.execute("SELECT payload FROM identity_passwords").fetchall()
    assert len(rows) == 2 and all('"algorithm":"scrypt"' in row[0] for row in rows)
    for secret in (GOOD, OTHER):
        assert secret.encode() not in stored
        assert secret not in json.dumps(replies)
        assert secret not in caplog.text

    # A new process on the same database keeps the passwords.
    with _app(tmp_path, moment) as again:
        assert _password(again, "leo", GOOD)[0] == 200


def test_reset_link_issue_rejects_short_secrets_and_bad_lifetimes() -> None:
    passwords = MemberPasswords(cost=FAST)
    with pytest.raises(PasswordError):
        passwords.issue_reset("leo", issued_by="root", now=NOW, secret="short")
    with pytest.raises(PasswordError):
        passwords.issue_reset("leo", issued_by="root", now=NOW, minutes=24 * 60 + 1)
    issued = passwords.issue_reset("leo", issued_by="root", now=NOW)
    assert issued.secret not in repr(issued) and issued.secret not in issued.grant.model_dump_json()


# -- Page ---------------------------------------------------------------------


def test_the_page_has_the_password_sign_in_hooks() -> None:
    for hook in (
        'id="password-form"', 'id="signin-account"', 'autocomplete="username"',
        'id="signin-password"', 'autocomplete="current-password"', 'id="link-entry"',
        'id="set-password-form"', 'autocomplete="new-password"', 'id="password-open"',
        'id="password-panel"', 'id="password-notice"', 'id="member-reset-result"',
        "/v1/member/sign-in/password", "/v1/member/sign-in/check", "/v1/member/password/reset",
        "/v1/member/password/change", "/v1/member/password/set", "/v1/member/password/status",
        "/v1/member/admin/members/password-reset", "/v1/member/admin/members/sign-out",
        "/v1/member/admin/members/credentials", 'fragment.get("reset")', "Force sign-out",
        "Password reset link",
    ):
        assert hook in PAGE, hook
    # Passwords never go to browser storage.
    script = PAGE.split("<script>", 1)[1]
    assert "localStorage.setItem(LOGIN_KEY,data.login)" in script
    assert not re.search(r"(localStorage|sessionStorage)\.setItem\([^)]*password", script, re.I)


@pytest.mark.skipif(_browser_missing(), reason="no Chromium browser is installed")
def test_the_sign_in_screen_in_a_real_browser(tmp_path: Path) -> None:
    from integrations.browser import Browser

    moment = [NOW]
    with _app(tmp_path, moment) as app:
        invitation = _invite(app, "leo.chi")
        browser = Browser(tmp_path / "browser", timeout_s=60)
        browser.start()

        def js(code: str) -> Any:
            return browser._evaluate(code)

        def until(check: Any, seconds: float = 20) -> None:
            deadline = time.monotonic() + seconds
            while not check() and time.monotonic() < deadline:
                time.sleep(0.2)
            assert check()

        def shown(element: str) -> bool:
            return bool(js(f'(e => !!e && e.getClientRects().length > 0)'
                           f'(document.getElementById("{element}"))'))

        def box(element: str) -> list[float]:
            return list(json.loads(str(js(
                f'JSON.stringify((r => [r.width, r.height])(document.getElementById('
                f'"{element}").getBoundingClientRect()))'))))

        try:
            browser.navigate(app.member_base_url + "/")
            until(lambda: shown("password-form"))
            width, height = box("password-form")
            assert 280 <= width <= 470 and 220 <= height <= 520, (width, height)
            for field in ("signin-account", "signin-password"):
                field_width, field_height = box(field)
                assert field_width > 240 and field_height >= 40, (field, field_width)
            assert box("password-sign-in")[1] >= 44
            assert not shown("set-password-form")
            assert js('document.getElementById("signin-password").type') == "password"

            # First time: the invitation opens "Set your password".
            browser.navigate(app.member_base_url + f"/#invitation={invitation}")
            until(lambda: shown("set-password-form"))
            assert js('location.hash') == ""
            assert not shown("password-form")
            assert js('document.getElementById("new-account").value') == "leo.chi"
            width, height = box("set-password-form")
            assert 280 <= width <= 470 and 300 <= height <= 700, (width, height)
            js('document.getElementById("new-password").value="short";'
               'document.getElementById("new-password-again").value="short";'
               'document.getElementById("set-password").click(); 0')
            until(lambda: "12 characters" in str(js(
                'document.getElementById("set-password-status").textContent')))
            js(f'document.getElementById("new-password").value={json.dumps(GOOD)};'
               f'document.getElementById("new-password-again").value={json.dumps(GOOD)};'
               'document.getElementById("set-password").click(); 0')
            until(lambda: shown("workspace"))
            assert js('document.getElementById("actor").textContent') == "leo.chi"
            until(lambda: js('passwordSet') is True)
            assert not shown("password-notice")

            # Sign out, then sign in with account and password.
            js('document.getElementById("sign-out").click(); 0')
            until(lambda: shown("password-form"))
            js('document.getElementById("signin-account").value="leo.chi";'
               'document.getElementById("signin-password").value="wrong password 99";'
               'document.getElementById("password-sign-in").click(); 0')
            until(lambda: "wrong" in str(js(
                'document.getElementById("sign-in-status").textContent')))
            assert js('document.getElementById("signin-password").value') == ""
            js('document.getElementById("signin-account").value="leo.chi";'
               f'document.getElementById("signin-password").value={json.dumps(GOOD)};'
               'document.getElementById("password-sign-in").click(); 0')
            until(lambda: shown("workspace"))
            assert GOOD not in str(js("JSON.stringify(localStorage)"))

            # Change it from the header.
            js('document.getElementById("password-open").click(); 0')
            until(lambda: shown("password-panel"))
            assert shown("pw-current-field")
            js(f'document.getElementById("pw-current").value={json.dumps(GOOD)};'
               f'document.getElementById("pw-new").value={json.dumps(OTHER)};'
               f'document.getElementById("pw-again").value={json.dumps(OTHER)};'
               'document.getElementById("pw-save").click(); 0')
            until(lambda: "changed" in str(js(
                'document.getElementById("pw-status").textContent')))
            assert js('document.documentElement.scrollWidth <= window.innerWidth + 1') is True
        finally:
            browser.close()
            browser.discard_profile()
    assert _password_after(tmp_path, "leo.chi", OTHER)


def _password_after(tmp_path: Path, account: str, password: str) -> bool:
    with _app(tmp_path, [NOW]) as app:
        return _password(app, account, password)[0] == 200
