"""What a member decided their device may run.

The owner's rule (2026-09-22): a platform user decides, for each device they
may use, which Workflows, which Skills and which tools that device may run for
them. Nobody decides for anyone else, and a decision reaches no further than
the devices that user is bound to.

A selection names an asset and nothing else. It carries no permission and no
policy reference, because those belong to the capability's own specification:
a user chooses *which* assets, never what they are allowed to do, so a
decision cannot widen itself. The plane that enforces derives the grant from
the specification it holds, and the plane that decides derives it from the
specification the device advertised; both read the same declaration, so
neither has to trust the other's arithmetic.
"""

from typing import Literal, Self

from pydantic import AwareDatetime, model_validator

from common.assets import AssetIdentity, RegistryContract
from common.base import Contract, Symbol, Text

# A Workflow and a Skill are installed; a capability is a tool the policy
# grants. The three lists stay separate because they are enforced in
# different places.
RunnableKind = Literal["workflow", "skill", "capability"]


class DeviceAssetSelection(RegistryContract):
    """One member's decision that one device may run one asset for them."""

    bridge_id: Symbol
    actor: Symbol
    kind: RunnableKind
    asset: AssetIdentity
    # Only a tool is authorized by the Bridge policy, so only a tool carries
    # an approval, and an approval always names who gave it.
    approval_ref: Text | None = None
    approved_by: Symbol | None = None
    decided_at: AwareDatetime
    status: Literal["active", "revoked"] = "active"

    @model_validator(mode="after")
    def approval_belongs_to_a_tool(self) -> Self:
        if (self.approval_ref is None) != (self.approved_by is None):
            raise ValueError("an approval names the member who gave it")
        if self.approval_ref is not None and self.kind != "capability":
            raise ValueError("only a tool selection carries an approval")
        return self

    @property
    def key(self) -> tuple[str, str, tuple[str, str, str]]:
        return (self.bridge_id, self.actor, self.asset.key)


class DeviceAuthorization(Contract):
    """Every decision in force for one device at one moment.

    This is what a Bridge is told it may run. It holds active selections only:
    a revoked decision is absent, not present and disabled, so nothing has to
    read a status to know what applies.
    """

    bridge_id: Symbol
    issued_at: AwareDatetime
    selections: tuple[DeviceAssetSelection, ...] = ()

    @model_validator(mode="after")
    def decisions_for_this_device(self) -> Self:
        if any(item.bridge_id != self.bridge_id for item in self.selections):
            raise ValueError("an authorization carries decisions for its own device")
        if any(item.status != "active" for item in self.selections):
            raise ValueError("an authorization carries the decisions in force")
        keys = [item.key for item in self.selections]
        if len(keys) != len(set(keys)):
            raise ValueError("a member decides once about an asset")
        if any(item.decided_at > self.issued_at for item in self.selections):
            raise ValueError("a decision cannot be newer than the authorization carrying it")
        return self

    def for_actor(self, actor: str) -> tuple[DeviceAssetSelection, ...]:
        return tuple(item for item in self.selections if item.actor == actor)

    def installable(self) -> tuple[DeviceAssetSelection, ...]:
        """What this device may install: the Workflows and Skills chosen."""
        return tuple(item for item in self.selections if item.kind in ("workflow", "skill"))

    def tools(self) -> tuple[DeviceAssetSelection, ...]:
        """What this device's policy may grant: the capabilities chosen."""
        return tuple(item for item in self.selections if item.kind == "capability")

    def allows(self, kind: RunnableKind, asset: AssetIdentity) -> bool:
        """Whether anyone on this device chose that asset. Which member may
        run it is decided per actor by the grants; this answers the narrower
        question of what the device installs at all."""
        return any(item.kind == kind and item.asset.key == asset.key for item in self.selections)
