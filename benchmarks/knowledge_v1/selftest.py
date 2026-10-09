"""Offline check of the grader: synthetic replies for every status, a temporary
Vault, and a stand-in reviewer; and of compare.py on synthetic run folders.
Run: python benchmarks/knowledge_v1/selftest.py"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
# This folder first: coding_v1 has a run.py of its own.
sys.path.insert(0, str(HERE.parents[1] / "benchmarks" / "coding_v1"))
sys.path.insert(0, str(HERE))

import compare  # noqa: E402
import reference_grade  # noqa: E402
from questions import load, sample  # noqa: E402
from run import grade  # noqa: E402

PASSAGE = {"text": "Doc › Intro\nThe tester measures EVM on 5G NR uplink signals.",
           "citation": {"kind": "raw", "raw_ref": "raw/doc.md", "section": 1}}
FORGED = {"text": "Doc › Intro\nThis sentence is nowhere in the Vault at all, not even close.",
          "citation": {"kind": "raw", "raw_ref": "raw/doc.md", "section": 2}}


class Reviewer:
    def __init__(self, supported: bool) -> None:
        self.supported = supported

    def review(self, question: str, answer: str, passages: list[dict[str, Any]]) -> dict[str, Any]:
        return {"ok": True, "supported": self.supported, "reasonable": self.supported,
                "confidence": "high", "reason": "stand-in"}


def direct(text: str, passages: list[dict[str, Any]], status: str = "succeeded",
           failure: str | None = None, phase: str = "needs_input") -> dict[str, Any]:
    capability = {"status": status, "data": {"answer": {"passages": passages, "text": text}},
                  "failure": {"code": failure} if failure else None}
    return {"http_status": 200, "timed_out": False, "seconds": 1.0, "reply": {"answer": {
        "answer": text, "harness": {"phase": "validated"}, "outcome": {"capability": capability}}}}


def partial(text: str, passages: list[dict[str, Any]]) -> dict[str, Any]:
    """The harness stopped at needs_input but answered what the evidence supports."""
    exchange = direct(text, passages)
    exchange["reply"]["answer"]["harness"] = {"phase": "needs_input"}
    return exchange


def plain(text: str) -> dict[str, Any]:
    return {"http_status": 200, "timed_out": False, "seconds": 1.0, "reply": {"answer": {
        "answer": text, "outcome": {"conversation": {"status": "answered", "text": text, "tools": []}}}}}


def tool(text: str, passages: list[dict[str, Any]]) -> dict[str, Any]:
    call = {"name": "knowledge__rs-knowledge", "capability": {
        "status": "succeeded", "data": {"answer": {"passages": passages}, "cited_passages": passages}}}
    return {"http_status": 200, "timed_out": False, "seconds": 1.0, "reply": {"answer": {
        "answer": text, "outcome": {"conversation": {"status": "answered", "text": text, "tools": [call]}}}}}


def write_run(root: Path, name: str, results: list[dict[str, Any]]) -> Path:
    folder = root / name
    for result in results:
        (folder / result["id"]).mkdir(parents=True)
        (folder / result["id"] / "result.json").write_text(json.dumps(result), encoding="utf-8")
    (folder / "metadata.json").write_text(json.dumps({"started": name, "commit": "abc1234"}), encoding="utf-8")
    (folder / "Q0003").mkdir(exist_ok=True)  # a question still being asked: no result.json yet
    return folder


def result(qid: str, status: str, route: str, seconds: float, why: str = "",
           citations: int = 0, overreach: int = 0) -> dict[str, Any]:
    out: dict[str, Any] = {"id": qid, "status": status, "route": route, "seconds": seconds, "grader": "1.1",
                           "gap": "" if status == "PASS" else "REASONING_GAP", "why": why}
    if citations:
        out["citations"] = [{"number": n, "ok": n != 2} for n in range(1, citations + 1)]
        out["review"] = {"ok": True, "supported": status == "PASS", "reasonable": True, "confidence": "high",
                         "overreach": ["claim"] * overreach}
    return out


def compare_cases() -> int:
    """compare.py on two synthetic runs; the second is partial (Q1001 not asked yet)."""
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        old = write_run(root, "run-a", [
            result("Q0001", "PASS", "direct", 10.0, citations=2),
            result("Q0002", "FAIL", "tool", 20.0, "reviewer: unsupported", citations=1, overreach=2),
            result("Q0011", "SYSTEM_ERROR", "tool", 600.0, "timed out"),
            result("Q1001", "INSUFFICIENT_KNOWLEDGE", "tool", 30.0, "gap")])
        write_run(root, "run-b", [
            result("Q0001", "FAIL", "tool", 40.0, "reviewer: overreach | detail", citations=1, overreach=1),
            result("Q0002", "PASS", "direct", 50.0, citations=3),
            result("Q0011", "FAIL", "tool", 60.0, "reviewer: no")])
        runs = [compare.load_run(compare.resolve(str(old))), compare.load_run(compare.resolve("run-b", root))]
        markdown = compare.compare(runs, compare.load_questions())
        moved = compare.transitions(runs[0].results, runs[1].results, ["Q0001", "Q0002", "Q0011"])
    checks = {
        "a partial run is compared on the shared questions": "| run-a | run-a | `abc1234` | 1.1 | 4 | 3 | 1 |"
        in markdown,
        "status counts": "| PASS | 1 | 1 |" in markdown and "| SYSTEM_ERROR | 1 | 0 |" in markdown,
        "route x status": "| run-b | direct | 1 | 1 | 0 | 0 | 0 | 0 | 100% |" in markdown,
        "breakdown by market with delta": "| Wireless Communication | 3 | 1 / 1 | 1 / 1 | +0 |" in markdown,
        "improved / regressed / same rank": (moved["counts"]["improved"], moved["counts"]["regressed"],
                                             moved["counts"]["changed, same rank"]) == (1, 1, 1),
        "transition rows with route change and reason": "| Q0001 | regressed | PASS → FAIL | direct → tool |"
        in markdown and "reviewer: overreach / detail" in markdown,
        "reviewer overreach share": "| run-a | 2 | 2 | 1 (50%) | 2 (100%) | 2 / 0 / 0 | 1 (50%) | 1.0 |"
        in markdown,
        "latency median and p90": "| run-a | tool | 2 | 310.0 | 600.0 |" in markdown,
        "citations and verification rate": "| run-b | 2 | 4 | 2.0 | 3 (75%) |" in markdown,
    }
    for name, ok in checks.items():
        print(f"{'PASS' if ok else 'FAIL'}  compare: {name}")
    return sum(1 for ok in checks.values() if not ok)


def hosted(text: str, passages: list[dict[str, Any]] | None, validated: bool = True,
           failure: str | None = None, phase: str = "needs_input") -> dict[str, Any]:
    """The tool route since 2026-10-09: the host ran the Knowledge Harness."""
    data: dict[str, Any] = {"knowledge_harness": "validated" if validated else "not_validated",
                            "answer": text, "phase": "validated" if validated else phase,
                            "failure_code": failure}
    if passages is not None:
        data["record"] = {"answer": {"passages": passages}}
    call = {"name": "knowledge__rs-knowledge",
            "host": {"status": "succeeded" if validated else "failed", "data": data}}
    return {"http_status": 200, "timed_out": False, "seconds": 1.0, "reply": {"answer": {
        "answer": text, "outcome": {"conversation": {"status": "answered", "text": text, "tools": [call]}}}}}


def main() -> int:
    question = {"id": "Q0001", "text": "What does the tester measure?"}
    with tempfile.TemporaryDirectory() as folder:
        vault = Path(folder)
        (vault / "raw").mkdir()
        (vault / "raw" / "doc.md").write_text("# Doc\n\nThe tester measures **EVM** on 5G NR uplink signals.\n",
                                              encoding="utf-8")
        cases = [
            ("PASS", direct("It measures EVM [1].", [PASSAGE]), Reviewer(True)),
            ("PASS", tool("It measures EVM (raw/doc.md, section 1).", [PASSAGE]), Reviewer(True)),
            ("PASS", hosted("It measures EVM [1].", [PASSAGE]), Reviewer(True)),
            ("FAIL", hosted("It measures EVM [1].", [FORGED]), Reviewer(True)),
            ("NEEDS_HUMAN_REVIEW", hosted("It measures EVM [1].", None), Reviewer(True)),
            ("INSUFFICIENT_KNOWLEDGE", hosted("Not in the Vault.", None, False,
                                              "knowledge_insufficient_evidence"), Reviewer(True)),
            ("FAIL", hosted("Not validated.", None, False, "knowledge_not_validated", "failed"),
             Reviewer(True)),
            ("FAIL", plain("It measures EVM."), Reviewer(True)),
            ("FAIL", direct("It measures EVM [1].", [FORGED]), Reviewer(True)),
            ("FAIL", direct("It measures EVM.", [PASSAGE]), Reviewer(True)),
            ("FAIL", direct("It measures EVM [1].", [PASSAGE]), Reviewer(False)),
            ("INSUFFICIENT_KNOWLEDGE", direct("Not in the Vault.", [], "failed",
                                              "knowledge_insufficient_evidence"), Reviewer(True)),
            ("SYSTEM_ERROR", {"http_status": 500, "timed_out": False, "reply": {}}, Reviewer(True)),
            ("PASS", partial("Supported part [1]. Missing: competitor.", [PASSAGE]), Reviewer(True)),
            ("FAIL", partial("Supported part [1]. Missing: competitor.", [PASSAGE]), Reviewer(False)),
        ]
        wrong = 0
        for want, exchange, reviewer in cases:
            got = grade(question, exchange, vault, reviewer)
            ok = got["status"] == want
            wrong += 0 if ok else 1
            print(f"{'PASS' if ok else 'FAIL'}  expected {want}, got {got['status']} ({got.get('why', '')})")
    bank = load()
    picked = sample(bank)
    shape_ok = len(bank) == 1100 and len(picked) == 110 and len({q["id"] for q in bank}) == 1100
    print(f"{'PASS' if shape_ok else 'FAIL'}  question bank 1100, sample 110")
    wrong += 0 if shape_ok else 1
    wrong += compare_cases()
    reference = {"key_points": [{"point": f"p{n}", "verified": True} for n in range(4)]}
    scored = reference_grade.score(reference, {"points": [
        {"n": 1, "label": "covered"}, {"n": 2, "label": "partial"},
        {"n": 3, "label": "contradicted"}, {"n": 9, "label": "covered"}],
        "invented": ["CMP180 supports Wi-Fi 8"]})
    graded_ok = (scored["coverage"] == 0.375 and scored["contradicted"] == 1
                 and scored["points"][3]["label"] == "missing" and len(scored["invented"]) == 1)
    print(f"{'PASS' if graded_ok else 'FAIL'}  reference grade: coverage, unlabeled point is missing")
    wrong += 0 if graded_ok else 1
    print("selftest:", "all good" if not wrong else f"{wrong} case(s) wrong")
    return 1 if wrong else 0


if __name__ == "__main__":
    sys.exit(main())
