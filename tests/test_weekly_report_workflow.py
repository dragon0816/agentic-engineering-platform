"""The weekly report's preview, end to end on a real company host.

Requirements: `docs/phases/PHASE_7_MIGRATION.md`, slice 3a. A workbook is
built on disk, Jira is a scripted transport, and the four steps run through
the real Gateway, policy and engine. Nothing is written: the workbook's bytes
are the same afterwards, and the plan is the only output.
"""

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest
from test_github_project_client import Reply, ScriptedTransport
from test_host_wiring import device, membership_record, workspace

from capabilities.weekly_report import rules
from capabilities.weekly_report.contracts import (
    SheetState,
    WeeklyMailDrafted,
    WeeklyReportApplied,
    WeeklyReportPlan,
    WeeklyReportSettings,
)
from capabilities.weekly_report.handlers import (
    APPLY_SPEC,
    MAIL_SPEC,
    PLAN_SPEC,
    PROJECT_SEARCH_SPEC,
    READ_SCRATCH_SHEET_SPEC,
    RESOLVE_WINDOW_SPEC,
    ReadScratchSheetHandler,
    ReadScratchSheetInput,
)
from capabilities.weekly_report.manifest import (
    mail_workflow,
    preview_workflow,
    report_workflow,
    weekly_skill,
)
from common.execution import RequestContext, TraceIdentifiers
from common.local_agent import LocalAgentRequest
from host_runtime.assets import export_assets
from host_runtime.cli import main
from host_runtime.host import build_runtime, host_report
from integrations import excel
from integrations.excel import digest_rows
from integrations.excel_writer import owner_file
from models.credentials import StaticCredentials

openpyxl = pytest.importorskip("openpyxl")

TOKEN = "a-board-token-that-must-not-appear-anywhere"
HEADERS = list(rules.WEEKLY_COLUMNS)
OLD_BLOCK = "7/17:\n[Completed]\n- BT Tx BR LE are ready\n"


def build_workbook(path: Path, *, scratch: bool) -> None:
    """Two weekly sheets and, when asked, the scratch sheet seeded from the
    newer one with a hand-written row."""
    workbook = openpyxl.Workbook()
    first = workbook.active
    first.title = "2026_29W"
    first.append(HEADERS)
    first.append(["GTM-100", "old ticket", "Acme", "Done", "Someone", "Wendy", "6/30:\n- shipped"])
    week30 = workbook.create_sheet("2026_30W")
    week30.append(HEADERS)
    week30.append(
        ["GTM-688", "[Acme] field edit", "Acme", "In Progress", "Ming", "Wendy", OLD_BLOCK]
    )
    if scratch:
        temp = workbook.create_sheet("weekly report temp")
        temp.append(HEADERS)
        temp.append(
            ["GTM-688", "[Acme] field edit", "Acme", "In Progress", "Ming", "Wendy", OLD_BLOCK]
        )
        temp.append(["GTM-5", "hand added", "Beta", "To Do", "Ming", "Teresa", ""])
    workbook.create_sheet("Tasks Summary-12-23")
    workbook.save(path)


def board_item(
    number: int,
    title: str,
    *comments: dict[str, Any],
    total: int | None = None,
    updated: str = "2026-07-30T10:00:00Z",
) -> dict[str, Any]:
    """One row of the board, shaped as the real one answered."""
    return {
        "id": f"PVTI_{number}",
        "type": "ISSUE",
        "fieldValues": {
            "nodes": [
                {"text": title, "field": {"name": "Title"}},
                {"name": "In Progress", "field": {"name": "Status"}},
                {"text": "Acme", "field": {"name": "Company"}},
                {"text": "Ming-Kai Shih", "field": {"name": "SDE Assignee"}},
                {"text": "Wendy/Teresa", "field": {"name": "Sales"}},
            ]
        },
        "content": {
            "__typename": "Issue",
            "number": number,
            "title": title,
            "url": f"https://github.com/an-owner/a-board/issues/{number}",
            "state": "OPEN",
            "updatedAt": updated,
            "repository": {"nameWithOwner": "an-owner/a-board"},
            "comments": {
                "totalCount": total if total is not None else len(comments),
                "nodes": list(comments),
            },
        },
    }


