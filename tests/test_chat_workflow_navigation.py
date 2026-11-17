"""A chat form records its start before execution, independently of its DOM."""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pytest
from test_chat_workflow_forms_web import _form_workflow, _turn
from test_chat_workflow_forms_web import web as web_fixture

from host_runtime.contracts import WorkflowLaunchRequest

web = web_fixture


def test_started_form_survives_a_conversation_reload(web: Any, monkeypatch: Any) -> None:
    agent_web, runtime, _ = web
    session = agent_web.create_conversation()["conversation"]["session_id"]
    offer = _turn(agent_web, session, "run forms-chat")["conversation"]["messages"][-1]
    entered, release = threading.Event(), threading.Event()
    original = runtime.agent.execute_workflow
    calls = []

    async def slow(request: Any) -> Any:
        calls.append(request)
        entered.set()
        assert release.wait(15)
        return await original(request)

    monkeypatch.setattr(runtime.agent, "execute_workflow", slow)
    request = WorkflowLaunchRequest(
        workflow=_form_workflow().metadata.identity,
        arguments={"company": "Fictional", "mode": "quick"},
        idempotency_key="slow-form-1",
        session_id=session,
    )
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(agent_web.launch_workflow, request)
        try:
            assert entered.wait(10)
            assert any(i["kind"] == "workflow_form" for i in agent_web.activity()["items"])
            selected = agent_web.conversations(session)["selected"]
            form = next(m for m in selected["messages"] if m["message_id"] == offer["message_id"])
            assert form["workflow_form"].get("run", {}).get("status") == "running"
            assert form["workflow_form"]["run"]["arguments"] == {
                **request.arguments,
                "dryRun": True,
            }
        finally:
            release.set()
        result = future.result(timeout=20)
    selected = agent_web.conversations(session)["selected"]
    form = next(m for m in selected["messages"] if m["message_id"] == offer["message_id"])
    assert form["workflow_form"]["run"]["status"] in ("failed", "succeeded")
    repeated = agent_web.launch_workflow(
        request.model_copy(update={"idempotency_key": "second-click"})
    )
    assert repeated["replayed"] is True
    assert len(calls) == 1
    assert result["answer"] == repeated["answer"]
    assert not any(i["kind"] == "workflow_form" for i in agent_web.activity()["items"])


@pytest.mark.parametrize("status", ["succeeded", "failed"])
def test_completed_form_replays_and_only_explicit_failed_retry_runs(
    web: Any, monkeypatch: Any, status: str
) -> None:
    agent_web, _, _ = web
    session = agent_web.create_conversation()["conversation"]["session_id"]
    offer = _turn(agent_web, session, "run forms-chat")["conversation"]["messages"][-1]
    calls: list[Any] = []

    def execute(request: Any) -> dict[str, Any]:
        calls.append(request)
        return {"ok": status == "succeeded", "answer": "stub " + status}

    monkeypatch.setattr(agent_web, "_execute_workflow_launch", execute)
    request = WorkflowLaunchRequest(
        workflow=_form_workflow().metadata.identity,
        arguments={"company": "Fictional", "mode": "quick"},
        session_id=session,
        form_message_id=offer["message_id"],
        idempotency_key="attempt-one",
    )
    agent_web.launch_workflow(request)
    assert agent_web.launch_workflow(request)["replayed"]
    retry = request.model_copy(update={"idempotency_key": "attempt-two", "retry_of": "attempt-one"})
    agent_web.launch_workflow(retry)
    assert len(calls) == (2 if status == "failed" else 1)
    # A delayed double click from the first retry cannot launch a third attempt.
    assert agent_web.launch_workflow(retry)["replayed"]
    assert len(calls) == (2 if status == "failed" else 1)


