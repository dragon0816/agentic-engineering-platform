"""Guarded application of a Workflow 10 preview into the temp sheet only."""

import asyncio
import datetime as dt
import hashlib
import json
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Protocol
from zipfile import BadZipFile, ZipFile

from capabilities.chipset_report.contracts import (
    ChipsetApplied,
    ChipsetApplyInput,
    ChipsetPreview,
    ChipsetReportSettings,
)
from capabilities.chipset_report.preview import ChipsetPreviewError, _read_table
from capabilities.chipset_report.ruleset import Rules, RulesetError, compile_rules, load_ruleset
from capabilities.chipset_report.source_snapshot import commit_candidate
from capabilities.runtime import CapabilityRefused
from common.base import Contract
from common.execution import RequestContext
from integrations import excel
from integrations.excel import WorkbookError
from integrations.excel_writer import (
    WorkbookWriteError,
    stage_workbook,
    unstage_workbook,
    workbook_is_open,
)


class ChipsetWorkbookWriter(Protocol):
    def sheet_names(self, path: Path) -> tuple[str, ...]: ...

    def backup(self, path: Path) -> Path | None: ...

    def replace(
        self,
        path: Path,
        sheet: str,
        headers: Sequence[str],
        records: Sequence[Mapping[str, str | int | float]],
        rules: Rules,
        *,
        format_records: Sequence[Mapping[str, object]] | None = None,
    ) -> int: ...

    def close(self, path: Path, *, save: bool) -> None: ...


