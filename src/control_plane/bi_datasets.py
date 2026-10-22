"""BI dataset sharing on the Shared Platform (slice 1, owner 2026-10-22).

`docs/proposals/BI_DATASET_SHARING.md` §4, §6, §8.5 and §8.6; contract
`docs/CONTRACTS.md` "BI dataset sharing".

A member publishes an `aep-bi-dataset-snapshot/1` as an immutable package of
kind `bi_dataset`. The platform assigns the version, checks `base_version`
against the highest published one, re-reads the snapshot (digest, strict
shape, secrets: the publishing Agent is not trusted), stamps the publication
and stores the stamped bytes. The first version of a new name waits for an
administrator in the existing review queue (owner Q5); later versions from
the owner, an owning-team member or a co-editor are published directly.

Readers are the owner's team by default; `organization` needs an explicit
confirmation and `public` is never allowed (owner Q4). Who may read follows
the existing entitlement (`entitled_in`), so a member who is removed stops
being offered new versions; the Agent keeps its copy (owner Q2) and learns it
from `status`. Every publish, review, selection, delivery and download is
written to an append-only audit log.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import sqlite3
import threading
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Literal, Self

from pydantic import AwareDatetime, Field, StrictBool, model_validator

# The one place outside the BI package and the Host's BI wiring that names it
# (ADR-K10): the platform reads every snapshot itself rather than trusting the
# publishing Agent, so it uses the same reader the Agent does.
from capabilities.bi_cards.snapshot import (
    MAX_SNAPSHOT_BYTES,
    Publication,
    Snapshot,
    SnapshotError,
    read_snapshot,
    stamp_publication,
)
from common.assets import (
    AssetIdentity,
    AssetMetadata,
    BusinessApproval,
    Owner,
    PackageMetadata,
    Provenance,
    TechnicalPolicy,
)
from common.base import Contract, Sha256, Slug, Symbol, Text
from common.distribution import PublishedAssetPackage
from common.identity import AuthenticatedActor, Visibility
from common.member import AssetSubmission
from common.ownership import VersionChange, highest_version, next_version, version_key
from control_plane.distribution import PackageRegistry, entitled_in
from control_plane.ownership import AssetOwnershipService, OwnershipError

if TYPE_CHECKING:
    from control_plane.submissions import SubmissionStore

KIND = "bi_dataset"
PUBLISH_SOURCE = "bi-dataset-publish"
DIGEST_REF = "bi-snapshot-digest:"
PLATFORM_REVIEWER = "aep-platform"
#: The default `max_bi_dataset_bytes`: the snapshot module's own limit.
DEFAULT_LIMIT = MAX_SNAPSHOT_BYTES
MIN_LIMIT = 1024 * 1024
MAX_LIMIT = 64 * 1024 * 1024
# What base64 and the JSON around the snapshot add to the request body.
BODY_OVERHEAD = 64 * 1024
MAX_STATUS_NAMES = 100

BiDatasetErrorCode = Literal[
    "snapshot_invalid",
    "digest_mismatch",
    "secret_found",
    "artifact_too_large",
    "version_superseded",
    "review_pending",
    "publisher_not_authorized",
    "visibility_not_allowed",
    "organization_unconfirmed",
    "team_required",
    "kind_mismatch",
    "asset_not_published",
    "asset_not_entitled",
    "name_missing",
    "session_expired",
    "actor_unknown",
    "actor_disabled",
    "invalid_request",
]

AuditEvent = Literal[
    "submitted",
    "approved",
    "rejected",
    "withdrawn",
    "published",
    "selected",
    "replaced",
    "revoked",
    "synced",
    "sync_refused",
    "downloaded",
]

_OWNERSHIP_CODES: dict[str, BiDatasetErrorCode] = {
    "session_expired": "session_expired",
    "actor_unknown": "actor_unknown",
    "actor_disabled": "actor_disabled",
    "publisher_not_authorized": "publisher_not_authorized",
    "owner_mismatch": "publisher_not_authorized",
    "version_not_assigned": "version_superseded",
    "version_not_above_highest": "version_superseded",
    "duplicate_package": "version_superseded",
}


_DECISION_EVENTS: dict[str, AuditEvent] = {
    "approved": "approved",
    "rejected": "rejected",
    "withdrawn": "withdrawn",
}


class BiDatasetError(Exception):
    """A refusal. `card` and `field` say where a secret was found; no value
    is ever carried."""

    def __init__(
        self,
        code: BiDatasetErrorCode,
        message: str | None = None,
        *,
        card: str | None = None,
        field: str | None = None,
    ) -> None:
        self.code: BiDatasetErrorCode = code
        self.message = message
        self.card = card
        self.field = field
        super().__init__(code)

    def body(self) -> dict[str, str]:
        reply: dict[str, str] = {"code": self.code}
        if self.message:
            reply["message"] = self.message
        if self.card:
            reply["card"] = self.card
        if self.field:
            reply["field"] = self.field
        return reply


def _snapshot_error(error: SnapshotError) -> BiDatasetError:
    code = _SNAPSHOT_CODES.get(error.code, "snapshot_invalid")
    return BiDatasetError(code, error.message, card=error.card, field=error.field)


_SNAPSHOT_CODES: dict[str, BiDatasetErrorCode] = {
    "snapshot_invalid": "snapshot_invalid",
    "digest_mismatch": "digest_mismatch",
    "secret_found": "secret_found",
    "artifact_too_large": "artifact_too_large",
}


# -- wire contracts ------------------------------------------------------------


class BiDatasetName(Contract):
    namespace: Slug
    name: Slug


class BiDatasetPublishRequest(Contract):
    namespace: Slug
    name: Slug
    base_version: Text | None = None
    note: Text = Field(max_length=500)
    readers: Literal["team", "organization", "private", "public"] | None = None
    confirm_organization: StrictBool = False
    team: Symbol | None = None
    snapshot: str


class BiDatasetPublishReply(Contract):
    status: Literal["published", "pending_review"]
    asset: AssetIdentity
    sha256: Sha256
    digest: Sha256
    size: int
    submission_id: Symbol | None = None


class BiDatasetStatusRequest(Contract):
    names: tuple[BiDatasetName, ...] = Field(min_length=1, max_length=MAX_STATUS_NAMES)


class BiDatasetStatusEntry(Contract):
    namespace: Slug
    name: Slug
    entitled: bool
    latest_version: Text | None = None
    published_by: Symbol | None = None
    published_at: Text | None = None
    note: Text | None = None


class BiDatasetStatusReply(Contract):
    datasets: tuple[BiDatasetStatusEntry, ...] = ()


class BiDatasetDownloadRequest(Contract):
    asset: AssetIdentity


class BiDatasetDownloadReply(Contract):
    asset: AssetIdentity
    sha256: Sha256
    size: int
    snapshot: str


class BiDatasetAuditRequest(BiDatasetName):
    pass


class BiDatasetAuditRecord(Contract):
    at: AwareDatetime
    event: AuditEvent
    actor: Symbol
    namespace: Slug
    name: Slug
    version: Text | None = None
    sha256: Sha256 | None = None
    size: int | None = None
    base_version: Text | None = None
    note: Text | None = None
    bridge_id: Symbol | None = None

    @model_validator(mode="after")
    def bridge_events_name_the_bridge(self) -> Self:
        if self.event in ("synced", "sync_refused") and self.bridge_id is None:
            raise ValueError("a delivery names the Bridge")
        return self


class BiDatasetAuditReply(Contract):
    events: tuple[BiDatasetAuditRecord, ...] = ()


# -- the audit log -------------------------------------------------------------

_AUDIT_SCHEMA = (
    "CREATE TABLE IF NOT EXISTS bi_dataset_audit ("
    " seq INTEGER PRIMARY KEY AUTOINCREMENT, namespace TEXT NOT NULL, name TEXT NOT NULL,"
    " record TEXT NOT NULL)"
)


class BiDatasetAudit:
    """Append-only. Durable in the registry's SQLite file, else in memory."""

    def __init__(self, path: Path | str | None = None) -> None:
        self._lock = threading.Lock()
        self._memory: list[BiDatasetAuditRecord] = []
        self._once: set[tuple[str, ...]] = set()
        self._conn: sqlite3.Connection | None = None
        if path is not None:
            self._conn = sqlite3.connect(
                str(path), isolation_level=None, check_same_thread=False, timeout=5
            )
            self._conn.execute(_AUDIT_SCHEMA)

    def record(self, item: BiDatasetAuditRecord) -> None:
        checked = BiDatasetAuditRecord.model_validate(item)
        with self._lock:
            if self._conn is None:
                self._memory.append(checked)
                return
            self._conn.execute(
                "INSERT INTO bi_dataset_audit (namespace, name, record) VALUES (?, ?, ?)",
                (checked.namespace, checked.name, checked.model_dump_json()),
            )

    def record_once(self, key: tuple[str, ...], item: BiDatasetAuditRecord) -> None:
        """Record a repeated observation (a refused sync) once per process."""
        with self._lock:
            if key in self._once:
                return
            self._once.add(key)
        self.record(item)

    def events(self, namespace: str, name: str) -> tuple[BiDatasetAuditRecord, ...]:
        with self._lock:
            if self._conn is None:
                key = (namespace, name)
                return tuple(item for item in self._memory if (item.namespace, item.name) == key)
            rows = self._conn.execute(
                "SELECT record FROM bi_dataset_audit WHERE namespace = ? AND name = ? ORDER BY seq",
                (namespace, name),
            ).fetchall()
        return tuple(BiDatasetAuditRecord.model_validate_json(row[0]) for row in rows)

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None


