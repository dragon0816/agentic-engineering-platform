"""Bounded conversation history retains honest single-message repair outcomes."""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from test_authoring_repair import Capturing
from test_chat_authoring import Echo, Out, spec
from test_conversation_turn_groups import _chat_config, _ChatGateway

from capabilities.runtime import CapabilityExecutionFailed
from common.assets import ExecutionDependencies
from common.base import Contract
from common.distribution import LocalStateError
from common.execution import RequestContext
from host_runtime.authoring_task import Requirement
from host_runtime.chat_authoring import digest
from host_runtime.conversations import MAX_STORED_MESSAGES, ConversationMessage, ConversationRecord
from host_runtime.host import build_runtime
from host_runtime.state import SqliteLocalState
from host_runtime.web import AgentWeb


@pytest.fixture
def state(tmp_path: Path) -> Iterator[SqliteLocalState]:
    store = SqliteLocalState(tmp_path / "state.sqlite", bridge_id="test-bridge")
    try:
        yield store
    finally:
        store.close()


def _messages(count: int, created: datetime) -> tuple[ConversationMessage, ...]:
    return tuple(
        ConversationMessage(
            message_id=f"old-{index}",
            role="user" if index % 2 == 0 else "assistant",
            text=f"Original message {index}",
            created_at=created + timedelta(microseconds=index),
            status="submitted" if index % 2 == 0 else "answered",
        )
        for index in range(count)
    )


def _record(count: int) -> ConversationRecord:
    created = datetime(2026, 11, 10, tzinfo=UTC)
    messages = _messages(count, created)
    return ConversationRecord(
        session_id="session-1",
        actor="owner",
        title="Original conversation",
        created_at=created,
        updated_at=messages[-1].created_at,
        messages=messages,
    )


def _append(record: ConversationRecord, count: int) -> ConversationRecord:
    added = tuple(
        ConversationMessage(
            message_id=f"new-{count}-{index}",
            role="user" if count > 1 and index == 0 else "assistant",
            text=f"New message {index}",
            created_at=record.updated_at + timedelta(seconds=index + 1),
            status="submitted" if count > 1 and index == 0 else "answered",
        )
        for index in range(count)
    )
    return record.model_copy(
        update={
            "messages": (*record.messages, *added)[-MAX_STORED_MESSAGES:],
            "updated_at": added[-1].created_at,
        }
    )


@pytest.mark.parametrize("old_count", [MAX_STORED_MESSAGES - 1, MAX_STORED_MESSAGES])
@pytest.mark.parametrize("append_count", [1, 2])
def test_single_or_pair_append_preserves_exact_retained_history_at_capacity(
    state: SqliteLocalState, old_count: int, append_count: int
) -> None:
    original = state.create_conversation(_record(old_count))
    proposed = _append(original, append_count)

    saved = state.save_conversation(proposed)

    assert saved.messages == proposed.messages
    dropped = max(0, old_count + append_count - MAX_STORED_MESSAGES)
    assert saved.messages[: old_count - dropped] == original.messages[dropped:]
    assert state.conversation("session-1", "owner") == saved
    assert state.conversation("session-1", "other") is None


@pytest.mark.parametrize(
    "mutation", ["rewrite", "stale_time", "foreign_actor", "stale_snapshot", "roll_three", "shrink"]
)
def test_rollover_does_not_authorize_rewrites_deletion_or_stale_owner_updates(
    state: SqliteLocalState, mutation: str
) -> None:
    original = state.create_conversation(_record(MAX_STORED_MESSAGES))
    proposed = _append(original, 1)
    expected = "conversation_update_stale"
    if mutation == "rewrite":
        messages = list(proposed.messages)
        messages[10] = messages[10].model_copy(update={"text": "Rewritten retained evidence"})
        proposed = proposed.model_copy(update={"messages": tuple(messages)})
    elif mutation == "stale_time":
        state.save_conversation(
            original.model_copy(update={"updated_at": original.updated_at + timedelta(seconds=10)})
        )
    elif mutation == "foreign_actor":
        proposed = proposed.model_copy(update={"actor": "other"})
        expected = "conversation_owner_fixed"
    elif mutation == "stale_snapshot":
        concurrent = state.save_conversation(_append(original, 2))
        later = concurrent.updated_at + timedelta(seconds=1)
        last = proposed.messages[-1].model_copy(update={"created_at": later})
        proposed = proposed.model_copy(
            update={"messages": (*proposed.messages[:-1], last), "updated_at": later}
        )
    elif mutation == "roll_three":
        proposed = _append(original, 3)
    elif mutation == "shrink":
        proposed = original.model_copy(
            update={
                "messages": original.messages[1:],
                "updated_at": original.updated_at + timedelta(seconds=1),
            }
        )
    before = state.conversation("session-1", "owner")

    with pytest.raises(LocalStateError) as error:
        state.save_conversation(proposed)

    assert error.value.code == expected
    assert state.conversation("session-1", "owner") == before


