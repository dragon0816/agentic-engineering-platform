"""The optional Laya benchmark is local, pinned and schema-checked."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from evaluation.jev_live import PUBLIC_CORPUS
from evaluation.laya_offline import (
    _answer,
    _question,
    _selected,
    run_pinned_benchmark,
)


class FakeRouter:
    loaded_revisions = {"english": "pinned-checkpoint-sha"}

    def __init__(self, *, answer: str = "read-file", confidence: float = 0.9) -> None:
        self.answer = answer
        self.confidence = confidence
        self.calls: list[tuple[str, dict[str, Any], str]] = []

    def predict(self, state: str, questions: dict[str, Any], *, model: str) -> Mapping[str, Any]:
        self.calls.append((state, questions, model))
        choices = questions["selection"]["criteria"]
        choice = self.answer if self.answer in choices else next(iter(choices))
        return {
            "answers": {
                "selection": {
                    "type": "choice",
                    "choice": choice,
                    "answer_confidence": self.confidence,
                    "confidence": 0.8,
                }
            }
        }


def test_question_uses_declared_candidates_and_preserve_catalog_without_gold_label() -> None:
    cases = json.loads(PUBLIC_CORPUS.read_text(encoding="utf-8"))
    skill = next(case for case in cases if case["case_id"] == "skill-file")
    question = _question(skill["decision_type"], tuple(skill["candidates"]))
    criteria = question["selection"]["criteria"]
    assert set(criteria) == {*skill["candidates"], "preserve_catalog"}
    assert "read-file" not in question["selection"]["instructions"]
    assert _selected("preserve_catalog", tuple(skill["candidates"])) == tuple(skill["candidates"])


def test_pinned_benchmark_scores_all_four_types_and_records_revision() -> None:
    router = FakeRouter()
    report = run_pinned_benchmark(router=router, version="0.3.24", trials=2)
    assert len(router.calls) == 33  # one warm-up plus 16 cases times two trials
    assert all(model == "english" for _, _, model in router.calls)
    assert report["metadata"]["checkpoint_revision"] == "pinned-checkpoint-sha"
    assert report["metrics"]["laya-local"]["skill_selection"]["cases"] == 4
    assert report["metrics"]["laya-local"]["intent_classification"]["cases"] == 4
    assert report["metrics"]["laya-local"]["retrieval_routing"]["cases"] == 4
    assert report["metrics"]["laya-local"]["failure_classification"]["cases"] == 4
    serialized = json.dumps(report)
    assert "Read the local public example" not in serialized


def test_changed_corpus_is_rejected_before_model_inference(tmp_path: Path) -> None:
    altered = tmp_path / "cases.json"
    altered.write_bytes(PUBLIC_CORPUS.read_bytes() + b" ")
    router = FakeRouter()
    with pytest.raises(ValueError, match="reviewed digest"):
        run_pinned_benchmark(router=router, version="0.3.24", corpus=altered)
    assert router.calls == []


def test_low_answer_confidence_abstains_when_threshold_requested() -> None:
    router = FakeRouter(confidence=0.4)
    report = run_pinned_benchmark(router=router, version="0.3.24", min_confidence=0.6)
    measured = report["metrics"]["laya-local"]["skill_selection"]
    assert measured["answered"] == 0
    assert measured["abstained"] == 4
    assert measured["fallback_reasons"] == {"low_confidence": 4}


def test_wrong_package_version_is_rejected_before_inference() -> None:
    router = FakeRouter()
    with pytest.raises(ValueError, match="laya==0.3.24"):
        run_pinned_benchmark(router=router, version="0.3.23")
    assert router.calls == []


def test_preserve_catalog_is_invalid_outside_skill_selection() -> None:
    reply = {
        "answers": {
            "selection": {
                "type": "choice",
                "choice": "preserve_catalog",
                "answer_confidence": 0.9,
            }
        }
    }
    assert _answer(reply, ("raw", "wiki"), None, allow_preserve=False) == (
        (),
        None,
        "invalid_answer",
    )


def test_entropy_confidence_cannot_substitute_for_answer_probability() -> None:
    reply = {"answers": {"selection": {"type": "choice", "choice": "raw", "confidence": 0.99}}}
    assert _answer(reply, ("raw", "wiki"), None, allow_preserve=False) == (
        (),
        None,
        "invalid_answer",
    )


def test_truncated_model_input_is_not_scored_as_a_valid_decision() -> None:
    reply = {
        "usage": {"truncated": True},
        "answers": {
            "selection": {
                "type": "choice",
                "choice": "raw",
                "answer_confidence": 0.99,
            }
        },
    }
    assert _answer(reply, ("raw", "wiki"), None, allow_preserve=False) == (
        (),
        None,
        "truncated_input",
    )
