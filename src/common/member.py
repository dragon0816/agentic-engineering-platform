"""Member-facing shared-platform contracts.

These requests intentionally contain no actor, groups, permissions, policy
references or decision time. The member entry point derives identity from its
own authenticated session and the authorization registry derives policy from
the asset and Bridge records it already trusts.
"""

from typing import Literal, Self

from pydantic import AwareDatetime, Field, JsonValue, model_validator

from common.assets import AssetIdentity, Owner
from common.authorization import DeviceAssetSelection
from common.base import Contract, Sha256, Slug, Symbol, Text
from common.distribution import PublishedAssetPackage
from common.enrollment import BridgeDevice, Invitation, PlatformRole
from common.ownership import AssetNameOwnership, VersionChange
from workflow.host_bridge import BridgeRegistration


class MemberCatalogRequest(Contract):
    bridge_id: Symbol


class MemberIdentityReply(Contract):
    actor: Symbol
    role: PlatformRole
    groups: tuple[Symbol, ...] = ()
    session_expires_at: AwareDatetime


class AdminInvitationCreateRequest(Contract):
    actor: Symbol
    role: PlatformRole = "member"
    groups: tuple[Symbol, ...] = ()
    valid_for_minutes: int = Field(default=60, ge=1, le=7 * 24 * 60, strict=True)

    @model_validator(mode="after")
    def unique_groups(self) -> Self:
        if len(self.groups) != len(set(self.groups)):
            raise ValueError("invitation groups must be unique")
        return self


class AdminInvitationMetadata(Contract):
    invitation: Invitation
    expires_at: AwareDatetime


class AdminInvitationListReply(Contract):
    invitations: tuple[AdminInvitationMetadata, ...] = ()

    @model_validator(mode="after")
    def unique_invitations(self) -> Self:
        identifiers = [item.invitation.invitation_id for item in self.invitations]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("an invitation is listed once")
        return self


class AdminInvitationRevokeRequest(Contract):
    invitation_id: Symbol


class AdminExtensionCatalogEntry(Contract):
    """Published Bridge Extension metadata visible to platform administrators."""

    package: PublishedAssetPackage
    deployment_state: str = "available"

    @model_validator(mode="after")
    def bridge_extension_only(self) -> Self:
        if self.package.kind != "bridge_extension":
            raise ValueError("the administrator extension catalog contains only extensions")
        if self.deployment_state != "available":
            raise ValueError("an unstaged Registry extension is only available")
        return self


class AdminExtensionCatalogReply(Contract):
    entries: tuple[AdminExtensionCatalogEntry, ...] = ()

    @model_validator(mode="after")
    def unique_extensions(self) -> Self:
        keys = [item.package.metadata.identity.key for item in self.entries]
        if len(keys) != len(set(keys)):
            raise ValueError("an extension is listed once")
        return self


class MemberCatalogEntry(Contract):
    package: PublishedAssetPackage
    selected: bool = False

    @model_validator(mode="after")
    def installable_add_on(self) -> Self:
        if self.package.kind not in ("workflow", "skill", "knowledge", "agent"):
            raise ValueError("the member add-on catalog contains only installable Agent Add-ons")
        return self


class MemberCatalogReply(Contract):
    bridge_id: Symbol
    entries: tuple[MemberCatalogEntry, ...] = ()

    @model_validator(mode="after")
    def unique_assets(self) -> Self:
        keys = [item.package.metadata.identity.key for item in self.entries]
        if len(keys) != len(set(keys)):
            raise ValueError("an add-on is listed once")
        return self


class MemberSelectRequest(Contract):
    bridge_id: Symbol
    asset: AssetIdentity


class MemberRevokeRequest(Contract):
    bridge_id: Symbol
    asset: AssetIdentity


class MemberReplaceRequest(Contract):
    """Atomic exact-version change within one Add-on family."""

    bridge_id: Symbol
    current: AssetIdentity
    replacement: AssetIdentity

    @model_validator(mode="after")
    def distinct_same_family(self) -> Self:
        if self.current.key == self.replacement.key:
            raise ValueError("replacement must name another exact version")
        if (self.current.namespace, self.current.name) != (
            self.replacement.namespace,
            self.replacement.name,
        ):
            raise ValueError("replacement must remain in one asset family")
        return self


class MemberSelectionReply(Contract):
    selection: DeviceAssetSelection

    @model_validator(mode="after")
    def installable_add_on(self) -> Self:
        if self.selection.kind not in ("workflow", "skill", "knowledge", "agent"):
            raise ValueError("the member entry point changes only installable Agent Add-ons")
        return self


class MemberReplacementReply(Contract):
    previous: DeviceAssetSelection
    selection: DeviceAssetSelection

    @model_validator(mode="after")
    def one_atomic_family_change(self) -> Self:
        if self.previous.status != "revoked" or self.selection.status != "active":
            raise ValueError("replacement revokes one selection and activates one")
        if self.previous.kind != self.selection.kind or (
            self.previous.asset.namespace,
            self.previous.asset.name,
        ) != (self.selection.asset.namespace, self.selection.asset.name):
            raise ValueError("replacement stays within one Add-on family and kind")
        return self


