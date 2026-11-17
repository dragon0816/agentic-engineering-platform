"""Run or score the BI ingest benchmark (BI ingest phase 7, §11 item 10).

Two commands, both writing a Markdown report under
`<workspace>/bi/benchmarks/` and never writing a card:

  run    Uploads every fictional note of the benchmark as an UNCLASSIFIED
         source of the dataset, starts a **trial** run of each on the AI path
         with the host's Knowledge model (the same `staging` / `ai_runs`
         functions the API uses; a trial can never be committed), waits for
         it, scores the candidates and writes the report.

           python scripts/bi_ingest_benchmark.py run --config <host config.json>
               --dataset <name> [--workspace <dir>] [--instructions-file <txt>]

         The model is the config's `models.routing_alias` (the model Agent Web
         uses for Knowledge), built with the config's credential mapping from
         environment variables and wrapped in the config's data approval. The
         data approval must include UNCLASSIFIED.

  score  Scores runs that already exist (for example trial runs started by
         hand in Agent Web, 「建立與匯入」 step 3), by note and run id:

           python scripts/bi_ingest_benchmark.py score --workspace <dir>
               --dataset <name> --run 01_robot_tsn_meeting.md=<run id> ...

Run with `PYTHONPATH=src` and `feature_plugins/bi_knowledge/python` from the
repository root (or an installed AEP).
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from aep_bi.cards import ai_runs, benchmark, runs
from aep_bi.cards.staging import Staging
from aep_bi.cards.store import BiStore, BiStoreError

FIXTURE = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "bi_ingest_benchmark"
ACTOR = "bi-benchmark"
REPORT_DIR = ("bi", "benchmarks")


def model_runtime(config_path: Path) -> tuple[ai_runs.AiRuntime, str, Path]:
    """The Knowledge model of a host config as an AI runtime whose background
    work runs at once (so a run has ended when `start` returns), with the
    model alias and the config's workspace."""
    from common.execution import Failure
    from host_runtime.contracts import CompanyHostConfiguration
    from models.approved import ApprovedModelClient
    from models.clients import ModelClients
    from models.credentials import EnvironmentCredentials

    config = CompanyHostConfiguration.model_validate_json(
        config_path.read_text(encoding="utf-8-sig")
    )
    binding = config.models
    if binding is None or binding.routing_alias is None:
        raise SystemExit("the host config has no model (models.routing_alias)")
    clients = ModelClients(
        binding.catalog,
        resolver=EnvironmentCredentials(config.credential_environment()),
        options=binding.options,
    )
    client = clients.for_alias(binding.routing_alias)
    if isinstance(client, Failure):
        raise SystemExit(f"the model could not be built: {client.code}")
    model = ApprovedModelClient(client, binding.data_approval)
    approval = binding.data_approval
    approved = () if approval is None else tuple(approval.approved_classes)
    pair = (model, str(binding.routing_alias))
    runtime = ai_runs.AiRuntime(
        model=lambda: pair,
        background=lambda title, work: work(),
        approved=lambda: approved,
    )
    return runtime, str(binding.routing_alias), Path(str(config.workspace_root))


def _cards_digest(workspace: Path, dataset: str) -> str:
    path = BiStore(workspace, dataset).dir / "bi.sqlite"
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else "(none)"


