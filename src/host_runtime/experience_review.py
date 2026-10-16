"""The experience review: groups of cases diagnosed into proposals (E2, report only).

`docs/phases/EXPERIENCE_REVIEW.md` section 4. For each group of open cases the
company model gets the cases and the rules that governed them, and returns a
cause, a diagnosis citing the cases and a proposal. E2 only reports: proposals
are saved under `<workspace>/experience-reviews/` and shown on Agent Web;
nothing is changed. Test questions it drafts leave the expected terms blank,
because a model must not invent what an answer should contain.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import ValidationError

from common.base import Contract
from common.execution import TraceIdentifiers
from host_runtime.experience import ExperienceCase, ExperienceStore, group
from host_runtime.skill_suggestions import SuggestionCounts, SuggestionItem, SuggestionPass
from models.contracts import ModelClient, ModelMessage, ModelRequest, ModelRequirements

REVIEWS_DIR = "experience-reviews"
MAX_GROUPS = 10
MAX_CASES_PER_GROUP = 8
RULE_CHARS = 8000

Cause = Literal[
    "rule_missing",
    "rule_unclear",
    "retrieval_missed",
    "data_missing",
    "model_error",
    "harness_defect",
]

PROMPT = """You review failures of a company AI assistant to propose improvements.
You get a group of similar failed cases (question, answer excerpt, failure code,
the user's rating note) and the rules that governed them. Reply with one JSON object:
{"cause": one of rule_missing | rule_unclear | retrieval_missed | data_missing |
 model_error | harness_defect,
 "diagnosis": "two or three sentences citing cases by number, e.g. (case 2)",
 "proposal": {"kind": one of rule_edit | knowledge_gap | test_question | issue,
              "target": "the rule file or area it concerns",
              "text": "for rule_edit: the rule text to add or change, written as a rule
                       with its reason; for knowledge_gap: what knowledge is missing and
                       which category folder should receive it; for test_question: the
                       question only; for issue: what looks wrong"},
 "confidence": "low | medium | high",
 "confirm": "what would confirm this diagnosis"}
Rules: base everything on the cases; never state product facts from your own
knowledge; if the cases do not support a diagnosis, say so with low confidence."""


class Proposal(Contract):
    kind: Literal["rule_edit", "knowledge_gap", "test_question", "issue"]
    target: str = ""
    text: str = ""


class Finding(Contract):
    group: str
    case_ids: tuple[str, ...]
    cases: int
    cause: Cause | None = None
    diagnosis: str = ""
    proposal: Proposal | None = None
    confidence: str = ""
    confirm: str = ""
    error: str | None = None


class ReviewReport(Contract):
    review_id: str
    started_at: str
    finished_at: str | None = None
    harvested: int = 0
    open_cases: int = 0
    findings: tuple[Finding, ...] = ()
    skipped_groups: int = 0
    # Suggested Skills (SKILL_SUGGESTIONS S1): what was considered,
    # qualified and dropped with the reason; counts beside it.
    suggestions: tuple[SuggestionItem, ...] = ()
    suggestion_counts: SuggestionCounts | None = None

    def markdown(self) -> str:
        lines = [
            f"# Experience review {self.review_id}",
            "",
            f"{self.started_at}: {self.harvested} new cases, {self.open_cases} open, "
            f"{len(self.findings)} groups reviewed"
            + (f", {self.skipped_groups} left for the next run" if self.skipped_groups else "")
            + ".",
            "",
        ]
        for number, item in enumerate(self.findings, 1):
            lines.append(f"## {number}. {item.group} ({item.cases} cases)")
            if item.error:
                lines += ["", f"Not reviewed: {item.error}", ""]
                continue
            lines += [
                "",
                f"- Cause: **{item.cause}** (confidence {item.confidence})",
                f"- Diagnosis: {item.diagnosis}",
            ]
            if item.proposal is not None:
                lines.append(
                    f"- Proposal ({item.proposal.kind}, {item.proposal.target}): "
                    f"{item.proposal.text}"
                )
            lines += [f"- Would confirm it: {item.confirm}", ""]
        if self.suggestion_counts is not None:
            lines.append(
                SuggestionPass(counts=self.suggestion_counts, suggestions=self.suggestions)
                .markdown()
                .rstrip("\n")
            )
        return "\n".join(lines) + "\n"


Rules = Callable[[str], str]  # domain -> the governing rule text


def _case_text(number: int, case: ExperienceCase) -> str:
    head = f"{case.signal}, {case.failure_code or '-'}, {case.created_at[:10]}"
    return (
        f"### case {number} ({head})\n"
        f"Question: {case.subject}\nAnswer excerpt: {case.answer[:800]}\n"
        + (f"Rating note: {case.rating_note}\n" if case.rating_note else "")
    )


def structured_call(
    model: ModelClient,
    alias: str,
    *,
    system: str,
    user: str,
    trace: TraceIdentifiers,
    output_contract: str,
    max_output_tokens: int = 3000,
) -> Any:
    """One structured call to the company model; the reply's JSON value. A
    model failure is raised as `RuntimeError(code)`, unreadable text as
    `ValueError`. Shared by the failure review and the Skill suggestions."""
    response = model.generate(
        ModelRequest(
            trace=trace,
            model_alias=alias,
            messages=(
                ModelMessage(role="system", text=system),
                ModelMessage(role="user", text=user),
            ),
            requirements=ModelRequirements(structured_output=True),
            output_contract=output_contract,
            max_output_tokens=max_output_tokens,
        )
    )
    if response.failure is not None:
        raise RuntimeError(response.failure.code)
    data = response.structured_output
    if not isinstance(data, dict):
        data = json.loads(response.text or "")
    return data


def _ask(
    model: ModelClient, alias: str, cases: list[ExperienceCase], rules: str, trace: TraceIdentifiers
) -> dict[str, Any]:
    shown = "\n".join(_case_text(n, c) for n, c in enumerate(cases, 1))
    data = structured_call(
        model,
        alias,
        system=PROMPT,
        user=f"===== rules in force =====\n"
        f"{rules[:RULE_CHARS] or '(none)'}\n\n"
        f"===== cases =====\n{shown}",
        trace=trace,
        output_contract="experience_review_finding",
    )
    if not isinstance(data, dict):
        raise ValueError("the reply is not a JSON object")
    return dict(data)


def run_review(
    store: ExperienceStore,
    model: ModelClient,
    alias: str,
    rules: Rules,
    *,
    workspace: Path,
    harvested: int = 0,
    max_groups: int = MAX_GROUPS,
    suggestions: SuggestionPass | None = None,
) -> ReviewReport:
    review_id = f"review-{datetime.now(UTC).strftime('%Y%m%dT%H%M%S')}-{uuid.uuid4().hex[:4]}"
    open_cases = store.cases("open")
    groups = list(group(open_cases).items())
    findings = []
    for number, (key, cases) in enumerate(groups[:max_groups], 1):
        shown = cases[-MAX_CASES_PER_GROUP:]
        finding = Finding(group=key, case_ids=tuple(c.case_id for c in cases), cases=len(cases))
        try:
            data = _ask(
                model,
                alias,
                shown,
                rules(cases[0].domain),
                TraceIdentifiers(
                    trace_id=review_id, request_id=f"group-{number}", span_id="review"
                ),
            )
            finding = finding.model_copy(
                update={
                    "cause": data.get("cause"),
                    "diagnosis": str(data.get("diagnosis") or ""),
                    "proposal": Proposal.model_validate(data["proposal"])
                    if isinstance(data.get("proposal"), dict)
                    else None,
                    "confidence": str(data.get("confidence") or ""),
                    "confirm": str(data.get("confirm") or ""),
                }
            )
            finding = Finding.model_validate(finding.model_dump())
            store.mark_reviewed(finding.case_ids, review_id)
        except (RuntimeError, ValueError, ValidationError, KeyError) as error:
            finding = finding.model_copy(
                update={
                    "cause": None,
                    "proposal": None,
                    "error": type(error).__name__ + ": " + str(error)[:120],
                }
            )
        findings.append(finding)
    report = ReviewReport(
        review_id=review_id,
        started_at=datetime.now(UTC).isoformat(timespec="seconds"),
        harvested=harvested,
        open_cases=len(open_cases),
        findings=tuple(findings),
        skipped_groups=max(0, len(groups) - max_groups),
        suggestions=suggestions.suggestions if suggestions is not None else (),
        suggestion_counts=suggestions.counts if suggestions is not None else None,
        finished_at=datetime.now(UTC).isoformat(timespec="seconds"),
    )
    folder = workspace / REVIEWS_DIR
    folder.mkdir(exist_ok=True)
    (folder / f"{review_id}.json").write_text(report.model_dump_json(indent=1), encoding="utf-8")
    (folder / f"{review_id}.md").write_text(report.markdown(), encoding="utf-8")
    return report


def review_model(runtime: Any) -> tuple[ModelClient, str] | None:
    """The company model and alias the review asks: the installed Knowledge
    capability's, as the review always used. None when there is none."""
    from capabilities.knowledge_query.handlers import KNOWLEDGE_QUERY_SPEC

    installed = runtime.agent.gateway.bridge.installed.get(KNOWLEDGE_QUERY_SPEC.identity)
    handler = getattr(installed, "handler", None)
    model, alias = getattr(handler, "model", None), getattr(handler, "alias", None)
    if model is None or alias is None:
        return None
    return model, str(alias)


def latest_review(workspace: Path) -> dict[str, Any] | None:
    folder = workspace / REVIEWS_DIR
    runs = sorted(folder.glob("review-*.json")) if folder.is_dir() else []
    if not runs:
        return None
    loaded: dict[str, Any] = json.loads(runs[-1].read_text(encoding="utf-8"))
    markdown = runs[-1].with_suffix(".md")
    loaded["markdown"] = (
        markdown.read_text(encoding="utf-8")
        if markdown.is_file()
        else ReviewReport.model_validate(loaded).markdown()
    )
    return loaded
