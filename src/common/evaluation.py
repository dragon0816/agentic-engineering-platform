"""Portable cases for deterministic, agent and scenario evaluation, and the
harness that decides whether one passed.

`EvaluationCase.assertions` has named what must hold since Phase 1, and until
now nothing read it: a case could declare `no_execution` while the test that
loaded it never looked for execution, and a misspelled assertion was
indistinguishable from a satisfied one. Here the declarations decide.

Two rules keep that honest, both learned from the source repository's
benchmark (`docs/PHASE_6_MIGRATION.md`). An assertion with no grader fails its
case, because a harness that ignores what it does not understand reports a
perfect score and is believed. And a grader reads evidence of what happened
rather than a flag claiming that it did, because a check against a claim is
not a check.
"""

import json
from collections.abc import Callable, Iterable, Iterator, Mapping
from pathlib import Path
from typing import Literal, Protocol, Self

from pydantic import Field, model_validator

from common.assets import REDACTED, SECRET_FIELD, SECRET_PATTERN, AssetIdentity
from common.base import Contract, Symbol, Text
from common.execution import Failure, RequestContext, RouteDecision, RunStatus, SideEffect

Category = Literal["deterministic", "agent", "scenario"]
# Mirrors `agent.routing.RoutingOutcome.origin`, so an observation can record
# what the platform actually reported rather than a narrowed version of it.
Origin = Literal["deterministic", "model", "needs_input"]


class EvaluationCase(Contract):
    """One thing the platform must keep doing. `expected_route` is absent for a
    case that is not a routed request: discovery and Bridge advertisement are
    control-plane concerns with no route to take, and Phase 6 found that
    requiring one there could only be satisfied by copying the case's own
    words back into the observation (`docs/PHASE_6_MIGRATION.md`)."""

    case_id: Symbol
    category: Category
    request: RequestContext
    expected_route: RouteDecision | None = None
    forbidden_side_effects: tuple[SideEffect, ...]
    assertions: tuple[Symbol, ...]


class ObservedRun(Contract):
    """What actually happened when a case was exercised. Every field is
    evidence a grader can check: a route that was taken, a count of calls that
    were made, effects that occurred. Nothing here asserts that an assertion
    holds, because grading a claim checks nothing."""

    decision: RouteDecision | None = None
    origin: Origin | None = None
    model_calls: int = Field(default=0, ge=0, strict=True)
    side_effects: tuple[SideEffect, ...] = ()
    # What this run was capable of detecting. A run that could not have seen
    # an effect must say so: an empty `side_effects` from a harness that was
    # not looking reads exactly like proof that nothing happened, and that is
    # the shape of check this phase exists to remove.
    observable: tuple[SideEffect, ...] = ()
    # Every capability the Bridge was asked to run, whether or not it was
    # installed, authorized or reached. That a route resolved and nothing ran
    # is an observation; no attempt at all is not.
    dispatched: tuple[AssetIdentity, ...] = ()
    status: RunStatus | None = None
    completed_steps: int = Field(default=0, ge=0, strict=True)
    # How many steps the workflow the case triggered declares. A mandatory
    # test that was skipped is a declared step that did not finish.
    declared_steps: int = Field(default=0, ge=0, strict=True)
    # Capabilities whose handler actually ran, as opposed to every dispatch
    # attempted. A dispatch the policy refused modified nothing.
    ran: tuple[AssetIdentity, ...] = ()
    # What the model call cost and how long it took, carried through from
    # Phase 5 so a comparison can rank aliases on more than correctness.
    duration_ms: int | None = Field(default=None, ge=0, strict=True)
    input_tokens: int = Field(default=0, ge=0, strict=True)
    output_tokens: int = Field(default=0, ge=0, strict=True)
    # Capabilities declaring an irreversible effect that were *dispatched*
    # without a grant carrying an approval reference. Attempted rather than
    # invoked on purpose: the policy refuses such a dispatch today, so reading
    # only what ran would make this grader unable to fail while the platform
    # works, and silent about the moment it stops.
    unapproved: tuple[AssetIdentity, ...] = ()
    # For a case about discovery rather than a request: what was found, the
    # lifecycle of each registered asset (as registered, not as filtered by a
    # query that already drops anything unpublished), the capabilities a
    # Bridge advertises and the tasks it reports installed. Identities rather
    # than names, because a capability's name and its identity's name are not
    # the same string.
    discovered: tuple[AssetIdentity, ...] = ()
    lifecycle: tuple[Symbol, ...] = ()
    advertised: tuple[AssetIdentity, ...] = ()
    installed: tuple[AssetIdentity, ...] = ()
    failure: Failure | None = None


