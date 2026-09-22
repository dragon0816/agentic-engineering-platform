"""Trace capture with redaction: every run in the repository leaves a record
that joins to its request, keeps the Bridge's order, and scans clean.

The redaction tests feed a credential in and read the record back, because a
redaction that is asserted and never exercised is the same as none. The rule
about the marker is tested on its own: a pattern written as `password: X`
matches its own replacement, and without that rule nothing could be stored
under such a key, which would surface as a trace that refuses to exist for a
run that leaked nothing.
"""

from pathlib import Path

import pytest
from evaluation_runner import GatewayRunner, RepositoryRunner, publish_artifact_spec
from pydantic import ValidationError

from common.assets import AssetIdentity
from common.evaluation import EvaluationCase, ObservedRun, load_cases
from common.execution import Failure, RouteDecision, TraceIdentifiers
from common.trace import MARKER, ExecutionTrace, TraceEvent, carries_credential, redact
from workflow.dispatch import ExecutionEvent

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "evaluation/cases"


def case(case_id: str) -> EvaluationCase:
    return next(item for item in load_cases(CASES) if item.case_id == case_id)


def identifiers(suffix: str = "") -> TraceIdentifiers:
    return TraceIdentifiers(
        trace_id=f"trace{suffix}", request_id=f"request{suffix}", span_id=f"span{suffix}"
    )


def refused(message: str) -> ObservedRun:
    return ObservedRun(
        decision=RouteDecision(kind="needs_input", reason="unknown_command"),
        origin="needs_input",
        failure=Failure(code="unknown_command", message=message),
    )


def test_every_trace_in_the_repository_joins_its_case_is_ordered_and_scans_clean() -> None:
    runner = RepositoryRunner()
    cases = load_cases(CASES)
    for item in cases:
        runner.run(item)
    assert set(runner.traces) == {item.case_id for item in cases}
    for item in cases:
        trace = runner.traces[item.case_id]
        assert trace.trace == item.request.trace
        assert [event.sequence for event in trace.events] == list(range(len(trace.events)))
        assert trace.events[0].kind == "route" and trace.events[-1].kind == "outcome"
        assert not carries_credential(trace.model_dump(mode="json"))
        assert trace.redactions == 0
        # Safe to store means it survives being stored.
        assert ExecutionTrace.model_validate_json(trace.model_dump_json()) == trace


def test_the_scenario_trace_shows_both_dispatches_in_bridge_order() -> None:
    runner = GatewayRunner()
    scenario = case("scenario-release-package")
    observed = runner.run(scenario)
    trace = runner.trace(scenario, observed)
    dispatches = [event for event in trace.events if event.kind == "dispatch"]
    assert [event.asset for event in dispatches] == [event.asset for event in runner.bridge.events]
    assert len(dispatches) == 2
    assert all(event.status == "succeeded" for event in dispatches)
    assert trace.events[0].status == "workflow" and trace.events[0].code == "deterministic"
    assert trace.events[-1].status == "succeeded" and trace.events[-1].code is None
    assert trace.status == "succeeded"
    assert trace.completed_steps == trace.declared_steps == 2
    # Both grants carry an approval reference, so both dispatches were made
    # under one, and the irreversible step is among them. The record names
    # them rather than only what lacked one.
    assert trace.approved == tuple(event.asset for event in dispatches)
    assert publish_artifact_spec().identity in trace.approved
    assert trace.unapproved == ()
    assert trace.model_calls == 0 and trace.duration_ms is None


def test_a_refused_request_traces_as_unresolved_with_its_code() -> None:
    runner = GatewayRunner()
    unknown = case("phase2-unknown-explicit-command")
    observed = runner.run(unknown)
    trace = runner.trace(unknown, observed)
    assert observed.failure is not None
    assert [event.kind for event in trace.events] == ["route", "outcome"]
    assert trace.events[0].status == "needs_input" and trace.events[0].code == "needs_input"
    assert trace.events[-1].status == "unresolved"
    assert trace.events[-1].code == observed.failure.code
    assert trace.dispatched == () and trace.status is None


