"""An explicitly approved browser probe confined to one actual failed repair pass."""

from __future__ import annotations

import asyncio
import copy
import json
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlsplit

from pydantic import JsonValue, ValidationError

from agent.gateway import HostTool, HostToolOutcome
from capabilities.browser_session.handlers import (
    BrowserRequest,
    BrowserSessionHandler,
    browser_origin_scope,
)
from capabilities.contracts import CapabilitySpec
from capabilities.runtime import CapabilityInvocation, LocalPolicy
from common.assets import AssetIdentity, FixedInput, RunInput, WorkflowStep
from common.execution import ExecutionAuthorization, Failure, RequestContext
from host_runtime.authoring_browser_preflight_budget import RepairBudgetError, check_deadline
from host_runtime.authoring_browser_preflight_contracts import (
    MAX_PREFLIGHT_REQUESTS,
    BrowserPreflightApprovalArguments,
    BrowserPreflightCall,
    BrowserPreflightRequest,
    BrowserRepairScope,
)
from host_runtime.authoring_browser_preflight_contracts import (
    PREFLIGHT_SOURCE as PREFLIGHT_SOURCE,
)
from host_runtime.authoring_browser_preflight_contracts import (
    PREFLIGHT_TOOL as PREFLIGHT_TOOL,
)
from host_runtime.chat_authoring import (
    ApprovalRequest,
    ChatAuthoring,
    ChatAuthoringError,
    ChatCandidate,
    _call_digest,
    _excerpt,
    _key,
    _now,
    digest,
)
from host_runtime.workspace import write_atomically
from integrations.web_script import WebScriptError, _fill_in, origin_permitted
from models.contracts import ModelTool
from workflow.dispatch import BridgeExecutor


def is_preflight(item: ApprovalRequest) -> bool:
    return item.kind == "capability" and item.source == PREFLIGHT_SOURCE


def _refused(code: str) -> HostToolOutcome:
    return HostToolOutcome(status="failed", failure=Failure(code=code, message=code))


def _origin(url: str) -> str:
    parts = urlsplit(url)
    if (
        parts.scheme not in ("http", "https")
        or not parts.hostname
        or parts.username is not None
        or parts.password is not None
    ):
        raise ValueError("invalid browser origin")
    _ = parts.port
    return f"{parts.scheme}://{parts.netloc}".lower()


def _inputs(step: WorkflowStep, arguments: dict[str, JsonValue]) -> BrowserRequest:
    values: dict[str, JsonValue] = {}
    for name, reference in step.inputs.items():
        if isinstance(reference, FixedInput):
            values[name] = copy.deepcopy(reference.value)
        elif isinstance(reference, RunInput):
            value: Any = arguments
            for part in reference.path:
                value = value[part]
            values[name] = copy.deepcopy(value)
        else:
            raise ValueError("preflight cannot consume an unexecuted step")
    request = BrowserRequest.model_validate_json(json.dumps(values))
    if request.for_each is not None:
        raise ValueError("preflight cannot run a collection loop")
    return request


