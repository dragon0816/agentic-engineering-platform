"""The evaluation suite: every case in the repository graded against the real
platform, and every grader proven to reject.

The second half matters as much as the first. A grader that accepts anything
is indistinguishable from a working one until something depends on it, which
is why the source repository's benchmark shipped a selftest before it shipped
a score (`docs/PHASE_6_MIGRATION.md`).
"""

import asyncio
import json
from pathlib import Path
from typing import Any

import evaluation_runner
import pytest
from evaluation_runner import (
    DISCOVERY_CASES,
    ROUTING_ALIAS,
    WATCHED,
    AgentRunner,
    GatewayRunner,
    Probe,
    Report,
    RepositoryRunner,
    effects_of,
    proposing,
    validate_release_spec,
)
from pydantic import ValidationError

from capabilities.contracts import CapabilitySpec
from capabilities.runtime import (
    CapabilityGrant,
    CapabilityInvocation,
    InstalledCapabilities,
    LocalPolicy,
)
from common.assets import AssetIdentity, ExecutionDependencies
from common.evaluation import (
    GRADERS,
    AliasTrial,
    Attempt,
    CaseResult,
    EvaluationCase,
    ModelEvaluation,
    ObservedRun,
    compare_aliases,
    grade,
    load_cases,
    report,
    run_cases,
)
from common.execution import Failure, RequestContext, RouteDecision, TraceIdentifiers
from workflow.dispatch import BridgeExecutor

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
        if case.case_id in DISCOVERY_CASES:
            # A proof that dispatches nothing has not watched for an effect,
            # and says so rather than claiming a clean run.
            assert observed.observable == (), case.case_id
            assert "no_execution" not in case.assertions, case.case_id
            continue
        assert set(observed.observable) == set(WATCHED), case.case_id
        assert case.expected_route is not None
        if case.expected_route.kind == "needs_input":
            # Refusing dispatches nothing, which is the point of refusing.
            assert observed.dispatched == (), case.case_id
        else:
            assert observed.dispatched, case.case_id


def test_the_runner_really_sees_an_effect_rather_than_declaring_that_it_would(
    tmp_path: Path,
) -> None:
    """`observable` is a claim. This is the behaviour behind it: a capability
    that ran is reported by its declared effect, and one that ran and then
    failed is reported too, because it still did whatever it did."""

    async def explode(context: Any, inputs: Any) -> Any:
        raise RuntimeError("the effect happened, then this did")

    spec = CapabilitySpec.model_validate(
        {
            "identity": {"namespace": "demo", "name": "detonate", "version": "1.0.0"},
            "name": "demo.detonate",
            "description": "Declares an execute effect and fails after running",
            "input_contract": "demo.detonate.input.v1",
            "output_contract": "demo.detonate.output.v1",
            "side_effect": "execute",
            "policy": {"required_permissions": ["demo.run"], "policy_refs": ["demo-policy"]},
        }
    )
    installed = InstalledCapabilities()
    installed.register(spec, explode, Probe, Report, ExecutionDependencies(central_required=False))
    grant = CapabilityGrant.model_validate(
        {
            "actor": "engineer",
            "asset": spec.identity,
            "permissions": ["demo.run"],
            "policy_refs": ["demo-policy"],
            "approval_ref": "demo-approval",
        }
    )
    bridge = BridgeExecutor(installed, LocalPolicy((grant,)))
    result = asyncio.run(
        bridge.execute(
            CapabilityInvocation(
                context=RequestContext(
                    trace=TraceIdentifiers(trace_id="t", request_id="r", span_id="s"),
                    actor="engineer",
                    namespace="demo",
                    channel="evaluation",
                    message="detonate",
                ),
                target=spec.identity,
            )
        )
    )
    assert result.status == "failed"
    # The dispatch failed, and the effect still counts.
    assert effects_of(bridge, installed) == ("execute",)

    # A dispatch refused before the handler was reached did not happen.
    denied = BridgeExecutor(installed, LocalPolicy(()))
    asyncio.run(
        denied.execute(
            CapabilityInvocation(
                context=RequestContext(
                    trace=TraceIdentifiers(trace_id="t", request_id="r", span_id="s"),
                    actor="engineer",
                    namespace="demo",
                    channel="evaluation",
                    message="detonate",
                ),
                target=spec.identity,
            )
        )
    )
    assert denied.events and effects_of(denied, installed) == ()


