import asyncio
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError
from test_routing import FakeModel

from agent.backend_contracts import (
    CONVERSATION_MAX_OUTPUT_TOKENS,
    MAX_CONVERSATION_TOOL_CALLS,
    MAX_CONVERSATION_TURNS,
    GatewayConversationRequest,
)
from agent.decisions import (
    DecisionAcceleratorConfig,
    DecisionResult,
    DecisionService,
    DecisionTrace,
)
from agent.gateway import (
    Gateway,
    GatewayResult,
    SkillCandidateRequest,
    _valid_skill_subset,
)
from agent.routing import CommandRouter, RequestRouter
from agent.skills import SkillManifest, SkillRegistry
from capabilities.contracts import CapabilitySpec
from capabilities.runtime import CapabilityGrant, InstalledCapabilities, LocalPolicy
from common.assets import ExecutionDependencies, WorkflowManifest
from common.base import Contract
from common.evaluation import EvaluationCase
from common.execution import Failure, RequestContext, TraceIdentifiers
from models.contracts import ModelMessage, ModelRequest, ModelResponse, ModelToolCall
from workflow.dispatch import BridgeExecutor
from workflow.engine import InstalledWorkflows, WorkflowEngine

ROOT = Path(__file__).resolve().parents[1]


class Probe(Contract):
    """Raw dot-command arguments are accepted only when the input contract declares them."""

    args: str = ""


class Report(Contract):
    validated: bool = True


class Handler:
    def __init__(self) -> None:
        self.calls = 0

    async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
        self.calls += 1
        return Report()


def capability_spec() -> CapabilitySpec:
    return CapabilitySpec.model_validate(
        {
            "identity": {
                "namespace": "engineering",
                "name": "validate-release",
                "version": "1.0.0",
            },
            "name": "engineering.validate_release",
            "description": "Inert release validation fixture",
            "input_contract": "engineering.validate-release.input.v1",
            "output_contract": "engineering.validate-release.output.v1",
            "side_effect": "read",
            "policy": {
                "required_permissions": ["engineering.validate"],
                "policy_refs": ["release-policy"],
            },
        }
    )


def workflow_manifest() -> WorkflowManifest:
    return WorkflowManifest.model_validate(
        {
            "metadata": {
                "identity": {
                    "namespace": "engineering",
                    "name": "release-validation",
                    "version": "1.0.0",
                },
                "owner": {"type": "team", "id": "engineering"},
                "visibility": "private",
                "lifecycle": "draft",
            },
            "kind": "workflow",
            "description": "Inert single-step release validation workflow",
            "execution": {"mode": "local"},
            "dependencies": {"central_required": False},
            "input_contract": "engineering.validate-release.input.v1",
            "output_contract": "engineering.validate-release.output.v1",
            "steps": [{"namespace": "engineering", "name": "validate-release", "version": "1.0.0"}],
        }
    )


def request(message: str) -> RequestContext:
    return RequestContext(
        trace=TraceIdentifiers(trace_id="trace-1", request_id="request-1", span_id="span-1"),
        actor="engineer",
        namespace="engineering",
        channel="test",
        message=message,
    )


def gateway(
    handler: Handler,
    model: FakeModel | None = None,
    *,
    granted: bool = True,
    decision_observer: Callable[[DecisionTrace], None] | None = None,
) -> Gateway:
    skills = SkillRegistry()
    for data in json.loads((ROOT / "skills/release-workflow.json").read_text(encoding="utf-8")):
        skills.register(SkillManifest.model_validate(data))
    installed = InstalledCapabilities()
    installed.register(
        capability_spec(), handler, Probe, Report, ExecutionDependencies(central_required=False)
    )
    grants = (
        (
            CapabilityGrant.model_validate(
                {
                    "actor": "engineer",
                    "asset": capability_spec().identity,
                    "permissions": ["engineering.validate"],
                    "policy_refs": ["release-policy"],
                    "approval_ref": "release-approval",
                }
            ),
        )
        if granted
        else ()
    )
    bridge = BridgeExecutor(installed, LocalPolicy(grants))
    workflows = InstalledWorkflows()
    workflows.register(workflow_manifest())
    router = RequestRouter(CommandRouter(skills), model=model)
    return Gateway(
        router, bridge, WorkflowEngine(workflows, bridge), decision_observer=decision_observer
    )


