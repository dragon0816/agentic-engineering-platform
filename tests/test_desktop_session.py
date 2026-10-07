"""`desktop/operate` (lab gap L2): registered applications only, their own windows only."""

from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from capabilities.desktop_session.handlers import (
    SPEC,
    DesktopHostBinding,
    DesktopRequest,
    DesktopSessionHandler,
    described,
)
from capabilities.runtime import CapabilityRefused

ROOT = Path(__file__).resolve().parents[1]
LAB = ROOT / "benchmarks" / "business_workflow_lab"
EXPENSE_EXE = LAB / "expense_desktop_mock" / "bin" / "ExpenseApp.exe"

LOOK: dict[str, Any] = {
    "title": "Expense Viewer (synthetic lab)",
    "controls": [
        {"id": "DateFrom", "type": "Edit", "name": "DateFrom", "value": "", "enabled": True},
        {"id": "NextButton", "type": "Button", "name": "NextButton", "enabled": False},
    ],
    "dialogs": [{"title": "Query complete", "texts": ["13 rows"], "buttons": ["OK"]}],
}


class FakeProcess:
    def __init__(self, pid: int) -> None:
        self.pid = pid
        self.code: int | None = None

    def poll(self) -> int | None:
        return self.code

    def terminate(self) -> None:
        self.code = 1

    def wait(self, timeout: float | None = None) -> int:
        return self.code or 0


class Fakes:
    def __init__(self, answer: dict[str, Any] | None = None) -> None:
        self.launched: list[list[str]] = []
        self.processes: list[FakeProcess] = []
        self.requests: list[dict[str, Any]] = []
        self.answer = answer or {"ok": True, "data": {"count": "Total 13 rows"}, "look": LOOK}

    def launch(self, command: list[str]) -> FakeProcess:
        self.launched.append(command)
        self.processes.append(FakeProcess(100 + len(self.processes)))
        return self.processes[-1]

    def run(self, request: dict[str, Any], timeout_s: float) -> dict[str, Any]:
        self.requests.append(request)
        return self.answer


def binding(tmp_path: Path) -> DesktopHostBinding:
    return DesktopHostBinding.model_validate({
        "applications": [{"name": "expense", "command": ["C:/apps/expense.exe"],
                          "window_title": "Expense Viewer"}],
        "timeout_seconds": 60,
        "workspace_roots": [str(tmp_path / "tasks")],
    })


def handler(tmp_path: Path, fakes: Fakes) -> DesktopSessionHandler:
    return DesktopSessionHandler(binding(tmp_path), tmp_path / "cache", runner=fakes.run,
                                 launcher=fakes.launch)


def request(**fields: Any) -> DesktopRequest:
    return DesktopRequest.model_validate({"app": "expense", **fields})


def test_spec_needs_approval_and_the_desktop_permission() -> None:
    assert SPEC.identity.key == ("desktop", "operate", "1.0.0")
    assert SPEC.side_effect == "external_side_effect"
    assert SPEC.policy.approval_required
    assert SPEC.policy.required_permissions == ("desktop.operate",)
    assert SPEC.policy.policy_refs == ("desktop-application-policy",)


def test_only_a_registered_application_is_started_and_its_pid_is_what_is_operated(
    tmp_path: Path,
) -> None:
    fakes = Fakes()
    run = handler(tmp_path, fakes)
    with pytest.raises(CapabilityRefused) as refused:
        run.run(DesktopRequest.model_validate({"app": "notepad", "launch": True}))
    assert refused.value.code == "desktop_app_not_allowed" and fakes.launched == []
    result = run.run(request(launch=True, actions=[
        {"do": "set", "id": "DateFrom", "value": "2026-09-01"},
        {"do": "read", "id": "CountLabel", "save_as": "count"}]))
    assert fakes.launched == [["C:/apps/expense.exe"]]
    sent = fakes.requests[0]
    assert sent["pid"] == 100 and sent["window"] == "Expense Viewer"
    assert sent["actions"][0] == {"do": "set", "id": "DateFrom", "value": "2026-09-01"}
    assert result.app == "expense" and result.data == {"count": "Total 13 rows"}
    assert "DateFrom [Edit] = ''" in result.look and "NextButton [Button] (disabled)" in result.look
    assert "Dialog: Query complete" in result.look and "buttons: OK" in result.look


