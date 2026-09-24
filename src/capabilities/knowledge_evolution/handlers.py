"""Bridge-installed creation of an approved Knowledge candidate workspace."""

import asyncio
from pathlib import Path

from capabilities.contracts import CapabilitySpec
from capabilities.runtime import CapabilityRefused
from common.base import Contract
from common.execution import RequestContext
from knowledge.evolution import (
    KnowledgeCandidateRequest,
    KnowledgeCatalog,
    create_candidate,
)

KNOWLEDGE_CANDIDATE_SPEC = CapabilitySpec.model_validate(
    {
        "identity": {
            "namespace": "knowledge-evolution",
            "name": "create-candidate",
            "version": "1.0.0",
        },
        "name": "knowledge_evolution.create_candidate",
        "description": "Create an approved Knowledge candidate in a separate local vault",
        "input_contract": "knowledge-evolution.candidate.input.v1",
        "output_contract": "knowledge-evolution.candidate.output.v1",
        "side_effect": "write",
        "policy": {
            "risk": "medium",
            "approval_required": True,
            "required_permissions": ["knowledge-evolution.create-candidate"],
            "policy_refs": ["knowledge-candidate-workspace-policy"],
        },
    }
)


class KnowledgeCandidateHandler:
    def __init__(self, catalog: KnowledgeCatalog, *, workspace_root: Path) -> None:
        self.catalog = catalog
        self.workspace_root = workspace_root.resolve()

    async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
        request = KnowledgeCandidateRequest.model_validate(inputs)
        found = self.catalog.get(request.base)
        if found is None:
            raise CapabilityRefused("knowledge_version_not_found")
        target_root = Path(request.target_root).resolve()
        try:
            relative_target = target_root.relative_to(self.workspace_root)
        except ValueError:
            raise CapabilityRefused("candidate_path_not_allowed") from None
        if not relative_target.parts:
            raise CapabilityRefused("candidate_path_not_allowed")
        manifest, vault = found
        return await asyncio.to_thread(
            create_candidate,
            manifest,
            vault,
            request.improvement,
            identity=request.candidate_identity,
            target_root=target_root,
            plan=request.plan,
            cases=request.cases,
            stamp=request.stamp,
        )