def board_comment(created: str, body: str) -> dict[str, Any]:
    return {"createdAt": created, "author": {"login": "an-engineer"}, "body": body}


def board_replies() -> list[Reply]:
    """One page of the board: a row with a comment, a row with none, a row
    that says nothing this week, and a row whose thread is longer than one
    page."""
    return [
        Reply(
            200,
            {
                "data": {
                    "user": {
                        "projectV2": {
                            "title": "a board",
                            "items": {
                                "pageInfo": {"hasNextPage": False, "endCursor": None},
                                "nodes": [
                                    board_item(
                                        1,
                                        "[GTM-1] [WNC] worked on",
                                        board_comment(
                                            "2026-07-29T09:00:00Z",
                                            "completed:\n- tx cal done",
                                        ),
                                    ),
                                    board_item(688, "[GTM-688] [Acme] field edit"),
                                    board_item(455, "[GTM-455] [Silent] nothing this week"),
                                    board_item(
                                        9,
                                        "[GTM-9] [Truncated] thread",
                                        board_comment(
                                            "2026-07-28T09:00:00Z",
                                            "ongoing task:\n- fix rx power",
                                        ),
                                        board_comment(
                                            "2026-07-30T09:00:00Z",
                                            "completed:\n- rx power fixed",
                                        ),
                                        total=3,
                                    ),
                                ],
                            },
                        }
                    }
                }
            },
        )
    ]


def grants() -> list[dict[str, Any]]:
    return [
        {
            "actor": "engineer",
            "asset": spec.identity.model_dump(),
            "permissions": list(spec.policy.required_permissions),
            "policy_refs": list(spec.policy.policy_refs),
            "approval_ref": "weekly-report-approval",
        }
        for spec in (
            RESOLVE_WINDOW_SPEC,
            PROJECT_SEARCH_SPEC,
            READ_SCRATCH_SHEET_SPEC,
            PLAN_SPEC,
            APPLY_SPEC,
            MAIL_SPEC,
        )
    ]


def settings(workbook: Path, **changes: Any) -> dict[str, Any]:
    return {"workbook_path": str(workbook), **changes}


def host(tmp_path: Path, *, scratch: bool = True, **changes: Any) -> tuple[Any, Any, Path]:
    workbook = tmp_path / "SDE_Weekly_Report.xlsx"
    build_workbook(workbook, scratch=scratch)
    config, layout = workspace(
        tmp_path,
        membership=membership_record(),
        grants=grants(),
        assets=False,
        config_changes={
            "integrations": {
                "github_project": {
                    "owner": "an-owner",
                    "project_number": 1,
                    "credential": {"name": "board_token"},
                },
                "weekly_report": settings(workbook, **changes),
            },
            "credentials": [{"secret": "board_token", "environment_variable": "AEP_GITHUB_TOKEN"}],
        },
    )
    export_assets(layout.workspace_root / "assets")
    return config, layout, workbook


def ask(runtime: Any, message: str) -> Any:
    return asyncio.run(
        runtime.agent.handle(
            LocalAgentRequest(
                ingress="local",
                actor="engineer",
                bridge_id=device()["bridge_id"],
                namespace="engineering",
                message=message,
                trace=TraceIdentifiers(trace_id="t-1", request_id="r-1", span_id="s-1"),
            )
        )
    )


def test_the_shipped_manifests_validate_and_export() -> None:
    workflow = preview_workflow()
    assert [step.capability.name for step in workflow.steps if hasattr(step, "capability")] == [
        "resolve-window",
        "search-project",
        "read-scratch-sheet",
        "plan",
    ]
    full = report_workflow()
    assert [step.capability.name for step in full.steps if hasattr(step, "capability")] == [
        "resolve-window",
        "search-project",
        "read-scratch-sheet",
        "plan",
        "apply",
    ]
    # The preview stays its own asset, so a member can be given the dry run
    # alone; the write names the capability it needs like the rest.
    assert "weekly_report.apply" in full.dependencies.local_capabilities
    assert "weekly_report.apply" not in workflow.dependencies.local_capabilities
    skill = weekly_skill()
    assert skill.alias == "weekly" and skill.commands[0].target == workflow.metadata.identity
    assert skill.default_command == "preview"
    assert [command.name for command in skill.commands] == ["preview", "apply", "mail"]
    assert skill.commands[1].target == full.metadata.identity
    assert skill.commands[2].target == mail_workflow().metadata.identity


