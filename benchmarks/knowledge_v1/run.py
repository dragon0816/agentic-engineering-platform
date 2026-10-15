"""knowledge_v1: ask the owner's Knowledge questions through Agent Web chat and
grade each answer (owner, 2026-10-07).

PASS when the Knowledge harness loop ran, the answer cites evidence that is
really in the Vault, and the reviewer finds its main points supported and its
conclusion reasonable. INSUFFICIENT_KNOWLEDGE (the harness ran and said the
Vault lacks the evidence) is acceptable too, as the question file says.

    python benchmarks/knowledge_v1/run.py --run-id <id> [--set sample|all|Q0001,Q0002] [--workers 2]
    python benchmarks/knowledge_v1/run.py --run-id <id> --regrade   # grade stored traces again
    python benchmarks/knowledge_v1/run.py --run-id <id> --regrade --into grader-1.4
        # grade stored traces again into runs/<id>/grader-1.4/, leaving the
        # original verdicts and report as they were

Each question gets a new conversation; the questions are sent as written,
without naming a knowledge base. Traces, verdicts and reasons are kept per
question under runs/<id>/<question>/.
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "benchmarks" / "coding_v1"))

from adapters.aep_web import AgentWebSession, agent_web  # noqa: E402
from evidence import INSUFFICIENT, cited_passages, knowledge_use, verify  # noqa: E402
from questions import SOURCE_SHA256, load, sample  # noqa: E402

sys.path.insert(0, str(REPO / "src"))
from telemetry.benchmark import BenchmarkTelemetry, agent_strategy, trace_ids  # noqa: E402

# 1.1 (2026-10-07): a gap reply that still cites evidence (a partial answer
# naming what is missing) is checked and reviewed like an answer; only a gap
# reply with no citations is INSUFFICIENT_KNOWLEDGE.
# 1.2 (2026-10-09): the tool route's Host-validated answer is read from the
# host record and cited like the direct route.
# 1.3 (2026-10-09): a tool-route answer the Harness refused to validate is a
# FAIL with VALIDATION_GAP, not a SYSTEM_ERROR.
GRADER_VERSION = "1.4"  # 1.4: the reviewer sees up to 48 passages
TIMEOUT_S = 600.0
HOST_JSON = Path(
    os.path.expandvars(r"%LOCALAPPDATA%\AgenticEngineeringPlatform\preview-0.1.0\host.json")
)
STATUSES = ("PASS", "INSUFFICIENT_KNOWLEDGE", "FAIL", "NEEDS_HUMAN_REVIEW", "SYSTEM_ERROR")


def vault_root() -> Path:
    host = json.loads(HOST_JSON.read_text(encoding="utf-8"))
    return Path(host["knowledge"][0]["vault_root"])


def grade(
    question: dict[str, Any], exchange: dict[str, Any], vault: Path, judge: Any
) -> dict[str, Any]:
    """The question's status, the harness layer it stopped at, and the evidence."""
    use = knowledge_use(exchange)
    base: dict[str, Any] = {
        "id": question["id"],
        "route": use["route"],
        "knowledge_status": use["status"],
        "failure": use["failure"],
        "phase": use["phase"],
        "tools": use["tools"],
        "seconds": exchange.get("seconds"),
        "grader": GRADER_VERSION,
    }
    if exchange.get("timed_out") or exchange.get("http_status") not in (200, None):
        return {
            **base,
            "status": "SYSTEM_ERROR",
            "gap": "SYSTEM_ERROR",
            "why": f"turn timed out or HTTP {exchange.get('http_status')}",
        }
    if use["route"] == "none":
        if use["status"] == "failed":
            return {
                **base,
                "status": "SYSTEM_ERROR",
                "gap": "SYSTEM_ERROR",
                "why": f"the conversation failed ({use['failure']})",
            }
        return {
            **base,
            "status": "FAIL",
            "gap": "EXECUTION_GAP",
            "why": "answered without using Knowledge",
        }
    gap = use["failure"] in INSUFFICIENT or use["phase"] == "needs_input"
    if use.get("harnessed") and not gap and use["status"] != "succeeded":
        # The Harness ran and its checks refused the answer: a validation
        # miss, not a system error.
        return {
            **base,
            "status": "FAIL",
            "gap": "VALIDATION_GAP",
            "why": f"the Knowledge Harness did not validate an answer ({use['failure']})",
        }
    if not gap and use["status"] != "succeeded":
        return {
            **base,
            "status": "SYSTEM_ERROR",
            "gap": "EXECUTION_GAP",
            "why": f"Knowledge did not complete ({use['failure'] or use['status']})",
        }
    if use.get("harnessed") and use["status"] == "succeeded" and not use["record"]:
        return {
            **base,
            "status": "NEEDS_HUMAN_REVIEW",
            "gap": "",
            "why": "the trace predates the host record carrying the cited passages",
        }
    passages = cited_passages(use) if use["status"] == "succeeded" else []
    base["partial"] = bool(gap and passages)
    if gap and not passages:
        return {
            **base,
            "status": "INSUFFICIENT_KNOWLEDGE",
            "gap": "SOURCE_GAP or RETRIEVAL_GAP",
            "why": f"the harness ran and reported a gap ({use['failure'] or use['phase']})",
        }
    if not passages:
        return {
            **base,
            "status": "FAIL",
            "gap": "VALIDATION_GAP",
            "why": "the answer cites no evidence",
        }
    checks = [verify(p, vault) for p in passages]
    base["citations"] = checks
    missing = [c for c in checks if not c["ok"]]
    if missing:
        return {
            **base,
            "status": "FAIL",
            "gap": "VALIDATION_GAP",
            "why": f"{len(missing)} of {len(checks)} citations not found in the Vault",
        }
    review = judge.review(question["text"], use["text"], passages)
    base["review"] = review
    if not review.get("ok"):
        return {
            **base,
            "status": "NEEDS_HUMAN_REVIEW",
            "gap": "",
            "why": f"the reviewer gave no verdict ({review.get('error')})",
        }
    if review.get("supported") and review.get("reasonable"):
        if review.get("confidence") == "low":
            return {
                **base,
                "status": "NEEDS_HUMAN_REVIEW",
                "gap": "",
                "why": "reviewer confidence low",
            }
        return {**base, "status": "PASS", "gap": "", "why": ""}
    return {
        **base,
        "status": "FAIL",
        "gap": "REASONING_GAP",
        "why": "reviewer: " + str(review.get("reason") or "")[:300],
    }