def run_benchmark(
    workspace: Path,
    dataset: str,
    ai: ai_runs.AiRuntime,
    *,
    fixture: Path = FIXTURE,
    instructions: str | None = None,
    wait: Callable[[], None] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Upload, trial-run and score every note; (summary, one row per note).
    `wait` runs pending background work when `ai` defers it (tests)."""
    staging = Staging(workspace, dataset)
    started: list[tuple[benchmark.Case, str | None, str | None]] = []
    for case in benchmark.load_cases(fixture):
        try:
            source = staging.add_source(
                case.note, text=case.text, classification="UNCLASSIFIED", actor=ACTOR
            )
            run = ai_runs.start(
                workspace,
                dataset,
                ai,
                kind="trial",
                source_id=str(source["id"]),
                instructions=instructions,
                types=case.expected.get("types"),
                actor=ACTOR,
            )
            started.append((case, str(run["id"]), None))
        except BiStoreError as error:
            started.append((case, None, f"{error.code}: {error.message}"))
    if wait is not None:
        wait()
    return _score(workspace, dataset, started)


def score_runs(
    workspace: Path, dataset: str, chosen: dict[str, str], *, fixture: Path = FIXTURE
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Score existing runs given as {note file name: run id}."""
    started: list[tuple[benchmark.Case, str | None, str | None]] = []
    for case in benchmark.load_cases(fixture):
        if case.note in chosen:
            started.append((case, chosen[case.note], None))
    unknown = sorted(set(chosen) - {case.note for case, _, _ in started})
    if unknown:
        raise SystemExit(f"not a benchmark note: {', '.join(unknown)}")
    return _score(workspace, dataset, started)


def _score(
    workspace: Path,
    dataset: str,
    started: Sequence[tuple[benchmark.Case, str | None, str | None]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    results, rows = [], []
    for case, run_id, error in started:
        candidates: list[dict[str, Any]] = []
        row: dict[str, Any] = {"note": case.note, "run": run_id, "status": None, "error": error}
        if run_id is not None:
            try:
                detail = runs.run_detail(workspace, dataset, run_id)
            except BiStoreError as failure:
                row["error"] = f"{failure.code}: {failure.message}"
            else:
                run = detail["run"]
                candidates = list(detail["candidates"])
                row.update(
                    status=run["status"],
                    kind=run["kind"],
                    model=run.get("model"),
                    failures=len(run.get("failures") or []),
                )
        results.append(benchmark.score(candidates, case.expected, text=case.text))
        rows.append(row)
    return benchmark.summarize(results), rows


def write_report(
    workspace: Path,
    dataset: str,
    summary: dict[str, Any],
    rows: Sequence[dict[str, Any]],
    *,
    mode: str,
    model: str | None,
    digests: tuple[str, str],
) -> Path:
    at = datetime.now(UTC).replace(microsecond=0)
    preface = [
        f"- 時間：{at.isoformat()}",
        f"- 資料集：{dataset}",
        f"- 模型：{model or '（評分既有的執行，模型見各執行）'}",
        f"- 方式：{mode}",
        "- 自動化的部分："
        + (
            f"上傳 {len(rows)} 份虛構筆記（UNCLASSIFIED）、用 AI 判讀試跑（trial，不能寫入卡片）、"
            "等待完成、評分、寫這份報告。"
            if mode == "run"
            else "讀取指定的既有執行、評分、寫這份報告；試跑本身是人工在 Agent Web 啟動的。"
        ),
        "- 需要人工的部分：領域負責人審閱各篇 `*.expected.json` 是否合理；"
        "真實模型每次的回答可能不同，分數只代表這一次。",
        "- 卡片：這個腳本只用試跑，不寫入卡片。"
        + (
            "bi.sqlite 前後相同。"
            if digests[0] == digests[1]
            else f"注意：bi.sqlite 前後不同（{digests[0][:12]} → {digests[1][:12]}），"
            "可能是同時有人在 Agent Web 寫入。"
        ),
        "",
        "| 筆記 | 執行 | 狀態 | 失敗段落 | 錯誤 |",
        "|---|---|---|---|---|",
        *(
            f"| {r['note']} | {r['run'] or '—'} | {r.get('status') or '—'} | "
            f"{r.get('failures', '—')} | {r.get('error') or ''} |"
            for r in rows
        ),
    ]
    text = benchmark.render_markdown(summary, title="BI 判讀 benchmark 報告", preface=preface)
    folder = workspace.joinpath(*REPORT_DIR)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{at.strftime('%Y%m%d-%H%M%S')}-{dataset}.md"
    path.write_text(text, encoding="utf-8")
    return path


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0] if __doc__ else None)
    commands = parser.add_subparsers(dest="command", required=True)
    live = commands.add_parser("run", help="upload, trial-run with the host model, score")
    live.add_argument("--config", type=Path, required=True, help="the host config JSON")
    live.add_argument("--dataset", required=True)
    live.add_argument("--workspace", type=Path, help="default: the config's workspace_root")
    live.add_argument("--instructions-file", type=Path, help="判讀規則 (default: shipped)")
    live.add_argument("--fixture", type=Path, default=FIXTURE)
    old = commands.add_parser("score", help="score runs that already exist")
    old.add_argument("--workspace", type=Path, required=True)
    old.add_argument("--dataset", required=True)
    old.add_argument("--run", action="append", required=True, metavar="NOTE=RUN_ID")
    old.add_argument("--fixture", type=Path, default=FIXTURE)
    args = parser.parse_args(argv)
    model: str | None = None
    if args.command == "run":
        ai, model, root = model_runtime(args.config)
        workspace = args.workspace or root
        before = _cards_digest(workspace, args.dataset)
        instructions = (
            args.instructions_file.read_text(encoding="utf-8") if args.instructions_file else None
        )
        summary, rows = run_benchmark(
            workspace, args.dataset, ai, fixture=args.fixture, instructions=instructions
        )
    else:
        workspace = args.workspace
        before = _cards_digest(workspace, args.dataset)
        chosen = {note: run for note, _, run in (item.partition("=") for item in args.run)}
        summary, rows = score_runs(workspace, args.dataset, chosen, fixture=args.fixture)
    after = _cards_digest(workspace, args.dataset)
    path = write_report(
        workspace,
        args.dataset,
        summary,
        rows,
        mode=args.command,
        model=model,
        digests=(before, after),
    )
    print(f"score {summary['score']}% ({summary['passed']}/{summary['checks']}); report: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