def test_the_preview_runs_end_to_end_and_writes_nothing(tmp_path: Path) -> None:
    config, layout, workbook = host(tmp_path)
    before = workbook.read_bytes()
    transport = ScriptedTransport(board_replies())
    with build_runtime(
        config,
        layout=layout,
        resolver=StaticCredentials({"board_token": TOKEN}),
        jira_transport=transport,
    ) as runtime:
        outcome = ask(runtime, "weekly.preview 2026_31W")
        assert outcome.refusal is None and outcome.workflow is not None
        run = outcome.workflow.run
        assert run.status == "succeeded", run.failure
        assert run.completed_steps == 4
        plan = WeeklyReportPlan.model_validate(outcome.workflow.step_results[-1].data)
    # The window, the fetch and the sheet.
    assert plan.window.week == "2026_31W"
    assert (plan.window.since.isoformat(), plan.window.until.isoformat()) == (
        "2026-07-27",
        "2026-08-02",
    )
    (search,) = transport.calls
    variables = search["body"]["variables"]
    assert (variables["owner"], variables["number"]) == ("an-owner", 1)
    assert search["headers"]["Authorization"] == f"Bearer {TOKEN}"
    # The board answers the thread with the row, so there is no second
    # call; a thread longer than one page is named instead of refetched.
    assert search["url"].endswith("/graphql")
    assert plan.issue_keys == ("GTM-1", "GTM-455", "GTM-688", "GTM-9")
    # What reaches the sheet, and why the rest does not.
    assert [row.key for row in plan.rows] == ["GTM-1", "GTM-688", "GTM-9"]
    assert plan.new_keys == ("GTM-1", "GTM-9") and plan.updated_keys == ("GTM-688",)
    reasons = {item.key: item.reason for item in plan.skipped}
    assert reasons["GTM-455"] == "not in the sheet and no comment content this week"
    assert reasons["GTM-688"] == "no marker-tagged comment content in window"
    blocks = {op.key: op.text for op in plan.comment_operations}
    assert blocks["GTM-1"] == "7/29:\n[Completed]\n- tx cal done\n"
    assert blocks["GTM-9"] == (
        "7/30:\n[Completed]\n- rx power fixed\n7/28:\n[In-progress]\n- fix rx power\n"
    )
    assert plan.highlight_keys == ("GTM-1", "GTM-9")
    assert plan.rows[0].company == "Acme" and plan.rows[0].sales == "Wendy/Teresa"
    assert not plan.capped and "CAPPED" not in plan.preview
    # The host's executor gives a step the time a Jira search needs, and a
    # caller waits at least that long.
    assert config.capability_timeout_seconds == 600 and config.workflow_wait_seconds == 900
    with pytest.raises(Exception, match="at least as long"):
        config.model_validate({**config.model_dump(), "workflow_wait_seconds": 10})
    # The evidence: the sheet as it was, and nothing changed.
    assert plan.sheet_digest != "0" * 64
    assert workbook.read_bytes() == before
    assert TOKEN not in plan.model_dump_json()
    assert "nothing was written" in plan.preview
    # A second preview against the same sheet is the same plan.
    with build_runtime(
        config,
        layout=layout,
        resolver=StaticCredentials({"board_token": TOKEN}),
        jira_transport=ScriptedTransport(board_replies()),
    ) as runtime:
        again = ask(runtime, "weekly.preview 2026_31W")
        assert again.workflow is not None
        repeat = WeeklyReportPlan.model_validate(again.workflow.step_results[-1].data)
    assert repeat.model_copy(update={"window": plan.window}) == plan


