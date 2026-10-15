"""The owner's schedule controls, shared by the CLI and Agent Web.

Every operation acts for the host's bound member only, after the same device
admission rule every other ingress uses. Creating a schedule saves intent;
granting its execution is a separate, explicit owner action; executing a due
or approved occurrence always goes through `ScheduleWorker`, the resident
Agent and the Bridge policy. Operations that may dispatch work (`tick`,
`approve`) or settle an uncertain claim (`resolve`) hold the caller's
one-request-at-a-time lock when one is supplied, so they never overlap
another run in the same process.
"""

import asyncio
from collections.abc import Callable, Iterator, Mapping
from contextlib import AbstractContextManager, contextmanager, nullcontext
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from pydantic import Field, JsonValue, StrictBool, ValidationError, field_validator

from agent.task_contract import TaskContract
from common.assets import AssetIdentity, WorkflowManifest
from common.base import Contract, Symbol, Text
from common.execution import IdempotencyKey, SideEffect, TraceIdentifiers
from common.scheduling import (
    Recurrence,
    ResolutionOutcome,
    ScheduleDefinition,
    ScheduledRun,
    ScheduleExecutionGrant,
    ScheduleGrantRecord,
    ScheduleRecord,
)
from common.workflow_forms import form_fields
from common.workflow_parameters import WorkflowParameterError, validate_run_parameters
from host_runtime.agent_tasks import AgentTaskTemplate, installed_agent_tasks
from host_runtime.host import HostRuntime
from host_runtime.schedule_policy import ScheduleGrantAuthorizer, target_side_effect
from host_runtime.schedule_worker import ScheduleWorker
from host_runtime.schedules import ScheduleStoreError, SqliteScheduleStore
from host_runtime.workspace import documents

#: The policy reference a grant made through a local owner control carries.
OWNER_GRANT_POLICY = "owner-schedule-grant"
SCHEDULE_FILE = "schedules.sqlite"


