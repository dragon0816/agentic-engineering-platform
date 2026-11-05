"""A briefly busy state database at start waits; anything else still fails at once.

A second writer is refused rather than waited for (`timeout=0`, by design): this is only
about opening the file when a host starts, where two starts can meet. The owner's start
on 2026-11-05 ended in exit code 2 this way, and the next click worked.
"""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

import pytest
from test_host_wiring import ready

from common.distribution import LocalStateError
from host_runtime import cli, host
from host_runtime.host import HostError, HostErrorCode, build_runtime
from host_runtime.state import LocalStateBusy, SqliteLocalState

BRIDGE = "bridge-company"


def _hold(path: Path) -> sqlite3.Connection:
    holder = sqlite3.connect(path, isolation_level=None, check_same_thread=False)
    holder.execute("BEGIN IMMEDIATE")
    return holder


def test_a_held_file_is_refused_at_once_and_says_it_is_busy(tmp_path: Path) -> None:
    path = tmp_path / "state.sqlite"
    SqliteLocalState(path, bridge_id=BRIDGE).close()
    holder = _hold(path)
    try:
        with pytest.raises(LocalStateBusy) as found:
            SqliteLocalState(path, bridge_id=BRIDGE)
    finally:
        holder.close()
    # Everything that already handles this error keeps working: same type, same code.
    assert isinstance(found.value, LocalStateError)
    assert found.value.code == "unavailable"


def test_a_host_start_waits_out_a_briefly_busy_file(tmp_path: Path) -> None:
    config, layout = ready(tmp_path)
    with build_runtime(config, layout=layout):
        pass
    holder = _hold(layout.state)
    release = threading.Timer(1.0, holder.close)
    release.start()
    try:
        with build_runtime(config, layout=layout) as runtime:
            assert runtime.state is not None
    finally:
        release.join()


def test_a_file_that_stays_busy_fails_in_bounded_time_naming_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config, layout = ready(tmp_path)
    with build_runtime(config, layout=layout):
        pass
    monkeypatch.setattr(host, "STATE_BUSY_WAIT_SECONDS", 0.5)
    holder = _hold(layout.state)
    try:
        with pytest.raises(HostError) as found:
            build_runtime(config, layout=layout)
    finally:
        holder.close()
    assert found.value.code == "state_busy"
    assert found.value.path == layout.state


def test_a_broken_file_fails_without_waiting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config, layout = ready(tmp_path)
    layout.state.parent.mkdir(parents=True, exist_ok=True)
    layout.state.write_bytes(b"this is not a database, and it is long enough to be read" * 40)
    waited: list[float] = []
    monkeypatch.setattr("host_runtime.host.time.sleep", waited.append)
    with pytest.raises(HostError) as found:
        build_runtime(config, layout=layout)
    assert found.value.code == "state_unavailable"
    assert waited == []


@pytest.mark.parametrize(
    ("code", "said"),
    [("state_busy", "try again"), ("state_unavailable", "try again")],
)
def test_the_message_names_the_file_and_what_to_do(
    code: HostErrorCode, said: str, tmp_path: Path
) -> None:
    path = tmp_path / "state.sqlite"
    message = cli.not_ready_message(HostError(code, path))
    assert str(path) in message
    assert said in message.lower()
    assert code in message
