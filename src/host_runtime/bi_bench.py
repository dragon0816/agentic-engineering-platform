"""The benchmark of a BI vault and its push check (BI T1).

`docs/phases/BI_TEST_AND_TOOLS.md` §3.2–§3.3. One run tests what the vault
keeps (`capabilities.bi_cards.vault_checks`):

- every question is asked twice the way a user asks it, through the Agent
  (`ask`), once reading the working database and once the published one, and
  graded by its terms (`knowledge.questions.grade`); a regression is a question
  that passes on published and fails on working;
- every extraction case is read by a trial AI run with the working skills of
  its folder (`extract`) and scored (`capabilities.bi_cards.benchmark`).

The report is saved after every step in `<vault local dir>/benchmarks/<run>.json`
with the digest of the working units it tested. A run may cover one home
(`docs/phases/BI_PAGE_SIMPLE.md` §9) and says what it left out. On push, `gate`
reads the finished runs for exactly the units being pushed and takes each
question's newest verdict, so a smaller run cannot hide what a larger one found;
those regressions block the push. Without such a run the push goes ahead with a
note (a run asks the model for minutes, so a push never starts one).
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from capabilities.bi_cards import (
    ai_runs,
    benchmark,
    domain_reach,
    error_class,
    schema_versions,
    vault,
    vault_checks,
)
from capabilities.bi_cards.ai_runs import AiRuntime
from capabilities.bi_cards.capability import QueryHandler
from capabilities.bi_cards.staging import Staging
from capabilities.bi_cards.store import VAULT_PREFIX, BiStore, BiStoreError
from host_runtime import bi_cards_tools, bi_harness
from knowledge.questions import Question, grade
from knowledge.repo.repository import CheckReport, canonical
from models.contracts import ModelMessage

REPORT_FORMAT = "aep.bi.bench_report/v1"
BENCH_DIR = "benchmarks"
MAX_ANSWER = 4000
Side = Literal["working", "published"]
#: (question text, side) -> {"ok": the turn answered, "answer": its text, "shown": the
#: strings its tools returned, when a trace was kept}.
Ask = Callable[[str, Side], Mapping[str, Any]]
#: (an extraction case) -> the candidates a trial run produced.
Extract = Callable[[Mapping[str, Any]], list[dict[str, Any]]]


def units_digest(units: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical(dict(units)).encode("utf-8")).hexdigest()


def _folder(workspace: Path, vault_id: str) -> Path:
    return vault.local_dir(workspace, vault_id) / BENCH_DIR


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def new_run_id() -> str:
    return f"bibench-{datetime.now(UTC).strftime('%Y%m%dT%H%M%S')}-{uuid.uuid4().hex[:4]}"


def _save(workspace: Path, vault_id: str, report: dict[str, Any]) -> None:
    folder = _folder(workspace, vault_id)
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"{report['run_id']}.json"
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    # The page polls this file; Windows refuses a replace while it is open.
    schema_versions.replace(temporary, target)


#: Tool calls kept per answer in a report; a turn stops well before this many.
MAX_CALLS = 12


def _side(
    question: Question,
    reply: Mapping[str, Any],
    world: Callable[[], error_class.World | None],
) -> dict[str, Any]:
    text = str(reply.get("answer") or "")
    graded = grade(question, text)
    shown = reply.get("shown")
    return {
        "ok": bool(reply.get("ok")),
        "grade": graded.model_dump(mode="json"),
        "answer": text[:MAX_ANSWER],
        # What the model asked and how much came back: why an answer said "no data".
        "calls": list(reply.get("calls") or [])[:MAX_CALLS],
        # Only says where to look; `grade` alone decides pass or fail.
        "errors": []
        if graded.passed
        else error_class.classify(
            missing=graded.missing,
            forbidden=graded.forbidden,
            answered=bool(reply.get("ok")),
            shown=shown,
            world=None if shown is None else world(),
        ),
    }


def _store_of(workspace: Path, vault_id: str, side: Side) -> BiStore:
    dataset = f"{VAULT_PREFIX}{vault_id}"
    if side == "working":
        return BiStore(workspace, dataset, view=vault.local_dir(workspace, vault_id))
    return vault.reading_store(workspace, dataset)


def _world(workspace: Path, vault_id: str, side: Side) -> error_class.World | None:
    """What this side's cards hold and what the vault's sources say. A source with no
    Markdown yet is left out: it then reads as not saying the term, never the reverse."""
    try:
        store = _store_of(workspace, vault_id, side)
        cards = {}
        for row in store.card_rows():
            fields = store.fields(row["id"])
            values = {name: str(field["value"]) for name, field in fields.items()}
            cards[row["id"]] = error_class.Card(
                text=" ".join([row["name"], row["canonical_key"], *values.values()]),
                values=values,
                linked=frozenset(r["other_id"] for r in store.relations(row["id"])),
                evidence=store.evidence(row["id"]),
            )
        staging = Staging(workspace, f"{VAULT_PREFIX}{vault_id}")
        texts = [
            staging.markdown_text(s["id"], int(s["markdown_rev"]))
            for s in staging.sources()
            if s.get("markdown_rev")
        ]
    except (BiStoreError, OSError, sqlite3.Error, KeyError):
        return None  # classes then say unknown, and the run goes on
    return error_class.World(cards=cards, sources="\n".join(texts))


def _finish(report: dict[str, Any]) -> None:
    results = report["results"]
    report["working_score"] = sum(1 for r in results if r["working"]["grade"]["passed"])
    report["published_score"] = sum(1 for r in results if r["published"]["grade"]["passed"])
    report["regressions"] = [
        r["unit"]
        for r in results
        if r["published"]["grade"]["passed"] and not r["working"]["grade"]["passed"]
    ]
    report["error_classes"] = error_class.counts(
        item for r in results for item in r["working"].get("errors") or []
    )
    scored = [c["result"] for c in report["cases"] if c.get("result")]
    report["extract"] = (
        {k: v for k, v in benchmark.summarize(scored).items() if k != "notes"} if scored else None
    )


def run(
    workspace: Path,
    vault_id: str,
    *,
    ask: Ask,
    extract: Extract,
    actor: str,
    run_id: str | None = None,
    home: str | None = None,
) -> dict[str, Any]:
    """Run the vault's questions and cases on its working copy (synchronous): all of them,
    or only `home`'s."""
    units = vault.Vault(workspace, vault_id).repo.working_units()
    every_question = vault_checks.questions(units)
    every_case = vault_checks.cases(units)
    questions = [q for q in every_question if vault_checks.in_scope(home, q["home"])]
    cases = [c for c in every_case if vault_checks.in_scope(home, vault_checks.case_home(c))]
    graded = [q for q in questions if q["must"] or q["must_not"]]
    left = {q["unit"] for q in every_question if q["must"] or q["must_not"]}
    left |= {c["unit"] for c in every_case}
    left -= {q["unit"] for q in graded} | {c["unit"] for c in cases}
    report: dict[str, Any] = {
        "format": REPORT_FORMAT,
        "run_id": run_id or new_run_id(),
        "vault_id": vault_id,
        "status": "running",
        "started_at": _now(),
        "finished_at": None,
        "by": actor,
        "units_sha256": units_digest(units),
        "digests": domain_reach.digests(units, _question_homes(units)),
        "scope": home or "",
        "not_covered": sorted(left),
        "total": len(graded),
        "ungraded": [q["unit"] for q in questions if not (q["must"] or q["must_not"])],
        "results": [],
        "cases": [],
        "error": None,
    }
    _save(workspace, vault_id, report)
    worlds: dict[str, error_class.World | None] = {}

    def world_of(side: Side) -> Callable[[], error_class.World | None]:
        def read() -> error_class.World | None:
            if side not in worlds:
                worlds[side] = _world(workspace, vault_id, side)
            return worlds[side]

        return read

    try:
        for item in graded:
            question = Question(
                set=item["set"],
                path=item["unit"],
                text=item["question"],
                must=tuple(item["must"]),
                must_not=tuple(item["must_not"]),
            )
            result = {"unit": item["unit"], "set": item["set"], "question": item["question"]}
            sides: tuple[Side, Side] = ("working", "published")
            for side in sides:
                result[side] = _side(question, ask(item["question"], side), world_of(side))
            report["results"].append(result)
            _save(workspace, vault_id, report)
        for case in cases:
            entry: dict[str, Any] = {"unit": case["unit"], "slug": case["slug"]}
            try:
                candidates = extract(case)
                entry["result"] = benchmark.score(candidates, case["expected"], text=case["note"])
            except Exception as failure:  # noqa: BLE001 (one case failing is reported)
                entry["error"] = str(failure)[:500] or type(failure).__name__
            report["cases"].append(entry)
            _save(workspace, vault_id, report)
        _finish(report)
        report["status"] = "finished"
    except Exception as failure:  # noqa: BLE001 (the report says what stopped it)
        _finish(report)
        report["status"] = "failed"
        report["error"] = str(failure)[:500] or type(failure).__name__
    report["finished_at"] = _now()
    # Two runs can end within a second, and which came last decides a question's verdict.
    report["finished_ns"] = time.time_ns()
    _save(workspace, vault_id, report)
    return report


