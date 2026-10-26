"""Multi-agent V1 core delegation (`agent__delegate`, ADR-MA1–MA5, owner Gate 0
2026-10-26). Fakes only: scripted models, fixture capabilities, no real model,
Bridge hardware or Agent Web restart."""

from __future__ import annotations

import asyncio
import json
import threading
import time
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from test_agent_profile_marketplace import configured
from test_agent_web import base, fetch, served  # noqa: F401 - the server fixture
from test_gateway import Handler, capability_spec, gateway
from test_host_wiring import BRIDGE, ready
from test_routing import FakeModel
from test_turn_effects import WRITE, _built

import telemetry.recorder as telemetry
from agent import delegation_scope, turn_progress
from agent.contracts import AgentProfile
from agent.conversation_harness import NOTE_MARK
from agent.delegation import (
    DelegationCatalog,
    DelegationResult,
    DelegationService,
    DelegationTarget,
)
from agent.delegation_scope import DELEGATE_TOOL, running_sub_run
from agent.gateway import Gateway, GatewayConversationResult, TurnMemory
from agent.harness_handoff import UNVERIFIED_NOTE
from common.assets import AssetIdentity
from common.authorization import DeviceAssetSelection, DeviceAuthorization
from common.execution import Failure, RequestContext, TraceIdentifiers
from host_runtime import agent_mode, mcp_server
from host_runtime.host import build_runtime, delegation_catalog
from host_runtime.profiles import ProfileError, delegation_target, validate_profile
from host_runtime.session_artifacts import SessionArtifacts
from host_runtime.web import AgentWebServer
from models.approved import _observed
from models.contracts import ModelMessage, ModelRequest, ModelResponse, ModelToolCall
from telemetry.store import TelemetryStore

RELEASE_SKILL = AssetIdentity(
    namespace="engineering", name="release-workflow-skill", version="1.0.0"
)
NOTES_SKILL = AssetIdentity(namespace="engineering", name="notes-skill", version="1.0.0")
VALIDATE = capability_spec().identity
WRITE_ID = AssetIdentity.model_validate(WRITE)
SESSION = "conversation-1"
SUB_MARK = "delegated specialist sub-agent"


# -- fixtures --------------------------------------------------------------


def agent_profile(
    name: str = "researcher",
    *,
    skills: tuple[AssetIdentity, ...] = (RELEASE_SKILL,),
    capabilities: tuple[AssetIdentity, ...] = (VALIDATE,),
    **changes: Any,
) -> AgentProfile:
    values: dict[str, Any] = {
        "metadata": {
            "identity": {"namespace": "engineering", "name": name, "version": "1.0.0"},
            "owner": {"type": "team", "id": "engineering"},
            "visibility": "team",
            "lifecycle": "published",
        },
        "description": f"The {name} specialist.",
        "skills": [item.model_dump() for item in skills],
        "allowed_capabilities": [item.model_dump() for item in capabilities],
        "selector_hint": f"Use {name} for checks.",
    }
    values.update(changes)
    return AgentProfile.model_validate(values)


def reply(*calls: tuple[str, dict[str, Any]], text: str = "") -> ModelResponse:
    return ModelResponse(
        trace=TraceIdentifiers(trace_id="x", request_id="x", span_id="x"),
        model_alias="routing",
        text=text,
        tool_calls=tuple(
            ModelToolCall(call_id=f"c{index}", name=name, arguments=arguments)
            for index, (name, arguments) in enumerate(calls)
        ),
    )


def delegate(
    objective: str,
    profile: str = "engineering/researcher",
    tools: list[str] | None = None,
    **extra: Any,
) -> Any:
    """A delegation call; to the researcher it asks for the read tool only
    (its Skill also has a Workflow, which is never read-only)."""
    if tools is None and profile == "engineering/researcher":
        tools = ["release__check"]
    narrowed = {"tools": tools} if tools else {}
    return (DELEGATE_TOOL, {"profile": profile, "objective": objective, **narrowed, **extra})


class Routed(FakeModel):
    """Answers each conversation from its own script: the parent turn, and each
    sub-run keyed by its objective. Thread-safe (sub-runs may run together)."""

    def __init__(
        self,
        scripts: dict[str, list[ModelResponse]],
        hook: Callable[[str, int], None] | None = None,
    ) -> None:
        super().__init__()
        self.scripts = scripts
        self.hook = hook
        self.lock = threading.Lock()
        self.seen: dict[str, int] = {}
        self.by_key: dict[str, list[ModelRequest]] = {}

    @staticmethod
    def key(item: ModelRequest) -> str:
        if SUB_MARK not in item.messages[0].text:
            return "parent"
        first = next(message for message in item.messages if message.role == "user")
        return first.text.split("\n\n", 1)[0]

    def generate(self, item: ModelRequest) -> ModelResponse:
        key = self.key(item)
        with self.lock:
            self.calls.append(item)
            self.by_key.setdefault(key, []).append(item)
            index = self.seen.get(key, 0)
            self.seen[key] = index + 1
        if self.hook is not None:
            self.hook(key, index)
        script = self.scripts[key]
        answer = script[min(index, len(script) - 1)]
        return answer.model_copy(update={"trace": item.trace, "model_alias": item.model_alias})


