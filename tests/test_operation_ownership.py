"""Worker-owned finality and durable exclusion across caller deadlines/restarts."""

import asyncio
import json
import sqlite3
import threading
from pathlib import Path

import pytest
from test_dispatch import invocation
from test_harness_reliability import policy_for
from test_host_wiring import host_json, ready
from test_run_python import handler as python_handler
from test_run_python import requires_win32

from capabilities.coding_change.run_python import (
    RUN_SPEC,
    RunPythonHandler,
    RunPythonRequest,
    RunPythonResult,
    RunPythonStepInput,
)
from capabilities.runtime import CapabilityInvocation, InstalledCapabilities
from common.assets import ExecutionDependencies
from common.distribution import LocalStateError
from common.operations import MemoryOperationStore, OperationFinalStatus, OperationRecord
from harness.thread_operations import workspace_resource_key
from host_runtime.cli import main
from host_runtime.host import build_runtime
from host_runtime.state import SqliteLocalState
from workflow.dispatch import BridgeExecutor
from workflow.journal import SuspensionConfirmation


def record(operation_id: str, resource: Path) -> OperationRecord:
    context = invocation().context
    return OperationRecord(
        operation_id=operation_id,
        resource_key=workspace_resource_key(resource),
        actor=context.actor,
        capability=RUN_SPEC.identity,
        trace=context.trace,
    )


def make_bridge(root: Path, store: SqliteLocalState | MemoryOperationStore) -> BridgeExecutor:
    installed = InstalledCapabilities()
    installed.register(
        RUN_SPEC,
        python_handler(root),
        RunPythonStepInput,
        RunPythonResult,
        ExecutionDependencies(central_required=False),
    )
    bridge = BridgeExecutor(installed, policy_for(installed), timeout_seconds=2)
    bridge.operations = store
    return bridge


def call(root: Path) -> CapabilityInvocation:
    return invocation().model_copy(
        update={
            "target": RUN_SPEC.identity,
            "arguments": {"request": {"workspace": str(root), "script": "print('fixture')"}},
        }
    )


