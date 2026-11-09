"""Workflows drafted, previewed, run and installed from a conversation (G4).

Conversational authoring slices A4-A6 (`docs/phases/CONVERSATIONAL_AUTHORING.md`):
the Agent drafts a Workflow from the conversation, previews it, and asks to
run it once or to install it. The owner's decisions of 2026-10-06 bound it:

- the model has no tool that approves, installs or runs a change; a run whose
  steps only read runs directly, anything else becomes an approval request
  the owner decides with a button (Agent Web) outside the model's reach;
- a candidate is private to its author, local and unpublished until the
  owner installs it; install writes it published with the owner as business
  approver and adds the grants its steps need;
- every run goes through the Bridge with exactly the grants the candidate's
  steps need for this actor, as a preview does.

Records live under `<workspace>/authoring/chat/`: one JSON file per
candidate and per approval request.

External authoring (owner 2026-10-08, `docs/phases/EXTERNAL_AUTHORING.md`)
uses the same candidates and approvals: Claude Code, Codex or Copilot submit
through `aep-host assets` or `aep-host mcp`, marked `source: external:<agent>`,
and may also submit Skills, which install into the skills folder once the
owner approves. An external agent sees only statuses and codes, never data.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
import secrets
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, cast

from pydantic import Field, JsonValue, ValidationError

from agent.gateway import GatewayConversationResult, HostTool, HostToolOutcome
from agent.skills import SkillManifest
from capabilities.coding_change.workspaces import containing_root, workspace_note
from capabilities.runtime import (
    CapabilityGrant,
    CapabilityInvocation,
    InstalledCapabilities,
    LocalPolicy,
)
from capabilities.workflow_author.conversation import assemble
from common.assets import AssetIdentity, FixedInput, WorkflowManifest, WorkflowStep
from common.base import Contract, Symbol, Text
from common.execution import Failure, RequestContext, TraceIdentifiers
from common.trace import redact
from common.workflow_parameters import WorkflowParameterError, validate_run_parameters
from common.workflow_run_form import OFFER_KEY
from host_runtime.authoring_inputs import bind_supplied_inputs
from host_runtime.authoring_task import (
    PAGINATION_TARGET_FIELDS,
    AuthoringPlanRequest,
    AuthoringQuestion,
    AuthoringTask,
    TaskStore,
    coverage_problems,
    task_guidance,
)
from host_runtime.conversations import ConversationMessage
from host_runtime.skill_authoring import (
    SkillCandidate,
    assemble_skill,
    check_skill,
    installed_skills,
    skill_digest,
)
from host_runtime.team_membership import TeamMembership, membership_note
from host_runtime.workflow_revision import (
    capability_source,
    may_revise_in_place,
    page,
    resolve,
    revision_summary,
    view,
)
from host_runtime.workspace import documents, write_atomically
from models.contracts import ModelTool
from workflow.dispatch import BridgeExecutor
from workflow.engine import InstalledWorkflows, WorkflowEngine, WorkflowRunSnapshot
from workflow.harness import run_workflow_checked

CandidateStatus = Literal["draft", "previewed", "installed"]
ApprovalKind = Literal["run", "install", "install_skill", "capability"]
ApprovalStatus = Literal["pending", "approved", "rejected", "failed"]
MAX_DATA_CHARS = 4_000
MAX_TRIAL_DIAGNOSTICS_BYTES = 12_000


def _diagnostic_text(value: str, limit: int, *, tail: bool = False) -> str:
    cleaned, _ = redact(value)
    encoded = str(cleaned).encode("utf-8")
    bounded = encoded[-limit:] if tail else encoded[:limit]
    return bounded.decode("utf-8", errors="ignore")


def _control_priority(control: dict[str, JsonValue]) -> int:
    state = control.get("state")
    state = state if isinstance(state, dict) else {}
    if state.get("invalid") not in (None, False, "false", ""):
        return 0
    kind = str(state.get("type", control.get("kind", ""))).lower()
    tag = str(control.get("tag", "")).lower()
    if kind not in {"checkbox", "radio", "hidden"} and (
        tag in {"input", "select", "textarea"}
        or kind in {"combobox", "textbox", "searchbox", "spinbutton"}
    ):
        return 1
    if tag == "button" or kind in {"button", "switch"} or "pressed" in state:
        return 2
    if kind in {"checkbox", "radio"}:
        return 4
    if tag == "a" or kind in {"link", "tab", "menuitem", "treeitem"}:
        return 5
    return 3


def _technical_metadata(data: JsonValue) -> dict[str, JsonValue]:
    """Whitelist technical facts; query hints precede row checkboxes and navigation."""
    detail: dict[str, JsonValue] = {}
    if not isinstance(data, dict):
        return detail
    for key in ("failed_action_index", "exit_code", "timed_out"):
        value = data.get(key)
        if key in data and (value is None or isinstance(value, (int, bool))):
            detail[key] = value
    for key in ("failed_action_kind", "url", "diagnostic_error"):
        value = data.get(key)
        if isinstance(value, str):
            detail[key] = _diagnostic_text(value, 700)
    target_field = data.get("failed_target_field")
    if isinstance(target_field, str) and target_field in PAGINATION_TARGET_FIELDS:
        detail["failed_target_field"] = target_field
    overview = data.get("overview")
    if isinstance(overview, dict):
        safe: dict[str, JsonValue] = {}
        for key in (
            "visited_nodes",
            "time_limit_reached",
            "scan_limit_reached",
            "controls_truncated",
            "text_truncated",
        ):
            value = overview.get(key)
            if isinstance(value, (int, bool)):
                safe[key] = value
        raw_controls = overview.get("controls")
        if isinstance(raw_controls, list):
            controls: list[dict[str, JsonValue]] = []
            for raw in raw_controls[:200]:
                if not isinstance(raw, dict):
                    continue
                control: dict[str, JsonValue] = {}
                for key, limit in (("label", 80), ("path", 200), ("tag", 80), ("kind", 32)):
                    value = raw.get(key)
                    if isinstance(value, str):
                        control[key] = _diagnostic_text(value, limit)
                state = raw.get("state")
                if isinstance(state, dict):
                    control["state"] = {
                        key: value if isinstance(value, bool) else _diagnostic_text(value, 80)
                        for key in ("type", "placeholder", "pressed", "expanded", "invalid")
                        if isinstance(value := state.get(key), (str, bool))
                    }
                if isinstance(raw.get("disabled"), bool):
                    control["disabled"] = raw["disabled"]
                controls.append(control)
            controls.sort(key=_control_priority)
            safe["controls"] = cast(list[JsonValue], controls[:32])
            if len(raw_controls) > 32:
                safe["controls_truncated"] = True
        if safe:
            detail["overview"] = safe
    output = data.get("output")
    if isinstance(output, str) and ("exit_code" in data or "timed_out" in data):
        detail["output_tail"] = _diagnostic_text(output, 4000, tail=True)
    return detail


def _trim_control_hint(detail: dict[str, JsonValue]) -> bool:
    overview = detail.get("overview")
    if isinstance(overview, dict) and isinstance(overview.get("controls"), list):
        controls = cast(list[JsonValue], overview["controls"])
        if controls:
            controls.pop()
            overview["controls_truncated"] = True
            return True
    return False


def _trim_technical_metadata(detail: dict[str, JsonValue]) -> bool:
    tail = detail.get("output_tail")
    if isinstance(tail, str) and len(tail) > 256:
        detail["output_tail"] = tail[len(tail) // 2 :]
        return True
    if _trim_control_hint(detail):
        return True
    for key in ("diagnostic_error", "url", "output_tail"):
        value = detail.get(key)
        if isinstance(value, str) and len(value) > 80:
            detail[key] = value[: len(value) // 2]
            return True
    return False


def _failed_data_preview(data: JsonValue) -> JsonValue:
    metadata = _technical_metadata(data)
    if not metadata:
        return _excerpt(data)
    # Leave room for the existing bulk excerpt without letting it crowd out hints.
    while len(json.dumps(metadata, ensure_ascii=False).encode("utf-8")) > 7000:
        if not _trim_technical_metadata(metadata):
            break
    preview_text = json.dumps(redact(data)[0], ensure_ascii=False)
    metadata["truncated"] = len(preview_text) > MAX_DATA_CHARS
    metadata["preview"] = preview_text[:MAX_DATA_CHARS]
    while (
        len(json.dumps(metadata, ensure_ascii=False).encode("utf-8")) > MAX_TRIAL_DIAGNOSTICS_BYTES
    ):
        text = metadata.get("preview")
        if isinstance(text, str) and text:
            metadata["preview"] = text[: len(text) // 2]
            metadata["truncated"] = True
            continue
        if not _trim_technical_metadata(metadata):
            break
    return metadata


def _trial_diagnostics(
    snapshot: WorkflowRunSnapshot, manifest: WorkflowManifest, problems: list[str]
) -> dict[str, JsonValue]:
    """Keep actual technical failure metadata, ahead of page bodies or result rows."""
    run = snapshot.run
    result: dict[str, JsonValue] = {
        "run_id": _diagnostic_text(run.run_id, 128),
        "status": run.status,
        "completed_steps": run.completed_steps,
        "step_results": len(snapshot.step_results),
    }
    if run.failure is not None:
        result["failure"] = {
            "code": _diagnostic_text(run.failure.code, 128),
            "message": _diagnostic_text(run.failure.message, 1500),
        }
    if problems:
        result["coverage_problems"] = [_diagnostic_text(p, 300) for p in problems[:20]]
    failed: list[JsonValue] = []
    for index, step in enumerate(snapshot.step_results):
        if step.status == "succeeded":
            continue
        detail: dict[str, JsonValue] = {"step_index": index, "status": step.status}
        if index < len(manifest.steps) and isinstance(manifest.steps[index], WorkflowStep):
            declared = manifest.steps[index]
            assert isinstance(declared, WorkflowStep)
            detail["capability"] = _diagnostic_text(_key(declared.capability), 256)
        if step.failure is not None:
            detail["failure"] = {
                "code": _diagnostic_text(step.failure.code, 128),
                "message": _diagnostic_text(step.failure.message, 1000),
            }
        detail.update(_technical_metadata(step.data))
        failed.append(detail)
        if len(failed) == 4:
            break
    if failed:
        result["failed_steps"] = failed
    # Redact before limiting strings, so a cut never exposes a credential suffix.
    result = cast(dict[str, JsonValue], redact(result)[0])
    failed = cast(list[JsonValue], result.get("failed_steps", []))
    while len(json.dumps(result, ensure_ascii=False).encode("utf-8")) > MAX_TRIAL_DIAGNOSTICS_BYTES:
        # Retain the real failure/action metadata first when several failures compete.
        if len(failed) > 1:
            failed.pop()
            result["failed_steps"] = failed
        elif isinstance(result.get("coverage_problems"), list) and result["coverage_problems"]:
            cast(list[JsonValue], result["coverage_problems"]).pop()
        else:
            # One failed step's bounded metadata can still be large in UTF-8.
            steps = result.get("failed_steps")
            bounded_detail = steps[0] if isinstance(steps, list) and steps else None
            if isinstance(bounded_detail, dict) and isinstance(
                bounded_detail.get("output_tail"), str
            ):
                tail = cast(str, bounded_detail["output_tail"])
                if len(tail) > 256:
                    bounded_detail["output_tail"] = tail[len(tail) // 2 :]
                    continue
                bounded_detail.pop("output_tail")
            elif isinstance(bounded_detail, dict) and _trim_control_hint(bounded_detail):
                continue
            else:
                result.pop("failed_steps", None)
    return result


def _trial_history_entry(
    candidate: ChatCandidate, snapshot: WorkflowRunSnapshot
) -> dict[str, JsonValue]:
    """Remember actual outcomes and declared target hints, never executable values."""
    entry: dict[str, JsonValue] = {
        "run_id": _diagnostic_text(snapshot.run.run_id, 128),
        "status": snapshot.run.status,
        "candidate_id": _diagnostic_text(candidate.candidate_id, 128),
        "revision": candidate.revision,
        "digest": digest(candidate.draft),
        "completed_steps": snapshot.run.completed_steps,
    }
    if snapshot.run.failure is not None:
        entry["code"] = _diagnostic_text(snapshot.run.failure.code, 128)
    failed: list[JsonValue] = []
    for index, result in enumerate(snapshot.step_results):
        if result.status == "succeeded":
            continue
        step: dict[str, JsonValue] = {"step_index": index, "status": result.status}
        if result.failure is not None:
            step["code"] = _diagnostic_text(result.failure.code, 128)
        declared = candidate.draft.steps[index] if index < len(candidate.draft.steps) else None
        if isinstance(declared, WorkflowStep):
            step["capability"] = _diagnostic_text(_key(declared.capability), 256)
        data = result.data
        target_field = data.get("failed_target_field") if isinstance(data, dict) else None
        if isinstance(target_field, str) and target_field in PAGINATION_TARGET_FIELDS:
            step["failed_target_field"] = target_field
        action_index = data.get("failed_action_index") if isinstance(data, dict) else None
        if (
            isinstance(action_index, int)
            and not isinstance(action_index, bool)
            and 0 <= action_index < 50
        ):
            step["failed_action_index"] = action_index
            if (
                isinstance(declared, WorkflowStep)
                and (declared.capability.namespace, declared.capability.name)
                == ("browser", "operate")
                and isinstance(actions := declared.inputs.get("actions"), FixedInput)
                and isinstance(actions.value, list)
                and action_index < len(actions.value)
            ):
                prefix: list[JsonValue] = []
                for action in actions.value[: action_index + 1]:
                    if not isinstance(action, dict) or not isinstance(action.get("do"), str):
                        continue
                    hint: dict[str, JsonValue] = {
                        "do": _diagnostic_text(cast(str, action["do"]), 32)
                    }
                    target = action.get("target")
                    if isinstance(target, dict):
                        hint["target"] = {
                            key: _diagnostic_text(value, 160 if key == "css" else 80)
                            for key in ("label", "css", "kind")
                            if isinstance(value := target.get(key), str)
                        }
                    prefix.append(hint)
                step["action_prefix"] = prefix
        failed.append(step)
        if len(failed) == 4:
            break
    if failed:
        entry["failed_steps"] = failed
    return cast(dict[str, JsonValue], redact(entry)[0])


def _append_trial_history(
    task: AuthoringTask, candidate: ChatCandidate, snapshot: WorkflowRunSnapshot
) -> tuple[dict[str, JsonValue], ...]:
    history = [*task.trial_history[-9:], _trial_history_entry(candidate, snapshot)]
    while len(json.dumps(history, ensure_ascii=False).encode("utf-8")) > 12000:
        if len(history) > 1:
            history.pop(0)
            continue
        # A long single approach retains its actual terminal failed action.
        steps = history[0].get("failed_steps")
        prefixes = (
            [
                step
                for step in steps
                if isinstance(step, dict)
                and isinstance(step.get("action_prefix"), list)
                and len(cast(list[JsonValue], step["action_prefix"])) > 1
            ]
            if isinstance(steps, list)
            else []
        )
        if not prefixes:
            break
        longest = max(prefixes, key=lambda step: len(cast(list[JsonValue], step["action_prefix"])))
        cast(list[JsonValue], longest["action_prefix"]).pop(0)
        longest["prefix_truncated"] = True
    return tuple(history)


GENERIC_FAILURE = "Capability invocation did not complete"
RUN_TIMEOUT_SECONDS = 900.0


class ChatAuthoringError(Exception):
    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        # Shown to the conversation model only, never to an external agent.
        self.detail = detail
        super().__init__(code)


class ChatCandidate(Contract):
    candidate_id: Symbol
    actor: Symbol
    session_id: Text | None = None
    # Who drafted it: "conversation" (the resident Agent) or "external:<agent>".
    source: Text = "conversation"
    title: Text
    created_at: Text
    updated_at: Text
    revision: int = Field(default=1, ge=1, strict=True)
    draft: WorkflowManifest
    preview_status: Text | None = None
    preview_of: Text | None = None
    status: CandidateStatus = "draft"
    installed_as: Text | None = None
    installed_digest: Text | None = None
    # A revision of an installed Workflow (owner 2026-10-19) records
    # `source: revision:<namespace/name@version>` and the digest of that
    # installed manifest when the revision was made.
    base_digest: Text | None = None
    # A revision kept under a team-owned Workflow's name because the person
    # belongs to that team (owner 2026-10-19): the team, and where the
    # membership came from (`platform`, `platform_cache` or `declared`).
    member_team: Symbol | None = None
    membership_source: Text | None = None
    authoring_task: AuthoringTask | None = None


REVISION_PREFIX = "revision:"


class ApprovalRequest(Contract):
    approval_id: Symbol
    actor: Symbol
    session_id: Text | None = None
    kind: ApprovalKind
    source: Text = "conversation"
    candidate_id: Symbol
    digest: Text
    workflow: Text
    arguments: dict[Symbol, JsonValue] = Field(default_factory=dict)
    summary: Text
    status: ApprovalStatus = "pending"
    created_at: Text
    decided_at: Text | None = None
    result: JsonValue = None


def _core(version: str) -> tuple[int, int, int]:
    """A SemVer's major, minor and patch, for ordering."""
    major, minor, patch = version.split("-", 1)[0].split("+", 1)[0].split(".")
    return int(major), int(minor), int(patch)


