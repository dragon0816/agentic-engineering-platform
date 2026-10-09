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
from collections.abc import Callable
from pathlib import PurePosixPath
from typing import Literal

from pydantic import Field, ValidationError

from common.base import Contract, Symbol, Text
from common.execution import Failure, TraceIdentifiers
from knowledge.contracts import KnowledgeSource
from knowledge.lint import WIKILINK, body_of, head_fields, read_pages
from knowledge.modelcalls import failure_from_exception
from knowledge.query_rewrite import content_words
from knowledge.raw import RawIndex, load_document, one_line_ending
from knowledge.vault import Vault, VaultError, normalize
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


_HEADING_LINE = re.compile(r"^ {0,3}#{1,6}\s")
_TABLE_DIVIDER = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)*\|?\s*$")


def is_table_row(line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith("|") and stripped.count("|") >= 2


def markdown_formatting_lines(lines: list[str]) -> set[int]:
    """Indices of headings, table header rows and dividers: structure, not claims."""
    found: set[int] = set()
    for index, line in enumerate(lines):
        if _HEADING_LINE.match(line) or _TABLE_DIVIDER.match(line):
            found.add(index)
        elif (
            is_table_row(line) and index + 1 < len(lines)
            and _TABLE_DIVIDER.match(lines[index + 1])
        ):
            found.add(index)
    return found


def keep_supported_lines(text: str, supported: Callable[[str], str]) -> str:
    """Filter an answer line by line while keeping its Markdown structure.

    `supported` returns the part of a claim line to keep ("" drops it).
    Headings and table header/divider rows are kept, then removed again if
    nothing they introduce survived.
    """
    lines = text.splitlines()
    formatting = markdown_formatting_lines(lines)
    kept: list[tuple[bool, str]] = []
    for index, line in enumerate(lines):
        if index in formatting:
            kept.append((True, line))
        elif line.strip():
            part = supported(line)
            if part:
                kept.append((False, part))
    # Drop a heading or table header whose body did not survive.
    result: list[str] = []
    for position, (structural, line) in enumerate(kept):
        if structural:
            following = kept[position + 1:]
            body = next((item for item in following if not item[0]), None)
            if body is None:
                continue
            if _HEADING_LINE.match(line):
                next_heading = next(
                    (offset for offset, item in enumerate(following)
                     if item[0] and _HEADING_LINE.match(item[1])),
                    len(following),
                )
                if not any(not item[0] for item in following[:next_heading]):
                    continue
            elif not is_table_row(body[1]) or any(
                item[0] and _HEADING_LINE.match(item[1])
                for item in following[:following.index(body)]
            ):
                continue
        result.append(line)
    return "\n".join(result).strip()


def cap_labeled_inferences(text: str, label: str | None) -> str:
    """Keep labeled inferences in place, at most MAX_LABELED_INFERENCES,
    and only beside a factual claim; drop structure left empty."""
    if not label:
        return text
    facts, _ = split_labeled_inferences(text, label)
    if not cited_claim_sentences(facts):
        return ""
    seen = 0

    def keep(line: str) -> str:
        nonlocal seen
        if _LIST_MARKER.sub("", line, count=1).strip().startswith(label):
            seen += 1
            return line if seen <= MAX_LABELED_INFERENCES else ""
        return line

    return keep_supported_lines(text, keep)


def cited_claim_sentences(text: str) -> tuple[str, ...]:
    """Split cited prose into claims; a Markdown table row is one claim.

    Headings and table header/divider rows are structure, not claims, so they
    need no citation. A table row is checked as a whole: its cells describe
    one cited item and must not be split at sentence punctuation.
    """
    lines = text.splitlines()
    formatting = markdown_formatting_lines(lines)
    claims: list[str] = []
    prose: list[str] = []
    for index, line in enumerate(lines):
        if index in formatting or is_table_row(line):
            claims.extend(_prose_sentences("\n".join(prose)))
            prose = []
            if index not in formatting:
                claims.append(line.strip())
            continue
        prose.append(line)
    claims.extend(_prose_sentences("\n".join(prose)))
    return tuple(claims)


def _prose_sentences(text: str) -> tuple[str, ...]:
    """Split cited prose without breaking release abbreviations or list lines."""
    # A list marker ("1.", "2)", "-") is formatting, not an uncited claim.
    unlisted = re.sub(r"(?m)^[ \t]*(?:\d{1,3}[.)]|[-*•])[ \t]+", "", text)
    # Keep every citation group that follows the terminal punctuation
    # ("fact。[5][7]") with its claim, not only the first one.
    attached = re.sub(
        r"([.!?。！？])[ \t]*((?:\[[0-9][0-9,\s-]*\][ \t]*)+)",
        lambda match: (
            " " + match.group(2).rstrip() + match.group(1)
            + match.group(2)[len(match.group(2).rstrip()):]
        ),
        unlisted,
    )
    protected = re.sub(
        r"\b(?:Rel|Fig|No)\.",
        lambda match: match.group(0)[:-1] + "\ue000",
        attached,
        flags=re.IGNORECASE,
    )
    return tuple(
        sentence.replace("\ue000", ".").strip()
        for sentence in re.split(r"(?<=[.!?])\s+|(?<=[。！？])\s*|\n+", protected)
        if sentence.strip()
    )


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


# Knowledge synthesis output limit when no Skill procedure sets one. 800 cut a
# reasoning model off before it answered (knowledge_v1 sample-001, owner 2026-10-07).
DEFAULT_SYNTHESIS_MAX_OUTPUT_TOKENS = 4000
TRUNCATED = "model_output_truncated"
TRUNCATED_NOTE = (
    "\n\nYour previous answer was cut off at the length limit. Answer again, more "
    "briefly: the supported points only, one short sentence each, with their citations."
)
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


MAX_LABELED_INFERENCES = 3
_LIST_MARKER = re.compile(r"^[ \t]*(?:\d{1,3}[.)]|[-*•])[ \t]+")
# Python treats CJK characters as word characters, so `\b` would hide the
# number in "2026年" or "Wi-Fi 7規格". Only ASCII letters and digits bind a
# number to a token here, which keeps ASCII behavior identical.
STATED_NUMBER = re.compile(r"(?<![0-9A-Za-z_])\d+(?:\.\d+)?(?![0-9A-Za-z_])")


def citable(passage: "Passage", allow_wiki: bool = False) -> bool:
    """Raw is always citable; a curated Wiki page only under Wiki-primary.

    `index.md` is navigation and never citable evidence.
    """
    if passage.citation.kind == "raw":
        return True
    return allow_wiki and passage.citation.wiki_page not in (None, "index.md")


def split_labeled_inferences(text: str, label: str | None) -> tuple[str, tuple[str, ...]]:
    """Separate a Skill's labeled inference lines from factual lines."""
    if not label:
        return text, ()
    facts: list[str] = []
    inferences: list[str] = []
    for line in text.splitlines():
        body = _LIST_MARKER.sub("", line, count=1).strip()
        if body.startswith(label):
            inferences.append(body)
        else:
            facts.append(line)
    return "\n".join(facts), tuple(inferences)


def product_codes(text: str) -> set[str]:
    """Product and option codes; "CMP-KB805" and "KB805" name the same option."""
    return {code.casefold().rsplit("-", 1)[-1] for code in _PRODUCT_ID.findall(text)}


def table_row_grounded(row: str, passages: tuple[Passage, ...]) -> bool:
    """A table row's codes must all appear in the sources that row cites.

    Cells of one row describe one item from possibly several cited passages,
    so the single-passage co-location rule for prose does not apply.
    """
    sources = " ".join(
        passages[number - 1].text
        for number in cited_numbers(row) if 1 <= number <= len(passages)
    )
    return not product_codes(_BRACKET.sub(" ", row)) - product_codes(sources)


def labeled_inference_grounded(
    line: str, passages: tuple[Passage, ...], label: str, *, allow_wiki: bool = False,
) -> bool:
    """Check one labeled inference against the Raw premises it cites.

    An inference may connect separately cited sources, which is why it is
    labeled rather than stated as fact. It may not introduce a product or
    option code or a number absent from its cited Raw premises, and each
    cited premise must share wording with the inference. This is a lexical
    guard, not proof that the inference is correct.
    """
    body = _LIST_MARKER.sub("", line.strip(), count=1).strip()
    if not label or not body.startswith(label):
        return False
    numbers = cited_numbers(body)
    if not numbers or any(
        number < 1 or number > len(passages)
        or not citable(passages[number - 1], allow_wiki)
        for number in numbers
    ):
        return False
    sources = " ".join(passages[number - 1].text for number in sorted(numbers))
    claim = _BRACKET.sub(" ", body[len(label):])
    if product_codes(claim) - product_codes(sources):
        return False
    if set(STATED_NUMBER.findall(claim)) - set(STATED_NUMBER.findall(sources)):
        return False
    claim_terms = {term for term in tokens(claim) if len(term) >= 2}
    return all(
        len(claim_terms & set(tokens(passages[number - 1].text))) >= 2
        for number in numbers
    )


def _has_raw_grounding(
    text: str, passages: tuple[Passage, ...], *, inference_label: str | None = None,
    allow_wiki: bool = False,
) -> bool:
    """Preflight the record's citation rules before a bounded synthesis retry.

    The final KnowledgeAnswerRecord remains authoritative. This check only
    decides whether a response needs another model attempt; it never adds a
    citation or changes the kind of evidence behind one. When a Skill names
    an inference label, labeled lines are checked as inferences, at most
    MAX_LABELED_INFERENCES, and at least one factual claim must remain.
    """
    text, inferences = split_labeled_inferences(text, inference_label)
    if inferences and (
        len(inferences) > MAX_LABELED_INFERENCES
        or not all(
            labeled_inference_grounded(
                line, passages, inference_label or "", allow_wiki=allow_wiki
            )
            for line in inferences
        )
    ):
        return False
    numbers = cited_numbers(text)
    if not numbers or any(
        number < 1 or number > len(passages)
        or not citable(passages[number - 1], allow_wiki)
        for number in numbers
    ):
        return False
    for sentence in cited_claim_sentences(text):
        sentence_citations = cited_numbers(sentence)
        if not sentence_citations:
            return False
        if is_table_row(sentence):
            if not table_row_grounded(sentence, passages):
                return False
            continue
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
    for sentence in cited_claim_sentences(text):
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


def _salvage_raw_sentences(
    text: str, passages: tuple[Passage, ...], *, market_guidance: bool,
    inference_label: str | None = None, allow_wiki: bool = False,
) -> str:
    """Keep individually grounded claims if another sentence failed citation checks.

    Grounded labeled inferences stay where the model placed them, up to the
    bound, and only when at least one fact survives.
    """

    def grounded(claim: str) -> bool:
        return _has_raw_grounding(claim, passages, allow_wiki=allow_wiki) and (
            not market_guidance or _has_market_fit_grounding(claim, passages)
        )

    def supported_part(line: str) -> str:
        body = _LIST_MARKER.sub("", line, count=1).strip()
        if inference_label and body.startswith(inference_label):
            return line.strip() if labeled_inference_grounded(
                line, passages, inference_label, allow_wiki=allow_wiki
            ) else ""
        if is_table_row(line):
            return line.strip() if grounded(line) else ""
        return "\n".join(
            sentence.strip()
            for sentence in cited_claim_sentences(line)
            if sentence.strip() and grounded(sentence.strip())
        )

    kept = keep_supported_lines(text, supported_part)
    if not cited_claim_sentences(split_labeled_inferences(kept, inference_label)[0]):
        return ""
    return cap_labeled_inferences(kept, inference_label)


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
        if passage.citation.kind != "raw" or len(passage.text) <= 800:
            focused.append(passage)
            continue
        # Keep distant table rows separate. Legacy Raw can also contain a
        # whole slide deck in one paragraph, so cap each line group/window.
        lines = passage.text.splitlines()
        groups = (
            ["\n".join(lines[index : index + 5]) for index in range(0, len(lines), 5)]
            if len(lines) >= 8 else [passage.text]
        )
        chunks = [
            group[start : start + 1200]
            for group in groups
            for start in range(0, len(group), 1000)
        ]
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
        self._vault = vault
        self._raw_by_ref: dict[str, list[_Doc]] = {}
        self._raw_by_id: dict[str, str] = {}
        self._wiki_by_title: dict[str, str] = {}
        self._index_docs: list[_Doc] = []
        self._navigation_ready = False
        self._wiki_sections: list[_Doc] | None = None

    def _prepare_wiki_navigation(self) -> None:
        if self._navigation_ready:
            return
        self._navigation_ready = True
        for doc in self._docs:
            ref = doc.citation.raw_ref
            if doc.citation.kind == "raw" and ref:
                self._raw_by_ref.setdefault(ref, []).append(doc)
                if doc.citation.source is not None:
                    self._raw_by_id[doc.citation.source.source_id] = ref
        self._wiki_by_title = {
            title.casefold(): rel for rel, title in self._vault.wiki_pages()
        }
        for line in self._vault.read("index.md").splitlines():
            match = re.match(r"^\s*[-*]\s+\[\[([^\]]+)\]\]\s*[—–-]\s*(.+)$", line)
            if match is not None:
                self._index_docs.append(
                    _Doc(line, Citation(kind="wiki", wiki_page="index.md"))
                )

    def batch(
        self, queries: tuple[str, ...], *, k: int, min_raw: int = 0
    ) -> tuple[tuple[Passage, ...], ...]:
        return tuple(
            _retrieve_docs(self._docs, query, k=k, min_raw=min_raw)
            for query in queries
        )

    def matching_raw(
        self, query: str, *, accepts: Callable[[Passage], bool], k: int = 3,
    ) -> tuple[Passage, ...]:
        """Rank eligible Raw sections after filtering the whole loaded corpus.

        A Skill's evidence constraint must not be applied only to the first
        lexical hits: a valid source can be ranked below unrelated snippets.
        """
        eligible = [
            doc for doc in self._docs
            if doc.citation.kind == "raw"
            and accepts(Passage(text=doc.text, citation=doc.citation, score=0.0))
        ]
        return _retrieve_docs(eligible, query, k=k, min_raw=k)

    def source_section(
        self, raw_ref: str, *, matches_sentence: Callable[[str], bool],
    ) -> Passage | None:
        """Follow a selected Raw source to its first matching original section."""
        self._prepare_wiki_navigation()
        for doc in self._raw_by_ref.get(raw_ref, ()):
            if any(
                matches_sentence(sentence)
                for sentence in re.split(r"(?<=[.!?。！？])\s+|\n+", doc.text)
            ):
                return Passage(text=doc.text, citation=doc.citation, score=0.0)
        return None

    def source_neighbors(self, raw_ref: str, section: int) -> tuple[Passage, ...]:
        """Read adjacent Raw sections without assigning them the hit's citation."""
        self._prepare_wiki_navigation()
        docs = self._raw_by_ref.get(raw_ref, ())
        position = next(
            (index for index, doc in enumerate(docs) if doc.citation.section == section),
            None,
        )
        if position is None:
            return ()
        return tuple(
            Passage(text=docs[index].text, citation=docs[index].citation, score=0.0)
            for index in (position - 1, position + 1)
            if 0 <= index < len(docs)
        )

    def matching_wiki_sources(
        self, query: str, *, accepts: Callable[[Passage], bool],
        k: int = 3, index_k: int = 8,
    ) -> tuple[Passage, ...]:
        """Read eligible Raw from each ranked index entry's linked Wiki source.

        Ranking one pooled set can let repeated sections of a popular product
        hide a different indexed source. Keep one section per source first.
        """
        self._prepare_wiki_navigation()
        if not self._index_docs:
            return ()
        index_hits = _retrieve_docs(self._index_docs, query, k=index_k, min_raw=0)
        refs: list[str] = []
        for hit in index_hits:
            match = WIKILINK.search(hit.text)
            page = self._wiki_by_title.get(match.group(1).casefold()) if match else None
            if page is None:
                continue
            linked: set[str] = set()
            self._follow_wiki_sources(page, linked, depth=1)
            for ref in sorted(linked):
                if ref not in refs:
                    refs.append(ref)
        selected: list[Passage] = []
        for ref in refs:
            eligible = [
                doc for doc in self._raw_by_ref.get(ref, ())
                if accepts(Passage(text=doc.text, citation=doc.citation, score=0.0))
            ]
            best = _retrieve_docs(eligible, query, k=1, min_raw=1)
            if best:
                selected.append(best[0])
            if len(selected) >= k:
                break
        return tuple(selected)

    def wiki_batch(
        self, queries: tuple[str, ...], *, k: int = 8
    ) -> tuple[tuple[Passage, ...], ...]:
        """Find curated Wiki leads before verifying claims in immutable Raw."""
        wiki = [doc for doc in self._docs if doc.citation.kind == "wiki"]
        return tuple(_retrieve_docs(wiki, query, k=k, min_raw=0) for query in queries)

    def wiki_guided_batch(
        self, queries: tuple[str, ...], *, k: int, min_raw: int = 0,
        index_k: int = 8,
    ) -> tuple[tuple[Passage, ...], ...]:
        """Navigate index → Wiki links → linked Raw, then supplement globally.

        The index and Wiki rank candidate sources; neither is silently treated
        as proof. The returned passages keep immutable Raw citations.
        """
        self._prepare_wiki_navigation()
        if not self._index_docs:
            return self.batch(queries, k=k, min_raw=min_raw)
        results: list[tuple[Passage, ...]] = []
        for query in queries:
            index_hits = _retrieve_docs(self._index_docs, query, k=index_k, min_raw=0)
            page_refs: list[str] = []
            for hit in index_hits:
                match = WIKILINK.search(hit.text)
                if match is None:
                    continue
                page = self._wiki_by_title.get(match.group(1).casefold())
                if page and page not in page_refs:
                    page_refs.append(page)
            raw_refs: list[str] = []
            for page in page_refs:
                linked: set[str] = set()
                self._follow_wiki_sources(page, linked, depth=1)
                for ref in sorted(linked):
                    if ref not in raw_refs:
                        raw_refs.append(ref)
            guided_limit = min(k, max(4, index_k // 3))
            guided_list: list[Passage] = []
            for ref in raw_refs:
                best = _retrieve_docs(
                    self._raw_by_ref.get(ref, []), query, k=1, min_raw=1
                )
                if best:
                    guided_list.append(best[0])
                if len(guided_list) >= guided_limit:
                    break
            guided = tuple(guided_list)
            global_passages = self.batch((query,), k=k, min_raw=min_raw)[0]
            seen: set[tuple[str | None, int | None]] = set()
            merged: list[Passage] = []
            for passage in (*guided, *global_passages):
                key = (passage.citation.raw_ref, passage.citation.section)
                if key not in seen and len(merged) < k:
                    merged.append(passage)
                    seen.add(key)
            results.append(tuple(merged))
        return tuple(results)

    def wiki_index_context(
        self, question: str, *, k: int = 3, index_k: int = 8,
    ) -> tuple[Passage, ...]:
        """Read bounded curated text from pages located through index.md."""
        self._prepare_wiki_navigation()
        if not self._index_docs:
            return ()
        index_hits = _retrieve_docs(self._index_docs, question, k=index_k, min_raw=0)
        pages: list[str] = []
        for hit in index_hits:
            match = WIKILINK.search(hit.text)
            if match is None:
                continue
            page = self._wiki_by_title.get(match.group(1).casefold())
            if page and page not in pages:
                pages.append(page)
        for page in tuple(pages):
            for link in WIKILINK.finditer(body_of(self._vault.read(page))):
                target = self._wiki_by_title.get(link.group(1).casefold())
                if target and target not in pages and len(pages) < 12:
                    pages.append(target)
        docs = [
            doc for doc in self._docs
            if doc.citation.kind == "wiki" and doc.citation.wiki_page in pages
        ]
        if not docs:
            return ()
        ranked = _retrieve_docs(docs, question, k=k, min_raw=0)
        if ranked:
            return ranked
        return tuple(
            Passage(text=doc.text, citation=doc.citation, score=0.0)
            for doc in docs[:k]
        )

    def _follow_wiki_sources(
        self, page: str, raw_refs: set[str], *, depth: int
    ) -> None:
        text = self._vault.read(page)
        head = head_fields(text) or {}
        raw_ref = normalize(head.get("source_path", ""))
        if raw_ref in self._raw_by_ref:
            raw_refs.add(raw_ref)
        source_ref = self._raw_by_id.get(head.get("source_id", ""))
        if source_ref:
            raw_refs.add(source_ref)
        if depth == 0:
            return
        for link in WIKILINK.finditer(body_of(text)):
            target = self._wiki_by_title.get(link.group(1).casefold())
            if target and target != page:
                self._follow_wiki_sources(target, raw_refs, depth=0)

    def wiki_provenance(self, page: str) -> tuple[str, ...]:
        """The Raw sources a Wiki page was curated from, via its source links."""
        self._prepare_wiki_navigation()
        refs: set[str] = set()
        self._follow_wiki_sources(page, refs, depth=1)
        return tuple(sorted(refs))[:16]

    def _wiki_section_docs(self) -> list[_Doc]:
        if self._wiki_sections is None:
            self._wiki_sections = [
                _Doc(text, Citation(kind="wiki", wiki_page=rel, section=number))
                for rel, title in self._vault.wiki_pages()
                for number, text in enumerate(
                    wiki_sections(title, self._vault.read(rel)), 1
                )
            ]
        return self._wiki_sections

    def wiki_primary_passages(
        self, queries: tuple[str, ...], *, k: int = 24, per_page: int = 3,
        index_k: int = 8, raw_k: int = 4, max_chars: int = 40000, linked_from: int = 6,
        content_only: bool = False,
    ) -> tuple[Passage, ...]:
        """Rank curated Wiki sections first, then add a few Raw fallbacks.

        For every query, sections of pages located through `index.md` lead,
        followed by a full-text ranking of all Wiki sections. Queries are
        interleaved so one facet cannot fill the budget, and no page supplies
        more than `per_page` sections. Raw passages cover claims the Wiki
        does not; they keep their own citations. With `content_only`, English
        function words are left out of every query's ranking.
        """
        if content_only:
            queries = tuple(content_words(query) for query in queries)
        self._prepare_wiki_navigation()
        docs = self._wiki_section_docs()
        by_page: dict[str, list[_Doc]] = {}
        for doc in docs:
            by_page.setdefault(doc.citation.wiki_page or "", []).append(doc)
        ranked: list[list[Passage]] = []
        for query in queries:
            led: list[Passage] = []
            if self._index_docs:
                for hit in _retrieve_docs(self._index_docs, query, k=index_k, min_raw=0):
                    match = WIKILINK.search(hit.text)
                    page = self._wiki_by_title.get(match.group(1).casefold()) if match else None
                    if page and by_page.get(page):
                        led.extend(_retrieve_docs(by_page[page], query, k=per_page, min_raw=0))
            found = [*led, *_retrieve_docs(docs, query, k=k, min_raw=0)]
            ranked.append(found)
            # Follow the leading concept/synthesis pages' links to the entity
            # (product) pages they discuss, as a reader of the Wiki would.
            linked: list[Passage] = []
            followed: set[str] = set()
            for passage in found[:linked_from]:
                page = passage.citation.wiki_page or ""
                if page.startswith("wiki/entities/") or page in followed:
                    continue
                followed.add(page)
                for link in WIKILINK.finditer(passage.text):
                    target = self._wiki_by_title.get(link.group(1).casefold())
                    if target and target.startswith("wiki/entities/") and by_page.get(target):
                        linked.extend(_retrieve_docs(by_page[target], query, k=1, min_raw=0))
            ranked.append(linked)
        selected: list[Passage] = []
        seen: set[tuple[str | None, int | None]] = set()
        counts: dict[str, int] = {}
        chars = 0
        for position in range(max((len(items) for items in ranked), default=0)):
            for items in ranked:
                if position >= len(items) or len(selected) >= k:
                    continue
                passage = items[position]
                page = passage.citation.wiki_page or ""
                key = (page, passage.citation.section)
                if (
                    key in seen or counts.get(page, 0) >= per_page
                    or chars + len(passage.text) > max_chars
                ):
                    continue
                selected.append(passage)
                seen.add(key)
                counts[page] = counts.get(page, 0) + 1
                chars += len(passage.text)
        raw_docs = [doc for doc in self._docs if doc.citation.kind == "raw"]
        fallback = (
            _retrieve_docs(raw_docs, queries[0], k=raw_k, min_raw=raw_k)
            if queries and raw_docs and raw_k else ()
        )
        return (*selected, *fallback)


_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
WIKI_SECTION_CHARS = 1800


def _bounded_parts(content: str, limit: int = WIKI_SECTION_CHARS) -> list[str]:
    """Split a long Wiki section by paragraph, then by line, repeating a
    table's header row and divider in every part so each stays readable."""
    if len(content) <= limit:
        return [content]
    parts: list[str] = []
    current = ""
    for paragraph in re.split(r"\n\s*\n", content):
        if len(paragraph) > limit:
            lines = paragraph.splitlines()
            header = (
                lines[:2]
                if len(lines) > 2 and lines[0].lstrip().startswith("|")
                and re.match(r"^\s*\|?\s*:?-{3,}", lines[1]) else []
            )
            chunk = list(header)
            for line in lines[len(header):]:
                if chunk and len("\n".join([*chunk, line])) > limit and len(chunk) > len(header):
                    parts.append("\n".join(chunk))
                    chunk = [*header]
                chunk.append(line)
            if len(chunk) > len(header):
                parts.append("\n".join(chunk))
            continue
        if current and len(current) + len(paragraph) + 2 > limit:
            parts.append(current)
            current = ""
        current = f"{current}\n\n{paragraph}" if current else paragraph
    if current:
        parts.append(current)
    return parts


def wiki_sections(title: str, text: str) -> list[str]:
    """Chunk one Wiki page by heading; each chunk names its page and heading.

    Tables stay with their heading, so a cited row keeps its column meaning.
    """
    sections: list[str] = []
    heading = ""
    lines: list[str] = []

    def flush() -> None:
        content = "\n".join(lines).strip()
        # A "See also" style list of links is navigation, not evidence.
        prose = re.sub(r"[-*•\s|]+", " ", WIKILINK.sub(" ", content)).strip()
        if not content or len(prose) < 24:
            return
        label = f"{title} › {heading}" if heading else title
        sections.extend(f"{label}\n{part}" for part in _bounded_parts(content))

    for line in one_line_ending(body_of(text)).splitlines():
        match = _HEADING.match(line)
        if match is None:
            lines.append(line)
            continue
        flush()
        lines = []
        heading = "" if match.group(2).strip() == title else match.group(2).strip()
    flush()
    return sections


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
        max_output_tokens: int = DEFAULT_SYNTHESIS_MAX_OUTPUT_TOKENS,
        inference_label: str | None = None,
        allow_wiki: bool = False,
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
        self.inference_label = inference_label
        self.allow_wiki = allow_wiki
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
        if raw_citations_only and (evidence_coverage or selected_passages is not None):
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
        drafts: list[str] = []
        for attempt in range(2 if raw_citations_only else 1):
            if attempt:
                # Keep the original passage numbers and omit uncitable text.
                # Never feed the unsupported first answer back to the model.
                kinds = "WIKI or RAW" if self.allow_wiki else "RAW"
                raw_numbered = "\n\n".join(
                    f"[{number}] {passage.citation.kind.upper()}: {passage.text}"
                    for number, passage in enumerate(passages, 1)
                    if citable(passage, self.allow_wiki)
                )
                prompt = self.prompt.format(
                    question=question,
                    passages=raw_numbered or f"No {kinds} passages available.",
                ) + market_guidance + (
                    f"\n\nUse one short sentence per supported claim. Put a {kinds} passage "
                    f"citation [n] in every sentence. If the {kinds} passages do not "
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
                if response.failure is not None and response.failure.code == TRUNCATED:
                    # A reasoning model can spend the limit before it answers; ask once
                    # more, from the same evidence, for a shorter answer (owner 2026-10-07).
                    response = self.model.generate(request.model_copy(update={"messages": (
                        ModelMessage(role="user", text=prompt + TRUNCATED_NOTE),)}))
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
            if raw_citations_only and not text and attempt == 0:
                # Some Gateway turns complete with no visible text despite no
                # provider failure. Give the same evidence one bounded retry.
                continue
            if text:
                drafts.append(text)
            if not raw_citations_only or not cited or (
                _has_raw_grounding(
                    text, passages, inference_label=self.inference_label,
                    allow_wiki=self.allow_wiki,
                )
                and (not market_guidance or _has_market_fit_grounding(text, passages))
            ):
                break
        if not text and drafts:
            # The retry came back empty (a Gateway turn with no visible text);
            # keep the earlier draft for per-sentence salvage below.
            text = drafts[-1]
            cited = cited_numbers(text)
        if len(drafts) == 2 and cited_numbers(drafts[0]):
            # The retry is a fresh generation, not a repair, so even a fully
            # grounded retry can drop supported claims the first draft had.
            # Keep the first draft only if it retains strictly more grounded
            # sentences; the per-sentence salvage below decides what survives.
            def supported(draft: str) -> int:
                salvaged = _salvage_raw_sentences(
                    draft, passages, market_guidance=bool(market_guidance),
                    inference_label=self.inference_label, allow_wiki=self.allow_wiki,
                )
                return len(salvaged.splitlines()) if salvaged else 0

            if supported(drafts[0]) > supported(drafts[1]):
                text = drafts[0]
                cited = cited_numbers(text)
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
            not _has_raw_grounding(
                    text, passages, inference_label=self.inference_label,
                    allow_wiki=self.allow_wiki,
                )
            or (market_guidance and not _has_market_fit_grounding(text, passages))
        ):
            text = _salvage_raw_sentences(
                text, passages, market_guidance=bool(market_guidance),
                inference_label=self.inference_label, allow_wiki=self.allow_wiki,
            )
            if not text:
                # A Wiki citation or uncited sentence cannot become a
                # Raw-grounded answer, even after the formatting retry.
                return Answer(question=question, status="uncited", passages=passages)
        return Answer(
            question=question,
            status="answered",
            passages=passages,
            text=text,
            synthesized_by=self.alias,
        )
