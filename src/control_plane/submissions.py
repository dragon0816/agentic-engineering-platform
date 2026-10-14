"""Member publish with a review queue (owner 2026-10-15).

`docs/phases/MEMBER_PUBLISH.md`. A member submits a Skill or Workflow manifest
from their Personal Agent; an administrator who is not the submitter approves
or rejects it; only an approval publishes it, as the submitter, under the
ownership and version rules of `docs/phases/ASSET_OWNERSHIP.md`.

What the author wrote about version, owner, lifecycle and reviews is never
trusted: the platform assigns the version, keeps the name's owner, resets both
reviews to pending on submit and writes the reviewer's decision on approval.
A submitted manifest is data. The platform never runs it.
"""

from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
import threading
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import ValidationError

from agent.skills import SkillManifest
from common.assets import (
    AssetIdentity,
    AssetMetadata,
    BusinessApproval,
    Owner,
    PackageMetadata,
    Provenance,
    TechnicalPolicy,
    WorkflowManifest,
)
from common.distribution import PublishedAssetPackage
from common.identity import AuthenticatedActor
from common.member import (
    AssetApproveRequest,
    AssetRejectRequest,
    AssetSubmission,
    AssetSubmissionDetailReply,
    AssetSubmissionListReply,
    AssetSubmitRequest,
    SubmissionStatus,
)
from common.ownership import next_version, version_key
from control_plane.distribution import PackageRegistry
from control_plane.ownership import AssetOwnershipService, OwnershipError

# What the member portal's 256 KiB body leaves for the manifest itself once it
# is JSON inside the request.
MAX_ARTIFACT_BYTES = 192 * 1024
SUBMISSION_SOURCE = "member-submission"

SubmissionErrorCode = Literal[
    "manifest_invalid",
    "artifact_too_large",
    "missing_dependency",
    "publisher_not_authorized",
    "submission_missing",
    "submission_not_pending",
    "self_review_refused",
    "version_superseded",
    "actor_unknown",
    "actor_disabled",
    "session_expired",
]

_PUBLISH_CODES: dict[str, SubmissionErrorCode] = {
    "publisher_not_authorized": "publisher_not_authorized",
    "owner_mismatch": "publisher_not_authorized",
    "version_not_above_highest": "version_superseded",
    "duplicate_package": "version_superseded",
    "actor_unknown": "actor_unknown",
    "actor_disabled": "actor_disabled",
    "session_expired": "session_expired",
}

_SCHEMA = (
    "CREATE TABLE IF NOT EXISTS submissions ("
    " submission_id TEXT PRIMARY KEY, namespace TEXT NOT NULL, name TEXT NOT NULL,"
    " version TEXT NOT NULL, submitter TEXT NOT NULL, status TEXT NOT NULL,"
    " submitted_at TEXT NOT NULL, record TEXT NOT NULL, artifact BLOB NOT NULL)"
)


class SubmissionError(Exception):
    def __init__(self, code: SubmissionErrorCode) -> None:
        self.code: SubmissionErrorCode = code
        super().__init__(code)


