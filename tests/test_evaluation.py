"""The evaluation suite: every case in the repository graded against the real
platform, and every grader proven to reject.

The second half matters as much as the first. A grader that accepts anything
is indistinguishable from a working one until something depends on it, which
is why the source repository's benchmark shipped a selftest before it shipped
a score (`docs/PHASE_6_MIGRATION.md`).
"""

import json
from pathlib import Path
from typing import Any

import pytest
from evaluation_runner import WATCHED, GatewayRunner, RepositoryRunner

from common.assets import AssetIdentity
from common.evaluation import (
    GRADERS,
    CaseResult,
    EvaluationCase,
    ObservedRun,
    grade,
    load_cases,
    report,
    run_cases,
)
from common.execution import RouteDecision

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "evaluation/cases"


def test_every_case_in_the_repository_passes_against_the_real_platform() -> None:
    cases = load_cases(CASES)
    assert len(cases) >= 6
    results = run_cases(cases, RepositoryRunner())
    summary = report(results)
    assert all(result.passed for result in results), summary
    assert summary.endswith(f"{len(cases)}/{len(cases)} cases passed")
    # Every declared assertion is understood; a typo must not read as a pass.
    assert not any(result.unknown_assertions for result in results)
    for result in results:
        assert CaseResult.model_validate_json(result.model_dump_json()) == result


def test_every_routed_case_is_exercised_where_execution_could_be_seen() -> None:
    """The gap slice 1 left: four cases were observed through a bare router or
    the registry proof, so `no_execution` passed without being able to fail."""
    runner = RepositoryRunner()
    for case in load_cases(CASES):
        observed = runner.run(case)
        assert set(observed.observable) == set(WATCHED), case.case_id
        if case.expected_route is None:
            continue
        if case.expected_route.kind == "needs_input":
            # Refusing dispatches nothing, which is the point of refusing.
            assert observed.dispatched == (), case.case_id
        else:
            assert observed.dispatched, case.case_id


def test_a_capability_the_repository_never_installs_is_still_dispatched() -> None:
    """`legacy/run-testing` has routing but no implementation on purpose. That
    the route resolved and nothing ran is the observation; no attempt at all
    would not be."""
    case = next(item for item in load_cases(CASES) if item.case_id == "phase2-known-command")
    observed = GatewayRunner().run(case)
    assert [item.name for item in observed.dispatched] == ["run-testing"]
    assert observed.side_effects == ()
    assert grade(case, observed).passed


def test_every_declared_assertion_has_a_grader() -> None:
    declared = {name for case in load_cases(CASES) for name in case.assertions}
    assert declared <= set(GRADERS), sorted(declared - set(GRADERS))
    # And no grader exists that nothing exercises, so the selftest below is
    # not proving something the suite never uses.
    assert set(GRADERS) == declared


def routed_case(**changes: Any) -> EvaluationCase:
    return EvaluationCase.model_validate(
        {
            "case_id": "synthetic",
            "category": "deterministic",
            "request": {
                "trace": {"trace_id": "t", "request_id": "r", "span_id": "s"},
                "actor": "engineer",
                "namespace": "sample",
                "message": "do the thing",
                "channel": "evaluation",
            },
            "expected_route": {
                "kind": "capability",
                "target": {"namespace": "sample", "name": "inspect", "version": "1.0.0"},
                "reason": "known",
            },
            "forbidden_side_effects": ["write", "execute", "external_side_effect"],
            "assertions": [],
            **changes,
        }
    )


def satisfied(case: EvaluationCase) -> ObservedRun:
    return ObservedRun(
        decision=case.expected_route,
        origin="deterministic",
        model_calls=0,
        side_effects=("read",),
        status="succeeded",
        completed_steps=1,
        observable=WATCHED,
        discovered=(case.expected_route.target,) if case.expected_route else (),
        lifecycle=("published",),
        advertised=(case.expected_route.target,) if case.expected_route else (),
        installed=(case.expected_route.target,) if case.expected_route else (),
    )


WRONG: dict[str, dict[str, Any]] = {
    "no_model_call": {"model_calls": 1},
    "no_execution": {"side_effects": ("execute",)},
    "exact_scoped_target": {
        "decision": RouteDecision(
            kind="capability",
            target={"namespace": "sample", "name": "other", "version": "1.0.0"},
            reason="known",
        )
    },
    "deterministic_trigger": {"origin": "model"},
    "fail_closed": {"decision": None},
    "workflow_succeeds": {"status": "failed"},
    "scoped_identity": {
        "decision": None,
        "discovered": (AssetIdentity(namespace="elsewhere", name="inspect", version="1.0.0"),),
    },
    "published_discovery": {"lifecycle": ("draft",)},
    "bridge_advertisement": {"advertised": ()},
}


