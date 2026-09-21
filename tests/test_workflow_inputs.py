"""Contract-first coverage for explicit input selection and governed chaining."""

import asyncio
from typing import Any

import pytest
from pydantic import JsonValue, ValidationError
from test_dispatch import Handler, Input, Output, grant, spec
from test_engine import context, manifest

from capabilities.runtime import InstalledCapabilities, LocalPolicy
from common.assets import ExecutionDependencies, WorkflowManifest, WorkflowStep
from common.base import Contract
from common.execution import RequestContext
from workflow.dispatch import BridgeExecutor
from workflow.engine import InstalledWorkflows, WorkflowEngine


def step(reference: dict[str, Any]) -> dict[str, Any]:
    return {"capability": spec().identity.model_dump(), "inputs": {"count": reference}}


def flow_for(steps: list[Any]) -> WorkflowManifest:
    data = manifest([spec().identity]).model_dump()
    data["steps"] = steps
    return WorkflowManifest.model_validate(data)


def runner_for(flow: WorkflowManifest, handler: Handler | None = None) -> WorkflowEngine:
    installed = InstalledCapabilities()
    installed.register(
        spec(), handler or Handler(), Input, Output, ExecutionDependencies(central_required=False)
    )
    workflows = InstalledWorkflows()
    workflows.register(flow)
    return WorkflowEngine(workflows, BridgeExecutor(installed, LocalPolicy((grant(),))))


def test_mixed_steps_round_trip_and_chain() -> None:
    flow = flow_for(
        [
            spec().identity.model_dump(),
            step({"source": "step", "step_index": 0, "path": ["count"]}),
            step({"source": "run", "path": ["count"]}),
        ]
    )
    assert WorkflowManifest.model_validate_json(flow.model_dump_json()) == flow
    result = asyncio.run(runner_for(flow).execute(context(), flow.metadata.identity, {"count": 1}))
    assert result.run.status == "succeeded"
    assert [r.data for r in result.step_results] == [{"count": 2}, {"count": 3}, {"count": 2}]
    assert all(r.trace == context().trace for r in result.step_results)


