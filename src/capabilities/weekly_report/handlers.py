"""The four read capabilities that take the weekly report up to its plan.

Each has a spec, a closed input and output, and a handler the host builds
from its configuration. None writes anything: the fetch reads the board, the
sheet step reads the workbook's bytes, and the other two compute. A failure
is raised, which the Bridge executor turns into a failed step and the run
into a failed run — there is no false success — and a source outage is a
`TransientCapabilityError`, which is the one kind a read step may retry.
"""

import asyncio
import datetime as _dt
import re
from collections.abc import Callable, Sequence
from pathlib import Path

from pydantic import Field

from capabilities.contracts import CapabilitySpec
from capabilities.runtime import CapabilityRefused, TransientCapabilityError
from capabilities.weekly_report import rules
from capabilities.weekly_report.apply import apply_plan
from capabilities.weekly_report.contracts import (
    ReportComment,
    ReportingWindow,
    ReportItem,
    SheetState,
    WeeklyReportApplied,
    WeeklyReportPlan,
    WeeklyReportRequest,
    WeeklyReportSettings,
)
from capabilities.weekly_report.plan import build_plan, resolve_window
from common.base import Contract, Symbol, Text
from common.execution import RequestContext
from integrations import excel
from integrations.excel import digest_rows
from integrations.excel_writer import WorkbookWriteError, WorkbookWriter
from integrations.github_project import GitHubError, GitHubProjectClient, ProjectItem

RESOLVE_WINDOW_SPEC = CapabilitySpec.model_validate(
    {
        "identity": {"namespace": "weekly-report", "name": "resolve-window", "version": "1.0.0"},
        "name": "weekly_report.resolve_window",
        "description": "Resolve the reporting week, its window, the stamp date and the JQL",
        "input_contract": "weekly-report.resolve-window.input.v1",
        "output_contract": "weekly-report.resolve-window.output.v1",
        "side_effect": "read",
        "policy": {
            "required_permissions": ["weekly-report.plan"],
            "policy_refs": ["weekly-report-policy"],
        },
    }
)

PROJECT_SEARCH_SPEC = CapabilitySpec.model_validate(
    {
        "identity": {"namespace": "github", "name": "search-project", "version": "1.0.0"},
        "name": "github.search_project",
        "description": "Read the week's items and their comment threads from a project board",
        "input_contract": "github.search-project.input.v1",
        "output_contract": "github.search-project.output.v1",
        "side_effect": "read",
        "policy": {"required_permissions": ["github.read"], "policy_refs": ["github-read-policy"]},
    }
)

READ_SCRATCH_SHEET_SPEC = CapabilitySpec.model_validate(
    {
        "identity": {"namespace": "excel", "name": "read-scratch-sheet", "version": "1.0.0"},
        "name": "excel.read_scratch_sheet",
        "description": "Read the weekly workbook's scratch sheet, or its seed, without Excel",
        "input_contract": "excel.read-scratch-sheet.input.v1",
        "output_contract": "excel.read-scratch-sheet.output.v1",
        "side_effect": "read",
        "policy": {"required_permissions": ["excel.read"], "policy_refs": ["excel-read-policy"]},
    }
)

PLAN_SPEC = CapabilitySpec.model_validate(
    {
        "identity": {"namespace": "weekly-report", "name": "plan", "version": "1.0.0"},
        "name": "weekly_report.plan",
        "description": "Decide every row and cell operation of the weekly report before writing",
        "input_contract": "weekly-report.plan.input.v1",
        "output_contract": "weekly-report.plan.output.v1",
        "side_effect": "read",
        "policy": {
            "required_permissions": ["weekly-report.plan"],
            "policy_refs": ["weekly-report-policy"],
        },
    }
)


class ResolveWindowInput(Contract):
    request: WeeklyReportRequest = WeeklyReportRequest()


class ResolveWindowHandler:
    def __init__(
        self, settings: WeeklyReportSettings, *, today: Callable[[], _dt.date] | None = None
    ) -> None:
        self.settings = WeeklyReportSettings.model_validate(settings)
        self._today = today if today is not None else _dt.date.today

    async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
        item = ResolveWindowInput.model_validate(inputs)
        return resolve_window(
            self.settings,
            week=item.request.week,
            since=item.request.since,
            until=item.request.until,
            max_issues=item.request.max_issues,
            today=self._today(),
        )


#: A key the workbook already uses, carried in the item's title by the
#: rebuild: `[GTM-833] ...`. It is what matches a row this report wrote in an
#: earlier week, so it wins over anything this platform could invent.
CARRIED_KEY = re.compile(r"^\s*\[([A-Za-z][A-Za-z0-9_]*-\d+)\]\s*")


