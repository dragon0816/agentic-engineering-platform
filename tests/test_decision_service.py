"""The optional decision accelerator never changes the unconfigured path."""

import pytest
from pydantic import ValidationError

from agent.decisions import (
    DecisionAcceleratorConfig,
    DecisionResult,
    DecisionService,
    DecisionTrace,
)


class Provider:
    def __init__(self, provider_id: str, confidence: float | None = None) -> None:
        self.provider_id = provider_id
        self.confidence = confidence
        self.calls: list[str] = []

    def decide(self, request: str) -> DecisionResult[str]:
        self.calls.append(request)
        return DecisionResult(
            decision_type="intent_classification",
            value=self.provider_id,
            confidence=self.confidence,
            reason_code="selected",
            provider_id=self.provider_id,
        )


def configured() -> DecisionAcceleratorConfig:
    return DecisionAcceleratorConfig(
        provider="JEV",
        endpoint="http://127.0.0.1:9797/v1",
        credential={"name": "jev_token"},
        enabled_decision_types=("intent_classification",),
        confidence_threshold=0.9,
    )


def test_none_calls_baseline_once_without_constructing_or_authorizing_accelerator() -> None:
    baseline = Provider("rule")
    seen: list[DecisionTrace] = []

    def forbidden() -> Provider:
        raise AssertionError("NONE must not construct an accelerator")

    def forbidden_authorizer(_: str) -> bool:
        raise AssertionError("NONE must not authorize an accelerator")

    service = DecisionService[str, str](
        baseline=baseline,
        accelerator_factory=forbidden,
        authorize_accelerator=forbidden_authorizer,
        observer=seen.append,
    )
    outcome = service.decide("sensitive input", decision_type="intent_classification")
    assert outcome.result.value == "rule"
    assert baseline.calls == ["sensitive input"]
    assert outcome.trace.provider_id == "rule"
    assert not outcome.trace.fallback
    assert "sensitive input" not in outcome.trace.model_dump_json()
    assert seen == [outcome.trace]


def test_configured_but_disabled_type_stays_on_baseline() -> None:
    baseline = Provider("rule")
    config = configured().model_copy(update={"enabled_decision_types": ("failure_classification",)})
    service = DecisionService[str, str](
        config=config,
        baseline=baseline,
        accelerator_factory=lambda: pytest.fail("disabled type constructed JEV"),
    )
    assert service.decide("text", decision_type="intent_classification").result.value == "rule"
    assert baseline.calls == ["text"]


def test_authorization_precedes_accelerator_construction_and_denial_falls_back() -> None:
    baseline = Provider("gateway_llm")
    seen: list[str] = []

    def authorize(request: str) -> bool:
        seen.append(request)
        return False

    service = DecisionService[str, str](
        config=configured(),
        baseline=baseline,
        accelerator_factory=lambda: pytest.fail("denied data reached JEV"),
        authorize_accelerator=authorize,
    )
    outcome = service.decide("confidential", decision_type="intent_classification")
    assert seen == ["confidential"]
    assert baseline.calls == ["confidential"]
    assert outcome.trace.fallback_reason == "accelerator_not_authorized"


@pytest.mark.parametrize("confidence", [None, 0.3, 0.89])
def test_low_or_unknown_confidence_falls_back(confidence: float | None) -> None:
    baseline = Provider("gateway_llm")
    accelerator = Provider("jev", confidence)
    service = DecisionService[str, str](
        config=configured(),
        baseline=baseline,
        accelerator_factory=lambda: accelerator,
        authorize_accelerator=lambda _: True,
    )
    outcome = service.decide("text", decision_type="intent_classification")
    assert outcome.result.value == "gateway_llm"
    assert accelerator.calls == ["text"] and baseline.calls == ["text"]
    assert outcome.trace.fallback_reason == "accelerator_low_confidence"


def test_authorized_high_confidence_uses_accelerator_without_baseline() -> None:
    baseline = Provider("gateway_llm")
    accelerator = Provider("jev", 0.95)
    service = DecisionService[str, str](
        config=configured(),
        baseline=baseline,
        accelerator_factory=lambda: accelerator,
        authorize_accelerator=lambda _: True,
    )
    outcome = service.decide("public", decision_type="intent_classification")
    assert outcome.result.value == "jev"
    assert outcome.trace.provider_id == "jev" and not outcome.trace.fallback
    assert baseline.calls == []