# -- packages --------------------------------------------------------------------


def snapshot_digest(package: PublishedAssetPackage) -> str | None:
    for ref in package.metadata.validation_refs:
        if ref.startswith(DIGEST_REF):
            return ref[len(DIGEST_REF) :]
    return None


def publication_of(package: PublishedAssetPackage) -> tuple[str | None, str | None]:
    """Who published this version and when, from its provenance."""
    for entry in reversed(package.metadata.provenance):
        if entry.source == PUBLISH_SOURCE:
            return entry.author, entry.revision
    return None, None


def build_package(
    identity: AssetIdentity,
    *,
    owner: Owner,
    visibility: Visibility,
    publisher: str,
    published_at: str,
    note: str,
    digest: str,
    artifact: bytes,
    business_approval: BusinessApproval,
) -> PublishedAssetPackage:
    return PublishedAssetPackage.model_validate(
        {
            "kind": KIND,
            "description": note,
            "metadata": AssetMetadata(
                identity=identity,
                owner=owner,
                visibility=visibility,
                lifecycle="published",
                provenance=(
                    Provenance(source=PUBLISH_SOURCE, revision=published_at, author=publisher),
                ),
                business_approval=business_approval,
                technical_policy=TechnicalPolicy(
                    risk="low",
                    approval_required=False,
                    status="not_required",
                    reviewer=PLATFORM_REVIEWER,
                    evidence="data snapshot; no executable content",
                ),
                validation_refs=(f"{DIGEST_REF}{digest}",),
                package=PackageMetadata(
                    artifact_ref=(
                        f"registry://{identity.namespace}/{identity.name}/{identity.version}"
                    ),
                    sha256=hashlib.sha256(artifact).hexdigest(),
                ),
            ).model_dump(mode="json"),
        }
    )