# A grader is satisfied (None) or says why it is not.
Grader = Callable[[EvaluationCase, ObservedRun], str | None]


def _no_model_call(case: EvaluationCase, observed: ObservedRun) -> str | None:
    if observed.model_calls:
        return f"{observed.model_calls} model call(s) were made"
    return None


EXECUTING: tuple[SideEffect, ...] = ("execute", "external_side_effect")


def _unobservable(observed: ObservedRun, effects: Iterable[SideEffect]) -> tuple[str, ...]:
    """The effects a check would need to have seen and could not."""
    return tuple(item for item in effects if item not in observed.observable)


def _no_execution(case: EvaluationCase, observed: ObservedRun) -> str | None:
    blind = _unobservable(observed, EXECUTING)
    if blind:
        return f"execution was not observable here ({', '.join(blind)} unwatched)"
    ran = [effect for effect in observed.side_effects if effect in EXECUTING]
    return f"executed: {', '.join(ran)}" if ran else None


def _exact_scoped_target(case: EvaluationCase, observed: ObservedRun) -> str | None:
    expected = case.expected_route.target if case.expected_route is not None else None
    actual = observed.decision.target if observed.decision is not None else None
    if expected is None:
        return "the case expects no target, so there is nothing to match exactly"
    if actual is None:
        return "no target was reached"
    if actual != expected:
        return f"reached {actual.namespace}/{actual.name}@{actual.version}"
    return None


def _deterministic_trigger(case: EvaluationCase, observed: ObservedRun) -> str | None:
    if observed.origin != "deterministic":
        return f"the route was reached by {observed.origin or 'nothing'}"
    return None


def _fail_closed(case: EvaluationCase, observed: ObservedRun) -> str | None:
    if observed.decision is None:
        return "nothing was decided"
    if observed.decision.kind != "needs_input":
        return f"the request resolved to {observed.decision.kind} instead of needs_input"
    # Refusing means doing nothing the case forbade, not doing nothing at all:
    # a permitted read is not a way of failing open.
    trespass = [item for item in observed.side_effects if item in case.forbidden_side_effects]
    if trespass:
        return f"effects occurred anyway: {', '.join(trespass)}"
    return None


def _workflow_succeeds(case: EvaluationCase, observed: ObservedRun) -> str | None:
    if observed.status != "succeeded":
        return f"the run ended {observed.status or 'without a status'}"
    if observed.completed_steps < 1:
        return "no step completed"
    return None


def _scoped_identity(case: EvaluationCase, observed: ObservedRun) -> str | None:
    """What was found belongs to the namespace that was asked about. That an
    identity has all three parts is guaranteed by `AssetIdentity` itself, so
    checking it here would be a grader that cannot fail; what is not
    guaranteed is that a query stays inside its scope."""
    found = observed.discovered or (
        (observed.decision.target,)
        if observed.decision is not None and observed.decision.target is not None
        else ()
    )
    if not found:
        return "nothing carried a scoped identity"
    strayed = [item for item in found if item.namespace != case.request.namespace]
    if strayed:
        return f"outside {case.request.namespace}: {', '.join(i.namespace for i in strayed)}"
    return None


def _published_discovery(case: EvaluationCase, observed: ObservedRun) -> str | None:
    if not observed.discovered:
        return "nothing was discovered"
    unpublished = [state for state in observed.lifecycle if state != "published"]
    if unpublished or not observed.lifecycle:
        return f"registered as {', '.join(observed.lifecycle) or 'nothing'}"
    return None


def _bridge_advertisement(case: EvaluationCase, observed: ObservedRun) -> str | None:
    """A Bridge reports that it can run what was found. Identities are
    compared, never names: a capability is named `sample.inspect` while the
    identity it carries is named `inspect`."""
    expected = case.expected_route.target if case.expected_route is not None else None
    if expected is not None:
        if expected not in observed.advertised:
            return f"no bridge advertised {expected.namespace}/{expected.name}"
        return None
    if not observed.discovered:
        return "nothing was discovered to advertise"
    missing = [item for item in observed.discovered if item not in observed.installed]
    if missing:
        return f"discovered but not installed: {', '.join(item.name for item in missing)}"
    return None


