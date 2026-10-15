"""Compare harness strategies from the local telemetry (gap plan P1-3, 2026-10-09).

Groups runs by `strategy_id` (and optionally `run_kind`, `skill_id`) and reports
what telemetry can actually support: run count, success rate, p50/p95 latency,
model calls per run, token-report coverage, how many runs retried, the share of
runs that never completed, and the mean dwell time per state. Nothing here is
a correctness claim; benchmark validators decide that.
"""

from __future__ import annotations

import json
import sqlite3
from collections import defaultdict
from pathlib import Path
from typing import Any

GROUPS = ("strategy_id", "run_kind", "skill_id")


def _percentile(values: list[float], share: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round(share * (len(ordered) - 1))))
    return round(ordered[index], 1)


def compare(
    path: Path,
    *,
    by: tuple[str, ...] = ("strategy_id", "run_kind"),
    since: str | None = None,
    until: str | None = None,
) -> list[dict[str, Any]]:
    if any(item not in GROUPS for item in by):
        raise ValueError(f"group by {', '.join(GROUPS)}")
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        clauses, args = ["1 = 1"], []
        if since:
            clauses.append("started_at >= ?")
            args.append(since)
        if until:
            clauses.append("started_at <= ?")
            args.append(until)
        runs = conn.execute(
            "SELECT run_id, "
            + ", ".join(by)
            + ", status, ended_at, summary FROM runs WHERE "
            + " AND ".join(clauses),
            args,
        ).fetchall()
        retried = {
            row[0]
            for row in conn.execute(
                "SELECT DISTINCT run_id FROM events WHERE event_type = 'retry.scheduled'"
            )
        }
        dwell_rows = conn.execute(
            "SELECT run_id, state, record FROM events WHERE event_type IN "
            "('state.exited', 'tool.completed') AND state IS NOT NULL"
        ).fetchall()
    finally:
        conn.close()
    dwell: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for run_id, state, record in dwell_rows:
        duration = json.loads(record).get("attributes", {}).get("duration_ms")
        if isinstance(duration, int | float):
            dwell[run_id].append((state, float(duration)))
    groups: dict[tuple[Any, ...], list[tuple[Any, ...]]] = defaultdict(list)
    for row in runs:
        groups[tuple(row[1 : 1 + len(by)])].append(row)
    report = []
    for key, rows in sorted(groups.items(), key=lambda item: str(item[0])):
        summaries = [json.loads(row[-1] or "{}") for row in rows]
        durations = [
            float(s["duration_ms"])
            for s in summaries
            if isinstance(s.get("duration_ms"), int | float)
        ]
        llm = [int(s.get("llm_calls") or 0) for s in summaries]
        reported = sum(1 for s in summaries if s.get("input_tokens") is not None)
        states: dict[str, list[float]] = defaultdict(list)
        for row in rows:
            for state, duration in dwell.get(row[0], []):
                states[state].append(duration)
        complete = [row for row in rows if row[-2] is not None]
        succeeded = sum(1 for row in complete if row[1 + len(by)] == "succeeded")
        report.append(
            {
                **dict(zip(by, key, strict=True)),
                "runs": len(rows),
                "incomplete": len(rows) - len(complete),
                "success_rate": round(succeeded / len(complete), 3) if complete else None,
                "p50_ms": _percentile(durations, 0.5),
                "p95_ms": _percentile(durations, 0.95),
                "llm_calls_per_run": round(sum(llm) / len(llm), 2) if llm else None,
                "token_coverage": round(reported / len(rows), 3) if rows else None,
                "retried_runs": sum(1 for row in rows if row[0] in retried),
                "dwell_ms": {
                    state: round(sum(v) / len(v), 1) for state, v in sorted(states.items())
                },
            }
        )
    return report


def markdown(rows: list[dict[str, Any]], by: tuple[str, ...]) -> str:
    head = [
        *by,
        "runs",
        "incomplete",
        "success",
        "p50 ms",
        "p95 ms",
        "LLM/run",
        "tokens",
        "retried",
    ]
    lines = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                str(v)
                for v in (
                    *(row[k] for k in by),
                    row["runs"],
                    row["incomplete"],
                    row["success_rate"],
                    row["p50_ms"],
                    row["p95_ms"],
                    row["llm_calls_per_run"],
                    row["token_coverage"],
                    row["retried_runs"],
                )
            )
            + " |"
        )
    return "\n".join(lines)
