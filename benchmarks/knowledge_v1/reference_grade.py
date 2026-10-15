"""Grade a run's answers against the Claude Code reference answers (owner 2026-10-09).

`reference.py` wrote, per question, the key points a correct answer must hold,
each with a verified Vault quote, and what the Vault lacks. Here the company
Gateway model compares one AEP answer with those key points:

- each key point is `covered`, `partial`, `missing` or `contradicted`;
- `invented` lists claims the answer states as fact although the reference
  says the Vault lacks them.

Coverage is (covered + partial / 2) / key points. It is a measurement next to
run.py's verdict, not a replacement: the reference is one good answer, and an
answer may be right in other words or with other evidence, so a person reads
the low ones before deciding anything.

    python benchmarks/knowledge_v1/reference_grade.py --run-id <id>
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "benchmarks" / "coding_v1"))
sys.path.insert(0, str(HERE))

from evidence import knowledge_use  # noqa: E402
from run import HOST_JSON, credential  # noqa: E402

from telemetry.benchmark import BenchmarkTelemetry  # noqa: E402  (run puts src on the path)

GRADER_VERSION = "1.2"
LABELS = ("covered", "partial", "missing", "contradicted")

RUBRIC = """You compare an ANSWER from a company knowledge assistant with a REFERENCE
written from the same knowledge base. The reference lists numbered key points a
correct answer must contain, and what the knowledge base does NOT contain.

For each key point decide, judging meaning and not wording:
- covered: the answer states it, possibly in other words;
- partial: the answer states part of it, or only vaguely;
- missing: the answer does not state it;
- contradicted: the answer states something incompatible with it.
Then list, under "invented", claims the answer presents as fact that the
reference's "not in the knowledge base" section says are absent. A claim that
the reference answer or its key points also state is never invented. A claim
the answer itself labels as not from the knowledge base (general knowledge,
clearly marked) is not invented either. Leave it empty when there are none.
Do not use your own knowledge of the facts.

