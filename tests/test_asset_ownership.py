"""Who owns a Skill or Workflow name, who publishes its versions, and which
version a member uses.

Requirements: `docs/phases/ASSET_OWNERSHIP.md` step 2, owner decisions of
2026-10-07. Every rule is checked against both Registry implementations.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError
from test_member_authorization import REPORT, platform, selection
from test_member_portal import post

from common.assets import AssetIdentity, AssetMetadata, Owner, PackageMetadata
from common.distribution import PublishedAssetPackage
from common.enrollment import Invitation
from common.identity import AuthenticatedActor
from common.ownership import (
    AssetNameOwnership,
    VersionDeprecation,
    above_all,
    highest_version,
    next_version,
)
from control_plane.authorization import AuthorizationError
from control_plane.distribution import ControlError, InMemoryPackageRegistry, PackageRegistry
from control_plane.enrollment import InMemoryEnrollmentRegistry
from control_plane.member import InMemoryMemberSessions, MemberService
from control_plane.member_http import MemberPortalServer
from control_plane.ownership import AssetOwnershipService, OwnershipError
from control_plane.registry_sqlite import SqliteRegistry

NOW = datetime(2026, 10, 7, 12, 0, tzinfo=UTC)
ALICE = Owner(type="user", id="alice")
CAROL = Owner(type="user", id="carol")
TEAM = Owner(type="team", id="quality")
ENGINEERING = Owner(type="team", id="engineering")


def identity_of(name: str, version: str = "1.0.0") -> AssetIdentity:
    return AssetIdentity(namespace="lab", name=name, version=version)


def artifact_for(identity: AssetIdentity) -> bytes:
    return json.dumps({"identity": identity.model_dump()}).encode("utf-8")


def package(
    identity: AssetIdentity,
    owner: Owner = ALICE,
    *,
    kind: str = "workflow",
    visibility: str = "private",
) -> PublishedAssetPackage:
    return PublishedAssetPackage.model_validate(
        {
            "kind": kind,
            "metadata": AssetMetadata(
                identity=identity,
                owner=owner,
                visibility=visibility,  # type: ignore[arg-type]
                lifecycle="published",
                package=PackageMetadata(
                    artifact_ref=(
                        f"registry://{identity.namespace}/{identity.name}/{identity.version}"
                    ),
                    sha256=hashlib.sha256(artifact_for(identity)).hexdigest(),
                ),
            ).model_dump(),
        }
    )


def enrollment() -> InMemoryEnrollmentRegistry:
    """alice and bob are in team `quality`; carol and dave are in no team."""
    registry = InMemoryEnrollmentRegistry(administrators=("platform-admin",))
    members: tuple[tuple[str, tuple[str, ...]], ...] = (
        ("alice", ("quality",)), ("bob", ("quality",)), ("carol", ()), ("dave", ())
    )
    for actor, groups in members:
        registry.issue(
            Invitation(
                invitation_id=f"invite-{actor}",
                actor=actor,
                issued_by="platform-admin",
                groups=groups,
            )
        )
        registry.accept(f"invite-{actor}", actor)
    return registry


def who(actor: str) -> AuthenticatedActor:
    return AuthenticatedActor(
        actor=actor,
        method="invitation-proof",
        authenticated_at=NOW - timedelta(minutes=1),
        expires_at=NOW + timedelta(hours=1),
    )


RegistryFactory = Callable[[Path], PackageRegistry]
REGISTRIES: dict[str, RegistryFactory] = {
    "memory": lambda path: InMemoryPackageRegistry(),
    "sqlite": lambda path: SqliteRegistry(path / "registry.sqlite"),
}


@pytest.fixture(params=sorted(REGISTRIES))
def registry(request: pytest.FixtureRequest, tmp_path: Path) -> PackageRegistry:
    return REGISTRIES[request.param](tmp_path)


def service_over(registry: PackageRegistry) -> AssetOwnershipService:
    return AssetOwnershipService(enrollment(), registry, artifacts={})


def publish(
    service: AssetOwnershipService,
    actor: str,
    identity: AssetIdentity,
    owner: Owner = ALICE,
    **options: Any,
) -> PublishedAssetPackage:
    return service.publish(
        who(actor), package(identity, owner), artifact=artifact_for(identity), now=NOW, **options
    )


# -- versions ---------------------------------------------------------------


def test_versions_follow_semantic_precedence() -> None:
    assert highest_version(["1.2.0", "1.10.0", "1.9.9"]) == "1.10.0"
    assert highest_version(["2.0.0-rc.1", "1.9.0"]) == "2.0.0-rc.1"
    assert highest_version(["2.0.0-rc.1", "2.0.0"]) == "2.0.0"
    assert highest_version(["1.0.0-alpha.2", "1.0.0-alpha.10"]) == "1.0.0-alpha.10"
    assert highest_version([]) is None
    assert next_version([], "major") == "1.0.0"
    assert next_version([], "patch") == "1.0.0"
    assert next_version(["1.2.3", "1.0.0"], "patch") == "1.2.4"
    assert next_version(["1.2.3"], "minor") == "1.3.0"
    assert next_version(["1.2.3"], "major") == "2.0.0"
    assert next_version(["2.0.0-rc.1"], "patch") == "2.0.1"
    assert above_all("1.2.4", ["1.2.3", "1.0.0"])
    assert not above_all("1.2.3", ["1.2.3"])
    assert not above_all("1.0.0", ["1.2.3"])
    # Build metadata carries no precedence, so it cannot make a version higher.
    assert not above_all("1.2.3+build.7", ["1.2.3"])
    assert above_all("1.0.0", [])


def test_an_ownership_record_is_coherent() -> None:
    record = AssetNameOwnership(namespace="lab", name="report", owner=ALICE, co_editors=("bob",))
    assert record.may_publish("bob", ()) and not record.manages("bob", ())
    assert record.manages("alice", ()) and not record.may_publish("carol", ())
    team = AssetNameOwnership(namespace="lab", name="report", owner=TEAM)
    assert team.manages("bob", ("quality",)) and not team.manages("quality", ())
    with pytest.raises(ValidationError, match="co-editors must be unique"):
        AssetNameOwnership(namespace="lab", name="r", owner=ALICE, co_editors=("bob", "bob"))
    with pytest.raises(ValidationError, match="owner is not also a co-editor"):
        AssetNameOwnership(namespace="lab", name="r", owner=ALICE, co_editors=("alice",))
    deprecated = VersionDeprecation(version="1.0.0", reason="wrong totals", deprecated_by="alice")
    with pytest.raises(ValidationError, match="deprecated once"):
        AssetNameOwnership(
            namespace="lab", name="r", owner=ALICE, deprecations=(deprecated, deprecated)
        )
    with pytest.raises(ValidationError, match="cannot replace itself"):
        VersionDeprecation(
            version="1.0.0", reason="x", replacement="1.0.0+b", deprecated_by="alice"
        )
    with pytest.raises(ValidationError):
        VersionDeprecation(version="latest", reason="x", deprecated_by="alice")


# -- the publish check ------------------------------------------------------


def test_the_first_publisher_owns_the_name(registry: PackageRegistry) -> None:
    service = service_over(registry)
    publish(service, "alice", identity_of("report"))

    record = registry.ownership("lab", "report")
    assert record == AssetNameOwnership(namespace="lab", name="report", owner=ALICE)
    # A first publish must declare its own publisher (or their team) as owner.
    with pytest.raises(OwnershipError, match="publisher_not_authorized"):
        publish(service, "carol", identity_of("other"), owner=ALICE)
    assert registry.ownership("lab", "other") is None
    publish(service, "bob", identity_of("team-report"), owner=TEAM)
    assert registry.ownership("lab", "team-report") == AssetNameOwnership(
        namespace="lab", name="team-report", owner=TEAM
    )


def test_only_the_owner_a_team_member_or_a_co_editor_publishes_a_new_version(
    registry: PackageRegistry,
) -> None:
    service = service_over(registry)
    publish(service, "alice", identity_of("report"))
    publish(service, "bob", identity_of("team-report"), owner=TEAM)

    # Somebody else cannot publish under alice's name, even declaring her owner.
    with pytest.raises(OwnershipError, match="publisher_not_authorized"):
        publish(service, "carol", identity_of("report", "1.1.0"))
    with pytest.raises(OwnershipError, match="publisher_not_authorized"):
        publish(service, "carol", identity_of("report", "1.1.0"), owner=CAROL)
    # Any member of the owning team may.
    publish(service, "alice", identity_of("team-report", "1.1.0"), owner=TEAM)
    # A co-editor publishes directly once the owner names them.
    service.add_co_editor(who("alice"), "lab", "report", "carol", now=NOW)
    publish(service, "carol", identity_of("report", "1.1.0"))
    # Every version keeps declaring the name's owner.
    with pytest.raises(OwnershipError, match="owner_mismatch"):
        publish(service, "carol", identity_of("report", "1.2.0"), owner=CAROL)
    # The owner removes the co-editor, and their next publish is refused.
    service.remove_co_editor(who("alice"), "lab", "report", "carol", now=NOW)
    with pytest.raises(OwnershipError, match="publisher_not_authorized"):
        publish(service, "carol", identity_of("report", "1.2.0"))
    assert [item.metadata.identity.version for item in registry.discover()] == [
        "1.0.0", "1.1.0", "1.0.0", "1.1.0"
    ]


def test_a_supplied_version_must_be_above_every_existing_one(registry: PackageRegistry) -> None:
    service = service_over(registry)
    publish(service, "alice", identity_of("report", "1.2.0"))

    for version in ("1.2.0", "1.1.9", "1.2.0+rebuild", "1.2.0-rc.1"):
        with pytest.raises(OwnershipError, match="version_not_above_highest|duplicate_package"):
            publish(service, "alice", identity_of("report", version))
    publish(service, "alice", identity_of("report", "1.3.0-rc.1"))
    publish(service, "alice", identity_of("report", "1.3.0"))
    assert registry.get(identity_of("report", "1.1.9")) is None


def test_the_platform_assigns_the_next_version_for_a_change_level(
    registry: PackageRegistry,
) -> None:
    service = service_over(registry)
    assert service.next_version(who("alice"), "lab", "report", "minor", now=NOW) == "1.0.0"
    publish(service, "alice", identity_of("report"), change="major")
    assert service.next_version(who("alice"), "lab", "report", "minor", now=NOW) == "1.1.0"
    # A change level with a version other than the assigned one is refused.
    with pytest.raises(OwnershipError, match="version_not_assigned"):
        publish(service, "alice", identity_of("report", "1.5.0"), change="minor")
    with pytest.raises(OwnershipError, match="publisher_not_authorized"):
        service.next_version(who("carol"), "lab", "report", "patch", now=NOW)

    built: list[AssetIdentity] = []

    def build(assigned: AssetIdentity) -> tuple[PublishedAssetPackage, bytes]:
        built.append(assigned)
        return package(assigned), artifact_for(assigned)

    saved = service.publish_next(who("alice"), "lab", "report", "patch", build, now=NOW)
    assert saved.metadata.identity == identity_of("report", "1.0.1")
    saved = service.publish_next(who("alice"), "lab", "report", "major", build, now=NOW)
    assert saved.metadata.identity == identity_of("report", "2.0.0")
    assert built == [identity_of("report", "1.0.1"), identity_of("report", "2.0.0")]


def test_an_automatic_publish_that_loses_a_race_is_assigned_the_next_version(
    registry: PackageRegistry,
) -> None:
    service = service_over(registry)
    publish(service, "alice", identity_of("report"))
    raced = False

    def build(assigned: AssetIdentity) -> tuple[PublishedAssetPackage, bytes]:
        nonlocal raced
        if not raced:
            # Another publisher takes the assigned version first.
            raced = True
            registry.publish(package(assigned))
        return package(assigned), artifact_for(assigned)

    saved = service.publish_next(who("alice"), "lab", "report", "patch", build, now=NOW)
    assert saved.metadata.identity.version == "1.0.2"


def test_the_platform_publish_keeps_the_name_with_its_owner(registry: PackageRegistry) -> None:
    registry.publish(package(identity_of("report")))
    assert registry.ownership("lab", "report") == AssetNameOwnership(
        namespace="lab", name="report", owner=ALICE
    )
    with pytest.raises(ControlError, match="owner_mismatch"):
        registry.publish(package(identity_of("report", "2.0.0"), Owner(type="user", id="carol")))
    with pytest.raises(ControlError, match="duplicate_package"):
        registry.publish(package(identity_of("report")))
    # The platform's own publish imports history as it was, in any order.
    registry.publish(package(identity_of("report", "2.0.0")))
    registry.publish(package(identity_of("report", "0.9.0")))


def test_a_concurrent_owner_change_is_refused_rather_than_lost(registry: PackageRegistry) -> None:
    registry.publish(package(identity_of("report")))
    before = registry.ownership("lab", "report")
    assert before is not None
    first = before.model_copy(update={"co_editors": ("bob",)})
    registry.save_ownership(first, previous=before)
    with pytest.raises(ControlError, match="ownership_changed"):
        registry.save_ownership(
            before.model_copy(update={"co_editors": ("carol",)}), previous=before
        )
    missing = AssetNameOwnership(namespace="lab", name="absent", owner=ALICE)
    with pytest.raises(ControlError, match="name_missing"):
        registry.save_ownership(missing, previous=missing)
    assert registry.ownership("lab", "report") == first


# -- the owner's management -------------------------------------------------


def test_only_the_owner_manages_a_name(registry: PackageRegistry) -> None:
    service = service_over(registry)
    publish(service, "alice", identity_of("report"))
    service.add_co_editor(who("alice"), "lab", "report", "bob", now=NOW)

    # A co-editor publishes but does not manage.
    with pytest.raises(OwnershipError, match="not_name_owner"):
        service.add_co_editor(who("bob"), "lab", "report", "carol", now=NOW)
    with pytest.raises(OwnershipError, match="not_name_owner"):
        service.deprecate(who("bob"), "lab", "report", "1.0.0", "bad", now=NOW)
    with pytest.raises(OwnershipError, match="not_name_owner"):
        service.transfer(who("bob"), "lab", "report", Owner(type="user", id="bob"), now=NOW)
    # Somebody the name is not shared with cannot even tell it exists.
    with pytest.raises(OwnershipError, match="name_missing"):
        service.ownership(who("carol"), "lab", "report", now=NOW)
    with pytest.raises(OwnershipError, match="co_editor_exists"):
        service.add_co_editor(who("alice"), "lab", "report", "bob", now=NOW)
    with pytest.raises(OwnershipError, match="co_editor_exists"):
        service.add_co_editor(who("alice"), "lab", "report", "alice", now=NOW)
    with pytest.raises(OwnershipError, match="co_editor_unknown"):
        service.add_co_editor(who("alice"), "lab", "report", "nobody", now=NOW)
    with pytest.raises(OwnershipError, match="co_editor_missing"):
        service.remove_co_editor(who("alice"), "lab", "report", "carol", now=NOW)
    record, versions = service.ownership(who("bob"), "lab", "report", now=NOW)
    assert record.co_editors == ("bob",) and versions == ("1.0.0",)


def test_ownership_transfers_to_a_person_or_a_team(registry: PackageRegistry) -> None:
    service = service_over(registry)
    publish(service, "alice", identity_of("report"))
    service.add_co_editor(who("alice"), "lab", "report", "dave", now=NOW)

    with pytest.raises(OwnershipError, match="owner_unchanged"):
        service.transfer(who("alice"), "lab", "report", ALICE, now=NOW)
    with pytest.raises(OwnershipError, match="new_owner_unknown"):
        service.transfer(who("alice"), "lab", "report", Owner(type="user", id="nobody"), now=NOW)
    record = service.transfer(who("alice"), "lab", "report", Owner(type="user", id="dave"), now=NOW)
    # A co-editor who becomes owner is no longer listed as a co-editor.
    assert record.owner == Owner(type="user", id="dave") and record.co_editors == ()
    with pytest.raises(OwnershipError, match="name_missing|not_name_owner"):
        service.add_co_editor(who("alice"), "lab", "report", "carol", now=NOW)
    # The new owner's versions declare the new owner; the old version is unchanged.
    dave = Owner(type="user", id="dave")
    publish(service, "dave", identity_of("report", "1.1.0"), owner=dave)
    old = registry.get(identity_of("report"))
    assert old is not None and old.metadata.owner == ALICE

    service.transfer(who("dave"), "lab", "report", TEAM, now=NOW)
    service.add_co_editor(who("bob"), "lab", "report", "carol", now=NOW)
    publish(service, "carol", identity_of("report", "1.2.0"), owner=TEAM)


def test_deprecating_a_version_stops_new_choices_but_keeps_existing_ones() -> None:
    enrollment_, packages, authorization = platform()
    owners = AssetOwnershipService(enrollment_, packages)
    newer = REPORT.model_copy(update={"version": "1.1.0"})
    team = Owner(type="team", id="engineering")
    packages.publish(package(newer, team, visibility="organization"))
    selected = authorization.select(who_engineer(), selection(), now=NOW)

    with pytest.raises(OwnershipError, match="not_name_owner"):
        owners.deprecate(who_engineer(), REPORT.namespace, REPORT.name, "1.0.0", "x", now=NOW)
    enrollment_.issue(
        Invitation(
            invitation_id="invite-lead",
            actor="lead",
            issued_by="platform-admin",
            groups=("engineering",),
        )
    )
    enrollment_.accept("invite-lead", "lead")
    with pytest.raises(OwnershipError, match="version_missing"):
        owners.deprecate(who("lead"), REPORT.namespace, REPORT.name, "9.0.0", "x", now=NOW)
    with pytest.raises(OwnershipError, match="version_missing"):
        owners.deprecate(
            who("lead"), REPORT.namespace, REPORT.name, "1.0.0", "x", replacement="9.0.0", now=NOW
        )
    record = owners.deprecate(
        who("lead"), REPORT.namespace, REPORT.name, "1.1.0", "wrong totals",
        replacement="1.0.0", now=NOW,
    )
    deprecation = record.deprecation("1.1.0")
    assert deprecation is not None and deprecation.deprecated_by == "lead"
    with pytest.raises(OwnershipError, match="version_deprecated"):
        owners.deprecate(who("lead"), REPORT.namespace, REPORT.name, "1.1.0", "again", now=NOW)

    # The package itself is unchanged, and the version is no longer offered.
    stored = packages.get(newer)
    assert stored is not None and stored.metadata.lifecycle == "published"
    offered = {item.metadata.identity for item in authorization.available(who_engineer(), now=NOW)}
    assert REPORT in offered and newer not in offered
    with pytest.raises(AuthorizationError, match="asset_deprecated"):
        authorization.select(who_engineer(), selection(asset=newer.model_dump()), now=NOW)
    with pytest.raises(AuthorizationError, match="asset_deprecated"):
        authorization.replace(who_engineer(), "bridge-company", REPORT, newer, now=NOW)
    # What was already chosen stays chosen.
    current = authorization.authorization("bridge-company", issued_at=NOW).for_actor("engineer")
    assert selected in current


# -- one active version per person -----------------------------------------


def who_engineer() -> AuthenticatedActor:
    return AuthenticatedActor(
        actor="engineer",
        method="invitation-proof",
        authenticated_at=NOW - timedelta(minutes=1),
        expires_at=NOW + timedelta(hours=1),
    )


def test_choosing_a_version_replaces_the_version_already_chosen() -> None:
    _, packages, authorization = platform()
    newer = REPORT.model_copy(update={"version": "1.1.0"})
    packages.publish(package(newer, ENGINEERING, visibility="organization"))

    first = authorization.select(who_engineer(), selection(), now=NOW)
    second = authorization.select(who_engineer(), selection(asset=newer.model_dump()), now=NOW)

    chosen = authorization.authorization("bridge-company", issued_at=NOW).for_actor("engineer")
    reports = [item for item in chosen if item.asset.name == REPORT.name]
    assert reports == [second]
    assert first.status == "active"  # the returned record is the one made then
    # Choosing the older version again replaces the newer one: rollback.
    authorization.select(who_engineer(), selection(), now=NOW)
    chosen = authorization.authorization("bridge-company", issued_at=NOW).for_actor("engineer")
    assert [item.asset for item in chosen if item.asset.name == REPORT.name] == [REPORT]
    with pytest.raises(AuthorizationError, match="duplicate_selection"):
        authorization.select(who_engineer(), selection(), now=NOW)


def test_one_active_version_is_per_member_and_per_device() -> None:
    _, packages, authorization = platform()
    newer = REPORT.model_copy(update={"version": "1.1.0"})
    packages.publish(package(newer, ENGINEERING, visibility="organization"))
    shared_bot = who_engineer().model_copy(update={"actor": "shared-bot"})

    on_shared = authorization.select(
        shared_bot, selection(bridge_id="bridge-shared", actor="shared-bot"), now=NOW
    )
    on_company = authorization.select(who_engineer(), selection(asset=newer.model_dump()), now=NOW)

    assert authorization.authorization("bridge-shared", issued_at=NOW).selections == (on_shared,)
    assert authorization.authorization("bridge-company", issued_at=NOW).selections == (on_company,)


# -- the schema migration ---------------------------------------------------


def legacy_registry(path: Path, rows: list[PublishedAssetPackage]) -> None:
    """A Registry database as the previous code wrote it: no ownership table."""
    with sqlite3.connect(path) as connection:
        connection.execute(
            "CREATE TABLE registry_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )
        connection.execute("INSERT INTO registry_meta VALUES ('schema_version', '1')")
        connection.execute(
            "CREATE TABLE packages (namespace TEXT NOT NULL, name TEXT NOT NULL, "
            "version TEXT NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(namespace, name, version))"
        )
        connection.execute(
            "CREATE TABLE artifacts (reference TEXT PRIMARY KEY, content BLOB NOT NULL)"
        )
        for item in rows:
            connection.execute(
                "INSERT INTO packages VALUES (?, ?, ?, ?)",
                (*item.metadata.identity.key, item.model_dump_json()),
            )


def test_an_existing_registry_gains_owners_from_each_names_earliest_version(
    tmp_path: Path,
) -> None:
    path = tmp_path / "registry.sqlite"
    carol = Owner(type="user", id="carol")
    # Inserted newest first: the earliest version decides, not the first row.
    legacy_registry(
        path,
        [
            package(identity_of("report", "1.10.0"), carol),
            package(identity_of("report", "1.2.0"), ALICE),
            package(identity_of("checklist"), TEAM, kind="skill"),
        ],
    )

    registry = SqliteRegistry(path)

    assert registry.ownership("lab", "report") == AssetNameOwnership(
        namespace="lab", name="report", owner=ALICE
    )
    assert registry.ownership("lab", "checklist") == AssetNameOwnership(
        namespace="lab", name="checklist", owner=TEAM
    )
    assert len(registry.discover()) == 3
    # Reopening changes nothing, and the previous code's schema still reads it.
    assert SqliteRegistry(path).ownership("lab", "report") == registry.ownership("lab", "report")
    with sqlite3.connect(path) as connection:
        assert connection.execute(
            "SELECT value FROM registry_meta WHERE key = 'schema_version'"
        ).fetchone() == ("1",)
    service = AssetOwnershipService(enrollment(), registry)
    with pytest.raises(OwnershipError, match="publisher_not_authorized"):
        publish(service, "carol", identity_of("report", "2.0.0"), owner=carol)
    publish(service, "alice", identity_of("report", "2.0.0"))


def test_a_name_published_by_the_previous_code_is_owned_on_its_next_publish(
    tmp_path: Path,
) -> None:
    path = tmp_path / "registry.sqlite"
    registry = SqliteRegistry(path)
    # The previous code, still running somewhere, inserts a row without a record.
    with sqlite3.connect(path) as connection:
        item = package(identity_of("late"))
        connection.execute(
            "INSERT INTO packages VALUES (?, ?, ?, ?)",
            (*item.metadata.identity.key, item.model_dump_json()),
        )
    assert registry.ownership("lab", "late") is None
    service = AssetOwnershipService(enrollment(), registry)
    with pytest.raises(OwnershipError, match="publisher_not_authorized"):
        publish(service, "carol", identity_of("late", "2.0.0"), owner=CAROL)
    # The refused publish wrote nothing; the owner's own publish records her.
    publish(service, "alice", identity_of("late", "2.0.0"))
    assert registry.ownership("lab", "late") == AssetNameOwnership(
        namespace="lab", name="late", owner=ALICE
    )


# -- the member entry point -------------------------------------------------


def test_the_owner_manages_a_name_over_the_member_entry_point() -> None:
    packages = InMemoryPackageRegistry()
    members = enrollment()
    owners = AssetOwnershipService(members, packages, artifacts={})
    publish(owners, "alice", identity_of("report"))
    sessions = InMemoryMemberSessions()
    _, _, authorization = platform()
    service = MemberService(
        enrollment=members,
        authorization=authorization,
        sessions=sessions,
        ownership=owners,
        clock=lambda: NOW,
    )
    alice = sessions.issue(who("alice"), now=NOW, secret="alice-" + "s" * 40)
    carol = sessions.issue(who("carol"), now=NOW, secret="carol-" + "s" * 40)
    name = {"namespace": "lab", "name": "report"}

    with MemberPortalServer(service) as server:
        url = server.base_url + "/v1/member/assets/"
        status, reply = post(url + "co-editors/add", alice.bearer, {**name, "co_editor": "carol"})
        assert status == 200 and reply["ownership"]["co_editors"] == ["carol"]
        assert reply["versions"] == ["1.0.0"]
        status, reply = post(url + "next-version", carol.bearer, {**name, "change": "minor"})
        assert (status, reply["version"]) == (200, "1.1.0")
        status, reply = post(
            url + "deprecate", carol.bearer, {**name, "version": "1.0.0", "reason": "x"}
        )
        assert (status, reply) == (403, {"code": "not_name_owner"})
        status, reply = post(
            url + "deprecate", alice.bearer, {**name, "version": "1.0.0", "reason": "wrong"}
        )
        assert status == 200 and reply["ownership"]["deprecations"][0]["version"] == "1.0.0"
        # A request cannot name who is asking.
        status, reply = post(url + "ownership", carol.bearer, {**name, "actor": "alice"})
        assert (status, reply) == (400, {"code": "invalid_request"})
        status, reply = post(
            url + "transfer", alice.bearer, {**name, "owner": {"type": "user", "id": "carol"}}
        )
        assert status == 200 and reply["ownership"]["owner"] == {"type": "user", "id": "carol"}
        assert reply["ownership"]["co_editors"] == []
        # alice can still read the record, since she may use the version she
        # published, but she no longer manages the name.
        status, reply = post(url + "co-editors/add", alice.bearer, {**name, "co_editor": "bob"})
        assert (status, reply) == (403, {"code": "not_name_owner"})
        status, reply = post(url + "ownership", server_outsider(sessions).bearer, name)
        assert (status, reply) == (404, {"code": "name_missing"})
        status, reply = post(url + "co-editors/remove", carol.bearer, {**name, "co_editor": "bob"})
        assert (status, reply) == (404, {"code": "co_editor_missing"})


def server_outsider(sessions: InMemoryMemberSessions) -> Any:
    """dave, a member with whom the private name is not shared."""
    return sessions.issue(who("dave"), now=NOW, secret="dave-" + "s" * 40)
