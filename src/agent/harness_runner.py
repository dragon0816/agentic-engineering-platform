"""Run a Skill-shaped plan with domain-neutral, Host-supplied actions.

Actions own payloads and side effects. The runner records only evidence refs
and Host check results; it cannot grant capabilities or validate its own output.
"""

from typing import Protocol

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
    while run.phase not in ("validated", "needs_input", "failed"):
        try:
            if run.phase == "collecting":
                run = observe_context(run, actions.collect_context())
            elif run.phase == "executing":
                run = observe_execution(run, actions.execute())
            else:
                run = validate_run(run, actions.validate())
        except HarnessActionFailure as error:
            return stop_harness(run, error.code, needs_input=error.needs_input)
    return run
