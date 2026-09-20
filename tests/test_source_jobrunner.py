"""Offline characterization of the pinned source job runner; no platform imports.

The excerpt keeps the run-tracking core (JobRun, JobRegistry, run_sync/run_async).
Excluded observability, step-table, discovery and error helpers are replaced by
inert doubles injected into the executed module's namespace.
"""

import hashlib
import time
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


class StubJobNotFound(Exception):
    def __init__(self, message: str, detail: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.detail = detail


class StubTimeout(Exception):
    def __init__(self, message: str, detail: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.detail = detail


def source_runner(job: Any = None) -> Any:
    source = (FIXTURES / "source_jobrunner.txt").read_text(encoding="utf-8")
    assert hashlib.sha256(source.encode()).hexdigest() == (
        "8f7edd5b111e0bd144d896c4c9c4a3468e4fa9baf81fa14eba62a24fdef9a399"
    )
    module = ModuleType("pinned_source_jobrunner")
    exec(compile(source, "source_jobrunner.txt", "exec"), module.__dict__)

    def load_job(name: str) -> Any:
        if job is None:
            raise StubJobNotFound(f"unknown job {name!r}", detail={"job": name})
        return job

    module.__dict__.update(
        JobNotFound=StubJobNotFound,
        Timeout=StubTimeout,
        _report=lambda hook, snapshot: None,
        _steps_module=lambda: SimpleNamespace(StepTable=lambda *args, **kwargs: None),
        _attach_steps=lambda run: None,
        _detach_steps=lambda token: None,
        _attach_caller=lambda run: None,
        _detach_caller=lambda token: None,
        _never_run=lambda run: [],
        _publish_tables=lambda run: None,
        _publish_files=lambda run: None,
        worker_id=lambda: "test-worker",
        validate_steps=lambda mod, name: [],
        load_job=load_job,
    )
    module.__dict__["registry"] = module.__dict__["JobRegistry"]()
    return module


def job_module(run: Any) -> SimpleNamespace:
    return SimpleNamespace(PARAMS_SCHEMA={}, run=run)


def test_source_sync_run_records_result_logs_and_history() -> None:
    module = source_runner(job_module(lambda params, log: {"ok": params["value"]}))
    response = module.run_sync("sample", {"value": 7}, timeout_sec=10)
    assert response["status"] == "success"
    assert response["result"] == {"ok": 7}
    assert response["workerId"] == "test-worker"
    messages = [line.split(" ", 1)[1] for line in response["log"]]
    assert messages == ["start job sample", "job sample finished"]
    assert module.registry.get(response["runId"]).status == "success"


def test_source_wraps_non_dict_results() -> None:
    module = source_runner(job_module(lambda params, log: 42))
    assert module.run_sync("sample", {}, timeout_sec=10)["result"] == {"value": 42}


def test_source_failure_records_code_and_message() -> None:
    def boom(params: Any, log: Any) -> dict[str, Any]:
        raise RuntimeError("boom")

    module = source_runner(job_module(boom))
    response = module.run_sync("sample", {}, timeout_sec=10)
    assert response["status"] == "failed"
    assert response["error"] == {"code": "RuntimeError", "message": "boom"}


def test_source_timeout_is_not_the_final_state() -> None:
    def slow(params: Any, log: Any) -> dict[str, Any]:
        time.sleep(0.3)
        return {"done": True}

    module = source_runner(job_module(slow))
    with pytest.raises(StubTimeout):
        module.run_sync("sample", {}, timeout_sec=0)
    run = module.registry.all()[0]
    assert run.status == "timeout"
    deadline = time.monotonic() + 5
    while run.status == "timeout" and time.monotonic() < deadline:
        time.sleep(0.02)
    assert run.status == "success"
    assert run.result == {"done": True}


def test_source_unknown_job_leaves_no_ghost_run() -> None:
    module = source_runner(job=None)
    with pytest.raises(StubJobNotFound):
        module.run_sync("missing", {}, timeout_sec=10)
    assert module.registry.all() == []


def test_source_keeps_only_the_last_50_runs() -> None:
    module = source_runner(job_module(lambda params, log: {}))
    first = module.run_async("sample", {})["runId"]
    run_ids = [module.run_async("sample", {})["runId"] for _ in range(module.MAX_RUNS_KEPT)]
    with pytest.raises(StubJobNotFound):
        module.registry.get(first)
    assert module.registry.get(run_ids[-1]) is not None
    assert len(module.registry.all()) == module.MAX_RUNS_KEPT


def test_source_caps_the_log_with_one_truncation_marker() -> None:
    module = source_runner(job_module(lambda params, log: {}))
    run = module.registry.create("sample")
    for n in range(module.MAX_LOG_LINES + 5):
        run.append_log(f"line-{n}")
    assert len(run.log) == module.MAX_LOG_LINES + 1
    assert run.log[-1].endswith(f"… log truncated ({module.MAX_LOG_LINES} lines)")
