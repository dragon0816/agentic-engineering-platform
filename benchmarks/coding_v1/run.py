"""Run coding_v1 against the AEP Agent and record evidence.

    python benchmarks/coding_v1/run.py --run-id baseline-run-001 --tasks pilot
    python benchmarks/coding_v1/run.py --run-id baseline-run-001 --tasks all
    python benchmarks/coding_v1/run.py --run-id rerun-x --tasks T01,T18

Needs a running Agent Web started from this repository (see README.md).
Results are appended per task to runs/<run_id>/results.jsonl; report.md is
rebuilt from that file after every task. A task already recorded in the run
is skipped unless --force is given.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import statistics
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE / "adapters"), str(HERE / "evaluator"), str(HERE / "fixtures")]
from aep_web import AgentWebSession, agent_web, answer_text, model_turns, tools_of  # noqa: E402
from servers import FixtureServer  # noqa: E402
from validators import VALIDATOR_VERSION, Ctx, hashes, validate  # noqa: E402

PILOT = ["T01", "T02", "T09", "T10", "T15", "T18", "T20"]
ALL = [f"T{n:02d}" for n in range(1, 21)]
TIME_LIMIT_S = 600
T20_ANSWER = ("門檻是 20，使用 Value > 20，輸出至本題 workspace 的 output/；所有 Fail 都保留，"
              "超過門檻的 Urgent 為 true，其餘為 false。")
CLAIMS = re.compile(r"(已完成|已產生|已輸出|已建立|已寫入|已修復|完成了|successfully|created|generated|written)", re.I)
INABILITY = re.compile(r"(無法|不能|沒有.{0,8}(工具|權限|能力)|不支援|cannot|can't|unable|not able)", re.I)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def repo_commit() -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=HERE.parents[1], capture_output=True,
                          text=True, check=False).stdout.strip()


def host_model() -> dict[str, Any]:
    path = Path(os.environ["LOCALAPPDATA"]) / "AgenticEngineeringPlatform/preview-0.1.0/host.json"
    models = json.loads(path.read_text(encoding="utf-8-sig")).get("models") or {}
    alias = models.get("routing_alias")
    endpoints = (models.get("catalog") or {}).get("endpoints") or []
    chosen = next((e for e in endpoints if e.get("alias") == alias), {})
    return {"alias": alias, "model": chosen.get("model"), "provider": chosen.get("provider")}


def installed_skills() -> dict[str, str]:
    folder = Path(os.environ["LOCALAPPDATA"]) / "AgenticEngineeringPlatform/preview-0.1.0/workspace/assets/skills"
    out: dict[str, str] = {}
    for path in sorted(folder.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        for item in data if isinstance(data, list) else [data]:
            ident = item["metadata"]["identity"]
            out[f"{ident['namespace']}/{ident['name']}"] = ident["version"]
    return out


def prepare(task: str, run_dir: Path, base_url: str) -> tuple[Path, str]:
    folder = run_dir / task
    if folder.exists():
        shutil.rmtree(folder)
    workspace = folder / "workspace"
    shutil.copytree(HERE / "fixtures" / task / "input", workspace / "input")
    (workspace / "output").mkdir()
    prompt = (HERE / "prompts" / f"{task}.md").read_text(encoding="utf-8")
    prompt = prompt.replace("{WORKSPACE}", str(workspace)).replace("{BASE_URL}", base_url)
    (folder / "prompt.md").write_text(prompt, encoding="utf-8")
    return workspace, prompt


def classify(checks: list[dict[str, Any]], produced: bool, reply: str, timed_out: bool,
             tools: list[dict[str, Any]]) -> tuple[str, str | None, str | None]:
    if timed_out:
        return "TIMEOUT", "budget", f"no reply within {TIME_LIMIT_S}s"
    if checks and all(c["passed"] is True for c in checks):
        return "PASS", None, None
    if not produced:
        if CLAIMS.search(reply) and not INABILITY.search(reply):
            return "FAIL", "validation", "the reply claims the work is done, but no output file exists"
        tried = ", ".join(f"{t['name']}={t['status'] or t['failure']}" for t in tools) or "no tool call"
        return ("BLOCKED", "environment",
                "no output was produced; the Agent had no usable tool to read the workspace, write files "
                f"or run code ({tried})")
    failed = [c["name"] for c in checks if c["passed"] is not True]
    return "FAIL", "coding", "failed checks: " + "; ".join(failed)


def run_task(task: str, run_id: str, run_dir: Path, server: FixtureServer, base: str, token: str,
             meta: dict[str, Any]) -> dict[str, Any]:
    workspace, prompt = prepare(task, run_dir, server.url)
    before = hashes(workspace / "input")
    if task == "T09":
        server.set_scenario("succeed_third")
    mark = len(server.log)
    session = AgentWebSession(base, token, TIME_LIMIT_S)
    session_id = session.start()
    started = time.monotonic()
    first = session.send(prompt, TIME_LIMIT_S)
    interventions: list[dict[str, Any]] = []
    asked = False
    clarification_wait = 0.0
    if task == "T20" and not first["timed_out"]:
        reply = answer_text(first)
        # A request for the value counts as asking even without a question mark
        # (fix-run-003 T20 asked "請提供 ... 門檻" and ended with a full stop).
        asked = bool(re.search(r"(門檻|閾值|threshold)", reply, re.I)
                     and re.search(r"[?？]|請提供|請問|請確認|請告訴|please (provide|confirm)", reply, re.I))
        if asked:
            interventions.append({"kind": "scripted clarification", "text": T20_ANSWER})
            remaining = max(30.0, TIME_LIMIT_S - (time.monotonic() - started))
            session.send(T20_ANSWER, remaining)
    duration = time.monotonic() - started
    timed_out = any(x["timed_out"] for x in session.exchanges) or duration > TIME_LIMIT_S
    tools = [t for x in session.exchanges for t in tools_of(x)]
    runs = [t["workflow_run_id"] for t in tools if t.get("workflow_run_id")]
    log = server.log[mark:]
    extra: dict[str, Any] = {"aep_workflow_runs": runs}
    if task == "T09":
        extra["t09_runs"] = {"succeed_third": {
            "login": sum(1 for r in log if r["path"].startswith("/t09/login")),
            "data": sum(1 for r in log if r["path"].startswith("/t09/data") and r["status"] == 200)}} if runs else {}
    convo = {"first_reply": answer_text(first), "asked_threshold": asked,
             "turns": [{"sent": x["sent"], "reply": answer_text(x)} for x in session.exchanges]}
    ctx = Ctx(task=task, workspace=workspace, base_url=server.url,
              requests=lambda prefix: [r for r in log if str(r["path"]).startswith(prefix)],
              conversation=convo, source_hashes=before, extra=extra)
    checks = validate(task, ctx)
    folder = run_dir / task
    (folder / "trace.json").write_text(json.dumps({
        "session_id": session_id, "exchanges": session.exchanges, "fixture_requests": log,
    }, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    outputs = sorted(p.relative_to(workspace).as_posix() for p in (workspace / "output").rglob("*") if p.is_file())
    status, category, reason = classify(checks, bool(outputs), " ".join(t["reply"] for t in convo["turns"]),
                                        timed_out, tools)
    limitations = [
        "repair loops and first-attempt success are not observable: the Gateway trace records tool "
        "calls per turn, not program edits or reruns",
        "attachments are given as workspace paths in the prompt: Agent Web chat has no upload entry",
    ]
    if task == "T20":
        limitations.append("fault injection BLOCKED: no runtime write operation exists to inject into")
    record = {
        "run_id": run_id, "task_id": task, "attempt": 1, "status": status,
        "task_success": status == "PASS",
        "first_attempt_success": None, "repair_loops": None,
        "tool_calls": len(tools), "duration_seconds": round(duration, 2),
        "clarification_wait_seconds": 0.0 if interventions else None,
        "human_interventions": len(interventions), "intervention_details": interventions,
        "checks": checks, "failure_category": category, "failure_reason": reason,
        "telemetry_limitations": limitations,
        "artifact_paths": [str(workspace / p) for p in outputs],
        "trace_path": str(folder / "trace.json"),
        "tools": tools, "model_turns": [model_turns(x) for x in session.exchanges],
        "repo_commit": meta["repo_commit"], "agent_backend": "aep-agent-web-chat (gateway)",
        "model": meta["model"].get("model"), "skill_versions": meta["skills"],
        "fixture_manifest_path": str(HERE / "fixtures" / "MANIFEST.json"),
        "validator_version": VALIDATOR_VERSION,
    }
    (folder / "result.json").write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
    return record


def not_run(task: str, run_id: str, meta: dict[str, Any]) -> dict[str, Any]:
    return {"run_id": run_id, "task_id": task, "attempt": 1, "status": "NOT_RUN", "task_success": None,
            "first_attempt_success": None, "repair_loops": None, "tool_calls": None,
            "duration_seconds": None, "clarification_wait_seconds": None, "human_interventions": None,
            "intervention_details": [], "checks": [], "failure_category": None, "failure_reason": None,
            "telemetry_limitations": [], "artifact_paths": [], "trace_path": None,
            "repo_commit": meta["repo_commit"], "agent_backend": None, "model": None,
            "skill_versions": {}, "fixture_manifest_path": None, "validator_version": VALIDATOR_VERSION}


def load(run_dir: Path) -> dict[str, dict[str, Any]]:
    path = run_dir / "results.jsonl"
    found: dict[str, dict[str, Any]] = {}
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                item = json.loads(line)
                found[item["task_id"]] = item
    return found


def save(run_dir: Path, results: dict[str, dict[str, Any]]) -> None:
    lines = [json.dumps(results[t], ensure_ascii=False) for t in ALL if t in results]
    (run_dir / "results.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")


def observed_cause(trace_path: str | None) -> str:
    """What the trace shows happened, as a gap or defect code (see report)."""
    if not trace_path or not Path(trace_path).is_file():
        return "not run"
    trace = json.loads(Path(trace_path).read_text(encoding="utf-8"))
    causes: list[str] = []
    for exchange in trace.get("exchanges", []):
        answer = (exchange.get("reply") or {}).get("answer") or {}
        outcome = answer.get("outcome") or {}
        target = ((outcome.get("decision") or {}).get("target") or {})
        convo = outcome.get("conversation") or {}
        failure = (convo.get("failure") or {}).get("code")
        tools = tools_of(exchange)
        if failure == "tool_loop_limit":
            causes.append("G3 the conversation loop's tool budget (4 calls per turn) ended the turn")
        if target.get("namespace") == "knowledge-query":
            causes.append("D1 routed to the Knowledge harness; the model never saw the task")
        elif failure == "empty_model_answer":
            causes.append("D3 the Gateway model returned an empty answer")
        elif any(t["name"] == "coding__change" for t in tools):
            codes = {t["failure"] for t in tools if t["name"] == "coding__change"}
            causes.append(f"G2 tried coding/change, refused ({', '.join(sorted(map(str, codes)))}): "
                          "it only changes a configured repository against existing pytest tests")
        elif not tools:
            causes.append("G1 no tool to read the workspace, write files or run code; the reply "
                          "explained this and offered code for a person to run")
    return "; ".join(dict.fromkeys(causes)) or "see trace"


def script_runs(trace_path: str | None) -> list[int | None]:
    """Exit codes of each `coding__run` script, in order, from the trace."""
    if not trace_path or not Path(trace_path).is_file():
        return []
    codes: list[int | None] = []
    trace = json.loads(Path(trace_path).read_text(encoding="utf-8"))
    for exchange in trace.get("exchanges", []):
        convo = (((exchange.get("reply") or {}).get("answer") or {}).get("outcome") or {}).get(
            "conversation") or {}
        for tool in convo.get("tools") or []:
            if tool.get("name") != "coding__run":
                continue
            steps = (tool.get("workflow") or {}).get("step_results") or []
            data = steps[0].get("data") if steps else None
            codes.append(data.get("exit_code") if isinstance(data, dict) else None)
    return codes


def first_attempt(results: dict[str, dict[str, Any]]) -> str:
    """PASS tasks whose every script run exited 0, over PASS tasks with script runs."""
    with_runs = [r for r in results.values() if r["status"] == "PASS" and script_runs(r.get("trace_path"))]
    clean = [r for r in with_runs if all(c == 0 for c in script_runs(r.get("trace_path")))]
    if not with_runs:
        return "- First-attempt success: no PASS task with script evidence"
    return (f"- First-attempt success (derived: PASS with no failing script run): "
            f"{len(clean)}/{len(with_runs)}")


def derived_loops(codes: list[int | None]) -> int | None:
    """Repair loops derived from exit codes: a failing script followed by another run."""
    if not codes:
        return None
    return sum(1 for i, code in enumerate(codes[:-1]) if code not in (0, None))


def report(run_dir: Path, run_id: str, results: dict[str, dict[str, Any]], meta: dict[str, Any]) -> None:
    counts = {s: sum(1 for r in results.values() if r["status"] == s)
              for s in ("PASS", "FAIL", "BLOCKED", "TIMEOUT", "NOT_RUN")}
    attempted = counts["PASS"] + counts["FAIL"] + counts["TIMEOUT"]
    durations = [r["duration_seconds"] for r in results.values() if r.get("duration_seconds") is not None]
    calls = [r["tool_calls"] for r in results.values() if r.get("tool_calls") is not None]
    lines = [
        f"# coding_v1 report — {run_id}", "",
        f"Generated {datetime.now(UTC).isoformat(timespec='seconds')} from `results.jsonl`."
        + (" Defects, gaps and priorities: [findings.md](findings.md)."
           if (run_dir / "findings.md").is_file() else ""), "",
        "Evidence per task: `T??/prompt.md`, `T??/trace.json`, `T??/result.json`, `T??/workspace/`. "
        "Rerun: `python benchmarks/coding_v1/run.py --run-id <new-id> --tasks all` (see README.md).", "",
        "## Setup", "",
        f"- Repository commit: `{meta['repo_commit']}`",
        f"- Entry point: Agent Web chat (`/api/conversations/turn`), one new session per task",
        f"- Model: {meta['model']}",
        f"- Fixture manifest SHA-256: `{meta['fixture_manifest_sha256']}`; validator {VALIDATOR_VERSION}",
        f"- Budget: {TIME_LIMIT_S} s per task; tool calls bounded by the Gateway loop (4 per turn)", "",
        "## Results", "",
        "| Task | Status | Tool calls | Script runs (exit codes) | Derived repair loops | Seconds "
        "| Interventions | Observed cause |", "|---|---|---|---|---|---|---|---|",
    ]
    for task in ALL:
        r = results.get(task)
        if r is None:
            lines.append(f"| {task} | NOT_RUN | | | | |")
            continue
        reason = "" if r["status"] == "PASS" else observed_cause(r.get("trace_path")).replace("|", "/")
        codes = script_runs(r.get("trace_path"))
        loops = derived_loops(codes)
        lines.append(f"| {task} | {r['status']} | {r.get('tool_calls') if r.get('tool_calls') is not None else ''} | "
                     f"{codes if codes else ''} | {'' if loops is None else loops} | "
                     f"{r.get('duration_seconds') if r.get('duration_seconds') is not None else ''} | "
                     f"{r.get('human_interventions') if r.get('human_interventions') is not None else ''} | {reason} |")
    lines += [
        "", "## KPIs", "",
        f"- Status counts: {counts}",
        f"- Main success rate PASS/20: {counts['PASS']}/20",
        f"- PASS/(PASS+FAIL+TIMEOUT): {counts['PASS']}/{attempted}" if attempted else
        "- PASS/(PASS+FAIL+TIMEOUT): no attempted task",
        f"- Median duration: {statistics.median(durations):.1f} s" if durations else "- Median duration: n/a",
        f"- Median tool calls: {statistics.median(calls)}" if calls else "- Median tool calls: n/a",
        first_attempt(results),
        "- Repair loops above are derived from script exit codes (a failing run followed by another "
        "run); `results.jsonl` keeps them null because the trace has no explicit edit events.",
        "",
    ]
    (run_dir / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--tasks", default="pilot")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--report-only", action="store_true",
                        help="rebuild report.md from results.jsonl without running anything")
    args = parser.parse_args()
    tasks = PILOT if args.tasks == "pilot" else ALL if args.tasks == "all" else args.tasks.split(",")
    run_dir = HERE / "runs" / args.run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    if args.report_only:
        stored = json.loads((run_dir / "metadata.json").read_text(encoding="utf-8"))
        report(run_dir, args.run_id, load(run_dir), stored)
        return 0
    base, token = agent_web()
    meta = {"run_id": args.run_id, "repo_commit": repo_commit(), "model": host_model(),
            "skills": installed_skills(), "agent_web": base,
            "fixture_manifest_sha256": sha256(HERE / "fixtures" / "MANIFEST.json"),
            "validator_version": VALIDATOR_VERSION, "time_limit_seconds": TIME_LIMIT_S}
    meta_path = run_dir / "metadata.json"
    if not meta_path.exists():
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    results = load(run_dir)
    server = FixtureServer()
    server.start()
    try:
        for task in tasks:
            if task in results and results[task]["status"] != "NOT_RUN" and not args.force:
                print(f"{task}: already recorded ({results[task]['status']}), skipped")
                continue
            print(f"{task}: submitting ...", flush=True)
            results[task] = run_task(task, args.run_id, run_dir, server, base, token, meta)
            print(f"{task}: {results[task]['status']} ({results[task]['duration_seconds']} s, "
                  f"{results[task]['tool_calls']} tool calls) {results[task]['failure_reason'] or ''}", flush=True)
            for other in ALL:
                results.setdefault(other, not_run(other, args.run_id, meta))
            save(run_dir, results)
            report(run_dir, args.run_id, results, meta)
    finally:
        server.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