def reports(workspace: Path, vault_id: str) -> list[dict[str, Any]]:
    """The vault's runs, newest first."""
    folder = _folder(workspace, vault_id)
    found = []
    for path in folder.glob("*.json") if folder.is_dir() else ():
        try:
            found.append(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            continue
    # Within one second, a run still going is the newer.
    return sorted(
        found,
        key=lambda r: (str(r.get("started_at") or ""), r.get("finished_ns") or float("inf")),
        reverse=True,
    )


def latest(workspace: Path, vault_id: str) -> dict[str, Any] | None:
    found = reports(workspace, vault_id)
    return found[0] if found else None


def _for_home(report: Mapping[str, Any], home: str, units: Mapping[str, Any]) -> dict[str, Any]:
    """A whole-vault report as far as `home` goes, by what its questions and cases belong to
    now, so a question given a domain after the run counts for that domain."""
    own = {q["unit"] for q in vault_checks.questions(units) if q["home"] == home}
    mine = {c["unit"] for c in vault_checks.cases(units) if vault_checks.case_home(c) == home}
    results = [r for r in report.get("results") or [] if r["unit"] in own]
    return {
        **report,
        "scope": home,
        "results": results,
        "cases": [c for c in report.get("cases") or [] if c["unit"] in mine],
        "total": len(results),
        "working_score": sum(1 for r in results if _passed(r, "working")),
        "published_score": sum(1 for r in results if _passed(r, "published")),
        "regressions": [
            r["unit"] for r in results if _passed(r, "published") and not _passed(r, "working")
        ],
        "not_covered": [],
    }


def latest_for(workspace: Path, vault_id: str, home: str | None) -> dict[str, Any] | None:
    """The newest report saying something of `home`: its own run, or a whole-vault run as far
    as it goes. With no home, the newest run of any kind."""
    found = reports(workspace, vault_id)
    if not home:
        return found[0] if found else None
    units = vault.Vault(workspace, vault_id).repo.working_units()
    for report in found:
        if report.get("scope") == home:
            return report
        if not report.get("scope"):
            narrowed = _for_home(report, home, units)
            if narrowed["results"] or narrowed["cases"]:
                return narrowed
    return None


def _question_homes(units: Mapping[str, Any]) -> list[str]:
    return sorted({q["home"] for q in vault_checks.questions(units) if q["home"]})


def gate(workspace: Path, before: Mapping[str, Any], after: Mapping[str, Any]) -> CheckReport:
    """The BI vault push check (`vault.set_benchmark`). A verdict counts while what its
    question's domain stands on is unchanged, so a colleague's push in another domain does not
    void it. A regression blocks a push that touches its domain; one elsewhere is a note
    (`docs/phases/BI_PAGE_SIMPLE.md` §14)."""
    digest = units_digest(after)
    current = domain_reach.digests(after, _question_homes(after))
    runs = [
        r
        for path in sorted((workspace / "bi" / "vaults").glob(f"*/{BENCH_DIR}"))
        for r in reports(workspace, path.parent.name)
        if r.get("status") == "finished"
    ]
    runs.sort(key=lambda r: (str(r.get("finished_at") or ""), r.get("finished_ns") or 0))

    def home_of(unit: str) -> str | None:
        value = after.get(unit)
        home = value.get("home") if isinstance(value, dict) else None
        return str(home) if home else None

    def counts(run_: Mapping[str, Any], unit: str) -> bool:
        if run_.get("units_sha256") == digest:
            return True
        home = home_of(unit)
        return home is not None and (run_.get("digests") or {}).get(home) == current.get(home)

    # Each question's newest verdict that still counts: a run of one home says nothing of
    # another's questions.
    verdicts: dict[str, Any] = {}
    newest = None
    for run_ in runs:
        for item in run_.get("results") or []:
            if counts(run_, item["unit"]):
                verdicts[item["unit"]] = item
                newest = run_
        if run_.get("units_sha256") == digest:
            newest = run_
    if newest is None:
        return CheckReport(
            blocking=[],
            notes=["這次 push 的內容沒有跑過測試（可以先在步驟 3 跑一次再 push）"],
        )
    passed = [_passed(item, "working") for item in verdicts.values()]
    published = [_passed(item, "published") for item in verdicts.values()]
    note = (
        f"測試 {newest.get('run_id')}：{sum(passed)}/{len(passed)} 題通過"
        f"（發佈版本是 {sum(published)}/{len(published)}）"
    )
    graded = {q["unit"] for q in vault_checks.questions(after) if q["must"] or q["must_not"]}
    untested = len(graded - verdicts.keys())
    if untested:
        note += f"；另有 {untested} 題這次的內容沒有測"
    extract = newest.get("extract")
    if extract:
        note += f"；擷取 {extract.get('score')} 分"

    def where(unit: str) -> str:
        home = home_of(unit)
        return f"（{home}）" if home else ""

    reached = domain_reach.touched(before, after)
    blocking: list[str] = []
    elsewhere: list[str] = []
    for unit, item in verdicts.items():
        if _passed(item, "published") and not _passed(item, "working"):
            line = f"測試退步{where(unit)}：「{item['question']}」發佈版本答得對，這次的內容答錯"
            home = home_of(unit)
            mine = "*" in reached or home is None or home in reached
            (blocking if mine else elsewhere).append(line)
    notes = [note, *(f"其他領域，不擋這次 push：{line}" for line in elsewhere)]
    return CheckReport(blocking=blocking, notes=notes)


def _passed(item: Mapping[str, Any], side: Side) -> bool:
    return bool(item[side]["grade"]["passed"])


def standing(workspace: Path, vault_id: str) -> dict[str, list[str]]:
    """What the push check says of the working copy today, for a person to see before
    pressing push: a regression stands in every working domain."""
    target = vault.Vault(workspace, vault_id).repo
    report = gate(workspace, target.units(), target.working_units())
    return {"blocking": list(report.blocking), "notes": list(report.notes)}


# -- how a run asks and extracts in Agent Web ------------------------------------------------

ROLE = (
    "You are answering a benchmark question about the shared BI knowledge base dataset "
    "{dataset}. Use bi__query with dataset {dataset} and answer from what it returns, as you "
    "would answer the person."
)


@dataclass(frozen=True)
class BenchRuntime:
    """What BI work on the Agent harness needs from Agent Web: how a benchmark
    asks a question as the Agent and runs an extraction case, a way to run work
    in the background, and the skill AI's harness turn."""

    ask_for: Callable[[str, str], Ask]  # (vault id, actor) -> Ask
    extract_for: Callable[[str, str], Extract]  # (vault id, actor) -> Extract
    background: Callable[[str, Callable[[], None]], None]
    #: (vault dataset, skill name, actor) -> the skill AI's turn on the harness
    #: (BI T2, `host_runtime.bi_skill_agent`); None: one model call.
    skill_asker_for: Callable[[str, str, str], Any] | None = None
    #: (vault dataset, actor) -> the analysis AI's turn on the harness (BI T3).
    analysis_asker_for: Callable[[str, str], Any] | None = None
    #: (dataset, schema draft id, actor) -> Session A's turn on the harness
    #: (`docs/phases/BI_BUILD_FLOW.md` §5, `host_runtime.bi_schema_agent`).
    schema_asker_for: Callable[[str, str, str], Any] | None = None
    #: (vault dataset, actor) -> the question AI's turn on the harness
    #: (`docs/phases/BI_BUILD_FLOW.md` §7, `host_runtime.bi_questions_agent`).
    questions_asker_for: Callable[[str, str], Any] | None = None


def ask_on(
    gateway: Any,
    workspace: Path,
    dataset: str,
    actor: str,
    namespace: str,
    picked: tuple[BiStore, str],
    question: str,
) -> Mapping[str, Any]:
    """Ask through the Agent harness as a Host sub-run, offering only `bi__query`,
    read for this turn from the store `picked` (with its source note)."""
    handler = QueryHandler(workspace, store_for=lambda d: picked if d == dataset else None)
    tool = bi_cards_tools.reading_tool(gateway, handler)
    if tool is None:
        raise BiStoreError("bi_skill_off", "BI Skill 沒有開啟：到 Capabilities 開啟後再測試")
    result = bi_harness.converse(
        gateway,
        profile="bi-benchmark",
        actor=actor,
        namespace=namespace,
        history=[ModelMessage(role="user", text=question)],
        tools=[tool],
        role=ROLE.format(dataset=dataset),
    )
    outcomes = [
        item.host.data
        for item in result.tools
        if item.name == bi_cards_tools.TOOL_NAME
        and item.host is not None
        and item.host.status == "succeeded"
    ]
    calls = [
        {
            "arguments": item.arguments,
            "status": item.host.status if item.host is not None else "",
            "total": item.host.data.get("total")
            if item.host is not None and isinstance(item.host.data, dict)
            else None,
        }
        for item in result.tools
        if item.name == bi_cards_tools.TOOL_NAME
    ]
    return {
        "ok": result.status == "answered",
        "answer": result.text,
        "shown": list(error_class.walk_strings(outcomes)),
        "calls": calls,
    }


def agent_ask(gateway: Any, workspace: Path, vault_id: str, actor: str, namespace: str) -> Ask:
    """Ask through the Agent harness as a Host sub-run (no memory, no session),
    offering only `bi__query`, read for this turn from the chosen version."""
    dataset = f"{VAULT_PREFIX}{vault_id}"

    def chosen(side: Side) -> tuple[BiStore, str]:
        if side == "working":
            view = _store_of(workspace, vault_id, side)
            return view, "內容來自這台電腦的工作版本（還沒 push 的改動也在內）"
        reads = vault.Vault(workspace, vault_id).reads()
        note = f"內容來自發佈版本 {reads['tag']}" if reads["tag"] else "內容來自已 push 的最新版本"
        return _store_of(workspace, vault_id, side), note

    def ask(question: str, side: Side) -> Mapping[str, Any]:
        return ask_on(gateway, workspace, dataset, actor, namespace, chosen(side), question)

    return ask


def trial_candidates(
    workspace: Path,
    dataset: str,
    actor: str,
    ai: AiRuntime,
    *,
    name: str,
    text: str,
    folder: Any,
    types: Any,
    skill_draft: Any = None,
) -> list[dict[str, Any]]:
    """Read `text` the way ingest reads a source: add it as a source of the
    dataset and run a trial (nothing is written to cards) with the working
    skills of `folder`, or `skill_draft` in place of one (BI T2); the
    candidates come back. `ai` runs the work at once."""
    from host_runtime import bi_cards_api

    status, payload = bi_cards_api.route(
        workspace,
        actor,
        "POST",
        "/api/bi/sources",
        {},
        {"dataset": dataset, "name": name, "text": text},
        None,
        ai,
    )
    if status != 200:
        raise BiStoreError(str(payload.get("code")), str(payload.get("message")))
    run = ai_runs.start(
        workspace,
        dataset,
        ai,
        kind="trial",
        source_id=payload["source"]["id"],
        instructions=None,
        types=types or None,
        actor=actor,
        folder=folder or None,
        skill_draft=skill_draft,
    )
    staging = Staging(workspace, dataset)
    row = staging.run_row(run["id"]) or {}
    if row.get("status") == "failed":
        raise BiStoreError("run_failed", str(row.get("error") or "試跑失敗"))
    return list(staging.candidates(run["id"]))


def trial_extract(workspace: Path, vault_id: str, actor: str, ai: AiRuntime) -> Extract:
    """An extraction case read by a trial run with the working skills."""
    dataset = f"{VAULT_PREFIX}{vault_id}"
    now = AiRuntime(model=ai.model, background=lambda _title, work: work(), approved=ai.approved)

    def extract(case: Mapping[str, Any]) -> list[dict[str, Any]]:
        return trial_candidates(
            workspace,
            dataset,
            actor,
            now,
            name=f"{case['slug']}.md",
            text=case["note"],
            folder=case.get("folder"),
            types=case["expected"].get("types"),
        )

    return extract
