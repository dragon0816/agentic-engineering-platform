"""Compare knowledge_v1 runs side by side, offline.

    python benchmarks/knowledge_v1/compare.py <run> [<run> ...] [--out <file.md>]

A run is a folder holding `Q*/result.json` (any path, read-only) or a run ID
under `runs/`. Only the stored results are read: no Agent Web, no reviewer,
no network, and nothing is graded again.

Every table covers only the questions present in all the runs compared, so a
run still in progress can be compared with finished ones; the report says how
many questions each run left out. Transitions are counted between consecutive
runs in the order given, on that shared set.

A status change is an improvement or a regression by this rank:
PASS 3 > INSUFFICIENT_KNOWLEDGE 2 > NEEDS_HUMAN_REVIEW 1 > FAIL = SYSTEM_ERROR 0.
FAIL <-> SYSTEM_ERROR is a change of the same rank.
"""

from __future__ import annotations

import argparse
import collections
import json
import math
import statistics
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
QUESTIONS = HERE / "questions" / "questions.json"
STATUSES = ("PASS", "INSUFFICIENT_KNOWLEDGE", "FAIL", "NEEDS_HUMAN_REVIEW", "SYSTEM_ERROR")
SHORT = {
    "PASS": "PASS",
    "INSUFFICIENT_KNOWLEDGE": "INSUFFICIENT",
    "FAIL": "FAIL",
    "NEEDS_HUMAN_REVIEW": "NEEDS_HUMAN_REVIEW",
    "SYSTEM_ERROR": "SYSTEM_ERROR",
}
ACCEPTABLE = {"PASS", "INSUFFICIENT_KNOWLEDGE"}
RANK = {
    "PASS": 3,
    "INSUFFICIENT_KNOWLEDGE": 2,
    "NEEDS_HUMAN_REVIEW": 1,
    "FAIL": 0,
    "SYSTEM_ERROR": 0,
}
ROUTES = ("direct", "tool", "none")


@dataclass
class Run:
    name: str
    path: Path
    meta: dict[str, Any]
    results: dict[str, dict[str, Any]] = field(default_factory=dict)


def resolve(arg: str, runs_root: Path = HERE / "runs") -> Path:
    """A folder path as given, else a run ID under runs/."""
    path = Path(arg)
    if path.is_dir():
        return path.resolve()
    if (runs_root / arg).is_dir():
        return (runs_root / arg).resolve()
    raise SystemExit(f"no run folder {arg!r} (neither a path nor a run ID under {runs_root})")


