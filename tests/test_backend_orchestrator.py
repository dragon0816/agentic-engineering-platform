"""Backend selection and Gateway adaptation retain the existing execution boundary."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import ValidationError

from agent.backend_contracts import (
    MAX_CONVERSATION_TURNS,
    BackendHealth,
    BackendProfile,
    GatewayConversationRequest,
)
from agent.backends.gateway import GatewayModelBackend
from agent.gateway import ConversationToolExecution, GatewayConversationResult
from agent.orchestrator import BackendRouter, BackendSelectionError
from common.execution import Failure, RequestContext, TraceIdentifiers
from models.contracts import ModelMessage


def context() -> RequestContext:
    return RequestContext(
        trace=TraceIdentifiers(trace_id="trace-1", request_id="request-1", span_id="span-1"),
        actor="engineer",
        namespace="engineering",
        message="What can you do?",
        channel="local",
    )


def test_backend_profile_separates_model_and_native_harness() -> None:
    profile = BackendProfile(backend_id="gateway", kind="model", harness="aep", tools=True)
    assert BackendProfile.model_validate_json(profile.model_dump_json()) == profile
    with pytest.raises(ValidationError, match="model backend uses the AEP harness"):
        BackendProfile(backend_id="bad", kind="model", harness="native")
    with pytest.raises(ValidationError, match="agent backend uses a native harness"):
        BackendProfile(backend_id="bad", kind="agent", harness="aep")


class StubBackend:
    def __init__(self, backend_id: str, state: str = "unknown") -> None:
        self.profile = BackendProfile(backend_id=backend_id, kind="model", harness="aep")
        self.state = state

    def health(self) -> BackendHealth:
        return BackendHealth(backend_id=self.profile.backend_id, state=self.state)

    async def execute(self, request: GatewayConversationRequest) -> GatewayConversationResult:
        raise AssertionError("selection must not execute a backend")


def test_router_selects_only_exact_eligible_and_non_unavailable_backend() -> None:
    gateway = StubBackend("gateway")
    native = StubBackend("native", "unavailable")
    router = BackendRouter((gateway, native))
    assert router.select("gateway", eligible_ids=("gateway",)) is gateway
    with pytest.raises(BackendSelectionError, match="not_eligible"):
        router.select("native", eligible_ids=("gateway",))
    with pytest.raises(BackendSelectionError, match="unavailable"):
        router.select("native", eligible_ids=("gateway", "native"))
    with pytest.raises(BackendSelectionError, match="not_registered"):
        router.select("invented", eligible_ids=("gateway", "invented"))
    with pytest.raises(ValueError, match="duplicate backend"):
        BackendRouter((gateway, StubBackend("gateway")))


def test_router_rejects_mismatched_health_identity() -> None:
    backend = StubBackend("gateway")
    mismatch = BackendHealth(backend_id="other", state="ready")
    with patch.object(backend, "health", return_value=mismatch):
        with pytest.raises(BackendSelectionError, match="health_mismatch"):
            BackendRouter((backend,)).select("gateway", eligible_ids=("gateway",))


def test_gateway_adapter_forwards_full_request_and_preserves_failure_evidence() -> None:
    from agent.gateway import Gateway
    from agent.routing import CommandRouter, RequestRouter
    from agent.skills import SkillRegistry
    from capabilities.runtime import InstalledCapabilities, LocalPolicy
    from workflow.dispatch import BridgeExecutor
    from workflow.engine import InstalledWorkflows, WorkflowEngine

    bridge = BridgeExecutor(InstalledCapabilities(), LocalPolicy(()))
    gateway = Gateway(
        RequestRouter(CommandRouter(SkillRegistry())),
        bridge,
        WorkflowEngine(InstalledWorkflows(), bridge),
    )
    result = GatewayConversationResult(
        trace=context().trace,
        status="failed",
        text="The configured model could not answer this turn.",
        model_turns=2,
        tools=(
            ConversationToolExecution(
                call_id="call-1",
                name="skill__run",
                failure=Failure(code="permission_denied", message="Denied"),
            ),
        ),
        failure=Failure(code="model_unavailable", message="Unavailable"),
    )
    history = (ModelMessage(role="user", text="What can you do?"),)
    request = GatewayConversationRequest(
        context=context(), history=history, persona_guidance="Speak briefly."
    )
    adapter = GatewayModelBackend(gateway)
    assert adapter.health().state == "unknown"
    with patch.object(gateway, "converse", new=AsyncMock(return_value=result)) as converse:
        observed = asyncio.run(adapter.execute(request))
    assert observed is result
    converse.assert_awaited_once_with(
        context(),
        history,
        persona_guidance="Speak briefly.",
        allowed_tools=None,
        max_turns=MAX_CONVERSATION_TURNS,
        max_history_messages=12,
    )
