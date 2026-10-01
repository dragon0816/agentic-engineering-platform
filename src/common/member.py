"""Member-facing shared-platform contracts.

These requests intentionally contain no actor, groups, permissions, policy
references or decision time. The member entry point derives identity from its
own authenticated session and the authorization registry derives policy from
the asset and Bridge records it already trusts.
"""

from typing import Self

from pydantic import model_validator

from common.assets import AssetIdentity
from common.authorization import DeviceAssetSelection
from common.base import Contract, Symbol
from common.distribution import PublishedAssetPackage


class MemberCatalogRequest(Contract):
    bridge_id: Symbol


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


class MemberSelectionReply(Contract):
    selection: DeviceAssetSelection

    @model_validator(mode="after")
    def installable_add_on(self) -> Self:
        if self.selection.kind not in ("workflow", "skill", "knowledge", "agent"):
            raise ValueError("the member entry point changes only installable Agent Add-ons")
        return self
