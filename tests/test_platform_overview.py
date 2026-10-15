"""The administrator's Platform overview on the Member Portal.

Requirements: owner request of 2026-10-15 (`docs/phases/PLATFORM_OVERVIEW.md`):
an administrator sees, on the portal, every registered computer and the
publication status of every Skill, Workflow, Knowledge, Agent profile,
Extension, submission, Application and member; members keep their own view.
The owner's follow-up of the same day: the portal manages co-editors and the
owner of a name, and an administrator sets a member's role and groups.
"""

from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from test_application_catalog import application
from test_asset_access import _member
from test_asset_ownership import NOW, artifact_for, identity_of, package
from test_bridge_enrollment import bridge, enroll, enrollment
from test_member_publish import workflow_manifest
from test_shared_platform_app import request

from common.assets import AssetIdentity
from common.enrollment import Invitation
from control_plane.activity import PERSIST_EVERY, BridgeActivity
from control_plane.app import SharedPlatformApplication
from control_plane.enrollment import EnrollmentError, InMemoryEnrollmentRegistry
from control_plane.identity_store import SqliteIdentityStorage

WEEKLY = {"namespace": "lab", "name": "weekly-check"}


def manifest(name: str = "weekly-check", visibility: str = "team") -> dict[str, Any]:
    item = workflow_manifest(name)
    item["metadata"]["owner"] = {"type": "team", "id": "engineering"}
    item["metadata"]["visibility"] = visibility
    return item


def _app(tmp_path: Path, moment: list[Any]) -> SharedPlatformApplication:
    return SharedPlatformApplication.empty(
        administrators=("platform-admin",),
        registry_path=tmp_path / "registry.sqlite",
        clock=lambda: moment[0],
    )


def _seed(app: SharedPlatformApplication) -> dict[str, Any]:
    """A platform with something of every kind, every submission status,
    a Bridge that called the Bridge API and a pending invitation."""
    url = app.member_base_url + "/v1/member/"
    root = _member(app, "root", "platform_admin")
    leo = _member(app, "leo", groups=("engineering",))
    chi = _member(app, "leo.chi")
    visitor = _member(app, "visitor")

    def submit(session: str, body: dict[str, Any]) -> dict[str, Any]:
        status, reply = request(url + "assets/submit", authorization=session, body=body)
        assert status == 200, reply
        return dict(reply["submission"])

    first = submit(leo, {"kind": "workflow", "change": "minor", "manifest": manifest()})
    assert (
        request(
            url + "admin/submissions/approve",
            authorization=root,
            body={"submission_id": first["submission_id"], "evidence": "read"},
        )[0]
        == 200
    )
    submit(leo, {"kind": "workflow", "change": "patch", "manifest": manifest()})  # pending
    rejected = submit(
        leo, {"kind": "workflow", "change": "minor", "manifest": manifest("other-check")}
    )
    assert (
        request(
            url + "admin/submissions/reject",
            authorization=root,
            body={"submission_id": rejected["submission_id"], "reason": "not yet"},
        )[0]
        == 200
    )
    withdrawn = submit(
        leo, {"kind": "workflow", "change": "minor", "manifest": manifest("third-check")}
    )
    assert (
        request(
            url + "assets/submissions/withdraw",
            authorization=leo,
            body={"submission_id": withdrawn["submission_id"]},
        )[0]
        == 200
    )

    # Published by the platform itself (preview seed): one of every other kind,
    # all private to a person nobody here is, and two Knowledge versions.
    registry = app.state.packages
    for name, kind, version in (
        ("handbook", "knowledge", "1.0.0"),
        ("handbook", "knowledge", "1.1.0"),
        ("summarize", "skill", "1.0.0"),
        ("reviewer", "agent", "1.0.0"),
        ("lab-probe", "bridge_extension", "1.0.0"),
    ):
        identity = identity_of(name, version)
        registry.publish(package(identity, kind=kind), artifact=artifact_for(identity))  # type: ignore[call-arg]
    app.state.applications.register(application(visibility="private"))

    status, token = enroll(app, leo, enrollment("leo"))
    assert status == 200, token
    assert bridge(app, "probe", token)[0] == 200
    asset = {**WEEKLY, "version": first["identity"]["version"]}
    status, selected = request(
        url + "select", authorization=leo, body={"bridge_id": "bridge-leo-pc", "asset": asset}
    )
    assert status == 200, selected
    assert (
        request(
            url + "assets/access/update",
            authorization=leo,
            body={**WEEKLY, "visibility": "organization", "members": ["leo.chi"], "groups": []},
        )[0]
        == 200
    )

    invitation = app.issue_invitation(
        Invitation(invitation_id="invite-newbie", actor="newbie", issued_by="platform-admin"),
        expires_at=NOW + timedelta(days=1),
    )
    return {
        "url": url,
        "root": root,
        "leo": leo,
        "chi": chi,
        "visitor": visitor,
        "token": token,
        "invitation": invitation.bearer,
        "version": asset["version"],
    }


