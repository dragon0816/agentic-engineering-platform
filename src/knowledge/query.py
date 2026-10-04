"""Query with provenance: retrieval over Raw sections and Wiki pages whose every
citation names where the words came from.

Retrieval is deterministic and lexical (BM25 over passages, with characters
and character bigrams for CJK text so Chinese and Japanese are searchable
without a segmenter). A Raw section cites its `KnowledgeSource` with the page
or slide it came from (an adopted legacy file's sections are its paragraphs);
a Wiki paragraph cites its page and, when the page carries `source_id`, the
source behind it. Only the current version of each original is in the
corpus. Synthesis through `ModelClient` is optional and may
cite only what retrieval returned: an answer that cites something it was not
given is refused, and one that honestly cites nothing is reported as such.
"""

import hashlib
import math
import re
from collections import Counter
from pathlib import PurePosixPath
from typing import Literal

from pydantic import Field, ValidationError

from common.base import Contract, Symbol, Text
from common.execution import Failure, TraceIdentifiers
from knowledge.contracts import KnowledgeSource
from knowledge.lint import body_of, head_fields, read_pages
from knowledge.modelcalls import failure_from_exception
from knowledge.raw import RawIndex, load_document, one_line_ending
from knowledge.vault import Vault, VaultError
from models.contracts import ModelClient, ModelMessage, ModelRequest, ModelRequirements

_TOKEN = re.compile(r"\w+", re.UNICODE)
_CJK = re.compile(r"[぀-ヿ㐀-䶿一-鿿豈-﫿]+")
_BRACKET = re.compile(r"\[([0-9][0-9,\s-]*)\]")
_OPTION_TOKEN = re.compile(
    r"(?<![A-Z0-9])(?:[A-Z0-9]+-)?([BK]\d{1,4}[A-Z]{0,2})(?![A-Z0-9])", re.IGNORECASE
)
_ACRONYM = re.compile(r"(?<![A-Za-z0-9])[A-Z]{2,8}(?![A-Za-z0-9])")
_PRODUCT_ID = re.compile(
    r"(?<![A-Z0-9])(?:[A-Z]{2,}[A-Z0-9]*-)?[A-Z]{1,6}\d{2,}[A-Z0-9]*(?![A-Z0-9])",
    re.IGNORECASE,
)
_MARKET_RATE = re.compile(r"(?<!\w)\d+(?:\.\d+)?\s*[GT](?!\w)", re.IGNORECASE)
_MARKET_LINK = re.compile(
    r"\b(?:supports?|meets?|validates?|qualifies?|tests?)\b|支援|符合|適用|可測|可驗證"
    r"|對接|接軌|可對應",
    re.IGNORECASE,
)
_MARKET_UNCERTAIN = re.compile(
    r"\b(?:not|cannot|unverified|unsupported)\b|未證實|無法確認|不能證明|不代表"
    r"|尚未驗證|不等於|缺乏證據|推論",
    re.IGNORECASE,
)
DEFAULT_PROMPT = """Answer the question from the passages below and nothing else. Cite every
claim with the passage number in square brackets, like [2]. If the passages do
not answer the question, say so in one sentence and cite nothing.

Question: {question}

{passages}"""
_MARKET_FIT_GUIDANCE = """

Separate directly stated product or option capabilities from market requirements.
A market source naming a standard and a different product source naming a
high-speed interface do not prove that product supports, tests or is qualified
for the market standard. If no Raw passage directly establishes the connection,
say that market fit is unverified. Cite the capability and market facts
separately; do not present a possible application as a verified product claim."""


def tokens(text: str) -> tuple[str, ...]:
    """Lowercased word tokens. A word that mixes scripts is split so its Latin
    part is searchable; a run of CJK characters yields each character, each
    overlapping bigram and the run itself, so a query of any length can match."""
    out: list[str] = []
    for word in _TOKEN.findall(text.lower()):
        position = 0
        for run in _CJK.finditer(word):
            if run.start() > position:
                out.append(word[position : run.start()])
            cjk = run.group(0)
            out.extend(cjk)
            out.extend(cjk[i : i + 2] for i in range(len(cjk) - 1))
            if len(cjk) > 2:
                out.append(cjk)
            position = run.end()
        if position < len(word):
            out.append(word[position:])
    return tuple(token for token in out if token)


