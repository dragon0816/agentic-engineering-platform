"""Bridge-installed query over exact published Knowledge versions."""

import asyncio

from capabilities.contracts import CapabilitySpec
from capabilities.runtime import CapabilityRefused
from common.base import Contract
from common.execution import RequestContext
from knowledge.evolution import KnowledgeCatalog, KnowledgeQueryRequest, grounded_record
from knowledge.query import QueryEngine
from models.contracts import ModelClient

KNOWLEDGE_QUERY_SPEC = CapabilitySpec.model_validate(
    {
        "identity": {"namespace": "knowledge-query", "name": "ask", "version": "1.0.0"},
        "name": "knowledge_query.ask",
        "description": "Answer from one exact published Knowledge version with Raw citations",
        "input_contract": "knowledge-query.ask.input.v1",
        "output_contract": "knowledge-query.ask.output.v1",
        "side_effect": "read",
        "policy": {
            "approval_required": False,
            "required_permissions": ["knowledge-query.ask"],
            "policy_refs": ["knowledge-grounding-policy"],
        },
    }
)


class KnowledgeQueryHandler:
    def __init__(self, catalog: KnowledgeCatalog, model: ModelClient, *, alias: str) -> None:
        self.catalog = catalog
        self.model = model
        self.alias = alias

    async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
        request = KnowledgeQueryRequest.model_validate(inputs)
        found = self.catalog.get(request.asset)
        if found is None:
            raise CapabilityRefused("knowledge_version_not_found")
        _manifest, vault = found
        answer = await asyncio.to_thread(
            QueryEngine(
                vault,
                self.model,
                alias=self.alias,
                prompt=(
                    "Answer the question from the passages below and nothing else. "
                    "RAW passages are the only citable evidence. WIKI passages may "
                    "provide context but do not cite them or make a claim supported "
                    "only by them. Cite every supported claim with RAW passage numbers "
                    "in square brackets, like [2]. If no RAW passage supports an "
                    "answer, say so in one sentence and cite nothing.\n\n"
                    "Question: {question}\n\n{passages}"
                ),
            ).ask,
            request.question,
            k=8,
            trace=context.trace,
            raw_citations_only=True,
            evidence_coverage=True,
        )
        if answer.status in ("no_match", "unanswered"):
            raise CapabilityRefused("knowledge_insufficient_evidence")
        if answer.status == "model_failed":
            raise CapabilityRefused("knowledge_model_failed")
        try:
            return grounded_record(request.asset, context.trace, answer)
        except ValueError:
            raise CapabilityRefused("knowledge_not_grounded") from None
