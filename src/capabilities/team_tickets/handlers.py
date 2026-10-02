"""Adapt source W3-07's record preview to the configured GitHub Project."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence

from capabilities.contracts import CapabilitySpec
from capabilities.runtime import CapabilityRefused, TransientCapabilityError
from capabilities.team_tickets.contracts import (
    TeamTicketsPreview,
    TeamTicketsRequest,
    TicketPreviewRecord,
)
from common.base import Contract
from common.execution import RequestContext
from integrations.github_project import (
    GitHubError,
    GitHubProjectClient,
    ProjectComment,
    ProjectItem,
)

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

PREVIEW_SPEC = CapabilitySpec.model_validate(
    {
        "identity": {"namespace": "team-tickets", "name": "preview", "version": "1.0.0"},
        "name": "team_tickets.preview",
        "description": "Read the configured GitHub Project into a Workflow 7 ticket preview",
        "input_contract": "team-tickets.preview.request.v1",
        "output_contract": "team-tickets.preview.output.v1",
        "side_effect": "read",
        "policy": {"required_permissions": ["github.read"], "policy_refs": ["github-read-policy"]},
    }
)


class TeamTicketsPreviewHandler:
    def __init__(self, client: GitHubProjectClient) -> None:
        self.client = client

    async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
        request = TeamTicketsPreviewInput.model_validate(inputs).request
        try:
            rows = await asyncio.to_thread(self.client.items)
        except GitHubError as failure:
            if failure.code in ("github_unavailable", "github_rate_limited"):
                raise TransientCapabilityError(failure.code) from None
            raise CapabilityRefused(failure.code) from None
        return preview_items(rows, request)


class TeamTicketsPreviewInput(Contract):
    request: TeamTicketsRequest = TeamTicketsRequest()


def preview_items(rows: Sequence[ProjectItem], request: TeamTicketsRequest) -> TeamTicketsPreview:
    """Map available GitHub fields to the source's managed columns, visibly.

    The source's Jira resolution has no equivalent in this Project. Empty
    values and `unmapped_fields` are preferable to invented source data.
    """
    checked = TeamTicketsRequest.model_validate(request)
    # Source W3-07 searches with ORDER BY created DESC. Project V2's item
    # ordering is unrelated to issue creation time, so normalize before the
    # cap; otherwise a limited preview can omit the newest tickets.
    tracked = sorted((row for row in rows if row.key), key=lambda row: row.created, reverse=True)
    capped = len(tracked) > checked.max_items
    selected = tracked[: checked.max_items]
    records: list[TicketPreviewRecord] = []
    missing: set[str] = {"Resolution"}
    truncated: list[str] = []
    for row in selected:
        fields = row.fields
        issue_type = fields.get("Type") or fields.get("Issue Type") or ""
        assignee = fields.get("Assignee") or fields.get("Assignees") or ""
        status = fields.get("Status") or row.state
        if row.comments_truncated:
            truncated.append(row.key)
            activity = ""
            missing.add("Jira activity")
        else:
            activity = _activity(row.comments, checked.comment_count)
        values = {
            "Key": row.key,
            "Summary": row.title,
            "Type": issue_type,
            "Status": status,
            "Priority": fields.get("Priority") or "",
            "Reporter": row.author,
            "Assignee": assignee,
            "Created": _source_date(row.created),
            "Updated": _source_date(row.updated),
            "Resolution": "",
            "Jira activity": activity,
        }
        for header in ("Type", "Priority", "Reporter", "Assignee", "Created", "Updated"):
            if not values[header]:
                missing.add(header)
        sheet = "Task" if issue_type.casefold() in ("task", "sub-task") else "Issues"
        records.append(TicketPreviewRecord(key=row.key, url=row.url, sheet=sheet, values=values))
    return TeamTicketsPreview(
        records=tuple(records),
        task_count=sum(record.sheet == "Task" for record in records),
        issues_count=sum(record.sheet == "Issues" for record in records),
        capped=capped,
        truncated_threads=tuple(truncated),
        unmapped_fields=tuple(header for header in MANAGED_HEADERS if header in missing),
    )


def _source_date(value: str) -> str:
    """Match source W3-07's displayed YYYY-MM-DD HH:MM cell format."""
    return value[:10] + " " + value[11:16] if len(value) >= 16 else ""


def _activity(comments: Sequence[ProjectComment], count: int) -> str:
    if count == 0:
        return ""
    ordered = sorted(comments, key=lambda item: item.created, reverse=True)[:count]
    parts: list[str] = []
    for comment in ordered:
        body = comment.body.replace("\r\n", "\n").strip()
        if len(body) > 1000:
            body = body[:1000] + "…"
        parts.append(f"[{_source_date(comment.created)} {comment.author}]\n{body}")
    return "\n\n".join(parts)
