"""Preview catalog discovery, sync metadata and administrator separation."""

from datetime import timedelta
from pathlib import Path

from test_member_portal import post, signed_in
from test_platform_transport import NOW, Platform

from common.enrollment import Invitation
from control_plane.app import SharedPlatformConfiguration, application_from_config
from control_plane.member import InMemoryMemberSessions, MemberService
from control_plane.member_http import MemberPortalServer
from control_plane.preview_catalog import preview_packages, seed_preview_catalog


def test_preview_catalog_has_two_categorized_skills_workflows_and_one_extension() -> None:
    packages = preview_packages()
    assert [package.kind for package, _content in packages].count("skill") == 2
    assert [package.kind for package, _content in packages].count("workflow") == 2
    assert [package.kind for package, _content in packages].count("bridge_extension") == 1
    for package, content in packages:
        assert package.metadata.categories
        assert package.metadata.package is not None
        assert package.metadata.package.sha256
        assert content
    extension = next(package for package, _ in packages if package.kind == "bridge_extension")
    assert extension.metadata.technical_policy.status == "approved"


def test_durable_preview_seed_is_idempotent(tmp_path: Path) -> None:
    configuration = SharedPlatformConfiguration(
        administrators=("platform-admin",),
        control_port=0,
        member_port=0,
        registry_path=str(tmp_path / "platform.sqlite"),
        seed_preview_catalog=True,
    )
    first, _ = application_from_config(configuration, clock=lambda: NOW)
    try:
        assert len(first.state.packages.discover()) == 5
        assert len(first.state.artifacts) == 5
    finally:
        first.stop()
    second, _ = application_from_config(configuration, clock=lambda: NOW)
    try:
        assert len(second.state.packages.discover()) == 5
        assert len(second.state.artifacts) == 5
    finally:
        second.stop()


def test_only_admin_can_discover_extension_fixture_over_http() -> None:
    platform = Platform()
    seed_preview_catalog(platform)
    platform.enrollment.issue(
        Invitation(
            invitation_id="invite-preview-admin",
            actor="preview-admin",
            issued_by="platform-admin",
            role="platform_admin",
            groups=("engineering",),
        )
    )
    platform.enrollment.accept("invite-preview-admin", "preview-admin")
    sessions = InMemoryMemberSessions()
    member = sessions.issue(
        signed_in(), now=NOW, secret="preview-member-session-secret-long-enough"
    )
    admin = sessions.issue(
        signed_in(
            actor="preview-admin",
            expires_at=NOW + timedelta(hours=1),
        ),
        now=NOW,
        secret="preview-admin-session-secret-long-enough",
    )
    service = MemberService(
        enrollment=platform.enrollment,
        authorization=platform.authorization,
        sessions=sessions,
        clock=lambda: NOW,
    )
    with MemberPortalServer(service) as server:
        status, failure = post(server.base_url + "/v1/member/admin/extensions", member.bearer, {})
        assert status == 403 and failure == {"code": "not_administrator"}
        status, reply = post(server.base_url + "/v1/member/admin/extensions", admin.bearer, {})
    assert status == 200
    assert len(reply["entries"]) == 1
    assert reply["entries"][0]["package"]["kind"] == "bridge_extension"
    assert reply["entries"][0]["deployment_state"] == "available"
