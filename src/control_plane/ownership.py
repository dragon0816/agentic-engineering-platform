"""Member operations on Skill and Workflow names: publish a version, and the
owner's management of the name.

Owner decisions of 2026-10-07 (`docs/phases/ASSET_OWNERSHIP.md`). The rules
themselves are in `common.ownership` and are applied by the Registry inside
the transaction that writes, so this service decides only who is asking and
what they may know:

- who the member is comes from a still-valid authentication, and what groups
  they belong to from the platform's own record of them, never from a claim;
- a name a member cannot use or publish is reported as missing, so its owner
  and co-editors are not disclosed to somebody it is not shared with.

Publishing here is not permission to run anything. Members still choose which
version their devices use, and the Bridge policy still authorizes every run.
"""

from __future__ import annotations

from collections.abc import Callable, MutableMapping
from datetime import UTC, datetime
from typing import Literal

from pydantic import TypeAdapter

from common.assets import AssetIdentity, Owner
from common.base import Slug, Symbol
from common.distribution import PublishedAssetPackage
from common.identity import AuthenticatedActor, NameAccess, Visibility
from common.member import AssetAccessEntry
from common.ownership import (
    AssetNameOwnership,
    VersionChange,
    VersionDeprecation,
    next_version,
    version_key,
)
from control_plane.distribution import ControlError, PackageRegistry, entitled_in
from control_plane.enrollment import EnrollmentError, InMemoryEnrollmentRegistry
from control_plane.registry_sqlite import SqliteRegistry

OwnershipErrorCode = Literal[
    "session_expired",
    "actor_unknown",
    "actor_disabled",
    # The publish rules (`control_plane.distribution.admit_member_version`).
    "publisher_not_authorized",
    "owner_mismatch",
    "version_not_assigned",
    "version_not_above_highest",
    "duplicate_package",
    "artifact_missing",
    "artifact_hash_mismatch",
    # The owner's management of a name.
    "name_missing",
    "not_name_owner",
    "ownership_changed",
    "co_editor_unknown",
    "co_editor_exists",
    "co_editor_missing",
    "owner_unchanged",
    "new_owner_unknown",
    "version_missing",
    "version_deprecated",
    # Who can use a name (owner decision 2026-10-15).
    "access_member_unknown",
]

_REGISTRY_CODES: dict[str, OwnershipErrorCode] = {
    "publisher_not_authorized": "publisher_not_authorized",
    "owner_mismatch": "owner_mismatch",
    "version_not_assigned": "version_not_assigned",
    "version_not_above_highest": "version_not_above_highest",
    "duplicate_package": "duplicate_package",
    "artifact_missing": "artifact_missing",
    "artifact_hash_mismatch": "artifact_hash_mismatch",
    "name_missing": "name_missing",
    "ownership_changed": "ownership_changed",
}

# How often an automatic publish asks again for the next version after
# another publisher took the one it was given.
PUBLISH_ATTEMPTS = 3

Builder = Callable[[AssetIdentity], tuple[PublishedAssetPackage, bytes | None]]


class OwnershipError(Exception):
    def __init__(self, code: OwnershipErrorCode) -> None:
        self.code: OwnershipErrorCode = code
        super().__init__(code)


def _registry_error(error: ControlError) -> OwnershipError:
    code = _REGISTRY_CODES.get(error.code)
    if code is None:
        raise error
    return OwnershipError(code)