def cited_numbers(text: str) -> set[int]:
    """Every passage number a text cites: `[2]`, `[1, 3]` and `[1-3]` alike."""
    cited: set[int] = set()
    for group in _BRACKET.findall(text):
        for part in group.split(","):
            part = part.strip()
            if not part:
                continue
            if "-" in part:
                low, _, high = part.partition("-")
                if low.strip().isdigit() and high.strip().isdigit():
                    cited.update(range(int(low), int(high) + 1))
            elif part.isdigit():
                cited.add(int(part))
    return cited


class Citation(Contract):
    """Where a passage came from. A Raw passage names the source, its file and
    section, with the page or slide when the extractor knew it; a Wiki passage
    names the page and, when the page carries provenance, the source behind it."""

    kind: Literal["raw", "wiki"]
    source: KnowledgeSource | None = None
    raw_ref: Text | None = None
    section: int | None = Field(default=None, ge=1, strict=True)
    page: int | None = Field(default=None, ge=1, strict=True)
    slide: int | None = Field(default=None, ge=1, strict=True)
    wiki_page: Text | None = None


class Passage(Contract):
    text: Text
    citation: Citation
    score: float = Field(ge=0)


AnswerStatus = Literal["retrieved", "answered", "unanswered", "no_match", "model_failed", "uncited"]


class Answer(Contract):
    """What a question got. `retrieved` is passages only; `answered` adds a
    synthesized text whose every citation names one of them; `unanswered` is
    the model saying the passages do not answer, with its sentence kept;
    `uncited` means the text was refused for citing something it was not given."""

    question: str
    status: AnswerStatus
    passages: tuple[Passage, ...] = ()
    text: str = ""
    synthesized_by: Symbol | None = None
    failure: Failure | None = None


def _has_raw_grounding(text: str, passages: tuple[Passage, ...]) -> bool:
    """Preflight the record's citation rules before a bounded synthesis retry.

    The final KnowledgeAnswerRecord remains authoritative. This check only
    decides whether a response needs another model attempt; it never adds a
    citation or changes the kind of evidence behind one.
    """
    numbers = cited_numbers(text)
    if not numbers or any(
        number < 1 or number > len(passages) or passages[number - 1].citation.kind != "raw"
        for number in numbers
    ):
        return False
    with_attached_citations = re.sub(
        r"([.!?。！？])\s*(\[[0-9][0-9,\s-]*\])", r" \2\1", text
    )
    sentences = (
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+|(?<=[。！？])\s*", with_attached_citations)
    )
    for sentence in sentences:
        if not sentence:
            continue
        sentence_citations = cited_numbers(sentence)
        if not sentence_citations:
            return False
        # Exact option codes and uppercase technical abbreviations in one
        # claim must coexist in at least one cited excerpt. This is a narrow
        # lexical guard, not a general proof of semantic entailment.
        option_codes = {code.upper() for code in _OPTION_TOKEN.findall(sentence)}
        acronyms = set(_ACRONYM.findall(_OPTION_TOKEN.sub("", sentence))) - {"RAW"}
        for code in option_codes:
            if not any(
                code in {item.upper() for item in _OPTION_TOKEN.findall(passages[n - 1].text)}
                and acronyms <= {token.upper() for token in tokens(passages[n - 1].text)}
                for n in sentence_citations
            ):
                return False
    return True


def _has_market_fit_grounding(text: str, passages: tuple[Passage, ...]) -> bool:
    """Reject a narrow unsupported rate-to-product link in a broad market answer.

    Product codes and market rates can be present in separate cited sources;
    their co-occurrence in the answer is not evidence of verified fit. This is
    intentionally narrower than semantic entailment and is only used for the
    broad high-speed market question family.
    """
    products = {item.casefold() for item in _PRODUCT_ID.findall(text)}
    rates = {item.replace(" ", "").casefold() for item in _MARKET_RATE.findall(text)}
    if not products or not rates:
        return True
    attached = re.sub(r"([.!?。！？])\s*(\[[0-9][0-9,\s-]*\])", r" \2\1", text)
    for sentence in re.split(r"(?<=[.!?])\s+|(?<=[。！？])\s*", attached):
        if not _MARKET_LINK.search(sentence) or _MARKET_UNCERTAIN.search(sentence):
            continue
        if not ("市場" in sentence or "market" in sentence.casefold()
                or _MARKET_RATE.search(sentence)):
            continue
        if not any(
            number >= 1
            and number <= len(passages)
            and passages[number - 1].citation.kind == "raw"
            and products & {
                code.casefold() for code in _PRODUCT_ID.findall(passages[number - 1].text)
            }
            and rates & {
                rate.replace(" ", "").casefold()
                for rate in _MARKET_RATE.findall(passages[number - 1].text)
            }
            for number in cited_numbers(sentence)
        ):
            return False
    return True


