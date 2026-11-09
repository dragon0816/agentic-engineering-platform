"""Actual failed approaches survive revision/history windows as bounded task memory."""

import json
from pathlib import Path
from typing import Any

import pytest
from test_chat_authoring import studio

from capabilities.browser_session.handlers import SPEC, BrowserRequest, BrowserResult
from capabilities.runtime import CapabilityExecutionFailed
from common.assets import ExecutionDependencies
from common.base import Contract
from common.execution import RequestContext
from host_runtime.authoring_task import Requirement, TaskStore
from host_runtime.chat_authoring import ChatAuthoring, ChatCandidate


def _browser(chat: ChatAuthoring) -> None:
    async def fail(context: RequestContext, inputs: Contract) -> Contract:
        request = BrowserRequest.model_validate(inputs)
        index = len(request.actions) - 1
        raise CapabilityExecutionFailed(
            "web_target_missing",
            BrowserResult(
                failed_action_index=index,
                failed_action_kind=request.actions[index].do,
            ),
            where=f"actions[{index}]",
        )

    chat.installed.register(
        SPEC, fail, BrowserRequest, BrowserResult, ExecutionDependencies(central_required=False)
    )


def _draft(
    chat: ChatAuthoring,
    label: str,
    *,
    previous: ChatCandidate | None = None,
    count: int = 2,
    long_css: bool = False,
    actor: str = "owner",
    session: str = "session-1",
) -> ChatCandidate:
    if previous is None:
        chat.tasks.plan(
            actor,
            session,
            "Read Sales Orders",
            [
                Requirement.model_validate(
                    {
                        "requirement_id": "orders",
                        "description": "Read Sales Orders",
                        "check_ids": ["rows"],
                        "assertions": [
                            {
                                "path": ["steps", 0, "capability", "name"],
                                "operator": "equals",
                                "expected": "operate",
                            }
                        ],
                    }
                )
            ],
        )
    actions = [
        {
            "do": "click",
            "target": {
                "css": "#" + "locator" * 80 if long_css else f"#sales-{i}",
                "kind": "link",
            },
        }
        for i in range(count - 1)
    ]
    actions.append(
        {"do": "fill", "target": {"label": label, "kind": "field"}, "value": "PRIVATE-FILL-VALUE"}
    )
    item, problems = chat.draft(
        actor,
        session,
        "Orders",
        {
            "name": "orders-history",
            "description": "Read Sales Orders",
            "parameters": [],
            "steps": [
                {
                    "capability": "browser/operate@1.0.0",
                    "inputs": {
                        "actions": {"source": "fixed", "value": actions},
                        "values": {
                            "source": "fixed",
                            "value": {"business_value": "PRIVATE-RUN-VALUE"},
                        },
                    },
                }
            ],
            "checks": [{"check_id": "rows", "step_index": 0, "kind": "data_nonempty"}],
        },
        previous.candidate_id if previous else None,
    )
    assert item is not None and not problems
    return item


def test_two_actual_failed_revisions_survive_reload_and_new_owner_input(tmp_path: Path) -> None:
    chat, _ = studio(tmp_path)
    _browser(chat)
    first = _draft(chat, "Sales Orders")
    first_result = chat.execute("owner", first, {}, "explicit-first-trial")
    assert first_result["status"] == "failed"
    second = _draft(chat, "Advanced filters", previous=first)
    second_result = chat.execute("owner", second, {}, "explicit-second-trial")
    assert second_result["status"] == "failed"

    store = TaskStore(chat.tasks.root)
    before = store.load("owner", "session-1")
    assert before is not None
    history: Any = before.trial_history
    assert [r["run_id"] for r in history] == [first_result["run_id"], second_result["run_id"]]
    assert [r["revision"] for r in history] == [first.revision, second.revision]
    assert history[0]["failed_steps"][0]["action_prefix"][-1]["target"]["label"] == "Sales Orders"
    assert (
        history[1]["failed_steps"][0]["action_prefix"][-1]["target"]["label"] == "Advanced filters"
    )
    assert history[0]["failed_steps"][0]["failed_action_index"] == 1
    assert history[0]["failed_steps"][0]["code"] == "web_target_missing"
    assert history[0]["failed_steps"][0]["action_prefix"][0]["target"]["css"] == "#sales-0"
    store.observe(
        "owner", "session-1", "Continue using the existing SOP", event_id="new-owner-turn"
    )
    after = TaskStore(chat.tasks.root).load("owner", "session-1")
    assert after is not None and after.trial_history == before.trial_history
    assert store.load("other", "session-1") is None and store.load("owner", "other") is None
    encoded = json.dumps(history)
    assert "PRIVATE-FILL-VALUE" not in encoded and "PRIVATE-RUN-VALUE" not in encoded


