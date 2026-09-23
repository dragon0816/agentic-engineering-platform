"""Closed contracts for the weekly report: what a host configures, what a
run asks for, what each step answers, and the plan that is also the preview
and the evidence."""

import datetime as _dt
from pathlib import Path, PureWindowsPath
from typing import Annotated, Any, Literal, Self

from pydantic import Field, StrictBool, StringConstraints, model_validator

from capabilities.weekly_report import rules
from common.assets import reject_embedded_secrets
from common.base import Contract, Sha256, Symbol, Text

Colour = Annotated[str, StringConstraints(pattern=r"^#[0-9A-Fa-f]{6}$")]
BorderStyle = Literal["thin", "medium", "none"]


class WeeklyReportSettings(Contract):
    """What the source read from `config/workflow-w2.json`, minus everything
    secret or machine-specific, with the source's defaults."""

    workbook_path: Text
    temp_sheet: Text = "weekly report temp"
    week_style: rules.WeekStyle = "iso"
    # The two spellings the workbook has used and `parse_week_name` reads.
    week_suffix: Literal["W", ""] = "W"
    project: Symbol = rules.DEFAULT_PROJECT
    statuses: tuple[Text, ...] = rules.DEFAULT_STATUSES
    # A base JQL overrides project and statuses when given; the window is
    # AND-ed onto it and its ORDER BY stays last.
    jql: Text | None = None
    page_size: int = Field(default=100, ge=1, le=100, strict=True)
    max_issues: int | None = Field(default=None, ge=1, strict=True)
    # Canonical marker -> synonyms; None means the observed defaults.
    markers: dict[Text, tuple[Text, ...]] | None = None
    bullet: Annotated[str, StringConstraints(min_length=1, max_length=4)] = "- "
    zero_pad_date: StrictBool = False
    # Widens the comment window backwards for teams that comment late.
    lookback_days: int | None = Field(default=None, ge=1, le=60, strict=True)
    key_highlight: Colour = "#FFF2CC"
    comment_color: Colour = "#FF0000"
    # Forced onto the older text: last week's block is itself red, so letting
    # the tail inherit would turn the whole history red run after run.
    comment_tail_color: Colour = "#000000"
    new_row_fill: Colour = "#FFC7CE"
    new_row_border: BorderStyle = "thin"

    @model_validator(mode="after")
    def absolute_and_secret_free(self) -> Self:
        if not (
            PureWindowsPath(self.workbook_path).is_absolute()
            or Path(self.workbook_path).is_absolute()
        ):
            raise ValueError("workbook_path must be an absolute path")
        if not self.statuses:
            raise ValueError("at least one status selects the board")
        if self.markers is not None and not self.markers:
            raise ValueError("a marker vocabulary names at least one marker")
        reject_embedded_secrets(self.model_dump(mode="json"))
        return self

    def base_jql(self) -> str:
        return self.jql if self.jql else rules.default_jql(self.project, self.statuses)


class WeeklyReportRequest(Contract):
    """What a run asks for, as a remote job's fields or as the text after a
    command (`weekly preview 2026_31W since=2026-07-27 max=50`), which is
    what the deterministic router hands a workflow as `args`. A week is a
    sheet name such as `2026_31W`; a name that is not one is refused rather
    than silently replaced by today's week, which is where the source and
    this port differ."""

    args: str = ""
    week: Text | None = None
    since: _dt.date | None = None
    until: _dt.date | None = None
    max_issues: int | None = Field(default=None, ge=1, strict=True)

    @model_validator(mode="before")
    @classmethod
    def words_become_fields(cls, data: Any) -> Any:
        """`args` is parsed into the fields it names; a field given directly
        wins over the text, and a word that is none of these is refused."""
        if not isinstance(data, dict):
            return data
        text = data.get("args")
        if not isinstance(text, str) or not text.strip():
            return data
        filled = dict(data)
        for word in text.split():
            name, has_value, value = word.partition("=")
            if not has_value and rules.parse_week_name(word) is not None:
                filled.setdefault("week", word)
            elif has_value and name in ("since", "until"):
                filled.setdefault(name, value)
            elif has_value and name in ("max", "max_issues"):
                try:
                    filled.setdefault("max_issues", int(value))
                except ValueError:
                    raise ValueError(f"{name} takes a whole number") from None
            else:
                raise ValueError(
                    "a request is a week such as 2026_31W, since=YYYY-MM-DD, "
                    "until=YYYY-MM-DD or max=N"
                )
        return filled

    @model_validator(mode="after")
    def a_week_is_a_sheet_name(self) -> Self:
        if self.week is not None and rules.parse_week_name(self.week) is None:
            raise ValueError("week is a weekly sheet name such as 2026_31W")
        if self.since is not None and self.until is not None and self.since > self.until:
            raise ValueError("a window ends no earlier than it starts")
        return self


