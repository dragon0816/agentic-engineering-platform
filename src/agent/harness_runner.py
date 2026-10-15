"""Run a Skill-shaped plan with domain-neutral, Host-supplied actions.

Actions own payloads and side effects. The runner records only evidence refs
and Host check results; it cannot grant capabilities or validate its own output.
"""

import inspect
from typing import Any, Protocol

import telemetry.recorder as telemetry
from agent.harness_plan import AgentHarnessPlan
from agent.harness_run import (
    AgentHarnessRun,
    HarnessCheckResult,
    observe_context,
    observe_execution,
    start_harness,
    stop_harness,
    validate_run,
)
from common.base import Symbol


class HarnessActionFailure(Exception):
    """A typed adapter failure that the shared runner can stop on."""

    def __init__(self, code: Symbol, *, needs_input: bool = False) -> None:
        self.code = code
        self.needs_input = needs_input
        super().__init__(code)


class HarnessActions(Protocol):
    def collect_context(self) -> Symbol:
        """Return a reference to observed input context, never its payload."""

    def execute(self) -> Symbol:
        """Run the already authorized domain action and return an evidence ref."""

    def validate(self) -> tuple[HarnessCheckResult, ...]:
        """Report independently observed Host checks for the plan."""


def run_harness(plan: AgentHarnessPlan, actions: HarnessActions) -> AgentHarnessRun:
    """Drive one bounded plan; preserve Host/Bridge authority in the actions."""
    run = start_harness(plan)
    attempt = 0
    while run.phase not in ("validated", "needs_input", "failed"):
        telemetry.emit(
            "state.entered", status="started", state=run.phase, attributes={"loop_index": attempt}
        )
        try:
            if run.phase == "collecting":
                run = observe_context(run, actions.collect_context())
            elif run.phase == "executing":
                run = observe_execution(run, actions.execute())
            else:
                checks = actions.validate()
                for check in checks:
                    # The validator and its verdict, never a claim of correctness.
                    telemetry.emit(
                        "verification.completed",
                        state="validating",
                        status="succeeded" if check.status == "passed" else "failed",
                        attributes={"validator": check.check_id, "loop_index": attempt},
                    )
                run = validate_run(run, checks)
                if run.phase not in ("validated", "needs_input", "failed"):
                    attempt += 1
                    telemetry.emit(
                        "retry.scheduled",
                        state="validating",
                        attributes={"retry_reason": "validation_failed", "loop_index": attempt},
                    )
        except HarnessActionFailure as error:
            telemetry.emit(
                "state.entered",
                status="failed",
                state="stopped",
                attributes={"failure_code": error.code},
            )
            return stop_harness(run, error.code, needs_input=error.needs_input)
    telemetry.emit(
        "state.entered",
        status="succeeded" if run.phase == "validated" else "failed",
        state=run.phase,
    )
    return run


async def _maybe(value: Any) -> Any:
    return await value if inspect.isawaitable(value) else value


async def run_harness_async(plan: AgentHarnessPlan, actions: Any) -> AgentHarnessRun:
    """`run_harness` for adapters whose actions are coroutines (the Workflow
    engine runs on an event loop). Same states, checks and telemetry."""
    run = start_harness(plan)
    attempt = 0
    while run.phase not in ("validated", "needs_input", "failed"):
        telemetry.emit(
            "state.entered",
            status="started",
            state=run.phase,
            attributes={"loop_index": attempt, "domain": plan.domain},
        )
        try:
            if run.phase == "collecting":
                run = observe_context(run, await _maybe(actions.collect_context()))
            elif run.phase == "executing":
                run = observe_execution(run, await _maybe(actions.execute()))
            else:
                checks = tuple(await _maybe(actions.validate()))
                for check in checks:
                    telemetry.emit(
                        "verification.completed",
                        state="validating",
                        status="succeeded" if check.status == "passed" else "failed",
                        attributes={"validator": check.check_id, "loop_index": attempt},
                    )
                run = validate_run(run, checks)
                if run.phase not in ("validated", "needs_input", "failed"):
                    attempt += 1
                    telemetry.emit(
                        "retry.scheduled",
                        state="validating",
                        attributes={"retry_reason": "validation_failed", "loop_index": attempt},
                    )
        except HarnessActionFailure as error:
            telemetry.emit(
                "state.entered",
                status="failed",
                state="stopped",
                attributes={"failure_code": error.code},
            )
            return stop_harness(run, error.code, needs_input=error.needs_input)
    telemetry.emit(
        "state.entered",
        status="succeeded" if run.phase == "validated" else "failed",
        state=run.phase,
    )
    return run
