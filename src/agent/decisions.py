"""Provider-neutral bounded decisions with an absent-by-default accelerator.

This module owns no model transport or security classification. An optional
accelerator may be constructed only after a trusted caller authorizes its
entire request for egress. The baseline provider remains the ordinary AEP
rule/Gateway path and is always available as a fallback.
"""

from __future__ import annotations

import threading
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


class AcceleratorEgressApproval(Contract):
    """The owner's approval to send what an accelerator receives off this
    machine. Today the JEV adapter sends only the latest user message."""

    approval_ref: Text
    scope: Literal["latest_user_message"] = "latest_user_message"


class DecisionAcceleratorConfig(Contract):
    """Local non-secret settings. `NONE` never constructs an accelerator."""

    provider: AcceleratorKind = "NONE"
    endpoint: Text | None = None
    credential: SecretRef | None = None
    model_profile: Symbol | None = None
    timeout_ms: int = Field(default=300, ge=1, le=5_000, strict=True)
    confidence_threshold: float = Field(default=0.9, ge=0, le=1)
    enabled_decision_types: tuple[DecisionType, ...] = ()
    # `shadow` asks the accelerator in the background and records what it
    # would have chosen; the baseline decides every request.
    mode: Literal["active", "shadow"] = "active"
    # Skill selection keeps the most likely commands up to this many (1 = the
    # single best), until their probability reaches the threshold.
    skill_max_tools: int = Field(default=1, ge=1, le=10, strict=True)
    egress_approval: AcceleratorEgressApproval | None = None

    @model_validator(mode="after")
    def explicit_non_secret_binding(self) -> Self:
        if len(set(self.enabled_decision_types)) != len(self.enabled_decision_types):
            raise ValueError("enabled decision types must be unique")
        if self.provider == "NONE":
            if any(
                (self.endpoint, self.credential, self.model_profile, self.enabled_decision_types,
                 self.egress_approval)
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


ShadowOutcome = Literal[
    "would_select", "kept_catalog", "low_confidence", "unsupported", "error",
    "not_authorized", "not_installed",
]
_SHADOW_OUTCOMES: dict[str | None, ShadowOutcome] = {
    None: "would_select",
    "accelerator_low_confidence": "low_confidence",
    "accelerator_unsupported": "unsupported",
    "accelerator_not_authorized": "not_authorized",
    "accelerator_not_installed": "not_installed",
}


class DecisionShadow(Contract):
    """What an accelerator in shadow mode would have done; payload-free."""

    decision_type: DecisionType
    outcome: ShadowOutcome
    provider_id: Symbol | None = None
    value: JsonValue = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    reason_code: Symbol | None = None
    latency_ms: float = Field(ge=0)
    metadata: dict[Symbol, JsonValue] = Field(default_factory=dict)


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
        shadow_observer: Callable[[RequestT, DecisionShadow], None] | None = None,
        clock: Callable[[], float] = perf_counter,
    ) -> None:
        self.baseline = baseline
        self.config = config if config is not None else DecisionAcceleratorConfig()
        self._accelerator_factory = accelerator_factory
        self._authorize_accelerator = authorize_accelerator
        self._accept_accelerator = accept_accelerator
        self._observer = observer
        self._shadow_observer = shadow_observer
        self._shadows: list[threading.Thread] = []
        self._clock = clock

    def _accelerate(
        self, request: RequestT, decision_type: DecisionType
    ) -> tuple[DecisionResult[ValueT] | None, DecisionResult[ValueT] | None, Symbol | None]:
        """(admitted, candidate, fallback reason) from the configured accelerator."""
        try:
            authorized = (
                self._authorize_accelerator is not None and self._authorize_accelerator(request)
            )
        except Exception:
            authorized = False
        if not authorized:
            return None, None, "accelerator_not_authorized"
        if self._accelerator_factory is None:
            return None, None, "accelerator_not_installed"
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
                return None, candidate, "accelerator_unsupported"
        except Exception:
            # Provider exceptions may contain private payloads or secrets.
            return None, None, "accelerator_error"
        if candidate.confidence is None or candidate.confidence < self.config.confidence_threshold:
            return None, candidate, "accelerator_low_confidence"
        return candidate, candidate, None

    def _shadow(self, request: RequestT, decision_type: DecisionType) -> None:
        started = self._clock()
        _, candidate, reason = self._accelerate(request, decision_type)
        value = None if candidate is None else candidate.value
        outcome = _SHADOW_OUTCOMES.get(reason, "error")
        if candidate is not None and not candidate.accepted:
            # The accelerator itself chose to keep the whole catalogue.
            outcome = "kept_catalog"
        record = DecisionShadow(
            decision_type=decision_type,
            outcome=outcome,
            provider_id=None if candidate is None else candidate.provider_id,
            value=list(value) if isinstance(value, tuple) else value,
            confidence=None if candidate is None else candidate.confidence,
            reason_code=None if candidate is None else candidate.reason_code,
            latency_ms=max(0.0, (self._clock() - started) * 1_000),
            metadata={} if candidate is None else dict(candidate.metadata),
        )
        if self._shadow_observer is not None:
            try:
                self._shadow_observer(request, record)
            except Exception:
                # Loss of shadow telemetry cannot affect the conversation.
                pass

    def drain_shadows(self, timeout: float = 10.0) -> None:
        """Wait for background shadow decisions (tests, shutdown)."""
        for thread in list(self._shadows):
            thread.join(timeout)
        self._shadows = [thread for thread in self._shadows if thread.is_alive()]

    def decide(self, request: RequestT, *, decision_type: DecisionType) -> DecisionEnvelope[ValueT]:
        started = self._clock()
        selected: DecisionResult[ValueT] | None = None
        fallback_reason: Symbol | None = None
        enabled = (
            self.config.provider != "NONE" and decision_type in self.config.enabled_decision_types
        )
        if enabled and self.config.mode == "shadow":
            # Off the request's path: the person never waits for the shadow.
            thread = threading.Thread(
                target=self._shadow, args=(request, decision_type), daemon=True,
                name="decision-shadow",
            )
            self._shadows = [item for item in self._shadows if item.is_alive()] + [thread]
            thread.start()
        elif enabled:
            selected, _, fallback_reason = self._accelerate(request, decision_type)
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