def _state(chat: ChatAuthoring, scope: BrowserRepairScope) -> ChatCandidate:
    candidate = chat.candidate(scope.candidate_id, scope.actor)
    task = chat.tasks.load(scope.actor, scope.session_id)
    saved = candidate.authoring_task
    if (
        candidate.session_id != scope.session_id
        or candidate.status == "installed"
        or task is None
        or saved is None
        or task.last_status != "failed"
        or task.active_trial_token is not None
        or task.verified_digest is not None
        or task.last_run_id != scope.trial_run_id
        or task.last_trial_digest != scope.trial_digest
        or task.repair_attempts != scope.repair_attempt
        or not 1 <= task.repair_attempts < 3
        or _call_digest("trial_arguments", task.last_trial_arguments)
        != scope.trial_arguments_digest
        or saved.last_run_id != task.last_run_id
        or saved.last_trial_digest != task.last_trial_digest
        or saved.repair_attempts != task.repair_attempts
        or saved.last_trial_arguments != task.last_trial_arguments
    ):
        raise ChatAuthoringError("preflight_stale")
    diagnostics = task.last_trial_diagnostics or {}
    failed = diagnostics.get("failed_steps")
    if (
        diagnostics.get("run_id") != scope.trial_run_id
        or not isinstance(failed, list)
        or len(failed) != 1
        or not isinstance(failed[0], dict)
        or failed[0].get("step_index") != scope.step_index
        or failed[0].get("capability") != _key(scope.capability)
        or scope.step_index >= len(candidate.draft.steps)
    ):
        raise ChatAuthoringError("preflight_stale")
    step = candidate.draft.steps[scope.step_index]
    if not isinstance(step, WorkflowStep) or step.capability != scope.capability:
        raise ChatAuthoringError("preflight_stale")
    approvals = chat.approvals(scope.actor, session_id=scope.session_id, pending_only=False)
    if not any(
        a.kind == "run"
        and a.status == "approved"
        and a.candidate_id == scope.candidate_id
        and a.digest == scope.trial_digest
        and isinstance(a.result, dict)
        and a.result.get("run_id") == scope.trial_run_id
        and a.result.get("status") == "failed"
        for a in approvals
    ):
        raise ChatAuthoringError("preflight_trial_approval_required")
    if any(
        a.kind == "run" and a.status == "pending" and a.candidate_id == scope.candidate_id
        for a in approvals
    ):
        raise ChatAuthoringError("preflight_trial_pending")
    return candidate


def repair_scope_for(chat: ChatAuthoring, candidate: ChatCandidate) -> BrowserRepairScope | None:
    """Capture immutable origin authority before an automatic repair edits inputs."""
    task = chat.tasks.load(candidate.actor, candidate.session_id) if candidate.session_id else None
    if (
        task is None
        or not candidate.session_id
        or not task.last_run_id
        or not task.last_trial_digest
        or digest(candidate.draft) != task.last_trial_digest
    ):
        return None
    failed = (task.last_trial_diagnostics or {}).get("failed_steps")
    if not isinstance(failed, list) or len(failed) != 1 or not isinstance(failed[0], dict):
        return None
    index = failed[0].get("step_index")
    if type(index) is not int or not 0 <= index < len(candidate.draft.steps):
        return None
    step = candidate.draft.steps[index]
    if not isinstance(step, WorkflowStep) or (step.capability.namespace, step.capability.name) != (
        "browser",
        "operate",
    ):
        return None
    binding = chat.installed.get(step.capability)
    if binding is None or not isinstance(binding.handler, BrowserSessionHandler):
        return None
    try:
        request = _inputs(step, task.last_trial_arguments)
        origins = tuple(
            sorted(
                {
                    _origin(_fill_in(a.url, request.values))
                    for a in request.actions
                    if a.do == "open" and a.url is not None
                }
            )
        )
        scope = BrowserRepairScope(
            actor=candidate.actor,
            session_id=candidate.session_id,
            candidate_id=candidate.candidate_id,
            trial_run_id=task.last_run_id,
            trial_digest=task.last_trial_digest,
            trial_arguments_digest=_call_digest("trial_arguments", task.last_trial_arguments),
            repair_attempt=task.repair_attempts,
            step_index=index,
            capability=step.capability,
            origins=origins,
        )
        _state(chat, scope)
        if not all(origin_permitted(o, set(binding.handler.allowed_origins)) for o in origins):
            return None
        return scope
    except (ValueError, KeyError, IndexError, TypeError, ChatAuthoringError, WebScriptError):
        return None