def _keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {key for item in value.values() for key in _keys(item)}
    if isinstance(value, list):
        return {key for item in value for key in _keys(item)}
    return set()


def test_an_administrator_sees_everything_and_a_member_is_refused(tmp_path: Path) -> None:
    moment = [NOW]
    with _app(tmp_path, moment) as app:
        seeded = _seed(app)
        url = seeded["url"]
        for session in (seeded["leo"], seeded["chi"]):
            assert request(url + "admin/overview", authorization=session, body={}) == (
                403,
                {"code": "not_administrator"},
            )
        assert request(url + "admin/overview", body={})[0] == 401
        assert (
            request(url + "admin/overview", authorization=seeded["root"], body={"scope": "all"})[0]
            == 400
        )

        status, reply = request(url + "admin/overview", authorization=seeded["root"], body={})
        assert status == 200, reply
        counts = reply["counts"]
        assert {item["kind"]: (item["names"], item["versions"]) for item in counts["assets"]} == {
            "skill": (1, 1),
            "workflow": (1, 1),
            "knowledge": (1, 2),
            "agent": (1, 1),
            "bridge_extension": (1, 1),
        }
        assert (counts["bridges_active"], counts["bridges_disabled"]) == (1, 0)
        assert (counts["members_active"], counts["invitations_pending"]) == (4, 1)
        assert (counts["applications"], counts["application_versions"]) == (1, 1)
        assert [
            counts[f"submissions_{s}"] for s in ("pending", "approved", "rejected", "withdrawn")
        ] == [1, 1, 1, 1]

        assets = {(a["kind"], a["name"]): a for a in reply["assets"]}
        weekly = assets[("workflow", "weekly-check")]
        assert weekly["owner"] == {"type": "team", "id": "engineering"}
        assert weekly["latest_version"] == seeded["version"]
        assert weekly["declared_visibility"] == "team"
        assert weekly["visibility"] == "organization"  # the access override applies
        assert weekly["access"]["members"] == ["leo.chi"]
        assert weekly["bridges_selected"] == 1 and weekly["pending_submissions"] == 1
        assert weekly["published_at"] is not None
        handbook = assets[("knowledge", "handbook")]
        # Private to a person who is not a member: an administrator still sees it.
        assert handbook["versions"] == ["1.0.0", "1.1.0"]
        assert handbook["latest_version"] == "1.1.0" and handbook["published_at"] is None
        assert ("bridge_extension", "lab-probe") in assets and ("agent", "reviewer") in assets
        assert [a["identity"]["name"] for a in reply["applications"]] == ["report-portal"]
        assert {s["status"] for s in reply["submissions"]} == {
            "pending",
            "approved",
            "rejected",
            "withdrawn",
        }

        [pc] = reply["bridges"]
        assert pc["bridge_id"] == "bridge-leo-pc" and pc["members"] == ["leo"]
        assert pc["last_seen_operation"] == "probe" and pc["selections"] == 1
        assert pc["last_seen_at"].startswith("2026-10-07T12:00:00")
        members = {m["actor"]: m for m in reply["members"]}
        assert members["leo"]["bridges"] == ["bridge-leo-pc"]
        assert members["leo"]["groups"] == ["engineering"]
        assert members["root"]["role"] == "platform_admin"
        assert members["newbie"]["invitation"] == "pending"
        assert members["newbie"]["status"] is None
        assert members["newbie"]["invitation_expires_at"] is not None

        # No secret leaves in the reply: no token, fingerprint, proof or session.
        text = json.dumps(reply)
        fingerprints = [
            grant.fingerprint for grant in app.state.tokens.history_for("bridge-leo-pc")
        ]
        for secret in (
            seeded["token"]["secret"],
            seeded["invitation"].split(":")[1],
            seeded["root"].split(":")[1],
            *fingerprints,
        ):
            assert secret not in text
        assert not _keys(reply) & {"secret", "fingerprint", "proof", "session", "login"}

        # Later, the invitation expired and the Bridge called again.
        moment[0] = NOW + timedelta(days=2)
        root = _member(app, "root2", "platform_admin")
        assert bridge(app, "catalog", seeded["token"])[0] == 200
        status, later = request(url + "admin/overview", authorization=root, body={})
        assert status == 200
        assert {m["actor"]: m for m in later["members"]}["newbie"]["invitation"] == "expired"
        assert later["bridges"][0]["last_seen_operation"] == "catalog"
        status, listed = request(url + "admin/bridges/list", authorization=root, body={})
        assert status == 200 and listed["bridges"][0]["last_seen_operation"] == "catalog"


