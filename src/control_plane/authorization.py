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

from datetime import UTC, datetime
from typing import Literal

from pydantic import TypeAdapter

from capabilities.contracts import CapabilitySpec
from capabilities.runtime import CapabilityGrant
from common.assets import AssetIdentity
from common.authorization import DeviceAssetSelection, DeviceAuthorization
from common.base import Symbol
from common.distribution import PublishedAssetPackage
from common.enrollment import BridgeExecutionSubject
from common.identity import AuthenticatedActor, entitled
from control_plane.distribution import InMemoryPackageRegistry
from control_plane.enrollment import EnrollmentError, InMemoryEnrollmentRegistry

AuthorizationErrorCode = Literal[
    "session_expired",
    "actor_mismatch",
    "actor_unknown",
    "actor_disabled",
    "actor_not_admitted",
    "asset_not_published",
    "asset_not_entitled",
    "kind_mismatch",
    "tool_not_advertised",
    "tool_not_grantable",
    "approval_required",
    "approver_not_member",
    "duplicate_selection",
    "selection_missing",
    "decision_in_future",
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

    def _active(self, actor: str) -> bool:
        """Somebody the platform invited and has not disabled. An approver is
        checked against this rather than against the device's own members: a
        machine has one member, and a shared test machine's member is the
        virtual one it runs as, so requiring the approver to be bound there
        would leave every approval self-given."""
        try:
            return self.enrollment.user(actor).status == "active"
        except EnrollmentError:
            return False

    def _advertised(self, bridge_id: str, asset: AssetIdentity) -> CapabilitySpec | None:
        try:
            advertisement = self.enrollment.advertisement(bridge_id)
        except EnrollmentError:
            return None
        return next(
            (item for item in advertisement.capabilities if item.identity.key == asset.key), None
        )

    def _member_groups(self, actor: str) -> tuple[str, ...]:
        """What the platform recorded when this member accepted their
        invitation, which is the only place entitlement is read from. Somebody
        the platform does not know, or has disabled, is not entitled to
        anything, and saying so beats answering as if they had no groups."""
        try:
            user = self.enrollment.user(actor)
        except EnrollmentError:
            raise AuthorizationError("actor_unknown") from None
        if user.status != "active":
            raise AuthorizationError("actor_disabled")
        return user.groups

    def _valid(self, identity: AuthenticatedActor, now: datetime | None) -> AuthenticatedActor:
        who = AuthenticatedActor.model_validate(identity)
        if not who.valid_at(now if now is not None else datetime.now(UTC)):
            raise AuthorizationError("session_expired")
        return who

    def available(
        self, identity: AuthenticatedActor, *, now: datetime | None = None
    ) -> tuple[PublishedAssetPackage, ...]:
        """Which published Workflows and Skills this member may use: the list
        they choose from. It answers only for a member the platform knows,
        has not disabled, and whose session is still valid, because a list of
        what somebody may use is itself something only they should see.
        Being entitled to one grants no execution."""
        who = self._valid(identity, now)
        groups = self._member_groups(who.actor)
        return tuple(
            package
            for package in self.packages.discover()
            # A decision names a Workflow, a Skill or a tool, and tools come
            # from the device rather than the Registry, so offering any other
            # published kind here would offer what cannot be chosen.
            if package.kind in ("workflow", "skill")
            and entitled(package.metadata, who.actor, groups)
        )

    def select(
        self,
        identity: AuthenticatedActor,
        selection: DeviceAssetSelection,
        *,
        now: datetime | None = None,
    ) -> DeviceAssetSelection:
        """Record one decision, or say why the member may not make it."""
        moment = now if now is not None else datetime.now(UTC)
        who = self._valid(identity, moment)
        item = DeviceAssetSelection.model_validate(selection)
        if who.actor != item.actor:
            # A member decides as themselves; nobody decides for anyone else.
            raise AuthorizationError("actor_mismatch")
        # A decision dated in the future could never appear in an
        # authorization, because a bundle refuses a decision newer than
        # itself; one such record would leave the device with no bundle at
        # all, so it is refused where it arrives.
        if item.decided_at > moment:
            raise AuthorizationError("decision_in_future")
        if not self._member(item.actor, item.bridge_id):
            raise AuthorizationError("actor_not_admitted")
        if item.kind == "capability":
            spec = self._advertised(item.bridge_id, item.asset)
            if spec is None:
                # A device says what it can run; a member cannot choose a tool
                # that is not there.
                raise AuthorizationError("tool_not_advertised")
            if not spec.policy.policy_refs:
                # A grant names the policy it was made under, so a capability
                # that declares none cannot be granted to anybody. Refusing
                # here keeps one unusable tool from breaking the whole
                # device's authorization later.
                raise AuthorizationError("tool_not_grantable")
            if spec.policy.approval_required and item.approval_ref is None:
                raise AuthorizationError("approval_required")
            if item.approved_by is not None and not self._active(item.approved_by):
                raise AuthorizationError("approver_not_member")
        else:
            package = self.packages.get(item.asset)
            if package is None:
                raise AuthorizationError("asset_not_published")
            if package.kind != item.kind:
                raise AuthorizationError("kind_mismatch")
            if not entitled(package.metadata, item.actor, self._member_groups(item.actor)):
                raise AuthorizationError("asset_not_entitled")
        current = self._selections.get(item.key)
        if current is not None and current.status == "active":
            raise AuthorizationError("duplicate_selection")
        self._selections[item.key] = item
        return item.model_copy(deep=True)

    def revoke(
        self,
        identity: AuthenticatedActor,
        bridge_id: Symbol,
        asset: AssetIdentity,
        *,
        now: datetime | None = None,
    ) -> DeviceAssetSelection:
        """A member takes back their own decision. Like making one, it needs
        a session that is still valid."""
        who = self._valid(identity, now)
        key = (
            TypeAdapter(Symbol).validate_python(bridge_id),
            who.actor,
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
            # A tool the device has stopped advertising, or one that declares
            # no policy to be granted under, contributes nothing rather than
            # taking the other members' grants down with it.
            if spec is not None and spec.policy.policy_refs:
                derived.append(grant_from(spec, item))
        return tuple(derived)
