"""Recoverable tool failures (owner 2026-10-20).

Live test 2026-10-20: the Agent handed `coding_workspace_missing` to the person
and asked them to create a folder by hand, after two or three tool calls of a
150-call budget. Every failed tool call now carries `recovery`
(`recoverable`, `hint`), decided by the Host from the failure code; the system
prompt tells the model to fix a recoverable call and retry in the same turn,
and to ask the person only when the failure needs them.
"""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from typing import Any

from test_gateway import Handler, gateway, request
from test_routing import FakeModel

from agent.gateway import HostTool, HostToolOutcome
from agent.tool_recovery import classify, failure_of, recovery_for
from common.execution import Failure, RequestContext
from models.contracts import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    ModelTool,
    ModelToolCall,
)


def _last_tool(item: ModelRequest) -> dict[str, Any]:
    message = item.messages[-1]
    assert message.role == "tool"
    observed: dict[str, Any] = json.loads(message.text)
    return observed


class Recovering(FakeModel):
    """Calls `tool` with `first`; on a recoverable failure retries with
    `fixed`; on a non-recoverable one asks the person; after a success
    answers. It reads only what the Host put in the observation."""

    def __init__(self, tool: str, first: dict[str, Any], fixed: dict[str, Any]) -> None:
        super().__init__()
        self.tool, self.first, self.fixed = tool, first, fixed

    def generate(self, item: ModelRequest) -> ModelResponse:
        self.calls.append(item)

        def call(arguments: dict[str, Any]) -> ModelResponse:
            return ModelResponse(
                trace=item.trace,
                model_alias=item.model_alias,
                tool_calls=(
                    ModelToolCall(
                        call_id=f"c{len(self.calls)}", name=self.tool, arguments=arguments
                    ),
                ),
            )

        if item.messages[-1].role != "tool":
            return call(self.first)
        observed = _last_tool(item)
        recovery = observed.get("recovery")
        if recovery is None:
            return ModelResponse(trace=item.trace, model_alias=item.model_alias, text="完成了。")
        if recovery["recoverable"]:
            return call(self.fixed)
        return ModelResponse(
            trace=item.trace,
            model_alias=item.model_alias,
            text="這個工具需要你的授權，請到 Capabilities 開啟後再告訴我。",
        )


def _month_tool(seen: list[dict[str, Any]]) -> HostTool:
    async def run(context: RequestContext, args: dict[str, Any]) -> HostToolOutcome:
        seen.append(dict(args))
        if not isinstance(args.get("month"), str):
            return HostToolOutcome(
                status="failed",
                failure=Failure(code="invalid_input", message="Invalid input at month: missing"),
            )
        return HostToolOutcome(status="succeeded", data={"month": args["month"]})

    return HostTool(
        ModelTool(
            name="report__make",
            description="Make the month's report.",
            input_contract="x.v1",
            input_schema={"type": "object"},
        ),
        run,
    )


def test_a_recoverable_failure_is_fixed_and_retried_in_the_same_turn() -> None:
    seen: list[dict[str, Any]] = []
    model = Recovering("report__make", {}, {"month": "2026-10"})
    built = gateway(Handler(), model)
    built.host_tools = lambda: [_month_tool(seen)]
    result = asyncio.run(
        built.converse(request("做十月報表"), (ModelMessage(role="user", text="做十月報表"),))
    )
    assert result.status == "answered" and result.text == "完成了。"
    assert seen == [{}, {"month": "2026-10"}]
    assert len(model.calls) == 3  # one turn: call, corrected call, answer
    first, second = result.tools
    assert first.recovery is not None and first.recovery.recoverable is True
    assert "month" in first.recovery.hint and "call the tool again" in first.recovery.hint
    assert second.recovery is None and second.host is not None
    assert second.host.status == "succeeded"
    # The model saw the flag and the hint, and the rule that says what to do.
    observed = json.loads(model.calls[1].messages[-1].text)
    assert observed["recovery"]["recoverable"] is True
    system = model.calls[0].messages[0].text
    assert "recovery.recoverable" in system and "same turn" in system


def test_a_bridge_invalid_input_names_the_field_and_the_corrected_call_runs() -> None:
    handler = Handler()
    model = Recovering("release__check", {"args": 5}, {"args": "v1.2"})
    built = gateway(handler, model)
    result = asyncio.run(
        built.converse(request("check the release"), (ModelMessage(role="user", text="check"),))
    )
    assert result.status == "answered" and result.text == "完成了。"
    first, second = result.tools
    assert first.capability is not None and first.capability.failure is not None
    assert first.capability.failure.code == "invalid_input"
    assert first.recovery is not None and first.recovery.recoverable is True
    assert "args" in first.recovery.hint
    assert second.recovery is None and handler.calls == 1


def test_a_failure_that_needs_the_person_leads_the_model_to_ask() -> None:
    handler = Handler()
    model = Recovering("release__check", {}, {"args": "never"})
    built = gateway(handler, model, granted=False)
    result = asyncio.run(
        built.converse(request("check the release"), (ModelMessage(role="user", text="check"),))
    )
    assert result.status == "answered" and "授權" in result.text
    (only,) = result.tools
    assert only.recovery is not None and only.recovery.recoverable is False
    assert "do not retry" in only.recovery.hint
    assert handler.calls == 0 and len(model.calls) == 2


def test_the_codes_that_need_the_person_and_the_ones_the_model_can_fix() -> None:
    def flag(code: str, message: str = "m", retryable: bool = False) -> bool | None:
        found = classify(Failure(code=code, message=message, retryable=retryable))
        return None if found is None else found.recoverable

    for code in (
        "permission_denied",
        "approval_required",
        "secret_resolution_unavailable",
        "capability_not_installed",
        "workflow_not_installed",
        "needs_connectivity",
        "mail_scope_not_allowed",
        "outlook_sign_in_required",
        "credential_missing",
    ):
        assert flag(code) is False, code
    for code in (
        "invalid_input",
        "workflow_parameters_invalid",
        "workflow_invalid",
        "uninstalled_tool",
        "coding_workspace_not_allowed",
        "coding_workspace_not_absolute",
        "coding_workspace_missing",
    ):
        assert flag(code) is True, code
    assert flag("transient_failure", retryable=True) is True
    assert flag("transient_failure") is False
    assert flag("handler_error") is False
    # G1 already says what to do with a Knowledge answer that was not validated.
    assert flag("knowledge_not_validated") is None


def test_a_workflow_tool_failure_is_read_from_its_run() -> None:
    """`coding__run` is a Workflow: its step's code sits on the run."""
    failure = Failure(code="coding_workspace_not_allowed", message="Capability did not complete")
    item = SimpleNamespace(
        failure=None,
        host=None,
        capability=None,
        workflow=SimpleNamespace(run=SimpleNamespace(status="failed", failure=failure)),
    )
    assert failure_of(item) == failure
    found = recovery_for(item)
    assert found is not None and found.recoverable is True
    assert "created for you" in found.hint
    ran = SimpleNamespace(
        failure=None,
        host=None,
        capability=None,
        workflow=SimpleNamespace(run=SimpleNamespace(status="succeeded", failure=None)),
    )
    assert recovery_for(ran) is None