def test_exception_and_restart_are_visible_and_never_automatically_retried(
    web: Any, monkeypatch: Any
) -> None:
    from host_runtime.web import AgentWeb

    agent_web, runtime, _ = web
    session = agent_web.create_conversation()["conversation"]["session_id"]
    offer = _turn(agent_web, session, "run forms-chat")["conversation"]["messages"][-1]
    request = WorkflowLaunchRequest(
        workflow=_form_workflow().metadata.identity,
        arguments={"company": "Fictional", "mode": "quick"},
        session_id=session,
        form_message_id=offer["message_id"],
        idempotency_key="interrupted-one",
    )

    def broken(request: Any) -> Any:
        raise RuntimeError("synthetic private content")

    monkeypatch.setattr(agent_web, "_execute_workflow_launch", broken)
    with pytest.raises(RuntimeError):
        agent_web.launch_workflow(request)
    form = agent_web.conversations(session)["selected"]["messages"][-1]["workflow_form"]
    assert form["run"]["status"] == "failed"
    assert "synthetic private content" not in form["run"]["answer"]
    runtime.state.set_workflow_form_run(
        session,
        runtime.actor,
        offer["message_id"],
        {"status": "running", "owner": agent_web._workflow_form_owner, "key": "old-attempt"},
    )
    restarted = AgentWeb(runtime)
    shown = restarted.conversations(session)["selected"]["messages"][-1]["workflow_form"]["run"]
    assert shown["status"] == "interrupted"
    assert "owner" not in shown
    assert restarted.launch_workflow(request)["status"] == "interrupted"


def test_invalid_values_do_not_consume_the_form(web: Any) -> None:
    from common.workflow_parameters import WorkflowParameterError

    agent_web, _, _ = web
    session = agent_web.create_conversation()["conversation"]["session_id"]
    _turn(agent_web, session, "run forms-chat")
    request = WorkflowLaunchRequest(
        workflow=_form_workflow().metadata.identity,
        arguments={},
        session_id=session,
        idempotency_key="invalid-form",
    )
    with pytest.raises(WorkflowParameterError):
        agent_web.launch_workflow(request)
    assert (
        "run" not in agent_web.conversations(session)["selected"]["messages"][-1]["workflow_form"]
    )


def test_old_recorded_form_run_is_consumed_without_changing_history(
    web: Any, monkeypatch: Any
) -> None:
    agent_web, runtime, _ = web
    session = agent_web.create_conversation()["conversation"]["session_id"]
    _turn(agent_web, session, "run forms-chat")
    request = WorkflowLaunchRequest(
        workflow=_form_workflow().metadata.identity,
        arguments={"company": "Fictional", "mode": "quick"},
        idempotency_key="old-client",
        session_id=session,
    )
    agent_web._execute_workflow_launch(request)
    before = runtime.state.conversation(session, runtime.actor)
    shown = agent_web.conversations(session)["selected"]
    assert shown["messages"][1]["workflow_form"]["run"]["status"] == "failed"
    assert shown["messages"][1]["workflow_form"]["run"]["arguments"] == {
        **request.arguments,
        "dryRun": True,
    }
    assert runtime.state.conversation(session, runtime.actor) == before

    def unexpected(request: Any) -> Any:
        raise AssertionError("old form executed again")

    monkeypatch.setattr(agent_web, "_execute_workflow_launch", unexpected)
    assert agent_web.launch_workflow(request)["replayed"]


@pytest.mark.parametrize(
    "suffix,expected",
    [
        (
            ': company="Fictional, Inc=Lab", mode="deep", dryRun=false',
            ({"company": "Fictional, Inc=Lab", "mode": "deep", "dryRun": False}, []),
        ),
        (
            ': packages=(file), names=["a", "b"], options={"x": 1}',
            ({"names": ["a", "b"], "options": {"x": 1}}, ["packages"]),
        ),
        (': company="truncated', None),
        (': mode="quick", ', None),
    ],
)
def test_legacy_arguments_are_recovered_only_from_complete_generated_values(
    suffix: str, expected: Any
) -> None:
    from host_runtime.workflow_form_runs import _legacy_values

    prefix = "▶ Run forms-chat from the form"
    assert _legacy_values(prefix + suffix, prefix) == expected


@pytest.mark.parametrize("ending", ["number", "field_boundary"])
def test_legacy_recorder_limit_cannot_restore_valid_looking_truncated_values(ending: str) -> None:
    from host_runtime.workflow_form_runs import _legacy_values

    prefix = "▶ Run forms-chat from the form"
    lead = prefix + ': company="'
    tail = '", number=123' if ending == "number" else '"'
    recorded = lead + "x" * (1500 - len(lead) - len(tail)) + tail
    original = recorded + ("456" if ending == "number" else ', mode="deep"')
    assert original[:1500] == recorded
    assert _legacy_values(recorded, prefix) is None
