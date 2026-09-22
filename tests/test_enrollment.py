"""Phase 7 invitation and Bridge-enrollment contracts; no authentication server."""

from typing import Any

import pytest
from pydantic import ValidationError

from common.enrollment import (
    BridgeBinding,
    BridgeDevice,
    BridgeExecutionSubject,
    Invitation,
)
from control_plane.enrollment import EnrollmentError, InMemoryEnrollmentRegistry
from workflow.host_bridge import BridgeRegistration


def invite(**changes: Any) -> Invitation:
    return Invitation.model_validate(
        {
            "invitation_id": "invite-1",
            "actor": "engineer-a",
            "issued_by": "platform-admin",
            **changes,
        }
    )


def company_device(**changes: Any) -> BridgeDevice:
    return BridgeDevice.model_validate(
        {
            "bridge_id": "bridge-company-a",
            "registered_by": "engineer-a",
            "device_kind": "company_workstation",
            "windows_account_mode": "dedicated_user",
            "resource_scope": "corporate_internal",
            "local_isolation": "single_user",
            "interactive_slots": 1,
            **changes,
        }
    )


def shared_device(**changes: Any) -> BridgeDevice:
    return BridgeDevice.model_validate(
        {
            "bridge_id": "bridge-shared-test",
            "registered_by": "engineer-a",
            "device_kind": "shared_test_workstation",
            "windows_account_mode": "shared_user",
            "resource_scope": "external_only",
            "local_isolation": "cooperative_workspace",
            "interactive_slots": 1,
            **changes,
        }
    )


def registration(device: BridgeDevice) -> BridgeRegistration:
    return BridgeRegistration.model_validate(
        {
            "bridge_id": device.bridge_id,
            "owner_id": device.registered_by,
            "trace": {"trace_id": "trace-1", "request_id": "request-1", "span_id": "span-1"},
        }
    )


def registry_with(*actors: str) -> InMemoryEnrollmentRegistry:
    registry = InMemoryEnrollmentRegistry(administrators=("platform-admin",))
    for index, actor in enumerate(actors, start=1):
        item = invite(invitation_id=f"invite-{index}", actor=actor)
        registry.issue(item)
        registry.accept(item.invitation_id, actor)
    return registry