def test_a_running_process_is_kept_and_a_dead_one_is_started_again(tmp_path: Path) -> None:
    fakes = Fakes()
    run = handler(tmp_path, fakes)
    run.run(request())  # started on demand even without `launch`
    run.run(request(launch=True))
    assert len(fakes.launched) == 1
    fakes.processes[0].code = 0  # the person closed the window
    run.run(request())
    assert len(fakes.launched) == 2 and fakes.requests[-1]["pid"] == 101
    run.close()
    assert fakes.processes[1].code == 1


def test_save_as_lands_only_in_an_output_folder_of_an_allowed_workspace(tmp_path: Path) -> None:
    fakes = Fakes()
    run = handler(tmp_path, fakes)
    workspace = tmp_path / "tasks" / "t1"
    refused_paths = [
        "relative/output/x.csv",
        str(tmp_path / "elsewhere" / "output" / "x.csv"),
        str(workspace / "x.csv"),
        str(workspace / "output" / ".." / "x.csv"),
    ]
    for path in refused_paths:
        with pytest.raises(CapabilityRefused) as refused:
            run.run(request(actions=[{"do": "save_as", "path": path}]))
        assert refused.value.code == "desktop_path_not_allowed", path
    assert fakes.requests == []
    target = workspace / "output" / "exports" / "rows.csv"
    run.run(request(actions=[{"do": "save_as", "path": str(target)}]))
    assert fakes.requests[-1]["actions"] == [{"do": "save_as", "path": str(target.resolve())}]
    assert target.parent.is_dir()
    target.write_text("x", encoding="utf-8")
    with pytest.raises(CapabilityRefused) as refused:
        run.run(request(actions=[{"do": "save_as", "path": str(target)}]))
    assert refused.value.code == "desktop_path_exists"


def test_helper_refusals_come_back_as_desktop_codes(tmp_path: Path) -> None:
    fakes = Fakes({"ok": False, "code": "control_missing", "message": "no control 'X'", "step": 0})
    run = handler(tmp_path, fakes)
    with pytest.raises(CapabilityRefused) as refused:
        run.run(request(actions=[{"do": "invoke", "id": "X"}]))
    assert refused.value.code == "desktop_control_missing"
    assert refused.value.where == "action 0 (invoke)"


def test_a_refusal_names_the_action_but_never_the_helpers_message(tmp_path: Path) -> None:
    fakes = Fakes({"ok": False, "code": "dialog_missing",
                   "message": "no dialog titled like 'Secret Title'", "step": 1})
    run = handler(tmp_path, fakes)
    with pytest.raises(CapabilityRefused) as refused:
        run.run(request(actions=[{"do": "invoke", "id": "QueryButton"},
                                 {"do": "wait_dialog", "title": "Secret Title"}]))
    assert refused.value.code == "desktop_dialog_missing"
    assert refused.value.where == "action 1 (wait_dialog)"
    assert "Secret" not in str(refused.value)
    # A step outside the request names no place.
    fakes = Fakes({"ok": False, "code": "dialog_missing", "message": "", "step": 9})
    with pytest.raises(CapabilityRefused) as refused:
        handler(tmp_path, fakes).run(request(actions=[{"do": "invoke", "id": "QueryButton"}]))
    assert refused.value.where is None


def test_actions_missing_what_they_need_are_invalid() -> None:
    with pytest.raises(ValueError):
        request(actions=[{"do": "set", "id": "DateFrom"}])
    with pytest.raises(ValueError):
        request(actions=[{"do": "read", "id": "CountLabel"}])
    with pytest.raises(ValueError):
        request(actions=[{"do": "click", "id": "QueryButton"}])


def test_the_look_text_is_bounded() -> None:
    many = {"title": "W", "controls": [
        {"id": f"F{i}", "type": "Edit", "name": f"F{i}", "value": "x" * 100, "enabled": True}
        for i in range(120)]}
    text = described(many, limit=2000)
    assert len(text) <= 2002 and text.startswith("Window: W")


@pytest.mark.skipif(sys.platform != "win32", reason="Windows UI Automation")
@pytest.mark.skipif(not EXPENSE_EXE.is_file(),
                    reason="build benchmarks/business_workflow_lab/expense_desktop_mock first")
