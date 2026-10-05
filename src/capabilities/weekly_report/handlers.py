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
from capabilities.weekly_report import chart, effort, mail, rules
from capabilities.weekly_report.apply import apply_plan
from capabilities.weekly_report.contracts import (
    ReportComment,
    ReportingWindow,
    ReportItem,
    SheetState,
    WeeklyMailDrafted,
    WeeklyReportApplied,
    WeeklyReportPlan,
    WeeklyReportRequest,
    WeeklyReportSettings,
)
from capabilities.weekly_report.plan import build_plan, resolve_window
from common.base import Contract, Symbol, Text
from common.execution import RequestContext
from integrations import excel, outlook_draft
from integrations.excel import digest_rows
from integrations.excel_writer import WorkbookWriteError, WorkbookWriter
from integrations.github_project import GitHubError, GitHubProjectClient, ProjectItem
from integrations.outlook_draft import DraftError, DraftWriter, MailDraft

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
            start_time=item.request.start_time,
            end_time=item.request.end_time,
            dry_run=item.request.dry_run,
            draft_mail=item.request.draft_mail,
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
    # Where comments start counting (earlier with a configured look-back),
    # and the precise bounds when the run gave them.
    comment_since: _dt.date | None = None
    start_time: _dt.datetime | None = None
    end_time: _dt.datetime | None = None


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
        window = _Window(item)
        closed = {status.casefold() for status in self.settings.closed_statuses}
        chosen: list[tuple[ProjectItem, tuple[ReportComment, ...]]] = []
        capped = False
        # Selection follows source Workflow 11 (`github_weekly_report.py`):
        # a tracked key, not closed, and moved or commented inside the window.
        for row in rows:
            if not row.key or not _tracked(row, self.settings):
                continue
            status = _field(dict(row.fields), self.settings.status_fields)
            if status.strip().casefold() in closed:
                continue
            active = _active_comments(row, window, self.settings)
            if not (window.contains(row.updated) or active):
                continue
            if item.max_issues is not None and len(chosen) >= item.max_issues:
                capped = True
                break
            chosen.append((row, active))
        found = tuple(_as_item(row, self.settings, active) for row, active in chosen)
        truncated = tuple(
            reported.key
            for reported, (row, _) in zip(found, chosen, strict=True)
            if row.comments_truncated
        )
        return ProjectSearchOutput(items=found, capped=capped, truncated=truncated)


class _Window:
    """In-window by moment when the run gave times, else by day in the
    timestamp's own offset, as the source compares them."""

    def __init__(self, item: ProjectSearchInput) -> None:
        self.since = item.since
        self.comment_since = item.comment_since or item.since
        self.until = item.until
        self.start_time = item.start_time
        self.end_time = item.end_time

    def contains(self, stamp: str | None, *, comments: bool = False) -> bool:
        moment = rules.parse_jira_datetime(stamp) if stamp else None
        if moment is None:
            return False
        if self.start_time is not None or self.end_time is not None:
            if self.start_time is not None and moment < self.start_time:
                return False
            return not (self.end_time is not None and moment > self.end_time)
        start = self.comment_since if comments else self.since
        return start <= moment.date() <= self.until


def _tracked(row: ProjectItem, settings: WeeklyReportSettings) -> bool:
    if settings.tracked_key_prefix is None:
        return True
    carried = CARRIED_KEY.match(dict(row.fields).get("Title") or row.title)
    return carried is not None and carried.group(1).startswith(
        f"{settings.tracked_key_prefix}-"
    )


#: Migrated issues keep the old Excel weekly log under this heading, as
#: `M/D:` sections without comment timestamps.
_MIGRATED_LOG = "## Weekly report comments"
_LOG_DATE = re.compile(r"(?m)^\s*(\d{1,2})/(\d{1,2})\s*:\s*$")


def _active_comments(
    row: ProjectItem, window: _Window, settings: WeeklyReportSettings
) -> tuple[ReportComment, ...]:
    """The comments that count for this window (source `_comments`).

    A comment edited inside the window counts at its edit time. The migrated
    log in the issue body is used only when no real comment with a marker
    falls in the window, so nobody has to write `M/D:` headers in comments.
    """
    active: list[ReportComment] = []
    marked = False
    for comment in row.comments:
        stamp = comment.created
        if comment.updated and window.contains(comment.updated, comments=True):
            stamp = comment.updated
        if not window.contains(stamp, comments=True):
            continue
        active.append(ReportComment(created=stamp or None, body=comment.body))
        if rules.extract_marker_blocks(comment.body, settings.markers):
            marked = True
    if _MIGRATED_LOG in row.body and not marked:
        log = row.body.split(_MIGRATED_LOG, 1)[1]
        sections = list(_LOG_DATE.finditer(log))
        for index, match in enumerate(sections):
            try:
                day = _dt.date(window.until.year, int(match.group(1)), int(match.group(2)))
            except ValueError:
                continue
            stamp = f"{day.isoformat()}T12:00:00+08:00"
            if not window.contains(stamp, comments=True):
                continue
            stop = sections[index + 1].start() if index + 1 < len(sections) else len(log)
            chunk = log[match.end() : stop].strip()
            if chunk:
                active.append(ReportComment(created=stamp, body=chunk))
    return tuple(active)