class SubmissionStore:
    """The review queue. The durable store shares the Registry's SQLite file;
    without one the platform keeps the queue in memory, as it does every
    other reference store."""

    def __init__(self, path: Path | str | None = None) -> None:
        self._lock = threading.Lock()
        self._memory: dict[str, tuple[AssetSubmission, bytes]] = {}
        self._conn: sqlite3.Connection | None = None
        if path is not None:
            self._conn = sqlite3.connect(
                str(path), isolation_level=None, check_same_thread=False, timeout=5
            )
            self._conn.execute(_SCHEMA)

    def add(self, item: AssetSubmission, artifact: bytes) -> None:
        with self._lock:
            if self._conn is None:
                self._memory[item.submission_id] = (item, artifact)
                return
            identity = item.identity
            self._conn.execute(
                "INSERT INTO submissions (submission_id, namespace, name, version, submitter,"
                " status, submitted_at, record, artifact) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (item.submission_id, identity.namespace, identity.name, identity.version,
                 item.submitter, item.status, item.submitted_at.astimezone(UTC).isoformat(),
                 item.model_dump_json(), artifact),
            )

    def update(self, item: AssetSubmission, *, expected: SubmissionStatus) -> bool:
        """Change one submission if it still has the expected status; whether
        it did. Two reviewers deciding at once cannot both win."""
        with self._lock:
            if self._conn is None:
                held = self._memory.get(item.submission_id)
                if held is None or held[0].status != expected:
                    return False
                self._memory[item.submission_id] = (item, held[1])
                return True
            cursor = self._conn.execute(
                "UPDATE submissions SET status = ?, record = ? WHERE submission_id = ?"
                " AND status = ?",
                (item.status, item.model_dump_json(), item.submission_id, expected),
            )
            return cursor.rowcount == 1

    def get(self, submission_id: str) -> tuple[AssetSubmission, bytes] | None:
        with self._lock:
            if self._conn is None:
                return self._memory.get(submission_id)
            row = self._conn.execute(
                "SELECT record, artifact FROM submissions WHERE submission_id = ?",
                (submission_id,),
            ).fetchone()
        if row is None:
            return None
        return AssetSubmission.model_validate_json(row[0]), bytes(row[1])

    def list(
        self, *, submitter: str | None = None, status: SubmissionStatus | None = None
    ) -> tuple[AssetSubmission, ...]:
        """Newest first."""
        with self._lock:
            if self._conn is None:
                items = [held[0] for held in self._memory.values()]
            else:
                rows = self._conn.execute("SELECT record FROM submissions").fetchall()
                items = [AssetSubmission.model_validate_json(row[0]) for row in rows]
        chosen = [
            item for item in items
            if (submitter is None or item.submitter == submitter)
            and (status is None or item.status == status)
        ]
        chosen.sort(key=lambda item: item.submitted_at, reverse=True)
        return tuple(chosen)

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None


def _parse(kind: str, manifest: object) -> WorkflowManifest | SkillManifest:
    try:
        if kind == "workflow":
            return WorkflowManifest.model_validate(manifest)
        return SkillManifest.model_validate(manifest)
    except (ValidationError, ValueError):
        raise SubmissionError("manifest_invalid") from None


def _with_metadata(
    manifest: WorkflowManifest | SkillManifest, metadata: AssetMetadata
) -> WorkflowManifest | SkillManifest:
    data = manifest.model_dump(mode="json")
    data["metadata"] = metadata.model_dump(mode="json")
    try:
        return type(manifest).model_validate(data)
    except (ValidationError, ValueError):
        raise SubmissionError("manifest_invalid") from None


def _content(manifest: WorkflowManifest | SkillManifest) -> bytes:
    # The same bytes the preview catalog publishes and a Bridge installs.
    return manifest.model_dump_json(indent=2).encode("utf-8")


