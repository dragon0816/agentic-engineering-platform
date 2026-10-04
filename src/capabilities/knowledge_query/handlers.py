"""Bridge-installed query over exact published Knowledge versions."""

import asyncio

from capabilities.contracts import CapabilitySpec
from capabilities.runtime import CapabilityRefused
from common.base import Contract
from common.execution import RequestContext
from knowledge.evidence import (
    KnowledgeEvidenceAssessment,
    answer_claims_overlap_raw,
    answer_concerns_subject,
    assess_knowledge_evidence,
    extractive_observation_answer,
    extractive_relation_answer,
    omit_unsupported_product_recommendations,
    omit_unverified_answer_lines,
    passage_number,
)
from knowledge.evolution import KnowledgeCatalog, KnowledgeQueryRequest, grounded_record
from knowledge.market_matrix import MarketMatrixRequest, discover_market_matrix
from knowledge.query import Answer, QueryEngine
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

MARKET_MATRIX_SPEC = CapabilitySpec.model_validate(
    {
        "identity": {"namespace": "knowledge-query", "name": "market-matrix", "version": "1.0.0"},
        "name": "knowledge_query.market_matrix",
        "description": "Discover Raw evidence and gaps across the fixed product/market grid",
        "input_contract": "knowledge-query.market-matrix.input.v1",
        "output_contract": "knowledge-query.market-matrix.output.v1",
        "side_effect": "read",
        "policy": {
            "approval_required": False,
            "required_permissions": ["knowledge-query.ask"],
            "policy_refs": ["knowledge-grounding-policy"],
        },
    }
)


class MarketMatrixHandler:
    def __init__(self, catalog: KnowledgeCatalog) -> None:
        self.catalog = catalog

    async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
        request = MarketMatrixRequest.model_validate(inputs)
        found = self.catalog.get(request.asset)
        if found is None:
            raise CapabilityRefused("knowledge_version_not_found")
        _manifest, vault = found
        return await asyncio.to_thread(discover_market_matrix, request.asset, context.trace, vault)


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
        assessment: KnowledgeEvidenceAssessment | None = None
        selected_passages = None
        if request.procedure is not None:
            assessment = await asyncio.to_thread(
                assess_knowledge_evidence, vault, request.question, request.procedure
            )
            if assessment.observations:
                selected_passages = assessment.selected_passages()
                if not selected_passages:
                    raise CapabilityRefused("knowledge_insufficient_evidence")
                if assessment.status == "missing" and not request.procedure.wiki_index_first:
                    candidates = []
                    for observation in assessment.observations:
                        if not observation.passages:
                            continue
                        passage = observation.passages[0]
                        number = passage_number(selected_passages, passage)
                        if number is None:
                            raise CapabilityRefused("knowledge_insufficient_evidence")
                        candidates.append(f"Raw candidate for {observation.name} [{number}].")
                    return grounded_record(
                        request.asset, context.trace,
                        Answer(
                            question=request.question,
                            status="answered",
                            passages=selected_passages,
                            text=" ".join(candidates),
                        ),
                        assessment=assessment.summary(),
                    )
        facets = () if assessment is None else tuple(item.name for item in assessment.observations)
        facet_guidance = (
            "\n\nRequested evidence facets: " + ", ".join(facets) + ". "
            "Support each requested facet with a cited Raw passage. A comparison "
            "or recommendation needs a cited Raw passage directly connecting "
            "the relevant facets; separate co-mentions are insufficient."
            if facets else ""
        )
        skill_guidance = (
            "\n\nInstalled Knowledge Skill guidance: " + request.procedure.answer_guidance
            if request.procedure is not None and request.procedure.answer_guidance
            else ""
        )
        partial_guidance = (
            "\n\nThe retrieved evidence does not establish every requested facet or "
            "direct relationship. State only independently supported facts "
            "with Raw citations. Do not claim the requested comparison or "
            "direct link is established. The Host will report the exact gaps."
            if assessment is not None and assessment.status == "missing"
            else ""
        )
        answer = await asyncio.to_thread(
            QueryEngine(
                vault,
                self.model,
                alias=self.alias,
                max_output_tokens=(
                    request.procedure.synthesis_max_output_tokens
                    if request.procedure is not None else 800
                ),
                prompt=(
                    "Answer the question from the passages below and nothing else. "
                    "RAW passages are the only citable evidence. WIKI passages may "
                    "provide context but do not cite them or make a claim supported "
                    "only by them. Cite every supported claim with RAW passage numbers "
                    "in square brackets, like [2]. If no RAW passage supports an "
                    "answer, say so in one sentence and cite nothing.\n\n"
                    "Question: {question}\n\n{passages}"
                    + facet_guidance + skill_guidance + partial_guidance
                ),
            ).ask,
            request.question,
            k=8,
            trace=context.trace,
            raw_citations_only=True,
            evidence_coverage=selected_passages is None,
            selected_passages=selected_passages,
        )
        if (
            request.procedure is not None
            and request.procedure.wiki_index_first
            and answer.status == "answered"
        ):
            answer = omit_unsupported_product_recommendations(
                answer, request.question, request.procedure
            )
            answer = omit_unverified_answer_lines(answer)
        if (
            assessment is not None
            and request.procedure is not None
            and request.procedure.extractive_fallback
            and request.procedure.wiki_index_first
            and bool(assessment.observations)
            and (
                answer.status != "answered"
                or not answer_claims_overlap_raw(answer)
                or (
                    (subject := request.procedure.subject(request.question)) is not None
                    and not answer_concerns_subject(answer, subject)
                )
            )
        ):
            fallbacks = (
                extractive_relation_answer(
                    request.question, assessment, request.procedure
                ),
                extractive_observation_answer(
                    request.question, assessment, request.procedure
                ),
            )
            verified = None
            for fallback in fallbacks:
                if fallback is None:
                    continue
                fallback = omit_unsupported_product_recommendations(
                    fallback, request.question, request.procedure
                )
                if fallback.status != "answered":
                    continue
                try:
                    grounded_record(
                        request.asset, context.trace, fallback,
                        assessment=assessment.summary(),
                    )
                except ValueError:
                    continue
                verified = fallback
                break
            if verified is None:
                if assessment.status == "missing":
                    assert selected_passages is not None
                    candidates = []
                    for observation in assessment.observations:
                        if not observation.passages:
                            continue
                        number = passage_number(selected_passages, observation.passages[0])
                        if number is not None:
                            candidates.append(f"Raw candidate for {observation.name} [{number}].")
                    if candidates:
                        return grounded_record(
                            request.asset, context.trace,
                            Answer(
                                question=request.question, status="answered",
                                passages=selected_passages,
                                text=" ".join(candidates),
                            ),
                            assessment=assessment.summary(),
                        )
                raise CapabilityRefused("knowledge_not_grounded")
            answer = verified
        if answer.status in ("no_match", "unanswered"):
            raise CapabilityRefused("knowledge_insufficient_evidence")
        if answer.status == "model_failed":
            raise CapabilityRefused("knowledge_model_failed")
        try:
            return grounded_record(
                request.asset, context.trace, answer,
                assessment=None if assessment is None else assessment.summary(),
            )
        except ValueError:
            raise CapabilityRefused("knowledge_not_grounded") from None
