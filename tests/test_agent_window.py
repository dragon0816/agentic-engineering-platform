"""The window is an ingress, and these tests hold it to that.

Nothing here opens a window. What is worth pinning is that the window asks
the same question the command line asks, and that whatever comes back becomes
something a person can read -- including a failure, because a window that
dies on one is worse than no window.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from test_host_wiring import host_json, ready

from common.assets import AssetIdentity
from common.execution import (
    CapabilityResult,
    Failure,
    RouteDecision,
    RunStatus,
    TraceIdentifiers,
    WorkflowRun,
)
from common.local_agent import LocalAgentRequest
from host_runtime.agent import LocalAgentOutcome
from host_runtime.cli import main
from host_runtime.host import build_runtime
from host_runtime.window import AgentWindow, readable
from workflow.engine import WorkflowRunSnapshot

WEEKLY = AssetIdentity(namespace="engineering", name="jira-weekly-report-preview", version="1.0.0")


def trace() -> TraceIdentifiers:
    return TraceIdentifiers(trace_id="trace-1", request_id="request-1", span_id="span-1")


def outcome(**changes: Any) -> LocalAgentOutcome:
    return LocalAgentOutcome(trace=trace(), ingress="local", actor="engineer", **changes)


def ran(status: RunStatus, data: Any, *, failure: Failure | None = None) -> LocalAgentOutcome:
    return outcome(
        decision=RouteDecision(kind="workflow", target=WEEKLY, reason="matched"),
        workflow=WorkflowRunSnapshot(
            run=WorkflowRun(
                run_id="run-1",
                workflow=WEEKLY,
                trace=trace(),
                status=status,
                completed_steps=5,
                failure=failure,
            ),
            step_results=(
                CapabilityResult(
                    trace=trace(), status="succeeded", data=data, handler_invoked=True
                ),
            ),
        ),
    )


def window(tmp_path: Path, **changes: Any) -> AgentWindow:
    config, _layout = ready(tmp_path)
    with build_runtime(config) as runtime:
        return AgentWindow(runtime, "engineering", **changes)


def test_the_window_asks_what_the_command_line_asks(tmp_path: Path) -> None:
    """One Agent, one request shape. A window that built its own would be a
    second place where routing could differ."""
    request = window(tmp_path).request_for("weekly.preview 2026_39W")
    assert request.ingress == "local"
    assert request.actor == "engineer", "the device owner, as `ask` defaults to"
    assert request.bridge_id == "bridge-company", "the host's own Bridge, never a chosen one"
    assert request.namespace == "engineering"
    assert request.message == "weekly.preview 2026_39W"


def test_a_named_actor_is_the_one_used(tmp_path: Path) -> None:
    assert window(tmp_path, actor="somebody-else").request_for("x").actor == "somebody-else"


def test_a_plans_own_words_are_what_is_shown() -> None:
    """The weekly report's last step carries the dry run written out. Showing
    that instead of its JSON is the whole reason a person opens the window."""
    shown = readable(ran("succeeded", {"preview": "62 row(s): 0 new, 62 updated", "rows": 62}))
    assert "62 row(s): 0 new, 62 updated" in shown
    assert "succeeded, 5 step(s)" in shown
    assert '"rows"' not in shown, "the words, not the payload, when there are words"


def test_a_step_without_words_still_shows_what_it_returned() -> None:
    """Summarising an unknown shape would invent a claim about it; printing it
    as it stands cannot."""
    shown = readable(ran("succeeded", {"written": 4, "sheet": "2026_39W"}))
    assert '"written": 4' in shown
    assert '"sheet": "2026_39W"' in shown


def test_chinese_in_an_answer_is_not_mangled() -> None:
    """The board carries names and comments in Chinese, and `\\uXXXX` escapes
    are not a readable answer."""
    assert "測試完成" in readable(ran("succeeded", {"note": "測試完成"}))


def test_a_failed_run_names_its_failure() -> None:
    shown = readable(
        ran("failed", None, failure=Failure(code="workbook_locked", message="Excel has it open"))
    )
    assert "failure: workbook_locked" in shown


def test_a_refusal_is_the_whole_answer() -> None:
    shown = readable(outcome(refusal="actor_not_bound"))
    assert shown == "Refused: actor_not_bound"


def test_an_answer_never_arrives_empty() -> None:
    """A blank transcript line reads as though nothing was asked."""
    assert readable(outcome()) == "nothing came back"


def test_a_request_that_raises_is_shown_rather_than_lost(tmp_path: Path) -> None:
    """The work runs on a worker thread, where an exception reaches no
    console. Unhandled, the window would sit on `working...` for ever."""

    def explode(_request: LocalAgentRequest) -> LocalAgentOutcome:
        raise RuntimeError("the board could not be reached")

    answer = window(tmp_path, ask=explode).answer_for("weekly.preview")
    assert "did not finish" in answer
    assert "the board could not be reached" in answer


def test_chat_without_a_namespace_says_how_to_fix_it(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The same refusal `ask` gives, because it is the same missing setting --
    and it must not open a window to say so."""
    config, _layout = ready(tmp_path, config_changes={"namespace": None})
    assert main(["chat", "--config", str(host_json(tmp_path, config))]) == 2
    assert "no namespace is configured" in capsys.readouterr().err
