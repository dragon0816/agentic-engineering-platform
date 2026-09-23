"""The four read capabilities that take the weekly report up to its plan.

Each has a spec, a closed input and output, and a handler the host builds
from its configuration. None writes anything: the fetch reads Jira, the
sheet step reads the workbook's bytes, and the other two compute. A failure
is raised, which the Bridge executor turns into a failed step and the run
into a failed run — there is no false success — and a Jira outage is a
`TransientCapabilityError`, which is the one kind a read step may retry.
"""

import asyncio
import datetime as _dt
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pydantic import Field

from capabilities.contracts import CapabilitySpec
from capabilities.runtime import CapabilityRefused, TransientCapabilityError
from capabilities.weekly_report import rules
from capabilities.weekly_report.apply import apply_plan
from capabilities.weekly_report.contracts import (
    JiraComment,
    JiraIssue,
    ReportingWindow,
    SheetState,
    WeeklyReportApplied,
    WeeklyReportPlan,
    WeeklyReportRequest,
    WeeklyReportSettings,
)
from capabilities.weekly_report.plan import build_plan, resolve_window
from common.base import Contract, Text
from common.execution import RequestContext
from integrations import excel
from integrations.excel import digest_rows
from integrations.excel_writer import WorkbookWriteError, WorkbookWriter
from integrations.jira import JiraClient, JiraError

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

JIRA_SEARCH_SPEC = CapabilitySpec.model_validate(
    {
        "identity": {"namespace": "jira", "name": "search", "version": "1.0.0"},
        "name": "jira.search",
        "description": "Search Jira issues by JQL with their comment threads, under a cap",
        "input_contract": "jira.search.input.v1",
        "output_contract": "jira.search.output.v1",
        "side_effect": "read",
        "policy": {"required_permissions": ["jira.read"], "policy_refs": ["jira-read-policy"]},
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


class JiraSearchInput(Contract):
    jql: Text
    max_issues: int | None = Field(default=None, ge=1, strict=True)


class JiraSearchOutput(Contract):
    jql: Text
    issues: tuple[JiraIssue, ...] = ()
    # Whether the cap cut the result short: the report then says so rather
    # than passing a partial week off as the whole one.
    capped: bool = False


class JiraSearchHandler:
    """The source's `fetch_week_issues` and `hydrate_comments`: the search
    with the report's fields, then a comment thread re-fetched for every
    issue the search truncated."""

    def __init__(self, client: JiraClient) -> None:
        self.client = client

    async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
        item = JiraSearchInput.model_validate(inputs)
        try:
            raw, capped = await asyncio.to_thread(self._fetch, item.jql, item.max_issues)
        except JiraError as error:
            if error.code == "jira_unavailable":
                raise TransientCapabilityError(error.code) from None
            raise
        issues = tuple(_normalize(issue, self.client) for issue in raw)
        return JiraSearchOutput(jql=item.jql, issues=issues, capped=capped)

    def _fetch(self, jql: str, max_issues: int | None) -> tuple[list[dict[str, Any]], bool]:
        # One past the cap, so a week of exactly the cap's size is not
        # reported as cut short.
        asked = max_issues + 1 if max_issues is not None else None
        fetched = self.client.search_issues(jql, rules.REPORT_FIELDS, max_issues=asked)
        capped = max_issues is not None and len(fetched) > max_issues
        issues = fetched[:max_issues] if max_issues is not None else fetched
        for issue in issues:
            fields = issue.setdefault("fields", {})
            block = fields.get("comment") or {}
            got = list(block.get("comments") or [])
            total = block.get("total")
            if total is None or len(got) >= int(total):
                fields["comment"] = {"comments": got, "total": total or len(got)}
                continue
            # The search endpoint truncates embedded comments (the live site
            # returns one), so the thread is fetched on its own.
            full = self.client.comments(str(issue.get("key")))
            fields["comment"] = {"comments": full, "total": len(full)}
        return issues, capped


def _normalize(issue: dict[str, Any], client: JiraClient) -> JiraIssue:
    fields = issue.get("fields") or {}
    thread = (fields.get("comment") or {}).get("comments") or []
    comments = tuple(
        JiraComment(
            created=str(item.get("created") or item.get("updated") or "") or None,
            body=rules.comment_body_text(item.get("body")),
        )
        for item in thread
        if isinstance(item, dict)
    )
    # The one mapping of Jira fields to the sheet's columns, the rules' own.
    row = rules.issue_to_row(issue)
    key = row["Key"]
    return JiraIssue(
        key=key,
        summary=row["Summary"],
        status=row["Status"],
        assignee=row["Assignee"],
        company=row["Company"],
        sales=row["Sales"],
        updated=str(fields.get("updated")) if fields.get("updated") else None,
        comments=comments,
        browse_url=client.browse_url(key),
    )


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
    issues: tuple[JiraIssue, ...] = ()
    capped: bool = False
    sheet: SheetState


class PlanHandler:
    def __init__(self, settings: WeeklyReportSettings) -> None:
        self.settings = WeeklyReportSettings.model_validate(settings)

    async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
        item = PlanInput.model_validate(inputs)
        return build_plan(self.settings, item.window, item.issues, item.sheet, capped=item.capped)


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
