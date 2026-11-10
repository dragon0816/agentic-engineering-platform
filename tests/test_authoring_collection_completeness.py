"""A declared full collection cannot become verified by dropping its pagination."""

from collections.abc import Callable
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
from pydantic import JsonValue
from test_chat_authoring import studio

from capabilities.browser_session.handlers import SPEC, BrowserRequest, BrowserResult
from common.assets import ExecutionDependencies
from common.base import Contract
from common.execution import RequestContext
from host_runtime.authoring_task import AuthoringTask, Requirement, TaskStore
from host_runtime.chat_authoring import ChatAuthoring, ChatAuthoringError, ChatCandidate, digest
from integrations.web_script import ScriptMode, ScriptRunner, WebAction, WebScript


def _requirement() -> Requirement:
    # This deliberately models the weak plan from the actual regression.
    return Requirement.model_validate(
        {
            "requirement_id": "orders",
            "description": "Read all orders",
            "check_ids": ["rows"],
            "assertions": [
                {"path": ["steps", 0, "inputs", "actions", "value"], "operator": "present"}
            ],
        }
    )


def _studio(
    tmp_path: Path, *, planned: bool = True, actual_dispatch: bool = False
) -> ChatAuthoring:
    chat, _ = studio(tmp_path)

    async def read(context: RequestContext, inputs: Contract) -> Contract:
        request = BrowserRequest.model_validate(inputs)
        if actual_dispatch:
            result = _ObservedRunner().run(
                WebScript(actions=request.actions, values=request.values), "act"
            )
            return BrowserResult(data=result.data)
        # A model/output's complete flag is not an alternative full-count proof.
        return BrowserResult(data={"orders": [{"id": "one"}], "complete": True})

    chat.installed.register(
        SPEC, read, BrowserRequest, BrowserResult, ExecutionDependencies(central_required=False)
    )
    if planned:
        chat.tasks.plan("owner", "session-1", "Read all orders", [_requirement()])
    return chat


def _raw() -> dict[str, Any]:
    return {
        "name": "read-orders",
        "description": "Read all orders",
        "parameters": [],
        "steps": [
            {
                "capability": "browser/operate@1.0.0",
                "inputs": {
                    "actions": {
                        "source": "fixed",
                        "value": [
                            {
                                "do": "read_table",
                                "table": "#orders",
                                "save_as": "orders",
                                "pagination": {
                                    "current": {"css": "#current"},
                                    "total": {"css": "#total"},
                                    "next": {"css": "#next"},
                                },
                            }
                        ],
                    }
                },
            }
        ],
        "checks": [{"check_id": "rows", "step_index": 0, "kind": "data_nonempty"}],
    }


def _draft(
    chat: ChatAuthoring, raw: dict[str, Any], previous: ChatCandidate | None = None
) -> ChatCandidate:
    item, problems = chat.draft(
        "owner", "session-1", "Orders", raw, previous.candidate_id if previous else None
    )
    assert item is not None and not problems
    return item


def test_dropping_pagination_stays_runnable_but_cannot_verify_or_install(tmp_path: Path) -> None:
    chat = _studio(tmp_path)
    original = _draft(chat, _raw())
    assert chat.execute("owner", original, {}, "owner-full-trial")["verified"] is True
    raw = _raw()
    del raw["steps"][0]["inputs"]["actions"]["value"][0]["pagination"]
    partial = _draft(chat, raw, original)
    assert chat.readiness(partial)["coverage_complete"] is False
    result = chat.execute("owner", partial, {}, "owner-partial-trial")
    assert result["status"] == "succeeded" and result["verified"] is False
    current = chat.candidate(partial.candidate_id, "owner")
    with pytest.raises(ChatAuthoringError, match="authoring_coverage_incomplete"):
        chat.install(current, "owner", "explicit-owner-install")


@pytest.mark.parametrize(
    "edit", ["dummy", "rename", "remove", "new_candidate", "replan", "duplicate", "duplicate_paged"]
)
def test_collection_obligation_survives_normal_authoring_edits(tmp_path: Path, edit: str) -> None:
    chat = _studio(tmp_path)
    original = _draft(chat, _raw())
    raw = _raw()
    actions = raw["steps"][0]["inputs"]["actions"]["value"]
    del actions[0]["pagination"]
    if edit == "dummy":
        dummy = deepcopy(_raw()["steps"][0]["inputs"]["actions"]["value"][0])
        dummy.update(table="#other", save_as="unrelated")
        actions.append(dummy)
    elif edit == "rename":
        actions[0] = deepcopy(_raw()["steps"][0]["inputs"]["actions"]["value"][0])
        actions[0]["save_as"] = "renamed_orders"
    elif edit == "remove":
        actions[0] = {"do": "read_text", "target": {"css": "#orders"}, "save_as": "orders"}
    elif edit in {"duplicate", "duplicate_paged"}:
        if edit == "duplicate_paged":
            actions[0] = deepcopy(_raw()["steps"][0]["inputs"]["actions"]["value"][0])
        actions.append(deepcopy(_raw()["steps"][0]["inputs"]["actions"]["value"][0]))
    elif edit == "new_candidate":
        raw["name"] = "replacement-orders"
    elif edit == "replan":
        rebound = _requirement().model_dump(mode="json")
        rebound["assertions"] = [{"path": ["steps"], "operator": "present"}]
        chat.tasks.plan(
            "owner",
            "session-1",
            "Updated plan",
            [Requirement.model_validate(rebound)],
        )
    current = _draft(chat, raw, None if edit == "new_candidate" else original)
    assert chat.readiness(current)["coverage_complete"] is False
    task = TaskStore(chat.tasks.root).load("owner", "session-1")
    assert task is not None
    assert any(
        o.save_as == "orders" and o.source_digest == digest(original.draft)
        for o in task.collection_obligations
    )


