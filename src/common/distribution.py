"""Local-first package, Bridge-state and member-scoped remote-job contracts."""

import hashlib
from collections.abc import Collection, Mapping
from typing import Literal, Self

from pydantic import AwareDatetime, JsonValue, model_validator

from common.assets import (
    AssetIdentity,
    AssetMetadata,
    RegistryContract,
    reject_embedded_secrets,
)
from common.base import Contract, Sha256, Symbol
from common.enrollment import BridgeDevice
from common.execution import ExecutionAuthorization, RunStatus, TraceIdentifiers

AssetKind = Literal["task", "workflow", "skill", "knowledge", "agent"]


class PublishedAssetPackage(RegistryContract):
    """Downloadable Registry metadata; discovery grants no execution authority."""

    kind: AssetKind
    metadata: AssetMetadata

    @model_validator(mode="after")
    def downloadable_published_version(self) -> Self:
        if self.metadata.lifecycle != "published":
            raise ValueError("only published assets may be distributed")
        if self.metadata.package is None:
            raise ValueError("distributed assets require an exact package artifact")
        return self


class InstallationPlan(RegistryContract):
    """Exact bytes selected for a local host; this is not authorization."""

    actor: Symbol
    bridge_id: Symbol
    packages: tuple[PublishedAssetPackage, ...]

    @model_validator(mode="after")
    def unambiguous_versions(self) -> Self:
        identities = [item.metadata.identity.key for item in self.packages]
        if not self.packages or len(identities) != len(set(identities)):
            raise ValueError("installation packages must be non-empty and unique")
        return self


class InstalledAsset(Contract):
    identity: AssetIdentity
    kind: AssetKind
    artifact_ref: str
    sha256: Sha256
    installed_by: Symbol


class LocalRunSummary(Contract):
    run_id: Symbol
    actor: Symbol
    workflow: AssetIdentity
    status: RunStatus
    updated_at: AwareDatetime


class BridgeStateSnapshot(Contract):
    """Authoritative state emitted by a Bridge, never reconstructed centrally."""

    authority: Literal["bridge"] = "bridge"
    device: BridgeDevice
    observed_at: AwareDatetime
    installed: tuple[InstalledAsset, ...] = ()
    runs: tuple[LocalRunSummary, ...] = ()

    @model_validator(mode="after")
    def unique_local_state(self) -> Self:
        identities = [item.identity.key for item in self.installed]
        run_ids = [item.run_id for item in self.runs]
        if len(identities) != len(set(identities)) or len(run_ids) != len(set(run_ids)):
            raise ValueError("Bridge snapshot identities must be unique")
        if any(item.updated_at > self.observed_at for item in self.runs):
            raise ValueError("a run update cannot be newer than its Bridge observation")
        return self


class BridgeStatusProjection(Contract):
    """Timestamped shared view; the nested Bridge snapshot remains the evidence."""

    connectivity: Literal["online", "stale"]
    received_at: AwareDatetime
    snapshot: BridgeStateSnapshot

    @model_validator(mode="after")
    def received_after_observation(self) -> Self:
        if self.received_at < self.snapshot.observed_at:
            raise ValueError("a snapshot cannot be received before it was observed")
        return self


class RemoteWorkflowJob(RegistryContract):
    """Governed Workflow request; arbitrary commands have no representation."""

    job_id: Symbol
    ingress: Literal["shared_platform", "telegram"]
    actor: Symbol
    bridge_id: Symbol
    workflow: AssetIdentity
    arguments: dict[Symbol, JsonValue]
    trace: TraceIdentifiers
    authorization: ExecutionAuthorization

    @model_validator(mode="after")
    def matching_runtime_authorization(self) -> Self:
        grant = self.authorization
        if not grant.allowed:
            raise ValueError("remote jobs require an explicit allow decision")
        if grant.actor != self.actor or grant.asset != self.workflow or grant.trace != self.trace:
            raise ValueError("remote job authorization must match actor, workflow and trace")
        reject_embedded_secrets(self.arguments)
        return self


class RemoteJobRecord(Contract):
    request: RemoteWorkflowJob
    status: Literal["queued", "cancel_requested"] = "queued"


LocalStateErrorCode = Literal[
    "installation_bridge_mismatch",
    "artifact_missing",
    "artifact_hash_mismatch",
    "duplicate_install",
    "run_owner_fixed",
    "run_update_stale",
    "unavailable",
]


class LocalStateError(Exception):
    """A local inventory or run-state rule refused a change. The code is the
    whole message: no artifact bytes, path or record is echoed."""

    def __init__(self, code: LocalStateErrorCode) -> None:
        self.code: LocalStateErrorCode = code
        super().__init__(code)


def verify_installation(
    plan: InstallationPlan,
    artifacts: Mapping[str, bytes],
    *,
    bridge_id: str,
    installed: Collection[tuple[str, str, str]],
) -> tuple[InstalledAsset, ...]:
    """The rows an installation would add, or the reason it adds none.

    One rule for every local inventory, in memory or on disk: the plan names
    this Bridge, every artifact is present and matches its declared digest,
    and nothing in it is installed already. The whole plan is checked before
    the first row is returned, so a caller that applies the result applies
    all of it or none."""
    checked = InstallationPlan.model_validate(plan)
    if checked.bridge_id != bridge_id:
        raise LocalStateError("installation_bridge_mismatch")
    present = set(installed)
    added: list[InstalledAsset] = []
    for package in checked.packages:
        metadata = package.metadata
        artifact = metadata.package
        if artifact is None:  # the contract already refuses this; narrowing only
            raise LocalStateError("artifact_missing")
        payload = artifacts.get(artifact.artifact_ref)
        if payload is None:
            raise LocalStateError("artifact_missing")
        if hashlib.sha256(payload).hexdigest() != artifact.sha256:
            raise LocalStateError("artifact_hash_mismatch")
        if metadata.identity.key in present:
            raise LocalStateError("duplicate_install")
        present.add(metadata.identity.key)
        added.append(
            InstalledAsset(
                identity=metadata.identity,
                kind=package.kind,
                artifact_ref=artifact.artifact_ref,
                sha256=artifact.sha256,
                installed_by=checked.actor,
            )
        )
    return tuple(added)
