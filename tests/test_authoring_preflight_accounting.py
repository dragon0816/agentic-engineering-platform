"""Count actual Gateway dispatch, including Host-check retries, not returned totals."""

from pathlib import Path
from typing import Literal

from test_turn_effects import _built, _converse, _reply

from agent.gateway import turn_call_budget


def test_accounting_covers_every_host_check_pass_and_resets_outside_scope(tmp_path: Path) -> None:
    missing = tmp_path / "out" / "report.xlsx"
    missing.parent.mkdir()
    built, model, write, _ = _built(
        [
            _reply(("notes__publish", {"note": "weekly"})),
            _reply(text=f"已寫入 {missing}。"),
            _reply(("notes__publish", {"note": "weekly"})),
            _reply(text="已發布筆記。"),
            _reply(text="一般回答。"),
        ]
    )
    built._workspace_roots = (str(tmp_path),)
    counts = {"model": 0, "tool": 0}

    def charge(kind: Literal["model", "tool"]) -> None:
        counts[kind] += 1

    with turn_call_budget(charge):
        result = _converse(built)
    assert result.status == "answered" and len(model.calls) == 4
    assert counts == {"model": 4, "tool": 2} and write.calls == 1
    assert len(result.tools) == 1  # Return value deliberately omits first-pass calls.
    _converse(built)
    assert len(model.calls) == 5 and counts == {"model": 4, "tool": 2}


def test_model_limit_stops_before_next_request() -> None:
    built, model, write, _ = _built(
        [
            _reply(("notes__publish", {"note": "once"})),
            _reply(text="This request must never happen."),
        ]
    )
    calls = 0

    def charge(kind: Literal["model", "tool"]) -> str | None:
        nonlocal calls
        if kind == "model":
            if calls == 1:
                return "preflight_budget_exhausted"
            calls += 1
        return None

    with turn_call_budget(charge):
        result = _converse(built)
    assert len(model.calls) == 1 and write.calls == 1
    assert result.status == "failed" and result.failure.code == "preflight_budget_exhausted"


def test_tool_limit_refuses_remaining_batch_before_dispatch() -> None:
    built, model, write, _ = _built(
        [
            _reply(("notes__publish", {"note": "first"}), ("notes__publish", {"note": "second"})),
        ]
    )
    calls = 0

    def charge(kind: Literal["model", "tool"]) -> str | None:
        nonlocal calls
        if kind == "tool":
            if calls == 1:
                return "preflight_budget_exhausted"
            calls += 1
        return None

    with turn_call_budget(charge):
        result = _converse(built)
    assert len(model.calls) == 1 and write.calls == 1
    assert result.status == "failed" and result.failure.code == "preflight_budget_exhausted"
