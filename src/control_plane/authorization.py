"""Where a member's decisions are recorded and turned into a device's policy.

The registry refuses a decision a member is not entitled to make: one about a
device they are not bound to, about an asset the Registry has not published,
or about a tool the device does not say it has. It then derives the Bridge's
grants from the capability specification the device advertised, never from
anything the member wrote, so a decision about *which* tools cannot become a
decision about what they may do.

Nothing here contacts a Bridge. It is the reference model for the shared
platform's side of the owner's rule, and the transport that delivers an
authorization to a device is a later slice.
"""

from datetime import datetime
from typing import Literal

from pydantic import TypeAdapter

from capabilities.contracts import CapabilitySpec
from capabilities.runtime import CapabilityGrant
from common.assets import AssetIdentity
from common.authorization import DeviceAssetSelection, DeviceAuthorization
from common.base import Symbol
from common.enrollment import BridgeExecutionSubject
from control_plane.distribution import InMemoryPackageRegistry
from control_plane.enrollment import EnrollmentError, InMemoryEnrollmentRegistry

AuthorizationErrorCode = Literal[
    "actor_not_admitted",
    "asset_not_published",
    "kind_mismatch",
    "tool_not_advertised",
    "approval_required",
    "approver_not_member",
    "duplicate_selection",
    "selection_missing",
]


class AuthorizationError(Exception):
    def __init__(self, code: AuthorizationErrorCode) -> None:
        self.code: AuthorizationErrorCode = code
        super().__init__(code)


def grant_from(spec: CapabilitySpec, selection: DeviceAssetSelection) -> CapabilityGrant:
    """The one shape of a grant: the permissions and policy references the
    capability itself declares, plus the approval the member recorded. The
    member's decision contributes which capability and whether it is approved,
    and nothing else."""
    return CapabilityGrant(
        actor=selection.actor,
        asset=spec.identity,
        permissions=spec.policy.required_permissions,
        policy_refs=spec.policy.policy_refs,
        approval_ref=selection.approval_ref,
    )


class InMemoryAuthorizationRegistry:
    """Side-effect-free reference for what members decided their devices run."""

    def __init__(
        self, enrollment: InMemoryEnrollmentRegistry, packages: InMemoryPackageRegistry
    ) -> None:
        self.enrollment = enrollment
        self.packages = packages
        self._selections: dict[tuple[str, str, tuple[str, str, str]], DeviceAssetSelection] = {}

    def _member(self, actor: str, bridge_id: str) -> bool:
        return self.enrollment.admit(BridgeExecutionSubject(actor=actor, bridge_id=bridge_id))

    def _advertised(self, bridge_id: str, asset: AssetIdentity) -> CapabilitySpec | None:
        try:
            advertisement = self.enrollment.advertisement(bridge_id)
        except EnrollmentError:
            return None
        return next(
            (item for item in advertisement.capabilities if item.identity.key == asset.key), None
        )

    def select(self, selection: DeviceAssetSelection) -> DeviceAssetSelection:
        """Record one decision, or say why the member may not make it."""
        item = DeviceAssetSelection.model_validate(selection)
        if not self._member(item.actor, item.bridge_id):
            raise AuthorizationError("actor_not_admitted")
        if item.kind == "capability":
            spec = self._advertised(item.bridge_id, item.asset)
            if spec is None:
                # A device says what it can run; a member cannot choose a tool
                # that is not there.
                raise AuthorizationError("tool_not_advertised")
            if spec.policy.approval_required and item.approval_ref is None:
                raise AuthorizationError("approval_required")
            if item.approved_by is not None and not self._member(item.approved_by, item.bridge_id):
                raise AuthorizationError("approver_not_member")
        else:
            package = self.packages.get(item.asset)
            if package is None:
                raise AuthorizationError("asset_not_published")
            if package.kind != item.kind:
                raise AuthorizationError("kind_mismatch")
        current = self._selections.get(item.key)
        if current is not None and current.status == "active":
            raise AuthorizationError("duplicate_selection")
        self._selections[item.key] = item
        return item.model_copy(deep=True)

    def revoke(
        self, bridge_id: Symbol, actor: Symbol, asset: AssetIdentity
    ) -> DeviceAssetSelection:
        key = (
            TypeAdapter(Symbol).validate_python(bridge_id),
            TypeAdapter(Symbol).validate_python(actor),
            AssetIdentity.model_validate(asset).key,
        )
        current = self._selections.get(key)
        if current is None or current.status != "active":
            raise AuthorizationError("selection_missing")
        revoked = DeviceAssetSelection.model_validate({**current.model_dump(), "status": "revoked"})
        self._selections[key] = revoked
        return revoked.model_copy(deep=True)

    def authorization(self, bridge_id: Symbol, *, issued_at: datetime) -> DeviceAuthorization:
        """What this device may run, as of now: the decisions in force."""
        key = TypeAdapter(Symbol).validate_python(bridge_id)
        return DeviceAuthorization(
            bridge_id=key,
            issued_at=issued_at,
            selections=tuple(
                item.model_copy(deep=True)
                for item in sorted(self._selections.values(), key=lambda entry: entry.key)
                if item.bridge_id == key and item.status == "active"
            ),
        )

    def grants(self, bridge_id: Symbol) -> tuple[CapabilityGrant, ...]:
        """The device's policy, derived from what it advertised. A tool the
        device has stopped advertising grants nothing, because the grant is
        built from the specification and there is none."""
        key = TypeAdapter(Symbol).validate_python(bridge_id)
        derived: list[CapabilityGrant] = []
        for item in sorted(self._selections.values(), key=lambda entry: entry.key):
            if item.bridge_id != key or item.status != "active" or item.kind != "capability":
                continue
            spec = self._advertised(key, item.asset)
            if spec is not None:
                derived.append(grant_from(spec, item))
        return tuple(derived)
