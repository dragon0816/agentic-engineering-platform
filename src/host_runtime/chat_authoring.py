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
import secrets
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, JsonValue, ValidationError

from agent.gateway import HostTool, HostToolOutcome
from agent.skills import SkillManifest
from capabilities.coding_change.workspaces import containing_root, workspace_note
from capabilities.runtime import CapabilityGrant, InstalledCapabilities, LocalPolicy
from capabilities.workflow_author.conversation import assemble
from common.assets import AssetIdentity, FixedInput, WorkflowManifest, WorkflowStep
from common.base import Contract, Symbol, Text
from common.execution import Failure, RequestContext, TraceIdentifiers
from host_runtime.skill_authoring import (
    SkillCandidate,
    assemble_skill,
    check_skill,
    installed_skills,
    skill_digest,
)
from host_runtime.workspace import documents, write_atomically
from models.contracts import ModelTool
from workflow.dispatch import BridgeExecutor
from workflow.engine import InstalledWorkflows, WorkflowEngine, WorkflowRunSnapshot

CandidateStatus = Literal["draft", "previewed", "installed"]
ApprovalKind = Literal["run", "install", "install_skill"]
ApprovalStatus = Literal["pending", "approved", "rejected", "failed"]
MAX_DATA_CHARS = 4_000
MAX_DRAFT_CHARS = 14_000
GENERIC_FAILURE = "Capability invocation did not complete"
RUN_TIMEOUT_SECONDS = 900.0


