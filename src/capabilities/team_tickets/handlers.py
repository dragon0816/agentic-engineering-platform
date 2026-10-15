"""Source W3-07's read-only Jira preview over the Host's approved Jira client."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from capabilities.contracts import CapabilitySpec
from capabilities.runtime import CapabilityRefused, TransientCapabilityError
from capabilities.team_tickets.contracts import (
    TeamTicketsPreview,
    TeamTicketsRequest,
    TeamTicketsSettings,
    TicketPreviewRecord,
)
from common.base import Contract
from common.execution import RequestContext
from integrations.jira import JiraClient, JiraError

MANAGED_HEADERS = (
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
)
SEARCH_FIELDS = (
    "summary",
    "issuetype",
    "status",
    "priority",
    "reporter",
    "assignee",
    "created",
    "updated",
    "resolution",
)

PREVIEW_SPEC = CapabilitySpec.model_validate(
    {
        "identity": {"namespace": "team-tickets", "name": "jira-preview", "version": "1.0.0"},
        "name": "team_tickets.jira_preview",
        "description": "Read company Jira into the original Workflow 7 Task and Issues preview",
        "input_contract": "team-tickets.jira-preview.request.v1",
        "output_contract": "team-tickets.jira-preview.output.v1",
        "side_effect": "read",
        "policy": {"required_permissions": ["jira.read"], "policy_refs": ["jira-read-policy"]},
    }
)


class TeamTicketsPreviewInput(Contract):
    request: TeamTicketsRequest = TeamTicketsRequest()


class TeamTicketsPreviewHandler:
    def __init__(self, client: JiraClient, settings: TeamTicketsSettings) -> None:
        self.client = client
        self.settings = settings

    async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
        request = TeamTicketsPreviewInput.model_validate(inputs).request
        try:
            return await asyncio.to_thread(self._preview, request)
        except JiraError as failure:
            if failure.code == "jira_unavailable":
                raise TransientCapabilityError(failure.code) from None
            raise CapabilityRefused(failure.code) from None

    def _preview(self, request: TeamTicketsRequest) -> TeamTicketsPreview:
        jql = build_jql(self.settings, request.extra_jql)
        issues = self.client.search_issues(jql, SEARCH_FIELDS, max_issues=request.max_items + 1)
        activities: dict[str, str] = {}
        comment_failures: list[str] = []
        if request.comment_count:
            keys = [str(issue.get("key") or "") for issue in issues[: request.max_items]]
            workers = min(self.settings.comment_concurrency, max(1, len(keys)))
            with ThreadPoolExecutor(max_workers=workers) as pool:
                for key, activity, failed in pool.map(
                    lambda key: self._comment_activity(key, request.comment_count), keys
                ):
                    if key:
                        activities[key] = activity
                    if failed:
                        comment_failures.append(key)
        return preview_items(
            issues,
            request,
            self.client.connection.base_url,
            activities=activities,
            comment_failures=comment_failures,
        )

    def _comment_activity(self, key: str, count: int) -> tuple[str, str, bool]:
        if not key:
            return "", "", False
        try:
            reply = self.client.request(
                "GET",
                f"issue/{key}/comment",
                params={"orderBy": "-created", "maxResults": count},
            )
            comments = (reply or {}).get("comments") or []
            return key, format_activity(comments[:count]), False
        except JiraError as failure:
            # Source W3-07 degrades comment fetches per ticket, not per run.
            return key, f"(comment fetch failed: {failure.code})", True
        except Exception:  # noqa: BLE001 - preserve the source's per-ticket degradation
            return key, "(comment fetch failed: comment_unavailable)", True


def build_jql(settings: TeamTicketsSettings, extra_jql: str = "") -> str:
    """Match the source W3-07 query, with scope owned by Host settings."""
    reporters = ", ".join('"' + name.replace('"', '\\"') + '"' for name in settings.reporters)
    query = f"project = {settings.project} AND reporter in ({reporters})"
    if extra_jql.strip():
        query += f" AND ({extra_jql.strip()})"
    return query + " ORDER BY created DESC"


def preview_items(
    issues: Sequence[Mapping[str, Any]],
    request: TeamTicketsRequest,
    base_url: str,
    *,
    activities: Mapping[str, str] | None = None,
    comment_failures: Sequence[str] = (),
) -> TeamTicketsPreview:
    """Map the source's eleven managed columns without opening a workbook."""
    checked = TeamTicketsRequest.model_validate(request)
    selected = issues[: checked.max_items]
    records: list[TicketPreviewRecord] = []
    for issue in selected:
        key = str(issue.get("key") or "")
        if not key:
            continue
        values = issue_to_record(issue, (activities or {}).get(key, ""))
        issue_type = values["Type"]
        sheet = "Task" if issue_type.casefold() in ("task", "sub-task") else "Issues"
        records.append(
            TicketPreviewRecord(
                key=key,
                url=f"{base_url.rstrip('/')}/browse/{key}",
                sheet=sheet,
                values=values,
            )
        )
    return TeamTicketsPreview(
        records=tuple(records),
        task_count=sum(record.sheet == "Task" for record in records),
        issues_count=sum(record.sheet == "Issues" for record in records),
        capped=len(issues) > checked.max_items,
        comment_failures=tuple(comment_failures),
    )


def _person(value: Any) -> str:
    if not isinstance(value, Mapping):
        return ""
    return str(value.get("displayName") or value.get("name") or "")


def _date(value: Any) -> str:
    if not value:
        return ""
    text = str(value)
    return text[:10] + " " + text[11:16]


def format_activity(comments: Sequence[Mapping[str, Any]]) -> str:
    parts: list[str] = []
    for comment in comments:
        body = str(comment.get("body") or "").replace("\r\n", "\n").strip()
        if len(body) > 1000:
            body = body[:1000] + "…"
        parts.append(f"[{_date(comment.get('created'))} {_person(comment.get('author'))}]\n{body}")
    return "\n\n".join(parts)


def issue_to_record(issue: Mapping[str, Any], activity: str = "") -> dict[str, str]:
    fields = issue.get("fields") or {}
    if not isinstance(fields, Mapping):
        fields = {}

    def name_of(field: str, default: str = "") -> str:
        value = fields.get(field)
        if isinstance(value, Mapping):
            return str(value.get("name") or default)
        return default

    return {
        "Key": str(issue.get("key") or ""),
        "Summary": str(fields.get("summary") or ""),
        "Type": name_of("issuetype"),
        "Status": name_of("status"),
        "Priority": name_of("priority"),
        "Reporter": _person(fields.get("reporter")),
        "Assignee": _person(fields.get("assignee")),
        "Created": _date(fields.get("created")),
        "Updated": _date(fields.get("updated")),
        "Resolution": name_of("resolution", "Unresolved") or "Unresolved",
        "Jira activity": activity,
    }
