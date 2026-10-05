"""Explicit TypeSafe benchmark over one pinned PUBLIC synthetic corpus.

This diagnostic is separate from Agent Web. It cannot send an arbitrary file,
conversation, Skill catalog, or Knowledge material to TypeSafe.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections.abc import Callable, Sequence
from pathlib import Path
from time import perf_counter

from agent.decisions import DecisionAcceleratorConfig
from agent.gateway import SkillCandidateRequest
from agent.jev import JEVSkillSelectionProvider
from common.execution import RequestContext, TraceIdentifiers
from evaluation.jev_benchmark import (
    DecisionObservation,
    GoldenDecisionCase,
    baseline_observations,
    load_cases,
    score,
)
from models import wire
from models.contracts import ModelMessage, ModelRequest, ModelRequirements, ModelTool

PUBLIC_CORPUS = Path(__file__).resolve().parents[2] / "evaluation" / "jev" / "golden-v1.json"
PUBLIC_CORPUS_SHA256 = "4e0192921913d44073c4fdfffa2998c37a3e0f85c67556c5171b6d983a764b9b"
#: Skill selection over the live install's eight Skill commands, English and
#: Chinese, with their real descriptions (2026-10-05, owner request).
SKILLS_CORPUS = PUBLIC_CORPUS.with_name("golden-v2-skills.json")
REVIEWED_CORPORA = {
    PUBLIC_CORPUS.name: PUBLIC_CORPUS_SHA256,
    SKILLS_CORPUS.name: "286d59d42628ebf75368eade78c4d2f95ff4f7493f156b32c1b680ddd98af196",
}
TYPESAFE_SYSTEMONE = "https://api.typesafe.ai/v1/systemone"
KEY_ENV = "AEP_JEV_API_KEY"


def _public_cases(path: Path) -> tuple[GoldenDecisionCase, ...]:
    if hashlib.sha256(path.read_bytes()).hexdigest() != REVIEWED_CORPORA.get(path.name):
        raise ValueError("PUBLIC benchmark corpus does not match its reviewed digest")
    cases = load_cases(path)
    if any(case.classification != "PUBLIC" for case in cases):
        raise ValueError("JEV benchmark accepts PUBLIC cases only")
    return cases


def _candidate(case: GoldenDecisionCase, trial: int) -> SkillCandidateRequest:
    trace = TraceIdentifiers(
        trace_id=f"jev-{case.case_id}-{trial}",
        request_id=f"jev-{case.case_id}-{trial}",
        span_id=f"jev-{case.case_id}-{trial}",
    )
    return SkillCandidateRequest(
        context=RequestContext(
            trace=trace,
            actor="synthetic-evaluator",
            namespace="synthetic",
            channel="evaluation",
            message=case.request,
        ),
        initial_request=ModelRequest(
            trace=trace,
            model_alias="synthetic-evaluation",
            messages=(
                ModelMessage(role="system", text="Synthetic PUBLIC Skill-selection benchmark."),
                ModelMessage(role="user", text=case.request),
            ),
            requirements=ModelRequirements(tool_calling=True),
            tools=tuple(
                ModelTool(
                    name=name,
                    description=case.candidate_descriptions.get(
                        name, f"Synthetic installed command {name}"
                    ),
                    input_contract="synthetic.command.v1",
                )
                for name in case.candidates
            ),
        ),
    )


def run_public_benchmark(
    *,
    corpus: Path = PUBLIC_CORPUS,
    model: str,
    trials: int = 1,
    timeout_ms: int = 3_000,
    credential: Callable[[], str],
    transport: wire.Transport | None = None,
    endpoint: str = TYPESAFE_SYSTEMONE,
) -> dict[str, dict[str, dict[str, object]]]:
    """Benchmark one reviewed corpus; authorization happens before credentials/network."""
    cases = _public_cases(corpus)
    if not 1 <= trials <= 5:
        raise ValueError("JEV benchmark supports one to five trials")
    config = DecisionAcceleratorConfig(
        provider="JEV",
        # Validated like the Host's accelerator endpoint: HTTPS, or HTTP only
        # to this machine (an SSH tunnel to a self-hosted SystemOne service).
        endpoint=endpoint,
        credential={"name": "jev_api_key"},
        model_profile=model,
        timeout_ms=timeout_ms,
        enabled_decision_types=("skill_selection",),
    )
    if not credential().strip():
        raise ValueError("JEV credential is unavailable")
    provider = JEVSkillSelectionProvider(config, credential, transport=transport)
    observations: list[DecisionObservation] = list(baseline_observations(cases))
    for trial in range(trials):
        for case in cases:
            if case.decision_type != "skill_selection":
                observations.append(
                    DecisionObservation(
                        case_id=case.case_id,
                        provider_id="jev-systemone",
                        trial=trial,
                        status="unavailable",
                    )
                )
                continue
            started = perf_counter()
            try:
                result = provider.decide(_candidate(case, trial))
            except Exception:
                # Provider exceptions can contain payloads or bearer values.
                observations.append(
                    DecisionObservation(
                        case_id=case.case_id,
                        provider_id="jev-systemone",
                        trial=trial,
                        status="abstained",
                        latency_ms=(perf_counter() - started) * 1_000,
                        fallback_reason="provider_error",
                    )
                )
                continue
            observations.append(
                DecisionObservation(
                    case_id=case.case_id,
                    provider_id="jev-systemone",
                    trial=trial,
                    status="answered" if result.accepted else "abstained",
                    selected=result.value if result.accepted else (),
                    confidence=result.confidence,
                    latency_ms=(perf_counter() - started) * 1_000,
                    fallback_reason=None if result.accepted else result.reason_code,
                )
            )
    return score(cases, observations)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the reviewed PUBLIC JEV SystemOne benchmark")
    parser.add_argument("--model", required=True, help="Model name returned by TypeSafe /v1/models")
    parser.add_argument("--trials", type=int, default=1)
    parser.add_argument("--timeout-ms", type=int, default=3_000)
    parser.add_argument(
        "--corpus", choices=("v1", "skills"), default="v1",
        help="v1: the original four synthetic cases; skills: the live Skill catalogue",
    )
    parser.add_argument(
        "--endpoint", default=TYPESAFE_SYSTEMONE,
        help="SystemOne URL: HTTPS, or http://127.0.0.1:<port>/v1/systemone through a tunnel",
    )
    args = parser.parse_args(argv)
    try:
        report = run_public_benchmark(
            model=args.model,
            trials=args.trials,
            timeout_ms=args.timeout_ms,
            credential=lambda: os.environ[KEY_ENV],
            endpoint=args.endpoint,
            corpus=SKILLS_CORPUS if args.corpus == "skills" else PUBLIC_CORPUS,
        )
    except (OSError, ValueError, KeyError) as error:
        parser.exit(2, f"JEV benchmark unavailable: {type(error).__name__}\n")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
