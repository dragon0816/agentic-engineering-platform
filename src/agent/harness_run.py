"""Bounded, payload-free lifecycle shared by all Agent harness domains.

Adapters perform retrieval or execution. Only Host-owned validation results
may advance this state to `validated`; a Skill's prose is never such a result.
"""

from typing import Literal, Self

from pydantic import Field, model_validator

from agent.harness_plan import AgentHarnessPlan
from common.base import Contract, Symbol

HarnessPhase = Literal[
    "collecting", "executing", "validating", "needs_input", "failed", "validated"
]
HarnessEventKind = Literal[
    "started", "context_observed", "execution_observed", "validation_failed",
    "retrying", "validated", "needs_input", "failed",
]


class HarnessRunEvent(Contract):
    sequence: int = Field(ge=0, strict=True)
    kind: HarnessEventKind
    evidence_ref: Symbol | None = None


class HarnessCheckResult(Contract):
    check_id: Symbol
    status: Literal["passed", "failed"]
    evidence_ref: Symbol


class AgentHarnessRun(Contract):
    plan: AgentHarnessPlan
    phase: HarnessPhase
    retry_count: int = Field(ge=0, le=3, strict=True)
    events: tuple[HarnessRunEvent, ...] = Field(min_length=1, max_length=60)
    checks: tuple[HarnessCheckResult, ...] = Field(max_length=40)
    failure_code: Symbol | None = None

    @model_validator(mode="after")
    def consistent_progress(self) -> Self:
        if self.retry_count > self.plan.retry_budget:
            raise ValueError("run exceeded its plan retry budget")
        if [event.sequence for event in self.events] != list(range(len(self.events))):
            raise ValueError("harness events must be contiguous")
        if self.events[0].kind != "started":
            raise ValueError("harness run must begin with a started event")
        if (self.phase in ("needs_input", "failed")) != (self.failure_code is not None):
            raise ValueError("terminal failure state requires a failure code")
        if self.phase == "validated":
            if self.events[-1].kind != "validated" or not self.checks:
                raise ValueError("validated run needs observed Host checks")
            if {item.check_id for item in self.checks} != set(self.plan.host_checks):
                raise ValueError("validated run must cover every Host check")
            if any(item.status != "passed" for item in self.checks):
                raise ValueError("validated run cannot contain a failed check")
        return self


def start_harness(plan: AgentHarnessPlan) -> AgentHarnessRun:
    first: HarnessPhase = (
        "collecting" if plan.stages[0] == "collect_context" else "executing"
    )
    return AgentHarnessRun(
        plan=plan, phase=first, retry_count=0,
        events=(HarnessRunEvent(sequence=0, kind="started"),), checks=(),
    )


def _advance(
    run: AgentHarnessRun,
    phase: HarnessPhase,
    *events: tuple[HarnessEventKind, Symbol | None],
    checks: tuple[HarnessCheckResult, ...] | None = None,
    failure_code: Symbol | None = None,
    retry_count: int | None = None,
) -> AgentHarnessRun:
    prior = run.model_dump(mode="json")
    appended = tuple(
        HarnessRunEvent(sequence=len(run.events) + index, kind=kind, evidence_ref=ref)
        for index, (kind, ref) in enumerate(events)
    )
    prior.update(
        phase=phase,
        events=run.events + appended,
        checks=run.checks if checks is None else checks,
        failure_code=failure_code,
        retry_count=run.retry_count if retry_count is None else retry_count,
    )
    return AgentHarnessRun.model_validate(prior)


def observe_context(run: AgentHarnessRun, evidence_ref: Symbol) -> AgentHarnessRun:
    if run.phase != "collecting":
        raise ValueError("context observation is not expected in this phase")
    return _advance(run, "executing", ("context_observed", evidence_ref))


def observe_execution(run: AgentHarnessRun, evidence_ref: Symbol) -> AgentHarnessRun:
    if run.phase != "executing":
        raise ValueError("execution observation is not expected in this phase")
    return _advance(run, "validating", ("execution_observed", evidence_ref))


def validate_run(
    run: AgentHarnessRun, checks: tuple[HarnessCheckResult, ...]
) -> AgentHarnessRun:
    if run.phase != "validating":
        raise ValueError("validation is not expected in this phase")
    names = tuple(item.check_id for item in checks)
    if len(names) != len(set(names)) or set(names) != set(run.plan.host_checks):
        raise ValueError("validation must report each Host check exactly once")
    if all(item.status == "passed" for item in checks):
        return _advance(run, "validated", ("validated", checks[-1].evidence_ref), checks=checks)
    failed = next(item for item in checks if item.status == "failed")
    if run.plan.fallback == "retry" and run.retry_count < run.plan.retry_budget:
        first: HarnessPhase = (
            "collecting"
            if run.plan.stages[0] == "collect_context" and run.plan.retry_from == "first"
            else "executing"
        )
        return _advance(
            run, first,
            ("validation_failed", failed.evidence_ref), ("retrying", None),
            checks=(), retry_count=run.retry_count + 1,
        )
    terminal: HarnessPhase = (
        "needs_input" if run.plan.fallback == "needs_input" else "failed"
    )
    event: HarnessEventKind = "needs_input" if terminal == "needs_input" else "failed"
    return _advance(
        run, terminal, ("validation_failed", failed.evidence_ref),
        (event, failed.evidence_ref), checks=checks, failure_code=run.plan.exhausted_code,
    )


def stop_harness(
    run: AgentHarnessRun, code: Symbol, *, needs_input: bool
) -> AgentHarnessRun:
    if run.phase in ("validated", "failed", "needs_input"):
        raise ValueError("terminal harness run cannot be stopped again")
    phase: HarnessPhase = "needs_input" if needs_input else "failed"
    event: HarnessEventKind = "needs_input" if needs_input else "failed"
    return _advance(run, phase, (event, None), failure_code=code)
