"""Observe Raw evidence for the facets requested by a Knowledge Skill.

These are retrieval observations, not proof that a model's claims are true.
Only the Host can accept the final cited answer. A missing observation must
remain a visible gap rather than an invented recommendation.
"""

import re
from typing import Literal, Self

from pydantic import Field, model_validator

from common.base import Contract, Symbol
from knowledge.procedure import KnowledgeFacetInstruction, KnowledgeProcedure
from knowledge.query import Answer, Citation, Passage, RetrievalSnapshot, cited_numbers, tokens
from knowledge.vault import Vault


class FacetObservation(Contract):
    name: Symbol
    passages: tuple[Passage, ...] = Field(max_length=3)
    attempts: int = Field(ge=1, le=3, strict=True)


class FacetRelation(Contract):
    left: Symbol
    right: Symbol
    citation: Citation


def connected_facets(
    names: tuple[str, ...], edges: tuple[tuple[str, str], ...]
) -> bool:
    """Every requested facet must be connected by direct Raw relationships."""
    if len(names) < 2:
        return True
    reached = {names[0]}
    pending = list(reached)
    while pending:
        current = pending.pop()
        for left, right in edges:
            other = right if left == current else (left if right == current else None)
            if other in names and other not in reached:
                reached.add(other)
                pending.append(other)
    return reached == set(names)


class KnowledgeEvidenceAssessment(Contract):
    status: Literal["covered", "missing"]
    observations: tuple[FacetObservation, ...] = ()
    missing_facets: tuple[Symbol, ...] = ()
    relation_required: bool = False
    relation_passages: tuple[Passage, ...] = Field(default=(), max_length=3)
    relations: tuple[FacetRelation, ...] = Field(default=(), max_length=18)

    @model_validator(mode="after")
    def consistent(self) -> Self:
        observed = {item.name for item in self.observations}
        if len(observed) != len(self.observations):
            raise ValueError("facet observations must be unique")
        expected_missing = tuple(
            item.name for item in self.observations if not item.passages
        )
        if self.missing_facets != expected_missing:
            raise ValueError("missing facets must match observations")
        connected = connected_facets(
            tuple(item.name for item in self.observations),
            tuple((item.left, item.right) for item in self.relations),
        )
        covered = not self.missing_facets and (not self.relation_required or connected)
        if (self.status == "covered") != covered:
            raise ValueError("coverage status must match observed evidence")
        return self

    def selected_passages(self) -> tuple[Passage, ...]:
        """Use a bounded union of observed Raw, preserving provenance."""
        selected: list[Passage] = []
        seen: set[tuple[str, int | None, str]] = set()
        for passage in (
            *(passage for item in self.observations for passage in item.passages),
            *self.relation_passages,
        ):
            key = (
                passage.citation.raw_ref or "",
                passage.citation.section,
                passage.text,
            )
            if key not in seen and len(selected) < 16:
                selected.append(passage)
                seen.add(key)
        return tuple(selected)

    def summary(self) -> "KnowledgeEvidenceSummary":
        return KnowledgeEvidenceSummary(
            status=self.status,
            facets=tuple(
                FacetEvidenceSummary(
                    name=item.name,
                    citations=tuple(passage.citation for passage in item.passages),
                    attempts=item.attempts,
                )
                for item in self.observations
            ),
            missing_facets=self.missing_facets,
            relation_required=self.relation_required,
            relation_citations=tuple(passage.citation for passage in self.relation_passages),
            relations=self.relations,
        )


class FacetEvidenceSummary(Contract):
    name: Symbol
    citations: tuple[Citation, ...] = Field(max_length=3)
    attempts: int = Field(ge=1, le=3, strict=True)


class KnowledgeEvidenceSummary(Contract):
    status: Literal["covered", "missing"]
    facets: tuple[FacetEvidenceSummary, ...] = ()
    missing_facets: tuple[Symbol, ...] = ()
    relation_required: bool = False
    relation_citations: tuple[Citation, ...] = Field(default=(), max_length=3)
    relations: tuple[FacetRelation, ...] = Field(default=(), max_length=18)


_CLAIM_STOPWORDS = {
    "about", "after", "also", "answer", "because", "before", "could", "from", "have",
    "into", "only", "other", "that", "their", "there", "these", "this", "those",
    "with", "would", "should", "source", "sources", "evidence", "raw", "資料", "來源",
    "證據", "可以", "需要", "以及", "因此", "目前", "根據", "這些", "該項",
}


def answer_claims_overlap_raw(answer: Answer) -> bool:
    """Reject obvious citation laundering; this is not semantic entailment.

    Each answer sentence needs meaningful lexical overlap with its cited Raw
    passages, and every stated number must occur there. Stronger strategic
    claims still need the separate direct-relationship check.
    """
    attached = re.sub(r"([.!?。！？])\s*(\[[0-9][0-9,\s-]*\])", r" \2\1", answer.text)
    for sentence in re.split(r"(?<=[.!?])\s+|(?<=[。！？])\s*", attached):
        if not sentence.strip():
            continue
        numbers = cited_numbers(sentence)
        sources = [
            answer.passages[number - 1].text
            for number in numbers if 1 <= number <= len(answer.passages)
            and answer.passages[number - 1].citation.kind == "raw"
        ]
        if not sources:
            return False
        claim = re.sub(r"\[[0-9][0-9,\s-]*\]", "", sentence)
        source_text = " ".join(sources)
        stated_numbers = set(re.findall(r"\b\d+(?:\.\d+)?\b", claim))
        source_numbers = set(re.findall(r"\b\d+(?:\.\d+)?\b", source_text))
        if not stated_numbers <= source_numbers:
            return False
        claim_terms = {
            term for term in tokens(claim)
            if len(term) >= 2 and term not in _CLAIM_STOPWORDS
        }
        source_terms = set(tokens(source_text))
        if not claim_terms or len(claim_terms & source_terms) < min(2, len(claim_terms)):
            return False
    return True


