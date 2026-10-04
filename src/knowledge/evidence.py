"""Observe Raw evidence for the facets requested by a Knowledge Skill.

These are retrieval observations, not proof that a model's claims are true.
Only the Host can accept the final cited answer. A missing observation must
remain a visible gap rather than an invented recommendation.
"""

import re
from pathlib import PurePosixPath
from typing import Literal, Self

from pydantic import Field, model_validator

from common.assets import REDACTED, SECRET_PATTERN
from common.base import Contract, Symbol
from knowledge.procedure import KnowledgeFacetInstruction, KnowledgeFocusHint, KnowledgeProcedure
from knowledge.query import (
    MAX_LABELED_INFERENCES,
    STATED_NUMBER,
    Answer,
    Citation,
    Passage,
    RetrievalSnapshot,
    cited_claim_sentences,
    cited_numbers,
    labeled_inference_grounded,
    split_labeled_inferences,
    tokens,
)
from knowledge.vault import Vault


class FacetObservation(Contract):
    name: Symbol
    passages: tuple[Passage, ...] = Field(max_length=6)
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
    context_passages: tuple[Passage, ...] = Field(default=(), max_length=6)
    wiki_context: tuple[Passage, ...] = Field(default=(), max_length=3)

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
            *self.context_passages,
            *self.wiki_context,
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


def passage_number(passages: tuple[Passage, ...], target: Passage) -> int | None:
    """Retrieval scores may differ for the same Raw section across Skill queries."""
    return next(
        (
            index for index, passage in enumerate(passages, 1)
            if passage.citation == target.citation
            and passage.text == SECRET_PATTERN.sub(REDACTED, target.text)
        ),
        None,
    )


def _safe_passage(passage: Passage) -> Passage:
    """Keep provenance while redacting credential-like Raw text before output."""
    cleaned = SECRET_PATTERN.sub(REDACTED, passage.text)
    return passage if cleaned == passage.text else passage.model_copy(update={"text": cleaned})


class FacetEvidenceSummary(Contract):
    name: Symbol
    citations: tuple[Citation, ...] = Field(max_length=6)
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


def answer_claims_overlap_raw(answer: Answer, *, inference_label: str | None = None) -> bool:
    """Reject obvious citation laundering; this is not semantic entailment.

    Each answer sentence needs meaningful lexical overlap with its cited Raw
    passages, and every stated number must occur there. Stronger strategic
    claims still need the separate direct-relationship check. Lines carrying
    the Skill's inference label are checked as bounded labeled inferences.
    """
    facts, inferences = split_labeled_inferences(answer.text, inference_label)
    if inferences and (
        len(inferences) > MAX_LABELED_INFERENCES
        or not all(
            labeled_inference_grounded(line, answer.passages, inference_label or "")
            for line in inferences
        )
    ):
        return False
    for sentence in cited_claim_sentences(facts):
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
        stated_numbers = set(STATED_NUMBER.findall(claim))
        source_numbers = set(STATED_NUMBER.findall(source_text))
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


_RECOMMENDATION = re.compile(
    r"推薦|建議|優先推|可推|可搭配|可選|目標市場|target market|"
    r"recommend|suggest|propose",
    re.IGNORECASE,
)
_TEST_USE_CASE = re.compile(
    r"test|測試|emulat|simulat|measurement|fading|waveform|callbox|"
    r"scenario|conformance|option|support|designed|適用|支援|模擬|量測",
    re.IGNORECASE,
)
_RECOMMENDED_PRODUCT_ID = re.compile(
    r"(?<![A-Z0-9])(?:[A-Z]{2,}[A-Z0-9]*-)?[A-Z]{1,6}\d{2,}[A-Z0-9]*(?![A-Z0-9])",
    re.IGNORECASE,
)


def _unwrapped_prose(text: str) -> str:
    """Rejoin PDF hard-wrapped lines so a sentence window counts sentences.

    Extracted PDF Raw breaks lines mid-sentence and mid-word ("vec-\\ntor").
    Blank lines still separate paragraphs; the Raw text itself is unchanged.
    """
    joined = re.sub(r"(?<=[a-z])-\n(?=[a-z])", "", text)
    return re.sub(r"[ \t]*\n(?![ \t]*\n)[ \t]*", " ", joined)


