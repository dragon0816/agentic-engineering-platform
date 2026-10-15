"""Who owns a member-published asset and who may use it.

Requirements: owner decisions of 2026-10-15 (`docs/phases/MEMBER_PUBLISH.md`,
"Owner and who can use it"), after two assets published by `leo` were
invisible to `leo.chi`:

1. a new name keeps the team (or organization) owner its manifest declares
   when the submitter belongs to it; otherwise the submitter owns it, and an
   existing name keeps its recorded owner;
2. the publisher chooses the visibility when submitting;
3. after publication the name's owner, a member of an owning team, or a
   platform administrator decides who may use it, and every place that
   lists, offers or accepts an asset for a member follows that decision.
"""

from __future__ import annotations

import sqlite3
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError
from test_asset_ownership import NOW, REGISTRIES, enrollment, who
from test_member_publish import submit, workflow_manifest

from common.assets import AssetIdentity, AssetMetadata, Owner
from common.enrollment import Invitation
from common.identity import NameAccess, entitled
from common.member import AssetApproveRequest, AssetSubmitRequest
from control_plane.authorization import InMemoryAuthorizationRegistry
from control_plane.distribution import ControlError, InMemoryPackageRegistry, PackageRegistry
from control_plane.enrollment import InMemoryEnrollmentRegistry
from control_plane.ownership import AssetOwnershipService, OwnershipError
from control_plane.registry_sqlite import SCHEMA_VERSION, SqliteRegistry
from control_plane.submissions import SubmissionService, SubmissionStore

QUALITY = {"type": "team", "id": "quality"}


def _browser_missing() -> bool:
    from integrations.browser import browser_path

    return browser_path() is None
WEEKLY = AssetIdentity(namespace="lab", name="weekly-check", version="1.0.0")


def declared(owner: dict[str, str], visibility: str = "team") -> dict[str, Any]:
    manifest = workflow_manifest()
    manifest["metadata"]["owner"] = owner
    manifest["metadata"]["visibility"] = visibility
    return manifest


def members() -> InMemoryEnrollmentRegistry:
    """The ownership tests' members, plus `root`, a platform administrator
    in no team."""
    registry = enrollment()
    registry.issue(Invitation(invitation_id="invite-root", actor="root",
                              issued_by="platform-admin", role="platform_admin"))
    registry.accept("invite-root", "root")
    return registry


@pytest.fixture(params=sorted(REGISTRIES))
def queue(request: pytest.FixtureRequest, tmp_path: Path) -> SubmissionService:
    registry: PackageRegistry = REGISTRIES[request.param](tmp_path)
    artifacts: dict[str, bytes] = {}
    store = SubmissionStore(None if request.param == "memory" else tmp_path / "registry.sqlite")
    ownership = AssetOwnershipService(members(), registry, artifacts=artifacts)
    return SubmissionService(ownership, registry, store, artifacts=artifacts, clock=lambda: NOW)


def publish(queue: SubmissionService, actor: str = "alice", **options: Any) -> AssetIdentity:
    item = submit(queue, actor, **options)
    queue.approve(who("root"), AssetApproveRequest(
        submission_id=item.submission_id, evidence="read it"))
    return item.identity


def available(queue: SubmissionService, actor: str) -> list[str]:
    registry = InMemoryAuthorizationRegistry(queue.ownership.enrollment, queue.packages)
    return [
        package.metadata.identity.name
        for package in registry.available(who(actor), now=NOW)
    ]


# -- 1. the owner of a new name ---------------------------------------------


def test_a_declared_team_owner_is_kept_when_the_submitter_belongs_to_it(
    queue: SubmissionService,
) -> None:
    item = submit(queue, "alice", manifest=declared(QUALITY))
    assert item.owner == Owner(type="team", id="quality")
    assert queue.detail(item.submission_id).manifest["metadata"]["owner"] == QUALITY
    publish_identity = queue.approve(who("root"), AssetApproveRequest(
        submission_id=item.submission_id, evidence="ok")).identity
    record = queue.packages.ownership("lab", "weekly-check")
    assert record is not None and record.owner == Owner(type="team", id="quality")
    package = queue.packages.get(publish_identity)
    assert package is not None and package.metadata.owner.id == "quality"
    # The team's other member may use it; somebody outside the team may not.
    assert available(queue, "bob") == ["weekly-check"]
    assert available(queue, "carol") == []


