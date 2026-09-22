"""Inert references for Registry distribution and member-scoped job control."""

import hashlib
from collections.abc import Callable, Mapping
from datetime import datetime, timedelta
from typing import Literal, TypeVar

from pydantic import TypeAdapter

from common.assets import AssetIdentity
from common.base import Symbol
from common.distribution import (
    BridgeStateSnapshot,
    BridgeStatusProjection,
    InstallationPlan,
    InstalledAsset,
    PublishedAssetPackage,
    RemoteJobRecord,
    RemoteWorkflowJob,
)
from common.enrollment import BridgeDevice, BridgeExecutionSubject

ControlErrorCode = Literal[
    "duplicate_package",
    "package_missing",
    "installation_bridge_mismatch",
    "artifact_missing",
    "artifact_hash_mismatch",
    "duplicate_install",
    "snapshot_missing",
    "snapshot_time_invalid",
    "device_identity_mismatch",
    "device_disabled",
    "company_owner_required",
    "subject_not_admitted",
    "duplicate_job",
    "job_missing",
    "job_actor_mismatch",
]


class ControlError(Exception):
    def __init__(self, code: ControlErrorCode) -> None:
        self.code: ControlErrorCode = TypeAdapter(ControlErrorCode).validate_python(code)
        super().__init__(self.code)


ContractT = TypeVar("ContractT", PublishedAssetPackage, InstalledAsset, RemoteJobRecord)


def _copy(item: ContractT) -> ContractT:
    return item.model_copy(deep=True)


class InMemoryPackageRegistry:
    """Published package metadata only; no downloader and no executable import."""

    def __init__(self) -> None:
        self._packages: dict[tuple[str, str, str], str] = {}

    def publish(self, package: PublishedAssetPackage) -> PublishedAssetPackage:
        item = PublishedAssetPackage.model_validate(package)
        key = item.metadata.identity.key
        if key in self._packages:
            raise ControlError("duplicate_package")
        self._packages[key] = item.model_dump_json()
        return _copy(item)

    def discover(self, *, namespace: str | None = None) -> tuple[PublishedAssetPackage, ...]:
        result = []
        for key in sorted(self._packages):
            item = PublishedAssetPackage.model_validate_json(self._packages[key])
            if namespace is None or item.metadata.identity.namespace == namespace:
                result.append(item)
        return tuple(result)

    def plan(
        self,
        *,
        actor: Symbol,
        bridge_id: Symbol,
        requested: tuple[AssetIdentity, ...],
    ) -> InstallationPlan:
        packages = []
        for requested_identity in requested:
            checked = AssetIdentity.model_validate(requested_identity)
            payload = self._packages.get(checked.key)
            if payload is None:
                raise ControlError("package_missing")
            packages.append(PublishedAssetPackage.model_validate_json(payload))
        return InstallationPlan(actor=actor, bridge_id=bridge_id, packages=tuple(packages))


class InMemoryLocalInventory:
    """Verified local inventory; validates the whole plan before one mutation."""

    def __init__(self, *, bridge_id: Symbol) -> None:
        self.bridge_id = TypeAdapter(Symbol).validate_python(bridge_id)
        self._installed: dict[tuple[str, str, str], InstalledAsset] = {}

    def apply(
        self, plan: InstallationPlan, artifacts: Mapping[str, bytes]
    ) -> tuple[InstalledAsset, ...]:
        checked = InstallationPlan.model_validate(plan)
        if checked.bridge_id != self.bridge_id:
            raise ControlError("installation_bridge_mismatch")
        candidate = dict(self._installed)
        added = []
        for package in checked.packages:
            metadata = package.metadata
            package_metadata = metadata.package
            if package_metadata is None:  # defensive narrowing; contract already refuses this
                raise ControlError("artifact_missing")
            payload = artifacts.get(package_metadata.artifact_ref)
            if payload is None:
                raise ControlError("artifact_missing")
            if hashlib.sha256(payload).hexdigest() != package_metadata.sha256:
                raise ControlError("artifact_hash_mismatch")
            if metadata.identity.key in candidate:
                raise ControlError("duplicate_install")
            installed = InstalledAsset(
                identity=metadata.identity,
                kind=package.kind,
                artifact_ref=package_metadata.artifact_ref,
                sha256=package_metadata.sha256,
                installed_by=checked.actor,
            )
            candidate[metadata.identity.key] = installed
            added.append(installed)
        self._installed = candidate
        return tuple(_copy(item) for item in added)

    def installed(self) -> tuple[InstalledAsset, ...]:
        return tuple(_copy(self._installed[key]) for key in sorted(self._installed))