def parent_request(message: str = "please check the release", **changes: Any) -> RequestContext:
    values: dict[str, Any] = {
        "trace": TraceIdentifiers(trace_id="trace-1", request_id="request-1", span_id="span-1"),
        "actor": "engineer",
        "namespace": "engineering",
        "channel": "test",
        "message": message,
        "session_id": SESSION,
    }
    values.update(changes)
    return RequestContext(**values)


def wired(
    scripts: dict[str, list[ModelResponse]],
    targets: tuple[AgentProfile, ...] = (),
    *,
    enabled: bool = True,
    owner_mode: bool = False,
    listed: bool = True,
    ledger: Any = None,
    hook: Callable[[str, int], None] | None = None,
) -> tuple[Gateway, Routed, Any, DelegationService]:
    """The release fixture (read capability, Workflow) and the notes write
    capability, a routed model and the delegation service as the Host tools."""
    built, _, write, _ = _built([], owner_mode=owner_mode)
    model = Routed(scripts, hook)
    built.router.model = model
    service = DelegationService(
        built,
        enabled=lambda: enabled,
        catalog=lambda: DelegationCatalog(
            targets=tuple(DelegationTarget(profile=item, listed=listed) for item in targets)
        ),
        ledger=ledger,
    )
    built.host_tools = service.tools
    return built, model, write, service


def converse(
    built: Gateway,
    message: str = "please check the release",
    *,
    history: tuple[ModelMessage, ...] = (),
    **changes: Any,
) -> GatewayConversationResult:
    context = parent_request(message, **changes)
    return asyncio.run(built.converse(context, (*history, ModelMessage(role="user", text=message))))


def delegated(item: Any) -> DelegationResult:
    assert item.host is not None and isinstance(item.host.data, dict)
    return DelegationResult.model_validate(item.host.data["delegation"])


def tool_names(request: ModelRequest) -> set[str]:
    return {tool.name for tool in request.tools}


# -- the flag --------------------------------------------------------------


def test_with_the_flag_off_there_is_no_tool_and_the_turn_is_unchanged() -> None:
    scripts = {"parent": [reply(("release__check", {})), reply(text="檢查完成，結果正常。")]}
    off, off_model, _, service = wired(scripts, (agent_profile(),), enabled=False)
    assert service.tools() == ()
    plain, plain_model, _, _ = wired(scripts, (agent_profile(),))
    plain.host_tools = None  # the Host before multi-agent
    with_flag_off = converse(off)
    before = converse(plain)
    assert DELEGATE_TOOL not in tool_names(off_model.calls[0])
    assert [tool_names(item) for item in off_model.calls] == [
        tool_names(item) for item in plain_model.calls
    ]
    assert [item.messages[0].text for item in off_model.calls] == [
        item.messages[0].text for item in plain_model.calls
    ]
    assert with_flag_off.text == before.text and with_flag_off.status == before.status
    assert [item.name for item in with_flag_off.tools] == ["release__check"]


def test_a_direct_call_with_the_flag_off_is_refused_and_runs_nothing() -> None:
    built, model, _, service = wired({"parent": [reply(text="x")]}, (agent_profile(),))
    service.enabled = lambda: False
    outcome = asyncio.run(
        service._handle(parent_request(), {"profile": "engineering/researcher", "objective": "x"})
    )
    assert outcome.status == "failed" and outcome.failure is not None
    assert outcome.failure.code == "delegation_disabled"
    assert model.calls == []


# -- offered to the parent only --------------------------------------------------------------


def test_the_tool_is_offered_to_the_parent_with_targets_and_never_to_a_sub_agent() -> None:
    scripts = {
        "parent": [reply(delegate("check the release")), reply(text="子代理的結果如上。")],
        "check the release": [reply(("release__check", {})), reply(text="摘要\n- release ok")],
    }
    built, model, _, _ = wired(scripts, (agent_profile(),))
    result = converse(built)
    assert result.status == "answered"
    parent = model.by_key["parent"][0]
    assert DELEGATE_TOOL in tool_names(parent)
    tool = next(item for item in parent.tools if item.name == DELEGATE_TOOL)
    assert "engineering/researcher@1.0.0: The researcher specialist." in tool.description
    assert "Use researcher for checks." in tool.description
    for sub in model.by_key["check the release"]:
        assert DELEGATE_TOOL not in tool_names(sub)
        assert tool_names(sub) == {"release__check"}
    found = delegated(result.tools[0])
    assert found.status == "succeeded" and found.validated
    assert found.findings == ("release ok",)
    assert [call.name for call in found.tool_calls] == ["release__check"]


