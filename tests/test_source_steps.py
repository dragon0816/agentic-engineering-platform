"""Offline characterization of the pinned source step table; no platform imports.

The excerpt is the `jobs/_steps.py` module without its module docstring. It is
self-contained stdlib code; tests attach a table and drive it with inert bodies.
"""

import hashlib
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
DECLARED = [
    {"id": "load", "title": "load"},
    {"id": "price", "title": "price"},
    {"id": "render", "title": "render"},
]


def source_steps() -> Any:
    source = (FIXTURES / "source_steps.txt").read_text(encoding="utf-8")
    assert hashlib.sha256(source.encode()).hexdigest() == (
        "fb7e1e3754f4783dbf32edb93cf79698eff1d415ed6058487ff8eb3d4ec334a5"
    )
    module = ModuleType("pinned_source_steps")
    exec(compile(source, "source_steps.txt", "exec"), module.__dict__)
    return module


def table_for(module: Any) -> Any:
    return module.StepTable(DECLARED, log=lambda message: None)


def test_source_steps_after_a_failure_stay_pending() -> None:
    module = source_steps()
    table = table_for(module)
    token = module.attach(table)
    try:
        with module.run("load"):
            pass
        with pytest.raises(RuntimeError):
            with module.run("price"):
                raise RuntimeError("boom")
    finally:
        module.detach(token)
    statuses = {row["id"]: row["status"] for row in table.snapshot()}
    assert statuses == {"load": "success", "price": "failed", "render": "pending"}
    assert table.never_run() == ["render"]
    # The source records exception text on the failed row; the adaptation never does.
    assert table.snapshot()[1]["error"] == "boom"


def test_source_finished_or_failed_steps_cannot_be_entered_again() -> None:
    module = source_steps()
    table = table_for(module)
    table.start("load")
    table.finish("load")
    with pytest.raises(TypeError, match="already success"):
        table.start("load")
    table.start("price")
    table.finish("price", error=RuntimeError("boom"))
    with pytest.raises(TypeError, match="already failed"):
        table.start("price")
    assert not hasattr(table, "resume")


def test_source_runs_one_step_at_a_time() -> None:
    table = table_for(source_steps())
    table.start("load")
    with pytest.raises(TypeError, match="still running"):
        table.start("price")


def test_source_skip_needs_a_reason_and_leaves_never_run() -> None:
    table = table_for(source_steps())
    with pytest.raises(TypeError, match="needs a reason"):
        table.skip("render", "")
    table.skip("render", "no draft requested")
    assert table.status("render") == "skipped"
    assert table.never_run() == ["load", "price"]
