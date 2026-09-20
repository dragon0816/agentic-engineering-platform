import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from agent.routing import CommandRouter, RequestRouter, RoutingOutcome
from agent.skills import SkillManifest, SkillRegistry
from common.evaluation import EvaluationCase
from common.execution import AttachmentRef, RequestContext, TraceIdentifiers
from models.contracts import ModelRequest, ModelResponse, ModelStreamEvent

ROOT = Path(__file__).resolve().parents[1]
CASES: list[dict[str, Any]] = json.loads(
    (ROOT / "tests/fixtures/routing_cases.json").read_text(encoding="utf-8")
)


def skills() -> SkillRegistry:
    registry = SkillRegistry()
    for data in json.loads((ROOT / "skills/source-routing.json").read_text(encoding="utf-8")):
        registry.register(SkillManifest.model_validate(data))
    return registry


def request(message: str) -> RequestContext:
    return RequestContext(
        trace=TraceIdentifiers(trace_id="trace-1", request_id="request-1", span_id="span-1"),
        actor="engineer",
        namespace="legacy",
        channel="test",
        message=message,
    )


class FakeModel:
    def __init__(self, output: Any = None) -> None:
        self.calls: list[ModelRequest] = []
        self.output = output

    def generate(self, request: ModelRequest) -> ModelResponse:
        self.calls.append(request)
        return ModelResponse(
            trace=request.trace, model_alias=request.model_alias, structured_output=self.output
        )

    def stream(self, request: ModelRequest) -> Iterator[ModelStreamEvent]:
        raise AssertionError("routing must not stream")


@pytest.mark.parametrize("case", CASES[:-1], ids=[case["message"] for case in CASES[:-1]])
def test_adapted_routes_match_source_without_model(case: dict[str, Any]) -> None:
    model = FakeModel()
    result = RequestRouter(CommandRouter(skills()), model=model).route(request(case["message"]))
    assert result.decision.target is not None
    assert result.decision.target.name == case["skill"].replace("_", "-")
    assert result.arguments.get("args") == case["args"]
    assert result.origin == "deterministic"
    assert result.trace == request(case["message"]).trace
    assert model.calls == []


# "build.package" pins an intentional source difference: the source retried a failed
# dot lookup against the keyword table; the adaptation fails closed on the same message.
@pytest.mark.parametrize("message", ["unknown.command", "run_testing.unknown", "build.package"])
def test_unknown_explicit_command_never_falls_through(message: str) -> None:
    model = FakeModel()
    result = RequestRouter(CommandRouter(skills()), model=model).route(request(message))
    assert result.decision.kind == "needs_input"
    assert model.calls == []


def test_ambiguous_request_uses_one_validated_model_selection() -> None:
    target = skills().discover("legacy")[0].commands[0].target
    model = FakeModel({"kind": "capability", "target": target.model_dump(), "arguments": {}})
    result = RequestRouter(CommandRouter(skills()), model=model).route(request("help me"))
    assert result.decision.target == target
    assert result.origin == "model"
    assert len(model.calls) == 1


@pytest.mark.parametrize(
    "output",
    [
        None,
        {"kind": "execute"},
        {
            "kind": "capability",
            "target": {"namespace": "other", "name": "unknown", "version": "1.0.0"},
            "arguments": {},
        },
    ],
)
def test_invalid_model_selection_cannot_create_a_route(output: Any) -> None:
    model = FakeModel(output)
    result = RequestRouter(CommandRouter(skills()), model=model).route(request("help me"))
    assert result.decision.kind == "needs_input"
    assert len(model.calls) == 1


def test_registry_versions_and_namespaces_are_unambiguous() -> None:
    registry = skills()
    manifest = registry.discover("legacy")[0]
    with pytest.raises(ValueError):
        registry.register(manifest)
    data = manifest.model_dump()
    data["metadata"]["identity"]["version"] = "2.0.0"
    with pytest.raises(ValueError):
        registry.register(SkillManifest.model_validate(data))
    assert registry.discover("other") == ()
    data["metadata"]["identity"]["namespace"] = "other"
    registry.register(SkillManifest.model_validate(data))
    assert len(registry.discover("other")) == 1


def test_bad_rule_and_missing_default_rejected() -> None:
    data = skills().discover("legacy")[0].model_dump()
    data["rules"] = [{"pattern": "[", "command": "run"}]
    with pytest.raises(ValidationError):
        SkillManifest.model_validate(data)
    data["rules"] = []
    data["default_command"] = "missing"
    with pytest.raises(ValidationError):
        SkillManifest.model_validate(data)


def test_attachment_metadata_is_not_resolved_or_sent_to_model() -> None:
    context = request("help me").model_dump()
    context["attachments"] = [
        AttachmentRef(
            file_id="file-1",
            filename="private.txt",
            resource_ref="opaque-1",
            size_bytes=12,
            media_type="text/plain",
        )
    ]
    attached = RequestContext.model_validate(context)
    assert RequestContext.model_validate_json(attached.model_dump_json()) == attached
    model = FakeModel()
    RequestRouter(CommandRouter(skills()), model=model).route(attached)
    assert "opaque-1" not in model.calls[0].model_dump_json()
    assert "private.txt" not in model.calls[0].model_dump_json()


def test_direct_skill_selection_uses_declared_default() -> None:
    result = CommandRouter(skills()).direct(request("ambiguous"), "run_testing")
    assert result.decision.target is not None
    assert result.decision.target.name == "run-testing"


def test_direct_selection_without_default_or_rule_match_needs_input() -> None:
    registry = SkillRegistry()
    data = skills().discover("legacy")[0].model_dump()
    data["rules"] = []
    data["default_command"] = None
    registry.register(SkillManifest.model_validate(data))
    result = CommandRouter(registry).direct(request("unrelated"), data["alias"])
    assert result.decision.kind == "needs_input"
    assert result.failure is not None and result.failure.code == "no_default_command"


def test_workflow_route_remains_intent_without_model_selection() -> None:
    registry = SkillRegistry()
    data = skills().discover("legacy")[0].model_dump()
    data["commands"][0]["kind"] = "workflow"
    registry.register(SkillManifest.model_validate(data))
    model = FakeModel()
    result = RequestRouter(CommandRouter(registry), model=model).route(request("run_testing.run"))
    assert result.decision.kind == "workflow"
    assert model.calls == []


def test_model_exception_is_sanitized_and_not_retried() -> None:
    class Broken(FakeModel):
        def generate(self, request: ModelRequest) -> ModelResponse:
            self.calls.append(request)
            raise RuntimeError("password=synthetic")

    model = Broken()
    result = RequestRouter(CommandRouter(skills()), model=model).route(request("help me"))
    assert result.failure is not None and result.failure.code == "model_unavailable"
    assert "synthetic" not in result.model_dump_json()
    assert len(model.calls) == 1


def test_phase2_evaluation_cases() -> None:
    cases = json.loads((ROOT / "evaluation/cases/phase2-routing.json").read_text(encoding="utf-8"))
    for payload in cases:
        case = EvaluationCase.model_validate(payload)
        model = FakeModel()
        result = RequestRouter(CommandRouter(skills()), model=model).route(case.request)
        assert result.decision == case.expected_route
        assert model.calls == []


def test_routing_outcome_cannot_hide_an_unresolved_decision() -> None:
    with pytest.raises(ValidationError):
        RoutingOutcome.model_validate(
            {
                "trace": request("test").trace,
                "decision": {"kind": "needs_input", "reason": "unknown"},
                "origin": "model",
            }
        )