class SubmissionService:
    """Submit, review and publish, over one Registry and one queue."""

    def __init__(
        self,
        ownership: AssetOwnershipService,
        packages: PackageRegistry,
        store: SubmissionStore,
        *,
        artifacts: Mapping[str, bytes] | None = None,
        clock: Callable[[], datetime] | None = None,
        allow_self_review: bool = True,
    ) -> None:
        self.ownership = ownership
        # Owner 2026-10-15, temporary while publishing is verified: an
        # administrator may approve their own submission. Revisit after the
        # verification (`docs/phases/MEMBER_PUBLISH.md`); False refuses it.
        self.allow_self_review = allow_self_review
        self.packages = packages
        self.store = store
        self._artifacts = artifacts
        self._clock = clock if clock is not None else lambda: datetime.now(UTC)
        self._lock = threading.Lock()

    def _member(self, who: AuthenticatedActor) -> tuple[str, tuple[str, ...]]:
        try:
            return self.ownership.member(who, self._clock())
        except OwnershipError as error:
            raise SubmissionError(_PUBLISH_CODES.get(error.code, "actor_unknown")) from None

    def _published(self, namespace: str, name: str) -> tuple[str, ...]:
        return tuple(
            item.metadata.identity.version
            for item in self.packages.discover()
            if (item.metadata.identity.namespace, item.metadata.identity.name)
            == (namespace, name)
        )

    def _pending(self, namespace: str, name: str) -> tuple[AssetSubmission, ...]:
        return tuple(
            item for item in self.store.list(status="pending")
            if (item.identity.namespace, item.identity.name) == (namespace, name)
        )

    def _dependencies_present(self, manifest: SkillManifest, actor: str) -> bool:
        pending = {
            item.identity for item in self.store.list(submitter=actor, status="pending")
        }
        for command in manifest.commands:
            if command.kind != "workflow":
                continue
            if self.packages.get(command.target) is None and command.target not in pending:
                return False
        return True

    # -- the member --------------------------------------------------------

    def submit(self, who: AuthenticatedActor, request: AssetSubmitRequest) -> AssetSubmission:
        actor, groups = self._member(who)
        item = AssetSubmitRequest.model_validate(request)
        manifest = _parse(item.kind, item.manifest)
        original = manifest.metadata
        namespace, name = original.identity.namespace, original.identity.name
        with self._lock:
            record = self.packages.ownership(namespace, name)
            if record is not None and not record.may_publish(actor, groups):
                raise SubmissionError("publisher_not_authorized")
            if isinstance(manifest, SkillManifest) and not self._dependencies_present(
                manifest, actor
            ):
                raise SubmissionError("missing_dependency")
            # A version is reserved by a pending submission, so two of one
            # name never collide; it is still checked again on approval.
            taken = (
                *self._published(namespace, name),
                *(entry.identity.version for entry in self._pending(namespace, name)),
            )
            version = next_version(taken, item.change)
            identity = AssetIdentity(namespace=namespace, name=name, version=version)
            policy = original.technical_policy
            metadata = AssetMetadata.model_validate(
                {
                    **original.model_dump(mode="json"),
                    "identity": identity.model_dump(mode="json"),
                    "owner": (
                        record.owner if record is not None else Owner(type="user", id=actor)
                    ).model_dump(mode="json"),
                    "lifecycle": "published",
                    "business_approval": BusinessApproval().model_dump(mode="json"),
                    "technical_policy": TechnicalPolicy(
                        risk=policy.risk,
                        approval_required=True,
                        required_permissions=policy.required_permissions,
                        policy_refs=policy.policy_refs,
                        assessment="manual",
                    ).model_dump(mode="json"),
                    "provenance": [
                        *(entry.model_dump(mode="json") for entry in original.provenance),
                        Provenance(source=SUBMISSION_SOURCE, author=actor).model_dump(
                            mode="json"
                        ),
                    ],
                    "package": None,
                }
            )
            content = _content(_with_metadata(manifest, metadata))
            if len(content) > MAX_ARTIFACT_BYTES:
                raise SubmissionError("artifact_too_large")
            submission = AssetSubmission(
                submission_id=f"sub-{secrets.token_hex(8)}",
                kind=item.kind,
                identity=identity,
                submitter=actor,
                change=item.change,
                note=item.note,
                sha256=hashlib.sha256(content).hexdigest(),
                risk=policy.risk,
                required_permissions=policy.required_permissions,
                submitted_at=self._clock(),
            )
            self.store.add(submission, content)
        return submission

    def mine(self, who: AuthenticatedActor) -> AssetSubmissionListReply:
        actor, _ = self._member(who)
        return AssetSubmissionListReply(submissions=self.store.list(submitter=actor))

    def withdraw(self, who: AuthenticatedActor, submission_id: str) -> AssetSubmission:
        actor, _ = self._member(who)
        held = self.store.get(submission_id)
        if held is None or held[0].submitter != actor:
            raise SubmissionError("submission_missing")
        return self._decide(held[0], status="withdrawn", reviewer=None, reason=None)

    # -- the administrator (the caller checks the role) --------------------

    def queue(self, status: SubmissionStatus | None) -> AssetSubmissionListReply:
        return AssetSubmissionListReply(submissions=self.store.list(status=status))

    def detail(self, submission_id: str) -> AssetSubmissionDetailReply:
        held = self.store.get(submission_id)
        if held is None:
            raise SubmissionError("submission_missing")
        item, content = held
        previous_version: str | None = None
        previous_manifest = None
        published = sorted(
            self._published(item.identity.namespace, item.identity.name), key=version_key
        )
        if published:
            previous_version = published[-1]
            reference = (
                f"registry://{item.identity.namespace}/{item.identity.name}/{previous_version}"
            )
            if self._artifacts is not None and reference in self._artifacts:
                previous_manifest = json.loads(self._artifacts[reference])
        return AssetSubmissionDetailReply(
            submission=item,
            manifest=json.loads(content),
            previous_version=previous_version,
            previous_manifest=previous_manifest,
        )

    def approve(
        self, reviewer: AuthenticatedActor, request: AssetApproveRequest
    ) -> AssetSubmission:
        actor, _ = self._member(reviewer)
        decision = AssetApproveRequest.model_validate(request)
        with self._lock:
            held = self.store.get(decision.submission_id)
            if held is None:
                raise SubmissionError("submission_missing")
            item, content = held
            if item.status != "pending":
                raise SubmissionError("submission_not_pending")
            if item.submitter == actor and not self.allow_self_review:
                raise SubmissionError("self_review_refused")
            manifest = _parse(item.kind, json.loads(content))
            evidence = f"submission:{item.submission_id}; {decision.evidence}"
            policy = manifest.metadata.technical_policy
            metadata = manifest.metadata.model_copy(
                update={
                    "business_approval": BusinessApproval(
                        status="approved", reviewer=actor, evidence=evidence
                    ),
                    "technical_policy": policy.model_copy(
                        update={"status": "approved", "reviewer": actor, "evidence": evidence}
                    ),
                }
            )
            published = _with_metadata(manifest, metadata)
            artifact = _content(published)
            identity = metadata.identity
            package = PublishedAssetPackage.model_validate(
                {
                    "kind": item.kind,
                    "metadata": metadata.model_copy(
                        update={
                            "package": PackageMetadata(
                                artifact_ref=(
                                    f"registry://{identity.namespace}/{identity.name}/"
                                    f"{identity.version}"
                                ),
                                sha256=hashlib.sha256(artifact).hexdigest(),
                            )
                        }
                    ),
                    "description": (
                        published.description
                        if isinstance(published, WorkflowManifest)
                        else published.instructions
                    ),
                }
            )
            try:
                self.ownership.publish_reviewed(item.submitter, package, artifact=artifact)
            except OwnershipError as error:
                raise SubmissionError(
                    _PUBLISH_CODES.get(error.code, "publisher_not_authorized")
                ) from None
            return self._decide(item, status="approved", reviewer=actor, reason=None)

    def reject(
        self, reviewer: AuthenticatedActor, request: AssetRejectRequest
    ) -> AssetSubmission:
        actor, _ = self._member(reviewer)
        decision = AssetRejectRequest.model_validate(request)
        held = self.store.get(decision.submission_id)
        if held is None:
            raise SubmissionError("submission_missing")
        return self._decide(held[0], status="rejected", reviewer=actor, reason=decision.reason)

    def _decide(
        self,
        item: AssetSubmission,
        *,
        status: SubmissionStatus,
        reviewer: str | None,
        reason: str | None,
    ) -> AssetSubmission:
        if item.status != "pending":
            raise SubmissionError("submission_not_pending")
        decided = AssetSubmission.model_validate(
            {
                **item.model_dump(),
                "status": status,
                "reviewer": reviewer,
                "reason": reason,
                "decided_at": self._clock(),
            }
        )
        if not self.store.update(decided, expected="pending"):
            raise SubmissionError("submission_not_pending")
        return decided
