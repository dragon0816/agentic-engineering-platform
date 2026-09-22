"""Invitation and device enrollment reference model; no auth or transport.

All mutating methods are trusted host calls. A production host must authenticate
the caller and validate an out-of-band invitation proof before calling ``accept``.
The invitation identifier in these contracts is metadata, not a bearer secret.
"""

from typing import Literal, TypeVar

from pydantic import TypeAdapter

from common.base import Contract, Symbol
from common.enrollment import (
    BridgeBinding,
    BridgeDevice,
    BridgeExecutionSubject,
    Invitation,
    PlatformUser,
)
from workflow.host_bridge import BridgeRegistration

EnrollmentErrorCode = Literal[
    "not_administrator",
    "duplicate_invitation",
    "invitation_missing",
    "invitation_used",
    "invitation_actor_mismatch",
    "user_missing",
    "user_disabled",
    "duplicate_device",
    "device_missing",
    "device_disabled",
    "advertisement_identity_mismatch",
    "binding_forbidden",
    "duplicate_binding",
    "company_device_single_user",
]


class EnrollmentError(Exception):
    def __init__(self, code: EnrollmentErrorCode) -> None:
        self.code: EnrollmentErrorCode = TypeAdapter(EnrollmentErrorCode).validate_python(code)
        super().__init__(self.code)


ContractT = TypeVar("ContractT", bound=Contract)


def _copy(item: ContractT) -> ContractT:
    return item.model_copy(deep=True)