def test_a_declared_owner_the_submitter_does_not_belong_to_is_replaced_by_them(
    queue: SubmissionService,
) -> None:
    assert submit(queue, "carol", manifest=declared(QUALITY)).owner == Owner(
        type="user", id="carol")
    # A declared person is never trusted, even when it names the submitter's
    # teammate.
    other = declared({"type": "user", "id": "bob"})
    other["metadata"]["identity"]["name"] = "other-check"
    assert submit(queue, "alice", manifest=other).owner == Owner(type="user", id="alice")


def test_an_existing_name_keeps_its_recorded_owner(queue: SubmissionService) -> None:
    publish(queue, "alice")  # owned by alice as a person
    later = submit(queue, "alice", change="patch", manifest=declared(QUALITY))
    assert later.owner == Owner(type="user", id="alice")


# -- 2. the publisher chooses who may use it ---------------------------------


def test_the_publisher_chooses_the_visibility_when_submitting(
    queue: SubmissionService,
) -> None:
    default = submit(queue, "alice", manifest=declared(QUALITY, "organization"))
    assert default.visibility == "organization"
    chosen = queue.submit(who("alice"), _request(declared(QUALITY, "organization"), "team"))
    assert chosen.visibility == "team"
    assert queue.detail(chosen.submission_id).manifest["metadata"]["visibility"] == "team"
    with pytest.raises(ValidationError):
        _request(declared(QUALITY), "everyone")


def _request(manifest: dict[str, Any], visibility: str) -> AssetSubmitRequest:
    return AssetSubmitRequest.model_validate(
        {"kind": "workflow", "change": "minor", "visibility": visibility, "manifest": manifest})


# -- 3. who can use it, after publication -----------------------------------


def test_an_access_record_widens_and_narrows_what_a_member_may_use() -> None:
    metadata = AssetMetadata.model_validate(
        {"identity": WEEKLY.model_dump(), "owner": {"type": "user", "id": "leo"},
         "visibility": "team", "lifecycle": "published"})

    def access(**changes: Any) -> NameAccess:
        return NameAccess.model_validate({"namespace": "lab", "name": "weekly-check",
                                          "updated_by": "leo", "updated_at": NOW, **changes})

    assert not entitled(metadata, "leo.chi", ("engineering",))
    assert entitled(metadata, "leo.chi", (), access(visibility="organization"))
    assert entitled(metadata, "leo.chi", (), access(members=("leo.chi",)))
    assert entitled(metadata, "leo.chi", ("engineering",), access(groups=("engineering",)))
    assert not entitled(metadata, "leo.chi", ("qa",), access(groups=("engineering",)))
    shared = metadata.model_copy(update={"visibility": "organization"})
    assert not entitled(shared, "leo.chi", (), access(visibility="private"))
    # It never takes the asset away from its owner.
    assert entitled(shared, "leo", (), access(visibility="private"))
    with pytest.raises(ValueError, match="its own name"):
        entitled(metadata, "leo.chi", (), access(name="other"))
    with pytest.raises(ValidationError, match="unique"):
        access(members=("a", "a"))


def test_only_the_owner_a_team_member_or_an_administrator_decides(
    queue: SubmissionService,
) -> None:
    publish(queue, "alice", manifest=declared(QUALITY, "team"))
    service = queue.ownership
    with pytest.raises(OwnershipError, match="not_name_owner"):
        service.set_access(who("carol"), "lab", "weekly-check", visibility="organization",
                           now=NOW)
    assert available(queue, "carol") == []
    entry = service.set_access(who("bob"), "lab", "weekly-check", visibility=None,
                               members=("carol",), now=NOW)
    assert entry.access is not None and entry.access.updated_by == "bob"
    assert (entry.declared_visibility, entry.visibility) == ("team", "team")
    assert available(queue, "carol") == ["weekly-check"]
    by_admin = service.set_access(who("root"), "lab", "weekly-check",
                                  visibility="private", now=NOW)
    assert by_admin.visibility == "private" and by_admin.access is not None
    assert by_admin.access.members == ()
    assert available(queue, "carol") == []
    assert available(queue, "bob") == ["weekly-check"]  # the owning team keeps it
    with pytest.raises(OwnershipError, match="access_member_unknown"):
        service.set_access(who("alice"), "lab", "weekly-check", visibility=None,
                           members=("nobody",), now=NOW)
    with pytest.raises(OwnershipError, match="name_missing"):
        service.set_access(who("alice"), "lab", "missing", visibility=None, now=NOW)


