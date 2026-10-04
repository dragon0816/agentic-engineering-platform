"""Typed Knowledge query procedure supplied by an installed Skill.

The shared Agent harness treats Skill procedure JSON as opaque. Only the
Knowledge adapter interprets these search and evidence hints; they are never
execution grants or substitutes for Host validation.
"""

import re
from typing import Literal, Self

from pydantic import Field, model_validator

from common.base import Contract, Symbol, Text


class KnowledgeFacetEvidenceRequirement(Contract):
    question_pattern: Text
    evidence_patterns: tuple[Text, ...] = Field(min_length=1, max_length=8)


class KnowledgeFacetInstruction(Contract):
    name: Symbol
    request_patterns: tuple[Text, ...] = Field(min_length=1, max_length=12)
    search_queries: tuple[Text, ...] = Field(min_length=1, max_length=3)
    discovery_queries: tuple[Text, ...] = Field(default=(), max_length=3)
    support_terms: tuple[Text, ...] = Field(min_length=1, max_length=12)
    search_subject: bool = False
    include_subject: bool = False
    link_terms: tuple[Text, ...] = Field(default=(), max_length=12)
    link_subject: bool = False
    focus_is_support: bool = False
    focus_is_link: bool = False
    require_focus: bool = False
    require_focus_when_unbound: bool = False
    entity_pattern: Text | None = None
    evidence_requirements: tuple[KnowledgeFacetEvidenceRequirement, ...] = Field(
        default=(), max_length=8
    )
    comparison_terms: tuple[Text, ...] = Field(default=(), max_length=8)
    source_areas: tuple[Text, ...] = Field(default=(), max_length=8)
    collect_all_queries: bool = False
    max_passages: int = Field(default=3, ge=1, le=6, strict=True)


class KnowledgeFocusHint(Contract):
    pattern: Text
    query: Text
    evidence_terms: tuple[Text, ...] = Field(min_length=1, max_length=8)


class KnowledgeProcedure(Contract):
    kind: Literal["knowledge_query_v1"] = "knowledge_query_v1"
    intent_patterns: tuple[Text, ...] = Field(min_length=1, max_length=20)
    subject_pattern: Text | None = None
    focus_hints: tuple[KnowledgeFocusHint, ...] = Field(default=(), max_length=20)
    facets: tuple[KnowledgeFacetInstruction, ...] = Field(min_length=1, max_length=12)
    relation_terms: tuple[Text, ...] = Field(default=(), max_length=20)
    relation_search_queries: tuple[Text, ...] = Field(default=(), max_length=4)
    require_relation_for_combination: bool = False
    extractive_fallback: bool = False
    wiki_index_first: bool = False
    wiki_index_hits: int = Field(default=8, ge=1, le=32, strict=True)
    synthesis_max_output_tokens: int = Field(default=800, ge=256, le=8192, strict=True)
    answer_guidance: str | None = Field(default=None, max_length=2000)
    # Opt-in: lines starting with this label are bounded, Raw-cited inferences
    # connecting separately cited facts. They never establish a direct
    # relationship or complete a missing facet.
    inference_label: str | None = Field(default=None, min_length=1, max_length=16)
    # "wiki_primary": curated Wiki pages are the cited answer source and each
    # cited page carries its Raw provenance; Raw fills gaps the Wiki lacks.
    citation_policy: Literal["raw_only", "wiki_primary"] = "raw_only"

    @model_validator(mode="after")
    def valid_patterns(self) -> Self:
        if len({facet.name for facet in self.facets}) != len(self.facets):
            raise ValueError("Knowledge facet names must be unique")
        if self.require_relation_for_combination and not self.relation_terms:
            raise ValueError("combined Knowledge evidence needs relation terms")
        if self.subject_pattern is None and any(facet.link_subject for facet in self.facets):
            raise ValueError("subject-linked facets need a subject pattern")
        patterns = [
            *self.intent_patterns,
            *(pattern for facet in self.facets for pattern in facet.request_patterns),
            *(hint.pattern for hint in self.focus_hints),
            *(facet.entity_pattern for facet in self.facets if facet.entity_pattern),
            *(
                pattern
                for facet in self.facets
                for requirement in facet.evidence_requirements
                for pattern in (
                    requirement.question_pattern, *requirement.evidence_patterns,
                )
            ),
        ]
        if self.subject_pattern is not None:
            patterns.append(self.subject_pattern)
        for pattern in patterns:
            if len(pattern) > 512:
                raise ValueError("Knowledge procedure pattern is too long")
            try:
                re.compile(pattern, re.IGNORECASE)
            except re.error:
                raise ValueError("invalid Knowledge procedure pattern") from None
        return self

    def matches_intent(self, question: str) -> bool:
        return any(re.search(pattern, question, re.IGNORECASE) for pattern in self.intent_patterns)

    def requested_facets(self, question: str) -> tuple[KnowledgeFacetInstruction, ...]:
        return tuple(
            facet for facet in self.facets
            if any(re.search(pattern, question, re.IGNORECASE)
                   for pattern in facet.request_patterns)
        )

    def subject(self, question: str) -> str | None:
        if self.subject_pattern is None:
            return None
        matched = re.search(self.subject_pattern, question, re.IGNORECASE)
        return None if matched is None else matched.group(0)

    def focus(self, question: str) -> KnowledgeFocusHint | None:
        return next(
            (hint for hint in self.focus_hints if re.search(hint.pattern, question, re.IGNORECASE)),
            None,
        )
