"""Provider-neutral bounded decisions with an absent-by-default accelerator.

This module owns no model transport or security classification. An optional
accelerator may be constructed only after a trusted caller authorizes its
entire request for egress. The baseline provider remains the ordinary AEP
rule/Gateway path and is always available as a fallback.
"""

from __future__ import annotations

from collections.abc import Callable
from time import perf_counter
from typing import Generic, Literal, Protocol, Self, TypeVar
from urllib.parse import urlparse

from pydantic import Field, JsonValue, StrictBool, model_validator

from common.assets import SecretRef
from common.base import Contract, Symbol, Text

DecisionType = Literal[
    "route_selection",
    "intent_classification",
    "skill_selection",
    "context_classification",
    "retrieval_routing",
    "failure_classification",
    "result_evaluation",
    "next_action",
]
AcceleratorKind = Literal["NONE", "JEV"]
ACCELERABLE_TYPES = frozenset(
    {"intent_classification", "skill_selection", "retrieval_routing", "failure_classification"}
)
RequestT = TypeVar("RequestT")
RequestContra = TypeVar("RequestContra", contravariant=True)
ValueT = TypeVar("ValueT")


class DecisionAcceleratorConfig(Contract):
    """Local non-secret settings. `NONE` never constructs an accelerator."""

    provider: AcceleratorKind = "NONE"
    endpoint: Text | None = None
    credential: SecretRef | None = None
    model_profile: Symbol | None = None
    timeout_ms: int = Field(default=300, ge=1, le=5_000, strict=True)
    confidence_threshold: float = Field(default=0.9, ge=0, le=1)
    enabled_decision_types: tuple[DecisionType, ...] = ()

    @model_validator(mode="after")
    def explicit_non_secret_binding(self) -> Self:
        if len(set(self.enabled_decision_types)) != len(self.enabled_decision_types):
            raise ValueError("enabled decision types must be unique")
        if self.provider == "NONE":
            if any(
                (self.endpoint, self.credential, self.model_profile, self.enabled_decision_types)
            ):
                raise ValueError("NONE has no accelerator endpoint, credential or enabled types")
            return self
        if not self.endpoint or self.credential is None or not self.enabled_decision_types:
            raise ValueError("an accelerator needs endpoint, SecretRef and enabled types")
        if any(decision not in ACCELERABLE_TYPES for decision in self.enabled_decision_types):
            raise ValueError("execution, security, completion and planning stay on the baseline")
        parsed = urlparse(self.endpoint)
        loopback = parsed.hostname in {"127.0.0.1", "localhost", "::1"}
        if (
            (parsed.scheme != "https" and not (parsed.scheme == "http" and loopback))
            or not parsed.netloc
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("accelerator endpoint must be HTTPS or loopback without credentials")
        return self


class DecisionResult(Contract, Generic[ValueT]):
    """The normalized result; provider metadata is never an authorization."""

    decision_type: DecisionType
    value: ValueT
    accepted: StrictBool = True
    confidence: float | None = Field(default=None, ge=0, le=1)
    reason_code: Symbol
    provider_id: Symbol
    metadata: dict[Symbol, JsonValue] = Field(default_factory=dict)


class DecisionTrace(Contract):
    """Payload-free observability for one completed service decision."""

    decision_type: DecisionType
    provider_id: Symbol
    latency_ms: float = Field(ge=0)
    confidence: float | None = Field(default=None, ge=0, le=1)
    reason_code: Symbol
    fallback: StrictBool = False
    fallback_reason: Symbol | None = None

    @model_validator(mode="after")
    def fallback_has_reason(self) -> Self:
        if self.fallback != (self.fallback_reason is not None):
            raise ValueError("a fallback has one reason")
        return self


class DecisionEnvelope(Contract, Generic[ValueT]):
    result: DecisionResult[ValueT]
    trace: DecisionTrace

    @model_validator(mode="after")
    def same_decision(self) -> Self:
        if self.result.decision_type != self.trace.decision_type:
            raise ValueError("decision result and trace describe the same type")
        return self


class DecisionProvider(Protocol[RequestContra, ValueT]):
    """Trusted adapters decide one bounded question, not an execution loop."""

    provider_id: str

    def decide(self, request: RequestContra) -> DecisionResult[ValueT]: ...


class DecisionService(Generic[RequestT, ValueT]):
    """Use the exact baseline unless an authorized accelerator earns selection."""

    def __init__(
        self,
        *,
        baseline: DecisionProvider[RequestT, ValueT],
        config: DecisionAcceleratorConfig | None = None,
        accelerator_factory: Callable[[], DecisionProvider[RequestT, ValueT]] | None = None,
        authorize_accelerator: Callable[[RequestT], bool] | None = None,
        accept_accelerator: Callable[[RequestT, DecisionResult[ValueT]], bool] | None = None,
        observer: Callable[[DecisionTrace], None] | None = None,
        clock: Callable[[], float] = perf_counter,
    ) -> None:
        self.baseline = baseline
        self.config = config if config is not None else DecisionAcceleratorConfig()
        self._accelerator_factory = accelerator_factory
        self._authorize_accelerator = authorize_accelerator
        self._accept_accelerator = accept_accelerator
        self._observer = observer
        self._clock = clock

    def decide(self, request: RequestT, *, decision_type: DecisionType) -> DecisionEnvelope[ValueT]:
        started = self._clock()
        selected: DecisionResult[ValueT] | None = None
        fallback_reason: Symbol | None = None
        if self.config.provider != "NONE" and decision_type in self.config.enabled_decision_types:
            try:
                authorized = (
                    self._authorize_accelerator is not None
                    and self._authorize_accelerator(request)
                )
            except Exception:
                authorized = False
            if not authorized:
                fallback_reason = "accelerator_not_authorized"
            elif self._accelerator_factory is None:
                fallback_reason = "accelerator_not_installed"
            else:
                try:
                    provider = self._accelerator_factory()
                    candidate = provider.decide(request)
                    if (
                        candidate.decision_type != decision_type
                        or candidate.provider_id != provider.provider_id
                        or not candidate.accepted
                        or (
                            self._accept_accelerator is not None
                            and not self._accept_accelerator(request, candidate)
                        )
                    ):
                        fallback_reason = "accelerator_unsupported"
                    elif (
                        candidate.confidence is None
                        or candidate.confidence < self.config.confidence_threshold
                    ):
                        fallback_reason = "accelerator_low_confidence"
                    else:
                        selected = candidate
                except Exception:
                    # Provider exceptions may contain private payloads or secrets.
                    fallback_reason = "accelerator_error"
        if selected is None:
            selected = self.baseline.decide(request)
            if selected.decision_type != decision_type:
                raise ValueError("baseline decision type mismatch")
        trace = DecisionTrace(
            decision_type=decision_type,
            provider_id=selected.provider_id,
            latency_ms=max(0.0, (self._clock() - started) * 1_000),
            confidence=selected.confidence,
            reason_code=selected.reason_code,
            fallback=fallback_reason is not None,
            fallback_reason=fallback_reason,
        )
        if self._observer is not None:
            try:
                self._observer(trace)
            except Exception:
                # Loss of telemetry cannot change an authorized decision.
                pass
        return DecisionEnvelope(result=selected, trace=trace)
