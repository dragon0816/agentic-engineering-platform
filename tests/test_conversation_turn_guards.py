"""Owner 2026-10-19: a 150-call tool cap with guards against spinning, and the
live, content-free progress of a running turn. Fakes only."""

import asyncio
import json
from collections.abc import Callable
from typing import Any

import pytest
from pydantic import ValidationError
from test_gateway import Handler, _text, gateway, request
from test_routing import FakeModel

import agent.gateway as gateway_module
import telemetry.recorder as telemetry_recorder
from agent.backend_contracts import (
    MAX_CONVERSATION_TOOL_CALLS,
    MAX_CONVERSATION_TURNS,
    MAX_IDENTICAL_CALLS,
    MAX_IDENTICAL_FAILURES,
    ConversationLimits,
)
from agent.contracts import AgentProfile
from agent.gateway import Gateway, HostTool, HostToolOutcome
from common.execution import Failure, RequestContext, TraceIdentifiers
from models.contracts import ModelMessage, ModelRequest, ModelResponse, ModelTool, ModelToolCall

SECRET_ARGUMENT = "argument-marker-7f3"
ANSWER_TEXT = "answer-marker-c41"


def _calls(*calls: tuple[str, dict[str, Any]]) -> ModelResponse:
    return ModelResponse(
        trace=TraceIdentifiers(trace_id="x", request_id="x", span_id="x"),
        model_alias="routing",
        tool_calls=tuple(
            ModelToolCall(call_id=f"c{index}", name=name, arguments=arguments)
            for index, (name, arguments) in enumerate(calls)
        ),
    )


class Scripted(FakeModel):
    """Answers each model call with `script(call number)`."""

    def __init__(self, script: Callable[[int], ModelResponse]) -> None:
        super().__init__()
        self.script = script

    def generate(self, item: ModelRequest) -> ModelResponse:
        self.calls.append(item)
        reply = self.script(len(self.calls))
        return reply.model_copy(update={"trace": item.trace, "model_alias": item.model_alias})


def _tool(
    name: str, outcome: Callable[[dict[str, Any]], HostToolOutcome]
) -> tuple[HostTool, list[dict[str, Any]]]:
    seen: list[dict[str, Any]] = []

    async def handler(context: RequestContext, arguments: dict[str, Any]) -> HostToolOutcome:
        seen.append(arguments)
        return outcome(arguments)

    return HostTool(ModelTool(name=name, description=name, input_contract="x.v1"), handler), seen


def _failing(arguments: dict[str, Any]) -> HostToolOutcome:
    return HostToolOutcome(status="failed", failure=Failure(code="not_found", message="no"))


def _working(arguments: dict[str, Any]) -> HostToolOutcome:
    return HostToolOutcome(status="succeeded", data={"ok": True})


def _built(script: Callable[[int], ModelResponse], *tools: HostTool) -> tuple[Gateway, Scripted]:
    model = Scripted(script)
    built = gateway(Handler(), model)
    built.host_tools = lambda: list(tools)
    return built, model


def _converse(built: Gateway) -> Any:
    history = (ModelMessage(role="user", text="do the work"),)
    return asyncio.run(built.converse(request("do the work"), history))