@pytest.mark.parametrize("assertion", sorted(GRADERS))
def test_every_grader_rejects_a_deliberately_wrong_observation(assertion: str) -> None:
    """A grader that passes anything would report a perfect score and be
    believed. Each one is shown a run that violates exactly what it checks."""
    case = routed_case(assertions=[assertion])
    passing = satisfied(case)
    if assertion == "fail_closed":
        # This one is satisfied by refusing, so its passing shape is different.
        case = routed_case(
            assertions=[assertion],
            expected_route={"kind": "needs_input", "reason": "unknown command"},
        )
        passing = ObservedRun(
            decision=case.expected_route, origin="deterministic", observable=WATCHED
        )

    assert grade(case, passing).passed, grade(case, passing).reasons()

    broken = ObservedRun.model_validate({**passing.model_dump(), **WRONG[assertion]})
    result = grade(case, broken)
    assert not result.passed
    assert any(item.assertion == assertion and not item.passed for item in result.grades)
    assert any(assertion in reason for reason in result.reasons())


def test_an_unrecognised_assertion_fails_its_case_rather_than_passing() -> None:
    case = routed_case(assertions=["no_model_call", "invented_assertion"])
    result = grade(case, satisfied(case))
    assert not result.passed
    assert result.unknown_assertions == ("invented_assertion",)
    assert any("no grader is registered" in reason for reason in result.reasons())
    # The graders that do exist still ran, so the report says everything.
    assert any(item.assertion == "no_model_call" and item.passed for item in result.grades)


def test_a_forbidden_side_effect_and_a_wrong_route_are_always_checked() -> None:
    case = routed_case(assertions=[])
    trespass = grade(
        case,
        ObservedRun.model_validate({**satisfied(case).model_dump(), "side_effects": ("write",)}),
    )
    assert not trespass.passed
    assert any("forbidden: write" in reason for reason in trespass.reasons())

    astray = grade(case, ObservedRun(decision=None))
    assert not astray.passed
    assert any("routed to nothing" in reason for reason in astray.reasons())

    # A wrong target of the right kind is the common mistake, so the reason
    # names the target rather than only the kind.
    elsewhere = RouteDecision(
        kind="capability",
        target=AssetIdentity(namespace="sample", name="other", version="1.0.0"),
        reason="known",
    )
    wrong = grade(
        case, ObservedRun.model_validate({**satisfied(case).model_dump(), "decision": elsewhere})
    )
    assert not wrong.passed
    assert any("sample/other@1.0.0" in reason for reason in wrong.reasons())

    # Refusing is not failing open just because something permitted happened.
    refusing = routed_case(
        assertions=["fail_closed"], expected_route={"kind": "needs_input", "reason": "unknown"}
    )
    permitted = ObservedRun(
        decision=refusing.expected_route,
        origin="needs_input",
        side_effects=("read",),
        observable=WATCHED,
    )
    assert grade(refusing, permitted).passed


def test_cases_load_in_a_stable_order_and_refuse_a_repeated_id(tmp_path: Path) -> None:
    first = load_cases(CASES)
    assert [case.case_id for case in first] == [case.case_id for case in load_cases(CASES)]

    payload = json.loads((CASES / "phase2-routing.json").read_text(encoding="utf-8"))
    (tmp_path / "a.json").write_text(json.dumps(payload), encoding="utf-8")
    (tmp_path / "b.json").write_text(json.dumps(payload[:1]), encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate case id"):
        load_cases(tmp_path)

    # A file may hold one case or many.
    (tmp_path / "b.json").unlink()
    assert len(load_cases(tmp_path)) == len(payload)


def test_the_report_names_every_failure_and_its_reason() -> None:
    case = routed_case(assertions=["no_model_call"])
    lines = report([grade(case, satisfied(case)), grade(case, ObservedRun(model_calls=2))])
    assert "PASS synthetic" in lines
    assert "FAIL synthetic" in lines
    assert "no_model_call: 2 model call(s) were made" in lines
    assert lines.endswith("1/2 cases passed")


def test_a_check_that_could_not_have_seen_its_evidence_does_not_pass() -> None:
    """Absence of evidence is not evidence of absence. A run that was not
    watching for an effect leaves the case unproven, not satisfied."""
    case = routed_case(assertions=["no_execution"])
    blind = ObservedRun.model_validate({**satisfied(case).model_dump(), "observable": ("read",)})
    result = grade(case, blind)
    assert not result.passed
    assert any("not observable" in reason for reason in result.reasons())
    assert any("execution was not observable" in reason for reason in result.reasons())

    # The always-on forbidden check refuses the same way, naming what it
    # could not see rather than reporting a clean run.
    quiet = routed_case(assertions=[])
    unwatched = ObservedRun.model_validate(
        {**satisfied(quiet).model_dump(), "observable": ("read", "execute")}
    )
    missed = grade(quiet, unwatched)
    assert not missed.passed
    assert any("not observable here: write" in reason for reason in missed.reasons())

    # And a run that was watching, and saw nothing, passes.
    assert grade(case, satisfied(case)).passed