def _focused_raw_passages(
    passages: tuple[Passage, ...], question: str
) -> tuple[Passage, ...]:
    """Narrow long retrieved Raw sections before synthesis, without changing Raw.

    Legacy specifications can hold many table rows in one paragraph. A model
    seeing the whole section may incorrectly join distant rows under one
    citation. The returned excerpt is an exact consecutive part of the same
    section; the citation still points to that original section.
    """
    terms = set(tokens(question))
    for facet_terms, _ in _coverage_terms(question):
        terms.update(facet_terms)
    focused: list[Passage] = []
    for passage in passages:
        lines = passage.text.splitlines()
        if passage.citation.kind != "raw" or len(passage.text) <= 800 or len(lines) < 8:
            focused.append(passage)
            continue
        chunks = ["\n".join(lines[index : index + 5]) for index in range(0, len(lines), 5)]
        best = max(
            enumerate(chunks),
            key=lambda item: (len(set(tokens(item[1])) & terms), -item[0]),
        )[1]
        focused.append(Passage(text=best, citation=passage.citation, score=passage.score))
    return tuple(focused)


class _Doc:
    def __init__(self, text: str, citation: Citation) -> None:
        self.text = text
        self.citation = citation
        self.counts = Counter(tokens(text))
        self.length = sum(self.counts.values())
        reference = citation.raw_ref or citation.wiki_page or ""
        self.search_counts = self.counts + Counter(
            tokens(PurePosixPath(reference).stem.replace("_", " ").replace("-", " "))
        )
        self.search_length = sum(self.search_counts.values())


def _coverage_terms(question: str) -> tuple[tuple[set[str], tuple[str, ...]], ...]:
    """Small, product-neutral bilingual facets for broad evidence questions.

    These are retrieval aliases, never answer facts. Their exact matching
    prevents an unrelated single-language or narrow question from changing
    the established BM25 order.
    """
    lower = question.casefold()

    def asks(*phrases: str) -> bool:
        return any(phrase in lower for phrase in phrases)

    if not (asks("高速", "high speed", "high-speed") and asks("市場", "market")):
        return ()
    if not asks("產品", "product", "instrument", "analyzer", "tester"):
        return ()
    speed = "高速 high speed high-speed digital"
    communications = "通訊 通信 communication communications connectivity links"
    market = "市場 market applications industry"
    product = "產品 product products instrument analyzer tester specs specifications"
    option = "選配 選件 option options optional configuration feature"
    facets: list[tuple[set[str], tuple[str, ...]]] = [
        (set(tokens(f"{speed} {communications} {market}")), ("market", "市場")),
    ]
    if asks("option", "選配", "選件"):
        facets.append(
            (
                set(tokens(f"{speed} {communications} {product} {option}")),
                ("option", "選配", "選件"),
            )
        )
    else:
        facets.append((set(tokens(f"{speed} {communications} {product}")), ("product", "產品")))
    return tuple(facets)


def _facet_candidate(doc: _Doc, label: tuple[str, ...]) -> bool:
    if doc.citation.kind != "raw":
        return False
    searchable = f"{doc.text} {doc.citation.raw_ref or ''}".casefold()
    if not any(word in searchable for word in label):
        return False
    return any(word in searchable for word in ("高速", "high speed", "high-speed"))


