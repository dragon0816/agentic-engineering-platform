"""IT-owned execution: legacy owner/grant settings are not tool permission gates."""

import asyncio

from test_dispatch import Handler, Input, Output, grant, invocation, spec

from capabilities.contracts import CapabilitySpec
from capabilities.runtime import InstalledCapabilities, LocalPolicy
from common.assets import ExecutionDependencies
from workflow.dispatch import BridgeExecutor


def write_spec() -> CapabilitySpec:
    payload = spec().model_dump(mode="json")
    payload["side_effect"] = "write"
    payload["policy"] = {
        "approval_required": True,
        "required_permissions": ["sample.read"],
        "policy_refs": ["sample-policy"],
    }
    return CapabilitySpec.model_validate(payload)


def bridge(capability: CapabilitySpec, policy: LocalPolicy) -> tuple[BridgeExecutor, Handler]:
    handler = Handler()
    registry = InstalledCapabilities()
    registry.register(
        capability, handler, Input, Output, ExecutionDependencies(central_required=False)
    )
    return BridgeExecutor(registry, policy), handler


def test_a_person_runs_a_write_without_a_recorded_approval_in_owner_mode() -> None:
    run, handler = bridge(write_spec(), LocalPolicy((grant(approval_ref=None),), owner_mode=True))
    assert asyncio.run(run.execute(invocation())).status == "succeeded"
    assert len(handler.calls) == 1


def test_a_write_the_model_chose_runs_without_an_application_approval() -> None:
    run, handler = bridge(write_spec(), LocalPolicy((grant(),), owner_mode=True))
    result = asyncio.run(run.execute(invocation().model_copy(update={"origin": "model"})))
    assert result.status == "succeeded" and result.failure is None
    assert result.data == {"count": 2} and len(handler.calls) == 1


def test_a_read_the_model_chose_runs() -> None:
    run, handler = bridge(spec(), LocalPolicy((grant(),), owner_mode=True))
    result = asyncio.run(run.execute(invocation().model_copy(update={"origin": "model"})))
    assert result.status == "succeeded" and len(handler.calls) == 1


def test_execution_without_recorded_approval_does_not_depend_on_owner_mode() -> None:
    run, handler = bridge(write_spec(), LocalPolicy((grant(approval_ref=None),)))
    result = asyncio.run(run.execute(invocation()))
    assert result.status == "succeeded" and result.failure is None
    assert len(handler.calls) == 1


def test_legacy_grants_for_another_actor_do_not_control_the_call() -> None:
    run, handler = bridge(spec(), LocalPolicy((grant(actor="someone-else"),), owner_mode=True))
    result = asyncio.run(run.execute(invocation()))
    assert result.status == "succeeded" and result.failure is None
    assert len(handler.calls) == 1 and handler.calls[0].actor == "engineer"


def test_on_a_local_host_the_owner_needs_no_grants_file(tmp_path, capsys) -> None:  # type: ignore[no-untyped-def]
    """The product default: no grants.json, and the owner runs what is installed."""
    from test_host_wiring import host_json, membership_record, workspace

    from host_runtime.cli import main
    from host_runtime.host import build_runtime

    config, layout = workspace(
        tmp_path, membership=membership_record(), config_changes={"local_owner_grants": True}
    )
    assert not layout.grants.exists()
    target = layout.workspace_root / "notes.txt"
    assert main(["ask", "--config", str(host_json(tmp_path, config)), f"files.read {target}"]) == 0
    assert "succeeded" in capsys.readouterr().out
    with build_runtime(config) as runtime:
        assert runtime.agent.gateway.bridge.policy.owner_mode
