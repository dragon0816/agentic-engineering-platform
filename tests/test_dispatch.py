import asyncio

import pytest
from pydantic import Field

from capabilities.contracts import CapabilitySpec
from capabilities.runtime import (
    CapabilityGrant,
    CapabilityInvocation,
    InstalledCapabilities,
    LocalPolicy,
)
from common.assets import AssetIdentity, ExecutionDependencies, SecretRef
from common.base import Contract
from common.execution import AttachmentRef, RequestContext, TraceIdentifiers
from workflow.dispatch import BridgeExecutor


class Input(Contract):
    count: int = Field(ge=0)


class Output(Contract):
    count: int


class Handler:
    def __init__(self) -> None:
        self.calls: list[RequestContext] = []

    async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
        self.calls.append(context)
        assert isinstance(inputs, Input)
        return Output(count=inputs.count + 1)


def spec() -> CapabilitySpec:
    return CapabilitySpec.model_validate(
        {
            "identity": {"namespace": "sample", "name": "count", "version": "1.0.0"},
            "name": "sample.count",
            "description": "Pure count fixture",
            "input_contract": "count.input.v1",
            "output_contract": "count.output.v1",
            "side_effect": "read",
            "policy": {"required_permissions": ["sample.read"], "policy_refs": ["sample-policy"]},
        }
    )


def invocation() -> CapabilityInvocation:
    return CapabilityInvocation(
        context=RequestContext(
            trace=TraceIdentifiers(trace_id="trace-1", request_id="request-1", span_id="span-1"),
            actor="engineer",
            namespace="sample",
            channel="test",
            message="count",
            attachments=(
                AttachmentRef(
                    file_id="file-1",
                    filename="sample.txt",
                    resource_ref="opaque-1",
                    size_bytes=1,
                    media_type="text/plain",
                ),
            ),
        ),
        target=spec().identity,
        arguments={"count": 1},
    )


def grant(**changes: object) -> CapabilityGrant:
    return CapabilityGrant.model_validate(
        {
            "actor": "engineer",
            "asset": spec().identity,
            "permissions": ["sample.read"],
            "policy_refs": ["sample-policy"],
            "approval_ref": "execution-approval-1",
            **changes,
        }
    )


def installed(handler: Handler) -> InstalledCapabilities:
    registry = InstalledCapabilities()
    registry.register(spec(), handler, Input, Output, ExecutionDependencies(central_required=False))
    return registry


def test_default_deny_never_calls_handler() -> None:
    handler = Handler()
    bridge = BridgeExecutor(installed(handler))
    result = asyncio.run(bridge.execute(invocation()))
    assert result.failure is not None and result.failure.code == "permission_denied"
    assert handler.calls == []


@pytest.mark.parametrize(
    "changes",
    [
        {"actor": "other"},
        {"permissions": []},
        {"approval_ref": None},
        {"policy_refs": ["wrong"]},
        {"asset": {"namespace": "other", "name": "count", "version": "1.0.0"}},
    ],
)
def test_permissions_and_execution_approval_are_enforced(changes: dict[str, object]) -> None:
    handler = Handler()
    bridge = BridgeExecutor(installed(handler), LocalPolicy((grant(**changes),)))
    assert asyncio.run(bridge.execute(invocation())).status == "failed"
    assert handler.calls == []


def test_authorized_dispatch_preserves_context_and_safe_trace() -> None:
    handler = Handler()
    bridge = BridgeExecutor(installed(handler), LocalPolicy((grant(),)))
    call = invocation()
    result = asyncio.run(bridge.execute(call))
    assert result.data == {"count": 2}
    assert result.trace == call.context.trace
    assert handler.calls[0].attachments == call.context.attachments
    assert "opaque-1" not in bridge.events[0].model_dump_json()
    assert bridge.events[0].status == "succeeded"


@pytest.mark.parametrize(
    "arguments", [{"count": "1"}, {"count": -1}, {"count": 1, "token": "fake"}]
)
def test_invalid_input_is_rejected_before_handler(arguments: dict[str, object]) -> None:
    handler = Handler()
    bridge = BridgeExecutor(installed(handler), LocalPolicy((grant(),)))
    call = CapabilityInvocation.model_validate(
        {**invocation().model_dump(), "arguments": arguments}
    )
    result = asyncio.run(bridge.execute(call))
    assert result.failure is not None and result.failure.code == "invalid_input"
    assert handler.calls == []


def test_dependency_unavailability_is_explicit() -> None:
    handler = Handler()
    registry = InstalledCapabilities()
    registry.register(
        spec(),
        handler,
        Input,
        Output,
        ExecutionDependencies.model_validate(
            {
                "central_required": True,
                "central_services": [{"name": "central", "required": True}],
            }
        ),
    )
    bridge = BridgeExecutor(registry, LocalPolicy((grant(),)))
    result = asyncio.run(bridge.execute(invocation()))
    assert result.status == "unavailable"
    assert result.failure is not None and result.failure.code == "needs_connectivity"
    assert handler.calls == []
    connected = BridgeExecutor(registry, LocalPolicy((grant(),)), services=frozenset({"central"}))
    assert asyncio.run(connected.execute(invocation())).status == "succeeded"


