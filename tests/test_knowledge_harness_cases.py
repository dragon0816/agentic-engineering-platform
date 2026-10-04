"""Owner's standalone and combined Knowledge validation cases stay honest."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from evaluation.knowledge_harness import KnowledgeHarnessSuite

CASES = Path(__file__).resolve().parents[1] / "evaluation/knowledge/harness-cases-v1.json"


def test_suite_covers_standalone_and_combined_strategy_without_asserting_facts() -> None:
    suite = KnowledgeHarnessSuite.model_validate_json(CASES.read_text(encoding="utf-8"))
    assert {case.facets[0] for case in suite.cases if case.tier == "standalone"} == {
        "market_trend", "product_option_spec", "technical_knowledge"
    }
    strategy = next(case for case in suite.cases if "swot" in case.outputs)
    assert set(strategy.facets) == {
        "market_trend", "product_option_spec", "technical_knowledge", "competitor"
    }
    assert {"strategy", "swot", "execution_actions"} <= set(strategy.outputs)
    assert all(case.evidence_rule == "raw_citations_or_explicit_gap" for case in suite.cases)
    assert KnowledgeHarnessSuite.model_validate(suite.model_dump(mode="json")) == suite


def test_strategy_cannot_pass_as_a_single_facet_or_omit_competitor() -> None:
    payload = json.loads(CASES.read_text(encoding="utf-8"))
    payload["cases"][-1]["facets"].remove("competitor")
    with pytest.raises(ValidationError, match="all four evidence facets"):
        KnowledgeHarnessSuite.model_validate(payload)
    payload = json.loads(CASES.read_text(encoding="utf-8"))
    payload["cases"][-1]["tier"] = "standalone"
    with pytest.raises(ValidationError, match="standalone cases"):
        KnowledgeHarnessSuite.model_validate(payload)
