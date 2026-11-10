"""Automatic trial repair preserves the inputs of the actual approved trial."""

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from test_authoring_repair import Capturing
from test_chat_authoring import Echo, Out, context, spec, studio, workflow
from test_conversation_turn_groups import _chat_config, _ChatGateway

from agent.gateway import HostToolOutcome
from capabilities.runtime import CapabilityExecutionFailed
from common.assets import ExecutionDependencies
from common.base import Contract
from common.execution import RequestContext
from host_runtime.authoring_task import Requirement
from host_runtime.host import build_runtime
from host_runtime.web import AgentWeb


@pytest.mark.parametrize(
    "supplied", ["empty", "omitted", "matching_subset", "conflicting", "patched"]
)
@pytest.mark.parametrize("entry", ["approval", "card"])
def test_approved_failure_continuation_cannot_replace_qa_inputs_with_defaults(
    tmp_path: Path, supplied: str, entry: str
) -> None:
    config, layout = _chat_config(tmp_path)
    with build_runtime(config, layout=layout, model_transport=_ChatGateway()) as runtime:
        calls: list[str] = []

        async def fail(context: RequestContext, inputs: Contract) -> Contract:
            value = Echo.model_validate(inputs).value
            calls.append(value)
            raise CapabilityExecutionFailed("fixture_failure", Out(echoed=value))

        capability = "qa-write" if entry == "approval" else "qa-read"
        runtime.agent.gateway.bridge.installed.register(
            spec(capability, "write" if entry == "approval" else "read"),
            fail,
            Echo,
            Out,
            ExecutionDependencies(central_required=False),
        )
        web = AgentWeb(runtime)
        session = web.create_conversation()["conversation"]["session_id"]
        chat = runtime.chat_authoring
        assert chat is not None
        chat.tasks.plan(
            runtime.actor,
            session,
            "QA report",
            [
                Requirement.model_validate(
                    {
                        "requirement_id": "report",
                        "description": "Produce the QA report",
                        "check_ids": ["report"],
                        "assertions": [
                            {
                                "path": ["steps", 0, "capability", "name"],
                                "operator": "equals",
                                "expected": capability,
                            }
                        ],
                    }
                )
            ],
        )
        defaults: dict[str, Any] = {
            "start": "2026-07-01",
            "end": "2026-07-31",
            "rate": 0.8,
            "margin": 0.02,
            "mapping": "formal-map.xlsx",
            "prefix": "formal-report",
        }
        approved: dict[str, Any] = {
            "start": "2026-11-01",
            "end": "2026-11-08",
            "rate": 0.9,
            "margin": 0.03,
            "mapping": "alternate-map.xlsx",
            "prefix": "QA-report",
        }
        if entry == "card":
            defaults = dict(approved)
        raw = {
            "name": "qa-argument-continuity",
            "description": "QA report",
            "parameters": [
                {
                    "name": name,
                    "label": name,
                    "kind": "number"
                    if name in {"rate", "margin"}
                    else "date"
                    if name in {"start", "end"}
                    else "text",
                    "scope": "runtime",
                    "required": True,
                    "default": value,
                }
                for name, value in defaults.items()
            ],
            "steps": [
                {
                    "capability": f"lab/{capability}@1.0.0",
                    "inputs": {
                        "value": {"source": "run", "path": ["prefix"]},
                    },
                }
            ],
            "checks": [{"check_id": "report", "step_index": 0, "kind": "data_nonempty"}],
        }
        item, problems = chat.draft(runtime.actor, session, "QA report", raw)
        assert item is not None and not problems
        call: dict[str, Any] = {"candidate_id": item.candidate_id}
        if supplied != "omitted":
            call["arguments"] = (
                {"prefix": "formal-report"}
                if supplied == "conflicting"
                else ({"prefix": "QA-report", "rate": 0.9} if supplied == "matching_subset" else {})
            )
        responses: list[dict[str, Any]] = []
        if supplied == "patched":
            from host_runtime.chat_authoring import digest

            responses.append(
                {
                    "tools": [
                        (
                            "authoring__patch_workflow",
                            {
                                "candidate_id": item.candidate_id,
                                "base_digest": digest(item.draft),
                                "operations": [
                                    {
                                        "op": "replace",
                                        "path": ["steps", 0, "inputs", "value"],
                                        "value": {"source": "fixed", "value": "patched-step"},
                                    }
                                ],
                            },
                        )
                    ]
                }
            )
        responses.append(
            {
                "tools": [
                    (
                        "authoring__run_workflow",
                        {
                            **call,
                        },
                    )
                ]
            },
        )
        model = Capturing(
            *responses,
            {"text": "The QA trial awaits approval."},
            {"text": "The QA trial remains unverified."},
        )
        runtime.agent.gateway.router.model = model

        if entry == "approval":
            first = chat.request(runtime.actor, session, "run", item.candidate_id, approved)
            result = web.decide_approval(first.approval_id, "approve")
            assert result["ok"] is True
            assert result["approval"]["result"]["status"] == "failed"
        else:
            (card,) = web.draft_turn_cards(session, datetime(2000, 1, 1, tzinfo=UTC))
            result = web.decide_card(card["card_id"], "try")
            assert result["code"] == "tried" and result["ok"] is False

        assert calls == (
            ["QA-report", "patched-step" if supplied == "patched" else "QA-report"]
            if entry == "card" and supplied != "conflicting"
            else ["QA-report"]
        )
        pending = [
            a
            for a in chat.approvals(runtime.actor, session_id=session)
            if a.kind == "run" and a.candidate_id == item.candidate_id
        ]
        if supplied != "conflicting" and entry == "approval":
            assert len(pending) == 1 and pending[0].arguments == approved
        elif supplied == "conflicting":
            assert all(a.arguments == approved for a in pending)
            assert any(
                "authoring_trial_arguments_conflict" in m.text
                for request in model.requests
                for m in request.messages
            )
        task = chat.tasks.load(runtime.actor, session)
        assert task is not None and task.question is None
        assert task.last_trial_arguments == approved
        assert (
            chat.candidate(item.candidate_id, runtime.actor).draft.parameters
            == item.draft.parameters
        )
        assert (chat.candidate(item.candidate_id, runtime.actor).draft == item.draft) is (
            supplied != "patched"
        )