def _call(item: ApprovalRequest) -> BrowserPreflightCall:
    if not is_preflight(item):
        raise ChatAuthoringError("preflight_scope_required")
    try:
        call = BrowserPreflightApprovalArguments.model_validate(
            item.arguments
        ).authoring_browser_preflight
    except ValueError as error:
        raise ChatAuthoringError("preflight_invalid") from error
    if (
        item.actor != call.scope.actor
        or item.session_id != call.scope.session_id
        or item.candidate_id != call.scope.candidate_id
        or item.workflow != _key(call.scope.capability)
        or item.digest != _call_digest(item.workflow, item.arguments)
    ):
        raise ChatAuthoringError("preflight_stale")
    return call


def _requests(chat: ChatAuthoring, scope: BrowserRepairScope) -> list[ApprovalRequest]:
    result = []
    for item in chat.approvals(scope.actor, session_id=scope.session_id, pending_only=False):
        if not is_preflight(item) or item.candidate_id != scope.candidate_id:
            continue
        call = _call(item)
        if call.scope.trial_run_id == scope.trial_run_id:
            result.append(item)
    return result


def _check_call(chat: ChatAuthoring, call: BrowserPreflightCall) -> ChatCandidate:
    candidate = _state(chat, call.scope)
    check_deadline(chat, call.scope)
    if digest(candidate.draft) != call.candidate_digest:
        raise ChatAuthoringError("preflight_stale")
    if (call.scope.capability.namespace, call.scope.capability.name) != ("browser", "operate"):
        raise ChatAuthoringError("preflight_scope_required")
    binding = chat.installed.get(call.scope.capability)
    if binding is None or not isinstance(binding.handler, BrowserSessionHandler):
        raise ChatAuthoringError("preflight_scope_required")
    allowed = set(call.scope.origins)
    if not allowed or any(_origin(o) != o for o in allowed):
        raise ChatAuthoringError("preflight_origin_refused")
    for action in call.browser.actions:
        if action.do == "open" and action.url is not None:
            url = _fill_in(action.url, call.browser.values)
            if _origin(url) not in allowed:
                raise ChatAuthoringError("preflight_origin_refused")
    if not all(origin_permitted(o, set(binding.handler.allowed_origins)) for o in allowed):
        raise ChatAuthoringError("preflight_origin_refused")
    return candidate