class ProjectSearchInput(Contract):
    """The window the week implies, or the one a run asked for."""

    since: _dt.date
    until: _dt.date
    max_issues: int | None = Field(default=None, ge=1, strict=True)


class ProjectSearchOutput(Contract):
    items: tuple[ReportItem, ...] = ()
    # Whether the cap cut the result short: the report then says so rather
    # than passing a partial week off as the whole one.
    capped: bool = False
    # Items whose comment thread was longer than one page. Named rather than
    # counted, because a truncated thread is a week reported wrong.
    truncated: tuple[Symbol, ...] = ()


class ProjectSearchHandler:
    """The week's items, read from the board that replaced Jira.

    The board is read whole and the week is selected here, because a project
    board has no query language to push a window into. That is cheap at this
    size and honest at any: the alternative is a filter the board cannot
    apply and this code pretending it did.
    """

    def __init__(self, client: GitHubProjectClient, settings: WeeklyReportSettings) -> None:
        self.client = client
        self.settings = WeeklyReportSettings.model_validate(settings)

    async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
        item = ProjectSearchInput.model_validate(inputs)
        try:
            rows = await asyncio.to_thread(self.client.items)
        except GitHubError as error:
            # A throttle and an outage are the same answer to a caller: try
            # later. Everything else is a refusal this run cannot fix.
            if error.code in ("github_unavailable", "github_rate_limited"):
                raise TransientCapabilityError(error.code) from None
            raise CapabilityRefused(error.code) from None
        # A card nobody has filed as an issue has no key, no history and no
        # comments, so it can never carry a week's work. Including it gave
        # every such card the same key and merged them into one row.
        tracked = [row for row in rows if row.key]
        chosen = [row for row in tracked if _within(row.updated, item.since, item.until)]
        capped = item.max_issues is not None and len(chosen) > item.max_issues
        if item.max_issues is not None:
            chosen = chosen[: item.max_issues]
        found = tuple(_as_item(row, self.settings) for row in chosen)
        truncated = tuple(
            reported.key
            for reported, row in zip(found, chosen, strict=True)
            if row.comments_truncated
        )
        return ProjectSearchOutput(items=found, capped=capped, truncated=truncated)


def _within(stamp: str, since: _dt.date, until: _dt.date) -> bool:
    """Whether an item moved inside the week. An item with no timestamp is
    included: the board answered without one, and dropping a row because a
    field was empty is how a week goes quietly missing."""
    moment = rules.parse_jira_datetime(stamp) if stamp else None
    if moment is None:
        return True
    day = moment.date()
    return since <= day <= until


def _as_item(row: ProjectItem, settings: WeeklyReportSettings) -> ReportItem:
    """One board row as the report reads it.

    The board's fields are authoritative for the columns people maintain
    there, by the owner's decision of 2026-09-23; which field feeds which
    column is configuration, because a board's columns are renamed by the
    people who use it and that is not a code change.
    """
    fields = dict(row.fields)
    title = fields.get("Title") or row.title
    carried = CARRIED_KEY.match(title)
    if carried:
        key = carried.group(1)
        summary = title[carried.end() :].strip()
    else:
        # Work that started on the board and never had a key of its own. The
        # issue number is what makes it one row rather than all of them:
        # a row with no number at all is not read (see `tracked` above).
        number = row.key.rsplit("#", 1)[-1]
        key = f"{settings.board_key_prefix}-{number}"
        summary = title.strip()
    return ReportItem(
        key=key,
        summary=summary,
        status=_field(fields, settings.status_fields),
        assignee=_field(fields, settings.assignee_fields),
        company=_field(fields, settings.company_fields),
        sales=_field(fields, settings.sales_fields),
        instrument=_field(fields, settings.instrument_fields),
        updated=row.updated or None,
        comments=tuple(
            ReportComment(created=comment.created or None, body=comment.body)
            for comment in row.comments
        ),
        browse_url=row.url or None,
    )


def _field(fields: dict[str, str], names: Sequence[str]) -> str:
    """The first of these columns the board actually has a value in."""
    for name in names:
        value = fields.get(name)
        if value:
            return value
    return ""


class ReadScratchSheetInput(Contract):
    week: Text


