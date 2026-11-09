"""Compose validated step objects without replacing either source's values."""

import asyncio
from pathlib import Path

import pytest
from pydantic import JsonValue
from test_workflow_harness import context

from capabilities.data_merge.handlers import SPEC, MergeHandler, MergeRequest, MergeResult
from capabilities.runtime import (
    CapabilityGrant,
    CapabilityInvocation,
    InstalledCapabilities,
    LocalPolicy,
)
from common.assets import ExecutionDependencies, WorkflowManifest
from common.base import Contract
from common.execution import RequestContext
from workflow.dispatch import BridgeExecutor
from workflow.engine import InstalledWorkflows, WorkflowEngine


def bridge() -> BridgeExecutor:
    installed = InstalledCapabilities()
    installed.register(
        SPEC,
        MergeHandler(),
        MergeRequest,
        MergeResult,
        ExecutionDependencies(central_required=False),
    )
    grant = CapabilityGrant(
        actor="owner",
        asset=SPEC.identity,
        permissions=("data.merge",),
        policy_refs=("data-policy",),
    )
    return BridgeExecutor(installed, LocalPolicy((grant,)))


@pytest.mark.parametrize(
    ("arguments", "code"),
    [
        ({"left": {"date": "private-A"}, "right": {"date": "private-B"}}, "data_merge_conflict"),
        ({"left": {str(i): i for i in range(1001)}, "right": {}}, "invalid_input"),
        ({"left": {}, "right": {str(i): i for i in range(1001)}}, "invalid_input"),
        ({"left": {}, "right": []}, "invalid_input"),
        ({"left": {}}, "invalid_input"),
        ({"left": {}, "right": {}, "overwrite": True}, "invalid_input"),
    ],
    ids=["conflict", "left-limit", "right-limit", "nonobject", "missing", "extra"],
)
def test_invalid_composition_never_exposes_values(
    arguments: dict[str, JsonValue], code: str
) -> None:
    result = asyncio.run(
        bridge().execute(
            CapabilityInvocation(
                context=context(),
                target=SPEC.identity,
                arguments=arguments,
            )
        )
    )
    assert result.status == "failed"
    assert result.failure is not None and result.failure.code == code
    assert result.data is None
    assert "private-" not in result.model_dump_json()


def test_equal_nested_duplicates_are_allowed_without_deep_merging() -> None:
    arguments: dict[str, JsonValue] = {
        "left": {"date": "09.11.2026", "shared": {"currency": ["USD", 32]}},
        "right": {"rows": [{"amount": 1}], "shared": {"currency": ["USD", 32]}},
    }
    result = asyncio.run(
        bridge().execute(
            CapabilityInvocation(
                context=context(),
                target=SPEC.identity,
                arguments=arguments,
            )
        )
    )
    assert result.status == "succeeded"
    assert result.data == {
        "data": {
            "date": "09.11.2026",
            "shared": {"currency": ["USD", 32]},
            "rows": [{"amount": 1}],
        }
    }
    assert arguments["left"] == {"date": "09.11.2026", "shared": {"currency": ["USD", 32]}}
    conflict = asyncio.run(
        bridge().execute(
            CapabilityInvocation(
                context=context(),
                target=SPEC.identity,
                arguments={"left": {"shared": {"a": 1}}, "right": {"shared": {"b": 2}}},
            )
        )
    )
    assert conflict.failure is not None and conflict.failure.code == "data_merge_conflict"


@pytest.mark.parametrize(
    ("left", "right"),
    [(True, 1), ({"nested": [True]}, {"nested": [1]}), (False, 0)],
    ids=["boolean-number", "nested-boolean-number", "false-zero"],
)
def test_boolean_and_number_duplicates_conflict(left: JsonValue, right: JsonValue) -> None:
    result = asyncio.run(
        bridge().execute(
            CapabilityInvocation(
                context=context(),
                target=SPEC.identity,
                arguments={"left": {"value": left}, "right": {"value": right}},
            )
        )
    )
    assert result.status == "failed"
    assert result.failure is not None and result.failure.code == "data_merge_conflict"