def _schema_major(version: str) -> int:
    return int(version.split(".", 1)[0])


class BiDatasetService:
    """Publish, status, download and audit for `bi_dataset` names."""

    def __init__(
        self,
        ownership: AssetOwnershipService,
        packages: PackageRegistry,
        submissions: SubmissionStore,
        audit: BiDatasetAudit,
        artifacts: Mapping[str, bytes],
        *,
        clock: Callable[[], datetime] | None = None,
        max_bytes: int = MAX_SNAPSHOT_BYTES,
    ) -> None:
        self.ownership = ownership
        self.packages = packages
        self.submissions = submissions
        self.audit = audit
        self._artifacts = artifacts
        self._clock = clock if clock is not None else lambda: datetime.now(UTC)
        self._lock = threading.Lock()
        self.max_bytes = max_bytes

    @property
    def max_bytes(self) -> int:
        return self._max_bytes

    @max_bytes.setter
    def max_bytes(self, value: int) -> None:
        if isinstance(value, bool) or not MIN_LIMIT <= value <= MAX_LIMIT:
            raise ValueError("max_bi_dataset_bytes must be between 1 MiB and 64 MiB")
        self._max_bytes = value

    def body_limit(self) -> int:
        """The publish request body this limit needs: base64 plus JSON."""
        return self._max_bytes * 4 // 3 + BODY_OVERHEAD

    # -- helpers -------------------------------------------------------------

    def _member(self, who: AuthenticatedActor, now: datetime) -> tuple[str, tuple[str, ...]]:
        try:
            return self.ownership.member(who, now)
        except OwnershipError as error:
            raise BiDatasetError(_OWNERSHIP_CODES.get(error.code, "actor_unknown")) from None

    def _administrator(self, actor: str) -> bool:
        try:
            return self.ownership.enrollment.user(actor).role == "platform_admin"
        except Exception:  # noqa: BLE001 - an unknown member is not an administrator
            return False

    def _packages_of(self, namespace: str, name: str) -> list[PublishedAssetPackage]:
        found = [
            item
            for item in self.packages.discover(namespace=namespace)
            if item.metadata.identity.name == name
        ]
        found.sort(key=lambda item: version_key(item.metadata.identity.version))
        return found

    def _pending(self, namespace: str, name: str) -> tuple[AssetSubmission, ...]:
        return tuple(
            item
            for item in self.submissions.list(status="pending")
            if (item.identity.namespace, item.identity.name) == (namespace, name)
        )

    def _read(self, data: bytes) -> Snapshot:
        try:
            return read_snapshot(data, max_bytes=self._max_bytes)
        except SnapshotError as error:
            raise _snapshot_error(error) from None

    def _schema_version_of(self, package: PublishedAssetPackage) -> str | None:
        reference = package.metadata.package.artifact_ref if package.metadata.package else None
        if reference is None or reference not in self._artifacts:
            return None
        try:
            return read_snapshot(self._artifacts[reference], max_bytes=MAX_LIMIT).schema_version
        except SnapshotError:
            return None

    # -- publishing ------------------------------------------------------------

    def publish(
        self, who: AuthenticatedActor, request: BiDatasetPublishRequest
    ) -> BiDatasetPublishReply:
        item = BiDatasetPublishRequest.model_validate(request)
        now = self._clock()
        actor, groups = self._member(who, now)
        try:
            raw = base64.b64decode(item.snapshot, validate=True)
        except (binascii.Error, ValueError):
            raise BiDatasetError("snapshot_invalid") from None
        if len(raw) > self._max_bytes:
            raise BiDatasetError("artifact_too_large")
        snapshot = self._read(raw)
        if item.readers in ("public", "private"):
            raise BiDatasetError("visibility_not_allowed")
        if item.readers == "organization" and not item.confirm_organization:
            raise BiDatasetError("organization_unconfirmed")
        with self._lock:
            record = self.packages.ownership(item.namespace, item.name)
            published = self._packages_of(item.namespace, item.name)
            if record is not None and published and published[-1].kind != KIND:
                raise BiDatasetError("kind_mismatch")
            if record is not None and not record.may_publish(actor, groups):
                raise BiDatasetError("publisher_not_authorized")
            if self._pending(item.namespace, item.name):
                raise BiDatasetError("review_pending")
            versions = [p.metadata.identity.version for p in published]
            highest = highest_version(versions)
            if item.base_version != highest:
                raise BiDatasetError("version_superseded")
            if record is None:
                return self._submit_first(item, snapshot, raw, actor, groups, now)
            previous = published[-1]
            previous_schema = self._schema_version_of(previous)
            change: VersionChange = (
                "major"
                if previous_schema is not None
                and _schema_major(previous_schema) != _schema_major(snapshot.schema_version)
                else "minor"
            )
            version = next_version(versions, change)
            identity = AssetIdentity(namespace=item.namespace, name=item.name, version=version)
            visibility = item.readers or previous.metadata.visibility
            published_at = now.astimezone(UTC).isoformat()
            artifact = self._stamp(snapshot, identity, highest, actor, published_at, item.note)
            package = build_package(
                identity,
                owner=record.owner,
                visibility=visibility,
                publisher=actor,
                published_at=published_at,
                note=item.note,
                digest=snapshot.digest,
                artifact=artifact,
                business_approval=BusinessApproval(
                    status="not_required",
                    reviewer=actor,
                    evidence="owner or co-editor publish of a later version (owner Q5, 2026-10-22)",
                ),
            )
            try:
                self.ownership.publish(who, package, artifact=artifact, change=change, now=now)
            except OwnershipError as error:
                raise BiDatasetError(
                    _OWNERSHIP_CODES.get(error.code, "publisher_not_authorized")
                ) from None
        sha256 = hashlib.sha256(artifact).hexdigest()
        self.audit.record(
            BiDatasetAuditRecord(
                at=now,
                event="published",
                actor=actor,
                namespace=item.namespace,
                name=item.name,
                version=version,
                sha256=sha256,
                size=len(artifact),
                base_version=highest,
                note=item.note,
            )
        )
        return BiDatasetPublishReply(
            status="published",
            asset=identity,
            sha256=sha256,
            digest=snapshot.digest,
            size=len(artifact),
        )

    def _stamp(
        self,
        snapshot: Snapshot,
        identity: AssetIdentity,
        base_version: str | None,
        publisher: str,
        published_at: str,
        note: str,
    ) -> bytes:
        artifact = stamp_publication(
            snapshot,
            Publication(
                namespace=identity.namespace,
                name=identity.name,
                version=identity.version,
                base_version=base_version,
                published_by=publisher,
                published_at=published_at,
                note=note,
            ),
        )
        if len(artifact) > self._max_bytes:
            raise BiDatasetError("artifact_too_large")
        return artifact

    def _submit_first(
        self,
        item: BiDatasetPublishRequest,
        snapshot: Snapshot,
        raw: bytes,
        actor: str,
        groups: tuple[str, ...],
        now: datetime,
    ) -> BiDatasetPublishReply:
        """The first version of a new name waits for an administrator."""
        if item.team is not None:
            if item.team not in groups:
                raise BiDatasetError("publisher_not_authorized")
            owner = Owner(type="team", id=item.team)
        elif len(groups) == 1:
            owner = Owner(type="team", id=groups[0])
        elif not groups:
            owner = Owner(type="user", id=actor)
        else:
            raise BiDatasetError("team_required")
        identity = AssetIdentity(namespace=item.namespace, name=item.name, version="1.0.0")
        artifact = self._stamp(
            snapshot, identity, None, actor, now.astimezone(UTC).isoformat(), item.note
        )
        from control_plane.submissions import new_submission_id

        submission = AssetSubmission(
            submission_id=new_submission_id(),
            kind=KIND,
            identity=identity,
            submitter=actor,
            change="minor",
            note=item.note,
            sha256=hashlib.sha256(artifact).hexdigest(),
            owner=owner,
            visibility=item.readers or "team",
            submitted_at=now,
        )
        self.submissions.add(submission, artifact)
        self.audit.record(
            BiDatasetAuditRecord(
                at=now,
                event="submitted",
                actor=actor,
                namespace=item.namespace,
                name=item.name,
                version=identity.version,
                sha256=submission.sha256,
                size=len(artifact),
                note=item.note,
            )
        )
        return BiDatasetPublishReply(
            status="pending_review",
            asset=identity,
            sha256=submission.sha256,
            digest=snapshot.digest,
            size=len(artifact),
            submission_id=submission.submission_id,
        )

    # -- the review queue's side ---------------------------------------------

    def review_summary(self, content: bytes) -> dict[str, object]:
        """What a reviewer reads instead of a manifest: no card values."""
        snapshot = read_snapshot(content, max_bytes=MAX_LIMIT)
        return {
            "kind": KIND,
            "dataset": snapshot.dataset,
            "classification": "INTERNAL",
            "schema": {"ref": snapshot.schema_ref, "source": snapshot.schema_source},
            "stats": dict(snapshot.stats),
            "digest": snapshot.digest,
            "publication": (
                None if snapshot.publication is None else snapshot.publication.as_json()
            ),
        }

    def reviewed_package(
        self, item: AssetSubmission, content: bytes, *, reviewer: str, evidence: str
    ) -> tuple[PublishedAssetPackage, bytes]:
        """The package an approval publishes, stamped at approval time."""
        snapshot = read_snapshot(content, max_bytes=MAX_LIMIT)
        published_at = self._clock().astimezone(UTC).isoformat()
        note = item.note or "first version"
        artifact = stamp_publication(
            snapshot,
            Publication(
                namespace=item.identity.namespace,
                name=item.identity.name,
                version=item.identity.version,
                base_version=None,
                published_by=item.submitter,
                published_at=published_at,
                note=note,
            ),
        )
        package = build_package(
            item.identity,
            owner=item.owner if item.owner is not None else Owner(type="user", id=item.submitter),
            visibility=item.visibility or "team",
            publisher=item.submitter,
            published_at=published_at,
            note=note,
            digest=snapshot.digest,
            artifact=artifact,
            business_approval=BusinessApproval(
                status="approved", reviewer=reviewer, evidence=evidence
            ),
        )
        return package, artifact

    def decided(self, item: AssetSubmission, *, actor: str, status: str) -> None:
        event = _DECISION_EVENTS.get(status)
        if event is None:
            return
        self.audit.record(
            BiDatasetAuditRecord(
                at=self._clock(),
                event=event,
                actor=actor,
                namespace=item.identity.namespace,
                name=item.identity.name,
                version=item.identity.version,
                sha256=item.sha256,
                note=item.note,
            )
        )

    # -- readers ---------------------------------------------------------------

    def status(
        self, who: AuthenticatedActor, request: BiDatasetStatusRequest
    ) -> BiDatasetStatusReply:
        item = BiDatasetStatusRequest.model_validate(request)
        actor, groups = self._member(who, self._clock())
        entries = []
        for name in item.names:
            usable = [
                package
                for package in self._packages_of(name.namespace, name.name)
                if package.kind == KIND
                and entitled_in(self.packages, package.metadata, actor, groups)
            ]
            if not usable:
                entries.append(
                    BiDatasetStatusEntry(namespace=name.namespace, name=name.name, entitled=False)
                )
                continue
            latest = usable[-1]
            by, at = publication_of(latest)
            entries.append(
                BiDatasetStatusEntry(
                    namespace=name.namespace,
                    name=name.name,
                    entitled=True,
                    latest_version=latest.metadata.identity.version,
                    published_by=by,
                    published_at=at,
                    note=latest.description,
                )
            )
        return BiDatasetStatusReply(datasets=tuple(entries))

    def download(
        self, who: AuthenticatedActor, request: BiDatasetDownloadRequest
    ) -> BiDatasetDownloadReply:
        item = BiDatasetDownloadRequest.model_validate(request)
        now = self._clock()
        actor, groups = self._member(who, now)
        package = self.packages.get(item.asset)
        if package is None or package.kind != KIND or package.metadata.package is None:
            raise BiDatasetError("asset_not_published")
        if not entitled_in(self.packages, package.metadata, actor, groups):
            raise BiDatasetError("asset_not_entitled")
        content = self._artifacts.get(package.metadata.package.artifact_ref)
        if content is None:
            raise BiDatasetError("asset_not_published")
        sha256 = hashlib.sha256(content).hexdigest()
        self.audit.record(
            BiDatasetAuditRecord(
                at=now,
                event="downloaded",
                actor=actor,
                namespace=item.asset.namespace,
                name=item.asset.name,
                version=item.asset.version,
                sha256=sha256,
                size=len(content),
            )
        )
        return BiDatasetDownloadReply(
            asset=item.asset,
            sha256=sha256,
            size=len(content),
            snapshot=base64.b64encode(content).decode("ascii"),
        )

    def audit_events(
        self, who: AuthenticatedActor, request: BiDatasetAuditRequest
    ) -> BiDatasetAuditReply:
        item = BiDatasetAuditRequest.model_validate(request)
        actor, groups = self._member(who, self._clock())
        record = self.packages.ownership(item.namespace, item.name)
        allowed = record is not None and (
            record.may_publish(actor, groups) or self._administrator(actor)
        )
        if not allowed:
            # The name's submitter may follow their own pending first version.
            allowed = any(
                entry.submitter == actor
                for entry in self.submissions.list(submitter=actor)
                if (entry.identity.namespace, entry.identity.name) == (item.namespace, item.name)
                and entry.kind == KIND
            )
        if not allowed:
            raise BiDatasetError("name_missing")
        return BiDatasetAuditReply(events=self.audit.events(item.namespace, item.name))

    # -- selection and delivery (called by the member and Bridge services) ---

    def selection_event(
        self, event: AuditEvent, actor: str, asset: AssetIdentity, bridge_id: str
    ) -> None:
        self.audit.record(
            BiDatasetAuditRecord(
                at=self._clock(),
                event=event,
                actor=actor,
                namespace=asset.namespace,
                name=asset.name,
                version=asset.version,
                bridge_id=bridge_id,
            )
        )