def _names_focus(raw_ref: str | None, focus: KnowledgeFocusHint) -> bool:
    """A Raw file named for the focus (e.g. an NTN whitepaper) is focused context."""
    name = PurePosixPath(raw_ref or "").stem
    return any(
        re.search(
            rf"(?<![A-Za-z0-9]){re.escape(term)}(?![A-Za-z0-9])", name, re.IGNORECASE
        )
        for term in focus.evidence_terms
    )


def _source_supports_focused_use_case(
    source: Passage, entity: str, focus: KnowledgeFocusHint,
) -> bool:
    """Allow a product use case to inherit a nearby market-context sentence.

    Source paragraphs often introduce NTN before naming the instrument. A
    short sentence window keeps that context without treating a distant target
    market list as proof of an unrelated product's testing role. A document
    whose own file name is the focus (an NTN whitepaper) supplies that context
    for every section, but the cited section still needs the product in a
    concrete test role.
    """
    document_focus = _names_focus(source.citation.raw_ref, focus)
    sentences = [
        sentence.strip()
        for sentence in re.split(
            r"(?<=[.!?。！？])\s+|\n+", _unwrapped_prose(_evidence_words(source.text))
        )
        if sentence.strip()
    ]
    for index, sentence in enumerate(sentences):
        if entity.casefold() not in sentence.casefold() or not _TEST_USE_CASE.search(sentence):
            continue
        if document_focus:
            return True
        neighbors = " ".join(sentences[max(0, index - 2):index + 3]).casefold()
        if any(term.casefold() in neighbors for term in focus.evidence_terms):
            return True
    return False


def unsupported_product_recommendations(
    answer: Answer, question: str, procedure: KnowledgeProcedure,
) -> tuple[str, ...]:
    """Find recommendations supported only by a broad market/product listing.

    This is a narrow Skill-specific check, not a semantic verifier. A product
    recommendation needs one cited Raw clause naming the product, the market
    focus and a concrete test role together. A reseller list followed by
    `Target Markets: NTN` does not establish that relationship.
    """
    focus = procedure.focus(question)
    if focus is None:
        return ()
    product = next(
        (facet for facet in procedure.requested_facets(question)
         if facet.name == "product_option_spec"),
        None,
    )
    if product is None:
        return ()
    rejected: list[str] = []
    for line in answer.text.splitlines():
        if not _RECOMMENDATION.search(line):
            continue
        entities = tuple(dict.fromkeys(
            match.group(0).upper()
            for match in _RECOMMENDED_PRODUCT_ID.finditer(line)
        ))
        if not entities:
            continue
        sources = tuple(
            answer.passages[number - 1]
            for number in cited_numbers(line)
            if 1 <= number <= len(answer.passages)
            and answer.passages[number - 1].citation.kind == "raw"
        )
        for entity in entities:
            supported = any(
                _source_supports_focused_use_case(source, entity, focus)
                for source in sources
            )
            if not supported:
                rejected.append(line)
                break
    return tuple(rejected)


def omit_unsupported_product_recommendations(
    answer: Answer, question: str, procedure: KnowledgeProcedure,
) -> Answer:
    """Preserve independently cited claims after dropping weak recommendations."""
    rejected = unsupported_product_recommendations(answer, question, procedure)
    if not rejected:
        return answer
    remaining = "\n".join(
        line for line in answer.text.splitlines() if line not in rejected
    ).strip()
    return answer.model_copy(update={
        "status": "answered" if remaining else "uncited",
        "text": remaining,
    })


