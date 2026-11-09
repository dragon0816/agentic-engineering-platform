"""Whether the model can fix a failed tool call itself (owner 2026-10-20).

A live conversation handed `coding_workspace_missing` to the person twice and
asked them to create a folder by hand, after two or three tool calls of a
150-call budget. Every failed tool call now carries `recovery`: a
machine-readable `recoverable` flag and a short `hint`, decided by the Host
from the failure code, never by the model.

- Recoverable: the model's own arguments were wrong or missing (`invalid_input`
  with the field named, a Workflow's run values, a draft's problems, a task
  folder outside the roots, a tool name that is not offered), a known technical
  observation/execution failure, or the failure is marked retryable. Corrected
  model repair stays within existing turn, repetition and authoring budgets;
  it does not authorize an unchanged transport retry or bypass a policy gate.
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

_BROWSER_TARGET_REPAIR = (
    "Inspect fresh authorized DOM and the failed action/page evidence; check control "
    "state.invalid, visibility and readiness. Correct the selector, scope or action from "
    "observed evidence and repair the candidate. Do not ask the person for CSS, custom "
    "locators or manual navigation. Preserve the whole goal and existing bounds."
)
_BROWSER_PAGING_REPAIR = (
    "Inspect fresh DOM, headers, current/total pages and row keys. Repair the candidate's "
    "pagination/readiness procedure from that evidence, starting at the intended first page. "
    "Preserve all requested filters, dates, pages and completeness checks; never strip "
    "pagination or relax limits to pass. Use a complete bounded procedure, or record the "
    "unmet requirement if existing bounds prevent completion. Do not ask for manual navigation."
)
_AUTHORING_PLAN_REPAIR = (
    "Read the saved authoring plan and candidate. Preserve every requirement and supplied "
    "input, correct the plan/coverage declarations and revise the complete candidate. Use "
    "actual current-revision trial evidence for coverage; never invent proof or reduce the goal."
)

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
    "web_target_missing": _BROWSER_TARGET_REPAIR,
    "web_target_ambiguous": _BROWSER_TARGET_REPAIR,
    "web_target_obscured": _BROWSER_TARGET_REPAIR,
    "web_target_disabled": _BROWSER_TARGET_REPAIR,
    "web_target_not_visible": _BROWSER_TARGET_REPAIR,
    "web_selector_invalid": _BROWSER_TARGET_REPAIR,
    "web_scope_missing": _BROWSER_TARGET_REPAIR,
    "web_scope_ambiguous": _BROWSER_TARGET_REPAIR,
    "web_wait_timeout": _BROWSER_TARGET_REPAIR,
    "web_row_missing": _BROWSER_TARGET_REPAIR,
    "web_row_ambiguous": _BROWSER_TARGET_REPAIR,
    "web_table_missing": _BROWSER_TARGET_REPAIR,
    "web_table_header_missing": _BROWSER_TARGET_REPAIR,
    "web_column_missing": _BROWSER_TARGET_REPAIR,
    "web_page_did_not_load": _BROWSER_TARGET_REPAIR,
    "web_page_unreadable": _BROWSER_TARGET_REPAIR,
    "web_value_missing": (
        "Read the saved supplied inputs and current candidate placeholders. Bind the missing "
        "value from its recorded origin; ask only if a required business value is truly absent."
    ),
    "web_pagination_invalid": _BROWSER_PAGING_REPAIR,
    "web_pagination_not_at_start": _BROWSER_PAGING_REPAIR,
    "web_pagination_changed": _BROWSER_PAGING_REPAIR,
    "web_pagination_did_not_advance": _BROWSER_PAGING_REPAIR,
    "web_pagination_duplicate_keys": _BROWSER_PAGING_REPAIR,
    "web_pagination_limit_exceeded": _BROWSER_PAGING_REPAIR,
    "web_table_limit_exceeded": _BROWSER_PAGING_REPAIR,
    "coding_program_failed": (
        "Read the retained stdout/exit diagnostics and inputs. Repair the program and "
        "candidate for the whole task, then trial the revision within existing bounds. "
        "Old output files are not evidence of success."
    ),
    "coding_program_timeout": (
        "Read retained diagnostics, identify the slow operation and repair the bounded "
        "program. Keep timeout/resource limits and the whole goal; do not blindly rerun it."
    ),
    "coding_output_scan_limit": (
        "Output fingerprinting exceeded its bound. Preserve existing files and limits; "
        "use a fresh allowed task workspace with the recorded inputs and regenerate the "
        "whole requested output. Do not delete historical files or trust unscanned outputs."
    ),
    "data_merge_conflict": (
        "Inspect both source objects and their bindings. Correct conflicting keys in the "
        "candidate or use distinct explicit field names; never silently overwrite a value."
    ),
    "workflow_output_check_failed": (
        "Inspect the failed output checks and actual fresh outputs. Repair the candidate "
        "to meet every original requirement and check; do not weaken assertions or accept "
        "stale files. Preserve successful side effects and trial only the needed revision "
        "under existing approvals and repair budgets."
    ),
    "authoring_plan_required": _AUTHORING_PLAN_REPAIR,
    "authoring_plan_invalid": _AUTHORING_PLAN_REPAIR,
    "authoring_requirements_missing": _AUTHORING_PLAN_REPAIR,
    "authoring_coverage_incomplete": _AUTHORING_PLAN_REPAIR,
    "authoring_trial_required": (
        "Trial the current candidate with authoring__run_workflow under existing approvals "
        "and unfinished-trial budget, then record actual evidence for every requirement. "
        "Do not install or claim verified readiness before that proof."
    ),
    "authoring_revision_required": (
        "Preserve the successful partial run and its artifacts. Revise the candidate to "
        "complete missing requirements; do not replay the unchanged successful procedure."
    ),
    "authoring_repair_remaining": (
        "Use the remaining bounded authoring repairs: inspect fresh evidence, revise the "
        "candidate for every requirement and trial it under existing approvals."
    ),
    "authoring_technical_question": _BROWSER_TARGET_REPAIR,
    "authoring_input_already_supplied": (
        "Read the saved plan and reuse the supplied value and its origin; do not ask again."
    ),
    "authoring_resources_already_supplied": (
        "Read the saved plan and supplied resources; bind the known resource instead of "
        "asking the person to provide it again."
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
    "web_origin_not_allowed": "The requested browser origin is outside the authorized boundary.",
    "web_click_not_read_only": "This click is not allowed under the current read-only policy.",
    "authoring_repair_limit": (
        "Stop: the unfinished-trial budget is exhausted. Wait for the owner to decide the "
        "next step; do not automatically retry, reset the task or continue execution."
    ),
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
    "Stop and report the unresolved failure and available evidence. Do not repeat the same "
    "call unchanged, invent a fix or hand technical navigation to the person."
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
    "Agent can repair the arguments, observations or candidate in this same turn. A "
    "nonretryable execution failure forbids blind transport retries, but does not forbid "
    "an evidence-based model repair. Inspect fresh authorized DOM and state.invalid, read "
    "diagnostics, then correct the procedure while preserving the whole goal, filters and "
    "pagination. Do not ask for CSS, custom locators or manual navigation. A corrected "
    "technical call failing again does not automatically require the person: obey the "
    "existing turn, repetition and unfinished-trial budgets. authoring_repair_limit means "
    "stop and wait for the owner. If recoverable is false, stop and explain; ask only for "
    "an actual missing business input, resource, authorization or approval. Never bypass "
    "policy, replay a successful side effect or relax limits. Never repeat a failed call "
    "unchanged unless an existing trusted transient-read retry rule explicitly permits it."
)
