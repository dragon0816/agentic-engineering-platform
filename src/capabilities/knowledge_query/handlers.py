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
    assess_wiki_primary,
    extractive_observation_answer,
    extractive_relation_answer,
    omit_unsupported_product_recommendations,
    omit_unverified_answer_lines,
    passage_number,
)
from knowledge.evolution import (
    KnowledgeCatalog,
    KnowledgeQueryRequest,
    WikiProvenance,
    grounded_record,
)
from knowledge.market_matrix import MarketMatrixRequest, discover_market_matrix
from knowledge.procedure import KnowledgeProcedure
from knowledge.query import (
    DEFAULT_SYNTHESIS_MAX_OUTPUT_TOKENS,
    MAX_LABELED_INFERENCES,
    Answer,
    QueryEngine,
    RetrievalSnapshot,
    cited_numbers,
)
from knowledge.query_rewrite import content_words, rewrite_queries
from knowledge.search_rounds import search_rounds
from knowledge.vault import Vault
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
        if request.procedure is not None and request.procedure.citation_policy == "wiki_primary":
            return await asyncio.to_thread(
                self._wiki_primary, context, request, request.procedure, vault
            )
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
        inference_label = (
            request.procedure.inference_label if request.procedure is not None else None
        )
        inference_guidance = (
            f"\n\nYou may add at most {MAX_LABELED_INFERENCES} inference lines after the "
            f"facts. Start each inference line with {inference_label}, cite the RAW "
            "passages of its premises, and use only product codes and numbers that "
            "appear in them. An inference is not a verified fact or a direct "
            "relationship; never state it as one. Do not write unlabeled inferences."
            if inference_label else ""
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
                    if request.procedure is not None
                    else DEFAULT_SYNTHESIS_MAX_OUTPUT_TOKENS
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
                    + inference_guidance
                ),
                inference_label=inference_label,
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
            answer = omit_unverified_answer_lines(answer, inference_label=inference_label)
        if (
            assessment is not None
            and request.procedure is not None
            and request.procedure.extractive_fallback
            and request.procedure.wiki_index_first
            and bool(assessment.observations)
            and (
                answer.status != "answered"
                or not answer_claims_overlap_raw(answer, inference_label=inference_label)
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

    def _wiki_primary(
        self, context: RequestContext, request: KnowledgeQueryRequest,
        procedure: KnowledgeProcedure, vault: Vault,
    ) -> Contract:
        """Answer from curated Wiki sections, with Raw as provenance and fallback."""
        snapshot = RetrievalSnapshot(vault)
        subject = procedure.subject(request.question)
        focus = procedure.focus(request.question)
        prefix = " ".join(part for part in (subject, focus.query if focus else None) if part)
        bilingual = procedure.bilingual_retrieval
        if bilingual and not prefix:
            # A facet query without the question's words finds the same pages
            # for every question.
            prefix = content_words(request.question)
        queries = [request.question, *(focus.expansions if focus else ())]
        if bilingual:
            queries[1:1] = rewrite_queries(
                self.model, self.alias, request.question, context.trace)
        for facet in procedure.requested_facets(request.question):
            for search in (*facet.search_queries, *facet.discovery_queries)[:2]:
                queries.append(f"{prefix} {search}".strip())
        sections = procedure.evidence_sections or (36 if bilingual else 24)
        chars = procedure.evidence_chars or 40000
        passages = snapshot.wiki_primary_passages(
            tuple(dict.fromkeys(queries))[:12], k=sections, max_chars=chars,
            content_only=bilingual)
        if procedure.retrieval_rounds and passages:
            passages = search_rounds(
                snapshot, self.model, self.alias, context.trace, request.question,
                passages, rounds=procedure.retrieval_rounds, k=sections, max_chars=chars,
                per_page=procedure.evidence_sections_per_page)
        if not passages:
            raise CapabilityRefused("knowledge_insufficient_evidence")
        assessment = assess_wiki_primary(passages, request.question, procedure)
        label = procedure.inference_label
        facets = tuple(item.name for item in assessment.observations)
        prompt = (
            "Answer the question from the passages below and nothing else. WIKI "
            "passages are the curated knowledge base and the primary evidence; RAW "
            "passages are original source text for claims the Wiki does not cover. "
            "Cite every supported claim with passage numbers in square brackets, "
            "like [2]. Never cite a passage that does not state the claim. If no "
            "passage supports an answer, say so in one sentence and cite nothing."
            "\n\nQuestion: {question}\n\n{passages}"
            + (
                "\n\nRequested evidence facets: " + ", ".join(facets) + ". A "
                "comparison or recommendation needs a cited passage directly "
                "connecting the relevant facets; separate co-mentions are insufficient."
                if facets else ""
            )
            + (
                "\n\nInstalled Knowledge Skill guidance: " + procedure.answer_guidance
                if procedure.answer_guidance else ""
            )
            + (
                "\n\nThe retrieved evidence does not establish every requested facet or "
                "direct relationship. Still state every independently supported fact "
                "with citations; do not claim the missing comparison or direct link. "
                "The Host will report the exact gaps."
                if assessment.status == "missing" else ""
            )
            + (
                f"\n\nYou may add at most {MAX_LABELED_INFERENCES} inference lines after "
                f"the facts. Start each inference line with {label}, cite the passages "
                "of its premises, and use only product codes and numbers that appear "
                "in them. An inference is not a verified fact or a direct relationship."
                if label else ""
            )
        )
        answer = QueryEngine(
            vault, self.model, alias=self.alias,
            max_output_tokens=procedure.synthesis_max_output_tokens,
            prompt=prompt, inference_label=label, allow_wiki=True,
        ).ask(
            request.question, trace=context.trace, raw_citations_only=True,
            selected_passages=passages,
        )
        if answer.status == "model_failed":
            raise CapabilityRefused("knowledge_model_failed")
        if answer.status == "answered":
            answer = omit_unsupported_product_recommendations(
                answer, request.question, procedure, allow_wiki=True
            )
            answer = omit_unverified_answer_lines(
                answer, inference_label=label, allow_wiki=True
            )
        if answer.status != "answered":
            raise CapabilityRefused("knowledge_insufficient_evidence")
        cited_pages = tuple(dict.fromkeys(
            passage.citation.wiki_page
            for number, passage in enumerate(answer.passages, 1)
            if number in cited_numbers(answer.text)
            and passage.citation.kind == "wiki" and passage.citation.wiki_page
        ))
        try:
            return grounded_record(
                request.asset, context.trace, answer,
                assessment=assessment.summary(),
                citation_policy="wiki_primary",
                wiki_provenance=tuple(
                    WikiProvenance(wiki_page=page, raw_refs=snapshot.wiki_provenance(page))
                    for page in cited_pages
                ),
            )
        except ValueError:
            raise CapabilityRefused("knowledge_not_grounded") from None
