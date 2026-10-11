"""Ingest planning through the model interface: from one Raw document to a
`WritePlan` that the vault validates and applies.

Two passes, as the source tooling found cheaper and more accurate than one:
first the model picks which existing wiki pages matter (from an inventory of
paths and titles, capped), then it proposes the writes with those pages, the
index, the recorded decisions and the source text in front of it. A long
source is condensed chunk by chunk first, and that — by far the most
expensive step — is cached under the vault, keyed by everything the condensed
text depends on, so a plan rejected downstream never costs the condensation
twice and a changed input never reads a stale one.

The model proposes; it never writes. Its answer is data, repaired where the
repair is mechanical (the provenance lines a sources page must carry, whether
a page is created or updated) and otherwise handed to `knowledge.vault` to
validate and apply. No provider is named here; every call goes through
`ModelClient` with `structured_output` declared.
"""

import hashlib
import json
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, ValidationError

from common.base import Contract, Symbol, Text
from common.execution import Failure, TraceIdentifiers
from knowledge.layered_index import index_entries, is_navigation
from knowledge.modelcalls import failure_from_exception
from knowledge.raw import RawDocument, one_line_ending
from knowledge.sections import (
    HUMAN_AREAS,
    OPS,
    SectionError,
    apply_op,
    correction_of,
    lost_lines,
    parse,
    sourced_lines,
)
from knowledge.vault import (
    SOURCES_AREA,
    IndexEntry,
    PlannedPage,
    PlanProblem,
    Vault,
    WritePlan,
    carries_provenance,
    normalize,
    provenance_lines,
)
from models.contracts import ModelClient, ModelMessage, ModelRequest, ModelRequirements

PLAN_CONTRACT = "knowledge.ingest-plan.v1"
RELEVANCE_CONTRACT = "knowledge.ingest-relevance.v1"
CATEGORY_CONTRACT = "knowledge.ingest-categories.v1"
MAX_CATEGORIES = 3
INVENTORY_LINE_CHARS = 200
CONDENSE_OVER_CHARS = 40_000
CHUNK_CHARS = 24_000
MAX_RELEVANT = 8
NO_DECISIONS = "(no settled decisions)"
# A model that has nothing to report sometimes says so in words; these are not
# contradictions.
_NO_CONTRADICTION = frozenset({"none", "n/a", "no", "no contradictions", "-"})

DEFAULT_CONVENTIONS = """You maintain a Markdown wiki that is curated from immutable Raw sources.
Pages live under wiki/sources/ (one summary page per source), wiki/entities/,
wiki/concepts/ and wiki/syntheses/. Every page begins with YAML frontmatter with
at least `title`, `type` and `updated`. Link pages with [[Page Name]] — bare page
names, never paths and never a .md suffix. State only what the source supports,
keep the source's own terms, and when a source contradicts an existing page,
write a line starting with ⚠️ on the affected page that says which source says
what and when. Decisions listed as settled are final: never reinstate a rejected
claim. Pages under wiki/paths/ are written by people: never create or change them."""

CATEGORY_PROMPT = """A source is about to be ingested into a large wiki. Below are the categories
of its index and the source text. Pick the categories whose pages you would need
to read and possibly update to ingest this source.

Answer with JSON only: {{"categories": ["an exact category title", ...]}}
Rules: titles exactly as listed; at most {cap}; an empty list is a valid answer.

===== categories =====
{categories}

===== source: {source_ref} =====
{source_text}"""

RELEVANCE_PROMPT = """A source is about to be ingested. Below are the existing wiki pages (path and
title) and the source text. Decide which existing pages you would need to read
and possibly update to ingest this source.

Answer with JSON only: {{"relevant": ["wiki/entities/Foo.md", ...]}}
Rules: list only paths that appear in the inventory; prefer fewer; at most {cap};
an empty list is a valid answer.

===== existing wiki pages =====
{inventory}

===== source: {source_ref} =====
{source_text}"""

