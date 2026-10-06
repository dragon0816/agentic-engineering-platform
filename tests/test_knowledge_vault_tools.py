"""One conversation tool per Knowledge vault (owner decision 2026-10-06).

Before this, the model saw one `knowledge__ask` tool with no schema and never
sent the `asset` the query requires: every chat Knowledge question was refused
`invalid_input` (checked live, before and after the 2026-10-05 Skill changes).
"""

from __future__ import annotations

import asyncio
from typing import Any

from test_gateway import Report, request
from test_routing import FakeModel

from agent.gateway import VAULT_QUESTION_SCHEMA, Gateway, KnowledgeVaultTool
from agent.routing import CommandRouter, RequestRouter
from agent.skills import SkillManifest, SkillRegistry
from capabilities.knowledge_query.handlers import KNOWLEDGE_QUERY_SPEC
from capabilities.runtime import CapabilityGrant, InstalledCapabilities, LocalPolicy
from common.assets import AssetIdentity, ExecutionDependencies
from common.base import Contract
from common.execution import RequestContext
from knowledge.evolution import KnowledgeQueryRequest
from models.contracts import ModelMessage, ModelRequest, ModelResponse, ModelToolCall
from workflow.dispatch import BridgeExecutor
from workflow.engine import InstalledWorkflows, WorkflowEngine

RS = AssetIdentity(namespace="engineering", name="rs-knowledge", version="1.0.0")
HR = AssetIdentity(namespace="people", name="hr-policies", version="2.0.0")
VAULTS = [
    KnowledgeVaultTool(asset=RS, purpose="R&S instrument specs, options and markets",
                       boundaries="prices and customer data"),
    KnowledgeVaultTool(asset=HR, purpose="company HR policies"),
]


class Recording:
    def __init__(self) -> None:
        self.inputs: list[KnowledgeQueryRequest] = []

    async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
        self.inputs.append(KnowledgeQueryRequest.model_validate(inputs))
        return Report()


class CallsVault(FakeModel):
    def __init__(self, name: str, arguments: dict[str, Any]) -> None:
        super().__init__()
        self.name, self.arguments = name, arguments

    def generate(self, item: ModelRequest) -> ModelResponse:
        self.calls.append(item)
        if len(self.calls) == 1:
            return ModelResponse(trace=item.trace, model_alias=item.model_alias, tool_calls=(
                ModelToolCall(call_id="c1", name=self.name, arguments=self.arguments),))
        return ModelResponse(trace=item.trace, model_alias=item.model_alias, text="answered")


def gateway(model: FakeModel, handler: Recording, *, vaults: bool = True) -> Gateway:
    skills = SkillRegistry()
    skills.register(SkillManifest.model_validate({
        "metadata": {
            "identity": {"namespace": "engineering", "name": "knowledge-query",
                         "version": "1.0.0"},
            "owner": {"type": "team", "id": "engineering"}, "visibility": "organization",
            "lifecycle": "published",
        },
        "alias": "knowledge",
        "instructions": "Answers require Raw citations.",
        "commands": [{"name": "ask", "kind": "capability",
                      "target": KNOWLEDGE_QUERY_SPEC.identity.model_dump()}],
        "default_command": "ask",
    }))
    installed = InstalledCapabilities()
    installed.register(KNOWLEDGE_QUERY_SPEC, handler, KnowledgeQueryRequest, Report,
                       ExecutionDependencies(central_required=False))
    bridge = BridgeExecutor(installed, LocalPolicy((CapabilityGrant(
        actor="engineer", asset=KNOWLEDGE_QUERY_SPEC.identity,
        permissions=KNOWLEDGE_QUERY_SPEC.policy.required_permissions,
        policy_refs=KNOWLEDGE_QUERY_SPEC.policy.policy_refs,
    ),)))
    return Gateway(
        RequestRouter(CommandRouter(skills), model=model), bridge,
        WorkflowEngine(InstalledWorkflows(), bridge),
        knowledge_vaults=(lambda: VAULTS) if vaults else None,
        knowledge_capability=KNOWLEDGE_QUERY_SPEC.identity,
    )


def converse(model: FakeModel, handler: Recording, **kwargs: Any) -> Any:
    question = "CMP180 支援哪些標準？"
    return asyncio.run(gateway(model, handler, **kwargs).converse(
        request(question), (ModelMessage(role="user", text=question),)))


def test_each_vault_is_a_tool_described_by_its_purpose_and_asks_only_the_question() -> None:
    model, handler = CallsVault("knowledge__rs-knowledge", {"question": "CMP180?"}), Recording()
    result = converse(model, handler)
    offered = {tool.name: tool for tool in model.calls[0].tools}
    assert set(offered) == {"knowledge__rs-knowledge", "knowledge__hr-policies"}
    rs = offered["knowledge__rs-knowledge"]
    assert rs.input_schema == VAULT_QUESTION_SCHEMA
    assert "R&S instrument specs" in rs.description and "prices and customer data" in rs.description
    assert result.tools[0].capability is not None
    assert result.tools[0].capability.status == "succeeded"
    assert handler.inputs[0].asset == RS and handler.inputs[0].question == "CMP180?"


def test_the_model_cannot_point_a_vault_tool_at_another_vault() -> None:
    model = CallsVault("knowledge__rs-knowledge",
                       {"question": "salaries?", "asset": HR.model_dump(), "procedure": None})
    handler = Recording()
    converse(model, handler)
    assert handler.inputs[0].asset == RS and handler.inputs[0].procedure is None


def test_without_a_vault_provider_the_command_stays_one_generic_tool() -> None:
    model, handler = CallsVault("knowledge__ask", {"question": "x"}), Recording()
    result = converse(model, handler, vaults=False)
    assert [tool.name for tool in model.calls[0].tools] == ["knowledge__ask"]
    failure = result.tools[0].capability.failure
    assert failure is not None and failure.code == "invalid_input"   # the old behaviour


def test_a_manifest_without_purpose_keeps_its_published_bytes() -> None:
    from knowledge.evolution import KnowledgeManifest

    data = {
        "metadata": {"identity": RS.model_dump(), "owner": {"type": "team", "id": "rf"},
                     "visibility": "organization"},
        "domain": "rf-instruments", "vault_ref": "C:/vault",
        "raw_sha256": "0" * 64, "decisions_sha256": "1" * 64, "content_sha256": "2" * 64,
    }
    plain = KnowledgeManifest.model_validate(data)
    assert "purpose" not in plain.model_dump(mode="json")
    assert "boundaries" not in plain.model_dump_json()
    described = KnowledgeManifest.model_validate(
        {**data, "purpose": "R&S specs", "boundaries": "no prices"})
    assert described.model_dump(mode="json")["purpose"] == "R&S specs"