@pytest.mark.parametrize(
    "evidence",
    [
        "valid",
        "missing_arguments",
        "active_token",
        "stale_digest",
        "copied_candidate",
        "history_candidate",
        "history_run",
        "history_digest",
        "foreign_session",
        "foreign_actor",
    ],
)
def test_read_only_repair_inherits_actual_inputs_only_with_matching_host_evidence(
    tmp_path: Path, evidence: str
) -> None:
    from test_authoring_trial_diagnostics import _plan

    chat, _ = studio(tmp_path)
    calls: list[str] = []

    async def fail(context: RequestContext, inputs: Contract) -> Contract:
        calls.append(Echo.model_validate(inputs).value)
        raise CapabilityExecutionFailed("fixture_failure", Out(echoed="failed"))

    chat.installed.register(
        spec("qa-read", "read"), fail, Echo, Out, ExecutionDependencies(central_required=False)
    )
    _plan(chat, capability="qa-read")
    raw = workflow("qa-read")
    raw["parameters"][0]["default"] = "formal-month"
    raw["checks"] = [{"check_id": "rows", "step_index": 0, "kind": "data_nonempty"}]
    item, problems = chat.draft("owner", "session-1", "Read", raw)
    assert item is not None and not problems
    assert chat.execute("owner", item, {"month": "QA-month"}, "actual-read")["status"] == "failed"
    current = chat.candidate(item.candidate_id, "owner")
    task = current.authoring_task
    assert task is not None
    if evidence == "copied_candidate":
        raw["name"] = "another-candidate"
        copied, problems = chat.draft("owner", "session-1", "Other", raw)
        assert copied is not None and not problems
        current = copied
    elif evidence in {"missing_arguments", "active_token", "stale_digest"}:
        updates: dict[str, dict[str, Any]] = {
            "missing_arguments": {"last_trial_arguments": {}},
            "active_token": {"active_trial_token": "still-running"},
            "stale_digest": {"last_trial_digest": "0" * 64},
        }
        task = task.model_copy(update=updates[evidence])
    elif evidence.startswith("history_"):
        entry = dict(task.trial_history[-1])
        entry[
            {
                "history_candidate": "candidate_id",
                "history_run": "run_id",
                "history_digest": "digest",
            }[evidence]
        ] = "wrong"
        task = task.model_copy(update={"trial_history": (*task.trial_history[:-1], entry)})
    if evidence not in {"valid", "copied_candidate", "foreign_session", "foreign_actor"}:
        current = chat._save_candidate(current.model_copy(update={"authoring_task": task}))
        chat.tasks.save("owner", "session-1", task)
    repair = context().model_copy(
        update={
            "actor": "other-actor" if evidence == "foreign_actor" else "owner",
            "session_id": "other-session" if evidence == "foreign_session" else "session-1",
            "message": f"[Host authoring continuation: failure] Candidate {current.candidate_id}; "
            "failure",
        }
    )
    tool = next(t for t in chat.tools() if t.tool.name == "authoring__run_workflow")

    async def invoke() -> HostToolOutcome:
        return await tool.handler(repair, {"candidate_id": current.candidate_id, "arguments": {}})

    outcome = asyncio.run(invoke())
    if evidence == "valid":
        assert calls == ["QA-month", "QA-month"]
    else:
        assert calls == ["QA-month"]
        assert outcome.failure is not None
        assert outcome.failure.code in {
            "authoring_trial_arguments_unavailable",
            "authoring_repair_scope",
            "candidate_unknown",
        }
    active = chat.tasks.load("owner", "session-1")
    assert active is not None and active.question is None


