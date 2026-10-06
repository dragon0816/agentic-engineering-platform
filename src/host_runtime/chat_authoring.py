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
from capabilities.runtime import CapabilityGrant, InstalledCapabilities, LocalPolicy
from capabilities.workflow_author.conversation import assemble
from common.assets import AssetIdentity, WorkflowManifest, WorkflowStep
from common.base import Contract, Symbol, Text
from common.execution import Failure, RequestContext, TraceIdentifiers
from host_runtime.workspace import documents, write_atomically
from models.contracts import ModelTool
from workflow.dispatch import BridgeExecutor
from workflow.engine import InstalledWorkflows, WorkflowEngine, WorkflowRunSnapshot

CandidateStatus = Literal["draft", "previewed", "installed"]
ApprovalKind = Literal["run", "install"]
ApprovalStatus = Literal["pending", "approved", "rejected", "failed"]
MAX_DATA_CHARS = 4_000
RUN_TIMEOUT_SECONDS = 900.0


class ChatAuthoringError(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class ChatCandidate(Contract):
    candidate_id: Symbol
    actor: Symbol
    session_id: Text | None = None
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
    candidate_id: Symbol
    digest: Text
    workflow: Text
    arguments: dict[Symbol, JsonValue] = Field(default_factory=dict)
    summary: Text
    status: ApprovalStatus = "pending"
    created_at: Text
    decided_at: Text | None = None
    result: JsonValue = None


def _key(identity: AssetIdentity) -> str:
    return f"{identity.namespace}/{identity.name}@{identity.version}"


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def digest(manifest: WorkflowManifest) -> str:
    """The Workflow's code identity: the same steps, scripts and inputs give
    the same digest, so a rerun with new values is visibly the same Workflow."""
    return hashlib.sha256(manifest.model_dump_json().encode("utf-8")).hexdigest()


def _excerpt(value: JsonValue) -> JsonValue:
    text = json.dumps(value, ensure_ascii=False)
    if len(text) <= MAX_DATA_CHARS:
        return value
    return {"truncated": True, "preview": text[:MAX_DATA_CHARS]}


def summarize(snapshot: WorkflowRunSnapshot) -> dict[str, JsonValue]:
    run = snapshot.run
    steps: list[JsonValue] = []
    for index, step in enumerate(snapshot.step_results):
        steps.append({
            "index": index, "status": step.status,
            "failure": None if step.failure is None else step.failure.code,
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
    ) -> None:
        self.root = root
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
        candidate_id: str | None = None,
    ) -> tuple[ChatCandidate | None, list[str]]:
        """Validate the model's Workflow and keep it as a candidate. Returns
        the candidate, or None with the problems the model must fix."""
        previous = self.candidate(candidate_id, actor) if candidate_id else None
        revision = previous.revision + 1 if previous is not None else 1
        assembled = assemble(raw, namespace=self.namespace, owner=actor, installed=self.installed)
        assembled["metadata"]["identity"]["version"] = f"1.0.{revision - 1}"
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
        if not manifest.steps:
            problems.append("the Workflow has no steps")
        if problems:
            return None, problems
        now = _now()
        item = ChatCandidate(
            candidate_id=previous.candidate_id if previous is not None
            else f"wf-{datetime.now(UTC):%Y%m%d-%H%M%S}-{secrets.token_hex(3)}",
            actor=actor, session_id=session_id, title=title.strip() or manifest.description,
            created_at=previous.created_at if previous is not None else now, updated_at=now,
            revision=revision, draft=manifest,
            installed_as=previous.installed_as if previous is not None else None,
            installed_digest=previous.installed_digest if previous is not None else None,
            status="installed" if previous is not None and previous.installed_digest == digest(
                manifest) else "draft",
        )
        return self._save_candidate(item), []

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
        arguments: dict[str, JsonValue] | None = None,
    ) -> ApprovalRequest:
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
            actor=actor, session_id=session_id, kind=kind, candidate_id=candidate_id,
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
                name="authoring__draft_workflow", description=DRAFT_GUIDE,
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