def test_matching_output_may_repair_selectors_and_step_positions_then_verify(
    tmp_path: Path,
) -> None:
    chat = _studio(tmp_path)
    original = _draft(chat, _raw())
    raw = _raw()
    action = raw["steps"][0]["inputs"]["actions"]["value"][0]
    action.update(table="#corrected-orders", header_table="#corrected-headers")
    raw["steps"][0]["inputs"]["actions"]["value"].insert(
        0,
        {
            "do": "wait_for",
            "target": {"css": "#corrected-orders"},
        },
    )
    raw["steps"].insert(
        0,
        {
            "capability": "browser/operate@1.0.0",
            "inputs": {
                "actions": {
                    "source": "fixed",
                    "value": [{"do": "wait_for", "target": {"css": "#orders-ready"}}],
                }
            },
        },
    )
    raw["checks"][0]["step_index"] = 1
    restored = _draft(chat, raw, original)
    assert chat.readiness(restored)["coverage_complete"] is True
    assert chat.execute("owner", restored, {}, "owner-corrected-trial")["verified"] is True
    current = chat.candidate(restored.candidate_id, "owner")
    assert chat.install(current, "owner", "owner-install")["installed_as"]


def test_stale_trial_cannot_clear_obligation_or_verify_unpaged_revision(tmp_path: Path) -> None:
    from test_authoring_trial_diagnostics import _snapshot

    chat = _studio(tmp_path)
    original = _draft(chat, _raw())
    running = chat.begin_trial("owner", original, {})
    raw = _raw()
    del raw["steps"][0]["inputs"]["actions"]["value"][0]["pagination"]
    partial = _draft(chat, raw, original)
    chat.record_trial("owner", running, _snapshot(running, "old-paged-trial", {}, succeeded=True))
    assert chat.readiness(partial)["verified"] is False
    assert chat.readiness(partial)["coverage_complete"] is False
    restored = _draft(chat, _raw(), partial)
    assert chat.execute("owner", restored, {}, "owner-restored-trial")["verified"] is True


def test_real_previous_declaration_is_captured_forward_after_legacy_plan(tmp_path: Path) -> None:
    assert AuthoringTask(objective="Legacy").collection_obligations == ()
    chat = _studio(tmp_path, planned=False)
    original = _draft(chat, _raw())
    chat.tasks.plan("owner", "session-1", "Read all orders", [_requirement()])
    raw = _raw()
    del raw["steps"][0]["inputs"]["actions"]["value"][0]["pagination"]
    partial = _draft(chat, raw, original)
    assert chat.readiness(partial)["coverage_complete"] is False
    task = chat.tasks.load("owner", "session-1")
    assert task is not None and task.collection_obligations[0].source_digest == digest(
        original.draft
    )


def test_legacy_current_manifest_is_captured_at_trial_after_reload(tmp_path: Path) -> None:
    chat = _studio(tmp_path, planned=False)
    item = _draft(chat, _raw())
    chat.tasks.plan("owner", "session-1", "Read all orders", [_requirement()])
    before = TaskStore(chat.tasks.root).load("owner", "session-1")
    assert before is not None and before.collection_obligations == ()

    result = chat.execute(
        "owner", chat.candidate(item.candidate_id, "owner"), {}, "owner-legacy-trial"
    )

    assert result["verified"] is True
    task = TaskStore(chat.tasks.root).load("owner", "session-1")
    assert task is not None and task.collection_obligations[0].source_digest == digest(item.draft)
    assert TaskStore(chat.tasks.root).load("other", "session-1") is None
    assert TaskStore(chat.tasks.root).load("owner", "other") is None


def test_task_store_preserves_first_collection_source_against_replacement(tmp_path: Path) -> None:
    chat = _studio(tmp_path)
    item = _draft(chat, _raw())
    task = chat.tasks.load("owner", "session-1")
    assert task is not None and task.collection_obligations
    obligation = task.collection_obligations[0]
    forged = obligation.model_copy(update={"source_digest": "0" * 64})
    chat.tasks.save(
        "owner", "session-1", task.model_copy(update={"collection_obligations": (forged,)})
    )
    chat.tasks.save("owner", "session-1", task.model_copy(update={"collection_obligations": ()}))
    saved = TaskStore(chat.tasks.root).load("owner", "session-1")
    assert saved is not None and saved.collection_obligations == (obligation,)
    assert saved.collection_obligations[0].source_digest == digest(item.draft)


