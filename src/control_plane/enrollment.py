"""Invitation and device enrollment reference model; no auth or transport.

All mutating methods are trusted host calls. A production host must authenticate
the caller and validate an out-of-band invitation proof before calling ``accept``.
The invitation identifier in these contracts is metadata, not a bearer secret.
"""

import secrets
from datetime import UTC, datetime
from typing import Literal, TypeVar

from pydantic import TypeAdapter

from common.base import Contract, Symbol
from common.enrollment import (
    BridgeBinding,
    BridgeDevice,
    BridgeExecutionSubject,
    Invitation,
    PlatformRole,
    PlatformUser,
    PlatformUserChange,
)
from control_plane.identity_store import SqliteIdentityStorage
from workflow.host_bridge import BridgeRegistration

EnrollmentErrorCode = Literal[
    "not_administrator",
    "duplicate_invitation",
    "invitation_missing",
    "invitation_used",
    "invitation_revoked",
    "invitation_actor_mismatch",
    "user_missing",
    "user_disabled",
    "duplicate_device",
    "device_missing",
    "device_disabled",
    "advertisement_identity_mismatch",
    "binding_forbidden",
    "binding_missing",
    "duplicate_binding",
    "device_single_user",
    # Platform overview (owner 2026-10-15): the last platform administrator
    # keeps that role.
    "last_administrator",
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

    def __init__(
        self,
        *,
        administrators: tuple[Symbol, ...],
        storage: SqliteIdentityStorage | None = None,
    ) -> None:
        checked = tuple(TypeAdapter(Symbol).validate_python(item) for item in administrators)
        if not checked or len(checked) != len(set(checked)):
            raise ValueError("administrators must be non-empty and unique")
        self._administrators = frozenset(checked)
        self._storage = storage
        self._invitations = {
            item.invitation_id: item
            for item in (
                Invitation.model_validate_json(raw)
                for raw in (() if storage is None else storage.records("identity_invitations"))
            )
        }
        self._users = {
            item.actor: item
            for item in (
                PlatformUser.model_validate_json(raw)
                for raw in (() if storage is None else storage.records("identity_users"))
            )
        }
        self._devices = {
            item.bridge_id: item
            for item in (
                BridgeDevice.model_validate_json(raw)
                for raw in (() if storage is None else storage.records("identity_devices"))
            )
        }
        self._advertisements = {
            item.bridge_id: item
            for item in (
                BridgeRegistration.model_validate_json(raw)
                for raw in (() if storage is None else storage.records("identity_advertisements"))
            )
        }
        self._user_changes = {
            item.change_id: item
            for item in (
                PlatformUserChange.model_validate_json(raw)
                for raw in (() if storage is None else storage.records("identity_user_changes"))
            )
        }
        self._bindings = {
            (item.bridge_id, item.actor): item
            for item in (
                BridgeBinding.model_validate_json(raw)
                for raw in (() if storage is None else storage.records("identity_bindings"))
            )
        }

    def _save(self, table: str, key: str, item: Contract) -> None:
        if self._storage is not None:
            self._storage.put(table, key, item)

    def _admin(self, actor: str) -> None:
        user = self._users.get(actor)
        if actor not in self._administrators and not (
            user is not None and user.status == "active" and user.role == "platform_admin"
        ):
            raise EnrollmentError("not_administrator")

    def is_administrator(self, actor: Symbol) -> bool:
        try:
            self._admin(TypeAdapter(Symbol).validate_python(actor))
        except EnrollmentError:
            return False
        return True

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
        self._save("identity_invitations", item.invitation_id, item)
        return _copy(item)

    def invitations(self) -> tuple[Invitation, ...]:
        return tuple(_copy(item) for item in self._invitations.values())

    def revoke_invitation(self, requested_by: Symbol, invitation_id: Symbol) -> Invitation:
        self._admin(TypeAdapter(Symbol).validate_python(requested_by))
        key = TypeAdapter(Symbol).validate_python(invitation_id)
        item = self._invitations.get(key)
        if item is None:
            raise EnrollmentError("invitation_missing")
        if item.status != "pending":
            raise EnrollmentError("invitation_used")
        revoked = Invitation.model_validate({**item.model_dump(), "status": "revoked"})
        self._invitations[key] = revoked
        self._save("identity_invitations", key, revoked)
        return _copy(revoked)

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
        user = PlatformUser(
            actor=checked_actor,
            invitation_id=key,
            groups=item.groups,
            role=item.role,
        )
        accepted = Invitation.model_validate(
            {**item.model_dump(), "status": "accepted", "accepted_by": checked_actor}
        )
        self._invitations = {**self._invitations, key: accepted}
        self._users = {**self._users, checked_actor: user}
        self._save("identity_invitations", key, accepted)
        self._save("identity_users", checked_actor, user)
        return _copy(user)

    def user(self, actor: Symbol) -> PlatformUser:
        """The platform's own record of one member, including the groups the
        accepted invitation granted. Entitlement is decided from this."""
        key = TypeAdapter(Symbol).validate_python(actor)
        item = self._users.get(key)
        if item is None:
            raise EnrollmentError("user_missing")
        return _copy(item)

    def users(self) -> tuple[PlatformUser, ...]:
        """Every member who accepted an invitation, for an administrator."""
        return tuple(_copy(item) for item in sorted(
            self._users.values(), key=lambda entry: entry.actor))

    def user_changes(self, actor: Symbol | None = None) -> tuple[PlatformUserChange, ...]:
        """The audit of role and group changes, oldest first."""
        return tuple(
            _copy(item)
            for item in sorted(self._user_changes.values(), key=lambda entry: entry.changed_at)
            if actor is None or item.actor == actor
        )

    def update_user(
        self,
        requested_by: Symbol,
        actor: Symbol,
        *,
        role: PlatformRole,
        groups: tuple[Symbol, ...],
        now: datetime | None = None,
    ) -> PlatformUser:
        """An administrator changes a member's role and groups. Groups decide
        which team-owned names a member manages and which team assets they
        may use, from the next request on. The change is audited, and the
        last active platform administrator cannot lose that role."""
        requester = TypeAdapter(Symbol).validate_python(requested_by)
        self._admin(requester)
        key = TypeAdapter(Symbol).validate_python(actor)
        checked_role: PlatformRole = TypeAdapter(PlatformRole).validate_python(role)
        checked_groups = tuple(
            dict.fromkeys(TypeAdapter(Symbol).validate_python(item) for item in groups)
        )
        user = self._users.get(key)
        if user is None:
            raise EnrollmentError("user_missing")
        if user.role == "platform_admin" and checked_role != "platform_admin":
            others = [
                item for item in self._users.values()
                if item.actor != key and item.role == "platform_admin" and item.status == "active"
            ]
            if not others:
                raise EnrollmentError("last_administrator")
        updated = PlatformUser.model_validate(
            {**user.model_dump(), "role": checked_role, "groups": checked_groups}
        )
        change = PlatformUserChange(
            change_id=f"user-change-{secrets.token_hex(8)}",
            actor=key,
            changed_by=requester,
            changed_at=now if now is not None else datetime.now(UTC),
            role_before=user.role,
            role_after=updated.role,
            groups_before=user.groups,
            groups_after=updated.groups,
        )
        self._users = {**self._users, key: updated}
        self._user_changes = {**self._user_changes, change.change_id: change}
        self._save("identity_users", key, updated)
        self._save("identity_user_changes", change.change_id, change)
        return _copy(updated)

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
        self._save("identity_devices", item.bridge_id, item)
        self._save("identity_advertisements", item.bridge_id, advert)
        return _copy(item)

    def device(self, bridge_id: Symbol) -> BridgeDevice:
        key = TypeAdapter(Symbol).validate_python(bridge_id)
        item = self._devices.get(key)
        if item is None:
            raise EnrollmentError("device_missing")
        return _copy(item)

    def devices(self) -> tuple[BridgeDevice, ...]:
        """Every registered device, for an administrator's list."""
        return tuple(_copy(item) for item in sorted(
            self._devices.values(), key=lambda entry: entry.bridge_id))

    def advertisement(self, bridge_id: Symbol) -> BridgeRegistration:
        """What this device last said it can run. It is the device's own
        claim, not an authorization: what a member may run is decided
        separately and enforced by the Bridge policy."""
        key = TypeAdapter(Symbol).validate_python(bridge_id)
        item = self._advertisements.get(key)
        if item is None:
            raise EnrollmentError("device_missing")
        return _copy(item)

    def advertise(self, bridge_id: Symbol, advertisement: BridgeRegistration) -> BridgeRegistration:
        """Replace what a device says it can run. The same identity rule as
        enrolling: the advertisement names this device and its registering
        owner, so a Bridge cannot describe another machine."""
        key = TypeAdapter(Symbol).validate_python(bridge_id)
        advert = BridgeRegistration.model_validate(advertisement).model_copy(deep=True)
        device = self._devices.get(key)
        if device is None:
            raise EnrollmentError("device_missing")
        if device.status != "active":
            raise EnrollmentError("device_disabled")
        if advert.bridge_id != key or advert.owner_id != device.registered_by:
            raise EnrollmentError("advertisement_identity_mismatch")
        self._advertisements = {**self._advertisements, key: advert}
        self._save("identity_advertisements", key, advert)
        return _copy(advert)

    def may_administer(self, requested_by: Symbol, bridge_id: Symbol) -> bool:
        """Whether this actor may change what happens on that device: a
        platform administrator, the member who registered it, or a bound
        device administrator. Asked by anything that acts on a device's
        records, so one rule answers for all of them."""
        requester = TypeAdapter(Symbol).validate_python(requested_by)
        device = self._devices.get(TypeAdapter(Symbol).validate_python(bridge_id))
        return device is not None and self._may_administer(requester, device)

    def _may_administer(self, requested_by: str, device: BridgeDevice) -> bool:
        if requested_by in self._administrators:
            return True
        user = self._users.get(requested_by)
        if user is None or user.status != "active":
            return False
        if user.role == "platform_admin":
            return True
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
        existing = self._bindings.get(key)
        if existing is not None and existing.status == "active":
            raise EnrollmentError("duplicate_binding")
        # A withdrawn binding is history, not a bar: somebody who was taken
        # off a device can be put back on it.
        active = [
            current
            for current in self._bindings.values()
            if current.bridge_id == item.bridge_id and current.status == "active"
        ]
        if active:
            # One member per machine, whatever its kind. A shared test machine
            # is bound to a virtual member of its own; the employees who need
            # it reach it through an ingress, and no colleague's credential
            # ever sits on it.
            raise EnrollmentError("device_single_user")
        if item.role == "device_admin" and item.actor != device.registered_by:
            raise EnrollmentError("binding_forbidden")
        self._bindings = {**self._bindings, key: item}
        self._save("identity_bindings", f"{item.bridge_id}:{item.actor}", item)
        return _copy(item)

    def unbind(self, requested_by: Symbol, bridge_id: Symbol, actor: Symbol) -> BridgeBinding:
        """Withdraw a member's use of one device. Whoever may bind may also
        unbind; what a withdrawn binding justified stops with it."""
        requester = TypeAdapter(Symbol).validate_python(requested_by)
        key = (
            TypeAdapter(Symbol).validate_python(bridge_id),
            TypeAdapter(Symbol).validate_python(actor),
        )
        device = self._devices.get(key[0])
        if device is None:
            raise EnrollmentError("device_missing")
        if not self._may_administer(requester, device):
            raise EnrollmentError("binding_forbidden")
        current = self._bindings.get(key)
        if current is None or current.status != "active":
            raise EnrollmentError("binding_missing")
        withdrawn = BridgeBinding.model_validate({**current.model_dump(), "status": "revoked"})
        self._bindings = {**self._bindings, key: withdrawn}
        self._save("identity_bindings", f"{key[0]}:{key[1]}", withdrawn)
        return _copy(withdrawn)

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
        self._save("identity_users", key, updated)
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
        self._save("identity_users", key, updated)
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
        self._save("identity_devices", key, updated)
        return _copy(updated)
