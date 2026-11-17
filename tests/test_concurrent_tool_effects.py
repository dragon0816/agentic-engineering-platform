"""Successful effects are coordinated across coroutines and native HTTP loops."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from pydantic import JsonValue
from test_dispatch import Input, Output, invocation, spec

from agent.turn_effects import TurnEffects, turn_scope, use_effects
from capabilities.contracts import CapabilitySpec
from capabilities.runtime import InstalledCapabilities
from common.assets import ExecutionDependencies
from common.base import Contract
from common.execution import CapabilityResult, RequestContext
from workflow.dispatch import BridgeExecutor


class SlowWrite:
    def __init__(self) -> None:
        self.calls = 0
        self.active = 0
        self.peak = 0

    async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
        self.calls += 1
        self.active += 1
        self.peak = max(self.peak, self.active)
        await asyncio.sleep(0.03)
        self.active -= 1
        return Output(count=Input.model_validate(inputs).count)


def bridge(handler: SlowWrite) -> BridgeExecutor:
    installed = InstalledCapabilities()
    raw = spec().model_dump(mode="json")
    raw["side_effect"] = "write"
    installed.register(
        CapabilitySpec.model_validate(raw),
        handler,
        Input,
        Output,
        ExecutionDependencies(central_required=False),
    )
    return BridgeExecutor(installed)


def test_same_loop_duplicate_writes_execute_once() -> None:
    handler = SlowWrite()
    executor = bridge(handler)

    async def scenario() -> None:
        with turn_scope():
            results = await asyncio.gather(
                executor.execute(invocation()), executor.execute(invocation())
            )
        assert all(result.status == "succeeded" for result in results)
        assert sum(result.handler_invoked for result in results) == 1
        assert sum("capability_replayed" in result.warnings for result in results) == 1

    asyncio.run(scenario())
    assert handler.calls == 1


def test_distinct_writes_share_the_registry_execution_lock() -> None:
    handler = SlowWrite()
    executor = bridge(handler)

    async def scenario() -> None:
        calls = [invocation().model_copy(update={"arguments": {"count": n}}) for n in (1, 2)]
        with turn_scope():
            results = await asyncio.gather(*(executor.execute(call) for call in calls))
        assert all(result.status == "succeeded" for result in results)

    asyncio.run(scenario())
    assert handler.calls == 2 and handler.peak == 1


def test_native_threads_share_receipts_without_blocking_the_event_loop() -> None:
    handler = SlowWrite()
    executor = bridge(handler)
    other = BridgeExecutor(executor.installed)
    effects = TurnEffects()

    def run(executor: BridgeExecutor) -> CapabilityResult:
        with use_effects(effects):
            return asyncio.run(executor.execute(invocation()))

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(run, (executor, other)))
    assert handler.calls == 1
    assert all(result.status == "succeeded" for result in results)


def test_concurrent_direct_workflow_runs_share_one_actual_run(tmp_path: Path) -> None:
    import threading

    from test_chat_authoring import Echo, Out, studio, workflow
    from test_chat_authoring import spec as authoring_spec

    chat, recorder = studio(tmp_path)
    target = authoring_spec("write-it", "write")

    async def slow(context: RequestContext, inputs: Contract) -> Contract:
        await asyncio.sleep(0.04)
        return await recorder(context, inputs)

    chat.installed.unregister(target.identity)
    chat.installed.register(target, slow, Echo, Out, ExecutionDependencies(central_required=False))
    item, problems = chat.draft("owner", "session-1", "Echo", workflow("write-it"))
    assert item is not None and not problems
    effects = TurnEffects()
    barrier = threading.Barrier(2)

    def execute(index: int) -> dict[str, JsonValue]:
        with use_effects(effects):
            barrier.wait(timeout=5)
            return chat.execute("owner", item, {"month": "fixture"}, f"worker-{index}")

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(execute, (0, 1)))
    assert all(result["status"] == "succeeded" for result in results)
    assert len({result["run_id"] for result in results}) == 1
    assert sum(result.get("replayed") is True for result in results) == 1
    assert recorder.calls == ["fixture"]
