"""authoring_v1: can Claude Code, Codex and Copilot build assets AEP can use?

External authoring X6 (docs/phases/EXTERNAL_AUTHORING.md, owner 2026-10-08).
Each agent works headless in its own project with only the AEP creator
skills and the `aep` MCP server. It gets a PUBLIC task description, never
the grader's values. While it works, this operator (not the agent) approves
what it submitted, as the owner would in Agent Web. Afterwards each
installed asset is checked as the Host would use it: the Workflow is run
from its installed file with hidden values and its output compared; the
Skill must load beside every other installed Skill and point at the
installed Workflow.

Every agent gets its own sandbox Host: a copy of the live host.json whose
workspace is under this run, with the live assets, membership and grants
copied in. The live Host's installs are never touched.

    .venv\\Scripts\\python.exe benchmarks\\authoring_v1\\run.py --run-id r001 --agents claude-code
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "src"))

from agent.skills import SkillManifest, SkillRegistry  # noqa: E402
from common.assets import WorkflowManifest  # noqa: E402
from host_runtime.chat_authoring import ChatCandidate  # noqa: E402
from host_runtime.external_authoring import ExternalAuthoring, build, connect  # noqa: E402

LIVE = Path(os.environ.get("LOCALAPPDATA", "")) / "AgenticEngineeringPlatform" / "preview-0.1.0"
SESSION_SECONDS = 1500
WORKSPACE_COPY = ("membership.json", "grants.json", "authorization.json", "agent-persona.json",
                  "workflow-settings.json")


# -- tasks -----------------------------------------------------------------------


@dataclass
class Task:
    task_id: str
    prompt: str
    prepare: Callable[[Path], None]
    grade: Callable[[ExternalAuthoring, Path], dict[str, Any]]


def _write_csv(path: Path, rows: list[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        csv.writer(handle).writerows(rows)


EXAMPLE_ITEMS = [["category", "item", "amount"], ["travel", "taxi", "120.50"],
                 ["meals", "lunch", "85"], ["travel", "train", "300"],
                 ["office", "paper", "42.25"], ["meals", "dinner", "210.10"]]
HIDDEN_ITEMS = [["category", "item", "amount"], ["zeta", "a", "1.005"], ["alpha", "b", "10"],
                ["alpha", "c", "2.5"], ["mid", "d", "0"], ["zeta", "e", "3.10"],
                ["alpha", "f", "-1.25"]]


def _totals(rows: list[list[str]]) -> list[list[str]]:
    # Exact sums rounded half up, so 4.105 is 4.11 whatever binary floats say.
    sums: dict[str, Decimal] = {}
    for category, _, amount in rows[1:]:
        sums[category] = sums.get(category, Decimal(0)) + Decimal(amount)
    cent = Decimal("0.01")
    return [["category", "total"]] + [
        [c, str(sums[c].quantize(cent, rounding=ROUND_HALF_UP))] for c in sorted(sums)]


def _installed(authoring: ExternalAuthoring, name: str) -> WorkflowManifest | None:
    found = [m for m in authoring.chat.installed_workflows()
             if m.metadata.identity.name == name and m.metadata.lifecycle == "published"]
    return max(found, key=lambda m: tuple(int(x) for x in m.metadata.identity.version.split(".")),
               default=None)


def _run_installed(authoring: ExternalAuthoring, manifest: WorkflowManifest,
                   arguments: dict[str, Any]) -> dict[str, Any]:
    now = datetime.now(UTC).isoformat()
    candidate = ChatCandidate(candidate_id="grader", actor=authoring.actor, title="grader",
                              created_at=now, updated_at=now, draft=manifest)
    return authoring.chat.execute(authoring.actor, candidate, arguments, "authoring-v1-grader")


def _workspace_of(manifest: WorkflowManifest) -> Path | None:
    for step in manifest.steps:
        request = getattr(step, "inputs", {}).get("request")
        value = getattr(request, "value", None)
        if isinstance(value, dict) and value.get("workspace"):
            return Path(str(value["workspace"]))
    return None


def prepare_w1(folder: Path) -> None:
    _write_csv(folder / "workspace" / "input" / "expenses.csv", EXAMPLE_ITEMS)


def grade_w1(authoring: ExternalAuthoring, folder: Path) -> dict[str, Any]:
    manifest = _installed(authoring, "csv-category-totals")
    checks: dict[str, Any] = {"installed": manifest is not None}
    if manifest is None:
        return checks
    params = {p.name for p in manifest.parameters}
    checks["parameters"] = {"input_file", "output_name"} <= params
    workspace = _workspace_of(manifest)
    checks["workspace_fixed"] = workspace is not None
    if workspace is None:
        return checks
    hidden = workspace / "input" / "grader-hidden.csv"
    _write_csv(hidden, HIDDEN_ITEMS)
    result = _run_installed(authoring, manifest,
                            {"input_file": str(hidden), "output_name": "grader-check"})
    checks["run_succeeded"] = result.get("status") == "succeeded"
    output = workspace / "output" / "grader-check.csv"
    checks["output_written"] = output.is_file()
    if output.is_file():
        with output.open(encoding="utf-8-sig", newline="") as handle:
            got = [row for row in csv.reader(handle) if row]
        checks["output_correct"] = got == _totals(HIDDEN_ITEMS)
        checks["output_seen"] = got[:8]
    return checks


W1 = Task("W1", """\
Build an AEP Workflow with the aep-workflow-creator skill.

