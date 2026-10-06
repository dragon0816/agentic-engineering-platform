"""Submit the lab tasks to the AEP Agent through Agent Web chat and grade them.

  python benchmarks/business_workflow_lab/operator/run_lab.py --run-id baseline-001 --tasks smoke
  python benchmarks/business_workflow_lab/operator/run_lab.py --run-id baseline-001 --tasks all
  python benchmarks/business_workflow_lab/operator/run_lab.py --run-id baseline-001 --report-only

Each task gets a new chat session (the same path a person uses), a fresh
workspace with only that task's attachments, and the mocks reset to the
task's scenario. The operator never performs the task: it sends the prompt,
answers X02's clarification only when the Agent actually asks, asks for the
parameter rerun on W01/D01/C01/X01, and grades what the Agent left behind.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
LAB = HERE.parent
REPO = LAB.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "benchmarks" / "coding_v1" / "adapters"))
from aep_web import AgentWebSession, agent_web, answer_text, model_turns, tools_of  # noqa: E402
from grade import TEMPLATE, find_workbook, grade_workbook, verdict  # noqa: E402
from reset import events, reset  # noqa: E402

SAP_PORT = 8810
SAP_URL = f"http://127.0.0.1:{SAP_PORT}/"
TASKS = ["W01", "W02", "W03", "W04", "D01", "D02", "D03", "D04", "C01", "C02", "C03", "C04", "X01", "X02", "X03"]
SMOKE = ["W01", "D01", "C01"]
LIMIT_S = {t: 1800 if t.startswith("X") else 900 for t in TASKS}
SCENARIO = {"W04": {"sap": "expire_session_once"}, "D04": {"expense": "export_fail_once"},
            "C04": {"quote": "transient_once"}}
NEEDS = {"W": ("sap",), "D": ("expense",), "C": ("quote",)}
SYSTEMS = {"W01": ["sap"], "W02": ["sap"], "W03": ["sap"], "W04": ["sap"],
           "D01": ["expense"], "D02": ["expense"], "D03": ["expense"], "D04": ["expense"],
           "C01": ["quote"], "C02": ["quote"], "C03": ["quote"], "C04": ["quote"],
           "X01": ["sap", "expense", "quote"], "X02": ["sap", "expense", "quote"], "X03": ["sap", "expense", "quote"]}
MANUAL = {"sap": "sap_manual.md", "expense": "expense_manual.md", "quote": "quote_cli_manual.md"}
RERUN = {
    "W01": ("請使用你剛才產生的 workflow，不要修改程式碼，只改參數：起訖日期 2026-08-01 到 2026-08-31、status 改為 "
            "Closed，輸出到 output\\rerun\\august_closed_orders.xlsx。", "rerun"),
    "D01": ("請使用你剛才產生的 workflow，不要修改程式碼，只改參數：員工 E002、期間 2026-08-01 到 2026-08-31，"
            "輸出到 output\\rerun\\E002_august_expenses.xlsx。", "rerun"),
    "C01": ("請使用你剛才產生的 workflow，不要修改程式碼，只改參數：CustomerID C002、期間 2026-08-01 到 2026-10-31，"
            "輸出到 output\\rerun\\C002_quotes.xlsx。", "rerun"),
    "X01": ("請使用你剛才產生的 workflow，不要修改程式碼，只改參數：期間 2026-08-01 到 2026-08-31，"
            "輸出到 output\\rerun\\august_projects.xlsx。", "rerun"),
}
X02_ANSWER = ("費用限 C001 對應專案的 Approved；訂單排除 Cancelled；報價全部保留。關注條件為截至 2026-09-30 "
              "已逾期未收的發票、缺收據費用、ValidUntil 小於 2026-09-30 且非 Accepted 的報價。使用附件匯率，不要用即時匯率。")
BYPASS = re.compile(r"source\.json|operator[\\/]+data|operator[\\/]+state|expense_app|quote_cli\.cli|"
                    r"from\s+quote_cli|import\s+quote_cli|business_workflow_lab[\\/]+operator", re.I)
SUBPROCESS_BLOCKED = re.compile(r"WinError 1816|Not enough quota|PermissionError.*(subprocess|CreateProcess)|"
                                r"_winapi\.CreateProcess", re.I)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def cli_help() -> str:
    run = subprocess.run([sys.executable, str(LAB / "quote_cli_mock" / "run_quote_cli.py"), "--help"],
                         capture_output=True, text=True, encoding="utf-8", timeout=60)
    return run.stdout.strip()


def sap_running() -> bool:
    try:
        urllib.request.urlopen(SAP_URL + "login", timeout=2).read()
        return True
    except OSError:
        return False


def start_sap() -> subprocess.Popen[bytes] | None:
    if sap_running():
        return None
    log = (LAB / "operator" / "state" / "sap_server.log").open("ab")
    proc = subprocess.Popen([sys.executable, str(LAB / "sap_mock" / "server.py"), "--port", str(SAP_PORT)],
                            stdout=log, stderr=subprocess.STDOUT)
    for _ in range(50):
        if sap_running():
            return proc
        time.sleep(0.2)
    raise RuntimeError("the SAP mock did not start")


def prepare(task: str, folder: Path, help_text: str) -> tuple[Path, str]:
    workspace = folder / "workspace"
    if workspace.exists():
        shutil.rmtree(workspace)
    (workspace / "input").mkdir(parents=True)
    (workspace / "output").mkdir()
    attachments = []
    template = f"{TEMPLATE[task]}_template.xlsx"
    shutil.copy(LAB / "templates" / template, workspace / "input" / template)
    shutil.copy(LAB / "templates" / "fx_rates.csv", workspace / "input" / "fx_rates.csv")
    attachments += [template, "fx_rates.csv"]
    for system in SYSTEMS[task]:
        body = (LAB / "manuals" / MANUAL[system]).read_text(encoding="utf-8")
        body = body.replace("{SAP_URL}", SAP_URL).replace("{LAB}", str(LAB)).replace("{CLI_HELP}", help_text)
        (workspace / "input" / MANUAL[system]).write_text(body, encoding="utf-8")
        attachments.append(MANUAL[system])
    if task == "X03":
        source = folder.parent / "X01" / "workspace" / "output" / "workflow"
        if source.is_dir():
            shutil.copytree(source, workspace / "input" / "x01_workflow")
            attachments.append("x01_workflow\\（X01 產生的 workflow 與程式）")
    request = (LAB / "prompts" / f"{task}.md").read_text(encoding="utf-8").strip()
    listing = "\n".join(f"  - input\\{name}" for name in attachments)
    prompt = (f"{request}\n\n---\n環境說明（操作者提供）\n"
              f"- 今天日期：2026-10-06（Asia/Taipei）\n"
              f"- 本題 workspace：{workspace}\n"
              f"- 附件（在 workspace 的 input 資料夾）：\n{listing}\n"
              f"- 交付物請寫到 workspace 的 output 資料夾；需要可重跑的 workflow 時，請建立成本平台的 workflow。")
    (folder / "prompt.md").write_text(prompt + "\n", encoding="utf-8")
    return workspace, prompt


FOLLOW_UP = ("（操作者已按下核准，執行結果已附在對話中。）請檢查結果並繼續；"
             "完成時說明產出了哪些檔案。")


def settle(session: AgentWebSession, deadline: float, interventions: list[dict[str, Any]],
           decided: list[dict[str, Any]]) -> None:
    """Press the owner's approve button for each request the Agent made (spec §10: recorded
    as an intervention), then tell it the result is in the conversation."""
    for _ in range(6):
        pending = session.approvals()
        if not pending or time.monotonic() > deadline:
            return
        for item in pending:
            reply = session.decide(item["approval_id"], "approve",
                                   max(60.0, deadline - time.monotonic()))
            approval = reply.get("approval") or {}
            result = approval.get("result") if isinstance(approval.get("result"), dict) else {}
            decided.append({"approval_id": item["approval_id"], "kind": item["kind"],
                            "workflow": item.get("workflow"), "arguments": item.get("arguments"),
                            "status": approval.get("status"), "run_id": result.get("run_id"),
                            "run_status": result.get("status"), "digest": result.get("digest"),
                            "text": str(reply.get("text") or "")[:800]})
            interventions.append({"kind": "operator pressed the owner's approve button",
                                  "approval_id": item["approval_id"], "summary": item["summary"]})
        session.send(FOLLOW_UP, max(60.0, deadline - time.monotonic()))


def authored_runs(exchanges: list[dict[str, Any]], decided: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Platform Workflow runs: read-only runs the host did at once, and approved runs."""
    out = []
    for exchange in exchanges:
        convo = (((exchange.get("reply") or {}).get("answer") or {}).get("outcome") or {}).get(
            "conversation") or {}
        for tool in convo.get("tools") or []:
            host = tool.get("host") or {}
            data = host.get("data") if isinstance(host.get("data"), dict) else {}
            if tool.get("name") == "authoring__run_workflow" and data.get("run_id"):
                out.append({"run_id": data["run_id"], "digest": data.get("digest"),
                            "status": data.get("status")})
    out += [{"run_id": d["run_id"], "digest": d["digest"], "status": d["run_status"]}
            for d in decided if d.get("run_id")]
    return out


