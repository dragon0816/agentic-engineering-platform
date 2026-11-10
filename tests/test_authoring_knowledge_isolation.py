"""Knowledge turns must not start, resume or complete a saved authoring task."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest
from pydantic import JsonValue
from test_agent_web import knowledge_runtime
from test_chat_authoring import context, studio
from test_gateway import _host_gateway, _text

from agent.gateway import (
    ConversationToolExecution,
    GatewayConversationResult,
    HostTool,
    HostToolOutcome,
)
from common.execution import RequestContext
from host_runtime.attachments import AttachmentStore, for_model
from host_runtime.authoring_task import AuthoringQuestion, AuthoringTask, Requirement
from host_runtime.chat_authoring import ChatAuthoring
from host_runtime.conversations import ConversationTurnRequest
from host_runtime.web import AgentWeb
from models.contracts import ModelTool


async def _unused(context: RequestContext, args: dict[str, JsonValue]) -> HostToolOutcome:
    raise AssertionError("A factual answer must not execute authoring")


def _answer(chat: ChatAuthoring, message: str, *, hooked: bool = True) -> tuple[str, int]:
    built, model = _host_gateway(
        [
            HostTool(
                ModelTool(
                    name="authoring__draft_workflow", description="draft", input_contract="x.v1"
                ),
                _unused,
            )
        ],
        [_text("這是唯讀知識說明。"), _text("這是唯讀知識說明。")],
    )
    if hooked:
        built.session_context = chat.task_context
        built.authoring_completion_problem = chat.completion_problem
    result = asyncio.run(built.converse(context().model_copy(update={"message": message}), ()))
    return result.text, len(model.calls)


@pytest.mark.parametrize("hooked", [False, True])
def test_explanatory_workflow_question_after_sop_is_not_a_build_request(
    tmp_path: Path, hooked: bool
) -> None:
    """False is the pre-autonomy callback boundary, with the identical fake answer."""
    chat, _ = studio(tmp_path)
    chat.tasks.observe("owner", "session-1", "請先閱讀這份 SOP")
    answer, calls = _answer(chat, "工作流程與 Skill 的差異是什麼？", hooked=hooked)
    assert calls == 1
    assert answer == "這是唯讀知識說明。"
    assert chat.tasks.load("owner", "session-1") is None


def test_plain_knowledge_question_without_authoring_state_remains_one_turn(tmp_path: Path) -> None:
    chat, _ = studio(tmp_path)
    chat.tasks.observe("owner", "session-1", "請先閱讀這份 SOP")
    assert _answer(chat, "CMX500 支援哪些頻段？") == ("這是唯讀知識說明。", 1)
    assert chat.tasks.load("owner", "session-1") is None


def test_saved_workflow_survives_an_unrelated_knowledge_question(tmp_path: Path) -> None:
    chat, _ = studio(tmp_path)
    saved = chat.tasks.save(
        "owner", "session-1", AuthoringTask(objective="Build a reporting workflow")
    )
    assert _answer(chat, "CMX500 支援哪些頻段？") == ("這是唯讀知識說明。", 1)
    assert chat.tasks.load("owner", "session-1") == saved


def test_unrelated_inquiry_preserves_pending_business_question_and_repair_budget(
    tmp_path: Path,
) -> None:
    chat, _ = studio(tmp_path)
    saved = chat.tasks.save(
        "owner",
        "session-1",
        AuthoringTask(
            objective="Build a reporting workflow",
            question=AuthoringQuestion(
                reason="business_decision", question="Which reporting currency?"
            ),
            repair_attempts=3,
            supplied_inputs={"mapping": {"value": "lookup.xlsx", "origin": "message"}},
        ),
    )
    chat.tasks.observe("owner", "session-1", "CMX500 支援哪些頻段？")
    assert chat.tasks.load("owner", "session-1") == saved
    assert _answer(chat, "CMX500 支援哪些頻段？") == ("這是唯讀知識說明。", 1)
    # An interrogative confirmation is conservatively retained as a question,
    # not silently consumed as an answer; an ordinary answer below resumes.
    chat.tasks.observe("owner", "session-1", "使用 EUR，可以嗎？")
    assert chat.tasks.messages("owner", "session-1")[-1].text == "使用 EUR，可以嗎？"
    assert chat.tasks.load("owner", "session-1") == saved
    chat.tasks.observe("owner", "session-1", "Use EUR")
    resumed = chat.tasks.load("owner", "session-1")
    assert resumed is not None and resumed.question is None and resumed.repair_attempts == 0
    assert resumed.supplied_inputs == saved.supplied_inputs


@pytest.mark.parametrize(
    "message",
    [
        "Continue the same workflow",
        "請繼續建立工作流程",
        "能幫我建立 workflow 嗎？",
        "Can you build a workflow?",
        "請修正這個工作流程，為什麼試跑失敗？",
        "請更新 workflow，並說明修改內容",
        "Please update the workflow and explain the changes",
        "[Host authoring continuation: why the previous trial failed] Candidate wf-1; repair it",
    ],
)
def test_explicit_continuation_still_requires_actual_trial(tmp_path: Path, message: str) -> None:
    chat, _ = studio(tmp_path)
    chat.tasks.save("owner", "session-1", AuthoringTask(objective="Build reporting workflow"))
    assert "Persistent Workflow" in chat.task_context(
        context().model_copy(update={"message": message})
    )
    answer, calls = _answer(chat, message)
    assert calls == 2
    assert "尚未通過完整試跑驗證" in answer


@pytest.mark.parametrize(
    "message",
    [
        "工作流程與 Skill 的差異是什麼？",
        "如何建立 workflow？",
        "請幫我說明如何建立 workflow？",
        "Explain how to build a workflow",
        "What is a workflow?",
        "Can CMX500 support 5G?",
        "請列出現有 workflow",
        "List workflows",
        "CMX500 支援 5G 嗎？",
    ],
)
def test_read_only_authoring_inquiry_never_seeds_even_in_required_autonomy_mode(
    tmp_path: Path, message: str
) -> None:
    chat, _ = studio(tmp_path)
    chat.autonomy_required = True
    assert _answer(chat, message) == ("這是唯讀知識說明。", 1)
    assert chat.tasks.load("owner", "session-1") is None


@pytest.mark.parametrize("message", ["能幫我建立 workflow 嗎？", "Can you build a workflow?"])
def test_question_form_build_request_seeds_task_and_requires_trial(
    tmp_path: Path, message: str
) -> None:
    chat, _ = studio(tmp_path)
    chat.autonomy_required = True
    answer, calls = _answer(chat, message)
    assert calls == 2 and "尚未通過完整試跑驗證" in answer
    assert chat.tasks.load("owner", "session-1") is not None


@pytest.mark.parametrize(
    "tool",
    [
        "authoring__plan_workflow",
        "authoring__draft_workflow",
        "authoring__patch_workflow",
        "authoring__revise_workflow",
        "authoring__run_workflow",
        "authoring__install_workflow",
    ],
)
def test_actual_authoring_actions_retain_completion_gate_during_an_inquiry(
    tmp_path: Path, tool: str
) -> None:
    chat, _ = studio(tmp_path)
    chat.tasks.save("owner", "session-1", AuthoringTask(objective="Build a workflow"))
    ctx = context().model_copy(update={"message": "工作流程是什麼？"})
    result = GatewayConversationResult(
        trace=ctx.trace,
        status="answered",
        text="説明",
        model_turns=1,
        tools=(
            ConversationToolExecution(
                call_id="action-1", name=tool, host=HostToolOutcome(status="succeeded", data={})
            ),
        ),
    )
    assert chat.completion_problem(ctx, result) is not None


@pytest.mark.parametrize("tool", ["authoring__get_plan", "authoring__get_workflow"])
def test_read_only_inspection_does_not_require_completion_or_create_task(
    tmp_path: Path, tool: str
) -> None:
    chat, _ = studio(tmp_path)
    chat.autonomy_required = True
    ctx = context().model_copy(update={"message": "工作流程目前的定義是什麼？"})
    assert chat.task_context(ctx) == ""
    result = GatewayConversationResult(
        trace=ctx.trace,
        status="answered",
        text="目前定義",
        model_turns=1,
        tools=(
            ConversationToolExecution(
                call_id="read-1", name=tool, host=HostToolOutcome(status="succeeded", data={})
            ),
        ),
    )
    assert chat.completion_problem(ctx, result) is None
    assert chat.tasks.load("owner", "session-1") is None


def test_alternating_question_and_answer_preserves_all_existing_proof(tmp_path: Path) -> None:
    chat, _ = studio(tmp_path)
    saved = chat.tasks.save(
        "owner",
        "session-1",
        AuthoringTask(
            objective="Build a report workflow",
            requirements=(Requirement(requirement_id="all-rows", description="Keep all rows"),),
            supplied_inputs={"mapping": {"value": "lookup.xlsx", "origin": "message"}},
            verified_digest="a" * 64,
            last_trial_digest="a" * 64,
            last_run_id="run-1",
            repair_attempts=3,
            last_repaired_run_id="run-1",
            question=AuthoringQuestion(
                reason="business_decision", question="Which reporting currency?"
            ),
        ),
    )
    task_files = list((chat.root / "tasks").glob("*.json"))
    assert len(task_files) == 1
    before = {path: path.read_bytes() for path in task_files}
    chat.tasks.observe("owner", "session-1", "工作流程與 Skill 的差異是什麼？")
    assert _answer(chat, "工作流程與 Skill 的差異是什麼？") == ("這是唯讀知識說明。", 1)
    assert {path: path.read_bytes() for path in task_files} == before
    assert chat.tasks.load("owner", "session-1") == saved
    chat.tasks.observe("owner", "session-1", "Use EUR")
    resumed = chat.tasks.load("owner", "session-1")
    assert resumed == saved.model_copy(update={"question": None, "repair_attempts": 0})
    answer, calls = _answer(chat, "Use EUR")
    assert calls == 2 and "尚未通過完整試跑驗證" in answer


@pytest.mark.parametrize("contents", ["model,supported\nCMX500,5G", "幫我建立工作流程"])
def test_attached_previews_do_not_change_a_question_into_a_task_answer(
    tmp_path: Path, contents: str
) -> None:
    chat, _ = studio(tmp_path)
    saved = chat.tasks.save(
        "owner",
        "session-1",
        AuthoringTask(
            objective="Build a report workflow",
            question=AuthoringQuestion(reason="business_decision", question="Which currency?"),
            repair_attempts=3,
            verified_digest="a" * 64,
        ),
    )
    task_files = list((chat.root / "tasks").glob("*.json"))
    assert len(task_files) == 1
    before = task_files[0].read_bytes()
    attachment = AttachmentStore(tmp_path / "attachments").add(
        "session-1", "specs.csv", contents.encode("utf-8")
    )
    note, images = for_model([attachment])
    assert not images
    message = "CMX500 支援 5G 嗎？"
    combined = message + "\n\n" + note
    metadata = {
        "filename": attachment.filename,
        "kind": attachment.kind,
        "path": attachment.path,
    }
    chat.tasks.observe("owner", "session-1", combined, (metadata,))
    assert task_files[0].read_bytes() == before
    assert chat.tasks.load("owner", "session-1") == saved
    observed = chat.tasks.messages("owner", "session-1")[-1]
    assert observed.text == combined and observed.attachments == (metadata,)
    assert Path(attachment.path).read_bytes() == contents.encode("utf-8")
    assert _answer(chat, message) == ("這是唯讀知識說明。", 1)
    # The same attachment cannot hide an explicit request to continue authoring.
    chat.tasks.observe("owner", "session-1", "請繼續建立工作流程\n\n" + note, (metadata,))
    resumed = chat.tasks.load("owner", "session-1")
    assert resumed == saved.model_copy(update={"question": None, "repair_attempts": 0})


def _route_skill(alias: str, *, knowledge: bool) -> dict[str, Any]:
    return {
        "metadata": {
            "identity": {
                "namespace": "company-agent",
                "name": alias.replace("_", "-"),
                "version": "1.0.0",
            },
            "owner": {"type": "team", "id": "engineering"},
            "visibility": "private",
            "lifecycle": "validated",
        },
        "alias": alias,
        "instructions": "Use the exact installed route.",
        "commands": [
            {
                "name": "ask" if knowledge else "run",
                "kind": "capability" if knowledge else "workflow",
                "target": {
                    "namespace": "knowledge-query" if knowledge else "engineering",
                    "name": "ask" if knowledge else "report",
                    "version": "1.0.0",
                },
            }
        ],
        "rules": [{"pattern": "^Firmware lookup", "command": "ask"}] if knowledge else [],
    }


@pytest.mark.parametrize(
    "message",
    [
        "knowledge_evidence_candidate.ask CMX500 supported bands",
        "widget-guide Safe mode firmware",
        "Safe mode firmware",
        "Firmware lookup Safe mode",
        "/wiki-query Safe mode firmware",
    ],
)
def test_existing_web_knowledge_routes_preserve_pending_task_before_routing(
    tmp_path: Path, message: str
) -> None:
    with knowledge_runtime(
        tmp_path,
        harness_skill=True,
        harness_skill_file="knowledge-evidence-v1.2.json",
        extra_skills=(_route_skill("knowledge_rule", knowledge=True),),
    ) as runtime:
        web = AgentWeb(runtime, namespace="company-agent")
        session = web.create_conversation()["conversation"]["session_id"]
        chat = runtime.chat_authoring
        assert chat is not None
        saved = chat.tasks.save(
            runtime.actor,
            session,
            AuthoringTask(
                objective="Build a workflow",
                question=AuthoringQuestion(reason="business_decision", question="Which currency?"),
                repair_attempts=3,
                verified_digest="a" * 64,
            ),
        )
        task_file = next((chat.root / "tasks").glob("*.json"))
        before = task_file.read_bytes()
        selected = runtime.agent.gateway.router.commands.match(
            context().model_copy(update={"namespace": web.namespace, "message": message})
        )
        if message.startswith(("knowledge_evidence_candidate.", "Firmware lookup")):
            assert selected is not None and selected.decision.target is not None
            assert selected.decision.target.namespace == "knowledge-query"
        else:
            assert selected is None
        response = web.conversation_turn(
            ConversationTurnRequest(session_id=session, message=message)
        )
        assert response["ok"]
        assert task_file.read_bytes() == before
        assert chat.tasks.load(runtime.actor, session) == saved
        assert chat.tasks.messages(runtime.actor, session)[-1].text == message
        if message.startswith(("knowledge_evidence_candidate.", "Firmware lookup")):
            outcome = response["answer"]["outcome"]
            assert outcome["decision"]["target"]["namespace"] == "knowledge-query"
        else:
            assert response["answer"]["harness"]["plan"]["domain"] == "knowledge"


@pytest.mark.parametrize(
    "message", ["Use EUR", "authoring_action.run", "Run read-local-file", "/run read-local-file"]
)
def test_web_business_answers_and_nonknowledge_commands_still_reopen_tasks(
    tmp_path: Path, message: str
) -> None:
    with knowledge_runtime(
        tmp_path, extra_skills=(_route_skill("authoring_action", knowledge=False),)
    ) as runtime:
        web = AgentWeb(runtime, namespace="company-agent")
        session = web.create_conversation()["conversation"]["session_id"]
        chat = runtime.chat_authoring
        assert chat is not None
        saved = chat.tasks.save(
            runtime.actor,
            session,
            AuthoringTask(
                objective="Build a workflow",
                question=AuthoringQuestion(reason="business_decision", question="Which currency?"),
                repair_attempts=3,
            ),
        )
        if message == "Run read-local-file":
            assert web._run_form_offer(message) is not None
        response = web.conversation_turn(
            ConversationTurnRequest(session_id=session, message=message)
        )
        if message in ("Run read-local-file", "/run read-local-file"):
            assert response["answer"]["workflow_form"]
        assert chat.tasks.load(runtime.actor, session) == saved.model_copy(
            update={"question": None, "repair_attempts": 0}
        )
