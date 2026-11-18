"""The benchmark of a wiki repository and its push check (knowledge repositories R4a).

`docs/phases/KNOWLEDGE_REPO.md` §13 item 3; decision "The benchmark of a wiki
repository" (2026-10-31). The question sets are asked through the Knowledge
Harness against the working folder (`wiki_work`) and against the pushed head,
as the sandbox benchmark did against the project vault (`knowledge_bench`).
A run records the digest of the pages it tested. On push, `gate` finds the
newest finished run for exactly the pages being pushed: its regressions block
the push; without such a run the push goes ahead with a note that it was not
tested (a run asks the model for minutes, so it is never started by a push).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from aep_wiki.host.knowledge_bench import RESULTS, Ask, BenchmarkReport, run_benchmark
from aep_wiki.knowledge import wiki_work
from common.assets import AssetIdentity
from knowledge import wiki_repos
from knowledge.repo import wiki
from knowledge.repo.repository import CheckReport, canonical, local_root
from knowledge.vault import Vault

HEAD_VIEW = "head"


def pages_digest(pages: Mapping[str, str]) -> str:
    return hashlib.sha256(canonical(dict(pages)).encode("utf-8")).hexdigest()


def run(
    workspace: Path,
    repo_id: str,
    ask: Ask,
    *,
    sets: tuple[str, ...],
    actor: str,
    skill: AssetIdentity | None = None,
    questions_fallback: Path | None = None,
    run_id: str | None = None,
) -> BenchmarkReport:
    """Ask the question sets of the working folder (captured first) and of the
    pushed head; the report is saved in the working folder's `.benchmarks/`."""
    repo = wiki_repos.repository(workspace, repo_id)
    folder = wiki_work.open_work(repo)
    wiki_work.capture(repo)
    folder = wiki_work.open_work(repo)
    head = repo.local / wiki_work.WORK_VIEW / HEAD_VIEW
    wiki.materialize(repo.units(), head, repo_folder=repo.folder)
    return run_benchmark(
        ask,
        sandbox_id=repo_id,
        sandbox=Vault(folder),
        project=Vault(head),
        sets=sets,
        actor=actor,
        skill=skill,
        questions_fallback=questions_fallback,
        run_id=run_id,
        pages_sha256=pages_digest(wiki.pages(repo.working_units())),
    )


def _reports(workspace: Path) -> list[dict[str, Any]]:
    found = []
    pattern = f"*/{wiki_work.WORK_VIEW}/{wiki_work.VIEW}/{RESULTS}/bench-*.json"
    for path in local_root(workspace).glob(pattern):
        try:
            found.append(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            continue
    return found


def gate(workspace: Path, before: Mapping[str, str], after: Mapping[str, str]) -> CheckReport:
    """The wiki push check (`wiki.set_benchmark`)."""
    del before  # a run compared against the head it was started from
    digest = pages_digest(after)
    runs = [
        r
        for r in _reports(workspace)
        if r.get("pages_sha256") == digest and r.get("status") == "finished"
    ]
    if not runs:
        return CheckReport(
            blocking=[], notes=["這次 push 的內容沒有跑過測試（可以先在「測試」跑一次再 push）"]
        )
    newest = max(runs, key=lambda r: str(r.get("finished_at") or ""))
    regressions = list(newest.get("regressions") or [])
    note = (
        f"測試 {newest.get('run_id')}：{newest.get('sandbox_score')}/{newest.get('total')} 題通過"
        f"（push 前是 {newest.get('project_score')}/{newest.get('total')}）"
    )
    blocking = [f"測試退步：{path} 在 push 前答得對，現在答錯" for path in regressions]
    return CheckReport(blocking=blocking, notes=[note])