def test_unsupported_accelerator_decision_falls_back() -> None:
    class Unsupported(Provider):
        def decide(self, request: str) -> DecisionResult[str]:
            self.calls.append(request)
            return DecisionResult(
                decision_type="intent_classification",
                value="unknown",
                accepted=False,
                confidence=0.99,
                reason_code="unsupported",
                provider_id=self.provider_id,
            )

    baseline = Provider("gateway_llm")
    accelerator = Unsupported("jev")
    service = DecisionService[str, str](
        config=configured(),
        baseline=baseline,
        accelerator_factory=lambda: accelerator,
        authorize_accelerator=lambda _: True,
    )
    outcome = service.decide("public", decision_type="intent_classification")
    assert outcome.result.value == "gateway_llm"
    assert outcome.trace.fallback_reason == "accelerator_unsupported"


def test_invalid_accelerator_value_falls_back_before_use() -> None:
    baseline = Provider("gateway_llm")
    accelerator = Provider("jev", 0.99)
    service = DecisionService[str, str](
        config=configured(),
        baseline=baseline,
        accelerator_factory=lambda: accelerator,
        authorize_accelerator=lambda _: True,
        accept_accelerator=lambda _request, result: result.value == "installed",
    )
    outcome = service.decide("public", decision_type="intent_classification")
    assert outcome.result.value == "gateway_llm"
    assert outcome.trace.fallback_reason == "accelerator_unsupported"
    assert baseline.calls == ["public"] and accelerator.calls == ["public"]


def test_accelerator_exception_is_sanitized_and_baseline_continues() -> None:
    baseline = Provider("gateway_llm")

    def broken() -> Provider:
        raise RuntimeError("secret_value=synthetic")

    service = DecisionService[str, str](
        config=configured(),
        baseline=baseline,
        accelerator_factory=broken,
        authorize_accelerator=lambda _: True,
    )
    outcome = service.decide("public", decision_type="intent_classification")
    assert outcome.result.value == "gateway_llm"
    assert outcome.trace.fallback_reason == "accelerator_error"
    assert "synthetic" not in outcome.model_dump_json()


def test_configured_without_an_installed_provider_uses_the_baseline() -> None:
    baseline = Provider("gateway_llm")
    service = DecisionService[str, str](
        config=configured(), baseline=baseline, authorize_accelerator=lambda _: True
    )
    outcome = service.decide("public", decision_type="intent_classification")
    assert outcome.result.value == "gateway_llm"
    assert outcome.trace.fallback_reason == "accelerator_not_installed"


def test_observer_failure_cannot_change_a_decision() -> None:
    baseline = Provider("rule")

    def broken(_: DecisionTrace) -> None:
        raise RuntimeError("observability unavailable")

    service = DecisionService[str, str](baseline=baseline, observer=broken)
    assert service.decide("text", decision_type="intent_classification").result.value == "rule"


def test_config_requires_non_secret_explicit_jev_binding() -> None:
    assert DecisionAcceleratorConfig().provider == "NONE"
    with pytest.raises(ValidationError):
        DecisionAcceleratorConfig(provider="JEV")
    with pytest.raises(ValidationError):
        DecisionAcceleratorConfig(
            provider="NONE", enabled_decision_types=("intent_classification",)
        )
    with pytest.raises(ValidationError):
        DecisionAcceleratorConfig.model_validate(
            {**configured().model_dump(mode="json"), "endpoint": "http://remote.example/v1"}
        )
    with pytest.raises(ValidationError):
        DecisionAcceleratorConfig.model_validate(
            {
                **configured().model_dump(mode="json"),
                "endpoint": "https://decision.example/v1?api_key=synthetic",
            }
        )
    with pytest.raises(ValidationError):
        DecisionAcceleratorConfig.model_validate(
            {
                **configured().model_dump(mode="json"),
                "enabled_decision_types": ["context_classification"],
            }
        )
    with pytest.raises(ValidationError):
        DecisionAcceleratorConfig.model_validate(
            {**configured().model_dump(mode="json"), "enabled_decision_types": ["route_selection"]}
        )