def test_a_cap_is_reported_only_when_it_cut_the_week_short(tmp_path: Path) -> None:
    config, layout, _ = host(tmp_path)
    for words, expected_capped, expected_rows in (
        ("max=4", False, 3),  # exactly the cap: the whole week
        ("max=3", True, 2),  # one short of it: the fourth, worked on, is cut
        ("max=2", True, 2),  # the silent ticket and the cut one are both gone
    ):
        transport = ScriptedTransport(board_replies())
        with build_runtime(
            config,
            layout=layout,
            resolver=StaticCredentials({"board_token": TOKEN}),
            jira_transport=transport,
        ) as runtime:
            outcome = ask(runtime, f"weekly.preview 2026_31W {words}")
            assert outcome.workflow is not None and outcome.workflow.run.status == "succeeded"
            plan = WeeklyReportPlan.model_validate(outcome.workflow.step_results[-1].data)
        assert plan.capped is expected_capped, words
        assert len(plan.rows) == expected_rows, words
        assert ("CAPPED" in plan.preview) is expected_capped
        # The board has no query language to push a cap into, so the cap is
        # applied here and the board is still read whole.
        assert len(transport.calls) == 1
    # A host with the report but no board is told so before anything
    # runs, by the doctor and by the engine.
    without = config.model_copy(
        update={"integrations": config.integrations.model_copy(update={"github_project": None})}
    )
    checks = {c.name: c for c in host_report(without, layout).checks}
    assert checks["integrations"].status == "failed"
    assert "needs a project board" in checks["integrations"].detail
    with build_runtime(without, layout=layout) as runtime:
        outcome = ask(runtime, "weekly.preview 2026_31W")
        assert outcome.workflow is not None
        assert outcome.workflow.run.status == "unavailable"
        assert outcome.workflow.run.completed_steps == 0


def test_a_jira_refusal_fails_the_run_and_claims_nothing(tmp_path: Path) -> None:
    config, layout, _ = host(tmp_path)
    transport = ScriptedTransport([Reply(401, {"message": "nope"})])
    with build_runtime(
        config,
        layout=layout,
        resolver=StaticCredentials({"board_token": TOKEN}),
        jira_transport=transport,
    ) as runtime:
        outcome = ask(runtime, "weekly.preview 2026_31W")
        assert outcome.workflow is not None and outcome.workflow.run.status == "failed"
        assert outcome.workflow.run.completed_steps == 1
        failure = outcome.workflow.run.failure
        assert failure is not None and TOKEN not in failure.message
        # A request that is not one is refused before anything is fetched,
        # and so is a window that cannot be, with the input named as the fault.
        refused = ask(runtime, "weekly.preview whenever")
        assert refused.workflow is not None and refused.workflow.run.status == "failed"
        assert refused.workflow.run.completed_steps == 0
        impossible = ask(runtime, "weekly.preview 2026_31W since=2026-09-01")
        assert impossible.workflow is not None and impossible.workflow.run.status == "failed"
        first = impossible.workflow.step_results[0]
        assert first.failure is not None and first.failure.code == "invalid_input"
    assert len(transport.calls) == 1


