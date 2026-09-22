"""A member decides what their devices may run, and nobody decides for them.

Requirements: `docs/phases/PHASE_7_MIGRATION.md`, slice 2g. Everything here is
the shared platform's own reference model: no Bridge is contacted, no socket
is opened, and no asset is executed.
"""

import hashlib
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from pydantic import ValidationError

from capabilities.contracts import CapabilitySpec
from common.assets import AssetIdentity, AssetMetadata, Owner, PackageMetadata
from common.authorization import DeviceAssetSelection, DeviceAuthorization
from common.distribution import AssetKind, PublishedAssetPackage
from common.enrollment import BridgeBinding, BridgeDevice, Invitation
from common.execution import TraceIdentifiers
from control_plane.authorization import AuthorizationError, InMemoryAuthorizationRegistry
from control_plane.distribution import InMemoryPackageRegistry
from control_plane.enrollment import InMemoryEnrollmentRegistry
from workflow.host_bridge import BridgeRegistration

NOW = datetime(2026, 9, 22, 12, 0, tzinfo=UTC)
REPORT = AssetIdentity(namespace="engineering", name="weekly-report", version="1.0.0")
SHIPMENT = AssetIdentity(namespace="engineering", name="shipment-skill", version="1.0.0")
READ = AssetIdentity(namespace="filesystem", name="read-file", version="1.0.0")
PUBLISH = AssetIdentity(namespace="engineering", name="publish-artifact", version="1.0.0")
ABSENT = AssetIdentity(namespace="engineering", name="not-here", version="1.0.0")


def spec(
    identity: AssetIdentity, side_effect: str, approval: bool, permission: str
) -> CapabilitySpec:
    return CapabilitySpec.model_validate(
        {
            "identity": identity.model_dump(),
            "name": f"{identity.namespace}.{identity.name}",
            "description": f"Inert {identity.name} used by the authorization reference",
            "input_contract": f"{identity.namespace}.{identity.name}.input.v1",
            "output_contract": f"{identity.namespace}.{identity.name}.output.v1",
            "side_effect": side_effect,
            "policy": {
                "approval_required": approval,
                "required_permissions": [permission],
                "policy_refs": [f"{identity.name}-policy"],
            },
        }
    )


def read_tool() -> CapabilitySpec:
    return spec(READ, "read", False, "filesystem.read")


def publish_tool() -> CapabilitySpec:
    return spec(PUBLISH, "external_side_effect", True, "engineering.publish")


def device(kind: str) -> BridgeDevice:
    profile = {
        "company_workstation": (
            "bridge-company",
            "dedicated_user",
            "corporate_internal",
            "single_user",
        ),
        "shared_test_workstation": (
            "bridge-shared",
            "shared_user",
            "external_only",
            "cooperative_workspace",
        ),
    }[kind]
    return BridgeDevice.model_validate(
        {
            "bridge_id": profile[0],
            "registered_by": "engineer",
            "device_kind": kind,
            "windows_account_mode": profile[1],
            "resource_scope": profile[2],
            "local_isolation": profile[3],
        }
    )


def package(identity: AssetIdentity, kind: AssetKind) -> PublishedAssetPackage:
    payload = identity.name.encode()
    return PublishedAssetPackage(
        kind=kind,
        metadata=AssetMetadata(
            identity=identity,
            owner=Owner(type="team", id="engineering"),
            visibility="organization",
            lifecycle="published",
            package=PackageMetadata(
                artifact_ref=f"registry://{identity.namespace}/{identity.name}/{identity.version}",
                sha256=hashlib.sha256(payload).hexdigest(),
            ),
        ),
    )


def platform() -> tuple[
    InMemoryEnrollmentRegistry, InMemoryPackageRegistry, InMemoryAuthorizationRegistry
]:
    """An invitation-only platform with one company and one shared device,
    both advertising the two tools, and two published assets."""
    enrollment = InMemoryEnrollmentRegistry(administrators=("platform-admin",))
    for actor in ("engineer", "tester"):
        enrollment.issue(
            Invitation(invitation_id=f"invite-{actor}", actor=actor, issued_by="platform-admin")
        )
        enrollment.accept(f"invite-{actor}", actor)
    for kind in ("company_workstation", "shared_test_workstation"):
        described = device(kind)
        enrollment.register_device(
            described,
            BridgeRegistration(
                bridge_id=described.bridge_id,
                owner_id="engineer",
                trace=TraceIdentifiers(trace_id="t", request_id="r", span_id="s"),
                capabilities=(read_tool(), publish_tool()),
            ),
        )
        enrollment.bind(
            "engineer",
            BridgeBinding(bridge_id=described.bridge_id, actor="engineer", role="device_admin"),
        )
    enrollment.bind(
        "engineer", BridgeBinding(bridge_id="bridge-shared", actor="tester", role="operator")
    )
    packages = InMemoryPackageRegistry()
    packages.publish(package(REPORT, "workflow"))
    packages.publish(package(SHIPMENT, "skill"))
    return enrollment, packages, InMemoryAuthorizationRegistry(enrollment, packages)


