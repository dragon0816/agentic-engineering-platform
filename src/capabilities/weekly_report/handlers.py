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
import hashlib
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pydantic import Field

from capabilities.contracts import CapabilitySpec
from capabilities.runtime import TransientCapabilityError
from capabilities.weekly_report import rules
from capabilities.weekly_report.contracts import (
    JiraComment,
    JiraIssue,
    ReportingWindow,
    SheetState,
    WeeklyReportPlan,
    WeeklyReportRequest,
    WeeklyReportSettings,
)
from capabilities.weekly_report.plan import build_plan, resolve_window
from common.base import Contract, Text
from common.execution import RequestContext
from integrations import excel
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
            raw = await asyncio.to_thread(self._fetch, item.jql, item.max_issues)
        except JiraError as error:
            if error.code == "jira_unavailable":
                raise TransientCapabilityError(error.code) from None
            raise
        issues = tuple(_normalize(issue, self.client) for issue in raw)
        capped = item.max_issues is not None and len(issues) >= item.max_issues
        return JiraSearchOutput(jql=item.jql, issues=issues, capped=capped)

    def _fetch(self, jql: str, max_issues: int | None) -> list[dict[str, Any]]:
        issues = self.client.search_issues(jql, rules.REPORT_FIELDS, max_issues=max_issues)
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
        return issues


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
    key = str(issue.get("key") or "")
    return JiraIssue(
        key=key,
        summary=rules.display(fields.get("summary")),
        status=rules.display(fields.get("status")),
        assignee=rules.display(fields.get("assignee")),
        company=rules.display(fields.get(rules.FIELD_COMPANY)),
        sales=rules.display(fields.get(rules.FIELD_SALES)),
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
        if "key" in lowered and "comments" in lowered:
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


def digest_rows(headers: tuple[str, ...], rows: tuple[tuple[str, ...], ...]) -> str:
    """A stable digest of a sheet's text: the evidence's before and after."""
    payload = json.dumps([list(headers), [list(row) for row in rows]], ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


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


PLAN_OUTPUT = WeeklyReportPlan