def tree_hashes(folder: Path) -> dict[str, str]:
    if not folder.is_dir():
        return {}
    return {p.relative_to(folder).as_posix(): sha256(p) for p in sorted(folder.rglob("*")) if p.is_file()}


def script_runs(exchanges: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for exchange in exchanges:
        convo = (((exchange.get("reply") or {}).get("answer") or {}).get("outcome") or {}).get("conversation") or {}
        for tool in convo.get("tools") or []:
            if tool.get("name") != "coding__run":
                continue
            steps = (tool.get("workflow") or {}).get("step_results") or []
            data = steps[0].get("data") if steps else None
            data = data if isinstance(data, dict) else {}
            out.append({"exit_code": data.get("exit_code"), "timed_out": data.get("timed_out"),
                        "script": data.get("script_path"), "output_tail": str(data.get("output") or "")[-600:],
                        "refused": (tool.get("failure") or {}).get("code")})
    return out


def conversation_failures(exchanges: list[dict[str, Any]]) -> list[str]:
    out = []
    for exchange in exchanges:
        convo = (((exchange.get("reply") or {}).get("answer") or {}).get("outcome") or {}).get("conversation") or {}
        failure = (convo.get("failure") or {}).get("code")
        if failure:
            out.append(failure)
        if exchange.get("timed_out"):
            out.append("turn_timed_out")
    return out


def interfaces(task_events: dict[str, list[dict[str, Any]]], runs: list[dict[str, Any]],
               bypass: list[str]) -> tuple[list[str], dict[str, Any]]:
    used, evidence = [], {}
    sap = [e for e in task_events["sap"] if e["event"] not in {"operator_reset"}]
    if sap:
        agents = sorted({str(e.get("ua", "")) for e in sap if e.get("ua")})
        browser = any("Mozilla" in a for a in agents)
        used.append("browser (SAP web)" if browser else "HTTP client script (SAP web, no browser)")
        evidence["sap"] = {"user_agents": agents, "browser": browser,
                           "logins": sum(1 for e in sap if e["event"] == "login" and e.get("ok")),
                           "queries": sum(1 for e in sap if e["event"] == "query"),
                           "details": sorted({str(e.get("id")) for e in sap if e["event"] == "detail"}),
                           "exports": sum(1 for e in sap if e["event"] == "export"),
                           "session_expired": sum(1 for e in sap if e["event"] == "session_expired_injected")}
    expense = [e for e in task_events["expense"] if e["event"] not in {"operator_reset"}]
    if expense:
        used.append("desktop GUI (Expense)")
        evidence["expense"] = [e["event"] for e in expense]
    quote = [e for e in task_events["quote"] if e["event"] not in {"operator_reset"}]
    process = [e for e in quote if e["event"] != "command"
               or str(e.get("argv0", "")).replace("\\", "/").endswith(
                   ("quote_cli/__main__.py", "run_quote_cli.py"))]
    if process:
        used.append("CLI subprocess (quote)")
        evidence["quote"] = [{"event": e["event"], "argv": e.get("argv"), "argv0": e.get("argv0")}
                             for e in quote]
    elif quote:
        used.append("quote CLI imported in-process (not a CLI run)")
        evidence["quote_in_process"] = [{"event": e["event"], "argv0": e.get("argv0")} for e in quote]
    if runs:
        used.append("coding execution (restricted runner)")
    if bypass:
        used.append("direct read of mock internals (bypass)")
    return used, evidence


def run_task(task: str, run_dir: Path, base: str, token: str, help_text: str,
             results: dict[str, dict[str, Any]], variant_override: str | None = None) -> dict[str, Any]:
    label = task if variant_override is None else f"{task}-{variant_override}"
    folder = run_dir / label
    folder.mkdir(parents=True, exist_ok=True)
    workspace, prompt = prepare(task, folder, help_text)
    scenario = dict(SCENARIO.get(task, {}))
    if variant_override == "force_exit2":
        scenario = {"quote": "force_exit2"}
    offsets = reset(label=f"{run_dir.name}/{label}", **scenario)
    limit = LIMIT_S[task]
    session = AgentWebSession(base, token, limit)
    session_id = session.start()
    started = time.monotonic()
    first = session.send(prompt, limit)
    interventions: list[dict[str, Any]] = []
    asked = None
    if task == "X02" and not first["timed_out"]:
        reply = answer_text(first)
        asked = bool(re.search(r"[?？]", reply) and re.search(r"(費用|關注|status|狀態|條件|專案|規則)", reply, re.I))
        if asked:
            interventions.append({"kind": "scripted clarification (operator answer fixed by the spec)",
                                  "text": X02_ANSWER})
            session.send(X02_ANSWER, max(60.0, limit - (time.monotonic() - started)))
    output = workspace / "output"
    deadline = started + limit
    decided: list[dict[str, Any]] = []
    if not session.exchanges[-1]["timed_out"]:
        settle(session, deadline, interventions, decided)
    first_runs = authored_runs(session.exchanges, decided)
    rerun_checks: list[dict[str, Any]] | None = None
    workflow_same: bool | None = None
    if task in RERUN and variant_override is None and find_workbook(output, task) is not None:
        message, variant = RERUN[task]
        interventions.append({"kind": "operator rerun request (spec §9 second parameter set)", "text": message})
        mark = len(session.exchanges)
        session.send(message, max(60.0, deadline - time.monotonic()))
        settle(session, deadline, interventions, decided)
        rerun_runs = [r for r in authored_runs(session.exchanges[mark:], decided)
                      if r not in first_runs]
        digests = {r["digest"] for r in first_runs if r.get("digest")}
        # Same Workflow code: the rerun used a digest the first runs used, and succeeded.
        workflow_same = bool(rerun_runs) and all(r.get("digest") in digests for r in rerun_runs)
        rerun_book = find_workbook(output, task, "rerun")
        rerun_checks = grade_workbook(task, variant, rerun_book, answer_text(session.exchanges[-1]), output)
    duration = time.monotonic() - started
    task_events = {s: events(s, offsets[s]) for s in ("sap", "expense", "quote")}
    runs = script_runs(session.exchanges)
    scripts = sorted((workspace / ".aep-run").rglob("*.py")) if (workspace / ".aep-run").is_dir() else []
    bypass = sorted({f"{p.relative_to(workspace).as_posix()}: {m.group(0)}" for p in scripts
                     for m in [BYPASS.search(p.read_text(encoding="utf-8", errors="replace"))] if m})
    used, evidence = interfaces(task_events, runs, bypass)
    replies = "\n".join(answer_text(x) for x in session.exchanges)
    variant = variant_override or "main"
    book = find_workbook(output, task)
    checks = grade_workbook(task, variant, book, replies, output)
    if task == "W04":
        sap = evidence.get("sap", {})
        checks.append({"name": "W04: the injected session expiry happened and the Agent signed in again",
                       "ok": sap.get("session_expired", 0) >= 1 and sap.get("logins", 0) >= 2, "detail": sap})
    if task == "W02":
        details = set(evidence.get("sap", {}).get("details", []))
        from expected import expected

        missing = sorted(set(expected("W02")["ids"]) - details)
        checks.append({"name": "W02: every order's detail page was opened", "ok": not missing, "detail": missing})
    if task == "X02":
        checks.append({"name": "X02: asked for the missing rules before acting", "ok": bool(asked),
                       "detail": answer_text(first)[:400]})
    excel_ok = verdict(checks) if (book is not None or variant == "force_exit2") else False
    timed_out = any(x["timed_out"] for x in session.exchanges) or duration > limit
    code_generated = bool(runs) if runs or session.exchanges else None
    executed = any(r["exit_code"] == 0 for r in runs) if runs else False
    loops = sum(1 for r in runs[:-1] if r["exit_code"] not in (0, None)) if runs else None
    rerun_ok: bool | None = None
    if task in RERUN and variant_override is None:
        # None when no rerun was asked for: the first turn left nothing to rerun.
        rerun_ok = bool(workflow_same) and verdict(rerun_checks) is True if rerun_checks is not None else None
    status, layer, reason = classify(task, variant, timed_out, excel_ok, evidence, used, bypass, runs,
                                     conversation_failures(session.exchanges), rerun_ok, book)
    record = {
        "task_id": label, "status": status,
        "code_generated": code_generated, "execution_succeeded": executed,
        "excel_correct": excel_ok, "workflow_rerun_succeeded": rerun_ok,
        "elapsed_seconds": round(duration, 1), "repair_loops": loops,
        "human_interventions": len(interventions), "interfaces_used": used,
        "failure_reason": reason, "blocked_layer": layer,
        "artifact_paths": sorted(str(p) for p in output.rglob("*") if p.is_file()),
        "evidence_paths": [str(folder / "trace.json"), str(folder / "events.json")]
                          + [str(p) for p in scripts],
        "script_runs": [{"exit_code": r["exit_code"], "script": r["script"], "refused": r["refused"]} for r in runs],
        "conversation_failures": conversation_failures(session.exchanges),
        "bypass_signals": bypass, "interventions": interventions,
        "platform_runs": authored_runs(session.exchanges, decided), "approvals": decided,
        "workflow_unchanged_on_rerun": workflow_same,
        "checks": checks, "rerun_checks": rerun_checks,
        "session_id": session_id, "model_turns": [model_turns(x) for x in session.exchanges],
        "tool_calls": len([t for x in session.exchanges for t in tools_of(x)]),
    }
    (folder / "trace.json").write_text(json.dumps({"session_id": session_id, "exchanges": session.exchanges},
                                                  ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    (folder / "events.json").write_text(json.dumps({"interfaces": evidence, "events": task_events},
                                                   ensure_ascii=False, indent=1), encoding="utf-8")
    (folder / "result.json").write_text(json.dumps(record, ensure_ascii=False, indent=1, default=str),
                                        encoding="utf-8")
    return record


def classify(task: str, variant: str, timed_out: bool, excel_ok: bool | None, evidence: dict[str, Any],
             used: list[str], bypass: list[str], runs: list[dict[str, Any]], failures: list[str],
             rerun_ok: bool | None, book: Path | None) -> tuple[str, str | None, str | None]:
    """(status, blocked layer, reason). A missing tool is BLOCKED, never FAIL."""
    if timed_out:
        return "TIMEOUT", None, "the turn did not finish within the time limit"
    notes = []
    if failures:
        notes.append("conversation stopped: " + ", ".join(sorted(set(failures))))
    if bypass:
        notes.append("scripts read mock internals instead of using the interface: " + "; ".join(bypass[:3]))
    systems = SYSTEMS[task]
    if "expense" in systems and "expense" not in evidence:
        return ("BLOCKED", "harness: no native desktop (GUI automation) tool in the AEP conversation or Bridge",
                "; ".join(["the Expense desktop app was never operated", *notes]))
    if "sap" in systems and not evidence.get("sap", {}).get("browser"):
        how = ("scripts reached the site with an HTTP client" if "sap" in evidence
               else "the site was never reached")
        return ("BLOCKED", "harness: no browser tool in the AEP conversation (web/act exists only as a Workflow step)",
                "; ".join([how, *notes]))
    if "quote" in systems and "quote" not in evidence:
        # Name only what was observed: a refused subprocess, or the turn ending first.
        if any(SUBPROCESS_BLOCKED.search(r["output_tail"]) for r in runs):
            layer = "runner: the restricted runner refused to start a subprocess (one-process job)"
        elif failures:
            layer = ("harness: the conversation stopped before the CLI was tried "
                     f"({', '.join(sorted(set(failures)))})")
        else:
            layer = "harness: no tool ran the CLI as a process"
        return "BLOCKED", layer, "; ".join(["the quote CLI was never run as a process", *notes])
    if book is None and variant != "force_exit2":
        return "FAIL", None, "; ".join(["no Excel deliverable", *notes])
    if excel_ok is not True:
        return "FAIL", None, "; ".join(["Excel checks failed", *notes])
    if rerun_ok is False:
        return "FAIL", None, "; ".join(["the parameter rerun did not succeed with unchanged workflow code", *notes])
    return "PASS", None, None


def reclassify(record: dict[str, Any], folder: Path) -> dict[str, Any]:
    """Recompute status from stored evidence after a grading-rule fix; the Agent is not rerun."""
    trace = json.loads((folder / "trace.json").read_text(encoding="utf-8"))
    stored = json.loads((folder / "events.json").read_text(encoding="utf-8"))
    task, _, variant = record["task_id"].partition("-")
    runs = script_runs(trace["exchanges"])
    book = find_workbook(folder / "workspace" / "output", task)
    status, layer, reason = classify(task, variant or "main", "TIMEOUT" == record["status"], record["excel_correct"],
                                     stored["interfaces"], record["interfaces_used"], record["bypass_signals"], runs,
                                     conversation_failures(trace["exchanges"]), record["workflow_rerun_succeeded"],
                                     book)
    updated = dict(record, status=status, blocked_layer=layer, failure_reason=reason)
    if record.get("rerun_checks") is None:
        updated["workflow_rerun_succeeded"] = None
    (folder / "result.json").write_text(json.dumps(updated, ensure_ascii=False, indent=1, default=str),
                                        encoding="utf-8")
    return updated


def not_run(task: str, reason: str | None = None, layer: str | None = None, status: str = "NOT_RUN") -> dict[str, Any]:
    return {"task_id": task, "status": status, "code_generated": None, "execution_succeeded": None,
            "excel_correct": None, "workflow_rerun_succeeded": None, "elapsed_seconds": None, "repair_loops": None,
            "human_interventions": 0, "interfaces_used": [], "failure_reason": reason, "blocked_layer": layer,
            "artifact_paths": [], "evidence_paths": []}


def report(run_dir: Path, results: dict[str, dict[str, Any]], meta: dict[str, Any]) -> None:
    order = TASKS + ["C04-force_exit2"]
    rows = [results[t] for t in order if t in results]
    counts: dict[str, int] = {}
    for r in rows:
        counts[r["status"]] = counts.get(r["status"], 0) + 1

    def flag(value: Any) -> str:
        return {True: "yes", False: "no", None: "–"}.get(value, str(value))

    smoke = json.loads((LAB / "operator" / "state" / "smoke.json").read_text(encoding="utf-8")) \
        if (LAB / "operator" / "state" / "smoke.json").exists() else []
    lines = [
        f"# business_workflow_lab — {run_dir.name}",
        "",
        f"Run at {meta['started']}, AEP commit `{meta['repo_commit']}`, model `{meta.get('model')}`, "
        f"Agent Web chat (Gateway conversation). Synthetic data seed 20261006; source manifest "
        f"`{meta['source_sha256'][:12]}…`.",
        "",
        "## 1. Mock systems",
        "",
        f"Smoke checks: {sum(1 for s in smoke if s['ok'])}/{len(smoke)} passed "
        "(`operator/smoke.py`, recorded in `operator/state/smoke.json`).",
        "",
        "## 2. Task results",
        "",
        "Status counts: " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())),
        "",
        "| Task | Status | Code generated | Executed | Excel correct | Workflow rerun | Seconds | Repair loops "
        "| Interventions | Interfaces | Blocked layer / reason |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        why = " — ".join(x for x in (r.get("blocked_layer"), r.get("failure_reason")) if x).replace("|", "/")
        lines.append(f"| {r['task_id']} | {r['status']} | {flag(r['code_generated'])} | "
                     f"{flag(r['execution_succeeded'])} | {flag(r['excel_correct'])} | "
                     f"{flag(r['workflow_rerun_succeeded'])} | {r['elapsed_seconds'] or ''} | "
                     f"{'' if r['repair_loops'] is None else r['repair_loops']} | {r['human_interventions']} | "
                     f"{', '.join(r['interfaces_used'])} | {why} |")
    lines += [
        "",
        "Columns are independent: *Excel correct* judges only the workbook against the template and the "
        "expected answer; the interface requirement (browser / desktop GUI / CLI subprocess) decides BLOCKED "
        "separately. `–` means not applicable or not observable.",
        "",
        "## 3. Failed checks per task",
        "",
    ]
    for r in rows:
        failed = [c for c in r.get("checks") or [] if c["ok"] is False]
        failed += [dict(c, name="rerun: " + c["name"]) for c in r.get("rerun_checks") or [] if c["ok"] is False]
        if failed:
            lines.append(f"**{r['task_id']}**")
            lines += [f"- {c['name']}: `{json.dumps(c['detail'], ensure_ascii=False)[:220]}`" for c in failed]
            lines.append("")
    lines += [
        "## 4. Limits of this run",
        "",
        "- Isolation: the Agent's restricted runner runs as the same Windows account and can read files that "
        "account can read, so source data and answers under `operator/` were readable in principle. The run "
        "scans every script the Agent ran for references to mock internals (`bypass_signals` in each result); "
        "it cannot prove no bypass happened.",
        "- Repair loops are derived from script exit codes (a failing run followed by another run).",
        "- Formula cached values: openpyxl does not calculate formulas, so a missing cached value is recorded "
        "as undecided, and totals are verified independently from the detail rows.",
        "",
    ]
    (run_dir / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (run_dir / "results.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1, default=str),
                                          encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--tasks", default="smoke", help="smoke | all | comma-separated task IDs")
    parser.add_argument("--force", action="store_true", help="rerun tasks already recorded")
    parser.add_argument("--report-only", action="store_true")
    parser.add_argument("--reclassify", action="store_true",
                        help="with --report-only: recompute status from the stored traces and events")
    args = parser.parse_args()
    run_dir = LAB / "runs" / args.run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    meta_path = run_dir / "metadata.json"
    results_path = run_dir / "results.json"
    results = {r["task_id"]: r for r in json.loads(results_path.read_text(encoding="utf-8"))} \
        if results_path.exists() else {}
    if args.report_only:
        if args.reclassify:
            for label, record in results.items():
                folder = run_dir / label
                if (folder / "trace.json").exists():
                    results[label] = reclassify(record, folder)
        report(run_dir, results, json.loads(meta_path.read_text(encoding="utf-8")))
        return 0
    tasks = SMOKE if args.tasks == "smoke" else TASKS if args.tasks == "all" else args.tasks.split(",")
    base, token = agent_web()
    if not meta_path.exists():
        commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True,
                                cwd=REPO).stdout.strip()
        meta = {"run_id": args.run_id, "started": datetime.now().isoformat(timespec="seconds"),
                "repo_commit": commit, "agent_web": base,
                "source_sha256": sha256(LAB / "operator" / "data" / "source.json"),
                "templates": {p.name: sha256(p) for p in sorted((LAB / "templates").glob("*.xlsx"))}}
        try:
            host = json.loads((Path.home() / "AppData/Local/AgenticEngineeringPlatform/preview-0.1.0/host.json")
                              .read_text(encoding="utf-8-sig"))
            models = host.get("models") or {}
            alias = models.get("routing_alias")
            endpoints = (models.get("catalog") or {}).get("endpoints") or []
            meta["model"] = next((e.get("model") for e in endpoints if e.get("alias") == alias), alias)
        except (OSError, ValueError):
            meta["model"] = None
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    help_text = cli_help()
    sap = start_sap()
    try:
        for task in tasks:
            if task in results and results[task]["status"] != "NOT_RUN" and not args.force:
                print(f"{task}: already recorded ({results[task]['status']}), skipped", flush=True)
                continue
            if task == "X03" and results.get("X01", {}).get("status") != "PASS":
                results[task] = not_run(task, "X01 did not pass, so there is no workflow to reuse",
                                        "dependency: X01", status="BLOCKED")
                print("X03: BLOCKED (dependency X01)", flush=True)
            else:
                print(f"{task}: submitting ...", flush=True)
                results[task] = run_task(task, run_dir, base, token, help_text, results)
                r = results[task]
                print(f"{task}: {r['status']} ({r['elapsed_seconds']} s) {r.get('blocked_layer') or ''} "
                      f"{r['failure_reason'] or ''}", flush=True)
                if task == "C04":
                    print("C04-force_exit2: submitting ...", flush=True)
                    results["C04-force_exit2"] = run_task(task, run_dir, base, token, help_text, results,
                                                          "force_exit2")
                    r = results["C04-force_exit2"]
                    print(f"C04-force_exit2: {r['status']} {r['failure_reason'] or ''}", flush=True)
            for other in TASKS:
                results.setdefault(other, not_run(other))
            reset(label=f"{args.run_id}/after-{task}")
            report(run_dir, results, meta)
    finally:
        if sap is not None:
            sap.terminate()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
