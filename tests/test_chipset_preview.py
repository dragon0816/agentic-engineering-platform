"""Source Workflow 10 preview must keep source order and never alter Excel."""

import asyncio
import datetime as dt
import json
import shutil
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import openpyxl
import pytest
from pydantic import ValidationError
from test_host_wiring import membership_record, workspace

from capabilities.chipset_report.apply import apply_plan
from capabilities.chipset_report.contracts import (
    ChipsetPreview,
    ChipsetPreviewInput,
    ChipsetReportSettings,
)
from capabilities.chipset_report.manifest import (
    APPLY_SPEC,
    PREVIEW_SPEC,
    preview_workflow,
    report_workflow,
)
from capabilities.chipset_report.preview import ChipsetPreviewError, build_preview
from capabilities.chipset_report.ruleset import Rules
from capabilities.runtime import CapabilityRefused
from common.assets import WorkflowStep
from common.execution import TraceIdentifiers
from common.local_agent import LocalWorkflowRequest
from host_runtime.assets import export_assets
from host_runtime.host import build_runtime


def _book(path: Path, sheet: str, headers: tuple[str, ...], rows: list[tuple[Any, ...]]) -> None:
    book = openpyxl.Workbook()
    tab = book.active
    assert tab is not None
    tab.title = sheet
    tab.append(headers)
    for row in rows:
        tab.append(row)
    book.save(path)
    book.close()


def _settings(source: Path, target: Path, **changes: object) -> ChipsetReportSettings:
    values: dict[str, object] = {
        "source_files": [{"path": str(source), "sheet": "Project List", "fiscal_year": "FY2526"}],
        "target_file": str(target),
        "target_header_row": 2,
    }
    values.update(changes)
    return ChipsetReportSettings.model_validate(values)


def test_source_records_are_transformed_with_real_header_row_and_no_write(tmp_path: Path) -> None:
    source, target = tmp_path / "FY2526.xlsx", tmp_path / "target.xlsm"
    _book(
        source,
        "Project List",
        ("Brand", "MFG", "Project Name", "Chipset models", "Status", "OPP ID"),
        [("Acme", "OEM", "Device", "QFW7114", "On-going", "OPP-1")],
    )
    book = openpyxl.Workbook()
    tab = book.active
    assert tab is not None
    tab.title = "Chipset_requirement"
    tab["A1"] = "sort button"
    tab.append(("Chipset Vendor", "chipset", "Technology", "Brand", "MFG", "Comments"))
    book.save(target)
    book.close()
    before = target.read_bytes()

    preview = build_preview(_settings(source, target), today=dt.date(2026, 10, 3))
    assert preview.target_sheet == "Chipset_requirement"
    assert preview.temp_sheet == "temp"
    assert preview.headers[:3] == ("Chipset Vendor", "chipset", "Technology")
    assert preview.sources[0].rows == 1
    assert preview.projects_read == 1
    assert preview.rows_generated >= 1
    assert any("QFW7114" in str(row["chipset"]) for row in preview.records)
    assert target.read_bytes() == before


class RecordingChipsetWriter:
    def __init__(self, *, damage_managed: bool = False) -> None:
        self.damage_managed = damage_managed
        self.replaced: list[str] = []

    def sheet_names(self, path: Path) -> tuple[str, ...]:
        book = openpyxl.load_workbook(path)
        try:
            return tuple(book.sheetnames)
        finally:
            book.close()

    def backup(self, path: Path) -> Path:
        backup = path.with_name("backup" + path.suffix)
        shutil.copy2(path, backup)
        return backup

    def replace(
        self,
        path: Path,
        sheet: str,
        headers: Sequence[str],
        records: Sequence[Mapping[str, str | int | float]],
        rules: Rules,
        *,
        format_records: Sequence[Mapping[str, object]] | None = None,
    ) -> int:
        self.replaced.append(sheet)
        book = openpyxl.load_workbook(path)
        try:
            if sheet in book.sheetnames:
                del book[sheet]
            tab = book.create_sheet(sheet)
            tab.append(tuple(headers))
            for record in records:
                tab.append(tuple(record.get(header, "") for header in headers))
            if self.damage_managed:
                book["Chipset_requirement"]["A1"] = "corrupted"
            book.save(path)
        finally:
            book.close()
        return len(records)

    def close(self, path: Path, *, save: bool) -> None:
        return None


