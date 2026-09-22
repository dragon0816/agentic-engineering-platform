"""Trace capture with redaction: every run in the repository leaves a record
that joins to its request, keeps the Bridge's order, and scans clean.

The redaction tests feed a credential in and read the record back, because a
redaction that is asserted and never exercised is the same as none. Three of
them exist because the first review found the key material still in the
record: a private key whose header alone was removed, a quoted password cut
at its first space, and a secret under a `password` key that happened to be a
mapping. The rule about the marker is tested on its own: a pattern written as
`password: X` matched its own replacement, and without that rule nothing
could be stored under such a key.
"""

from pathlib import Path

import pytest
from evaluation_runner import GatewayRunner, RepositoryRunner, publish_artifact_spec
from pydantic import ValidationError

from common.assets import REDACTED, SECRET_PATTERN, AssetIdentity, reject_embedded_secrets
from common.evaluation import EvaluationCase, ObservedRun, load_cases
from common.execution import Failure, RouteDecision, TraceIdentifiers
from common.trace import ExecutionTrace, TraceEvent, carries_credential, redact
from workflow.dispatch import ExecutionEvent

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "evaluation/cases"
PEM = "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA\n-----END RSA PRIVATE KEY-----"


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


def bracketed() -> tuple[TraceEvent, TraceEvent]:
    return (
        TraceEvent(sequence=0, kind="route", status="needs_input", code="needs_input"),
        TraceEvent(sequence=1, kind="outcome", status="unresolved"),
    )


def identity(name: str) -> AssetIdentity:
    return AssetIdentity(namespace="engineering", name=name, version="1.0.0")


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
    assert trace.failure.message == f"upstream answered 401 to {REDACTED} and stopped"
    assert trace.redactions == 1
    assert "sk-live-4141" not in trace.model_dump_json()


def test_a_private_key_is_removed_whole_not_only_its_header() -> None:
    """Found by review: the pattern named the header, so the base64 body was
    stored in a record the validator accepted as clean."""
    trace = ExecutionTrace.build(identifiers(), refused(f"the vault returned {PEM} to us"), ())
    assert trace.failure is not None
    assert trace.failure.message == f"the vault returned {REDACTED} to us"
    assert "MIIEow" not in trace.model_dump_json()
    # A block that was cut off before its END line is removed to the end.
    cut = PEM.split("\n-----END")[0] + "\nMIIEowMore"
    assert redact(f"partial {cut}") == (f"partial {REDACTED}", 1)


def test_a_quoted_credential_with_a_space_is_removed_whole() -> None:
    """Found by review: `\\S+` stopped at the first space inside the quotes,
    and the tail of the password was stored."""
    assert redact('password: "abc def" rejected', "message") == (f"{REDACTED} rejected", 1)
    assert redact("api_key='p q r' expired") == (f"{REDACTED} expired", 1)


def test_a_json_shaped_credential_is_redacted() -> None:
    # A field named for the secret: the value alone is the secret.
    headers = {"headers": {"access_token": "abc"}}
    assert redact(headers) == ({"headers": {"access_token": REDACTED}}, 1)
    # JSON inside a string, where the quotes hide the match from a substitution.
    body = 'the provider returned {"access_token": "abc", "expires": 60}'
    assert redact(body, "message") == (REDACTED, 1)
    observed = refused(body)
    trace = ExecutionTrace.build(identifiers(), observed, ())
    assert trace.failure is not None and trace.failure.message == REDACTED
    assert trace.redactions == 1


def test_a_secret_under_a_credential_key_is_removed_whatever_its_shape() -> None:
    """Found by review: a mapping under `password` relabelled its children
    with their own innocent names, so nothing scanned and nothing was removed."""
    nested = {"password": {"value": "hunter2", "type": "basic"}}
    assert carries_credential(nested)
    assert redact(nested) == ({"password": REDACTED}, 1)
    assert redact({"password": ["hunter2", "hunter3"]}) == ({"password": REDACTED}, 1)
    assert not carries_credential({"password": REDACTED})
    assert not carries_credential({"password": None})
    assert redact({"password": None}) == ({"password": None}, 0)


