"""Offline wire and fallback checks against TypeSafe's SystemOne choice schema."""

import json
from collections.abc import Iterator, Mapping

import pytest

from agent.decisions import DecisionAcceleratorConfig, DecisionService
from agent.gateway import SkillCandidateRequest, _InstalledSkillCandidates, _valid_skill_subset
from agent.jev import JEVSkillSelectionProvider
from common.execution import RequestContext, TraceIdentifiers
from models.contracts import ModelMessage, ModelRequest, ModelRequirements, ModelTool


class Reply:
    def __init__(self, status: int, body: bytes) -> None:
        self.status = status
        self.body = body
        self.closed = False

    def chunks(self) -> Iterator[bytes]:
        yield self.body

    def close(self) -> None:
        self.closed = True


class Transport:
    def __init__(self, reply: Reply) -> None:
        self.reply = reply
        self.calls: list[tuple[str, bytes, Mapping[str, str], float]] = []

    def send(
        self, url: str, body: bytes, headers: Mapping[str, str], timeout_s: float
    ) -> Reply:
        self.calls.append((url, body, headers, timeout_s))
        return self.reply


def candidate() -> SkillCandidateRequest:
    trace = TraceIdentifiers(trace_id="trace", request_id="request", span_id="span")
    return SkillCandidateRequest(
        context=RequestContext(
            trace=trace,
            actor="tester",
            namespace="engineering",
            channel="test",
            message="Find a report",
        ),
        initial_request=ModelRequest(
            trace=trace,
            model_alias="company",
            messages=(
                ModelMessage(role="system", text="Synthetic PUBLIC persona"),
                ModelMessage(role="user", text="Find a report"),
            ),
            requirements=ModelRequirements(tool_calling=True),
            tools=(
                ModelTool(name="search", description="Search PUBLIC reports", input_contract="q"),
                ModelTool(name="draft", description="Draft a PUBLIC note", input_contract="note"),
            ),
        ),
    )


def config() -> DecisionAcceleratorConfig:
    return DecisionAcceleratorConfig(
        provider="JEV",
        endpoint="https://api.typesafe.ai/v1/systemone",
        credential={"name": "jev_token"},
        model_profile="jev-latest",
        timeout_ms=300,
        enabled_decision_types=("skill_selection",),
    )


def answer(choice: str, confidence: float = 0.96) -> Reply:
    return Reply(
        200,
        json.dumps(
            {
                "model": "jev-latest",
                "answers": {
                    "skill_candidate": {
                        "type": "choice",
                        "choice": choice,
                        "confidence": confidence,
                        "probabilities": {"0": 0.01, "1": 0.96, "2": 0.03},
                    }
                },
                "usage": {"input_tokens": 100, "output_tokens": 1},
            }
        ).encode(),
    )


def service(transport: Transport) -> DecisionService[SkillCandidateRequest, tuple[str, ...]]:
    return DecisionService(
        baseline=_InstalledSkillCandidates(),
        config=config(),
        authorize_accelerator=lambda _: True,
        accelerator_factory=lambda: JEVSkillSelectionProvider(
            config(), lambda: "synthetic-token", transport=transport
        ),
        accept_accelerator=_valid_skill_subset,
    )


def test_official_choice_wire_and_high_confidence_selection() -> None:
    reply = answer("1")
    transport = Transport(reply)
    result = service(transport).decide(candidate(), decision_type="skill_selection")
    assert result.result.value == ("search",)
    assert result.result.metadata == {"input_tokens": 100, "output_tokens": 1}
    assert result.trace.provider_id == "jev"
    assert not result.trace.fallback
    url, raw, headers, timeout = transport.calls[0]
    assert url == "https://api.typesafe.ai/v1/systemone"
    assert timeout == 0.3
    assert headers["Authorization"] == "Bearer synthetic-token"
    sent = json.loads(raw)
    assert sent["model"] == "jev-latest"
    assert sent["state"]["messages"][0]["text"] == "Synthetic PUBLIC persona"
    assert sent["questions"]["skill_candidate"]["criteria"]["1"] == "Search PUBLIC reports"
    assert "synthetic-token" not in result.model_dump_json()
    assert reply.closed


@pytest.mark.parametrize(
    ("reply", "fallback"),
    [
        (answer("0"), "accelerator_unsupported"),
        (answer("9"), "accelerator_error"),
        (answer("1", 0.4), "accelerator_low_confidence"),
        (Reply(401, b"secret error"), "accelerator_error"),
        (Reply(200, b"invalid json"), "accelerator_error"),
    ],
)
def test_invalid_or_refused_jev_answer_preserves_baseline(reply: Reply, fallback: str) -> None:
    transport = Transport(reply)
    result = service(transport).decide(candidate(), decision_type="skill_selection")
    assert result.result.value == ("search", "draft")
    assert result.trace.fallback_reason == fallback
    assert "secret error" not in result.model_dump_json()
    assert reply.closed


def test_denial_prevents_client_and_secret_resolution() -> None:
    result = DecisionService[SkillCandidateRequest, tuple[str, ...]](
        baseline=_InstalledSkillCandidates(),
        config=config(),
        authorize_accelerator=lambda _: False,
        accelerator_factory=lambda: pytest.fail("JEV must not be constructed"),
    ).decide(candidate(), decision_type="skill_selection")
    assert result.result.value == ("search", "draft")
    assert result.trace.fallback_reason == "accelerator_not_authorized"


def test_transport_timeout_falls_back_without_exposing_exception() -> None:
    class TimeoutTransport:
        def send(
            self, url: str, body: bytes, headers: Mapping[str, str], timeout_s: float
        ) -> Reply:
            raise TimeoutError("synthetic private marker")

    provider = JEVSkillSelectionProvider(
        config(), lambda: "synthetic-token", transport=TimeoutTransport()
    )
    outcome = DecisionService[SkillCandidateRequest, tuple[str, ...]](
        baseline=_InstalledSkillCandidates(),
        config=config(),
        authorize_accelerator=lambda _: True,
        accelerator_factory=lambda: provider,
        accept_accelerator=_valid_skill_subset,
    ).decide(candidate(), decision_type="skill_selection")
    assert outcome.result.value == ("search", "draft")
    assert outcome.trace.fallback_reason == "accelerator_error"
    assert "synthetic private marker" not in outcome.model_dump_json()


def test_blank_credential_prevents_network_call() -> None:
    transport = Transport(answer("1"))
    provider = JEVSkillSelectionProvider(config(), lambda: " ", transport=transport)
    with pytest.raises(ValueError, match="credential is unavailable"):
        provider.decide(candidate())
    assert transport.calls == []
