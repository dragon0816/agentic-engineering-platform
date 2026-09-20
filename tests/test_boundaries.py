from collections.abc import Iterator

import pytest
from pydantic import ValidationError

from agent.contracts import AgentProfile, DeterministicRouter
from capabilities.contracts import CapabilitySpec
from common.evaluation import EvaluationCase
from common.execution import (
    ApprovalRequest,
    CapabilityResult,
    RequestContext,
    TraceIdentifiers,
    WorkflowRun,
)
from knowledge.contracts import KnowledgeSource
from models.contracts import (
    ModelClient,
    ModelMessage,
    ModelRequest,
    ModelResponse,
    ModelStreamEvent,
)


def trace() -> TraceIdentifiers:
    return TraceIdentifiers(trace_id="trace-1", request_id="request-1", span_id="span-1")


def test_failure_states_are_structured() -> None:
    with pytest.raises(ValidationError):
        CapabilityResult(trace=trace(), status="unavailable")
    result = CapabilityResult.model_validate(
        {
            "trace": trace(),
            "status": "unavailable",
            "failure": {"code": "needs_connectivity", "message": "Central service unavailable"},
        }
    )
    assert CapabilityResult.model_validate_json(result.model_dump_json()) == result
    with pytest.raises(ValidationError):
        WorkflowRun.model_validate(
            {
                "run_id": "run-1",
                "trace": trace(),
                "status": "failed",
                "workflow": {"namespace": "a", "name": "b", "version": "1.0.0"},
            }
        )


def test_side_effects_require_policy() -> None:
    with pytest.raises(ValidationError):
        CapabilitySpec.model_validate(
            {
                "identity": {"namespace": "a", "name": "b", "version": "1.0.0"},
                "name": "a.b",
                "description": "Write operation",
                "input_contract": "input.v1",
                "output_contract": "output.v1",
                "side_effect": "write",
                "policy": {"approval_required": False},
            }
        )


def test_model_contract_accepts_neutral_fake_adapter() -> None:
    class FakeModel:
        def generate(self, request: ModelRequest) -> ModelResponse:
            return ModelResponse(trace=request.trace, model_alias="test", text="done")

        def stream(self, request: ModelRequest) -> Iterator[ModelStreamEvent]:
            yield ModelStreamEvent(trace=request.trace, kind="text", text="done")
            yield ModelStreamEvent(trace=request.trace, kind="done")

    client: ModelClient = FakeModel()
    request = ModelRequest.model_validate(
        {
            "trace": trace(),
            "model_alias": "local-engineering",
            "messages": [{"role": "user", "text": "Explain this", "images": ["image-ref-1"]}],
            "requirements": {"vision": True, "local_only": True},
        }
    )
    assert client.generate(request).text == "done"
    assert len(list(client.stream(request))) == 2
    assert ModelRequest.model_validate_json(request.model_dump_json()) == request


def test_known_route_interface_has_no_model_dependency() -> None:
    class EmptyRoutes:
        def resolve(self, request: RequestContext) -> None:
            return None

    router: DeterministicRouter = EmptyRoutes()
    request = RequestContext(
        trace=trace(), actor="user", namespace="sample", channel="cli", message="ambiguous"
    )
    assert router.resolve(request) is None


def test_knowledge_source_preserves_location() -> None:
    source = KnowledgeSource(
        source_id="source-1",
        original_ref="drop/report.pdf",
        sha256="a" * 64,
        page=3,
        raw_ref="raw/report.md",
    )
    assert KnowledgeSource.model_validate_json(source.model_dump_json()) == source
    with pytest.raises(ValidationError):
        KnowledgeSource(
            source_id="source-1", original_ref="drop/report.pdf", sha256="a" * 64, page=0
        )


def test_profile_bounds_and_evaluation_schema() -> None:
    with pytest.raises(ValidationError):
        AgentProfile.model_validate({"max_turns": 0})
    with pytest.raises(ValidationError):
        EvaluationCase.model_validate({"case_id": "empty"})


def test_tool_call_history_is_provider_neutral() -> None:
    message = ModelMessage.model_validate(
        {
            "role": "assistant",
            "tool_calls": [{"call_id": "call-1", "name": "inspect", "arguments": {}}],
        }
    )
    assert ModelMessage.model_validate_json(message.model_dump_json()) == message
    result = ModelMessage(role="tool", text="done", tool_call_id="call-1")
    assert result.tool_call_id == message.tool_calls[0].call_id
    with pytest.raises(ValidationError):
        ModelMessage.model_validate({**message.model_dump(), "role": "user"})


def test_approval_request_round_trip() -> None:
    request = ApprovalRequest.model_validate(
        {
            "approval_id": "approval-1",
            "trace": trace(),
            "asset": {"namespace": "sample", "name": "inspect", "version": "1.0.0"},
            "requester": "engineer",
            "layer": "execution",
            "reason": "Explicit permission request",
        }
    )
    assert ApprovalRequest.model_validate_json(request.model_dump_json()) == request


def test_model_requirements_and_stream_events_are_validated() -> None:
    with pytest.raises(ValidationError):
        ModelRequest.model_validate(
            {
                "trace": trace(),
                "model_alias": "test",
                "messages": [{"role": "user", "text": "image", "images": ["ref"]}],
            }
        )
    with pytest.raises(ValidationError):
        ModelStreamEvent(trace=trace(), kind="failed")