class InMemoryEnrollmentRegistry:
    """Side-effect-free reference for invitation and Bridge membership rules."""

    def __init__(self, *, administrators: tuple[Symbol, ...]) -> None:
        checked = tuple(TypeAdapter(Symbol).validate_python(item) for item in administrators)
        if not checked or len(checked) != len(set(checked)):
            raise ValueError("administrators must be non-empty and unique")
        self._administrators = frozenset(checked)
        self._invitations: dict[str, Invitation] = {}
        self._users: dict[str, PlatformUser] = {}
        self._devices: dict[str, BridgeDevice] = {}
        self._advertisements: dict[str, BridgeRegistration] = {}
        self._bindings: dict[tuple[str, str], BridgeBinding] = {}

    def _admin(self, actor: str) -> None:
        if actor not in self._administrators:
            raise EnrollmentError("not_administrator")

    def issue(self, invitation: Invitation) -> Invitation:
        item = Invitation.model_validate(invitation).model_copy(deep=True)
        self._admin(item.issued_by)
        if item.status != "pending":
            raise EnrollmentError("invitation_used")
        if (
            item.invitation_id in self._invitations
            or item.actor in self._users
            or any(existing.actor == item.actor for existing in self._invitations.values())
        ):
            raise EnrollmentError("duplicate_invitation")
        self._invitations[item.invitation_id] = item
        return _copy(item)

    def invitation(self, invitation_id: Symbol) -> Invitation:
        key = TypeAdapter(Symbol).validate_python(invitation_id)
        item = self._invitations.get(key)
        if item is None:
            raise EnrollmentError("invitation_missing")
        return _copy(item)

    def accept(self, invitation_id: Symbol, actor: Symbol) -> PlatformUser:
        key = TypeAdapter(Symbol).validate_python(invitation_id)
        checked_actor = TypeAdapter(Symbol).validate_python(actor)
        item = self._invitations.get(key)
        if item is None:
            raise EnrollmentError("invitation_missing")
        if item.status != "pending":
            raise EnrollmentError("invitation_used")
        if item.actor != checked_actor:
            raise EnrollmentError("invitation_actor_mismatch")
        user = PlatformUser(actor=checked_actor, invitation_id=key, groups=item.groups)
        accepted = Invitation.model_validate(
            {**item.model_dump(), "status": "accepted", "accepted_by": checked_actor}
        )
        self._invitations = {**self._invitations, key: accepted}
        self._users = {**self._users, checked_actor: user}
        return _copy(user)

    def user(self, actor: Symbol) -> PlatformUser:
        """The platform's own record of one member, including the groups the
        accepted invitation granted. Entitlement is decided from this."""
        key = TypeAdapter(Symbol).validate_python(actor)
        item = self._users.get(key)
        if item is None:
            raise EnrollmentError("user_missing")
        return _copy(item)

    def register_device(
        self, device: BridgeDevice, advertisement: BridgeRegistration
    ) -> BridgeDevice:
        item = BridgeDevice.model_validate(device).model_copy(deep=True)
        advert = BridgeRegistration.model_validate(advertisement).model_copy(deep=True)
        user = self._users.get(item.registered_by)
        if user is None:
            raise EnrollmentError("user_missing")
        if user.status != "active":
            raise EnrollmentError("user_disabled")
        if item.bridge_id in self._devices:
            raise EnrollmentError("duplicate_device")
        if advert.bridge_id != item.bridge_id or advert.owner_id != item.registered_by:
            raise EnrollmentError("advertisement_identity_mismatch")
        self._devices = {**self._devices, item.bridge_id: item}
        self._advertisements = {**self._advertisements, item.bridge_id: advert}
        return _copy(item)

    def device(self, bridge_id: Symbol) -> BridgeDevice:
        key = TypeAdapter(Symbol).validate_python(bridge_id)
        item = self._devices.get(key)
        if item is None:
            raise EnrollmentError("device_missing")
        return _copy(item)

    def advertisement(self, bridge_id: Symbol) -> BridgeRegistration:
        """What this device said it can run when it enrolled. It is the
        device's own claim, not an authorization: what a member may run is
        decided separately and enforced by the Bridge policy."""
        key = TypeAdapter(Symbol).validate_python(bridge_id)
        item = self._advertisements.get(key)
        if item is None:
            raise EnrollmentError("device_missing")
        return _copy(item)

    def _may_administer(self, requested_by: str, device: BridgeDevice) -> bool:
        if requested_by in self._administrators:
            return True
        user = self._users.get(requested_by)
        if user is None or user.status != "active":
            return False
        if requested_by == device.registered_by:
            return True
        existing = self._bindings.get((device.bridge_id, requested_by))
        return (
            existing is not None and existing.status == "active" and existing.role == "device_admin"
        )

    def bind(self, requested_by: Symbol, binding: BridgeBinding) -> BridgeBinding:
        requester = TypeAdapter(Symbol).validate_python(requested_by)
        item = BridgeBinding.model_validate(binding).model_copy(deep=True)
        device = self._devices.get(item.bridge_id)
        if device is None:
            raise EnrollmentError("device_missing")
        if device.status != "active":
            raise EnrollmentError("device_disabled")
        if not self._may_administer(requester, device):
            raise EnrollmentError("binding_forbidden")
        user = self._users.get(item.actor)
        if user is None:
            raise EnrollmentError("user_missing")
        if user.status != "active":
            raise EnrollmentError("user_disabled")
        key = (item.bridge_id, item.actor)
        if key in self._bindings:
            raise EnrollmentError("duplicate_binding")
        active = [
            current
            for current in self._bindings.values()
            if current.bridge_id == item.bridge_id and current.status == "active"
        ]
        if device.device_kind == "company_workstation" and active:
            raise EnrollmentError("company_device_single_user")
        if item.role == "device_admin" and item.actor != device.registered_by:
            raise EnrollmentError("binding_forbidden")
        self._bindings = {**self._bindings, key: item}
        return _copy(item)

    def members(self, bridge_id: Symbol) -> tuple[BridgeBinding, ...]:
        key = TypeAdapter(Symbol).validate_python(bridge_id)
        if key not in self._devices:
            raise EnrollmentError("device_missing")
        return tuple(
            _copy(item)
            for item in self._bindings.values()
            if item.bridge_id == key and item.status == "active"
        )

    def admit(self, subject: BridgeExecutionSubject) -> bool:
        item = BridgeExecutionSubject.model_validate(subject)
        user = self._users.get(item.actor)
        device = self._devices.get(item.bridge_id)
        binding = self._bindings.get((item.bridge_id, item.actor))
        return bool(
            user is not None
            and user.status == "active"
            and device is not None
            and device.status == "active"
            and binding is not None
            and binding.status == "active"
        )

    def disable_user(self, requested_by: Symbol, actor: Symbol) -> PlatformUser:
        requester = TypeAdapter(Symbol).validate_python(requested_by)
        self._admin(requester)
        key = TypeAdapter(Symbol).validate_python(actor)
        user = self._users.get(key)
        if user is None:
            raise EnrollmentError("user_missing")
        updated = PlatformUser.model_validate({**user.model_dump(), "status": "disabled"})
        self._users = {**self._users, key: updated}
        return _copy(updated)

    def enable_user(self, requested_by: Symbol, actor: Symbol) -> PlatformUser:
        requester = TypeAdapter(Symbol).validate_python(requested_by)
        self._admin(requester)
        key = TypeAdapter(Symbol).validate_python(actor)
        user = self._users.get(key)
        if user is None:
            raise EnrollmentError("user_missing")
        updated = PlatformUser.model_validate({**user.model_dump(), "status": "active"})
        self._users = {**self._users, key: updated}
        return _copy(updated)

    def disable_device(self, requested_by: Symbol, bridge_id: Symbol) -> BridgeDevice:
        requester = TypeAdapter(Symbol).validate_python(requested_by)
        key = TypeAdapter(Symbol).validate_python(bridge_id)
        device = self._devices.get(key)
        if device is None:
            raise EnrollmentError("device_missing")
        if not self._may_administer(requester, device):
            raise EnrollmentError("binding_forbidden")
        updated = BridgeDevice.model_validate({**device.model_dump(), "status": "disabled"})
        self._devices = {**self._devices, key: updated}
        return _copy(updated)