def _corpus(vault: Vault) -> list[_Doc]:
    docs: list[_Doc] = []
    index = RawIndex.scan(vault)
    by_id = {entry.source.source_id: entry.source for entry in index.entries}
    # A superseded Raw handed its evidence to its successor; only the current
    # version of each original is worth citing.
    superseded = {entry.supersedes for entry in index.entries if entry.supersedes is not None}
    for entry in index.entries:
        if entry.source.source_id in superseded:
            continue
        try:
            document = load_document(vault, entry)
        except (ValueError, ValidationError, UnicodeDecodeError, VaultError):
            continue
        for number, section in enumerate(document.sections, 1):
            if not section.text.strip():
                continue
            docs.append(
                _Doc(
                    section.text,
                    Citation(
                        kind="raw",
                        source=document.source,
                        raw_ref=entry.raw_ref,
                        section=number,
                        page=section.page,
                        slide=section.slide,
                    ),
                )
            )
    texts, _ = read_pages(vault, vault.wiki_files())
    for rel, text in texts.items():
        head = head_fields(text)
        source = by_id.get((head or {}).get("source_id", ""))
        for paragraph in re.split(r"\n\s*\n", one_line_ending(body_of(text))):
            if paragraph.strip():
                docs.append(
                    _Doc(
                        paragraph.strip(),
                        Citation(kind="wiki", wiki_page=rel, source=source),
                    )
                )
    return docs


def retrieve(
    vault: Vault,
    question: str,
    *,
    k: int = 5,
    min_raw: int = 0,
    evidence_coverage: bool = False,
) -> tuple[Passage, ...]:
    """BM25 over every current Raw section and Wiki paragraph; ties break by
    corpus order, so the same question always returns the same passages."""
    return _retrieve_docs(
        _corpus(vault), question, k=k, min_raw=min_raw,
        evidence_coverage=evidence_coverage,
    )


def retrieve_batch(
    vault: Vault, queries: tuple[str, ...], *, k: int, min_raw: int = 0
) -> tuple[tuple[Passage, ...], ...]:
    """Search several Skill queries against one immutable corpus snapshot."""
    return RetrievalSnapshot(vault).batch(queries, k=k, min_raw=min_raw)


class RetrievalSnapshot:
    """One Raw/Wiki corpus load across bounded facet searches."""

    def __init__(self, vault: Vault) -> None:
        self._docs = _corpus(vault)

    def batch(
        self, queries: tuple[str, ...], *, k: int, min_raw: int = 0
    ) -> tuple[tuple[Passage, ...], ...]:
        return tuple(
            _retrieve_docs(self._docs, query, k=k, min_raw=min_raw)
            for query in queries
        )