def test_apply_only_copies_back_validated_temp_sheet(tmp_path: Path) -> None:
    source, target = tmp_path / "FY2526.xlsx", tmp_path / "target.xlsx"
    _book(source, "Project List", ("Chipset models",), [("QFW7114",)])
    _book(target, "Chipset_requirement", ("chipset", "Technology"), [])
    settings = _settings(source, target, target_header_row=1)
    state = tmp_path / "state"
    plan = build_preview(settings, today=dt.date(2026, 10, 3), state_dir=state)
    assert plan.source_changes[0].critical_count == 0
    assert not state.exists()
    writer = RecordingChipsetWriter()
    applied = apply_plan(
        plan, settings, writer, staging_root=tmp_path / "staging", state_dir=state
    )
    assert applied.rows_written == plan.rows_generated
    assert writer.replaced == ["temp"]
    assert applied.backup_path is not None and Path(applied.backup_path).is_file()
    assert len(applied.snapshot_paths) == 1 and Path(applied.snapshot_paths[0]).is_file()
    book = openpyxl.load_workbook(target, read_only=True)
    try:
        assert book.sheetnames == ["Chipset_requirement", "temp"]
        assert book["Chipset_requirement"]["A1"].value == "chipset"
        assert book["temp"]["A1"].value == plan.headers[0]
    finally:
        book.close()


def test_apply_refuses_stale_target_and_discards_corrupt_stage(tmp_path: Path) -> None:
    source, target = tmp_path / "FY2526.xlsx", tmp_path / "target.xlsx"
    _book(source, "Project List", ("Chipset models",), [("QFW7114",)])
    _book(target, "Chipset_requirement", ("chipset", "Technology"), [])
    settings = _settings(source, target, target_header_row=1)
    state = tmp_path / "state"
    plan = build_preview(settings, today=dt.date(2026, 10, 3), state_dir=state)
    book = openpyxl.load_workbook(target)
    book["Chipset_requirement"]["A2"] = "someone's edit"
    book.save(target)
    book.close()
    with pytest.raises(CapabilityRefused, match="target_changed"):
        apply_plan(
            plan, settings, RecordingChipsetWriter(), staging_root=tmp_path / "s1",
            state_dir=state,
        )
    assert not (tmp_path / "s1").exists()
    assert not state.exists()

    fresh = build_preview(settings, today=dt.date(2026, 10, 3), state_dir=state)
    before = target.read_bytes()
    with pytest.raises(CapabilityRefused, match="managed_sheet_changed"):
        apply_plan(
            fresh,
            settings,
            RecordingChipsetWriter(damage_managed=True),
            staging_root=tmp_path / "s2",
            state_dir=state,
        )
    assert target.read_bytes() == before
    assert not state.exists()


def test_apply_refuses_when_temp_changed_after_preview(tmp_path: Path) -> None:
    source, target = tmp_path / "FY2526.xlsx", tmp_path / "target.xlsx"
    _book(source, "Project List", ("Chipset models",), [("QFW7114",)])
    _book(target, "Chipset_requirement", ("chipset", "Technology"), [])
    settings = _settings(source, target, target_header_row=1)
    plan = build_preview(settings, today=dt.date(2026, 10, 3))
    book = openpyxl.load_workbook(target)
    book.create_sheet("temp")["A1"] = "somebody's new temp"
    book.save(target)
    book.close()
    before = target.read_bytes()
    with pytest.raises(CapabilityRefused, match="temp_sheet_changed"):
        apply_plan(plan, settings, RecordingChipsetWriter(), staging_root=tmp_path / "stage")
    assert target.read_bytes() == before

def test_installed_workflow_10_apply_respects_exact_write_grant(tmp_path: Path) -> None:
    source, target = tmp_path / "FY2526.xlsx", tmp_path / "target.xlsx"
    _book(source, "Project List", ("Chipset models",), [("QFW7114",)])
    _book(target, "Chipset_requirement", ("chipset", "Technology"), [])
    read_grant = {
        "actor": "engineer",
        "asset": PREVIEW_SPEC.identity.model_dump(mode="json"),
        "permissions": list(PREVIEW_SPEC.policy.required_permissions),
        "policy_refs": list(PREVIEW_SPEC.policy.policy_refs),
        "approval_ref": "chipset-read-approval",
    }
    write_grant = {
        "actor": "engineer",
        "asset": APPLY_SPEC.identity.model_dump(mode="json"),
        "permissions": list(APPLY_SPEC.policy.required_permissions),
        "policy_refs": list(APPLY_SPEC.policy.policy_refs),
        "approval_ref": "chipset-write-approval",
    }
    config, layout = workspace(
        tmp_path,
        membership=membership_record(),
        grants=[read_grant],
        assets=False,
        config_changes={
            "integrations": {
                "chipset_report": {
                    "source_files": [{"path": str(source), "sheet": "Project List"}],
                    "target_file": str(target),
                    "target_header_row": 1,
                }
            }
        },
    )
    export_assets(layout.workspace_root / "assets")

    def request(key: str) -> LocalWorkflowRequest:
        return LocalWorkflowRequest(
            actor="engineer",
            bridge_id=config.device.bridge_id,
            workflow=report_workflow().metadata.identity,
            arguments={},
            idempotency_key=key,
            trace=TraceIdentifiers(trace_id="chipset", request_id=key, span_id="apply"),
        )

    before = target.read_bytes()
    writer = RecordingChipsetWriter()
    with build_runtime(config, layout=layout, chipset_writer=lambda: writer) as runtime:
        denied = asyncio.run(runtime.agent.execute_workflow(request("chipset-denied")))
        assert denied.workflow is not None
        assert denied.workflow.run.status == "failed"
        assert denied.workflow.run.failure is not None
        assert denied.workflow.run.failure.code == "permission_denied"
    assert target.read_bytes() == before and writer.replaced == []

    layout.grants.write_text(json.dumps([read_grant, write_grant]), encoding="utf-8")
    with build_runtime(config, layout=layout, chipset_writer=lambda: writer) as runtime:
        allowed = asyncio.run(runtime.agent.execute_workflow(request("chipset-allowed")))
        assert allowed.workflow is not None
        assert allowed.workflow.run.status == "succeeded", allowed.workflow.run.failure
    assert writer.replaced == ["temp"]

