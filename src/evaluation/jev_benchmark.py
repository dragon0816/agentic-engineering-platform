"""Offline, payload-free benchmark for optional bounded decision providers.

Only Skill candidate selection has a live bounded baseline today. Other types
are reported as unavailable until they have a real baseline implementation;
the benchmark never fabricates model answers or treats missing data as zero cost.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from collections.abc import Sequence
from pathlib import Path
from statistics import mean
from typing import Literal, Self

from pydantic import Field, ValidationError, model_validator

from agent.decisions import ACCELERABLE_TYPES, DecisionService
from agent.gateway import SkillCandidateRequest, _InstalledSkillCandidates
from common.base import Contract, Symbol, Text
from common.execution import RequestContext, TraceIdentifiers
from models.contracts import ModelMessage, ModelRequest, ModelRequirements, ModelTool

DecisionKind = Literal[
    "intent_classification", "skill_selection", "retrieval_routing", "failure_classification"
]
ObservationStatus = Literal["answered", "abstained", "unavailable"]


class GoldenDecisionCase(Contract):
    """One PUBLIC synthetic request and a reviewer-defined exact expected set."""

    case_id: Symbol
    decision_type: DecisionKind
    classification: Literal["PUBLIC"]
    request: Text
    candidates: tuple[Symbol, ...] = Field(min_length=2)
    expected: tuple[Symbol, ...] = Field(min_length=1)
    # What the selector is told each candidate does, as the installed Skill
    # describes it; a candidate without one gets a placeholder.
    candidate_descriptions: dict[Symbol, Text] = Field(default_factory=dict)
    # Each candidate's Skill `selector_hint`, as the Gateway passes it.
    candidate_hints: dict[Symbol, Text] = Field(default_factory=dict)

    @model_validator(mode="after")
    def closed_labels(self) -> Self:
        if self.decision_type not in ACCELERABLE_TYPES:
            raise ValueError("this decision cannot be accelerated")
        if len(set(self.candidates)) != len(self.candidates):
            raise ValueError("candidate labels must be unique")
        if len(set(self.expected)) != len(self.expected) or not set(self.expected) <= set(
            self.candidates
        ):
            raise ValueError("expected labels must be unique installed candidates")
        if self.decision_type != "skill_selection" and len(self.expected) != 1:
            raise ValueError("classification cases require exactly one label")
        if not (set(self.candidate_descriptions) | set(self.candidate_hints)) <= set(
            self.candidates
        ):
            raise ValueError("descriptions and hints name only candidates")
        return self


class DecisionObservation(Contract):
    """Observed provider output; unavailable is explicit, not a free correct answer."""

    case_id: Symbol
    provider_id: Symbol
    trial: int = Field(default=0, ge=0, strict=True)
    status: ObservationStatus
    selected: tuple[Symbol, ...] = ()
    confidence: float | None = Field(default=None, ge=0, le=1, allow_inf_nan=False)
    latency_ms: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    fallback_reason: Symbol | None = None
    cost_usd: float | None = Field(default=None, ge=0, allow_inf_nan=False)

    @model_validator(mode="after")
    def observation_shape(self) -> Self:
        if len(set(self.selected)) != len(self.selected):
            raise ValueError("selected labels must be unique")
        if self.status == "answered" and not self.selected:
            raise ValueError("an answer must select at least one label")
        if self.status != "answered" and self.selected:
            raise ValueError("an unanswered observation cannot select a label")
        if self.status == "unavailable" and any(
            value is not None
            for value in (self.confidence, self.latency_ms, self.fallback_reason, self.cost_usd)
        ):
            raise ValueError("unavailable has no measured provider data")
        return self


def load_cases(path: Path) -> tuple[GoldenDecisionCase, ...]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list) or not raw:
        raise ValueError("golden corpus must be a nonempty JSON array")
    cases = tuple(GoldenDecisionCase.model_validate(item) for item in raw)
    if len({item.case_id for item in cases}) != len(cases):
        raise ValueError("golden case IDs must be unique")
    return cases


def load_observations(path: Path) -> tuple[DecisionObservation, ...]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list) or not raw:
        raise ValueError("observations must be a nonempty JSON array")
    return tuple(DecisionObservation.model_validate(item) for item in raw)


def baseline_observations(cases: Sequence[GoldenDecisionCase]) -> tuple[DecisionObservation, ...]:
    """Exercise the real NONE Skill baseline; expose other missing baselines."""
    provider = _InstalledSkillCandidates()
    service = DecisionService[SkillCandidateRequest, tuple[str, ...]](baseline=provider)
    observations: list[DecisionObservation] = []
    for case in cases:
        if case.decision_type != "skill_selection":
            observations.append(
                DecisionObservation(
                    case_id=case.case_id, provider_id="aep-none-baseline", status="unavailable"
                )
            )
            continue
        trace = TraceIdentifiers(
            trace_id=f"jev-{case.case_id}",
            request_id=f"jev-{case.case_id}",
            span_id=f"jev-{case.case_id}",
        )
        context = RequestContext(
            trace=trace,
            actor="synthetic-evaluator",
            namespace="synthetic",
            channel="evaluation",
            message=case.request,
        )
        tools = tuple(
                ModelTool(
                    name=name,
                    description=f"Synthetic installed command {name}",
                    input_contract="synthetic.command.v1",
                )
                for name in case.candidates
        )
        request = SkillCandidateRequest(
            context=context,
            initial_request=ModelRequest(
                trace=trace,
                model_alias="synthetic-evaluation",
                messages=(ModelMessage(role="user", text=case.request),),
                requirements=ModelRequirements(tool_calling=True),
                tools=tools,
            ),
        )
        observed = service.decide(request, decision_type="skill_selection")
        observations.append(
            DecisionObservation(
                case_id=case.case_id,
                provider_id="aep-none-baseline",
                status="answered",
                selected=observed.result.value,
                confidence=observed.trace.confidence,
                latency_ms=observed.trace.latency_ms,
                cost_usd=0.0,  # The rule baseline makes no model call.
            )
        )
    return tuple(observations)


def _percentile(values: Sequence[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    # Nearest-rank percentile; defined for a single measured observation.
    position = max(0, math.ceil(fraction * len(ordered)) - 1)
    return ordered[min(position, len(ordered) - 1)]


def _metrics(
    cases: Sequence[GoldenDecisionCase],
    observations: Sequence[DecisionObservation],
    trials: set[int],
) -> dict[str, object]:
    by_case = {case.case_id: case for case in cases}
    expected_count = len(cases) * len(trials)
    seen = {(item.case_id, item.trial) for item in observations}
    available = [item for item in observations if item.status != "unavailable"]
    answered = [item for item in available if item.status == "answered"]
    correct = [
        item
        for item in answered
        if set(item.selected) == set(by_case[item.case_id].expected)
    ]
    latency = [item.latency_ms for item in available if item.latency_ms is not None]
    known_cost = [item.cost_usd for item in available if item.cost_usd is not None]
    calibration = [
        (item.confidence - float(item in correct)) ** 2
        for item in answered
        if item.confidence is not None
    ]
    fallback = Counter(item.fallback_reason for item in available if item.fallback_reason)
    return {
        "cases": len(cases),
        "trials": len(trials),
        "expected_observations": expected_count,
        "missing_observations": expected_count - len(seen),
        "unavailable": sum(item.status == "unavailable" for item in observations),
        "answered": len(answered),
        "abstained": sum(item.status == "abstained" for item in available),
        "coverage": len(answered) / expected_count if expected_count else None,
        "exact_accuracy": len(correct) / expected_count if expected_count else None,
        "answered_accuracy": len(correct) / len(answered) if answered else None,
        "confidence_brier": mean(calibration) if calibration else None,
        "confidence_samples": len(calibration),
        "latency_p50_ms": _percentile(latency, 0.50),
        "latency_p95_ms": _percentile(latency, 0.95),
        "latency_samples": len(latency),
        "fallback_rate": sum(fallback.values()) / len(available) if available else None,
        "fallback_reasons": dict(sorted(fallback.items())),
        "known_cost_usd": sum(known_cost),
        "unknown_cost_samples": len(available) - len(known_cost),
        "total_cost_usd": (
            sum(known_cost) if available and len(known_cost) == len(available) else None
        ),
    }


def score(
    cases: Sequence[GoldenDecisionCase], observations: Sequence[DecisionObservation]
) -> dict[str, dict[str, dict[str, object]]]:
    """Exact labels and coverage; missing evidence cannot improve a score."""
    if not cases or not observations:
        raise ValueError("cases and observations must be nonempty")
    by_case = {case.case_id: case for case in cases}
    if len(by_case) != len(cases):
        raise ValueError("case IDs must be unique")
    seen: set[tuple[str, str, int]] = set()
    groups: dict[str, list[DecisionObservation]] = defaultdict(list)
    for item in observations:
        case = by_case.get(item.case_id)
        if case is None:
            raise ValueError("observation references an unknown case")
        key = (item.provider_id, item.case_id, item.trial)
        if key in seen:
            raise ValueError("duplicate provider/case/trial observation")
        seen.add(key)
        if not set(item.selected) <= set(case.candidates):
            raise ValueError("provider selected an uninstalled or unknown candidate")
        if case.decision_type != "skill_selection" and len(item.selected) > 1:
            raise ValueError("classification selected multiple labels")
        groups[item.provider_id].append(item)
    report: dict[str, dict[str, dict[str, object]]] = {}
    for provider, items in sorted(groups.items()):
        report[provider] = {}
        trials = {item.trial for item in items}
        for kind in sorted(ACCELERABLE_TYPES):
            kind_cases = [case for case in cases if case.decision_type == kind]
            if kind_cases:
                kind_items = [item for item in items if by_case[item.case_id].decision_type == kind]
                report[provider][kind] = _metrics(kind_cases, kind_items, trials)
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Score PUBLIC synthetic bounded decisions offline")
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--observations", type=Path)
    args = parser.parse_args(argv)
    try:
        cases = load_cases(args.cases)
        observations = (
            load_observations(args.observations)
            if args.observations is not None
            else baseline_observations(cases)
        )
        print(json.dumps(score(cases, observations), indent=2, sort_keys=True))
    except (OSError, ValueError, ValidationError) as error:
        parser.exit(2, f"invalid benchmark input: {type(error).__name__}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