def _retrieve_docs(
    docs: list[_Doc], question: str, *, k: int, min_raw: int,
    evidence_coverage: bool = False,
) -> tuple[Passage, ...]:
    if k < 1:
        raise ValueError("k is positive")
    if not 0 <= min_raw <= k:
        raise ValueError("min_raw must be between zero and k")
    # Filenames in a question are often copied verbatim from the vault. Treat
    # their separators as word breaks, just as the indexed source stem does.
    normalized_question = question.replace("_", " ").replace("-", " ")
    # A Chinese test question should also find English source passages. This
    # expands retrieval terms only; it never supplies answer facts.
    if "測試" in question or "测试" in question:
        normalized_question += " test testing measurement"
    query = tokens(normalized_question)
    if not query:
        return ()
    if not docs:
        return ()
    facets = _coverage_terms(question) if evidence_coverage else ()
    covered = bool(facets)
    average = sum(doc.length for doc in docs) / len(docs)
    frequency: Counter[str] = Counter()
    for doc in docs:
        frequency.update(set(doc.counts))
    search_average = sum(doc.search_length for doc in docs) / len(docs) if covered else average
    search_frequency: Counter[str] = Counter()
    if covered:
        for doc in docs:
            search_frequency.update(set(doc.search_counts))
    k1, b = 1.5, 0.75

    def score(doc: _Doc, terms: set[str], *, search_fields: bool = False) -> float:
        counts = doc.search_counts if search_fields else doc.counts
        length = doc.search_length if search_fields else doc.length
        frequencies = search_frequency if search_fields else frequency
        mean_length = search_average if search_fields else average
        return sum(
            math.log(1 + (len(docs) - frequencies[term] + 0.5) / (frequencies[term] + 0.5))
            * counts[term]
            * (k1 + 1)
            / (counts[term] + k1 * (1 - b + b * length / mean_length))
            for term in terms
            if counts[term]
        )

    scored: list[tuple[float, int, _Doc]] = []
    for position, doc in enumerate(docs):
        relevance = score(doc, set(query))
        if relevance > 0:
            scored.append((relevance, position, doc))
    scored.sort(key=lambda item: (-item[0], item[1]))
    selected: list[tuple[float, int, _Doc]] = []
    selected_texts: set[str] = set()
    # An explicitly named Raw file is stronger evidence of intent than short
    # CJK overlaps in unrelated notes. Reserve its first six sections in
    # source order so an introduction can be read even when the question and
    # the document use different languages.
    named_refs = {
        doc.citation.raw_ref
        for doc in docs
        if doc.citation.kind == "raw"
        and doc.citation.raw_ref is not None
        and len(PurePosixPath(doc.citation.raw_ref).stem) >= 8
        and PurePosixPath(doc.citation.raw_ref).stem.casefold() in question.casefold()
    }
    if named_refs:
        for item in sorted(scored, key=lambda candidate: candidate[1]):
            if len(selected) >= min(k, 6):
                break
            if item[2].citation.raw_ref in named_refs:
                selected.append(item)
                selected_texts.add(item[2].text.strip().casefold())
    if covered:
        for terms, label in facets:
            candidates = (
                (score(doc, terms, search_fields=True), position, doc)
                for position, doc in enumerate(docs)
                if _facet_candidate(doc, label)
            )
            ranked = sorted(
                (item for item in candidates if item[0] > 0),
                key=lambda item: (-item[0], item[1]),
            )
            limit = 1 if label[0] == "market" else 2
            added = 0
            for item in ranked:
                if len(selected) >= k or added >= limit:
                    break
                seen_sources = {candidate[2].citation.raw_ref for candidate in selected}
                normalized = item[2].text.strip().casefold()
                if item[2].citation.raw_ref in seen_sources or normalized in selected_texts:
                    continue
                selected.append(item)
                selected_texts.add(normalized)
                added += 1
    product_codes = {
        code.casefold()
        for code in _PRODUCT_ID.findall(question)
        if len(code) >= 5 and not code.upper().startswith(("B", "K"))
    }
    product_positions: set[int] = set()
    if product_codes and not named_refs:
        product_limit = min(k, 2 if covered else 5)
        seen_sources = {item[2].citation.raw_ref for item in selected}
        for item in scored:
            if len(product_positions) >= product_limit or len(selected) >= k:
                break
            doc = item[2]
            if (
                doc.citation.kind != "raw"
                or doc.citation.raw_ref in seen_sources
                or len(doc.text) < 80
                or not product_codes.intersection(doc.search_counts)
            ):
                continue
            selected.append(item)
            product_positions.add(item[1])
            selected_texts.add(doc.text.strip().casefold())
            seen_sources.add(doc.citation.raw_ref)
    selected_positions = {position for _, position, _ in selected}
    for item in scored:
        if len(selected) >= min_raw:
            break
        normalized = item[2].text.strip().casefold()
        if (
            item[2].citation.kind == "raw"
            and item[1] not in selected_positions
            and (not covered or normalized not in selected_texts)
        ):
            selected.append(item)
            selected_positions.add(item[1])
            selected_texts.add(normalized)
    for item in scored:
        if len(selected) >= k:
            break
        normalized = item[2].text.strip().casefold()
        if item[1] not in selected_positions and (not covered or normalized not in selected_texts):
            selected.append(item)
            selected_positions.add(item[1])
            selected_texts.add(normalized)
    ordered = (
        sorted(
            selected,
            key=lambda item: (
                0 if item[2].citation.raw_ref in named_refs else 1,
                item[1] if item[2].citation.raw_ref in named_refs else -item[0],
                item[1],
            ),
        )
        if named_refs
        else sorted(
            selected,
            key=lambda item: (0 if item[1] in product_positions else 1, -item[0], item[1]),
        )
    )
    return tuple(
        Passage(text=doc.text, citation=doc.citation, score=round(score, 6))
        for score, _, doc in ordered
    )


