"""Persistent accounting for one repair pass, including its approval continuations."""

from __future__ import annotations

import hashlib
import time
from typing import TYPE_CHECKING, Literal

from pydantic import Field

from agent.backend_contracts import ConversationLimits
from common.base import Contract
from host_runtime.authoring_browser_preflight_contracts import BrowserRepairScope
from host_runtime.workspace import write_atomically

if TYPE_CHECKING:
    from pathlib import Path

    from host_runtime.chat_authoring import ChatAuthoring


class RepairBudgetError(Exception):
    pass


class RepairPassBudget(Contract):
    scope: BrowserRepairScope
    deadline_at: float = Field(gt=0, allow_inf_nan=False)
    model_limit: int = Field(default=20, ge=1, le=20, strict=True)
    tool_limit: int = Field(ge=1, le=150, strict=True)
    model_calls: int = Field(default=0, ge=0, le=20, strict=True)
    tool_calls: int = Field(default=0, ge=0, le=150, strict=True)


def _path(chat: ChatAuthoring, scope: BrowserRepairScope) -> Path:
    identity = hashlib.sha256(scope.model_dump_json().encode()).hexdigest()
    return chat._file("preflight-budget", "pass-" + identity)


def budget(chat: ChatAuthoring, scope: BrowserRepairScope) -> RepairPassBudget:
    try:
        record = RepairPassBudget.model_validate_json(_path(chat, scope).read_bytes())
        if record.scope != scope:
            raise ValueError("repair budget scope differs")
        return record
    except (OSError, ValueError) as error:
        raise RepairBudgetError("preflight_budget_unavailable") from error


def ensure_budget(
    chat: ChatAuthoring, scope: BrowserRepairScope, limits: ConversationLimits
) -> None:
    """Never refresh an existing pass's deadline or consumed calls."""
    with chat._candidate_lock(scope.candidate_id):
        path = _path(chat, scope)
        if path.exists():
            budget(chat, scope)
            return
        record = RepairPassBudget(
            scope=scope,
            deadline_at=time.time() + limits.time_limit_seconds,
            tool_limit=limits.tool_calls,
        )
        write_atomically(path, record.model_dump_json().encode())


def check_deadline(chat: ChatAuthoring, scope: BrowserRepairScope) -> None:
    if time.time() >= budget(chat, scope).deadline_at:
        raise RepairBudgetError("preflight_budget_expired")


def charge(
    chat: ChatAuthoring, scope: BrowserRepairScope, kind: Literal["model", "tool"]
) -> str | None:
    """Charge before the actual request, not from a possibly truncated return value."""
    try:
        with chat._candidate_lock(scope.candidate_id):
            record = budget(chat, scope)
            if time.time() >= record.deadline_at:
                return "preflight_budget_expired"
            if kind == "model":
                if record.model_calls >= record.model_limit:
                    return "preflight_budget_exhausted"
                record = record.model_copy(update={"model_calls": record.model_calls + 1})
            else:
                if record.tool_calls >= record.tool_limit:
                    return "preflight_budget_exhausted"
                record = record.model_copy(update={"tool_calls": record.tool_calls + 1})
            write_atomically(_path(chat, scope), record.model_dump_json().encode())
            return None
    except Exception:  # Host accounting failure must not authorize another request.
        return "preflight_budget_unavailable"