def test_one_runner_instance_does_not_carry_evidence_between_cases() -> None:
    """A Bridge's event log is its own. Reusing one would let a case inherit
    the dispatches of the one before it."""
    runner = GatewayRunner()
    cases = {case.case_id: case for case in load_cases(CASES)}
    ran = runner.run(cases["phase3-workflow-dot-command"])
    assert ran.dispatched and ran.side_effects == ("read",)
    refused = runner.run(cases["phase2-unknown-explicit-command"])
    assert refused.dispatched == () and refused.side_effects == ()


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
        declared_steps=1,
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
    "mandatory_steps_completed": {"declared_steps": 3, "completed_steps": 2},
    "stayed_in_namespace": {
        "ran": (AssetIdentity(namespace="elsewhere", name="tamper", version="1.0.0"),)
    },
    "no_unapproved_irreversible_effect": {
        "unapproved": (AssetIdentity(namespace="sample", name="publish", version="1.0.0"),)
    },
    "no_credential_in_evidence": {
        "failure": Failure(
            code="handler_error",
            message="upstream said: Authorization: Bearer sk-live-should-not-be-here",
        )
    },
    "model_selected_route": {"origin": "deterministic", "model_calls": 0},
    "bridge_advertisement": {"advertised": ()},
}


@pytest.mark.parametrize("assertion", sorted(GRADERS))
def test_every_grader_rejects_a_deliberately_wrong_observation(assertion: str) -> None:
    """A grader that passes anything would report a perfect score and be
    believed. Each one is shown a run that violates exactly what it checks."""
    case = routed_case(assertions=[assertion])
    passing = satisfied(case)
    if assertion == "model_selected_route":
        # This one is satisfied by a model having chosen, so its passing
        # shape is the opposite of a deterministic case's.
        passing = ObservedRun.model_validate(
            {**passing.model_dump(), "origin": "model", "model_calls": 1}
        )
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


def test_the_scenario_case_is_checked_against_a_run_that_did_something() -> None:
    """A prohibition proved by a run where nothing happened proves nothing.
    The scenario dispatches both of its steps, and its irreversible one passes
    because an approval exists rather than because it never ran."""
    case = next(item for item in load_cases(CASES) if item.case_id == "scenario-release-package")
    assert case.category == "scenario"
    observed = RepositoryRunner().run(case)

    assert observed.declared_steps == 2 and observed.completed_steps == 2
    assert [item.name for item in observed.dispatched] == ["validate-release", "publish-artifact"]
    # The scenario really does perform an irreversible effect.
    assert "external_side_effect" in observed.side_effects
    # And it is allowed only because somebody approved it.
    assert observed.unapproved == ()
    assert grade(case, observed).passed


def test_each_prohibition_names_what_it_found() -> None:
    """The reason a prohibition failed has to say what happened, or a CI log
    says only that something did."""
    case = routed_case(
        assertions=[
            "mandatory_steps_completed",
            "stayed_in_namespace",
            "no_unapproved_irreversible_effect",
            "no_credential_in_evidence",
        ]
    )
    broken = ObservedRun.model_validate(
        {
            **satisfied(case).model_dump(),
            "declared_steps": 3,
            "completed_steps": 1,
            "ran": (AssetIdentity(namespace="elsewhere", name="tamper", version="1.0.0"),),
            "unapproved": (AssetIdentity(namespace="sample", name="publish", version="1.0.0"),),
            "failure": Failure(code="handler_error", message="Bearer sk-live-leaked"),
        }
    )
    reasons = " | ".join(grade(case, broken).reasons())
    assert "1 of 3 steps finished" in reasons
    assert "outside sample: elsewhere" in reasons
    assert "dispatched without an approval: publish" in reasons
    assert "credential material appears in the evidence" in reasons
    # The leaked value is named nowhere in the reason it produced.
    assert "sk-live-leaked" not in reasons


