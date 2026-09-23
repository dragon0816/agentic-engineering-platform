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
from test_host_wiring import device, membership_record, workspace
from test_jira_client import Reply, ScriptedTransport

from capabilities.weekly_report import rules
from capabilities.weekly_report.contracts import (
    SheetState,
    WeeklyReportPlan,
    WeeklyReportSettings,
)
from capabilities.weekly_report.handlers import (
    JIRA_SEARCH_SPEC,
    PLAN_SPEC,
    READ_SCRATCH_SHEET_SPEC,
    RESOLVE_WINDOW_SPEC,
    ReadScratchSheetHandler,
    ReadScratchSheetInput,
    digest_rows,
)
from capabilities.weekly_report.manifest import preview_workflow, weekly_skill
from common.execution import RequestContext, TraceIdentifiers
from common.local_agent import LocalAgentRequest
from host_runtime.assets import export_assets
from host_runtime.cli import main
from host_runtime.host import build_runtime, host_report
from integrations import excel
from models.credentials import StaticCredentials

openpyxl = pytest.importorskip("openpyxl")

TOKEN = "a-jira-api-token-that-must-not-appear-anywhere"
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


def jira_issue(key: str, summary: str, *comments: dict[str, Any]) -> dict[str, Any]:
    return {
        "key": key,
        "fields": {
            "summary": summary,
            "status": {"name": "In Progress"},
            "assignee": {"displayName": "Ming-Kai Shih"},
            "updated": "2026-07-30T10:00:00.000+0800",
            rules.FIELD_COMPANY: "Acme",
            rules.FIELD_SALES: "Wendy/Teresa",
            "comment": {"comments": list(comments), "total": len(comments)},
        },
    }


def jira_comment(created: str, body: Any) -> dict[str, Any]:
    return {"created": created, "body": body}


ADF = {
    "type": "doc",
    "content": [
        {"type": "paragraph", "content": [{"type": "text", "text": "completed:"}]},
        {
            "type": "bulletList",
            "content": [
                {
                    "type": "listItem",
                    "content": [
                        {"type": "paragraph", "content": [{"type": "text", "text": "tx cal done"}]}
                    ],
                }
            ],
        },
    ],
}


def jira_replies() -> list[Reply]:
    """One search page, then the comment thread of the issue whose thread the
    search truncated."""
    return [
        Reply(
            200,
            {
                "issues": [
                    jira_issue(
                        "GTM-1",
                        "[WNC] worked on",
                        jira_comment("2026-07-29T09:00:00.000+0800", ADF),
                    ),
                    jira_issue("GTM-688", "[Acme] field edit"),
                    jira_issue("GTM-455", "[Silent] nothing this week"),
                    {
                        **jira_issue("GTM-9", "[Truncated] thread"),
                        "fields": {
                            **jira_issue("GTM-9", "[Truncated] thread")["fields"],
                            "comment": {"comments": [], "total": 2},
                        },
                    },
                ],
                "isLast": True,
            },
        ),
        Reply(
            200,
            {
                "comments": [
                    jira_comment("2026-07-28T09:00:00.000+0800", "ongoing task:\n- fix rx power"),
                    jira_comment("2026-07-30T09:00:00.000+0800", "completed:\n- rx power fixed"),
                ],
                "total": 2,
            },
        ),
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
        for spec in (RESOLVE_WINDOW_SPEC, JIRA_SEARCH_SPEC, READ_SCRATCH_SHEET_SPEC, PLAN_SPEC)
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
                "jira": {
                    "base_url": "https://example-team.atlassian.net",
                    "email": "a@example.com",
                    "credential": {"name": "jira_token"},
                },
                "weekly_report": settings(workbook, **changes),
            },
            "credentials": [{"secret": "jira_token", "environment_variable": "AEP_JIRA_TOKEN"}],
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
        "search",
        "read-scratch-sheet",
        "plan",
    ]
    skill = weekly_skill()
    assert skill.alias == "weekly" and skill.commands[0].target == workflow.metadata.identity


def test_the_preview_runs_end_to_end_and_writes_nothing(tmp_path: Path) -> None:
    config, layout, workbook = host(tmp_path)
    before = workbook.read_bytes()
    transport = ScriptedTransport(jira_replies())
    with build_runtime(
        config,
        layout=layout,
        resolver=StaticCredentials({"jira_token": TOKEN}),
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
    assert 'updated >= "2026-07-27" AND updated < "2026-08-03"' in plan.window.jql
    search, thread = transport.calls
    assert search["json"]["jql"] == plan.window.jql
    assert search["json"]["fields"] == list(rules.REPORT_FIELDS)
    assert "/issue/GTM-9/comment" in thread["url"]
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
        resolver=StaticCredentials({"jira_token": TOKEN}),
        jira_transport=ScriptedTransport(jira_replies()),
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
        transport = ScriptedTransport(jira_replies())
        with build_runtime(
            config,
            layout=layout,
            resolver=StaticCredentials({"jira_token": TOKEN}),
            jira_transport=transport,
        ) as runtime:
            outcome = ask(runtime, f"weekly.preview 2026_31W {words}")
            assert outcome.workflow is not None and outcome.workflow.run.status == "succeeded"
            plan = WeeklyReportPlan.model_validate(outcome.workflow.step_results[-1].data)
        assert plan.capped is expected_capped, words
        assert len(plan.rows) == expected_rows, words
        assert ("CAPPED" in plan.preview) is expected_capped
        assert transport.calls[0]["json"]["maxResults"] == 100
    # A host with the report but no Jira site is told so before anything
    # runs, by the doctor and by the engine.
    without = config.model_copy(
        update={"integrations": config.integrations.model_copy(update={"jira": None})}
    )
    checks = {c.name: c for c in host_report(without, layout).checks}
    assert checks["integrations"].status == "failed"
    assert "needs a Jira site" in checks["integrations"].detail
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
        resolver=StaticCredentials({"jira_token": TOKEN}),
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
    checks = {c.name: c for c in host_report(config, layout).checks}
    assert checks["integrations"].status == "passed"
    assert "Jira at https://example-team.atlassian.net" in checks["integrations"].detail
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
        "workflows/engineering__jira-weekly-report-preview__1.0.0.json",
    ]
    assert "wrote" in capsys.readouterr().out
    exported = json.loads((out / written[1]).read_text(encoding="utf-8"))
    assert exported["metadata"]["identity"]["name"] == "jira-weekly-report-preview"
    # A host without the secret mapped will not be built.
    with pytest.raises(Exception, match="credential_unmapped"):
        build_runtime(unmapped, layout=layout)