def test_the_owner_lists_their_names_and_an_administrator_lists_all(
    queue: SubmissionService,
) -> None:
    publish(queue, "alice", manifest=declared(QUALITY, "team"))
    other = declared({"type": "user", "id": "carol"}, "private")
    other["metadata"]["identity"]["name"] = "carols-check"
    publish(queue, "carol", manifest=other)
    service = queue.ownership
    assert [e.name for e in service.access_list(who("bob"), now=NOW)] == ["weekly-check"]
    assert [e.name for e in service.access_list(who("carol"), now=NOW)] == ["carols-check"]
    assert [e.name for e in service.access_list(who("root"), everything=True,
                                                now=NOW)] == ["carols-check", "weekly-check"]
    with pytest.raises(OwnershipError, match="not_name_owner"):
        service.access_list(who("carol"), everything=True, now=NOW)
    [entry] = service.access_list(who("alice"), now=NOW)
    assert (entry.kind, entry.owner.id, entry.versions, entry.access) == (
        "workflow", "quality", ("1.0.0",), None)


def test_selection_follows_the_access_record(queue: SubmissionService) -> None:
    identity = publish(queue, "carol", manifest=declared({"type": "user", "id": "carol"},
                                                         "private"))
    registry = InMemoryAuthorizationRegistry(queue.ownership.enrollment, queue.packages)
    assert [p.metadata.identity for p in registry.available(who("dave"), now=NOW)] == []
    queue.ownership.set_access(who("carol"), "lab", "weekly-check", visibility="organization",
                               now=NOW)
    assert [p.metadata.identity for p in registry.available(who("dave"), now=NOW)] == [
        identity]
    queue.ownership.set_access(who("carol"), "lab", "weekly-check", visibility=None, now=NOW)
    assert registry.available(who("dave"), now=NOW) == ()


def test_an_access_record_needs_a_published_name_and_survives_a_restart(
    tmp_path: Path,
) -> None:
    decided = NameAccess(namespace="lab", name="weekly-check", visibility="organization",
                         members=("carol",), groups=("quality",), updated_by="alice",
                         updated_at=NOW)
    for registry in (InMemoryPackageRegistry(), SqliteRegistry(tmp_path / "r.sqlite")):
        with pytest.raises(ControlError, match="name_missing"):
            registry.save_access(decided)
    path = tmp_path / "registry.sqlite"
    first = SqliteRegistry(path)
    service = AssetOwnershipService(members(), first)
    queue = SubmissionService(service, first, SubmissionStore(path), clock=lambda: NOW)
    publish(queue, "alice")
    queue.store.close()
    service.set_access(who("alice"), "lab", "weekly-check", visibility="organization",
                       members=("carol",), now=NOW + timedelta(minutes=1))
    again = SqliteRegistry(path)
    saved = again.access("lab", "weekly-check")
    assert saved is not None and saved.members == ("carol",)
    assert saved.visibility == "organization" and saved.updated_by == "alice"
    # Additive: the schema version is unchanged, so earlier code still opens it.
    with sqlite3.connect(path) as connection:
        row = connection.execute(
            "SELECT value FROM registry_meta WHERE key = 'schema_version'").fetchone()
    assert row == (SCHEMA_VERSION,) and SCHEMA_VERSION == "1"


# -- over the member portal ---------------------------------------------------


def _member(app: Any, actor: str, role: str = "member", groups: tuple[str, ...] = ()) -> str:
    from test_shared_platform_app import request

    proof = app.issue_invitation(
        Invitation(invitation_id=f"invite-{actor}", actor=actor, issued_by="platform-admin",
                   groups=groups, role=role),
        expires_at=app.member_service.now() + timedelta(days=1),
    )
    status, reply = request(app.member_base_url + "/v1/member/sign-in",
                            authorization=f"Invitation {proof.bearer}", method="POST")
    assert status == 200
    return f"Bearer {reply['session']}"


