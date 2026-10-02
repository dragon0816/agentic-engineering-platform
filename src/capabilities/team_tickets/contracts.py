"""Closed inputs and evidence for Workflow 7's read-only Jira preview."""

from __future__ import annotations

import re
from typing import Literal, Self

from pydantic import Field, field_validator, model_validator

from common.base import Contract, Text


class TeamTicketsRequest(Contract):
    max_items: int = Field(default=2000, ge=1, le=2000, strict=True)
    comment_count: int = Field(default=2, ge=0, le=100, strict=True)
    extra_jql: str = Field(default="", max_length=2000)
    args: str = ""

    @model_validator(mode="after")
    def no_silent_text_arguments(self) -> Self:
        if self.args.strip():
            raise ValueError("use structured max_items, comment_count and extra_jql fields")
        return self


class TeamTicketsSettings(Contract):
    """Trusted Host-only Jira search scope; no PAT or workbook path lives here."""

    project: Text
    reporters: tuple[Text, ...] = Field(min_length=1)
    comment_concurrency: int = Field(default=5, ge=1, le=20, strict=True)

    @field_validator("project")
    @classmethod
    def jira_project_key(cls, value: str) -> str:
        if re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", value) is None:
            raise ValueError("project must be one Jira project key")
        return value


class TicketPreviewRecord(Contract):
    key: Text
    url: Text
    sheet: Literal["Task", "Issues"]
    values: dict[str, str]


class TeamTicketsPreview(Contract):
    source: Literal["jira"] = "jira"
    records: tuple[TicketPreviewRecord, ...] = ()
    task_count: int = Field(default=0, ge=0, strict=True)
    issues_count: int = Field(default=0, ge=0, strict=True)
    capped: bool = False
    comment_failures: tuple[str, ...] = ()