@pytest.mark.parametrize(
    "changes",
    [
        {"invite_token": "synthetic"},
        {"password": "synthetic"},
        {"status": "active"},
        {"actor": "person with spaces"},
    ],
)
def test_invitation_is_closed_metadata_without_credentials(changes: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        invite(**changes)


@pytest.mark.parametrize(
    "data",
    [
        company_device().model_dump() | {"windows_account_mode": "shared_user"},
        company_device().model_dump() | {"resource_scope": "external_only"},
        company_device().model_dump() | {"local_isolation": "cooperative_workspace"},
        shared_device().model_dump() | {"windows_account_mode": "dedicated_user"},
        shared_device().model_dump() | {"resource_scope": "corporate_internal"},
        shared_device().model_dump() | {"local_isolation": "single_user"},
        shared_device().model_dump() | {"interactive_slots": 2},
    ],
)
def test_device_profiles_fail_closed(data: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        BridgeDevice.model_validate(data)


def test_invitation_is_issued_by_admin_and_accepted_once_for_named_actor() -> None:
    registry = InMemoryEnrollmentRegistry(administrators=("platform-admin",))
    with pytest.raises(EnrollmentError, match="not_administrator"):
        registry.issue(invite(issued_by="other"))
    issued = registry.issue(invite())
    assert issued.status == "pending"
    with pytest.raises(EnrollmentError, match="duplicate_invitation"):
        registry.issue(invite(invitation_id="invite-other"))
    with pytest.raises(EnrollmentError, match="invitation_actor_mismatch"):
        registry.accept(issued.invitation_id, "engineer-b")
    user = registry.accept(issued.invitation_id, "engineer-a")
    assert user.actor == "engineer-a" and user.status == "active"
    assert registry.invitation(issued.invitation_id).status == "accepted"
    with pytest.raises(EnrollmentError, match="invitation_used"):
        registry.accept(issued.invitation_id, "engineer-a")


def test_company_bridge_has_exactly_one_active_member() -> None:
    registry = registry_with("engineer-a", "engineer-b")
    registry.register_device(company_device(), registration(company_device()))
    first = BridgeBinding(bridge_id="bridge-company-a", actor="engineer-a", role="device_admin")
    registry.bind("engineer-a", first)
    assert registry.admit(BridgeExecutionSubject(actor="engineer-a", bridge_id="bridge-company-a"))
    with pytest.raises(EnrollmentError, match="company_device_single_user"):
        registry.bind(
            "engineer-a",
            BridgeBinding(bridge_id="bridge-company-a", actor="engineer-b", role="operator"),
        )


def test_shared_bridge_accepts_multiple_platform_users_with_distinct_subjects() -> None:
    registry = registry_with("engineer-a", "engineer-b")
    device = shared_device()
    registry.register_device(device, registration(device))
    for actor, role in (("engineer-a", "device_admin"), ("engineer-b", "operator")):
        registry.bind(
            "engineer-a", BridgeBinding(bridge_id=device.bridge_id, actor=actor, role=role)
        )
        assert registry.admit(BridgeExecutionSubject(actor=actor, bridge_id=device.bridge_id))
    assert registry.members(device.bridge_id) == (
        BridgeBinding(bridge_id=device.bridge_id, actor="engineer-a", role="device_admin"),
        BridgeBinding(bridge_id=device.bridge_id, actor="engineer-b", role="operator"),
    )
    assert not registry.admit(
        BridgeExecutionSubject(actor="engineer-c", bridge_id=device.bridge_id)
    )


def test_registration_must_match_enrolled_device_and_contains_no_authority() -> None:
    registry = registry_with("engineer-a")
    device = shared_device()
    wrong = BridgeRegistration.model_validate(
        {**registration(device).model_dump(), "owner_id": "somebody-else"}
    )
    with pytest.raises(EnrollmentError, match="advertisement_identity_mismatch"):
        registry.register_device(device, wrong)
    saved = registry.register_device(device, registration(device))
    assert saved.bridge_id == device.bridge_id
    assert not hasattr(saved, "permissions")
    assert not hasattr(saved, "execute")


def test_users_and_devices_are_disabled_independently_at_use_time() -> None:
    registry = registry_with("engineer-a")
    device = shared_device()
    registry.register_device(device, registration(device))
    registry.bind(
        "engineer-a",
        BridgeBinding(bridge_id=device.bridge_id, actor="engineer-a", role="device_admin"),
    )
    subject = BridgeExecutionSubject(actor="engineer-a", bridge_id=device.bridge_id)
    registry.disable_user("platform-admin", "engineer-a")
    assert not registry.admit(subject)
    registry.enable_user("platform-admin", "engineer-a")
    assert registry.admit(subject)
    registry.disable_device("engineer-a", device.bridge_id)
    assert not registry.admit(subject)


def test_registry_returns_isolated_serializable_snapshots() -> None:
    registry = registry_with("engineer-a")
    device = shared_device()
    registry.register_device(device, registration(device))
    snapshot = registry.device(device.bridge_id)
    assert BridgeDevice.model_validate_json(snapshot.model_dump_json()) == snapshot
    object.__setattr__(snapshot, "status", "disabled")
    assert registry.device(device.bridge_id).status == "active"


def test_binding_does_not_authorize_capabilities_or_resolve_secrets() -> None:
    binding = BridgeBinding(bridge_id="bridge-shared-test", actor="engineer-a", role="operator")
    assert not hasattr(binding, "permissions")
    assert not hasattr(binding, "capabilities")
    assert not hasattr(binding, "secrets")
    with pytest.raises(ValidationError):
        BridgeBinding.model_validate({**binding.model_dump(), "permissions": ["release.push"]})
