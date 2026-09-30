"""The shared-platform member entry point, from session to selection.

The browser session is deliberately different from the Bridge credential.
Requests name a Bridge and an asset, but never an actor, permission, policy or
decision time: the platform derives all of those from trusted state.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Iterator
from datetime import timedelta
from typing import Any

import pytest
from pydantic import ValidationError
from test_platform_transport import NOW, WORKFLOW, Platform

from common.identity import AuthenticatedActor
from common.member import MemberCatalogRequest, MemberSelectRequest
from control_plane.member import InMemoryMemberSessions, MemberError, MemberService
from control_plane.member_http import MemberPortalServer


def signed_in(actor: str = "engineer", **changes: Any) -> AuthenticatedActor:
    return AuthenticatedActor.model_validate(
        {
            "actor": actor,
            "method": "invitation-proof",
            "authenticated_at": NOW - timedelta(minutes=1),
            "expires_at": NOW + timedelta(hours=1),
            **changes,
        }
    )


def post(url: str, bearer: str, body: object) -> tuple[int, dict[str, Any]]:
    request = urllib.request.Request(url, method="POST", data=json.dumps(body).encode("utf-8"))
    request.add_header("Authorization", f"Bearer {bearer}")
    request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=20) as answer:
            return answer.status, json.loads(answer.read())
    except urllib.error.HTTPError as refused:
        return refused.code, json.loads(refused.read())


@pytest.fixture
def portal() -> Iterator[tuple[Platform, InMemoryMemberSessions, MemberPortalServer]]:
    platform = Platform()
    sessions = InMemoryMemberSessions()
    service = MemberService(
        enrollment=platform.enrollment,
        authorization=platform.authorization,
        sessions=sessions,
        clock=lambda: NOW,
    )
    with MemberPortalServer(service) as server:
        yield platform, sessions, server


def test_member_requests_cannot_claim_identity_policy_or_time() -> None:
    MemberCatalogRequest(bridge_id="bridge-company")
    MemberSelectRequest(bridge_id="bridge-company", asset=WORKFLOW)
    for field, value in (
        ("actor", "someone-else"),
        ("permissions", ["filesystem.write"]),
        ("policy_refs", ["bypass"]),
        ("decided_at", NOW),
    ):
        with pytest.raises(ValidationError):
            MemberSelectRequest.model_validate(
                {"bridge_id": "bridge-company", "asset": WORKFLOW.model_dump(), field: value}
            )


def test_only_a_direct_member_authentication_can_open_a_member_session() -> None:
    sessions = InMemoryMemberSessions()
    issued = sessions.issue(
        signed_in(), now=NOW, secret="member-session-secret-long-enough-to-be-safe"
    )
    assert "member-session-secret" not in repr(issued)
    assert issued.grant.actor == "engineer"
    assert sessions.authenticate(issued.grant.session_id, issued.secret, now=NOW).bridge_id is None

    with pytest.raises(ValueError, match="Bridge authentication"):
        sessions.issue(
            signed_in(bridge_id="bridge-company", method="bridge-access-token"),
            now=NOW,
            secret="bridge-session-secret-long-enough-to-be-safe",
        )
    with pytest.raises(MemberError, match="session_expired"):
        sessions.authenticate(
            issued.grant.session_id,
            issued.secret,
            now=issued.grant.expires_at,
        )


def test_member_catalog_select_and_revoke_cross_real_http(
    portal: tuple[Platform, InMemoryMemberSessions, MemberPortalServer],
) -> None:
    platform, sessions, server = portal
    issued = sessions.issue(
        signed_in(), now=NOW, secret="member-session-secret-long-enough-to-be-safe"
    )
    grants_before = platform.authorization.grants("bridge-company")

    status, before = post(
        server.base_url + "/v1/member/catalog",
        issued.bearer,
        {"bridge_id": "bridge-company"},
    )
    assert status == 200
    assert all(item["package"]["kind"] == "workflow" for item in before["entries"])
    workflow = next(item for item in before["entries"] if item["package"]["kind"] == "workflow")
    assert workflow["package"]["metadata"]["identity"] == WORKFLOW.model_dump()
    assert workflow["selected"] is True  # Platform fixture already selected it.

    # Revoke and choose again through requests that carry no actor or grant.
    status, revoked = post(
        server.base_url + "/v1/member/revoke",
        issued.bearer,
        {"bridge_id": "bridge-company", "asset": WORKFLOW.model_dump()},
    )
    assert status == 200 and revoked["selection"]["status"] == "revoked"
    status, selected = post(
        server.base_url + "/v1/member/select",
        issued.bearer,
        {"bridge_id": "bridge-company", "asset": WORKFLOW.model_dump()},
    )
    assert status == 200
    assert selected["selection"]["actor"] == "engineer"
    assert selected["selection"]["kind"] == "workflow"
    assert selected["selection"]["decided_at"] == NOW.isoformat().replace("+00:00", "Z")
    # Selecting an installable Workflow creates no execution permission.
    assert platform.authorization.grants("bridge-company") == grants_before


def test_member_entry_point_rejects_bridge_credentials_and_unbound_devices(
    portal: tuple[Platform, InMemoryMemberSessions, MemberPortalServer],
) -> None:
    platform, sessions, server = portal
    issued = sessions.issue(
        signed_in(), now=NOW, secret="member-session-secret-long-enough-to-be-safe"
    )

    status, failure = post(
        server.base_url + "/v1/member/catalog",
        f"{platform.company_token.grant.token_id}:{platform.company_token.secret}",
        {"bridge_id": "bridge-company"},
    )
    assert status == 401 and failure == {"code": "authentication_failed"}

    status, failure = post(
        server.base_url + "/v1/member/catalog",
        issued.bearer,
        {"bridge_id": "bridge-shared"},
    )
    assert status == 403 and failure == {"code": "actor_not_admitted"}


def test_portal_page_is_a_generic_same_origin_selection_ui(
    portal: tuple[Platform, InMemoryMemberSessions, MemberPortalServer],
) -> None:
    _platform, _sessions, server = portal
    with urllib.request.urlopen(server.base_url + "/", timeout=20) as answer:
        page = answer.read().decode("utf-8")
    assert "Shared Workflow Catalog" in page
    assert "/v1/member/catalog" in page
    assert "/v1/member/select" in page
    assert "/v1/member/revoke" in page
    assert "localStorage" not in page
    assert "bridge-access-token" not in page


def test_plain_http_member_portal_is_loopback_only(
    portal: tuple[Platform, InMemoryMemberSessions, MemberPortalServer],
) -> None:
    platform, sessions, _server = portal
    service = MemberService(
        enrollment=platform.enrollment,
        authorization=platform.authorization,
        sessions=sessions,
        clock=lambda: NOW,
    )
    with pytest.raises(ValueError, match="requires TLS"):
        MemberPortalServer(service, host="0.0.0.0")
