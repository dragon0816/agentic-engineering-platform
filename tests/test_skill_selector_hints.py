"""Skill `selector_hint`: what a Skill selector (JEV SystemOne) is told a tool is for.

Measured on the self-hosted Laya service (docs/JEV_ADAPTER_READINESS.md,
2026-10-05): the Gateway's tool descriptions (full instructions plus a shared
"Executes installed ..." suffix) buried what told tools apart; short bilingual
hints raised held-out accuracy from 50 % to 80 %.
"""

from __future__ import annotations

import json

from test_jev import Reply, Transport, answer, candidate, config

from agent.jev import JEVSkillSelectionProvider, _distinct
from agent.skills import SkillManifest
from capabilities.company_agent.manifest import knowledge_skill
from capabilities.weekly_report.manifest import weekly_skill
from evaluation.jev_live import SKILLS_V3_CORPUS, run_public_benchmark


def test_a_manifest_without_a_hint_keeps_its_published_bytes() -> None:
    data = weekly_skill().model_dump(mode="json")
    assert data["selector_hint"].startswith("SDE weekly report")
    data.pop("selector_hint")
    unhinted = SkillManifest.model_validate(data)
    assert "selector_hint" not in unhinted.model_dump(mode="json")
    assert "selector_hint" not in unhinted.model_dump_json()
    assert knowledge_skill().metadata.identity.version == "1.1.0"   # a hinted new version


def test_the_adapter_prefers_the_hint_and_strips_the_shared_suffix() -> None:
    assert _distinct(
        "Run the report. Executes installed workflow engineering/x@1.0.0."
    ) == "Run the report."
    request = candidate()
    names = [tool.name for tool in request.tools]
    hinted = request.model_copy(update={"selector_hints": {names[0]: "週報 weekly report"}})
    transport = Transport(answer("1"))
    JEVSkillSelectionProvider(config(), lambda: "t", transport=transport).decide(hinted)
    criteria = json.loads(transport.calls[0][1])["questions"]["skill_candidate"]["criteria"]
    assert criteria["1"] == "週報 weekly report"
    assert "閒聊" in criteria["0"]                       # concrete preserve option


def test_the_gateway_passes_each_hinted_tool(tmp_path) -> None:  # type: ignore[no-untyped-def]
    from agent.gateway import SkillCandidateRequest

    request = candidate()
    names = [tool.name for tool in request.tools]
    try:
        SkillCandidateRequest.model_validate(
            {**request.model_dump(mode="json"), "selector_hints": {"not-a-tool": "x"}}
        )
    except ValueError as error:
        assert "installed tools" in str(error)
    else:  # pragma: no cover
        raise AssertionError("a hint for an unknown tool must be refused")
    assert names


def test_the_v3_corpus_sends_hints_and_keeps_unhinted_tools_readable() -> None:
    calls = []

    class Recording(Transport):
        def send(self, url, body, headers, timeout_s):  # type: ignore[no-untyped-def]
            calls.append(json.loads(body))
            return Reply(200, json.dumps({
                "answers": {"skill_candidate": {"type": "choice", "choice": "0",
                                                "confidence": 0.5}},
                "usage": {"input_tokens": 1, "output_tokens": 0},
            }).encode())

    run_public_benchmark(corpus=SKILLS_V3_CORPUS, model="laya-rl-agent",
                         credential=lambda: "t", transport=Recording(answer("0")))
    assert len(calls) == 46
    criteria = calls[0]["questions"]["skill_candidate"]["criteria"]
    assert any(text.startswith("SDE weekly report") for text in criteria.values())
    assert not any("Executes installed" in text for text in criteria.values())


def test_a_conversation_hands_the_selector_each_skills_hint() -> None:
    import asyncio

    from test_gateway import FakeModel, Handler, gateway, request

    from agent.decisions import DecisionAcceleratorConfig, DecisionService
    from agent.gateway import SkillCandidateRequest, _valid_skill_subset
    from models.contracts import ModelMessage, ModelRequest, ModelResponse

    class AnswerModel(FakeModel):
        def generate(self, item: ModelRequest) -> ModelResponse:
            self.calls.append(item)
            return ModelResponse(trace=item.trace, model_alias=item.model_alias, text="Ready")

    app = gateway(Handler(), AnswerModel())
    registry = app.router.commands.skills
    (skill,) = [item for item in registry.discover("engineering") if item.alias == "release"]
    hinted = skill.model_copy(update={"selector_hint": "release 發佈 check and package"})
    key = (skill.metadata.identity.namespace, skill.alias)
    registry._skills[key] = hinted.model_dump_json()   # the installed manifest, now hinted
    seen: list[SkillCandidateRequest] = []

    def authorize(item: SkillCandidateRequest) -> bool:
        seen.append(item)
        return False

    app.skill_decisions = DecisionService[SkillCandidateRequest, tuple[str, ...]](
        baseline=app.skill_decisions.baseline,
        config=DecisionAcceleratorConfig(
            provider="JEV", endpoint="http://127.0.0.1:9797/v1",
            credential={"name": "jev_token"}, enabled_decision_types=("skill_selection",),
        ),
        authorize_accelerator=authorize,
        accelerator_factory=lambda: None,  # type: ignore[arg-type,return-value]
        accept_accelerator=_valid_skill_subset,
    )
    asyncio.run(app.converse(request("Check"), (ModelMessage(role="user", text="Check"),)))
    assert seen and seen[0].selector_hints == {
        "release__check": "release 發佈 check and package",
        "release__package": "release 發佈 check and package",
    }
