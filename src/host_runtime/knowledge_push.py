"""Push a sandbox into its project vault (collaboration C4, owner 2026-10-11).

`docs/phases/KNOWLEDGE_COLLAB.md` section 6. No lock: the first push wins.

1. Merge three ways (where the sandbox started, the sandbox, the project vault
   now) into a candidate; an open conflict stops here.
2. Gate: the chosen question sets on the candidate and on the project vault.
   A regression blocks (owner); so does a candidate scoring lower.
3. Compare and write: if the project vault changed since step 1, start again
   (someone else pushed first); otherwise copy the merged files in place, each
   replaced file backed up first.
4. Record who pushed, from which sandbox, what changed, the benchmark and the
   backup, in `pushes/<push id>.json` and a `log.md` entry.

Each step is saved in `<sandbox>/.push/<push id>.json` so a page can follow it.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from common.assets import AssetIdentity
from common.base import Contract
from host_runtime.knowledge_bench import Ask, BenchmarkReport, run_benchmark
from knowledge.evolution import knowledge_digest
from knowledge.merge import Resolution
from knowledge.pipeline import KnowledgePipeline, PipelineError
from knowledge.vault import Vault

PUSH_STATE = ".push"
PUSHES = "pushes"
MAX_ATTEMPTS = 3

PushStatus = Literal["merging", "benchmarking", "writing", "pushed", "blocked", "conflicts",
                     "moved", "refused", "failed"]


class PushReport(Contract):
    push_id: str
    sandbox_id: str
    base: str
    actor: str
    status: PushStatus = "merging"
    started_at: str
    finished_at: str | None = None
    attempts: int = 0
    reason: str | None = None
    sets: tuple[str, ...] = ()
    candidate_root: str | None = None
    written: tuple[str, ...] = ()
    proposals: tuple[str, ...] = ()
    conflicts: tuple[str, ...] = ()
    resolutions: dict[str, str] = {}
    benchmark: dict[str, object] | None = None
    lost_sourced_lines: int = 0
    lint_worse: dict[str, int] = {}
    backup: str | None = None


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def gate(report: BenchmarkReport) -> str | None:
    """Why the benchmark blocks the push, or None when it may go ahead."""
    if report.status != "finished":
        return f"benchmark {report.status}"
    if report.regressions:
        return "regression: " + ", ".join(report.regressions)
    if report.sandbox_score < report.project_score:
        return f"score {report.sandbox_score} is below the project vault's {report.project_score}"
    return None


def run_push(pipeline: KnowledgePipeline, ask: Ask, *, sandbox_id: str, actor: str,
             sets: tuple[str, ...], resolutions: dict[str, Resolution] | None = None,
             skill: AssetIdentity | None = None, push_id: str | None = None,
             questions_fallback: Path | None = None) -> PushReport:
    info, sandbox = pipeline.sandboxes.open(sandbox_id)
    project = Vault(pipeline.bases[info.base_name])
    pid = push_id or f"push-{datetime.now(UTC).strftime('%Y%m%dT%H%M%S')}-{uuid.uuid4().hex[:4]}"
    report = PushReport(push_id=pid, sandbox_id=sandbox_id, base=info.base_name, actor=actor,
                        started_at=_now(), sets=sets, resolutions=dict(resolutions or {}))
    folder = sandbox.root / PUSH_STATE
    folder.mkdir(exist_ok=True)

    def save(current: PushReport, **changes: object) -> PushReport:
        updated = current.model_copy(update=changes)
        (folder / f"{pid}.json").write_text(updated.model_dump_json(indent=1), encoding="utf-8")
        return updated

    report = save(report)
    if not pipeline.may_push(info.base_name, actor):
        return save(report, status="refused", reason="not a maintainer", finished_at=_now())
    try:
        for attempt in range(1, MAX_ATTEMPTS + 1):
            report = save(report, status="merging", attempts=attempt)
            before = knowledge_digest(project)
            try:
                merged = pipeline.merge(sandbox_id, "apply", dict(resolutions or {}))
            except PipelineError as error:
                if error.code != "unresolved_conflicts":
                    raise
                preview = pipeline.merge(sandbox_id, "dry_run", dict(resolutions or {}))
                return save(report, status="conflicts", finished_at=_now(),
                            conflicts=tuple(c.key for c in preview.conflicts),
                            reason="resolve the conflicts on the Knowledge page")
            report = save(report, status="benchmarking", candidate_root=merged.candidate_root,
                          written=merged.written,
                          proposals=tuple(c.path for c in merged.changes if c.proposal),
                          lost_sourced_lines=merged.lost_sourced_lines,
                          lint_worse=merged.lint_worse)
            assert merged.candidate_root is not None
            candidate = Vault(Path(merged.candidate_root))
            bench = run_benchmark(ask, sandbox_id=sandbox_id, sandbox=candidate,
                                  project=project, sets=sets, actor=actor, skill=skill,
                                  questions_fallback=questions_fallback,
                                  run_id=f"bench-{pid}-{attempt}")
            report = save(report, benchmark=bench.summary())
            blocked = gate(bench)
            if blocked:
                return save(report, status="blocked", reason=blocked, finished_at=_now())
            if merged.lost_sourced_lines:
                return save(report, status="blocked", finished_at=_now(),
                            reason=f"{merged.lost_sourced_lines} sourced lines would be lost")
            if knowledge_digest(project) != before:
                continue  # someone pushed first: merge and measure again
            report = save(report, status="writing")
            backup = pipeline.write_push(info.base_name, merged.candidate_root, merged.written, pid)
            report = save(report, status="pushed", backup=backup, finished_at=_now())
            _record(project, report, info.label)
            pipeline.sync_after_push(sandbox_id)
            return report
        return save(report, status="moved", finished_at=_now(),
                    reason="the project vault kept changing; try again")
    except Exception as failure:  # noqa: BLE001 - the page shows why a push stopped
        code = getattr(failure, "code", None) or type(failure).__name__
        return save(report, status="failed", reason=str(code), finished_at=_now())


def _record(project: Vault, report: PushReport, label: str) -> None:
    folder = project.root / PUSHES
    folder.mkdir(exist_ok=True)
    (folder / f"{report.push_id}.json").write_text(report.model_dump_json(indent=1),
                                                    encoding="utf-8")
    bench = report.benchmark or {}
    entry = (f"\n## [{report.started_at[:10]}] push | {label}\n"
             f"- By {report.actor} from sandbox {report.sandbox_id}; {len(report.written)} files; "
             f"benchmark {bench.get('sandbox_score', 0)}/{bench.get('total', 0)} "
             f"(project vault {bench.get('project_score', 0)}).\n"
             f"- Record: {PUSHES}/{report.push_id}.json; backup: "
             f".ingest-backup/{report.push_id}/\n")
    log = project.root / "log.md"
    existing = log.read_bytes().decode("utf-8") if log.is_file() else "# Log\n"
    newline = "\r\n" if "\r\n" in existing else "\n"
    log.write_bytes((existing.rstrip() + "\n" + entry).replace("\r\n", "\n")
                    .replace("\n", newline).encode("utf-8"))


def latest_push(sandbox: Vault) -> dict[str, object] | None:
    folder = sandbox.root / PUSH_STATE
    runs = sorted(folder.glob("push-*.json")) if folder.is_dir() else []
    if not runs:
        return None
    loaded: dict[str, object] = json.loads(runs[-1].read_text(encoding="utf-8"))
    return loaded