def _mandatory_steps_completed(case: EvaluationCase, observed: ObservedRun) -> str | None:
    if not observed.declared_steps:
        return "the run declared no steps, so nothing required it to finish"
    if observed.completed_steps < observed.declared_steps:
        return f"{observed.completed_steps} of {observed.declared_steps} steps finished"
    return None


def _stayed_in_namespace(case: EvaluationCase, observed: ObservedRun) -> str | None:
    """Touching an unrelated repository is, to a platform, *running* a
    capability outside the namespace the request named. A dispatch the policy
    refused reached nothing, so it modified nothing."""
    strayed = [item for item in observed.ran if item.namespace != case.request.namespace]
    if strayed:
        return f"outside {case.request.namespace}: {', '.join(i.namespace for i in strayed)}"
    return None


def _no_unapproved_irreversible_effect(case: EvaluationCase, observed: ObservedRun) -> str | None:
    if "external_side_effect" not in observed.observable:
        return "an irreversible effect was not observable here"
    if observed.unapproved:
        named = ", ".join(item.name for item in observed.unapproved)
        return f"dispatched without an approval: {named}"
    return None


def labelled(value: object, label: str = "") -> Iterator[str]:
    """Every string in the evidence, paired with the field that holds it.
    Shared with `common.trace`, so what redaction removes and what this
    grader refuses are decided by one rule.
    `SECRET_PATTERN` is written for prose (`api_key: value`), and JSON puts a
    quote between the two, so scanning the raw document would miss exactly
    the shape a leaked credential arrives in. A label that names a secret is
    inherited by everything beneath it: the value under `password` is a
    secret whatever its shape, so a mapping there reads as `password: <each
    string in it>` rather than as a run of innocently named fields."""
    if isinstance(value, str):
        # Quotes are stripped because a leaked token usually arrives inside a
        # JSON string, where `"access_token": "..."` puts a quote exactly
        # where the pattern expects the separator.
        text = value.replace('"', "").replace("'", "")
        yield f"{label}: {text}" if label else text
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from labelled(item, label if SECRET_FIELD.match(label) else str(key))
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from labelled(item, label)


def _model_selected_route(case: EvaluationCase, observed: ObservedRun) -> str | None:
    """The mirror of `deterministic_trigger`: this case exists because the
    deterministic layer could not resolve it, so a model had to choose."""
    if observed.origin != "model":
        return f"the route was reached by {observed.origin or 'nothing'}"
    if not observed.model_calls:
        return "no model was asked, so nothing it could have chosen"
    return None


def _no_credential_in_evidence(case: EvaluationCase, observed: ObservedRun) -> str | None:
    """A token echoed into a failure message surfaces in the evidence, which
    is exactly where a reader would meet it."""
    for line in labelled(observed.model_dump(mode="json")):
        if SECRET_PATTERN.search(line):
            return "credential material appears in the evidence"
    return None


GRADERS: Mapping[str, Grader] = {
    "no_model_call": _no_model_call,
    "no_execution": _no_execution,
    "exact_scoped_target": _exact_scoped_target,
    "deterministic_trigger": _deterministic_trigger,
    "fail_closed": _fail_closed,
    "workflow_succeeds": _workflow_succeeds,
    "scoped_identity": _scoped_identity,
    "published_discovery": _published_discovery,
    "bridge_advertisement": _bridge_advertisement,
    "mandatory_steps_completed": _mandatory_steps_completed,
    "stayed_in_namespace": _stayed_in_namespace,
    "no_unapproved_irreversible_effect": _no_unapproved_irreversible_effect,
    "no_credential_in_evidence": _no_credential_in_evidence,
    "model_selected_route": _model_selected_route,
}


class GradeOutcome(Contract):
    assertion: Symbol
    passed: bool
    detail: Text = "satisfied"


class CaseResult(Contract):
    case_id: Symbol
    passed: bool
    grades: tuple[GradeOutcome, ...] = ()
    unknown_assertions: tuple[Symbol, ...] = ()

    def reasons(self) -> tuple[str, ...]:
        named = tuple(
            f"{grade.assertion}: {grade.detail}" for grade in self.grades if not grade.passed
        )
        unknown = tuple(f"{name}: no grader is registered" for name in self.unknown_assertions)
        return named + unknown