def test_the_agent_trace_records_the_model_usage() -> None:
    runner = RepositoryRunner()
    _, trace = runner.observe(case("agent-ambiguous-release"))
    assert trace.origin == "model" and trace.events[0].code == "model"
    assert trace.model_calls == 1
    assert (trace.input_tokens, trace.output_tokens) == (12, 5)
    assert trace.duration_ms is not None


def test_a_discovery_proof_traces_as_unrouted_with_nothing_run() -> None:
    _, trace = RepositoryRunner().observe(case("discover-sample-task"))
    assert [event.kind for event in trace.events] == ["route", "outcome"]
    assert trace.events[0].status == "unrouted" and trace.events[0].asset is None
    assert trace.events[-1].status == "nothing_ran"


def test_a_bearer_token_in_a_failure_arrives_redacted_and_counted() -> None:
    observed = refused("upstream answered 401 to Bearer sk-live-4141 and stopped")
    trace = ExecutionTrace.build(identifiers(), observed, ())
    assert trace.failure is not None
    assert trace.failure.message == f"upstream answered 401 to {MARKER} and stopped"
    assert trace.redactions == 1
    assert "sk-live-4141" not in trace.model_dump_json()


def test_a_json_shaped_credential_is_redacted() -> None:
    # A field named for the secret: the value alone is the secret.
    headers = {"headers": {"access_token": "abc"}}
    assert redact(headers) == ({"headers": {"access_token": MARKER}}, 1)
    # JSON inside a string, where the quotes hide the match from a substitution.
    body = 'the provider returned {"access_token": "abc", "expires": 60}'
    assert redact(body, "message") == (MARKER, 1)
    observed = refused(body)
    trace = ExecutionTrace.build(identifiers(), observed, ())
    assert trace.failure is not None and trace.failure.message == MARKER
    assert trace.redactions == 1


def test_redaction_leaves_clean_text_alone_and_counts_nothing() -> None:
    clean = {"message": "the handler timed out after 30s", "steps": ["probe", "report"]}
    assert redact(clean) == (clean, 0)
    assert redact(("a", 1, None, True)) == (["a", 1, None, True], 0)


def test_the_marker_is_not_itself_a_credential() -> None:
    assert carries_credential({"password": "hunter2"})
    assert not carries_credential({"password": MARKER})
    assert carries_credential("Authorization: Bearer abc")
    assert not carries_credential(f"Authorization: {MARKER}")


def test_a_trace_cannot_be_built_around_credential_material() -> None:
    """The validator, not only `build`: a trace assembled from stored parts is
    held to the same rule as one the platform produced."""
    events = (
        TraceEvent(sequence=0, kind="route", status="needs_input", code="needs_input"),
        TraceEvent(sequence=1, kind="outcome", status="unresolved"),
    )
    with pytest.raises(ValidationError, match="credential material"):
        ExecutionTrace(
            trace=identifiers(),
            events=events,
            failure=Failure(code="upstream", message="refused Bearer abc"),
        )
    with pytest.raises(ValidationError, match="credential material"):
        ExecutionTrace(
            trace=identifiers(),
            events=events,
            decision=RouteDecision(kind="needs_input", reason="api_key=abc was rejected"),
        )


def test_an_event_from_another_request_cannot_join_a_trace() -> None:
    foreign = ExecutionEvent(
        trace=identifiers("-other"),
        asset=AssetIdentity(namespace="engineering", name="validate-release", version="1.0.0"),
        status="succeeded",
    )
    with pytest.raises(ValueError, match="another request"):
        ExecutionTrace.build(identifiers(), ObservedRun(), (foreign,))


def test_events_out_of_order_or_out_of_shape_are_refused() -> None:
    route = TraceEvent(sequence=0, kind="route", status="unrouted")
    outcome = TraceEvent(sequence=1, kind="outcome", status="nothing_ran")
    skipped = outcome.model_copy(update={"sequence": 2})
    with pytest.raises(ValidationError, match="without gaps"):
        ExecutionTrace(trace=identifiers(), events=(route, skipped))
    with pytest.raises(ValidationError, match="opens with the route"):
        ExecutionTrace(
            trace=identifiers(),
            events=(
                outcome.model_copy(update={"sequence": 0}),
                route.model_copy(update={"sequence": 1}),
            ),
        )
    with pytest.raises(ValidationError):
        ExecutionTrace(trace=identifiers(), events=(route,))
