"""Resolve owned schedule targets under actual environment permissions.

Legacy grant records remain audit history, not admission. Authenticated schedule
owner/Bridge identity, installed targets and task model/data contracts remain.
No effect ceiling or per-occurrence AEP approval is added.
"""

from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import Protocol, Self

from pydantic import StrictBool, model_validator

from agent.task_contract import TaskContract
from capabilities.contracts import CapabilitySpec
from common.assets import AssetIdentity, WorkflowStep
from common.base import Contract, Symbol
from common.execution import (
    ExecutionAuthorization,
    RequestContext,
    SideEffect,
    TraceIdentifiers,
)
from common.scheduling import ScheduleRecord, max_side_effect
from host_runtime.agent import LocalAgent
from host_runtime.schedules import SqliteScheduleStore

#: Codes for a target that cannot be resolved on this host; reported as
#: `unavailable` rather than `needs_input`.
UNAVAILABLE_CODES = frozenset(
    {"workflow_not_installed", "task_not_installed", "capability_not_installed"}
)


class ScheduleDecision(Contract):
    """One occurrence's authorization, with the reason when refused."""

    allowed: StrictBool = False
    code: Symbol
    side_effect: SideEffect | None = None
    # True when everything else holds and only a per-run human approval is
    # missing: the occurrence then waits rather than failing.
    approval_required: StrictBool = False
    authorization: ExecutionAuthorization = ExecutionAuthorization()

    @model_validator(mode="after")
    def allowed_carries_authorization(self) -> Self:
        if self.allowed != self.authorization.allowed:
            raise ValueError("an allowed decision carries an explicit authorization")
        if self.allowed and self.approval_required:
            raise ValueError("an allowed decision needs no further approval")
        return self


class ScheduleDecider(Protocol):
    def decide(
        self,
        schedule: ScheduleRecord,
        trace: TraceIdentifiers,
        *,
        run_approved: bool,
        now: datetime,
    ) -> ScheduleDecision: ...


def target_capabilities(
    agent: LocalAgent,
    target_kind: str,
    target: AssetIdentity,
    task_templates: Mapping[tuple[str, str, str], TaskContract],
) -> tuple[CapabilitySpec, ...] | str:
    """Every installed capability the exact target may reach, or why not.

    A Workflow reaches its declared steps. An Agent Task reaches only its
    template's explicitly allowed capabilities; a text-only task reaches none
    and is therefore `read`.
    """
    engine = agent.gateway.engine
    if target_kind == "workflow":
        manifest = engine.workflows.get(target)
        if manifest is None:
            return "workflow_not_installed"
        identities = tuple(
            step.capability if isinstance(step, WorkflowStep) else step for step in manifest.steps
        )
    else:
        template = task_templates.get(target.key)
        if template is None:
            return "task_not_installed"
        identities = template.allowed_capabilities
    specs: list[CapabilitySpec] = []
    for identity in identities:
        binding = engine.bridge.installed.get(identity)
        if binding is None:
            return "capability_not_installed"
        specs.append(binding.spec)
    return tuple(specs)


def target_side_effect(
    agent: LocalAgent,
    target_kind: str,
    target: AssetIdentity,
    task_templates: Mapping[tuple[str, str, str], TaskContract],
) -> SideEffect | None:
    """The highest effect class the target can reach, or None if unresolvable."""
    specs = target_capabilities(agent, target_kind, target, task_templates)
    if isinstance(specs, str):
        return None
    return max_side_effect(spec.side_effect for spec in specs)


def schedule_context(schedule: ScheduleRecord, trace: TraceIdentifiers) -> RequestContext:
    definition = schedule.definition
    target = definition.target
    return RequestContext(
        trace=trace,
        actor=definition.owner,
        namespace=target.namespace,
        message=(
            f"scheduled {definition.target_kind} {target.namespace}/{target.name}@{target.version}"
        ),
        channel="local",
    )


class ScheduleGrantAuthorizer:
    """Compatibility name for the environment-backed owned-target resolver."""

    def __init__(
        self,
        store: SqliteScheduleStore,
        agent: LocalAgent,
        *,
        task_templates: Mapping[tuple[str, str, str], TaskContract] | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.store = store
        self.agent = agent
        self.task_templates = dict(task_templates or {})
        self._clock = clock if clock is not None else lambda: datetime.now(UTC)

    def decide(
        self,
        schedule: ScheduleRecord,
        trace: TraceIdentifiers,
        *,
        run_approved: bool,
        now: datetime,
    ) -> ScheduleDecision:
        definition = schedule.definition
        if self.agent.membership.member() != definition.owner:
            return ScheduleDecision(code="schedule_owner_mismatch")
        specs = target_capabilities(
            self.agent, definition.target_kind, definition.target, self.task_templates
        )
        if isinstance(specs, str):
            return ScheduleDecision(code=specs)
        effect = max_side_effect(spec.side_effect for spec in specs)
        return ScheduleDecision(
            allowed=True,
            code="schedule_authorized",
            side_effect=effect,
            authorization=ExecutionAuthorization(
                allowed=True,
                actor=definition.owner,
                asset=definition.target,
                trace=trace,
                policy_ref="execution-environment",
            ),
        )

    def __call__(self, schedule: ScheduleRecord, trace: TraceIdentifiers) -> ExecutionAuthorization:
        """Legacy callback shape, with no synthetic owner approval."""
        return self.decide(schedule, trace, run_approved=False, now=self._clock()).authorization