def test_stale_token_cannot_append_or_duplicate_actual_trial_history(tmp_path: Path) -> None:
    from test_authoring_trial_diagnostics import _snapshot

    chat, _ = studio(tmp_path)
    _browser(chat)
    item = _draft(chat, "Sales Orders")
    stale = chat.begin_trial("owner", item, {})
    current = chat.begin_trial("owner", item, {})
    snapshot = _snapshot(current, "actual-latest", {"failed_action_index": 1})
    chat.record_trial("owner", current, snapshot)
    before = chat.tasks.load("owner", "session-1")
    assert before is not None and len(before.trial_history) == 1
    chat.record_trial("owner", stale, _snapshot(stale, "stale", {"failed_action_index": 0}))
    chat.record_trial("owner", current, snapshot)
    after = chat.tasks.load("owner", "session-1")
    assert after is not None and after.trial_history == before.trial_history


def test_history_keeps_latest_ten_actual_runs_and_never_copies_open_urls_or_values(
    tmp_path: Path,
) -> None:
    chat, _ = studio(tmp_path)
    _browser(chat)
    item = _draft(chat, "Sales Orders")
    raw = item.draft.model_dump(mode="json")
    raw["steps"][0]["inputs"]["actions"]["value"].insert(
        0,
        {
            "do": "open",
            "url": "https://PRIVATE-OPEN-URL.invalid",
        },
    )
    updated, problems = chat.draft("owner", "session-1", "Orders", raw, item.candidate_id)
    assert updated is not None and not problems
    run_ids = []
    for index in range(13):
        chat.tasks.observe(
            "owner",
            "session-1",
            "Run the next owner-requested trial",
            event_id=f"owner-trial-{index}",
        )
        result = chat.execute("owner", updated, {}, f"explicit-trial-{index}")
        run_ids.append(result["run_id"])
    task = TaskStore(chat.tasks.root).load("owner", "session-1")
    assert task is not None and len(task.trial_history) == 10
    assert [entry["run_id"] for entry in task.trial_history] == run_ids[-10:]
    encoded = json.dumps(task.trial_history, ensure_ascii=False)
    assert len(encoded.encode()) <= 12000
    assert "PRIVATE" not in encoded and '"url"' not in encoded and '"value"' not in encoded
    from test_chat_authoring import context

    guidance = chat.task_context(context())
    compact = json.loads(guidance.splitlines()[1])
    assert [entry["run_id"] for entry in compact] == run_ids[-3:]


def test_single_large_approach_is_bounded_without_losing_its_actual_failed_action(
    tmp_path: Path,
) -> None:
    chat, _ = studio(tmp_path)
    _browser(chat)
    item = _draft(chat, "Final observed field", count=50, long_css=True)
    result = chat.execute("owner", item, {}, "explicit-large-trial")
    assert result["status"] == "failed"
    task = chat.tasks.load("owner", "session-1")
    assert task is not None and len(task.trial_history) == 1
    history: Any = task.trial_history
    assert len(json.dumps(history, ensure_ascii=False).encode()) <= 12000
    step = history[0]["failed_steps"][0]
    assert step["failed_action_index"] == 49
    assert step["action_prefix"][-1]["target"]["label"] == "Final observed field"
    from test_chat_authoring import context

    compact = json.loads(chat.task_context(context()).splitlines()[1])
    assert len(compact[0]["failed_step"]["action_prefix"]) == 3