def test_an_administrator_sets_a_members_role_and_groups(tmp_path: Path) -> None:
    with _app(tmp_path, [NOW]) as app:
        seeded = _seed(app)
        url, root, chi = seeded["url"], seeded["root"], seeded["chi"]
        update = url + "admin/members/update"
        body = {"actor": "leo.chi", "role": "member", "groups": ["engineering"]}
        assert request(update, authorization=seeded["leo"], body=body) == (
            403,
            {"code": "not_administrator"},
        )
        # leo.chi is in no team yet, so the team's name is not theirs to manage.
        add = {**WEEKLY, "co_editor": "visitor"}
        assert request(url + "assets/co-editors/add", authorization=chi, body=add) == (
            403,
            {"code": "not_name_owner"},
        )

        status, reply = request(update, authorization=root, body=body)
        assert status == 200, reply
        assert reply["member"]["groups"] == ["engineering"]
        assert reply["member"]["last_changed_by"] == "root"
        status, changed = request(url + "assets/co-editors/add", authorization=chi, body=add)
        assert status == 200 and changed["ownership"]["co_editors"] == ["visitor"]
        [change] = app.state.enrollment.user_changes("leo.chi")
        assert (change.changed_by, change.groups_before, change.groups_after) == (
            "root",
            (),
            ("engineering",),
        )

        status, bad = request(update, authorization=root, body={**body, "groups": ["qa team"]})
        assert (status, bad["reason"]) == (400, "group_invalid")
        assert request(update, authorization=root, body={**body, "actor": "nobody"})[0] == 403
        # The last platform administrator keeps the role.
        demote = {"actor": "root", "role": "member", "groups": []}
        assert request(update, authorization=root, body=demote) == (
            409,
            {"code": "last_administrator"},
        )
        assert (
            request(
                update,
                authorization=root,
                body={"actor": "leo.chi", "role": "platform_admin", "groups": ["engineering"]},
            )[0]
            == 200
        )
        assert request(update, authorization=root, body=demote)[0] == 200
        assert request(url + "admin/overview", authorization=root, body={}) == (
            403,
            {"code": "not_administrator"},
        )
        assert request(url + "admin/overview", authorization=chi, body={})[0] == 200


