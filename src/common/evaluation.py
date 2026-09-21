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
from collections.abc import Callable, Iterable, Mapping
from pathlib import Path
from typing import Literal

from pydantic import Field

from common.assets import AssetIdentity
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
    status: RunStatus | None = None
    completed_steps: int = Field(default=0, ge=0, strict=True)
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


def _no_execution(case: EvaluationCase, observed: ObservedRun) -> str | None:
    ran = [
        effect for effect in observed.side_effects if effect in ("execute", "external_side_effect")
    ]
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
    trespass = [effect for effect in observed.side_effects if effect in case.forbidden_side_effects]
    grades.append(
        GradeOutcome(
            assertion="forbidden_side_effects",
            passed=not trespass,
            detail="satisfied" if not trespass else f"forbidden: {', '.join(trespass)}",
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
