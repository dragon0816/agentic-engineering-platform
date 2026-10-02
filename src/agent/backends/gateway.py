"""Keep the existing Gateway conversation behavior behind a backend adapter."""

from agent.backend_contracts import BackendHealth, BackendProfile, GatewayConversationRequest
from agent.gateway import Gateway, GatewayConversationResult


class GatewayModelBackend:
    def __init__(self, gateway: Gateway) -> None:
        self.gateway = gateway
        self._profile = BackendProfile(
            backend_id="gateway", kind="model", harness="aep", tools=True
        )

    @property
    def profile(self) -> BackendProfile:
        return self._profile

    def health(self) -> BackendHealth:
        # Configuration is not evidence that a remote model is reachable.
        return BackendHealth(backend_id=self.profile.backend_id, state="unknown")

    async def execute(self, request: GatewayConversationRequest) -> GatewayConversationResult:
        return await self.gateway.converse(
            request.context,
            request.history,
            persona_guidance=request.persona_guidance,
            allowed_tools=(
                None if request.allowed_tools is None else frozenset(request.allowed_tools)
            ),
            max_turns=request.max_turns,
        )