def test_redaction_is_idempotent_and_leaves_clean_text_alone() -> None:
    clean = {"message": "the handler timed out after 30s", "steps": ["probe", "report"]}
    assert redact(clean) == (clean, 0)
    assert redact(("a", 1, None, True)) == (["a", 1, None, True], 0)
    once, count = redact({"note": "Bearer abc", "password": "x", "fine": "yes"})
    assert count == 2
    assert redact(once) == (once, 0)


def test_the_marker_is_not_itself_a_credential() -> None:
    """The pattern refuses its own replacement, so the rule holds wherever
    the pattern is used: the trace, the evidence grader, the adapters and the
    registry's rejection of embedded secrets."""
    assert carries_credential({"password": "hunter2"})
    assert not carries_credential({"password": REDACTED})
    assert carries_credential("Authorization: Bearer abc")
    assert not carries_credential(f"Authorization: {REDACTED}")
    assert SECRET_PATTERN.search(f"password: {REDACTED}") is None
    reject_embedded_secrets({"note": f"password: {REDACTED}"})
    with pytest.raises(ValueError):
        reject_embedded_secrets({"note": "password: hunter2"})


def test_a_trace_cannot_be_built_around_credential_material() -> None:
    """The validator, not only `build`: a trace assembled from stored parts is
    held to the same rule as one the platform produced."""
    with pytest.raises(ValidationError, match="credential material"):
        ExecutionTrace(
            trace=identifiers(),
            events=bracketed(),
            failure=Failure(code="upstream", message="refused Bearer abc"),
        )
    with pytest.raises(ValidationError, match="credential material"):
        ExecutionTrace(
            trace=identifiers(),
            events=bracketed(),
            decision=RouteDecision(kind="needs_input", reason="api_key=abc was rejected"),
        )
    with pytest.raises(ValidationError, match="credential material"):
        ExecutionTrace(
            trace=identifiers(),
            events=bracketed(),
            failure=Failure(code="upstream", message=f"the vault returned {PEM}"),
        )


def test_a_stored_trace_cannot_claim_more_than_its_dispatches() -> None:
    """Found by review: `approved` is defined as dispatched identities, and a
    record assembled by a host could name an approval for something that was
    never dispatched."""
    validate, publish = identity("validate-release"), identity("publish-artifact")
    route = TraceEvent(sequence=0, kind="route", status="workflow", code="deterministic")
    dispatch = TraceEvent(sequence=1, kind="dispatch", asset=validate, status="succeeded")
    outcome = TraceEvent(sequence=2, kind="outcome", status="succeeded")
    consistent = ExecutionTrace(
        trace=identifiers(),
        events=(route, dispatch, outcome),
        dispatched=(validate,),
        ran=(validate,),
        approved=(validate,),
    )
    assert consistent.approved == (validate,)
    with pytest.raises(ValidationError, match="never dispatched"):
        ExecutionTrace.model_validate({**consistent.model_dump(), "approved": (publish,)})
    with pytest.raises(ValidationError, match="never dispatched"):
        ExecutionTrace(trace=identifiers(), events=bracketed(), ran=(validate,))
    with pytest.raises(ValidationError, match="same identities in order"):
        ExecutionTrace(trace=identifiers(), events=(route, dispatch, outcome), dispatched=())
    with pytest.raises(ValidationError, match="under an approval or without one"):
        ExecutionTrace(
            trace=identifiers(),
            events=(route, dispatch, outcome),
            dispatched=(validate,),
            approved=(validate,),
            unapproved=(validate,),
        )


def test_an_event_from_another_request_cannot_join_a_trace() -> None:
    foreign = ExecutionEvent(
        trace=identifiers("-other"), asset=identity("validate-release"), status="succeeded"
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