def test_no_target_means_no_tool() -> None:
    built, model, _, service = wired({"parent": [reply(text="好的。")]}, ())
    assert service.tools() == ()
    converse(built)
    assert DELEGATE_TOOL not in tool_names(model.calls[0])


def test_a_sub_agent_cannot_delegate_further() -> None:
    built, model, _, service = wired({"parent": [reply(text="x")]}, (agent_profile(),))

    async def inside() -> Any:
        with running_sub_run("engineering/researcher@1.0.0"):
            assert service.tools() == ()
            return await service._handle(
                parent_request(), {"profile": "engineering/researcher", "objective": "deeper"}
            )

    outcome = asyncio.run(inside())
    assert outcome.failure is not None and outcome.failure.code == "delegation_depth_exceeded"
    assert model.calls == []


# -- targets --------------------------------------------------------------


def test_an_unlisted_target_needs_the_person_to_name_it() -> None:
    scripts = {
        "parent": [reply(delegate("look")), reply(text="無法委派。")],
        "look": [reply(text="摘要")],
    }
    built, model, _, _ = wired(scripts, (agent_profile(),), listed=False)
    result = converse(built, "幫我檢查 release")
    refused = result.tools[0]
    assert refused.host is not None and refused.host.failure is not None
    assert refused.host.failure.code == "delegation_target_not_allowed"
    assert "look" not in model.by_key
    built, model, _, _ = wired(scripts, (agent_profile(),), listed=False)
    named = converse(built, "請用 researcher 幫我檢查 release")
    assert delegated(named.tools[0]).status == "succeeded"
    assert "look" in model.by_key


def test_unknown_ambiguous_and_malformed_targets_are_refused() -> None:
    other = agent_profile().model_copy(
        update={
            "metadata": agent_profile().metadata.model_copy(
                update={
                    "identity": AssetIdentity(
                        namespace="engineering", name="researcher", version="2.0.0"
                    )
                }
            )
        }
    )
    _, _, _, service = wired({"parent": [reply(text="x")]}, (agent_profile(), other))
    for reference, code in (
        ("engineering/nobody", "delegation_target_not_allowed"),
        ("engineering/researcher", "delegation_profile_ambiguous"),
        ("not a profile", "delegation_arguments_invalid"),
    ):
        outcome = asyncio.run(
            service._handle(parent_request(), {"profile": reference, "objective": "x"})
        )
        assert outcome.failure is not None and outcome.failure.code == code
    exact = asyncio.run(
        service._handle(
            parent_request(), {"profile": "engineering/researcher@3.0.0", "objective": "x"}
        )
    )
    assert exact.failure is not None and exact.failure.code == "delegation_target_not_allowed"


# -- the permission intersection --------------------------------------------------------------


def test_effective_tools_never_exceed_the_parent_or_the_profile() -> None:
    _, _, _, service = wired({"parent": [reply(text="x")]}, ())
    context = parent_request()
    # The profile allows the read (and the Workflow made of it): the parent's
    # write is not offered; a Workflow is never read-only.
    assert service._effective(context, agent_profile(), None) == (
        ("release__package", "release__check"),
        False,
    )
    assert service._effective(context, agent_profile(), ("release__check",)) == (
        ("release__check",),
        True,
    )
    # The profile names the notes write: only it (and it is not read-only).
    writer = agent_profile("writer", skills=(NOTES_SKILL,), capabilities=(WRITE_ID,))
    assert service._effective(context, writer, None) == (("notes__publish",), False)
    # A requested subset narrows and never widens.
    assert service._effective(context, agent_profile(), ("notes__publish",)) == ((), True)
    assert service._effective(context, agent_profile(), ("release__check", "x__y")) == (
        ("release__check",),
        True,
    )
    # A Skill the profile names without its capability gives nothing.
    assert service._effective(context, agent_profile(capabilities=()), None) == ((), True)


def test_a_tool_the_parent_actor_is_not_granted_is_not_offered_to_the_sub_agent() -> None:
    read = Handler()
    model = Routed(
        {
            "parent": [reply(delegate("check it")), reply(text="完成。")],
            "check it": [reply(("release__check", {})), reply(text="沒有工具可用。")],
        }
    )
    built = gateway(read, model, granted=False)
    service = DelegationService(
        built,
        enabled=lambda: True,
        catalog=lambda: DelegationCatalog(
            targets=(DelegationTarget(profile=agent_profile(), listed=True),)
        ),
    )
    built.host_tools = service.tools
    result = converse(built)
    assert tool_names(model.by_key["check it"][0]) == set()
    assert read.calls == 0
    found = delegated(result.tools[0])
    assert [(call.name, call.status) for call in found.tool_calls] == [("release__check", "failed")]


