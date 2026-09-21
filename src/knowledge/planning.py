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
from knowledge.raw import RawDocument, one_line_ending
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
what. Decisions listed as settled are final: never reinstate a rejected claim."""

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
      "content": "the whole page, frontmatter included"}},
    {{"path": "wiki/entities/<Name>.md", "content": "the whole page"}}
  ],
  "index_entries": [{{"section": "Sources|Entities|Concepts|Syntheses",
                      "line": "- [[Page]] — one line."}}],
  "log_body": "- Source: ...\\n- Added ...",
  "contradictions": []
}}

Rules:
- `content` is the complete file, frontmatter included; a page that already
  exists is replaced by what you write, so write the whole page again, never a
  diff.
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

        inventory = self.vault.wiki_pages()
        inventory_text = (
            "\n".join(f"- {path} — {title}" for path, title in inventory) or "(no pages yet)"
        )
        try:
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
            plan = self._plan_from(answer, document)
        except ValidationError as error:
            failure = Failure(code="plan_shape", message=f"{error.error_count()} field errors")
            return self._failed(
                source_ref, _ModelFailed(failure, "unparseable"), relevant, condensed, cache_hit
            )
        plan = ensure_provenance(plan)
        outcome = self.vault.apply(plan)  # a dry run: validation only, nothing written
        return PlanningOutcome(
            status="planned" if outcome.accepted else "invalid",
            source_ref=source_ref,
            plan=plan,
            problems=outcome.problems,
            relevant=relevant,
            condensed=condensed,
            cache_hit=cache_hit,
        )

    def _plan_from(self, answer: JsonValue, document: RawDocument) -> WritePlan:
        """The strict plan. Whether a page is created or updated is a fact the
        vault knows, so it is decided here, never guessed by the model."""
        proposal = IngestProposal.model_validate(answer)
        pages = []
        for item in proposal.pages:
            path = item.get("path")
            action = "update" if isinstance(path, str) and self._exists(path) else "create"
            pages.append(
                PlannedPage.model_validate(
                    {"path": path, "content": item.get("content", ""), "action": action}
                )
            )
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
        )

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
            raise _ModelFailed(
                Failure(
                    code="model_error",
                    message=f"{type(error).__name__}: {error}"[:200].strip()
                    or type(error).__name__,
                    retryable=True,
                )
            ) from error
        if response.failure is not None:
            raise _ModelFailed(response.failure)
        return response.structured_output, response.text

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
