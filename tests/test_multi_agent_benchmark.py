"""multi_agent_v1 in fake-model mode (the review's seven baseline scenarios).
Real AEP delegation code, scripted models, mock handlers: no network, no real
model, no hardware. The live mode is the owner's and is never run here."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest

BENCH = Path(__file__).resolve().parents[1] / "benchmarks" / "multi_agent_v1"
sys.path.insert(0, str(BENCH))


def _load(name: str) -> Any:
    """A benchmark script by its path, under a name of its own: other
    benchmarks' tests import a module called `run` too."""
    key = f"multi_agent_v1_{name}"
    if key in sys.modules:
        return sys.modules[key]
    spec = importlib.util.spec_from_file_location(key, BENCH / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[key] = module
    spec.loader.exec_module(module)
    return module


# The benchmark scripts are not a package. `scenarios_fake` is the module the
# runner itself imports (by that name) when it runs the fake mode.
run: Any = _load("run")
live: Any = _load("live")
mock_cmp180: Any = _load("mock_cmp180")
scenarios_fake: Any = __import__("scenarios_fake")


def test_the_definitions_and_the_fake_scenarios_are_the_same_seven() -> None:
    defined = [item["id"] for item in run.scenarios()]
    assert defined == list(scenarios_fake.SCENARIOS)
    assert len(defined) == 7
    assert sorted(item["review_row"] for item in run.scenarios()) == list(range(1, 8))


def test_the_fake_run_passes_every_check_and_writes_its_report(tmp_path: Path) -> None:
    assert run.main(["--mode", "fake", "--out", str(tmp_path), "--run-id", "ci"]) == 0
    folder = tmp_path / "ci"
    rows = [
        json.loads(line)
        for line in (folder / "results.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert [row["scenario"] for row in rows] == list(scenarios_fake.SCENARIOS)
    for row in rows:
        failed = [check for check in row["checks"] if check["passed"] is not True]
        assert row["checks"] and not failed, (row["scenario"], failed)
    summary = json.loads((folder / "summary.json").read_text(encoding="utf-8"))
    assert all(entry["passed"] == entry["runs"] == 1 for entry in summary.values())
    # The review's common measurements are recorded per route.
    measured = summary["parallel_docs"]["routes"]["delegation"]
    for key in (
        "latency_p50_s",
        "latency_p95_s",
        "llm_calls",
        "input_tokens",
        "output_tokens",
        "retries",
        "policy_refusals",
        "tool_failures",
        "delegations",
    ):
        assert key in measured, key
    assert measured["delegations"] == 2 and measured["provenance_complete"] == 1.0
    assert summary["knowledge_only"]["routes"]["direct"]["delegations"] == 0
    assert summary["workflow_recovery"]["routes"]["delegation"]["retries"] == 1
    assert summary["routing_classification"]["routes"]["not_approved"]["provider_calls"] == 0
    report = (folder / "report.md").read_text(encoding="utf-8")
    assert "## Checks not passed\n\n- none" in report


def test_a_broken_scenario_fails_the_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def broken(_workspace: Path) -> Any:
        raise RuntimeError("boom")

    monkeypatch.setitem(scenarios_fake.SCENARIOS, "isolation", broken)
    code = run.main(
        ["--mode", "fake", "--scenarios", "isolation", "--out", str(tmp_path), "--run-id", "x"]
    )
    assert code == 1
    row = json.loads((tmp_path / "x" / "results.jsonl").read_text(encoding="utf-8"))
    assert row["passed"] is False and "RuntimeError: boom" in row["checks"][0]["actual"]


def test_unknown_scenarios_and_a_live_run_without_an_address_are_refused(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        run.main(["--scenarios", "nope", "--out", str(tmp_path)])
    with pytest.raises(SystemExit):
        run.main(["--mode", "live", "--out", str(tmp_path)])


def test_percentiles_are_nearest_rank() -> None:
    assert run.percentile([], 0.5) is None
    assert run.percentile([3.0, 1.0, 2.0], 0.5) == 2.0
    assert run.percentile([float(n) for n in range(1, 21)], 0.95) == 19.0


def test_the_mock_instrument_never_reaches_hardware() -> None:
    tester = mock_cmp180.MockCmp180()
    assert tester.physical is False
    assert tester.measure_tx_power("n78", 630000)["simulated"] is True
    with pytest.raises(mock_cmp180.RealInstrumentRefused):
        mock_cmp180.MockCmp180(address="TCPIP::192.0.2.10::inst0::INSTR")


def test_every_live_prompt_resolves_without_running_anything() -> None:
    for scenario in run.scenarios():
        prompt = live._prompt(scenario)
        if scenario["id"] == "isolation":
            assert prompt is None
        else:
            assert prompt, scenario["id"]
    coding = next(item for item in run.scenarios() if item["id"] == "coding_parser")
    assert "test.log" in live._prompt(coding)