Reply with one JSON object:
{"points": [{"n": 1, "label": "covered|partial|missing|contradicted",
             "why": "a few words"}, ...],
 "invented": ["short quote", ...]}"""


def _ask(client: Any, alias: str, prompt: str) -> dict[str, Any]:
    from common.execution import TraceIdentifiers
    from models.contracts import ModelMessage, ModelRequest, ModelRequirements

    request = ModelRequest(
        trace=TraceIdentifiers(
            trace_id="knowledge-v1-reference", request_id="reference", span_id="reference"
        ),
        model_alias=alias,
        messages=(ModelMessage(role="system", text=RUBRIC), ModelMessage(role="user", text=prompt)),
        requirements=ModelRequirements(structured_output=True),
        output_contract="knowledge_v1_reference_grade",
        max_output_tokens=4000,
    )
    response = client.generate(request)
    if response.failure is not None:
        return {"error": response.failure.code}
    verdict = response.structured_output
    if not isinstance(verdict, dict):
        try:
            verdict = json.loads(response.text)
        except ValueError:
            return {"error": "unparseable"}
    return verdict if isinstance(verdict, dict) else {"error": "unparseable"}


def score(reference: dict[str, Any], verdict: dict[str, Any]) -> dict[str, Any]:
    """Labels per key point, the coverage share and the invented claims."""
    points = reference.get("key_points") or []
    given = {item.get("n"): item for item in verdict.get("points") or [] if isinstance(item, dict)}
    labels = []
    for n, point in enumerate(points, 1):
        item = given.get(n) or {}
        label = item.get("label") if item.get("label") in LABELS else "missing"
        labels.append(
            {
                "n": n,
                "point": point.get("point"),
                "verified": point.get("verified"),
                "label": label,
                "why": item.get("why"),
            }
        )
    weight = {"covered": 1.0, "partial": 0.5}
    coverage = (
        sum(weight.get(item["label"], 0.0) for item in labels) / len(labels) if labels else None
    )
    return {
        "coverage": None if coverage is None else round(coverage, 3),
        "points": labels,
        "contradicted": sum(1 for item in labels if item["label"] == "contradicted"),
        "invented": [str(x) for x in verdict.get("invented") or []],
    }


def prompt(question: str, reference: dict[str, Any], answer: str) -> str:
    points = "\n".join(
        f"{n}. {p.get('point')}" for n, p in enumerate(reference.get("key_points") or [], 1)
    )
    return (
        f"Question:\n{question}\n\nREFERENCE answer:\n{reference.get('answer') or ''}\n\n"
        f"REFERENCE key points:\n{points}\n\n"
        "Not in the knowledge base (per the reference):\n"
        f"{reference.get('missing') or '(none)'}\n\nANSWER:\n{answer}"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    run_dir = HERE / "runs" / args.run_id
    references = {
        p.stem: json.loads(p.read_text(encoding="utf-8"))
        for p in sorted((HERE / "references").glob("Q*.json"))
    }
    credential()
    from judge import Judge  # needs the credential in the environment

    judge = Judge(HOST_JSON)
    rows = []
    meta_path = run_dir / "metadata.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
    graded_runs = meta.get("telemetry_runs") or [None]
    grading = BenchmarkTelemetry(
        "knowledge_v1", args.run_id, kind="benchmark_grading", parent_run_id=graded_runs[-1]
    )
    grading.start(
        cases=sum(1 for q in references if (run_dir / q / "trace.json").exists()),
        grader=GRADER_VERSION,
        judge="company",
    )
    for qid, reference in references.items():
        trace_path = run_dir / qid / "trace.json"
        if not trace_path.exists():
            continue
        exchange = json.loads(trace_path.read_text(encoding="utf-8"))["exchange"]
        answer = knowledge_use(exchange)["text"]
        verdict = _ask(judge.client, judge.alias, prompt(reference["question"], reference, answer))
        graded = {"error": verdict["error"]} if "error" in verdict else score(reference, verdict)
        result = {"id": qid, "grader": GRADER_VERSION, **graded}
        (run_dir / qid / "reference-grade.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8"
        )
        status = (
            json.loads((run_dir / qid / "result.json").read_text(encoding="utf-8"))["status"]
            if (run_dir / qid / "result.json").exists()
            else "-"
        )
        rows.append((qid, status, result))
        labels = {
            label: sum(1 for p in result.get("points") or [] if p["label"] == label)
            for label in LABELS
        }
        grading.case_completed(
            qid,
            "ERROR" if "error" in result else "GRADED",
            run_verdict=status,
            coverage=result.get("coverage"),
            key_points=len(result.get("points") or []),
            **{f"points_{label}": count for label, count in labels.items()},
            invented_count=len(result.get("invented") or []),
            reference_sufficient=reference.get("sufficient"),
            failure_code=result.get("error"),
        )
        print(
            f"{qid}: coverage {result.get('coverage')}, contradicted "
            f"{result.get('contradicted')}, invented {len(result.get('invented') or [])} "
            f"({status}) {result.get('error') or ''}",
            flush=True,
        )
    lines = [
        f"# knowledge_v1 {args.run_id}: answers against the Claude Code references",
        "",
        f"Grader {GRADER_VERSION}. Coverage = (covered + partial / 2) / key points.",
        "",
        "| Question | run.py status | Coverage | Covered | Partial | Missing | Contradicted |"
        " Invented |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for qid, status, result in rows:
        count = {
            label: sum(1 for p in result.get("points") or [] if p["label"] == label)
            for label in LABELS
        }
        lines.append(
            f"| {qid} | {status} | {result.get('coverage', result.get('error'))} | "
            f"{count['covered']} | {count['partial']} | {count['missing']} | "
            f"{count['contradicted']} | {len(result.get('invented') or [])} |"
        )
    (run_dir / "reference-report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    grading.finish()
    print(f"done: {len(rows)} graded; see {run_dir / 'reference-report.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
