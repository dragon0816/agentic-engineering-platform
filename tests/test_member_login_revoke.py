"""A member revokes one of their own logins (`logins/revoke`, owner 2026-10-19).

Agent Web revokes the Personal Agent code it replaced and the browser login a
password sign-in created. Another member's login, an unknown one and one already
ended all answer `login_missing`. In-process platform fixture only.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path

import pytest
from test_shared_platform_app import request

from common.enrollment import Invitation
from control_plane.app import SharedPlatformApplication


@pytest.fixture
def app(tmp_path: Path) -> Iterator[SharedPlatformApplication]:
    platform = SharedPlatformApplication.empty(
        administrators=("platform-admin",), registry_path=tmp_path / "registry.sqlite"
    )
    with platform:
        yield platform


def _authenticates(app: SharedPlatformApplication, code: str) -> bool:
    status, _ = request(
        app.member_base_url + "/v1/member/session", authorization=f"Login {code}", method="POST"
    )
    return status == 200


def _member(app: SharedPlatformApplication, actor: str) -> str:
    proof = app.issue_invitation(
        Invitation(invitation_id=f"invite-{actor}", actor=actor, issued_by="platform-admin"),
        expires_at=app.member_service.now() + timedelta(days=1),
    )
    status, reply = request(
        app.member_base_url + "/v1/member/sign-in",
        authorization=f"Invitation {proof.bearer}",
        method="POST",
    )
    assert status == 200
    return f"Bearer {reply['session']}"


def test_a_member_revokes_only_their_own_logins(app: SharedPlatformApplication) -> None:
    anna, ben = _member(app, "anna"), _member(app, "ben")
    issue = app.member_base_url + "/v1/member/logins/issue-agent"
    revoke = app.member_base_url + "/v1/member/logins/revoke"
    _, annas = request(issue, authorization=anna, body={})
    _, bens = request(issue, authorization=ben, body={})
    # Ben cannot revoke Anna's login; it answers like a missing one.
    status, reply = request(revoke, authorization=ben, body={"login_id": annas["login_id"]})
    assert status == 404 and reply == {"code": "login_missing"}
    assert _authenticates(app, annas["login"])
    status, reply = request(revoke, authorization=ben, body={"login_id": "login-0000000000000000"})
    assert status == 404 and reply == {"code": "login_missing"}
    # Anna revokes her own; again answers missing.
    status, reply = request(revoke, authorization=anna, body={"login_id": annas["login_id"]})
    assert status == 200 and reply == {"login_id": annas["login_id"], "status": "revoked"}
    assert not _authenticates(app, annas["login"]) and _authenticates(app, bens["login"])
    assert request(revoke, authorization=anna, body={"login_id": annas["login_id"]})[0] == 404
    # No session, or a malformed body, is refused.
    assert request(revoke, body={"login_id": bens["login_id"]})[0] == 401
    assert request(revoke, authorization=ben, body={"login": "x"})[0] == 400
    assert _authenticates(app, bens["login"])
