"""An opt-in schedule loop inside the long-running Host process.

The Host process that owns deterministic execution near local resources is
the one that runs `aep-host web` (or `aep-host schedules run`). The loop runs
there only when the owner opts in -- `schedules.resident_loop` in host.json or
`--schedules` on the command line -- and never because a Host or Agent Web
object was constructed. Each poll is one `ScheduleControl.tick`, which holds
Agent Web's one-request-at-a-time lock, so a scheduled run never overlaps a
browser request against the same state or workbook. Stopping waits for the
poll in progress; an interrupted run is left as an open claim for operator
resolution, never replayed.
"""

import threading
from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import Any

from host_runtime.host import HostRuntime

LOOP_THREAD_NAME = "aep-schedule-loop"


class ScheduleLoop:
    """Poll immediately, then once per interval, until stopped."""

    def __init__(self, tick: Callable[[], object], *, interval_seconds: float) -> None:
        if not 0 < interval_seconds <= 3600:
            raise ValueError("schedule poll interval must be 0..3600 seconds")
        self._tick = tick
        self.interval_seconds = interval_seconds
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.ticks = 0
        self.failures = 0
        # The failing exception's type only: its message may quote local data.
        self.last_failure: str | None = None

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if self._thread is not None:
            raise RuntimeError("a schedule loop is started once")
        self._thread = threading.Thread(target=self._run, name=LOOP_THREAD_NAME, daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 30.0) -> bool:
        """Ask the loop to stop; True once its thread has finished."""
        self._stop.set()
        thread = self._thread
        if thread is None:
            return True
        thread.join(timeout)
        return not thread.is_alive()

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self._tick()
                self.ticks += 1
            except Exception as error:  # noqa: BLE001 - one failed poll never ends the loop
                self.failures += 1
                self.last_failure = type(error).__name__
            self._stop.wait(self.interval_seconds)

    def status(self) -> dict[str, Any]:
        return {
            "running": self.running,
            "interval_seconds": self.interval_seconds,
            "ticks": self.ticks,
            "failures": self.failures,
            "last_failure": self.last_failure,
        }


def resident_schedule_loop(
    runtime: HostRuntime,
    *,
    lock: AbstractContextManager[Any] | None,
    requested: bool = False,
) -> ScheduleLoop | None:
    """The loop for this process when the owner opted in; not yet started."""
    settings = runtime.config.schedules
    if not (requested or settings.resident_loop):
        return None
    from host_runtime.schedule_control import ScheduleControl

    def tick() -> object:
        # A fresh control per poll sees newly installed Agent Task templates.
        return ScheduleControl(runtime, lock=lock).tick()

    return ScheduleLoop(tick, interval_seconds=float(settings.poll_seconds))