@pytest.fixture
def stops(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """Every `turn.stopped` telemetry event's attributes."""
    seen: list[dict[str, Any]] = []
    original = telemetry_recorder.emit

    def emit(event_type: str, **kwargs: Any) -> None:
        if event_type == "turn.stopped":
            seen.append(kwargs.get("attributes") or {})
        original(event_type, **kwargs)

    monkeypatch.setattr(telemetry_recorder, "emit", emit)
    return seen


# -- the cap -------------------------------------------------------------------------


def test_the_default_cap_is_150_tool_calls_and_the_turn_budget_one_more() -> None:
    assert MAX_CONVERSATION_TOOL_CALLS == 150 and MAX_CONVERSATION_TURNS == 151
    assert ConversationLimits().tool_calls == 150
    assert ConversationLimits().time_limit_seconds == 30 * 60
    for bad in (0, 151):
        with pytest.raises(ValidationError):
            ConversationLimits(tool_calls=bad)
    # A profile may declare the whole turn budget, and no more.
    assert AgentProfile.model_fields["max_turns"].metadata
    with pytest.raises(ValidationError):
        AgentProfile.model_validate({"max_turns": MAX_CONVERSATION_TURNS + 1})


def test_the_cap_runs_150_distinct_calls_then_stops_with_tool_loop_limit(
    stops: list[dict[str, Any]],
) -> None:
    tool, seen = _tool("work__step", _working)
    built, _ = _built(lambda n: _calls(("work__step", {"n": n})), tool)
    result = _converse(built)
    assert result.status == "needs_input"
    assert result.failure is not None and result.failure.code == "tool_loop_limit"
    assert len(result.tools) == len(seen) == 150
    assert stops[-1]["stop_reason"] == "tool_loop_limit"
    assert stops[-1]["tool_calls"] == 150 and stops[-1]["tool_cap"] == 150


def test_the_host_setting_lowers_the_cap() -> None:
    tool, seen = _tool("work__step", _working)
    built, _ = _built(lambda n: _calls(("work__step", {"n": n})), tool)
    built.conversation_limits = lambda: ConversationLimits(tool_calls=7)
    result = _converse(built)
    assert result.failure is not None and result.failure.code == "tool_loop_limit"
    assert len(result.tools) == len(seen) == 7


def test_an_unreadable_host_setting_keeps_the_defaults() -> None:
    def broken() -> ConversationLimits:
        raise OSError("unreadable")

    tool, seen = _tool("work__step", _working)
    built, _ = _built(lambda n: _calls(("work__step", {"n": n})) if n < 4 else _text("done"), tool)
    built.conversation_limits = broken
    result = _converse(built)
    assert result.status == "answered" and len(seen) == 3


# -- the repetition guard ----------------------------------------------------------------


def test_three_identical_failures_in_a_row_stop_the_turn(stops: list[dict[str, Any]]) -> None:
    tool, seen = _tool("files__read", _failing)
    built, model = _built(lambda n: _calls(("files__read", {"path": SECRET_ARGUMENT})), tool)
    result = _converse(built)
    assert result.status == "needs_input"
    assert result.failure is not None and result.failure.code == "tool_repeat_limit"
    assert len(seen) == MAX_IDENTICAL_FAILURES == 3
    assert len(model.calls) == 3
    (stopped,) = stops
    assert stopped["stop_reason"] == "tool_repeat_limit"
    assert stopped["repeat_kind"] == "identical_failures" and stopped["repeats"] == 3
    assert stopped["tool_id"] == "files__read" and stopped["tool_calls"] == 3
    # Counts and names only: never the arguments.
    assert SECRET_ARGUMENT not in json.dumps(stopped)


def test_failures_with_differing_arguments_are_not_a_repeat() -> None:
    tool, seen = _tool("files__read", _failing)
    built, _ = _built(
        lambda n: _calls(("files__read", {"path": f"file-{n}"})) if n <= 4 else _text("gave up"),
        tool,
    )
    result = _converse(built)
    assert result.status == "answered" and len(seen) == 4


def test_a_success_between_identical_failures_resets_the_streak() -> None:
    tool, seen = _tool("files__read", _failing)
    other, _ = _tool("files__list", _working)
    plan = [
        ("files__read", {"path": "a"}),
        ("files__read", {"path": "a"}),
        ("files__list", {}),
        ("files__read", {"path": "a"}),
    ]
    built, _ = _built(lambda n: _calls(plan[n - 1]) if n <= len(plan) else _text("ok"), tool, other)
    result = _converse(built)
    assert result.status == "answered" and len(seen) == 3


def test_an_identical_successful_call_runs_at_most_five_times(
    stops: list[dict[str, Any]],
) -> None:
    tool, seen = _tool("window__look", _working)
    built, _ = _built(lambda n: _calls(("window__look", {"app": "erp"})), tool)
    result = _converse(built)
    assert result.failure is not None and result.failure.code == "tool_repeat_limit"
    assert len(seen) == MAX_IDENTICAL_CALLS == 5
    assert stops[-1]["repeat_kind"] == "identical_calls" and stops[-1]["repeats"] == 5


def test_a_fix_and_rerun_cycle_is_not_a_repeat() -> None:
    """A Workflow run with the same arguments after each revised draft is
    progress: the new draft is a call never made before in the turn."""
    run, runs = _tool("authoring__run_workflow", _failing)
    draft, _ = _tool("authoring__draft_workflow", _working)

    def script(n: int) -> ModelResponse:
        if n > 16:
            return _text("fixed")
        if n % 2:
            return _calls(("authoring__run_workflow", {"name": "report"}))
        return _calls(("authoring__draft_workflow", {"name": "report", "script": f"v{n}"}))

    built, _ = _built(script, run, draft)
    result = _converse(built)
    assert result.status == "answered" and len(runs) == 8


def test_several_calls_in_one_reply_count_each() -> None:
    tool, seen = _tool("window__look", _working)
    built, _ = _built(lambda n: _calls(*[("window__look", {"app": "erp"})] * 7), tool)
    result = _converse(built)
    assert result.failure is not None and result.failure.code == "tool_repeat_limit"
    assert len(seen) == 5


# -- the time budget ---------------------------------------------------------------------


class FakeClock:
    def __init__(self) -> None:
        self.now = 1_000.0

    def __call__(self) -> float:
        return self.now


def test_the_turn_stops_at_its_time_budget(stops: list[dict[str, Any]]) -> None:
    clock = FakeClock()

    def slow(arguments: dict[str, Any]) -> HostToolOutcome:
        clock.now += 10 * 60  # each step takes ten minutes
        return HostToolOutcome(status="succeeded", data={"ok": True})

    tool, seen = _tool("work__step", slow)
    built, _ = _built(lambda n: _calls(("work__step", {"n": n})), tool)
    built.clock = clock
    result = _converse(built)
    assert result.status == "needs_input"
    assert result.failure is not None and result.failure.code == "turn_time_limit"
    assert len(seen) == 3  # 30 minutes are used up after the third step
    assert stops[-1]["stop_reason"] == "turn_time_limit"
    assert stops[-1]["time_limit_s"] == 1800 and stops[-1]["elapsed_s"] == 1800


def test_the_time_budget_is_configurable() -> None:
    clock = FakeClock()

    def slow(arguments: dict[str, Any]) -> HostToolOutcome:
        clock.now += 61
        return HostToolOutcome(status="succeeded", data={"ok": True})

    tool, seen = _tool("work__step", slow)
    built, _ = _built(lambda n: _calls(("work__step", {"n": n})), tool)
    built.clock = clock
    built.conversation_limits = lambda: ConversationLimits(time_limit_seconds=120)
    result = _converse(built)
    assert result.failure is not None and result.failure.code == "turn_time_limit"
    assert len(seen) == 2


def test_a_quick_turn_is_not_affected_by_the_guards() -> None:
    tool, seen = _tool("work__step", _working)
    built, _ = _built(lambda n: _calls(("work__step", {"n": 1})) if n == 1 else _text("done"), tool)
    result = _converse(built)
    assert result.status == "answered" and result.text.startswith("done") and len(seen) == 1


# -- context growth ----------------------------------------------------------------------


def test_old_tool_results_are_compacted_to_keep_the_turn_in_context() -> None:
    big = "x" * 15_000

    def large(arguments: dict[str, Any]) -> HostToolOutcome:
        return HostToolOutcome(status="succeeded", data={"text": big})

    tool, _ = _tool("files__read", large)
    built, model = _built(
        lambda n: _calls(("files__read", {"path": f"f{n}"})) if n <= 30 else _text("done"), tool
    )
    result = _converse(built)
    assert result.status == "answered"
    last = model.calls[-1].messages
    observations = [message.text for message in last if message.role == "tool"]
    assert len(observations) == 30
    assert sum(len(text) for text in observations) <= (
        gateway_module.MAX_TURN_OBSERVATION_CHARS + 30 * 400
    )
    assert json.loads(observations[0])["compacted"] is True
    assert big in observations[-1]