def _describe(decision: RouteDecision | None) -> str:
    """Enough of a route to see what went wrong: a wrong target of the right
    kind is the common case, and naming only the kind hides it."""
    if decision is None:
        return "nothing"
    if decision.target is None:
        return decision.kind
    target = decision.target
    return f"{decision.kind} {target.namespace}/{target.name}@{target.version}"


def grade(
    case: EvaluationCase, observed: ObservedRun, *, graders: Mapping[str, Grader] = GRADERS
) -> CaseResult:
    """Everything the case declared, checked. The route and the forbidden
    effects are always checked, because they are part of every case; the named
    assertions are checked by their graders, and a name with no grader fails
    rather than passing quietly."""
    grades: list[GradeOutcome] = []
    if case.expected_route is not None:
        matched = observed.decision == case.expected_route
        grades.append(
            GradeOutcome(
                assertion="expected_route",
                passed=matched,
                detail="satisfied" if matched else f"routed to {_describe(observed.decision)}",
            )
        )
    # Absence of evidence is not evidence of absence: a forbidden effect the
    # run could not have seen leaves the case unproven, not satisfied.
    blind = _unobservable(observed, case.forbidden_side_effects)
    trespass = [effect for effect in observed.side_effects if effect in case.forbidden_side_effects]
    if blind:
        detail = f"not observable here: {', '.join(blind)}"
    elif trespass:
        detail = f"forbidden: {', '.join(trespass)}"
    else:
        detail = "satisfied"
    grades.append(
        GradeOutcome(
            assertion="forbidden_side_effects",
            passed=not blind and not trespass,
            detail=detail,
        )
    )
    unknown: list[str] = []
    for name in case.assertions:
        grader = graders.get(name)
        if grader is None:
            unknown.append(name)
            continue
        reason = grader(case, observed)
        grades.append(
            GradeOutcome(
                assertion=name, passed=reason is None, detail=reason if reason else "satisfied"
            )
        )
    return CaseResult(
        case_id=case.case_id,
        passed=all(item.passed for item in grades) and not unknown,
        grades=tuple(grades),
        unknown_assertions=tuple(unknown),
    )


class Attempt(Contract):
    """One run of one case against one alias."""

    passed: bool
    duration_ms: int | None = Field(default=None, ge=0, strict=True)
    input_tokens: int = Field(default=0, ge=0, strict=True)
    output_tokens: int = Field(default=0, ge=0, strict=True)
    reasons: tuple[Text, ...] = ()


class AliasTrial(Contract):
    """What one alias did across the repetitions. At least two, enforced
    where the data lives rather than only in the function that builds it: a
    host reconstructing a trial from stored attempts must not be able to
    present a one-cell reliability of 1.0."""

    alias: Symbol
    attempts: tuple[Attempt, ...] = Field(min_length=2)

    @property
    def passes(self) -> int:
        return sum(1 for item in self.attempts if item.passed)

    @property
    def reliability(self) -> float:
        """Passes over attempts. An alias that answers correctly nine times
        in ten is a different thing from one that always does, and a single
        number is the only way that difference is visible."""
        return self.passes / len(self.attempts)

    @property
    def unmeasured(self) -> int:
        """Attempts that carry no duration, usually because they were refused
        before any call was made."""
        return sum(1 for item in self.attempts if item.duration_ms is None)

    @property
    def mean_duration_ms(self) -> float | None:
        """Over the attempts that were measured, or None when none were. Two
        aliases are compared per measured call, never on totals over
        different numbers of calls."""
        measured = [item.duration_ms for item in self.attempts if item.duration_ms is not None]
        return sum(measured) / len(measured) if measured else None

    @property
    def total_duration_ms(self) -> int | None:
        """Only when every attempt was measured. A total over some of the
        attempts would read as faster exactly when the alias failed to answer."""
        if self.unmeasured:
            return None
        return sum(item.duration_ms or 0 for item in self.attempts)


class ModelEvaluation(Contract):
    """A comparison, or the reason there was not one."""

    case_id: Symbol
    status: Literal["measured", "skipped"]
    # Why it was skipped. A measured comparison carries none, so a report can
    # never print "skipped" beside a detail that says otherwise.
    detail: Text | None = None
    trials: tuple[AliasTrial, ...] = ()

    @model_validator(mode="after")
    def measured_means_measured(self) -> Self:
        if (self.status == "measured") != bool(self.trials):
            raise ValueError("a measured comparison has trials; a skipped one has none")
        if (self.status == "skipped") != (self.detail is not None):
            raise ValueError("a skipped comparison says why; a measured one has no detail")
        return self


