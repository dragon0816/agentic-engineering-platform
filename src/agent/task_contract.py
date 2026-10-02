"""Backend-neutral task objective and independently checkable output contract."""

import hashlib
import json
from typing import Literal, Self

from pydantic import Field, model_validator

from common.assets import AssetIdentity, reject_embedded_secrets
from common.base import Contract, Sha256, Slug, Symbol, Text
from common.execution import TraceIdentifiers


class ExpectedOutput(Contract):
    """An opaque local artifact reference; the host resolves it, not a model."""

    output_id: Symbol
    artifact_ref: Symbol


class CompletionCheck(Contract):
    """A check that the host can repeat without trusting a backend's claim."""

    check_id: Symbol
    output_id: Symbol
    kind: Literal["nonempty", "sha256"]
    expected_sha256: Sha256 | None = None

    @model_validator(mode="after")
    def expected_digest_only_for_digest_check(self) -> Self:
        if (self.kind == "sha256") != (self.expected_sha256 is not None):
            raise ValueError("expected_sha256 is required only for a sha256 check")
        return self


class TaskContract(Contract):
    """A portable task definition. Its objective is kept out of durable run state.

    This contract carries intent and exact references, never execution authority.
    Classification of outbound bytes and capability approval remain separate.
    """

    task_id: Symbol
    trace: TraceIdentifiers
    actor: Symbol
    namespace: Slug
    objective: Text = Field(max_length=20000, repr=False)
    skills: tuple[AssetIdentity, ...] = Field(default=(), max_length=20)
    resource_refs: tuple[Symbol, ...] = Field(default=(), max_length=50)
    expected_outputs: tuple[ExpectedOutput, ...] = Field(min_length=1, max_length=20)
    checks: tuple[CompletionCheck, ...] = Field(min_length=1, max_length=40)

    @model_validator(mode="after")
    def bounded_and_checkable(self) -> Self:
        if len(self.skills) != len({skill.key for skill in self.skills}):
            raise ValueError("skill references must be unique")
        if len(self.resource_refs) != len(set(self.resource_refs)):
            raise ValueError("resource references must be unique")
        outputs = {output.output_id: output for output in self.expected_outputs}
        if len(outputs) != len(self.expected_outputs) or len(
            {output.artifact_ref for output in self.expected_outputs}
        ) != len(self.expected_outputs):
            raise ValueError("expected outputs must be unique")
        if len(self.checks) != len({check.check_id for check in self.checks}):
            raise ValueError("completion checks must be unique")
        if any(check.output_id not in outputs for check in self.checks):
            raise ValueError("completion check references an unknown output")
        if set(outputs) != {check.output_id for check in self.checks}:
            raise ValueError("every expected output requires a completion check")
        reject_embedded_secrets(self.model_dump(mode="json"))
        return self

    @property
    def digest(self) -> str:
        payload = json.dumps(
            self.model_dump(mode="json"), sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()
