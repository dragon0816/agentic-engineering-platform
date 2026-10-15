"""Evidence-level regression for the read-only market discovery matrix."""

from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from common.assets import AssetIdentity
from common.execution import TraceIdentifiers
from knowledge.market_matrix import (
    MarketCellSufficiency,
    MarketMatrixRecord,
    MatrixCell,
    ProductFamily,
    TargetMarket,
    assess_market_cell,
    discover_market_matrix,
)
from knowledge.raw import RawDocument, RawSection, render, source_for
from knowledge.vault import Vault

ASSET = AssetIdentity(namespace="engineering", name="rs-knowledge", version="1.0.0")
TRACE = TraceIdentifiers(trace_id="trace-1", request_id="request-1", span_id="span-1")


def _vault(tmp_path: Path, sections: tuple[str, ...]) -> Vault:
    for name in ("raw", "wiki"):
        (tmp_path / name).mkdir()
    (tmp_path / "index.md").write_text("# Index\n", encoding="utf-8")
    (tmp_path / "log.md").write_text("# Log\n", encoding="utf-8")
    for index, text in enumerate(sections):
        raw_ref = f"raw/source-{index}.md"
        source = source_for(text.encode("utf-8"), f"drop/source-{index}.txt").model_copy(
            update={"raw_ref": raw_ref}
        )
        document = RawDocument(
            source=source,
            extractor="fixture",
            created=date(2026, 10, 4),
            sections=(RawSection(text=text, page=index + 1),),
        )
        (tmp_path / raw_ref).write_text(render(document), encoding="utf-8")
    return Vault(tmp_path)


def _cell(record: MarketMatrixRecord, family: str, market: str) -> MatrixCell:
    return next(
        cell for cell in record.cells if cell.product_family == family and cell.market == market
    )


def test_matrix_has_25_cells_and_does_not_infer_fit(tmp_path: Path) -> None:
    vault = _vault(
        tmp_path,
        (
            "CMP180 is listed beside automotive connectivity; no option is specified.",
            "FSW lists a measurement capability.",
            "AI data center power validation is a market requirement.",
            "SMBV100B is listed for wireless measurement experiments.",
        ),
    )
    record = discover_market_matrix(ASSET, TRACE, vault)
    assert len(record.cells) == 25
    joint = _cell(record, "nonsignaling_wireless", "automotive")
    assert joint.evidence_level == "nearby_mention"
    assert joint.evidence[0].raw_ref == "raw/source-0.md"
    assert joint.evidence[0].page == 1
    assert "CMP180" in joint.evidence[0].excerpt
    assert "automotive" in joint.evidence[0].excerpt
    assert joint.market_fit_verified is False
    assert "radio standard" not in joint.knowledge_gaps[0]
    assert "connectivity" in joint.knowledge_gaps[0]
    assert "CMP/CMW" in joint.knowledge_gaps[1]
    separate = _cell(record, "signal_generation_analysis", "ai_server")
    assert separate.evidence_level == "separate_passages"
    assert {item.facet for item in separate.evidence} == {"product", "market"}
    missing = _cell(record, "vector_network_analysis", "semiconductor")
    assert missing.evidence_level == "no_raw_match"
    assert missing.evidence == ()
    assert all(cell.market_fit_verified is False for cell in record.cells)
    wireless_signal = _cell(record, "signal_generation_analysis", "wireless_communications")
    assert wireless_signal.evidence_level == "nearby_mention"


def test_matrix_contract_refuses_fit_claim_without_evidence(tmp_path: Path) -> None:
    record = discover_market_matrix(ASSET, TRACE, _vault(tmp_path, ("CMP180 wireless",)))
    bad = record.model_dump(mode="json")
    bad["cells"][0]["market_fit_verified"] = True
    with pytest.raises(ValidationError):
        type(record).model_validate(bad)


def test_selected_cell_reports_insufficient_evidence_without_promoting_a_lead(
    tmp_path: Path,
) -> None:
    record = discover_market_matrix(
        ASSET,
        TRACE,
        _vault(
            tmp_path,
            (
                "CMP180 is listed beside automotive connectivity.",
                "FSW lists a measurement capability.",
                "AI data center power validation is a market requirement.",
            ),
        ),
    )
    cases: tuple[tuple[ProductFamily, TargetMarket, str], ...] = (
        ("nonsignaling_wireless", "automotive", "nearby_mention"),
        ("signal_generation_analysis", "ai_server", "separate_passages"),
        ("vector_network_analysis", "semiconductor", "no_raw_match"),
    )
    for family, market, expected_level in cases:
        assessment = assess_market_cell(record, family, market)
        cell = _cell(record, family, market)
        assert assessment.status == "needs_evidence"
        assert assessment.discovery_level == expected_level
        assert assessment.discovery_evidence == cell.evidence
        assert tuple(need.question for need in assessment.missing_evidence) == (cell.knowledge_gaps)
        assert tuple(need.facet for need in assessment.missing_evidence) == (
            "market_requirements",
            "product_options",
            "customer_use_case",
        )
        assert assessment.asset == ASSET
        assert assessment.trace == TRACE
        assert (
            MarketCellSufficiency.model_validate(assessment.model_dump(mode="json")) == assessment
        )
        tampered = assessment.model_dump(mode="json")
        tampered["status"] = "validated"
        with pytest.raises(ValidationError):
            MarketCellSufficiency.model_validate(tampered)
        tampered = assessment.model_dump(mode="json")
        tampered["missing_evidence"] = tampered["missing_evidence"][:2]
        with pytest.raises(ValidationError):
            MarketCellSufficiency.model_validate(tampered)
