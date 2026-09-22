"""Bounded progress streams: every state change reaches the run's owner, a slow
consumer never blocks the run, terminal events always arrive, and events carry
identities, statuses and codes only."""

import asyncio
import json
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


class Gated(Handler):
    """Each call waits until the test releases it, so event order is deterministic."""

    def __init__(self, *, fail_first: bool = False) -> None:
        super().__init__()
        self.release = asyncio.Event()
        self.fail_first = fail_first

    async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
        await self.release.wait()
        if self.fail_first and not self.calls:
            self.calls.append(context)
            raise RuntimeError("private error payload")
        return await super().__call__(context, inputs)


async def collect(stream: AsyncIterator[RunProgress] | None) -> list[RunProgress]:
    assert stream is not None
    return [event async for event in stream]


async def start_gated(steps: int, handler: Gated) -> tuple[WorkflowEngine, str]:
    flow = flow_for([spec().identity.model_dump()] * steps)
    runner = runner_for(flow, handler)
    started = await runner.execute(
        context(), flow.metadata.identity, {"count": 4141}, timeout_seconds=0.001
    )
    assert started.run.failure is not None and started.run.failure.code == "workflow_timeout"
    return runner, started.run.run_id


def base_event(**changes: Any) -> dict[str, Any]:
    return {
        "sequence": 1,
        "run_id": "run-1",
        "workflow": spec().identity.model_dump(),
        "event": "snapshot",
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
        {"event": "started"},
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
        handler = Gated()
        runner, run_id = await start_gated(2, handler)
        stream = runner.watch(context(), run_id)
        handler.release.set()
        events = await collect(stream)
        assert [(e.event, e.step_index) for e in events] == [
            ("snapshot", None),
            ("step_finished", 0),
            ("step_started", 1),
            ("step_finished", 1),
            ("finished", None),
        ]
        assert events[0].status == "running" and events[0].completed_steps == 0
        assert events[-1].status == "succeeded" and events[-1].completed_steps == 2
        sequences = [e.sequence for e in events]
        assert sequences == sorted(sequences) and len(set(sequences)) == len(sequences)
        assert not any(e.lagged for e in events)
        assert all(e.run_id == run_id for e in events)
        for event in events:
            # A progress event carries identities, statuses and codes, never a
            # payload. The check is over every field but the run id: that is
            # a random hexadecimal identifier, and one in a few hundred runs
            # it happens to contain the digits being looked for.
            exposed = event.model_dump(mode="json")
            exposed.pop("run_id")
            assert "4141" not in json.dumps(exposed)
            assert "4142" not in json.dumps(exposed)
        final = await runner.wait(run_id)
        assert final is not None and final.step_results[0].data == {"count": 4142}

    asyncio.run(scenario())


def test_finished_run_yields_one_terminal_snapshot_with_its_code() -> None:
    async def scenario() -> None:
        flow = flow_for([spec().identity.model_dump()])
        runner = runner_for(flow)
        done = await runner.execute(context(), flow.metadata.identity, {"count": 1})
        replays = [await collect(runner.watch(context(), done.run.run_id)) for _ in range(2)]
        for events in replays:
            assert [(e.event, e.status, e.code) for e in events] == [
                ("snapshot", "succeeded", None)
            ]
        # Replays describe existing state: the sequence does not advance.
        assert replays[0][0].sequence == replays[1][0].sequence

        handler = Gated(fail_first=True)
        handler.release.set()
        runner = runner_for(flow, handler)
        failed = await runner.execute(context(), flow.metadata.identity, {"count": 1})
        assert failed.run.status == "failed"
        events = await collect(runner.watch(context(), failed.run.run_id))
        assert [(e.event, e.status, e.code) for e in events] == [
            ("snapshot", "failed", "handler_error")
        ]

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
        handler = Gated()
        runner, run_id = await start_gated(3, handler)
        runner.watch_queue_size = 2
        stream = runner.watch(context(), run_id)
        handler.release.set()
        final = await runner.wait(run_id)
        assert final is not None and final.run.status == "succeeded"
        events = await collect(stream)
        assert events[-1].event == "finished" and events[-1].status == "succeeded"
        assert events[-1].lagged is True
        assert len(events) <= 2

    asyncio.run(scenario())


def test_watcher_capacity_is_reported_and_closed_streams_release_it() -> None:
    async def scenario() -> None:
        handler = Gated()
        runner, run_id = await start_gated(1, handler)
        streams = [runner.watch(context(), run_id) for _ in range(MAX_WATCHERS_PER_RUN)]
        assert all(stream is not None for stream in streams)
        rejected = await collect(runner.watch(context(), run_id))
        assert [(e.event, e.code) for e in rejected] == [("rejected", "watch_capacity")]
        # Abandoning streams — closed before or after iterating, or simply
        # dropped — releases their slots for the rest of the run.
        assert streams[1] is not None
        await streams[1].__anext__()
        await streams[1].aclose()
        for stream in streams[2:-1]:
            assert stream is not None
            await stream.aclose()
        del streams[-1]
        replacement = runner.watch(context(), run_id)
        assert replacement is not None
        handler.release.set()
        final = await runner.wait(run_id)
        assert final is not None and final.run.status == "succeeded"
        assert (await collect(streams[0]))[-1].event == "finished"
        assert (await collect(replacement))[-1].event == "finished"

    asyncio.run(scenario())


def test_cancelled_run_still_ends_its_streams() -> None:
    async def scenario() -> None:
        handler = Gated()  # never released: the step is stuck until cancelled
        runner, run_id = await start_gated(1, handler)
        stream = runner.watch(context(), run_id)
        runner._tasks[run_id].cancel()
        events = await collect(stream)
        assert events[-1].event == "finished"
        assert events[-1].status == "failed" and events[-1].code == "workflow_aborted"

    asyncio.run(scenario())


def test_queue_size_is_guarded_on_construction_and_assignment() -> None:
    flow = flow_for([spec().identity.model_dump()])
    runner = runner_for(flow)
    with pytest.raises(ValueError):
        WorkflowEngine(runner.workflows, runner.bridge, watch_queue_size=1)
    with pytest.raises(ValueError):
        runner.watch_queue_size = 1
    runner.watch_queue_size = 2


def test_gateway_watch_passes_through_without_authority() -> None:
    async def scenario() -> None:
        gw = gateway(GatewayHandler())
        done = await gw.handle(request("release.package"))
        assert done.workflow is not None and done.workflow.run.status == "succeeded"
        run_id = done.workflow.run.run_id
        events = await collect(gw.watch(request("watch"), run_id))
        assert [e.event for e in events] == ["snapshot"] and events[0].status == "succeeded"
        assert gw.watch(request("watch"), "run-missing") is None
        with pytest.raises(ValidationError):
            gw.watch(request("watch"), "not a symbol!")

    asyncio.run(scenario())
