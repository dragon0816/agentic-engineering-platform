"""Offline check of the grader: synthetic replies for every status, a temporary
Vault, and a stand-in reviewer. Run: python benchmarks/knowledge_v1/selftest.py"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
# This folder first: coding_v1 has a run.py of its own.
sys.path.insert(0, str(HERE.parents[1] / "benchmarks" / "coding_v1"))
sys.path.insert(0, str(HERE))

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
           failure: str | None = None) -> dict[str, Any]:
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
    print("selftest:", "all good" if not wrong else f"{wrong} case(s) wrong")
    return 1 if wrong else 0


if __name__ == "__main__":
    sys.exit(main())
