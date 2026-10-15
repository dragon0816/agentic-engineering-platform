"""Workflow 7's Jira read-only preview against source W3-07 behavior."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping
from pathlib import Path
from threading import Barrier
from typing import Any

import pytest
from pydantic import ValidationError
from test_host_wiring import membership_record, workspace
from test_jira_client import Reply, ScriptedTransport

from capabilities.team_tickets.contracts import (
    TeamTicketsPreview,
    TeamTicketsRequest,
    TeamTicketsSettings,
)
from capabilities.team_tickets.handlers import (
    MANAGED_HEADERS,
    PREVIEW_SPEC,
    build_jql,
    format_activity,
    issue_to_record,
    preview_items,
)
from capabilities.team_tickets.manifest import preview_workflow
from common.execution import TraceIdentifiers
from common.local_agent import LocalWorkflowRequest
from host_runtime.assets import export_assets
from host_runtime.host import build_runtime, host_report
from models.credentials import StaticCredentials


def issue(number: int, *, kind: str = "Task") -> dict[str, Any]:
    return {
        "key": f"MRT1CV-{number}",
        "fields": {
            "summary": f"Ticket {number}",
            "issuetype": {"name": kind},
            "status": {"name": "In Progress"},
            "priority": {"name": "Major"},
            "reporter": {"displayName": "Leo"},
            "assignee": {"name": "jerry"},
            "created": "2026-10-02T09:15:00.000+0800",
            "updated": "2026-10-03T11:30:00.000+0800",
            "resolution": None,
        },
    }


def settings() -> TeamTicketsSettings:
    return TeamTicketsSettings(project="MRT1CV", reporters=("CHI_L", "peng_k"))


def test_source_jql_and_managed_column_mapping_are_preserved() -> None:
    assert build_jql(settings(), "statusCategory != Done") == (
        'project = MRT1CV AND reporter in ("CHI_L", "peng_k") '
        "AND (statusCategory != Done) ORDER BY created DESC"
    )
    activity = format_activity(
        [
            {
                "created": "2026-10-03T08:00:00.000+0800",
                "author": {"displayName": "Leo"},
                "body": "latest\r\nline",
            },
            {
                "created": "2026-10-02T08:00:00.000+0800",
                "author": {"name": "jerry"},
                "body": "older",
            },
        ]
    )
    values = issue_to_record(issue(1), activity)
    assert tuple(values) == MANAGED_HEADERS
    assert values["Reporter"] == "Leo"
    assert values["Assignee"] == "jerry"
    assert values["Created"] == "2026-10-02 09:15"
    assert values["Resolution"] == "Unresolved"
    assert values["Jira activity"] == (
        "[2026-10-03 08:00 Leo]\nlatest\nline\n\n[2026-10-02 08:00 jerry]\nolder"
    )


def test_source_task_routing_and_issue_cap_are_visible_without_excel() -> None:
    result = preview_items(
        (issue(3, kind="Bug"), issue(2, kind="Sub-task"), issue(1)),
        TeamTicketsRequest(max_items=2, comment_count=0),
        "https://jira.rsint.net",
    )
    assert result.source == "jira"
    assert [row.key for row in result.records] == ["MRT1CV-3", "MRT1CV-2"]
    assert [row.sheet for row in result.records] == ["Issues", "Task"]
    assert result.records[0].url == "https://jira.rsint.net/browse/MRT1CV-3"
    assert result.capped is True


def test_host_static_scope_rejects_invalid_project_or_missing_reporters() -> None:
    with pytest.raises(ValidationError):
        TeamTicketsSettings(project="MRT1CV OR 1=1", reporters=("CHI_L",))
    with pytest.raises(ValidationError):
        TeamTicketsSettings(project="MRT1CV", reporters=())
    exported = json.dumps(preview_workflow().model_dump(mode="json"))
    assert "MRT1CV" not in exported and "CHI_L" not in exported
    assert "jira_pat" not in exported


def test_workflow_7_uses_jira_bearer_and_policy_without_a_workbook(tmp_path: Path) -> None:
    grant = {
        "actor": "engineer",
        "asset": PREVIEW_SPEC.identity.model_dump(mode="json"),
        "permissions": list(PREVIEW_SPEC.policy.required_permissions),
        "policy_refs": list(PREVIEW_SPEC.policy.policy_refs),
        "approval_ref": "workflow-7-jira-read-approval",
    }
    config, layout = workspace(
        tmp_path,
        membership=membership_record(),
        grants=[grant],
        assets=False,
        config_changes={
            "integrations": {
                "jira": {
                    "base_url": "https://jira.rsint.net/",
                    "auth_mode": "server",
                    "credential": {"name": "jira_pat"},
                },
                "team_tickets": {"project": "MRT1CV", "reporters": ["CHI_L", "peng_k"]},
            },
            "credentials": [{"secret": "jira_pat", "environment_variable": "AEP_JIRA_TOKEN"}],
        },
    )
    export_assets(layout.workspace_root / "assets")
    transport = ScriptedTransport(
        [
            Reply(200, {"issues": [issue(1)], "total": 1}),
            Reply(
                200,
                {
                    "comments": [
                        {
                            "created": "2026-10-03T08:00:00.000+0800",
                            "author": {"displayName": "Leo"},
                            "body": "progress",
                        }
                    ]
                },
            ),
        ]
    )
    request = LocalWorkflowRequest(
        actor="engineer",
        bridge_id=config.device.bridge_id,
        workflow=preview_workflow().metadata.identity,
        arguments={"max_items": 10, "comment_count": 2},
        idempotency_key="workflow-7-jira-preview-1",
        trace=TraceIdentifiers(trace_id="trace-w7", request_id="request-w7", span_id="span-w7"),
    )
    with build_runtime(
        config,
        layout=layout,
        resolver=StaticCredentials({"jira_pat": "fixture-token"}),
        jira_transport=transport,
    ) as runtime:
        outcome = asyncio.run(runtime.agent.execute_workflow(request))
        assert outcome.refusal is None and outcome.workflow is not None
        assert outcome.workflow.run.status == "succeeded", outcome.workflow.run.failure
        preview = TeamTicketsPreview.model_validate(outcome.workflow.step_results[-1].data)
        assert preview.records[0].values["Reporter"] == "Leo"
        assert preview.records[0].values["Jira activity"].endswith("progress")
        assert preview.comment_failures == ()
    assert transport.calls[0]["method"] == "POST"
    assert transport.calls[0]["url"] == "https://jira.rsint.net/rest/api/2/search"
    assert "ORDER BY created DESC" in transport.calls[0]["json"]["jql"]
    assert transport.calls[1]["json"] is None
    assert "orderBy=-created" in transport.calls[1]["url"]
    assert transport.calls[0]["headers"]["Authorization"] == "Bearer fixture-token"
    assert not any(tmp_path.rglob("*.xlsx"))

    layout.grants.write_text("[]", encoding="utf-8")
    denied_transport = ScriptedTransport([])
    with build_runtime(
        config,
        layout=layout,
        resolver=StaticCredentials({"jira_pat": "fixture-token"}),
        jira_transport=denied_transport,
    ) as runtime:
        denied = asyncio.run(
            runtime.agent.execute_workflow(
                request.model_copy(update={"idempotency_key": "workflow-7-jira-denied-1"})
            )
        )
        assert denied.workflow is not None and denied.workflow.run.status != "succeeded"
    assert denied_transport.calls == []


def test_comment_failure_is_visible_without_losing_other_issue_rows() -> None:
    from capabilities.team_tickets.handlers import TeamTicketsPreviewHandler
    from integrations.jira import JiraClient, JiraConnection

    transport = ScriptedTransport(
        [
            Reply(200, {"issues": [issue(2), issue(1)], "total": 2}),
            Reply(403, {}),
            Reply(200, {"comments": []}),
        ]
    )
    client = JiraClient(
        JiraConnection(
            base_url="https://jira.rsint.net",
            auth_mode="server",
            credential={"name": "jira_pat"},
        ),
        StaticCredentials({"jira_pat": "fixture-token"}),
        transport=transport,
    )
    serial_settings = settings().model_copy(update={"comment_concurrency": 1})
    result = TeamTicketsPreviewHandler(client, serial_settings)._preview(TeamTicketsRequest())
    assert [row.key for row in result.records] == ["MRT1CV-2", "MRT1CV-1"]
    assert result.comment_failures == ("MRT1CV-2",)
    assert result.records[0].values["Jira activity"] == "(comment fetch failed: jira_auth)"
    assert result.records[1].values["Jira activity"] == ""


def test_source_bounded_comment_parallelism_is_preserved() -> None:
    from capabilities.team_tickets.handlers import TeamTicketsPreviewHandler
    from integrations.jira import JiraClient, JiraConnection

    class ConcurrentTransport:
        def __init__(self) -> None:
            self.comments_started = Barrier(2)

        def request(
            self,
            method: str,
            url: str,
            body: bytes | None,
            headers: Mapping[str, str],
            timeout_s: float,
        ) -> Reply:
            if method == "POST":
                return Reply(200, {"issues": [issue(2), issue(1)], "total": 2})
            self.comments_started.wait(timeout=5)
            return Reply(200, {"comments": []})

    transport = ConcurrentTransport()
    client = JiraClient(
        JiraConnection(
            base_url="https://jira.rsint.net",
            auth_mode="server",
            credential={"name": "jira_pat"},
            max_retries=0,
        ),
        StaticCredentials({"jira_pat": "fixture-token"}),
        transport=transport,
    )
    parallel_settings = settings().model_copy(update={"comment_concurrency": 2})
    result = TeamTicketsPreviewHandler(client, parallel_settings)._preview(TeamTicketsRequest())
    assert len(result.records) == 2
    assert result.comment_failures == ()


def test_missing_jira_connection_is_reported_in_doctor(tmp_path: Path) -> None:
    config, layout = workspace(
        tmp_path,
        config_changes={"integrations": {"team_tickets": settings().model_dump(mode="json")}},
    )
    checks = {check.name: check for check in host_report(config, layout).checks}
    assert "needs a Jira connection" in checks["integrations"].detail