def preflight_tool(
    chat: ChatAuthoring, context: RequestContext, scope: BrowserRepairScope
) -> HostTool:
    async def request(ctx: RequestContext, arguments: dict[str, JsonValue]) -> HostToolOutcome:
        if (ctx.actor, ctx.session_id, ctx.trace) != (
            context.actor,
            context.session_id,
            context.trace,
        ):
            return _refused("preflight_scope_required")
        try:
            parsed = BrowserPreflightRequest.model_validate(arguments)
            if (parsed.candidate_id, ctx.actor, ctx.session_id) != (
                scope.candidate_id,
                scope.actor,
                scope.session_id,
            ):
                raise ChatAuthoringError("preflight_scope_required")
            with chat._candidate_lock(scope.candidate_id):
                candidate = _state(chat, scope)
                task = chat.tasks.load(scope.actor, scope.session_id)
                assert task is not None
                step = candidate.draft.steps[scope.step_index]
                assert isinstance(step, WorkflowStep)
                original = _inputs(step, task.last_trial_arguments)
                call = BrowserPreflightCall(
                    scope=scope,
                    candidate_digest=parsed.base_digest,
                    browser=original.model_copy(update={"actions": parsed.actions, "look": True}),
                )
                _check_call(chat, call)
                payload = BrowserPreflightApprovalArguments(
                    authoring_browser_preflight=call
                ).model_dump(mode="json")
                key = _key(scope.capability)
                identity = _call_digest(key, payload)
                previous = _requests(chat, scope)
                for item in previous:
                    if item.digest != identity:
                        continue
                    if item.status == "pending":
                        return HostToolOutcome(
                            status="awaiting_approval",
                            data={
                                "approval_id": item.approval_id,
                                "summary": item.summary,
                                "preflight_only": True,
                                "next": "Wait for this exact approval; nothing ran yet.",
                            },
                        )
                    result = item.result if isinstance(item.result, dict) else {}
                    if item.status == "approved" and result.get("status") == "succeeded":
                        return HostToolOutcome(
                            status="succeeded", data={**result, "replayed": True}
                        )
                    return _refused("preflight_previous_failure")
                if len(previous) >= MAX_PREFLIGHT_REQUESTS:
                    return _refused("preflight_limit")
                item = chat._save_approval(
                    ApprovalRequest(
                        approval_id=f"ap-{datetime.now(UTC):%Y%m%d-%H%M%S}-{secrets.token_hex(3)}",
                        actor=scope.actor,
                        session_id=scope.session_id,
                        kind="capability",
                        source=PREFLIGHT_SOURCE,
                        candidate_id=scope.candidate_id,
                        digest=identity,
                        workflow=key,
                        arguments=payload,
                        summary=(
                            f"Validate {len(parsed.actions)} browser actions for "
                            f"{candidate.title}; sites: {', '.join(scope.origins)}. "
                            "This is not a full Workflow trial."
                        ),
                        created_at=_now(),
                    )
                )
                return HostToolOutcome(
                    status="awaiting_approval",
                    data={
                        "approval_id": item.approval_id,
                        "summary": item.summary,
                        "preflight_only": True,
                        "next": "Nothing ran. Stop for the normal approval button.",
                    },
                )
        except (ValidationError, ValueError, KeyError, TypeError, WebScriptError):
            return _refused("preflight_invalid")
        except (ChatAuthoringError, RepairBudgetError) as error:
            if isinstance(error, RepairBudgetError):
                return _refused(str(error))
            return _refused(error.code)

    return HostTool(
        ModelTool(
            name=PREFLIGHT_TOOL,
            description="Validate a small proposed browser correction BEFORE patching the failed "
            "step. Supply this candidate_id, current base_digest and one to eight documented "
            "browser actions. Only its original sites are allowed. No downloads or pagination. "
            "At most two requests in this same repair pass. An explicit approval is required; "
            "stop when pending. After real evidence, patch only the failed step, preserving all "
            "other code/inputs, and request the full trial. "
            "This never verifies or installs a Workflow.",
            input_contract="host.authoring-browser-preflight.v1",
            input_schema=BrowserPreflightRequest.model_json_schema(),
        ),
        request,
        side_effect="external_side_effect",
    )


@dataclass
class _ApprovedPolicy(LocalPolicy):
    """One approved model call with the normal trial's narrowed temporary grant."""

    original: LocalPolicy
    context: RequestContext
    target: AssetIdentity

    def confirmation_needed(self, spec: CapabilitySpec, origin: str) -> bool:
        return origin != "model" or spec.identity != self.target

    def authorize(self, context: RequestContext, spec: CapabilitySpec) -> ExecutionAuthorization:
        if context != self.context or spec.identity != self.target:
            return ExecutionAuthorization()
        return self.original.authorize(context, spec)