def _key(identity: AssetIdentity) -> str:
    return f"{identity.namespace}/{identity.name}@{identity.version}"


def _call_digest(key: str, arguments: dict[str, JsonValue]) -> str:
    """The approved call exactly: a changed target or argument is a new request."""
    payload = json.dumps([key, arguments], sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def digest(manifest: WorkflowManifest) -> str:
    """The Workflow's code identity: the same steps, scripts and inputs give
    the same digest, so a rerun with new values is visibly the same Workflow."""
    return hashlib.sha256(manifest.model_dump_json().encode("utf-8")).hexdigest()


def _excerpt(value: JsonValue, limit: int = MAX_DATA_CHARS) -> JsonValue:
    text = json.dumps(value, ensure_ascii=False)
    if len(text) <= limit:
        return value
    return {"truncated": True, "preview": text[:limit]}


def summarize(snapshot: WorkflowRunSnapshot) -> dict[str, JsonValue]:
    run = snapshot.run
    steps: list[JsonValue] = []
    for index, step in enumerate(snapshot.step_results):
        steps.append(
            {
                "index": index,
                "status": step.status,
                "failure": None
                if step.failure is None
                else (
                    step.failure.code
                    if step.failure.message == GENERIC_FAILURE
                    else f"{step.failure.code}: {step.failure.message}"
                ),
                "data": _excerpt(step.data)
                if step.status == "succeeded"
                else _failed_data_preview(step.data),
            }
        )
    return {
        "run_id": run.run_id,
        "status": run.status,
        "failure": None
        if run.failure is None
        else {"code": run.failure.code, "message": run.failure.message},
        "steps": steps,
    }


DRAFT_GUIDE = (
    "First use authoring__plan_workflow to preserve the SOP requirements before exploring. "
    "Use authoring__get_plan to read saved state. For genuinely missing business choices, "
    "resources or authentication, use authoring__needs_input and ask only that question. "
    "Do not replace the requested automation with manual page switching or a smaller task. "
    "Bind each saved requirement to real output check_ids and procedure assertions; a changed "
    "candidate needs a successful current-version trial before installation. "
    "Save and trial intermediate Workflows to validate discovered steps, then revise the "
    "same candidate. coverage_problems lists remaining requirements; partial trial success "
    "is not verified readiness. Never invent a candidate_id: use the ID returned by draft. "
    "Draft or revise a Workflow from this conversation so it can be previewed, run and reused. "
    "Use it whenever the person asks for a Workflow for this platform, a reusable Workflow, "
    "anything to keep and reuse (做成可以重複用的, 以後都用這個, 建立一個工具), or a run on the "
    "platform runtime; the person installs the draft from the card in the conversation. A "
    "workflow file written by a script is not one, and never "
    "say something ran on the platform unless authoring__run_workflow ran it. "
    '`workflow` is {"name": kebab-case, "description": one sentence, "parameters": '
    '[{"name": snake_case, "label": question, "kind": "text"|"date"|"integer"|'
    '"boolean"|"folder"|"file", "scope": "runtime", "required": true|false}], '
    '"steps": [{"capability": "namespace/name@version", "inputs": {...}}]}. '
    'An input is {"source": "fixed", "value": JSON} for what the Workflow fixes, '
    '{"source": "run", "path": ["<parameter>"]} for a run value ([] is all run values), '
    'or {"source": "step", "step_index": N, "path": [...]} for an earlier step\'s output. '
    "To run your own Python program as a step use coding/run-python@1.0.0 with inputs "
    '{"request": {"source": "fixed", "value": {"workspace": "<absolute task folder>", '
    '"script": "<complete script>"}}, "arguments": {"source": "run", "path": []}}; the '
    'script reads the run values with json.load(open(os.environ["AEP_WORKFLOW_PARAMS"])) and '
    "writes only to the workspace's output folder, so the same script reruns with new values. "
    "If it prints only one complete JSON object, run-python exposes it as output.data. "
    "Use a prior Python step to prepare locale-specific browser values, then bind the "
    "browser values input from that step's ['data']; do not freeze formatted dates. "
    "To combine prepared parameters and Browser data, add a read-only data/merge@1.0.0 "
    "step: bind left from the preparation step's ['data'] and right from the Browser "
    "step's ['data']. Bind the report's arguments from the merge step's ['data']. "
    "Unequal duplicate keys fail; choose nonoverlapping names. Report code must use "
    "these actual values rather than hardcoding the original file/date/rates. "
    'To operate a web system as a step use browser/operate@1.0.0 with inputs {"actions": '
    '{"source": "fixed", "value": [the browser__operate actions]}, "values": '
    '{"source": "run", "path": []}, "workspace": {"source": "fixed", "value": '
    '"<absolute task folder>"}}; a download lands in <workspace>/output/downloads for a later '
    "coding/run-python step. To operate a desktop application as a step use "
    'desktop/operate@1.0.0 with {"app": fixed, "actions": fixed, "values": run values}. '
    "{placeholders} in those actions take the run values; put run values in output file "
    "names so a rerun with new values neither collides with nor overwrites an earlier result. "
    "A system the person signs in to or "
    "operates is reached only through these steps, never fetched or read by a script. "
    "A result made with conversation tools does not show the Workflow works: before saying "
    "it is ready for reuse, run the version that will be reused (the installed one, once "
    "installed) and check what it wrote; fix and rerun until it does the job. When asked to "
    "rerun it with new values, run that installed version unchanged. "
    "Declare what a successful run must produce in `checks`, so the Host can tell a run "
    'that did the job from one that only ended: [{"check_id": snake_case, "step_index": '
    'N, "kind": "files_nonempty"|"file_exists"|"data_nonempty", "pattern": '
    '"*.xlsx"}] (a run-python step lists its output files). '
    "Never put a password, token or key in a fixed value. Pass `candidate_id` to revise a "
    "candidate you drafted before, with the whole Workflow. To change an installed Workflow, "
    "never rewrite it from scratch: read it with authoring__get_workflow (`workflow`), copy "
    "it into a draft with authoring__revise_workflow, then edit that draft here. "
    "The host fills in owner, version and lifecycle."
)


class ChatAuthoring:
    def __init__(
        self,
        root: Path,
        *,
        bridge: Callable[[], BridgeExecutor],
        namespace: str,
        workflows_dir: Path,
        grants_file: Path,
        run_timeout_seconds: float = RUN_TIMEOUT_SECONDS,
        skills_dir: Path | None = None,
        coding_workspace_roots: tuple[str, ...] = (),
        on_installed: Callable[[WorkflowManifest, tuple[CapabilityGrant, ...]], None] | None = None,
        teams: Callable[[str], TeamMembership] | None = None,
        autonomy_required: bool = False,
    ) -> None:
        self.root = root
        # actor -> the teams they belong to (platform, its cache, or the PC's
        # declaration); decides only whether a revision of a team-owned
        # Workflow keeps its name. None: nobody is a team member here.
        self.teams = teams
        # Makes an installed Workflow usable at once, without a restart
        # (owner 2026-10-08: a Workflow installed from the draft list said
        # workflow_not_installed when run from the Capabilities page).
        self.on_installed = on_installed
        # (installed Workflow, the model's run values) -> its run form offer,
        # set by the host; None keeps the plain run (owner 2026-10-15).
        self.form_offer: (
            Callable[[AssetIdentity, dict[str, JsonValue]], dict[str, Any] | None] | None
        ) = None
        self.skills_dir = skills_dir
        # Where a run-python or browser step's fixed workspace may be; checked
        # at draft time so a Workflow never fails only at its approved run.
        self.coding_workspace_roots = coding_workspace_roots
        self._bridge = bridge
        self.namespace = namespace
        self.workflows_dir = workflows_dir
        self.grants_file = grants_file
        self.run_timeout_seconds = run_timeout_seconds
        self.autonomy_required = autonomy_required
        self.tasks = TaskStore(root / "tasks")
        self.session_messages: Callable[[str, str], Sequence[ConversationMessage]] = (
            lambda _actor, _session: ()
        )

    def task_context(self, context: RequestContext) -> str:
        if context.session_id is None:
            return ""
        task = self.tasks.load(context.actor, context.session_id)
        if (
            task is None
            and self.needs_plan(context)
            and re.search(r"workflow|工作流程|自動化|重複用", context.message, re.IGNORECASE)
        ):
            task = self.tasks.save(
                context.actor,
                context.session_id,
                AuthoringTask(objective=context.message[:40000]),
            )
        return task_guidance(task) if task is not None else ""

    def completion_problem(
        self, context: RequestContext, result: GatewayConversationResult
    ) -> str | None:
        """A saved task cannot disappear when the model's history window moves."""
        if context.session_id is None:
            return None
        task = self.tasks.load(context.actor, context.session_id)
        if task is None or task.question is not None:
            return None
        candidates = {
            item.candidate_id: item
            for item in self.candidates(context.actor)
            if item.session_id == context.session_id
        }
        if any(
            task.verified_digest == digest(item.draft) and not coverage_problems(task, item.draft)
            for item in candidates.values()
        ):
            return None
        if any(
            approval.kind in ("run", "capability")
            and (
                approval.kind == "capability"
                or (
                    approval.candidate_id in candidates
                    and approval.digest == digest(candidates[approval.candidate_id].draft)
                )
            )
            for approval in self.approvals(context.actor, session_id=context.session_id)
        ):
            return None
        return (
            "The saved SOP Workflow task is unfinished. Preserve every requirement, "
            "use authoring__get_plan and browser__inspect to repair the candidate, then "
            "trial its current revision with authoring__run_workflow. If a real business "
            "decision, missing resource or authentication prevents progress, record it "
            "with authoring__needs_input. Do not hand technical navigation to the person "
            "or claim the Workflow is complete without current trial evidence."
        )

    def needs_plan(self, context: RequestContext) -> bool:
        if self.autonomy_required:
            return True
        if context.session_id is None:
            return False
        notes = (
            *self.session_messages(context.actor, context.session_id),
            *self.tasks.messages(context.actor, context.session_id),
        )
        return any(
            "sop" in note.text.casefold()
            or any(
                a.get("filename", "").casefold().endswith((".pdf", ".docx"))
                for a in note.attachments
            )
            for note in notes
        )

    def repair_scope(self, context: RequestContext, candidate_id: str) -> None:
        if not context.message.startswith("[Host authoring continuation:"):
            return
        found = re.search(r"Candidate (wf-[a-zA-Z0-9-]+);", context.message)
        if found is None or candidate_id != found[1]:
            raise ChatAuthoringError("authoring_repair_scope")
        item = self.candidate(candidate_id, context.actor)
        if item.session_id != context.session_id:
            raise ChatAuthoringError("authoring_repair_scope")

    @property
    def installed(self) -> InstalledCapabilities:
        return self._bridge().installed

    # -- records -----------------------------------------------------------

    def _file(self, kind: str, ident: str) -> Path:
        if not ident.replace("-", "").isalnum():
            raise ChatAuthoringError(f"{kind}_unknown")
        return self.root / f"{kind}s" / f"{ident}.json"

    def candidate(self, candidate_id: str, actor: str) -> ChatCandidate:
        path = self._file("candidate", candidate_id)
        if not path.is_file():
            raise ChatAuthoringError("candidate_unknown")
        item = ChatCandidate.model_validate_json(path.read_text(encoding="utf-8"))
        if item.actor != actor:
            raise ChatAuthoringError("candidate_unknown")
        return item

    def _save_candidate(self, item: ChatCandidate) -> ChatCandidate:
        stamped = item.model_copy(update={"updated_at": _now()})
        path = self._file("candidate", stamped.candidate_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        write_atomically(path, stamped.model_dump_json(indent=2).encode("utf-8"))
        return stamped

    def candidates(self, actor: str) -> list[ChatCandidate]:
        found = []
        for path in sorted((self.root / "candidates").glob("*.json")):
            try:
                item = ChatCandidate.model_validate_json(path.read_text(encoding="utf-8"))
            except ValueError:
                continue
            if item.actor == actor:
                found.append(item)
        return sorted(found, key=lambda item: item.updated_at, reverse=True)

    def approval(self, approval_id: str, actor: str) -> ApprovalRequest:
        path = self._file("approval", approval_id)
        if not path.is_file():
            raise ChatAuthoringError("approval_unknown")
        item = ApprovalRequest.model_validate_json(path.read_text(encoding="utf-8"))
        if item.actor != actor:
            raise ChatAuthoringError("approval_unknown")
        return item

    def _save_approval(self, item: ApprovalRequest) -> ApprovalRequest:
        path = self._file("approval", item.approval_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        write_atomically(path, item.model_dump_json(indent=2).encode("utf-8"))
        return item

    def approvals(
        self, actor: str, *, session_id: str | None = None, pending_only: bool = True
    ) -> list[ApprovalRequest]:
        found = []
        for path in sorted((self.root / "approvals").glob("*.json")):
            try:
                item = ApprovalRequest.model_validate_json(path.read_text(encoding="utf-8"))
            except ValueError:
                continue
            if item.actor != actor or (pending_only and item.status != "pending"):
                continue
            if session_id is not None and item.session_id != session_id:
                continue
            found.append(item)
        return sorted(found, key=lambda item: item.created_at)

    # -- drafting and preview ---------------------------------------------

    def draft(
        self,
        actor: str,
        session_id: str | None,
        title: str,
        raw: dict[str, Any],
        candidate_id: str | None = None,
        *,
        source: str = "conversation",
    ) -> tuple[ChatCandidate | None, list[str]]:
        """Validate the model's Workflow and keep it as a candidate. Returns
        the candidate, or None with the problems the model must fix."""
        previous = self.candidate(candidate_id, actor) if candidate_id else None
        manifest, problems = self.check(
            actor,
            raw,
            previous,
            base=previous.draft if previous is not None else None,
            member_team=previous.member_team if previous is not None else None,
        )
        if manifest is None:
            return None, problems
        task = self.tasks.load(actor, session_id) if session_id else None
        if task is None and previous is not None:
            task = previous.authoring_task
        if session_id:
            manifest, supplied = bind_supplied_inputs(
                manifest,
                tuple(
                    sorted(
                        (
                            *self.session_messages(actor, session_id),
                            *self.tasks.messages(actor, session_id),
                        ),
                        key=lambda note: note.created_at,
                    )
                ),
                remembered=task.supplied_inputs if task is not None else None,
            )
            if task is not None:
                task = task.model_copy(
                    update={"supplied_inputs": {**task.supplied_inputs, **supplied}}
                )
        self.prepare_workspaces(manifest)
        now = _now()
        if previous is not None and previous.source.startswith(REVISION_PREFIX):
            # A revision stays one, whoever edits it next.
            source = previous.source
        item = ChatCandidate(
            candidate_id=previous.candidate_id
            if previous is not None
            else f"wf-{datetime.now(UTC):%Y%m%d-%H%M%S}-{secrets.token_hex(3)}",
            actor=actor,
            session_id=session_id,
            source=source,
            title=title.strip() or manifest.description,
            created_at=previous.created_at if previous is not None else now,
            updated_at=now,
            revision=previous.revision + 1 if previous is not None else 1,
            draft=manifest,
            installed_as=previous.installed_as if previous is not None else None,
            installed_digest=previous.installed_digest if previous is not None else None,
            base_digest=previous.base_digest if previous is not None else None,
            member_team=previous.member_team if previous is not None else None,
            membership_source=previous.membership_source if previous is not None else None,
            status="installed"
            if previous is not None and previous.installed_digest == digest(manifest)
            else "draft",
            authoring_task=task.model_copy(update={"verified_digest": None}) if task else None,
        )
        if session_id and item.authoring_task is not None:
            self.tasks.save(actor, session_id, item.authoring_task)
        return self._save_candidate(item), []

    def readiness(self, item: ChatCandidate) -> dict[str, JsonValue]:
        active = self.tasks.load(item.actor, item.session_id) if item.session_id else None
        task = active or item.authoring_task
        if task is None:
            return {}
        problems = coverage_problems(task, item.draft)
        return {
            "trial_required": True,
            "verified": not problems and task.verified_digest == digest(item.draft),
            "coverage_complete": not problems,
            "coverage_problems": list(problems),
        }

    def check(
        self,
        actor: str,
        raw: dict[str, Any],
        previous: ChatCandidate | None = None,
        *,
        base: WorkflowManifest | None = None,
        member_team: str | None = None,
    ) -> tuple[WorkflowManifest | None, list[str]]:
        """The Workflow the host would keep, or the problems to fix; saves
        nothing. `base` is the Workflow this one continues (the previous
        draft, or the installed Workflow a revision copies): what the draft
        format has no field for is carried over from it. `member_team` is the
        team a revision is made as a member of: its name stays usable."""
        assembled = assemble(raw, namespace=self.namespace, owner=actor, installed=self.installed)
        if base is not None:
            _carry_over(assembled, base, actor, member_team)
        identity = assembled["metadata"]["identity"]
        # A name belongs to whoever installed it first; its versions only go up,
        # so a new draft of an existing name never reuses an installed version
        # (owner decision 2026-10-07; lab fix-008 W01 hit workflow_version_exists).
        published = self._published(str(identity["namespace"]), str(identity["name"]))
        others = sorted(
            {
                m.metadata.owner.id
                for m in published
                if (m.metadata.owner.type, m.metadata.owner.id) != ("user", actor)
                # A co-editor (recorded contributor) publishes the next version.
                and actor not in m.metadata.contributors
                # So does a member of the owning team, revising (owner 2026-10-19).
                and (m.metadata.owner.type, m.metadata.owner.id) != ("team", member_team)
            }
        )
        if others:
            return None, [
                f"workflow.name: '{identity['name']}' already belongs to "
                f"{', '.join(others)}; choose another name, or ask its owner to let "
                "you co-edit it"
            ]
        taken = [_core(m.metadata.identity.version) for m in published]
        # A revision of an installed Workflow keeps the one version above what
        # is installed (1.0.0 -> 1.0.1) however often it is edited.
        if (
            previous is not None
            and previous.draft.metadata.identity.name == identity["name"]
            and not previous.source.startswith(REVISION_PREFIX)
        ):
            taken.append(_core(previous.draft.metadata.identity.version))
        major, minor, patch = max(taken) if taken else (1, 0, -1)
        identity["version"] = f"{major}.{minor}.{patch + 1}"
        problems: list[str] = []
        unnamed = _unnamed_capabilities(raw)
        if unnamed:
            return None, unnamed
        try:
            manifest = WorkflowManifest.model_validate(assembled)
        except ValidationError as error:
            return None, _step_problems(error)
        for index, step in enumerate(manifest.steps):
            if not isinstance(step, WorkflowStep):
                problems.append(f"step {index}: nested Workflows are not supported here")
            elif self.installed.get(step.capability) is None:
                problems.append(
                    f"step {index}: capability {_key(step.capability)} is not installed"
                )
            else:
                problems.extend(self._workspace_problems(index, step))
                binding = self.installed.get(step.capability)
                assert binding is not None
                fixed = {
                    name: value.value
                    for name, value in step.inputs.items()
                    if isinstance(value, FixedInput)
                }
                try:
                    binding.input_model.model_validate(fixed)
                except ValidationError as error:
                    for problem in error.errors(include_input=False):
                        location = problem["loc"]
                        if (location and location[0] in fixed) or len(fixed) == len(step.inputs):
                            place = ".".join(str(v) for v in location)
                            problems.append(
                                f"step {index}: invalid fixed input {place} ({problem['type']})"
                            )
        if not manifest.steps:
            problems.append("the Workflow has no steps")
        if previous is not None and not raw.get("allow_removed_steps"):
            # A revision that drops what the Workflow did must say so (owner
            # 2026-10-09: a stock Workflow lost its script step after a failure
            # and then "succeeded" without producing anything).
            kept = {
                _key(step.capability) for step in manifest.steps if isinstance(step, WorkflowStep)
            }
            removed = sorted(
                {
                    _key(step.capability)
                    for step in previous.draft.steps
                    if isinstance(step, WorkflowStep)
                }
                - kept
            )
            if removed:
                problems.append(
                    "this revision removes step(s) " + ", ".join(removed) + " that the "
                    'previous version had; if that is intended, pass "allow_removed_steps": '
                    "true and tell the person what the Workflow no longer does"
                )
        return (None, problems) if problems else (manifest, [])

    @staticmethod
    def _fixed_workspace(step: WorkflowStep) -> str | None:
        """The task folder a run-python or browser step fixes, if any."""
        name = (step.capability.namespace, step.capability.name)
        source = None
        if name == ("coding", "run-python"):
            request = step.inputs.get("request")
            value = request.value if isinstance(request, FixedInput) else None
            source = value.get("workspace") if isinstance(value, dict) else None
        elif name == ("browser", "operate"):
            fixed = step.inputs.get("workspace")
            source = fixed.value if isinstance(fixed, FixedInput) else None
        return source if isinstance(source, str) else None

    def _workspace_problems(self, index: int, step: WorkflowStep) -> list[str]:
        """A fixed task folder must lie under the coding roots. Checking
        creates nothing; `prepare_workspaces` does, when the Workflow is kept,
        run or installed."""
        source = self._fixed_workspace(step)
        if source is None:
            return []
        roots = self.coding_workspace_roots
        if containing_root(source, roots) is None:
            allowed = "; ".join(roots) if roots else "none are configured on this host"
            return [
                f"step {index}: workspace {source} is outside the allowed task folders "
                f"({allowed}); use a folder under one of them"
            ]
        return []

    def prepare_workspaces(self, manifest: WorkflowManifest) -> None:
        """Create each fixed task folder that does not exist yet, under its
        coding root, with input/ and output/."""
        for step in manifest.steps:
            if not isinstance(step, WorkflowStep):
                continue
            source = self._fixed_workspace(step)
            resolved = (
                None if source is None else containing_root(source, self.coding_workspace_roots)
            )
            if resolved is not None and not resolved.is_dir():
                for part in ("input", "output"):
                    (resolved / part).mkdir(parents=True, exist_ok=True)

    def _published(self, namespace: str, name: str) -> list[WorkflowManifest]:
        """The versions of one Workflow name installed on this Host."""
        found = []
        for path in self.workflows_dir.glob(f"{namespace}__{name}__*.json"):
            try:
                manifest = WorkflowManifest.model_validate_json(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if (manifest.metadata.identity.namespace, manifest.metadata.identity.name) == (
                namespace,
                name,
            ):
                found.append(manifest)
        return found

    def _engine(self, manifest: WorkflowManifest, actor: str, ref: str) -> WorkflowEngine:
        workflows = InstalledWorkflows()
        workflows.register(manifest)
        bridge = self._bridge()
        trial = BridgeExecutor(
            bridge.installed,
            LocalPolicy(self.grants(manifest, actor, ref)),
            timeout_seconds=bridge.timeout_seconds,
        )
        return WorkflowEngine(workflows, trial, settings_provider=lambda _manifest: {})

    @staticmethod
    def _context(actor: str, namespace: str, session_id: str | None, label: str) -> RequestContext:
        token = secrets.token_hex(8)
        return RequestContext(
            trace=TraceIdentifiers(
                trace_id=f"chat-authoring-{token}", request_id=f"{label}-{token}", span_id=label
            ),
            actor=actor,
            namespace=namespace,
            channel="local",
            session_id=session_id,
            message=f"{label} a Workflow drafted in a conversation",
        )

    def preview(
        self, actor: str, candidate_id: str, arguments: dict[str, JsonValue]
    ) -> dict[str, JsonValue]:
        item = self.candidate(candidate_id, actor)
        engine = self._engine(item.draft, actor, f"chat-preview:{candidate_id}")
        shown = asyncio.run(
            engine.preview(
                self._context(actor, self.namespace, item.session_id, "preview"),
                item.draft.metadata.identity,
                arguments,
            )
        )
        self._save_candidate(
            item.model_copy(
                update={
                    "preview_status": shown.status,
                    "preview_of": digest(item.draft),
                    "status": item.status
                    if item.status == "installed"
                    else ("previewed" if shown.status == "previewed" else "draft"),
                }
            )
        )
        data = json.loads(shown.model_dump_json())
        return {
            "candidate_id": candidate_id,
            "digest": digest(item.draft),
            "preview": _excerpt(data),
        }

    # -- running and installing -------------------------------------------

    def read_only(self, manifest: WorkflowManifest) -> bool:
        for step in manifest.steps:
            binding = (
                self.installed.get(step.capability) if isinstance(step, WorkflowStep) else None
            )
            if binding is None or binding.spec.side_effect != "read":
                return False
        return True

    def _form_instead(
        self, context: RequestContext, draft: WorkflowManifest, arguments: dict[str, JsonValue]
    ) -> dict[str, Any] | None:
        """In a person's conversation, an installed Workflow whose run values
        are incomplete or invalid is handed over as its form, not run and not
        asked for in prose."""
        if self.form_offer is None or context.session_id is None or not draft.parameters:
            return None
        try:
            validate_run_parameters(draft, arguments)
        except WorkflowParameterError:
            return self.form_offer(draft.metadata.identity, arguments)
        return None

    def execute(
        self, actor: str, candidate: ChatCandidate, arguments: dict[str, JsonValue], ref: str
    ) -> dict[str, JsonValue]:
        try:
            arguments = validate_run_parameters(candidate.draft, arguments)
        except WorkflowParameterError as error:
            raise ChatAuthoringError("workflow_input_invalid", str(error)) from None
        candidate = self.begin_trial(actor, candidate, arguments)
        self.prepare_workspaces(candidate.draft)
        engine = self._engine(candidate.draft, actor, ref)
        snapshot = asyncio.run(
            run_workflow_checked(
                engine,
                self._context(actor, self.namespace, candidate.session_id, "run"),
                candidate.draft.metadata.identity,
                arguments,
                timeout_seconds=self.run_timeout_seconds,
            )
        )
        self.record_trial(actor, candidate, snapshot)
        return {
            "candidate_id": candidate.candidate_id,
            "digest": digest(candidate.draft),
            "workflow": _key(candidate.draft.metadata.identity),
            **summarize(snapshot),
            **self.readiness(self.candidate(candidate.candidate_id, actor)),
        }

    def begin_trial(
        self, actor: str, candidate: ChatCandidate, arguments: dict[str, JsonValue]
    ) -> ChatCandidate:
        if candidate.actor != actor:
            raise ChatAuthoringError("candidate_unknown")
        current = self.candidate(candidate.candidate_id, actor)
        if digest(current.draft) != digest(candidate.draft):
            raise ChatAuthoringError("candidate_changed")
        active = self.tasks.load(actor, candidate.session_id) if candidate.session_id else None
        task = active or current.authoring_task
        if task is None:
            return current
        task = task.model_copy(
            update={
                "active_trial_token": secrets.token_hex(16),
                "last_trial_arguments": arguments,
                "verified_digest": None,
                "question": None,
            }
        )
        current = current.model_copy(update={"authoring_task": task})
        current = self._save_candidate(current)
        if candidate.session_id:
            self.tasks.save(actor, candidate.session_id, task)
        return current

    def record_trial(
        self,
        actor: str,
        candidate: ChatCandidate,
        snapshot: WorkflowRunSnapshot,
        executed_manifest: WorkflowManifest | None = None,
    ) -> None:
        if candidate.actor != actor:
            raise ChatAuthoringError("candidate_unknown")
        current = self.candidate(candidate.candidate_id, actor)
        if digest(current.draft) != digest(candidate.draft):
            return
        if executed_manifest is not None and not same_workflow_body(
            candidate.draft, executed_manifest
        ):
            return
        expected = candidate.authoring_task
        active = self.tasks.load(actor, candidate.session_id) if candidate.session_id else None
        task = active or current.authoring_task
        if (
            task is None
            or expected is None
            or not expected.active_trial_token
            or task.active_trial_token != expected.active_trial_token
        ):
            return
        problems = coverage_problems(task, current.draft)
        passed = snapshot.run.status == "succeeded" and not problems
        task = task.model_copy(
            update={
                "last_trial_digest": digest(candidate.draft),
                "verified_digest": digest(candidate.draft) if passed else None,
                "last_status": snapshot.run.status,
                "last_run_id": snapshot.run.run_id,
                "last_failure": snapshot.run.failure.code if snapshot.run.failure else None,
                "last_trial_diagnostics": None
                if passed
                else _trial_diagnostics(snapshot, current.draft, problems),
                "trial_history": _append_trial_history(task, current, snapshot),
                "repair_attempts": 0
                if passed
                else min(
                    3, task.repair_attempts + int(snapshot.run.status in ("failed", "succeeded"))
                ),
                "active_trial_token": None,
            }
        )
        self._save_candidate(current.model_copy(update={"authoring_task": task}))
        if candidate.session_id:
            self.tasks.save(actor, candidate.session_id, task)

    def request(
        self,
        actor: str,
        session_id: str | None,
        kind: ApprovalKind,
        candidate_id: str,
        arguments: dict[str, JsonValue] | None = None,
        *,
        source: str = "conversation",
    ) -> ApprovalRequest:
        if kind == "install_skill":
            return self.request_skill_install(
                actor, candidate_id, source=source, session_id=session_id
            )
        item = self.candidate(candidate_id, actor)
        if kind == "install" and item.status == "installed":
            raise ChatAuthoringError("candidate_already_installed")
        identity = item.draft.metadata.identity
        steps = ", ".join(
            _key(step.capability) for step in item.draft.steps if isinstance(step, WorkflowStep)
        )
        summary = (
            f"Run {_key(identity)} once with {json.dumps(arguments or {}, ensure_ascii=False)}"
            if kind == "run"
            else f"Install {_key(identity)} for reuse"
        ) + f" — steps: {steps}"
        return self._save_approval(
            ApprovalRequest(
                approval_id=f"ap-{datetime.now(UTC):%Y%m%d-%H%M%S}-{secrets.token_hex(3)}",
                actor=actor,
                session_id=session_id,
                kind=kind,
                source=source,
                candidate_id=candidate_id,
                digest=digest(item.draft),
                workflow=_key(identity),
                arguments=arguments or {},
                summary=summary[:600],
                created_at=_now(),
            )
        )

    def request_capability(
        self,
        actor: str,
        session_id: str | None,
        target: AssetIdentity,
        arguments: dict[str, JsonValue],
    ) -> ApprovalRequest:
        """A side effect the conversation model chose itself (owner mode): it
        runs, as the person, only when they approve it."""
        key = _key(target)
        shown = json.dumps(arguments, ensure_ascii=False)
        return self._save_approval(
            ApprovalRequest(
                approval_id=f"ap-{datetime.now(UTC):%Y%m%d-%H%M%S}-{secrets.token_hex(3)}",
                actor=actor,
                session_id=session_id,
                kind="capability",
                candidate_id="capability",
                digest=_call_digest(key, arguments),
                workflow=key,
                arguments=arguments,
                summary=f"Run {key} once with {shown}"[:600],
                created_at=_now(),
            )
        )

    def capability_approval_tool_data(
        self,
        context: RequestContext,
        target: AssetIdentity,
        arguments: dict[str, JsonValue],
    ) -> dict[str, JsonValue]:
        request = self.request_capability(context.actor, context.session_id, target, arguments)
        return {
            "approval_id": request.approval_id,
            "summary": request.summary,
            "next": "Nothing ran yet. Tell the person it waits for their approval button; "
            "after they approve, the result appears in this conversation.",
        }

    def _run_capability(self, item: ApprovalRequest, actor: str) -> ApprovalRequest:
        if _call_digest(item.workflow, item.arguments) != item.digest:
            return self._save_approval(
                item.model_copy(
                    update={
                        "status": "failed",
                        "decided_at": _now(),
                        "result": {"failure": "the request changed after it was made; ask again"},
                    }
                )
            )
        namespace, _, rest = item.workflow.partition("/")
        name, _, version = rest.partition("@")
        target = AssetIdentity(namespace=namespace, name=name, version=version)
        result = asyncio.run(
            self._bridge().execute(
                CapabilityInvocation(
                    context=self._context(actor, self.namespace, item.session_id, "run"),
                    target=target,
                    arguments=item.arguments,
                )
            )
        )
        status: ApprovalStatus = "approved" if result.status == "succeeded" else "failed"
        return self._save_approval(
            item.model_copy(
                update={
                    "status": status,
                    "decided_at": _now(),
                    "result": {
                        "status": result.status,
                        "data": json.loads(json.dumps(result.data, default=str)),
                        "failure": None if result.failure is None else result.failure.code,
                    },
                }
            )
        )

    def decide(self, approval_id: str, actor: str, approve: bool) -> ApprovalRequest:
        """The owner's decision, from a button the model cannot press."""
        item = self.approval(approval_id, actor)
        if item.status != "pending":
            raise ChatAuthoringError("approval_already_decided")
        if not approve:
            return self._save_approval(
                item.model_copy(update={"status": "rejected", "decided_at": _now()})
            )
        if item.kind == "install_skill":
            return self._decide_skill(item, actor)
        if item.kind == "capability":
            return self._run_capability(item, actor)
        candidate = self.candidate(item.candidate_id, actor)
        if digest(candidate.draft) != item.digest:
            return self._save_approval(
                item.model_copy(
                    update={
                        "status": "failed",
                        "decided_at": _now(),
                        "result": {"failure": "the candidate changed after the request; ask again"},
                    }
                )
            )
        try:
            if item.kind == "run":
                result: JsonValue = self.execute(
                    actor, candidate, item.arguments, f"chat-approval:{approval_id}"
                )
            else:
                result = self.install(candidate, actor, approval_id)
        except ChatAuthoringError as error:
            return self._save_approval(
                item.model_copy(
                    update={
                        "status": "failed",
                        "decided_at": _now(),
                        "result": {"failure": error.code},
                    }
                )
            )
        return self._save_approval(
            item.model_copy(update={"status": "approved", "decided_at": _now(), "result": result})
        )

    def install(
        self, candidate: ChatCandidate, actor: str, approval_id: str
    ) -> dict[str, JsonValue]:
        active = self.tasks.load(actor, candidate.session_id) if candidate.session_id else None
        task = active or candidate.authoring_task
        if task is not None:
            problems = coverage_problems(task, candidate.draft)
            if problems:
                raise ChatAuthoringError("authoring_coverage_incomplete", "; ".join(problems))
            if task.verified_digest != digest(candidate.draft):
                raise ChatAuthoringError(
                    "authoring_trial_required",
                    "Run this exact candidate successfully before installing it",
                )
        identity = candidate.draft.metadata.identity
        name = f"{identity.namespace}__{identity.name}__{identity.version}.json"
        target = self.workflows_dir / name
        if target.exists():
            raise ChatAuthoringError("workflow_version_exists")
        metadata = candidate.draft.metadata.model_dump(mode="json")
        metadata.update(
            {
                "lifecycle": "published",
                "business_approval": {
                    "status": "approved",
                    "reviewer": actor,
                    "evidence": f"chat-approval:{approval_id}",
                },
                "validation_refs": [
                    f"chat-candidate:{candidate.candidate_id}:{digest(candidate.draft)}"
                ],
            }
        )
        published = WorkflowManifest.model_validate(
            {**candidate.draft.model_dump(mode="json"), "metadata": metadata}
        )
        self.prepare_workspaces(published)
        self.workflows_dir.mkdir(parents=True, exist_ok=True)
        write_atomically(
            target,
            (
                json.dumps(published.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n"
            ).encode("utf-8"),
        )
        ref = f"chat-approval:{approval_id}"
        self._add_grants(published, actor, ref)
        self._save_candidate(
            candidate.model_copy(
                update={
                    "status": "installed",
                    "installed_as": _key(identity),
                    "installed_digest": digest(candidate.draft),
                }
            )
        )
        live = self.on_installed is not None
        if self.on_installed is not None:
            self.on_installed(published, self.grants(published, actor, ref))
        return {
            "installed_as": _key(identity),
            "file": target.name,
            "digest": digest(candidate.draft),
            "note": "It runs now, in conversations and from the Capabilities page."
            if live
            else "Reuse it from a conversation now; other channels see it after a restart.",
        }

    # -- Skills (external authoring X1) -------------------------------------

    def skill_candidate(self, candidate_id: str, actor: str) -> SkillCandidate:
        path = self._file("skill-candidate", candidate_id)
        if not path.is_file():
            raise ChatAuthoringError("candidate_unknown")
        item = SkillCandidate.model_validate_json(path.read_text(encoding="utf-8"))
        if item.actor != actor:
            raise ChatAuthoringError("candidate_unknown")
        return item

    def _save_skill_candidate(self, item: SkillCandidate) -> SkillCandidate:
        stamped = item.model_copy(update={"updated_at": _now()})
        path = self._file("skill-candidate", stamped.candidate_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        write_atomically(path, stamped.model_dump_json(indent=2).encode("utf-8"))
        return stamped

    def skill_candidates(self, actor: str) -> list[SkillCandidate]:
        found = []
        for path in sorted((self.root / "skill-candidates").glob("*.json")):
            try:
                item = SkillCandidate.model_validate_json(path.read_text(encoding="utf-8"))
            except ValueError:
                continue
            if item.actor == actor:
                found.append(item)
        return sorted(found, key=lambda item: item.updated_at, reverse=True)

    def _skills_dir(self) -> Path:
        if self.skills_dir is None:
            raise ChatAuthoringError("skills_not_configured")
        return self.skills_dir

    def installed_workflows(self) -> list[WorkflowManifest]:
        found = []
        for path in sorted(self.workflows_dir.glob("*.json")):
            try:
                found.append(WorkflowManifest.model_validate_json(path.read_text(encoding="utf-8")))
            except (OSError, ValueError):
                continue
        return found

    # -- revising an installed Workflow (owner 2026-10-19) --------------------

    def installed_workflow(self, reference: str, actor: str) -> WorkflowManifest:
        """The installed Workflow `reference` names that this actor may read:
        an exact version, or the highest installed version of a name."""
        manifest, code, close = resolve(self.installed_workflows(), reference, actor)
        if manifest is None:
            raise ChatAuthoringError(
                code, f"{code}; installed Workflows like it: {', '.join(close)}" if close else ""
            )
        return manifest

    def show_installed(self, actor: str, reference: str, offset: int = 0) -> dict[str, JsonValue]:
        manifest = self.installed_workflow(reference, actor)
        body = view(manifest)
        body.update(
            {
                "origin": "installed",
                "digest": digest(manifest),
                "next": "To change it, call authoring__revise_workflow with this workflow, "
                "then edit the draft; never rewrite it from scratch.",
            }
        )
        return page(body, offset)

    def revision_base(self, item: ChatCandidate) -> WorkflowManifest | None:
        """The installed Workflow a revision candidate copied, while installed."""
        if not item.source.startswith(REVISION_PREFIX):
            return None
        wanted = item.source.removeprefix(REVISION_PREFIX)
        return next(
            (m for m in self.installed_workflows() if _key(m.metadata.identity) == wanted), None
        )

    def revision_changes(self, item: ChatCandidate) -> list[str] | None:
        """What a revision changes against its base; None when it is not a
        revision or its base is no longer installed."""
        base = self.revision_base(item)
        return None if base is None else revision_summary(base, item.draft)

    def _fork_name(self, name: str, actor: str) -> str:
        """A name of the actor's own for a Workflow they may not revise in place."""
        suffix = "-".join(part for part in _SLUG_SPLIT.split(actor.lower()) if part) or "mine"
        for number in range(1, 20):
            candidate = f"{name}-{suffix}" + ("" if number == 1 else f"-{number}")
            owners = {
                (m.metadata.owner.type, m.metadata.owner.id)
                for m in self._published(self.namespace, candidate)
            }
            if owners <= {("user", actor)}:
                return candidate
        raise ChatAuthoringError("workflow_fork_name_unavailable")

    def revise(
        self, actor: str, session_id: str | None, reference: str, title: str = ""
    ) -> tuple[ChatCandidate | None, list[str], dict[str, JsonValue]]:
        """Copy an installed Workflow into a draft one version up (owner
        2026-10-19). Its owner, a co-editor or a member of the owning team keeps
        the name; anyone else gets a fork under a name of their own. The draft
        is the actor's, private and unpublished; installing it is the person's
        press, as for any draft.
        Returns the candidate, or None with the problems; and notes."""
        base = self.installed_workflow(reference, actor)
        base_key = _key(base.metadata.identity)
        for open_item in self.candidates(actor):
            if open_item.source == REVISION_PREFIX + base_key and open_item.status != "installed":
                if open_item.session_id != session_id:
                    open_item = self._save_candidate(
                        open_item.model_copy(update={"session_id": session_id})
                    )
                in_place = open_item.draft.metadata.identity.name == base.metadata.identity.name
                return open_item, [], {"continued": True, "forked": not in_place}
        in_place = may_revise_in_place(base.metadata, actor, self.namespace)
        member = None if in_place else self._team_member(base, actor)
        in_place = in_place or member is not None
        member_team = base.metadata.owner.id if member is not None else None
        name = (
            base.metadata.identity.name
            if in_place
            else self._fork_name(base.metadata.identity.name, actor)
        )
        raw: dict[str, Any] = {
            "name": name,
            "description": base.description,
            "parameters": [p.model_dump(mode="json") for p in base.parameters],
            "steps": [step.model_dump(mode="json") for step in base.steps],
            "checks": [c.model_dump(mode="json") for c in base.checks],
        }
        manifest, problems = self.check(actor, raw, base=base, member_team=member_team)
        if manifest is None:
            return None, problems, {}
        self.prepare_workspaces(manifest)
        now = _now()
        task = self.tasks.load(actor, session_id) if session_id else None
        item = ChatCandidate(
            candidate_id=f"wf-{datetime.now(UTC):%Y%m%d-%H%M%S}-{secrets.token_hex(3)}",
            actor=actor,
            session_id=session_id,
            source=REVISION_PREFIX + base_key,
            title=title.strip()
            or f"{'Revision' if in_place else 'Fork'} of {base.metadata.identity.name}",
            created_at=now,
            updated_at=now,
            draft=manifest,
            base_digest=digest(base),
            member_team=member_team,
            membership_source=member.source if member is not None else None,
            authoring_task=task.model_copy(update={"verified_digest": None}) if task else None,
        )
        if session_id and item.authoring_task is not None:
            self.tasks.save(actor, session_id, item.authoring_task)
        return self._save_candidate(item), [], {"continued": False, "forked": not in_place}

    def _team_member(self, base: WorkflowManifest, actor: str) -> TeamMembership | None:
        """The membership that lets `actor` revise a team-owned Workflow in
        place (owner 2026-10-19), or None. Only the Workflow's own namespace
        can be drafted here; a lookup that fails counts as not a member."""
        owner = base.metadata.owner
        if (
            self.teams is None
            or owner.type != "team"
            or base.metadata.identity.namespace != self.namespace
        ):
            return None
        try:
            membership = self.teams(actor)
        except Exception:  # noqa: BLE001 - unknown membership forks, never fails
            return None
        return membership if membership.includes(owner.id) else None

    def capability_source(
        self, reference: str, file: str | None, offset: int = 0
    ) -> dict[str, JsonValue]:
        """Read-only source of a capability package shipped inside AEP."""
        handlers: list[tuple[str, str, object]] = []
        for spec in self.installed.discover():
            binding = self.installed.get(spec.identity)
            if binding is not None:
                handlers.append((_key(spec.identity), spec.name, binding.handler))
        return capability_source(reference, file, offset, handlers)

    def check_skill(
        self, actor: str, raw: dict[str, Any], previous: SkillCandidate | None = None
    ) -> tuple[SkillManifest | None, list[str]]:
        """The Skill the host would keep, or the problems to fix; saves nothing."""
        assembled = assemble_skill(raw, namespace=self.namespace, owner=actor)
        skills = installed_skills(self._skills_dir())
        identity = assembled["metadata"]["identity"]
        taken = [
            _core(m.metadata.identity.version)
            for m in skills
            if (m.metadata.identity.namespace, m.metadata.identity.name)
            == (identity["namespace"], identity["name"])
        ]
        disabled = self._skills_dir() / "disabled"
        taken.extend(
            _core(m.metadata.identity.version)
            for m in installed_skills(disabled)
            if (m.metadata.identity.namespace, m.metadata.identity.name)
            == (identity["namespace"], identity["name"])
        )
        if previous is not None and previous.draft.metadata.identity.name == identity["name"]:
            taken.append(_core(previous.draft.metadata.identity.version))
        major, minor, patch = max(taken) if taken else (1, 0, -1)
        identity["version"] = f"{major}.{minor}.{patch + 1}"
        return check_skill(
            raw,
            assembled,
            actor=actor,
            installed=self.installed,
            workflows=self.installed_workflows(),
            skills=skills,
        )

    def draft_skill(
        self,
        actor: str,
        title: str,
        raw: dict[str, Any],
        candidate_id: str | None = None,
        *,
        source: str = "conversation",
        session_id: str | None = None,
    ) -> tuple[SkillCandidate | None, list[str]]:
        previous = self.skill_candidate(candidate_id, actor) if candidate_id else None
        manifest, problems = self.check_skill(actor, raw, previous)
        if manifest is None:
            return None, problems
        now = _now()
        item = SkillCandidate(
            candidate_id=previous.candidate_id
            if previous is not None
            else f"sk-{datetime.now(UTC):%Y%m%d-%H%M%S}-{secrets.token_hex(3)}",
            actor=actor,
            session_id=session_id
            if session_id is not None
            else (previous.session_id if previous is not None else None),
            source=source,
            title=title.strip() or manifest.alias,
            created_at=previous.created_at if previous is not None else now,
            updated_at=now,
            revision=previous.revision + 1 if previous is not None else 1,
            draft=manifest,
        )
        return self._save_skill_candidate(item), []

    def request_skill_install(
        self,
        actor: str,
        candidate_id: str,
        *,
        source: str = "conversation",
        session_id: str | None = None,
    ) -> ApprovalRequest:
        item = self.skill_candidate(candidate_id, actor)
        if item.status == "installed":
            raise ChatAuthoringError("candidate_already_installed")
        identity = item.draft.metadata.identity
        commands = ", ".join(f"{c.name}→{_key(c.target)}" for c in item.draft.commands) or "none"
        summary = (
            f"Install Skill {_key(identity)} (alias {item.draft.alias}) — commands: "
            f"{commands}; used after the host restarts"
        )
        return self._save_approval(
            ApprovalRequest(
                approval_id=f"ap-{datetime.now(UTC):%Y%m%d-%H%M%S}-{secrets.token_hex(3)}",
                actor=actor,
                session_id=session_id,
                kind="install_skill",
                source=source,
                candidate_id=candidate_id,
                digest=skill_digest(item.draft),
                workflow=_key(identity),
                summary=summary[:600],
                created_at=_now(),
            )
        )

    def _decide_skill(self, item: ApprovalRequest, actor: str) -> ApprovalRequest:
        candidate = self.skill_candidate(item.candidate_id, actor)
        if skill_digest(candidate.draft) != item.digest:
            return self._save_approval(
                item.model_copy(
                    update={
                        "status": "failed",
                        "decided_at": _now(),
                        "result": {"failure": "the candidate changed after the request; ask again"},
                    }
                )
            )
        try:
            result = self.install_skill(candidate, actor, item.approval_id)
        except ChatAuthoringError as error:
            return self._save_approval(
                item.model_copy(
                    update={
                        "status": "failed",
                        "decided_at": _now(),
                        "result": {"failure": error.code},
                    }
                )
            )
        return self._save_approval(
            item.model_copy(update={"status": "approved", "decided_at": _now(), "result": result})
        )

    def install_skill(
        self, candidate: SkillCandidate, actor: str, approval_id: str
    ) -> dict[str, JsonValue]:
        """Write the Skill published, and set the actor's earlier versions of
        the name aside: one installed version per name."""
        folder = self._skills_dir()
        identity = candidate.draft.metadata.identity
        target = folder / f"{identity.namespace}__{identity.name}__{identity.version}.json"
        if target.exists():
            raise ChatAuthoringError("skill_version_exists")
        # Checked again at install: something may have been installed since.
        others = [
            m
            for m in installed_skills(folder)
            if (m.metadata.identity.namespace, m.metadata.identity.name)
            != (identity.namespace, identity.name)
            or (m.metadata.owner.type, m.metadata.owner.id) != ("user", actor)
        ]
        _, problems = check_skill(
            {"instructions": candidate.draft.instructions},
            candidate.draft.model_dump(mode="json"),
            actor=actor,
            installed=self.installed,
            workflows=self.installed_workflows(),
            skills=others,
        )
        if problems:
            raise ChatAuthoringError("skill_no_longer_valid")
        metadata = candidate.draft.metadata.model_dump(mode="json")
        metadata.update(
            {
                "lifecycle": "published",
                "business_approval": {
                    "status": "approved",
                    "reviewer": actor,
                    "evidence": f"chat-approval:{approval_id}",
                },
                "validation_refs": [
                    f"skill-candidate:{candidate.candidate_id}:{skill_digest(candidate.draft)}"
                ],
            }
        )
        published = SkillManifest.model_validate(
            {**candidate.draft.model_dump(mode="json"), "metadata": metadata}
        )
        set_aside: list[str] = []
        for path in sorted(folder.glob(f"{identity.namespace}__{identity.name}__*.json")):
            (folder / "disabled").mkdir(parents=True, exist_ok=True)
            path.replace(folder / "disabled" / path.name)
            set_aside.append(path.name)
        folder.mkdir(parents=True, exist_ok=True)
        write_atomically(
            target,
            (
                json.dumps(published.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n"
            ).encode("utf-8"),
        )
        self._save_skill_candidate(
            candidate.model_copy(
                update={
                    "status": "installed",
                    "installed_as": _key(identity),
                    "installed_digest": skill_digest(candidate.draft),
                }
            )
        )
        return {
            "installed_as": _key(identity),
            "file": target.name,
            "digest": skill_digest(candidate.draft),
            "set_aside": list(set_aside),
            "note": "The host uses it after a restart.",
        }

    # -- the owner's draft list in Agent Web (owner 2026-10-08) -------------

    def install_now(self, actor: str, candidate_id: str) -> ApprovalRequest:
        """The owner pressed Install on a draft: that press is the approval."""
        skill = candidate_id.startswith("sk-")
        source = (
            self.skill_candidate(candidate_id, actor)
            if skill
            else self.candidate(candidate_id, actor)
        ).source
        request = self.request(
            actor, None, "install_skill" if skill else "install", candidate_id, source=source
        )
        return self.decide(request.approval_id, actor, True)

    def delete_candidate(self, actor: str, candidate_id: str) -> None:
        """Forget a draft. An installed version stays installed; requests still
        waiting for it are closed as rejected."""
        if candidate_id.startswith("sk-"):
            self.skill_candidate(candidate_id, actor)
            path = self._file("skill-candidate", candidate_id)
        else:
            self.candidate(candidate_id, actor)
            path = self._file("candidate", candidate_id)
        for item in self.approvals(actor):
            if item.candidate_id == candidate_id:
                self._save_approval(
                    item.model_copy(update={"status": "rejected", "decided_at": _now()})
                )
        path.unlink(missing_ok=True)

    # -- what an external agent may see -------------------------------------

    def external_view(self, item: ApprovalRequest) -> dict[str, JsonValue]:
        """An approval's outcome without data: statuses and codes only, so
        nothing a run read reaches an external agent (PUBLIC rule)."""
        view: dict[str, JsonValue] = {
            "approval_id": item.approval_id,
            "kind": item.kind,
            "status": item.status,
            "workflow": item.workflow,
            "candidate_id": item.candidate_id,
            "decided_at": item.decided_at,
        }
        result = item.result if isinstance(item.result, dict) else {}
        if item.status == "failed":
            failure = result.get("failure")
            view["failure"] = (
                failure if isinstance(failure, str) and " " not in failure else "failed"
            )
        elif item.status == "approved" and item.kind != "run":
            view.update({k: result.get(k) for k in ("installed_as", "digest", "note")})
        elif item.status == "approved":
            view["run"] = run_codes(result)
        return view

    # -- grants ------------------------------------------------------------

    def grants(
        self, manifest: WorkflowManifest, actor: str, ref: str
    ) -> tuple[CapabilityGrant, ...]:
        found: dict[str, CapabilityGrant] = {}
        for step in manifest.steps:
            if not isinstance(step, WorkflowStep):
                raise ChatAuthoringError("nested_workflow")
            binding = self.installed.get(step.capability)
            if binding is None:
                raise ChatAuthoringError("capability_missing")
            found[_key(step.capability)] = CapabilityGrant(
                actor=actor,
                asset=binding.spec.identity,
                permissions=binding.spec.policy.required_permissions,
                policy_refs=binding.spec.policy.policy_refs,
                approval_ref=ref,
            )
        return tuple(found.values())

    def _add_grants(self, manifest: WorkflowManifest, actor: str, ref: str) -> None:
        existing = (
            [CapabilityGrant.model_validate(item) for item in documents(self.grants_file)]
            if self.grants_file.is_file()
            else []
        )
        have = {(grant.actor, grant.asset.key) for grant in existing}
        added = [
            grant
            for grant in self.grants(manifest, actor, ref)
            if (grant.actor, grant.asset.key) not in have
        ]
        if added:
            payload = [grant.model_dump(mode="json") for grant in (*existing, *added)]
            write_atomically(
                self.grants_file,
                (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
            )

    # -- conversation tools ------------------------------------------------

    def tools(self) -> Sequence[HostTool]:
        async def run_sync(fn: Callable[[], HostToolOutcome]) -> HostToolOutcome:
            return await asyncio.to_thread(fn)

        Args = dict[str, JsonValue]

        async def question_tool(context: RequestContext, args: Args) -> HostToolOutcome:
            if context.session_id is None:
                return _refused("authoring_session_required", "A question belongs to this task")
            task = self.tasks.load(context.actor, context.session_id)
            if task is None:
                return _refused("authoring_plan_required", "Preserve the task first")
            try:
                question = AuthoringQuestion.model_validate(args)
            except ValueError:
                return _refused(
                    "authoring_question_invalid", "Use a typed business/resource question"
                )
            if question.reason == "repair_limit" and task.repair_attempts < 3:
                return _refused("authoring_repair_remaining", "Use the remaining bounded repairs")
            if question.reason == "missing_resource":
                if question.input_name is None:
                    return _refused(
                        "authoring_resource_name_required",
                        "Name the missing input; inspect supplied attachments before asking",
                    )
                notes = (
                    *self.session_messages(context.actor, context.session_id),
                    *self.tasks.messages(context.actor, context.session_id),
                )
                paths = {
                    str(attachment.get("path", ""))
                    for note in notes
                    if note.role == "user"
                    for attachment in note.attachments
                }
                paths.update(
                    value
                    for note in notes
                    if note.role == "user"
                    for value in re.findall(r"""["'`]([^"'`\r\n]+)["'`]""", note.text)
                    if Path(value).is_absolute()
                )
                existing = [path for path in paths if Path(path).is_file()]
                name = question.resource_name
                if existing and (
                    name is None
                    or any(
                        Path(path).name.casefold() == Path(name).name.casefold()
                        for path in existing
                    )
                ):
                    return _refused(
                        "authoring_resources_already_supplied",
                        "Use the supplied file references. If a different resource is missing, "
                        "specify its exact resource_name and input_name",
                    )
            if re.search(r"\b(?:css|xpath|selector|dom)\b", question.question, re.IGNORECASE) or (
                question.reason != "authentication_required"
                and re.search(r"手動.{0,20}(?:畫面|頁面|瀏覽器)", question.question)
            ):
                return _refused(
                    "authoring_technical_question",
                    "Use browser__inspect and repair; do not ask the person for "
                    "technical navigation",
                )
            if question.input_name and question.input_name in task.supplied_inputs:
                value = task.supplied_inputs[question.input_name].get("value")
                missing_file = (
                    question.reason == "missing_resource"
                    and isinstance(value, str)
                    and not Path(value).is_file()
                )
                if not missing_file:
                    return _refused(
                        "authoring_input_already_supplied", "Use the saved input and its origin"
                    )
            self.tasks.save(
                context.actor, context.session_id, task.model_copy(update={"question": question})
            )
            return HostToolOutcome(
                status="succeeded",
                data={"status": "needs_input", **question.model_dump(mode="json")},
            )

        async def get_plan_tool(context: RequestContext, args: Args) -> HostToolOutcome:
            task = (
                self.tasks.load(context.actor, context.session_id) if context.session_id else None
            )
            return HostToolOutcome(
                status="succeeded",
                data=task.model_dump(mode="json")
                if task is not None
                else {"status": "not_planned"},
            )

        async def plan_tool(context: RequestContext, args: Args) -> HostToolOutcome:
            if context.session_id is None:
                return _refused("authoring_session_required", "Plan belongs to a conversation")
            try:
                raw = args.get("requirements")
                if not isinstance(raw, list) or not raw:
                    return _refused(
                        "authoring_requirements_missing", "List the SOP requirements first"
                    )
                requirements = list(AuthoringPlanRequest.model_validate(args).requirements)
                task = self.tasks.plan(
                    context.actor, context.session_id, context.message[:40000], requirements
                )
                return HostToolOutcome(status="succeeded", data=task.model_dump(mode="json"))
            except ValueError as error:
                return _refused("authoring_plan_invalid", str(error)[:500])

        async def draft_tool(context: RequestContext, args: Args) -> HostToolOutcome:
            def work() -> HostToolOutcome:
                self.repair_scope(context, str(args.get("candidate_id") or ""))
                if (
                    self.needs_plan(context)
                    and context.session_id
                    and self.tasks.load(context.actor, context.session_id) is None
                ):
                    return _refused(
                        "authoring_plan_required",
                        "Use authoring__plan_workflow to preserve every SOP requirement "
                        "before drafting",
                    )
                raw = args.get("workflow")
                if not isinstance(raw, dict):
                    return _refused("workflow_missing", "give the Workflow as an object")
                candidate_id = args.get("candidate_id")
                item, problems = self.draft(
                    context.actor,
                    context.session_id,
                    str(args.get("title") or ""),
                    raw,
                    str(candidate_id) if candidate_id else None,
                )
                if item is None:
                    return HostToolOutcome(
                        status="failed",
                        data={"problems": problems},
                        failure=Failure(code="workflow_invalid", message="; ".join(problems)[:500]),
                    )
                return HostToolOutcome(
                    status="succeeded",
                    data={
                        "candidate_id": item.candidate_id,
                        "workflow": _key(item.draft.metadata.identity),
                        "revision": item.revision,
                        "digest": digest(item.draft),
                        "read_only": self.read_only(item.draft),
                        **self.readiness(item),
                        "next": "preview it, then run it; a run that writes waits for the owner's "
                        "approval",
                    },
                )

            return await run_sync(work)

        async def preview_tool(context: RequestContext, args: Args) -> HostToolOutcome:
            def work() -> HostToolOutcome:
                return HostToolOutcome(
                    status="succeeded",
                    data=self.preview(
                        context.actor, str(args.get("candidate_id") or ""), _arguments(args)
                    ),
                )

            return await run_sync(work)

        async def run_tool(context: RequestContext, args: Args) -> HostToolOutcome:
            def work() -> HostToolOutcome:
                self.repair_scope(context, str(args.get("candidate_id") or ""))
                item = self.candidate(str(args.get("candidate_id") or ""), context.actor)
                arguments = _arguments(args)
                active = (
                    self.tasks.load(context.actor, context.session_id)
                    if context.session_id
                    else None
                )
                task = active or item.authoring_task
                if (
                    task is not None
                    and task.repair_attempts >= 3
                    and "Host authoring continuation" in context.message
                ):
                    return _refused(
                        "authoring_repair_limit", "Three unfinished trials; stop for the owner"
                    )
                repair = context.message.startswith("[Host authoring continuation:")
                if (
                    repair
                    and task is not None
                    and task.last_status == "succeeded"
                    and task.last_trial_digest == digest(item.draft)
                ):
                    return _refused(
                        "authoring_revision_required",
                        "This partial procedure already ran successfully. Preserve its result "
                        "and revise the candidate to complete missing requirements; do not "
                        "repeat the successful execution during continuation",
                    )
                if (
                    item.status == "installed"
                    and item.installed_digest == digest(item.draft)
                    and not (repair and not self.read_only(item.draft))
                ):
                    offer = self._form_instead(context, item.draft, arguments)
                    if offer is not None:
                        return HostToolOutcome(status="succeeded", data={OFFER_KEY: offer})
                    # The installed version, unchanged: installing was the approval.
                    return _trial_outcome(
                        self.execute(
                            context.actor, item, arguments, f"chat-installed:{item.candidate_id}"
                        )
                    )
                if self.read_only(item.draft):
                    return _trial_outcome(
                        self.execute(
                            context.actor, item, arguments, f"chat-read-only:{item.candidate_id}"
                        )
                    )
                request = self.request(
                    context.actor, context.session_id, "run", item.candidate_id, arguments
                )
                return HostToolOutcome(
                    status="awaiting_approval",
                    data={
                        "approval_id": request.approval_id,
                        "candidate_id": item.candidate_id,
                        "digest": digest(item.draft),
                        "summary": request.summary,
                        "next": "Nothing ran yet. Tell the person it waits for their approval "
                        "button; after they approve, the result appears in this conversation.",
                    },
                )

            return await run_sync(work)

        async def install_tool(context: RequestContext, args: Args) -> HostToolOutcome:
            def work() -> HostToolOutcome:
                request = self.request(
                    context.actor,
                    context.session_id,
                    "install",
                    str(args.get("candidate_id") or ""),
                )
                return HostToolOutcome(
                    status="awaiting_approval",
                    data={
                        "approval_id": request.approval_id,
                        "summary": request.summary,
                        "next": (
                            "Nothing is installed yet; it waits for the person's approval button."
                        ),
                    },
                )

            return await run_sync(work)

        async def get_tool(context: RequestContext, args: Args) -> HostToolOutcome:
            def work() -> HostToolOutcome:
                self.repair_scope(context, str(args.get("candidate_id") or ""))
                reference = str(args.get("workflow") or "").strip()
                candidate_id = str(args.get("candidate_id") or "").strip()
                if reference and not candidate_id:
                    return HostToolOutcome(
                        status="succeeded",
                        data=self.show_installed(context.actor, reference, _offset(args)),
                    )
                if not candidate_id:
                    return _refused(
                        "workflow_missing",
                        "give `workflow` (an installed Workflow) or `candidate_id` (a draft)",
                    )
                item = self.candidate(candidate_id, context.actor)
                body: dict[str, JsonValue] = {
                    "candidate_id": item.candidate_id,
                    "workflow": _key(item.draft.metadata.identity),
                    "status": item.status,
                    "digest": digest(item.draft),
                    "parameters": [p.model_dump(mode="json") for p in item.draft.parameters],
                    "steps": [step.model_dump(mode="json") for step in item.draft.steps],
                    **self.readiness(item),
                }
                if item.draft.checks:
                    body["checks"] = [c.model_dump(mode="json") for c in item.draft.checks]
                if item.source.startswith(REVISION_PREFIX):
                    body["revision_of"] = item.source.removeprefix(REVISION_PREFIX)
                return HostToolOutcome(status="succeeded", data=page(body, _offset(args)))

            return await run_sync(work)

        async def revise_tool(context: RequestContext, args: Args) -> HostToolOutcome:
            def work() -> HostToolOutcome:
                if (
                    self.needs_plan(context)
                    and context.session_id
                    and self.tasks.load(context.actor, context.session_id) is None
                ):
                    return _refused(
                        "authoring_plan_required", "Preserve the SOP requirements before revising"
                    )
                reference = str(args.get("workflow") or "").strip()
                if not reference:
                    return _refused("workflow_missing", "name the installed Workflow to revise")
                item, problems, notes = self.revise(
                    context.actor, context.session_id, reference, str(args.get("title") or "")
                )
                if item is None:
                    return HostToolOutcome(
                        status="failed",
                        data={"problems": problems},
                        failure=Failure(code="workflow_invalid", message="; ".join(problems)[:500]),
                    )
                base = item.source.removeprefix(REVISION_PREFIX)
                forked = bool(notes.get("forked"))
                data: dict[str, JsonValue] = {
                    "candidate_id": item.candidate_id,
                    "workflow": _key(item.draft.metadata.identity),
                    "revision_of": base,
                    "base_digest": item.base_digest,
                    "forked": forked,
                    "continued": bool(notes.get("continued")),
                    "next": "Read the draft with authoring__get_workflow (candidate_id), change "
                    "only what was asked, and save it with authoring__draft_workflow passing "
                    "this candidate_id and the whole Workflow. The person installs it with the "
                    "card's Install button; never say it is installed before that.",
                }
                if item.member_team:
                    data["member_of_team"] = item.member_team
                    data["membership_source"] = item.membership_source
                    data["note_membership"] = membership_note(
                        item.member_team, item.membership_source
                    ) + (
                        "; tell the person, and that publishing it to the shared platform "
                        "is still checked there."
                    )
                if forked:
                    data["note"] = (
                        f"{base} is not this person's to revise, so this is a fork under the "
                        f"new name {item.draft.metadata.identity.name}, owned by them; tell "
                        "them so."
                    )
                if notes.get("continued"):
                    data["note_continued"] = (
                        "An open revision draft of this Workflow already existed; this "
                        "continues it."
                    )
                return HostToolOutcome(status="succeeded", data=data)

            return await run_sync(work)

        async def source_tool(context: RequestContext, args: Args) -> HostToolOutcome:
            def work() -> HostToolOutcome:
                file = args.get("file")
                data = self.capability_source(
                    str(args.get("capability") or ""),
                    str(file) if isinstance(file, str) and file else None,
                    _offset(args),
                )
                if data.get("ok") is False:
                    return HostToolOutcome(
                        status="failed",
                        data=data,
                        failure=Failure(code=str(data.get("code")), message=str(data.get("code"))),
                    )
                return HostToolOutcome(status="succeeded", data=data)

            return await run_sync(work)

        async def list_tool(context: RequestContext, args: Args) -> HostToolOutcome:
            def work() -> HostToolOutcome:
                return HostToolOutcome(
                    status="succeeded",
                    data=[
                        {
                            "candidate_id": item.candidate_id,
                            "title": item.title,
                            "workflow": _key(item.draft.metadata.identity),
                            "status": item.status,
                            "digest": digest(item.draft),
                            "description": item.draft.description,
                            "parameters": [p.name for p in item.draft.parameters],
                        }
                        for item in self.candidates(context.actor)[:30]
                    ],
                )

            return await run_sync(work)

        def guarded(handler: Any) -> Any:
            async def call(context: RequestContext, args: dict[str, JsonValue]) -> HostToolOutcome:
                try:
                    outcome: HostToolOutcome = await handler(context, args)
                    return outcome
                except ChatAuthoringError as error:
                    return _refused(error.code, error.detail or error.code)

            return call

        candidate = {"candidate_id": {"type": "string"}}
        values = {"arguments": {"type": "object", "description": "run values by parameter name"}}
        return (
            HostTool(
                ModelTool(
                    name="authoring__needs_input",
                    description=(
                        "Record a genuinely missing business decision/resource or authentication "
                        "step before asking. Supply input_name when asking for a parameter; "
                        "missing_resource requires input_name and the exact resource_name "
                        "when other files were already provided. "
                        "already supplied inputs must be reused. Never request CSS/selectors "
                        "or manual navigation. Do not use this to reduce the task scope."
                    ),
                    input_contract="host.authoring.question.v1",
                    input_schema=AuthoringQuestion.model_json_schema(),
                ),
                guarded(question_tool),
                "write",
            ),
            HostTool(
                ModelTool(
                    name="authoring__get_plan",
                    description=(
                        "Read this session's saved requirements, input origins and trial state. "
                        "Do not call plan again merely to read."
                    ),
                    input_contract="host.authoring.plan-read.v1",
                    input_schema={
                        "type": "object",
                        "properties": {},
                        "additionalProperties": False,
                    },
                ),
                guarded(get_plan_tool),
                "read",
            ),
            HostTool(
                ModelTool(
                    name="authoring__plan_workflow",
                    description=(
                        "Preserve this conversation's complete SOP requirements before "
                        "exploring/drafting. "
                        "Each requirement has requirement_id, description, check_ids "
                        "naming the future Workflow output checks, "
                        "and assertions over the eventual manifest: "
                        "{path:[...],operator:present|equals|contains|min_count,expected:J"
                        "SON}. "
                        "Use * in paths to visit all steps/actions. Plan unbound "
                        "requirements first, then add assertions after discovery. "
                        "Example full-table proof path "
                        "['steps','*','inputs','actions','value','*','pagination'] "
                        "operator present; "
                        "date filters require fill actions, artifacts need fresh file "
                        "checks. Preserve every requirement ID/description and existing check "
                        "ID. Correct or relocate procedure assertions after discovery without "
                        "clearing existing coverage; changes require a fresh current trial. "
                        "Retrieve persistent plan from session context, and add coverage "
                        "instead of asking the user for selectors."
                    ),
                    input_contract="host.authoring.plan.v1",
                    input_schema=AuthoringPlanRequest.model_json_schema(),
                ),
                guarded(plan_tool),
                "write",
            ),
            HostTool(
                ModelTool(
                    name="authoring__draft_workflow",
                    description=" ".join(
                        part
                        for part in (DRAFT_GUIDE, workspace_note(self.coding_workspace_roots))
                        if part
                    ),
                    input_contract="host.authoring.draft.v1",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "workflow": {"type": "object"},
                            "candidate_id": {"type": "string"},
                        },
                        "required": ["title", "workflow"],
                    },
                ),
                guarded(draft_tool),
            ),
            HostTool(
                ModelTool(
                    name="authoring__preview_workflow",
                    description=(
                        "Preview a drafted Workflow: read steps run for real, other steps show "
                        "what they would do; nothing changes."
                    ),
                    input_contract="host.authoring.preview.v1",
                    input_schema={
                        "type": "object",
                        "properties": {**candidate, **values},
                        "required": ["candidate_id"],
                    },
                ),
                guarded(preview_tool),
            ),
            HostTool(
                ModelTool(
                    name="authoring__run_workflow",
                    description=(
                        "Run a drafted or installed Workflow once with run values. A Workflow "
                        "whose steps only read runs now and returns its result; otherwise it "
                        "waits for the person's approval button and nothing runs yet. If a "
                        "platform run failed, fix the cause (revise the candidate when its "
                        "steps were wrong) and run it again here; do not redo the work "
                        "outside the Workflow."
                    ),
                    input_contract="host.authoring.run.v1",
                    input_schema={
                        "type": "object",
                        "properties": {**candidate, **values},
                        "required": ["candidate_id"],
                    },
                ),
                guarded(run_tool),
            ),
            HostTool(
                ModelTool(
                    name="authoring__install_workflow",
                    description=(
                        "Ask the person to install a drafted Workflow for reuse; it waits for "
                        "their approval button."
                    ),
                    input_contract="host.authoring.install.v1",
                    input_schema={
                        "type": "object",
                        "properties": candidate,
                        "required": ["candidate_id"],
                    },
                ),
                guarded(install_tool),
            ),
            HostTool(
                ModelTool(
                    name="authoring__get_workflow",
                    description=(
                        "Show a Workflow in full: parameters, and steps with every input "
                        "(including an embedded run-python script). Pass `workflow` for an "
                        "installed one (namespace/name@version, or a name for its highest "
                        "installed version), whether it came from the bundle, the Marketplace, "
                        "the Shared Platform or a conversation; pass `candidate_id` for a "
                        "draft. A long Workflow comes in slices: read the rest with `offset`."
                    ),
                    input_contract="host.authoring.get.v1",
                    input_schema={
                        "type": "object",
                        "properties": {
                            **candidate,
                            "workflow": {"type": "string"},
                            "offset": {"type": "integer", "minimum": 0},
                        },
                    },
                ),
                guarded(get_tool),
            ),
            HostTool(
                ModelTool(
                    name="authoring__revise_workflow",
                    description=(
                        "Change an installed Workflow by building on its real steps instead of "
                        "rewriting it: copies it into a draft one version up (1.0.0 -> 1.0.1, "
                        "same name) that you then edit with authoring__draft_workflow and its "
                        "candidate_id. When the Workflow is neither the person's nor their "
                        "team's, the draft is a fork under a new name of theirs. Nothing is "
                        "installed: the person "
                        "presses Install on the card."
                    ),
                    input_contract="host.authoring.revise.v1",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "workflow": {
                                "type": "string",
                                "description": "namespace/name@version or name",
                            },
                            "title": {"type": "string"},
                        },
                        "required": ["workflow"],
                    },
                ),
                guarded(revise_tool),
            ),
            HostTool(
                ModelTool(
                    name="authoring__show_capability_source",
                    description=(
                        "Read, never edit, the Python source of a capability that ships inside "
                        "AEP (a package such as weekly_report, or an installed capability "
                        "target), to base a revision on the original logic. Without `file` it "
                        "lists the package's files; long files come in slices (`offset`). To "
                        "change the behaviour, revise the Workflow that uses it (a parameter, "
                        "or a coding/run-python step with the adjusted logic)."
                    ),
                    input_contract="host.authoring.capability_source.v1",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "capability": {"type": "string"},
                            "file": {"type": "string"},
                            "offset": {"type": "integer", "minimum": 0},
                        },
                        "required": ["capability"],
                    },
                ),
                guarded(source_tool),
            ),
            HostTool(
                ModelTool(
                    name="authoring__list_workflows",
                    description="List the Workflows this person drafted or installed from "
                    "conversations, to reuse one with new run values.",
                    input_contract="host.authoring.list.v1",
                    input_schema={"type": "object", "properties": {}},
                ),
                guarded(list_tool),
            ),
        )


_SLUG_SPLIT = re.compile(r"[^a-z0-9]+")
#: What the draft format has no field for, kept from the Workflow a draft continues.
_CARRIED = ("progress_steps", "occupies_machine", "secrets")


def _carry_over(
    assembled: dict[str, Any], base: WorkflowManifest, actor: str, member_team: str | None = None
) -> None:
    """Keep what `assemble` cannot express from the Workflow a draft continues:
    progress stages, the machine flag, secret names, central execution and
    discovery categories. A co-editor's next version keeps the name's owner."""
    data = base.model_dump(mode="json")
    for name in _CARRIED:
        if name in data:
            assembled[name] = data[name]
    if base.execution.mode != "local":
        assembled["execution"] = data["execution"]
        assembled["dependencies"]["central_services"] = data["dependencies"]["central_services"]
        assembled["dependencies"]["central_required"] = data["dependencies"]["central_required"]
    metadata = assembled["metadata"]
    if base.metadata.categories:
        metadata["categories"] = list(base.metadata.categories)
    identity = base.metadata.identity
    same_name = (identity.namespace, identity.name) == (
        metadata["identity"]["namespace"],
        metadata["identity"]["name"],
    )
    owner = base.metadata.owner
    co_editor = actor in base.metadata.contributors and (owner.type, owner.id) != ("user", actor)
    # A team member's revision keeps the team as owner (owner 2026-10-19).
    team_member = member_team is not None and (owner.type, owner.id) == ("team", member_team)
    if same_name and (co_editor or team_member):
        metadata["owner"] = owner.model_dump(mode="json")
        metadata["contributors"] = list(base.metadata.contributors)


def _offset(args: dict[str, JsonValue]) -> int:
    value = args.get("offset")
    return value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else 0


def _arguments(args: dict[str, JsonValue]) -> dict[str, JsonValue]:
    value = args.get("arguments")
    return dict(value) if isinstance(value, dict) else {}


def _refused(code: str, message: str) -> HostToolOutcome:
    return HostToolOutcome(status="failed", failure=Failure(code=code, message=message))


def run_codes(result: JsonValue) -> dict[str, JsonValue]:
    """A run summary reduced to statuses and failure codes."""
    body = result if isinstance(result, dict) else {}
    failure = body.get("failure")
    steps = body.get("steps")
    return {
        "status": body.get("status"),
        "failure": failure.get("code") if isinstance(failure, dict) else None,
        "steps": [
            {
                "index": step.get("index"),
                "status": step.get("status"),
                "failure": str(step.get("failure")).split(":", 1)[0]
                if step.get("failure")
                else None,
            }
            for step in (steps if isinstance(steps, list) else [])
            if isinstance(step, dict)
        ],
    }


def approval_text(item: ApprovalRequest) -> str:
    """What the conversation shows, and the Agent reads, after a decision."""
    if item.status == "rejected":
        return f"【已拒絕】{item.summary}。沒有執行任何動作。"
    result = item.result if isinstance(item.result, dict) else {}
    if item.status == "failed":
        return f"【未執行】{item.summary}。原因：{result.get('failure')}"
    if item.kind == "capability":
        detail = json.dumps(result.get("data"), ensure_ascii=False)
        return f"【已核准並執行】{item.workflow} 結果：{result.get('status')}\n{detail[:2000]}"
    if item.kind == "install_skill":
        return (
            f"【已核准安裝 Skill】{result.get('installed_as')}"
            f"（digest {result.get('digest')}）。主機重新啟動後生效。"
        )
    if item.kind == "install":
        return (
            f"【已核准安裝】{result.get('installed_as')}（digest {result.get('digest')}）。"
            "之後可以在對話中用新的參數重跑它。"
        )
    lines = [
        f"【已核准並執行】{item.workflow}（候選 {item.candidate_id}，digest "
        f"{result.get('digest')}）結果：{result.get('status')}"
    ]
    failure = result.get("failure")
    if failure:
        lines.append(f"失敗：{json.dumps(failure, ensure_ascii=False)}")
    steps = result.get("steps")
    for step in steps if isinstance(steps, list) else []:
        if not isinstance(step, dict):
            continue
        data = step.get("data")
        detail = json.dumps(data, ensure_ascii=False)
        lines.append(
            f"步驟 {step.get('index')}：{step.get('status')}"
            + (f"（{step.get('failure')}）" if step.get("failure") else "")
            + f"\n{detail[:2500]}"
        )
    return "\n".join(lines)


#: A step's union branch that a model's step never means (nested Workflows are
#: refused anyway), and the validator wrapper pydantic names the step branch by.
_NESTED_BRANCH = "AssetIdentity"
_STEP_BRANCH = re.compile(r"^function-after\[.*WorkflowStep\]$")


_INPUT_FORM = (
    ' (each input is {"source": "fixed", "value": JSON}, {"source": "run", "path": '
    '["<parameter>"]} or {"source": "step", "step_index": N, "path": [...]})'
)


def _unnamed_capabilities(raw: dict[str, Any]) -> list[str]:
    """Steps whose capability is not `namespace/name@version` (#233): said
    plainly, instead of the union errors pydantic gives for a missing one."""
    problems = []
    steps = [step for step in raw.get("steps") or [] if isinstance(step, dict)]
    for index, step in enumerate(steps):
        value = step.get("capability")
        if isinstance(value, dict) or re.fullmatch(
            r"[a-z0-9-]+/[a-z0-9-]+@[0-9][0-9A-Za-z.+-]*", str(value or "")
        ):
            continue
        shown = str(value or "")[:80]
        problems.append(
            f"steps.{index}.capability: '{shown}' is not namespace/name@version of an installed "
            "capability (for example coding/run-python@1.0.0; not a tool name like coding__run)"
        )
    return problems[:8]


def _step_problems(error: ValidationError) -> list[str]:
    """The draft's validation errors a model can act on (#233): a step is
    validated as either a nested Workflow or a step, so every wrong step also
    reports 'namespace/name/version: Field required' for the nested branch.
    Those are dropped and the step branch's long name is left out, so the real
    problem comes first. The rule itself is unchanged."""
    shown: list[str] = []
    for item in error.errors():
        loc = [str(part) for part in item["loc"]]
        if len(loc) > 2 and loc[0] == "steps" and loc[2] == _NESTED_BRANCH:
            continue
        loc = [part for part in loc if not _STEP_BRANCH.match(part)]
        problem = f"{'.'.join(loc)}: {item['msg']}"
        if loc[:1] == ["steps"] and "inputs" in loc and len(loc) <= 5 and not shown:
            problem += _INPUT_FORM
        shown.append(problem)
    if not shown:  # only the nested branch failed: say it as it is
        shown = [f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in error.errors()]
    return shown[:8]


def _trial_outcome(result: dict[str, JsonValue]) -> HostToolOutcome:
    if result.get("status") == "succeeded":
        return HostToolOutcome(status="succeeded", data=result)
    raw = result.get("failure")
    code = raw.get("code") if isinstance(raw, dict) else "workflow_trial_failed"
    return HostToolOutcome(
        status="failed",
        data=result,
        failure=Failure(
            code=str(code or "workflow_trial_failed"),
            message="The actual Workflow trial failed; diagnose and revise the candidate",
        ),
    )


def same_workflow_body(candidate: WorkflowManifest, executed: WorkflowManifest) -> bool:
    """Publication adds approval metadata, never changes the executable draft."""

    def comparable(manifest: WorkflowManifest) -> dict[str, Any]:
        value = manifest.model_dump(mode="json")
        for key in ("lifecycle", "business_approval", "validation_refs"):
            value["metadata"].pop(key, None)
        return value

    return comparable(candidate) == comparable(executed)
