"""Replay a JEV shadow log: what each threshold and list length would have done.

Usage:
    python -m evaluation.jev_shadow_report <workspace>/jev-shadow.jsonl

Each conversation turn is paired with the shadow decision for the same trace.
The tool the model called first is the reference: a narrowed list that still
contains it agrees; one that hides it would have taken the right tool away.
Turns where the model called no tool are counted separately (narrowing them
cost nothing visible but saved nothing either). The log holds no message text.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

THRESHOLDS = (0.5, 0.6, 0.7, 0.8, 0.9, 0.95)
LIST_LENGTHS = (1, 2, 3, 4)


def load(path: Path) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    shadows: dict[str, dict[str, Any]] = {}
    turns: dict[str, dict[str, Any]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        target = shadows if record.get("kind") == "shadow" else turns
        target[str(record.get("trace_id"))] = record
    return [(shadows[key], turns[key]) for key in shadows if key in turns]


def narrowed(shadow: dict[str, Any], threshold: float, length: int) -> list[str] | None:
    """The list the adapter would have kept, or None for the whole catalogue."""
    probabilities: dict[str, float] = shadow.get("probabilities") or {}
    if not probabilities:
        return None
    ranked = sorted(probabilities.items(), key=lambda item: -item[1])
    if length == 1:
        top, _ = ranked[0]
        confidence = shadow.get("choice_confidence")
        if top == "catalog" or confidence is None or confidence < threshold:
            return None
        return [top]
    kept: list[str] = []
    total = 0.0
    for name, probability in ranked:
        if name == "catalog":
            return None
        kept.append(name)
        total += probability
        if total >= threshold or len(kept) >= length:
            break
    return kept if total >= threshold else None


def _percentile(values: Sequence[float], share: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(share * len(ordered)))]


def report(pairs: Iterable[tuple[dict[str, Any], dict[str, Any]]]) -> dict[str, Any]:
    pairs = list(pairs)
    with_tool = [(s, t) for s, t in pairs if t.get("called")]
    latencies = [float(s["latency_ms"]) for s, _ in pairs if s.get("latency_ms") is not None]
    rows = []
    for length in LIST_LENGTHS:
        for threshold in THRESHOLDS:
            narrowed_turns = agree = hidden = idle = 0
            sizes: list[int] = []
            for shadow, turn in pairs:
                kept = narrowed(shadow, threshold, length)
                if kept is None:
                    continue
                narrowed_turns += 1
                sizes.append(len(kept))
                called = turn.get("called") or []
                if not called:
                    idle += 1
                elif called[0] in kept:
                    agree += 1
                else:
                    hidden += 1
            rows.append({
                "max_tools": length,
                "threshold": threshold,
                "narrowed": narrowed_turns,
                "narrowed_share": round(narrowed_turns / len(pairs), 3) if pairs else None,
                "agreed_with_model": agree,
                "hid_the_models_tool": hidden,
                "narrowed_without_tool_use": idle,
                "precision": round(agree / (agree + hidden), 3) if agree + hidden else None,
                "mean_tools_kept": round(sum(sizes) / len(sizes), 2) if sizes else None,
            })
    return {
        "turns": len(pairs),
        "turns_with_tool_use": len(with_tool),
        "shadow_latency_ms": {"p50": _percentile(latencies, 0.5),
                              "p95": _percentile(latencies, 0.95)},
        "outcomes": _count(s.get("outcome") for s, _ in pairs),
        "replay": rows,
    }


def _count(values: Iterable[Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[str(value)] = counts.get(str(value), 0) + 1
    return counts


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Replay a JEV shadow log")
    parser.add_argument("log", type=Path)
    args = parser.parse_args(argv)
    print(json.dumps(report(load(args.log)), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