def load_run(path: Path) -> Run:
    meta_path = path / "metadata.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.is_file() else {}
    run = Run(path.name, path, meta)
    for result_path in sorted(path.glob("Q*/result.json")):
        try:
            result = json.loads(result_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue  # a result being written right now by a live run
        run.results[str(result.get("id") or result_path.parent.name)] = result
    return run


def load_questions(path: Path = QUESTIONS) -> dict[str, dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {q["id"]: q for q in data["questions"]}


def tags(question: dict[str, Any]) -> dict[str, str]:
    """Market, product family, type and difficulty; foundation questions carry
    technical/topic tags instead, as in run.py's report."""
    return {
        "market": question.get("market", "foundation"),
        "product": question.get("product", question.get("technical", "foundation")),
        "type": question.get("type", "foundation"),
        "difficulty": question.get("difficulty", "foundation"),
    }


def _cell(text: Any, limit: int = 140) -> str:
    flat = " ".join(str(text or "").split()).replace("|", "/")
    return flat if len(flat) <= limit else flat[: limit - 1] + "…"


def _pct(part: int, whole: int) -> str:
    return f"{part} ({round(100 * part / whole)}%)" if whole else "0"


def _p90(values: list[float]) -> float:
    ordered = sorted(values)
    return ordered[max(0, math.ceil(0.9 * len(ordered)) - 1)]


def transitions(
    old: dict[str, dict[str, Any]], new: dict[str, dict[str, Any]], ids: list[str]
) -> dict[str, Any]:
    """Improved / regressed / unchanged counts and every status change."""
    counts: collections.Counter[str] = collections.Counter()
    changes = []
    for qid in ids:
        before, after = old[qid], new[qid]
        if before["status"] == after["status"]:
            counts["unchanged"] += 1
            continue
        delta = RANK.get(after["status"], 0) - RANK.get(before["status"], 0)
        kind = "improved" if delta > 0 else "regressed" if delta < 0 else "changed, same rank"
        counts[kind] += 1
        reason = after.get("why") or (f"was: {before.get('why')}" if before.get("why") else "")
        changes.append(
            {
                "id": qid,
                "kind": kind,
                "old": before["status"],
                "new": after["status"],
                "old_route": before.get("route"),
                "new_route": after.get("route"),
                "reason": reason,
            }
        )
    return {"counts": counts, "changes": changes}


def compare(runs: list[Run], questions: dict[str, dict[str, Any]]) -> str:
    shared = sorted(set.intersection(*(set(r.results) for r in runs)))
    names = [r.name for r in runs]
    lines = [
        "# knowledge_v1 run comparison",
        "",
        "Generated offline by `benchmarks/knowledge_v1/compare.py` from the stored `result.json` files.",
        "",
        "| Run | Started | Commit | Grader | Questions | Compared | Left out |",
        "|---|---|---|---|---|---|---|",
    ]
    for run in runs:
        graders = sorted({str(r.get("grader")) for r in run.results.values()})
        lines.append(
            f"| {run.name} | {run.meta.get('started', '')} | `{str(run.meta.get('commit', ''))[:7]}` | "
            f"{', '.join(graders)} | {len(run.results)} | {len(shared)} | "
            f"{len(run.results) - len(shared)} |"
        )
    lines.append("")
    if any(len(r.results) != len(shared) for r in runs):
        lines += [f"Only the {len(shared)} questions present in every run are compared below.", ""]
    if not shared:
        return "\n".join(lines + ["No question is present in every run.", ""])
    picked = [{qid: run.results[qid] for qid in shared} for run in runs]
    meta = {qid: tags(questions.get(qid, {})) for qid in shared}

    # Status totals.
    lines += [
        "## Status",
        "",
        "| Status | " + " | ".join(names) + " |",
        "|---|" + "---|" * len(runs),
    ]
    status_counts = [collections.Counter(r["status"] for r in p.values()) for p in picked]
    lines.append(
        "| **acceptable** | "
        + " | ".join(
            f"**{_pct(c['PASS'] + c['INSUFFICIENT_KNOWLEDGE'], len(shared))}**"
            for c in status_counts
        )
        + " |"
    )
    for status in STATUSES:
        lines.append(f"| {status} | " + " | ".join(str(c[status]) for c in status_counts) + " |")
    lines.append("")

    # Route x status, one table per run.
    lines += [
        "## Route × status",
        "",
        "| Run | Route | Questions | " + " | ".join(SHORT[s] for s in STATUSES) + " | PASS rate |",
        "|---|---|---|" + "---|" * (len(STATUSES) + 1),
    ]
    for name, results in zip(names, picked, strict=True):
        by_route: dict[str, collections.Counter[str]] = collections.defaultdict(collections.Counter)
        for result in results.values():
            by_route[result.get("route") or "none"][result["status"]] += 1
        for route in [*ROUTES, *sorted(set(by_route) - set(ROUTES))]:
            counts = by_route.get(route, collections.Counter())
            total = sum(counts.values())
            rate = f"{round(100 * counts['PASS'] / total)}%" if total else "–"
            lines.append(
                f"| {name} | {route} | {total} | "
                + " | ".join(str(counts[s]) for s in STATUSES)
                + f" | {rate} |"
            )
    lines.append("")

    # Breakdowns by question tag: acceptable and PASS per run.
    for key, title in (
        ("market", "market"),
        ("product", "product family"),
        ("type", "question type"),
        ("difficulty", "difficulty"),
    ):
        groups = sorted({m[key] for m in meta.values()})
        header = "| " + title + " | n | " + " | ".join(f"{n} acc / PASS" for n in names)
        lines += [
            f"## By {title}",
            "",
            header + (" | Δ acc |" if len(runs) > 1 else " |"),
            "|---|---|" + "---|" * (len(runs) + (1 if len(runs) > 1 else 0)),
        ]
        for group in groups:
            ids = [q for q in shared if meta[q][key] == group]
            cells, accs = [], []
            for results in picked:
                acc = sum(1 for q in ids if results[q]["status"] in ACCEPTABLE)
                accs.append(acc)
                cells.append(f"{acc} / {sum(1 for q in ids if results[q]['status'] == 'PASS')}")
            delta = f" | {accs[-1] - accs[0]:+d}" if len(runs) > 1 else ""
            lines.append(f"| {group} | {len(ids)} | " + " | ".join(cells) + delta + " |")
        lines.append("")

    # Gap types.
    gap_counts = [
        collections.Counter(r.get("gap") for r in p.values() if r.get("gap")) for p in picked
    ]
    gaps = sorted(set().union(*gap_counts))
    lines += [
        "## Gap types",
        "",
        "| Gap | " + " | ".join(names) + " |",
        "|---|" + "---|" * len(runs),
    ]
    lines += [f"| {gap} | " + " | ".join(str(c[gap]) for c in gap_counts) + " |" for gap in gaps]
    lines.append("")

    # Reviewer verdicts.
    lines += [
        "## Reviewer verdicts",
        "",
        "Over answers the reviewer read (citations all verified); overreach = at least one claim listed "
        "as going beyond the passages.",
        "",
        "| Run | Reviewed | Verdict given | Supported | Reasonable | Confidence high / medium / low "
        "| With overreach | Overreach items per answer |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for name, results in zip(names, picked, strict=True):
        reviews = [r["review"] for r in results.values() if isinstance(r.get("review"), dict)]
        given = [v for v in reviews if v.get("ok")]
        confidence = collections.Counter(str(v.get("confidence")) for v in given)
        reaching = [len(v.get("overreach") or []) for v in given]
        mean_items = f"{statistics.mean(reaching):.1f}" if reaching else "–"
        lines.append(
            f"| {name} | {len(reviews)} | {len(given)} | "
            f"{_pct(sum(1 for v in given if v.get('supported')), len(given))} | "
            f"{_pct(sum(1 for v in given if v.get('reasonable')), len(given))} | "
            f"{confidence['high']} / {confidence['medium']} / {confidence['low']} | "
            f"{_pct(sum(1 for n in reaching if n), len(given))} | {mean_items} |"
        )
    lines.append("")

    # Latency per route.
    lines += [
        "## Latency (seconds)",
        "",
        "| Run | Route | n | median | p90 |",
        "|---|---|---|---|---|",
    ]
    for name, results in zip(names, picked, strict=True):
        by_route: dict[str, list[float]] = collections.defaultdict(list)
        for result in results.values():
            if isinstance(result.get("seconds"), int | float):
                by_route[result.get("route") or "none"].append(float(result["seconds"]))
                by_route["all"].append(float(result["seconds"]))
        for route in [*ROUTES, "all"]:
            values = by_route.get(route)
            if values:
                lines.append(
                    f"| {name} | {route} | {len(values)} | {statistics.median(values):.1f} | "
                    f"{_p90(values):.1f} |"
                )
    lines.append("")

    # Citations.
    lines += [
        "## Citations",
        "",
        "Checked answers are those whose citations were checked against the Vault.",
        "",
        "| Run | Checked answers | Citations | Per checked answer | Verified in the Vault |",
        "|---|---|---|---|---|",
    ]
    for name, results in zip(names, picked, strict=True):
        checked = [r["citations"] for r in results.values() if isinstance(r.get("citations"), list)]
        total = sum(len(c) for c in checked)
        ok = sum(1 for c in checked for item in c if item.get("ok"))
        per = f"{total / len(checked):.1f}" if checked else "–"
        lines.append(f"| {name} | {len(checked)} | {total} | {per} | {_pct(ok, total)} |")
    lines.append("")

    # Question-level transitions between consecutive runs.
    for index in range(1, len(runs)):
        old_name, new_name = names[index - 1], names[index]
        moved = transitions(picked[index - 1], picked[index], shared)
        counts = moved["counts"]
        lines += [
            f"## Transitions {old_name} → {new_name}",
            "",
            f"Improved {counts['improved']}, regressed {counts['regressed']}, "
            f"unchanged {counts['unchanged']}"
            + (
                f", changed at the same rank {counts['changed, same rank']}"
                if counts["changed, same rank"]
                else ""
            )
            + f" (of {len(shared)}).",
            "",
        ]
        if moved["changes"]:
            lines += [
                "| Question | Change | Old → new | Route | Tags | Reason (new run) |",
                "|---|---|---|---|---|---|",
            ]
            for change in moved["changes"]:
                route = (
                    change["new_route"]
                    if change["old_route"] == change["new_route"]
                    else f"{change['old_route']} → {change['new_route']}"
                )
                tag = meta[change["id"]]
                lines.append(
                    f"| {change['id']} | {change['kind']} | {SHORT[change['old']]} → "
                    f"{SHORT[change['new']]} | {route} | {_cell(tag['market'], 30)}; "
                    f"{_cell(tag['type'], 20)} | {_cell(change['reason'])} |"
                )
            lines.append("")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("runs", nargs="+", help="run folders (any path) or run IDs under runs/")
    parser.add_argument("--out", help="write the Markdown here instead of printing it")
    args = parser.parse_args(argv)
    runs = [load_run(resolve(arg)) for arg in args.runs]
    seen: collections.Counter[str] = collections.Counter()
    for run in runs:  # the same run ID from two checkouts stays distinguishable
        seen[run.name] += 1
        if seen[run.name] > 1:
            run.name = f"{run.name} ({seen[run.name]})"
    markdown = compare(runs, load_questions())
    if args.out:
        Path(args.out).write_text(markdown, encoding="utf-8")
        print(f"wrote {args.out}")
    else:
        sys.stdout.write(markdown)
    return 0


if __name__ == "__main__":
    sys.exit(main())
