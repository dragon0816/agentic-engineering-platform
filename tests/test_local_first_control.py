"""Local Registry installation and shared-test remote-control contracts."""

import hashlib
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from pydantic import ValidationError

from common.assets import AssetIdentity, AssetMetadata, Owner, PackageMetadata
from common.distribution import (
    BridgeStateSnapshot,
    InstallationPlan,
    LocalRunSummary,
    PublishedAssetPackage,
    RemoteWorkflowJob,
)
from common.enrollment import BridgeDevice
from common.execution import ExecutionAuthorization, TraceIdentifiers
from control_plane.distribution import (
    ControlError,
    InMemoryLocalInventory,
    InMemoryPackageRegistry,
    InMemoryRemoteControl,
)

NOW = datetime(2026, 9, 22, 8, 0, tzinfo=UTC)


def identity(name: str = "report-workflow") -> AssetIdentity:
    return AssetIdentity(namespace="engineering", name=name, version="1.0.0")


def package(name: str = "report-workflow", payload: bytes = b"package") -> PublishedAssetPackage:
    return PublishedAssetPackage(
        kind="workflow",
        metadata=AssetMetadata(
            identity=identity(name),
            owner=Owner(type="team", id="engineering"),
            visibility="organization",
            lifecycle="published",
            package=PackageMetadata(
                artifact_ref=f"registry://engineering/{name}/1.0.0",
                sha256=hashlib.sha256(payload).hexdigest(),
            ),
        ),
    )


def device(kind: str) -> BridgeDevice:
    if kind == "company_workstation":
        return BridgeDevice(
            bridge_id="bridge-company",
            registered_by="engineer-a",
            device_kind="company_workstation",
            windows_account_mode="dedicated_user",
            resource_scope="corporate_internal",
            local_isolation="single_user",
        )
    return BridgeDevice(
        bridge_id="bridge-shared",
        registered_by="engineer-a",
        device_kind="shared_test_workstation",
        windows_account_mode="shared_user",
        resource_scope="external_only",
        local_isolation="cooperative_workspace",
    )


def trace() -> TraceIdentifiers:
    return TraceIdentifiers(trace_id="trace-1", request_id="request-1", span_id="span-1")


def remote_job(**changes: Any) -> RemoteWorkflowJob:
    values = dict(changes)
    workflow = identity()
    request_trace = trace()
    actor = values.pop("actor", "engineer-a")
    bridge_id = values.pop("bridge_id", "bridge-shared")
    authorization = values.pop(
        "authorization",
        ExecutionAuthorization(
            allowed=True,
            actor=actor,
            asset=workflow,
            trace=request_trace,
            policy_ref="policy/remote-workflow",
        ),
    )
    return RemoteWorkflowJob.model_validate(
        {
            "job_id": "job-1",
            "ingress": "shared_platform",
            "actor": actor,
            "bridge_id": bridge_id,
            "workflow": workflow,
            "arguments": {"week": "2026-W39"},
            "trace": request_trace,
            "authorization": authorization,
            **values,
        }
    )


def test_registry_package_requires_published_exact_artifact_without_secrets() -> None:
    item = package()
    assert item.metadata.package is not None
    assert item.metadata.package.sha256 == hashlib.sha256(b"package").hexdigest()
    with pytest.raises(ValidationError):
        PublishedAssetPackage.model_validate(
            {**item.model_dump(), "metadata": {**item.metadata.model_dump(), "package": None}}
        )
    with pytest.raises(ValidationError):
        PublishedAssetPackage.model_validate(
            {
                **item.model_dump(),
                "metadata": {**item.metadata.model_dump(), "lifecycle": "validated"},
            }
        )
    with pytest.raises(ValidationError):
        PublishedAssetPackage.model_validate(
            {
                **item.model_dump(),
                "metadata": {
                    **item.metadata.model_dump(),
                    "package": {
                        "artifact_ref": "https://host/file?access_token=synthetic",
                        "sha256": "0" * 64,
                    },
                },
            }
        )


def test_published_package_plans_install_but_grants_no_execution() -> None:
    registry = InMemoryPackageRegistry()
    registry.publish(package())
    assert registry.discover(namespace="engineering") == (package(),)
    plan = registry.plan(actor="engineer-a", bridge_id="bridge-company", requested=(identity(),))
    assert plan.packages == (package(),)
    assert not hasattr(plan, "authorization")
    assert not hasattr(plan, "execute")


