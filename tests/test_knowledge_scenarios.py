"""Owner's standalone and combined Knowledge validation cases stay honest."""

import json
from itertools import combinations
from pathlib import Path

import pytest
from pydantic import ValidationError

from evaluation.knowledge_scenarios import KnowledgeScenarioSuite
from knowledge.procedure import KnowledgeProcedure

CASES = Path(__file__).resolve().parents[1] / "evaluation/knowledge/scenarios-v1.json"


def test_suite_covers_standalone_and_combined_strategy_without_asserting_facts() -> None:
    suite = KnowledgeScenarioSuite.model_validate_json(CASES.read_text(encoding="utf-8"))
    assert {case.facets[0] for case in suite.cases if case.tier == "standalone"} == {
        "market_trend", "product_option_spec", "technical_knowledge", "competitor"
    }
    facets = ("market_trend", "product_option_spec", "technical_knowledge", "competitor")
    assert {frozenset(case.facets) for case in suite.cases} == {
        frozenset(items) for size in range(1, 5)
        for items in combinations(facets, size)
    }
    strategy = next(case for case in suite.cases if "swot" in case.outputs)
    assert set(strategy.facets) == {
        "market_trend", "product_option_spec", "technical_knowledge", "competitor"
    }
    assert {"strategy", "swot", "execution_actions"} <= set(strategy.outputs)
    assert all(case.evidence_rule == "raw_citations_or_explicit_gap" for case in suite.cases)
    assert KnowledgeScenarioSuite.model_validate(suite.model_dump(mode="json")) == suite


def test_candidate_skill_selects_exact_facets_for_all_15_owner_questions() -> None:
    skill_path = CASES.parents[2] / "tests/fixtures/harness_skills/knowledge-evidence-v1.2.json"
    payload = json.loads(skill_path.read_text(encoding="utf-8"))
    procedure = KnowledgeProcedure.model_validate(payload["procedure"])
    suite = KnowledgeScenarioSuite.model_validate_json(CASES.read_text(encoding="utf-8"))
    for case in suite.cases:
        assert procedure.matches_intent(case.question), case.case_id
        assert {facet.name for facet in procedure.requested_facets(case.question)} == set(
            case.facets
        ), case.case_id


def test_strategy_cannot_pass_as_a_single_facet_or_omit_competitor() -> None:
    payload = json.loads(CASES.read_text(encoding="utf-8"))
    payload["cases"][-1]["facets"].remove("competitor")
    with pytest.raises(ValidationError, match="all four evidence facets"):
        KnowledgeScenarioSuite.model_validate(payload)
    payload = json.loads(CASES.read_text(encoding="utf-8"))
    payload["cases"][-1]["tier"] = "standalone"
    with pytest.raises(ValidationError, match="standalone cases"):
        KnowledgeScenarioSuite.model_validate(payload)


def test_suite_rejects_an_omitted_combination_even_with_fifteen_cases() -> None:
    payload = json.loads(CASES.read_text(encoding="utf-8"))
    missing = next(
        index for index, case in enumerate(payload["cases"])
        if case["case_id"] == "market-technical-wireless"
    )
    payload["cases"][missing] = dict(payload["cases"][missing])
    payload["cases"][missing]["facets"] = ["market_trend", "product_option_spec"]
    with pytest.raises(ValidationError, match="all 15 nonempty"):
        KnowledgeScenarioSuite.model_validate(payload)