class AssetOwnershipService:
    """Member-scoped publishing and name management over one Registry."""

    def __init__(
        self,
        enrollment: InMemoryEnrollmentRegistry,
        packages: PackageRegistry,
        *,
        artifacts: MutableMapping[str, bytes] | None = None,
    ) -> None:
        self.enrollment = enrollment
        self.packages = packages
        # Where an in-memory Registry's artifact bytes go; a SQLite Registry
        # keeps them in the same transaction as the package.
        self._artifacts = artifacts

    # -- who is asking -----------------------------------------------------

    def _member(
        self, identity: AuthenticatedActor, now: datetime | None
    ) -> tuple[str, tuple[str, ...]]:
        who = AuthenticatedActor.model_validate(identity)
        if not who.valid_at(now if now is not None else datetime.now(UTC)):
            raise OwnershipError("session_expired")
        try:
            user = self.enrollment.user(who.actor)
        except EnrollmentError:
            raise OwnershipError("actor_unknown") from None
        if user.status != "active":
            raise OwnershipError("actor_disabled")
        return who.actor, user.groups

    def _versions(self, namespace: str, name: str) -> tuple[str, ...]:
        return tuple(
            sorted(
                (
                    item.metadata.identity.version
                    for item in self.packages.discover()
                    if (item.metadata.identity.namespace, item.metadata.identity.name)
                    == (namespace, name)
                ),
                key=version_key,
            )
        )

    def _visible(
        self, namespace: str, name: str, actor: str, groups: tuple[str, ...]
    ) -> tuple[AssetNameOwnership, tuple[str, ...]]:
        """The record, if this member may publish the name or use one of its
        versions; otherwise the name is missing as far as they can tell."""
        ns = TypeAdapter(Slug).validate_python(namespace)
        nm = TypeAdapter(Slug).validate_python(name)
        record = self.packages.ownership(ns, nm)
        if record is None:
            raise OwnershipError("name_missing")
        versions = self._versions(ns, nm)
        if record.may_publish(actor, groups):
            return record, versions
        for version in versions:
            package = self.packages.get(AssetIdentity(namespace=ns, name=nm, version=version))
            if package is not None and entitled_in(self.packages, package.metadata, actor, groups):
                return record, versions
        raise OwnershipError("name_missing")

    def _managed(
        self, namespace: str, name: str, actor: str, groups: tuple[str, ...]
    ) -> tuple[AssetNameOwnership, tuple[str, ...]]:
        record, versions = self._visible(namespace, name, actor, groups)
        if not record.manages(actor, groups):
            raise OwnershipError("not_name_owner")
        return record, versions

    def _save(
        self, updated: AssetNameOwnership, previous: AssetNameOwnership
    ) -> AssetNameOwnership:
        try:
            return self.packages.save_ownership(updated, previous=previous)
        except ControlError as error:
            raise _registry_error(error) from None

    # -- reading -----------------------------------------------------------

    def ownership(
        self,
        identity: AuthenticatedActor,
        namespace: str,
        name: str,
        *,
        now: datetime | None = None,
    ) -> tuple[AssetNameOwnership, tuple[str, ...]]:
        actor, groups = self._member(identity, now)
        return self._visible(namespace, name, actor, groups)

    def next_version(
        self,
        identity: AuthenticatedActor,
        namespace: str,
        name: str,
        change: VersionChange,
        *,
        now: datetime | None = None,
    ) -> str:
        """The version a publish with this change level would be given now:
        1.0.0 for an unowned name, otherwise the highest version increased."""
        actor, groups = self._member(identity, now)
        ns = TypeAdapter(Slug).validate_python(namespace)
        nm = TypeAdapter(Slug).validate_python(name)
        record = self.packages.ownership(ns, nm)
        if record is not None and not record.may_publish(actor, groups):
            raise OwnershipError("publisher_not_authorized")
        return next_version(self._versions(ns, nm), change)

    # -- publishing --------------------------------------------------------

    def publish(
        self,
        identity: AuthenticatedActor,
        package: PublishedAssetPackage,
        *,
        artifact: bytes | None = None,
        change: VersionChange | None = None,
        now: datetime | None = None,
    ) -> PublishedAssetPackage:
        """Publish one version as this member, under the ownership rules.
        Without a change level the version is the publisher's and must be
        above every existing one; with one it must be the assigned one."""
        actor, groups = self._member(identity, now)
        return self._publish(actor, groups, package, artifact=artifact, change=change)

    def publish_reviewed(
        self,
        submitter: Symbol,
        package: PublishedAssetPackage,
        *,
        artifact: bytes,
    ) -> PublishedAssetPackage:
        """Publish an approved submission as the member who submitted it
        (`docs/phases/MEMBER_PUBLISH.md`). The administrator's approval is the
        authority here, so the submitter's session may long have ended; their
        account must still be active, and the ownership and version rules are
        checked again with their current groups."""
        try:
            user = self.enrollment.user(submitter)
        except EnrollmentError:
            raise OwnershipError("actor_unknown") from None
        if user.status != "active":
            raise OwnershipError("actor_disabled")
        return self._publish(user.actor, user.groups, package, artifact=artifact, change=None)

    def member(
        self, identity: AuthenticatedActor, now: datetime | None = None
    ) -> tuple[str, tuple[str, ...]]:
        """The member's actor and current groups, from a still-valid identity."""
        return self._member(identity, now)

    def _publish(
        self,
        actor: str,
        groups: tuple[str, ...],
        package: PublishedAssetPackage,
        *,
        artifact: bytes | None,
        change: VersionChange | None,
    ) -> PublishedAssetPackage:
        try:
            if isinstance(self.packages, SqliteRegistry):
                return self.packages.publish_as(
                    package, publisher=actor, groups=groups, change=change, artifact=artifact
                )
            item = PublishedAssetPackage.model_validate(package)
            described = item.metadata.package
            if artifact is not None and (self._artifacts is None or described is None):
                raise ControlError("artifact_missing")
            saved = self.packages.publish_as(item, publisher=actor, groups=groups, change=change)
            if artifact is not None and self._artifacts is not None and described is not None:
                self._artifacts[described.artifact_ref] = artifact
            return saved
        except ControlError as error:
            raise _registry_error(error) from None

    def publish_next(
        self,
        identity: AuthenticatedActor,
        namespace: str,
        name: str,
        change: VersionChange,
        build: Builder,
        *,
        now: datetime | None = None,
    ) -> PublishedAssetPackage:
        """Publish the next version the platform assigns.

        A package's artifact carries its own version, so the platform cannot
        renumber one after it is built: `build` is given the assigned identity
        and returns the package and its bytes. If another publisher takes that
        version first, the next one is assigned and built again."""
        for _ in range(PUBLISH_ATTEMPTS):
            version = self.next_version(identity, namespace, name, change, now=now)
            assigned = AssetIdentity(namespace=namespace, name=name, version=version)
            package, artifact = build(assigned)
            if package.metadata.identity != assigned:
                raise OwnershipError("version_not_assigned")
            try:
                return self.publish(identity, package, artifact=artifact, change=change, now=now)
            except OwnershipError as error:
                if error.code not in ("version_not_assigned", "duplicate_package"):
                    raise
        raise OwnershipError("version_not_assigned")

    # -- the owner's management of a name ----------------------------------

    def add_co_editor(
        self,
        identity: AuthenticatedActor,
        namespace: str,
        name: str,
        co_editor: Symbol,
        *,
        now: datetime | None = None,
    ) -> AssetNameOwnership:
        actor, groups = self._member(identity, now)
        record, _ = self._managed(namespace, name, actor, groups)
        member = TypeAdapter(Symbol).validate_python(co_editor)
        try:
            if self.enrollment.user(member).status != "active":
                raise OwnershipError("co_editor_unknown")
        except EnrollmentError:
            raise OwnershipError("co_editor_unknown") from None
        if member in record.co_editors or (
            record.owner.type == "user" and record.owner.id == member
        ):
            raise OwnershipError("co_editor_exists")
        updated = AssetNameOwnership.model_validate(
            {**record.model_dump(), "co_editors": (*record.co_editors, member)}
        )
        return self._save(updated, record)

    def remove_co_editor(
        self,
        identity: AuthenticatedActor,
        namespace: str,
        name: str,
        co_editor: Symbol,
        *,
        now: datetime | None = None,
    ) -> AssetNameOwnership:
        actor, groups = self._member(identity, now)
        record, _ = self._managed(namespace, name, actor, groups)
        member = TypeAdapter(Symbol).validate_python(co_editor)
        if member not in record.co_editors:
            raise OwnershipError("co_editor_missing")
        remaining = tuple(item for item in record.co_editors if item != member)
        updated = AssetNameOwnership.model_validate(
            {**record.model_dump(), "co_editors": remaining}
        )
        return self._save(updated, record)

    def transfer(
        self,
        identity: AuthenticatedActor,
        namespace: str,
        name: str,
        owner: Owner,
        *,
        now: datetime | None = None,
    ) -> AssetNameOwnership:
        """Hand the name to another person or team. Co-editors stay; a new
        owner who was a co-editor stops being listed as one. Versions already
        published keep the owner they declared, since they are immutable;
        later versions declare the new owner."""
        actor, groups = self._member(identity, now)
        record, _ = self._managed(namespace, name, actor, groups)
        new_owner = Owner.model_validate(owner)
        if new_owner == record.owner:
            raise OwnershipError("owner_unchanged")
        if new_owner.type == "user":
            try:
                if self.enrollment.user(new_owner.id).status != "active":
                    raise OwnershipError("new_owner_unknown")
            except EnrollmentError:
                raise OwnershipError("new_owner_unknown") from None
        co_editors = tuple(
            item
            for item in record.co_editors
            if not (new_owner.type == "user" and item == new_owner.id)
        )
        updated = AssetNameOwnership.model_validate(
            {
                **record.model_dump(),
                "owner": new_owner.model_dump(),
                "co_editors": co_editors,
            }
        )
        return self._save(updated, record)

    def deprecate(
        self,
        identity: AuthenticatedActor,
        namespace: str,
        name: str,
        version: str,
        reason: str,
        *,
        replacement: str | None = None,
        now: datetime | None = None,
    ) -> AssetNameOwnership:
        """Mark one published version as not to be chosen anew. The package
        itself is not changed: selections already made and installs already
        done keep working, so a member can still roll back to it."""
        actor, groups = self._member(identity, now)
        record, versions = self._managed(namespace, name, actor, groups)
        deprecation = VersionDeprecation(
            version=version, reason=reason, replacement=replacement, deprecated_by=actor
        )
        if deprecation.version not in versions:
            raise OwnershipError("version_missing")
        if deprecation.replacement is not None and deprecation.replacement not in versions:
            raise OwnershipError("version_missing")
        if record.deprecation(deprecation.version) is not None:
            raise OwnershipError("version_deprecated")
        updated = AssetNameOwnership.model_validate(
            {
                **record.model_dump(),
                "deprecations": (
                    *(item.model_dump() for item in record.deprecations),
                    deprecation.model_dump(),
                ),
            }
        )
        return self._save(updated, record)

    # -- who can use a name (owner decision 2026-10-15) --------------------
    # Published packages are immutable, so the decision is a `NameAccess`
    # record beside the name. The name's owner, a member of an owning team,
    # or a platform administrator makes it.

    def _administrator(self, actor: str) -> bool:
        try:
            return self.enrollment.user(actor).role == "platform_admin"
        except EnrollmentError:
            return False

    def _access_entry(self, record: AssetNameOwnership) -> AssetAccessEntry | None:
        versions = self._versions(*record.key)
        if not versions:
            return None
        latest = self.packages.get(
            AssetIdentity(namespace=record.namespace, name=record.name, version=versions[-1])
        )
        if latest is None:
            return None
        access = self.packages.access(*record.key)
        declared = latest.metadata.visibility
        return AssetAccessEntry(
            namespace=record.namespace,
            name=record.name,
            kind=latest.kind,
            owner=record.owner,
            versions=versions,
            declared_visibility=declared,
            visibility=(
                access.visibility
                if access is not None and access.visibility is not None
                else declared
            ),
            access=access,
        )

    def access_list(
        self,
        identity: AuthenticatedActor,
        *,
        everything: bool = False,
        now: datetime | None = None,
    ) -> tuple[AssetAccessEntry, ...]:
        """The names this member manages, or every published name for a
        platform administrator who asks for all of them."""
        actor, groups = self._member(identity, now)
        if everything and not self._administrator(actor):
            raise OwnershipError("not_name_owner")
        names = sorted(
            {
                (item.metadata.identity.namespace, item.metadata.identity.name)
                for item in self.packages.discover()
            }
        )
        entries: list[AssetAccessEntry] = []
        for namespace, name in names:
            record = self.packages.ownership(namespace, name)
            if record is None or not (everything or record.manages(actor, groups)):
                continue
            entry = self._access_entry(record)
            if entry is not None:
                entries.append(entry)
        return tuple(entries)

    def set_access(
        self,
        identity: AuthenticatedActor,
        namespace: str,
        name: str,
        *,
        visibility: Visibility | None,
        members: tuple[str, ...] = (),
        groups: tuple[str, ...] = (),
        now: datetime | None = None,
    ) -> AssetAccessEntry:
        """Decide who may use every version of a name, replacing the previous
        decision. Selections already made and installs already done are not
        withdrawn, as with a deprecation; what is offered and chosen anew
        follows the decision."""
        moment = now if now is not None else datetime.now(UTC)
        actor, member_groups = self._member(identity, moment)
        ns = TypeAdapter(Slug).validate_python(namespace)
        nm = TypeAdapter(Slug).validate_python(name)
        record = self.packages.ownership(ns, nm)
        if record is None or not self._versions(ns, nm):
            raise OwnershipError("name_missing")
        if not (record.manages(actor, member_groups) or self._administrator(actor)):
            raise OwnershipError("not_name_owner")
        for member in members:
            try:
                self.enrollment.user(TypeAdapter(Symbol).validate_python(member))
            except EnrollmentError:
                raise OwnershipError("access_member_unknown") from None
        decided = NameAccess(
            namespace=ns,
            name=nm,
            visibility=visibility,
            members=tuple(dict.fromkeys(members)),
            groups=tuple(dict.fromkeys(groups)),
            updated_by=actor,
            updated_at=moment,
        )
        try:
            self.packages.save_access(decided)
        except ControlError as error:
            raise _registry_error(error) from None
        entry = self._access_entry(record)
        if entry is None:
            raise OwnershipError("name_missing")
        return entry