def test_live_the_lab_expense_app_is_queried_and_exported(tmp_path: Path) -> None:
    # The lab app's fault mode back to normal, so the export is not made to fail.
    subprocess.run([sys.executable, str(LAB / "operator" / "reset.py")], check=True,
                   capture_output=True, timeout=60)
    live = DesktopHostBinding.model_validate({
        "applications": [{"name": "expense", "command": [str(EXPENSE_EXE)],
                          "window_title": "Expense Viewer"}],
        "timeout_seconds": 300,
        "workspace_roots": [str(tmp_path / "tasks")],
    })
    run = DesktopSessionHandler(live, tmp_path / "cache")
    target = tmp_path / "tasks" / "t1" / "output" / "expenses.csv"
    try:
        queried = run.run(request(launch=True, actions=[
            {"do": "set", "id": "EmployeeFilter", "value": "E001"},
            {"do": "set", "id": "DateFrom", "value": "2026-09-01"},
            {"do": "set", "id": "DateTo", "value": "2026-09-30"},
            {"do": "invoke", "id": "QueryButton"},
            {"do": "dialog", "save_as": "message"},
            {"do": "dismiss"},
            {"do": "read_table", "id": "ResultsList", "save_as": "rows"},
        ], look=False))
        message = queried.data["message"]
        assert isinstance(message, dict) and "13" in str(message["texts"])
        rows = queried.data["rows"]
        assert isinstance(rows, list) and len(rows) == 8
        assert isinstance(rows[0], dict) and rows[0]["ExpenseID"] == "EXP-00001"
        exported = run.run(request(actions=[
            {"do": "invoke", "id": "ExportCsvButton"},
            {"do": "save_as", "path": str(target)},
            {"do": "dialog", "save_as": "done"},
            {"do": "dismiss"},
        ]))
        assert "ExportCsvButton [Button]" in exported.look
        with target.open(encoding="utf-8-sig", newline="") as handle:
            assert len(list(csv.DictReader(handle))) == 13
    finally:
        run.close()


def test_run_values_fill_placeholders_so_a_step_replays_with_new_values(tmp_path: Path) -> None:
    fakes = Fakes()
    run = handler(tmp_path, fakes)
    out = tmp_path / "tasks" / "D01" / "output"
    request = DesktopRequest.model_validate({
        "app": "expense", "values": {"employee": "E002", "month": "2026-08"},
        "actions": [{"do": "set", "id": "EmployeeFilter", "value": "{employee}"},
                    {"do": "save_as", "path": str(out / "{employee}_{month}.csv")}]})
    run.run(request)
    sent = fakes.requests[-1]["actions"]
    assert sent[0]["value"] == "E002"
    assert sent[1]["path"].endswith("E002_2026-08.csv")
    missing = DesktopRequest.model_validate({
        "app": "expense", "actions": [{"do": "set", "id": "DateFrom", "value": "{start}"}]})
    with pytest.raises(CapabilityRefused) as refused:
        run.run(missing)
    assert refused.value.code == "desktop_value_missing"


def test_an_app_name_matches_regardless_of_case_and_the_tool_lists_the_apps(tmp_path: Path) -> None:
    from capabilities.desktop_session.handlers import DesktopResult
    from capabilities.runtime import InstalledCapabilities, LocalPolicy
    from common.assets import ExecutionDependencies
    from host_runtime.bridge_tools import bridge_tools
    from workflow.dispatch import BridgeExecutor

    fakes = Fakes()
    run = handler(tmp_path, fakes)
    assert run.run(DesktopRequest.model_validate({"app": "Expense"})).app == "expense"
    installed = InstalledCapabilities()
    installed.register(SPEC, run, DesktopRequest, DesktopResult,
                       ExecutionDependencies(central_required=False))
    (tool,) = bridge_tools(BridgeExecutor(installed, LocalPolicy(())))
    assert "Registered applications: expense (Expense Viewer)" in tool.tool.description


def test_save_as_may_replace_an_earlier_file_only_when_asked(tmp_path: Path) -> None:
    """Lab fix-006 X01: a rerun's fixed export name met the first run's file."""
    fakes = Fakes()
    run = handler(tmp_path, fakes)
    target = tmp_path / "tasks" / "X01" / "output" / "expenses.csv"
    target.parent.mkdir(parents=True)
    target.write_text("first run", encoding="utf-8")
    keep = DesktopRequest.model_validate({
        "app": "expense", "actions": [{"do": "save_as", "path": str(target)}]})
    with pytest.raises(CapabilityRefused) as refused:
        run.run(keep)
    assert refused.value.code == "desktop_path_exists" and target.exists()
    replace = DesktopRequest.model_validate({
        "app": "expense", "actions": [{"do": "save_as", "path": str(target), "replace": True}]})
    run.run(replace)
    assert not target.exists()
    assert "replace" not in fakes.requests[-1]["actions"][0]