def compare_aliases(
    case: EvaluationCase,
    aliases: Iterable[Symbol],
    run: Callable[[EvaluationCase, Symbol], ObservedRun],
    *,
    repeat: int = 3,
    graders: Mapping[str, Grader] = GRADERS,
) -> ModelEvaluation:
    """The same case across every configured alias, repeated.

    A single attempt is refused rather than reported: the source
    repository's benchmark states the rule plainly, that one cell is not a
    measurement when the thing measured is not deterministic
    (`docs/PHASE_6_MIGRATION.md`)."""
    if repeat < 2:
        raise ValueError("a single attempt is not a measurement")
    named = tuple(aliases)
    if not named:
        return ModelEvaluation(
            case_id=case.case_id,
            status="skipped",
            detail="no alias is configured, so there was nothing to compare",
        )
    if len(set(named)) != len(named):
        # The same reason `load_cases` refuses a repeated id: two rows for one
        # alias with different numbers, and a reader keeping whichever came last.
        raise ValueError("an alias is compared once")
    trials: list[AliasTrial] = []
    for alias in named:
        attempts: list[Attempt] = []
        for _ in range(repeat):
            attempts.append(_attempt(case, alias, run, graders))
        trials.append(AliasTrial(alias=alias, attempts=tuple(attempts)))
    return ModelEvaluation(case_id=case.case_id, status="measured", trials=tuple(trials))


def _attempt(
    case: EvaluationCase,
    alias: Symbol,
    run: Callable[[EvaluationCase, Symbol], ObservedRun],
    graders: Mapping[str, Grader],
) -> Attempt:
    """One run, graded. A `run` that raises is a failed attempt, not the end
    of the comparison: a measurement of unreliability that aborts on the
    first unreliable call cannot report the alias it was built to find."""
    try:
        observed = run(case, alias)
    except Exception as error:  # noqa: BLE001 - the host's runner failing is a data point
        text = f"{type(error).__name__}: {error}"[:200]
        return Attempt(
            passed=False, reasons=(f"the run raised {SECRET_PATTERN.sub(REDACTED, text)}",)
        )
    result = grade(case, observed, graders=graders)
    return Attempt(
        passed=result.passed,
        duration_ms=observed.duration_ms,
        input_tokens=observed.input_tokens,
        output_tokens=observed.output_tokens,
        reasons=result.reasons(),
    )


class CaseRunner(Protocol):
    """Turns a case into evidence. A host writes one of these; the harness
    only grades what it returns, so how a case is exercised stays outside the
    contract it is graded against."""

    def run(self, case: EvaluationCase) -> ObservedRun: ...


def run_cases(
    cases: Iterable[EvaluationCase],
    runner: CaseRunner,
    *,
    graders: Mapping[str, Grader] = GRADERS,
) -> tuple[CaseResult, ...]:
    return tuple(grade(case, runner.run(case), graders=graders) for case in cases)


def load_cases(directory: Path) -> tuple[EvaluationCase, ...]:
    """Every case under a directory, in a stable order. A file may hold one
    case or a list of them. A repeated `case_id` is refused here rather than
    producing two confusingly similar results later."""
    cases: list[EvaluationCase] = []
    seen: set[str] = set()
    for path in sorted(directory.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        for item in payload if isinstance(payload, list) else [payload]:
            case = EvaluationCase.model_validate(item)
            if case.case_id in seen:
                raise ValueError(f"duplicate case id: {case.case_id}")
            seen.add(case.case_id)
            cases.append(case)
    return tuple(cases)


def report(results: Iterable[CaseResult]) -> str:
    """One line per case, and the reason under every failure, so a CI log says
    what broke rather than that something did."""
    lines: list[str] = []
    checked = failed = 0
    for result in results:
        checked += 1
        if result.passed:
            lines.append(f"PASS {result.case_id}")
            continue
        failed += 1
        lines.append(f"FAIL {result.case_id}")
        lines.extend(f"     {reason}" for reason in result.reasons())
    lines.append(f"{checked - failed}/{checked} cases passed")
    return "\n".join(lines)
