"""Contracts of the sandboxed Knowledge pipeline (docs/phases/KNOWLEDGE_K1.md)."""

from __future__ import annotations

from typing import Literal, Self

from pydantic import Field, model_validator

from common.base import Contract, Symbol, Text


class PipelineVault(Contract):
    """A project vault people open sandboxes from (host.json). Its location is
    set per project (docs/phases/KNOWLEDGE_COLLAB.md section 2)."""

    name: Symbol
    root: Text
    drop_root: Text | None = None  # default <root>/drop
    questions_root: Text | None = None  # default <root>/checks/questions
    maintainers: tuple[Text, ...] = ()  # who may push
    # The Knowledge asset the Agent answers from that this project feeds, e.g.
    # rs-knowledge; "Refresh" stages the project vault as its next version.
    knowledge_asset: Symbol | None = None


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
    domain: Symbol | None = None  # a K2 index category, e.g. product-vna
    # The folder the sandbox maintains, e.g. Knowledge or Productions/VNA.
    scope: Text | None = Field(default=None, max_length=200)


class SandboxListRequest(Contract):
    pass


class SandboxRecord(Contract):
    sandbox_id: Text
    base_name: Text
    label: Text
    created_by: Text
    created_at: Text
    scope: Text | None = None


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


class MergeRequest(Contract):
    sandbox_id: Text
    mode: Literal["dry_run", "apply"] = "dry_run"
    # "<path>#<part>" -> which side wins a conflict
    resolutions: dict[str, Literal["sandbox", "published"]] = Field(default_factory=dict)


class DropFoldersRequest(Contract):
    base: Symbol


class PullRequest(Contract):
    sandbox_id: Text
    folders: tuple[Text, ...] = Field(min_length=1, max_length=50)


class FileRequest(Contract):
    sandbox_id: Text
    path: Text


class RuleWriteRequest(Contract):
    sandbox_id: Text
    path: Text
    text: str = Field(min_length=1, max_length=1_000_000)


class PlanPageRequest(Contract):
    sandbox_id: Text
    plan_id: Text
    path: Text


class SkillGuideRequest(Contract):
    pass