def answer_concerns_subject(answer: Answer, subject: str) -> bool:
    """The answer names the subject or cites a Raw document named for it.

    Option statements in a product's own feature or specification document
    ("R&S CMP-KM351 ...") often omit the base model name; the cited Raw
    file still ties the claim to that product.
    """
    folded = subject.casefold()
    if folded in answer.text.casefold():
        return True
    return any(
        folded in PurePosixPath(answer.passages[number - 1].citation.raw_ref or "")
        .stem.casefold()
        for number in cited_numbers(answer.text)
        if 1 <= number <= len(answer.passages)
        and answer.passages[number - 1].citation.kind == "raw"
    )


def omit_unverified_answer_lines(
    answer: Answer, *, inference_label: str | None = None,
) -> Answer:
    """Retain independently supported lines of a partly faulty model answer.

    Labeled inferences survive only beside at least one supported fact and
    up to MAX_LABELED_INFERENCES.
    """
    if answer.status != "answered":
        return answer
    kept = [
        line for line in answer.text.splitlines()
        if line.strip() and answer_claims_overlap_raw(
            answer.model_copy(update={"text": line}), inference_label=inference_label
        )
    ]
    facts, inferences = split_labeled_inferences("\n".join(kept), inference_label)
    remaining = (
        "\n".join([facts, *inferences[:MAX_LABELED_INFERENCES]]).strip()
        if facts.strip() else ""
    )
    return answer.model_copy(update={
        "status": "answered" if remaining else "uncited",
        "text": remaining,
    })


def _evidence_words(text: str) -> str:
    """Search visible source prose, not market words embedded in navigation URLs."""
    cleaned = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", text)
    cleaned = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", cleaned)
    cleaned = re.sub(r"https?://\S+", " ", cleaned)
    return re.sub(r"<[^>]+>", " ", cleaned)


def evidence_excerpt(
    text: str, *, subject: str | None, terms: tuple[str, ...],
    priority_patterns: tuple[str, ...] = (),
) -> str:
    """Choose a readable, topic-bearing sentence from a cited Raw section."""
    prose = _evidence_words(text)
    sentences = [
        sentence.strip(" -•\t")
        for sentence in re.split(r"(?<=[.!?。！？])\s+|\n", prose)
    ]
    meaningful = [
        sentence for sentence in sentences
        if len(sentence) >= 25 and sum(char.isalpha() for char in sentence) >= 15
    ]
    if not meaningful:
        return re.sub(r"\s+", " ", prose).strip()[:320]

    def rank(sentence: str) -> tuple[int, int]:
        lowered = sentence.casefold()
        score = 3 if subject and subject.casefold() in lowered else 0
        score += 6 * sum(
            bool(re.search(pattern, sentence, re.IGNORECASE))
            for pattern in priority_patterns
        )
        score += sum(term.casefold() in lowered for term in terms)
        return score, -len(sentence)

    chosen = max(meaningful, key=rank)
    return re.sub(r"\s+", " ", chosen).strip()[:450]


def extractive_relation_answer(
    question: str, assessment: KnowledgeEvidenceAssessment,
    procedure: KnowledgeProcedure,
) -> Answer | None:
    """Keep cited direct Raw statements when model synthesis cannot be validated."""
    if assessment.status != "covered" or not assessment.relation_passages:
        return None
    facets = procedure.requested_facets(question)
    subject = procedure.subject(question)
    focus = procedure.focus(question)
    selected = assessment.selected_passages()
    extracts: list[str] = []
    for passage in sorted(
        assessment.relation_passages,
        key=lambda item: "/PR/" in (item.citation.raw_ref or ""),
    ):
        number = passage_number(selected, passage)
        if number is None:
            continue
        sentences = re.split(r"(?<=[.!?。！？])\s+|\n", _evidence_words(passage.text))
        linked = next(
            (
                sentence.strip(" -•\t") for sentence in sentences
                if 45 <= len(sentence.strip()) <= 500
                and not sentence.lstrip().startswith(("|", "#"))
                and not re.search(r"\b(?:them|those|these)\b", sentence, re.IGNORECASE)
                and not (
                    "/PR/" in (passage.citation.raw_ref or "")
                    and re.search(
                        r"unique|comprehensive|empower|all .* technologies",
                        sentence, re.IGNORECASE,
                    )
                )
                if _relation_pairs(
                    passage.model_copy(update={"text": sentence}), facets, subject,
                    focus, procedure.relation_terms,
                )
            ),
            None,
        )
        if linked:
            extracts.append(f"{linked} [{number}]")
        if extracts:
            break
    if not extracts:
        return None
    answer = Answer(
        question=question, status="answered", passages=selected,
        text="\n\n".join(extracts),
    )
    return answer if answer_claims_overlap_raw(answer) else None