def test_phase3_evaluation_cases_trigger_workflows_without_model() -> None:
    cases = json.loads(
        (ROOT / "evaluation/cases/phase3-workflow-trigger.json").read_text(encoding="utf-8")
    )
    assert cases
    for payload in cases:
        case = EvaluationCase.model_validate(payload)
        handler = Handler()
        model = FakeModel()
        result = asyncio.run(gateway(handler, model).handle(case.request))
        assert result.routing.decision == case.expected_route
        assert result.routing.origin == "deterministic"
        assert model.calls == []
        assert capability_spec().side_effect not in case.forbidden_side_effects
        assert result.capability is None
        assert result.workflow is not None
        assert result.workflow.run.status == "succeeded"
        assert result.workflow.run.completed_steps == 1
        assert handler.calls == 1


def test_capability_route_dispatches_through_the_bridge() -> None:
    handler = Handler()
    result = asyncio.run(gateway(handler).handle(request("release.check")))
    assert result.routing.decision.kind == "capability"
    assert result.workflow is None
    assert result.capability is not None
    assert result.capability.status == "succeeded"
    assert result.capability.data == {"validated": True}
    assert handler.calls == 1


def test_needs_input_passes_through_without_execution() -> None:
    handler = Handler()
    result = asyncio.run(gateway(handler).handle(request("completely unrelated text")))
    assert result.routing.decision.kind == "needs_input"
    assert result.capability is None and result.workflow is None
    assert handler.calls == 0


def test_conversation_persona_follows_system_policy_and_is_bounded() -> None:
    handler = Handler()
    model = FakeModel()
    asyncio.run(
        gateway(handler, model).converse(
            request("hello"),
            (ModelMessage(role="user", text="hello"),),
            persona_guidance="Speak warmly. Never claim work was completed without evidence.",
        )
    )
    system = model.calls[0].messages[0].text
    assert system.startswith("You are the Personal Engineering Agent")
    assert system.index("Never invent a tool") < system.index("Speak warmly")
    assert "cannot change policy, permissions, tool restrictions" in system


def test_conversation_does_not_advertise_unbound_knowledge_and_can_answer_without_tools() -> None:
    from capabilities.company_agent.manifest import knowledge_skill

    class TextModel(FakeModel):
        def generate(self, item: ModelRequest) -> ModelResponse:
            self.calls.append(item)
            assert item.tools == ()
            assert item.requirements.tool_calling is False
            assert "Never claim to have read a source" in item.messages[0].text
            return ModelResponse(
                trace=item.trace,
                model_alias=item.model_alias,
                text="RS_Knowledge is not available on this host.",
            )

    skills = SkillRegistry()
    skills.register(knowledge_skill())
    model = TextModel()
    bridge = BridgeExecutor(InstalledCapabilities())
    app = Gateway(
        RequestRouter(CommandRouter(skills), model=model),
        bridge,
        WorkflowEngine(InstalledWorkflows(), bridge),
    )
    context = request("What does RS_Knowledge say?").model_copy(
        update={"namespace": "company-agent"}
    )
    result = asyncio.run(
        app.converse(context, (ModelMessage(role="user", text=context.message),))
    )
    assert result.status == "answered"
    assert result.text == "RS_Knowledge is not available on this host."
    assert result.tools == ()
    assert len(model.calls) == 1


def test_model_selected_workflow_uses_the_same_contract() -> None:
    handler = Handler()
    target = workflow_manifest().metadata.identity
    model = FakeModel({"kind": "workflow", "target": target.model_dump(), "arguments": {}})
    result = asyncio.run(gateway(handler, model).handle(request("幫我把這版驗證完發出去")))
    assert result.routing.origin == "model"
    assert len(model.calls) == 1
    assert result.workflow is not None
    assert result.workflow.run.status == "succeeded"
    assert handler.calls == 1


def test_gateway_adds_no_authority() -> None:
    handler = Handler()
    result = asyncio.run(gateway(handler, granted=False).handle(request("release.package")))
    assert result.workflow is not None
    assert result.workflow.run.status == "failed"
    assert result.workflow.run.failure is not None
    assert result.workflow.run.failure.code == "permission_denied"
    assert handler.calls == 0