def _target_digest(settings: ChipsetReportSettings, path: Path) -> str:
    _, headers, records = _read_table(
        str(path),
        settings.target_sheet,
        header_row=settings.target_header_row,
        max_rows=settings.max_rows,
        source=False,
    )
    payload = json.dumps([headers, records], ensure_ascii=False, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _sheet_digest(path: Path, sheet: str, max_rows: int) -> str:
    _, headers, records = _read_table(
        str(path), sheet, header_row=1, max_rows=max_rows, source=False
    )
    payload = json.dumps([headers, records], ensure_ascii=False, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _macro_bytes(path: Path) -> bytes | None:
    if path.suffix.lower() != ".xlsm":
        return None
    with ZipFile(path) as archive:
        names = [name for name in archive.namelist() if name.lower().endswith("vbaproject.bin")]
        return archive.read(names[0]) if names else None


def _other_sheet_digests(path: Path, temp_sheet: str) -> dict[str, str]:
    """Value/formula preservation check before the staged copy is installed."""
    try:
        import openpyxl
    except ImportError:
        raise CapabilityRefused("library_missing") from None
    book = openpyxl.load_workbook(path, read_only=True, data_only=False)
    try:
        out: dict[str, str] = {}
        for sheet in book:
            if sheet.title == temp_sheet:
                continue
            digest = hashlib.sha256()
            for row in sheet.iter_rows(values_only=True):
                digest.update(json.dumps(row, ensure_ascii=False, default=str).encode("utf-8"))
                digest.update(b"\n")
            out[sheet.title] = digest.hexdigest()
        return out
    finally:
        book.close()


def apply_plan(
    plan: ChipsetPreview,
    settings: ChipsetReportSettings,
    writer: ChipsetWorkbookWriter,
    *,
    staging_root: Path,
    state_dir: Path | None = None,
) -> ChipsetApplied:
    """Refuse stale plans before staging, and copy back only a verified save."""
    settings = ChipsetReportSettings.model_validate(settings)
    plan = ChipsetPreview.model_validate(plan)
    real = Path(settings.target_file)
    if settings.temp_sheet.strip().casefold() == "chipset_requirement":
        raise CapabilityRefused("protected_sheet")
    if plan.temp_sheet != settings.temp_sheet or plan.target_sheet != settings.target_sheet:
        raise CapabilityRefused("plan_settings_changed")
    if not real.is_file():
        raise CapabilityRefused("workbook_missing")
    if workbook_is_open(real) is not None:
        raise CapabilityRefused("workbook_open")
    if _target_digest(settings, real) != plan.target_digest:
        raise CapabilityRefused("target_changed")
    temp_present = settings.temp_sheet in excel.sheet_names(real)
    if temp_present != plan.temp_present:
        raise CapabilityRefused("temp_sheet_changed")
    if temp_present and (
        _sheet_digest(real, settings.temp_sheet, settings.max_rows) != plan.temp_digest
    ):
        raise CapabilityRefused("temp_sheet_changed")
    before_others = _other_sheet_digests(real, settings.temp_sheet)
    before_macro = _macro_bytes(real)
    compiled = compile_rules(load_ruleset(settings.rules_file))
    backup = writer.backup(real) if settings.backup else None
    staged = stage_workbook(real, staging_root)
    working = staged
    finished = False
    try:
        before_sheets = writer.sheet_names(working)
        written = writer.replace(
            working,
            settings.temp_sheet,
            plan.headers,
            plan.records,
            compiled,
            format_records=plan.format_records,
        )
        after_sheets = writer.sheet_names(working)
        if set(after_sheets) - {settings.temp_sheet} != set(before_sheets) - {
            settings.temp_sheet
        }:
            raise CapabilityRefused("sheets_changed")
        finished = True
    finally:
        try:
            writer.close(working, save=finished)
        except WorkbookWriteError as error:
            if finished and error.code == "save_failed":
                raise CapabilityRefused("save_failed") from None
    if _target_digest(settings, working) != plan.target_digest:
        raise CapabilityRefused("managed_sheet_changed")
    if _other_sheet_digests(working, settings.temp_sheet) != before_others:
        raise CapabilityRefused("other_sheets_changed")
    if _macro_bytes(working) != before_macro:
        raise CapabilityRefused("macros_changed")
    sheet_digest = _sheet_digest(working, settings.temp_sheet, settings.max_rows)
    try:
        unstage_workbook(staged, real)
    except WorkbookWriteError:
        raise CapabilityRefused("write_back_failed") from None
    if _sheet_digest(real, settings.temp_sheet, settings.max_rows) != sheet_digest:
        raise CapabilityRefused("copyback_changed")
    snapshot_paths: list[str] = []
    snapshot_warnings: list[str] = []
    if state_dir is not None:
        for source_change in plan.source_changes:
            index = source_change.source_index
            if index < 0 or index >= len(settings.source_files):
                snapshot_warnings.append("source_index_invalid")
                continue
            source = settings.source_files[index]
            if not source.enabled:
                snapshot_warnings.append("source_disabled")
                continue
            try:
                saved = commit_candidate(
                    state_dir,
                    source.path,
                    source_change.candidate,
                    taken_at=dt.datetime.now(dt.UTC),
                    verified_copyback=True,
                )
            except (OSError, ValueError):
                # The workbook succeeded; the optional diff baseline failed.
                snapshot_warnings.append("snapshot_not_saved")
            else:
                snapshot_paths.append(str(saved))
    return ChipsetApplied(
        workbook=str(real),
        sheet=settings.temp_sheet,
        rows_written=written,
        target_digest=plan.target_digest,
        sheet_digest_before=plan.temp_digest,
        sheet_digest=sheet_digest,
        backup_path=str(backup) if backup else None,
        staged_path=str(staged),
        snapshot_paths=tuple(snapshot_paths),
        snapshot_warnings=tuple(snapshot_warnings),
    )


class ChipsetApplyHandler:
    def __init__(
        self,
        settings: ChipsetReportSettings,
        writer: Callable[[], ChipsetWorkbookWriter],
        *,
        staging_root: Path,
        state_dir: Path | None = None,
    ) -> None:
        self.settings = ChipsetReportSettings.model_validate(settings)
        self.writer = writer
        self.staging_root = staging_root
        self.state_dir = state_dir

    async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
        item = ChipsetApplyInput.model_validate(inputs)
        try:
            return await asyncio.to_thread(
                apply_plan,
                item.plan,
                self.settings,
                self.writer(),
                staging_root=self.staging_root,
                state_dir=self.state_dir,
            )
        except (WorkbookWriteError, WorkbookError, ChipsetPreviewError, RulesetError) as error:
            raise CapabilityRefused(str(error)) from None
        except (BadZipFile, ValueError):
            raise CapabilityRefused("invalid_workbook_or_plan") from None