def extractive_observation_answer(
    question: str, assessment: KnowledgeEvidenceAssessment,
    procedure: KnowledgeProcedure,
) -> Answer | None:
    """Return cited source facts when model synthesis cannot be grounded.

    This is an evidence summary, not a generated product recommendation.
    The Host still decides whether required facets and links were cited.
    """
    selected = assessment.selected_passages()
    facets = {item.name: item for item in procedure.requested_facets(question)}
    subject = procedure.subject(question)
    lines: list[str] = []
    seen_citations: set[str] = set()
    for observation in assessment.observations:
        facet = facets.get(observation.name)
        if facet is None:
            continue
        limit = 3 if facet.collect_all_queries else 1
        added = 0
        for passage in observation.passages:
            citation = passage.citation.model_dump_json()
            if citation in seen_citations:
                continue
            number = passage_number(selected, passage)
            if number is None:
                continue
            excerpt = evidence_excerpt(
                passage.text, subject=subject,
                terms=facet.support_terms + facet.link_terms,
                priority_patterns=(facet.entity_pattern,) if facet.entity_pattern else (),
            )
            if len(excerpt) < 25:
                continue
            lines.append(f"{excerpt} [{number}]")
            seen_citations.add(citation)
            added += 1
            if added >= limit:
                break
    if assessment.relation_required:
        for passage in assessment.relation_passages:
            citation = passage.citation.model_dump_json()
            if citation in seen_citations:
                continue
            number = passage_number(selected, passage)
            if number is None:
                continue
            excerpt = evidence_excerpt(
                passage.text, subject=subject,
                terms=procedure.relation_terms,
            )
            if len(excerpt) >= 25:
                lines.append(f"{excerpt} [{number}]")
                break
    if not lines:
        return None
    answer = Answer(
        question=question, status="answered", passages=selected,
        text="\n".join(lines),
    )
    checked = omit_unverified_answer_lines(answer)
    return checked if checked.status == "answered" else None


def _supports_facet(
    passage: Passage, facet: KnowledgeFacetInstruction, subject: str | None,
    focus: KnowledgeFocusHint | None, question: str,
) -> bool:
    if passage.citation.kind != "raw":
        return False
    if facet.source_areas and not any(
        (passage.citation.raw_ref or "").startswith(area)
        for area in facet.source_areas
    ):
        return False
    content = _evidence_words(passage.text).casefold()
    source_identity = f"{content} {passage.citation.raw_ref or ''}".casefold()
    if facet.include_subject and subject and subject.casefold() not in source_identity:
        return False
    focus_found = bool(
        focus and any(term.casefold() in source_identity for term in focus.evidence_terms)
    )
    if facet.require_focus and focus and not focus_found:
        return False
    if facet.require_focus_when_unbound and subject is None and focus and not focus_found:
        return False
    if facet.entity_pattern and not re.search(facet.entity_pattern, source_identity, re.IGNORECASE):
        return False
    if facet.comparison_terms and subject is not None and not any(
        subject.casefold() in sentence.casefold()
        and any(term.casefold() in sentence.casefold() for term in facet.comparison_terms)
        and any(term.casefold() in sentence.casefold() for term in facet.support_terms)
        for sentence in re.split(r"(?<=[.!?。！？])\s+|\n", content)
    ):
        return False
    for requirement in facet.evidence_requirements:
        if re.search(requirement.question_pattern, question, re.IGNORECASE) and not any(
            re.search(pattern, content, re.IGNORECASE)
            for pattern in requirement.evidence_patterns
        ):
            return False
    return (facet.focus_is_support and focus_found) or any(
        term.casefold() in content for term in facet.support_terms
    )


