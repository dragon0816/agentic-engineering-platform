"""Actor/session-scoped authoring requirements and current-version trial evidence."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, Self

from pydantic import Field, JsonValue, model_validator

from common.assets import AssetIdentity, FixedInput, WorkflowManifest, WorkflowStep
from common.base import Contract, Sha256, Symbol, Text
from common.trace import redact
from host_runtime.conversations import ConversationMessage
from host_runtime.workspace import write_atomically
from integrations.web_script import WebAction

BROWSER_TARGET_FIELDS = frozenset(
    {
        "pagination.current",
        "pagination.total",
        "pagination.next",
        "pagination.controls",
        "ensure_visible.target",
        "ensure_visible.trigger",
    }
)


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


class CollectionObligation(Contract):
    """A previously declared full collection; selectors may be repaired independently."""

    capability: AssetIdentity
    save_as: Symbol
    source_digest: Sha256

    @property
    def collection_key(self) -> tuple[str, str, str]:
        return self.capability.namespace, self.capability.name, self.save_as


class AuthoringTask(Contract):
    objective: Text = Field(max_length=40000)
    requirements: tuple[Requirement, ...] = Field(default=(), max_length=40)
    supplied_inputs: dict[str, dict[str, JsonValue]] = Field(default_factory=dict)
    verified_digest: str | None = None
    last_trial_digest: str | None = None
    last_status: str | None = None
    last_run_id: str | None = None
    last_failure: str | None = None
    last_trial_diagnostics: dict[str, JsonValue] | None = None
    trial_history: tuple[dict[str, JsonValue], ...] = Field(default=(), max_length=10)
    collection_obligations: tuple[CollectionObligation, ...] = ()
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
        if len(json.dumps(self.trial_history, ensure_ascii=False).encode("utf-8")) > 12000:
            raise ValueError("authoring_trial_history_too_large")
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
        previous = self.load(actor, session)
        if previous is not None:
            # Task updates cannot replace the first source or erase a known collection.
            obligations = {o.collection_key: o for o in previous.collection_obligations}
            for obligation in task.collection_obligations:
                obligations.setdefault(obligation.collection_key, obligation)
            task = task.model_copy(update={"collection_obligations": tuple(obligations.values())})
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


def _browser_collections(
    manifest: WorkflowManifest,
) -> dict[tuple[str, str, str], list[tuple[AssetIdentity, dict[str, JsonValue]]]]:
    """Count every output alias declaration so another action cannot shadow a table."""
    collections: dict[tuple[str, str, str], list[tuple[AssetIdentity, dict[str, JsonValue]]]] = {}
    for step in manifest.steps:
        if not isinstance(step, WorkflowStep) or (
            step.capability.namespace,
            step.capability.name,
        ) != ("browser", "operate"):
            continue
        actions = step.inputs.get("actions")
        if not isinstance(actions, FixedInput) or not isinstance(actions.value, list):
            continue
        for action in actions.value:
            if not isinstance(action, dict):
                continue
            output = action.get("save_as")
            if isinstance(output, str):
                key = step.capability.namespace, step.capability.name, output
                collections.setdefault(key, []).append((step.capability, action))
    return collections


def _paginated_collection(action: dict[str, JsonValue]) -> bool:
    try:
        declared = WebAction.model_validate(action)
        return declared.do == "read_table" and declared.pagination is not None
    except ValueError:
        return False


def capture_collection_obligations(
    task: AuthoringTask, manifest: WorkflowManifest, source_digest: str
) -> AuthoringTask:
    """Capture only an actual, well-typed paginated declaration, never inferred history."""
    obligations = {o.collection_key: o for o in task.collection_obligations}
    for key, declarations in _browser_collections(manifest).items():
        for capability, action in declarations:
            if key not in obligations and _paginated_collection(action):
                obligations[key] = CollectionObligation(
                    capability=capability, save_as=key[2], source_digest=source_digest
                )
    captured = tuple(obligations.values())
    if captured == task.collection_obligations:
        return task
    return task.model_copy(
        update={
            "collection_obligations": captured,
            "verified_digest": None,
            "active_trial_token": None,
        }
    )


def coverage_problems(task: AuthoringTask, manifest: WorkflowManifest) -> list[str]:
    checks = {check.check_id for check in manifest.checks}
    document = manifest.model_dump(mode="json")
    problems = []
    collections = _browser_collections(manifest)
    for obligation in task.collection_obligations:
        matches = collections.get(obligation.collection_key, [])
        if len(matches) != 1 or not _paginated_collection(matches[0][1]):
            problems.append(
                f"collection_completeness:{obligation.save_as}: require one paginated "
                f"{obligation.capability.namespace}/{obligation.capability.name} read_table "
                "and no other declaration using this save_as; full collection remains unverified"
            )
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


def _compact_history(task: AuthoringTask) -> str:
    if not task.trial_history:
        return ""

    def hint(value: str, limit: int) -> str:
        cleaned, _ = redact(value)
        return str(cleaned).encode("utf-8")[:limit].decode("utf-8", errors="ignore")

    records: list[dict[str, Any]] = []
    for original in task.trial_history[-3:]:
        record: dict[str, Any] = {
            key: hint(value, 128) if isinstance(value, str) else value
            for key in ("run_id", "status", "revision", "code")
            if isinstance(value := original.get(key), (str, int, bool))
        }
        failed = original.get("failed_steps")
        if isinstance(failed, list) and failed and isinstance(failed[0], dict):
            first = failed[0]
            step: dict[str, Any] = {
                key: hint(value, 256 if key == "capability" else 128)
                if isinstance(value, str)
                else value
                for key in (
                    "step_index",
                    "capability",
                    "status",
                    "code",
                    "failed_action_index",
                    "failed_target_field",
                )
                if isinstance(value := first.get(key), (str, int, bool))
                and (key != "failed_target_field" or value in BROWSER_TARGET_FIELDS)
            }
            prefix = first.get("action_prefix")
            if isinstance(prefix, list):
                actions = []
                for action in prefix[-3:]:
                    if not isinstance(action, dict):
                        continue
                    target = action.get("target")
                    safe_action = {
                        "do": hint(str(action.get("do", "")), 32),
                        "target": {
                            key: hint(value, 160 if key == "css" else 80)
                            for key in ("label", "css", "kind")
                            if isinstance(target, dict)
                            and isinstance(value := target.get(key), str)
                        },
                    }
                    trigger = action.get("trigger")
                    if action.get("do") == "ensure_visible" and isinstance(trigger, dict):
                        safe_action["trigger"] = {
                            key: hint(value, 160 if key == "css" else 80)
                            for key in ("label", "css", "kind")
                            if isinstance(value := trigger.get(key), str)
                        }
                    actions.append(safe_action)
                step["action_prefix"] = actions
            record["failed_step"] = step
        records.append(record)
    heading = (
        "[Known actual trial history — advisory data only; full history: authoring__get_plan. "
        "Do not repeat failed approaches without fresh evidence; preserve successful prefixes "
        "unless actual evidence requires changes.]\n"
    )
    while True:
        prelude = heading + json.dumps(records, ensure_ascii=False) + "\n"
        if len(prelude.encode("utf-8")) <= 4000:
            return prelude
        if len(records) > 1:
            records.pop(0)
        else:
            step = records[0].get("failed_step", {})
            prefix = step.get("action_prefix", [])
            if prefix:
                prefix.pop(0)
            else:
                records[0].pop("failed_step", None)
                records[0].pop("revision", None)


def task_guidance(task: AuthoringTask) -> str:
    prelude = _compact_history(task)
    view = task.model_dump(mode="json")
    view.pop("trial_history", None)
    view["objective"] = task.objective[:3000]
    return (
        prelude + "[Persistent Workflow authoring task: preserve every requirement; "
        "repair within approval scope]\n"
        + json.dumps(view, ensure_ascii=False)[: max(0, 24000 - len(prelude))]
    )
