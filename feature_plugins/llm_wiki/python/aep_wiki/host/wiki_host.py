"""The LLM Wiki's sandboxed Knowledge pipeline on the Host (docs/phases/KNOWLEDGE_K1.md).

Built from host.json `knowledge_pipeline` (its format stays in core,
`host_runtime.contracts`) and registered as the 21 `knowledge-pipeline/*`
capabilities. Moved unchanged from `host_runtime.host`
(docs/phases/FEATURE_PLUGIN_WIKI_PROPOSAL_DRAFT_20261118.md stage A); the Host
asks the feature for these bindings at the place it registered them before.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from aep_wiki.capabilities.handlers import (
    ADOPT_SPEC,
    CONVERT_SPEC,
    DROP_ADD_SPEC,
    DROP_FOLDERS_SPEC,
    FILE_READ_SPEC,
    INDEX_BUILD_SPEC,
    INDEX_ENRICH_SPEC,
    INGEST_APPLY_SPEC,
    INGEST_PLAN_SPEC,
    LINT_SPEC,
    MERGE_SPEC,
    PLAN_PAGE_SPEC,
    PULL_SPEC,
    QUESTION_SETS_SPEC,
    RULE_FILES_SPEC,
    RULE_WRITE_SPEC,
    SANDBOX_CONTENTS_SPEC,
    SANDBOX_CREATE_SPEC,
    SANDBOX_DISCARD_SPEC,
    SANDBOX_LIST_SPEC,
    SKILL_GUIDE_SPEC,
    AdoptHandler,
    ConvertHandler,
    DropAddHandler,
    DropFoldersHandler,
    FileReadHandler,
    IndexBuildHandler,
    IndexEnrichHandler,
    IngestApplyHandler,
    IngestPlanHandler,
    LintHandler,
    MergeHandler,
    PlanPageHandler,
    PullHandler,
    QuestionSetsHandler,
    RuleFilesHandler,
    RuleWriteHandler,
    SandboxContentsHandler,
    SandboxCreateHandler,
    SandboxDiscardHandler,
    SandboxListHandler,
    SkillGuideHandler,
)
from aep_wiki.knowledge.describe import ImageDescriber
from aep_wiki.knowledge.pipeline import (
    AdoptSummary,
    ConvertResult,
    DropFolders,
    IngestApplyResult,
    IngestPlanResult,
    KnowledgePipeline,
    LintSummary,
    MergeReport,
    PlanPage,
    PullResult,
    QuestionSets,
    RuleFiles,
    SandboxContents,
    SandboxFile,
    SkillGuide,
)
from aep_wiki.knowledge.sandbox import Sandboxes
from capabilities.knowledge_pipeline.contracts import (
    AdoptRequest,
    ConvertRequest,
    DropAdded,
    DropAddRequest,
    DropFoldersRequest,
    FileRequest,
    IndexBuildRequest,
    IndexEnrichRequest,
    IngestApplyRequest,
    IngestPlanRequest,
    LintRequest,
    MergeRequest,
    PlanPageRequest,
    PullRequest,
    RuleWriteRequest,
    SandboxCreateRequest,
    SandboxDiscarded,
    SandboxList,
    SandboxListRequest,
    SandboxRecord,
    SandboxRef,
    SkillGuideRequest,
)
from host_runtime.contracts import CompanyHostConfiguration, HostLayout
from knowledge.layered_index import EnrichReport, IndexReport
from knowledge.office import office_extractors
from models.contracts import ModelClient


def pipeline_bindings(
    config: CompanyHostConfiguration,
    layout: HostLayout,
    model: ModelClient | None,
) -> list[tuple[Any, Any, Any, Any]]:
    """Sandboxed convert/ingest/lint (docs/phases/KNOWLEDGE_K1.md). Ingest
    planning and image description use the routing model when there is one;
    images are described only when its endpoint declares vision."""
    assert config.knowledge_pipeline is not None
    binding = config.models
    alias = binding.routing_alias if binding is not None else None
    endpoints = binding.catalog.endpoints if binding is not None else ()
    endpoint = next((e for e in endpoints if e.alias == alias), None)
    describer = (
        ImageDescriber(model, alias=alias)
        if model is not None
        and alias is not None
        and endpoint is not None
        and endpoint.capabilities.vision
        else None
    )
    pipeline = KnowledgePipeline(
        Sandboxes(
            layout.workspace_root,
            root=(
                Path(config.knowledge_pipeline.sandbox_root)
                if config.knowledge_pipeline.sandbox_root
                else None
            ),
        ),
        {item.name: Path(item.root) for item in config.knowledge_pipeline.vaults},
        extractors=office_extractors(),
        model=model,
        alias=alias,
        describer=describer,
        drop_roots={
            item.name: Path(item.drop_root)
            for item in config.knowledge_pipeline.vaults
            if item.drop_root
        },
        questions_roots={
            item.name: Path(item.questions_root)
            for item in config.knowledge_pipeline.vaults
            if item.questions_root
        },
        maintainers={
            item.name: tuple(item.maintainers) for item in config.knowledge_pipeline.vaults
        },
    )
    return [
        (SANDBOX_CREATE_SPEC, SandboxCreateHandler(pipeline), SandboxCreateRequest, SandboxRecord),
        (SANDBOX_LIST_SPEC, SandboxListHandler(pipeline), SandboxListRequest, SandboxList),
        (CONVERT_SPEC, ConvertHandler(pipeline), ConvertRequest, ConvertResult),
        (INGEST_PLAN_SPEC, IngestPlanHandler(pipeline), IngestPlanRequest, IngestPlanResult),
        (INGEST_APPLY_SPEC, IngestApplyHandler(pipeline), IngestApplyRequest, IngestApplyResult),
        (LINT_SPEC, LintHandler(pipeline), LintRequest, LintSummary),
        (ADOPT_SPEC, AdoptHandler(pipeline), AdoptRequest, AdoptSummary),
        (INDEX_ENRICH_SPEC, IndexEnrichHandler(pipeline), IndexEnrichRequest, EnrichReport),
        (INDEX_BUILD_SPEC, IndexBuildHandler(pipeline), IndexBuildRequest, IndexReport),
        (MERGE_SPEC, MergeHandler(pipeline), MergeRequest, MergeReport),
        (DROP_FOLDERS_SPEC, DropFoldersHandler(pipeline), DropFoldersRequest, DropFolders),
        (PULL_SPEC, PullHandler(pipeline), PullRequest, PullResult),
        (QUESTION_SETS_SPEC, QuestionSetsHandler(pipeline), SandboxRef, QuestionSets),
        (RULE_FILES_SPEC, RuleFilesHandler(pipeline), SandboxRef, RuleFiles),
        (FILE_READ_SPEC, FileReadHandler(pipeline), FileRequest, SandboxFile),
        (RULE_WRITE_SPEC, RuleWriteHandler(pipeline), RuleWriteRequest, SandboxFile),
        (PLAN_PAGE_SPEC, PlanPageHandler(pipeline), PlanPageRequest, PlanPage),
        (SKILL_GUIDE_SPEC, SkillGuideHandler(pipeline), SkillGuideRequest, SkillGuide),
        (DROP_ADD_SPEC, DropAddHandler(pipeline), DropAddRequest, DropAdded),
        (SANDBOX_CONTENTS_SPEC, SandboxContentsHandler(pipeline), SandboxRef, SandboxContents),
        (SANDBOX_DISCARD_SPEC, SandboxDiscardHandler(pipeline), SandboxRef, SandboxDiscarded),
    ]