class AssetNameRequest(Contract):
    """One Skill or Workflow name, across its versions."""

    namespace: Slug
    name: Slug


class AssetNextVersionRequest(AssetNameRequest):
    change: VersionChange


class AssetNextVersionReply(Contract):
    namespace: Slug
    name: Slug
    version: Text


class AssetCoEditorRequest(AssetNameRequest):
    co_editor: Symbol


class AssetTransferRequest(AssetNameRequest):
    owner: Owner


class AssetDeprecateRequest(AssetNameRequest):
    version: Text
    reason: Text
    replacement: Text | None = None


class AssetOwnershipReply(Contract):
    """A name's owner, co-editors and deprecations, with its versions."""

    ownership: AssetNameOwnership
    versions: tuple[Text, ...] = ()


# -- Member publish with a review queue (owner 2026-10-15) -----------------
# `docs/phases/MEMBER_PUBLISH.md`. A submission is not a package: a package is
# published by definition, so the queue keeps its own record until approval.

SubmissionKind = Literal["skill", "workflow"]
SubmissionStatus = Literal["pending", "approved", "rejected", "withdrawn"]
SubmissionRisk = Literal["low", "medium", "high", "critical"]


class AssetSubmitRequest(Contract):
    """A manifest as the member's Agent has it. The platform assigns the
    version, owner and reviews; nothing the author wrote there is trusted."""

    kind: SubmissionKind
    change: VersionChange
    note: Text | None = None
    manifest: dict[str, JsonValue]


class AssetSubmission(Contract):
    """One submission's secret-free record, without its artifact bytes."""

    submission_id: Symbol
    kind: SubmissionKind
    identity: AssetIdentity
    submitter: Symbol
    change: VersionChange
    note: Text | None = None
    sha256: Sha256
    risk: SubmissionRisk = "low"
    required_permissions: tuple[Symbol, ...] = ()
    status: SubmissionStatus = "pending"
    reviewer: Symbol | None = None
    reason: Text | None = None
    submitted_at: AwareDatetime
    decided_at: AwareDatetime | None = None

    @model_validator(mode="after")
    def decided_with_reviewer(self) -> Self:
        if self.status in ("approved", "rejected") and (
            self.reviewer is None or self.decided_at is None
        ):
            raise ValueError("a review decision names its reviewer and time")
        if self.status == "rejected" and self.reason is None:
            raise ValueError("a rejection gives its reason")
        return self


class AssetSubmissionReply(Contract):
    submission: AssetSubmission


class AssetSubmissionListRequest(Contract):
    status: SubmissionStatus | None = None


class AssetSubmissionListReply(Contract):
    submissions: tuple[AssetSubmission, ...] = ()


class AssetSubmissionRequest(Contract):
    submission_id: Symbol


class AssetSubmissionDetailReply(Contract):
    """What a reviewer reads: the manifest as it would be published, and the
    highest published version of the same name to compare it with."""

    submission: AssetSubmission
    manifest: dict[str, JsonValue]
    previous_version: Text | None = None
    previous_manifest: dict[str, JsonValue] | None = None


class AssetApproveRequest(AssetSubmissionRequest):
    evidence: Text


class AssetRejectRequest(AssetSubmissionRequest):
    reason: Text


# -- Bridge self-enrollment (owner 2026-10-15, docs/phases/BRIDGE_ENROLLMENT.md) --


class BridgeEnrollRequest(Contract):
    """A member's own Agent asking to enroll the computer it runs on.

    The same shape as the Agent's `EnrollmentRequest`: the device facts and
    what it advertises, with no secret. Who is asking comes from the member
    session, never from this body; the body must name that member.
    """

    schema_version: Literal["1"] = "1"
    device: BridgeDevice
    advertisement: BridgeRegistration

    @model_validator(mode="after")
    def one_device(self) -> Self:
        if self.advertisement.bridge_id != self.device.bridge_id:
            raise ValueError("advertisement bridge identity must match the device")
        return self


class AdminBridgeRequest(Contract):
    bridge_id: Symbol


class AdminBridgeEntry(Contract):
    """One enrolled computer as an administrator sees it; no secret."""

    bridge_id: Symbol
    registered_by: Symbol
    device_kind: Symbol
    status: Literal["active", "disabled"]
    members: tuple[Symbol, ...] = ()
    # When its newest token was issued (the last enrollment) and until when
    # the token that still works is valid.
    enrolled_at: AwareDatetime | None = None
    token_expires_at: AwareDatetime | None = None


class AdminBridgeListReply(Contract):
    bridges: tuple[AdminBridgeEntry, ...] = ()