def _supports_facet(
    passage: Passage, facet: KnowledgeFacetInstruction, subject: str | None
) -> bool:
    if passage.citation.kind != "raw":
        return False
    content = passage.text.casefold()
    source_identity = f"{passage.text} {passage.citation.raw_ref or ''}".casefold()
    if facet.include_subject and subject and subject.casefold() not in source_identity:
        return False
    return any(term.casefold() in content for term in facet.support_terms)


def _relation_pairs(
    passage: Passage,
    facets: tuple[KnowledgeFacetInstruction, ...],
    subject: str | None,
    terms: tuple[str, ...],
) -> tuple[tuple[str, str], ...]:
    if passage.citation.kind != "raw":
        return ()
    pairs: set[tuple[str, str]] = set()
    for sentence in re.split(r"(?<=[.!?。！？])\s+|\n", passage.text):
        lowered = sentence.casefold()
        if not any(term.casefold() in lowered for term in terms):
            continue
        present = [
            facet.name for facet in facets
            if (
                facet.link_subject and subject is not None
                and subject.casefold() in lowered
            ) or any(
                term.casefold() in lowered
                for term in (facet.link_terms or facet.support_terms)
            )
        ]
        for left_index, left in enumerate(present):
            for right in present[left_index + 1:]:
                pairs.add((left, right))
    return tuple(sorted(pairs))


def assess_knowledge_evidence(
    vault: Vault, question: str, procedure: KnowledgeProcedure,
    *, snapshot: RetrievalSnapshot | None = None,
) -> KnowledgeEvidenceAssessment:
    """Run each Skill query once, then use its fallback only for missing facets."""
    facets = procedure.requested_facets(question)
    if not facets:
        return KnowledgeEvidenceAssessment(status="covered")
    subject = procedure.subject(question)
    snapshot = snapshot or RetrievalSnapshot(vault)
    queries = [
        f"{subject or ''} {facet.search_queries[0]}"
        if facet.include_subject else facet.search_queries[0]
        for facet in facets
    ]
    relation_required = procedure.require_relation_for_combination and len(facets) > 1
    if relation_required:
        relation_hint = " ".join(
            [subject or "", *procedure.relation_terms, *(f.search_queries[0] for f in facets)]
        )
        queries.append(relation_hint)
    batches = snapshot.batch(tuple(queries), k=12, min_raw=12)
    accepted = [
        tuple(
            passage for passage in batches[index]
            if _supports_facet(passage, facet, subject)
        )[:3]
        for index, facet in enumerate(facets)
    ]
    attempts = [1] * len(facets)
    for attempt in range(1, max(len(facet.search_queries) for facet in facets)):
        missing_indices = [
            index for index, facet in enumerate(facets)
            if not accepted[index] and attempt < len(facet.search_queries)
        ]
        if not missing_indices:
            break
        retry_queries = tuple(
            f"{subject or ''} {facets[index].search_queries[attempt]}"
            if facets[index].include_subject else facets[index].search_queries[attempt]
            for index in missing_indices
        )
        retry_batches = snapshot.batch(retry_queries, k=12, min_raw=12)
        for index, batch in zip(missing_indices, retry_batches, strict=True):
            attempts[index] += 1
            accepted[index] = tuple(
                passage for passage in batch
                if _supports_facet(passage, facets[index], subject)
            )[:3]
    observations = tuple(
        FacetObservation(name=facet.name, passages=accepted[index], attempts=attempts[index])
        for index, facet in enumerate(facets)
    )
    relation_pairs = (
        tuple(
            (passage, _relation_pairs(passage, facets, subject, procedure.relation_terms))
            for passage in batches[-1]
        ) if relation_required else ()
    )
    relation_passages = tuple(
        passage for passage, pairs in relation_pairs if pairs
    )[:3]
    relations = tuple(
        FacetRelation(left=left, right=right, citation=passage.citation)
        for passage, pairs in relation_pairs
        if passage in relation_passages
        for left, right in pairs
    )
    missing = tuple(item.name for item in observations if not item.passages)
    linked = connected_facets(
        tuple(facet.name for facet in facets),
        tuple((item.left, item.right) for item in relations),
    )
    status: Literal["covered", "missing"] = (
        "covered" if not missing and (not relation_required or linked) else "missing"
    )
    return KnowledgeEvidenceAssessment(
        status=status,
        observations=observations,
        missing_facets=missing,
        relation_required=relation_required,
        relation_passages=relation_passages,
        relations=relations,
    )