class _ObservedPage:
    def reload(self, *, check_origin: Callable[[str], None], timeout_s: float) -> None:
        raise AssertionError("no reload")

    def navigate(self, url: str) -> None:
        pass

    def evaluate(self, expression: str) -> Any:
        return "https://example.invalid/orders"


class _ObservedRunner(ScriptRunner):
    """Stub observations only; actual ScriptRunner._do owns all output assignment."""

    def __init__(self) -> None:
        def download(click: Callable[[], None], save_as: str) -> str:
            click()
            return "download.xlsx"

        super().__init__(_ObservedPage(), ("https://example.invalid",), downloader=download)

    def _table_pages(self, action: WebAction, mode: ScriptMode) -> list[Any]:
        return [{"id": "one"}]

    def _perform(
        self,
        spec: dict[str, Any],
        *,
        deadline: float | None = None,
        before_press: Callable[[], None] | None = None,
        verify_scope: Callable[[], str] | None = None,
        check_observation: Callable[[], None] | None = None,
    ) -> dict[str, Any]:
        assert before_press is None and verify_scope is None and check_observation is None
        return {"text": "overwritten", "ok": True}

    def _evaluate(self, expression: str) -> dict[str, Any]:
        return {"record": {"overwritten": True}}

    def inspect(
        self, scope: str = "body", offset: int = 0, limit: int = 80
    ) -> dict[str, JsonValue]:
        return {"overwritten": True}


@pytest.mark.parametrize("writer", ["read_text", "read_record", "inspect_dom", "download"])
@pytest.mark.parametrize("position", ["before", "after"])
def test_actual_same_output_writer_cannot_shadow_paginated_proof(
    tmp_path: Path, writer: str, position: str
) -> None:
    chat = _studio(tmp_path, actual_dispatch=True)
    original = _draft(chat, _raw())
    raw = _raw()
    action: dict[str, Any] = {"do": writer, "save_as": "orders"}
    if writer in {"read_text", "download"}:
        action["target"] = {"css": "#summary", "kind": "any"}
    elif writer == "read_record":
        action["table"] = "#summary"
    actions = raw["steps"][0]["inputs"]["actions"]["value"]
    actions.insert(0, action) if position == "before" else actions.append(action)
    current = _draft(chat, raw, original)

    result = chat.execute("owner", current, {}, "owner-actual-dispatch-trial")

    assert result["status"] == "succeeded"
    steps = result["steps"]
    assert isinstance(steps, list) and isinstance(steps[0], dict)
    output = steps[0]["data"]
    assert isinstance(output, dict) and isinstance(output["data"], dict)
    observed = output["data"]["orders"]
    assert (observed == [{"id": "one"}]) is (position == "before")
    assert result["coverage_complete"] is False and result["verified"] is False


def test_collection_source_digest_uses_actual_bound_saved_manifest(tmp_path: Path) -> None:
    chat = _studio(tmp_path)
    raw = _raw()
    raw["parameters"] = [
        {"name": "period", "label": "Period", "kind": "text", "scope": "runtime", "required": True}
    ]
    unbound, problems = chat.check("owner", raw)
    assert unbound is not None and not problems
    chat.tasks.observe("owner", "session-1", "period=2026-10")

    current = _draft(chat, raw)

    assert current.draft.parameters[0].default == "2026-10"
    assert digest(current.draft) != digest(unbound)
    task = chat.tasks.load("owner", "session-1")
    assert task is not None
    assert task.collection_obligations[0].source_digest == digest(current.draft)


def test_unknown_action_with_pagination_cannot_create_or_satisfy_obligation(tmp_path: Path) -> None:
    from common.assets import FixedInput, WorkflowStep
    from host_runtime.authoring_task import capture_collection_obligations, coverage_problems

    chat = _studio(tmp_path)
    item = _draft(chat, _raw())
    task = chat.tasks.load("owner", "session-1")
    assert task is not None
    step = item.draft.steps[0]
    assert isinstance(step, WorkflowStep)
    action = deepcopy(_raw()["steps"][0]["inputs"]["actions"]["value"][0])
    action["do"] = "unknown_writer"
    changed_step = step.model_copy(
        update={"inputs": {"actions": FixedInput(source="fixed", value=[action])}}
    )
    manifest = item.draft.model_copy(update={"steps": (changed_step,)})
    legacy = AuthoringTask(objective="Legacy", requirements=task.requirements)
    captured = capture_collection_obligations(legacy, manifest, digest(manifest))
    assert captured.collection_obligations == ()
    assert any(
        "collection_completeness" in problem for problem in coverage_problems(task, manifest)
    )