def test_portal_routes_read_and_change_who_can_use_a_name(tmp_path: Path) -> None:
    from test_shared_platform_app import request

    from control_plane.app import SharedPlatformApplication

    app = SharedPlatformApplication.empty(
        administrators=("platform-admin",), registry_path=tmp_path / "registry.sqlite",
        clock=lambda: NOW)
    with app:
        url = app.member_base_url + "/v1/member/"
        leo = _member(app, "leo", groups=("engineering",))
        colleague = _member(app, "leo.chi", groups=("engineering",))
        stranger = _member(app, "visitor")
        admin = _member(app, "leo-review", "platform_admin")
        manifest = declared({"type": "team", "id": "engineering"}, "organization")
        status, submitted = request(url + "assets/submit", authorization=leo, body={
            "kind": "workflow", "change": "minor", "visibility": "team",
            "manifest": manifest})
        assert status == 200, submitted
        assert submitted["submission"]["owner"] == {"type": "team", "id": "engineering"}
        assert submitted["submission"]["visibility"] == "team"
        assert request(url + "admin/submissions/approve", authorization=admin, body={
            "submission_id": submitted["submission"]["submission_id"],
            "evidence": "read"})[0] == 200

        status, mine = request(url + "assets/access", authorization=colleague, body={})
        assert status == 200 and [e["name"] for e in mine["entries"]] == ["weekly-check"]
        assert mine["entries"][0]["visibility"] == "team"
        assert request(url + "assets/access", authorization=stranger, body={}) == (
            200, {"entries": []})
        assert request(url + "assets/access", authorization=stranger,
                       body={"scope": "all"}) == (403, {"code": "not_name_owner"})
        status, every = request(url + "assets/access", authorization=admin,
                                body={"scope": "all"})
        assert status == 200 and len(every["entries"]) == 1

        change = {"namespace": "lab", "name": "weekly-check", "visibility": "organization",
                  "members": [], "groups": []}
        assert request(url + "assets/access/update", authorization=stranger, body=change) == (
            403, {"code": "not_name_owner"})
        status, updated = request(url + "assets/access/update", authorization=leo,
                                  body=change)
        assert status == 200 and updated["entry"]["visibility"] == "organization"
        assert updated["entry"]["access"]["updated_by"] == "leo"
        status, unknown = request(url + "assets/access/update", authorization=leo,
                                  body={**change, "members": ["nobody"]})
        assert (status, unknown) == (400, {"code": "access_member_unknown"})
        status, bad = request(url + "assets/access/update", authorization=leo,
                              body={**change, "members": ["leo@example"]})
        assert status == 400 and bad["reason"] == "account_invalid"
        assert request(url + "assets/access/update", authorization=admin,
                       body={**change, "visibility": None})[0] == 200
        assert app.state.packages.access("lab", "weekly-check") is not None


def test_an_invitation_for_an_invalid_account_says_why(tmp_path: Path) -> None:
    from test_shared_platform_app import request

    from control_plane.app import SharedPlatformApplication

    app = SharedPlatformApplication.empty(
        administrators=("platform-admin",), registry_path=tmp_path / "registry.sqlite",
        clock=lambda: NOW)
    with app:
        admin = _member(app, "leo-review", "platform_admin")
        status, reply = request(app.member_base_url + "/v1/member/admin/invitations",
                                authorization=admin, body={"actor": "leo.chi@example"})
        assert status == 400
        assert reply["code"] == "invalid_request" and reply["reason"] == "account_invalid"
        assert "no '@'" in reply["message"] and "leo.chi@example" not in reply["message"]
        status, reply = request(app.member_base_url + "/v1/member/admin/invitations",
                                authorization=admin,
                                body={"actor": "leo.chi", "groups": ["qa team"]})
        assert (status, reply["reason"]) == (400, "group_invalid")
        status, _ = request(app.member_base_url + "/v1/member/admin/invitations",
                            authorization=admin, body={"actor": "leo.chi"})
        assert status == 200


# -- the Member Portal page ---------------------------------------------------


def test_the_portal_page_has_the_published_assets_editor_and_name_rules() -> None:
    from control_plane.member_page import PAGE

    for hook in ('id="published"', 'id="published-rows"', 'id="published-scope"',
                 'id="access-editor"', 'id="access-visibility"', 'id="access-members"',
                 'id="access-groups"', 'id="access-save"', "/v1/member/assets/access",
                 "/v1/member/assets/access/update", "Everyone in the organization",
                 "Only the owning team", "not_name_owner"):
        assert hook in PAGE, hook
    # The invitation field shows a valid account, and the rule, not an email.
    assert 'placeholder="name@example"' not in PAGE and 'placeholder="leo.chi"' in PAGE
    assert "no @" in PAGE and "^[a-zA-Z_][a-zA-Z0-9_.-]*$" in PAGE
    # A refusal shows the platform's reason when it gives one.
    assert "data.message||data.code" in PAGE
    # An expired session is renewed from the stored login, then retried once.
    assert 'data.code==="session_expired"&&await renewSession()' in PAGE
    assert "Authorization:`Login ${login}`" in PAGE
    # The reviewer sees who will own it and who may use it.
    assert "Owner once published" in PAGE and "who can use it: ${s.visibility}" in PAGE


