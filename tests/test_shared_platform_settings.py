"""Agent Web's "Shared platform" settings card enrolls this PC.

Requirements: `docs/phases/BRIDGE_ENROLLMENT.md` (owner 2026-10-15): one
Member Portal URL feeds `publishing` and `platform`; "Enroll this PC" asks the
portal, as the member, for this computer's Bridge token, saves it for this
Windows user under `AEP_SHARED_PLATFORM_TOKEN` (never in a file, never echoed),
rewrites host.json after a backup and switches the running Agent without a
restart. With a hand-written grants.json a sync installs files only (owner
decision (a)). Everything runs against a real in-process shared platform.
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from test_host_wiring import host_json, ready
from test_member_publish import _signed_in, workflow_manifest
from test_shared_platform_app import request

from common.assets import AssetIdentity
from control_plane.app import SharedPlatformApplication
from host_runtime.contracts import CompanyHostConfiguration
from host_runtime.host import build_runtime
from host_runtime.shared_platform import LOGIN_VARIABLE, TOKEN_VARIABLE
from host_runtime.web import AgentWeb, AgentWebServer
from host_runtime.web_page import PAGE
from integrations.browser import Browser, browser_path

OLD_PLATFORM = {
    # The old local test platform this PC pointed at, no longer running.
    "base_url": "http://127.0.0.1:9",
    "member_portal_url": "http://127.0.0.1:9",
    "token_id": "token-0000000000000000",
    "credential": {"name": "platform_token"},
    "timeout_seconds": 2,
}


@pytest.fixture
def app(tmp_path: Path) -> Iterator[SharedPlatformApplication]:
    platform = SharedPlatformApplication.empty(
        administrators=("platform-admin",), registry_path=tmp_path / "registry.sqlite"
    )
    with platform:
        yield platform


@pytest.fixture(autouse=True)
def _environment(monkeypatch: pytest.MonkeyPatch) -> None:
    # The card also sets this process's environment; put it back afterwards.
    for name in (TOKEN_VARIABLE, LOGIN_VARIABLE, "AEP_LOCAL_PLATFORM_TOKEN"):
        monkeypatch.delenv(name, raising=False)
    from host_runtime import platform_publish

    # Never read this developer's own saved Windows variables.
    monkeypatch.setattr(platform_publish, "_saved_user_variable", lambda name: None)


def _agent_login(app: SharedPlatformApplication, session: str) -> str:
    status, issued = request(
        app.member_base_url + "/v1/member/logins/issue-agent", authorization=session, body={}
    )
    assert status == 200
    return str(issued["login"])


def _host(tmp_path: Path) -> tuple[Path, Any]:
    """This PC as it was: a hand-written grants.json and an old platform."""
    config, layout = ready(
        tmp_path,
        config_changes={
            "platform": OLD_PLATFORM,
            "credentials": [
                {"secret": "platform_token", "environment_variable": "AEP_LOCAL_PLATFORM_TOKEN"}
            ],
        },
    )
    return host_json(tmp_path, config), layout


def _web(runtime: Any, path: Path, saved: dict[str, str]) -> AgentWeb:
    web = AgentWeb(runtime, config_path=path)
    web.user_environment = lambda name, value: saved.__setitem__(name, value)
    return web


def _card(app: SharedPlatformApplication, code: str = "", enroll: bool = True) -> dict[str, Any]:
    return {
        "member_portal_url": app.member_base_url + "/",
        "base_url": app.control_base_url,
        "code": code,
        "enroll": enroll,
    }


def test_enrolling_writes_host_json_saves_the_token_and_switches_without_restart(
    app: SharedPlatformApplication,
    tmp_path: Path,
) -> None:
    path, layout = _host(tmp_path)
    before = path.read_text(encoding="utf-8")
    login = _agent_login(app, _signed_in(app, "engineer", "member"))
    saved: dict[str, str] = {}
    with build_runtime(
        CompanyHostConfiguration.model_validate_json(before), layout=layout
    ) as runtime:
        web = _web(runtime, path, saved)
        assert web.platform()["connection"] != "answered"  # the old platform

        reply = web.update_shared_platform(_card(app, "  " + login + "\n"))
        assert reply["ok"] is True and reply["just_enrolled"] is True, reply
        assert reply["probe"] == "answered" and reply["restart_required"] is False

        # The code and the token are kept for this Windows user only.
        assert saved[LOGIN_VARIABLE] == login
        token = saved[TOKEN_VARIABLE]
        assert len(token) >= 32 and os.environ[TOKEN_VARIABLE] == token
        written = path.read_text(encoding="utf-8")
        for secret in (token, login):
            assert secret not in json.dumps(reply)
            assert secret not in json.dumps(web.shared_platform_settings())
            assert secret not in written
            assert secret not in json.dumps(web.task_list())
            assert secret not in (layout.workspace_root / "shared-platform.json").read_text(
                encoding="utf-8"
            )

        # host.json: valid, backed up, one portal URL in both places, the
        # old platform's token mapping untouched.
        config = CompanyHostConfiguration.model_validate_json(written)
        assert config.platform is not None and config.publishing is not None
        assert config.platform.base_url == app.control_base_url
        assert config.platform.member_portal_url == app.member_base_url
        assert config.publishing.member_portal_url == app.member_base_url
        assert config.platform.credential.name == "shared_platform_token"
        assert config.credential_environment() == {
            "platform_token": "AEP_LOCAL_PLATFORM_TOKEN",
            "platform_member_login": LOGIN_VARIABLE,
            "shared_platform_token": TOKEN_VARIABLE,
        }
        [backup] = list(tmp_path.glob("host.json.bak-*-before-shared-platform"))
        assert backup.read_text(encoding="utf-8") == before

        # The running Agent already uses the new client.
        assert runtime.platform is not None
        assert runtime.platform.binding.token_id == config.platform.token_id
        assert web.platform()["connection"] == "answered"
        settings = web.shared_platform_settings()
        assert settings["enrolled"]["bridge_id"] == "bridge-company"
        assert settings["enrolled"]["token_id"] == config.platform.token_id
        assert settings["login_saved"] is True and settings["assets_only"] is True
        assert settings["last_catalog"]["status"] == "answered"

        # Enrolling again rotates the token; the old one no longer works.
        first = config.platform.token_id
        again = web.update_shared_platform(_card(app))
        assert again["ok"] and again["probe"] == "answered"
        rotated = CompanyHostConfiguration.model_validate_json(path.read_text("utf-8"))
        assert rotated.platform is not None and rotated.platform.token_id != first
        assert app.state.tokens.grant(first).status == "revoked"
        assert saved[TOKEN_VARIABLE] != token


def test_a_new_process_finds_the_saved_token_without_the_environment(
    app: SharedPlatformApplication,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path, layout = _host(tmp_path)
    saved: dict[str, str] = {}
    login = _agent_login(app, _signed_in(app, "engineer", "member"))
    with build_runtime(
        CompanyHostConfiguration.model_validate_json(path.read_text("utf-8")), layout=layout
    ) as runtime:
        web = _web(runtime, path, saved)
        assert web.update_shared_platform(_card(app, login))["ok"]
    # As after a restart from a shell started before the token was saved.
    monkeypatch.delenv(TOKEN_VARIABLE)
    from host_runtime import platform_publish

    monkeypatch.setattr(platform_publish, "_saved_user_variable", saved.get)
    config = CompanyHostConfiguration.model_validate_json(path.read_text("utf-8"))
    with build_runtime(config, layout=layout) as restarted:
        assert AgentWeb(restarted).platform()["connection"] == "answered"


def test_the_card_refuses_what_it_cannot_use_and_never_echoes_a_secret(
    app: SharedPlatformApplication,
    tmp_path: Path,
) -> None:
    path, layout = _host(tmp_path)
    before = path.read_text(encoding="utf-8")
    saved: dict[str, str] = {}
    with build_runtime(
        CompanyHostConfiguration.model_validate_json(before), layout=layout
    ) as runtime:
        web = _web(runtime, path, saved)
        bad = web.update_shared_platform(
            {**_card(app), "member_portal_url": "http://172.25.228.141:8776"}
        )
        assert bad["ok"] is False and bad["code"] == "portal_url_invalid"
        bad = web.update_shared_platform({**_card(app), "base_url": "http://172.25.228.141:8775"})
        assert bad["code"] == "bridge_url_invalid"
        assert web.update_shared_platform({**_card(app), "base_url": ""})["code"] == (
            "bridge_url_missing"
        )
        # An address nothing answers at (an old local platform, a dropped
        # tunnel) is refused before anything is saved or enrolled.
        gone = web.update_shared_platform({**_card(app), "base_url": "http://127.0.0.1:9"})
        assert gone["code"] == "bridge_unreachable" and "nothing was saved" in gone["message"]
        typed = "not-a-code-but-maybe-a-password"
        refused = web.update_shared_platform(_card(app, typed))
        assert refused["code"] == "login_malformed" and typed not in json.dumps(refused)
        # Nothing was written for any of these.
        assert path.read_text(encoding="utf-8") == before and saved == {}
        assert not list(tmp_path.glob("host.json.bak-*"))

        # A Personal Agent code of another account: the settings are saved,
        # the PC is not enrolled, and the message names this PC's owner.
        other = web.update_shared_platform(
            _card(app, _agent_login(app, _signed_in(app, "leo", "member")))
        )
        assert other["ok"] is False and other["code"] == "device_owner_mismatch"
        assert other["saved"] is True and "engineer" in other["message"]
        assert TOKEN_VARIABLE not in saved
        config = CompanyHostConfiguration.model_validate_json(path.read_text("utf-8"))
        assert config.platform is not None
        assert config.platform.token_id == OLD_PLATFORM["token_id"]  # still the old one
        assert config.platform.member_portal_url == app.member_base_url  # one URL, both
        assert config.publishing is not None
        assert config.publishing.member_portal_url == app.member_base_url
        assert app.state.enrollment.devices() == ()

        # Save only (no enrollment) keeps the old token and needs no code.
        saved_only = web.update_shared_platform(_card(app, enroll=False))
        assert saved_only["ok"] is True and "just_enrolled" not in saved_only
        assert saved_only["enrolled"] is None

        assert AgentWeb(runtime).update_shared_platform(_card(app))["code"] == (
            "settings_read_only"
        )


def test_publish_approve_enroll_select_and_synchronize_end_to_end(
    app: SharedPlatformApplication,
    tmp_path: Path,
) -> None:
    """A member publishes, an administrator approves, another member's PC
    enrolls, sees it, selects it and synchronizes it: the exact bytes are
    installed, and this PC's grants.json is left as it was."""
    portal = app.member_base_url + "/v1/member/"
    leo = _signed_in(app, "leo", "member")
    admin = _signed_in(app, "leo-admin", "platform_admin")
    status, submitted = request(
        portal + "assets/submit",
        authorization=leo,
        body={"kind": "workflow", "change": "minor", "manifest": workflow_manifest()},
    )
    assert status == 200, submitted
    assert (
        request(
            portal + "admin/submissions/approve",
            authorization=admin,
            body={"submission_id": submitted["submission"]["submission_id"], "evidence": "read it"},
        )[0]
        == 200
    )

    path, layout = _host(tmp_path)
    grants = layout.grants.read_bytes()
    engineer = _signed_in(app, "engineer", "member")
    saved: dict[str, str] = {}
    with build_runtime(
        CompanyHostConfiguration.model_validate_json(path.read_text("utf-8")), layout=layout
    ) as runtime:
        web = _web(runtime, path, saved)
        assert web.update_shared_platform(_card(app, _agent_login(app, engineer)))["ok"]

        listed = web.platform()
        assert listed["assets_only"] is True and listed["bridge_id"] == "bridge-company"
        [entry] = [item for item in listed["catalog"] if item["name"] == "weekly-check"]
        assert (entry["version"], entry["authorized"], entry["installed"]) == (
            "1.0.0",
            False,
            False,
        )
        assert "grants.json" in listed["note"]

        identity = {"namespace": "lab", "name": "weekly-check", "version": "1.0.0"}
        status, chosen = request(
            portal + "select",
            authorization=engineer,
            body={"bridge_id": "bridge-company", "asset": identity},
        )
        assert status == 200, chosen

        result = web.synchronize()
        assert result["status"] == "answered" and result["assets_only"] is True, result
        assert result["installed"] == [identity]
        installed = layout.workflows / "lab__weekly-check__1.0.0.json"
        package = app.state.packages.get(AssetIdentity(**identity))
        assert package is not None and package.metadata.package is not None
        assert installed.read_bytes() == app.state.artifacts[package.metadata.package.artifact_ref]
        assert layout.grants.read_bytes() == grants
        assert not layout.authorization.exists()
        [after] = [item for item in result["after"]["catalog"] if item["name"] == "weekly-check"]
        assert after["authorized"] is True and after["installed"] is True


