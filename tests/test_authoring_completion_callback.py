"""Persistent authoring proof is checked even when this turn called no tools."""

import asyncio
from typing import Any

import pytest
from test_gateway import _host_gateway, _text, request

from agent.delegation_scope import running_sub_run
from agent.gateway import GatewayConversationResult, HostTool, HostToolOutcome
from common.execution import RequestContext
from models.contracts import ModelTool


def _draft_tool() -> HostTool:
    async def run(context: RequestContext, args: dict[str, Any]) -> HostToolOutcome:
        return HostToolOutcome(status="succeeded")

    return HostTool(
        ModelTool(
            name="authoring__draft_workflow",
            description="Draft",
            input_contract="draft.v1",
            input_schema={},
        ),
        run,
    )


def test_persistent_unverified_task_retries_without_current_tool_calls() -> None:
    built, model = _host_gateway(
        [_draft_tool()], [_text("請自行逐頁切換完成驗證。"), _text("草稿可供使用。")]
    )
    seen: list[GatewayConversationResult] = []

    def problem(ctx: RequestContext, result: GatewayConversationResult) -> str:
        assert ctx.actor == request("Build it").actor
        seen.append(result)
        return "Current candidate has not passed its exact-digest trial. Run it yourself."

    built.authoring_completion_problem = problem
    result = asyncio.run(built.converse(request("Build it"), ()))

    assert len(model.calls) == 2
    assert len(seen) == 2 and all(not turn.tools for turn in seen)
    assert "Current candidate" in model.calls[1].messages[-1].text
    assert result.status == "needs_input"
    assert result.failure is not None and result.failure.code == "authoring_completion_unverified"
    assert "未通過" in result.text


@pytest.mark.parametrize("proof", ["verified", "pending_trial_approval"])
def test_persistent_proof_accepts_answer_without_new_tools(proof: str) -> None:
    built, model = _host_gateway([_draft_tool()], [_text("目前狀態可供審閱。")])
    seen: list[str] = []

    def problem(ctx: RequestContext, result: GatewayConversationResult) -> None:
        seen.append(proof)
        return None

    built.authoring_completion_problem = problem
    result = asyncio.run(built.converse(request("Build it"), ()))
    assert result.status == "answered" and result.failure is None
    assert len(model.calls) == 1 and seen == [proof]


def test_callback_can_resolve_on_existing_bounded_retry() -> None:
    built, model = _host_gateway(
        [_draft_tool()], [_text("目前已有草稿。"), _text("試跑結果可供審閱。")]
    )
    checks = 0

    def problem(ctx: RequestContext, result: GatewayConversationResult) -> str | None:
        nonlocal checks
        checks += 1
        return "Trial still required" if checks == 1 else None

    built.authoring_completion_problem = problem
    result = asyncio.run(built.converse(request("Build it"), ()))
    assert len(model.calls) == 2 and checks == 2
    assert result.status == "answered" and result.failure is None


def test_callback_is_not_applied_without_authoring_tools() -> None:
    built, model = _host_gateway([], [_text("一般回答。")])

    def problem(ctx: RequestContext, result: GatewayConversationResult) -> str:
        raise AssertionError("No authoring tools were offered")

    built.authoring_completion_problem = problem
    result = asyncio.run(built.converse(request("Hello"), ()))
    assert result.status == "answered" and len(model.calls) == 1


def test_legacy_gateway_with_no_completion_callback_is_unchanged() -> None:
    built, model = _host_gateway([_draft_tool()], [_text("目前已有草稿。")])
    result = asyncio.run(built.converse(request("Build it"), ()))
    assert result.status == "answered" and len(model.calls) == 1


def test_callback_is_not_applied_to_delegated_sub_run() -> None:
    built, model = _host_gateway([_draft_tool()], [_text("Sub-run findings")])

    def problem(ctx: RequestContext, result: GatewayConversationResult) -> str:
        raise AssertionError("A delegated sub-run does not own the person's authoring task")

    built.authoring_completion_problem = problem
    with running_sub_run("engineering/reviewer@1.0.0"):
        result = asyncio.run(built.converse(request("Find evidence"), ()))
    assert result.status == "answered" and len(model.calls) == 1


def test_callback_is_not_applied_when_authoring_tools_are_filtered_out() -> None:
    built, model = _host_gateway([_draft_tool()], [_text("Read-only findings")])

    def problem(ctx: RequestContext, result: GatewayConversationResult) -> str:
        raise AssertionError("Authoring was not offered")

    built.authoring_completion_problem = problem
    result = asyncio.run(built.converse(request("Find evidence"), (), allowed_tools=frozenset()))
    assert result.status == "answered" and len(model.calls) == 1
