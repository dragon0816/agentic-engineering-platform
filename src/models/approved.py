"""Host-admin data approval before an entire model request leaves this host."""

import time
from collections.abc import Iterator

import telemetry.recorder as telemetry
from agent.backend_contracts import BackendProfile
from agent.data_policy import BackendDataApproval, ContextMaterial, DataPolicy, OutboundContext
from common.execution import Failure
from models.contracts import ModelClient, ModelRequest, ModelResponse, ModelStreamEvent


def _observed(request: ModelRequest, response: ModelResponse, elapsed_ms: float) -> None:
    """`llm.completed` for every model call the host makes (telemetry v0.2).
    Usage the provider did not report stays null, never zero."""
    telemetry.note_llm(response.input_tokens, response.output_tokens)
    telemetry.emit(
        "llm.completed",
        status="failed" if response.failure is not None else "succeeded",
        attributes={
            "model_alias": request.model_alias,
            "duration_ms": response.duration_ms
            if response.duration_ms is not None
            else round(elapsed_ms, 1),
            "input_tokens": response.input_tokens or None,
            "output_tokens": response.output_tokens or None,
            "max_output_tokens": request.max_output_tokens,
            "tools_offered": len(request.tools),
            "tool_calls": len(response.tool_calls),
            "failure_code": None if response.failure is None else response.failure.code,
        },
    )


class ApprovedModelClient:
    """Treat every model request as UNCLASSIFIED until field provenance exists.

    The wrapper sees the complete ModelRequest before the provider adapter
    serializes it. An admin approval tied to the routed endpoint must include
    UNCLASSIFIED; a URL or credential alone never grants data transfer.
    """

    def __init__(self, client: ModelClient, approval: BackendDataApproval | None) -> None:
        self.client = client
        self.policy = DataPolicy(() if approval is None else (approval,))
        self.profile = BackendProfile(backend_id="gateway", kind="model", harness="aep")

    def _failure(self, request: ModelRequest) -> Failure | None:
        context = OutboundContext(
            materials=(
                ContextMaterial(
                    material_id=request.trace.request_id,
                    origin="system",
                    text="complete outbound model request",
                ),
            )
        )
        decision = self.policy.decide(self.profile, context)
        if decision.allowed:
            return None
        return Failure(
            code=decision.code,
            message="This host has no matching administrator-approved internal Gateway data class",
        )

    def generate(self, request: ModelRequest) -> ModelResponse:
        failure = self._failure(request)
        if failure is not None:
            response = ModelResponse(
                trace=request.trace, model_alias=request.model_alias, failure=failure
            )
            _observed(request, response, 0.0)
            return response
        started = time.perf_counter()
        response = self.client.generate(request)
        _observed(request, response, (time.perf_counter() - started) * 1000)
        return response

    def stream(self, request: ModelRequest) -> Iterator[ModelStreamEvent]:
        failure = self._failure(request)
        if failure is not None:
            yield ModelStreamEvent(trace=request.trace, kind="failed", failure=failure)
            return
        yield from self.client.stream(request)
