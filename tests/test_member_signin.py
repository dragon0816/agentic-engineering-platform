"""Invitation proof to member-session integration for the shared platform."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import timedelta
from typing import Any

import pytest
from test_platform_transport import NOW, Platform

from common.base import Contract
from common.enrollment import BridgeExecutionSubject, Invitation
from control_plane.enrollment import EnrollmentError
from control_plane.member import InMemoryMemberSessions, MemberService
from control_plane.member_http import MemberPortalServer
from control_plane.member_signin import InMemoryInvitationSignIn, InvitationSignInError

PROOF = "invitation-proof-secret-with-at-least-thirty-two-chars"


def invitation(actor: str = "new-member", invitation_id: str = "invite-new") -> Invitation:
    return Invitation(
        invitation_id=invitation_id,
        actor=actor,
        issued_by="platform-admin",
        groups=("engineering",),
    )


def sign_in(platform: Platform, sessions: InMemoryMemberSessions) -> InMemoryInvitationSignIn:
    return InMemoryInvitationSignIn(
        enrollment=platform.enrollment,
        sessions=sessions,
        clock=lambda: NOW,
    )


def post(
    url: str,
    authorization: str,
    body: object | None = None,
) -> tuple[int, dict[str, Any]]:
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(url, method="POST", data=data)
    request.add_header("Authorization", authorization)
    if data is not None:
        request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=20) as answer:
            return answer.status, json.loads(answer.read())
    except urllib.error.HTTPError as refused:
        return refused.code, json.loads(refused.read())


def test_invitation_metadata_and_stored_grant_never_contain_the_proof() -> None:
    platform = Platform()
    sessions = InMemoryMemberSessions()
    adapter = sign_in(platform, sessions)

    issued = adapter.invite(
        invitation(),
        expires_at=NOW + timedelta(hours=2),
        secret=PROOF,
    )

    assert not isinstance(issued, Contract)
    assert PROOF not in repr(issued)
    assert "secret" not in issued.grant.model_dump()
    assert PROOF not in issued.grant.model_dump_json()
    assert PROOF not in platform.enrollment.invitation("invite-new").model_dump_json()
    assert platform.enrollment.invitation("invite-new").status == "pending"


def test_weak_proof_or_invalid_expiry_does_not_create_an_invitation() -> None:
    platform = Platform()
    adapter = sign_in(platform, InMemoryMemberSessions())

    with pytest.raises(InvitationSignInError, match="invalid_request"):
        adapter.invite(
            invitation(),
            expires_at=NOW + timedelta(hours=1),
            secret="guessable",
        )
    with pytest.raises(EnrollmentError, match="invitation_missing"):
        platform.enrollment.invitation("invite-new")

    with pytest.raises(ValueError, match="expire after"):
        adapter.invite(invitation(), expires_at=NOW, secret=PROOF)
    with pytest.raises(EnrollmentError, match="invitation_missing"):
        platform.enrollment.invitation("invite-new")


def test_unknown_and_wrong_invitation_proofs_are_indistinguishable() -> None:
    platform = Platform()
    adapter = sign_in(platform, InMemoryMemberSessions())
    adapter.invite(invitation(), expires_at=NOW + timedelta(hours=1), secret=PROOF)

    for invitation_id, proof in (
        ("invite-unknown", PROOF),
        ("invite-new", "wrong-proof-that-is-still-long-enough-to-compare"),
    ):
        with pytest.raises(InvitationSignInError) as refused:
            adapter.accept(invitation_id, proof)
        assert refused.value.code == "authentication_failed"
    assert platform.enrollment.invitation("invite-new").status == "pending"


def test_redeeming_invitation_creates_member_and_short_lived_session_once() -> None:
    platform = Platform()
    sessions = InMemoryMemberSessions()
    adapter = sign_in(platform, sessions)
    issued = adapter.invite(
        invitation(),
        expires_at=NOW + timedelta(minutes=30),
        secret=PROOF,
    )
    grants_before = platform.authorization.grants("bridge-company")
    authorization_before = platform.authorization.authorization("bridge-company", issued_at=NOW)

    session = adapter.accept(issued.grant.invitation_id, issued.secret)
    who = sessions.authenticate(session.grant.session_id, session.secret, now=NOW)

    assert who.actor == "new-member"
    assert who.bridge_id is None
    assert who.method == "invitation-proof"
    assert session.grant.expires_at == issued.grant.expires_at
    assert platform.enrollment.user("new-member").groups == ("engineering",)
    assert adapter.grant("invite-new").status == "redeemed"
    assert platform.authorization.grants("bridge-company") == grants_before
    assert (
        platform.authorization.authorization("bridge-company", issued_at=NOW)
        == authorization_before
    )
    assert not platform.enrollment.admit(
        BridgeExecutionSubject(actor="new-member", bridge_id="bridge-company")
    )
    with pytest.raises(InvitationSignInError) as replay:
        adapter.accept(issued.grant.invitation_id, issued.secret)
    assert replay.value.code == "invitation_used"


def test_expired_or_revoked_invitation_proof_cannot_create_a_session() -> None:
    platform = Platform()
    sessions = InMemoryMemberSessions()
    clock = [NOW]
    expired = InMemoryInvitationSignIn(
        enrollment=platform.enrollment,
        sessions=sessions,
        clock=lambda: clock[0],
    )
    adapter_grant = expired.invite(
        invitation("expired", "invite-expired"),
        expires_at=NOW + timedelta(hours=1),
        secret=PROOF,
    )
    clock[0] = NOW + timedelta(hours=2)
    with pytest.raises(InvitationSignInError) as refusal:
        expired.accept(adapter_grant.grant.invitation_id, PROOF)
    assert refusal.value.code == "invitation_expired"

    active = sign_in(platform, sessions)
    second = active.invite(
        invitation("revoked", "invite-revoked"),
        expires_at=NOW + timedelta(hours=1),
        secret=PROOF,
    )
    active.revoke(second.grant.invitation_id)
    with pytest.raises(InvitationSignInError) as refusal:
        active.accept(second.grant.invitation_id, second.secret)
    assert refusal.value.code == "invitation_revoked"


def test_invitation_link_redeems_over_real_http_without_identity_claims() -> None:
    platform = Platform()
    sessions = InMemoryMemberSessions()
    adapter = sign_in(platform, sessions)
    service = MemberService(
        enrollment=platform.enrollment,
        authorization=platform.authorization,
        sessions=sessions,
        clock=lambda: NOW,
    )
    issued = adapter.invite(
        invitation(),
        expires_at=NOW + timedelta(hours=1),
        secret=PROOF,
    )

    with MemberPortalServer(service, sign_in=adapter) as server:
        link = server.invitation_url(issued)
        assert link.startswith(server.base_url + "/#invitation=")
        assert PROOF in link

        status, refused = post(
            server.base_url + "/v1/member/sign-in",
            f"Invitation {issued.bearer}",
            {"actor": "somebody-else"},
        )
        assert status == 400 and refused == {"code": "invalid_request"}

        status, reply = post(
            server.base_url + "/v1/member/sign-in",
            f"Invitation {issued.bearer}",
        )
        assert status == 200
        session_id, separator, session_secret = reply["session"].partition(":")
        assert separator
        assert sessions.authenticate(session_id, session_secret, now=NOW).actor == "new-member"

        with urllib.request.urlopen(server.base_url + "/", timeout=20) as answer:
            page = answer.read().decode("utf-8")
        assert "/v1/member/sign-in" in page
        assert "#invitation=" not in page
        for browser_store in ("localStorage", "sessionStorage", "indexedDB"):
            assert browser_store not in page


def test_sign_in_http_hides_unknown_and_wrong_proofs_and_rejects_bridge_scheme() -> None:
    platform = Platform()
    sessions = InMemoryMemberSessions()
    adapter = sign_in(platform, sessions)
    service = MemberService(
        enrollment=platform.enrollment,
        authorization=platform.authorization,
        sessions=sessions,
        clock=lambda: NOW,
    )
    issued = adapter.invite(
        invitation(),
        expires_at=NOW + timedelta(hours=1),
        secret=PROOF,
    )

    with MemberPortalServer(service, sign_in=adapter) as server:
        answers = [
            post(
                server.base_url + "/v1/member/sign-in",
                f"Invitation invite-unknown:{PROOF}",
            ),
            post(
                server.base_url + "/v1/member/sign-in",
                "Invitation invite-new:wrong-proof-value",
            ),
            post(
                server.base_url + "/v1/member/sign-in",
                f"Bearer {issued.bearer}",
            ),
        ]
    assert answers == [(401, {"code": "authentication_failed"})] * 3