def _relation_pairs(
    passage: Passage,
    facets: tuple[KnowledgeFacetInstruction, ...],
    subject: str | None,
    focus: KnowledgeFocusHint | None,
    terms: tuple[str, ...],
) -> tuple[tuple[str, str], ...]:
    if passage.citation.kind != "raw":
        return ()
    pairs: set[tuple[str, str]] = set()
    for sentence in re.split(r"(?<=[.!?。！？])\s+|\n", _evidence_words(passage.text)):
        lowered = sentence.casefold()
        if not any(term.casefold() in lowered for term in terms):
            continue
        present = [
            facet.name for facet in facets
            if (not facet.include_subject or subject is None or subject.casefold() in lowered)
            and (
                (
                    facet.link_subject and subject is not None
                    and subject.casefold() in lowered
                ) or (
                    facet.focus_is_link and focus is not None
                    and any(term.casefold() in lowered for term in focus.evidence_terms)
                ) or (
                    any(
                        term.casefold() in lowered
                        for term in (facet.link_terms or facet.support_terms)
                    )
                    and (facet.entity_pattern is None or re.search(
                        facet.entity_pattern, sentence, re.IGNORECASE
                    ))
                )
            )
        ]
        for left_index, left in enumerate(present):
            for right in present[left_index + 1:]:
                pairs.add((left, right))
    return tuple(sorted(pairs))


def _diverse_passages(
    passages: tuple[Passage, ...], *, limit: int,
    entity_pattern: str | None = None,
) -> tuple[Passage, ...]:
    """Keep distinct sources and, for product discovery, instrument families."""
    unique: list[Passage] = []
    seen_citations: set[str] = set()
    for passage in passages:
        citation = passage.citation.model_dump_json()
        if citation not in seen_citations:
            unique.append(passage)
            seen_citations.add(citation)
    if entity_pattern is not None:
        def source_tier(passage: Passage) -> int:
            ref = passage.citation.raw_ref or ""
            if "/PR/" in ref:
                return 2
            return 0 if ref.startswith(("raw/Knowledge/", "raw/Productions/")) else 1

        unique.sort(key=source_tier)
    selected: list[Passage] = []
    seen_sources: set[str] = set()
    seen_families: set[str] = set()
    if entity_pattern is not None:
        for passage in unique:
            families = tuple(dict.fromkeys(
                family.group(0).upper()
                for matched in re.finditer(entity_pattern, passage.text, re.IGNORECASE)
                if (family := re.match(r"[A-Za-z]+", matched.group(0))) is not None
            ))
            novel = next((family for family in families if family not in seen_families), None)
            if novel is not None:
                selected.append(passage)
                seen_families.add(novel)
                seen_sources.add(passage.citation.raw_ref or "")
                if len(selected) == limit:
                    return tuple(selected)
    for passage in unique:
        source = passage.citation.raw_ref or ""
        if source not in seen_sources:
            selected.append(passage)
            seen_sources.add(source)
            if len(selected) == limit:
                return tuple(selected)
    for passage in unique:
        if passage not in selected:
            selected.append(passage)
            if len(selected) == limit:
                break
    return tuple(selected)


def _interleave_passages(
    groups: tuple[tuple[Passage, ...], ...], *, limit: int,
    entity_pattern: str | None = None,
) -> tuple[Passage, ...]:
    """Give each Skill discovery query a chance to surface a distinct source."""
    interleaved = tuple(
        passage
        for rank in range(max((len(group) for group in groups), default=0))
        for group in groups
        if rank < len(group)
        for passage in (group[rank],)
    )
    return _diverse_passages(interleaved, limit=limit, entity_pattern=entity_pattern)


def _direct_product_use_case(
    sentence: str, focus: KnowledgeFocusHint,
    entity_pattern: str,
) -> bool:
    visible = _evidence_words(sentence)
    return (
        bool(re.search(entity_pattern, visible, re.IGNORECASE))
        and any(term.casefold() in visible.casefold() for term in focus.evidence_terms)
        and bool(_TEST_USE_CASE.search(visible))
    )


