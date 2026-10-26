"""Preview a week of Workflow 11 into one folder, without touching anything.

    python -m capabilities.weekly_report.preview --week 2026_43W --out <dir>
    python -m capabilities.weekly_report.preview --week 2026_43W --out <dir> --fixture

The real mode reads the host's own `host.json` (the default is the Windows
preview install's), the GitHub board through the same client and credential
mapping the Workflow uses (`AEP_GITHUB_TOKEN` behind the `board_token`
secret, never printed), and plans the week with the Workflow's own steps:
`resolve_window`, the board search, the sheet read and `build_plan`. The
fixture mode uses a synthetic board and a synthetic workbook of the same
structure and needs no credential and no network.

Everything is written under `--out` and nowhere else:

* `email.html` and `effort-chart.png`: the draft body exactly as the mail
  step composes it (`handlers.compose_draft`), with only the inline image's
  `cid:` reference pointed at the PNG beside it so a browser shows it.
* `workbook-preview.xlsx`: a copy of the configured workbook with the week's
  sheet written by the real executor (`apply.apply_plan`) through an
  openpyxl writer, Key cells linked to their Issues. The configured workbook
  is only read, to copy it.
* `plan.json`: every ticket's key, link, assignee and where it came from,
  instruments, whether it was commented in the window, what the sheet plan
  does with it, and the counts.
* fixture mode only: `fixture-workbook.xlsx`, the synthetic source workbook.

Nothing here writes the real workbook, opens Outlook or sends anything.
"""

from __future__ import annotations

import argparse
import asyncio
import datetime as _dt
import json
import os
import shutil
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Protocol

from capabilities.weekly_report import effort, mail
from capabilities.weekly_report.apply import apply_plan
from capabilities.weekly_report.contracts import (
    ReportingWindow,
    ReportItem,
    SheetState,
    WeeklyReportApplied,
    WeeklyReportPlan,
    WeeklyReportSettings,
)
from capabilities.weekly_report.handlers import (
    ProjectSearchHandler,
    ProjectSearchInput,
    ProjectSearchOutput,
    ReadScratchSheetHandler,
    ReadScratchSheetInput,
    compose_draft,
)
from capabilities.weekly_report.plan import build_plan, resolve_window
from capabilities.weekly_report.rules import WEEKLY_COLUMNS, parse_report_time
from common.execution import RequestContext, TraceIdentifiers
from integrations.excel_openpyxl import OpenpyxlWorkbookWriter
from integrations.github_project import ProjectComment, ProjectItem

PREVIEW_WORKBOOK = "workbook-preview.xlsx"
FIXTURE_WORKBOOK = "fixture-workbook.xlsx"
CHART_CID = "effort-chart"


class BoardReader(Protocol):
    def items(self) -> list[ProjectItem]: ...


def _context() -> RequestContext:
    return RequestContext(
        trace=TraceIdentifiers(trace_id="preview", request_id="preview", span_id="preview"),
        actor="preview",
        namespace="engineering",
        channel="preview",
        message="weekly report preview",
    )


def default_config() -> Path:
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(base) / "AgenticEngineeringPlatform" / "preview-0.1.0" / "host.json"