class InMemoryRemoteControl:
    """Shared status projection and bounded shared-test queue; executes nothing."""

    def __init__(
        self,
        *,
        admission: Callable[[BridgeExecutionSubject], bool] | None = None,
        max_pending_per_bridge: int = 100,
    ) -> None:
        if isinstance(max_pending_per_bridge, bool) or not 1 <= max_pending_per_bridge <= 1000:
            raise ValueError("max_pending_per_bridge must be between 1 and 1000")
        self._max_pending = max_pending_per_bridge
        self._admission = admission or (lambda subject: False)
        self._snapshots: dict[str, tuple[str, datetime]] = {}
        self._jobs: dict[str, RemoteJobRecord] = {}
        self._queues: dict[str, list[str]] = {}

    def report(
        self, snapshot: BridgeStateSnapshot, *, received_at: datetime
    ) -> BridgeStatusProjection:
        item = BridgeStateSnapshot.model_validate(snapshot)
        projection = BridgeStatusProjection(
            connectivity="online", received_at=received_at, snapshot=item
        )
        self._snapshots[item.device.bridge_id] = (item.model_dump_json(), projection.received_at)
        return projection.model_copy(deep=True)

    def view(
        self,
        bridge_id: Symbol,
        *,
        now: datetime,
        stale_after: timedelta = timedelta(seconds=60),
    ) -> BridgeStatusProjection:
        key = TypeAdapter(Symbol).validate_python(bridge_id)
        saved = self._snapshots.get(key)
        if saved is None:
            raise ControlError("snapshot_missing")
        payload, received_at = saved
        if stale_after <= timedelta(0) or now < received_at:
            raise ControlError("snapshot_time_invalid")
        connectivity = "online" if now - received_at <= stale_after else "stale"
        return BridgeStatusProjection(
            connectivity=connectivity,
            received_at=received_at,
            snapshot=BridgeStateSnapshot.model_validate_json(payload),
        )

    def submit(self, job: RemoteWorkflowJob, device: BridgeDevice) -> RemoteJobRecord:
        request = RemoteWorkflowJob.model_validate(job)
        target = BridgeDevice.model_validate(device)
        if target.bridge_id != request.bridge_id:
            raise ControlError("device_identity_mismatch")
        if target.status != "active":
            raise ControlError("device_disabled")
        if target.device_kind == "company_workstation" and request.actor != target.registered_by:
            raise ControlError("company_owner_required")
        subject = BridgeExecutionSubject(actor=request.actor, bridge_id=request.bridge_id)
        if not self._admission(subject):
            raise ControlError("subject_not_admitted")
        if request.job_id in self._jobs:
            raise ControlError("duplicate_job")
        queue = self._queues.setdefault(request.bridge_id, [])
        if len(queue) >= self._max_pending:
            raise ValueError("shared-test queue is full")
        record = RemoteJobRecord(request=request)
        self._jobs[request.job_id] = record
        queue.append(request.job_id)
        return _copy(record)

    def poll(self, bridge_id: Symbol, *, limit: int) -> tuple[RemoteJobRecord, ...]:
        key = TypeAdapter(Symbol).validate_python(bridge_id)
        if isinstance(limit, bool) or not 1 <= limit <= 50:
            raise ValueError("poll limit must be between 1 and 50")
        return tuple(_copy(self._jobs[job_id]) for job_id in self._queues.get(key, [])[:limit])

    def cancel(self, job_id: Symbol, *, actor: Symbol) -> RemoteJobRecord:
        key = TypeAdapter(Symbol).validate_python(job_id)
        checked_actor = TypeAdapter(Symbol).validate_python(actor)
        record = self._jobs.get(key)
        if record is None:
            raise ControlError("job_missing")
        if record.request.actor != checked_actor:
            raise ControlError("job_actor_mismatch")
        updated = RemoteJobRecord(request=record.request, status="cancel_requested")
        self._jobs[key] = updated
        return _copy(updated)
