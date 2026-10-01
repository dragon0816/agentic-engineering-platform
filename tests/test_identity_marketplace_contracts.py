"""Identity roles, category facets and admin-facing contract evolution."""

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from common.assets import AssetIdentity, AssetMetadata, Owner, PackageMetadata
from common.enrollment import Invitation, PlatformUser
from common.identity import IssuedMemberLogin, MemberLoginGrant
from common.member import AdminInvitationCreateRequest, AdminInvitationListReply

NOW = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)


def metadata(**changes: object) -> AssetMetadata:
    values: dict[str, object] = {
        "identity": AssetIdentity(namespace="engineering", name="fixture", version="1.0.0"),
        "owner": Owner(type="team", id="engineering"),
        "visibility": "team",
        "lifecycle": "published",
        "package": PackageMetadata(artifact_ref="registry://fixture", sha256="0" * 64),
    }
    values.update(changes)
    return AssetMetadata.model_validate(values)


def test_existing_invitations_and_users_default_to_member() -> None:
    invitation = Invitation(
        invitation_id="invite-engineer", actor="engineer", issued_by="platform-admin"
    )
    user = PlatformUser(actor="engineer", invitation_id=invitation.invitation_id)
    assert invitation.role == "member"
    assert user.role == "member"
    promoted = Invitation.model_validate({**invitation.model_dump(), "role": "platform_admin"})
    assert promoted.role == "platform_admin"


def test_categories_are_optional_unique_discovery_metadata() -> None:
    assert metadata().categories == ()
    assert metadata(categories=("automation", "testing")).categories == (
        "automation",
        "testing",
    )
    with pytest.raises(ValidationError, match="categories must be unique"):
        metadata(categories=("automation", "automation"))


def test_admin_invitation_request_has_bounded_unique_groups() -> None:
    request = AdminInvitationCreateRequest(
        actor="new-member",
        role="platform_admin",
        groups=("engineering", "quality"),
        valid_for_minutes=90,
    )
    assert request.role == "platform_admin"
    with pytest.raises(ValidationError, match="groups must be unique"):
        AdminInvitationCreateRequest(actor="duplicate", groups=("engineering", "engineering"))


def test_browser_login_secret_never_enters_its_contract_or_repr() -> None:
    secret = "a-browser-login-secret-that-is-long-enough"
    grant = MemberLoginGrant(
        login_id="login-engineer",
        actor="engineer",
        fingerprint="0" * 64,
        label="This browser",
        issued_at=NOW,
        expires_at=NOW + timedelta(days=30),
    )
    issued = IssuedMemberLogin(grant, secret)
    assert issued.bearer == f"login-engineer:{secret}"
    assert secret not in grant.model_dump_json()
    assert secret not in repr(issued)


def test_admin_invitation_list_refuses_duplicate_records() -> None:
    invitation = Invitation(
        invitation_id="invite-engineer", actor="engineer", issued_by="platform-admin"
    )
    record = {"invitation": invitation, "expires_at": NOW + timedelta(hours=1)}
    with pytest.raises(ValidationError, match="listed once"):
        AdminInvitationListReply(invitations=(record, record))
