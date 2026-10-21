"""Whether the model can fix a failed tool call itself (owner 2026-10-20).

A live conversation handed `coding_workspace_missing` to the person twice and
asked them to create a folder by hand, after two or three tool calls of a
150-call budget. Every failed tool call now carries `recovery`: a
machine-readable `recoverable` flag and a short `hint`, decided by the Host
from the failure code, never by the model.

- Recoverable: the model's own arguments were wrong or missing (`invalid_input`
  with the field named, a Workflow's run values, a draft's problems, a task
  folder outside the roots, a tool name that is not offered), or the failure is
  marked retryable. The model fixes the call and tries again in the same turn.
- Needs the person: permission, credentials, approval, something not installed
  or switched off, connectivity, mail scope. The model says what is needed.
- Anything else is not recoverable: the model explains it rather than guessing
  a fix. The repetition guard (three identical failures) still stops a loop.
"""

from __future__ import annotations

import re
from typing import Any

from common.base import Contract, Text
from common.execution import Failure

#: Failure codes the model can fix by changing its own call, with what to do.
_FIXABLE: dict[str, str] = {
    "workflow_parameters_invalid": (
        "The run values were refused ({detail}). Pass only the fields the tool's schema "
        "offers, with the right types, and call it again."
    ),
    "workflow_invalid": (
        "The draft has problems ({detail}). Fix each one and draft again with the whole Workflow."
    ),
    "workflow_missing": "A required argument is missing ({detail}). Add it and call again.",
    "candidate_unknown": (
        "That candidate_id is not one of yours. Use the candidate_id a draft returned in "
        "this conversation, or draft again."
    ),
    "uninstalled_tool": (
        "That tool is not offered. Call one of the supplied tools by its exact name."
    ),
    "coding_workspace_not_absolute": (
        "Give the workspace as an absolute folder under the task roots in your instructions "
        "and call again; a missing folder there is created for you."
    ),
    "coding_workspace_not_allowed": (
        "The workspace is outside the task roots (or uses ..). Use a folder under one of the "
        "roots in your instructions and call again; a missing folder there is created for you."
    ),
    "coding_workspace_not_a_folder": (
        "The workspace names a file. Use a folder under the task roots and call again."
    ),
    "coding_workspace_missing": (
        "Use a folder under the task roots in your instructions and call again; a missing "
        "folder there is created for you."
    ),
    "browser_workspace_not_absolute": (
        "Give the workspace as an absolute folder under the task roots and call again."
    ),
    "browser_workspace_not_allowed": (
        "The workspace is outside the task roots. Use a folder under one of them and call again."
    ),
}

#: Failure codes only the person can resolve, with what to tell them.
_PERSON: dict[str, str] = {
    "permission_denied": "This Agent is not authorized to use this tool here.",
    "approval_required": "This needs the person's approval.",
    "secret_resolution_unavailable": "A credential this tool needs is not available here.",
    "capability_not_installed": "The capability this tool needs is not installed.",
    "missing_local_capability": "A capability this tool depends on is not installed.",
    "workflow_not_installed": "The Workflow is not installed.",
    "needs_connectivity": "A central service this tool needs is not reachable.",
}
#: Words in a code that mean the person must act (sign-in, credentials, scope).
_PERSON_WORDS = (
    "credential",
    "secret",
    "token",
    "password",
    "login",
    "sign_in",
    "signin",
    "unauthor",
    "auth_",
    "forbidden",
    "scope",
    "approval",
    "not_installed",
    "switched_off",
    "disabled",
)
_ASK_PERSON = " Tell the person what is needed and how they can provide it; do not retry the call."
_UNKNOWN = (
    "Explain this failure to the person and what they can do. Do not repeat the same call "
    "unchanged."
)
_INVALID_AT = re.compile(r"Invalid input at (.+)$")


class ToolRecovery(Contract):
    """What the model may do about one failed tool call."""

    recoverable: bool
    hint: Text


def failure_of(item: Any) -> Failure | None:
    """The failure a conversation tool call ended with, wherever it sits."""
    found: Any = None
    host = getattr(item, "host", None)
    capability = getattr(item, "capability", None)
    workflow = getattr(item, "workflow", None)
    if getattr(item, "failure", None) is not None:
        found = item.failure
    elif host is not None:
        found = host.failure if host.status == "failed" else None
    elif capability is not None:
        found = capability.failure if capability.status != "succeeded" else None
    elif workflow is not None and workflow.run.status != "succeeded":
        found = workflow.run.failure
    return found if isinstance(found, Failure) else None


def classify(failure: Failure) -> ToolRecovery | None:
    """`recoverable` and a `hint` for one failure; None when another rule
    already tells the model what to do (a Knowledge answer that was not
    validated keeps its own instruction, G1)."""
    code = failure.code
    if code == "knowledge_not_validated":
        return None
    if code == "invalid_input":
        found = _INVALID_AT.search(failure.message or "")
        where = found.group(1).strip() if found else ""
        fields = sorted({part.split(":", 1)[0].strip() for part in where.split(";") if part})
        named = ", ".join(field for field in fields if field) or "the arguments"
        return ToolRecovery(
            recoverable=True,
            hint=(
                f"The input was refused at {named}"
                + (f" ({where})" if where else "")
                + ". Correct those fields (add a missing one, fix its type, keep it within the "
                "bounds shown; leave out an optional field instead of sending null) and call "
                "the tool again in this turn."
            ),
        )
    if code in _FIXABLE:
        detail = (failure.message or code)[:300]
        return ToolRecovery(recoverable=True, hint=_FIXABLE[code].format(detail=detail))
    if code in _PERSON:
        return ToolRecovery(recoverable=False, hint=_PERSON[code] + _ASK_PERSON)
    lowered = code.lower()
    if any(word in lowered for word in _PERSON_WORDS):
        return ToolRecovery(
            recoverable=False, hint="This needs the person (" + code + ")." + _ASK_PERSON
        )
    if failure.retryable:
        return ToolRecovery(
            recoverable=True,
            hint="A temporary failure. Call the same tool once more; if it fails again, tell "
            "the person.",
        )
    return ToolRecovery(recoverable=False, hint=_UNKNOWN)


def recovery_for(item: Any) -> ToolRecovery | None:
    failure = failure_of(item)
    return None if failure is None else classify(failure)


RECOVERY_GUIDANCE = (
    "A failed tool result carries `recovery`. When `recovery.recoverable` is true, the "
    "problem is in your call: fix the arguments as its hint says and call again in this same "
    "turn, without asking the person or telling them about the error. Ask the person only "
    "when `recoverable` is false (permission, credentials, approval, something not installed, "
    "mail scope) or the corrected call failed too. Never repeat a failed call unchanged."
)