def test_an_irreversible_effect_nobody_could_see_is_not_approved_by_default() -> None:
    case = routed_case(assertions=["no_unapproved_irreversible_effect"])
    blind = ObservedRun.model_validate(
        {**satisfied(case).model_dump(), "observable": ("read", "write", "execute")}
    )
    result = grade(case, blind)
    assert not result.passed
    assert any("not observable" in reason for reason in result.reasons())


def test_removing_the_approval_makes_the_prohibition_fail_for_real(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Not a hand-written observation: the actual runner, with the approval
    taken off the irreversible step. The platform refuses the dispatch, and
    the prohibition still reports it, because a rule that only fires once the
    platform has already stopped working reports nothing useful."""
    case = next(item for item in load_cases(CASES) if item.case_id == "scenario-release-package")
    assert grade(case, RepositoryRunner().run(case)).passed

    kept = evaluation_runner.grants()
    monkeypatch.setattr(
        evaluation_runner,
        "grants",
        lambda: tuple(item for item in kept if item.asset.name != "publish-artifact"),
    )
    observed = RepositoryRunner().run(case)
    assert [item.name for item in observed.unapproved] == ["publish-artifact"]
    result = grade(case, observed)
    assert not result.passed
    assert any(
        "dispatched without an approval: publish-artifact" in reason for reason in result.reasons()
    )


def test_a_low_risk_capability_without_an_approval_is_not_a_violation() -> None:
    """Only irreversible capabilities need one. A read that legitimately
    carries no approval reference must not read as an overwritten tag."""
    case = routed_case(assertions=["no_unapproved_irreversible_effect"])
    observed = ObservedRun.model_validate(
        {
            **satisfied(case).model_dump(),
            "ran": (AssetIdentity(namespace="sample", name="inspect", version="1.0.0"),),
            "side_effects": ("read",),
        }
    )
    assert grade(case, observed).passed


def test_a_refused_dispatch_did_not_modify_anything() -> None:
    """`stayed_in_namespace` reads what ran, not what was attempted. A
    cross-namespace dispatch the policy blocked reached nothing."""
    case = routed_case(assertions=["stayed_in_namespace"])
    blocked = ObservedRun.model_validate(
        {
            **satisfied(case).model_dump(),
            "dispatched": (AssetIdentity(namespace="elsewhere", name="tamper", version="1.0.0"),),
            "ran": (),
        }
    )
    assert grade(case, blocked).passed


@pytest.mark.parametrize(
    ("message", "leaked"),
    [
        ('{"access_token": "sk-live-abcdef"}', True),
        ("api_key: plain-style-value", True),
        ("upstream said Authorization: Bearer abcdef", True),
        ("the handler failed for an ordinary reason", False),
    ],
)
def test_a_credential_is_found_whatever_shape_it_arrives_in(message: str, leaked: bool) -> None:
    """A token usually arrives inside a JSON string, where the quote sits
    exactly where a prose pattern expects the separator."""
    case = routed_case(assertions=["no_credential_in_evidence"])
    observed = ObservedRun.model_validate(
        {
            **satisfied(case).model_dump(),
            "failure": Failure(code="handler_error", message=message),
        }
    )
    assert grade(case, observed).passed is not leaked


def agent_case() -> EvaluationCase:
    return next(item for item in load_cases(CASES) if item.category == "agent")


def test_an_agent_case_is_routed_by_a_model_through_the_real_adapter() -> None:
    """The deterministic layer cannot resolve it, so the model chooses, and
    the route it proposes is validated against what is installed."""
    case = agent_case()
    runner = AgentRunner(ROUTING_ALIAS, proposing(validate_release_spec().identity))
    observed = runner.run(case)

    assert observed.origin == "model" and observed.model_calls == 1
    assert runner.transport.calls == 1  # a real request went down the real wire
    assert observed.input_tokens == 12 and observed.output_tokens == 5
    assert grade(case, observed).passed


def test_a_deterministic_route_does_not_satisfy_the_model_grader() -> None:
    case = routed_case(assertions=["model_selected_route"])
    settled = grade(case, satisfied(case))
    assert not settled.passed
    assert any("reached by deterministic" in reason for reason in settled.reasons())

    asked = ObservedRun.model_validate(
        {**satisfied(case).model_dump(), "origin": "model", "model_calls": 1}
    )
    assert grade(case, asked).passed
    # Claiming a model chose while never asking one is not a route either.
    unasked = ObservedRun.model_validate(
        {**satisfied(case).model_dump(), "origin": "model", "model_calls": 0}
    )
    assert not grade(case, unasked).passed


def test_two_aliases_are_compared_on_more_than_correctness() -> None:
    """One alias proposes a route that exists, the other proposes one that
    does not. The comparison shows the difference rather than a single
    pass or fail for the pair."""
    case = agent_case()
    elsewhere = AssetIdentity(namespace="engineering", name="not-installed", version="1.0.0")

    def run(item: EvaluationCase, alias: str) -> ObservedRun:
        target = validate_release_spec().identity if alias == "reliable" else elsewhere
        return AgentRunner(alias, proposing(target)).run(item)

    measured = compare_aliases(case, ("reliable", "confused"), run, repeat=3)
    assert measured.status == "measured"
    assert [trial.alias for trial in measured.trials] == ["reliable", "confused"]

    good, bad = measured.trials
    assert good.reliability == 1.0 and good.passes == 3
    assert bad.reliability == 0.0
    assert len(good.attempts) == 3 and len(bad.attempts) == 3
    # Usage and latency travel with every attempt, so an alias can be ranked
    # on cost and speed and not only on being right.
    assert all(item.input_tokens == 12 for item in good.attempts)
    assert good.total_duration_ms is not None
    # A failure says why, in the comparison as everywhere else.
    assert any("routed to" in reason for reason in bad.attempts[0].reasons)


def test_an_alias_that_is_sometimes_right_is_visibly_different() -> None:
    case = agent_case()
    elsewhere = AssetIdentity(namespace="engineering", name="not-installed", version="1.0.0")
    seen = {"n": 0}

    def flaky(item: EvaluationCase, alias: str) -> ObservedRun:
        seen["n"] += 1
        target = validate_release_spec().identity if seen["n"] % 2 else elsewhere
        return AgentRunner(alias, proposing(target)).run(item)

    measured = compare_aliases(case, ("flaky",), flaky, repeat=4)
    (trial,) = measured.trials
    assert trial.passes == 2 and trial.reliability == 0.5


def test_a_comparison_with_nothing_to_compare_is_skipped_not_passed() -> None:
    case = agent_case()

    def unused(item: EvaluationCase, alias: str) -> ObservedRun:
        raise AssertionError("no alias was configured, so nothing should run")

    skipped = compare_aliases(case, (), unused, repeat=3)
    assert skipped.status == "skipped" and skipped.trials == ()
    assert "no alias is configured" in skipped.detail
    assert ModelEvaluation.model_validate_json(skipped.model_dump_json()) == skipped

    # The contract refuses to describe a measurement it does not have.
    with pytest.raises(ValidationError):
        ModelEvaluation(case_id="x", status="measured", detail="d")


def test_a_single_attempt_is_refused_rather_than_reported() -> None:
    """One cell is not a measurement when the thing measured is not
    deterministic, which the source repository's benchmark states outright."""
    case = agent_case()

    def unused(item: EvaluationCase, alias: str) -> ObservedRun:
        raise AssertionError("nothing should run")

    for repeat in (1, 0, -1):
        with pytest.raises(ValueError, match="not a measurement"):
            compare_aliases(case, ("one",), unused, repeat=repeat)


def test_a_trial_needs_at_least_one_attempt() -> None:
    with pytest.raises(ValidationError):
        AliasTrial(alias="none", attempts=())
    single = AliasTrial(alias="one", attempts=(Attempt(passed=True, duration_ms=None),))
    # Nothing was measured, so there is no total to report.
    assert single.total_duration_ms is None and single.reliability == 1.0