@pytest.mark.parametrize("evidence", ["missing", "foreign_session", "stale_run"])
def test_write_continuation_requires_matching_actual_approved_run(
    tmp_path: Path, evidence: str
) -> None:
    from test_authoring_trial_diagnostics import _plan

    chat, _ = studio(tmp_path)
    calls: list[str] = []

    async def fail(context: RequestContext, inputs: Contract) -> Contract:
        calls.append(Echo.model_validate(inputs).value)
        raise CapabilityExecutionFailed("fixture_failure", Out(echoed="failed"))

    chat.installed.register(
        spec("qa-write", "write"), fail, Echo, Out, ExecutionDependencies(central_required=False)
    )
    _plan(chat, capability="qa-write")
    raw = workflow("qa-write")
    raw["parameters"][0]["default"] = "formal-month"
    raw["checks"] = [{"check_id": "rows", "step_index": 0, "kind": "data_nonempty"}]
    item, problems = chat.draft("owner", "session-1", "Write", raw)
    assert item is not None and not problems
    approval = chat.request("owner", "session-1", "run", item.candidate_id, {"month": "QA-month"})
    decided = chat.decide(approval.approval_id, "owner", True)
    assert isinstance(decided.result, dict) and decided.result["status"] == "failed"
    if evidence == "missing":
        chat._file("approval", approval.approval_id).unlink()
    elif evidence == "foreign_session":
        chat._save_approval(decided.model_copy(update={"session_id": "other-session"}))
    else:
        chat._save_approval(
            decided.model_copy(update={"result": {**decided.result, "run_id": "stale"}})
        )
    repair = context().model_copy(
        update={
            "message": f"[Host authoring continuation: failure] Candidate {item.candidate_id}; "
            "failure"
        }
    )
    tool = next(t for t in chat.tools() if t.tool.name == "authoring__run_workflow")

    async def invoke() -> HostToolOutcome:
        return await tool.handler(repair, {"candidate_id": item.candidate_id, "arguments": {}})

    outcome = asyncio.run(invoke())
    assert (
        outcome.failure is not None
        and outcome.failure.code == "authoring_trial_arguments_unavailable"
    )
    assert calls == ["QA-month"]
    assert chat.approvals("owner", session_id="session-1") == []