def test_handler_error_is_sanitized_and_not_retried() -> None:
    class Broken(Handler):
        async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
            self.calls.append(context)
            raise RuntimeError("password=synthetic-secret")

    handler = Broken()
    bridge = BridgeExecutor(installed(handler), LocalPolicy((grant(),)))
    result = asyncio.run(bridge.execute(invocation()))
    assert result.status == "failed"
    assert "synthetic-secret" not in result.model_dump_json()
    assert len(handler.calls) == 1


def test_timeout_is_structured_and_not_retried() -> None:
    class Slow(Handler):
        async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
            self.calls.append(context)
            await asyncio.Event().wait()
            return Output(count=0)

    handler = Slow()
    bridge = BridgeExecutor(installed(handler), LocalPolicy((grant(),)), timeout_seconds=0.01)
    result = asyncio.run(bridge.execute(invocation()))
    assert result.failure is not None and result.failure.code == "timeout"
    assert len(handler.calls) == 1


def test_output_is_validated() -> None:
    class BadOutput(Handler):
        async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
            return Output(count=0).model_copy(update={"count": "bad"})

    bridge = BridgeExecutor(installed(BadOutput()), LocalPolicy((grant(),)))
    result = asyncio.run(bridge.execute(invocation()))
    assert result.failure is not None and result.failure.code == "invalid_output"


def test_duplicate_install_and_unknown_target_fail_explicitly() -> None:
    registry = installed(Handler())
    with pytest.raises(ValueError):
        registry.register(
            spec(), Handler(), Input, Output, ExecutionDependencies(central_required=False)
        )
    call = CapabilityInvocation.model_validate(
        {
            **invocation().model_dump(),
            "target": AssetIdentity(namespace="missing", name="tool", version="1.0.0"),
        }
    )
    assert asyncio.run(BridgeExecutor(registry).execute(call)).status == "unavailable"


def test_secret_and_missing_local_requirements_do_not_execute() -> None:
    handler = Handler()
    for dependencies, secrets, code in [
        (
            ExecutionDependencies(central_required=False, local_capabilities=("missing",)),
            (),
            "missing_local_capability",
        ),
        (
            ExecutionDependencies(central_required=False),
            (SecretRef(name="credential"),),
            "secret_resolution_unavailable",
        ),
    ]:
        registry = InstalledCapabilities()
        registry.register(spec(), handler, Input, Output, dependencies, secrets)
        result = asyncio.run(
            BridgeExecutor(registry, LocalPolicy((grant(),))).execute(invocation())
        )
        assert result.failure is not None and result.failure.code == code
    assert handler.calls == []


def test_technical_review_alone_does_not_authorize_execution() -> None:
    handler = Handler()
    data = spec().model_dump()
    data["policy"].update(status="approved", reviewer="technical-owner", evidence="review-1")
    registry = InstalledCapabilities()
    registry.register(
        CapabilitySpec.model_validate(data),
        handler,
        Input,
        Output,
        ExecutionDependencies(central_required=False),
    )
    assert asyncio.run(BridgeExecutor(registry).execute(invocation())).status == "failed"
    assert handler.calls == []


def test_end_to_end_route_then_authorized_bridge_dispatch() -> None:
    from agent.routing import CommandRouter, RequestRouter
    from agent.skills import SkillManifest, SkillRegistry

    registry = SkillRegistry()
    registry.register(
        SkillManifest.model_validate(
            {
                "metadata": {
                    "identity": spec().identity,
                    "owner": {"type": "user", "id": "engineer"},
                    "visibility": "private",
                },
                "alias": "count",
                "instructions": "Inspect a count using the local pure fixture.",
                "commands": [{"name": "inspect", "target": spec().identity}],
            }
        )
    )
    context = invocation().context.model_copy(update={"message": "count.inspect"})
    route = RequestRouter(CommandRouter(registry)).route(context)
    assert route.decision.target is not None

    class EmptyInput(Contract):
        pass

    async def pure(context: RequestContext, inputs: Contract) -> Contract:
        return Output(count=len(context.attachments))

    local = InstalledCapabilities()
    local.register(spec(), pure, EmptyInput, Output, ExecutionDependencies(central_required=False))
    bridge = BridgeExecutor(local, LocalPolicy((grant(),)))
    call = CapabilityInvocation(
        context=context, target=route.decision.target, arguments=route.arguments
    )
    result = asyncio.run(bridge.execute(call))
    assert result.data == {"count": 1}
    assert result.trace == route.trace