@pytest.mark.skipif(_browser_missing(), reason="no Chromium browser is installed")
def test_the_portal_renews_its_session_and_edits_access_in_a_real_browser(
    tmp_path: Path,
) -> None:
    """A real browser: the published assets list renders with a size, the
    page keeps working after its one-hour session expired, the editor saves,
    and an invitation for an e-mail address is refused in the page."""
    import json
    import time

    from test_shared_platform_app import request

    from control_plane.app import SharedPlatformApplication
    from integrations.browser import Browser

    moment = [NOW]
    app = SharedPlatformApplication.empty(
        administrators=("platform-admin",), registry_path=tmp_path / "registry.sqlite",
        clock=lambda: moment[0])
    with app:
        url = app.member_base_url + "/v1/member/"
        leo = _member(app, "leo", groups=("engineering",))
        status, submitted = request(url + "assets/submit", authorization=leo, body={
            "kind": "workflow", "change": "minor", "manifest": declared(
                {"type": "team", "id": "engineering"}, "team")})
        assert status == 200, submitted
        proof = app.issue_invitation(
            Invitation(invitation_id="invite-root", actor="root", issued_by="platform-admin",
                       groups=("engineering",), role="platform_admin"),
            expires_at=NOW + timedelta(days=1))
        browser = Browser(tmp_path / "browser", timeout_s=60)
        browser.start()

        def text(element: str) -> str:
            return str(browser._evaluate(f'document.getElementById("{element}").textContent'))

        def until(check: Any, seconds: float = 20) -> None:
            deadline = time.monotonic() + seconds
            while not check() and time.monotonic() < deadline:
                time.sleep(0.2)
            assert check()

        try:
            browser.navigate(app.member_base_url + f"/#invitation={proof.bearer}")
            until(lambda: "root" in text("actor"))
            approve = request(url + "admin/submissions/approve", authorization=leo, body={
                "submission_id": submitted["submission"]["submission_id"], "evidence": "x"})
            assert approve[0] == 403  # leo is no administrator; root approves below
            root_session = _member(app, "root2", "platform_admin")
            assert request(url + "admin/submissions/approve", authorization=root_session, body={
                "submission_id": submitted["submission"]["submission_id"],
                "evidence": "read"})[0] == 200

            # The session the page signed in with is over; the stored login is not.
            moment[0] = NOW + timedelta(hours=3)
            browser._evaluate('document.getElementById("published-scope").value="all";'
                              ' loadPublished(); 0')
            until(lambda: "weekly-check" in text("published-rows"))
            assert "unavailable" not in text("published-status")
            size = json.loads(str(browser._evaluate(
                'JSON.stringify(["published","published-rows"].map(id => {const r ='
                ' document.getElementById(id).getBoundingClientRect(); return [r.width,'
                ' r.height];}))')))
            assert size[0][0] > 300 and size[0][1] > 100 and size[1][1] > 20, size

            browser._evaluate('document.querySelector("#published-rows button").click(); 0')
            until(lambda: "weekly-check" in text("access-title"))
            assert "engineering" in text("access-effect")
            browser._evaluate('document.getElementById("access-visibility").value='
                              '"organization"; document.getElementById("access-members")'
                              '.value="leo"; document.getElementById("access-save").click(); 0')
            until(lambda: "Saved." in text("published-status"))
            saved = app.state.packages.access("lab", "weekly-check")
            assert saved is not None and saved.visibility == "organization"
            assert saved.members == ("leo",) and saved.updated_by == "root"

            browser._evaluate('document.getElementById("invite-actor").value="leo.chi@example";'
                              ' document.getElementById("create-invite").click(); 0')
            until(lambda: "no @" in str(browser._evaluate(
                'document.getElementById("invite-url").value')))
            # Refused in the page: the platform was never asked.
            assert sorted(item.actor for item in app.state.enrollment.invitations()) == [
                "leo", "root", "root2"]
        finally:
            browser.close()
            browser.discard_profile()