def test_a_sub_agent_cannot_call_a_tool_outside_its_set() -> None:
    scripts = {
        "parent": [reply(delegate("just read")), reply(text="好。")],
        "just read": [reply(("notes__publish", {"note": "x"})), reply(text="我沒辦法寫。")],
    }
    built, _, write, _ = wired(scripts, (agent_profile(),))
    result = converse(built)
    assert write.calls == 0
    found = delegated(result.tools[0])
    assert found.tool_calls[0].status == "failed"


# -- limits --------------------------------------------------------------


def test_at_most_three_sub_agents_per_turn() -> None:
    objectives = ["one", "two", "three", "four"]
    scripts: dict[str, list[ModelResponse]] = {
        "parent": [reply(*(delegate(item) for item in objectives)), reply(text="合併結果。")],
        **{item: [reply(text=f"摘要 {item}")] for item in objectives},
    }
    built, model, _, _ = wired(scripts, (agent_profile(),))
    result = converse(built)
    statuses = [delegated(item).status for item in result.tools]
    assert statuses.count("succeeded") == 3 and statuses.count("failed") == 1
    refused = next(item for item in result.tools if delegated(item).status == "failed")
    assert refused.host is not None and refused.host.failure is not None
    assert refused.host.failure.code == "delegation_limit_reached"
    assert sum(1 for key in model.by_key if key != "parent") == 3


def test_the_profile_turn_limit_applies_to_the_sub_run() -> None:
    scripts = {
        "parent": [reply(delegate("loop")), reply(text="子代理沒有完成。")],
        "loop": [reply(("release__check", {"args": "again"}))],
    }
    built, model, _, _ = wired(scripts, (agent_profile(max_turns=2, max_tool_calls=20),))
    result = converse(built)
    found = delegated(result.tools[0])
    assert found.status == "failed" and found.failure is not None
    assert found.failure.code == "tool_loop_limit"
    # Two model turns per pass; a stop is not retried by the conversation check.
    assert len(model.by_key["loop"]) == 2


def test_the_time_limit_stops_a_sub_run() -> None:
    release = threading.Event()

    def hook(key: str, index: int) -> None:
        if key == "slow":
            release.wait(10)
        if key == "parent" and index == 1:
            release.set()

    scripts = {
        "parent": [reply(delegate("slow")), reply(text="子代理逾時。")],
        "slow": [reply(text="太晚了")],
    }
    built, _, _, _ = wired(scripts, (agent_profile(time_limit_s=1),), hook=hook)
    started = time.monotonic()
    try:
        result = converse(built)
    finally:
        release.set()
    assert time.monotonic() - started < 8
    found = delegated(result.tools[0])
    assert found.status == "failed" and found.failure is not None
    assert found.failure.code == "delegation_time_limit"
    assert result.status == "answered"


# -- context, questions, writes --------------------------------------------------------------


def test_the_sub_agent_sees_only_the_objective_not_the_parent_context() -> None:
    scripts = {
        "parent": [reply(delegate("summarize the release state")), reply(text="好。")],
        "summarize the release state": [reply(text="摘要")],
    }
    built, model, _, _ = wired(scripts, (agent_profile(),))
    built.session_context = lambda _context: "SESSION-LIST of produced files"
    built.turn_memory = lambda _context, _skills: TurnMemory(guidance="MEMORY-GUIDANCE")
    history = (
        ModelMessage(role="user", text="PARENT-SECRET earlier question"),
        ModelMessage(role="assistant", text="PARENT-SECRET earlier answer"),
    )
    context = parent_request("now delegate it")
    asyncio.run(
        built.converse(
            context,
            (*history, ModelMessage(role="user", text="now delegate it")),
            persona_guidance="PERSONA-X",
        )
    )
    parent_text = json.dumps([item.text for item in model.by_key["parent"][0].messages])
    assert "PARENT-SECRET" in parent_text and "SESSION-LIST" in parent_text
    assert "MEMORY-GUIDANCE" in parent_text and "PERSONA-X" in parent_text
    sub = model.by_key["summarize the release state"][0]
    assert [message.role for message in sub.messages] == ["system", "user"]
    assert sub.messages[1].text == "summarize the release state"
    sub_text = json.dumps([item.text for item in sub.messages])
    for leaked in ("PARENT-SECRET", "SESSION-LIST", "MEMORY-GUIDANCE", "PERSONA-X"):
        assert leaked not in sub_text


def test_a_sub_agent_returns_needs_input_instead_of_asking() -> None:
    scripts = {
        "parent": [reply(delegate("weekly numbers")), reply(text="請問要查哪一季？")],
        "weekly numbers": [reply(text="NEEDS_INPUT: 要查哪一季？")],
    }
    built, model, _, _ = wired(scripts, (agent_profile(),))
    result = converse(built)
    item = result.tools[0]
    found = delegated(item)
    assert found.status == "needs_input" and found.question == "要查哪一季？"
    assert item.host is not None and item.host.status == "failed"
    assert item.host.failure is not None and item.host.failure.code == "delegation_needs_input"
    # The person hears it from the parent, which got the question.
    observed = [m.text for m in model.by_key["parent"][1].messages if m.role == "tool"]
    assert "要查哪一季" in observed[0]
    assert result.text == "請問要查哪一季？"
    # The sub-agent was told never to ask the person.
    assert "Never ask the person" in model.by_key["weekly numbers"][0].messages[0].text