Name it exactly `csv-category-totals`. It takes two run parameters:
- `input_file` (kind "file"): the absolute path of a CSV with the columns category,item,amount;
- `output_name` (kind "text"): a file name without extension.
It writes `output/<output_name>.csv` with the header `category,total`, one row per category
sorted by category name, each total being the sum of `amount` with two decimals (e.g. 12.50).

Use coding/run-python with this fixed workspace folder: {workspace}
An example input is at {workspace}\\input\\expenses.csv.

Check it, submit it, run it once with the example (input_file = that path, output_name =
"example"), fix it until the run succeeds, then ask to install it. Runs and installs wait for
the owner's approval; poll aep_status until they are decided. Finish when the install is
approved, and say the installed version.
""", prepare_w1, grade_w1)


SALES = [["date", "region", "amount"], ["2026-01-03", "north", "100"],
         ["2026-01-15", "south", "40"], ["2026-02-01", "north", "250"],
         ["2026-02-10", "east", "75"], ["2026-02-28", "south", "300"],
         ["2026-03-05", "north", "20"], ["2026-03-31", "east", "500"]]


def prepare_w2(folder: Path) -> None:
    _write_csv(folder / "workspace" / "input" / "sales.csv", SALES)


def _window(start: str, end: str, minimum: int) -> dict[str, int]:
    totals: dict[str, int] = {}
    for day, region, amount in SALES[1:]:
        if start <= day <= end and int(amount) >= minimum:
            totals[region] = totals.get(region, 0) + int(amount)
    return dict(sorted(totals.items()))


def grade_w2(authoring: ExternalAuthoring, folder: Path) -> dict[str, Any]:
    manifest = _installed(authoring, "sales-window-summary")
    checks: dict[str, Any] = {"installed": manifest is not None}
    if manifest is None:
        return checks
    kinds = {p.name: p.kind for p in manifest.parameters}
    checks["parameters"] = (kinds.get("from_date") == "date" and kinds.get("to_date") == "date"
                            and kinds.get("min_amount") == "integer")
    workspace = _workspace_of(manifest)
    checks["workspace_fixed"] = workspace is not None
    if workspace is None:
        return checks
    result = _run_installed(authoring, manifest, {
        "from_date": "2026-02-01", "to_date": "2026-03-31", "min_amount": 50})
    checks["run_succeeded"] = result.get("status") == "succeeded"
    output = workspace / "output" / "summary-2026-02-01-2026-03-31.json"
    checks["output_written"] = output.is_file()
    if output.is_file():
        try:
            got = json.loads(output.read_text(encoding="utf-8-sig"))
        except ValueError:
            got = None
        checks["output_correct"] = got == _window("2026-02-01", "2026-03-31", 50)
        checks["output_seen"] = got
    return checks


W2 = Task("W2", """\
Build an AEP Workflow with the aep-workflow-creator skill.

Name it exactly `sales-window-summary`. The sales file is fixed: {workspace}\\input\\sales.csv
(columns date (YYYY-MM-DD), region, amount (integer)). Run parameters:
- `from_date` and `to_date` (kind "date", inclusive),
- `min_amount` (kind "integer"): only rows with amount >= min_amount count.
It writes `output/summary-<from_date>-<to_date>.json`: a JSON object mapping each region with
at least one counted row to the sum of its counted amounts (an integer), keys sorted.

