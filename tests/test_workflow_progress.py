"""Bounded progress streams: every state change reaches the run's owner, a slow
consumer never blocks the run, terminal events always arrive, and events carry
identities, statuses and codes only."""

import asyncio
from collections.abc import AsyncIterator
from typing import Any

import pytest
from pydantic import ValidationError
from test_dispatch import Handler, spec
from test_engine import context
from test_gateway import Handler as GatewayHandler
from test_gateway import gateway, request
from test_workflow_inputs import flow_for, runner_for

from common.base import Contract
from common.execution import RequestContext, RunProgress, TraceIdentifiers
from workflow.engine import MAX_WATCHERS_PER_RUN, WorkflowEngine


def other_actor_context() -> RequestContext:
    return RequestContext(
        trace=TraceIdentifiers(trace_id="trace-2", request_id="request-2", span_id="span-2"),
        actor="someone-else",
        namespace="sample",
        channel="test",
        message="watch",
    )


class Paced(Handler):
    async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
        await asyncio.sleep(0.02)
        return await super().__call__(context, inputs)


async def collect(stream: AsyncIterator[RunProgress] | None) -> list[RunProgress]:
    assert stream is not None
    return [event async for event in stream]


def base_event(**changes: Any) -> dict[str, Any]:
    return {
        "sequence": 1,
        "run_id": "run-1",
        "workflow": spec().identity.model_dump(),
        "event": "started",
        "status": "running",
        "completed_steps": 0,
        **changes,
    }


@pytest.mark.parametrize(
    "changes",
    [
        {"event": "step_started"},
        {"event": "step_finished"},
        {"event": "finished"},
        {"event": "rejected"},
        {"sequence": -1},
        {"step_index": -1},
        {"lagged": 1},
    ],
)
def test_progress_contract_rejects_malformed_events(changes: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        RunProgress.model_validate(base_event(**changes))


def test_progress_contract_round_trips() -> None:
    event = RunProgress.model_validate(
        base_event(event="finished", status="succeeded", completed_steps=2, lagged=True)
    )
    assert RunProgress.model_validate_json(event.model_dump_json()) == event


def test_live_run_streams_every_change_then_ends() -> None:
    async def scenario() -> None:
        flow = flow_for([spec().identity.model_dump()] * 2)
        runner = runner_for(flow, Paced())
        started = await runner.execute(
            context(), flow.metadata.identity, {"count": 4141}, timeout_seconds=0.001
        )
        events = await collect(runner.watch(context(), started.run.run_id))
        assert events[0].event == "snapshot" and events[0].status == "running"
        assert [e.event for e in events[1:]] == [
            "step_finished",
            "step_started",
            "step_finished",
            "finished",
        ]
        assert [e.step_index for e in events[1:-1]] == [0, 1, 1]
        assert events[-1].status == "succeeded" and events[-1].completed_steps == 2
        assert [e.sequence for e in events] == sorted(e.sequence for e in events)
        assert len({e.sequence for e in events}) == len(events)
        assert not any(e.lagged for e in events)
        assert all(e.run_id == started.run.run_id for e in events)
        for event in events:
            assert "4141" not in event.model_dump_json()
            assert "4142" not in event.model_dump_json()
        final = await runner.wait(started.run.run_id)
        assert final is not None and final.step_results[0].data == {"count": 4142}

    asyncio.run(scenario())


def test_finished_run_yields_one_terminal_snapshot() -> None:
    async def scenario() -> None:
        flow = flow_for([spec().identity.model_dump()])
        runner = runner_for(flow)
        done = await runner.execute(context(), flow.metadata.identity, {"count": 1})
        for _ in range(2):
            events = await collect(runner.watch(context(), done.run.run_id))
            assert [e.event for e in events] == ["snapshot"]
            assert events[0].status == "succeeded" and events[0].completed_steps == 1

    asyncio.run(scenario())


def test_unknown_and_foreign_runs_have_no_stream() -> None:
    async def scenario() -> None:
        flow = flow_for([spec().identity.model_dump()])
        runner = runner_for(flow)
        done = await runner.execute(context(), flow.metadata.identity, {"count": 1})
        assert runner.watch(context(), "run-missing") is None
        assert runner.watch(other_actor_context(), done.run.run_id) is None

    asyncio.run(scenario())


def test_slow_consumer_never_blocks_the_run_and_still_gets_the_end() -> None:
    async def scenario() -> None:
        flow = flow_for([spec().identity.model_dump()] * 3)
        runner = runner_for(flow, Paced())
        runner.watch_queue_size = 2
        started = await runner.execute(
            context(), flow.metadata.identity, {"count": 1}, timeout_seconds=0.001
        )
        stream = runner.watch(context(), started.run.run_id)
        final = await runner.wait(started.run.run_id)
        assert final is not None and final.run.status == "succeeded"
        events = await collect(stream)
        assert events[-1].event == "finished" and events[-1].status == "succeeded"
        assert events[-1].lagged is True
        assert len(events) <= 2

    asyncio.run(scenario())


def test_watcher_capacity_is_reported_not_silently_dropped() -> None:
    async def scenario() -> None:
        flow = flow_for([spec().identity.model_dump()])
        runner = runner_for(flow, Paced())
        started = await runner.execute(
            context(), flow.metadata.identity, {"count": 1}, timeout_seconds=0.001
        )
        streams = [runner.watch(context(), started.run.run_id) for _ in range(MAX_WATCHERS_PER_RUN)]
        assert all(stream is not None for stream in streams)
        rejected = await collect(runner.watch(context(), started.run.run_id))
        assert [(e.event, e.code) for e in rejected] == [("rejected", "watch_capacity")]
        final = await runner.wait(started.run.run_id)
        assert final is not None and final.run.status == "succeeded"
        assert (await collect(streams[0]))[-1].event == "finished"

    asyncio.run(scenario())


def test_cancelled_run_still_ends_its_streams() -> None:
    class Stuck(Handler):
        async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
            await asyncio.sleep(30)
            return await super().__call__(context, inputs)

    async def scenario() -> None:
        flow = flow_for([spec().identity.model_dump()])
        runner = runner_for(flow, Stuck())
        started = await runner.execute(
            context(), flow.metadata.identity, {"count": 1}, timeout_seconds=0.01
        )
        stream = runner.watch(context(), started.run.run_id)
        runner._tasks[started.run.run_id].cancel()
        events = await collect(stream)
        assert events[-1].event == "finished"
        assert events[-1].status == "failed" and events[-1].code == "workflow_aborted"

    asyncio.run(scenario())


def test_engine_requires_room_for_terminal_delivery() -> None:
    flow = flow_for([spec().identity.model_dump()])
    with pytest.raises(ValueError):
        WorkflowEngine(runner_for(flow).workflows, runner_for(flow).bridge, watch_queue_size=1)


def test_gateway_watch_passes_through_without_authority() -> None:
    async def scenario() -> None:
        gw = gateway(GatewayHandler())
        done = await gw.handle(request("release.package"))
        assert done.workflow is not None and done.workflow.run.status == "succeeded"
        run_id = done.workflow.run.run_id
        events = await collect(gw.watch(request("watch"), run_id))
        assert [e.event for e in events] == ["snapshot"] and events[0].status == "succeeded"
        assert gw.watch(request("watch"), "run-missing") is None

    asyncio.run(scenario())
