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
from integrations.excel_writer import BorderStyle, Colour


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
    max_issues: int | None = Field(default=None, ge=1, strict=True)
    # Which board column feeds which of the report's, first non-empty
    # winning. Configuration because the people who use a board rename its
    # columns, and that is not a code change. The defaults are the columns
    # the board carried when it was read on 2026-09-23.
    status_fields: tuple[Text, ...] = ("Status", "GTM Status")
    assignee_fields: tuple[Text, ...] = ("SDE Assignee", "Assignees")
    company_fields: tuple[Text, ...] = ("Company",)
    sales_fields: tuple[Text, ...] = ("Sales",)
    instrument_fields: tuple[Text, ...] = ("Production",)
    # The key given to work that started on the board and never carried one
    # of the workbook's own, as `GH-63`.
    board_key_prefix: Symbol = "GH"
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
    # Drive a local copy and write it back once, which the source measured at
    # 137s against 1001s in a synced folder. Off drives the real file in place.
    local_staging: StrictBool = True
    # Who the weekly mail's draft is addressed to. Empty is allowed and is
    # the safer default: the draft is then written with no recipients and the
    # person who opens it fills them in, which is one more place a mail about
    # the whole team's work cannot leave by itself.
    mail_to: tuple[Text, ...] = ()
    mail_cc: tuple[Text, ...] = ()
    mail_subject_prefix: Text = "GTM weekly report"
    # Count only items somebody actually worked on in the week -- an item
    # whose timestamp moved because a field was edited is not work. Off
    # counts everything the week matched, and the mail says which it did.
    mail_requires_activity: StrictBool = True

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
        named: set[str] = set()

        def take(field: str, value: object) -> None:
            if field in named:
                raise ValueError(f"a request names {field} once")
            named.add(field)
            # A field given directly wins; None is absent, not a choice.
            if filled.get(field) is None:
                filled[field] = value

        for word in text.split():
            name, has_value, value = word.partition("=")
            if not has_value and rules.parse_week_name(word) is not None:
                take("week", word)
            elif has_value and name in ("since", "until"):
                take(name, value)
            elif has_value and name in ("max", "max_issues"):
                try:
                    count = int(value)
                except ValueError:
                    raise ValueError(f"{name} takes a whole number") from None
                take("max_issues", count)
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
    and the cap. What is searched is the host's own board, so there is no
    query here for anybody to have to read."""

    week: Text
    since: _dt.date
    until: _dt.date
    comment_since: _dt.date
    stamp_date: _dt.date
    max_issues: int | None = Field(default=None, ge=1, strict=True)

    @model_validator(mode="after")
    def ordered(self) -> Self:
        if self.since > self.until or self.comment_since > self.since:
            raise ValueError("a window ends no earlier than it starts")
        return self


class ReportComment(Contract):
    """One comment as the rules read it: when it was written, as the source
    wrote the timestamp, and its body flattened to text."""

    created: str | None = None
    body: str = ""


class ReportItem(Contract):
    """One tracked item reduced to the report's fields, its comments
    flattened. Named for what it is and not for where it came from: the
    source moved from Jira to a GitHub Projects board in 2026-09, and
    nothing downstream of this contract had to know."""

    key: Symbol
    summary: str = ""
    status: str = ""
    assignee: str = ""
    company: str = ""
    sales: str = ""
    #: What the work is done on, as the team writes it, several on one
    #: ticket included. The workbook does not carry it; the mail counts by
    #: it.
    instrument: str = ""
    updated: str | None = None
    comments: tuple[ReportComment, ...] = ()
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
    #: Where this row's key cell links to. Carried per row rather than
    #: composed from a site and a key: Jira's addresses were
    #: `<site>/browse/<key>` and a board's are not, and the plan has to be
    #: the whole instruction whatever the source was.
    url: str = ""


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
    #: Items whose comment thread was longer than one page of the source's
    #: answer. Named on the plan, because a thread read short is a week
    #: reported wrong and the plan is what a reader checks.
    truncated_threads: tuple[Symbol, ...] = ()
    # The scratch sheet as it stood when this was planned. A writer that finds
    # a different digest is looking at a sheet somebody has changed since.
    sheet_digest: Sha256
    scratch_present: StrictBool = False
    seed_sheet: Text | None = None
    # The sheet's own header row, so a writer addresses the columns the
    # member actually has rather than the ones the contract names.
    sheet_headers: tuple[str, ...] = ()
    # The Jira site the key cells link to, taken from the issues themselves.
    #: Kept for a plan made before rows carried their own link.
    browse_base: Text | None = None
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


class FailedComment(Contract):
    """A comment cell the writer could not write. The source kept going and
    reported these rather than failing the week's report over one cell, and
    so does this; they are in the evidence either way."""

    key: Symbol
    reason: Text


class WeeklyReportApplied(Contract):
    """What writing the plan did, and the evidence the parity gate names:
    the scratch sheet's digest on both sides of the write, the backup that
    was taken, and every count the source reported."""

    week: Text
    workbook: Text
    sheet: Text
    digest_before: Sha256
    digest_after: Sha256
    backup_path: Text | None = None
    staged_path: Text | None = None
    inserted: int = Field(ge=0, strict=True)
    updated: int = Field(ge=0, strict=True)
    highlighted: int = Field(ge=0, strict=True)
    new_rows_marked: int = Field(ge=0, strict=True)
    recoloured: int = Field(ge=0, strict=True)
    prepended: int = Field(ge=0, strict=True)
    linked: int = Field(ge=0, strict=True)
    retired_fills: int = Field(ge=0, strict=True)
    failures: tuple[FailedComment, ...] = ()

    def summary(self) -> str:
        return (
            f"{self.inserted} inserted, {self.updated} updated, "
            f"{self.prepended} block(s) prepended, {self.recoloured} recoloured, "
            f"{len(self.failures)} failed"
        )


class WeeklyMailDrafted(Contract):
    """What the weekly mail's draft is, and what it counted.

    The body is not here. It is in the draft, which is where a person reads
    it; carrying the whole mail back through a run record would put the
    team's own titles and comments into a log that is kept for months.
    `preview` is the plain-text rendering, which is the thing worth reading
    before opening Outlook.
    """

    week: Text
    subject: Text
    to: tuple[Text, ...] = ()
    cc: tuple[Text, ...] = ()
    # Outlook's own identifier for the saved item, and the folder it landed
    # in. Neither is a secret and neither carries content.
    entry_id: str = ""
    folder: str = ""
    matched: int = Field(ge=0, strict=True)
    counted: int = Field(ge=0, strict=True)
    # Named rather than counted: fifty-nine items vanishing from a week with
    # only a number to show for it is how a wrong week goes unnoticed.
    excluded: tuple[Symbol, ...] = ()
    # Whether the count was narrowed to items somebody worked on, so a reader
    # of the record knows which of two questions these numbers answer.
    activity_required: StrictBool = True
    chart_path: str = ""
    preview: str = ""

    @model_validator(mode="after")
    def counted_is_what_is_left(self) -> Self:
        if self.counted + len(self.excluded) != self.matched:
            raise ValueError("every matched item is either counted or named as excluded")
        return self