def test_an_asset_the_owner_shares_after_publication_reaches_another_members_pc(
    app: SharedPlatformApplication,
    tmp_path: Path,
) -> None:
    """Owner decision 2026-10-15: `leo` publishes something only he may use;
    another member's Bridge catalog does not list it and the portal refuses
    to select it. Once leo says who else may use it, that member's catalog
    lists it, the selection is accepted and a sync installs it."""
    portal = app.member_base_url + "/v1/member/"
    leo = _signed_in(app, "leo", "member")
    admin = _signed_in(app, "leo-admin", "platform_admin")
    manifest = workflow_manifest()  # declares another person as owner
    status, submitted = request(
        portal + "assets/submit",
        authorization=leo,
        body={"kind": "workflow", "change": "minor", "visibility": "private", "manifest": manifest},
    )
    assert status == 200, submitted
    assert submitted["submission"]["owner"] == {"type": "user", "id": "leo"}
    assert (
        request(
            portal + "admin/submissions/approve",
            authorization=admin,
            body={"submission_id": submitted["submission"]["submission_id"], "evidence": "read it"},
        )[0]
        == 200
    )

    path, layout = _host(tmp_path)
    engineer = _signed_in(app, "engineer", "member")
    identity = {"namespace": "lab", "name": "weekly-check", "version": "1.0.0"}
    with build_runtime(
        CompanyHostConfiguration.model_validate_json(path.read_text("utf-8")), layout=layout
    ) as runtime:
        web = _web(runtime, path, {})
        assert web.update_shared_platform(_card(app, _agent_login(app, engineer)))["ok"]
        assert [i for i in web.platform()["catalog"] if i["name"] == "weekly-check"] == []
        assert request(
            portal + "select",
            authorization=engineer,
            body={"bridge_id": "bridge-company", "asset": identity},
        ) == (403, {"code": "asset_not_entitled"})

        status, shared = request(
            portal + "assets/access/update",
            authorization=leo,
            body={"namespace": "lab", "name": "weekly-check", "members": ["engineer"]},
        )
        assert status == 200, shared
        [entry] = [i for i in web.platform()["catalog"] if i["name"] == "weekly-check"]
        assert entry["version"] == "1.0.0"
        assert (
            request(
                portal + "select",
                authorization=engineer,
                body={"bridge_id": "bridge-company", "asset": identity},
            )[0]
            == 200
        )
        result = web.synchronize()
        assert result["status"] == "answered" and result["installed"] == [identity], result
        assert (layout.workflows / "lab__weekly-check__1.0.0.json").exists()