class ReportingWindow(Contract):
    """The week resolved: its name, its window, the comment window (wider
    when a look-back is configured), the date to stamp dateless blocks with,
    the composed JQL and the cap."""

    week: Text
    since: _dt.date
    until: _dt.date
    comment_since: _dt.date
    stamp_date: _dt.date
    jql: Text
    max_issues: int | None = Field(default=None, ge=1, strict=True)

    @model_validator(mode="after")
    def ordered(self) -> Self:
        if self.since > self.until or self.comment_since > self.since:
            raise ValueError("a window ends no earlier than it starts")
        return self


class JiraComment(Contract):
    """One comment as the rules read it: when it was created, as Jira wrote
    the timestamp, and its body flattened to text."""

    created: str | None = None
    body: str = ""


class JiraIssue(Contract):
    """An issue reduced to the report's fields, its comments flattened."""

    key: Symbol
    summary: str = ""
    status: str = ""
    assignee: str = ""
    company: str = ""
    sales: str = ""
    updated: str | None = None
    comments: tuple[JiraComment, ...] = ()
    browse_url: str | None = None


class SheetState(Contract):
    """The scratch sheet as it stands, or the seed sheet when the scratch
    sheet is absent: what the plan needs to decide what to write. `digest`
    is over the scratch sheet's own rows and is the evidence's "before"."""

    headers: tuple[str, ...]
    existing: dict[str, str] = {}
    sheet_names: tuple[str, ...] = ()
    seed_sheet: str | None = None
    scratch_present: StrictBool
    source_sheet: str | None = None
    digest: Sha256

    @model_validator(mode="after")
    def a_source_when_read(self) -> Self:
        if self.scratch_present and self.source_sheet is None:
            raise ValueError("a present scratch sheet is the source read")
        return self


class WeeklyRow(Contract):
    """A weekly-sheet row. `Comments` is deliberately absent: it is a
    hand-maintained log and is only ever prepended to."""

    key: Symbol
    summary: str = ""
    company: str = ""
    status: str = ""
    assignee: str = ""
    sales: str = ""


class CommentOperation(Contract):
    key: Symbol
    text: Text
    markers: tuple[str, ...]
    line_count: int = Field(ge=1, strict=True)


class SkippedComment(Contract):
    key: Symbol
    reason: Text


class Remark(Contract):
    """A block already at the top of the cell that only needs its colour
    back after the run's reset."""

    key: Symbol
    text: Text


class WeeklyReportPlan(Contract):
    """Every row and cell operation, worked out before anything is touched.
    It is what a writer executes, what a dry run shows, and what the parity
    gate grades: the normalized key set, the rows, the blocks and the digest
    of the sheet as it was."""

    window: ReportingWindow
    sales_header: Text
    rows: tuple[WeeklyRow, ...] = ()
    new_keys: tuple[str, ...] = ()
    updated_keys: tuple[str, ...] = ()
    comment_operations: tuple[CommentOperation, ...] = ()
    remarks: tuple[Remark, ...] = ()
    skipped: tuple[SkippedComment, ...] = ()
    highlight_keys: tuple[str, ...] = ()
    # Every key the search returned, sorted: the normalized key set.
    issue_keys: tuple[str, ...] = ()
    # Whether the cap cut the search short: a partial week is said to be one.
    capped: bool = False
    sheet_digest: Sha256
    preview: str

    @model_validator(mode="after")
    def consistent(self) -> Self:
        rows = {row.key for row in self.rows}
        if set(self.new_keys) | set(self.updated_keys) != rows:
            raise ValueError("every planned row is new or updated")
        if set(self.new_keys) & set(self.updated_keys):
            raise ValueError("a row is new or updated, not both")
        if len(self.highlight_keys) != len(set(self.highlight_keys)):
            raise ValueError("a key is tinted once")
        if any(op.key not in rows for op in self.comment_operations):
            raise ValueError("a comment is prepended to a planned row")
        if list(self.issue_keys) != sorted(set(self.issue_keys)):
            raise ValueError("the key set is sorted and unique")
        return self

    def summary(self) -> str:
        return (
            f"{len(self.rows)} row(s) ({len(self.new_keys)} new, "
            f"{len(self.updated_keys)} updated); "
            f"{len(self.comment_operations)} comment block(s) to prepend, "
            f"{len(self.remarks)} to recolour, {len(self.skipped)} skipped"
        )
