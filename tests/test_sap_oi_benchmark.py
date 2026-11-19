"""Acceptance rejects plausible but wrong saved reports, not just absent files."""

import asyncio
import json
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET
from zipfile import ZIP_DEFLATED, ZipFile

import pytest
from test_dispatch import invocation

from benchmarks.harness_reliability_sap_oi.adapter import (
    SPEC,
    ExportHandler,
    ExportInput,
    ExportResult,
)
from benchmarks.harness_reliability_sap_oi.oracle import gold, verify_records, verify_workbook
from benchmarks.harness_reliability_sap_oi.workbook import build_workbook
from capabilities.runtime import CapabilityGrant, InstalledCapabilities, LocalPolicy
from common.assets import ExecutionDependencies
from workflow.dispatch import BridgeExecutor

HERE = Path(__file__).resolve().parents[1] / "benchmarks/harness_reliability_sap_oi"
NS = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def records() -> list[dict[str, Any]]:
    # Test controls use frozen gold IDs, not the model's normalization code.
    source = json.loads((HERE / "fixtures/records.json").read_text(encoding="utf-8"))
    chosen: dict[str, dict[str, Any]] = {}
    for row in source:
        if row["document"] in gold()["included_documents"]:
            chosen[row["document"]] = row | {
                "amount": float(row["amount"]),
                "fx": 32 if row["currency"] == "USD" else 1,
                "month": row["created_at"][:7],
            }
    return list(chosen.values())


def test_complete_saved_report_has_matching_formula_cache_and_native_pivot(tmp_path: Path) -> None:
    workbook = tmp_path / "report.xlsx"
    build_workbook(workbook, records(), "http://127.0.0.1:8766")
    result = verify_workbook(workbook)
    assert result["passed"] is True and result["grand_total_twd"] == 13580
    assert result["excel_desktop_refresh"] == "unverified_not_installed"


@pytest.mark.parametrize("damage", ["wrong_total", "wrong_fx", "wrong_cache", "missing_pivot"])
def test_nonempty_readable_workbook_is_rejected_when_acceptance_fails(
    tmp_path: Path,
    damage: str,
) -> None:
    workbook = tmp_path / "wrong.xlsx"
    build_workbook(workbook, records(), "http://127.0.0.1:8766")
    with ZipFile(workbook) as source:
        parts = {name: source.read(name) for name in source.namelist()}
    if damage == "missing_pivot":
        name = "xl/pivotTables/pivotTable1.xml"
        root = ET.fromstring(parts[name])
        root.set("name", "WrongName")
    elif damage == "wrong_cache":
        name = "xl/pivotCache/pivotCacheRecords1.xml"
        root = ET.fromstring(parts[name])
        root.findall("s:r", NS)[-1][-1].set("v", "999999")
    else:
        name = "xl/worksheets/sheet1.xml" if damage == "wrong_total" else "xl/worksheets/sheet2.xml"
        root = ET.fromstring(parts[name])
        address = "E10" if damage == "wrong_total" else "I3"
        value = root.find(f"s:sheetData/s:row/s:c[@r='{address}']/s:v", NS)
        assert value is not None
        value.text = "999999" if damage == "wrong_total" else "1"
    parts[name] = ET.tostring(root, encoding="utf-8")
    with ZipFile(workbook, "w", ZIP_DEFLATED) as target:
        for name, payload in parts.items():
            target.writestr(name, payload)
    assert workbook.stat().st_size > 0
    with pytest.raises(ValueError):
        verify_workbook(workbook)


def test_missing_page_and_wrong_currency_conversion_are_rejected() -> None:
    with pytest.raises(ValueError, match="normalized_row_count"):
        verify_records(records()[:5])
    wrong = records()
    wrong[1]["fx"] = 1
    with pytest.raises(ValueError, match="fx_mismatch"):
        verify_records(wrong)


def test_mandatory_verification_failure_cannot_become_bridge_success(tmp_path: Path) -> None:
    output = tmp_path / "output"
    output.mkdir()
    candidate = output / "normalized.json"
    candidate.write_text(json.dumps(records()[:5]), encoding="utf-8")
    installed = InstalledCapabilities()
    installed.register(
        SPEC,
        ExportHandler(tmp_path, "http://127.0.0.1:8766"),
        ExportInput,
        ExportResult,
        ExecutionDependencies(central_required=False),
    )
    grant = CapabilityGrant(
        actor="engineer",
        asset=SPEC.identity,
        permissions=SPEC.policy.required_permissions,
        policy_refs=SPEC.policy.policy_refs,
        approval_ref="synthetic-fixture",
    )
    bridge = BridgeExecutor(installed, LocalPolicy((grant,)))
    result = asyncio.run(
        bridge.execute(
            invocation().model_copy(
                update={"target": SPEC.identity, "arguments": {"normalized_path": str(candidate)}}
            )
        )
    )
    assert result.status == "failed" and result.failure is not None
    assert result.failure.code == "oi_verification_failed" and not result.failure.retryable
    assert ExportResult.model_validate(result.data).verification == {
        "passed": False,
        "check": "normalized_row_count",
    }
    assert not (output / "sales-oi-pivot.xlsx").exists()


@pytest.mark.parametrize(
    "status,artifact,exporter,rows,expected",
    [
        ("answered", True, True, 16, True),
        ("needs_input", True, False, 16, False),
        ("answered", True, False, 16, False),
        ("answered", False, True, 16, False),
        ("answered", True, True, 5, False),
    ],
)
def test_task_acceptance_requires_exporter_and_completed_conversation(
    status: str, artifact: bool, exporter: bool, rows: int, expected: bool
) -> None:
    from benchmarks.harness_reliability_sap_oi.acceptance import task_passed

    assert task_passed(status, artifact, exporter, rows) is expected


def test_141_benchmark_drops_only_its_telegram_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    import os

    from benchmarks.harness_reliability_sap_oi.environment import disable_test_telegram

    monkeypatch.setenv("AEP_TELEGRAM_BOT_TOKEN", "synthetic-test-value")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "synthetic-test-value")
    monkeypatch.setenv("TELEGRAM_CONTROL_CHAT_ID", "synthetic-chat")
    monkeypatch.setenv("AEP_GATEWAY_59_KEY", "synthetic-model-key")
    disable_test_telegram()
    assert not any(name.upper().startswith(("TELEGRAM_", "AEP_TELEGRAM_")) for name in os.environ)
    assert os.environ["AEP_GATEWAY_59_KEY"] == "synthetic-model-key"