def test_equal_numeric_json_values_allow_integer_float_duplicates() -> None:
    result = asyncio.run(
        bridge().execute(
            CapabilityInvocation(
                context=context(),
                target=SPEC.identity,
                arguments={"left": {"value": 1}, "right": {"value": 1.0}},
            )
        )
    )
    assert result.status == "succeeded"
    assert result.data == {"data": {"value": 1.0}}


def test_real_host_registers_and_authorizes_merge_for_the_local_owner(tmp_path: Path) -> None:
    from test_host_wiring import membership_record, workspace

    from host_runtime.host import build_runtime

    config, layout = workspace(
        tmp_path,
        assets=False,
        membership=membership_record(),
        config_changes={"local_owner_grants": True},
    )
    with build_runtime(config, layout=layout) as runtime:
        executor = runtime.agent.gateway.bridge
        installed = executor.installed.get(SPEC.identity)
        assert installed is not None and installed.input_model is MergeRequest
        assert installed.spec.side_effect == "read"
        result = asyncio.run(
            executor.execute(
                CapabilityInvocation(
                    context=context().model_copy(update={"actor": config.device.registered_by}),
                    target=SPEC.identity,
                    origin="model",
                    arguments={"left": {"date": "09.11.2026"}, "right": {"rows": [[1]]}},
                )
            )
        )
        assert result.status == "succeeded"
        assert result.data == {"data": {"date": "09.11.2026", "rows": [[1]]}}


@pytest.mark.parametrize("source", ["run", "step"])
def test_workflow_report_receives_parameters_and_observed_rows(source: str) -> None:
    executor = bridge()
    echo_spec = SPEC.model_copy(
        update={
            "identity": SPEC.identity.model_copy(update={"namespace": "fixture", "name": "echo"}),
            "name": "fixture.echo",
        }
    )

    async def echo(context: RequestContext, inputs: Contract) -> Contract:
        return MergeResult.model_validate(inputs)

    executor.installed.register(
        echo_spec, echo, MergeResult, MergeResult, ExecutionDependencies(central_required=False)
    )
    executor.policy.add(
        CapabilityGrant(
            actor="owner",
            asset=echo_spec.identity,
            permissions=("data.merge",),
            policy_refs=("data-policy",),
        )
    )
    left: dict[str, JsonValue] = (
        {"source": "run"}
        if source == "run"
        else {"source": "step", "step_index": 0, "path": ["data"]}
    )
    manifest = WorkflowManifest.model_validate(
        {
            "metadata": {
                "identity": {
                    "namespace": "engineering",
                    "name": "composed-report",
                    "version": "1.0.0",
                },
                "owner": {"type": "user", "id": "owner"},
                "visibility": "private",
                "lifecycle": "published",
            },
            "description": "Compose prepared parameters and observed rows.",
            "execution": {"mode": "local"},
            "dependencies": {"central_required": False},
            "input_contract": "fixture.in.v1",
            "output_contract": "fixture.out.v1",
            "parameters": [
                {"name": "date", "label": "Date", "kind": "text"},
                {"name": "rate", "label": "Rate", "kind": "number"},
            ],
            "steps": [
                {"capability": echo_spec.identity, "inputs": {"data": {"source": "run"}}},
                {
                    "capability": echo_spec.identity,
                    "inputs": {
                        "data": {
                            "source": "fixed",
                            "value": {"rows": [{"order": "O1", "amount": 5}]},
                        }
                    },
                },
                {
                    "capability": SPEC.identity,
                    "inputs": {
                        "left": left,
                        "right": {"source": "step", "step_index": 1, "path": ["data"]},
                    },
                },
                {
                    "capability": echo_spec.identity,
                    "inputs": {
                        "data": {
                            "source": "step",
                            "step_index": 2,
                            "path": ["data"],
                        }
                    },
                },
            ],
        }
    )
    workflows = InstalledWorkflows()
    workflows.register(manifest)
    result = asyncio.run(
        WorkflowEngine(workflows, executor).execute(
            context(),
            manifest.metadata.identity,
            {"date": "09.11.2026", "rate": 32.5},
        )
    )
    assert result.run.status == "succeeded" and result.run.completed_steps == 4
    assert result.step_results[-1].data == {
        "data": {
            "date": "09.11.2026",
            "rate": 32.5,
            "rows": [{"order": "O1", "amount": 5}],
        }
    }