def test_disabled_source_is_skipped_and_protected_sheet_is_refused(tmp_path: Path) -> None:
    source, target = tmp_path / "FY2526.xlsx", tmp_path / "target.xlsx"
    _book(source, "Project List", ("Chipset models",), [("QFW7114",)])
    _book(target, "Chipset_requirement", ("chipset",), [])
    with pytest.raises(ValidationError):
        _settings(source, target, temp_sheet=" chipset_REQUIREMENT ")
    with pytest.raises(ValidationError):
        _settings(source, target, source_files=[{"path": str(source), "enabled": False}])


def test_missing_target_is_a_refusal_not_an_all_new_report(tmp_path: Path) -> None:
    source = tmp_path / "FY2526.xlsx"
    _book(source, "Project List", ("Chipset models",), [("QFW7114",)])
    with pytest.raises(ChipsetPreviewError, match="workbook_missing"):
        build_preview(
            _settings(source, tmp_path / "missing.xlsx"), today=dt.date(2026, 10, 3)
        )


def test_manifest_is_read_only_and_command_args_are_bounded() -> None:
    workflow = preview_workflow()
    assert workflow.run_alias == 10
    assert PREVIEW_SPEC.side_effect == "read"
    assert isinstance(workflow.steps[0], WorkflowStep)
    assert workflow.steps[0].capability == PREVIEW_SPEC.identity
    assert ChipsetPreviewInput(args="max=20").max_rows == 20
    with pytest.raises(ValidationError):
        ChipsetPreviewInput(args="write")


def test_installed_workflow_10_preview_runs_through_bridge_policy(tmp_path: Path) -> None:
    source, target = tmp_path / "FY2526.xlsx", tmp_path / "target.xlsx"
    _book(
        source,
        "Project List",
        ("Brand", "MFG", "Project Name", "Chipset models", "Status"),
        [("Acme", "OEM", "Device", "QFW7114", "On-going")],
    )
    _book(target, "Chipset_requirement", ("chipset", "Technology"), [])
    grant = {
        "actor": "engineer",
        "asset": PREVIEW_SPEC.identity.model_dump(mode="json"),
        "permissions": list(PREVIEW_SPEC.policy.required_permissions),
        "policy_refs": list(PREVIEW_SPEC.policy.policy_refs),
        "approval_ref": "chipset-read-approval",
    }
    config, layout = workspace(
        tmp_path,
        membership=membership_record(),
        grants=[grant],
        assets=False,
        config_changes={
            "integrations": {
                "chipset_report": {
                    "source_files": [{"path": str(source), "sheet": "Project List"}],
                    "target_file": str(target),
                    "target_header_row": 1,
                }
            }
        },
    )
    export_assets(layout.workspace_root / "assets")
    request = LocalWorkflowRequest(
        actor="engineer",
        bridge_id=config.device.bridge_id,
        workflow=preview_workflow().metadata.identity,
        arguments={},
        idempotency_key="chipset-preview-1",
        trace=TraceIdentifiers(trace_id="chipset", request_id="preview", span_id="test"),
    )
    before = target.read_bytes()
    with build_runtime(config, layout=layout) as runtime:
        outcome = asyncio.run(runtime.agent.execute_workflow(request))
        assert outcome.refusal is None and outcome.workflow is not None
        assert outcome.workflow.run.status == "succeeded", outcome.workflow.run.failure
        preview = ChipsetPreview.model_validate(outcome.workflow.step_results[-1].data)
        assert preview.rows_generated >= 1
    assert target.read_bytes() == before
