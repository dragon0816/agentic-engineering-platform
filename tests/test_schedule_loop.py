"""The resident schedule loop starts only on request and stops cleanly."""

import threading
import time as clock
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from test_host_wiring import ready

from common.scheduling import ScheduleDefinition
from host_runtime.host import build_runtime
from host_runtime.schedule_control import ScheduleControl
from host_runtime.schedule_loop import LOOP_THREAD_NAME, ScheduleLoop, resident_schedule_loop
from host_runtime.schedules import SqliteScheduleStore
from host_runtime.web import AgentWeb


def _wait_for(condition: object, seconds: float = 10.0) -> bool:
    deadline = clock.monotonic() + seconds
    while clock.monotonic() < deadline:
        if callable(condition) and condition():
            return True
        clock.sleep(0.02)
    return False


def _loop_threads() -> list[threading.Thread]:
    return [thread for thread in threading.enumerate() if thread.name == LOOP_THREAD_NAME]


def test_loop_polls_survives_a_failed_poll_and_stops() -> None:
    calls: list[int] = []

    def tick() -> object:
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("first poll fails")
        return ()

    loop = ScheduleLoop(tick, interval_seconds=0.01)
    assert not loop.running
    loop.start()
    with pytest.raises(RuntimeError):
        loop.start()
    assert _wait_for(lambda: len(calls) >= 3)
    assert loop.stop(timeout=5)
    assert not loop.running
    assert loop.failures == 1 and loop.last_failure == "RuntimeError"
    stopped_at = len(calls)
    clock.sleep(0.05)
    assert len(calls) == stopped_at
    assert loop.stop()  # idempotent
    with pytest.raises(ValueError):
        ScheduleLoop(tick, interval_seconds=0)


def test_building_a_host_or_agent_web_starts_no_loop(tmp_path: Path) -> None:
    config, _layout = ready(tmp_path)
    assert config.schedules.resident_loop is False
    before = len(_loop_threads())
    with build_runtime(config) as runtime:
        web = AgentWeb(runtime)
        assert web.schedule_loop is None
        assert resident_schedule_loop(runtime, lock=web.request_lock) is None
        assert len(_loop_threads()) == before


def test_opt_in_by_config_or_flag_and_the_loop_waits_for_the_request_lock(
    tmp_path: Path,
) -> None:
    config, layout = ready(tmp_path)
    opted = config.model_copy(
        update={"schedules": config.schedules.model_copy(update={"resident_loop": True})}
    )
    with build_runtime(opted) as runtime:
        web = AgentWeb(runtime)
        configured = resident_schedule_loop(runtime, lock=web.request_lock)
        assert configured is not None and configured.interval_seconds == 30
    with build_runtime(config) as runtime:
        web = AgentWeb(runtime)
        now = datetime.now(UTC)
        at = (now - timedelta(hours=1)).time().replace(second=0, microsecond=0)
        definition = ScheduleDefinition.model_validate(
            {
                "schedule_id": "hourly-read",
                "owner": "engineer",
                "target_kind": "workflow",
                "target": {
                    "namespace": "engineering",
                    "name": "read-local-file",
                    "version": "1.0.0",
                },
                "recurrence": {
                    "kind": "daily",
                    "timezone": "UTC",
                    "at": at.isoformat("minutes"),
                },
                "runtime_inputs": {"args": "notes.txt"},
            }
        )
        control = ScheduleControl(runtime, lock=web.request_lock)
        with SqliteScheduleStore(
            layout.workspace_root / "schedules.sqlite", bridge_id="bridge-company"
        ) as store:
            store.create(definition, now=now - timedelta(hours=2))
        control.grant("hourly-read", max_side_effect="read")
        loop = resident_schedule_loop(runtime, lock=web.request_lock, requested=True)
        assert loop is not None
        loop.interval_seconds = 0.05
        with web.request_lock:
            loop.start()
            clock.sleep(0.3)
            # A browser request holds the lock: nothing has been claimed yet.
            assert control.history("hourly-read") == ()
        assert _wait_for(lambda: len(control.history("hourly-read")) == 1)
        assert loop.stop(timeout=10)
        (run,) = control.history("hourly-read")
        assert (run.status, run.result_code) == ("succeeded", "workflow_succeeded")
        assert loop.failures == 0
        assert not _loop_threads()