def run_preview(
    settings: WeeklyReportSettings,
    board: BoardReader,
    out: Path,
    *,
    week: str | None,
    today: _dt.date,
    start_time: _dt.datetime | None = None,
    end_time: _dt.datetime | None = None,
    source_label: str = "",
) -> dict[str, Any]:
    """Plan the week as the Workflow does and write the preview into `out`.
    Returns what `plan.json` holds."""
    out.mkdir(parents=True, exist_ok=True)
    configured = Path(settings.workbook_path)
    copy = out / PREVIEW_WORKBOOK
    # Copy first and plan against the copy: the plan's sheet digest is then
    # of exactly the bytes the executor writes, and the configured workbook
    # is read once, by the copy.
    shutil.copyfile(configured, copy)
    local = settings.model_copy(update={"workbook_path": str(copy), "local_staging": False})

    window = resolve_window(
        settings,
        week=week,
        since=None,
        until=None,
        max_issues=None,
        today=today,
        start_time=start_time,
        end_time=end_time,
        dry_run=False,
        draft_mail=True,
    )
    context = _context()
    found = asyncio.run(
        ProjectSearchHandler(board, settings)(  # type: ignore[arg-type]
            context,
            ProjectSearchInput(
                since=window.since,
                until=window.until,
                max_issues=window.max_issues,
                comment_since=window.comment_since,
                start_time=window.start_time,
                end_time=window.end_time,
            ),
        )
    )
    assert isinstance(found, ProjectSearchOutput)
    sheet = asyncio.run(
        ReadScratchSheetHandler(local)(context, ReadScratchSheetInput(week=window.week))
    )
    assert isinstance(sheet, SheetState)
    plan = build_plan(
        local,
        window,
        found.items,
        sheet,
        capped=found.capped,
        truncated_threads=found.truncated,
    )
    applied = apply_plan(plan, local, OpenpyxlWorkbookWriter(), staging_root=out)
    chart_note = _write_mail(settings, window, found.items, out)
    record = _record(
        settings, window, found, plan, applied, chart_note=chart_note, source=source_label
    )
    (out / "plan.json").write_text(
        json.dumps(record, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )
    return record


def _write_mail(
    settings: WeeklyReportSettings,
    window: ReportingWindow,
    items: Sequence[ReportItem],
    out: Path,
) -> str:
    """`email.html` and the chart, from the mail step's own composition."""
    try:
        draft, _ = compose_draft(settings, window, items, out)
    except ImportError:
        # The chart needs the optional `weekly-mail` extra; the body is the
        # draft's without its picture, exactly as `build_html` renders that.
        activity = effort.active_items(
            items, window.since, window.until, required=settings.mail_requires_activity
        )
        html = mail.build_html(
            window,
            activity.counted,
            chart_cid="",
            matched=len(items),
            project=settings.project,
            activity_required=activity.required,
            prefix=settings.mail_subject_prefix,
        )
        (out / "email.html").write_text(html, encoding="utf-8")
        return "matplotlib is not installed: no chart (install the weekly-mail extra)"
    html = draft.html_body.replace(f"cid:{CHART_CID}", f"{CHART_CID}.png")
    (out / "email.html").write_text(html, encoding="utf-8")
    return ""


def _record(
    settings: WeeklyReportSettings,
    window: ReportingWindow,
    found: ProjectSearchOutput,
    plan: WeeklyReportPlan,
    applied: WeeklyReportApplied,
    *,
    chart_note: str,
    source: str,
) -> dict[str, Any]:
    new, updated = set(plan.new_keys), set(plan.updated_keys)
    skipped = {item.key: item.reason for item in plan.skipped}
    blocks = {operation.key: operation.text for operation in plan.comment_operations}
    tickets = []
    for item in found.items:
        commented = effort.commented_in_week(item, window.since, window.until)
        if item.key in new:
            sheet_action = "new row"
        elif item.key in updated:
            sheet_action = "updated row"
        else:
            sheet_action = "not written"
        tickets.append(
            {
                "key": item.key,
                "url": item.browse_url,
                "repository": item.repository,
                "number": item.number,
                "jira_key": item.jira_key or None,
                "summary": item.summary,
                "status": item.status,
                "assignee": item.assignee,
                "assignee_source": item.assignee_source,
                "members": list(effort.members_for(item)),
                "instruments": effort.instruments_for(item),
                "comments_in_window": len(item.comments),
                "commented_in_window": commented,
                "counted_in_mail": commented or not settings.mail_requires_activity,
                "sheet": sheet_action,
                "sheet_note": skipped.get(item.key),
                "comment_block": blocks.get(item.key),
            }
        )
    counted = [ticket for ticket in tickets if ticket["counted_in_mail"]]
    return {
        "week": window.week,
        "source": source,
        "window": {
            "since": window.since.isoformat(),
            "until": window.until.isoformat(),
            "start_time": window.start_time.isoformat() if window.start_time else None,
            "end_time": window.end_time.isoformat() if window.end_time else None,
            "days_in": "Asia/Taipei (UTC+8)",
        },
        "configured_workbook": settings.workbook_path,
        "sheet": plan.target_sheet or settings.temp_sheet,
        "counts": {
            "tickets_in_scope": len(found.items),
            "commented_in_window": sum(1 for ticket in tickets if ticket["commented_in_window"]),
            "counted_in_mail": len(counted),
            "rows_planned": len(plan.rows),
            "new_rows": len(plan.new_keys),
            "updated_rows": len(plan.updated_keys),
            "comment_blocks": len(plan.comment_operations),
            "linked_keys": applied.linked,
            "capped": found.capped,
            "truncated_threads": list(found.truncated),
        },
        "members": effort.member_totals(
            [item for item in found.items if _counted(item, window, settings)]
        ),
        "instruments": effort.instrument_totals(
            [item for item in found.items if _counted(item, window, settings)]
        ),
        "tickets": tickets,
        "outputs": {
            "email": "email.html",
            "chart": f"{CHART_CID}.png" if not chart_note else None,
            "chart_note": chart_note or None,
            "workbook": PREVIEW_WORKBOOK,
        },
    }


def _counted(item: ReportItem, window: ReportingWindow, settings: WeeklyReportSettings) -> bool:
    if not settings.mail_requires_activity:
        return True
    return effort.commented_in_week(item, window.since, window.until)


# ---------------------------------------------------------------------------
# Fixture mode: synthetic data only
# ---------------------------------------------------------------------------


class FixtureBoard:
    """A synthetic board for week 2026_43W (2026-10-19 .. 10-25). Every name,
    title and number here is invented."""

    def items(self) -> list[ProjectItem]:
        def comment(stamp: str, body: str) -> ProjectComment:
            return ProjectComment(created=stamp, updated=stamp, body=body)

        def row(
            number: int,
            title: str,
            *,
            assignees: tuple[tuple[str, str], ...] = (),
            sde: str = "",
            production: str = "",
            status: str = "In Progress",
            updated: str = "2026-10-21T02:00:00Z",
            comments: tuple[ProjectComment, ...] = (),
        ) -> ProjectItem:
            fields = {"Status": status, "Company": "Example Co", "Sales": "Sam"}
            if sde:
                fields["SDE Assignee"] = sde
            if production:
                fields["Production"] = production
            return ProjectItem(
                item_id=f"PVTI_fixture_{number}",
                key=f"example-org/example-board#{number}",
                repository="example-org/example-board",
                number=number,
                title=title,
                url=f"https://github.com/example-org/example-board/issues/{number}",
                updated=updated,
                issue_assignees=tuple(login for login, _ in assignees),
                issue_assignee_names=tuple(name or login for login, name in assignees),
                fields=fields,
                comments=comments,
            )

        return [
            row(
                101,
                "[GTM-901] Example migrated ticket",
                assignees=(("alex-w", "Alex Wu"),),
                production="CMP180",
                comments=(comment("2026-10-20T03:00:00Z", "[Completed]\n- example step"),),
            ),
            row(
                102,
                "Example ticket filed on GitHub",
                assignees=(("bo-l", ""),),
                production="CMX500, CMP180",
                comments=(comment("2026-10-22T08:30:00Z", "[On-going]\n- example work"),),
            ),
            row(
                103,
                "Example ticket with no Issue assignee",
                sde="Casey Lin",
                production="WMT",
                # Monday 07:00 in Taipei: Sunday in UTC, this week in Taipei.
                comments=(comment("2026-10-18T23:00:00Z", "[Completed]\n- monday morning"),),
            ),
            row(
                104,
                "Example ticket edited but not commented",
                assignees=(("alex-w", "Alex Wu"),),
                production="CMP180",
            ),
            row(
                105,
                "Example finished ticket",
                assignees=(("bo-l", ""),),
                status="Done",
                comments=(comment("2026-10-21T01:00:00Z", "[Completed]\n- done"),),
            ),
            row(
                106,
                "Example quiet ticket",
                assignees=(("bo-l", ""),),
                updated="2026-10-01T01:00:00Z",
            ),
        ]


def write_fixture_workbook(path: Path) -> None:
    """A synthetic workbook with the structure of the team's: `YYYY_NW` week
    sheets whose row 1 is `Key .. Comments`, older weeks keyed by Jira ids,
    the newest by GitHub Issue, plus an unrelated sheet."""
    import openpyxl

    book = openpyxl.Workbook()
    book.remove(book.worksheets[0])
    first = book.create_sheet("Tasks Summary")
    first.append(["Synthetic summary sheet"])
    older = book.create_sheet("2026_41W")
    older.append(list(WEEKLY_COLUMNS))
    older.append(["GTM-900", "Example old ticket", "Example Co", "Done", "Alex Wu", "Sam", ""])
    last = book.create_sheet("2026_42W")
    last.append(list(WEEKLY_COLUMNS))
    last.append(
        ["#101", "Example migrated ticket", "Example Co", "In Progress", "Alex Wu", "Sam", ""]
    )
    last["A2"].hyperlink = "https://github.com/example-org/example-board/issues/101"
    book.save(path)


# ---------------------------------------------------------------------------
# Real mode
# ---------------------------------------------------------------------------


def real_sources(config_path: Path) -> tuple[WeeklyReportSettings, BoardReader]:
    """The host's own settings and board client, with the Workflow's own
    credential mapping. The token is resolved on each call by the client and
    never held, logged or printed here."""
    from host_runtime.contracts import CompanyHostConfiguration
    from host_runtime.launcher import refreshed_environment
    from integrations.github_project import GitHubProjectClient
    from models.credentials import EnvironmentCredentials

    config = CompanyHostConfiguration.model_validate_json(
        config_path.read_text(encoding="utf-8-sig")
    )
    integrations = config.integrations
    if integrations is None or integrations.weekly_report is None:
        raise SystemExit("host.json has no integrations.weekly_report")
    if integrations.github_project is None:
        raise SystemExit("host.json has no integrations.github_project")
    mapped = config.credential_environment()
    if integrations.github_project.credential.name not in mapped:
        raise SystemExit("the board credential is not mapped to an environment variable")
    resolver = EnvironmentCredentials(mapped, refreshed_environment())
    return integrations.weekly_report, GitHubProjectClient(integrations.github_project, resolver)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m capabilities.weekly_report.preview",
        description="Preview Workflow 11 for one week into a folder; nothing else is written.",
    )
    parser.add_argument("--week", default=None, help="weekly sheet name, e.g. 2026_43W")
    parser.add_argument("--out", required=True, type=Path, help="the only folder written")
    parser.add_argument(
        "--fixture", action="store_true", help="synthetic board and workbook; no credential"
    )
    parser.add_argument("--config", type=Path, default=None, help="host.json (real mode)")
    parser.add_argument("--start-time", default=None, help="inclusive; Taiwan time by default")
    parser.add_argument(
        "--end-time", default=None, help="inclusive; a date alone is its last second"
    )
    parser.add_argument("--today", default=None, help="YYYY-MM-DD, for the stamp date")
    args = parser.parse_args(argv)
    out: Path = args.out.resolve()
    today = _dt.date.fromisoformat(args.today) if args.today else _dt.date.today()
    start = parse_report_time(args.start_time)
    end = parse_report_time(args.end_time, end=True)
    board: BoardReader
    if args.fixture:
        out.mkdir(parents=True, exist_ok=True)
        source_book = out / FIXTURE_WORKBOOK
        write_fixture_workbook(source_book)
        settings = WeeklyReportSettings(
            workbook_path=str(source_book), project="example-board", mail_to=(), mail_cc=()
        )
        board = FixtureBoard()
        label = "fixture (synthetic)"
        week = args.week or "2026_43W"
    else:
        config = args.config or default_config()
        settings, board = real_sources(config)
        label = f"GitHub board via {config}"
        week = args.week
    record = run_preview(
        settings,
        board,
        out,
        week=week,
        today=today,
        start_time=start,
        end_time=end,
        source_label=label,
    )
    counts = record["counts"]
    print(f"week {record['week']} ({record['window']['since']} .. {record['window']['until']})")
    print(
        f"tickets in scope {counts['tickets_in_scope']}, commented in window "
        f"{counts['commented_in_window']}, rows planned {counts['rows_planned']} "
        f"({counts['new_rows']} new, {counts['updated_rows']} updated), "
        f"{counts['linked_keys']} key link(s)"
    )
    print(f"sheet '{record['sheet']}' written into {out / PREVIEW_WORKBOOK}")
    print(f"preview in {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