def tags(question: dict[str, Any]) -> dict[str, Any]:
    """The question's bank tags (never its text)."""
    return {
        "case_type": question.get("type", "foundation"),
        "market": question.get("market"),
        "product": question.get("product"),
        "difficulty": question.get("difficulty"),
        "technical": question.get("technical"),
    }


def case_attributes(
    question: dict[str, Any], result: dict[str, Any], exchange: dict[str, Any] | None
) -> dict[str, Any]:
    """Telemetry attributes of one graded question: tags, verdict details, links."""
    review = result.get("review") if isinstance(result.get("review"), dict) else {}
    citations = result.get("citations") or []
    seconds = result.get("seconds")
    return {
        **tags(question),
        "gap": result.get("gap") or None,
        "route": result.get("route"),
        "knowledge_status": result.get("knowledge_status"),
        "failure_code": result.get("failure"),
        "phase": result.get("phase"),
        "partial": result.get("partial"),
        "duration_ms": int(seconds * 1000) if isinstance(seconds, int | float) else None,
        "citations_total": len(citations),
        "citations_verified": sum(1 for c in citations if c.get("ok")),
        "reviewer_supported": review.get("supported"),
        "reviewer_reasonable": review.get("reasonable"),
        "reviewer_confidence": review.get("confidence"),
        "overreach_count": len(review.get("overreach") or []),
        "aep_trace_ids": trace_ids(exchange) if exchange else None,
        "grader": result.get("grader"),
    }


def ask(question: dict[str, Any], folder: Path, base: str, token: str) -> dict[str, Any]:
    session = AgentWebSession(base, token, TIMEOUT_S)
    session.start()
    exchange = session.send(question["text"], TIMEOUT_S)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "trace.json").write_text(
        json.dumps(
            {"question": question, "session_id": session.session_id, "exchange": exchange},
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )
    return exchange


def credential() -> None:
    """The reviewer's key comes from the user environment, as the Host's does."""
    if "LITELLM_MASTER_KEY" not in os.environ:
        value = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "[Environment]::GetEnvironmentVariable('LITELLM_MASTER_KEY','User')",
            ],
            capture_output=True,
            text=True,
            check=False,
        ).stdout.strip()
        if value:
            os.environ["LITELLM_MASTER_KEY"] = value