def test_the_scratch_sheet_is_read_as_it_stands_or_seeded_when_absent(tmp_path: Path) -> None:
    present = tmp_path / "present.xlsx"
    build_workbook(present, scratch=True)
    handler = ReadScratchSheetHandler(WeeklyReportSettings(workbook_path=str(present)))
    context = RequestContext(
        trace=TraceIdentifiers(trace_id="t", request_id="r", span_id="s"),
        actor="engineer",
        namespace="engineering",
        message="read",
        channel="local",
    )

    def read(reader: ReadScratchSheetHandler, week: str) -> SheetState:
        return SheetState.model_validate(
            asyncio.run(reader(context, ReadScratchSheetInput(week=week)))
        )

    state = read(handler, "2026_31W")
    assert state.scratch_present and state.source_sheet == "weekly report temp"
    assert state.seed_sheet == "2026_30W"
    assert state.existing == {"GTM-688": OLD_BLOCK, "GTM-5": ""}
    assert state.headers == tuple(HEADERS)
    assert state.sheet_names[-1] == "Tasks Summary-12-23"
    again = read(handler, "2026_31W")
    assert again.digest == state.digest, "the digest is stable"
    # Strictly before the week reported: a run for week 30 seeds from 29.
    earlier = read(handler, "2026_30W")
    assert earlier.seed_sheet == "2026_29W"
    absent = tmp_path / "absent.xlsx"
    build_workbook(absent, scratch=False)
    seeded = read(
        ReadScratchSheetHandler(WeeklyReportSettings(workbook_path=str(absent))), "2026_31W"
    )
    assert not seeded.scratch_present and seeded.source_sheet == "2026_30W"
    assert seeded.existing == {"GTM-688": OLD_BLOCK}
    assert seeded.digest != state.digest and seeded.digest == handler_digest_of_nothing()
    # No weekly sheet at all: the column contract and nothing to compare.
    bare = tmp_path / "bare.xlsx"
    openpyxl.Workbook().save(bare)
    empty = read(ReadScratchSheetHandler(WeeklyReportSettings(workbook_path=str(bare))), "2026_31W")
    assert empty.headers == rules.WEEKLY_COLUMNS and empty.existing == {}
    assert empty.seed_sheet is None and empty.source_sheet is None
    # A scratch sheet with a blank header row is digested as it stands; the
    # column contract stands in only for the plan's own lookups.
    blank = tmp_path / "blank.xlsx"
    book = openpyxl.Workbook()
    book.active.title = "2026_30W"
    book.active.append(HEADERS)
    scratch = book.create_sheet("weekly report temp")
    scratch.append([None] * 7)
    scratch.append(["GTM-1", "x", "", "", "", "", ""])
    book.save(blank)
    headless = read(
        ReadScratchSheetHandler(WeeklyReportSettings(workbook_path=str(blank))), "2026_31W"
    )
    assert headless.headers == rules.WEEKLY_COLUMNS
    assert headless.digest == digest_rows(("",) * 7, (("GTM-1", "x", "", "", "", "", ""),))
    # A sheet whose header row names no Key and Comments is refused, not
    # planned as empty.
    odd = tmp_path / "odd.xlsx"
    book = openpyxl.Workbook()
    book.active.title = "weekly report temp"
    book.active.append(["Ticket", "Summary", "Notes"])
    book.active.append(["GTM-1", "x", "y"])
    book.save(odd)
    with pytest.raises(ValueError, match="no Key and Comments columns"):
        read(ReadScratchSheetHandler(WeeklyReportSettings(workbook_path=str(odd))), "2026_31W")
    with pytest.raises(excel.WorkbookError, match="workbook_missing"):
        excel.sheet_names(tmp_path / "nowhere.xlsx")
    (tmp_path / "junk.xlsx").write_bytes(b"not a workbook")
    with pytest.raises(excel.WorkbookError, match="workbook_unreadable"):
        excel.sheet_names(tmp_path / "junk.xlsx")
    with pytest.raises(excel.WorkbookError, match="sheet_missing"):
        excel.read_rows(present, "2026_99W")


def handler_digest_of_nothing() -> str:
    return digest_rows((), ())


