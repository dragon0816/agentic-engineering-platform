"""JEV shadow mode: the accelerator answers in the background, the baseline decides.

Shadow mode collects what Laya (a self-hosted JEV SystemOne) would have chosen
next to the tools the model actually called, without changing any answer and
without slowing the turn. Nothing is sent without the owner's egress approval.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError
from test_decision_service import Provider, configured
from test_jev import Transport, answer, candidate, config

from agent.decisions import DecisionAcceleratorConfig, DecisionService, DecisionShadow
from agent.jev import JEVSkillSelectionProvider
from evaluation.jev_shadow_report import load, narrowed, report
from host_runtime.jev_shadow import JevShadowLog, skill_accelerator
from models.credentials import StaticCredentials


def shadowed(**changes: Any) -> DecisionAcceleratorConfig:
    return configured().model_copy(update={"mode": "shadow", **changes})


def test_shadow_mode_answers_with_the_baseline_and_records_the_accelerator() -> None:
    baseline = Provider("baseline")
    accelerator = Provider("jev", confidence=0.95)
    gate = threading.Event()
    seen: list[tuple[str, DecisionShadow]] = []

    def slow_factory() -> Provider:
        gate.wait(5)  # the turn must not wait for this
        return accelerator

    service = DecisionService[str, str](
        baseline=baseline,
        config=shadowed(),
        accelerator_factory=slow_factory,
        authorize_accelerator=lambda _: True,
        shadow_observer=lambda request, record: seen.append((request, record)),
    )
    envelope = service.decide("request", decision_type="intent_classification")
    assert envelope.result.provider_id == "baseline" and not envelope.trace.fallback
    assert seen == []  # still waiting on the slow accelerator
    gate.set()
    service.drain_shadows()
    ((request, record),) = seen
    assert request == "request"
    assert record.outcome == "would_select" and record.value == "jev"
    assert record.confidence == 0.95 and record.latency_ms >= 0


@pytest.mark.parametrize(
    ("authorized", "factory", "outcome"),
    [
        (False, None, "not_authorized"),
        (True, None, "not_installed"),
    ],
)
def test_shadow_records_why_nothing_was_asked(authorized: bool, factory: Any, outcome: str) -> None:
    seen: list[DecisionShadow] = []
    service = DecisionService[str, str](
        baseline=Provider("baseline"),
        config=shadowed(),
        accelerator_factory=factory,
        authorize_accelerator=lambda _: authorized,
        shadow_observer=lambda _r, record: seen.append(record),
    )
    service.decide("request", decision_type="intent_classification")
    service.drain_shadows()
    assert [record.outcome for record in seen] == [outcome]


def test_low_confidence_and_errors_are_recorded_not_raised() -> None:
    seen: list[DecisionShadow] = []

    def broken() -> Provider:
        raise RuntimeError("secret-bearing failure")

    for factory in (lambda: Provider("jev", confidence=0.4), broken):
        service = DecisionService[str, str](
            baseline=Provider("baseline"),
            config=shadowed(),
            accelerator_factory=factory,
            authorize_accelerator=lambda _: True,
            shadow_observer=lambda _r, record: seen.append(record),
        )
        service.decide("request", decision_type="intent_classification")
        service.drain_shadows()
    assert [record.outcome for record in seen] == ["low_confidence", "error"]
    assert "secret" not in json.dumps([record.model_dump(mode="json") for record in seen])


def test_an_egress_approval_is_not_a_none_setting() -> None:
    with pytest.raises(ValidationError):
        DecisionAcceleratorConfig(egress_approval={"approval_ref": "owner"})
    assert configured().mode == "active" and configured().skill_max_tools == 1


def test_the_adapter_can_keep_the_most_likely_tools() -> None:
    reply = answer("1")
    body = json.loads(reply.body)
    body["answers"]["skill_candidate"]["probabilities"] = {"0": 0.02, "1": 0.6, "2": 0.38}
    reply.body = json.dumps(body).encode()
    provider = JEVSkillSelectionProvider(
        config(), lambda: "t", transport=Transport(reply), max_tools=3
    )
    result = provider.decide(candidate())
    assert result.value == ("search", "draft") and result.confidence == pytest.approx(0.98)
    assert result.reason_code == "likely_skill_candidates"
    first = json.loads(reply.body)
    first["answers"]["skill_candidate"]["probabilities"] = {"0": 0.7, "1": 0.2, "2": 0.1}
    reply.body = json.dumps(first).encode()
    preserved = JEVSkillSelectionProvider(
        config(), lambda: "t", transport=Transport(reply), max_tools=3
    ).decide(candidate())
    assert preserved.accepted is False and preserved.reason_code == "preserve_catalog"


def test_the_host_sends_nothing_without_the_owners_egress_approval() -> None:
    jev = DecisionAcceleratorConfig(
        provider="JEV",
        endpoint="http://127.0.0.1:18000/v1/systemone",
        credential={"name": "jev_api_key"},
        model_profile="laya-rl-agent",
        enabled_decision_types=("skill_selection",),
        mode="shadow",
    )
    factory, authorize = skill_accelerator(jev, StaticCredentials({"jev_api_key": "t"}))
    assert factory is not None and authorize is not None
    assert authorize(candidate()) is False
    approved = jev.model_copy(update={"egress_approval": {"approval_ref": "owner-2026-10-05"}})
    _, authorize = skill_accelerator(approved, StaticCredentials({"jev_api_key": "t"}))
    assert authorize is not None and authorize(candidate()) is True
    assert skill_accelerator(DecisionAcceleratorConfig(), StaticCredentials({})) == (None, None)


def test_the_shadow_log_pairs_choices_with_tool_use_and_holds_no_text(tmp_path: Path) -> None:
    from agent.gateway import ConversationToolExecution, GatewayConversationResult
    from common.execution import Failure

    log = JevShadowLog(tmp_path / "jev-shadow.jsonl")
    request = candidate()
    log.decision(
        request,
        DecisionShadow(
            decision_type="skill_selection",
            outcome="would_select",
            provider_id="jev",
            value=["search"],
            confidence=0.95,
            reason_code="single_skill_candidate",
            latency_ms=230,
            metadata={
                "probabilities": {"catalog": 0.02, "search": 0.95, "draft": 0.03},
                "choice_confidence": 0.95,
            },
        ),
    )
    log.conversation(
        GatewayConversationResult(
            trace=request.context.trace,
            status="answered",
            text="the answer text",
            model_turns=2,
            tools=(
                ConversationToolExecution(
                    call_id="c1",
                    name="search",
                    failure=Failure(code="denied", message="not run"),
                ),
            ),
        )
    )
    written = (tmp_path / "jev-shadow.jsonl").read_text(encoding="utf-8")
    assert "Find a report" not in written and "the answer text" not in written
    pairs = load(tmp_path / "jev-shadow.jsonl")
    assert len(pairs) == 1
    assert narrowed(pairs[0][0], 0.9, 1) == ["search"]
    assert narrowed(pairs[0][0], 0.96, 1) is None
    summary = report(pairs)
    row = next(r for r in summary["replay"] if r["max_tools"] == 1 and r["threshold"] == 0.9)
    assert row["agreed_with_model"] == 1 and row["precision"] == 1.0
    assert summary["shadow_latency_ms"]["p50"] == 230


def test_a_host_wires_the_shadow_and_refuses_an_unmapped_credential(tmp_path: Path) -> None:
    from test_host_wiring import ready

    from host_runtime.host import HostError, build_runtime

    accelerator = {
        "provider": "JEV",
        "endpoint": "http://127.0.0.1:18000/v1/systemone",
        "credential": {"name": "jev_api_key"},
        "model_profile": "laya-rl-agent",
        "enabled_decision_types": ["skill_selection"],
        "mode": "shadow",
    }
    config, layout = ready(
        tmp_path / "unmapped", config_changes={"decision_accelerator": accelerator}
    )
    with pytest.raises(HostError, match="credential_unmapped"):
        build_runtime(config, layout=layout)
    config, layout = ready(
        tmp_path / "mapped",
        config_changes={
            "decision_accelerator": accelerator,
            "credentials": [{"secret": "jev_api_key", "environment_variable": "AEP_JEV_API_KEY"}],
        },
    )
    with build_runtime(config, layout=layout) as runtime:
        decisions = runtime.agent.gateway.skill_decisions
        assert decisions.config.mode == "shadow"
        assert decisions._accelerator_factory is not None
        assert decisions._authorize_accelerator is not None
        assert decisions._authorize_accelerator(candidate()) is False  # no approval yet


def test_each_finished_turn_reaches_the_conversation_observer() -> None:
    import asyncio

    from test_gateway import Handler, gateway, request
    from test_routing import FakeModel

    from models.contracts import ModelMessage, ModelRequest, ModelResponse

    class AnswerModel(FakeModel):
        def generate(self, item: ModelRequest) -> ModelResponse:
            self.calls.append(item)
            return ModelResponse(trace=item.trace, model_alias=item.model_alias, text="Ready")

    app = gateway(Handler(), AnswerModel())
    seen: list[Any] = []
    app._conversation_observer = seen.append
    result = asyncio.run(app.converse(request("Hi"), (ModelMessage(role="user", text="Hi"),)))
    assert seen == [result] and result.status == "answered"


def test_an_accelerator_keeping_the_catalogue_is_recorded_as_such() -> None:
    class Keeping(Provider):
        def decide(self, request: str) -> Any:
            return super().decide(request).model_copy(update={"accepted": False})

    seen: list[DecisionShadow] = []
    service = DecisionService[str, str](
        baseline=Provider("baseline"),
        config=shadowed(),
        accelerator_factory=lambda: Keeping("jev", confidence=0.95),
        authorize_accelerator=lambda _: True,
        shadow_observer=lambda _r, record: seen.append(record),
    )
    service.decide("request", decision_type="intent_classification")
    service.drain_shadows()
    assert [record.outcome for record in seen] == ["kept_catalog"]
