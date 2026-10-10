"""Benchmark progress and results as telemetry (owner 2026-10-10)."""

import json
from pathlib import Path

from telemetry.benchmark import BenchmarkTelemetry, store_path, trace_ids
from telemetry.store import TelemetryStore


def _events(store: TelemetryStore, run_id: str) -> list[dict]:  # type: ignore[type-arg]
    return store.run_events(run_id)


def test_a_benchmark_run_records_cases_and_a_summary(tmp_path: Path) -> None:
    store = TelemetryStore(tmp_path / "telemetry.sqlite")
    bench = BenchmarkTelemetry("knowledge_v1", "core-006", store=store)
    bench.start(cases=2, strategy={"strategy_id": "st-1", "aep_build": "abc"})
    bench.case_started("Q0011", case_type="application")
    bench.case_completed("Q0011", "PASS", duration_ms=1200, aep_trace_ids=["trace-a"],
                         question="never stored", answer="never stored")
    bench.case_completed("Q0051", "FAIL", gap="REASONING_GAP")
    run_id = bench.run_id
    bench.finish()
    reopened = TelemetryStore(tmp_path / "telemetry.sqlite")
    events = _events(reopened, run_id)
    assert [e["event_type"] for e in events] == [
        "run.started", "benchmark.case_started", "benchmark.case_completed",
        "benchmark.case_completed", "run.completed"]
    assert [e["sequence"] for e in events] == [0, 1, 2, 3, 4]
    passed = events[2]["attributes"]
    assert passed["verdict"] == "PASS" and passed["aep_trace_ids"] == ["trace-a"]
    assert "question" not in passed and "answer" not in passed
    assert events[2]["status"] == "succeeded" and events[3]["status"] == "failed"
    (run,) = reopened.runs(kind="benchmark_run")
    assert run["run_id"] == run_id and run["strategy_id"] == "st-1" and run["complete"]
    assert run["cases"] == 2 and run["status_counts"] == {"PASS": 1, "FAIL": 1}


def test_a_grading_run_hangs_under_its_benchmark_run(tmp_path: Path) -> None:
    store = TelemetryStore(tmp_path / "telemetry.sqlite")
    grading = BenchmarkTelemetry("knowledge_v1", "core-006", kind="benchmark_grading",
                                 parent_run_id="bench-x", store=store)
    grading.start(cases=1)
    grading.case_completed("Q0011", "GRADED", coverage=0.5)
    run_id = grading.run_id
    grading.finish()
    reopened = TelemetryStore(tmp_path / "telemetry.sqlite")
    assert [e["event_type"] for e in _events(reopened, run_id)][1] == "benchmark.case_graded"
    (run,) = reopened.runs(parent_run_id="bench-x")
    assert run["run_kind"] == "benchmark_grading"


def test_runs_can_be_found_by_trace(tmp_path: Path) -> None:
    store = TelemetryStore(tmp_path / "telemetry.sqlite")
    bench = BenchmarkTelemetry("s", "l", store=store)
    bench.start(cases=0)
    assert store.runs(trace_id=bench.trace_id)[0]["run_id"] == bench.run_id
    assert store.runs(trace_id="trace-other") == []


def test_trace_ids_come_from_agent_web_replies() -> None:
    reply = {"reply": {"answer": {"outcome": {"trace": {"trace_id": "trace-1"}}}}}
    assert trace_ids([reply, reply, {"reply": {}}, {}]) == ["trace-1"]
    assert trace_ids(reply) == ["trace-1"]


def test_no_store_when_telemetry_is_off_and_nothing_raises(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    host = tmp_path / "host.json"
    host.write_text(json.dumps({"workspace_root": str(workspace)}), encoding="utf-8")
    assert store_path(host) == workspace / "telemetry.sqlite"
    (workspace / "telemetry.json").write_text('{"enabled": false}', encoding="utf-8")
    assert store_path(host) is None
    bench = BenchmarkTelemetry("s", "l", host_json=host)
    bench.start(cases=1)
    bench.case_completed("A", "PASS")
    bench.finish()
    assert not (workspace / "telemetry.sqlite").exists()