class ChatAuthoringError(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
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
        steps.append({
            "index": index, "status": step.status,
            "failure": None if step.failure is None else (
                step.failure.code if step.failure.message == GENERIC_FAILURE
                else f"{step.failure.code}: {step.failure.message}"),
            "data": _excerpt(step.data),
        })
    return {
        "run_id": run.run_id, "status": run.status,
        "failure": None if run.failure is None else {
            "code": run.failure.code, "message": run.failure.message},
        "steps": steps,
    }


DRAFT_GUIDE = (
    "Draft or revise a Workflow from this conversation so it can be previewed, run and reused. "
    "Use it whenever the person asks for a Workflow for this platform, a reusable Workflow, or "
    "a run on the platform runtime; a workflow file written by a script is not one, and never "
    "say something ran on the platform unless authoring__run_workflow ran it. "
    "`workflow` is {\"name\": kebab-case, \"description\": one sentence, \"parameters\": "
    "[{\"name\": snake_case, \"label\": question, \"kind\": \"text\"|\"date\"|\"integer\"|"
    "\"boolean\"|\"folder\"|\"file\", \"scope\": \"runtime\", \"required\": true|false}], "
    "\"steps\": [{\"capability\": \"namespace/name@version\", \"inputs\": {...}}]}. "
    "An input is {\"source\": \"fixed\", \"value\": JSON} for what the Workflow fixes, "
    "{\"source\": \"run\", \"path\": [\"<parameter>\"]} for a run value ([] is all run values), "
    "or {\"source\": \"step\", \"step_index\": N, \"path\": [...]} for an earlier step's output. "
    "To run your own Python program as a step use coding/run-python@1.0.0 with inputs "
    "{\"request\": {\"source\": \"fixed\", \"value\": {\"workspace\": \"<absolute task folder>\", "
    "\"script\": \"<complete script>\"}}, \"arguments\": {\"source\": \"run\", \"path\": []}}; the "
    "script reads the run values with json.load(open(os.environ[\"AEP_WORKFLOW_PARAMS\"])) and "
    "writes only to the workspace's output folder, so the same script reruns with new values. "
    "To operate a web system as a step use browser/operate@1.0.0 with inputs {\"actions\": "
    "{\"source\": \"fixed\", \"value\": [the browser__operate actions]}, \"values\": "
    "{\"source\": \"run\", \"path\": []}, \"workspace\": {\"source\": \"fixed\", \"value\": "
    "\"<absolute task folder>\"}}; a download lands in <workspace>/output/downloads for a later "
    "coding/run-python step. To operate a desktop application as a step use "
    "desktop/operate@1.0.0 with {\"app\": fixed, \"actions\": fixed, \"values\": run values}. "
    "{placeholders} in those actions take the run values; put run values in output file "
    "names so a rerun with new values neither collides with nor overwrites an earlier result. "
    "A system the person signs in to or "
    "operates is reached only through these steps, never fetched or read by a script. "
    "A result made with conversation tools does not show the Workflow works: before saying "
    "it is ready for reuse, run the version that will be reused (the installed one, once "
    "installed) and check what it wrote; fix and rerun until it does the job. When asked to "
    "rerun it with new values, run that installed version unchanged. "
    "Never put a password, token or key in a fixed value. Pass `candidate_id` to revise a "
    "candidate you drafted before. The host fills in owner, version and lifecycle."
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
    ) -> None:
        self.root = root
        self.skills_dir = skills_dir
        # Where a run-python or browser step's fixed workspace may be; checked
        # at draft time so a Workflow never fails only at its approved run.
        self.coding_workspace_roots = coding_workspace_roots
        self._bridge = bridge
        self.namespace = namespace
        self.workflows_dir = workflows_dir
        self.grants_file = grants_file
        self.run_timeout_seconds = run_timeout_seconds

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
        self, actor: str, session_id: str | None, title: str, raw: dict[str, Any],
        candidate_id: str | None = None, *, source: str = "conversation",
    ) -> tuple[ChatCandidate | None, list[str]]:
        """Validate the model's Workflow and keep it as a candidate. Returns
        the candidate, or None with the problems the model must fix."""
        previous = self.candidate(candidate_id, actor) if candidate_id else None
        manifest, problems = self.check(actor, raw, previous)
        if manifest is None:
            return None, problems
        now = _now()
        item = ChatCandidate(
            candidate_id=previous.candidate_id if previous is not None
            else f"wf-{datetime.now(UTC):%Y%m%d-%H%M%S}-{secrets.token_hex(3)}",
            actor=actor, session_id=session_id, source=source,
            title=title.strip() or manifest.description,
            created_at=previous.created_at if previous is not None else now, updated_at=now,
            revision=previous.revision + 1 if previous is not None else 1, draft=manifest,
            installed_as=previous.installed_as if previous is not None else None,
            installed_digest=previous.installed_digest if previous is not None else None,
            status="installed" if previous is not None and previous.installed_digest == digest(
                manifest) else "draft",
        )
        return self._save_candidate(item), []

    def check(
        self, actor: str, raw: dict[str, Any], previous: ChatCandidate | None = None
    ) -> tuple[WorkflowManifest | None, list[str]]:
        """The Workflow the host would keep, or the problems to fix; saves
        nothing."""
        assembled = assemble(raw, namespace=self.namespace, owner=actor, installed=self.installed)
        identity = assembled["metadata"]["identity"]
        # A name belongs to whoever installed it first; its versions only go up,
        # so a new draft of an existing name never reuses an installed version
        # (owner decision 2026-10-07; lab fix-008 W01 hit workflow_version_exists).
        published = self._published(str(identity["namespace"]), str(identity["name"]))
        others = sorted({m.metadata.owner.id for m in published
                         if (m.metadata.owner.type, m.metadata.owner.id) != ("user", actor)})
        if others:
            return None, [f"workflow.name: '{identity['name']}' already belongs to "
                          f"{', '.join(others)}; choose another name, or ask its owner to let "
                          "you co-edit it"]
        taken = [_core(m.metadata.identity.version) for m in published]
        if previous is not None and previous.draft.metadata.identity.name == identity["name"]:
            taken.append(_core(previous.draft.metadata.identity.version))
        major, minor, patch = max(taken) if taken else (1, 0, -1)
        identity["version"] = f"{major}.{minor}.{patch + 1}"
        problems: list[str] = []
        try:
            manifest = WorkflowManifest.model_validate(assembled)
        except ValidationError as error:
            return None, [f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}"
                          for e in error.errors()[:8]]
        for index, step in enumerate(manifest.steps):
            if not isinstance(step, WorkflowStep):
                problems.append(f"step {index}: nested Workflows are not supported here")
            elif self.installed.get(step.capability) is None:
                problems.append(
                    f"step {index}: capability {_key(step.capability)} is not installed")
            else:
                problems.extend(self._workspace_problems(index, step))
        if not manifest.steps:
            problems.append("the Workflow has no steps")
        return (None, problems) if problems else (manifest, [])

    def _workspace_problems(self, index: int, step: WorkflowStep) -> list[str]:
        """A fixed task folder must lie under the coding roots. One that does
        not exist yet is created there, with input/ and output/."""
        name = (step.capability.namespace, step.capability.name)
        source = None
        if name == ("coding", "run-python"):
            request = step.inputs.get("request")
            value = request.value if isinstance(request, FixedInput) else None
            source = value.get("workspace") if isinstance(value, dict) else None
        elif name == ("browser", "operate"):
            fixed = step.inputs.get("workspace")
            source = fixed.value if isinstance(fixed, FixedInput) else None
        if not isinstance(source, str):
            return []
        roots = self.coding_workspace_roots
        resolved = containing_root(source, roots)
        if resolved is None:
            allowed = "; ".join(roots) if roots else "none are configured on this host"
            return [f"step {index}: workspace {source} is outside the allowed task folders "
                    f"({allowed}); use a folder under one of them"]
        if not resolved.is_dir():
            for part in ("input", "output"):
                (resolved / part).mkdir(parents=True, exist_ok=True)
        return []

    def _published(self, namespace: str, name: str) -> list[WorkflowManifest]:
        """The versions of one Workflow name installed on this Host."""
        found = []
        for path in self.workflows_dir.glob(f"{namespace}__{name}__*.json"):
            try:
                manifest = WorkflowManifest.model_validate_json(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if (manifest.metadata.identity.namespace, manifest.metadata.identity.name) == (
                    namespace, name):
                found.append(manifest)
        return found

    def _engine(self, manifest: WorkflowManifest, actor: str, ref: str) -> WorkflowEngine:
        workflows = InstalledWorkflows()
        workflows.register(manifest)
        bridge = self._bridge()
        trial = BridgeExecutor(
            bridge.installed, LocalPolicy(self.grants(manifest, actor, ref)),
            timeout_seconds=bridge.timeout_seconds,
        )
        return WorkflowEngine(workflows, trial, settings_provider=lambda _manifest: {})

    @staticmethod
    def _context(actor: str, namespace: str, session_id: str | None, label: str) -> RequestContext:
        token = secrets.token_hex(8)
        return RequestContext(
            trace=TraceIdentifiers(trace_id=f"chat-authoring-{token}",
                                   request_id=f"{label}-{token}", span_id=label),
            actor=actor, namespace=namespace, channel="local", session_id=session_id,
            message=f"{label} a Workflow drafted in a conversation",
        )

    def preview(
        self, actor: str, candidate_id: str, arguments: dict[str, JsonValue]
    ) -> dict[str, JsonValue]:
        item = self.candidate(candidate_id, actor)
        engine = self._engine(item.draft, actor, f"chat-preview:{candidate_id}")
        shown = asyncio.run(engine.preview(
            self._context(actor, self.namespace, item.session_id, "preview"),
            item.draft.metadata.identity, arguments))
        self._save_candidate(item.model_copy(update={
            "preview_status": shown.status, "preview_of": digest(item.draft),
            "status": item.status if item.status == "installed" else (
                "previewed" if shown.status == "previewed" else "draft"),
        }))
        data = json.loads(shown.model_dump_json())
        return {"candidate_id": candidate_id, "digest": digest(item.draft),
                "preview": _excerpt(data)}

    # -- running and installing -------------------------------------------

    def read_only(self, manifest: WorkflowManifest) -> bool:
        for step in manifest.steps:
            binding = (
                self.installed.get(step.capability) if isinstance(step, WorkflowStep) else None
            )
            if binding is None or binding.spec.side_effect != "read":
                return False
        return True

    def execute(
        self, actor: str, candidate: ChatCandidate, arguments: dict[str, JsonValue], ref: str
    ) -> dict[str, JsonValue]:
        engine = self._engine(candidate.draft, actor, ref)
        snapshot = asyncio.run(engine.execute(
            self._context(actor, self.namespace, candidate.session_id, "run"),
            candidate.draft.metadata.identity, arguments,
            timeout_seconds=self.run_timeout_seconds,
        ))
        return {"candidate_id": candidate.candidate_id, "digest": digest(candidate.draft),
                "workflow": _key(candidate.draft.metadata.identity), **summarize(snapshot)}

    def request(
        self, actor: str, session_id: str | None, kind: ApprovalKind, candidate_id: str,
        arguments: dict[str, JsonValue] | None = None, *, source: str = "conversation",
    ) -> ApprovalRequest:
        if kind == "install_skill":
            return self.request_skill_install(actor, candidate_id, source=source)
        item = self.candidate(candidate_id, actor)
        if kind == "install" and item.status == "installed":
            raise ChatAuthoringError("candidate_already_installed")
        identity = item.draft.metadata.identity
        steps = ", ".join(
            _key(step.capability) for step in item.draft.steps if isinstance(step, WorkflowStep))
        summary = (
            f"Run {_key(identity)} once with {json.dumps(arguments or {}, ensure_ascii=False)}"
            if kind == "run" else f"Install {_key(identity)} for reuse"
        ) + f" — steps: {steps}"
        return self._save_approval(ApprovalRequest(
            approval_id=f"ap-{datetime.now(UTC):%Y%m%d-%H%M%S}-{secrets.token_hex(3)}",
            actor=actor, session_id=session_id, kind=kind, source=source,
            candidate_id=candidate_id,
            digest=digest(item.draft), workflow=_key(identity), arguments=arguments or {},
            summary=summary[:600], created_at=_now(),
        ))

    def decide(self, approval_id: str, actor: str, approve: bool) -> ApprovalRequest:
        """The owner's decision, from a button the model cannot press."""
        item = self.approval(approval_id, actor)
        if item.status != "pending":
            raise ChatAuthoringError("approval_already_decided")
        if not approve:
            return self._save_approval(item.model_copy(update={
                "status": "rejected", "decided_at": _now()}))
        if item.kind == "install_skill":
            return self._decide_skill(item, actor)
        candidate = self.candidate(item.candidate_id, actor)
        if digest(candidate.draft) != item.digest:
            return self._save_approval(item.model_copy(update={
                "status": "failed", "decided_at": _now(),
                "result": {"failure": "the candidate changed after the request; ask again"}}))
        try:
            if item.kind == "run":
                result: JsonValue = self.execute(
                    actor, candidate, item.arguments, f"chat-approval:{approval_id}")
            else:
                result = self.install(candidate, actor, approval_id)
        except ChatAuthoringError as error:
            return self._save_approval(item.model_copy(update={
                "status": "failed", "decided_at": _now(), "result": {"failure": error.code}}))
        return self._save_approval(item.model_copy(update={
            "status": "approved", "decided_at": _now(), "result": result}))

    def install(
        self, candidate: ChatCandidate, actor: str, approval_id: str
    ) -> dict[str, JsonValue]:
        identity = candidate.draft.metadata.identity
        name = f"{identity.namespace}__{identity.name}__{identity.version}.json"
        target = self.workflows_dir / name
        if target.exists():
            raise ChatAuthoringError("workflow_version_exists")
        metadata = candidate.draft.metadata.model_dump(mode="json")
        metadata.update({
            "lifecycle": "published",
            "business_approval": {"status": "approved", "reviewer": actor,
                                  "evidence": f"chat-approval:{approval_id}"},
            "validation_refs": [
                f"chat-candidate:{candidate.candidate_id}:{digest(candidate.draft)}"],
        })
        published = WorkflowManifest.model_validate(
            {**candidate.draft.model_dump(mode="json"), "metadata": metadata})
        self.workflows_dir.mkdir(parents=True, exist_ok=True)
        write_atomically(target, (json.dumps(published.model_dump(mode="json"),
                                             ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
        self._add_grants(published, actor, f"chat-approval:{approval_id}")
        self._save_candidate(candidate.model_copy(update={
            "status": "installed", "installed_as": _key(identity),
            "installed_digest": digest(candidate.draft)}))
        return {"installed_as": _key(identity), "file": target.name,
                "digest": digest(candidate.draft),
                "note": "Reuse it from a conversation now; other channels see it after a restart."}

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

    def check_skill(
        self, actor: str, raw: dict[str, Any], previous: SkillCandidate | None = None
    ) -> tuple[SkillManifest | None, list[str]]:
        """The Skill the host would keep, or the problems to fix; saves nothing."""
        assembled = assemble_skill(raw, namespace=self.namespace, owner=actor)
        skills = installed_skills(self._skills_dir())
        identity = assembled["metadata"]["identity"]
        taken = [_core(m.metadata.identity.version) for m in skills
                 if (m.metadata.identity.namespace, m.metadata.identity.name)
                 == (identity["namespace"], identity["name"])]
        disabled = self._skills_dir() / "disabled"
        taken.extend(_core(m.metadata.identity.version) for m in installed_skills(disabled)
                     if (m.metadata.identity.namespace, m.metadata.identity.name)
                     == (identity["namespace"], identity["name"]))
        if previous is not None and previous.draft.metadata.identity.name == identity["name"]:
            taken.append(_core(previous.draft.metadata.identity.version))
        major, minor, patch = max(taken) if taken else (1, 0, -1)
        identity["version"] = f"{major}.{minor}.{patch + 1}"
        return check_skill(raw, assembled, actor=actor, installed=self.installed,
                           workflows=self.installed_workflows(), skills=skills)

    def draft_skill(
        self, actor: str, title: str, raw: dict[str, Any], candidate_id: str | None = None,
        *, source: str = "conversation",
    ) -> tuple[SkillCandidate | None, list[str]]:
        previous = self.skill_candidate(candidate_id, actor) if candidate_id else None
        manifest, problems = self.check_skill(actor, raw, previous)
        if manifest is None:
            return None, problems
        now = _now()
        item = SkillCandidate(
            candidate_id=previous.candidate_id if previous is not None
            else f"sk-{datetime.now(UTC):%Y%m%d-%H%M%S}-{secrets.token_hex(3)}",
            actor=actor, source=source, title=title.strip() or manifest.alias,
            created_at=previous.created_at if previous is not None else now, updated_at=now,
            revision=previous.revision + 1 if previous is not None else 1, draft=manifest,
        )
        return self._save_skill_candidate(item), []

    def request_skill_install(
        self, actor: str, candidate_id: str, *, source: str = "conversation"
    ) -> ApprovalRequest:
        item = self.skill_candidate(candidate_id, actor)
        if item.status == "installed":
            raise ChatAuthoringError("candidate_already_installed")
        identity = item.draft.metadata.identity
        commands = ", ".join(f"{c.name}→{_key(c.target)}" for c in item.draft.commands) or "none"
        summary = (f"Install Skill {_key(identity)} (alias {item.draft.alias}) — commands: "
                   f"{commands}; used after the host restarts")
        return self._save_approval(ApprovalRequest(
            approval_id=f"ap-{datetime.now(UTC):%Y%m%d-%H%M%S}-{secrets.token_hex(3)}",
            actor=actor, session_id=None, kind="install_skill", source=source,
            candidate_id=candidate_id, digest=skill_digest(item.draft), workflow=_key(identity),
            summary=summary[:600], created_at=_now(),
        ))

    def _decide_skill(self, item: ApprovalRequest, actor: str) -> ApprovalRequest:
        candidate = self.skill_candidate(item.candidate_id, actor)
        if skill_digest(candidate.draft) != item.digest:
            return self._save_approval(item.model_copy(update={
                "status": "failed", "decided_at": _now(),
                "result": {"failure": "the candidate changed after the request; ask again"}}))
        try:
            result = self.install_skill(candidate, actor, item.approval_id)
        except ChatAuthoringError as error:
            return self._save_approval(item.model_copy(update={
                "status": "failed", "decided_at": _now(), "result": {"failure": error.code}}))
        return self._save_approval(item.model_copy(update={
            "status": "approved", "decided_at": _now(), "result": result}))

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
        others = [m for m in installed_skills(folder)
                  if (m.metadata.identity.namespace, m.metadata.identity.name)
                  != (identity.namespace, identity.name)
                  or (m.metadata.owner.type, m.metadata.owner.id) != ("user", actor)]
        _, problems = check_skill(
            {"instructions": candidate.draft.instructions},
            candidate.draft.model_dump(mode="json"), actor=actor, installed=self.installed,
            workflows=self.installed_workflows(), skills=others,
        )
        if problems:
            raise ChatAuthoringError("skill_no_longer_valid")
        metadata = candidate.draft.metadata.model_dump(mode="json")
        metadata.update({
            "lifecycle": "published",
            "business_approval": {"status": "approved", "reviewer": actor,
                                  "evidence": f"chat-approval:{approval_id}"},
            "validation_refs": [
                f"skill-candidate:{candidate.candidate_id}:{skill_digest(candidate.draft)}"],
        })
        published = SkillManifest.model_validate(
            {**candidate.draft.model_dump(mode="json"), "metadata": metadata})
        set_aside: list[str] = []
        for path in sorted(folder.glob(f"{identity.namespace}__{identity.name}__*.json")):
            (folder / "disabled").mkdir(parents=True, exist_ok=True)
            path.replace(folder / "disabled" / path.name)
            set_aside.append(path.name)
        folder.mkdir(parents=True, exist_ok=True)
        write_atomically(target, (json.dumps(published.model_dump(mode="json"),
                                             ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
        self._save_skill_candidate(candidate.model_copy(update={
            "status": "installed", "installed_as": _key(identity),
            "installed_digest": skill_digest(candidate.draft)}))
        return {"installed_as": _key(identity), "file": target.name,
                "digest": skill_digest(candidate.draft), "set_aside": list(set_aside),
                "note": "The host uses it after a restart."}

    # -- what an external agent may see -------------------------------------

    def external_view(self, item: ApprovalRequest) -> dict[str, JsonValue]:
        """An approval's outcome without data: statuses and codes only, so
        nothing a run read reaches an external agent (PUBLIC rule)."""
        view: dict[str, JsonValue] = {
            "approval_id": item.approval_id, "kind": item.kind, "status": item.status,
            "workflow": item.workflow, "candidate_id": item.candidate_id,
            "decided_at": item.decided_at}
        result = item.result if isinstance(item.result, dict) else {}
        if item.status == "failed":
            failure = result.get("failure")
            view["failure"] = failure if isinstance(failure, str) and " " not in failure \
                else "failed"
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
                actor=actor, asset=binding.spec.identity,
                permissions=binding.spec.policy.required_permissions,
                policy_refs=binding.spec.policy.policy_refs, approval_ref=ref,
            )
        return tuple(found.values())

    def _add_grants(self, manifest: WorkflowManifest, actor: str, ref: str) -> None:
        existing = (
            [CapabilityGrant.model_validate(item) for item in documents(self.grants_file)]
            if self.grants_file.is_file() else []
        )
        have = {(grant.actor, grant.asset.key) for grant in existing}
        added = [grant for grant in self.grants(manifest, actor, ref)
                 if (grant.actor, grant.asset.key) not in have]
        if added:
            payload = [grant.model_dump(mode="json") for grant in (*existing, *added)]
            write_atomically(self.grants_file, (json.dumps(payload, ensure_ascii=False, indent=2)
                                                + "\n").encode("utf-8"))

    # -- conversation tools ------------------------------------------------

    def tools(self) -> Sequence[HostTool]:
        async def run_sync(fn: Callable[[], HostToolOutcome]) -> HostToolOutcome:
            return await asyncio.to_thread(fn)

        Args = dict[str, JsonValue]

        async def draft_tool(context: RequestContext, args: Args) -> HostToolOutcome:
            def work() -> HostToolOutcome:
                raw = args.get("workflow")
                if not isinstance(raw, dict):
                    return _refused("workflow_missing", "give the Workflow as an object")
                candidate_id = args.get("candidate_id")
                item, problems = self.draft(
                    context.actor, context.session_id, str(args.get("title") or ""), raw,
                    str(candidate_id) if candidate_id else None)
                if item is None:
                    return HostToolOutcome(status="failed", data={"problems": problems},
                                           failure=Failure(code="workflow_invalid",
                                                           message="; ".join(problems)[:500]))
                return HostToolOutcome(status="succeeded", data={
                    "candidate_id": item.candidate_id,
                    "workflow": _key(item.draft.metadata.identity),
                    "revision": item.revision, "digest": digest(item.draft),
                    "read_only": self.read_only(item.draft),
                    "next": "preview it, then run it; a run that writes waits for the owner's "
                            "approval",
                })
            return await run_sync(work)

        async def preview_tool(context: RequestContext, args: Args) -> HostToolOutcome:
            def work() -> HostToolOutcome:
                return HostToolOutcome(status="succeeded", data=self.preview(
                    context.actor, str(args.get("candidate_id") or ""), _arguments(args)))
            return await run_sync(work)

        async def run_tool(context: RequestContext, args: Args) -> HostToolOutcome:
            def work() -> HostToolOutcome:
                item = self.candidate(str(args.get("candidate_id") or ""), context.actor)
                arguments = _arguments(args)
                if self.read_only(item.draft):
                    return HostToolOutcome(status="succeeded", data=self.execute(
                        context.actor, item, arguments, f"chat-read-only:{item.candidate_id}"))
                request = self.request(context.actor, context.session_id, "run",
                                       item.candidate_id, arguments)
                return HostToolOutcome(status="awaiting_approval", data={
                    "approval_id": request.approval_id, "summary": request.summary,
                    "next": "Nothing ran yet. Tell the person it waits for their approval "
                            "button; after they approve, the result appears in this conversation.",
                })
            return await run_sync(work)

        async def install_tool(context: RequestContext, args: Args) -> HostToolOutcome:
            def work() -> HostToolOutcome:
                request = self.request(context.actor, context.session_id, "install",
                                       str(args.get("candidate_id") or ""))
                return HostToolOutcome(status="awaiting_approval", data={
                    "approval_id": request.approval_id, "summary": request.summary,
                    "next": "Nothing is installed yet; it waits for the person's approval button.",
                })
            return await run_sync(work)

        async def get_tool(context: RequestContext, args: Args) -> HostToolOutcome:
            def work() -> HostToolOutcome:
                item = self.candidate(str(args.get("candidate_id") or ""), context.actor)
                body: dict[str, JsonValue] = {
                        "candidate_id": item.candidate_id,
                        "workflow": _key(item.draft.metadata.identity),
                        "status": item.status, "digest": digest(item.draft),
                        "parameters": [p.model_dump(mode="json") for p in item.draft.parameters],
                        "steps": [step.model_dump(mode="json") for step in item.draft.steps]}
                return HostToolOutcome(status="succeeded", data=_excerpt(body, MAX_DRAFT_CHARS))
            return await run_sync(work)

        async def list_tool(context: RequestContext, args: Args) -> HostToolOutcome:
            def work() -> HostToolOutcome:
                return HostToolOutcome(status="succeeded", data=[
                    {"candidate_id": item.candidate_id, "title": item.title,
                     "workflow": _key(item.draft.metadata.identity), "status": item.status,
                     "digest": digest(item.draft), "description": item.draft.description,
                     "parameters": [p.name for p in item.draft.parameters]}
                    for item in self.candidates(context.actor)[:30]
                ])
            return await run_sync(work)

        def guarded(handler: Any) -> Any:
            async def call(context: RequestContext, args: dict[str, JsonValue]) -> HostToolOutcome:
                try:
                    outcome: HostToolOutcome = await handler(context, args)
                    return outcome
                except ChatAuthoringError as error:
                    return _refused(error.code, error.code)
            return call

        candidate = {"candidate_id": {"type": "string"}}
        values = {"arguments": {"type": "object", "description": "run values by parameter name"}}
        return (
            HostTool(ModelTool(
                name="authoring__draft_workflow",
                description=" ".join(
                    part for part in (DRAFT_GUIDE, workspace_note(self.coding_workspace_roots))
                    if part),
                input_contract="host.authoring.draft.v1",
                input_schema={"type": "object", "properties": {
                    "title": {"type": "string"}, "workflow": {"type": "object"},
                    "candidate_id": {"type": "string"}}, "required": ["title", "workflow"]},
            ), guarded(draft_tool)),
            HostTool(ModelTool(
                name="authoring__preview_workflow",
                description="Preview a drafted Workflow: read steps run for real, other steps show "
                            "what they would do; nothing changes.",
                input_contract="host.authoring.preview.v1",
                input_schema={"type": "object", "properties": {**candidate, **values},
                              "required": ["candidate_id"]},
            ), guarded(preview_tool)),
            HostTool(ModelTool(
                name="authoring__run_workflow",
                description="Run a drafted or installed Workflow once with run values. A Workflow "
                            "whose steps only read runs now and returns its result; otherwise it "
                            "waits for the person's approval button and nothing runs yet. If a "
                            "platform run failed, fix the cause (revise the candidate when its "
                            "steps were wrong) and run it again here; do not redo the work "
                            "outside the Workflow.",
                input_contract="host.authoring.run.v1",
                input_schema={"type": "object", "properties": {**candidate, **values},
                              "required": ["candidate_id"]},
            ), guarded(run_tool)),
            HostTool(ModelTool(
                name="authoring__install_workflow",
                description="Ask the person to install a drafted Workflow for reuse; it waits for "
                            "their approval button.",
                input_contract="host.authoring.install.v1",
                input_schema={"type": "object", "properties": candidate,
                              "required": ["candidate_id"]},
            ), guarded(install_tool)),
            HostTool(ModelTool(
                name="authoring__get_workflow",
                description="Show a drafted or installed Workflow in full (parameters and steps "
                            "with their inputs), to check or revise it.",
                input_contract="host.authoring.get.v1",
                input_schema={"type": "object", "properties": candidate,
                              "required": ["candidate_id"]},
            ), guarded(get_tool)),
            HostTool(ModelTool(
                name="authoring__list_workflows",
                description="List the Workflows this person drafted or installed from "
                            "conversations, to reuse one with new run values.",
                input_contract="host.authoring.list.v1",
                input_schema={"type": "object", "properties": {}},
            ), guarded(list_tool)),
        )


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
            {"index": step.get("index"), "status": step.get("status"),
             "failure": str(step.get("failure")).split(":", 1)[0]
             if step.get("failure") else None}
            for step in (steps if isinstance(steps, list) else []) if isinstance(step, dict)
        ],
    }


def approval_text(item: ApprovalRequest) -> str:
    """What the conversation shows, and the Agent reads, after a decision."""
    if item.status == "rejected":
        return f"【已拒絕】{item.summary}。沒有執行任何動作。"
    result = item.result if isinstance(item.result, dict) else {}
    if item.status == "failed":
        return f"【未執行】{item.summary}。原因：{result.get('failure')}"
    if item.kind == "install_skill":
        return (f"【已核准安裝 Skill】{result.get('installed_as')}"
                f"（digest {result.get('digest')}）。主機重新啟動後生效。")
    if item.kind == "install":
        return (f"【已核准安裝】{result.get('installed_as')}（digest {result.get('digest')}）。"
                "之後可以在對話中用新的參數重跑它。")
    lines = [f"【已核准並執行】{item.workflow}（候選 {item.candidate_id}，digest "
             f"{result.get('digest')}）結果：{result.get('status')}"]
    failure = result.get("failure")
    if failure:
        lines.append(f"失敗：{json.dumps(failure, ensure_ascii=False)}")
    steps = result.get("steps")
    for step in steps if isinstance(steps, list) else []:
        if not isinstance(step, dict):
            continue
        data = step.get("data")
        detail = json.dumps(data, ensure_ascii=False)
        lines.append(f"步驟 {step.get('index')}：{step.get('status')}"
                     + (f"（{step.get('failure')}）" if step.get("failure") else "")
                     + f"\n{detail[:2500]}")
    return "\n".join(lines)
