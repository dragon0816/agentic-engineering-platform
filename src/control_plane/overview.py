"""The administrator's Platform overview of the Shared Platform.

Owner request 2026-10-15 (`docs/phases/PLATFORM_OVERVIEW.md`): on the Member
Portal an administrator sees, in one place, every registered computer, every
published Skill, Workflow, Knowledge, Agent profile and Extension with all its
versions, every submission, every Application and every member, whatever they
are entitled to themselves.

Everything here is read-only and secret-free: no token value or fingerprint,
no invitation proof, no session or login. The overview is built from the
stores the platform already keeps; it decides nothing.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from datetime import datetime
from typing import Literal

from pydantic import AwareDatetime, Field

from common.assets import Owner
from common.base import Contract, Slug, Symbol, Text
from common.distribution import PublishedAssetPackage
from common.enrollment import PlatformRole
from common.identity import NameAccess, Visibility
from common.member import AdminBridgeEntry, AssetSubmission
from common.ownership import VersionDeprecation, version_key
from control_plane.activity import BridgeActivity
from control_plane.authorization import InMemoryAuthorizationRegistry
from control_plane.distribution import PackageRegistry
from control_plane.enrollment import EnrollmentError, InMemoryEnrollmentRegistry
from control_plane.identity import InMemoryAccessTokens
from software.marketplace import ApplicationCatalog, ApplicationProjection, project_application

# The kinds the overview shows, each in its own tab.
OverviewKind = Literal["skill", "workflow", "knowledge", "agent", "bridge_extension"]
OVERVIEW_KINDS: tuple[OverviewKind, ...] = (
    "skill", "workflow", "knowledge", "agent", "bridge_extension"
)


class OverviewAsset(Contract):
    """One published name with every version, as an administrator sees it."""

    namespace: Slug
    name: Slug
    kind: Symbol
    owner: Owner
    co_editors: tuple[Symbol, ...] = ()
    latest_version: Text
    versions: tuple[Text, ...]
    deprecations: tuple[VersionDeprecation, ...] = ()
    declared_visibility: Visibility
    visibility: Visibility
    access: NameAccess | None = None
    description: Text | None = None
    # Distinct computers on which some member selected a version of it.
    bridges_selected: int = Field(default=0, ge=0)
    # When the latest version was approved, if it came through the review
    # queue; a seeded or migrated version has no recorded date.
    published_at: AwareDatetime | None = None
    pending_submissions: int = Field(default=0, ge=0)


class OverviewKindCount(Contract):
    kind: Symbol
    names: int = Field(ge=0)
    versions: int = Field(ge=0)


class OverviewCounts(Contract):
    bridges_active: int = 0
    bridges_disabled: int = 0
    members_active: int = 0
    members_disabled: int = 0
    invitations_pending: int = 0
    assets: tuple[OverviewKindCount, ...] = ()
    applications: int = 0
    application_versions: int = 0
    submissions_pending: int = 0
    submissions_approved: int = 0
    submissions_rejected: int = 0
    submissions_withdrawn: int = 0


InvitationState = Literal["accepted", "pending", "expired", "revoked"]


class OverviewMember(Contract):
    """A member, or an invitation not accepted yet. No invitation proof."""

    actor: Symbol
    role: PlatformRole
    groups: tuple[Symbol, ...] = ()
    # None while the invitation is not accepted.
    status: Literal["active", "disabled"] | None = None
    invitation: InvitationState
    invited_by: Symbol | None = None
    invitation_expires_at: AwareDatetime | None = None
    bridges: tuple[Symbol, ...] = ()
    last_changed_by: Symbol | None = None
    last_changed_at: AwareDatetime | None = None


class AdminMemberReply(Contract):
    member: OverviewMember


class AdminOverviewReply(Contract):
    generated_at: AwareDatetime
    counts: OverviewCounts
    bridges: tuple[AdminBridgeEntry, ...] = ()
    assets: tuple[OverviewAsset, ...] = ()
    submissions: tuple[AssetSubmission, ...] = ()
    applications: tuple[ApplicationProjection, ...] = ()
    members: tuple[OverviewMember, ...] = ()


def bridge_entries(
    enrollment: InMemoryEnrollmentRegistry,
    tokens: InMemoryAccessTokens,
    authorization: InMemoryAuthorizationRegistry,
    activity: BridgeActivity | None,
    now: datetime,
) -> tuple[AdminBridgeEntry, ...]:
    """Every registered computer, without any token value or fingerprint."""
    selections = Counter(item.bridge_id for item in authorization.selections())
    entries = []
    for device in enrollment.devices():
        history = tokens.history_for(device.bridge_id)
        working = tokens.grants_for(device.bridge_id, now=now)
        expiries = [item.expires_at for item in working if item.expires_at is not None]
        seen = activity.last(device.bridge_id) if activity is not None else None
        entries.append(
            AdminBridgeEntry(
                bridge_id=device.bridge_id,
                registered_by=device.registered_by,
                device_kind=device.device_kind,
                status=device.status,
                members=tuple(item.actor for item in enrollment.members(device.bridge_id)),
                enrolled_at=history[0].issued_at if history else None,
                token_expires_at=max(expiries) if expiries else None,
                last_seen_at=seen.at if seen is not None else None,
                last_seen_operation=seen.operation if seen is not None else None,
                selections=selections.get(device.bridge_id, 0),
            )
        )
    return tuple(entries)


def asset_rows(
    packages: PackageRegistry,
    authorization: InMemoryAuthorizationRegistry,
    submissions: Iterable[AssetSubmission],
) -> tuple[OverviewAsset, ...]:
    """Every published name of the overview's kinds, all versions, for an
    administrator: no entitlement filter applies."""
    by_name: dict[tuple[str, str], list[PublishedAssetPackage]] = defaultdict(list)
    for package in packages.discover():
        if package.kind in OVERVIEW_KINDS:
            identity = package.metadata.identity
            by_name[(identity.namespace, identity.name)].append(package)
    chosen: dict[tuple[str, str], set[str]] = defaultdict(set)
    for selection in authorization.selections():
        chosen[(selection.asset.namespace, selection.asset.name)].add(selection.bridge_id)
    approved: dict[tuple[str, str, str], datetime] = {}
    pending: Counter[tuple[str, str]] = Counter()
    for item in submissions:
        if item.status == "approved" and item.decided_at is not None:
            approved[item.identity.key] = item.decided_at
        elif item.status == "pending":
            pending[(item.identity.namespace, item.identity.name)] += 1
    rows = []
    for (namespace, name), versions in sorted(by_name.items()):
        ordered = sorted(versions, key=lambda item: version_key(item.metadata.identity.version))
        latest = ordered[-1]
        record = packages.ownership(namespace, name)
        access = packages.access(namespace, name)
        declared = latest.metadata.visibility
        rows.append(
            OverviewAsset(
                namespace=namespace,
                name=name,
                kind=latest.kind,
                owner=record.owner if record is not None else latest.metadata.owner,
                co_editors=record.co_editors if record is not None else (),
                latest_version=latest.metadata.identity.version,
                versions=tuple(item.metadata.identity.version for item in ordered),
                deprecations=record.deprecations if record is not None else (),
                declared_visibility=declared,
                visibility=(
                    access.visibility
                    if access is not None and access.visibility is not None
                    else declared
                ),
                access=access,
                description=latest.description,
                bridges_selected=len(chosen.get((namespace, name), ())),
                published_at=approved.get(latest.metadata.identity.key),
                pending_submissions=pending.get((namespace, name), 0),
            )
        )
    return tuple(rows)


def member_rows(
    enrollment: InMemoryEnrollmentRegistry,
    invitation_expiry: Mapping[str, datetime],
    now: datetime,
) -> tuple[OverviewMember, ...]:
    """Every member, and every invitation nobody accepted yet."""
    invitations = {item.invitation_id: item for item in enrollment.invitations()}
    bridges: dict[str, list[str]] = defaultdict(list)
    for device in enrollment.devices():
        try:
            bound = enrollment.members(device.bridge_id)
        except EnrollmentError:
            continue
        for binding in bound:
            bridges[binding.actor].append(device.bridge_id)
    changes = {item.actor: item for item in enrollment.user_changes()}
    rows: list[OverviewMember] = []
    for user in enrollment.users():
        invitation = invitations.get(user.invitation_id)
        change = changes.get(user.actor)
        rows.append(
            OverviewMember(
                actor=user.actor,
                role=user.role,
                groups=user.groups,
                status=user.status,
                invitation="accepted",
                invited_by=invitation.issued_by if invitation is not None else None,
                bridges=tuple(bridges.get(user.actor, ())),
                last_changed_by=change.changed_by if change is not None else None,
                last_changed_at=change.changed_at if change is not None else None,
            )
        )
    accepted = {user.actor for user in enrollment.users()}
    for invitation in invitations.values():
        if invitation.status == "accepted" or invitation.actor in accepted:
            continue
        expires = invitation_expiry.get(invitation.invitation_id)
        state: InvitationState = (
            "revoked"
            if invitation.status == "revoked"
            else "expired"
            if expires is not None and expires <= now
            else "pending"
        )
        rows.append(
            OverviewMember(
                actor=invitation.actor,
                role=invitation.role,
                groups=invitation.groups,
                invitation=state,
                invited_by=invitation.issued_by,
                invitation_expires_at=expires,
            )
        )
    return tuple(sorted(rows, key=lambda item: item.actor))


def overview(
    *,
    enrollment: InMemoryEnrollmentRegistry,
    tokens: InMemoryAccessTokens,
    authorization: InMemoryAuthorizationRegistry,
    packages: PackageRegistry,
    applications: ApplicationCatalog,
    submissions: tuple[AssetSubmission, ...],
    activity: BridgeActivity | None,
    invitation_expiry: Mapping[str, datetime],
    now: datetime,
) -> AdminOverviewReply:
    bridges = bridge_entries(enrollment, tokens, authorization, activity, now)
    assets = asset_rows(packages, authorization, submissions)
    members = member_rows(enrollment, invitation_expiry, now)
    projected = tuple(project_application(entry) for entry in applications.discover())
    names = Counter(item.kind for item in assets)
    versions: Counter[str] = Counter()
    for item in assets:
        versions[item.kind] += len(item.versions)
    statuses = Counter(item.status for item in submissions)
    counts = OverviewCounts(
        bridges_active=sum(1 for item in bridges if item.status == "active"),
        bridges_disabled=sum(1 for item in bridges if item.status == "disabled"),
        members_active=sum(1 for item in members if item.status == "active"),
        members_disabled=sum(1 for item in members if item.status == "disabled"),
        invitations_pending=sum(1 for item in members if item.invitation == "pending"),
        assets=tuple(
            OverviewKindCount(kind=kind, names=names.get(kind, 0), versions=versions.get(kind, 0))
            for kind in OVERVIEW_KINDS
        ),
        applications=len({(item.identity.namespace, item.identity.name) for item in projected}),
        application_versions=len(projected),
        submissions_pending=statuses.get("pending", 0),
        submissions_approved=statuses.get("approved", 0),
        submissions_rejected=statuses.get("rejected", 0),
        submissions_withdrawn=statuses.get("withdrawn", 0),
    )
    return AdminOverviewReply(
        generated_at=now,
        counts=counts,
        bridges=bridges,
        assets=assets,
        submissions=submissions,
        applications=projected,
        members=members,
    )
