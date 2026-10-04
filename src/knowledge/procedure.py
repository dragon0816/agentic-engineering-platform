"""Typed Knowledge query procedure supplied by an installed Skill.

The shared Agent harness treats Skill procedure JSON as opaque. Only the
Knowledge adapter interprets these search and evidence hints; they are never
execution grants or substitutes for Host validation.
"""

import re
from typing import Literal, Self

from pydantic import Field, model_validator

from common.base import Contract, Symbol, Text


class KnowledgeFacetInstruction(Contract):
    name: Symbol
    request_patterns: tuple[Text, ...] = Field(min_length=1, max_length=12)
    search_queries: tuple[Text, ...] = Field(min_length=1, max_length=3)
    support_terms: tuple[Text, ...] = Field(min_length=1, max_length=12)
    include_subject: bool = False
    link_terms: tuple[Text, ...] = Field(default=(), max_length=12)
    link_subject: bool = False


class KnowledgeProcedure(Contract):
    kind: Literal["knowledge_query_v1"] = "knowledge_query_v1"
    intent_patterns: tuple[Text, ...] = Field(min_length=1, max_length=20)
    subject_pattern: Text | None = None
    facets: tuple[KnowledgeFacetInstruction, ...] = Field(min_length=1, max_length=12)
    relation_terms: tuple[Text, ...] = Field(default=(), max_length=20)
    require_relation_for_combination: bool = False

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
