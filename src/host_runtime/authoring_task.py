"""Actor/session-scoped authoring requirements and current-version trial evidence."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, Self

from pydantic import Field, JsonValue, model_validator

from common.assets import WorkflowManifest
from common.base import Contract, Symbol, Text
from host_runtime.conversations import ConversationMessage
from host_runtime.workspace import write_atomically


class ProcedureAssertion(Contract):
    """A bounded assertion over the candidate, including wildcard list paths."""

    path: tuple[str | int, ...] = Field(min_length=1, max_length=20)
    operator: Literal["present", "equals", "contains", "min_count"] = "present"
    expected: JsonValue = None

    @model_validator(mode="after")
    def meaningful_count(self) -> Self:
        if self.operator == "min_count" and (
            type(self.expected) is not int or not 1 <= self.expected <= 100000
        ):
            raise ValueError("min_count requires a positive bounded integer")
        return self


class Requirement(Contract):
    requirement_id: Symbol
    description: Text = Field(max_length=2000)
    check_ids: tuple[Symbol, ...] = Field(default=(), max_length=30)
    assertions: tuple[ProcedureAssertion, ...] = Field(default=(), max_length=30)


class AuthoringPlanRequest(Contract):
    requirements: tuple[Requirement, ...] = Field(min_length=1, max_length=40)


class AuthoringQuestion(Contract):
    reason: Literal[
        "business_decision",
        "missing_resource",
        "authentication_required",
        "capability_gap",
        "repair_limit",
    ]
    question: Text = Field(max_length=1000)
    input_name: Symbol | None = None
    resource_name: Text | None = Field(default=None, max_length=500)


class AuthoringTask(Contract):
    objective: Text = Field(max_length=40000)
    requirements: tuple[Requirement, ...] = Field(default=(), max_length=40)
    supplied_inputs: dict[str, dict[str, JsonValue]] = Field(default_factory=dict)
    verified_digest: str | None = None
    last_trial_digest: str | None = None
    last_status: str | None = None
    last_run_id: str | None = None
    last_failure: str | None = None
    repair_attempts: int = Field(default=0, ge=0, le=3)
    last_repaired_run_id: str | None = None
    active_trial_token: str | None = None
    last_trial_arguments: dict[str, JsonValue] = Field(default_factory=dict)
    question: AuthoringQuestion | None = None

    @model_validator(mode="after")
    def unique_requirements(self) -> Self:
        ids = [r.requirement_id for r in self.requirements]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate_requirement")
        return self


class TaskStore:
    def __init__(self, root: Path) -> None:
        self.root = root

    def _path(self, actor: str, session: str) -> Path:
        ident = hashlib.sha256(json.dumps([actor, session]).encode()).hexdigest()
        return self.root / f"{ident}.json"

    def load(self, actor: str, session: str) -> AuthoringTask | None:
        path = self._path(actor, session)
        return AuthoringTask.model_validate_json(path.read_bytes()) if path.is_file() else None

    def save(self, actor: str, session: str, task: AuthoringTask) -> AuthoringTask:
        path = self._path(actor, session)
        path.parent.mkdir(parents=True, exist_ok=True)
        write_atomically(path, task.model_dump_json(indent=2).encode())
        return task

    def messages(self, actor: str, session: str) -> tuple[ConversationMessage, ...]:
        path = self._path(actor, session).with_suffix(".inputs.json")
        if not path.is_file():
            return ()
        return tuple(ConversationMessage.model_validate(v) for v in json.loads(path.read_bytes()))

    def observe(
        self,
        actor: str,
        session: str,
        text: str,
        attachments: tuple[dict[str, str], ...] = (),
        *,
        event_id: str | None = None,
    ) -> None:
        previous = self.messages(actor, session)
        # A transport request id identifies an actual new owner turn, even
        # when its words repeat. Legacy callers retain content deduplication.
        identity = [text, attachments] if event_id is None else ["event", event_id]
        item = ConversationMessage(
            message_id="input-"
            + hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()[:24],
            role="user",
            text=text[:40000],
            created_at=datetime.now(UTC),
            status="submitted",
            attachments=attachments,
        )
        if any(m.message_id == item.message_id for m in previous):
            return
        path = self._path(actor, session).with_suffix(".inputs.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        write_atomically(
            path,
            json.dumps(
                [m.model_dump(mode="json") for m in (*previous, item)[-100:]], ensure_ascii=False
            ).encode(),
        )
        task = self.load(actor, session)
        if task is not None and (task.question is not None or task.repair_attempts >= 3):
            # New input reopens evaluation; it does not itself confirm or
            # invalidate the saved plan/trial evidence.
            update: dict[str, Any] = {"question": None}
            if task.repair_attempts >= 3:
                update["repair_attempts"] = 0
            # Keep the repaired-run marker: renewing the budget cannot replay
            # the same failed run or alter existing proof/trial ownership.
            self.save(actor, session, task.model_copy(update=update))

    def plan(
        self, actor: str, session: str, objective: str, requirements: list[Requirement]
    ) -> AuthoringTask:
        previous = self.load(actor, session)
        if previous is not None:
            new = {r.requirement_id: r for r in requirements}
            for old in previous.requirements:
                if old.requirement_id not in new:
                    raise ValueError("requirement_removed")
                current = new[old.requirement_id]
                if old.description != current.description or not set(old.check_ids) <= set(
                    current.check_ids
                ):
                    raise ValueError("requirement_weakened")
                # Procedure paths may change as discovery corrects bindings or
                # inserts steps. Keep business requirements/checks, require
                # nonempty evidence, and invalidate proof on every rebind.
                if old.assertions and not current.assertions:
                    raise ValueError("requirement_weakened")
            changed = previous.requirements != tuple(requirements)
            task = previous.model_copy(
                update={
                    "requirements": tuple(requirements),
                    "verified_digest": None if changed else previous.verified_digest,
                    "active_trial_token": None if changed else previous.active_trial_token,
                }
            )
        else:
            task = AuthoringTask(objective=objective, requirements=tuple(requirements))
        return self.save(actor, session, task)


def _values(document: Any, path: tuple[str | int, ...]) -> list[Any]:
    if not path:
        return [document]
    first, rest = path[0], path[1:]
    if first == "*":
        children = (
            document.values()
            if isinstance(document, dict)
            else document
            if isinstance(document, list)
            else []
        )
        return [value for child in children for value in _values(child, rest)]
    if isinstance(document, dict) and first in document:
        return _values(document[first], rest)
    if isinstance(document, list) and isinstance(first, int) and 0 <= first < len(document):
        return _values(document[first], rest)
    return []


def coverage_problems(task: AuthoringTask, manifest: WorkflowManifest) -> list[str]:
    checks = {check.check_id for check in manifest.checks}
    document = manifest.model_dump(mode="json")
    problems = []
    for requirement in task.requirements:
        ident = requirement.requirement_id
        if not requirement.check_ids or not set(requirement.check_ids) <= checks:
            problems.append(f"{ident}: bind requirement to declared output checks")
        if not requirement.assertions:
            problems.append(f"{ident}: bind requirement to actual procedure assertions")
        for assertion in requirement.assertions:
            values = _values(document, assertion.path)
            passed = bool(values)
            if assertion.operator == "present":
                passed = any(value not in (None, "", [], {}) for value in values)
            elif assertion.operator == "equals":
                passed = any(value == assertion.expected for value in values)
            elif assertion.operator == "contains":
                passed = any(
                    assertion.expected in value
                    for value in values
                    if isinstance(value, (list, str))
                    and (not isinstance(value, str) or isinstance(assertion.expected, str))
                )
            elif assertion.operator == "min_count":
                count = (
                    len(values[0])
                    if len(values) == 1 and isinstance(values[0], (list, dict, str))
                    else len(values)
                )
                passed = isinstance(assertion.expected, int) and count >= assertion.expected
            if not passed:
                problems.append(
                    f"{ident}: procedure assertion {assertion.operator} is not satisfied"
                )
    if not task.requirements:
        problems.append("authoring_requirements_missing")
    return problems


def task_guidance(task: AuthoringTask) -> str:
    view = task.model_dump(mode="json")
    view["objective"] = task.objective[:3000]
    return (
        "[Persistent Workflow authoring task: preserve every requirement; "
        "repair within approval scope]\n" + json.dumps(view, ensure_ascii=False)[:24000]
    )