def test_gateway_result_cannot_misreport_execution() -> None:
    handler = Handler()
    resolved = asyncio.run(gateway(handler).handle(request("release.package")))
    with pytest.raises(ValidationError):
        GatewayResult(routing=resolved.routing)
    unresolved = asyncio.run(gateway(handler).handle(request("unrelated")))
    with pytest.raises(ValidationError):
        GatewayResult(routing=unresolved.routing, workflow=resolved.workflow)


def test_route_arguments_pass_through_unchanged() -> None:
    class Echo(Handler):
        def __init__(self) -> None:
            super().__init__()
            self.seen: list[Any] = []

        async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
            self.seen.append(inputs)
            return await super().__call__(context, inputs)

    handler = Echo()
    result = asyncio.run(gateway(handler).handle(request("release.check  notes.txt now ")))
    assert result.capability is not None and result.capability.status == "succeeded"
    assert handler.seen == [Probe(args="notes.txt now")]
    no_args = asyncio.run(gateway(handler).handle(request("release.check")))
    assert no_args.capability is not None and no_args.capability.status == "succeeded"
    assert handler.seen[-1] == Probe()


def test_bounded_conversation_uses_only_an_installed_tool_then_synthesizes() -> None:
    class ConversationModel(FakeModel):
        def generate(self, item: ModelRequest) -> ModelResponse:
            self.calls.append(item)
            if len(self.calls) == 1:
                assert {tool.name for tool in item.tools} == {
                    "release__check",
                    "release__package",
                }
                return ModelResponse(
                    trace=item.trace,
                    model_alias=item.model_alias,
                    tool_calls=(
                        ModelToolCall(
                            call_id="call-1",
                            name="release__check",
                            arguments={},
                        ),
                    ),
                )
            assert item.messages[-1].role == "tool"
            assert '"status": "succeeded"' in item.messages[-1].text
            return ModelResponse(
                trace=item.trace,
                model_alias=item.model_alias,
                text="The release check passed.",
            )

    handler = Handler()
    model = ConversationModel()
    decisions: list[DecisionTrace] = []
    result = asyncio.run(
        gateway(handler, model, decision_observer=decisions.append).converse(
            request("Can you check this release?"),
            (ModelMessage(role="user", text="Can you check this release?"),),
        )
    )
    assert result.status == "answered"
    assert result.text == "The release check passed."
    assert result.model_turns == 2
    assert len(result.tools) == 1
    assert result.tools[0].decision is not None
    assert result.tools[0].decision.target == capability_spec().identity
    assert handler.calls == 1
    assert len(decisions) == 1
    assert decisions[0].decision_type == "skill_selection"
    assert decisions[0].provider_id == "rule"
    assert not decisions[0].fallback
    assert "Can you check this release?" not in decisions[0].model_dump_json()


def test_accelerated_skill_subset_cannot_execute_a_hidden_tool() -> None:
    class CandidateProvider:
        provider_id = "jev"

        def decide(self, item: SkillCandidateRequest) -> DecisionResult[tuple[str, ...]]:
            assert item.context.message == "Check release"
            return DecisionResult(
                decision_type="skill_selection",
                value=("release__check",),
                confidence=0.99,
                reason_code="candidate_subset",
                provider_id=self.provider_id,
            )

    class HiddenToolModel(FakeModel):
        def generate(self, item: ModelRequest) -> ModelResponse:
            self.calls.append(item)
            assert [tool.name for tool in item.tools] == ["release__check"]
            if len(self.calls) == 1:
                return ModelResponse(
                    trace=item.trace,
                    model_alias=item.model_alias,
                    tool_calls=(
                        ModelToolCall(
                            call_id="hidden-call", name="release__package", arguments={}
                        ),
                    ),
                )
            return ModelResponse(
                trace=item.trace, model_alias=item.model_alias, text="No action taken."
            )

    handler = Handler()
    model = HiddenToolModel()
    app = gateway(handler, model)
    app.skill_decisions = DecisionService[SkillCandidateRequest, tuple[str, ...]](
        baseline=app.skill_decisions.baseline,
        config=DecisionAcceleratorConfig(
            provider="JEV",
            endpoint="http://127.0.0.1:9797/v1",
            credential={"name": "jev_token"},
            enabled_decision_types=("skill_selection",),
        ),
        authorize_accelerator=lambda _: True,
        accelerator_factory=CandidateProvider,
        accept_accelerator=_valid_skill_subset,
    )
    result = asyncio.run(
        app.converse(request("Check release"), (ModelMessage(role="user", text="Check release"),))
    )
    assert result.status == "answered"
    assert result.tools[0].failure is not None
    assert result.tools[0].failure.code == "uninstalled_tool"
    assert handler.calls == 0


