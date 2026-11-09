from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from test_chat_authoring import Echo, Out, spec
from test_chat_workflow_forms_telegram import _Scripted
from test_conversation_turn_groups import _chat_config, _ChatGateway

from capabilities.runtime import CapabilityExecutionFailed
from capabilities.web.handlers import WebHostBinding
from common.assets import ExecutionDependencies
from common.base import Contract
from common.execution import RequestContext
from host_runtime.authoring_task import Requirement
from host_runtime.chat_authoring import digest
from host_runtime.conversations import ConversationMessage
from host_runtime.host import build_runtime
from host_runtime.web import AgentWeb
from models.contracts import ModelRequest, ModelResponse


class Capturing(_Scripted):
    def __init__(self, *answers: Any) -> None:
        super().__init__(*answers)
        self.requests: list[ModelRequest] = []

    def generate(self, request: ModelRequest) -> ModelResponse:
        self.requests.append(request)
        return super().generate(request)


def test_failed_authoring_resumes_once_with_only_safe_tools_and_retests(tmp_path: Path) -> None:
    config, layout = _chat_config(tmp_path)
    config = config.model_copy(update={"web": WebHostBinding(allowed_origins=("*",))})
    with build_runtime(config, layout=layout, model_transport=_ChatGateway()) as runtime:
        calls: list[str] = []

        async def fixture(context: RequestContext, inputs: Contract) -> Contract:
            value = Echo.model_validate(inputs).value
            calls.append(value)
            if value == "bad":
                raise CapabilityExecutionFailed("fixture_failure", Out(echoed="failed"))
            return Out(echoed=value)

        runtime.agent.gateway.bridge.installed.register(
            spec("read-it", "read"),
            fixture,
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
            "Read fixture using good input",
            [
                Requirement(
                    requirement_id="read",
                    description="Read fixture",
                    check_ids=("read",),
                    assertions=(
                        {
                            "path": ["steps", 0, "capability", "name"],
                            "operator": "equals",
                            "expected": "read-it",
                        },
                    ),
                )
            ],
        )
        raw: dict[str, Any] = {
            "name": "repair-fixture",
            "description": "Read fixture",
            "parameters": [],
            "steps": [
                {
                    "capability": "lab/read-it@1.0.0",
                    "inputs": {"value": {"source": "fixed", "value": "bad"}},
                }
            ],
            "checks": [{"check_id": "read", "step_index": 0, "kind": "data_nonempty"}],
        }
        item, problems = chat.draft(runtime.actor, session, "fixture", raw)
        assert item is not None and not problems
        failed = chat.execute(runtime.actor, item, {}, "owner-requested-test")
        assert failed["status"] == "failed"
        raw["steps"][0]["inputs"]["value"]["value"] = "good"
        model = Capturing(
            {
                "tools": [
                    (
                        "authoring__draft_workflow",
                        {"title": "fixture", "candidate_id": item.candidate_id, "workflow": raw},
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
            {"text": "試跑成功，草稿可供審核。"},
        )
        runtime.agent.gateway.router.model = model
        result = web._resume_failed_authoring(session)
        assert result is not None and result["status"] == "answered"
        assert calls == ["bad", "good"]
        assert web._resume_failed_authoring(session) is None
        assert calls == ["bad", "good"]
        for request in model.requests:
            names = {tool.name for tool in request.tools}
            assert "browser__operate" not in names and "coding__run" not in names
            assert "browser__inspect" in names
        current = chat.candidate(item.candidate_id, runtime.actor)
        assert current.authoring_task is not None and current.authoring_task.verified_digest


def test_draft_card_trial_failure_starts_safe_repair(tmp_path: Path) -> None:
    _exercise_draft_card_repair(tmp_path, "none")


def test_successful_partial_card_trial_continues_until_procedure_is_verified(
    tmp_path: Path,
) -> None:
    _exercise_draft_card_repair(tmp_path, "none", partial=True)


@pytest.mark.parametrize("pending", ["stale_digest", "other_candidate", "current"])
def test_only_current_candidate_trial_approval_blocks_card_repair(
    tmp_path: Path, pending: str
) -> None:
    _exercise_draft_card_repair(tmp_path, pending)


def _exercise_draft_card_repair(tmp_path: Path, pending: str, *, partial: bool = False) -> None:
    config, layout = _chat_config(tmp_path)
    config = config.model_copy(update={"web": WebHostBinding(allowed_origins=("*",))})
    with build_runtime(config, layout=layout, model_transport=_ChatGateway()) as runtime:
        calls: list[str] = []

        async def fixture(context: RequestContext, inputs: Contract) -> Contract:
            value = Echo.model_validate(inputs).value
            calls.append(value)
            if value == "bad" and not partial:
                raise CapabilityExecutionFailed("fixture_failure", Out(echoed="failed"))
            return Out(echoed=value)

        runtime.agent.gateway.bridge.installed.register(
            spec("read-it", "read"),
            fixture,
            Echo,
            Out,
            ExecutionDependencies(central_required=False),
        )
        web = AgentWeb(runtime)
        session = web.create_conversation()["conversation"]["session_id"]
        chat = runtime.chat_authoring
        assert chat is not None
        requirement = Requirement.model_validate(
            {
                "requirement_id": "read",
                "description": "Read fixture",
                "check_ids": ["read"],
                "assertions": [
                    {
                        "path": ["steps", 0, "inputs", "value", "value"]
                        if partial
                        else ["steps", 0, "capability", "name"],
                        "operator": "equals",
                        "expected": "good" if partial else "read-it",
                    }
                ],
            }
        )
        chat.tasks.plan(
            runtime.actor,
            session,
            "Read fixture",
            [requirement],
        )
        raw: dict[str, Any] = {
            "name": "repair-card",
            "description": "Read fixture",
            "parameters": [],
            "steps": [
                {
                    "capability": "lab/read-it@1.0.0",
                    "inputs": {"value": {"source": "fixed", "value": "bad"}},
                }
            ],
            "checks": [{"check_id": "read", "step_index": 0, "kind": "data_nonempty"}],
        }
        item, problems = chat.draft(runtime.actor, session, "fixture", raw)
        assert item is not None and not problems
        approval = None
        if pending == "other_candidate":
            other_raw = dict(raw, name="unrelated-card")
            other, problems = chat.draft(runtime.actor, session, "Unrelated", other_raw)
            assert other is not None and not problems
            approval = chat.request(runtime.actor, session, "run", other.candidate_id, {})
        elif pending in ("current", "stale_digest"):
            approval = chat.request(runtime.actor, session, "run", item.candidate_id, {})
        if pending == "stale_digest":
            raw["description"] = "Updated after approval was requested"
            item, problems = chat.draft(runtime.actor, session, "fixture", raw, item.candidate_id)
            assert item is not None and not problems
        cards = web.draft_turn_cards(session, datetime(2000, 1, 1, tzinfo=UTC))
        card = next(card for card in cards if card["title"].endswith("“fixture”?"))
        raw["steps"][0]["inputs"]["value"]["value"] = "good"
        model = Capturing(
            {
                "tools": [
                    (
                        "authoring__draft_workflow",
                        {
                            "title": "fixture",
                            "candidate_id": item.candidate_id,
                            "workflow": raw,
                        },
                    )
                ]
            },
            {
                "tools": [
                    (
                        "authoring__run_workflow",
                        {
                            "candidate_id": item.candidate_id,
                            "arguments": {},
                        },
                    )
                ]
            },
            {"text": "Trial passed; review the candidate."},
        )
        runtime.agent.gateway.router.model = model

        result = web.decide_card(card["card_id"], "try")

        assert result["code"] == "tried" and result["ok"] is partial
        active = chat.tasks.load(runtime.actor, session)
        assert active is not None
        if pending == "current":
            assert calls == ["bad"] and model.requests == []
            assert active.repair_attempts == 1
            assert "repair" not in result
        else:
            assert calls == ["bad", "good"]
            assert result["repair"]["status"] == "answered"
            assert active.verified_digest == digest(
                chat.candidate(item.candidate_id, runtime.actor).draft
            )
            assert active.repair_attempts == 0
            assert web._resume_failed_authoring(session) is None
            assert calls == ["bad", "good"]
        if approval is not None:
            pending_approvals = chat.approvals(runtime.actor, session_id=session)
            assert any(a.approval_id == approval.approval_id for a in pending_approvals)


@pytest.mark.parametrize("failed", [False, True])
def test_approved_trial_refreshes_stored_install_card(tmp_path: Path, failed: bool) -> None:
    config, layout = _chat_config(tmp_path)
    config = config.model_copy(update={"web": WebHostBinding(allowed_origins=("*",))})
    with build_runtime(config, layout=layout, model_transport=_ChatGateway()) as runtime:

        async def fixture(context: RequestContext, inputs: Contract) -> Contract:
            if Echo.model_validate(inputs).value == "bad":
                raise CapabilityExecutionFailed("fixture_failure", Out(echoed="failed"))
            return Out(echoed="good")

        runtime.agent.gateway.bridge.installed.register(
            spec("write-it", "write"),
            fixture,
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
            "Write fixture",
            [
                Requirement.model_validate(
                    {
                        "requirement_id": "write",
                        "description": "Write fixture",
                        "check_ids": ["written"],
                        "assertions": [
                            {
                                "path": ["steps", 0, "capability", "name"],
                                "operator": "equals",
                                "expected": "write-it",
                            }
                        ],
                    }
                )
            ],
        )
        raw: dict[str, Any] = {
            "name": "refresh-card",
            "description": "Write fixture",
            "parameters": [
                {
                    "name": "value",
                    "label": "Value",
                    "kind": "text",
                    "scope": "runtime",
                    "required": True,
                }
            ],
            "steps": [
                {
                    "capability": "lab/write-it@1.0.0",
                    "inputs": {"value": {"source": "run", "path": ["value"]}},
                }
            ],
            "checks": [{"check_id": "written", "step_index": 0, "kind": "data_nonempty"}],
        }
        item, problems = chat.draft(runtime.actor, session, "Refresh", raw)
        assert item is not None and not problems
        if failed:
            # A previously proved candidate must lose its visible Install button on failure.
            first = chat.request(
                runtime.actor, session, "run", item.candidate_id, {"value": "good"}
            )
            assert (
                web.decide_approval(first.approval_id, "approve")["approval"]["status"]
                == "approved"
            )
            task = chat.tasks.load(runtime.actor, session)
            assert task is not None
            chat.tasks.save(runtime.actor, session, task.model_copy(update={"repair_attempts": 2}))
        cards = web.draft_turn_cards(session, datetime(2000, 1, 1, tzinfo=UTC))
        (card,) = cards
        assert ("install" in [b["action"] for b in card["buttons"]]) is failed
        record = runtime.state.conversation(session, runtime.actor)
        assert record is not None
        now = datetime.now(UTC)
        runtime.state.save_conversation(
            record.model_copy(
                update={
                    "updated_at": now,
                    "messages": (
                        *record.messages,
                        ConversationMessage(
                            message_id="draft-card-message",
                            role="assistant",
                            text="Review this candidate",
                            status="answered",
                            created_at=now,
                            action_cards=(card,),
                        ),
                    ),
                }
            )
        )
        approval = chat.request(
            runtime.actor, session, "run", item.candidate_id, {"value": "bad" if failed else "good"}
        )

        result = web.decide_approval(approval.approval_id, "approve")

        assert result["approval"]["status"] == "approved"
        assert result["approval"]["result"]["status"] == ("failed" if failed else "succeeded")
        messages = web.conversations(session)["selected"]["messages"]
        stored = next(m for m in messages if m["message_id"] == "draft-card-message")
        (shown,) = stored["action_cards"]
        assert shown["card_id"] == card["card_id"]
        assert ("install" in [b["action"] for b in shown["buttons"]]) is not failed
        assert chat.candidate(item.candidate_id, runtime.actor).revision == item.revision
