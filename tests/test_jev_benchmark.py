"""A missing bounded baseline stays visible; graders reject malformed evidence."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from evaluation.jev_benchmark import (
    DecisionObservation,
    GoldenDecisionCase,
    baseline_observations,
    load_cases,
    main,
    score,
)

CORPUS = Path(__file__).resolve().parents[1] / "evaluation" / "jev" / "golden-v1.json"


def _case(case_id: str = "one", kind: str = "intent_classification") -> GoldenDecisionCase:
    return GoldenDecisionCase.model_validate(
        {
            "case_id": case_id,
            "decision_type": kind,
            "classification": "PUBLIC",
            "request": "Classify a synthetic test request.",
            "candidates": ["yes", "no"],
            "expected": ["yes"],
        }
    )


def _observation(
    case_id: str = "one",
    *,
    selected: tuple[str, ...] = ("yes",),
    status: str = "answered",
    confidence: float | None = 0.9,
    latency_ms: float | None = 10.0,
    cost_usd: float | None = 0.01,
    fallback_reason: str | None = None,
) -> DecisionObservation:
    return DecisionObservation.model_validate(
        {
            "case_id": case_id,
            "provider_id": "synthetic-replay",
            "status": status,
            "selected": selected,
            "confidence": confidence,
            "latency_ms": latency_ms,
            "cost_usd": cost_usd,
            "fallback_reason": fallback_reason,
        }
    )


def test_corpus_is_public_balanced_and_source_controlled() -> None:
    cases = load_cases(CORPUS)
    assert len(cases) == 16
    assert {case.decision_type for case in cases} == {
        "intent_classification",
        "skill_selection",
        "retrieval_routing",
        "failure_classification",
    }
    assert all(case.classification == "PUBLIC" for case in cases)
    assert all(sum(case.decision_type == kind for case in cases) == 4 for kind in {
        case.decision_type for case in cases
    })
    assert "rohde" not in CORPUS.read_text(encoding="utf-8").lower()


def test_real_none_baseline_reports_only_implemented_skill_decision() -> None:
    cases = load_cases(CORPUS)
    samples = baseline_observations(cases)
    report = score(cases, samples)["aep-none-baseline"]
    skills = report["skill_selection"]
    assert skills["coverage"] == 1.0
    assert skills["exact_accuracy"] == 0.25
    assert skills["fallback_rate"] == 0.0
    assert skills["total_cost_usd"] == 0.0
    assert skills["latency_samples"] == 4
    for kind in ("intent_classification", "retrieval_routing", "failure_classification"):
        assert report[kind]["unavailable"] == 4
        assert report[kind]["coverage"] == 0.0
        assert report[kind]["latency_p50_ms"] is None
        assert report[kind]["total_cost_usd"] is None


def test_metrics_count_fallback_accuracy_calibration_unknown_cost_and_latency() -> None:
    cases = (_case("one"), _case("two"), _case("three"), _case("four"))
    samples = (
        _observation("one", latency_ms=10, confidence=0.9),
        _observation(
            "two", selected=("no",), latency_ms=20, confidence=0.8,
            fallback_reason="accelerator_low_confidence", cost_usd=None,
        ),
        _observation(
            "three", selected=(), status="abstained", confidence=None,
            latency_ms=40, cost_usd=0.0,
        ),
        DecisionObservation(case_id="four", provider_id="synthetic-replay", status="unavailable"),
    )
    metrics = score(cases, samples)["synthetic-replay"]["intent_classification"]
    assert metrics["coverage"] == 0.5
    assert metrics["answered_accuracy"] == 0.5
    assert metrics["exact_accuracy"] == 0.25
    assert metrics["confidence_brier"] == pytest.approx((0.01 + 0.64) / 2)
    assert metrics["latency_p50_ms"] == 20
    assert metrics["latency_p95_ms"] == 40
    assert metrics["fallback_rate"] == pytest.approx(1 / 3)
    assert metrics["fallback_reasons"] == {"accelerator_low_confidence": 1}
    assert metrics["known_cost_usd"] == pytest.approx(0.01)
    assert metrics["unknown_cost_samples"] == 1
    assert metrics["total_cost_usd"] is None


def test_missing_observations_are_not_silently_scored_as_success() -> None:
    cases = (_case("one"), _case("two", "failure_classification"))
    report = score(cases, (_observation(),))["synthetic-replay"]
    missing = report["failure_classification"]
    assert missing["missing_observations"] == 1
    assert missing["coverage"] == 0.0
    assert missing["exact_accuracy"] == 0.0
    assert missing["total_cost_usd"] is None


def test_invalid_case_and_observation_contracts_fail_closed(tmp_path: Path) -> None:
    case = _case()
    with pytest.raises(ValidationError):
        GoldenDecisionCase.model_validate({**case.model_dump(), "classification": "RESTRICTED"})
    with pytest.raises(ValidationError):
        GoldenDecisionCase.model_validate({**case.model_dump(), "expected": ["unknown"]})
    with pytest.raises(ValidationError):
        DecisionObservation(case_id="one", provider_id="p", status="answered")
    with pytest.raises(ValidationError):
        DecisionObservation(
            case_id="one", provider_id="p", status="unavailable", cost_usd=0.0
        )
    with pytest.raises(ValidationError):
        DecisionObservation(
            case_id="one", provider_id="p", status="answered", selected=("yes",),
            latency_ms=float("inf"),
        )
    source = tmp_path / "duplicate.json"
    source.write_text(json.dumps([case.model_dump(), case.model_dump()]), encoding="utf-8")
    with pytest.raises(ValueError, match="unique"):
        load_cases(source)


def test_unknown_or_duplicate_or_uninstalled_predictions_fail_closed() -> None:
    case = _case()
    with pytest.raises(ValueError, match="unknown case"):
        score((case,), (_observation("missing"),))
    with pytest.raises(ValueError, match="duplicate"):
        score((case,), (_observation(), _observation()))
    with pytest.raises(ValueError, match="unknown candidate"):
        score((case,), (_observation(selected=("invented",)),))
    with pytest.raises(ValueError, match="multiple labels"):
        score((case,), (_observation(selected=("yes", "no")),))


def test_repeated_trials_use_all_cases_as_each_trial_denominator() -> None:
    case = _case()
    first = _observation()
    second = first.model_copy(update={"trial": 1, "selected": ("no",)})
    metrics = score((case,), (first, second))["synthetic-replay"]["intent_classification"]
    assert metrics["trials"] == 2
    assert metrics["exact_accuracy"] == 0.5
    assert metrics["missing_observations"] == 0


def test_cli_outputs_only_metric_identifiers_not_case_payload(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["--cases", str(CORPUS)]) == 0
    output = capsys.readouterr().out
    report = json.loads(output)
    assert report["aep-none-baseline"]["skill_selection"]["exact_accuracy"] == 0.25
    assert "sensor voltage" not in output