def test_a_sub_agent_write_still_waits_for_the_person() -> None:
    writer = agent_profile("writer", skills=(NOTES_SKILL,), capabilities=(WRITE_ID,))
    scripts = {
        "parent": [
            reply(delegate("publish the note", "engineering/writer")),
            reply(text="這個寫入等你按核准。"),
        ],
        "publish the note": [
            reply(("notes__publish", {"note": "weekly"})),
            reply(text="寫入等待核准。"),
        ],
    }
    built, _, write, _ = wired(scripts, (writer,), owner_mode=True)
    asked: list[tuple[str | None, AssetIdentity]] = []

    def approval(context: RequestContext, target: AssetIdentity, arguments: Any) -> Any:
        asked.append((context.session_id, target))
        return {"approval_id": "ap-1", "summary": "publish", "next": "wait"}

    built.capability_approval = approval
    result = converse(built)
    assert write.calls == 0
    assert asked == [(SESSION, WRITE_ID)]  # the card lands in the parent's conversation
    item = result.tools[0]
    assert item.host is not None and item.host.status == "awaiting_approval"
    found = delegated(item)
    assert found.status == "awaiting_approval" and found.approvals == ("ap-1",)
    assert found.read_only is False


def test_a_side_effect_happens_once_across_the_parent_and_its_sub_run() -> None:
    writer = agent_profile("writer", skills=(NOTES_SKILL,), capabilities=(WRITE_ID,))
    scripts = {
        "parent": [
            reply(("notes__publish", {"note": "weekly"})),
            reply(delegate("publish it again", "engineering/writer")),
            reply(text="筆記已發布一次。"),
        ],
        "publish it again": [
            reply(("notes__publish", {"note": "weekly"})),
            reply(text="這則筆記本回合已發布。"),
        ],
    }
    built, _, write, _ = wired(scripts, (writer,))
    result = converse(built)
    assert write.calls == 1
    found = delegated(result.tools[1])
    assert [(call.name, call.status, call.replayed) for call in found.tool_calls] == [
        ("notes__publish", "succeeded", True)
    ]


# -- parallelism --------------------------------------------------------------


def test_read_only_sub_agents_run_concurrently() -> None:
    gate = threading.Barrier(2, timeout=5)

    def hook(key: str, index: int) -> None:
        if key in ("alpha", "beta") and index == 0:
            gate.wait()  # passes only when both sub-runs are inside the model at once

    scripts = {
        "parent": [reply(delegate("alpha"), delegate("beta")), reply(text="兩個都好了。")],
        "alpha": [reply(text="摘要 alpha")],
        "beta": [reply(text="摘要 beta")],
    }
    built, _, _, _ = wired(scripts, (agent_profile(),), hook=hook)
    result = converse(built)
    assert [delegated(item).status for item in result.tools] == ["succeeded", "succeeded"]
    assert [item.call_id for item in result.tools] == ["c0", "c1"]  # call order kept
    assert [delegated(item).summary for item in result.tools] == ["摘要 alpha", "摘要 beta"]


def test_a_write_capable_sub_agent_runs_alone() -> None:
    gate = threading.Barrier(2, timeout=5)
    events: list[tuple[str, str]] = []
    lock = threading.Lock()

    def hook(key: str, index: int) -> None:
        if key == "parent" or index:
            return
        with lock:
            events.append(("start", key))
        if key in ("alpha", "beta"):
            gate.wait()
        time.sleep(0.2)
        with lock:
            events.append(("end", key))

    writer = agent_profile("writer", skills=(NOTES_SKILL,), capabilities=(WRITE_ID,))
    scripts = {
        "parent": [
            reply(
                delegate("alpha"),
                delegate("write", "engineering/writer"),
                delegate("beta"),
            ),
            reply(text="完成。"),
        ],
        "alpha": [reply(text="摘要 alpha")],
        "beta": [reply(text="摘要 beta")],
        "write": [reply(text="不需要寫。")],
    }
    built, _, _, service = wired(scripts, (agent_profile(), writer), hook=hook)
    assert service._parallel(parent_request(), delegate("a")[1])
    assert not service._parallel(parent_request(), delegate("a", tools=["release__package"])[1])
    assert not service._parallel(
        parent_request(), {"profile": "engineering/writer", "objective": "w"}
    )
    result = converse(built)
    assert [delegated(item).status for item in result.tools] == ["succeeded"] * 3
    write_start = events.index(("start", "write"))
    assert write_start > events.index(("end", "alpha"))
    assert write_start > events.index(("end", "beta"))
    assert events[-1] == ("end", "write")


