"""Host-admin data approval before an entire model request leaves this host."""

from collections.abc import Iterator

from agent.backend_contracts import BackendProfile
from agent.data_policy import BackendDataApproval, ContextMaterial, DataPolicy, OutboundContext
from common.execution import Failure
from models.contracts import ModelClient, ModelRequest, ModelResponse, ModelStreamEvent


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
            return ModelResponse(
                trace=request.trace, model_alias=request.model_alias, failure=failure
            )
        return self.client.generate(request)

    def stream(self, request: ModelRequest) -> Iterator[ModelStreamEvent]:
        failure = self._failure(request)
        if failure is not None:
            yield ModelStreamEvent(trace=request.trace, kind="failed", failure=failure)
            return
        yield from self.client.stream(request)
