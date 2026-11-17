"""IT owns tool usability; AEP checks contracts and actual outcomes, not grants."""

from __future__ import annotations

import asyncio

import pytest
from test_dispatch import Handler, Input, Output, grant, invocation, spec

from capabilities.contracts import CapabilitySpec
from capabilities.runtime import InstalledCapabilities, LocalPolicy
from common.assets import AssetIdentity, ExecutionDependencies
from common.base import Contract
from common.execution import RequestContext
from workflow.dispatch import BridgeExecutor


@pytest.mark.parametrize("effect", ["read", "write", "execute", "external_side_effect"])
@pytest.mark.parametrize("origin", ["person", "model"])
@pytest.mark.parametrize("owner_mode", [False, True])
@pytest.mark.parametrize("legacy_grant", [False, True])
def test_it_owned_execution_needs_no_application_grant_or_approval(
    effect: str, origin: str, owner_mode: bool, legacy_grant: bool
) -> None:
    raw = spec().model_dump(mode="json")
    raw["side_effect"] = effect
    raw["policy"]["approval_required"] = True
    capability = CapabilitySpec.model_validate(raw)
    handler = Handler()
    installed = InstalledCapabilities()
    installed.register(
        capability, handler, Input, Output, ExecutionDependencies(central_required=False)
    )
    old = (grant(actor="old-user", permissions=[], approval_ref=None),) if legacy_grant else ()
    bridge = BridgeExecutor(installed, LocalPolicy(old, owner_mode=owner_mode))
    call = invocation().model_copy(update={"origin": origin})

    result = asyncio.run(bridge.execute(call))

    assert result.status == "succeeded", result
    assert result.data == {"count": 2}
    assert handler.calls == [call.context]
    assert result.handler_invoked
    assert result.trace == call.context.trace


def test_no_grant_does_not_hide_an_actual_environment_error() -> None:
    class Denied:
        calls = 0

        async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
            self.calls += 1
            raise PermissionError("private OS error text must not escape")

    handler = Denied()
    installed = InstalledCapabilities()
    installed.register(
        spec(), handler, Input, Output, ExecutionDependencies(central_required=False)
    )
    result = asyncio.run(BridgeExecutor(installed).execute(invocation()))

    assert handler.calls == 1
    assert result.status == "failed" and result.failure is not None
    assert result.failure.code == "handler_error"
    assert result.handler_invoked
    assert "private OS error" not in result.model_dump_json()


def test_without_a_grant_malformed_arguments_still_never_run() -> None:
    handler = Handler()
    installed = InstalledCapabilities()
    installed.register(
        spec(), handler, Input, Output, ExecutionDependencies(central_required=False)
    )
    call = invocation().model_copy(update={"arguments": {"count": -1}})
    result = asyncio.run(BridgeExecutor(installed).execute(call))

    assert result.status == "failed" and result.failure is not None
    assert result.failure.code == "invalid_input"
    assert not result.handler_invoked and handler.calls == []


def test_no_application_permission_does_not_invent_an_unknown_tool() -> None:
    missing = AssetIdentity(namespace="sample", name="not-installed", version="1.0.0")
    call = invocation().model_copy(update={"target": missing})
    result = asyncio.run(BridgeExecutor(InstalledCapabilities()).execute(call))

    assert result.failure is not None and result.failure.code == "capability_not_installed"
    assert not result.handler_invoked
