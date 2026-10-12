"""Bridge capabilities of the sandboxed Knowledge pipeline (docs/phases/KNOWLEDGE_K1.md).

Every write lands in the caller's sandbox under the Host workspace, which the
person can discard. As every side-effecting capability, the writing steps
require an approved grant (`approval_ref`); each call is then the person's own
action. Writing to a base vault is not offered here (merge is stage K3).
"""

from __future__ import annotations

import asyncio
import base64
import binascii
from collections.abc import Callable
from typing import Any

from capabilities.contracts import CapabilitySpec
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
from capabilities.runtime import CapabilityRefused
from common.base import Contract
from common.execution import RequestContext
from knowledge.pipeline import KnowledgePipeline, PipelineError
from knowledge.sandbox import SandboxError
from knowledge.vault import VaultError

PERMISSION = "knowledge-pipeline.use"
POLICY = "knowledge-sandbox-policy"


def _spec(name: str, description: str, side_effect: str, risk: str = "low") -> CapabilitySpec:
    return CapabilitySpec.model_validate({
        "identity": {"namespace": "knowledge-pipeline", "name": name, "version": "1.0.0"},
        "name": f"knowledge_pipeline.{name.replace('-', '_')}",
        "description": description,
        "input_contract": f"knowledge-pipeline.{name}.input.v1",
        "output_contract": f"knowledge-pipeline.{name}.output.v1",
        "side_effect": side_effect,
        "policy": {"risk": risk, "approval_required": side_effect != "read",
                   "required_permissions": [PERMISSION], "policy_refs": [POLICY]},
    })


SANDBOX_CREATE_SPEC = _spec("sandbox-create", "Copy a base Knowledge vault into a personal sandbox",
                            "write")
SANDBOX_LIST_SPEC = _spec("sandbox-list", "List the personal Knowledge sandboxes", "read")
CONVERT_SPEC = _spec("convert", "Preview or write drop originals into Raw in a sandbox", "write")
INGEST_PLAN_SPEC = _spec("ingest-plan", "Plan the wiki writes for one Raw document in a sandbox",
                         "read", "medium")
INGEST_APPLY_SPEC = _spec("ingest-apply", "Apply a stored ingest plan to a sandbox wiki", "write",
                          "medium")
LINT_SPEC = _spec("lint", "Static lint and open conflicts of a sandbox wiki", "read")
ADOPT_SPEC = _spec("adopt", "Adopt Raw from earlier tooling in a sandbox so it can be ingested",
                   "write")
INDEX_ENRICH_SPEC = _spec("index-enrich",
                          "Write bilingual aliases, summary and categories into sandbox pages",
                          "write", "medium")
DROP_FOLDERS_SPEC = _spec("drop-folders", "List the project vault's drop folders", "read")
PULL_SPEC = _spec("pull", "Copy chosen drop folders of the project vault into a sandbox",
                  "write")
RULE_FILES_SPEC = _spec("rule-files", "List a sandbox's schema and skill files", "read")
FILE_READ_SPEC = _spec("file-read", "Read one Markdown file of a sandbox for preview", "read")
RULE_WRITE_SPEC = _spec("rule-write", "Save the schema or a skill file in a sandbox",
                        "write")
PLAN_PAGE_SPEC = _spec("plan-page", "Show a planned page before and after", "read")
QUESTION_SETS_SPEC = _spec("question-sets", "List a sandbox's benchmark question sets",
                           "read")
SKILL_GUIDE_SPEC = _spec("skill-guide", "The skill writing guide and templates", "read")
MERGE_SPEC = _spec("merge", "Preview or write a three-way merge of a sandbox into a new "
                   "candidate vault; the published vault is never edited", "write", "medium")
INDEX_BUILD_SPEC = _spec("index-build", "Preview or write the layered index of a sandbox",
                         "write")
