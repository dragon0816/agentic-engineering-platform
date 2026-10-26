"""multi_agent_v1 runner: the seven baseline scenarios of the multi-agent
Phase 0 review (§12), in fake-model mode (CI) or live mode (the owner).

    .venv\\Scripts\\python.exe benchmarks\\multi_agent_v1\\run.py --mode fake
    .venv\\Scripts\\python.exe benchmarks\\multi_agent_v1\\run.py --mode fake --repeat 5
    .venv\\Scripts\\python.exe benchmarks\\multi_agent_v1\\run.py --mode live --run-id live-001 \\
        --url http://127.0.0.1:<port> --token <page token>

Results go to `runs/<run_id>/`: `results.jsonl` (one line per scenario and
repetition), `summary.json` (pass counts and latency p50/p95 per scenario and
route) and `report.md`. The exit code is 0 only when every fake check passed.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
for path in (HERE, ROOT / "src"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

SCENARIO_FILE = HERE / "scenarios.json"


def scenarios() -> list[dict[str, Any]]:
    data = json.loads(SCENARIO_FILE.read_text(encoding="utf-8"))
    return list(data["scenarios"])


def percentile(values: list[float], share: float) -> float | None:
    """Nearest-rank percentile; None for no values."""
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, math.ceil(share * len(ordered)))
    return ordered[rank - 1]


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Per scenario: runs, passes, and per route the latency p50/p95 and the
    mean of each count measurement."""
    out: dict[str, Any] = {}
    for row in rows:
        entry = out.setdefault(row["scenario"], {"runs": 0, "passed": 0, "routes": {}})
        entry["runs"] += 1
        entry["passed"] += bool(row["passed"])
        for route, metrics in (row.get("routes") or {}).items():
            bucket = entry["routes"].setdefault(route, {"latency_s": [], "counts": {}})
            if isinstance(metrics.get("latency_s"), int | float):
                bucket["latency_s"].append(float(metrics["latency_s"]))
            for key, value in metrics.items():
                if (
                    key != "latency_s"
                    and isinstance(value, int | float)
                    and not isinstance(value, bool)
                ):
                    bucket["counts"].setdefault(key, []).append(float(value))
    for entry in out.values():
        for route, bucket in entry["routes"].items():
            latencies = bucket.pop("latency_s")
            counts = bucket.pop("counts")
            entry["routes"][route] = {
                "latency_p50_s": percentile(latencies, 0.5),
                "latency_p95_s": percentile(latencies, 0.95),
                **{key: round(sum(values) / len(values), 3) for key, values in counts.items()},
            }
    return out


def report(run_id: str, mode: str, summary: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    lines = [
        f"# multi_agent_v1 run `{run_id}` ({mode})",
        "",
        "Thresholds are set only after the live baseline (review §12); this report "
        "records measurements.",
        "",
        "| Scenario | Passed | Route | p50 s | p95 s | LLM calls | Delegations | "
        "Policy refusals | Tool failures |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for name, entry in summary.items():
        for route, metrics in entry["routes"].items():
            lines.append(
                f"| {name} | {entry['passed']}/{entry['runs']} | {route} | "
                f"{metrics.get('latency_p50_s')} | {metrics.get('latency_p95_s')} | "
                f"{metrics.get('llm_calls')} | {metrics.get('delegations')} | "
                f"{metrics.get('policy_refusals')} | {metrics.get('tool_failures')} |"
            )
    failed = [
        (row["scenario"], check)
        for row in rows
        for check in row.get("checks") or ()
        if check.get("passed") is not True
    ]
    lines += ["", "## Checks not passed", ""]
    lines += [f"- {name}: {check['name']} (got {check.get('actual')!r})" for name, check in failed]
    if not failed:
        lines.append("- none")
    return "\n".join(lines) + "\n"


def run_fake(selected: list[str], repeat: int) -> list[dict[str, Any]]:
    from scenarios_fake import SCENARIOS

    rows: list[dict[str, Any]] = []
    for index in range(repeat):
        for name in selected:
            with tempfile.TemporaryDirectory(prefix=f"ma1-{name}-") as folder:
                started = time.perf_counter()
                try:
                    row = SCENARIOS[name](Path(folder)).as_dict()
                except Exception as error:  # noqa: BLE001 - a broken scenario is a failed one
                    row = {
                        "scenario": name,
                        "mode": "fake",
                        "passed": False,
                        "checks": [
                            {
                                "name": "the scenario ran",
                                "passed": False,
                                "actual": f"{type(error).__name__}: {error}"[:500],
                            }
                        ],
                        "routes": {},
                    }
                row["repetition"] = index + 1
                row["wall_s"] = round(time.perf_counter() - started, 3)
                rows.append(row)
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--mode", choices=("fake", "live"), default="fake")
    parser.add_argument("--scenarios", default="all", help="comma-separated ids or 'all'")
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--out", default=str(HERE / "runs"))
    parser.add_argument("--url", default=None, help="live: Agent Web address")
    parser.add_argument("--token", default=None, help="live: the page token")
    parser.add_argument(
        "--workspace", default=None, help="live: a folder the Agent may write (coding tasks)"
    )
    arguments = parser.parse_args(argv)
    known = [item["id"] for item in scenarios()]
    selected = known if arguments.scenarios == "all" else arguments.scenarios.split(",")
    unknown = [name for name in selected if name not in known]
    if unknown:
        parser.error(f"unknown scenario(s): {', '.join(unknown)}")
    run_id = arguments.run_id or f"{arguments.mode}-{time.strftime('%Y%m%d-%H%M%S')}"
    if arguments.mode == "fake":
        rows = run_fake(selected, max(1, arguments.repeat))
    else:
        from live import run_live

        if not arguments.url or not arguments.token:
            parser.error("live mode needs --url and --token")
        rows = run_live(
            [item for item in scenarios() if item["id"] in selected],
            arguments.url,
            arguments.token,
            Path(arguments.workspace) if arguments.workspace else None,
            max(1, arguments.repeat),
        )
    target = Path(arguments.out) / run_id
    target.mkdir(parents=True, exist_ok=True)
    with (target / "results.jsonl").open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
    summary = summarize(rows)
    (target / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (target / "report.md").write_text(report(run_id, arguments.mode, summary, rows), "utf-8")
    passed = sum(1 for row in rows if row["passed"])
    print(f"{passed}/{len(rows)} scenario run(s) passed -> {target}")
    if arguments.mode == "live":
        return 0  # live runs record measurements; thresholds come after the baseline
    return 0 if passed == len(rows) else 1


if __name__ == "__main__":
    sys.exit(main())
