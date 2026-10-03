"""The high-speed-market evaluation pins source evidence and flags false fit."""

import hashlib
import json
from datetime import date
from pathlib import Path

import pytest
from test_raw import drop, make_vault

from common.assets import AssetIdentity
from common.execution import TraceIdentifiers
from evaluation.knowledge_market import MarketCase, evaluate_case
from knowledge.evolution import KnowledgeAnswerRecord, grounded_record
from knowledge.query import Answer, retrieve
from knowledge.raw import DropIntake, PlainTextExtractor
from knowledge.vault import Vault


def _case(tmp_path: Path) -> tuple[MarketCase, Vault]:
    vault = make_vault(tmp_path)
    intake = DropIntake(vault, [PlainTextExtractor()])
    refs: list[dict[str, str]] = []
    for name, kind, content, anchor in (
        (
            "market", "market_requirement",
            "高速通訊市場採用 800G 和 1.6T Ethernet。",
            "800G 和 1.6T Ethernet",
        ),
        (
            "product", "product_capability",
            "CMX-B200A option has two high-speed digital I/Q interfaces for R&S instruments.",
            "CMX-B200A option has two high-speed digital I/Q interfaces",
        ),
    ):
        original = f"drop/{name}.txt"
        drop(vault, original, content.encode("utf-8"))
        result = intake.intake(original, mode="apply", today=date(2026, 10, 3))
        assert result.raw_ref is not None
        body = (vault.root / result.raw_ref).read_bytes()
        refs.append(
            {
                "kind": kind,
                "raw_ref": result.raw_ref,
                "sha256": hashlib.sha256(body).hexdigest(),
                "anchor": anchor,
            }
        )
    case = MarketCase.model_validate(
        {
            "case_id": "synthetic-market",
            "question": "高速通訊市場有哪些產品和 option 可以接軌？",
            "market_targets": ["800G", "1.6T"],
            "products": ["CMX-B200A"],
            "evidence": refs,
            "reviewed_conclusion": "An I/Q interface does not establish 800G test qualification.",
        }
    )
    return case, vault


def _record(case: MarketCase, vault: Vault, text: str) -> KnowledgeAnswerRecord:
    passages = retrieve(vault, case.question, k=4, min_raw=2, evidence_coverage=True)
    answer = Answer(question=case.question, status="answered", passages=passages, text=text)
    return grounded_record(
        AssetIdentity(namespace="evaluation", name="market", version="1.0.0"),
        TraceIdentifiers(trace_id="market", request_id="market", span_id="market"),
        answer,
    )


def test_pinned_raw_distinguishes_product_capability_from_market_fit(tmp_path: Path) -> None:
    case, vault = _case(tmp_path)
    report = evaluate_case(vault, case)
    assert report["source_integrity"] == "verified"
    assert report["retrieval_found"] == 2
    assert report["status"] == "review_required"
    assert report["semantic_entailment_proven"] is False

    passages = retrieve(vault, case.question, k=4, min_raw=2, evidence_coverage=True)
    product_number = next(
        n for n, passage in enumerate(passages, 1)
        if "CMX-B200A" in passage.text
    )
    market_number = next(
        n for n, passage in enumerate(passages, 1)
        if "800G" in passage.text
    )
    asserted = _record(
        case, vault, f"CMX-B200A supports 800G Ethernet [{product_number}, {market_number}]."
    )
    failed = evaluate_case(vault, case, answer=asserted)
    assert failed["status"] == "failed"
    assert len(failed["unsupported_market_fit_claims"]) == 1

    linked_across_sentences = _record(
        case, vault,
        f"CMX-B200A has digital I/Q interfaces [{product_number}]. "
        f"這些能力可對應 800G 高速通訊市場 [{market_number}].",
    )
    linked_report = evaluate_case(vault, case, answer=linked_across_sentences)
    assert linked_report["status"] == "failed"
    assert len(linked_report["unsupported_market_fit_claims"]) == 1

    qualified = _record(
        case, vault,
        f"CMX-B200A has digital I/Q interfaces [{product_number}]. "
        f"This does not establish 800G market fit [{product_number}, {market_number}].",
    )
    checked = evaluate_case(vault, case, answer=qualified)
    assert checked["status"] == "review_required"
    assert checked["unsupported_market_fit_claims"] == []


def test_market_audit_fails_closed_on_raw_drift_and_path_escape(tmp_path: Path) -> None:
    case, vault = _case(tmp_path)
    source = vault.root / case.evidence[0].raw_ref
    source.write_text("edited", encoding="utf-8")
    with pytest.raises(ValueError, match="changed"):
        evaluate_case(vault, case)

    payload = case.model_dump(mode="json")
    payload["evidence"][0]["raw_ref"] = "raw/../secret.txt"
    with pytest.raises(ValueError, match="relative Raw"):
        MarketCase.model_validate(payload)


def test_reviewed_rs_case_is_structurally_valid() -> None:
    path = Path(__file__).resolve().parents[1] / "evaluation/knowledge/rs-market-v1.json"
    case = MarketCase.model_validate(json.loads(path.read_text(encoding="utf-8")))
    assert {entry.kind for entry in case.evidence} == {
        "market_requirement", "product_capability"
    }
    assert case.market_targets == ("800G", "1.6T")