DROP_ADD_SPEC = _spec("drop-add", "Put one original into a sandbox drop folder", "write")
SANDBOX_CONTENTS_SPEC = _spec("sandbox-contents", "List originals, Raw and plans of a sandbox",
                              "read")
SANDBOX_DISCARD_SPEC = _spec("sandbox-discard", "Move a personal sandbox aside (never deleted)",
                             "write")


async def _run(call: Callable[[], Any]) -> Any:
    try:
        return await asyncio.to_thread(call)
    except (PipelineError, SandboxError, VaultError) as error:
        raise CapabilityRefused(str(getattr(error, "code", "knowledge_pipeline_refused"))) from None


class SandboxCreateHandler:
    def __init__(self, pipeline: KnowledgePipeline) -> None:
        self.pipeline = pipeline

    async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
        request = SandboxCreateRequest.model_validate(inputs)
        info = await _run(lambda: self.pipeline.create_sandbox(
            request.base, request.label, context.actor, request.domain))
        return SandboxRecord(sandbox_id=info.sandbox_id, base_name=info.base_name,
                             label=info.label, created_by=info.created_by,
                             created_at=info.created_at)


class SandboxListHandler:
    def __init__(self, pipeline: KnowledgePipeline) -> None:
        self.pipeline = pipeline

    async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
        SandboxListRequest.model_validate(inputs)
        found = await _run(self.pipeline.sandboxes.list)
        return SandboxList(sandboxes=tuple(
            SandboxRecord(sandbox_id=i.sandbox_id, base_name=i.base_name, label=i.label,
                          created_by=i.created_by, created_at=i.created_at) for i in found))


class ConvertHandler:
    def __init__(self, pipeline: KnowledgePipeline) -> None:
        self.pipeline = pipeline

    async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
        request = ConvertRequest.model_validate(inputs)
        result: Contract = await _run(lambda: self.pipeline.convert(
            request.sandbox_id, tuple(request.paths), request.mode))
        return result


class IngestPlanHandler:
    def __init__(self, pipeline: KnowledgePipeline) -> None:
        self.pipeline = pipeline

    async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
        request = IngestPlanRequest.model_validate(inputs)
        result: Contract = await _run(lambda: self.pipeline.plan_ingest(
            request.sandbox_id, request.raw_ref))
        return result


class IngestApplyHandler:
    def __init__(self, pipeline: KnowledgePipeline) -> None:
        self.pipeline = pipeline

    async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
        request = IngestApplyRequest.model_validate(inputs)
        result: Contract = await _run(lambda: self.pipeline.apply_ingest(
            request.sandbox_id, request.plan_id))
        return result


class LintHandler:
    def __init__(self, pipeline: KnowledgePipeline) -> None:
        self.pipeline = pipeline

    async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
        request = LintRequest.model_validate(inputs)
        result: Contract = await _run(lambda: self.pipeline.lint(request.sandbox_id))
        return result


class DropAddHandler:
    def __init__(self, pipeline: KnowledgePipeline) -> None:
        self.pipeline = pipeline

    async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
        request = DropAddRequest.model_validate(inputs)
        try:
            data = base64.b64decode(request.data_base64, validate=True)
        except (binascii.Error, ValueError):
            raise CapabilityRefused("drop_not_base64") from None
        path = await _run(lambda: self.pipeline.add_drop(request.sandbox_id, request.name, data))
        return DropAdded(sandbox_id=request.sandbox_id, path=path)


class SandboxContentsHandler:
    def __init__(self, pipeline: KnowledgePipeline) -> None:
        self.pipeline = pipeline

    async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
        request = SandboxRef.model_validate(inputs)
        result: Contract = await _run(lambda: self.pipeline.contents(request.sandbox_id))
        return result


class SandboxDiscardHandler:
    def __init__(self, pipeline: KnowledgePipeline) -> None:
        self.pipeline = pipeline

    async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
        request = SandboxRef.model_validate(inputs)
        await _run(lambda: self.pipeline.discard_sandbox(request.sandbox_id))
        return SandboxDiscarded(sandbox_id=request.sandbox_id)


