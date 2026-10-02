"""Closed inputs and evidence for Workflow 7's read-only GitHub preview."""

from __future__ import annotations

from typing import Literal, Self

from pydantic import Field, model_validator

from common.base import Contract, Text


class TeamTicketsRequest(Contract):
    max_items: int = Field(default=2000, ge=1, le=2000, strict=True)
    comment_count: int = Field(default=2, ge=0, le=100, strict=True)
    args: str = ""

    @model_validator(mode="after")
    def no_silent_text_arguments(self) -> Self:
        if self.args.strip():
            raise ValueError("use structured max_items and comment_count fields")
        return self


class TicketPreviewRecord(Contract):
    key: Text
    url: Text
    sheet: Literal["Task", "Issues"]
    values: dict[str, str]


class TeamTicketsPreview(Contract):
    source: Literal["github-project"] = "github-project"
    records: tuple[TicketPreviewRecord, ...] = ()
    task_count: int = Field(default=0, ge=0, strict=True)
    issues_count: int = Field(default=0, ge=0, strict=True)
    capped: bool = False
    truncated_threads: tuple[str, ...] = ()
    unmapped_fields: tuple[str, ...] = ()
