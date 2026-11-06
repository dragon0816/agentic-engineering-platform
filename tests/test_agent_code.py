"""The Personal Agent code from Agent Web, and its automatic renewal (owner
2026-10-19, "Option A"; `docs/phases/PASSWORD_SIGN_IN.md`).

The person signs in once with their platform account and password in Settings
→ Shared platform; Agent Web gets a code with that session, stores it as the
paste path does and keeps no password anywhere. A code with under 7 days left
is renewed with itself and the old one revoked through `logins/revoke`; a
platform without that route still gets the new code stored.

Everything runs against a real in-process shared platform (the repo's
fixtures); never the live one.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from test_member_publish import _signed_in
from test_shared_platform_app import request
from test_shared_platform_settings import _host, _web

from control_plane.app import SharedPlatformApplication
from control_plane.member_http import BROWSER_LOGIN_LABEL
from host_runtime import agent_code
from host_runtime.contracts import CompanyHostConfiguration
from host_runtime.host import build_runtime
from host_runtime.platform_publish import MemberPortalPublisher, PublishError
from host_runtime.shared_platform import LOGIN_SHAPE, LOGIN_VARIABLE, TOKEN_VARIABLE
from host_runtime.web import AgentWeb, AgentWebServer
from integrations.browser import Browser, browser_path

PASSWORD = "lantern orchard pebble 42"
ACCOUNT = "engineer"  # this PC's device.registered_by in the host fixture


@pytest.fixture
def app(tmp_path: Path) -> Iterator[SharedPlatformApplication]:
    platform = SharedPlatformApplication.empty(
        administrators=("platform-admin",), registry_path=tmp_path / "registry.sqlite"
    )
    with platform:
        yield platform


@pytest.fixture(autouse=True)
def _environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (TOKEN_VARIABLE, LOGIN_VARIABLE, "AEP_LOCAL_PLATFORM_TOKEN"):
        monkeypatch.delenv(name, raising=False)
    from host_runtime import platform_publish

    # Never read this developer's own saved Windows variables.
    monkeypatch.setattr(platform_publish, "_saved_user_variable", lambda name: None)


def _with_password(app: SharedPlatformApplication, actor: str = ACCOUNT) -> str:
    session = _signed_in(app, actor, "member")
    status, reply = request(
        app.member_base_url + "/v1/member/password/set",
        authorization=session,
        body={"password": PASSWORD},
    )
    assert status == 200, reply
    return session


def _form(app: SharedPlatformApplication, password: str = PASSWORD) -> dict[str, Any]:
    return {
        "member_portal_url": app.member_base_url,
        "base_url": app.control_base_url,
        "account": ACCOUNT,
        "password": password,
    }


def _browser_logins(app: SharedPlatformApplication, actor: str = ACCOUNT) -> int:
    return sum(1 for grant in app.state.logins.active(actor) if grant.label == BROWSER_LOGIN_LABEL)


def _authenticates(app: SharedPlatformApplication, code: str) -> bool:
    status, _ = request(
        app.member_base_url + "/v1/member/session", authorization=f"Login {code}", method="POST"
    )
    return status == 200


def _everything_written(root: Path) -> str:
    texts = []
    for path in root.rglob("*"):
        if path.is_file() and path.suffix not in (".sqlite", ".sqlite-wal", ".sqlite-shm"):
            try:
                texts.append(path.read_text(encoding="utf-8", errors="ignore"))
            except OSError:
                continue
    return "\n".join(texts)


def test_sign_in_stores_the_code_and_keeps_no_password_anywhere(
    app: SharedPlatformApplication, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    _with_password(app)
    path, layout = _host(tmp_path)
    saved: dict[str, str] = {}
    browser_logins = _browser_logins(app)
    caplog.set_level(logging.DEBUG)
    with build_runtime(
        CompanyHostConfiguration.model_validate_json(path.read_text("utf-8")), layout=layout
    ) as runtime:
        web = _web(runtime, path, saved)
        form = _form(app)
        reply = web.sign_in_for_agent_code(form)
        assert reply["ok"] is True and reply["signed_in"] is True, reply
        assert "password" not in form  # taken out of the request body at once
        code = saved[LOGIN_VARIABLE]
        assert LOGIN_SHAPE.fullmatch(code) and os.environ[LOGIN_VARIABLE] == code
        assert _authenticates(app, code)
        status = reply["agent_code"]
        assert status["state"] == "valid" and status["estimated"] is False
        assert status["login_id"] == code.partition(":")[0]
        expires = datetime.fromisoformat(status["expires_at"])
        assert timedelta(days=29) < expires - datetime.now(UTC) <= timedelta(days=30)
        # The running Agent uses it at once (as the paste path does).
        publisher = web._publisher()
        assert publisher is not None and publisher.me() == ACCOUNT
        # The browser login the sign-in created was revoked; only the code remains.
        assert _browser_logins(app) == browser_logins
        tasks = json.dumps(web.task_list())
        settings = json.dumps(web.shared_platform_settings())
    # The password is nowhere: replies, files, environment, logs, tasks.
    for place in (
        json.dumps(reply),
        settings,
        tasks,
        _everything_written(tmp_path / "workspace") if (tmp_path / "workspace").exists() else "",
        _everything_written(layout.workspace_root),
        path.read_text(encoding="utf-8"),
        json.dumps(saved),
        caplog.text,
    ):
        assert PASSWORD not in place
    # Keep the same JSON containment check, but expose only its boolean on failure.
    # An assertion on the serialized string would dump the inherited environment.
    password_in_environment = PASSWORD in json.dumps(dict(os.environ))
    assert not password_in_environment
    # And the code itself is not in a file or a reply either.
    assert code not in json.dumps(reply) and code not in _everything_written(layout.workspace_root)
    assert code not in path.read_text(encoding="utf-8")


def test_a_wrong_password_returns_the_platforms_error_and_saves_nothing(
    app: SharedPlatformApplication, tmp_path: Path
) -> None:
    _with_password(app)
    path, layout = _host(tmp_path)
    before = path.read_text(encoding="utf-8")
    saved: dict[str, str] = {}
    with build_runtime(CompanyHostConfiguration.model_validate_json(before), layout=layout) as rt:
        web = _web(rt, path, saved)
        reply = web.sign_in_for_agent_code(_form(app, "not the right one at all"))
        assert reply["ok"] is False and reply["code"] == "authentication_failed"
        assert "wrong" in reply["message"]
        assert web.sign_in_for_agent_code({**_form(app), "password": ""})["code"] == (
            "password_missing"
        )
        other = web.sign_in_for_agent_code({**_form(app), "account": "someone"})
        assert other["code"] == "device_owner_mismatch"
    assert saved == {} and path.read_text(encoding="utf-8") == before
    assert agent_code.read_record(layout.workspace_root) is None


def _signed_in_web(
    app: SharedPlatformApplication, tmp_path: Path
) -> tuple[Path, Any, dict[str, str]]:
    _with_password(app)
    path, layout = _host(tmp_path)
    return path, layout, {}


def test_renewal_issues_a_new_code_stores_it_and_revokes_the_old_one(
    app: SharedPlatformApplication, tmp_path: Path
) -> None:
    path, layout, saved = _signed_in_web(app, tmp_path)
    with build_runtime(
        CompanyHostConfiguration.model_validate_json(path.read_text("utf-8")), layout=layout
    ) as runtime:
        web = _web(runtime, path, saved)
        assert web.sign_in_for_agent_code(_form(app))["ok"]
        old = saved[LOGIN_VARIABLE]
        # Not due yet: nothing happens.
        assert web.renew_agent_code() == {"ok": True, "renewed": False}
        record = agent_code.read_record(layout.workspace_root)
        assert record is not None
        agent_code.write_record(
            layout.workspace_root,
            record.model_copy(update={"expires_at": datetime.now(UTC) + timedelta(days=3)}),
        )
        assert web.shared_platform_settings()["agent_code"]["state"] == "renew_soon"
        result = web.renew_agent_code()
        assert result == {"ok": True, "renewed": True, "renewals": 1}
        new = saved[LOGIN_VARIABLE]
        assert new != old and _authenticates(app, new) and not _authenticates(app, old)
        renewed = agent_code.read_record(layout.workspace_root)
        assert renewed is not None and renewed.source == "renewed" and renewed.renewals == 1
        assert renewed.unrevoked is None and renewed.login_id == new.partition(":")[0]
        publisher = web._publisher()
        assert publisher is not None and publisher.me() == ACCOUNT  # the new code in use
        tasks = json.dumps(web.task_list())
        assert "renewal 1" in tasks and new not in tasks and old not in tasks


def test_renewal_without_the_revoke_route_still_stores_the_new_code(
    app: SharedPlatformApplication,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    path, layout, saved = _signed_in_web(app, tmp_path)

    def no_route(self: MemberPortalPublisher, login_id: str, session: str | None = None) -> Any:
        # What a platform from before 2026-10-19 answers for an unknown route.
        raise PublishError("invalid_request", 404)

    with build_runtime(
        CompanyHostConfiguration.model_validate_json(path.read_text("utf-8")), layout=layout
    ) as runtime:
        web = _web(runtime, path, saved)
        assert web.sign_in_for_agent_code(_form(app))["ok"]
        old = saved[LOGIN_VARIABLE]
        record = agent_code.read_record(layout.workspace_root)
        assert record is not None
        agent_code.write_record(
            layout.workspace_root,
            record.model_copy(update={"expires_at": datetime.now(UTC) + timedelta(days=2)}),
        )
        monkeypatch.setattr(MemberPortalPublisher, "revoke_login", no_route)
        caplog.set_level(logging.WARNING)
        assert web.renew_agent_code()["renewed"] is True
        new = saved[LOGIN_VARIABLE]
        assert new != old and _authenticates(app, new)
        assert _authenticates(app, old)  # it simply expires on its own
        renewed = agent_code.read_record(layout.workspace_root)
        assert renewed is not None and renewed.unrevoked is not None
        assert "invalid_request" in renewed.unrevoked
        assert "could not be revoked" in caplog.text
        for secret in (old.partition(":")[2], new.partition(":")[2]):
            assert secret not in caplog.text
            assert secret not in json.dumps(web.task_list())


def test_a_code_saved_before_this_pc_kept_a_record_is_renewed_once(
    app: SharedPlatformApplication, tmp_path: Path
) -> None:
    session = _with_password(app)
    path, layout = _host(tmp_path)
    saved: dict[str, str] = {}
    status, issued = request(
        app.member_base_url + "/v1/member/logins/issue-agent", authorization=session, body={}
    )
    assert status == 200
    with build_runtime(
        CompanyHostConfiguration.model_validate_json(path.read_text("utf-8")), layout=layout
    ) as runtime:
        web = _web(runtime, path, saved)
        # Pasted the old way, then the record is lost (as on PCs from before).
        reply = web.update_shared_platform(
            {
                "member_portal_url": app.member_base_url,
                "base_url": app.control_base_url,
                "code": issued["login"],
                "enroll": False,
            }
        )
        assert reply["ok"], reply
        assert reply["agent_code"]["state"] == "valid" and reply["agent_code"]["estimated"]
        (layout.workspace_root / agent_code.RECORD_FILE).unlink()
        assert web.shared_platform_settings()["agent_code"]["state"] == "unknown"
        assert web.renew_agent_code()["renewed"] is True
        assert not _authenticates(app, str(issued["login"]))
        assert web.shared_platform_settings()["agent_code"]["state"] == "valid"


def test_an_expired_code_asks_for_a_new_sign_in_and_is_not_renewed(
    app: SharedPlatformApplication, tmp_path: Path
) -> None:
    path, layout, saved = _signed_in_web(app, tmp_path)
    with build_runtime(
        CompanyHostConfiguration.model_validate_json(path.read_text("utf-8")), layout=layout
    ) as runtime:
        web = _web(runtime, path, saved)
        assert web.sign_in_for_agent_code(_form(app))["ok"]
        code = saved[LOGIN_VARIABLE]
        record = agent_code.read_record(layout.workspace_root)
        assert record is not None
        agent_code.write_record(
            layout.workspace_root,
            record.model_copy(update={"expires_at": datetime.now(UTC) - timedelta(hours=1)}),
        )
        assert web.shared_platform_settings()["agent_code"]["state"] == "expired"
        assert web.renew_agent_code() == {"ok": True, "renewed": False}
        assert saved[LOGIN_VARIABLE] == code
        # A code the platform no longer accepts (revoked elsewhere) is marked so.
        agent_code.write_record(
            layout.workspace_root,
            record.model_copy(update={"expires_at": datetime.now(UTC) + timedelta(days=1)}),
        )
        app.state.logins.revoke(code.partition(":")[0])
        web._member_publisher = (None, None)
        assert web.renew_agent_code()["ok"] is False
        assert web.shared_platform_settings()["agent_code"]["state"] == "expired"


def test_the_bridge_token_reminder_starts_under_fourteen_days() -> None:
    now = datetime(2026, 10, 19, tzinfo=UTC)
    assert agent_code.bridge_token_status(now + timedelta(days=30), now)["remind"] is False
    soon = agent_code.bridge_token_status(now + timedelta(days=10), now)
    assert soon["remind"] is True and soon["days_left"] == 10 and not soon["expired"]
    assert agent_code.bridge_token_status(now - timedelta(days=1), now)["expired"] is True
    assert agent_code.bridge_token_status(None, now) == {"expires_at": None, "remind": False}


# -- the settings card in a real browser ---------------------------------------------


@pytest.mark.skipif(browser_path() is None, reason="no Chromium browser is installed")
def test_the_sign_in_card_in_a_real_browser(app: SharedPlatformApplication, tmp_path: Path) -> None:
    _with_password(app)
    path, layout = _host(tmp_path)
    saved: dict[str, str] = {}
    shots = Path(os.environ.get("AEP_UI_SHOTS") or (tmp_path / "shots"))
    with build_runtime(
        CompanyHostConfiguration.model_validate_json(path.read_text("utf-8")), layout=layout
    ) as runtime:
        web = _web(runtime, path, saved)
        served = AgentWebServer(web)
        thread = threading.Thread(target=served.serve_forever, daemon=True)
        thread.start()
        browser = Browser(tmp_path / "browser", timeout_s=60)
        browser.start()

        def wait(expression: str, seconds: float = 30) -> object:
            deadline = time.monotonic() + seconds
            while time.monotonic() < deadline:
                value = browser._evaluate(expression)
                if value:
                    return value
                time.sleep(0.2)
            raise AssertionError(expression)

        def value(element: str, text: str) -> None:
            browser._evaluate(
                f"document.getElementById({json.dumps(element)}).value = {json.dumps(text)}"
            )

        try:
            browser.navigate(served.address)
            wait('!!document.getElementById("nav-settings")')
            browser._evaluate('document.getElementById("nav-settings").click()')
            wait('document.getElementById("shared-code-state").textContent.length > 0')
            browser._evaluate(
                'document.getElementById("shared-signin").scrollIntoView({block: "center"})'
            )
            sizes = json.loads(
                str(
                    browser._evaluate(
                        "JSON.stringify(['shared-signin-account','shared-signin-password',"
                        "'shared-signin-go','team-declared','team-save'].map((id) => {"
                        " const r = document.getElementById(id).getBoundingClientRect();"
                        " return [r.width, r.height]; }))"
                    )
                )
            )
            assert all(w >= 44 and h >= 44 for w, h in sizes), sizes
            assert not browser._evaluate(
                "document.documentElement.scrollWidth > document.documentElement.clientWidth"
            )
            for theme in ("light", "dark"):
                browser._evaluate(f"document.documentElement.dataset.theme = {json.dumps(theme)}")
                time.sleep(0.3)
                browser.screenshot(shots / f"agent-code-signin-before-{theme}.png")
            value("shared-portal-url", app.member_base_url)
            value("shared-bridge-url", app.control_base_url)
            value("shared-signin-account", ACCOUNT)
            value("shared-signin-password", PASSWORD)
            browser._evaluate('document.getElementById("shared-signin-go").click()')
            # Cleared at once, before the answer.
            assert (
                browser._evaluate('document.getElementById("shared-signin-password").value') == ""
            )
            wait('document.getElementById("shared-status").textContent.includes("code saved")')
            state = str(
                browser._evaluate('document.getElementById("shared-code-state").textContent')
            )
            assert "valid until" in state
            assert LOGIN_SHAPE.fullmatch(saved[LOGIN_VARIABLE])
            page_text = str(browser._evaluate("document.documentElement.outerHTML"))
            assert PASSWORD not in page_text and saved[LOGIN_VARIABLE] not in page_text
            for theme in ("light", "dark"):
                browser._evaluate(f"document.documentElement.dataset.theme = {json.dumps(theme)}")
                time.sleep(0.3)
                browser.screenshot(shots / f"agent-code-signin-after-{theme}.png")
        finally:
            browser.close()
            browser.discard_profile()
            served.shutdown()
            served.server_close()
            thread.join(timeout=5)
    assert isinstance(web, AgentWeb)