def assess_knowledge_evidence(
    vault: Vault, question: str, procedure: KnowledgeProcedure,
    *, snapshot: RetrievalSnapshot | None = None,
) -> KnowledgeEvidenceAssessment:
    """Run each Skill query once, then use its fallback only for missing facets."""
    facets = procedure.requested_facets(question)
    if not facets:
        return KnowledgeEvidenceAssessment(status="covered")
    subject = procedure.subject(question)
    focus = procedure.focus(question)
    snapshot = snapshot or RetrievalSnapshot(vault)
    def facet_queries(facet: KnowledgeFacetInstruction) -> tuple[str, ...]:
        searches = (
            facet.discovery_queries
            if subject is None and facet.discovery_queries else facet.search_queries
        )
        prefix = " ".join(
            part for part in (
                subject if facet.search_subject or facet.include_subject else None,
                focus.query if focus else None,
            ) if part
        )
        return tuple(f"{prefix} {search}".strip() for search in searches)

    planned = tuple(facet_queries(facet) for facet in facets)
    queries = [
        searches[0] for searches in planned
    ]
    relation_required = procedure.require_relation_for_combination and len(facets) > 1
    def search(
        queries: tuple[str, ...], *, k: int, min_raw: int,
    ) -> tuple[tuple[Passage, ...], ...]:
        if procedure.wiki_index_first:
            return snapshot.wiki_guided_batch(
                queries, k=k, min_raw=min_raw,
                index_k=procedure.wiki_index_hits,
            )
        return snapshot.batch(queries, k=k, min_raw=min_raw)
    batches = search(tuple(queries), k=12, min_raw=12)
    def eligible(
        batch: tuple[Passage, ...], facet: KnowledgeFacetInstruction,
    ) -> tuple[Passage, ...]:
        return tuple(
            passage for passage in batch
            if _supports_facet(passage, facet, subject, focus, question)
        )

    def ranked_eligible(
        batch: tuple[Passage, ...], facet: KnowledgeFacetInstruction,
        query: str,
    ) -> tuple[Passage, ...]:
        found = eligible(batch, facet)
        if facet.collect_all_queries:
            def accepts(passage: Passage) -> bool:
                return _supports_facet(
                    passage, facet, subject, focus, question
                )

            guided = snapshot.matching_wiki_sources(
                query, accepts=accepts, k=facet.max_passages,
                index_k=procedure.wiki_index_hits,
            ) if procedure.wiki_index_first else ()
            full = snapshot.matching_raw(
                query, accepts=accepts, k=24,
            )
            found = (*guided, *full, *found)
        return _diverse_passages(
            found, limit=facet.max_passages,
            entity_pattern=facet.entity_pattern if facet.collect_all_queries else None,
        )

    groups = [
        [ranked_eligible(batches[index], facet, planned[index][0])]
        for index, facet in enumerate(facets)
    ]
    accepted = [group[0] for group in groups]
    attempts = [1] * len(facets)
    for attempt in range(1, max(len(searches) for searches in planned)):
        missing_indices = [
            index for index, _facet in enumerate(facets)
            if (facets[index].collect_all_queries or not accepted[index])
            and attempt < len(planned[index])
        ]
        if not missing_indices:
            break
        retry_queries = tuple(
            planned[index][attempt]
            for index in missing_indices
        )
        retry_batches = search(retry_queries, k=12, min_raw=12)
        for index, batch in zip(missing_indices, retry_batches, strict=True):
            attempts[index] += 1
            found = ranked_eligible(batch, facets[index], planned[index][attempt])
            groups[index].append(found)
            accepted[index] = _interleave_passages(
                tuple(groups[index]), limit=facets[index].max_passages,
                entity_pattern=(
                    facets[index].entity_pattern
                    if facets[index].collect_all_queries else None
                ),
            )
    for index, facet in enumerate(facets):
        if not accepted[index]:
            def accepts(
                passage: Passage, item: KnowledgeFacetInstruction = facet,
            ) -> bool:
                return _supports_facet(passage, item, subject, focus, question)

            accepted[index] = snapshot.matching_raw(
                planned[index][-1],
                accepts=accepts,
                k=facet.max_passages,
            )
        if facet.collect_all_queries and focus and facet.entity_pattern:
            followed: set[str] = set()
            refined: list[Passage] = []
            entity_pattern = facet.entity_pattern

            def direct(sentence: str, pattern: str = entity_pattern) -> bool:
                return _direct_product_use_case(sentence, focus, pattern)

            for passage in accepted[index]:
                raw_ref = passage.citation.raw_ref
                if raw_ref and raw_ref not in followed:
                    followed.add(raw_ref)
                    if not any(
                        direct(sentence)
                        for sentence in re.split(
                            r"(?<=[.!?。！？])\s+|\n+", passage.text
                        )
                    ):
                        better = snapshot.source_section(
                            raw_ref, matches_sentence=direct
                        )
                        if better is not None and _supports_facet(
                            better, facet, subject, focus, question
                        ):
                            passage = better
                refined.append(passage)
            accepted[index] = tuple(refined)
    observations = tuple(
        FacetObservation(
            name=facet.name,
            passages=tuple(_safe_passage(item) for item in accepted[index]),
            attempts=attempts[index],
        )
        for index, facet in enumerate(facets)
    )
    if relation_required:
        relation_queries = [
            *(
                " ".join(part for part in (
                    subject, focus.query if focus else None, search,
                ) if part)
                for search in procedure.relation_search_queries
            ),
            *(
                " ".join(part for part in (
                    subject, focus.query if focus else None,
                    facets[left].search_queries[0], facets[right].search_queries[0],
                ) if part)
                for left in range(len(facets)) for right in range(left + 1, len(facets))
            ),
        ][:7]
        relation_batches = search(tuple(relation_queries), k=12, min_raw=12)
        relation_candidates = tuple(
            passage for batch in relation_batches for passage in batch
        )
    else:
        relation_candidates = ()
    relation_pairs = tuple(
        (passage, _relation_pairs(passage, facets, subject, focus, procedure.relation_terms))
        for passage in relation_candidates
    )
    relation_passages_list: list[Passage] = []
    seen_relations: set[tuple[str | None, int | None, str]] = set()
    for passage, pairs in relation_pairs:
        key = (passage.citation.raw_ref, passage.citation.section, passage.text)
        if pairs and key not in seen_relations and len(relation_passages_list) < 3:
            relation_passages_list.append(passage)
            seen_relations.add(key)
    relation_passages = tuple(_safe_passage(item) for item in relation_passages_list)
    relations = tuple(
        FacetRelation(left=left, right=right, citation=passage.citation)
        for passage, pairs in relation_pairs
        if passage in relation_passages_list
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
    context_passages: list[Passage] = []
    if procedure.wiki_index_first:
        for observation in observations:
            for passage in observation.passages[:2]:
                raw_ref = passage.citation.raw_ref
                section = passage.citation.section
                if raw_ref is None or section is None or len(passage.text) >= 240:
                    continue
                for neighbor in snapshot.source_neighbors(raw_ref, section):
                    if neighbor.citation == passage.citation or neighbor in context_passages:
                        continue
                    context_passages.append(_safe_passage(neighbor))
                    if len(context_passages) >= 6:
                        break
                if len(context_passages) >= 6:
                    break
            if len(context_passages) >= 6:
                break
    return KnowledgeEvidenceAssessment(
        status=status,
        observations=observations,
        missing_facets=missing,
        relation_required=relation_required,
        relation_passages=relation_passages,
        relations=relations,
        context_passages=tuple(context_passages),
        wiki_context=tuple(
            _safe_passage(item) for item in snapshot.wiki_index_context(
                question, index_k=procedure.wiki_index_hits
            )
        ) if procedure.wiki_index_first else (),
    )