# -- Harness checks on results --------------------------------------------------------------


def test_an_unbacked_claim_by_a_sub_agent_is_marked_and_kept_through_the_parent() -> None:
    scripts = {
        "parent": [reply(delegate("do it")), reply(text="以下是子代理的回報。")],
        "do it": [reply(text="我已經執行完成。")],
    }
    built, model, _, _ = wired(scripts, (agent_profile(),))
    result = converse(built)
    # The sub-run's claim check retried once, then kept the Host's note.
    assert len(model.by_key["do it"]) == 2
    found = delegated(result.tools[0])
    assert found.status == "succeeded" and not found.validated
    assert NOTE_MARK in found.summary and found.summary.startswith("我已經執行完成。")
    assert found.host_note is not None and found.host_note.startswith(NOTE_MARK)
    data = result.tools[0].host.data  # type: ignore[union-attr]
    assert isinstance(data, dict) and data["delegation_verdict"] == "not_validated"
    # G1: the parent's own answer carries the Host's note naming the delegation.
    assert UNVERIFIED_NOTE.strip() in result.text and DELEGATE_TOOL in result.text


def test_a_later_success_of_another_delegation_does_not_clear_the_note() -> None:
    scripts = {
        "parent": [reply(delegate("claim"), delegate("honest")), reply(text="兩份回報。")],
        "claim": [reply(text="我已經執行完成。")],
        "honest": [reply(text="摘要：沒有發現問題。")],
    }
    built, _, _, _ = wired(scripts, (agent_profile(),))
    result = converse(built)
    assert UNVERIFIED_NOTE.strip() in result.text


def test_a_failed_sub_run_is_reported_failed_and_cut_output_says_so() -> None:
    long_answer = "摘要\n" + "x" * 9_000
    scripts = {
        "parent": [reply(delegate("long")), reply(delegate("broken")), reply(text="好。")],
        "long": [reply(text=long_answer)],
        "broken": [
            ModelResponse(
                trace=TraceIdentifiers(trace_id="x", request_id="x", span_id="x"),
                model_alias="routing",
                failure=Failure(code="provider_error", message="down"),
            )
        ],
    }
    built, _, _, _ = wired(scripts, (agent_profile(),))
    result = converse(built)
    cut = delegated(result.tools[0])
    assert cut.status == "succeeded" and "已在此截斷" in cut.summary
    assert len(cut.summary) < 8_300
    broken = result.tools[1]
    assert broken.host is not None and broken.host.status == "failed"
    assert delegated(broken).failure is not None


# -- the parent ledger --------------------------------------------------------------


def test_sub_agent_runs_land_in_the_parent_session_ledger(tmp_path: Path) -> None:
    ledger = SessionArtifacts(tmp_path)
    scripts = {
        "parent": [reply(delegate("package the release")), reply(text="已交給子代理。")],
        "package the release": [reply(("release__package", {})), reply(text="摘要")],
    }
    scripts["parent"][0] = reply(delegate("package the release", tools=["release__package"]))
    built, _, _, _ = wired(scripts, (agent_profile(),), ledger=ledger)
    result = converse(built)
    found = delegated(result.tools[0])
    assert found.read_only is False  # a Workflow is never read-only
    runs = ledger.ledger(SESSION, "engineer").runs
    assert len(runs) == 1 and runs[0].workflow == "release-validation"
    assert [(item.kind, item.id) for item in found.artifacts] == [("run", runs[0].run_id)]
    # Another person's (or session's) ledger is untouched.
    assert ledger.ledger(SESSION, "someone-else").runs == ()


def test_input_artifacts_reach_the_sub_agent_by_name_and_unknown_ids_are_refused(
    tmp_path: Path,
) -> None:
    ledger = SessionArtifacts(tmp_path)
    notes = tmp_path / "notes.md"
    notes.write_text("ARTIFACT-CONTENT line", encoding="utf-8")
    [artifact_id] = ledger.record_files(SESSION, "engineer", [{"path": str(notes)}])
    scripts = {
        "parent": [
            reply(delegate("read the notes", input_artifact_ids=[artifact_id])),
            reply(delegate("read more", input_artifact_ids=["f99"])),
            reply(text="好。"),
        ],
        "read the notes": [reply(text="摘要")],
        "read more": [reply(text="摘要")],
    }
    built, model, _, _ = wired(scripts, (agent_profile(),), ledger=ledger)
    result = converse(built)
    text = model.by_key["read the notes"][0].messages[1].text
    assert "ARTIFACT-CONTENT" in text and "notes.md" in text and str(tmp_path) not in text
    refused = result.tools[1]
    assert refused.host is not None and refused.host.failure is not None
    assert refused.host.failure.code == "delegation_artifact_unknown"
    assert "read more" not in model.by_key


