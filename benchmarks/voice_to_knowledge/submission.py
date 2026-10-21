"""Proposed in-memory consumer contract. No production API or publish path."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from threading import Lock
from uuid import uuid4


class SubmissionError(ValueError):
    retryable = False

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Identity:
    tenant: str
    actor: str
    scopes: frozenset[str]


@dataclass(frozen=True)
class Claim:
    kind: str
    text: str
    start: int
    end: int
    basis: str | None = None
    verification_status: str = "unverified"


@dataclass(frozen=True)
class Submission:
    source_id: str
    audio_sha256: str
    transcript: str
    transcript_sha256: str
    skill_version: str
    model_version: str
    claims: tuple[Claim, ...]
    schema_version: str = "voice.mock.v0"

    def validate(self) -> None:
        valid = (
            self.schema_version == "voice.mock.v0"
            and self.source_id.strip()
            and self.skill_version.strip()
            and self.model_version.strip()
            and re.fullmatch("[0-9a-f]{64}", self.audio_sha256)
            and self.transcript_sha256 == digest(self.transcript)
            and 0 < len(self.transcript.encode()) <= 100_000
            and isinstance(self.claims, tuple)
            and len(self.claims) <= 100
        )
        if not valid:
            raise SubmissionError("invalid_request")
        for claim in self.claims:
            if (
                claim.kind not in {"fact", "observation", "inference", "uncertain"}
                or claim.verification_status != "unverified"
                or not claim.text.strip()
                or type(claim.start) is not int
                or type(claim.end) is not int
                or not 0 <= claim.start < claim.end <= len(self.transcript)
            ):
                raise SubmissionError("invalid_request")
            quote = self.transcript[claim.start : claim.end]
            if claim.kind == "inference":
                if claim.basis != quote:
                    raise SubmissionError("invalid_request")
            elif claim.text != quote:
                raise SubmissionError("invalid_request")


@dataclass(frozen=True)
class Draft:
    draft_id: str
    tenant: str
    actor: str
    submission: Submission
    markdown: str
    revision: int = 1
    status: str = "draft"
    mock: bool = True


@dataclass(frozen=True)
class Receipt:
    draft_id: str
    request_id: str
    status: str = "draft"
    revision: int = 1
    mock: bool = True


class MockSubmission:
    def __init__(self) -> None:
        self._drafts: dict[str, Draft] = {}
        self._keys: dict[tuple[str, str, str], tuple[str, str]] = {}
        self._lock = Lock()

    @staticmethod
    def _authorize(identity: Identity, scope: str) -> None:
        if (
            not identity.actor.strip()
            or not identity.tenant.strip()
            or scope not in identity.scopes
        ):
            raise SubmissionError("permission_denied")

    def create(
        self, identity: Identity, key: str, submission: Submission, request_id: str
    ) -> Receipt:
        self._authorize(identity, "draft.create")
        if not key.strip() or len(key) > 128 or not request_id.strip():
            raise SubmissionError("invalid_request")
        submission.validate()
        checksum = digest(json.dumps(asdict(submission), sort_keys=True, ensure_ascii=False))
        scoped = (identity.tenant, identity.actor, key)
        with self._lock:
            if scoped in self._keys:
                previous, draft_id = self._keys[scoped]
                if previous != checksum:
                    raise SubmissionError("idempotency_conflict")
                return Receipt(draft_id, request_id)
            draft_id = "mock-" + uuid4().hex
            # JSON string quoting makes arbitrary transcript Markdown inert in this text artifact.
            markdown = "# Mock draft — unverified\n\n" + "\n".join(
                f"- {c.kind}: {json.dumps(c.text, ensure_ascii=False)} "
                f"[{submission.source_id}:{c.start}:{c.end}]"
                for c in submission.claims
            )
            self._drafts[draft_id] = Draft(
                draft_id, identity.tenant, identity.actor, submission, markdown
            )
            self._keys[scoped] = (checksum, draft_id)
            return Receipt(draft_id, request_id)

    def read(self, identity: Identity, draft_id: str) -> Draft:
        self._authorize(identity, "draft.read.own")
        with self._lock:
            draft = self._drafts.get(draft_id)
            if draft is None or (draft.tenant, draft.actor) != (identity.tenant, identity.actor):
                raise SubmissionError("not_found")
            return draft