@pytest.mark.parametrize(
    "reference",
    [
        {"source": "step", "step_index": 0, "path": []},  # self
        {"source": "step", "step_index": 1, "path": []},  # future
        {"source": "step", "step_index": -1, "path": []},
        {"source": "step", "step_index": True, "path": []},
        {"source": "step", "step_index": "0", "path": []},
        {"source": "step", "path": []},
        {"source": "run", "step_index": 0, "path": []},
        {"source": "run", "path": [-1]},
        {"source": "run", "path": [True]},
        {"source": "run", "path": [1.5]},
        {"source": "literal", "value": "credential"},
        {"source": "run", "path": [], "expression": "eval()"},
    ],
)
def test_invalid_references_rejected(reference: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        flow_for([step(reference)])


def test_missing_mapping_is_not_implicit_pass_through() -> None:
    with pytest.raises(ValidationError):
        flow_for([{"capability": spec().identity.model_dump()}])
    with pytest.raises(ValidationError):
        flow_for([{"capability": spec().identity.model_dump(), "inputs": {}, "extra": 1}])


def test_missing_later_run_input_preflights_without_any_execution() -> None:
    handler = Handler()
    flow = flow_for(
        [
            spec().identity.model_dump(),
            step({"source": "run", "path": ["private-missing-key"]}),
        ]
    )
    runner = runner_for(flow, handler)
    result = asyncio.run(runner.execute(context(), flow.metadata.identity, {"count": 1}))
    assert result.run.status == "needs_input"
    assert result.run.failure is not None and result.run.failure.code == "workflow_input_missing"
    assert runner.get(result.run.run_id) is None
    assert handler.calls == []
    assert "private-missing-key" not in result.model_dump_json()


@pytest.mark.parametrize("path", [["absent"], ["count", "child"], [0]])
def test_missing_output_stops_before_dispatch(path: list[Any]) -> None:
    handler = Handler()
    flow = flow_for(
        [
            spec().identity.model_dump(),
            step({"source": "step", "step_index": 0, "path": path}),
            spec().identity.model_dump(),
        ]
    )
    result = asyncio.run(
        runner_for(flow, handler).execute(context(), flow.metadata.identity, {"count": 1})
    )
    assert result.run.status == "needs_input"
    assert result.run.failure is not None and result.run.failure.code == "workflow_input_missing"
    assert result.run.completed_steps == 1
    assert len(result.step_results) == len(handler.calls) == 1


@pytest.mark.parametrize("value", [None, "1", {"count": 1}])
def test_selected_value_still_requires_bridge_input_validation(value: Any) -> None:
    handler = Handler()
    flow = flow_for([step({"source": "run", "path": ["items", 0]})])
    result = asyncio.run(
        runner_for(flow, handler).execute(context(), flow.metadata.identity, {"items": [value]})
    )
    assert result.run.status == "failed"
    assert result.run.failure is not None and result.run.failure.code == "invalid_input"
    assert handler.calls == []  # Null is present, not a missing reference.


def test_array_and_exact_object_key_selection() -> None:
    flow = flow_for([step({"source": "run", "path": ["a.b/", 0, "0"]})])
    result = asyncio.run(
        runner_for(flow).execute(
            context(), flow.metadata.identity, {"a.b/": [{"0": 9}], "unused": True}
        )
    )
    assert result.run.status == "succeeded"
    assert result.step_results[0].data == {"count": 10}


def test_step_failure_prevents_later_reference_resolution() -> None:
    flow = flow_for(
        [
            step({"source": "run", "path": ["count"]}),
            step({"source": "step", "step_index": 0, "path": ["missing"]}),
        ]
    )
    result = asyncio.run(runner_for(flow).execute(context(), flow.metadata.identity, {"count": -1}))
    assert result.run.failure is not None and result.run.failure.code == "invalid_input"
    assert len(result.step_results) == 1


def test_explicit_empty_inputs_does_not_forward_run_arguments() -> None:
    handler = Handler()
    flow = flow_for([{"capability": spec().identity.model_dump(), "inputs": {}}])
    result = asyncio.run(
        runner_for(flow, handler).execute(context(), flow.metadata.identity, {"count": 1})
    )
    assert result.run.failure is not None and result.run.failure.code == "invalid_input"
    assert handler.calls == []


@pytest.mark.parametrize("source", ["run", "step"])
def test_empty_path_selects_whole_source_with_null_preserved(source: str) -> None:
    class Wrapped(Contract):
        value: JsonValue

    async def echo(context: RequestContext, inputs: Contract) -> Contract:
        return inputs

    ref = {"source": source, **({"step_index": 0} if source == "step" else {})}
    flow = flow_for(
        [
            spec().identity.model_dump(),
            {"capability": spec().identity.model_dump(), "inputs": {"value": ref}},
        ]
    )
    installed = InstalledCapabilities()
    installed.register(
        spec(), echo, Wrapped, Wrapped, ExecutionDependencies(central_required=False)
    )
    workflows = InstalledWorkflows()
    workflows.register(flow)
    runner = WorkflowEngine(workflows, BridgeExecutor(installed, LocalPolicy((grant(),))))
    result = asyncio.run(runner.execute(context(), flow.metadata.identity, {"value": None}))
    assert result.run.status == "succeeded"
    assert result.step_results[-1].data == {"value": {"value": None}}


@pytest.mark.parametrize("path", [["items", 5], ["items", "0"], ["missing"], ["items", 0, 0]])
def test_missing_run_paths_reject_before_execution(path: list[Any]) -> None:
    flow = flow_for([step({"source": "run", "path": path})])
    runner = runner_for(flow)
    result = asyncio.run(runner.execute(context(), flow.metadata.identity, {"items": [1]}))
    assert result.run.status == "needs_input"
    assert runner.get(result.run.run_id) is None
    assert runner.bridge.events == ()


def test_inputs_and_results_are_owned_by_the_run_even_after_caller_timeout() -> None:
    class Items(Contract):
        items: list[JsonValue]

    async def scenario() -> None:
        release = asyncio.Event()
        reached_second = asyncio.Event()
        calls = 0

        async def mutate(context: RequestContext, inputs: Contract) -> Contract:
            nonlocal calls
            calls += 1
            assert isinstance(inputs, Items)
            if calls == 2:
                reached_second.set()
                await release.wait()
            item = inputs.items[0]
            assert isinstance(item, dict) and isinstance(item["n"], int)
            item["n"] += 1
            return inputs

        steps = [
            {"capability": spec().identity.model_dump(), "inputs": {"items": ref}}
            for ref in (
                {"source": "run", "path": ["items"]},
                {"source": "step", "step_index": 0, "path": ["items"]},
                {"source": "run", "path": ["items"]},
                {"source": "step", "step_index": 0, "path": ["items"]},
            )
        ]
        flow = flow_for(steps)
        installed = InstalledCapabilities()
        installed.register(
            spec(), mutate, Items, Items, ExecutionDependencies(central_required=False)
        )
        workflows = InstalledWorkflows()
        workflows.register(flow)
        # The caller's manifest and returned installed manifests cannot mutate installation.
        assert isinstance(flow.steps[0], WorkflowStep)
        flow.steps[0].inputs.clear()
        retrieved = workflows.get(flow.metadata.identity)
        assert retrieved is not None and isinstance(retrieved.steps[0], WorkflowStep)
        retrieved.steps[0].inputs.clear()
        runner = WorkflowEngine(workflows, BridgeExecutor(installed, LocalPolicy((grant(),))))
        item: dict[str, JsonValue] = {"n": 1}
        timed_out = await runner.execute(
            context(), flow.metadata.identity, {"items": [item]}, timeout_seconds=0.02
        )
        assert timed_out.run.failure is not None
        assert timed_out.run.failure.code == "workflow_timeout"
        # The caller stopped waiting; the run did not. Waiting for the second
        # step to be entered is deterministic, unlike waiting a fixed 20 ms.
        await reached_second.wait()
        snapshot = runner.get(timed_out.run.run_id)
        assert snapshot is not None
        assert calls == 2 and snapshot.run.completed_steps == 1
        item["n"] = 999
        data = snapshot.step_results[0].data
        assert isinstance(data, dict)
        data["items"] = [{"n": 888}]
        release.set()
        final = await runner.wait(snapshot.run.run_id)
        assert final is not None and final.run.status == "succeeded"
        assert [r.data for r in final.step_results] == [{"items": [{"n": n}]} for n in (2, 3, 2, 3)]
        assert final.run.failure is None
        final_data = final.step_results[0].data
        assert isinstance(final_data, dict)
        final_data.clear()
        again = runner.get(snapshot.run.run_id)
        assert again is not None and again.step_results[0].data == {"items": [{"n": 2}]}

    asyncio.run(scenario())