def test_co_editors_and_owner_transfer_over_the_portal(tmp_path: Path) -> None:
    with _app(tmp_path, [NOW]) as app:
        seeded = _seed(app)
        url, leo, visitor = seeded["url"], seeded["leo"], seeded["visitor"]

        def call(route: str, session: str, **body: Any) -> tuple[int, dict[str, Any]]:
            return request(url + route, authorization=session, body={**WEEKLY, **body})

        assert call("assets/co-editors/add", leo, co_editor="nobody") == (
            400,
            {"code": "co_editor_unknown"},
        )
        status, added = call("assets/co-editors/add", leo, co_editor="visitor")
        assert status == 200 and added["ownership"]["co_editors"] == ["visitor"]
        assert call("assets/co-editors/add", leo, co_editor="visitor") == (
            409,
            {"code": "co_editor_exists"},
        )
        # A co-editor publishes, but does not manage the name.
        assert call("assets/co-editors/add", visitor, co_editor="leo.chi") == (
            403,
            {"code": "not_name_owner"},
        )
        status, mine = request(url + "assets/access", authorization=leo, body={})
        assert status == 200 and mine["entries"][0]["co_editors"] == ["visitor"]
        assert call("assets/co-editors/remove", leo, co_editor="visitor")[0] == 200
        assert call("assets/co-editors/remove", leo, co_editor="visitor") == (
            404,
            {"code": "co_editor_missing"},
        )

        assert call("assets/transfer", leo, owner={"type": "user", "id": "nobody"}) == (
            400,
            {"code": "new_owner_unknown"},
        )
        assert call("assets/transfer", leo, owner={"type": "team", "id": "engineering"}) == (
            409,
            {"code": "owner_unchanged"},
        )
        status, moved = call("assets/transfer", leo, owner={"type": "team", "id": "qa"})
        assert status == 200 and moved["ownership"]["owner"] == {"type": "team", "id": "qa"}
        assert call("assets/co-editors/add", leo, co_editor="visitor") == (
            403,
            {"code": "not_name_owner"},
        )
        status, reply = request(url + "admin/overview", authorization=seeded["root"], body={})
        weekly = next(a for a in reply["assets"] if a["name"] == "weekly-check")
        assert status == 200 and weekly["owner"] == {"type": "team", "id": "qa"}
        # A platform administrator in no team manages any name's sharing
        # (owner 2026-10-15), but publishing stays with owner and co-editors.
        root = seeded["root"]
        status, added = call("assets/co-editors/add", root, co_editor="visitor")
        assert status == 200 and added["ownership"]["co_editors"] == ["visitor"]
        status, back = call("assets/transfer", root, owner={"type": "team", "id": "engineering"})
        assert status == 200 and back["ownership"]["owner"]["id"] == "engineering"
        record = app.state.packages.ownership("lab", "weekly-check")
        assert record is not None and not record.may_publish("root", ())


def test_the_enrollment_registry_audits_changes_and_keeps_the_last_administrator() -> None:
    registry = InMemoryEnrollmentRegistry(administrators=("platform-admin",))
    for actor, role in (("root", "platform_admin"), ("leo", "member")):
        registry.issue(
            Invitation(
                invitation_id=f"invite-{actor}", actor=actor, issued_by="platform-admin", role=role
            )
        )  # type: ignore[arg-type]
        registry.accept(f"invite-{actor}", actor)
    with pytest.raises(EnrollmentError) as refused:
        registry.update_user("leo", "leo", role="platform_admin", groups=())
    assert refused.value.code == "not_administrator"
    with pytest.raises(EnrollmentError) as refused:
        registry.update_user("root", "root", role="member", groups=())
    assert refused.value.code == "last_administrator"
    with pytest.raises(EnrollmentError) as refused:
        registry.update_user("root", "ghost", role="member", groups=())
    assert refused.value.code == "user_missing"
    updated = registry.update_user(
        "root", "leo", role="member", groups=("qa", "qa", "lab"), now=NOW
    )
    assert updated.groups == ("qa", "lab") and registry.user("leo").groups == ("qa", "lab")
    assert [item.actor for item in registry.users()] == ["leo", "root"]
    [change] = registry.user_changes()
    assert change.changed_at == NOW and change.role_before == change.role_after == "member"


