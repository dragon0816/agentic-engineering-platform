"""Member-facing shared-platform contracts.

These requests intentionally contain no actor, groups, permissions, policy
references or decision time. The member entry point derives identity from its
own authenticated session and the authorization registry derives policy from
the asset and Bridge records it already trusts.
"""

from typing import Self

from pydantic import AwareDatetime, Field, model_validator

from common.assets import AssetIdentity
from common.authorization import DeviceAssetSelection
from common.base import Contract, Symbol
from common.distribution import PublishedAssetPackage
from common.enrollment import Invitation, PlatformRole


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
