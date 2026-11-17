"""BI vault V11 (owner 2026-10-29; `docs/phases/BI_VAULT.md` §12): the evidence
rules of the manager's knowledge bases are part of every AI extraction.

The fixed rules sit in the system prompt whatever the method says; the A–D
evidence grades are explained when a type grades evidence; a domain adds its
own classification notes; and a number the model calls a fact must be written
in its quote (an amount in 兆 / 億 included), else it becomes an inference.
The model is scripted; no provider is called. All data is fictional.
"""

from __future__ import annotations

from typing import Any

from test_bi_extract import Scripted

from aep_bi.cards import extract
from aep_bi.cards.schema import shipped

V2 = shipped()[1]
REPORT = """# 虛構產業報告

虛構電力公司 2025 年營收 1兆1,586億元，伺服器電源占 59%。
虛構散熱公司營收約 75–80 億元。
"""


def _run(model: Scripted, types: tuple[str, ...], notes: str = "") -> extract.Extraction:
    return extract.extract(
        model,
        "test-model",
        V2,
        text=REPORT,
        source_id="src1",
        source_name="report.md",
        types=types,
        instructions="方法自己的規則：只讀營收。",
        known={},
        domain_notes=notes,
    )


def test_the_evidence_rules_are_always_in_the_system_prompt() -> None:
    model = Scripted({"candidates": []}, {"candidates": []})
    _run(model, ("Signal",))
    system = model.requests[0].messages[0].text
    assert "Evidence rules (always apply)" in system and "No source, no value" in system
    assert "never today's date" in system and "no SAMPLE- names" in system
    assert "方法自己的規則：只讀營收。" in system  # the method's rules follow, unchanged
    assert "evidence_grade: A =" not in system  # no type here grades evidence
    assert "The knowledge base's own rules" not in system
    _run(model, ("SupplyLink",), notes="- AIDC：ODM 是 Account，晶片廠是 Ecosystem。")
    graded = model.requests[1].messages[0].text
    assert "evidence_grade: A =" in graded and "Only A and B" in graded
    assert graded.index("Evidence rules") < graded.index("方法自己的規則")
    assert graded.rstrip().endswith("- AIDC：ODM 是 Account，晶片廠是 Ecosystem。")
    # The source stays out of the system message (data, not instructions).
    assert "虛構電力公司" not in graded and "虛構電力公司" in model.requests[1].messages[1].text


def _revenue(amount: Any, quote: str) -> dict[str, Any]:
    return {
        "candidates": [
            {
                "entity_type": "RevenueFact",
                "name": "虛構電力公司 2025 營收",
                "fields": {
                    "amount": {"value": amount, "basis": "fact", "quote": quote},
                    "unit": {"value": "億TWD", "basis": "inference", "reason": "報告的單位"},
                },
            }
        ]
    }


def _field(result: extract.Extraction, name: str) -> dict[str, Any]:
    (card,) = result.candidates
    return next(f for f in card["fields"] if f["field"] == name)


def test_a_written_amount_stays_a_fact_and_a_made_up_one_does_not() -> None:
    converted = _run(Scripted(_revenue(11586, "營收 1兆1,586億元")), ("RevenueFact",))
    amount = _field(converted, "amount")
    assert amount["value"] == 11586.0 and amount["basis"] == "fact" and amount["evidence"]
    made_up = _run(Scripted(_revenue(77.5, "營收約 75–80 億元")), ("RevenueFact",))
    guessed = _field(made_up, "amount")
    assert guessed["basis"] == "inference" and guessed["evidence"] == []
    (card,) = made_up.candidates
    assert any(w["code"] == "number_not_in_quote" for w in card["warnings"])


def test_written_numbers_reads_scale_amounts() -> None:
    assert extract.number_written(11586, "1兆1,586億元")
    assert extract.number_written(25300, "2.53兆元") and extract.number_written(2.53, "2.53兆元")
    assert extract.number_written(1234, "營收 1,234 億") and extract.number_written(59, "占 59%")
    assert not extract.number_written(77.5, "75–80%")