def test_doctor_reports_the_integrations_without_contacting_anything(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    config, layout, workbook = host(tmp_path)
    monkeypatch.setenv("AEP_GITHUB_TOKEN", "a value nobody prints")
    checks = {c.name: c for c in host_report(config, layout).checks}
    assert checks["integrations"].status == "passed"
    assert "project an-owner/1" in checks["integrations"].detail
    assert "SDE_Weekly_Report.xlsx" in checks["integrations"].detail
    workbook.unlink()
    checks = {c.name: c for c in host_report(config, layout).checks}
    assert checks["integrations"].status == "failed"
    assert "not at the configured path" in checks["integrations"].detail
    unmapped = config.model_copy(update={"credentials": ()})
    checks = {c.name: c for c in host_report(unmapped, layout).checks}
    assert "not mapped" in checks["integrations"].detail
    plain = config.model_copy(update={"integrations": None, "credentials": ()})
    assert {c.name: c.status for c in host_report(plain, layout).checks}["integrations"] == (
        "pending"
    )
    monkeypatch.setattr(
        excel, "_openpyxl", lambda: (_ for _ in ()).throw(excel.WorkbookError("library_missing"))
    )
    build_workbook(workbook, scratch=True)
    checks = {c.name: c for c in host_report(config, layout).checks}
    assert "openpyxl is not installed" in checks["integrations"].detail
    # The shipped manifests are written where a workspace reads them.
    out = tmp_path / "exported"
    assert main(["export-assets", "--out", str(out)]) == 0
    written = sorted(path.relative_to(out).as_posix() for path in out.rglob("*.json"))
    assert written == [
        "skills/engineering__weekly-report__1.0.0.json",
        "workflows/engineering__jira-weekly-report-mail__1.0.0.json",
        "workflows/engineering__jira-weekly-report-preview__1.0.0.json",
        "workflows/engineering__jira-weekly-report__1.0.0.json",
    ]
    assert "wrote" in capsys.readouterr().out
    exported = json.loads((out / written[2]).read_text(encoding="utf-8"))
    assert exported["metadata"]["identity"]["name"] == "jira-weekly-report-preview"
    drafts = json.loads((out / written[1]).read_text(encoding="utf-8"))
    assert drafts["metadata"]["identity"]["name"] == "jira-weekly-report-mail"
    # The mail reads the board and drafts; it never touches the workbook.
    assert [step["capability"]["name"] for step in drafts["steps"]] == [
        "resolve-window",
        "search-project",
        "mail",
    ]
    # A host without the secret mapped will not be built.
    with pytest.raises(Exception, match="credential_unmapped"):
        build_runtime(unmapped, layout=layout)


def test_the_whole_report_writes_the_plan_and_carries_the_evidence(tmp_path: Path) -> None:
    """The five steps end to end on a real host: the workbook read, the plan
    made, and the plan written through a recording writer."""
    from test_weekly_report_apply import RecordingWriter

    config, layout, workbook = host(tmp_path)
    before = workbook.read_bytes()
    writer = RecordingWriter(existing_rows={"GTM-688": 2})
    with build_runtime(
        config,
        layout=layout,
        resolver=StaticCredentials({"board_token": TOKEN}),
        jira_transport=ScriptedTransport(board_replies()),
        writer=lambda: writer,
    ) as runtime:
        outcome = ask(runtime, "weekly.apply 2026_31W")
        assert outcome.refusal is None and outcome.workflow is not None
        run = outcome.workflow.run
        assert run.status == "succeeded", run.failure
        assert run.completed_steps == 5
        applied = WeeklyReportApplied.model_validate(outcome.workflow.step_results[-1].data)
    # The plan reached the writer: a new row, a refreshed one, blocks in red.
    assert (applied.inserted, applied.updated) == (2, 1)
    assert applied.prepended == 2 and applied.failures == ()
    assert applied.week == "2026_31W"
    # The evidence the parity gate names, on both sides of the write.
    assert applied.digest_before == applied.digest_after, "the recorder wrote nothing"
    assert applied.backup_path is not None
    assert workbook.read_bytes() == before
    assert "upsert" in writer.names and writer.closed_saving is True


def test_the_mail_drafts_end_to_end_and_never_touches_the_workbook(tmp_path: Path) -> None:
    """Three steps on a real host: the week resolved, the board read, a draft
    saved. The workbook is not opened at all, which is why the mail is its
    own asset rather than a fifth step on the report."""
    from integrations.outlook_draft import RecordingDraftWriter

    config, layout, workbook = host(tmp_path)
    before = workbook.read_bytes()
    drafter = RecordingDraftWriter()
    with build_runtime(
        config,
        layout=layout,
        resolver=StaticCredentials({"board_token": TOKEN}),
        jira_transport=ScriptedTransport(board_replies()),
        drafter=lambda: drafter,
    ) as runtime:
        outcome = ask(runtime, "weekly.mail 2026_31W")
        assert outcome.refusal is None and outcome.workflow is not None
        run = outcome.workflow.run
        assert run.status == "succeeded", run.failure
        assert run.completed_steps == 3
        drafted = WeeklyMailDrafted.model_validate(outcome.workflow.step_results[-1].data)
    assert workbook.read_bytes() == before, "the mail read no workbook and wrote none"
    assert len(drafter.drafts) == 1, "one draft, saved, not sent"
    saved = drafter.drafts[0]
    assert saved.subject == "GTM weekly report 2026_31W (2026-07-27 .. 2026-08-02)"
    assert drafted.week == "2026_31W"
    # Two of the four board rows carry a comment inside the week; the other
    # two moved without anybody working on them, and they are named.
    assert drafted.counted == 2
    assert drafted.counted + len(drafted.excluded) == drafted.matched
    assert "GTM-688" in drafted.excluded and "GTM-455" in drafted.excluded
    assert drafted.activity_required is True
    # The picture is written where the draft refers to it.
    assert drafted.chart_path and Path(drafted.chart_path).read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    assert f"cid:{saved.images[0].cid}" in saved.html_body
    assert "GTM-1" in drafted.preview, "the plain text is what a person checks"


def test_drafting_the_mail_needs_an_approval(tmp_path: Path) -> None:
    """A draft changes the member's own mailbox, so it is a write like the
    workbook's and is refused the same way without an approval."""
    from integrations.outlook_draft import RecordingDraftWriter

    assert MAIL_SPEC.side_effect == "write"
    assert MAIL_SPEC.policy.approval_required
    config, layout, _ = host(tmp_path)
    unapproved = [
        {key: value for key, value in grant.items() if key != "approval_ref"}
        if grant["asset"]["name"] == "mail"
        else grant
        for grant in grants()
    ]
    layout.grants.write_text(json.dumps(unapproved), encoding="utf-8")
    drafter = RecordingDraftWriter()
    with build_runtime(
        config,
        layout=layout,
        resolver=StaticCredentials({"board_token": TOKEN}),
        jira_transport=ScriptedTransport(board_replies()),
        drafter=lambda: drafter,
    ) as runtime:
        outcome = ask(runtime, "weekly.mail 2026_31W")
        assert outcome.workflow is not None
        assert outcome.workflow.run.status == "failed"
        assert outcome.workflow.run.completed_steps == 2, "the board was read, nothing was drafted"
        failure = outcome.workflow.step_results[-1].failure
        assert failure is not None and failure.code == "permission_denied"
    assert drafter.drafts == []


def test_a_host_without_outlook_says_so_rather_than_failing_to_assemble(tmp_path: Path) -> None:
    """The drafter is built per run, so a machine without Outlook still
    installs the capability and refuses at the draft with its own code."""
    from integrations.outlook_draft import DraftError

    def missing() -> Any:
        raise DraftError("outlook_missing")

    config, layout, _ = host(tmp_path)
    with build_runtime(
        config,
        layout=layout,
        resolver=StaticCredentials({"board_token": TOKEN}),
        jira_transport=ScriptedTransport(board_replies()),
        drafter=missing,
    ) as runtime:
        outcome = ask(runtime, "weekly.mail 2026_31W")
        assert outcome.workflow is not None
        assert outcome.workflow.run.status == "failed"
        failure = outcome.workflow.step_results[-1].failure
        assert failure is not None and failure.code == "outlook_missing"


def test_writing_the_workbook_needs_an_approval(tmp_path: Path) -> None:
    """The first side-effecting capability in this repository: the Bridge
    policy refuses it when the member's decision carries no approval."""
    from test_weekly_report_apply import RecordingWriter

    assert APPLY_SPEC.side_effect == "write"
    assert APPLY_SPEC.policy.approval_required
    config, layout, _ = host(tmp_path)
    unapproved = [
        {key: value for key, value in grant.items() if key != "approval_ref"}
        if grant["asset"]["name"] == "apply"
        else grant
        for grant in grants()
    ]
    layout.grants.write_text(json.dumps(unapproved), encoding="utf-8")
    writer = RecordingWriter(existing_rows={"GTM-688": 2})
    with build_runtime(
        config,
        layout=layout,
        resolver=StaticCredentials({"board_token": TOKEN}),
        jira_transport=ScriptedTransport(board_replies()),
        writer=lambda: writer,
    ) as runtime:
        outcome = ask(runtime, "weekly.apply 2026_31W")
        assert outcome.workflow is not None
        assert outcome.workflow.run.status == "failed"
        assert outcome.workflow.run.completed_steps == 4, "the plan was made, the write was not"
        failure = outcome.workflow.step_results[-1].failure
        assert failure is not None and failure.code == "permission_denied"
    assert "upsert" not in writer.names


def test_a_workbook_that_cannot_be_written_names_its_own_refusal(tmp_path: Path) -> None:
    """A handler's refusal keeps its code on the failed step, so the member
    is told which of "somebody has it open" and "it is not there" happened."""
    from test_weekly_report_apply import RecordingWriter

    config, layout, workbook = host(tmp_path)
    owner_file(workbook).write_bytes(b"")
    writer = RecordingWriter(existing_rows={"GTM-688": 2})
    with build_runtime(
        config,
        layout=layout,
        resolver=StaticCredentials({"board_token": TOKEN}),
        jira_transport=ScriptedTransport(board_replies()),
        writer=lambda: writer,
    ) as runtime:
        outcome = ask(runtime, "weekly.apply 2026_31W")
        assert outcome.workflow is not None and outcome.workflow.run.status == "failed"
        failure = outcome.workflow.step_results[-1].failure
        assert failure is not None and failure.code == "workbook_open"
    assert writer.calls == []


def test_a_host_without_excel_previews_but_says_it_cannot_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config, layout, _ = host(tmp_path)
    monkeypatch.setenv("AEP_GITHUB_TOKEN", "a value nobody prints")
    detail = {c.name: c for c in host_report(config, layout).checks}["integrations"].detail
    # This machine has no pywin32, so the doctor says so without failing: a
    # host may be given the dry run alone.
    assert "weekly report on" in detail
    assert ("can write it" in detail) or ("preview only" in detail)


def test_the_doctor_says_when_the_token_variable_is_not_set(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The one thing between a host that looks configured and a run that
    fails at the first fetch. `setx` on Windows sets a variable for the next
    process and not this one, so a host passes its own doctor and then
    cannot fetch anything."""
    config, layout, _ = host(tmp_path)
    monkeypatch.delenv("AEP_GITHUB_TOKEN", raising=False)
    report = host_report(config, layout)
    check = {c.name: c for c in report.checks}["integrations"]
    assert check.status == "pending"
    assert "AEP_GITHUB_TOKEN is not set" in check.detail, "which variable, by name"
    assert report.runtime == "ready", "an optional board token does not stop the local Agent"

    monkeypatch.setenv("AEP_GITHUB_TOKEN", "a value nobody prints")
    passed = {c.name: c for c in host_report(config, layout).checks}["integrations"]
    assert passed.status == "passed"
    assert "a value nobody prints" not in passed.detail, "knowing it is set is not reading it"


def test_a_card_nobody_filed_as_an_issue_is_not_a_row(tmp_path: Path) -> None:
    """A board carries cards that were never filed. They have no key, no
    history and no comments, so they can never carry a week's work, and
    reading them gave every one of them the same key: two such cards merged
    into a single row. Seen on the owner's own board on 2026-09-24, as a row
    called `GH`."""
    config, layout, _ = host(tmp_path)
    drafts = {
        "id": "PVTI_draft",
        "type": "DRAFT_ISSUE",
        "fieldValues": {"nodes": [{"text": "a card nobody filed", "field": {"name": "Title"}}]},
        "content": {"__typename": "DraftIssue", "title": "a card nobody filed"},
    }
    replies = board_replies()
    page = replies[0]
    payload = json.loads(b"".join(page.chunks()).decode("utf-8"))
    nodes = payload["data"]["user"]["projectV2"]["items"]["nodes"]
    nodes.extend([drafts, dict(drafts, id="PVTI_2")])
    transport = ScriptedTransport([Reply(200, payload)])
    with build_runtime(
        config,
        layout=layout,
        resolver=StaticCredentials({"board_token": TOKEN}),
        jira_transport=transport,
    ) as runtime:
        outcome = ask(runtime, "weekly.preview 2026_31W")
        assert outcome.workflow is not None and outcome.workflow.run.status == "succeeded"
        plan = WeeklyReportPlan.model_validate(outcome.workflow.step_results[-1].data)
    assert all(not row.key.endswith("GH") for row in plan.rows), "no row is the bare prefix"
    assert len(plan.rows) == len({row.key for row in plan.rows}), "no two cards share a row"