class ScheduleControlError(Exception):
    """A refusal a person can act on, by code; never carries input values."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


# -- requests a browser may send (owner, approver and policy come from here) --


class ScheduleCreateRequest(Contract):
    schedule_id: Symbol
    target_kind: Literal["workflow", "agent_task"]
    target: AssetIdentity
    recurrence: Recurrence
    runtime_inputs: dict[Symbol, JsonValue] = Field(default_factory=dict, max_length=50)
    initial_status: Literal["active", "paused"] = "active"


class ScheduleSelectRequest(Contract):
    schedule_id: Symbol


class ScheduleGrantRequest(Contract):
    schedule_id: Symbol
    max_side_effect: SideEffect
    expires_at: datetime | None = None

    @field_validator("expires_at")
    @classmethod
    def aware(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("expiry requires a timezone")
        return value


class ScheduleRunDecisionRequest(Contract):
    idempotency_key: IdempotencyKey
    note: Text | None = Field(default=None, max_length=500)


class ScheduleResolveRequest(Contract):
    idempotency_key: IdempotencyKey
    outcome: ResolutionOutcome
    note: Text | None = Field(default=None, max_length=500)
    confirm: StrictBool = False


class ScheduleControl:
    def __init__(
        self,
        runtime: HostRuntime,
        *,
        lock: AbstractContextManager[Any] | None = None,
        clock: Callable[[], datetime] | None = None,
        agent_tasks: Mapping[tuple[str, str, str], AgentTaskTemplate] | None = None,
    ) -> None:
        self.runtime = runtime
        self._lock = lock
        self._clock = clock if clock is not None else lambda: datetime.now(UTC)
        # Installed Agent Task templates, read once per control; the worker
        # receives exact task contracts for the bound member.
        self.agent_tasks = dict(
            installed_agent_tasks(runtime.layout.workspace_root)
            if agent_tasks is None
            else agent_tasks
        )
        trace = TraceIdentifiers(
            trace_id="scheduled-template",
            request_id="scheduled-template",
            span_id="scheduled-template",
        )
        self.task_templates: dict[tuple[str, str, str], TaskContract] = {
            key: template.to_task(actor=runtime.actor, task_id="scheduled-template", trace=trace)
            for key, template in self.agent_tasks.items()
        }

    # -- plumbing ----------------------------------------------------------

    @property
    def owner(self) -> str:
        return self.runtime.actor

    @property
    def bridge_id(self) -> str:
        return self.runtime.config.device.bridge_id

    @property
    def catch_up(self) -> timedelta:
        return timedelta(hours=self.runtime.config.schedules.catch_up_hours)

    def _admitted(self) -> None:
        if self.runtime.agent.admit(self.owner, self.bridge_id) is not None:
            raise ScheduleControlError("not_admitted")

    @contextmanager
    def _store(self) -> Iterator[SqliteScheduleStore]:
        self._admitted()
        try:
            with SqliteScheduleStore(
                self.runtime.layout.workspace_root / SCHEDULE_FILE, bridge_id=self.bridge_id
            ) as store:
                yield store
        except ScheduleStoreError as error:
            raise ScheduleControlError(error.code) from None

    def _serial(self) -> AbstractContextManager[Any]:
        return self._lock if self._lock is not None else nullcontext()

    def worker(self, store: SqliteScheduleStore) -> ScheduleWorker:
        return ScheduleWorker(
            store,
            self.runtime.agent,
            authorizer=ScheduleGrantAuthorizer(
                store, self.runtime.agent, task_templates=self.task_templates, clock=self._clock
            ),
            task_templates=self.task_templates,
            workflow_wait_seconds=float(self.runtime.config.workflow_wait_seconds),
            catch_up=self.catch_up,
        )

    # -- what can be scheduled ----------------------------------------------

    def workflow_manifests(self) -> tuple[WorkflowManifest, ...]:
        """Installed Workflows the running engine can execute, by exact version."""
        directory = self.runtime.layout.workflows
        found: dict[tuple[str, str, str], WorkflowManifest] = {}
        if directory.is_dir():
            for path in sorted(directory.glob("*.json")):
                try:
                    for item in documents(path):
                        manifest = WorkflowManifest.model_validate(item)
                        identity = manifest.metadata.identity
                        if self.runtime.agent.gateway.engine.workflows.get(identity) is not None:
                            found[identity.key] = manifest
                except Exception:  # noqa: BLE001 - doctor reports unreadable assets
                    continue
        return tuple(found[key] for key in sorted(found))

    def targets(self) -> list[dict[str, Any]]:
        """Exact installed targets with the fields a create form needs."""
        agent = self.runtime.agent
        listed: list[dict[str, Any]] = []
        for manifest in self.workflow_manifests():
            identity = manifest.metadata.identity
            listed.append(
                {
                    "target_kind": "workflow",
                    "target": identity.model_dump(mode="json"),
                    "description": manifest.description,
                    "side_effect": target_side_effect(agent, "workflow", identity, {}),
                    "fields": form_fields(manifest, "schedule"),
                    "typed": bool(manifest.parameters),
                }
            )
        for key in sorted(self.agent_tasks):
            template = self.agent_tasks[key]
            identity = template.identity
            listed.append(
                {
                    "target_kind": "agent_task",
                    "target": identity.model_dump(mode="json"),
                    "description": template.description,
                    "side_effect": target_side_effect(
                        agent, "agent_task", identity, self.task_templates
                    ),
                    "fields": [],
                    "typed": True,
                }
            )
        return listed

    def validate(self, definition: ScheduleDefinition) -> ScheduleDefinition:
        item = ScheduleDefinition.model_validate(definition)
        if item.owner != self.owner:
            raise ScheduleControlError("definition_owner_mismatch")
        if item.target_kind == "workflow":
            manifest = self.runtime.agent.gateway.engine.workflows.get(item.target)
            if manifest is None:
                raise ScheduleControlError("workflow_not_installed")
            try:
                validate_run_parameters(manifest, dict(item.runtime_inputs))
            except WorkflowParameterError:
                raise ScheduleControlError("workflow_parameters_invalid") from None
            return item
        template = self.task_templates.get(item.target.key)
        if template is None:
            raise ScheduleControlError("task_not_installed")
        if item.runtime_inputs:
            raise ScheduleControlError("task_input_unsupported")
        return item

    # -- intent --------------------------------------------------------------

    def create(self, definition: ScheduleDefinition) -> ScheduleRecord:
        self._admitted()
        item = self.validate(definition)
        with self._store() as store:
            return store.create(item, now=self._clock())

    def create_from_request(self, request: ScheduleCreateRequest) -> ScheduleRecord:
        item = ScheduleCreateRequest.model_validate(request)
        try:
            definition = ScheduleDefinition(
                schedule_id=item.schedule_id,
                owner=self.owner,
                target_kind=item.target_kind,
                target=item.target,
                recurrence=item.recurrence,
                runtime_inputs=item.runtime_inputs,
                initial_status=item.initial_status,
            )
        except (ValidationError, ValueError):
            raise ScheduleControlError("invalid_definition") from None
        return self.create(definition)

    def schedules(self) -> tuple[ScheduleRecord, ...]:
        with self._store() as store:
            return store.list(owner=self.owner)

    def set_active(self, schedule_id: str, *, active: bool) -> ScheduleRecord:
        with self._store() as store:
            return store.set_active(schedule_id, owner=self.owner, active=active, now=self._clock())

    def history(self, schedule_id: str, *, limit: int = 50) -> tuple[ScheduledRun, ...]:
        with self._store() as store:
            return store.history(schedule_id, owner=self.owner, limit=limit)

    # -- permission ----------------------------------------------------------

    def grant(
        self,
        schedule_id: str,
        *,
        max_side_effect: SideEffect,
        expires_at: datetime | None = None,
    ) -> ScheduleGrantRecord:
        """The owner grants unattended execution up to `max_side_effect`."""
        now = self._clock()
        with self._store() as store:
            definition = store.get(schedule_id, owner=self.owner).definition
            try:
                item = ScheduleExecutionGrant(
                    schedule_id=schedule_id,
                    owner=self.owner,
                    target_kind=definition.target_kind,
                    target=definition.target,
                    max_side_effect=max_side_effect,
                    policy_ref=OWNER_GRANT_POLICY,
                    approved_by=self.owner,
                    approved_at=now,
                    expires_at=expires_at,
                )
            except (ValidationError, ValueError):
                raise ScheduleControlError("invalid_grant") from None
            return store.grant(item)

    def revoke(self, schedule_id: str) -> ScheduleGrantRecord:
        with self._store() as store:
            return store.revoke(
                schedule_id, owner=self.owner, revoked_by=self.owner, now=self._clock()
            )

    # -- occurrences ---------------------------------------------------------

    def tick(self, *, now: datetime | None = None) -> tuple[ScheduledRun, ...]:
        """One poll: reconcile, claim due work and attempt it."""
        with self._serial(), self._store() as store:
            return asyncio.run(self.worker(store).poll_once(now=now or self._clock()))

    def approve(self, key: str, *, note: str | None = None) -> ScheduledRun:
        """Approve one waiting run and dispatch it through every check again."""
        with self._serial(), self._store() as store:
            return asyncio.run(
                self.worker(store).run_approved(
                    key, decided_by=self.owner, now=self._clock(), note=note
                )
            )

    def deny(self, key: str, *, note: str | None = None) -> ScheduledRun:
        with self._store() as store:
            return store.deny_run(
                key, owner=self.owner, decided_by=self.owner, now=self._clock(), note=note
            )

    def resolve(
        self, key: str, *, outcome: ResolutionOutcome, note: str | None = None
    ) -> ScheduledRun:
        """Record what the owner established about a claim; dispatch nothing."""
        with self._serial(), self._store() as store:
            return store.resolve(
                key,
                owner=self.owner,
                outcome=outcome,
                decided_by=self.owner,
                now=self._clock(),
                note=note,
            )

    # -- what a page shows ---------------------------------------------------

    def overview(self) -> dict[str, Any]:
        with self._store() as store:
            schedules: list[dict[str, Any]] = []
            open_claims = {run.idempotency_key for run in store.pending_claims()}
            for record in store.list(owner=self.owner):
                definition = record.definition
                grant = store.active_grant(definition.schedule_id, owner=self.owner)
                runs = store.history(definition.schedule_id, owner=self.owner, limit=10)
                schedules.append(
                    {
                        "schedule_id": definition.schedule_id,
                        "status": record.status,
                        "next_due_at": record.next_due_at.isoformat(),
                        "target_kind": definition.target_kind,
                        "target": definition.target.model_dump(mode="json"),
                        "recurrence": definition.recurrence.model_dump(mode="json"),
                        "runtime_inputs": definition.runtime_inputs,
                        "side_effect": target_side_effect(
                            self.runtime.agent,
                            definition.target_kind,
                            definition.target,
                            self.task_templates,
                        ),
                        "grant": None if grant is None else grant.grant.model_dump(mode="json"),
                        "runs": [run.model_dump(mode="json") for run in runs],
                        "blocked_by": next(
                            (
                                run.idempotency_key
                                for run in runs
                                if run.idempotency_key in open_claims
                            ),
                            None,
                        ),
                    }
                )
            waiting = store.awaiting_approval(owner=self.owner)
        return {
            "owner": self.owner,
            "schedules": schedules,
            "awaiting_approval": [run.model_dump(mode="json") for run in waiting],
            "catch_up_hours": self.runtime.config.schedules.catch_up_hours,
        }

    def decisions(self, schedule_id: str) -> list[dict[str, Any]]:
        with self._store() as store:
            return [
                item.model_dump(mode="json")
                for item in store.decisions(schedule_id, owner=self.owner)
            ]
