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
DEFAULT_PROMPT = """Answer the question from the passages below and nothing else. Cite every
claim with the passage number in square brackets, like [2]. If the passages do
not answer the question, say so in one sentence and cite nothing.

Question: {question}

{passages}"""


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


class _Doc:
    def __init__(self, text: str, citation: Citation) -> None:
        self.text = text
        self.citation = citation
        self.counts = Counter(tokens(text))
        self.length = sum(self.counts.values())


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


def retrieve(vault: Vault, question: str, *, k: int = 5) -> tuple[Passage, ...]:
    """BM25 over every current Raw section and Wiki paragraph; ties break by
    corpus order, so the same question always returns the same passages."""
    if k < 1:
        raise ValueError("k is positive")
    query = tokens(question)
    if not query:
        return ()
    docs = _corpus(vault)
    if not docs:
        return ()
    average = sum(doc.length for doc in docs) / len(docs)
    frequency: Counter[str] = Counter()
    for doc in docs:
        frequency.update(set(doc.counts))
    k1, b = 1.5, 0.75
    scored: list[tuple[float, int, _Doc]] = []
    for position, doc in enumerate(docs):
        score = 0.0
        for term in set(query):
            count = doc.counts.get(term, 0)
            if not count:
                continue
            idf = math.log(1 + (len(docs) - frequency[term] + 0.5) / (frequency[term] + 0.5))
            score += idf * count * (k1 + 1) / (count + k1 * (1 - b + b * doc.length / average))
        if score > 0:
            scored.append((score, position, doc))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return tuple(
        Passage(text=doc.text, citation=doc.citation, score=round(score, 6))
        for score, _, doc in scored[:k]
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

    def ask(self, question: str, *, k: int = 5, trace: TraceIdentifiers | None = None) -> Answer:
        passages = retrieve(self.vault, question, k=k)
        if not passages:
            return Answer(question=question, status="no_match")
        if self.model is None or self.alias is None:
            return Answer(question=question, status="retrieved", passages=passages)
        numbered = "\n\n".join(
            f"[{number}] {passage.text}" for number, passage in enumerate(passages, 1)
        )
        self._asked += 1
        if trace is None:
            digest = hashlib.sha256(question.encode("utf-8")).hexdigest()[:16]
            trace = TraceIdentifiers(
                trace_id=f"query-{digest}", request_id=f"ask-{self._asked}", span_id="synthesis"
            )
        request = ModelRequest(
            trace=trace,
            model_alias=self.alias,
            messages=(
                ModelMessage(
                    role="user", text=self.prompt.format(question=question, passages=numbered)
                ),
            ),
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
        return Answer(
            question=question,
            status="answered",
            passages=passages,
            text=text,
            synthesized_by=self.alias,
        )