def test_skill_candidate_authorization_sees_exact_history_persona_and_catalog() -> None:
    """A selector must not be authorized against only the latest user message.

    The first model turn carries older conversation, persona and Skill text;
    all three are part of the candidate's egress decision before JEV exists.
    """

    class AnswerModel(FakeModel):
        def generate(self, item: ModelRequest) -> ModelResponse:
            self.calls.append(item)
            return ModelResponse(trace=item.trace, model_alias=item.model_alias, text="Ready")

    model = AnswerModel()
    traces: list[DecisionTrace] = []
    app = gateway(Handler(), model, decision_observer=traces.append)
    seen: list[SkillCandidateRequest] = []

    def authorize(item: SkillCandidateRequest) -> bool:
        seen.append(item)
        assert item.context.message == "Continue"
        assert [message.role for message in item.initial_request.messages] == [
            "system", "user", "user"
        ]
        assert "private persona marker" in item.initial_request.messages[0].text
        assert "private history marker" in item.initial_request.messages[1].text
        assert {tool.name for tool in item.tools} == {"release__check", "release__package"}
        assert all("Executes installed" in tool.description for tool in item.tools)
        return False

    app.skill_decisions = DecisionService[SkillCandidateRequest, tuple[str, ...]](
        baseline=app.skill_decisions.baseline,
        config=DecisionAcceleratorConfig(
            provider="JEV",
            endpoint="http://127.0.0.1:9797/v1",
            credential={"name": "jev_token"},
            enabled_decision_types=("skill_selection",),
        ),
        authorize_accelerator=authorize,
        accelerator_factory=lambda: pytest.fail("denied payload constructed JEV"),
        accept_accelerator=_valid_skill_subset,
        observer=traces.append,
    )
    result = asyncio.run(
        app.converse(
            request("Continue"),
            (
                ModelMessage(role="user", text="private history marker"),
                ModelMessage(role="user", text="Continue"),
            ),
            persona_guidance="private persona marker",
        )
    )
    assert result.status == "answered"
    assert len(seen) == 1
    assert len(model.calls) == 1
    assert seen[0].initial_request == model.calls[0]
    assert traces[0].fallback_reason == "accelerator_not_authorized"
    assert "private" not in traces[0].model_dump_json()


def test_skill_candidate_rejects_mismatched_context_trace() -> None:
    original = request("Check release")
    different = request("Check release").model_copy(
        update={"trace": original.trace.model_copy(update={"trace_id": "other-trace"})}
    )
    model_request = ModelRequest(
        trace=different.trace,
        model_alias="routing",
        messages=(ModelMessage(role="user", text="Check release"),),
    )
    with pytest.raises(ValidationError, match="conversation trace"):
        SkillCandidateRequest(context=original, initial_request=model_request)


def test_conversation_cannot_execute_an_invented_tool_and_stops() -> None:
    class InventingModel(FakeModel):
        def generate(self, item: ModelRequest) -> ModelResponse:
            self.calls.append(item)
            return ModelResponse(
                trace=item.trace,
                model_alias=item.model_alias,
                tool_calls=(
                    ModelToolCall(
                        call_id=f"call-{len(self.calls)}",
                        name="admin__shell",
                        arguments={},
                    ),
                ),
            )

    handler = Handler()
    model = InventingModel()
    result = asyncio.run(
        gateway(handler, model).converse(
            request("do something unsupported"),
            (ModelMessage(role="user", text="do something unsupported"),),
        )
    )
    assert result.status == "needs_input"
    assert result.failure is not None and result.failure.code == "tool_loop_limit"
    assert len(result.tools) == MAX_CONVERSATION_TOOL_CALLS
    assert all(item.failure and item.failure.code == "uninstalled_tool" for item in result.tools)
    # coding_v1 D3: every conversation request leaves room for a whole script.
    assert {call.max_output_tokens for call in model.calls} == {CONVERSATION_MAX_OUTPUT_TOKENS}
    assert handler.calls == 0


