"""Per-occurrence authorization for scheduled work.

A saved schedule is not permission. Before a due occurrence may run
unattended, the Host requires all of:

1. the owner's active, unexpired `ScheduleExecutionGrant` naming the
   schedule's exact target;
2. every capability the target can reach declares an effect class no higher
   than the grant's `max_side_effect`;
3. the Bridge's own durable `CapabilityGrant` authorizes each of those
   capabilities for the owner (the Bridge checks again at dispatch);
4. for an `external_side_effect` target, a human approval of this very run.

The decision is computed from Host-owned records and installed manifests
only. No schedule definition, asset or model output contributes to it.
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
from common.scheduling import ScheduleRecord, max_side_effect, within_side_effect
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
    """The Host's schedule policy over the store's grants and the Bridge policy."""

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
        record = self.store.active_grant(definition.schedule_id, owner=definition.owner)
        if record is None:
            return ScheduleDecision(code="schedule_grant_missing")
        grant = record.grant
        if grant.expired(now):
            return ScheduleDecision(code="schedule_grant_expired")
        if not grant.covers(definition):
            return ScheduleDecision(code="schedule_grant_mismatch")
        specs = target_capabilities(
            self.agent, definition.target_kind, definition.target, self.task_templates
        )
        if isinstance(specs, str):
            return ScheduleDecision(code=specs)
        effect = max_side_effect(spec.side_effect for spec in specs)
        if not within_side_effect(effect, grant.max_side_effect):
            return ScheduleDecision(code="schedule_effect_above_grant", side_effect=effect)
        context = schedule_context(schedule, trace)
        policy = self.agent.gateway.engine.bridge.policy
        if not all(policy.authorize(context, spec).allowed for spec in specs):
            return ScheduleDecision(code="bridge_grant_missing", side_effect=effect)
        if effect == "external_side_effect" and not run_approved:
            return ScheduleDecision(
                code="run_approval_required", side_effect=effect, approval_required=True
            )
        return ScheduleDecision(
            allowed=True,
            code="schedule_authorized",
            side_effect=effect,
            authorization=ExecutionAuthorization(
                allowed=True,
                actor=definition.owner,
                asset=definition.target,
                trace=trace,
                policy_ref=grant.policy_ref,
            ),
        )

    def __call__(self, schedule: ScheduleRecord, trace: TraceIdentifiers) -> ExecutionAuthorization:
        """The plain authorizer shape: never approves a run needing a human."""
        return self.decide(schedule, trace, run_approved=False, now=self._clock()).authorization