def selection(**changes: Any) -> DeviceAssetSelection:
    return DeviceAssetSelection.model_validate(
        {
            "bridge_id": "bridge-company",
            "actor": "engineer",
            "kind": "workflow",
            "asset": REPORT.model_dump(),
            "decided_at": NOW,
            **changes,
        }
    )


def tool(**changes: Any) -> DeviceAssetSelection:
    return selection(**{"kind": "capability", "asset": READ.model_dump(), **changes})


def test_a_selection_names_an_asset_and_never_a_permission() -> None:
    # What a member may do is the capability's own declaration, so there is
    # nowhere in a decision to write a permission or a policy reference.
    for field in ("permissions", "policy_refs", "side_effect"):
        with pytest.raises(ValidationError):
            DeviceAssetSelection.model_validate({**selection().model_dump(), field: ["anything"]})
    with pytest.raises(ValidationError, match="names the member who gave it"):
        tool(approval_ref="release-approval")
    with pytest.raises(ValidationError, match="names the member who gave it"):
        tool(approved_by="engineer")
    with pytest.raises(ValidationError, match="only a tool selection"):
        selection(approval_ref="release-approval", approved_by="engineer")
    with pytest.raises(ValidationError):
        selection(approval_ref="password: hunter2", approved_by="engineer", kind="capability")
    assert selection().key == ("bridge-company", "engineer", REPORT.key)


def test_an_authorization_carries_the_decisions_in_force_for_its_own_device() -> None:
    with pytest.raises(ValidationError, match="its own device"):
        DeviceAuthorization(bridge_id="bridge-other", issued_at=NOW, selections=(selection(),))
    with pytest.raises(ValidationError, match="decides once about an asset"):
        DeviceAuthorization(
            bridge_id="bridge-company", issued_at=NOW, selections=(selection(), selection())
        )
    with pytest.raises(ValidationError, match="decisions in force"):
        DeviceAuthorization(
            bridge_id="bridge-company", issued_at=NOW, selections=(selection(status="revoked"),)
        )
    with pytest.raises(ValidationError, match="cannot be newer"):
        DeviceAuthorization(
            bridge_id="bridge-company",
            issued_at=NOW,
            selections=(selection(decided_at=NOW + timedelta(minutes=1)),),
        )
    bundle = DeviceAuthorization(
        bridge_id="bridge-company",
        issued_at=NOW,
        selections=(selection(), tool(), selection(kind="skill", asset=SHIPMENT.model_dump())),
    )
    assert [item.asset.name for item in bundle.installable()] == ["weekly-report", "shipment-skill"]
    assert [item.asset.name for item in bundle.tools()] == ["read-file"]
    assert bundle.allows("workflow", REPORT) and not bundle.allows("skill", REPORT)
    assert len(bundle.for_actor("engineer")) == 3 and bundle.for_actor("tester") == ()


def test_only_a_bound_member_decides_and_only_about_what_exists() -> None:
    _, _, registry = platform()
    # The tester is a member of the shared device, not the company one.
    with pytest.raises(AuthorizationError, match="actor_not_admitted"):
        registry.select(selection(actor="tester"))
    with pytest.raises(AuthorizationError, match="actor_not_admitted"):
        registry.select(selection(actor="stranger", bridge_id="bridge-shared"))
    with pytest.raises(AuthorizationError, match="asset_not_published"):
        registry.select(selection(asset=ABSENT.model_dump()))
    # The Registry published it as a workflow, so it cannot be chosen as a skill.
    with pytest.raises(AuthorizationError, match="kind_mismatch"):
        registry.select(selection(kind="skill"))
    # A device says what tools it has; a member cannot choose one it lacks.
    with pytest.raises(AuthorizationError, match="tool_not_advertised"):
        registry.select(tool(asset=ABSENT.model_dump()))
    recorded = registry.select(selection())
    assert recorded.status == "active"
    with pytest.raises(AuthorizationError, match="duplicate_selection"):
        registry.select(selection())


def test_a_tool_that_requires_approval_needs_one_from_a_member() -> None:
    _, _, registry = platform()
    publish = tool(asset=PUBLISH.model_dump())
    with pytest.raises(AuthorizationError, match="approval_required"):
        registry.select(publish)
    with pytest.raises(AuthorizationError, match="approver_not_member"):
        registry.select(
            publish.model_copy(
                update={"approval_ref": "release-approval", "approved_by": "stranger"}
            )
        )
    # On a company workstation the one member is the owner, so the owner
    # approves their own irreversible tool and the record says who and when.
    approved = registry.select(
        publish.model_copy(update={"approval_ref": "release-approval", "approved_by": "engineer"})
    )
    assert approved.approved_by == "engineer" and approved.decided_at == NOW
    # A tool that needs no approval needs none.
    assert registry.select(tool()).approval_ref is None