def test_the_settings_page_has_the_card_and_capabilities_no_longer_holds_the_code() -> None:
    for hook in (
        'id="shared-platform-card"',
        'id="shared-portal-url"',
        'id="shared-bridge-url"',
        'id="shared-code"',
        'id="shared-enroll"',
        "/api/settings/shared-platform",
        "loadSharedPlatform()",
        "marketplaceUrl(",
        "permissions come from this PC's grants.json",
    ):
        assert hook in PAGE
    assert 'id="publish-code"' not in PAGE and 'id="publish-connect"' not in PAGE
    card = PAGE[PAGE.index('id="shared-platform-card"') : PAGE.index("Laya decision acceleration")]
    assert "<section" not in card and 'type="password"' in card


@pytest.mark.skipif(browser_path() is None, reason="no Chromium browser is installed")
def test_the_card_renders_in_settings_in_a_real_browser(tmp_path: Path) -> None:
    config, layout = ready(tmp_path)
    path = host_json(tmp_path, config)
    with build_runtime(config, layout=layout) as runtime:
        served = AgentWebServer(AgentWeb(runtime, config_path=path))
        import threading

        thread = threading.Thread(target=served.serve_forever, daemon=True)
        thread.start()
        browser = Browser(tmp_path / "browser", timeout_s=60)
        browser.start()
        try:
            browser.navigate(served.address)
            controls = {item.element_id: item for item in browser.look().elements}
            browser.click(controls["nav-settings"].index, expected=controls["nav-settings"])
            size = browser._evaluate(
                'JSON.stringify(["shared-platform-card","shared-enroll","shared-code"].map('
                "(id) => { const r = document.getElementById(id).getBoundingClientRect();"
                " return [r.width, r.height]; }))"
            )
            card, button, field = json.loads(str(size))
            assert card[0] > 300 and card[1] > 120, size
            assert button[0] > 40 and button[1] > 20, size
            assert field[0] > 100 and field[1] > 20, size
            import time

            deadline = time.monotonic() + 20
            status: object = ""
            while "bridge-company" not in str(status) and time.monotonic() < deadline:
                time.sleep(0.2)  # the card fills in when its settings arrive
                status = browser._evaluate('document.getElementById("shared-this-pc").textContent')
            assert "bridge-company" in str(status) and "grants.json" in str(status)
        finally:
            browser.close()
            browser.discard_profile()
            served.shutdown()
            served.server_close()
            thread.join(timeout=5)