def test_public_repair_note_keeps_earlier_approach_upfront_as_advisory(tmp_path: Path) -> None:
    from test_authoring_repair import Capturing
    from test_conversation_turn_groups import _chat_config, _ChatGateway

    from host_runtime.host import build_runtime
    from host_runtime.web import AgentWeb

    config, layout = _chat_config(tmp_path)
    with build_runtime(config, layout=layout, model_transport=_ChatGateway()) as runtime:
        web = AgentWeb(runtime)
        session = web.create_conversation()["conversation"]["session_id"]
        chat = runtime.chat_authoring
        assert chat is not None
        _browser(chat)
        first = _draft(chat, "Sales Orders", actor=runtime.actor, session=session)
        assert chat.execute(runtime.actor, first, {}, "owner-first")["status"] == "failed"
        second = _draft(
            chat, "Advanced filters", previous=first, actor=runtime.actor, session=session
        )
        model = Capturing(
            {
                "tools": [
                    (
                        "authoring__needs_input",
                        {
                            "reason": "business_decision",
                            "question": "Which approved order scope applies?",
                            "input_name": "order_scope",
                        },
                    )
                ]
            },
            {"text": "Which approved order scope applies?"},
        )
        runtime.agent.gateway.router.model = model
        approval = chat.request(runtime.actor, session, "run", second.candidate_id, {})

        result = web.decide_approval(approval.approval_id, "approve")

        assert "repair" in result and model.requests
        note = next(m.text for m in reversed(model.requests[0].messages) if m.role == "user")
        assert "Known actual trial history" in note
        assert note.index("Known actual trial history") < note.index("Actual trial diagnostics")
        assert "Sales Orders" in note and "Advanced filters" in note
        assert "without fresh evidence" in note and "Preserve successful action prefixes" in note
        assert "PRIVATE-FILL-VALUE" not in note and "PRIVATE-RUN-VALUE" not in note


def test_legacy_state_gets_empty_history_without_backfilling_last_diagnostics() -> None:
    from host_runtime.authoring_task import AuthoringTask

    legacy = AuthoringTask.model_validate(
        {
            "objective": "Legacy task",
            "last_run_id": "old-run",
            "last_status": "failed",
            "last_trial_diagnostics": {"run_id": "old-run", "status": "failed"},
        }
    )
    assert legacy.trial_history == ()


def test_oversized_validated_metadata_is_bounded_without_changing_actual_proof(
    tmp_path: Path,
) -> None:
    from test_chat_authoring import context

    from common.execution import CapabilityResult, Failure, WorkflowRun
    from workflow.engine import WorkflowRunSnapshot

    chat, _ = studio(tmp_path)
    _browser(chat)
    item = _draft(chat, "Sales Orders")
    running = chat.begin_trial("owner", item, {})
    run_id = "run-" + "x" * 20000
    failure = Failure(code="failure-" + "x" * 20000, message="Actual failure")
    snapshot = WorkflowRunSnapshot(
        run=WorkflowRun(
            run_id=run_id,
            workflow=item.draft.metadata.identity,
            trace=context().trace,
            status="failed",
            failure=failure,
        ),
        step_results=tuple(
            CapabilityResult(
                trace=context().trace,
                status="failed",
                failure=failure,
                data={"failed_action_index": 1},
            )
            for _ in range(4)
        ),
    )

    chat.record_trial("owner", running, snapshot)

    task = TaskStore(chat.tasks.root).load("owner", "session-1")
    assert task is not None and task.last_run_id == run_id
    assert task.last_failure == failure.code
    assert len(json.dumps(task.trial_history, ensure_ascii=False).encode()) <= 12000
    assert task.last_trial_diagnostics is not None
    assert len(json.dumps(task.last_trial_diagnostics, ensure_ascii=False).encode()) <= 12000


