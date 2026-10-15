"""Local-only comparison of Laya's typed decisions with AEP's pinned baseline.

Laya is an optional diagnostic dependency. This module has no Agent Web wiring
and never downloads a model: the CLI enables Hugging Face offline mode before
importing Laya. A checkpoint must already exist in the runner's local cache.
"""

from __future__ import annotations

import argparse
import json
import math
import os
from collections.abc import Mapping, Sequence
from pathlib import Path
from time import perf_counter
from typing import Any, Protocol

from evaluation.jev_benchmark import DecisionObservation, baseline_observations, score
from evaluation.jev_live import PUBLIC_CORPUS, _public_cases

LAYA_VERSION = "0.3.24"
PROVIDER_ID = "laya-local"
QUESTION_ID = "selection"
PRESERVE_CATALOG = "preserve_catalog"

_INSTRUCTIONS = {
    "intent_classification": (
        "Choose the best intent for this request. Missing required context needs input."
    ),
    "skill_selection": (
        "Choose one installed command when clearly sufficient. Choose preserve_catalog "
        "when the user asks what tools exist or several commands may be needed."
    ),
    "retrieval_routing": (
        "Choose raw for exact source evidence, wiki for curated guidance, hybrid for both, "
        "or needs_input when no source was supplied."
    ),
    "failure_classification": "Classify the described failure; do not grant permission or retry.",
}


class LocalDecisionRouter(Protocol):
    @property
    def loaded_revisions(self) -> Mapping[str, str | None]: ...

    def predict(
        self, state: str, questions: dict[str, Any], *, model: str
    ) -> Mapping[str, Any]: ...


def _question(kind: str, candidates: tuple[str, ...]) -> dict[str, Any]:
    """Fixed, gold-label-blind mapping from the AEP corpus to one Laya choice."""
    if kind not in _INSTRUCTIONS:
        raise ValueError("unsupported decision type")
    criteria = {name: name.replace("_", " ").replace("-", " ") for name in candidates}
    if kind == "skill_selection":
        criteria[PRESERVE_CATALOG] = (
            "No single command is sufficient; retain all installed commands."
        )
    return {
        QUESTION_ID: {
            "type": "choice",
            "instructions": _INSTRUCTIONS[kind],
            "criteria": criteria,
        }
    }


def _selected(choice: str, candidates: tuple[str, ...]) -> tuple[str, ...]:
    if choice == PRESERVE_CATALOG:
        return candidates
    return (choice,)


def _answer(
    reply: Mapping[str, Any],
    candidates: tuple[str, ...],
    min_confidence: float | None,
    *,
    allow_preserve: bool,
) -> tuple[tuple[str, ...], float | None, str | None]:
    usage = reply.get("usage")
    if isinstance(usage, Mapping) and (
        usage.get("truncated") is True or bool(usage.get("options"))
    ):
        return (), None, "truncated_input"
    answers = reply.get("answers")
    answer = answers.get(QUESTION_ID) if isinstance(answers, Mapping) else None
    if not isinstance(answer, Mapping) or answer.get("type") != "choice":
        return (), None, "invalid_answer"
    choice = answer.get("choice")
    # Laya's entropy-based `confidence` is not the probability of its chosen
    # answer and is not comparable across option counts.
    confidence = answer.get("answer_confidence")
    if (
        not isinstance(choice, str)
        or choice not in candidates
        and not (allow_preserve and choice == PRESERVE_CATALOG)
        or isinstance(confidence, bool)
        or not isinstance(confidence, (float, int))
        or not math.isfinite(confidence)
        or not 0 <= confidence <= 1
    ):
        return (), None, "invalid_answer"
    if min_confidence is not None and confidence < min_confidence:
        return (), float(confidence), "low_confidence"
    return _selected(choice, candidates), float(confidence), None


def run_pinned_benchmark(
    *,
    router: LocalDecisionRouter,
    version: str,
    corpus: Path = PUBLIC_CORPUS,
    model: str = "english",
    trials: int = 1,
    min_confidence: float | None = None,
) -> dict[str, Any]:
    """Exercise only the reviewed PUBLIC corpus using one already-local model."""
    cases = _public_cases(corpus)
    if version != LAYA_VERSION:
        raise ValueError(f"this benchmark requires laya=={LAYA_VERSION}")
    if model != "english":
        raise ValueError("the English corpus is pinned to the English checkpoint")
    if not 1 <= trials <= 5:
        raise ValueError("trials must be between one and five")
    if min_confidence is not None and (
        isinstance(min_confidence, bool)
        or not math.isfinite(min_confidence)
        or not 0 <= min_confidence <= 1
    ):
        raise ValueError("min_confidence must be finite and between zero and one")

    # Loading time is not a per-decision latency. Report it separately so a
    # cold-start claim cannot be mistaken for a warm-inference measurement.
    warm = cases[0]
    warm_started = perf_counter()
    router.predict(warm.request, _question(warm.decision_type, warm.candidates), model=model)
    warmup_ms = (perf_counter() - warm_started) * 1_000

    observations: list[DecisionObservation] = list(baseline_observations(cases))
    for trial in range(trials):
        for case in cases:
            started = perf_counter()
            try:
                reply = router.predict(
                    case.request, _question(case.decision_type, case.candidates), model=model
                )
                selected, confidence, reason = _answer(
                    reply,
                    case.candidates,
                    min_confidence,
                    allow_preserve=case.decision_type == "skill_selection",
                )
            except Exception:
                # An exception may contain model input or a local cache path.
                selected, confidence, reason = (), None, "provider_error"
            observations.append(
                DecisionObservation(
                    case_id=case.case_id,
                    provider_id=PROVIDER_ID,
                    trial=trial,
                    status="answered" if selected else "abstained",
                    selected=selected,
                    confidence=confidence,
                    latency_ms=(perf_counter() - started) * 1_000,
                    fallback_reason=reason,
                    cost_usd=0.0,  # No metered provider call; excludes local hardware cost.
                )
            )
    return {
        "metadata": {
            "provider": PROVIDER_ID,
            "package_version": version,
            "checkpoint": model,
            "checkpoint_revision": router.loaded_revisions.get(model),
            "warmup_ms": warmup_ms,
            "min_confidence": min_confidence,
            "offline": True,
        },
        "metrics": score(cases, observations),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compare local Laya on pinned PUBLIC cases")
    parser.add_argument("--trials", type=int, default=3)
    parser.add_argument("--min-confidence", type=float)
    parser.add_argument("--device", default="cpu", choices=("cpu", "cuda", "xpu", "mps"))
    args = parser.parse_args(argv)
    try:
        _public_cases(PUBLIC_CORPUS)
        # These must precede the Laya/Hugging Face import. A cache miss fails
        # rather than silently downloading a checkpoint during the benchmark.
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
        from importlib.metadata import version

        from laya import Router  # type: ignore[import-not-found]

        router = Router(max_loaded=1, device=args.device)
        report = run_pinned_benchmark(
            router=router,
            version=version("laya"),
            trials=args.trials,
            min_confidence=args.min_confidence,
        )
    except ImportError:
        parser.exit(
            2,
            "Laya is not installed in this Python environment; see evaluation/jev/README.md\n",
        )
    except (OSError, ValueError, RuntimeError) as error:
        parser.exit(2, f"Laya benchmark unavailable: {type(error).__name__}\n")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