Use coding/run-python with this fixed workspace folder: {workspace}

Check it, submit it, run it once with from_date 2026-01-01, to_date 2026-01-31, min_amount 0,
fix it until the run succeeds, then ask to install it. Runs and installs wait for the owner's
approval; poll aep_status until they are decided. Finish when the install is approved.
""", prepare_w2, grade_w2)


def grade_s1(authoring: ExternalAuthoring, folder: Path) -> dict[str, Any]:
    skills_dir = authoring.chat.skills_dir
    assert skills_dir is not None
    found = [m for m in _skills(skills_dir) if m.metadata.identity.name == "csv-totals"]
    checks: dict[str, Any] = {"installed": bool(found)}
    if not found:
        return checks
    skill = found[0]
    registry = SkillRegistry()
    try:
        for manifest in _skills(skills_dir):
            registry.register(manifest)
        checks["loads_with_others"] = True
    except ValueError:
        checks["loads_with_others"] = False
    workflow = _installed(authoring, "csv-category-totals")
    targets = {(c.target.namespace, c.target.name, c.target.version) for c in skill.commands}
    checks["targets_installed_workflow"] = workflow is not None and (
        workflow.metadata.identity.namespace, workflow.metadata.identity.name,
        workflow.metadata.identity.version) in targets
    checks["alias"] = skill.alias == "csv_totals"
    checks["default_command"] = skill.default_command is not None
    text = skill.instructions.lower()
    checks["instructions_ask_inputs"] = "input_file" in text and "output_name" in text
    checks["selector_hint"] = bool(skill.selector_hint)
    return checks


def _skills(folder: Path) -> list[SkillManifest]:
    from host_runtime.skill_authoring import installed_skills

    return installed_skills(folder)


S1 = Task("S1", """\
Build an AEP Skill with the aep-skill-creator skill.

Name it exactly `csv-totals`, alias `csv_totals`. It lets the AEP Agent total a CSV by
category with the installed Workflow `csv-category-totals` (find its exact version in
aep_catalog). Give it one command bound to that Workflow and make it the default command.
Its instructions must tell the Agent to ask for the CSV path (`input_file`) and the result
name (`output_name`) when the person did not give them, and to report the output file.
Add a selector_hint with English and Chinese keywords.