def _as_item(
    row: ProjectItem,
    settings: WeeklyReportSettings,
    comments: Sequence[ReportComment] | None = None,
) -> ReportItem:
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
        assignee=", ".join(row.issue_assignees),
        issue_assignees=row.issue_assignees,
        company=_field(fields, settings.company_fields),
        sales=_field(fields, settings.sales_fields),
        instrument=_field(fields, settings.instrument_fields),
        updated=row.updated or None,
        comments=tuple(comments) if comments is not None else tuple(
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
    # A dry run: the plan is the answer and nothing is written.
    skip: bool = False


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
        if item.skip:
            return WeeklyReportApplied(
                week=item.plan.window.week,
                workbook=self.settings.workbook_path,
                sheet=self.settings.temp_sheet,
                digest_before=item.plan.sheet_digest,
                digest_after=item.plan.sheet_digest,
                inserted=0, updated=0, highlighted=0, new_rows_marked=0,
                recoloured=0, prepended=0, linked=0, retired_fills=0,
                skipped=True,
            )
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


MAIL_SPEC = CapabilitySpec.model_validate(
    {
        "identity": {"namespace": "weekly-report", "name": "mail", "version": "1.0.0"},
        "name": "weekly_report.mail",
        "description": "Draft the weekly mail, with the week's effort counted and charted",
        "input_contract": "weekly-report.mail.input.v1",
        "output_contract": "weekly-report.mail.output.v1",
        # A draft is a change to the member's own mailbox, so it is a write
        # and needs an approval like every other. It is not a send: nothing
        # in this repository can deliver a mail (`integrations.outlook_draft`).
        "side_effect": "write",
        "policy": {
            "risk": "low",
            "approval_required": True,
            "required_permissions": ["outlook.draft"],
            "policy_refs": ["weekly-report-mail-policy"],
        },
    }
)


class MailInput(Contract):
    window: ReportingWindow
    issues: tuple[ReportItem, ...] = ()


class MailHandler:
    """The week's mail, as a draft nobody has sent.

    The counting narrows what the board matched to what somebody worked on,
    and both numbers come back: a week that matched sixty-three items and
    counted four is either right or badly wrong, and only a reader who is
    told both can tell which.
    """

    def __init__(
        self,
        settings: WeeklyReportSettings,
        writer: Callable[[], DraftWriter],
        *,
        chart_root: Path,
    ) -> None:
        self.settings = WeeklyReportSettings.model_validate(settings)
        self._writer = writer
        self._chart_root = chart_root

    async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
        item = MailInput.model_validate(inputs)
        return await asyncio.to_thread(self._draft, item.window, item.issues)

    def _draft(self, window: ReportingWindow, issues: Sequence[ReportItem]) -> WeeklyMailDrafted:
        if window.dry_run or not window.draft_mail:
            return WeeklyMailDrafted(
                week=window.week,
                subject=mail.subject(window, prefix=self.settings.mail_subject_prefix),
                matched=0, counted=0, skipped=True,
            )
        activity = effort.active_items(
            issues,
            window.since,
            window.until,
            required=self.settings.mail_requires_activity,
        )
        counted = activity.counted
        # The picture is written beside the draft rather than into it: an
        # attachment is a file on disk, and one this run wrote is one it can
        # name in its evidence.
        picture = chart.composite_for(counted)
        images, cid = outlook_draft.images_for(picture, self._chart_root / window.week)
        draft = MailDraft(
            subject=mail.subject(window, prefix=self.settings.mail_subject_prefix),
            html_body=mail.build_html(
                window,
                counted,
                chart_cid=cid,
                matched=len(issues),
                project=self.settings.project,
                activity_required=activity.required,
                prefix=self.settings.mail_subject_prefix,
            ),
            to=outlook_draft.recipients(self.settings.mail_to),
            cc=outlook_draft.recipients(self.settings.mail_cc),
            images=images,
        )
        try:
            receipt = self._writer().save(draft)
        except DraftError as error:
            raise CapabilityRefused(error.code) from None
        return WeeklyMailDrafted(
            week=window.week,
            subject=draft.subject,
            to=draft.to,
            cc=draft.cc,
            entry_id=receipt.entry_id,
            folder=receipt.folder,
            matched=len(issues),
            counted=len(counted),
            excluded=activity.excluded,
            activity_required=activity.required,
            chart_path=images[0].path if images else "",
            preview=mail.build_text(
                window,
                counted,
                matched=len(issues),
                project=self.settings.project,
                prefix=self.settings.mail_subject_prefix,
            ),
        )


PLAN_OUTPUT = WeeklyReportPlan