# -- telemetry --------------------------------------------------------------


class Observed:
    """The scripted model behind the Host's `llm.completed` hook, with usage."""

    def __init__(self, inner: Routed) -> None:
        self.inner = inner

    def generate(self, item: ModelRequest) -> ModelResponse:
        answer = self.inner.generate(item).model_copy(
            update={"input_tokens": 120, "output_tokens": 30}
        )
        _observed(item, answer, 5.0)
        return answer

    def stream(self, item: ModelRequest) -> Iterator[Any]:
        raise AssertionError("not streamed")


@pytest.fixture
def store(tmp_path: Path) -> Iterator[TelemetryStore]:
    telemetry.reset()
    item = TelemetryStore(tmp_path / "telemetry.sqlite")
    telemetry.configure(item, {"build": "test", "strategy_label": None})
    yield item
    telemetry.reset()
    item.close()


def test_a_delegation_is_its_own_run_linked_to_the_parent_with_counts(
    store: TelemetryStore,
) -> None:
    scripts = {
        "parent": [reply(delegate("OBJECTIVE-TEXT-42")), reply(text="好。")],
        "OBJECTIVE-TEXT-42": [reply(("release__check", {})), reply(text="ANSWER-TEXT-42")],
    }
    built, model, _, _ = wired(scripts, (agent_profile(),))
    built.router.model = Observed(model)
    result = converse(built)
    found = delegated(result.tools[0])
    assert found.tokens.model_calls == 2
    assert (found.tokens.input, found.tokens.output) == (240, 60)
    recorder = telemetry.recorder()
    assert recorder is not None
    recorder.flush()
    [parent] = store.runs(kind="conversation_turn")
    [child] = store.runs(kind="agent_delegation")
    assert child["parent_run_id"] == parent["run_id"]
    events = store.events_after(0, limit=5000)
    completed = next(
        event
        for event in events
        if event["run_id"] == child["run_id"] and event["event_type"] == "run.completed"
    )
    attributes = completed["attributes"]
    assert attributes["agent"] == "engineering/researcher@1.0.0"
    assert attributes["delegation_status"] == "succeeded" and attributes["read_only"] is True
    assert attributes["llm_calls"] == 2 and attributes["input_tokens"] == 240
    assert attributes["tool_calls"] >= 1 and attributes["tools_effective"] == 1
    parent_done = next(
        event
        for event in events
        if event["run_id"] == parent["run_id"] and event["event_type"] == "run.completed"
    )
    assert parent_done["attributes"]["delegations"] == 1
    # Counts only: no objective or answer text in any event.
    stored = json.dumps([event["attributes"] for event in events])
    assert "OBJECTIVE-TEXT-42" not in stored and "ANSWER-TEXT-42" not in stored


# -- activity (rule 19) --------------------------------------------------------------


def test_a_running_delegation_shows_in_the_activity_of_its_turn(
    served: AgentWebServer,  # noqa: F811 - the fixture
) -> None:
    release = threading.Event()

    def hook(key: str, index: int) -> None:
        if key == "slow":
            release.wait(10)

    scripts = {
        "parent": [reply(delegate("slow")), reply(text="好。")],
        "slow": [reply(text="摘要")],
    }
    built, _, _, _ = wired(scripts, (agent_profile(),), hook=hook)
    web = served.web
    progress = web.turn_progress.begin(
        turn_progress.TurnProgress(turn_id="t1", session_id=SESSION, owner="engineer")
    )
    outcome: list[Any] = []

    def run() -> None:
        turn_progress.TURN_PROGRESS.set(progress)
        outcome.append(converse(built))

    thread = threading.Thread(target=run)
    thread.start()
    try:
        deadline = time.monotonic() + 5
        seen: dict[str, Any] = {}
        while time.monotonic() < deadline:
            seen = web.activity()
            if any(item.get("delegations") == 1 for item in seen["items"]):
                break
            time.sleep(0.02)
        assert seen["busy"] is True
        assert [item for item in seen["items"] if item["kind"] == "chat_turn"][0][
            "delegations"
        ] == 1
        answered = fetch(base(served) + "/api/activity", token=served.token).json()
        assert answered["items"][0]["delegations"] == 1
        assert progress.snapshot()["delegations_running"] == 1
    finally:
        release.set()
        thread.join(timeout=10)
        web.turn_progress.end(progress)
    assert outcome and delegated(outcome[0].tools[0]).status == "succeeded"
    assert "delegations_running" not in progress.snapshot()


# -- profiles on the Host --------------------------------------------------------------


def _install(layout: Any, item: AgentProfile) -> None:
    layout.agents.mkdir(parents=True, exist_ok=True)
    identity = item.metadata.identity
    (layout.agents / f"{identity.namespace}__{identity.name}__{identity.version}.json").write_text(
        item.model_dump_json(), encoding="utf-8"
    )