def test_conversation_tool_call_still_requires_bridge_policy() -> None:
    class PolicyModel(FakeModel):
        def generate(self, item: ModelRequest) -> ModelResponse:
            self.calls.append(item)
            if len(self.calls) == 1:
                return ModelResponse(
                    trace=item.trace,
                    model_alias=item.model_alias,
                    tool_calls=(
                        ModelToolCall(call_id="call-policy", name="release__check", arguments={}),
                    ),
                )
            assert '"code": "permission_denied"' in item.messages[-1].text
            return ModelResponse(
                trace=item.trace,
                model_alias=item.model_alias,
                text="The Bridge policy did not authorize that check.",
            )

    handler = Handler()
    result = asyncio.run(
        gateway(handler, PolicyModel(), granted=False).converse(
            request("check the release"),
            (ModelMessage(role="user", text="check the release"),),
        )
    )
    assert result.status == "answered"
    assert result.tools[0].capability is not None
    assert result.tools[0].capability.failure is not None
    assert result.tools[0].capability.failure.code == "permission_denied"
    assert handler.calls == 0


def test_the_chat_request_default_allows_the_whole_tool_budget() -> None:
    """coding_v1 G3: Agent Web chat builds its request with the default turn limit."""
    item = GatewayConversationRequest(
        context=request("x"), history=(ModelMessage(role="user", text="x"),)
    )
    assert item.max_turns == MAX_CONVERSATION_TURNS == MAX_CONVERSATION_TOOL_CALLS + 1
    with pytest.raises(ValidationError):
        GatewayConversationRequest(
            context=request("x"), history=(ModelMessage(role="user", text="x"),),
            max_turns=MAX_CONVERSATION_TURNS + 1,
        )


def _host_gateway(
    host_tools: list[Any], replies: list[ModelResponse | None]
) -> tuple[Gateway, Any]:
    from agent.gateway import HostTool  # noqa: F401 - imported for the fixture's type

    class Scripted(FakeModel):
        def generate(self, item: ModelRequest) -> ModelResponse:
            self.calls.append(item)
            reply = replies[len(self.calls) - 1]
            assert reply is not None
            return reply.model_copy(update={"trace": item.trace, "model_alias": item.model_alias})

    model = Scripted()
    built = gateway(Handler(), model)
    built.host_tools = lambda: host_tools
    return built, model


def _call(name: str, arguments: dict[str, Any]) -> ModelResponse:
    return ModelResponse(
        trace=TraceIdentifiers(trace_id="x", request_id="x", span_id="x"), model_alias="routing",
        tool_calls=(ModelToolCall(call_id="c1", name=name, arguments=arguments),),
    )


def _text(text: str) -> ModelResponse:
    return ModelResponse(
        trace=TraceIdentifiers(trace_id="x", request_id="x", span_id="x"), model_alias="routing",
        text=text,
    )


def test_a_host_tool_is_offered_and_its_outcome_is_recorded() -> None:
    """G4: authoring tools are host actions; awaiting approval means nothing ran."""
    from agent.gateway import HostTool, HostToolOutcome
    from models.contracts import ModelTool

    seen: list[dict[str, Any]] = []

    async def draft(context: RequestContext, arguments: dict[str, Any]) -> HostToolOutcome:
        seen.append(arguments)
        return HostToolOutcome(status="awaiting_approval", data={"approval_id": "a-1"})

    tool = HostTool(ModelTool(name="authoring__run_workflow", description="run",
                              input_contract="x.v1"), draft)
    built, model = _host_gateway([tool], [_call("authoring__run_workflow", {"x": 1}), _text("ok")])
    history = (ModelMessage(role="user", text="run it"),)
    result = asyncio.run(built.converse(request("run it"), history))
    assert result.status == "answered" and seen == [{"x": 1}]
    (item,) = result.tools
    assert item.host is not None and item.host.status == "awaiting_approval"
    assert item.decision is None
    assert "authoring__run_workflow" in {t.name for t in model.calls[0].tools}


