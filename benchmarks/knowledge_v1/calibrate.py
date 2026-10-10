"""How much do two strong answers agree? A ceiling for reference coverage (owner 2026-10-10).

Claude Code answers the chosen questions a second time, independently, with
the same prompt and read-only tools as `reference.py`. The second answers go
to `references-b/` and never replace the references. Each answer is then
graded against the other with the same judge and rubric as
`reference_grade.py`, in both directions. The mean is the coverage two careful
answers reach on each other, which is the realistic target for AEP's answers.

An answer is graded as its text plus its key points, because a reference keeps
its specifics in the key points.

    python benchmarks/knowledge_v1/calibrate.py --ids Q0011,Q0039,Q0121,Q0196,Q1001
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "benchmarks" / "coding_v1"))
sys.path.insert(0, str(HERE))

import questions as Q  # noqa: E402
import reference  # noqa: E402
import reference_grade as G  # noqa: E402
from run import HOST_JSON, credential  # noqa: E402

SECOND = HERE / "references-b"


def as_answer(record: dict[str, Any]) -> str:
    points = "\n".join(f"- {p.get('point')}" for p in record.get("key_points") or [])
    return f"{record.get('answer') or ''}\n\nKey points:\n{points}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ids", required=True)
    args = parser.parse_args()
    ids = [item.strip() for item in args.ids.split(",") if item.strip()]
    bank = {q["id"]: q for q in Q.load()}
    SECOND.mkdir(exist_ok=True)
    for qid in ids:
        target = SECOND / f"{qid}.json"
        if target.exists():
            print(f"{qid}: second answer kept")
            continue
        record = reference.answer(bank[qid])
        target.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        verified = f"{record['verified_points']}/{len(record['key_points'])}"
        print(f"{qid}: second answer {verified} points verified, {record['seconds']} s, "
              f"~${record['cost_usd_estimate']}", flush=True)
    credential()
    from judge import Judge  # needs the credential in the environment
    judge = Judge(HOST_JSON)
    rows = []
    for qid in ids:
        first = json.loads((HERE / "references" / f"{qid}.json").read_text(encoding="utf-8"))
        second = json.loads((SECOND / f"{qid}.json").read_text(encoding="utf-8"))
        result: dict[str, Any] = {"id": qid}
        for name, ref, ans in (("b_vs_a", first, second), ("a_vs_b", second, first)):
            asked = G.prompt(first["question"], ref, as_answer(ans))
            verdict = G._ask(judge.client, judge.alias, asked)
            result[name] = ({"error": verdict["error"]} if "error" in verdict
                            else G.score(ref, verdict))
        rows.append(result)
        print(f"{qid}: b vs a {result['b_vs_a'].get('coverage')}, "
              f"a vs b {result['a_vs_b'].get('coverage')}", flush=True)
    (SECOND / "calibration.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1),
                                             encoding="utf-8")
    both = [r[d]["coverage"] for r in rows for d in ("b_vs_a", "a_vs_b")
            if r[d].get("coverage") is not None]
    if both:
        print(f"mean coverage between two independent Claude Code answers: "
              f"{statistics.mean(both):.3f} (n={len(both)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
