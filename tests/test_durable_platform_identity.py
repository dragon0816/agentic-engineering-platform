"""Durable Shared Platform identity, browser login and admin invitation HTTP."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from common.assets import AssetIdentity
from common.authorization import DeviceAssetSelection
from common.enrollment import BridgeBinding, BridgeDevice, Invitation
from common.execution import TraceIdentifiers
from common.identity import AuthenticatedActor
from control_plane.app import SharedPlatformApplication
from control_plane.member import MemberError
from control_plane.preview_catalog import seed_preview_catalog
from workflow.host_bridge import BridgeRegistration

NOW = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)
INVITATION_SECRET = "a-durable-invitation-proof-that-is-long-enough"


def post(
    url: str,
    *,
    authorization: str,
    body: object | None = None,
) -> tuple[int, dict[str, Any]]:
    raw = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(url, method="POST", data=raw)
    request.add_header("Authorization", authorization)
    if raw is not None:
        request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=20) as answer:
            return answer.status, json.loads(answer.read())
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read())


def bootstrap(application: SharedPlatformApplication, actor: str = "owner") -> str:
    proof = application.issue_invitation(
        Invitation(
            invitation_id=f"invite-{actor}",
            actor=actor,
            issued_by="bootstrap-root",
            groups=("engineering",),
            role="platform_admin",
        ),
        expires_at=NOW + timedelta(days=1),
        secret=INVITATION_SECRET,
    )
    return proof.bearer


def test_invitation_member_session_and_login_survive_restart(tmp_path: Path) -> None:
    database = tmp_path / "platform.sqlite"
    first = SharedPlatformApplication.empty(
        administrators=("bootstrap-root",), registry_path=database, clock=lambda: NOW
    )
    invitation = bootstrap(first)
    first.stop()

    second = SharedPlatformApplication.empty(
        administrators=("bootstrap-root",), registry_path=database, clock=lambda: NOW
    )
    session = second.sign_in.accept(*invitation.split(":", 1))
    login = second.state.logins.issue(
        "owner",
        label="Test browser",
        now=NOW,
        secret="a-durable-browser-login-secret-that-is-long-enough",
    )
    second.stop()

    third = SharedPlatformApplication.empty(
        administrators=("bootstrap-root",), registry_path=database, clock=lambda: NOW
    )
    assert third.state.enrollment.user("owner").role == "platform_admin"
    assert third.state.sessions.authenticate(*session.bearer.split(":", 1), now=NOW).actor == (
        "owner"
    )
    assert third.state.logins.authenticate(*login.bearer.split(":", 1), now=NOW).actor == "owner"
    third.stop()


def test_member_asset_selection_survives_platform_restart(tmp_path: Path) -> None:
    database = tmp_path / "platform.sqlite"
    first = SharedPlatformApplication.empty(
        administrators=("bootstrap-root",), registry_path=database, clock=lambda: NOW
    )
    invitation = bootstrap(first)
    first.sign_in.accept(*invitation.split(":", 1))
    seed_preview_catalog(first.state)
    first.state.enrollment.register_device(
        BridgeDevice(
            bridge_id="bridge-owner",
            registered_by="owner",
            device_kind="company_workstation",
            windows_account_mode="dedicated_user",
            resource_scope="corporate_internal",
            local_isolation="single_user",
        ),
        BridgeRegistration(
            bridge_id="bridge-owner",
            owner_id="owner",
            trace=TraceIdentifiers(trace_id="durable", request_id="select", span_id="register"),
        ),
    )
    first.state.enrollment.bind(
        "owner",
        BridgeBinding(bridge_id="bridge-owner", actor="owner", role="device_admin"),
    )
    selected = first.state.authorization.select(
        AuthenticatedActor(
            actor="owner",
            method="invitation-proof",
            authenticated_at=NOW - timedelta(minutes=1),
            expires_at=NOW + timedelta(hours=1),
        ),
        DeviceAssetSelection(
            bridge_id="bridge-owner",
            actor="owner",
            kind="workflow",
            asset=AssetIdentity(namespace="preview", name="incident-triage", version="1.0.0"),
            decided_at=NOW,
        ),
        now=NOW,
    )
    first.stop()

    second = SharedPlatformApplication.empty(
        administrators=("bootstrap-root",), registry_path=database, clock=lambda: NOW
    )
    try:
        authorization = second.state.authorization.authorization("bridge-owner", issued_at=NOW)
        assert authorization.selections == (selected,)
    finally:
        second.stop()


def test_admin_can_invite_and_member_cannot(tmp_path: Path) -> None:
    app = SharedPlatformApplication.empty(
        administrators=("bootstrap-root",),
        registry_path=tmp_path / "platform.sqlite",
        clock=lambda: NOW,
    )
    owner_invitation = bootstrap(app)
    with app:
        status, signed_in = post(
            app.member_base_url + "/v1/member/sign-in",
            authorization=f"Invitation {owner_invitation}",
        )
        assert status == 200
        owner_session = signed_in["session"]
        owner_login = signed_in["login"]

        status, identity = post(
            app.member_base_url + "/v1/member/me",
            authorization=f"Bearer {owner_session}",
            body={},
        )
        assert status == 200
        assert (identity["actor"], identity["role"], identity["groups"]) == (
            "owner",
            "platform_admin",
            ["engineering"],
        )

        status, refreshed = post(
            app.member_base_url + "/v1/member/session",
            authorization=f"Login {owner_login}",
        )
        assert status == 200 and refreshed["session"].startswith("member-")

        status, created = post(
            app.member_base_url + "/v1/member/admin/invitations",
            authorization=f"Bearer {owner_session}",
            body={"actor": "colleague", "groups": ["quality"], "valid_for_minutes": 60},
        )
        assert status == 200
        assert created["invitation"]["invitation"]["actor"] == "colleague"
        assert "fingerprint" not in json.dumps(created["invitation"])

        colleague_invitation = created["url"].split("#invitation=", 1)[1]
        status, colleague = post(
            app.member_base_url + "/v1/member/sign-in",
            authorization=f"Invitation {colleague_invitation}",
        )
        assert status == 200
        status, refusal = post(
            app.member_base_url + "/v1/member/admin/invitations/list",
            authorization=f"Bearer {colleague['session']}",
            body={},
        )
        assert status == 403 and refusal == {"code": "not_administrator"}

        status, listed = post(
            app.member_base_url + "/v1/member/admin/invitations/list",
            authorization=f"Bearer {owner_session}",
            body={},
        )
        assert status == 200
        assert {item["invitation"]["actor"] for item in listed["invitations"]} == {
            "owner",
            "colleague",
        }


def test_revoked_browser_login_cannot_refresh_a_session() -> None:
    app = SharedPlatformApplication.empty(administrators=("bootstrap-root",), clock=lambda: NOW)
    login = app.state.logins.issue(
        "owner",
        label="Test browser",
        now=NOW,
        secret="a-revoked-browser-login-secret-that-is-long-enough",
    )
    app.state.logins.revoke(login.grant.login_id)
    try:
        app.state.logins.authenticate(*login.bearer.split(":", 1), now=NOW)
    except MemberError as error:
        assert error.code == "session_expired"
    else:
        raise AssertionError("a revoked browser login authenticated")
