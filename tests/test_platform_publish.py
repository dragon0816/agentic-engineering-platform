"""The Personal Agent publishes an installed Skill or Workflow as its member.

Requirements: `docs/phases/MEMBER_PUBLISH.md` (owner 2026-10-15), against a
real in-process shared platform.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path

import pytest
from test_member_publish import _signed_in, workflow_manifest
from test_shared_platform_app import request

from common.assets import AssetIdentity
from control_plane.app import SharedPlatformApplication
from host_runtime.contracts import HostLayout, PlatformPublishBinding
from host_runtime.platform_publish import (
    MemberPortalPublisher,
    PublishError,
    explain,
    installed_assets,
    installed_manifest,
)
from models.credentials import EnvironmentCredentials, StaticCredentials


@pytest.fixture
def platform(tmp_path: Path) -> Iterator[SharedPlatformApplication]:
    app = SharedPlatformApplication.empty(
        administrators=("platform-admin",), registry_path=tmp_path / "registry.sqlite")
    with app:
        yield app


def _agent_login(app: SharedPlatformApplication) -> str:
    member = _signed_in(app, "leo", "member")
    status, issued = request(app.member_base_url + "/v1/member/logins/issue-agent",
                             authorization=member, body={})
    assert status == 200
    return str(issued["login"])


def _installed(tmp_path: Path) -> HostLayout:
    layout = HostLayout.under(tmp_path / "workspace")
    layout.workflows.mkdir(parents=True)
    (layout.workflows / "lab__weekly-check__0.3.0.json").write_text(
        json.dumps(workflow_manifest(), indent=2) + "\n", encoding="utf-8")
    return layout


def _publisher(app: SharedPlatformApplication, login: str) -> MemberPortalPublisher:
    binding = PlatformPublishBinding(
        member_portal_url=app.member_base_url, credential={"name": "platform_member_login"})
    return MemberPortalPublisher(binding, StaticCredentials({"platform_member_login": login}))


def test_an_installed_workflow_is_submitted_listed_and_approved(
    platform: SharedPlatformApplication, tmp_path: Path
) -> None:
    layout = _installed(tmp_path)
    assert installed_assets(layout) == [{"kind": "workflow", "asset": "lab/weekly-check@0.3.0"}]
    publisher = _publisher(platform, _agent_login(platform))

    manifest = installed_manifest(layout, "workflow", "lab/weekly-check@0.3.0")
    submitted = publisher.submit("workflow", manifest, "minor", note="weekly numbers")
    assert submitted["status"] == "pending" and submitted["identity"]["version"] == "1.0.0"
    assert submitted["submitter"] == "leo"
    assert [s["submission_id"] for s in publisher.submissions()] == [submitted["submission_id"]]

    reviewer = _signed_in(platform, "leo-review", "platform_admin")
    status, _ = request(platform.member_base_url + "/v1/member/admin/submissions/approve",
                        authorization=reviewer,
                        body={"submission_id": submitted["submission_id"], "evidence": "ok"})
    assert status == 200
    assert publisher.submissions()[0]["status"] == "approved"
    published = platform.state.packages.get(
        AssetIdentity(namespace="lab", name="weekly-check", version="1.0.0"))
    assert published is not None and published.metadata.owner.id == "leo"


def test_a_pending_submission_can_be_withdrawn(
    platform: SharedPlatformApplication, tmp_path: Path
) -> None:
    publisher = _publisher(platform, _agent_login(platform))
    manifest = installed_manifest(_installed(tmp_path), "workflow", "lab/weekly-check@0.3.0")
    submitted = publisher.submit("workflow", manifest, "patch")
    assert publisher.withdraw(submitted["submission_id"])["status"] == "withdrawn"
    with pytest.raises(PublishError, match="submission_not_pending"):
        publisher.withdraw(submitted["submission_id"])


def test_a_session_is_reused_and_renewed_when_it_ends(
    platform: SharedPlatformApplication, tmp_path: Path
) -> None:
    login = _agent_login(platform)
    publisher = _publisher(platform, login)
    publisher.submissions()
    first = publisher._session
    publisher.submissions()
    assert publisher._session == first  # one session for several calls
    assert first is not None
    later = first[1] + timedelta(minutes=1)
    publisher._clock = lambda: later
    publisher.submissions()
    assert publisher._session != first


def test_without_a_login_or_a_platform_the_member_is_told_what_to_do(
    platform: SharedPlatformApplication, tmp_path: Path
) -> None:
    binding = PlatformPublishBinding(
        member_portal_url=platform.member_base_url, credential={"name": "platform_member_login"})
    unmapped = MemberPortalPublisher(binding, EnvironmentCredentials({}, environ={}))
    with pytest.raises(PublishError, match="login_missing"):
        unmapped.submissions()
    assert "Connect a Personal Agent" in explain("login_missing")
    wrong = _publisher(platform, "login-0000000000000000:not-the-secret-of-any-login-at-all")
    with pytest.raises(PublishError, match="authentication_failed"):
        wrong.submissions()
    gone = MemberPortalPublisher(
        PlatformPublishBinding(member_portal_url="http://127.0.0.1:9",
                               credential={"name": "x"}, timeout_seconds=2),
        StaticCredentials({"x": "login-1:secret"}))
    with pytest.raises(PublishError, match="platform_unreachable"):
        gone.submissions()


def test_the_asset_must_be_installed_and_named_exactly(tmp_path: Path) -> None:
    layout = _installed(tmp_path)
    for reference, code in (("lab/weekly-check", "bad_reference"),
                            ("lab/weekly-check@9.9.9", "not_installed"),
                            ("lab/weekly-check@0.3.0", "not_installed")):
        kind = "skill" if reference.endswith("0.3.0") else "workflow"
        with pytest.raises(PublishError, match=code):
            installed_manifest(layout, kind, reference)  # type: ignore[arg-type]


def test_the_publish_binding_holds_no_secret_and_needs_https_beyond_loopback() -> None:
    with pytest.raises(ValueError, match="https"):
        PlatformPublishBinding(member_portal_url="http://172.25.228.141:8776",
                               credential={"name": "platform_member_login"})
    with pytest.raises(ValueError):
        PlatformPublishBinding.model_validate({
            "member_portal_url": "http://127.0.0.1:28776",
            "credential": {"name": "platform_member_login", "value": "secret"}})
    ok = PlatformPublishBinding(member_portal_url="http://127.0.0.1:28776/",
                                credential={"name": "platform_member_login"})
    assert ok.member_portal_url == "http://127.0.0.1:28776"