def test_the_last_call_of_a_bridge_is_kept_and_written_at_most_once_a_minute(
    tmp_path: Path,
) -> None:
    storage = SqliteIdentityStorage(tmp_path / "registry.sqlite")
    activity = BridgeActivity(storage=storage)
    assert activity.last("bridge-a") is None
    activity.seen("bridge-a", "probe", NOW)
    activity.seen("bridge-a", "poll", NOW + timedelta(seconds=20))
    activity.seen("bridge-a", "report", NOW + timedelta(seconds=10))  # older: ignored
    current = activity.last("bridge-a")
    assert current is not None and (current.operation, current.at) == (
        "poll",
        NOW + timedelta(seconds=20),
    )
    restored = BridgeActivity(storage=storage).last("bridge-a")
    assert restored is not None and restored.operation == "probe"  # throttled write
    activity.seen("bridge-a", "sync", NOW + PERSIST_EVERY)
    restored = BridgeActivity(storage=storage).last("bridge-a")
    assert restored is not None and restored.operation == "sync"


def test_a_member_reads_the_content_of_an_asset_shared_with_them(tmp_path: Path) -> None:
    import hashlib

    from common.distribution import PublishedAssetPackage

    with _app(tmp_path, [NOW]) as app:
        seeded = _seed(app)
        url = seeded["url"] + "assets/manifest"
        weekly = {**WEEKLY, "version": seeded["version"]}
        status, reply = request(url, authorization=seeded["visitor"], body={"asset": weekly})
        assert status == 200, reply
        assert reply["schema_version"] == "1"
        assert reply["manifest"]["kind"] == "workflow" and reply["manifest"]["steps"]
        assert reply["manifest"]["metadata"]["identity"] == weekly
        assert reply["package"]["metadata"]["identity"] == weekly
        assert reply["artifact_sha256"] == reply["package"]["metadata"]["package"]["sha256"]
        assert reply["owner"] == {"type": "team", "id": "engineering"}
        assert reply["visibility"] == "organization" and reply["versions"] == [weekly["version"]]
        assert reply["published_at"] is not None and reply["deprecation"] is None

        # Private to a person who is not a member: refused as if it did not
        # exist, except for an administrator.
        handbook = {"namespace": "lab", "name": "handbook", "version": "1.1.0"}
        assert request(url, authorization=seeded["visitor"], body={"asset": handbook}) == (
            404,
            {"code": "asset_not_published"},
        )
        status, admin = request(url, authorization=seeded["root"], body={"asset": handbook})
        assert status == 200 and admin["versions"] == ["1.0.0", "1.1.0"]
        assert admin["manifest"] == {"identity": handbook}
        assert request(
            url, authorization=seeded["root"], body={"asset": {**handbook, "version": "9.9.9"}}
        ) == (404, {"code": "asset_not_published"})
        assert request(url, body={"asset": handbook})[0] == 401
        assert request(url, authorization=seeded["root"], body={})[0] == 400

        # Larger than the portal returns.
        big = AssetIdentity(namespace="lab", name="huge", version="1.0.0")
        content = json.dumps({"text": "a" * (600 * 1024)}).encode("utf-8")
        data = package(big, kind="knowledge").model_dump(mode="json")
        data["metadata"]["package"]["sha256"] = hashlib.sha256(content).hexdigest()
        app.state.packages.publish(  # type: ignore[call-arg]
            PublishedAssetPackage.model_validate(data), artifact=content
        )
        assert request(url, authorization=seeded["root"], body={"asset": big.model_dump()}) == (
            413,
            {"code": "artifact_too_large"},
        )
