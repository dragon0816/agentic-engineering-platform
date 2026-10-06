"""A Skill selector never narrows the tools to coding (owner, 2026-10-06).

Live JEV shadow records ranked coding tools first for Knowledge questions
(low confidence, so nothing changed). In active mode such a narrowing would
leave the model only coding; it must fall back to the whole catalogue.
"""

from __future__ import annotations

import asyncio

from test_gateway import Report, request
from test_jev import config
from test_knowledge_vault_tools import Recording
from test_routing import FakeModel

from agent.decisions import DecisionResult
from agent.gateway import Gateway, SkillCandidateRequest
from agent.routing import CommandRouter, RequestRouter
from agent.skills import SkillManifest, SkillRegistry
from capabilities.knowledge_query.handlers import KNOWLEDGE_QUERY_SPEC
from capabilities.runtime import InstalledCapabilities, LocalPolicy
from common.assets import ExecutionDependencies
from knowledge.evolution import KnowledgeQueryRequest
from models.contracts import ModelMessage, ModelRequest, ModelResponse
from workflow.dispatch import BridgeExecutor
from workflow.engine import InstalledWorkflows, WorkflowEngine


class Picks:
    provider_id = "jev-test"

    def __init__(self, names: tuple[str, ...]) -> None:
        self.names = names

    def decide(self, item: SkillCandidateRequest) -> DecisionResult[tuple[str, ...]]:
        return DecisionResult(decision_type="skill_selection", value=self.names, confidence=0.99,
                              reason_code="picked", provider_id=self.provider_id)


class Seen(FakeModel):
    def generate(self, item: ModelRequest) -> ModelResponse:
        self.calls.append(item)
        return ModelResponse(trace=item.trace, model_alias=item.model_alias, text="ok")


def skill(alias: str, name: str) -> SkillManifest:
    return SkillManifest.model_validate({
        "metadata": {"identity": {"namespace": "engineering", "name": name, "version": "1.0.0"},
                     "owner": {"type": "team", "id": "engineering"},
                     "visibility": "organization", "lifecycle": "published"},
        "alias": alias, "instructions": f"{alias} tool",
        "commands": [{"name": "ask", "kind": "capability",
                      "target": KNOWLEDGE_QUERY_SPEC.identity.model_dump()}],
        "default_command": "ask",
    })


def tools_offered(picked: tuple[str, ...], excluded: frozenset[str]) -> list[str]:
    skills = SkillRegistry()
    skills.register(skill("knowledge", "knowledge-query"))
    skills.register(skill("coding", "coding"))
    installed = InstalledCapabilities()
    installed.register(KNOWLEDGE_QUERY_SPEC, Recording(), KnowledgeQueryRequest, Report,
                       ExecutionDependencies(central_required=False))
    bridge = BridgeExecutor(installed, LocalPolicy(()))
    model = Seen()
    gateway = Gateway(
        RequestRouter(CommandRouter(skills), model=model, decision_accelerator=config()),
        bridge, WorkflowEngine(InstalledWorkflows(), bridge),
        skill_accelerator=lambda: Picks(picked),  # type: ignore[arg-type,return-value]
        skill_authorizer=lambda _request: True,
        accelerator_excluded_aliases=excluded,
    )
    asyncio.run(gateway.converse(request("CMP180 是什麼？"),
                                 (ModelMessage(role="user", text="CMP180 是什麼？"),)))
    return sorted(tool.name for tool in model.calls[0].tools)


def test_a_narrowing_to_coding_falls_back_to_every_tool() -> None:
    assert tools_offered(("coding__ask",), frozenset({"coding"})) == ["coding__ask", "knowledge__ask"]


def test_a_narrowing_without_coding_still_applies() -> None:
    assert tools_offered(("knowledge__ask",), frozenset({"coding"})) == ["knowledge__ask"]


def test_without_an_exclusion_the_selector_behaves_as_before() -> None:
    assert tools_offered(("coding__ask",), frozenset()) == ["coding__ask"]

