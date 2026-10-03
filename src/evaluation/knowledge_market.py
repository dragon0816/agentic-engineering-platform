"""Source-backed, bounded review of a high-speed market Knowledge answer.

This is an evaluation diagnostic, not a general semantic entailment or runtime
authorization engine. It verifies pinned Raw bytes and reports a narrow class
of unsupported product-to-market claims for human review.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections.abc import Sequence
from pathlib import Path, PurePosixPath
from typing import Literal, Self, TypedDict

from pydantic import Field, model_validator

from common.base import Contract, Symbol, Text
from knowledge.evolution import KnowledgeAnswerRecord
from knowledge.query import cited_numbers, retrieve
from knowledge.vault import Vault

_CLAIM = re.compile(r"(?<=[.!?])\s+|(?<=[。！？])\s*")
_POSITIVE_FIT = re.compile(
    r"\b(?:supports?|meets?|validates?|qualifies?|tests?)\b|支援|符合|適用|可測|可驗證"
    r"|對接|接軌|可對應",
    re.IGNORECASE,
)
_NEGATION = re.compile(
    r"\b(?:not|cannot|unverified|unsupported)\b|未證實|無法確認|不能證明|不代表|尚未驗證"
    r"|不等於|缺乏證據|推論",
    re.IGNORECASE,
)


class EvidenceAnchor(Contract):
    kind: Literal["market_requirement", "product_capability"]
    raw_ref: Text
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    anchor: Text

    @model_validator(mode="after")
    def raw_path(self) -> Self:
        path = PurePosixPath(self.raw_ref)
        if path.is_absolute() or ".." in path.parts or not self.raw_ref.startswith("raw/"):
            raise ValueError("evidence must name a relative Raw path")
        return self


class MarketCase(Contract):
    case_id: Symbol
    question: Text
    market_targets: tuple[Text, ...] = Field(min_length=1)
    products: tuple[Text, ...] = Field(min_length=1)
    evidence: tuple[EvidenceAnchor, ...] = Field(min_length=2)
    reviewed_conclusion: Text

    @model_validator(mode="after")
    def evidence_shape(self) -> Self:
        if {item.kind for item in self.evidence} != {
            "market_requirement", "product_capability"
        }:
            raise ValueError("case needs both market and product Raw evidence")
        if len({item.raw_ref for item in self.evidence}) != len(self.evidence):
            raise ValueError("Raw evidence paths must be unique")
        return self


class MarketReport(TypedDict):
    case_id: str
    source_integrity: str
    retrieval_expected: int
    retrieval_found: int
    retrieval_missing: list[str]
    unsupported_market_fit_claims: list[str]
    status: str
    reviewed_conclusion: str
    semantic_entailment_proven: bool


def load_case(path: Path) -> MarketCase:
    return MarketCase.model_validate_json(path.read_text(encoding="utf-8"))


def evaluate_case(
    vault: Vault, case: MarketCase, *, answer: KnowledgeAnswerRecord | None = None
) -> MarketReport:
    """Verify exact Raw anchors, retrieval and cited market-fit assertions.

    A clean automated result still needs a human semantic review. Missing or
    changed source bytes fail closed instead of silently shifting the gold.
    """
    root = (vault.root / "raw").resolve()
    for item in case.evidence:
        path = (vault.root / Path(item.raw_ref)).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError("pinned Raw evidence is unavailable")
        body = path.read_bytes()
        if hashlib.sha256(body).hexdigest() != item.sha256:
            raise ValueError("pinned Raw evidence has changed")
        if item.anchor not in body.decode("utf-8-sig"):
            raise ValueError("reviewed Raw anchor is missing")

    passages = retrieve(vault, case.question, k=8, min_raw=4, evidence_coverage=True)
    found = {passage.citation.raw_ref for passage in passages if passage.citation.kind == "raw"}
    expected = {item.raw_ref for item in case.evidence}
    missing = sorted(expected - found)
    unsupported: list[str] = []
    if answer is not None:
        if answer.answer.question != case.question:
            raise ValueError("answer is for a different question")
        cited = answer.answer.passages
        with_attached_citations = re.sub(
            r"([.!?。！？])\s*(\[[0-9][0-9,\s-]*\])", r" \2\1", answer.answer.text
        )
        names_anywhere = any(
            name.casefold() in answer.answer.text.casefold() for name in case.products
        )
        targets_anywhere = any(
            target.casefold() in answer.answer.text.casefold() for target in case.market_targets
        )
        for sentence in _CLAIM.split(with_attached_citations):
            if not _POSITIVE_FIT.search(sentence) or _NEGATION.search(sentence):
                continue
            if not names_anywhere or not targets_anywhere:
                continue
            if not (
                "市場" in sentence
                or "market" in sentence.casefold()
                or any(target.casefold() in sentence.casefold() for target in case.market_targets)
            ):
                continue
            refs = cited_numbers(sentence)
            if not any(
                1 <= number <= len(cited)
                and cited[number - 1].citation.kind == "raw"
                and cited[number - 1].citation.raw_ref in expected
                and any(name.casefold() in cited[number - 1].text.casefold()
                        for name in case.products)
                and any(target.casefold() in cited[number - 1].text.casefold()
                        for target in case.market_targets)
                for number in refs
            ):
                unsupported.append(sentence.strip())
    return {
        "case_id": case.case_id,
        "source_integrity": "verified",
        "retrieval_expected": len(expected),
        "retrieval_found": len(expected) - len(missing),
        "retrieval_missing": missing,
        "unsupported_market_fit_claims": unsupported,
        "status": "review_required" if not missing and not unsupported else "failed",
        "reviewed_conclusion": case.reviewed_conclusion,
        "semantic_entailment_proven": False,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit pinned Raw market-fit evidence")
    parser.add_argument("--vault", required=True, type=Path)
    parser.add_argument(
        "--case", type=Path,
        default=Path(__file__).resolve().parents[2] / "evaluation/knowledge/rs-market-v1.json"
    )
    parser.add_argument("--answer-record", type=Path)
    args = parser.parse_args(argv)
    try:
        record = (
            KnowledgeAnswerRecord.model_validate_json(
                args.answer_record.read_text(encoding="utf-8-sig")
            )
            if args.answer_record else None
        )
        report = evaluate_case(Vault(args.vault), load_case(args.case), answer=record)
    except (OSError, ValueError) as error:
        parser.exit(2, f"Market evidence audit unavailable: {type(error).__name__}\n")
    # PowerShell may still use cp950; ASCII JSON remains machine readable.
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return 0 if report["status"] == "review_required" else 1


if __name__ == "__main__":
    raise SystemExit(main())