PLAN_PROMPT = """Ingest the source below into the wiki.

Answer with JSON only, in this shape:
{{
  "summary": "one sentence, for a person, on what this ingest does",
  "pages": [
    {{"path": "wiki/sources/<Title>.md",
      "content": "the whole new page, frontmatter included"}},
    {{"path": "wiki/entities/<Existing>.md", "op": "append_to_section",
      "heading": "相關來源", "content": "- [[<Title>]] — what it adds"}},
    {{"path": "wiki/entities/<Existing>.md", "op": "set_frontmatter",
      "fields": {{"updated": "{today}"}}}}
  ],
  "index_entries": [{{"section": "Sources|Entities|Concepts|Syntheses",
                      "line": "- [[Page]] — one line."}}],
  "log_body": "- Source: ...\\n- Added ...",
  "contradictions": []
}}

Rules:
- A new page is one object with `content`: the complete file, frontmatter included.
- Never rewrite an existing page (those under "existing pages you may update").
  Change it with operations, one object each, applied in order:
  `add_section` (new `## heading` with `content`), `append_to_section` (lines added
  at the end of the section named by `heading`), `replace_section` (the section's
  new body) and `set_frontmatter` (`fields` to set; never `title`). `heading` is the
  heading text without `## `; `content` is the body without the heading.
- Never remove a line that links a source page or a ⚠️ line. A `replace_section`
  that must correct one adds `"correction": {{"reason": "...", "source": "[[Source
  page]]"}}`; otherwise the whole plan is refused.
- Never write under wiki/paths/: those pages are written by people.
- Exactly one page under wiki/sources/ summarises this source.
- `contradictions` lists real contradictions with existing pages, one sentence
  each; leave it empty when there are none. When you find one, also write a ⚠️
  line on the affected entity or concept page: readers see pages, not logs.
- Settled decisions below are final. Do not reinstate a rejected claim; if the
  source contradicts a decision, say so under contradictions and keep the decision.
- Today is {today}, for `created` and `updated`.
- Write only under wiki/. index.md and log.md are updated for you from
  index_entries and log_body.
- Use [[wikilinks]] freely, including to pages that do not exist yet.

===== settled decisions =====
{decisions}

===== current index.md =====
{index}

===== existing pages you may update =====
{related}

===== source: {source_ref} =====
{source_text}"""

CONDENSE_PROMPT = """This is part {n} of {total} of a long source. Extract this part's substance:
keep concrete facts, names, numbers, models, conclusions, in the source's own
terms, as bullet points. Add nothing that is not in the text and do not
describe the text — state its content."""

PlanningStatus = Literal["planned", "invalid", "model_failed", "unparseable"]


class IngestProposal(BaseModel):
    """The model's answer, as loosely as it may arrive; `WritePlan` is the
    strict form the vault checks."""

    model_config = ConfigDict(extra="ignore")

    summary: str = ""
    pages: list[dict[str, JsonValue]] = Field(default_factory=list)
    index_entries: list[dict[str, JsonValue]] = Field(default_factory=list)
    log_body: str = ""
    contradictions: list[str] = Field(default_factory=list)


class PlanningOutcome(Contract):
    """What planning one source produced. `planned` carries a plan the vault
    accepted in a dry run; `invalid` carries the plan and the problems; the
    other statuses carry the failure."""

    status: PlanningStatus
    source_ref: Text
    plan: WritePlan | None = None
    problems: tuple[PlanProblem, ...] = ()
    relevant: tuple[Text, ...] = ()
    condensed: bool = False
    cache_hit: bool = False
    failure: Failure | None = None


def source_text(document: RawDocument) -> str:
    """The Raw document as the model should read it: sections in order, with
    each image's description (or its absence) in place."""
    parts: list[str] = []
    for section in document.sections:
        if section.kind == "image":
            label = section.text.strip() or "(no description)"
            place = f" on page {section.page}" if section.page else ""
            place = place or (f" on slide {section.slide}" if section.slide else "")
            parts.append(f"[image{place}: {label}]")
        else:
            parts.append(section.text)
    return "\n\n".join(parts)


_FENCE = re.compile(r"```(?:json)?\s*\n(.*?)```", re.DOTALL)


def extract_json(text: str) -> JsonValue:
    """Models wrap JSON in prose or fences often enough to be worth handling."""
    body = text.strip()
    fenced = _FENCE.search(body)
    if fenced:
        body = fenced.group(1).strip()
    try:
        return json.loads(body)  # type: ignore[no-any-return]
    except ValueError:
        start, end = body.find("{"), body.rfind("}")
        if 0 <= start < end:
            return json.loads(body[start : end + 1])  # type: ignore[no-any-return]
        raise


def _closing_frontmatter(lines: list[str]) -> int | None:
    if not lines or lines[0].strip() != "---":
        return None
    return next((index for index, line in enumerate(lines[1:], 1) if line.strip() == "---"), None)


