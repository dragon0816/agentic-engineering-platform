"""Sandbox benchmark: the scope's question sets, sandbox against project vault (C3).

`docs/phases/KNOWLEDGE_COLLAB.md` section 5. Each question is asked through the
same Knowledge Harness as the Agent, once against the sandbox and once against
the project vault as it is now; neither is installed or written to host.json.
Answers are graded by the question's must-mention / must-not-say terms. A
regression is a question that passes on the project vault and fails in the
sandbox; the push gate (C4) reads the saved result.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from common.assets import AssetIdentity, AssetMetadata, BusinessApproval, Owner
from common.base import Contract
from host_runtime.contracts import KnowledgeAskRequest
from knowledge.evolution import (
    KnowledgeCatalog,
    KnowledgeManifest,
    decision_digest,
    knowledge_digest,
    raw_digest,
)
from knowledge.questions import Grade, Question, grade, load
from knowledge.vault import Vault

RESULTS = ".benchmarks"
Ask = Callable[[KnowledgeAskRequest, KnowledgeCatalog], dict[str, Any]]


class SideResult(Contract):
    ok: bool  # the Harness validated an answer
    grade: Grade
    answer: str = ""


class QuestionResult(Contract):
    path: str
    set: str
    question: str
    sandbox: SideResult
    project: SideResult

    @property
    def regression(self) -> bool:
        return self.project.grade.passed and not self.sandbox.grade.passed


class BenchmarkReport(Contract):
    run_id: str
    sandbox_id: str
    sets: tuple[str, ...]
    status: Literal["running", "finished", "failed"] = "running"
    started_at: str
    finished_at: str | None = None
    total: int = 0
    results: tuple[QuestionResult, ...] = ()
    ungraded: tuple[str, ...] = ()  # questions with no must / must-not terms
    error: str | None = None

    @property
    def sandbox_score(self) -> int:
        return sum(1 for r in self.results if r.sandbox.grade.passed)

    @property
    def project_score(self) -> int:
        return sum(1 for r in self.results if r.project.grade.passed)

    @property
    def regressions(self) -> tuple[str, ...]:
        return tuple(r.path for r in self.results if r.regression)

    def summary(self) -> dict[str, Any]:
        return {**json.loads(self.model_dump_json()), "sandbox_score": self.sandbox_score,
                "project_score": self.project_score, "regressions": list(self.regressions)}


def catalog_for(vault: Vault, asset: AssetIdentity, actor: str) -> KnowledgeCatalog:
    """A one-version catalog over a vault that is not installed."""
    manifest = KnowledgeManifest(
        metadata=AssetMetadata(
            identity=asset, owner=Owner(type="user", id=actor), visibility="private",
            lifecycle="published",
            business_approval=BusinessApproval(status="approved", reviewer=actor,
                                               evidence="sandbox-benchmark"),
            validation_refs=("sandbox-benchmark",)),
        domain=asset.namespace, vault_ref=str(vault.root.resolve()),
        raw_sha256=raw_digest(vault), decisions_sha256=decision_digest(vault),
        content_sha256=knowledge_digest(vault))
    catalog = KnowledgeCatalog()
    catalog.register(manifest, vault)
    return catalog


def questions_for(sandbox: Vault, fallback: Path | None,
                  sets: tuple[str, ...]) -> tuple[tuple[Question, ...], tuple[str, ...]]:
    """(gradable questions, ungraded paths) of the chosen sets; the sandbox's own
    checks/questions first, so a maintainer can edit questions with the rules."""
    root = sandbox.root / "checks" / "questions"
    found = load(root if root.is_dir() or fallback is None else fallback)
    chosen = [q for q in found if q.set in sets]
    return (tuple(q for q in chosen if q.must or q.must_not),
            tuple(q.path for q in chosen if not (q.must or q.must_not)))


def run_benchmark(
    ask: Ask, *, sandbox_id: str, sandbox: Vault, project: Vault, sets: tuple[str, ...],
    actor: str, skill: AssetIdentity | None, questions_fallback: Path | None = None,
    run_id: str | None = None,
) -> BenchmarkReport:
    """Run synchronously, saving the report after every question in
    `<sandbox>/.benchmarks/<run id>.json` so a page can follow it."""
    run = run_id or f"bench-{datetime.now(UTC).strftime('%Y%m%dT%H%M%S')}-{uuid.uuid4().hex[:4]}"
    questions, ungraded = questions_for(sandbox, questions_fallback, sets)
    report = BenchmarkReport(run_id=run, sandbox_id=sandbox_id, sets=sets,
                             started_at=datetime.now(UTC).isoformat(timespec="seconds"),
                             total=len(questions), ungraded=ungraded)
    folder = sandbox.root / RESULTS
    folder.mkdir(exist_ok=True)
    path = folder / f"{run}.json"

    def save(current: BenchmarkReport) -> None:
        path.write_text(json.dumps(current.summary(), ensure_ascii=False, indent=1),
                        encoding="utf-8")

    save(report)
    try:
        sides = {
            "sandbox": (AssetIdentity(namespace="engineering", name="sandbox",
                                      version="0.0.0-candidate"), sandbox),
            "project": (AssetIdentity(namespace="engineering", name="project",
                                      version="0.0.0-current"), project),
        }
        catalogs = {name: (asset, catalog_for(vault, asset, actor))
                    for name, (asset, vault) in sides.items()}

        def answer(name: str, question: Question) -> SideResult:
            asset, catalog = catalogs[name]
            reply = ask(KnowledgeAskRequest(asset=asset, question=question.text, skill=skill),
                        catalog)
            text = str(reply.get("answer") or "")
            return SideResult(ok=bool(reply.get("ok")), grade=grade(question, text),
                              answer=text[:4000])

        results: list[QuestionResult] = []
        with ThreadPoolExecutor(max_workers=2) as pool:
            for question in questions:
                mine, theirs = (pool.submit(answer, "sandbox", question),
                                pool.submit(answer, "project", question))
                results.append(QuestionResult(path=question.path, set=question.set,
                                              question=question.text, sandbox=mine.result(),
                                              project=theirs.result()))
                report = report.model_copy(update={"results": tuple(results)})
                save(report)
        report = report.model_copy(update={
            "status": "finished", "finished_at": datetime.now(UTC).isoformat(timespec="seconds")})
    except Exception as failure:  # noqa: BLE001 - the page shows why a run stopped
        report = report.model_copy(update={"status": "failed", "error": type(failure).__name__})
    save(report)
    return report


def latest(sandbox: Vault) -> dict[str, Any] | None:
    folder = sandbox.root / RESULTS
    runs = sorted(folder.glob("bench-*.json")) if folder.is_dir() else []
    if not runs:
        return None
    loaded: dict[str, Any] = json.loads(runs[-1].read_text(encoding="utf-8"))
    return loaded
