"""Agent tool schema from the Workflow declaration (slice S3)."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from test_gateway import ROOT, Handler, Probe, Report, capability_spec, request, workflow_manifest
from test_routing import FakeModel
from test_workflow_parameter_declaration import RICH, _manifest

from agent.gateway import Gateway
from agent.routing import CommandRouter, RequestRouter
from agent.skills import SkillManifest, SkillRegistry
from capabilities.runtime import CapabilityGrant, InstalledCapabilities, LocalPolicy
from common.assets import ExecutionDependencies, WorkflowManifest
from common.workflow_forms import agent_tool_schema
from models.contracts import ModelMessage, ModelRequest, ModelResponse, ModelTool, ModelToolCall
from models.wire import tool_schema
from workflow.dispatch import BridgeExecutor
from workflow.engine import InstalledWorkflows, WorkflowEngine


def test_schema_offers_only_agent_fields_and_never_privileged_ones() -> None:
    schema = agent_tool_schema(_manifest(RICH))
    properties = schema["properties"]
    assert schema["additionalProperties"] is False
    assert "send" not in properties            # privileged: a person's choice
    assert "output" not in properties          # web-only field
    assert "trace_level" not in properties     # internal field
    assert properties["mode"]["enum"] == ["brief", "full"]
    assert properties["mode"]["default"] == "brief"
    assert properties["reporters"] == {
        "type": "array", "items": {"type": "string", "minLength": 1},
        "description": "Reporters", "default": [],
    }
    assert properties["cc"]["items"]["format"] == "email"
    assert properties["project"]["pattern"] == r"^[a-z0-9/_-]+$"
    assert "enum" not in properties["chipset"]  # resolved at run time (S6)
    assert properties["ratio"] == {
        "type": "number", "minimum": 0, "maximum": 1, "description": "Ratio", "default": 0.5,
    }


def test_wire_uses_a_generated_schema_and_keeps_the_generic_fallback() -> None:
    generated = {"type": "object", "properties": {}, "additionalProperties": False}
    typed = tool_schema(ModelTool(
        name="t", description="d", input_contract="platform.command-arguments.v1",
        input_schema=generated,
    ))
    assert isinstance(typed, dict) and typed["function"]["parameters"] == generated
    legacy = tool_schema(ModelTool(
        name="t", description="d", input_contract="platform.command-arguments.v1",
    ))
    assert isinstance(legacy, dict)
    assert legacy["function"]["parameters"] == {"type": "object", "additionalProperties": True}


def _declared_gateway(handler: Handler, model: FakeModel) -> Gateway:
    skills = SkillRegistry()
    for data in json.loads((ROOT / "skills/release-workflow.json").read_text(encoding="utf-8")):
        skills.register(SkillManifest.model_validate(data))
    installed = InstalledCapabilities()
    installed.register(
        capability_spec(), handler, Probe, Report, ExecutionDependencies(central_required=False)
    )
    bridge = BridgeExecutor(installed, LocalPolicy((CapabilityGrant.model_validate({
        "actor": "engineer", "asset": capability_spec().identity,
        "permissions": ["engineering.validate"], "policy_refs": ["release-policy"],
        "approval_ref": "release-approval",
    }),)))
    data = workflow_manifest().model_dump(mode="json")
    data["parameters"] = [
        {"name": "args", "label": "Arguments", "kind": "text", "pattern": "^[a-z]+$",
         "help": "Validation mode"},
        {"name": "send", "label": "Send", "kind": "boolean", "confirm": True},
    ]
    workflows = InstalledWorkflows()
    workflows.register(WorkflowManifest.model_validate(data))
    return Gateway(
        RequestRouter(CommandRouter(skills), model=model), bridge,
        WorkflowEngine(workflows, bridge),
    )


class _ToolModel(FakeModel):
    def __init__(self, arguments: dict[str, Any]) -> None:
        super().__init__()
        self.arguments = arguments

    def generate(self, item: ModelRequest) -> ModelResponse:
        self.calls.append(item)
        if len(self.calls) == 1:
            return ModelResponse(trace=item.trace, model_alias=item.model_alias, tool_calls=(
                ModelToolCall(call_id="call-1", name="release__package", arguments=self.arguments),
            ))
        return ModelResponse(trace=item.trace, model_alias=item.model_alias, text="done")


def _converse(arguments: dict[str, Any]) -> tuple[Any, Handler, _ToolModel]:
    handler, model = Handler(), _ToolModel(arguments)
    result = asyncio.run(_declared_gateway(handler, model).converse(
        request("package the release"),
        (ModelMessage(role="user", text="package the release"),),
    ))
    return result, handler, model


def test_the_model_sees_the_declared_fields_and_a_valid_call_runs() -> None:
    result, handler, model = _converse({"args": "quick"})
    offered = {tool.name: tool for tool in model.calls[0].tools}
    schema = offered["release__package"].input_schema
    assert schema is not None and set(schema["properties"]) == {"args"}
    assert result.tools[0].workflow is not None
    assert handler.calls == 1


def test_privileged_or_invalid_arguments_are_refused_before_execution() -> None:
    for arguments in ({"args": "quick", "send": True}, {"args": "NOT-VALID"}):
        result, handler, _model = _converse(arguments)
        failure = result.tools[0].failure
        assert failure is not None and failure.code == "workflow_parameters_invalid"
        assert result.tools[0].workflow is None
        assert handler.calls == 0