def test_owner_continuation_gets_compact_history_before_large_task_context(tmp_path: Path) -> None:
    from test_chat_authoring import context

    chat, _ = studio(tmp_path)
    _browser(chat)
    first = _draft(chat, "Sales Orders")
    assert chat.execute("owner", first, {}, "owner-first")["status"] == "failed"
    second = _draft(chat, "Advanced filters", previous=first)
    assert chat.execute("owner", second, {}, "owner-second")["status"] == "failed"
    store = TaskStore(chat.tasks.root)
    task = store.load("owner", "session-1")
    assert task is not None
    requirements = [
        *task.requirements,
        *[
            task.requirements[0].model_copy(update={"requirement_id": f"requirement_{index}"})
            for index in range(1, 8)
        ],
    ]
    task = store.plan("owner", "session-1", "Read SOP", requirements)
    store.save(
        "owner",
        "session-1",
        task.model_copy(
            update={
                "objective": "Long objective " * 2000,
                "last_trial_diagnostics": {"large_diagnostic": "diagnostic " * 3000},
            }
        ),
    )
    TaskStore(chat.tasks.root).observe(
        "owner", "session-1", "Continue the same task", event_id="owner-continuation"
    )

    guidance = chat.task_context(context().model_copy(update={"message": "Continue the same task"}))

    assert guidance.startswith("[Known actual trial history")
    prelude = guidance.split("[Persistent Workflow authoring task", 1)[0]
    assert len(prelude.encode("utf-8")) <= 4000
    assert "Sales Orders" in prelude and "Advanced filters" in prelude
    assert "advisory" in prelude and "authoring__get_plan" in prelude
    assert '"trial_history"' not in guidance
    for index in range(1, 8):
        assert f'"requirement_{index}"' in guidance
    assert '"requirement_id": "orders"' in guidance
    assert len(guidance) <= 24000 + 110
    reloaded = TaskStore(chat.tasks.root).load("owner", "session-1")
    assert reloaded is not None and reloaded.trial_history == task.trial_history


@pytest.mark.parametrize(
    "target_field",
    ["pagination.current", "pagination.total", "pagination.next", "pagination.controls"],
)
def test_nested_pagination_target_survives_summary_and_advisory_history(
    tmp_path: Path, target_field: str
) -> None:
    from test_authoring_trial_diagnostics import _snapshot
    from test_chat_authoring import context

    from host_runtime.chat_authoring import summarize

    chat, _ = studio(tmp_path)
    _browser(chat)
    item = _draft(chat, "Orders")
    running = chat.begin_trial("owner", item, {})
    snapshot = _snapshot(
        running,
        "pagination-target-failed",
        {
            "failed_action_index": 1,
            "failed_target_field": target_field,
        },
    )
    chat.record_trial("owner", running, snapshot)
    task = chat.tasks.load("owner", "session-1")
    assert task is not None
    history: Any = task.trial_history
    assert history[-1]["failed_steps"][0]["failed_target_field"] == target_field
    diagnostics: Any = task.last_trial_diagnostics
    assert diagnostics["failed_steps"][0]["failed_target_field"] == target_field
    summary: Any = summarize(snapshot)
    assert summary["steps"][0]["data"]["failed_target_field"] == target_field
    compact = json.loads(chat.task_context(context()).splitlines()[1])
    assert compact[0]["failed_step"]["failed_target_field"] == target_field


def test_arbitrary_nested_target_metadata_is_not_carried_into_advisory_state(
    tmp_path: Path,
) -> None:
    from test_authoring_trial_diagnostics import _snapshot
    from test_chat_authoring import context

    chat, _ = studio(tmp_path)
    _browser(chat)
    running = chat.begin_trial("owner", _draft(chat, "Orders"), {})
    chat.record_trial(
        "owner",
        running,
        _snapshot(
            running,
            "unsupported-field",
            {
                "failed_action_index": 1,
                "failed_target_field": "PRIVATE-INPUT-VALUE",
            },
        ),
    )
    task = chat.tasks.load("owner", "session-1")
    assert task is not None
    assert "PRIVATE-INPUT-VALUE" not in json.dumps(task.trial_history)
    assert "PRIVATE-INPUT-VALUE" not in json.dumps(task.last_trial_diagnostics)
    assert "PRIVATE-INPUT-VALUE" not in chat.task_context(context())