def _host(tmp_path: Path, *, enabled: bool = True, owner: bool = True) -> tuple[Any, Any]:
    config, layout = ready(
        tmp_path,
        config_changes={
            "local_owner_grants": owner,
            "multi_agent": {"enabled": enabled},
        },
    )
    return configured(config), layout


def test_delegation_targets_are_validated_and_fail_closed(tmp_path: Path) -> None:
    config, layout = _host(tmp_path)
    target = agent_profile(skills=(), capabilities=())
    identity = target.metadata.identity
    with pytest.raises(ProfileError, match="profile_not_installed"):
        delegation_target(config, layout, None, identity)
    _install(layout, target)
    assert delegation_target(config, layout, None, identity) == target  # owner mode
    missing_skill = agent_profile("broken", capabilities=())
    _install(layout, missing_skill)
    with pytest.raises(ProfileError, match="profile_dependency_unavailable"):
        delegation_target(config, layout, None, missing_skill.metadata.identity)
    draft = agent_profile("drafted", skills=(), capabilities=())
    draft = draft.model_copy(
        update={"metadata": draft.metadata.model_copy(update={"lifecycle": "draft"})}
    )
    _install(layout, draft)
    with pytest.raises(ProfileError, match="profile_invalid"):
        delegation_target(config, layout, None, draft.metadata.identity)
    strict, strict_layout = _host(tmp_path / "strict", owner=False)
    _install(strict_layout, target)
    with pytest.raises(ProfileError, match="profile_not_selected"):
        delegation_target(strict, strict_layout, None, identity)
    off, off_layout = _host(tmp_path / "off", enabled=False)
    _install(off_layout, target)
    with pytest.raises(ProfileError, match="profile_delegation_unsupported"):
        delegation_target(off, off_layout, None, identity)


def test_may_delegate_to_is_accepted_only_with_the_flag_and_valid_targets(
    tmp_path: Path,
) -> None:
    now = datetime(2026, 10, 27, tzinfo=UTC)
    parent = agent_profile(
        "lead",
        skills=(),
        capabilities=(),
        may_delegate_to=[{"namespace": "engineering", "name": "researcher", "version": "1.0.0"}],
    )
    target = agent_profile(skills=(), capabilities=())

    def authorization(*assets: AgentProfile) -> DeviceAuthorization:
        return DeviceAuthorization(
            bridge_id=BRIDGE,
            issued_at=now,
            selections=tuple(
                DeviceAssetSelection(
                    bridge_id=BRIDGE,
                    actor="engineer",
                    kind="agent",
                    asset=item.metadata.identity,
                    decided_at=now,
                )
                for item in assets
            ),
        )

    config, layout = _host(tmp_path, owner=False)
    _install(layout, parent)
    with pytest.raises(ProfileError, match="profile_delegation_target_unavailable"):
        validate_profile(config, layout, authorization(parent), parent.metadata.identity)
    _install(layout, target)
    with pytest.raises(ProfileError, match="profile_delegation_target_unavailable"):
        validate_profile(config, layout, authorization(parent), parent.metadata.identity)
    assert (
        validate_profile(config, layout, authorization(parent, target), parent.metadata.identity)
        == parent
    )
    off = config.model_copy(
        update={"multi_agent": config.multi_agent.model_copy(update={"enabled": False})}
    )
    with pytest.raises(ProfileError, match="profile_delegation_unsupported"):
        validate_profile(off, layout, authorization(parent, target), parent.metadata.identity)


def test_the_host_offers_the_tool_only_with_the_flag_and_an_installed_target(
    tmp_path: Path,
) -> None:
    for enabled in (False, True):
        config, layout = _host(tmp_path / str(enabled), enabled=enabled)
        _install(layout, agent_profile(skills=(), capabilities=()))
        catalog = delegation_catalog(config, layout)
        with build_runtime(config, layout=layout) as runtime:
            offered = runtime.agent.gateway.host_tools
            assert offered is not None
            names = {tool.tool.name for tool in offered()}
        assert (DELEGATE_TOOL in names) is enabled
        if enabled:
            assert [item.key for item in catalog.targets] == ["engineering/researcher@1.0.0"]
            assert catalog.targets[0].listed is False  # no active profile lists it
        else:
            assert catalog == DelegationCatalog()


def test_cli_backends_get_no_delegation_tool() -> None:
    """CLI backends (Claude Code, Codex, Copilot) answer outside the Gateway loop;
    the only AEP tools they see are the MCP servers', which never carry it."""
    assert DELEGATE_TOOL not in agent_mode.MCP_TOOLS
    assert DELEGATE_TOOL not in mcp_server.TOOLS
    # And the Gateway's own sub-run marker is the only place the tool is hidden
    # from; a CLI turn never reaches `Gateway.converse` at all.
    assert delegation_scope.current_turn() is None