Check it, submit it, ask to install it, and poll aep_status until the owner decides.
""", lambda folder: None, grade_s1)

TASKS = {task.task_id: task for task in (W1, W2, S1)}


# -- sandbox and agents -------------------------------------------------------------


def sandbox(run: Path, agent: str) -> Path:
    """A Host of our own: the live configuration, with its workspace here."""
    root = run / agent
    workspace = root / "host-workspace"
    if not (workspace / "assets").is_dir():
        shutil.copytree(LIVE / "workspace" / "assets", workspace / "assets")
        for name in WORKSPACE_COPY:
            if (LIVE / "workspace" / name).is_file():
                shutil.copy2(LIVE / "workspace" / name, workspace / name)
    config = json.loads((LIVE / "host.json").read_text(encoding="utf-8-sig"))
    config["workspace_root"] = str(workspace)
    if config.get("coding"):
        roots = list(config["coding"].get("workspace_roots") or [])
        config["coding"]["workspace_roots"] = [*roots, str(root / "tasks")]
    config.pop("telegram", None)
    path = root / "host.json"
    path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def agent_command(agent: str, project: Path, config: Path, prompt: str) -> list[str] | None:
    if agent == "claude-code":
        exe = shutil.which("claude")
        return None if exe is None else [
            exe, "-p", prompt, "--mcp-config", str(project / ".mcp.json"), "--strict-mcp-config",
            "--allowedTools", "mcp__aep", "Read", "Write", "Edit", "Glob", "Grep", "Skill",
            "--permission-mode", "acceptEdits", "--output-format", "json"]
    if agent == "codex":
        exe = shutil.which("codex")
        if exe is None:
            return None
        args = ["-m", "host_runtime.cli", "mcp", "--config", str(config), "--agent", "codex"]
        return [exe, "exec", "--skip-git-repo-check", "--sandbox", "workspace-write",
                "-c", f"mcp_servers.aep.command={json.dumps(sys.executable)}",
                "-c", f"mcp_servers.aep.args={json.dumps(args)}", prompt]
    exe = shutil.which("copilot")
    if exe is None:
        return None
    mcp = {"mcpServers": {"aep": {"type": "local", "command": sys.executable, "tools": ["*"],
                                  "args": ["-m", "host_runtime.cli", "mcp", "--config",
                                           str(config), "--agent", "copilot"]}}}
    return [exe, "-p", prompt, "--additional-mcp-config", json.dumps(mcp),
            "--allow-tool", "aep", "--allow-tool", "write"]


class Operator:
    """Approves what the agent submitted, as the owner's button would."""

    def __init__(self, authoring: ExternalAuthoring, agent: str, log: Path) -> None:
        self.authoring, self.source, self.log = authoring, f"external:{agent}", log
        self.stop = threading.Event()

    def sweep(self) -> None:
        chat = self.authoring.chat
        for item in chat.approvals(self.authoring.actor):
            if item.source != self.source:
                continue
            decided = chat.decide(item.approval_id, self.authoring.actor, True)
            with self.log.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps({"at": datetime.now(UTC).isoformat(),
                                         "approval_id": item.approval_id, "kind": item.kind,
                                         "workflow": item.workflow, "status": decided.status},
                                        ensure_ascii=False) + "\n")

    def loop(self) -> None:
        while not self.stop.wait(4):
            try:
                self.sweep()
            except Exception as error:  # noqa: BLE001 - logged, the loop goes on
                with self.log.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps({"operator_error": type(error).__name__}) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--agents", default="claude-code")
    parser.add_argument("--tasks", default="W1,W2,S1")
    parser.add_argument("--grade-only", action="store_true",
                        help="grade what an earlier session of this run installed")
    args = parser.parse_args()
    run = HERE / "runs" / args.run_id
    run.mkdir(parents=True, exist_ok=True)
    results = run / "results.jsonl"
    for agent in args.agents.split(","):
        config = sandbox(run, agent)
        project = run / agent / "project"
        project.mkdir(parents=True, exist_ok=True)
        connect(agent, project, config, sys.executable)
        if agent_command(agent, project, config, "") is None and not args.grade_only:
            for task_id in args.tasks.split(","):
                record = {"agent": agent, "task": task_id, "status": "NOT_RUN",
                          "reason": f"{agent} is not installed"}
                print(f"[{agent}] {task_id}: NOT_RUN", flush=True)
                with results.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            continue
        print(f"[{agent}] building the sandbox host", flush=True)
        authoring = build(config, "operator")
        operator = Operator(authoring, agent, run / agent / "approvals.jsonl")
        for task_id in args.tasks.split(","):
            task = TASKS[task_id]
            folder = run / agent / "tasks" / task_id
            folder.mkdir(parents=True, exist_ok=True)
            if not args.grade_only:
                task.prepare(folder)
            prompt = task.prompt.format(workspace=folder / "workspace")
            command = agent_command(agent, project, config, prompt)
            record: dict[str, Any] = {"agent": agent, "task": task_id}
            if args.grade_only:
                checks = task.grade(authoring, folder)
                passed = all(v is True for k, v in checks.items() if k != "output_seen")
                record.update(checks=checks, status="PASS" if passed else "FAIL",
                              note="graded again after a runner fault")
            elif command is None:
                record.update(status="NOT_RUN", reason=f"{agent} is not installed")
            else:
                operator.stop.clear()
                watcher = threading.Thread(target=operator.loop, daemon=True)
                watcher.start()
                started = time.monotonic()
                print(f"[{agent}] {task_id} started", flush=True)
                try:
                    done = subprocess.run(command, cwd=project, capture_output=True,
                                          timeout=SESSION_SECONDS, encoding="utf-8",
                                          errors="replace", stdin=subprocess.DEVNULL)
                    timed_out = False
                    (folder / "transcript.txt").write_text(
                        done.stdout + "\n--- stderr ---\n" + done.stderr, encoding="utf-8")
                except subprocess.TimeoutExpired:
                    timed_out = True
                operator.stop.set()
                watcher.join()
                operator.sweep()
                record["seconds"] = round(time.monotonic() - started)
                checks = task.grade(authoring, folder)
                record["checks"] = checks
                passed = all(v is True for k, v in checks.items() if k != "output_seen")
                record["status"] = ("PASS" if passed else
                                    "TIMEOUT" if timed_out else "FAIL")
            print(f"[{agent}] {task_id}: {record['status']}", flush=True)
            with results.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