def test_a_failing_host_tool_is_an_observation_and_a_task_scope_hides_it() -> None:
    from agent.gateway import HostTool, HostToolOutcome
    from models.contracts import ModelTool

    async def broken(context: RequestContext, arguments: dict[str, Any]) -> HostToolOutcome:
        raise RuntimeError("boom")

    tool = HostTool(ModelTool(name="authoring__draft_workflow", description="d",
                              input_contract="x.v1"), broken)
    built, _ = _host_gateway([tool], [_call("authoring__draft_workflow", {}), _text("sorry")])
    result = asyncio.run(built.converse(request("d"), (ModelMessage(role="user", text="d"),)))
    assert result.tools[0].failure is not None
    assert result.tools[0].failure.code == "host_tool_failed"
    scoped, model = _host_gateway([tool], [_text("no tools")])
    asyncio.run(scoped.converse(request("d"), (ModelMessage(role="user", text="d"),),
                                allowed_tools=frozenset({"other__tool"})))
    assert all(t.name != "authoring__draft_workflow" for t in model.calls[0].tools)


def test_several_calls_in_one_reply_run_in_order_and_each_gets_an_answer() -> None:
    """Lab fix-002 X02: a reply with parallel calls ended the turn; now each runs."""
    from agent.gateway import HostTool, HostToolOutcome
    from models.contracts import ModelTool

    ran: list[str] = []

    async def note(context: RequestContext, arguments: dict[str, Any]) -> HostToolOutcome:
        ran.append(str(arguments["n"]))
        return HostToolOutcome(status="succeeded", data={"n": arguments["n"]})

    tool = HostTool(ModelTool(name="authoring__list_workflows", description="l",
                              input_contract="x.v1"), note)
    both = ModelResponse(
        trace=TraceIdentifiers(trace_id="x", request_id="x", span_id="x"), model_alias="routing",
        tool_calls=tuple(
            ModelToolCall(call_id=call_id, name="authoring__list_workflows", arguments={"n": n})
            for call_id, n in (("a", 1), ("b", 2))),
    )
    built, model = _host_gateway([tool], [both, _text("done")])
    history = (ModelMessage(role="user", text="go"),)
    result = asyncio.run(built.converse(request("go"), history))
    assert result.status == "answered" and ran == ["1", "2"] and len(result.tools) == 2
    answered = [m.tool_call_id for m in model.calls[1].messages if m.role == "tool"]
    assert answered == ["a", "b"]


def _cut() -> ModelResponse:
    return ModelResponse(
        trace=TraceIdentifiers(trace_id="x", request_id="x", span_id="x"), model_alias="routing",
        failure=Failure(code="model_output_truncated", message="cut"),
    )


def test_a_reply_cut_at_the_output_limit_is_retried_with_a_notice() -> None:
    """Lab fix-005 D04: one truncated reply ended the whole turn."""
    from agent.gateway import TRUNCATED_NOTICE

    built, model = _host_gateway([], [_cut(), _text("shorter answer")])
    history = (ModelMessage(role="user", text="go"),)
    result = asyncio.run(built.converse(request("go"), history))
    assert result.status == "answered" and result.text == "shorter answer"
    assert model.calls[1].messages[-1].text == TRUNCATED_NOTICE


def test_a_reply_that_keeps_getting_cut_still_fails_with_its_own_code() -> None:
    built, _ = _host_gateway([], [_cut(), _cut(), _cut(), _text("never")])
    history = (ModelMessage(role="user", text="go"),)
    result = asyncio.run(built.converse(request("go"), history))
    assert result.status == "failed" and result.failure is not None
    assert result.failure.code == "model_output_truncated"


def test_the_system_prompt_asks_for_an_open_rule_before_working() -> None:
    """Owner 2026-10-07 (lab X02): ask about a rule that changes the result, do not guess it."""
    built, model = _host_gateway([], [_text("Which status counts?")])
    asyncio.run(built.converse(request("go"), (ModelMessage(role="user", text="go"),)))
    system = model.calls[0].messages[0]
    assert system.role == "system"
    assert "ask that question first and do no other work in that turn" in system.text
    assert "names no filter means no filter" in system.text


def test_the_system_prompt_says_a_failed_knowledge_lookup_out_loud() -> None:
    """Owner 2026-10-07 (knowledge_v1 sample-001): after a failed Knowledge call the
    model answered from memory, uncited and without saying so."""
    built, model = _host_gateway([], [_text("ok")])
    asyncio.run(built.converse(request("go"), (ModelMessage(role="user", text="go"),)))
    system = model.calls[0].messages[0].text
    assert "say first that the knowledge base gave no answer" in system
    assert "marked as not from the knowledge base and uncited" in system