class ReadScratchSheetHandler:
    """The scratch sheet as it stands, read from the file's bytes: never
    Excel, never a write. When the scratch sheet is absent the seed sheet is
    read instead, which is what the sheet would be seeded from."""

    def __init__(self, settings: WeeklyReportSettings) -> None:
        self.settings = WeeklyReportSettings.model_validate(settings)

    async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
        item = ReadScratchSheetInput.model_validate(inputs)
        return await asyncio.to_thread(self._read, item.week)

    def _read(self, week: str) -> SheetState:
        path = Path(self.settings.workbook_path)
        scratch = self.settings.temp_sheet
        before = rules.parse_week_name(week)

        def choose(names: tuple[str, ...]) -> str | None:
            return scratch if scratch in names else rules.latest_weekly_sheet(names, before=before)

        names, source, read_headers, rows = excel.read_chosen_sheet(path, choose)
        seed = rules.latest_weekly_sheet(names, before=before)
        present = scratch in names
        if source is None:
            return SheetState(
                headers=rules.WEEKLY_COLUMNS,
                sheet_names=names,
                seed_sheet=None,
                scratch_present=False,
                digest=digest_rows((), ()),
            )
        # The digest is of the sheet as it stands, headers as read; the
        # column contract stands in only for the plan's own lookups.
        headers = read_headers
        if not any(header.strip() for header in headers):
            headers = rules.WEEKLY_COLUMNS
        existing: dict[str, str] = {}
        lowered = [header.strip().lower() for header in headers]
        if "key" not in lowered or "comments" not in lowered:
            # A sheet the plan cannot read is refused, not planned as empty:
            # every tracked ticket would otherwise be proposed as new.
            raise ValueError(f"sheet {source!r} has no Key and Comments columns in its header row")
        key_index, comments_index = lowered.index("key"), lowered.index("comments")
        for row in rows:
            if key_index >= len(row):
                continue
            key = row[key_index].strip()
            if key:
                existing[key] = row[comments_index] if comments_index < len(row) else ""
        return SheetState(
            headers=tuple(header.strip() for header in headers),
            existing=existing,
            sheet_names=names,
            seed_sheet=seed,
            scratch_present=present,
            source_sheet=source,
            # The digest is of the scratch sheet as it stands: when it is
            # absent there is nothing to have changed.
            digest=digest_rows(read_headers, rows) if present else digest_rows((), ()),
        )


APPLY_SPEC = CapabilitySpec.model_validate(
    {
        "identity": {"namespace": "weekly-report", "name": "apply", "version": "1.0.0"},
        "name": "weekly_report.apply",
        "description": "Write a weekly report plan into the team's workbook",
        "input_contract": "weekly-report.apply.input.v1",
        "output_contract": "weekly-report.apply.output.v1",
        # The first side effect in this repository: it changes a file the
        # team reads, so the Bridge policy refuses it without an approval.
        "side_effect": "write",
        "policy": {
            "risk": "medium",
            "approval_required": True,
            "required_permissions": ["excel.write"],
            "policy_refs": ["weekly-report-write-policy"],
        },
    }
)


class PlanInput(Contract):
    window: ReportingWindow
    issues: tuple[ReportItem, ...] = ()
    capped: bool = False
    truncated_threads: tuple[Symbol, ...] = ()
    sheet: SheetState


class PlanHandler:
    def __init__(self, settings: WeeklyReportSettings) -> None:
        self.settings = WeeklyReportSettings.model_validate(settings)

    async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
        item = PlanInput.model_validate(inputs)
        return build_plan(
            self.settings,
            item.window,
            item.issues,
            item.sheet,
            capped=item.capped,
            truncated_threads=item.truncated_threads,
        )


class ApplyInput(Contract):
    """The plan is the whole instruction: it carries the sheet it was made
    against, the seed to create one from, and the site the keys link to."""

    plan: WeeklyReportPlan


class ApplyHandler:
    """Write the plan through whichever `WorkbookWriter` the host built.

    The writer is made per run and closed by the executor, so a failed run
    never leaves Excel holding the file. A refusal the member can act on
    keeps its own code on the failed step.
    """

    def __init__(
        self,
        settings: WeeklyReportSettings,
        writer: Callable[[], WorkbookWriter],
        *,
        staging_root: Path,
    ) -> None:
        self.settings = WeeklyReportSettings.model_validate(settings)
        self._writer = writer
        self._staging_root = staging_root

    async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
        item = ApplyInput.model_validate(inputs)
        return await asyncio.to_thread(self._apply, item.plan)

    def _apply(self, plan: WeeklyReportPlan) -> WeeklyReportApplied:
        try:
            writer = self._writer()
        except WorkbookWriteError as error:
            raise CapabilityRefused(error.code) from None
        try:
            return apply_plan(plan, self.settings, writer, staging_root=self._staging_root)
        except WorkbookWriteError as error:
            # Everything a workbook can refuse keeps its own code, so the
            # member is told which of "somebody has it open", "it is not
            # there" and "the write failed" happened.
            raise CapabilityRefused(error.code) from None


PLAN_OUTPUT = WeeklyReportPlan