def report(
    run_dir: Path,
    results: list[dict[str, Any]],
    questions: dict[str, dict[str, Any]],
    meta: dict[str, Any],
) -> None:
    counts = collections.Counter(r["status"] for r in results)
    acceptable = counts["PASS"] + counts["INSUFFICIENT_KNOWLEDGE"]
    lines = [
        f"# knowledge_v1 — {run_dir.name}",
        "",
        f"Run at {meta['started']}, AEP commit `{meta['commit']}`, grader {GRADER_VERSION}, "
        f"question bank sha256 `{SOURCE_SHA256[:12]}…`, set `{meta['set']}`.",
        "",
        f"**{acceptable} of {len(results)} acceptable** "
        f"(PASS {counts['PASS']}, INSUFFICIENT_KNOWLEDGE {counts['INSUFFICIENT_KNOWLEDGE']}); "
        + ", ".join(f"{s} {counts[s]}" for s in STATUSES[2:]),
        "",
    ]

    def table(title: str, key: Any) -> None:
        groups: dict[str, collections.Counter[str]] = collections.defaultdict(collections.Counter)
        for result in results:
            groups[key(questions[result["id"]])][result["status"]] += 1
        lines.extend(
            [
                f"## By {title}",
                "",
                "| " + title + " | " + " | ".join(STATUSES) + " |",
                "|---|" + "---|" * len(STATUSES),
            ]
        )
        for name in sorted(groups):
            lines.append(f"| {name} | " + " | ".join(str(groups[name][s]) for s in STATUSES) + " |")
        lines.append("")

    table("market", lambda q: q.get("market", "foundation"))
    table("product", lambda q: q.get("product", q.get("technical", "foundation")))
    table("type", lambda q: q.get("type", "foundation"))
    routes = collections.Counter(r["route"] for r in results)
    gaps = collections.Counter(r["gap"] for r in results if r.get("gap"))
    lines += [
        "## Harness",
        "",
        "Routes: " + ", ".join(f"{k} {v}" for k, v in sorted(routes.items())),
        "",
        "Gaps: " + (", ".join(f"{k} {v}" for k, v in gaps.most_common()) or "none"),
        "",
        "## Not passed",
        "",
        "| Question | Status | Gap | Why |",
        "|---|---|---|---|",
    ]
    for result in sorted(results, key=lambda r: r["id"]):
        if result["status"] != "PASS":
            lines.append(
                f"| {result['id']} | {result['status']} | {result.get('gap', '')} | "
                f"{str(result.get('why', '')).replace('|', '/')[:200]} |"
            )
    (run_dir / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--set", default="sample", help="sample | all | comma-separated IDs")
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--force", action="store_true", help="ask again questions already recorded")
    parser.add_argument("--regrade", action="store_true", help="grade stored traces without asking")
    parser.add_argument(
        "--into",
        default="",
        help="with --regrade: write verdicts and report under runs/<id>/<into>/",
    )
    args = parser.parse_args()
    plain = args.into.replace("-", "").replace(".", "").isalnum()
    if args.into and (not args.regrade or not plain):
        parser.error("--into needs --regrade and a plain folder name")
    bank = load()
    by_id = {q["id"]: q for q in bank}
    chosen = (
        sample(bank)
        if args.set == "sample"
        else bank
        if args.set == "all"
        else [by_id[i.strip()] for i in args.set.split(",")]
    )
    run_dir = HERE / "runs" / args.run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True, check=False
    ).stdout.strip()
    meta_path = run_dir / "metadata.json"
    meta = (
        json.loads(meta_path.read_text(encoding="utf-8"))
        if meta_path.exists()
        else {
            "started": datetime.now(UTC).isoformat(timespec="seconds"),
            "commit": commit,
            "set": args.set,
            "question_bank_sha256": SOURCE_SHA256,
            "timeout_s": TIMEOUT_S,
        }
    )
    meta_path.write_text(json.dumps(meta, indent=1) + "\n", encoding="utf-8")
    credential()
    from judge import Judge  # needs the credential in the environment

    judge = Judge(HOST_JSON)
    vault = vault_root()
    base = token = ""
    if not args.regrade:
        base, token = agent_web()
    lock = threading.Lock()
    # Progress and verdicts go to the Host telemetry for the Atlas dashboard.
    bench = BenchmarkTelemetry("knowledge_v1", args.run_id)
    bench.start(
        cases=len(chosen),
        strategy=agent_strategy(base or None),
        grader=GRADER_VERSION,
        question_set=args.set if len(args.set) <= 40 else "custom",
        regrade=args.regrade,
    )
    meta.setdefault("telemetry_runs", []).append(bench.run_id)
    meta_path.write_text(json.dumps(meta, indent=1) + "\n", encoding="utf-8")

    out_dir = run_dir / args.into if args.into else run_dir

    def one(question: dict[str, Any]) -> dict[str, Any] | None:
        folder = run_dir / question["id"]
        result_path = out_dir / question["id"] / "result.json"
        result_path.parent.mkdir(parents=True, exist_ok=True)
        if result_path.exists() and not args.force and not args.regrade:
            kept = json.loads(result_path.read_text(encoding="utf-8"))
            bench.case_completed(
                question["id"], kept["status"], reused=True, **case_attributes(question, kept, None)
            )
            return kept
        bench.case_started(question["id"], **tags(question))
        if args.regrade:
            if not (folder / "trace.json").exists():
                return None
            exchange = json.loads((folder / "trace.json").read_text(encoding="utf-8"))["exchange"]
        else:
            exchange = ask(question, folder, base, token)
        result = grade(question, exchange, vault, judge)
        result_path.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
        bench.case_completed(
            question["id"], result["status"], **case_attributes(question, result, exchange)
        )
        with lock:
            print(
                f"{question['id']}: {result['status']} ({result.get('seconds')} s, "
                f"{result['route']}) "
                f"{result.get('why', '')[:120]}",
                flush=True,
            )
        return result

    started = time.monotonic()
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        results = [r for r in pool.map(one, chosen) if r is not None]
    report(out_dir, results, by_id, meta)
    bench.finish()
    print(
        f"done: {len(results)} graded in {round(time.monotonic() - started)} s; see "
        f"{out_dir / 'report.md'}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
