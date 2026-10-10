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
    ConvertRequest,
    DropAdded,
    DropAddRequest,
    IngestApplyRequest,
    IngestPlanRequest,
    LintRequest,
    SandboxCreateRequest,
    SandboxDiscarded,
    SandboxList,
    SandboxListRequest,
    SandboxRecord,
    SandboxRef,
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
            request.base, request.label, context.actor))
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