class AdoptHandler:
    def __init__(self, pipeline: KnowledgePipeline) -> None:
        self.pipeline = pipeline

    async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
        request = AdoptRequest.model_validate(inputs)
        result: Contract = await _run(lambda: self.pipeline.adopt(request.sandbox_id, request.mode))
        return result


class IndexEnrichHandler:
    def __init__(self, pipeline: KnowledgePipeline) -> None:
        self.pipeline = pipeline

    async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
        request = IndexEnrichRequest.model_validate(inputs)
        result: Contract = await _run(
            lambda: self.pipeline.index_enrich(request.sandbox_id, request.limit))
        return result


class IndexBuildHandler:
    def __init__(self, pipeline: KnowledgePipeline) -> None:
        self.pipeline = pipeline

    async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
        request = IndexBuildRequest.model_validate(inputs)
        result: Contract = await _run(
            lambda: self.pipeline.index_build(request.sandbox_id, request.mode))
        return result


class MergeHandler:
    def __init__(self, pipeline: KnowledgePipeline) -> None:
        self.pipeline = pipeline

    async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
        request = MergeRequest.model_validate(inputs)
        result: Contract = await _run(lambda: self.pipeline.merge(
            request.sandbox_id, request.mode, dict(request.resolutions)))
        return result


class DropFoldersHandler:
    def __init__(self, pipeline: KnowledgePipeline) -> None:
        self.pipeline = pipeline

    async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
        request = DropFoldersRequest.model_validate(inputs)
        result: Contract = await _run(lambda: self.pipeline.drop_folders(request.base))
        return result


class PullHandler:
    def __init__(self, pipeline: KnowledgePipeline) -> None:
        self.pipeline = pipeline

    async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
        request = PullRequest.model_validate(inputs)
        result: Contract = await _run(lambda: self.pipeline.pull(
            request.sandbox_id, tuple(request.folders)))
        return result


class RuleFilesHandler:
    def __init__(self, pipeline: KnowledgePipeline) -> None:
        self.pipeline = pipeline

    async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
        request = SandboxRef.model_validate(inputs)
        result: Contract = await _run(lambda: self.pipeline.rule_files(request.sandbox_id))
        return result


class FileReadHandler:
    def __init__(self, pipeline: KnowledgePipeline) -> None:
        self.pipeline = pipeline

    async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
        request = FileRequest.model_validate(inputs)
        result: Contract = await _run(
            lambda: self.pipeline.read_file(request.sandbox_id, request.path))
        return result


class RuleWriteHandler:
    def __init__(self, pipeline: KnowledgePipeline) -> None:
        self.pipeline = pipeline

    async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
        request = RuleWriteRequest.model_validate(inputs)
        result: Contract = await _run(
            lambda: self.pipeline.write_rule(request.sandbox_id, request.path, request.text))
        return result


class PlanPageHandler:
    def __init__(self, pipeline: KnowledgePipeline) -> None:
        self.pipeline = pipeline

    async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
        request = PlanPageRequest.model_validate(inputs)
        result: Contract = await _run(lambda: self.pipeline.plan_page(
            request.sandbox_id, request.plan_id, request.path))
        return result


class QuestionSetsHandler:
    def __init__(self, pipeline: KnowledgePipeline) -> None:
        self.pipeline = pipeline

    async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
        request = SandboxRef.model_validate(inputs)
        result: Contract = await _run(lambda: self.pipeline.question_sets(request.sandbox_id))
        return result


class SkillGuideHandler:
    def __init__(self, pipeline: KnowledgePipeline) -> None:
        self.pipeline = pipeline

    async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
        SkillGuideRequest.model_validate(inputs)
        result: Contract = await _run(self.pipeline.skill_guide)
        return result
