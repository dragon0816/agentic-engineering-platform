"""Summaries in extraction and the publish warning (`BI_CARD_MODEL.md` §3.6, task T7).

No model runs: an answer is given to `extract.candidate` as the model's would be.
All data is fictional.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from test_bi_vault import _call, _import, _ok, _push, _row, _two_pcs

from capabilities.bi_cards import catalog, extract
from capabilities.bi_cards.schema import Registry

V4, V5 = "bi.schema/v1.1@4.0.0", "bi.schema/v1.1@5.0.0"
TEXT = "FAKE-A 是一種虛構的同步技術，用於機器人。"


@pytest.fixture
def reg(tmp_path: Path) -> Registry:
    return catalog.resolve(tmp_path, V5)


def _candidate(reg: Registry, entity: str, fields: dict[str, Any]) -> dict[str, Any]:
    chunk = extract.chunks(TEXT)[0]
    return extract.candidate(
        reg, reg.type(entity), {"name": "FAKE-A", "fields": fields}, chunk, "s"
    )


def _field(found: dict[str, Any], name: str) -> dict[str, Any] | None:
    return next((f for f in found["fields"] if f["field"] == name), None)


def test_a_reading_is_inference_whatever_the_model_called_it(reg: Registry) -> None:
    found = _candidate(
        reg,
        "Technology",
        {
            "summary": {"value": "虛構的同步技術", "basis": "fact", "quote": "同步技術"},
            "usage": {"value": "機器人同步", "basis": "inference", "reason": "原文提到"},
            "scope": {"value": "機器人", "basis": "fact", "quote": "not in the text"},
        },
    )
    for name in ("summary", "usage", "scope"):
        item = _field(found, name)
        assert item is not None
        assert item["basis"] == "inference"
        assert item["evidence"] == []
    # Nothing here for a person to act on, on every card.
    assert not [w for w in found["warnings"] if w["code"] in ("inference", "evidence_not_found")]


@pytest.mark.parametrize(
    "entry",
    [
        {"value": "看起來像同步技術", "basis": "unknown"},
        {"value": "unknown", "basis": "inference"},
        {"value": "UNKNOWN", "basis": "fact", "quote": "同步"},
        {"value": "", "basis": "inference"},
    ],
)
def test_unknown_writes_nothing(reg: Registry, entry: dict[str, Any]) -> None:
    found = _candidate(reg, "Technology", {"summary": entry})
    assert _field(found, "summary") is None
    assert found["value_errors"] == []


def test_a_sourced_summary_stays_a_sourced_field(reg: Registry) -> None:
    found = _candidate(
        reg, "Signal", {"summary": {"value": "同步技術", "basis": "fact", "quote": "同步技術"}}
    )
    item = _field(found, "summary")
    assert item is not None
    assert item["basis"] == "fact"
    assert item["evidence"][0]["excerpt"] == "同步技術"
    unknown = _candidate(reg, "Signal", {"summary": {"value": "同步技術", "basis": "unknown"}})
    assert _field(unknown, "summary") is not None


def test_the_prompt_asks_only_where_the_schema_has_them(reg: Registry, tmp_path: Path) -> None:
    chunk = extract.chunks(TEXT)[0]
    asked = extract.messages(reg, ["Technology"], "", {}, chunk, "s.md")[0].text
    assert extract.READING_RULES in asked
    assert "    usage:" in asked and "    scope:" in asked
    old = catalog.resolve(tmp_path, V4)
    assert (
        extract.READING_RULES
        not in extract.messages(old, ["Technology"], "", {}, chunk, "s")[0].text
    )
    signal_only = extract.messages(old, ["Signal"], "", {}, chunk, "s")[0].text
    assert extract.READING_RULES not in signal_only


def test_two_chunks_keep_the_first_reading_with_no_conflict(reg: Registry) -> None:
    first = _candidate(reg, "Technology", {"summary": {"value": "第一段", "basis": "inference"}})
    other = _candidate(reg, "Technology", {"summary": {"value": "第二段", "basis": "inference"}})
    extract.merge(first, other)
    item = _field(first, "summary")
    assert item is not None
    assert item["value"] == "第一段"
    assert not [w for w in first["warnings"] if w["code"] == "value_conflict"]


def test_a_different_ordinary_value_is_still_a_conflict(reg: Registry) -> None:
    first = _candidate(reg, "Technology", {"maturity": {"value": "growth", "basis": "inference"}})
    other = _candidate(reg, "Technology", {"maturity": {"value": "mature", "basis": "inference"}})
    extract.merge(first, other)
    assert [w for w in first["warnings"] if w["code"] == "value_conflict"]


def _publish(ws: Path, vault_id: str, name: str) -> dict[str, Any]:
    _push(ws, vault_id)
    _ok(_call(ws, "POST", f"/api/bi/vaults/{vault_id}/tag", {"name": name, "purpose": "虛構版本"}))
    body = {"tag": name, "confirm": True}
    return _ok(_call(ws, "POST", f"/api/bi/vaults/{vault_id}/publish", body))


def test_publish_counts_cards_with_no_summary_per_type_and_never_blocks(tmp_path: Path) -> None:
    _, vault_id, dataset, a, _ = _two_pcs(tmp_path)
    _import(a, dataset, _row("FAKE-A"), _row("FAKE-B"), _row("FAKE-C", summary="有摘要"))
    answer = _publish(a, vault_id, "v1")
    assert answer["published"]["tag"] == "v1"
    assert answer["summary_missing"] == {"total": 2, "by_type": {"Technology": 2}}


def test_publish_says_nothing_when_every_card_has_a_summary(tmp_path: Path) -> None:
    _, vault_id, dataset, a, _ = _two_pcs(tmp_path)
    _import(a, dataset, _row("FAKE-C", summary="有摘要"))
    assert "summary_missing" not in _publish(a, vault_id, "v1")
