"""Contracts of the sandboxed Knowledge pipeline (docs/phases/KNOWLEDGE_K1.md)."""

from __future__ import annotations

from typing import Literal, Self

from pydantic import Field, model_validator

from common.base import Contract, Symbol, Text


class PipelineVault(Contract):
    """A base vault people may copy into a sandbox (host.json)."""

    name: Symbol
    root: Text


class KnowledgePipelineHostBinding(Contract):
    """Trusted host wiring for the pipeline (host.json `knowledge_pipeline`)."""

    vaults: tuple[PipelineVault, ...] = Field(min_length=1)
    # Where sandboxes live; default <workspace>/knowledge-sandboxes. A shorter
    # folder keeps long Raw paths under the Windows path limit.
    sandbox_root: Text | None = None

    @model_validator(mode="after")
    def unique_names(self) -> Self:
        names = [item.name for item in self.vaults]
        if len(names) != len(set(names)):
            raise ValueError("pipeline vault names are unique")
        return self


class SandboxCreateRequest(Contract):
    base: Symbol
    label: Text = Field(min_length=1, max_length=80)


class SandboxListRequest(Contract):
    pass


class SandboxRecord(Contract):
    sandbox_id: Text
    base_name: Text
    label: Text
    created_by: Text
    created_at: Text


class SandboxList(Contract):
    sandboxes: tuple[SandboxRecord, ...] = ()


class ConvertRequest(Contract):
    sandbox_id: Text
    paths: tuple[Text, ...] = ()
    mode: Literal["dry_run", "apply"] = "dry_run"


class IngestPlanRequest(Contract):
    sandbox_id: Text
    raw_ref: Text


class IngestApplyRequest(Contract):
    sandbox_id: Text
    plan_id: Text


class LintRequest(Contract):
    sandbox_id: Text


class DropAddRequest(Contract):
    sandbox_id: Text
    name: Text = Field(min_length=1, max_length=400)
    data_base64: str = Field(min_length=1)


class DropAdded(Contract):
    sandbox_id: Text
    path: Text


class SandboxRef(Contract):
    sandbox_id: Text


class SandboxDiscarded(Contract):
    sandbox_id: Text
    discarded: bool = True


class AdoptRequest(Contract):
    sandbox_id: Text
    mode: Literal["dry_run", "apply"] = "dry_run"


class IndexEnrichRequest(Contract):
    sandbox_id: Text
    limit: int = Field(default=60, ge=1, le=200)


class IndexBuildRequest(Contract):
    sandbox_id: Text
    mode: Literal["dry_run", "apply"] = "dry_run"