def execute_approved_preflight(
    chat: ChatAuthoring, item: ApprovalRequest, actor: str, *, approve: bool = True
) -> ApprovalRequest:
    """A decision is claimed durably before any external action, including on crash."""
    try:
        call = _call(item)
        if actor != call.scope.actor:
            raise ChatAuthoringError("preflight_scope_required")
        with chat._candidate_lock(call.scope.candidate_id):
            current = chat.approval(item.approval_id, actor)
            if current.status != "pending":
                raise ChatAuthoringError("approval_already_decided")
            call = _call(current)
            if not approve:
                return chat._save_approval(
                    current.model_copy(
                        update={
                            "status": "rejected",
                            "decided_at": _now(),
                        }
                    )
                )
            candidate = _check_call(chat, call)
            if len(_requests(chat, call.scope)) > MAX_PREFLIGHT_REQUESTS:
                raise ChatAuthoringError("preflight_limit")
            claimed = chat._save_approval(
                current.model_copy(
                    update={
                        "status": "approved",
                        "decided_at": _now(),
                        "result": {
                            "status": "unavailable",
                            "preflight_only": True,
                            "failure": "preflight_execution_unknown",
                        },
                    }
                )
            )
            original = chat._bridge()
            context = chat._context(actor, chat.namespace, call.scope.session_id, "preflight")
            # Exactly the normal approved-trial grant, narrowed to the already
            # approved failed capability. Never add it to the resident policy.
            grants = tuple(
                grant
                for grant in chat.grants(candidate.draft, actor, f"preflight:{item.approval_id}")
                if grant.asset == call.scope.capability
            )
            bridge = BridgeExecutor(
                original.installed,
                _ApprovedPolicy(LocalPolicy(grants), context, call.scope.capability),
                services=original.services,
                timeout_seconds=original.timeout_seconds,
            )
            bridge.exclusive = original.exclusive
            with browser_origin_scope(call.scope.origins):
                result = asyncio.run(
                    bridge.execute(
                        CapabilityInvocation(
                            context=context,
                            target=call.scope.capability,
                            arguments=call.browser.model_dump(mode="json"),
                            origin="model",
                        )
                    )
                )
            return chat._save_approval(
                claimed.model_copy(
                    update={
                        "result": {
                            "status": result.status,
                            "preflight_only": True,
                            "verified": False,
                            "model_origin": True,
                            "handler_invoked": result.handler_invoked,
                            "data": result.data,
                            "failure": result.failure.code if result.failure else None,
                        }
                    }
                )
            )
    except (ChatAuthoringError, RepairBudgetError) as error:
        code = error.code if isinstance(error, ChatAuthoringError) else str(error)
        if code in {"approval_already_decided", "authoring_candidate_busy"}:
            raise
        return chat._save_approval(
            item.model_copy(
                update={
                    "status": "failed",
                    "decided_at": _now(),
                    "result": {"status": "failed", "preflight_only": True, "failure": code},
                }
            )
        )


def claim_continuation(
    chat: ChatAuthoring, actor: str, session: str, approval_id: str
) -> BrowserRepairScope | None:
    try:
        item = chat.approval(approval_id, actor)
        call = _call(item)
        if call.scope.session_id != session:
            return None
        with chat._candidate_lock(call.scope.candidate_id):
            _check_call(chat, call)
            result = item.result if isinstance(item.result, dict) else {}
            if (
                item.status != "approved"
                or not result.get("handler_invoked")
                or result.get("status") not in {"succeeded", "failed"}
                or result.get("failure") in {"timeout", "handler_error"}
            ):
                return None
            marker = chat._file("preflight-resume", approval_id)
            if marker.exists():
                return None
            write_atomically(
                marker, json.dumps({"approval_id": approval_id, "claimed": True}).encode()
            )
            return call.scope
    except (ChatAuthoringError, RepairBudgetError, ValueError):
        return None


def continuation_evidence(chat: ChatAuthoring, actor: str, approval_id: str) -> str:
    item = chat.approval(approval_id, actor)
    return json.dumps(_excerpt(item.result), ensure_ascii=False)


def approval_details(item: ApprovalRequest) -> dict[str, JsonValue]:
    """Exact reviewable operations, shown only on this scoped approval's card."""
    try:
        call = _call(item)
    except ChatAuthoringError:
        return {"error": "preflight_invalid"}
    return {
        "candidate_id": call.scope.candidate_id,
        "candidate_digest": call.candidate_digest,
        "failed_step": call.scope.step_index,
        "origins": list(call.scope.origins),
        "actions": [a.model_dump(mode="json", exclude_none=True) for a in call.browser.actions],
        "values": dict(call.browser.values),
        "preflight_only": True,
    }