def test_a_decision_dated_in_the_future_is_refused_where_it_arrives() -> None:
    """A bundle refuses a decision newer than itself, so one future-dated
    record would leave the device with no authorization at all."""
    _, _, registry = platform()
    later = selection(decided_at=NOW + timedelta(days=1))
    with pytest.raises(AuthorizationError, match="decision_in_future"):
        registry.select(later, now=NOW)
    assert registry.select(later, now=NOW + timedelta(days=2)).decided_at == NOW + timedelta(days=1)
    assert registry.authorization("bridge-company", issued_at=NOW + timedelta(days=2)).selections


def test_a_tool_that_declares_no_policy_cannot_be_granted_to_anybody() -> None:
    """A grant names the policy it was made under. A capability that declares
    none is refused when it is chosen, rather than breaking the whole
    device's authorization when the grants are derived."""
    enrollment = InMemoryEnrollmentRegistry(administrators=("platform-admin",))
    enrollment.issue(
        Invitation(invitation_id="invite-engineer", actor="engineer", issued_by="platform-admin")
    )
    enrollment.accept("invite-engineer", "engineer")
    described = device("company_workstation")
    unpolicied = CapabilitySpec.model_validate(
        {
            **read_tool().model_dump(),
            "policy": {"approval_required": False, "required_permissions": [], "policy_refs": []},
        }
    )
    enrollment.register_device(
        described,
        BridgeRegistration(
            bridge_id=described.bridge_id,
            owner_id="engineer",
            trace=TraceIdentifiers(trace_id="t", request_id="r", span_id="s"),
            capabilities=(unpolicied,),
        ),
    )
    enrollment.bind(
        "engineer",
        BridgeBinding(bridge_id=described.bridge_id, actor="engineer", role="device_admin"),
    )
    registry = InMemoryAuthorizationRegistry(enrollment, InMemoryPackageRegistry())
    with pytest.raises(AuthorizationError, match="tool_not_grantable"):
        registry.select(tool())
    assert registry.grants("bridge-company") == ()


def test_the_grant_comes_from_the_specification_and_not_from_the_decision() -> None:
    _, _, registry = platform()
    registry.select(tool())
    registry.select(
        tool(asset=PUBLISH.model_dump(), approval_ref="release-approval", approved_by="engineer")
    )
    grants = registry.grants("bridge-company")
    assert [item.asset.name for item in grants] == ["publish-artifact", "read-file"]
    publish, read = grants[0], grants[1]
    # Exactly what the capabilities declare, which the member never wrote.
    assert publish.permissions == publish_tool().policy.required_permissions
    assert publish.policy_refs == publish_tool().policy.policy_refs
    assert publish.approval_ref == "release-approval"
    assert read.permissions == read_tool().policy.required_permissions
    assert read.approval_ref is None
    assert all(item.actor == "engineer" for item in grants)
    # A workflow selection is installed, not granted: it adds no grant.
    registry.select(selection())
    assert len(registry.grants("bridge-company")) == 2


def test_two_members_of_a_shared_device_each_decide_for_themselves() -> None:
    _, _, registry = platform()
    registry.select(tool(bridge_id="bridge-shared"))
    registry.select(tool(bridge_id="bridge-shared", actor="tester"))
    registry.select(
        tool(
            bridge_id="bridge-shared",
            asset=PUBLISH.model_dump(),
            approval_ref="release-approval",
            approved_by="engineer",
        )
    )
    grants = registry.grants("bridge-shared")
    # Each member's decision authorizes that member's runs and nobody else's.
    held = {(item.actor, item.asset.name) for item in grants}
    assert held == {
        ("engineer", "read-file"),
        ("engineer", "publish-artifact"),
        ("tester", "read-file"),
    }
    # On a shared device another bound member may be the approver.
    approved = registry.select(
        tool(
            bridge_id="bridge-shared",
            actor="tester",
            asset=PUBLISH.model_dump(),
            approval_ref="release-approval",
            approved_by="engineer",
        )
    )
    assert approved.actor == "tester" and approved.approved_by == "engineer"
    # The company device is untouched by any of it.
    assert registry.grants("bridge-company") == ()
    bundle = registry.authorization("bridge-shared", issued_at=NOW)
    assert bundle.bridge_id == "bridge-shared" and len(bundle.selections) == 4
    assert DeviceAuthorization.model_validate_json(bundle.model_dump_json()) == bundle


def test_revoking_a_decision_removes_its_grant_and_lets_it_be_made_again() -> None:
    _, _, registry = platform()
    registry.select(tool())
    registry.select(selection())
    assert len(registry.grants("bridge-company")) == 1
    revoked = registry.revoke("bridge-company", "engineer", READ)
    assert revoked.status == "revoked"
    assert registry.grants("bridge-company") == ()
    bundle = registry.authorization("bridge-company", issued_at=NOW)
    assert [item.asset.name for item in bundle.selections] == ["weekly-report"]
    with pytest.raises(AuthorizationError, match="selection_missing"):
        registry.revoke("bridge-company", "engineer", READ)
    with pytest.raises(AuthorizationError, match="selection_missing"):
        registry.revoke("bridge-company", "engineer", ABSENT)
    # A member may decide again after changing their mind.
    assert registry.select(tool()).status == "active"
    assert len(registry.grants("bridge-company")) == 1