class QueryEngine:
    """Answers questions over a vault. Without a model it returns the ranked
    passages; with one it also synthesizes an answer that may cite only them."""

    def __init__(
        self,
        vault: Vault,
        model: ModelClient | None = None,
        *,
        alias: Symbol | None = None,
        prompt: Text = DEFAULT_PROMPT,
        max_output_tokens: int = 800,
    ) -> None:
        if (model is None) != (alias is None):
            raise ValueError("a model and its alias come together")
        if max_output_tokens < 1:
            raise ValueError("limits are positive")
        self.vault = vault
        self.model = model
        self.alias = alias
        self.prompt = prompt
        self.max_output_tokens = max_output_tokens
        self._asked = 0

    def ask(
        self,
        question: str,
        *,
        k: int = 5,
        trace: TraceIdentifiers | None = None,
        raw_citations_only: bool = False,
        evidence_coverage: bool = False,
        selected_passages: tuple[Passage, ...] | None = None,
    ) -> Answer:
        passages = (
            selected_passages
            if selected_passages is not None
            else retrieve(
                self.vault,
                question,
                k=k,
                min_raw=min(k, 4) if raw_citations_only else 0,
                evidence_coverage=evidence_coverage,
            )
        )
        if not passages:
            return Answer(question=question, status="no_match")
        if raw_citations_only and evidence_coverage and _coverage_terms(question):
            passages = _focused_raw_passages(passages, question)
        if self.model is None or self.alias is None:
            return Answer(question=question, status="retrieved", passages=passages)
        if raw_citations_only:
            numbered = "\n\n".join(
                f"[{number}] {passage.citation.kind.upper()}: {passage.text}"
                for number, passage in enumerate(passages, 1)
            )
        else:
            numbered = "\n\n".join(
                f"[{number}] {passage.text}" for number, passage in enumerate(passages, 1)
            )
        self._asked += 1
        if trace is None:
            digest = hashlib.sha256(question.encode("utf-8")).hexdigest()[:16]
            trace = TraceIdentifiers(
                trace_id=f"query-{digest}", request_id=f"ask-{self._asked}", span_id="synthesis"
            )
        market_guidance = (
            _MARKET_FIT_GUIDANCE
            if raw_citations_only and evidence_coverage and _coverage_terms(question)
            else ""
        )
        prompt = self.prompt.format(question=question, passages=numbered) + market_guidance
        for attempt in range(2 if raw_citations_only else 1):
            if attempt:
                # Keep the original passage numbers and omit Wiki text. Never
                # feed the unsupported first answer back to the model.
                raw_numbered = "\n\n".join(
                    f"[{number}] RAW: {passage.text}"
                    for number, passage in enumerate(passages, 1)
                    if passage.citation.kind == "raw"
                )
                prompt = self.prompt.format(
                    question=question, passages=raw_numbered or "No RAW passages available."
                ) + market_guidance + (
                    "\n\nUse one short sentence per supported claim. Put a RAW passage "
                    "citation [n] in every sentence. If the RAW passages do not "
                    "support an answer, say so without citations."
                )
            request = ModelRequest(
                trace=trace,
                model_alias=self.alias,
                messages=(ModelMessage(role="user", text=prompt),),
                requirements=ModelRequirements(),
                max_output_tokens=self.max_output_tokens,
            )
            try:
                response = self.model.generate(request)
            except Exception as error:  # noqa: BLE001 - an adapter's failure is a status here
                return Answer(
                    question=question,
                    status="model_failed",
                    passages=passages,
                    failure=failure_from_exception(error),
                )
            if response.failure is not None:
                return Answer(
                    question=question,
                    status="model_failed",
                    passages=passages,
                    failure=response.failure,
                )
            text = response.text.strip()
            cited = cited_numbers(text)
            if not raw_citations_only or not cited or (
                _has_raw_grounding(text, passages)
                and (not market_guidance or _has_market_fit_grounding(text, passages))
            ):
                break
        if any(n < 1 or n > len(passages) for n in cited):
            # Words without a retrieved source behind them are not an answer here.
            return Answer(question=question, status="uncited", passages=passages)
        if not text or not cited:
            # The model said the passages do not answer, as asked; keep its words.
            return Answer(
                question=question,
                status="unanswered",
                passages=passages,
                text=text,
                synthesized_by=self.alias,
            )
        if raw_citations_only and (
            not _has_raw_grounding(text, passages)
            or (market_guidance and not _has_market_fit_grounding(text, passages))
        ):
            # A Wiki citation or uncited sentence cannot become a Raw-grounded
            # answer, even after the formatting retry.
            return Answer(question=question, status="uncited", passages=passages)
        return Answer(
            question=question,
            status="answered",
            passages=passages,
            text=text,
            synthesized_by=self.alias,
        )
