"""Workflow 7's GitHub read-only adapter, characterized against source W3-07."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from test_github_project_client import Reply, ScriptedTransport
from test_host_wiring import membership_record, workspace

from capabilities.team_tickets.contracts import TeamTicketsPreview, TeamTicketsRequest
from capabilities.team_tickets.handlers import PREVIEW_SPEC, preview_items
from capabilities.team_tickets.manifest import preview_workflow
from common.execution import TraceIdentifiers
from common.local_agent import LocalWorkflowRequest
from host_runtime.assets import export_assets
from host_runtime.host import build_runtime
from integrations.github_project import ProjectComment, ProjectItem
from models.credentials import StaticCredentials


def item(
    number: int,
    *,
    kind: str = "Task",
    comments: tuple[ProjectComment, ...] = (),
    truncated: bool = False,
) -> ProjectItem:
    return ProjectItem(
        item_id=f"PVTI_{number}",
        key=f"owner/repo#{number}",
        title=f"Ticket {number}",
        url=f"https://github.com/owner/repo/issues/{number}",
        state="OPEN",
        created="2026-10-01T09:15:00Z",
        updated="2026-10-02T11:30:00Z",
        author="engineer",
        fields={
            "Type": kind,
            "Status": "In Progress",
            "Priority": "Major",
            "Assignee": "Colleague",
        },
        comments=comments,
        comments_truncated=truncated,
    )


def test_source_columns_route_and_latest_comment_format_are_preserved() -> None:
    comments = (
        ProjectComment(created="2026-10-01T08:00:00Z", author="old", body="earlier"),
        ProjectComment(created="2026-10-02T08:00:00Z", author="new", body="latest\r\nline"),
    )
    result = preview_items(
        (item(1, comments=comments), item(2, kind="Bug")),
        TeamTicketsRequest(comment_count=2),
    )
    assert isinstance(result, TeamTicketsPreview)
    assert result.task_count == 1 and result.issues_count == 1
    assert result.records[0].sheet == "Task" and result.records[1].sheet == "Issues"
    values = result.records[0].values
    assert list(values) == [
        "Key",
        "Summary",
        "Type",
        "Status",
        "Priority",
        "Reporter",
        "Assignee",
        "Created",
        "Updated",
        "Resolution",
        "Jira activity",
    ]
    assert values["Key"] == "owner/repo#1"
    assert values["Reporter"] == "engineer"
    assert values["Created"] == "2026-10-01 09:15"
    assert values["Resolution"] == ""
    assert result.unmapped_fields == ("Resolution",)
    assert values["Jira activity"] == (
        "[2026-10-02 08:00 new]\nlatest\nline\n\n[2026-10-01 08:00 old]\nearlier"
    )


def test_truncated_thread_and_cap_are_visible_in_preview() -> None:
    result = preview_items(
        (item(1, comments=(ProjectComment(body="old"),), truncated=True), item(2)),
        TeamTicketsRequest(max_items=1),
    )
    assert result.capped is True
    assert result.truncated_threads == ("owner/repo#1",)
    assert result.records[0].values["Jira activity"] == ""
    assert "Jira activity" in result.unmapped_fields
    assert result.records[0].url.endswith("/issues/1")


def test_workflow_7_runs_through_agent_policy_without_a_workbook(tmp_path: Path) -> None:
    grant = {
        "actor": "engineer",
        "asset": PREVIEW_SPEC.identity.model_dump(mode="json"),
        "permissions": list(PREVIEW_SPEC.policy.required_permissions),
        "policy_refs": list(PREVIEW_SPEC.policy.policy_refs),
        "approval_ref": "team-tickets-read-approval",
    }
    config, layout = workspace(
        tmp_path,
        membership=membership_record(),
        grants=[grant],
        assets=False,
        config_changes={
            "integrations": {
                "github_project": {
                    "owner": "owner",
                    "project_number": 1,
                    "credential": {"name": "board_token"},
                },
            },
            "credentials": [{"secret": "board_token", "environment_variable": "AEP_GITHUB_TOKEN"}],
        },
    )
    export_assets(layout.workspace_root / "assets")
    payload: dict[str, Any] = {
        "data": {
            "user": {
                "projectV2": {
                    "title": "board",
                    "items": {
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                        "nodes": [
                            {
                                "id": "PVTI_1",
                                "type": "ISSUE",
                                "fieldValues": {
                                    "nodes": [{"name": "Task", "field": {"name": "Type"}}]
                                },
                                "content": {
                                    "__typename": "Issue",
                                    "number": 1,
                                    "title": "A ticket",
                                    "url": "https://github.com/owner/repo/issues/1",
                                    "state": "OPEN",
                                    "createdAt": "2026-10-01T09:15:00Z",
                                    "updatedAt": "2026-10-02T11:30:00Z",
                                    "author": {"login": "engineer"},
                                    "repository": {"nameWithOwner": "owner/repo"},
                                    "comments": {"totalCount": 0, "nodes": []},
                                },
                            }
                        ],
                    },
                }
            }
        },
    }
    transport = ScriptedTransport([Reply(200, payload)])
    request = LocalWorkflowRequest(
        actor="engineer",
        bridge_id=config.device.bridge_id,
        workflow=preview_workflow().metadata.identity,
        arguments={"max_items": 10},
        idempotency_key="workflow-7-preview-1",
        trace=TraceIdentifiers(trace_id="trace-w7", request_id="request-w7", span_id="span-w7"),
    )
    with build_runtime(
        config,
        layout=layout,
        resolver=StaticCredentials({"board_token": "fixture-token"}),
        jira_transport=transport,
    ) as runtime:
        outcome = asyncio.run(runtime.agent.execute_workflow(request))
        assert outcome.refusal is None and outcome.workflow is not None
        assert outcome.workflow.run.status == "succeeded", outcome.workflow.run.failure
        preview = TeamTicketsPreview.model_validate(outcome.workflow.step_results[-1].data)
        assert preview.records[0].values["Reporter"] == "engineer"
        assert preview.unmapped_fields == ("Priority", "Assignee", "Resolution")
    assert transport.calls[0]["body"]["variables"]["number"] == 1
    assert "createdAt" in transport.calls[0]["body"]["query"]
    assert not any(tmp_path.rglob("*.xlsx"))

    layout.grants.write_text("[]", encoding="utf-8")
    denied_transport = ScriptedTransport([])
    with build_runtime(
        config,
        layout=layout,
        resolver=StaticCredentials({"board_token": "fixture-token"}),
        jira_transport=denied_transport,
    ) as runtime:
        denied = asyncio.run(
            runtime.agent.execute_workflow(
                request.model_copy(update={"idempotency_key": "workflow-7-denied-1"})
            )
        )
        assert denied.workflow is not None and denied.workflow.run.status != "succeeded"
    assert denied_transport.calls == []