def ensure_provenance(plan: WritePlan) -> WritePlan:
    """The sources page must carry the source's identity lines. They are
    deterministic, so a model that omitted them is repaired, not rejected."""
    pages = []
    for page in plan.pages:
        if normalize(page.path).startswith(SOURCES_AREA) and not carries_provenance(
            page.content, plan.source
        ):
            lines = one_line_ending(page.content).split("\n")
            wanted = list(provenance_lines(plan.source))
            end = _closing_frontmatter(lines)
            if end is not None:
                kept = [
                    line
                    for line in lines[1:end]
                    if not line.startswith(("source_id:", "source_sha256:"))
                ]
                lines = ["---", *kept, *wanted, "---", *lines[end + 1 :]]
            else:
                lines = ["---", *wanted, "---", *lines]
            pages.append(page.model_copy(update={"content": "\n".join(lines)}))
        else:
            pages.append(page)
    return plan.model_copy(update={"pages": tuple(pages)})


class IngestPlanner:
    """Plans one Raw document's ingest. Reads the vault; never writes to it
    except the condensation cache."""

    def __init__(
        self,
        model: ModelClient,
        vault: Vault,
        *,
        alias: Symbol,
        conventions: Text = DEFAULT_CONVENTIONS,
        max_output_tokens: int = 8000,
        condense_over: int = CONDENSE_OVER_CHARS,
        chunk_chars: int = CHUNK_CHARS,
    ) -> None:
        if max_output_tokens < 1 or condense_over < 1 or chunk_chars < 1:
            raise ValueError("limits are positive")
        if not conventions.strip():
            raise ValueError("conventions are the system message and cannot be empty")
        self.model = model
        self.vault = vault
        self.alias = alias
        self.conventions = conventions
        self.max_output_tokens = max_output_tokens
        self.condense_over = condense_over
        self.chunk_chars = chunk_chars
        self._sources: set[str] | None = None

    def cache_key(self, text: str) -> str:
        """Everything the condensed text depends on: the rendered source, the
        chunking, the prompt and the model that answered."""
        material = f"{self.alias}\n{self.chunk_chars}\n{CONDENSE_PROMPT}\n{text}"
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    def plan(
        self, document: RawDocument, *, today: str, decisions: str = NO_DECISIONS
    ) -> PlanningOutcome:
        source = document.source
        source_ref = source.raw_ref or source.original_ref
        trace_id = f"ingest-{source.sha256[:16]}"
        text = source_text(document)
        condensed = cache_hit = False
        if len(text) > self.condense_over:
            key = self.cache_key(text)
            cached = self.vault.cache_read(key)
            if cached is not None:
                text, condensed, cache_hit = cached, True, True
            else:
                try:
                    text = self._condense(text, source_ref, trace_id)
                except _ModelFailed as failed:
                    return self._failed(source_ref, failed)
                self.vault.cache_write(key, text)
                condensed = True

        try:
            inventory, inventory_text = self._inventory(text, source_ref, trace_id)
            answer = self._ask(
                RELEVANCE_PROMPT.format(
                    inventory=inventory_text,
                    source_ref=source_ref,
                    source_text=text[: self.condense_over],
                    cap=MAX_RELEVANT,
                ),
                contract=RELEVANCE_CONTRACT,
                trace=TraceIdentifiers(trace_id=trace_id, request_id="relevance", span_id="pass-1"),
            )
        except _ModelFailed as failed:
            return self._failed(source_ref, failed, condensed=condensed, cache_hit=cache_hit)
        known = {path for path, _ in inventory}
        proposed = answer.get("relevant") if isinstance(answer, dict) else None
        items = proposed if isinstance(proposed, list) else []
        relevant = tuple(
            dict.fromkeys(item for item in items if isinstance(item, str) and item in known)
        )[:MAX_RELEVANT]

        related = (
            "\n\n".join(f"----- {path} -----\n{self.vault.read(path)}" for path in relevant)
            or "(no related pages)"
        )
        try:
            answer = self._ask(
                PLAN_PROMPT.format(
                    decisions=decisions or NO_DECISIONS,
                    index=self.vault.read("index.md"),
                    related=related,
                    source_ref=source_ref,
                    source_text=text,
                    today=today,
                ),
                contract=PLAN_CONTRACT,
                trace=TraceIdentifiers(trace_id=trace_id, request_id="plan", span_id="pass-2"),
            )
        except _ModelFailed as failed:
            return self._failed(source_ref, failed, relevant, condensed, cache_hit)
        try:
            plan, edit_problems = self._plan_from(answer, document)
        except ValidationError as error:
            failure = Failure(code="plan_shape", message=f"{error.error_count()} field errors")
            return self._failed(
                source_ref, _ModelFailed(failure, "unparseable"), relevant, condensed, cache_hit
            )
        plan = ensure_provenance(plan)
        outcome = self.vault.apply(plan)  # a dry run: validation only, nothing written
        problems = (*edit_problems, *outcome.problems)
        return PlanningOutcome(
            status="invalid" if problems else "planned",
            source_ref=source_ref,
            plan=plan,
            problems=problems,
            relevant=relevant,
            condensed=condensed,
            cache_hit=cache_hit,
        )

    def _plan_from(
        self, answer: JsonValue, document: RawDocument
    ) -> tuple[WritePlan, tuple[PlanProblem, ...]]:
        """The strict plan and the section-edit problems. Whether a page is
        created or updated is a fact the vault knows, so it is decided here,
        never guessed by the model. Section operations on one page are applied
        in order to its current text; the result is one whole page for the
        vault, checked against the deletion guard (K3.2)."""
        proposal = IngestProposal.model_validate(answer)
        problems: list[PlanProblem] = []
        pages: list[PlannedPage] = []
        edited: dict[str, int] = {}  # path -> its position in pages
        allowed: dict[str, set[str]] = {}  # sourced lines a correction may remove
        for item in proposal.pages:
            path = item.get("path")
            exists = isinstance(path, str) and self._exists(path)
            op = item.get("op")
            if isinstance(path, str) and normalize(path).startswith(HUMAN_AREAS):
                problems.append(PlanProblem(code="human_page", path=path))
                continue
            if op is None or op == "create":
                pages.append(PlannedPage.model_validate({
                    "path": path, "content": item.get("content", ""),
                    "action": "update" if exists else "create"}))
                continue
            if not isinstance(path, str) or not exists or op not in OPS:
                problems.append(PlanProblem(
                    code="section_operation", path=str(path),
                    detail="unknown operation" if op not in OPS else "page does not exist"))
                continue
            key = normalize(path)
            current = pages[edited[key]].content if key in edited else self.vault.read(key)
            try:
                updated = apply_op(current, dict(item))
            except SectionError as error:
                problems.append(PlanProblem(code="section_operation", path=path,
                                            detail=str(error)[:200]))
                continue
            if op == "replace_section" and correction_of(dict(item)) is not None:
                parsed = parse(current)
                body = parsed.sections[parsed.find(str(item.get("heading") or ""))][1]
                allowed.setdefault(key, set()).update(
                    sourced_lines("\n".join(body), self._source_titles()))
            if key in edited:
                pages[edited[key]] = pages[edited[key]].model_copy(update={"content": updated})
            else:
                edited[key] = len(pages)
                pages.append(PlannedPage(path=key, action="update", content=updated))
        for page in pages:
            if page.action != "update":
                continue
            lost = [line for line in lost_lines(self.vault.read(page.path), page.content,
                                                self._source_titles())
                    if line not in allowed.get(normalize(page.path), set())]
            if lost:
                problems.append(PlanProblem(code="drops_sourced_line", path=page.path,
                                            detail=f"{len(lost)}: {lost[0][:160]}"))
        return WritePlan(
            source=document.source,
            summary=proposal.summary,
            pages=tuple(pages),
            index_entries=tuple(
                IndexEntry.model_validate(entry) for entry in proposal.index_entries
            ),
            log_body=proposal.log_body,
            contradictions=tuple(
                note
                for note in proposal.contradictions
                if note.strip() and note.strip().lower() not in _NO_CONTRADICTION
            ),
        ), tuple(problems)

    def _source_titles(self) -> set[str]:
        if self._sources is None:
            self._sources = {title.casefold() for path, title in self.vault.wiki_pages()
                             if path.startswith(SOURCES_AREA)}
        return self._sources

    def _exists(self, path: str) -> bool:
        try:
            return self.vault.exists(path)
        except Exception:  # noqa: BLE001 - an unresolvable path is for check_plan to refuse
            return False

    def _condense(self, text: str, source_ref: str, trace_id: str) -> str:
        chunks = [text[i : i + self.chunk_chars] for i in range(0, len(text), self.chunk_chars)]
        parts = []
        for number, chunk in enumerate(chunks, 1):
            trace = TraceIdentifiers(
                trace_id=trace_id, request_id=f"condense-{number}", span_id="condense"
            )
            prompt = CONDENSE_PROMPT.format(n=number, total=len(chunks)) + "\n\n" + chunk
            part = self._ask_text(prompt, trace=trace).strip()
            if not part:
                # A hollow part would be cached for good; better no cache at all.
                raise _ModelFailed(
                    Failure(
                        code="condense_empty",
                        message=f"part {number} of {len(chunks)} came back empty",
                        retryable=True,
                    )
                )
            parts.append(part)
        return f"(source {source_ref} is long; its parts, condensed)\n\n" + "\n\n".join(parts)

    def _request(
        self, prompt: str, *, trace: TraceIdentifiers, contract: str | None
    ) -> ModelRequest:
        return ModelRequest(
            trace=trace,
            model_alias=self.alias,
            messages=(
                ModelMessage(role="system", text=self.conventions),
                ModelMessage(role="user", text=prompt),
            ),
            requirements=ModelRequirements(structured_output=contract is not None),
            output_contract=contract,
            max_output_tokens=self.max_output_tokens,
        )

    def _generate(self, request: ModelRequest) -> tuple[JsonValue, str]:
        try:
            response = self.model.generate(request)
        except Exception as error:  # noqa: BLE001 - an adapter's failure is a status here
            raise _ModelFailed(failure_from_exception(error)) from error
        if response.failure is not None:
            raise _ModelFailed(response.failure)
        return response.structured_output, response.text

    def _inventory(
        self, text: str, source_ref: str, trace_id: str
    ) -> tuple[tuple[tuple[str, str], ...], str]:
        """The pages the relevance pass may choose from. A flat index offers
        every page; a layered index (K2) first asks which categories the source
        touches and offers only their pages, each with its bilingual line."""
        every = self.vault.wiki_pages()
        pages = tuple((path, title) for path, title in every if not is_navigation(path))
        entries = [entry for entry in index_entries(
            self.vault, {title.casefold(): path for path, title in every}) if entry.category]
        if not entries:
            listed = "\n".join(f"- {path} — {title}" for path, title in pages)
            return pages, listed or "(no pages yet)"
        categories = list(dict.fromkeys(entry.category for entry in entries))
        answer = self._ask(
            CATEGORY_PROMPT.format(
                categories="\n".join(f"- {name}" for name in categories),
                source_ref=source_ref, source_text=text[: self.condense_over],
                cap=MAX_CATEGORIES),
            contract=CATEGORY_CONTRACT,
            trace=TraceIdentifiers(trace_id=trace_id, request_id="categories", span_id="pass-0"),
        )
        named = answer.get("categories") if isinstance(answer, dict) else None
        chosen = set(list(dict.fromkeys(
            item for item in (named if isinstance(named, list) else [])
            if item in categories))[:MAX_CATEGORIES])
        titles = dict(pages)
        lines: dict[str, str] = {}
        for entry in entries:
            if entry.category in chosen:
                lines.setdefault(entry.page, f"- {entry.page} — "
                                 f"{entry.line.lstrip('-* ')[:INVENTORY_LINE_CHARS]}")
        offered = tuple((path, titles.get(path, path)) for path in lines)
        return offered, "\n".join(lines.values()) or "(no pages in the chosen categories)"

    def _ask(self, prompt: str, *, contract: str, trace: TraceIdentifiers) -> JsonValue:
        structured, text = self._generate(self._request(prompt, trace=trace, contract=contract))
        if structured is not None:
            return structured
        try:
            return extract_json(text)
        except ValueError:
            raise _ModelFailed(
                Failure(code="plan_unparseable", message="the answer was not JSON"),
                status="unparseable",
            ) from None

    def _ask_text(self, prompt: str, *, trace: TraceIdentifiers) -> str:
        _, text = self._generate(self._request(prompt, trace=trace, contract=None))
        return text

    @staticmethod
    def _failed(
        source_ref: str,
        failed: "_ModelFailed",
        relevant: tuple[str, ...] = (),
        condensed: bool = False,
        cache_hit: bool = False,
    ) -> PlanningOutcome:
        return PlanningOutcome(
            status=failed.status,
            source_ref=source_ref,
            relevant=relevant,
            condensed=condensed,
            cache_hit=cache_hit,
            failure=failed.failure,
        )


class _ModelFailed(Exception):
    def __init__(self, failure: Failure, status: PlanningStatus = "model_failed") -> None:
        self.failure = failure
        self.status = status
        super().__init__(failure.code)