def test_timeout_keeps_the_resource_claim_until_the_real_worker_acknowledges_completion(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    release = threading.Event()
    started = threading.Event()
    calls: list[str] = []
    first_root, other_root = tmp_path / "first", tmp_path / "other"
    first_root.mkdir()
    other_root.mkdir()

    def controlled(
        self: RunPythonHandler, request: RunPythonRequest, arguments: object = None
    ) -> RunPythonResult:
        calls.append(request.workspace)
        if Path(request.workspace) == first_root:
            started.set()
            release.wait(3)
        return RunPythonResult(
            exit_code=0, timed_out=False, output="done", files=(), script_path="script.py"
        )

    monkeypatch.setattr(RunPythonHandler, "run", controlled)
    path = tmp_path / "state.sqlite"
    with SqliteLocalState(path, bridge_id="test-bridge") as state1:
        with SqliteLocalState(path, bridge_id="test-bridge") as state2:
            bridge1, bridge2 = make_bridge(tmp_path, state1), make_bridge(tmp_path, state2)
            bridge1.timeout_seconds = 0.1
            bridge2.timeout_seconds = 2

            async def scenario() -> None:
                try:
                    first = await bridge1.execute(call(first_root))
                    assert started.is_set()
                    assert first.failure is not None and first.failure.code == "timeout"
                    assert len(first.warnings) == 1
                    operation_id = first.warnings[0].removeprefix("operation_id=")
                    pending = state1.operation(operation_id)
                    assert pending is not None and pending.status == "unknown"
                    assert pending.finished_at is None
                    conflict = await bridge2.execute(call(first_root))
                    assert conflict.failure is not None
                    assert conflict.failure.code == "operation_in_progress"
                    assert conflict.warnings == first.warnings
                    assert calls == [str(first_root)]
                    independent = await bridge2.execute(call(other_root))
                    assert independent.status == "succeeded"
                    release.set()
                    for _ in range(100):
                        final = state1.operation(operation_id)
                        if final is not None and final.status == "completed":
                            break
                        await asyncio.sleep(0.01)
                    else:
                        pytest.fail("worker completion was not durably acknowledged")
                    after = await bridge2.execute(call(first_root))
                    assert after.status == "succeeded"
                    assert calls.count(str(first_root)) == 2
                finally:
                    release.set()

            asyncio.run(scenario())


def test_restart_never_expires_an_unresolved_claim_and_reconciliation_is_explicit(
    tmp_path: Path,
) -> None:
    path = tmp_path / "state.sqlite"
    with SqliteLocalState(path, bridge_id="bridge") as state:
        initial = state.claim_operation(record("operation-first", tmp_path))
        state.mark_operation_unknown(initial.operation_id)
    with SqliteLocalState(path, bridge_id="bridge") as restarted:
        conflict = restarted.claim_operation(record("operation-second", tmp_path))
        assert conflict.operation_id == "operation-first"
        assert conflict.status == "unknown"
        with pytest.raises(ValueError):
            SuspensionConfirmation(operator="engineer", process_confirmed_stopped=False)
        stopped = restarted.reconcile_operation(
            initial.operation_id,
            SuspensionConfirmation(operator="engineer", process_confirmed_stopped=True),
        )
        assert stopped.reconciled_by == "engineer"
        assert not stopped.unresolved
        assert (
            restarted.claim_operation(record("operation-third", tmp_path)).operation_id
            == "operation-third"
        )
        # A delayed old completion cannot overwrite the reconciliation/new claim.
        with pytest.raises(LocalStateError, match="operation_already_final"):
            restarted.complete_operation(initial.operation_id, "completed")


def test_caller_cancellation_does_not_release_a_running_worker(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    release, started = threading.Event(), threading.Event()

    def controlled(
        self: RunPythonHandler,
        request: RunPythonRequest,
        arguments: object = None,
    ) -> RunPythonResult:
        started.set()
        release.wait(3)
        return RunPythonResult(
            exit_code=0,
            timed_out=False,
            output="done",
            files=(),
            script_path="script.py",
        )

    monkeypatch.setattr(RunPythonHandler, "run", controlled)
    with SqliteLocalState(tmp_path / "state.sqlite", bridge_id="bridge") as state:
        bridge = make_bridge(tmp_path, state)
        bridge.timeout_seconds = 3

        async def scenario() -> None:
            task = asyncio.create_task(bridge.execute(call(tmp_path)))
            try:
                for _ in range(100):
                    if started.is_set():
                        break
                    await asyncio.sleep(0.01)
                assert started.is_set()
                task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await task
                assert state.operations()[0].status == "unknown"
                conflict = await bridge.execute(call(tmp_path))
                assert conflict.failure is not None
                assert conflict.failure.code == "operation_in_progress"
            finally:
                release.set()
                if not task.done():
                    await task

        asyncio.run(scenario())
        # asyncio.run waits for this controlled worker before closing its executor.
        assert state.operations()[0].status == "completed"


def test_claim_acknowledgment_failure_prevents_dispatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Unavailable(MemoryOperationStore):
        def claim_operation(self, item: OperationRecord) -> OperationRecord:
            raise LocalStateError("commit_unknown")

    calls: list[str] = []

    def forbidden(
        self: RunPythonHandler, request: RunPythonRequest, arguments: object = None
    ) -> RunPythonResult:
        calls.append("unexpected")
        raise AssertionError("worker must not start")

    monkeypatch.setattr(RunPythonHandler, "run", forbidden)
    result = asyncio.run(make_bridge(tmp_path, Unavailable()).execute(call(tmp_path)))
    assert result.failure is not None and result.failure.code == "operation_state_unavailable"
    assert calls == []


def test_failed_finish_acknowledgment_keeps_conflicting_work_blocked(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class UnavailableFinish(MemoryOperationStore):
        def complete_operation(
            self,
            operation_id: str,
            status: OperationFinalStatus,
            code: str | None = None,
        ) -> OperationRecord:
            raise LocalStateError("commit_unknown")

    calls: list[str] = []

    def controlled(
        self: RunPythonHandler, request: RunPythonRequest, arguments: object = None
    ) -> RunPythonResult:
        calls.append("ran")
        return RunPythonResult(
            exit_code=0, timed_out=False, output="done", files=(), script_path="script.py"
        )

    monkeypatch.setattr(RunPythonHandler, "run", controlled)
    store = UnavailableFinish()
    bridge = make_bridge(tmp_path, store)
    first = asyncio.run(bridge.execute(call(tmp_path)))
    assert first.failure is not None and first.failure.code == "operation_state_unavailable"
    second = asyncio.run(bridge.execute(call(tmp_path)))
    assert second.failure is not None and second.failure.code == "operation_in_progress"
    assert calls == ["ran"]


def test_completion_racing_a_late_timeout_is_not_downgraded(tmp_path: Path) -> None:
    with SqliteLocalState(tmp_path / "state.sqlite", bridge_id="bridge") as state:
        item = state.claim_operation(record("operation-first", tmp_path))
        final = state.complete_operation(item.operation_id, "completed")
        assert state.mark_operation_unknown(item.operation_id) == final
        body = final.model_dump_json()
        assert str(tmp_path) not in body
        assert "script" not in body


def test_unknown_execution_result_requires_reconciliation_even_after_worker_returns(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unknown(
        self: RunPythonHandler, request: RunPythonRequest, arguments: object = None
    ) -> RunPythonResult:
        return RunPythonResult(
            exit_code=None, timed_out=False, output="unknown", files=(), script_path="script.py"
        )

    monkeypatch.setattr(RunPythonHandler, "run", unknown)
    with SqliteLocalState(tmp_path / "state.sqlite", bridge_id="bridge") as state:
        bridge = make_bridge(tmp_path, state)
        first = asyncio.run(bridge.execute(call(tmp_path)))
        assert first.failure is not None and first.failure.code == "python_execution_unknown"
        item = state.operations()[0]
        assert item.status == "unknown" and item.finished_at is not None
        second = asyncio.run(bridge.execute(call(tmp_path)))
        assert second.failure is not None and second.failure.code == "operation_in_progress"


def test_state_six_migrates_without_losing_existing_rows(tmp_path: Path) -> None:
    path = tmp_path / "state.sqlite"
    with SqliteLocalState(path, bridge_id="bridge"):
        pass
    with sqlite3.connect(path) as conn:
        conn.execute("UPDATE local_meta SET value='6' WHERE key='schema_version'")
        conn.execute("DROP TABLE operations")
        conn.execute("INSERT INTO channel_cursor VALUES ('fixture', 123)")
    with SqliteLocalState(path, bridge_id="bridge") as migrated:
        assert migrated.claim_operation(record("operation-new", tmp_path)).status == "running"
    with sqlite3.connect(path) as conn:
        assert conn.execute(
            "SELECT position FROM channel_cursor WHERE channel='fixture'"
        ).fetchone() == (123,)
        assert conn.execute(
            "SELECT value FROM local_meta WHERE key='schema_version'"
        ).fetchone() == ("7",)


def test_operator_can_inspect_and_explicitly_reconcile_a_persisted_operation(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config, layout = ready(tmp_path)
    path = host_json(tmp_path, config)
    with build_runtime(config) as runtime:
        assert runtime.agent.gateway.bridge.operations is runtime.state
        runtime.state.claim_operation(record("operation-fixture", layout.workspace_root))
        runtime.state.mark_operation_unknown("operation-fixture")
    assert main(["operations", "--config", str(path)]) == 0
    rows = json.loads(capsys.readouterr().out)
    assert rows[0]["status"] == "unknown"
    assert str(layout.workspace_root) not in json.dumps(rows)
    arguments = [
        "reconcile-operation",
        "--config",
        str(path),
        "--operation-id",
        "operation-fixture",
    ]
    with pytest.raises(SystemExit):
        main(arguments)
    capsys.readouterr()
    with SqliteLocalState(layout.state, bridge_id=config.device.bridge_id) as state:
        pending = state.operation("operation-fixture")
        assert pending is not None and pending.status == "unknown"
    assert main([*arguments, "--confirm-stopped"]) == 0
    resolved = json.loads(capsys.readouterr().out)
    assert resolved["reconciled_by"] == "engineer"
    assert resolved["status"] == "failed" and resolved["code"] == "operation_reconciled"
    assert main([*arguments, "--confirm-stopped"]) == 1
    assert capsys.readouterr().err.strip() == "operation_already_final"


@requires_win32
def test_real_restricted_process_cannot_be_duplicated_after_bridge_timeout(tmp_path: Path) -> None:
    root = tmp_path / "task"
    root.mkdir()
    request = call(root).model_copy(
        update={
            "arguments": {
                "request": {
                    "workspace": str(root),
                    "script": (
                        "import time\nfrom pathlib import Path\ntime.sleep(.8)\n"
                        "with Path('output/effects.txt').open('a') as out: out.write('once\\n')\n"
                    ),
                }
            }
        }
    )
    with SqliteLocalState(tmp_path / "state.sqlite", bridge_id="bridge") as state:
        bridge = make_bridge(tmp_path, state)
        bridge.timeout_seconds = 0.1

        async def scenario() -> None:
            first = await bridge.execute(request)
            assert first.failure is not None and first.failure.code == "timeout"
            conflict = await bridge.execute(request)
            assert conflict.failure is not None and conflict.failure.code == "operation_in_progress"
            for _ in range(500):
                if not state.operations()[0].unresolved:
                    break
                await asyncio.sleep(0.01)
            else:
                pytest.fail("restricted worker did not confirm completion")

        asyncio.run(scenario())
        assert state.operations()[0].status == "completed"
        assert (root / "output" / "effects.txt").read_text().splitlines() == ["once"]