def test_failed_approved_trial_saves_one_real_repair_answer_at_max_history(tmp_path: Path) -> None:
    config, layout = _chat_config(tmp_path)
    with build_runtime(config, layout=layout, model_transport=_ChatGateway()) as runtime:
        calls: list[str] = []

        async def read(context: RequestContext, inputs: Contract) -> Contract:
            value = Echo.model_validate(inputs).value
            calls.append(value)
            if value == "bad":
                raise CapabilityExecutionFailed("fixture_failure", Out(echoed="failed"))
            return Out(echoed=value)

        runtime.agent.gateway.bridge.installed.register(
            spec("read-it", "read"), read, Echo, Out, ExecutionDependencies(central_required=False)
        )
        web = AgentWeb(runtime)
        session = web.create_conversation()["conversation"]["session_id"]
        record = runtime.state.conversation(session, runtime.actor)
        assert record is not None
        original = _messages(MAX_STORED_MESSAGES, record.created_at)
        runtime.state.save_conversation(
            record.model_copy(
                update={
                    "messages": original,
                    "updated_at": original[-1].created_at,
                }
            )
        )
        chat = runtime.chat_authoring
        assert chat is not None
        chat.tasks.plan(
            runtime.actor,
            session,
            "Read fixture",
            [
                Requirement.model_validate(
                    {
                        "requirement_id": "read",
                        "description": "Read fixture",
                        "check_ids": ["rows"],
                        "assertions": [
                            {
                                "path": ["steps", 0, "capability", "name"],
                                "operator": "equals",
                                "expected": "read-it",
                            }
                        ],
                    }
                )
            ],
        )
        raw: dict[str, Any] = {
            "name": "bounded-history-repair",
            "description": "Read fixture",
            "parameters": [],
            "steps": [
                {
                    "capability": "lab/read-it@1.0.0",
                    "inputs": {"value": {"source": "fixed", "value": "bad"}},
                }
            ],
            "checks": [{"check_id": "rows", "step_index": 0, "kind": "data_nonempty"}],
        }
        item, problems = chat.draft(runtime.actor, session, "Read fixture", raw)
        assert item is not None and not problems
        raw["steps"][0]["inputs"]["value"]["value"] = "good"
        model = Capturing(
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
                                    "path": ["steps", 0, "inputs", "value", "value"],
                                    "value": "good",
                                }
                            ],
                        },
                    )
                ]
            },
            {
                "tools": [
                    (
                        "authoring__run_workflow",
                        {"candidate_id": item.candidate_id, "arguments": {}},
                    )
                ]
            },
            {"text": "Trial passed; review the candidate."},
        )
        runtime.agent.gateway.router.model = model
        approval = chat.request(runtime.actor, session, "run", item.candidate_id, {})

        result = web.decide_approval(approval.approval_id, "approve")

        assert result["approval"]["result"]["status"] == "failed"
        assert result["repair"]["status"] == "answered" and calls == ["bad", "good"]
        saved = runtime.state.conversation(session, runtime.actor)
        assert saved is not None and len(saved.messages) == MAX_STORED_MESSAGES
        assert saved.messages[:-3] == original[3:]
        assert [m.role for m in saved.messages[-3:]] == ["user", "assistant", "assistant"]
        assert saved.messages[-1].message_id == result["repair"]["message"]["message_id"]
        assert saved.messages[-1].text == "Trial passed; review the candidate."
        assert web._resume_failed_authoring(session) is None and calls == ["bad", "good"]
