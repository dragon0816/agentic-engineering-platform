"""Static host settings and read-only run contracts for source Workflow 10."""

from pathlib import Path, PureWindowsPath
from typing import Self

from pydantic import Field, JsonValue, StrictBool, model_validator

from common.assets import reject_embedded_secrets
from common.base import Contract, Sha256, Text


def _absolute(value: str) -> bool:
    return PureWindowsPath(value).is_absolute() or Path(value).is_absolute()


class ChipsetSource(Contract):
    path: Text
    sheet: Text | None = None
    fiscal_year: Text | None = None
    enabled: StrictBool = True

    @model_validator(mode="after")
    def local_file(self) -> Self:
        if not _absolute(self.path):
            raise ValueError("source path must be absolute")
        return self


class ChipsetReportSettings(Contract):
    """The source's workflow-w1.json settings, with no per-run file picker."""

    source_files: tuple[ChipsetSource, ...] = Field(min_length=1)
    target_file: Text
    target_sheet: Text = "Chipset_requirement"
    temp_sheet: Text = "temp"
    # The real macro workbook has its headers on row 2; never guess row 1.
    target_header_row: int = Field(ge=1, strict=True)
    rules_file: Text | None = None
    include_statuses: tuple[Text, ...] | None = None
    exclude_statuses: tuple[Text, ...] = ("Lost",)
    max_rows: int = Field(default=5000, ge=1, le=50000, strict=True)
    write_trace_columns: StrictBool = True
    backup: StrictBool = True

    @model_validator(mode="after")
    def guarded_paths(self) -> Self:
        if not any(source.enabled for source in self.source_files):
            raise ValueError("at least one source must be enabled")
        if not _absolute(self.target_file):
            raise ValueError("target_file must be absolute")
        if self.rules_file is not None and not _absolute(self.rules_file):
            raise ValueError("rules_file must be absolute")
        if self.temp_sheet.strip().casefold() == "chipset_requirement":
            raise ValueError("temp_sheet must never be the managed sheet")
        if self.temp_sheet.strip().casefold() == self.target_sheet.strip().casefold():
            raise ValueError("temp_sheet must differ from target_sheet")
        reject_embedded_secrets(self.model_dump(mode="json"))
        return self


class ChipsetPreviewInput(Contract):
    """An empty request uses the host's static settings; max limits a preview."""

    args: str = ""
    max_rows: int | None = Field(default=None, ge=1, le=50000, strict=True)

    @model_validator(mode="after")
    def parse_command(self) -> Self:
        if not self.args.strip():
            return self
        words = self.args.split()
        if len(words) != 1 or not words[0].startswith("max="):
            raise ValueError("Workflow 10 preview accepts only max=N")
        try:
            value = int(words[0][4:])
        except ValueError:
            raise ValueError("max must be a whole number") from None
        if not 1 <= value <= 50000:
            raise ValueError("max must be between 1 and 50000")
        if self.max_rows is not None and self.max_rows != value:
            raise ValueError("max is specified twice")
        object.__setattr__(self, "max_rows", value)
        return self


class ChipsetPreviewStepInput(Contract):
    request: ChipsetPreviewInput = ChipsetPreviewInput()


class ChipsetSourceSummary(Contract):
    source_index: int
    sheet: Text | None = None
    fiscal_year: Text | None = None
    rows: int = 0
    skipped: StrictBool = False


class ChipsetSourceChange(Contract):
    source_index: int
    summary: str
    critical_count: int
    diff: dict[str, JsonValue]
    candidate: dict[str, dict[str, str | int]]


class DroppedChipsetEvidence(Contract):
    project: str
    fiscal_year: str
    row_number: int
    raw: str
    parsed: str
    reason: str


class ChipsetPreview(Contract):
    """The plan is the dry-run evidence; this contract cannot write a workbook."""

    target_sheet: Text
    temp_sheet: Text
    target_digest: Sha256
    temp_digest: Sha256 | None = None
    temp_present: StrictBool = False
    managed_headers: tuple[str, ...]
    headers: tuple[str, ...]
    records: tuple[dict[str, str | int | float], ...]
    format_records: tuple[dict[str, str | int | float], ...]
    row_fills: tuple[str, ...] = ()
    dropped: tuple[DroppedChipsetEvidence, ...] = ()
    sources: tuple[ChipsetSourceSummary, ...]
    source_changes: tuple[ChipsetSourceChange, ...] = ()
    projects_read: int
    projects_included: int
    rows_generated: int
    chipsets_extracted: int
    unresolved_technology: int
    match_counts: dict[str, int]
    dropped_count: int
    watched_missing: tuple[str, ...]


class ChipsetApplyInput(Contract):
    plan: ChipsetPreview


class ChipsetApplied(Contract):
    workbook: Text
    sheet: Text
    rows_written: int
    target_digest: Sha256
    sheet_digest_before: Sha256 | None = None
    sheet_digest: Sha256
    backup_path: Text | None = None
    staged_path: Text | None = None
    snapshot_paths: tuple[Text, ...] = ()
    snapshot_warnings: tuple[str, ...] = ()