def test_verified_install_is_atomic_and_inventory_remains_local() -> None:
    registry = InMemoryPackageRegistry()
    first = package()
    second = package("release-workflow", b"release")
    registry.publish(first)
    registry.publish(second)
    plan = registry.plan(
        actor="engineer-a",
        bridge_id="bridge-company",
        requested=(first.metadata.identity, second.metadata.identity),
    )
    local = InMemoryLocalInventory(bridge_id="bridge-company")
    with pytest.raises(ControlError, match="artifact_hash_mismatch"):
        local.apply(plan, {"registry://engineering/report-workflow/1.0.0": b"wrong"})
    assert local.installed() == ()
    local.apply(
        plan,
        {
            "registry://engineering/report-workflow/1.0.0": b"package",
            "registry://engineering/release-workflow/1.0.0": b"release",
        },
    )
    assert [item.identity.name for item in local.installed()] == [
        "release-workflow",
        "report-workflow",
    ]
    del registry
    assert len(local.installed()) == 2


def test_bridge_snapshot_is_local_authority_and_projection_becomes_stale() -> None:
    snapshot = BridgeStateSnapshot(
        device=device("shared_test_workstation"),
        observed_at=NOW,
        installed=(),
        runs=(
            LocalRunSummary(
                run_id="run-1",
                actor="engineer-a",
                workflow=identity(),
                status="running",
                updated_at=NOW,
            ),
        ),
    )
    control = InMemoryRemoteControl()
    control.report(snapshot, received_at=NOW)
    assert control.view("bridge-shared", now=NOW + timedelta(seconds=20)).connectivity == ("online")
    stale = control.view("bridge-shared", now=NOW + timedelta(seconds=61))
    assert stale.connectivity == "stale"
    assert stale.snapshot.authority == "bridge"
    assert stale.snapshot.runs[0].status == "running"


def test_remote_job_requires_matching_authorization_and_contains_no_secret_or_shell() -> None:
    with pytest.raises(ValidationError):
        remote_job(
            authorization=ExecutionAuthorization(
                allowed=True,
                actor="engineer-b",
                asset=identity(),
                trace=trace(),
                policy_ref="policy/remote-workflow",
            )
        )
    with pytest.raises(ValidationError):
        remote_job(arguments={"access_token": "synthetic"})
    with pytest.raises(ValidationError):
        RemoteWorkflowJob.model_validate({**remote_job().model_dump(), "command": "whoami"})


def test_remote_control_enforces_company_owner_and_shared_membership_across_ingress() -> None:
    admitted = {
        ("bridge-company", "engineer-a"),
        ("bridge-company", "engineer-b"),
        ("bridge-shared", "engineer-a"),
        ("bridge-shared", "engineer-b"),
    }
    control = InMemoryRemoteControl(
        admission=lambda subject: (subject.bridge_id, subject.actor) in admitted
    )
    company_record = control.submit(
        remote_job(bridge_id="bridge-company", ingress="telegram"),
        device("company_workstation"),
    )
    assert company_record.request.ingress == "telegram"
    with pytest.raises(ControlError, match="company_owner_required"):
        control.submit(
            remote_job(job_id="job-other", actor="engineer-b", bridge_id="bridge-company"),
            device("company_workstation"),
        )
    shared_record = control.submit(
        remote_job(job_id="job-shared", actor="engineer-b"),
        device("shared_test_workstation"),
    )
    assert shared_record.request.actor == "engineer-b"
    with pytest.raises(ControlError, match="subject_not_admitted"):
        control.submit(
            remote_job(job_id="job-unbound", actor="engineer-c"),
            device("shared_test_workstation"),
        )
    assert control.poll("bridge-shared", limit=1) == (shared_record,)
    assert control.poll("bridge-company", limit=1) == (company_record,)
    cancelled = control.cancel("job-shared", actor="engineer-b")
    assert cancelled.status == "cancel_requested"
    assert cancelled.request.actor == "engineer-b"
    with pytest.raises(ControlError, match="job_actor_mismatch"):
        control.cancel("job-shared", actor="engineer-a")


def test_installation_plan_and_snapshots_reject_ambiguous_duplicates() -> None:
    item = package()
    with pytest.raises(ValidationError):
        InstallationPlan(
            actor="engineer-a",
            bridge_id="bridge-company",
            packages=(item, item),
        )
    run = LocalRunSummary(
        run_id="run-1",
        actor="engineer-a",
        workflow=identity(),
        status="running",
        updated_at=NOW,
    )
    with pytest.raises(ValidationError):
        BridgeStateSnapshot(
            device=device("shared_test_workstation"),
            observed_at=NOW,
            runs=(run, run),
        )
