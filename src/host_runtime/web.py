"""A web interface to this machine's resident Agent, served by this machine.

Another ingress, and nothing more. It builds the same `LocalAgentRequest` the
command line, the window and Telegram build, hands it to the same Agent, and
shows what came back. No routing, no policy and no capability lives here.

It is deliberately generic. There is no page for the weekly report or for any
other piece of work: the report is one installed asset among however many this
machine has, and it appears in the list of them like the rest. A page written
for one workflow would have to be written again for the next.

From the standard library alone, like `control_plane.http`, for the same
reason: a company machine installs this bundle with `--no-index` behind a
proxy that reaches no package index and no content delivery network. Every
byte of the page is served from here.

## What guards it

A web page that runs capabilities is reachable by things a desktop window is
not -- any process on the machine, and any page open in the browser. So:

1. It listens on the loopback address only. Nothing on the network can reach
   it, which is the owner's decision of 2026-09-24.
2. Every request carries `Authorization: Bearer <token>`, where the token is
   made afresh each run and printed once. A page on another origin cannot set
   that header without a preflight, and this server answers no preflight and
   sends no cross-origin header, so it cannot be driven from another site.
3. The `Host` header must name the loopback address, which is what stops a
   name that resolves to 127.0.0.1 from being used to reach it from outside.
4. The token is compared in constant time and never logged; no request is
   logged at all, because a request here carries the team's own words.
"""

from __future__ import annotations

import base64
import binascii
import hmac
import json
import os
import re
import secrets
import threading
import time
import uuid
from collections.abc import Callable, Mapping
from contextlib import ExitStack
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import TracebackType
from typing import Any, Literal, Self
from urllib.parse import parse_qs, urlparse

import telemetry.recorder as telemetry
from agent.contracts import ActiveAgentProfile, AgentProfile
from agent.data_policy import ContextMaterial, OutboundContext
from agent.gateway import GatewayConversationResult
from agent.routing import DOT_COMMAND
from agent.skills import SkillManifest
from capabilities.knowledge_pipeline.handlers import (
    ADOPT_SPEC,
    CONVERT_SPEC,
    DROP_ADD_SPEC,
    DROP_FOLDERS_SPEC,
    FILE_READ_SPEC,
    INDEX_BUILD_SPEC,
    INDEX_ENRICH_SPEC,
    INGEST_APPLY_SPEC,
    INGEST_PLAN_SPEC,
    LINT_SPEC,
    MERGE_SPEC,
    PLAN_PAGE_SPEC,
    PULL_SPEC,
    QUESTION_SETS_SPEC,
    RULE_FILES_SPEC,
    RULE_WRITE_SPEC,
    SANDBOX_CONTENTS_SPEC,
    SANDBOX_CREATE_SPEC,
    SANDBOX_DISCARD_SPEC,
    SANDBOX_LIST_SPEC,
    SKILL_GUIDE_SPEC,
)
from capabilities.knowledge_query.handlers import KNOWLEDGE_QUERY_SPEC, MARKET_MATRIX_SPEC
from capabilities.script_tools import load_script_tools
from capabilities.workflow_author.review import rendered as review_rendered
from common.assets import AssetIdentity, Owner, WorkflowManifest
from common.distribution import LocalStateError
from common.execution import Failure, RequestContext, TraceIdentifiers
from common.local_agent import LocalAgentRequest, LocalCapabilityRequest, LocalWorkflowRequest
from common.workflow_forms import form_fields, settings_fields
from common.workflow_parameters import (
    WorkflowParameterError,
    static_fields,
    validate_run_parameters,
    validate_static_settings,
)
from extensions.package import PortableExtensionPackage
from extensions.runtime import ExtensionLifecycleStore
from host_runtime import telemetry_api
from host_runtime.answers import readable
from host_runtime.attachments import (
    AttachmentError,
    AttachmentStore,
    for_model,
)
from host_runtime.attachments import summary as attachment_summary
from host_runtime.authoring import AuthoringError, AuthoringSession, AuthoringStudio
from host_runtime.avatars import UserPreferences, UserPreferencesStore, catalog
from host_runtime.chat_authoring import ChatAuthoringError, approval_text
from host_runtime.choice_sources import ChoiceSources
from host_runtime.contracts import (
    AgentProfileActivationRequest,
    CompanyHostConfiguration,
    CredentialBinding,
    ExtensionLifecycleProjection,
    KnowledgeAskRequest,
    ModelBinding,
    ModelSettingsUpdateRequest,
    PlatformCatalogProjection,
    PlatformDecisionProjection,
    PlatformProjection,
    PlatformSyncRequest,
    PlatformSyncResult,
    WorkflowLaunchRequest,
    WorkflowOptionsRequest,
    WorkflowSettingsUpdateRequest,
)
from host_runtime.contributions import (
    ContributionDraft,
    ContributionDraftCreateRequest,
    ConversationExcerpt,
)
from host_runtime.conversation_backends import LocalConversationBackends
from host_runtime.conversation_context import (
    ConversationContextSettings,
    ConversationContextStore,
    prepare_history,
)
from host_runtime.conversations import (
    MAX_STORED_MESSAGES,
    ConversationBackendAuthenticationRequest,
    ConversationBackendSelectRequest,
    ConversationCreateRequest,
    ConversationDeleteRequest,
    ConversationFeedbackRequest,
    ConversationMessage,
    ConversationRecord,
    ConversationTurnRequest,
    MessageFeedback,
)
from host_runtime.experience import (
    ExperienceSettings,
    ExperienceStore,
    from_benchmarks,
    from_conversations,
    from_telemetry,
    load_settings,
    save_settings,
)
from host_runtime.experience_review import latest_review, run_review
from host_runtime.host import HostRuntime, build_telegram, choice_sources, load_authorization
from host_runtime.knowledge_bench import latest as latest_benchmark
from host_runtime.knowledge_bench import run_benchmark
from host_runtime.knowledge_harness import KnowledgeHarness, harness_skill, knowledge_source_lines
from host_runtime.knowledge_publish import (
    PublishError,
    publish_candidate,
    refresh_from_project,
)
from host_runtime.knowledge_push import latest_push, run_push
from host_runtime.persona import AgentPersonaStore, AgentPersonaUpdateRequest
from host_runtime.profiles import ProfileError, activate_profile
from host_runtime.reference_sets import (
    REFERENCE_SETS_FILE,
    ReferenceSetStore,
)
from host_runtime.skill_assist import Turn, assist
from host_runtime.slash_commands import (
    COMMANDS,
    SlashCommandError,
    SlashCommandInvocation,
    parse_slash_command,
)
from host_runtime.telegram_loop import ResidentTelegram
from host_runtime.telegram_settings import (
    TelegramSettingsError,
    TelegramSettingsForm,
    TelegramSettingsUpdate,
    apply_telegram_settings,
    telegram_status,
    windows_user_environment,
)
from host_runtime.turn_summary import tool_summary
from host_runtime.workflow_settings import (
    SETTINGS_FILE,
    WorkflowSettingsError,
    WorkflowSettingsStore,
)
from host_runtime.workspace import documents, write_atomically
from knowledge.evolution import KnowledgeAnswerRecord, KnowledgeManifest
from knowledge.market_matrix import (
    MARKET_QUESTIONS,
    PRODUCT_FAMILIES,
    PRODUCT_QUESTIONS,
    TARGET_MARKETS,
    MarketMatrixRecord,
    MarketMatrixRequest,
    assess_market_cell,
)
from knowledge.pipeline import KnowledgePipeline
from knowledge.procedure import KnowledgeProcedure
from knowledge.query import cited_numbers
from knowledge.sandbox import SandboxError, Sandboxes
from knowledge.schema import answer_rules_text
from knowledge.vault import Vault
from models.contracts import ModelMessage
from models.wire import MethodTransport, UrllibTransport

#: Anything larger than this is not a request to an Agent.
MAX_BODY_BYTES = 256 * 1024
#: An uploaded SOP PDF arrives base64-encoded: a 20 MiB PDF is about 27 MiB.
MAX_SOP_UPLOAD_BYTES = 28 * 1024 * 1024
#: One attached file (25 MB) as base64 in JSON, with room for its name.
MAX_ATTACHMENT_REQUEST_BYTES = 36 * 1024 * 1024
# The Knowledge tab's pipeline steps (docs/phases/KNOWLEDGE_K1.md), by the short
# name the page sends; nothing else can be called through its route.
PIPELINE_STEPS = {spec.identity.name: spec for spec in (
    SANDBOX_CREATE_SPEC, SANDBOX_LIST_SPEC, SANDBOX_CONTENTS_SPEC, SANDBOX_DISCARD_SPEC,
    DROP_ADD_SPEC, CONVERT_SPEC, INGEST_PLAN_SPEC, INGEST_APPLY_SPEC, LINT_SPEC,
    ADOPT_SPEC, INDEX_ENRICH_SPEC, INDEX_BUILD_SPEC, MERGE_SPEC, DROP_FOLDERS_SPEC,
    PULL_SPEC, QUESTION_SETS_SPEC, RULE_FILES_SPEC, FILE_READ_SPEC, RULE_WRITE_SPEC,
    PLAN_PAGE_SPEC, SKILL_GUIDE_SPEC)}
AUTHORING_ROUTES = (
    "/api/authoring/start", "/api/authoring/get", "/api/authoring/discuss",
    "/api/authoring/preview", "/api/authoring/install",
)
BEARER = "Bearer "
#: The only addresses this ever binds to or answers for.
LOOPBACK = ("127.0.0.1", "localhost", "[::1]", "::1")


def with_tools(message: ConversationMessage) -> str:
    """An answer's text plus its tool record, and a question's attached files,
    as the model reads them on later turns."""
    if message.role == "user" and message.attachments:
        files = "\n".join(
            f"- {file['filename']} ({file['kind']}): {file['path']}" for file in message.attachments
        )
        return f"{message.text}\n\n[附件]\n{files}"
    if message.role != "assistant" or not message.tool_summary:
        return message.text
    return f"{message.text}\n\n[工具紀錄]\n{message.tool_summary}"


def _trace() -> TraceIdentifiers:
    value = uuid.uuid4().hex
    return TraceIdentifiers(
        trace_id=f"trace-{value}", request_id=f"request-{value}", span_id=f"span-{value}"
    )


def manifests(directory: Path, model: type[Any]) -> tuple[Any, ...]:
    """Whatever reads cleanly. A manifest that does not parse is reported by
    `doctor`; refusing to list the others because of it would help nobody."""
    if not directory.is_dir():
        return ()
    found: list[Any] = []
    for path in sorted(directory.glob("*.json")):
        try:
            found.extend(model.model_validate(item) for item in documents(path))
        except Exception:  # noqa: BLE001 - a listing shows what it can read
            continue
    return tuple(found)


def extension_lifecycle(runtime: HostRuntime) -> tuple[ExtensionLifecycleProjection, ...]:
    """Project valid staged packages and optional runtime evidence without executing code."""
    layout = runtime.layout
    try:
        current = {
            item.extension.key: item
            for item in ExtensionLifecycleStore(layout.extension_lifecycle).read().records
        }
    except Exception:  # noqa: BLE001 - doctor owns malformed local state
        current = {}
    gate = (
        "Registered device owner or delegated device administrator approval required."
        if runtime.config.device.device_kind == "company_workstation"
        else "Device administrator or virtual-member approval required."
    )
    projected: list[ExtensionLifecycleProjection] = []
    if not layout.extensions.is_dir():
        return ()
    for path in sorted(layout.extensions.glob("*/*/*/package.json")):
        try:
            package = PortableExtensionPackage.model_validate_json(path.read_bytes())
            expected = (
                layout.extensions
                / package.identity.namespace
                / package.identity.name
                / package.identity.version
                / "package.json"
            )
            if path.resolve() != expected.resolve():
                continue
            record = current.get(package.identity.key)
            projected.append(
                ExtensionLifecycleProjection(
                    namespace=package.identity.namespace,
                    name=package.identity.name,
                    version=package.identity.version,
                    description=package.manifest.description,
                    state="staged" if record is None else record.state,
                    publisher_key_id=package.signature.key_id,
                    capabilities=tuple(
                        f"{item.identity.namespace}/{item.identity.name}@{item.identity.version}"
                        for item in package.manifest.capabilities
                    ),
                    approval_required=True,
                    activation_gate=gate,
                    code=None if record is None else record.code,
                )
            )
        except Exception:  # noqa: BLE001 - invalid staging is diagnosed elsewhere
            continue
    return tuple(projected)


_LOCAL_WORK = re.compile(
    r"https?://"
    r"|(?<![A-Za-z])[A-Za-z]:[\\/]"
    r"|\\\\[^\\\s]+\\"
    r"|[\w\-]+\.(?:xlsx|xls|csv|json|md|txt|py|log|pdf|docx|html)(?![A-Za-z0-9])",
    re.IGNORECASE,
)


def names_local_work(message: str) -> bool:
    """A URL, a drive or UNC path, or a file name with a common extension."""
    return _LOCAL_WORK.search(message) is not None


class AgentWeb:
    """What the pages ask for, with no HTTP in it.

    Separated so every answer this serves can be tested without a socket,
    and so a different front end could be built on the same answers.
    """

    def __init__(
        self,
        runtime: HostRuntime,
        *,
        namespace: str | None = None,
        config_path: Path | None = None,
        conversation_backends: LocalConversationBackends | None = None,
    ) -> None:
        self.runtime = runtime
        self.namespace = namespace if namespace is not None else runtime.config.namespace
        self.config_path = config_path
        self.persona = AgentPersonaStore(runtime.layout.workspace_root)
        self.preferences = UserPreferencesStore(runtime.layout.workspace_root)
        self.attachments = AttachmentStore(runtime.layout.workspace_root)
        self.conversation_context = ConversationContextStore(runtime.layout.workspace_root)
        self.backends = conversation_backends or LocalConversationBackends(
            runtime.layout.workspace_root
        )
        # Exclusive operations: commands that may run workflows, settings,
        # synchronization and profile changes. Conversations in different
        # sessions run concurrently; the Bridge separately serializes every
        # workflow run and every non-read capability (`BridgeExecutor.exclusive`),
        # so two runs never act on the same workbook at once.
        self._one_at_a_time = threading.RLock()
        # Per session: a turn lock queues that session's turns in order, and a
        # short record lock guards read-modify-write of its stored record.
        self._session_guard = threading.Lock()
        self._turn_locks: dict[str, threading.Lock] = {}
        self._record_locks: dict[str, threading.Lock] = {}
        # The opt-in resident schedule loop, when `aep-host web` started one.
        # It shares the lock above, so a scheduled run never overlaps a request.
        self.schedule_loop: Any = None
        # Telegram polling inside this process; replaced when its settings change.
        self.telegram_loop: ResidentTelegram | None = None
        self.feedback_sync: Any = None
        self.knowledge_harness = KnowledgeHarness(runtime, namespace)
        self.user_environment = windows_user_environment
        # Reads the configured Gateway's model list for the Settings picker.
        self.model_listing_transport: MethodTransport = UrllibTransport()
        # Per-install Workflow settings; the engine reads the same file per run.
        self.workflow_settings_store = WorkflowSettingsStore(
            runtime.layout.workspace_root / SETTINGS_FILE
        )
        # Published choice lists behind `ref:` fields; the engine reads the same file.
        self.reference_sets = ReferenceSetStore(
            runtime.layout.workspace_root / REFERENCE_SETS_FILE
        )
        # SOP to Workflow authoring sessions (docs/phases/SOP_TO_WORKFLOW.md W5).
        router = runtime.agent.gateway.router
        self.authoring = AuthoringStudio(
            runtime.layout.workspace_root / "authoring",
            installed=runtime.agent.gateway.bridge.installed,
            model=lambda: router.model,
            model_alias=router.model_alias,
            local_only=router.local_only,
            namespace=self.namespace or "engineering",
            workflows_dir=runtime.layout.workflows,
            grants_file=runtime.layout.grants,
            settings_store=self.workflow_settings_store,
        )

    @property
    def request_lock(self) -> threading.RLock:
        return self._one_at_a_time

    # -- Conversation approvals (G4, CONVERSATIONAL_AUTHORING A5) -----------

    def approvals(self, session_id: str | None = None) -> dict[str, Any]:
        """Pending run and install requests the Agent made; only the owner's
        button decides them."""
        chat = self.runtime.chat_authoring
        if chat is None:
            return {"approvals": []}
        return {"approvals": [
            {"approval_id": item.approval_id, "kind": item.kind, "workflow": item.workflow,
             "candidate_id": item.candidate_id, "summary": item.summary,
             "arguments": item.arguments, "session_id": item.session_id,
             "created_at": item.created_at}
            for item in chat.approvals(self.runtime.actor, session_id=session_id)
        ]}

    def drafts(self) -> dict[str, Any]:
        """The owner's Workflow and Skill drafts that are not installed yet
        (owner 2026-10-08): from conversations and from external agents."""
        chat = self.runtime.chat_authoring
        if chat is None:
            return {"drafts": []}
        actor = self.runtime.actor
        runs: dict[str, dict[str, Any]] = {}
        for item in chat.approvals(actor, pending_only=False):
            if item.kind == "run":
                result = item.result if isinstance(item.result, dict) else {}
                runs[item.candidate_id] = {"status": item.status,
                                           "result": result.get("status"),
                                           "at": item.decided_at or item.created_at}
        found: list[dict[str, Any]] = []
        for workflow in chat.candidates(actor):
            if workflow.status == "installed":
                continue
            identity = workflow.draft.metadata.identity
            found.append({
                "candidate_id": workflow.candidate_id, "kind": "workflow",
                "asset": f"{identity.namespace}/{identity.name}@{identity.version}",
                "title": workflow.title, "description": workflow.draft.description,
                "source": workflow.source, "updated_at": workflow.updated_at,
                "steps": [f"{s.capability.namespace}/{s.capability.name}@{s.capability.version}"
                          for s in workflow.draft.steps if hasattr(s, "capability")],
                "parameters": [p.name for p in workflow.draft.parameters],
                "last_run": runs.get(workflow.candidate_id),
                "detail": workflow.draft.model_dump_json(indent=2)})
        if chat.skills_dir is not None:
            for skill in chat.skill_candidates(actor):
                if skill.status == "installed":
                    continue
                identity = skill.draft.metadata.identity
                found.append({
                    "candidate_id": skill.candidate_id, "kind": "skill",
                    "asset": f"{identity.namespace}/{identity.name}@{identity.version}",
                    "title": skill.title, "description": skill.draft.selector_hint or "",
                    "source": skill.source, "updated_at": skill.updated_at,
                    "steps": [c.name for c in skill.draft.commands], "parameters": [],
                    "last_run": None, "detail": skill.draft.model_dump_json(indent=2)})
        found.sort(key=lambda item: str(item["updated_at"]), reverse=True)
        return {"drafts": found}

    def draft_action(self, action: str, candidate_id: str) -> dict[str, Any]:
        """Install (the owner's press is the approval) or delete a draft."""
        chat = self.runtime.chat_authoring
        if chat is None or action not in {"install", "delete"}:
            return {"ok": False, "code": "draft_request_invalid"}
        try:
            with self._one_at_a_time:
                if action == "delete":
                    chat.delete_candidate(self.runtime.actor, candidate_id)
                    return {"ok": True}
                decided = chat.install_now(self.runtime.actor, candidate_id)
        except ChatAuthoringError as error:
            return {"ok": False, "code": error.code}
        result = decided.result if isinstance(decided.result, dict) else {}
        if decided.status != "approved":
            return {"ok": False, "code": str(result.get("failure") or decided.status)}
        return {"ok": True, "installed_as": result.get("installed_as"),
                "note": result.get("note"), "text": approval_text(decided)}

    def external_approvals(self) -> dict[str, Any]:
        """What Claude Code, Codex or Copilot submitted and wait for the
        owner (EXTERNAL_AUTHORING X5), with the whole draft to review: a
        Skill's instructions reach the model's prompt."""
        chat = self.runtime.chat_authoring
        if chat is None:
            return {"approvals": []}
        found = []
        for item in chat.approvals(self.runtime.actor):
            if not item.source.startswith("external:"):
                continue
            try:
                draft = (chat.skill_candidate(item.candidate_id, self.runtime.actor).draft
                         if item.kind == "install_skill"
                         else chat.candidate(item.candidate_id, self.runtime.actor).draft)
                detail = draft.model_dump_json(indent=2)
            except ChatAuthoringError:
                detail = ""
            found.append({
                "approval_id": item.approval_id, "kind": item.kind, "source": item.source,
                "workflow": item.workflow, "summary": item.summary,
                "arguments": item.arguments, "created_at": item.created_at,
                "detail": detail})
        return {"approvals": found}

    def decide_approval(self, approval_id: str, decision: str) -> dict[str, Any]:
        """The owner pressed approve or reject. The result is added to the
        conversation so the Agent sees it on the next turn."""
        chat = self.runtime.chat_authoring
        if chat is None or decision not in {"approve", "reject"}:
            return {"ok": False, "code": "approval_request_invalid"}
        try:
            with self._one_at_a_time:
                decided = chat.decide(approval_id, self.runtime.actor, decision == "approve")
        except ChatAuthoringError as error:
            return {"ok": False, "code": error.code}
        text = approval_text(decided)
        message = None
        if decided.session_id:
            with self._record_lock(decided.session_id):
                record = self.runtime.state.conversation(decided.session_id, self.runtime.actor)
                if record is not None:
                    now = datetime.now(UTC)
                    # A pair, as every turn is: the owner's decision, then its result.
                    said = ConversationMessage(
                        message_id=f"message-{uuid.uuid4().hex}", role="user",
                        text=("【核准】" if decision == "approve" else "【拒絕】")
                        + decided.summary,
                        created_at=now, status="submitted",
                    )
                    added = ConversationMessage(
                        message_id=f"message-{uuid.uuid4().hex}", role="assistant", text=text,
                        created_at=now,
                        status="answered" if decided.status != "failed" else "failed",
                    )
                    self.runtime.state.save_conversation(record.model_copy(update={
                        "updated_at": max(now, record.updated_at),
                        "messages": (record.messages + (said, added))[-MAX_STORED_MESSAGES:],
                    }))
                    message = json.loads(added.model_dump_json())
        return {"ok": True, "approval": json.loads(decided.model_dump_json()),
                "text": text, "message": message}

    # -- SOP to Workflow authoring --------------------------------------------

    def _authoring_view(self, session: AuthoringSession) -> dict[str, Any]:
        draft = session.draft
        installed = self.runtime.agent.gateway.bridge.installed
        return {
            "ok": True,
            "session_id": session.session_id, "title": session.title,
            "status": session.status, "sop_kind": session.sop_kind,
            "sop_chars": len(session.sop_text),
            "turns": [turn.model_dump(mode="json") for turn in session.turns],
            "questions": list(session.questions), "problems": list(session.problems),
            "draft_text": None if draft is None else review_rendered(draft, installed),
            "run_fields": [] if draft is None else form_fields(draft, "web"),
            "settings_fields": [] if draft is None else settings_fields(draft),
            "settings": session.settings,
            "preview_arguments": session.preview_arguments,
            "preview": None if session.preview is None
            else session.preview.model_dump(mode="json"),
            "installed_as": session.installed_as,
        }

    def authoring_sessions(self) -> dict[str, Any]:
        return {"ok": True, "sessions": [
            {"session_id": item.session_id, "title": item.title, "status": item.status,
             "updated_at": item.updated_at}
            for item in self.authoring.sessions(self.runtime.actor)
        ]}

    def authoring_action(self, action: str, body: dict[str, Any]) -> dict[str, Any]:
        actor = self.runtime.actor
        try:
            if action == "start":
                pdf = body.get("pdf_base64")
                session = self.authoring.start(
                    actor, title=str(body.get("title") or "SOP"),
                    sop_text=None if pdf else str(body.get("sop_text") or ""),
                    pdf=base64.b64decode(str(pdf), validate=True) if pdf else None,
                )
            elif action == "get":
                session = self.authoring.load(str(body.get("session_id")), actor)
            elif action == "discuss":
                session = self.authoring.discuss(
                    str(body.get("session_id")), actor, str(body.get("message") or ""))
            elif action == "preview":
                arguments = body.get("arguments") or {}
                settings = body.get("settings") or {}
                if not isinstance(arguments, dict) or not isinstance(settings, dict):
                    return {"ok": False, "code": "authoring_preview_invalid"}
                with self.request_lock:
                    session = self.authoring.preview(
                        str(body.get("session_id")), actor, arguments, settings,
                        self.runtime.agent.gateway.bridge)
            elif action == "install":
                session, _path = self.authoring.install(str(body.get("session_id")), actor)
                view = self._authoring_view(session)
                view["restart_required"] = True
                return view
            else:
                return {"ok": False, "code": "authoring_action_unknown"}
        except AuthoringError as error:
            return {"ok": False, "code": error.code}
        except (ValueError, binascii.Error):
            return {"ok": False, "code": "authoring_request_invalid"}
        return self._authoring_view(session)

    def _turn_lock(self, session_id: str) -> threading.Lock:
        with self._session_guard:
            return self._turn_locks.setdefault(session_id, threading.Lock())

    def _record_lock(self, session_id: str) -> threading.Lock:
        with self._session_guard:
            return self._record_locks.setdefault(session_id, threading.Lock())

    def schedules_request(
        self, method: str, path: str, query: dict[str, list[str]], body: object
    ) -> tuple[int, dict[str, Any]]:
        """The Schedules panel's routes; see `host_runtime.schedule_web`."""
        from host_runtime import schedule_web
        from host_runtime.schedule_control import ScheduleControl

        loop = self.schedule_loop
        return schedule_web.handle(
            ScheduleControl(self.runtime, lock=self._one_at_a_time),
            method,
            path,
            query,
            body,
            loop_status=None if loop is None else loop.status(),
        )

    # -- what the pages ask for ---------------------------------------

    def about(self) -> dict[str, Any]:
        device = self.runtime.config.device
        persona = self.persona.load()
        return {
            "bridge_id": device.bridge_id,
            "actor": self.runtime.actor,
            "namespace": self.namespace or "",
            "kind": device.device_kind,
            "telegram": self.runtime.telegram is not None,
            "platform": self.runtime.platform is not None,
            "name": persona.name,
            "introduction": persona.introduction,
        }

    def readiness(self) -> dict[str, Any]:
        """Actionable local readiness without probing an external service."""
        assets = self.assets()
        gateway_ready = self._gateway_ready()
        backends = self.backends.statuses(gateway_available=gateway_ready)
        ready_backends = [item.label for item in backends if item.available]
        natural_ready = bool(ready_backends)
        return {
            "natural_language": {
                "status": "ready" if natural_ready else "setup_required",
                "action": (
                    "Ready backends: " + ", ".join(ready_backends) + "."
                    if natural_ready
                    else (
                        "Configure a Gateway model or install and sign in to a supported local CLI."
                    )
                ),
            },
            "shared_platform": {
                "configured": self.runtime.config.platform is not None,
                "action": (
                    "Open Shared platform to browse and synchronize selected assets."
                    if self.runtime.config.platform is not None
                    else "Configure a shared platform binding to install team capabilities."
                ),
            },
            "installed": {
                name: len(assets[name])
                for name in ("profiles", "skills", "workflows", "knowledge", "extensions")
            },
        }

    def _gateway_ready(self) -> bool:
        binding = self.runtime.config.models
        if binding is None or binding.routing_alias is None:
            return False
        endpoint = binding.catalog.endpoint(binding.routing_alias)
        if endpoint is None:
            return False
        if (
            binding.data_approval is None
            or "UNCLASSIFIED" not in binding.data_approval.approved_classes
        ):
            return False
        if endpoint.credential is None:
            return True
        environment = self.runtime.config.credential_environment().get(endpoint.credential.name)
        return bool(environment and os.environ.get(environment))

    def _gateway_conversation_text(self, result: GatewayConversationResult) -> str:
        if result.failure is not None and result.failure.code == "tool_loop_limit":
            return (
                f"這個回合已用完 {len(result.tools)} 次工具呼叫，工作還沒完成。"
                "目前做到的步驟已記錄在這段對話中；回覆「繼續」我會接著做。"
            )
        if result.failure is not None and result.failure.code == "empty_model_answer":
            return (
                "The LLM Gateway returned an empty answer (empty_model_answer). "
                "Retry the turn; if it repeats, inspect the Gateway model logs."
            )
        if result.failure is not None and result.failure.code == "model_unavailable":
            return (
                "The LLM Gateway request failed (model_unavailable). "
                "Check the configured model and Gateway status."
            )
        if result.failure is not None and result.failure.code in {
            "gateway_not_approved",
            "class_not_approved",
        }:
            return (
                "LLM Gateway data transfer is not approved for this request. "
                "Ask the host administrator to approve this exact Gateway and data class."
            )
        if result.failure is None or result.failure.code != "credential_unavailable":
            if result.failure is not None and result.text == (
                "The Personal Agent could not complete this turn."
            ):
                return f"{result.text} Reason: {result.failure.code}."
            return result.text
        binding = self.runtime.config.models
        endpoint = (
            None
            if binding is None or binding.routing_alias is None
            else binding.catalog.endpoint(binding.routing_alias)
        )
        variable = (
            None
            if endpoint is None or endpoint.credential is None
            else self.runtime.config.credential_environment().get(endpoint.credential.name)
        )
        if variable:
            return (
                f"LLM Gateway credential is unavailable. Set {variable} in the Agent "
                "process environment and restart the Agent."
            )
        return "LLM Gateway credential is unavailable. Check its mapping in Settings."

    def _settings_entry(self, manifest: WorkflowManifest) -> dict[str, Any]:
        identity = manifest.metadata.identity
        stored = self.workflow_settings_store.for_manifest(manifest)
        missing = [
            field.name for field in static_fields(manifest)
            if field.required and stored.get(field.name) is None and field.default is None
        ]
        return {
            "workflow": identity.model_dump(mode="json"),
            "description": manifest.description,
            "fields": settings_fields(manifest),
            "values": stored,
            "missing": missing,
        }

    def workflow_settings(self) -> dict[str, Any]:
        """Every installed Workflow that declares per-install settings."""
        try:
            entries = [
                self._settings_entry(manifest)
                for manifest in manifests(self.runtime.layout.workflows, WorkflowManifest)
                if static_fields(manifest)
            ]
        except WorkflowSettingsError as error:
            return {"ok": False, "code": "workflow_settings_unavailable", "message": str(error)}
        return {"ok": True, "workflows": entries}

    def save_workflow_settings(self, request: WorkflowSettingsUpdateRequest) -> dict[str, Any]:
        item = WorkflowSettingsUpdateRequest.model_validate(request)
        manifest = next(
            (
                candidate
                for candidate in manifests(self.runtime.layout.workflows, WorkflowManifest)
                if candidate.metadata.identity == item.workflow
            ),
            None,
        )
        if manifest is None:
            return {"ok": False, "code": "workflow_not_installed"}
        try:
            checked = validate_static_settings(manifest, item.values, complete=False)
            # Store what the person set; declared defaults stay in the manifest.
            self.workflow_settings_store.save(
                item.workflow,
                {name: value for name, value in item.values.items() if name in checked},
            )
        except WorkflowParameterError as error:
            return {"ok": False, "code": "workflow_settings_invalid", "message": str(error)}
        except WorkflowSettingsError as error:
            return {"ok": False, "code": "workflow_settings_refused", "message": str(error)}
        return {"ok": True, "workflow": self._settings_entry(manifest)}

    def workflow_options(self, request: WorkflowOptionsRequest) -> dict[str, Any]:
        """Choices for a `ref:` or `fn:` field given the answers so far."""
        item = WorkflowOptionsRequest.model_validate(request)
        manifest = next(
            (
                candidate
                for candidate in manifests(self.runtime.layout.workflows, WorkflowManifest)
                if candidate.metadata.identity == item.workflow
            ),
            None,
        )
        field = None if manifest is None else next(
            (candidate for candidate in manifest.parameters if candidate.name == item.field),
            None,
        )
        if manifest is None or field is None or not field.choices_source:
            return {"ok": False, "code": "workflow_field_unknown"}
        source = field.choices_source
        waiting = [
            name for name in ChoiceSources.needed(source) if item.answers.get(name) in (None, "")
        ]
        if waiting:
            return {"ok": True, "choices": [], "waiting_for": waiting}
        found = choice_sources(self.runtime.config, self.runtime.layout).resolve(
            manifest, source, item.answers
        )
        if found is None:
            return {
                "ok": True, "choices": [], "unavailable": True,
                "set": source.split(":", 1)[1].partition("?")[0],
            }
        return {
            "ok": True,
            "choices": [
                {"value": choice.value, "label": choice.label or choice.value}
                for choice in found
            ],
        }

    def available_models(self) -> dict[str, Any]:
        """List model names the configured Gateway serves, for the Settings picker.

        Only the saved endpoint is queried (never a browser-supplied URL),
        the credential comes from its environment variable and is never
        returned, and nothing but the model names is reported.
        """
        binding = self.runtime.config.models
        endpoint = (
            None if binding is None or binding.routing_alias is None
            else binding.catalog.endpoint(binding.routing_alias)
        )
        if endpoint is None or not endpoint.base_url:
            return {"ok": False, "code": "model_not_configured", "models": []}
        headers = {"Accept": "application/json"}
        if endpoint.credential is not None:
            variable = self.runtime.config.credential_environment().get(endpoint.credential.name)
            token = os.environ.get(variable) if variable else None
            if not token:
                return {"ok": False, "code": "credential_unavailable", "models": []}
            headers["Authorization"] = f"Bearer {token}"
        base_url = endpoint.base_url.rstrip("/")
        url = (
            base_url.removesuffix("/v1") + "/api/tags" if endpoint.provider == "ollama"
            else base_url + "/models"
        )
        try:
            reply = self.model_listing_transport.request("GET", url, None, headers, 10.0)
            try:
                payload = json.loads(b"".join(reply.chunks()) or b"{}")
            finally:
                reply.close()
        except (OSError, ValueError):
            return {"ok": False, "code": "gateway_unreachable", "models": []}
        if reply.status != 200 or not isinstance(payload, dict):
            return {"ok": False, "code": f"gateway_http_{reply.status}", "models": []}
        rows = payload.get("models" if endpoint.provider == "ollama" else "data") or []
        names = sorted({
            str(row.get("name" if endpoint.provider == "ollama" else "id"))
            for row in rows if isinstance(row, dict)
            and row.get("name" if endpoint.provider == "ollama" else "id")
        })
        return {"ok": True, "models": names[:500], "current": endpoint.model}

    def _gateway_configured(self) -> bool:
        binding = self.runtime.config.models
        return bool(
            binding is not None
            and binding.routing_alias is not None
            and binding.catalog.endpoint(binding.routing_alias) is not None
        )

    def settings(self) -> dict[str, Any]:
        """Current non-secret settings suitable for a local operator page."""
        binding = self.runtime.config.models
        endpoint = None
        if binding is not None and binding.routing_alias is not None:
            endpoint = binding.catalog.endpoint(binding.routing_alias)
        credential_environment = self.runtime.config.credential_environment()
        credential = None if endpoint is None else endpoint.credential
        return {
            "writable": self.config_path is not None,
            "restart_required": False,
            "persona": self.persona.load().model_dump(mode="json"),
            "context": self.conversation_context.load().model_dump(mode="json"),
            "telegram": self.telegram_settings(),
            "memory": {
                "scope": "session_only",
                "cross_session": False,
                "stored_messages": MAX_STORED_MESSAGES,
            },
            "model": {
                "configured": endpoint is not None,
                "data_approval": (
                    None
                    if binding is None or binding.data_approval is None
                    else {
                        "approval_ref": binding.data_approval.approval_ref,
                        "approved_classes": binding.data_approval.approved_classes,
                    }
                ),
                "alias": "" if endpoint is None else endpoint.alias,
                "provider": "" if endpoint is None else endpoint.provider,
                "model": "" if endpoint is None else endpoint.model,
                "declared_context_tokens": (
                    None if endpoint is None else endpoint.capabilities.max_context_tokens
                ),
                "base_url": "" if endpoint is None else endpoint.base_url or "",
                "credential_secret": "" if credential is None else credential.name,
                "credential_environment": (
                    "" if credential is None else credential_environment.get(credential.name, "")
                ),
                "credential_present": (
                    False
                    if credential is None
                    else bool(os.environ.get(credential_environment.get(credential.name, ""), ""))
                ),
                "require_local_model": (False if binding is None else binding.require_local_model),
            },
        }

    def telegram_settings(self) -> dict[str, Any]:
        status = telegram_status(self.runtime.config, self.runtime.layout)
        loop = self.telegram_loop
        status["running"] = loop is not None and loop.running
        status["failure"] = None if loop is None else loop.failure
        ingress = self.runtime.telegram
        allowed = {item["sender_id"] for item in status["senders"]}
        status["unknown_senders"] = [] if ingress is None else [
            {"sender_id": item.sender_id, "name": item.name, "seen": item.seen.isoformat()}
            for item in sorted(ingress.unmapped.values(), key=lambda item: item.seen,
                               reverse=True)
            if item.sender_id not in allowed
        ]
        return status

    # -- MCP servers (owner 2026-10-08) ------------------------------------

    def start_mcp(self) -> None:
        if self.runtime.mcp is not None:
            self.runtime.mcp.start()

    def mcp_servers(self) -> dict[str, Any]:
        hub = self.runtime.mcp
        return {"servers": [] if hub is None else hub.status()}

    def mcp_action(self, action: str, body: dict[str, Any]) -> dict[str, Any]:
        from pydantic import SecretStr

        from host_runtime.mcp_servers import McpServerConfig

        hub = self.runtime.mcp
        if hub is None:
            return {"ok": False, "code": "mcp_unavailable"}
        name = str(body.get("name") or "")
        try:
            if action == "save":
                config = McpServerConfig.model_validate(body.get("config"))
                secrets = {str(key): SecretStr(str(value))
                           for key, value in (body.get("secrets") or {}).items()}
                hub.save(config, secrets)
            elif action == "delete":
                hub.delete(name)
            elif action == "reconnect":
                hub.connect(name)
            else:
                return {"ok": False, "code": "mcp_request_invalid"}
        except ValueError as error:
            return {"ok": False, "code": "mcp_settings_invalid", "message": str(error)[:300]}
        return {"ok": True, **self.mcp_servers()}

    # -- experience review (docs/phases/EXPERIENCE_REVIEW.md, E1-E2) ---------

    def _experience_store(self) -> ExperienceStore:
        return ExperienceStore(self.runtime.layout.workspace_root)

    def experience_harvest(self) -> int:
        """Gather new cases from conversations, sandbox benchmarks and telemetry,
        and drop cases older than the retention setting."""
        workspace = self.runtime.layout.workspace_root
        store = self._experience_store()
        cases = from_conversations(self.runtime.state.conversations(self.runtime.actor,
                                                                    limit=500))
        boxes = self._sandboxes()
        if boxes is not None and boxes.root.is_dir():
            cases += from_benchmarks(boxes.root)
        cases += from_telemetry(workspace / "telemetry.sqlite")
        added = store.add(cases)
        store.prune(load_settings(workspace).retention_days)
        return added

    def _experience_rules(self, domain: str) -> str:
        """The rules that governed a domain's answers: the installed Knowledge
        Skill's guidance and the published vault's answer rules."""
        if domain != "knowledge":
            return ""
        installed = self.runtime.agent.gateway.bridge.installed.get(KNOWLEDGE_QUERY_SPEC.identity)
        handler = getattr(installed, "handler", None)
        catalog = getattr(handler, "catalog", None)
        parts = []
        skill = harness_skill(self.runtime.agent.gateway.router.commands.skills)
        found = next((s for s in self.runtime.agent.gateway.router.commands.skills.discover(
            skill.namespace) if s.metadata.identity == skill), None) if skill else None
        guidance = ((found.procedure or {}).get("answer_guidance") if found else None)
        if guidance:
            parts.append("Installed Knowledge Skill answer guidance:\n" + str(guidance))
        if catalog is not None and catalog.manifests():
            _, vault = catalog.get(catalog.manifests()[0].metadata.identity)
            parts.append(answer_rules_text(vault, "").replace("{{", "{").replace("}}", "}"))
        return "\n\n".join(part for part in parts if part)

    def experience_review(self) -> dict[str, Any]:
        """Harvest, then review the open groups; report only (E2)."""
        installed = self.runtime.agent.gateway.bridge.installed.get(KNOWLEDGE_QUERY_SPEC.identity)
        handler = getattr(installed, "handler", None)
        model, alias = getattr(handler, "model", None), getattr(handler, "alias", None)
        if model is None or alias is None:
            return {"ok": False, "code": "experience_review_unavailable"}
        added = self.experience_harvest()
        report = run_review(self._experience_store(), model, alias, self._experience_rules,
                            workspace=self.runtime.layout.workspace_root, harvested=added)
        self._experience_store().set_meta("last_review", report.started_at)
        return {"ok": True, "review_id": report.review_id, "findings": len(report.findings)}

    def experience(self) -> dict[str, Any]:
        workspace = self.runtime.layout.workspace_root
        store = self._experience_store()
        return {"ok": True, "settings": load_settings(workspace).model_dump(mode="json"),
                "open": len(store.cases("open")), "last_review": store.meta("last_review"),
                "review": latest_review(workspace)}

    def update_experience_settings(self, body: dict[str, Any]) -> dict[str, Any]:
        try:
            settings = ExperienceSettings.model_validate(body)
        except ValueError:
            return {"ok": False, "code": "experience_settings_invalid"}
        save_settings(self.runtime.layout.workspace_root, settings)
        self._experience_store().prune(settings.retention_days)
        return self.experience()

    def start_experience_review(self) -> dict[str, Any]:
        thread = threading.Thread(target=self.experience_review, name="experience-review",
                                  daemon=True)
        thread.start()
        return {"ok": True, "started": True}

    def start_experience_nightly(self, check_s: float = 1800.0) -> None:
        """Review once a night after 02:00 local time when there are new cases
        (owner, 2026-10-12)."""
        def loop() -> None:
            while True:
                time.sleep(check_s)
                try:
                    workspace = self.runtime.layout.workspace_root
                    if not load_settings(workspace).nightly:
                        continue
                    now = datetime.now().astimezone()
                    last = self._experience_store().meta("last_review") or ""
                    if now.hour < 2 or last[:10] == now.date().isoformat():
                        continue
                    self.experience_harvest()
                    if self._experience_store().cases("open"):
                        self.experience_review()
                except Exception:  # noqa: BLE001 - a failed night is retried the next
                    continue

        threading.Thread(target=loop, name="experience-nightly", daemon=True).start()

    def start_feedback_sync(self) -> None:
        """Send queued feedback to the Shared Platform while this runs."""
        from host_runtime.feedback_sync import FeedbackSync

        self.feedback_sync = FeedbackSync(self.runtime.state, lambda: self.runtime.platform)
        self.feedback_sync.start()

    def start_telegram(self) -> None:
        """Poll with the host's current Telegram ingress, if it has one."""
        if self.runtime.telegram is not None:
            self.telegram_loop = ResidentTelegram(self.runtime.telegram)
            self.telegram_loop.start()

    def update_telegram_settings(
        self, request: TelegramSettingsUpdate | TelegramSettingsForm
    ) -> dict[str, Any]:
        """Save the bot settings and replace the polling loop; no restart."""
        if self.config_path is None:
            return {"ok": False, "code": "settings_read_only"}
        if isinstance(request, TelegramSettingsForm):
            try:
                request = request.to_update(self.runtime.actor)
            except ValueError:
                return {"ok": False, "code": "telegram_actor_invalid"}
        with self._one_at_a_time:
            try:
                config = apply_telegram_settings(
                    self.config_path, self.runtime.layout, request,
                    store=self.user_environment,
                )
                ingress = build_telegram(
                    config, self.runtime.layout, self.runtime.agent, None
                )
            except TelegramSettingsError as error:
                return {"ok": False, "code": str(error)}
            except (OSError, ValueError):
                return {"ok": False, "code": "telegram_settings_refused"}
            self.runtime.config = config
            self.runtime.telegram = ingress
            previous, self.telegram_loop = self.telegram_loop, None

            def swap() -> None:
                # The old loop may be inside a long poll; two pollers on one
                # bot conflict, so the new one starts after the old one ends.
                if previous is not None:
                    previous.stop()
                self.start_telegram()

            threading.Thread(target=swap, name="telegram-swap", daemon=True).start()
        return {"ok": True, "restart_required": False, "telegram": self.telegram_settings()}

    def update_persona_settings(self, request: AgentPersonaUpdateRequest) -> dict[str, Any]:
        """Save local presentation guidance without changing runtime authority."""

        with self._one_at_a_time:
            saved = self.persona.save(request)
        return {"ok": True, "restart_required": False, "persona": saved.model_dump(mode="json")}

    def avatars(self) -> dict[str, Any]:
        """The pixel-art characters a person can pick, frames as data URIs."""
        return {"characters": list(catalog())}

    def user_preferences(self) -> dict[str, Any]:
        """This person's own Agent Web choices (owner 2026-10-07)."""
        return {"preferences": self.preferences.load(self.runtime.actor).model_dump(mode="json")}

    def update_user_preferences(self, request: UserPreferences) -> dict[str, Any]:
        with self._one_at_a_time:
            saved = self.preferences.save(self.runtime.actor, request)
        return {"ok": True, "preferences": saved.model_dump(mode="json")}

    def update_context_settings(self, request: ConversationContextSettings) -> dict[str, Any]:
        with self._one_at_a_time:
            saved = self.conversation_context.save(request)
        return {"ok": True, "restart_required": False, "context": saved.model_dump(mode="json")}

    def update_model_settings(self, request: ModelSettingsUpdateRequest) -> dict[str, Any]:
        """Validate and atomically save one provider-neutral model endpoint."""
        if self.config_path is None:
            return {
                "ok": False,
                "code": "settings_read_only",
                "restart_required": False,
            }
        checked = ModelSettingsUpdateRequest.model_validate(request)
        credential = (
            None if checked.credential_secret is None else {"name": checked.credential_secret}
        )
        model_binding = ModelBinding.model_validate(
            {
                "catalog": {
                    "endpoints": [
                        {
                            "alias": checked.alias,
                            "provider": checked.provider,
                            "model": checked.model,
                            "base_url": checked.base_url,
                            "credential": credential,
                            "capabilities": {
                                "reasoning": checked.reasoning,
                                "tool_calling": checked.tool_calling,
                                "structured_output": checked.structured_output,
                                "streaming": checked.streaming,
                                "vision": checked.vision,
                                "local": checked.local,
                                "max_context_tokens": checked.max_context_tokens,
                            },
                        }
                    ],
                    "routes": [{"name": "default", "alias": checked.alias}],
                },
                "routing_alias": checked.alias,
                "require_local_model": checked.require_local_model,
            }
        )
        with self._one_at_a_time:
            current = CompanyHostConfiguration.model_validate_json(
                self.config_path.read_text(encoding="utf-8-sig")
            )
            old_endpoint = (
                None
                if current.models is None or current.models.routing_alias is None
                else current.models.catalog.endpoint(current.models.routing_alias)
            )
            approval = None if current.models is None else current.models.data_approval
            old_credential_environment = next(
                (
                    item.environment_variable
                    for item in current.credentials
                    if old_endpoint is not None
                    and old_endpoint.credential is not None
                    and item.secret == old_endpoint.credential.name
                ),
                None,
            )
            # Model changes at the same approved Gateway keep working. A route,
            # provider or credential change needs a fresh host-config approval.
            if (
                approval is not None
                and old_endpoint is not None
                and old_endpoint.alias == checked.alias
                and old_endpoint.base_url == checked.base_url
                and old_endpoint.provider == checked.provider
                and (None if old_endpoint.credential is None else old_endpoint.credential.name)
                == checked.credential_secret
                and old_credential_environment == checked.credential_environment
            ):
                model_binding = ModelBinding.model_validate(
                    {
                        **model_binding.model_dump(mode="json"),
                        "data_approval": approval.model_dump(mode="json"),
                    }
                )
            old_model_secrets = {
                item.credential.name
                for item in (() if current.models is None else current.models.catalog.endpoints)
                if item.credential is not None
            }
            credentials = [
                item for item in current.credentials if item.secret not in old_model_secrets
            ]
            if checked.credential_secret is not None and checked.credential_environment is not None:
                credentials.append(
                    CredentialBinding(
                        secret=checked.credential_secret,
                        environment_variable=checked.credential_environment,
                    )
                )
            candidate = current.model_dump(mode="json")
            candidate["models"] = model_binding.model_dump(mode="json")
            candidate["credentials"] = [item.model_dump(mode="json") for item in credentials]
            updated = CompanyHostConfiguration.model_validate(candidate)
            write_atomically(
                self.config_path,
                updated.model_dump_json(indent=2).encode("utf-8") + b"\n",
            )
        projection = self.settings()
        projection.update({"ok": True, "restart_required": True})
        return projection

    def conversations(self, session_id: str | None = None) -> dict[str, Any]:
        records = self.runtime.state.conversations(self.runtime.actor)
        selected = (
            None
            if session_id is None
            else self.runtime.state.conversation(session_id, self.runtime.actor)
        )
        return {
            "conversations": [
                {
                    "session_id": item.session_id,
                    "title": item.title,
                    "updated_at": item.updated_at.isoformat(),
                    "messages": len(item.messages),
                    "backend": item.backend,
                }
                for item in records
            ],
            "selected": (None if selected is None else json.loads(selected.model_dump_json())),
        }

    def create_conversation(self) -> dict[str, Any]:
        now = datetime.now(UTC)
        record = ConversationRecord(
            session_id=f"conversation-{uuid.uuid4().hex}",
            actor=self.runtime.actor,
            title="New conversation",
            created_at=now,
            updated_at=now,
        )
        created = self.runtime.state.create_conversation(record)
        return {"conversation": json.loads(created.model_dump_json())}

    def delete_conversation(self, request: ConversationDeleteRequest) -> dict[str, Any]:
        item = ConversationDeleteRequest.model_validate(request)
        deleted = self.runtime.state.delete_conversation(item.session_id, self.runtime.actor)
        if deleted:
            self.attachments.delete_session(item.session_id)
        return {"ok": deleted, "code": None if deleted else "conversation_unknown"}

    def add_attachment(self, session_id: str, filename: str, data: bytes) -> dict[str, Any]:
        """Keep one file for this person's conversation (owner 2026-10-08)."""
        if self.runtime.state.conversation(session_id, self.runtime.actor) is None:
            return {"ok": False, "code": "conversation_unknown"}
        try:
            saved = self.attachments.add(session_id, filename, data)
        except AttachmentError as error:
            return {"ok": False, "code": error.code}
        return {"ok": True, "attachment": attachment_summary(saved)}

    def conversation_backends(self) -> dict[str, Any]:
        binding = self.runtime.config.models
        approval = None if binding is None else binding.data_approval
        issue = (
            "Host administrator approval for UNCLASSIFIED data is required"
            if approval is None or "UNCLASSIFIED" not in approval.approved_classes
            else None
        )
        return {
            "backends": [
                item.model_dump(mode="json")
                for item in self.backends.statuses(
                    gateway_available=self._gateway_ready(),
                    gateway_configured=self._gateway_configured(),
                    gateway_issue=issue,
                )
            ]
        }

    def select_conversation_backend(
        self, request: ConversationBackendSelectRequest
    ) -> dict[str, Any]:
        item = ConversationBackendSelectRequest.model_validate(request)
        statuses = {
            row.name: row
            for row in self.backends.statuses(
                gateway_available=self._gateway_ready(),
                gateway_configured=self._gateway_configured(),
            )
        }
        status = statuses[item.backend]
        if not status.selectable:
            return {"ok": False, "code": "backend_not_installed"}
        if item.backend != "gateway" and status.authentication != "ready":
            return {"ok": False, "code": "backend_authentication_required"}
        with self._record_lock(item.session_id):
            record = self.runtime.state.conversation(item.session_id, self.runtime.actor)
            if record is None:
                return {"ok": False, "code": "conversation_unknown"}
            classification = record.data_classification
            classified_by = record.classified_by
            if item.backend == "gateway":
                classification = "UNCLASSIFIED"
                classified_by = None
            elif classification != "PUBLIC":
                if not item.public_context:
                    return {"ok": False, "code": "public_context_required"}
                if record.messages:
                    return {"ok": False, "code": "public_context_requires_empty_session"}
                classification = "PUBLIC"
                classified_by = self.runtime.actor
            updated = record.model_copy(
                update={
                    "backend": item.backend,
                    "data_classification": classification,
                    "classified_by": classified_by,
                    "updated_at": datetime.now(UTC),
                }
            )
            saved = self.runtime.state.save_conversation(updated)
        return {"ok": True, "conversation": json.loads(saved.model_dump_json())}

    def authenticate_conversation_backend(
        self, request: ConversationBackendAuthenticationRequest
    ) -> dict[str, object]:
        item = ConversationBackendAuthenticationRequest.model_validate(request)
        return self.backends.authenticate(item.backend)

    def slash_commands(self) -> dict[str, Any]:
        return {"commands": [item.model_dump(mode="json") for item in COMMANDS]}

    def contribution_drafts(self) -> dict[str, Any]:
        return {
            "drafts": [
                json.loads(item.model_dump_json())
                for item in self.runtime.state.contribution_drafts(self.runtime.actor)
            ]
        }

    def create_contribution_draft(self, request: ContributionDraftCreateRequest) -> dict[str, Any]:
        """Capture evidence without creating, installing or publishing an asset."""
        item = ContributionDraftCreateRequest.model_validate(request)
        with self._record_lock(item.session_id):
            conversation = self.runtime.state.conversation(item.session_id, self.runtime.actor)
            if conversation is None:
                return {"ok": False, "code": "conversation_unknown"}
            if not conversation.messages:
                return {"ok": False, "code": "conversation_evidence_missing"}

            target: AssetIdentity | None = None
            proposed_name = None
            asset_kind: Literal["skill", "workflow", "knowledge", "platform"]
            if item.request_kind == "improvement":
                target = item.target
                if target is None:  # Closed request validation makes this unreachable.
                    return {"ok": False, "code": "target_required"}
                resolved = self._installed_contribution_target(target)
                if resolved is None:
                    return {"ok": False, "code": "target_not_installed"}
                asset_kind, owner = resolved
                namespace = target.namespace
            elif item.request_kind == "new_capability":
                if not self.namespace:
                    return {"ok": False, "code": "namespace_missing"}
                if item.candidate_kind is None:  # Closed request validation makes this unreachable.
                    return {"ok": False, "code": "candidate_kind_required"}
                asset_kind = item.candidate_kind
                proposed_name = item.proposed_name
                owner = Owner(type="user", id=self.runtime.actor)
                namespace = self.namespace
            else:
                if not self.namespace:
                    return {"ok": False, "code": "namespace_missing"}
                asset_kind = "platform"
                owner = Owner(type="user", id=self.runtime.actor)
                namespace = self.namespace

            evidence = tuple(
                ConversationExcerpt(
                    message_id=message.message_id,
                    role=message.role,
                    text=message.text,
                    trace=message.trace,
                )
                for message in conversation.messages[-20:]
            )
            draft = ContributionDraft(
                draft_id=f"contribution-{uuid.uuid4().hex}",
                request_kind=item.request_kind,
                actor=self.runtime.actor,
                namespace=namespace,
                owner=owner,
                asset_kind=asset_kind,
                target=target,
                proposed_name=proposed_name,
                summary=item.summary,
                expected_behavior=item.expected_behavior,
                actual_behavior=item.actual_behavior,
                acceptance_criteria=item.acceptance_criteria,
                source_session_id=conversation.session_id,
                evidence=evidence,
                created_at=datetime.now(UTC),
            )
            saved = self.runtime.state.create_contribution_draft(draft)
        return {"ok": True, "draft": json.loads(saved.model_dump_json())}

    def _installed_contribution_target(
        self, target: AssetIdentity | None
    ) -> tuple[Literal["skill", "workflow", "knowledge"], Owner] | None:
        if target is None:
            return None
        sources: tuple[tuple[Literal["skill", "workflow", "knowledge"], Path, type[Any]], ...] = (
            ("skill", self.runtime.layout.skills, SkillManifest),
            ("workflow", self.runtime.layout.workflows, WorkflowManifest),
            ("knowledge", self.runtime.layout.knowledge, KnowledgeManifest),
        )
        for kind, directory, model in sources:
            for manifest in manifests(directory, model):
                if manifest.metadata.identity == target:
                    return kind, manifest.metadata.owner
        return None

    @staticmethod
    def _replied_exchange(
        record: ConversationRecord, reply_to: str | None,
    ) -> tuple[ConversationMessage, ConversationMessage] | None:
        """The (question, answer) pair whose answer the user chose to reply to."""
        if reply_to is None:
            return None
        messages = record.messages
        for index, message in enumerate(messages):
            if (
                message.message_id == reply_to and message.role == "assistant"
                and index > 0 and messages[index - 1].role == "user"
            ):
                return messages[index - 1], message
        return None

    def conversation_feedback(self, request: ConversationFeedbackRequest) -> dict[str, Any]:
        """Record the user's rating and reason for one answer."""
        item = ConversationFeedbackRequest.model_validate(request)
        note = (item.note or "").strip() or None
        try:
            with self._record_lock(item.session_id):
                saved = self.runtime.state.set_message_feedback(
                    item.session_id, self.runtime.actor, item.message_id,
                    MessageFeedback(
                        rating=item.rating, note=note, updated_at=datetime.now(UTC)
                    ),
                    # Queued for the Shared Platform with the question and
                    # answer (owner 2026-10-08); sent now or once it answers.
                    queue=True,
                )
        except LocalStateError as error:
            return {"ok": False, "code": error.code}
        if self.feedback_sync is not None:
            self.feedback_sync.soon()
        message = next(m for m in saved.messages if m.message_id == item.message_id)
        return {
            "ok": True, "message_id": item.message_id,
            "feedback": None if message.feedback is None
            else message.feedback.model_dump(mode="json"),
        }

    def conversation_turn(self, request: ConversationTurnRequest) -> dict[str, Any]:
        item = ConversationTurnRequest.model_validate(request)
        with self._turn_lock(item.session_id):
            record = self.runtime.state.conversation(item.session_id, self.runtime.actor)
            if record is None:
                return {"ok": False, "code": "conversation_unknown"}
            try:
                attached = [self.attachments.get(item.session_id, file_id)
                            for file_id in item.attachments]
            except AttachmentError as error:
                return {"ok": False, "code": error.code}
            attachment_note, attachment_images = for_model(attached)
            started = datetime.now(UTC)
            if record.data_classification == "PUBLIC" and item.message.lstrip().startswith("/"):
                answer = {
                    "ok": False,
                    "answer": (
                        "Commands are unavailable in a PUBLIC conversation. "
                        "Start a Gateway session."
                    ),
                    "status": "needs_input",
                }
                slash = None
            else:
                try:
                    slash = parse_slash_command(item.message)
                except SlashCommandError as error:
                    answer = {
                        "ok": False,
                        "answer": f"Unsupported command ({error.code}). Type /help for commands.",
                        "status": "needs_input",
                    }
                    slash = None
                else:
                    if slash is not None:
                        with self._one_at_a_time:
                            answer = self._slash_command(slash)
                    else:
                        answer = {}
            namespace = self.namespace
            context_settings = self.conversation_context.load()
            quoted = self._replied_exchange(record, item.reply_to)
            if item.reply_to is not None and quoted is None and not answer:
                answer = {
                    "ok": False,
                    "answer": "找不到要回覆的那段對話，請重新選擇。",
                    "status": "needs_input",
                }
            recent = tuple(
                message for message in record.messages[-39:]
                if quoted is None or message.message_id not in {
                    quoted[0].message_id, quoted[1].message_id
                }
            )
            # A reply keeps the chosen exchange directly before the new
            # question, even when it is older than the recent-history window.
            raw_history = tuple(
                ModelMessage(role=message.role, text=with_tools(message))
                for message in (*recent, *(quoted or ()))
            ) + (ModelMessage(role="user", text=item.message),)
            routed_message = (
                item.message if quoted is None
                else f"{item.message}\n\n（延續先前的問題：{quoted[0].text}）"
            )
            try:
                history = prepare_history(raw_history, context_settings)
                history_error = False
            except ValueError:
                history = ()
                history_error = True
            if attached and history:
                # The files ride on the newest message, outside the typed
                # text's budget; the Gateway gives that message more room.
                history = (*history[:-1], ModelMessage(
                    role="user", text=f"{history[-1].text}\n\n{attachment_note}",
                    images=attachment_images))
            context_too_large = {
                "ok": False,
                "answer": (
                    "This message exceeds the conversation history budget. "
                    "Shorten it or increase the budget in Settings."
                ),
                "status": "needs_input",
                "code": "current_message_too_large",
            }
            if answer:
                pass
            elif attached and record.backend != "gateway":
                answer = {
                    "ok": False,
                    "answer": "附件目前只能用在 Gateway 對話；請改用 Gateway session。",
                    "status": "needs_input",
                }
            elif history_error and record.backend != "gateway":
                answer = context_too_large
            elif record.backend != "gateway":
                outbound = (
                    OutboundContext(
                        materials=tuple(
                            ContextMaterial(
                                material_id=f"message-{index}",
                                origin="history",
                                classification="PUBLIC",
                                classified_by=record.classified_by,
                                text=message.text,
                            )
                            for index, message in enumerate(history)
                        )
                    )
                    if record.data_classification == "PUBLIC"
                    else None
                )
                completed = self.backends.complete(
                    record.backend,
                    history,
                    # Local persona may contain private text; a PUBLIC session
                    # sends only explicitly declared conversation messages.
                    persona_guidance="",
                    outbound=outbound,
                    max_history_messages=context_settings.recent_messages,
                )
                answer = {
                    "ok": completed.status == "answered",
                    "answer": (
                        completed.text
                        if completed.status == "answered"
                        else f"The {record.backend} backend is unavailable ({completed.code})."
                    ),
                    "status": "answered" if completed.status == "answered" else "failed",
                    "backend": completed.model_dump(mode="json"),
                }
            elif not namespace:
                answer = {
                    "ok": False,
                    "answer": "No namespace is configured. Set `namespace` in host.json.",
                    "status": "needs_input",
                }
            else:
                trace = _trace()
                local = LocalAgentRequest(
                    ingress="local",
                    actor=self.runtime.actor,
                    bridge_id=self.runtime.config.device.bridge_id,
                    namespace=namespace,
                    message=item.message,
                    trace=trace,
                    session_id=item.session_id,
                )
                context = RequestContext(
                    trace=trace,
                    actor=self.runtime.actor,
                    namespace=namespace,
                    message=item.message,
                    channel="local",
                    session_id=item.session_id,
                )
                import asyncio

                # Known commands keep their deterministic path and never pay
                # for model selection. Ordinary language enters the bounded
                # tool loop with only recent local conversation text.
                # The turn is one Harness run (telemetry v0.2); an exception
                # leaves it incomplete, which the contract allows.
                turn_run = ExitStack()
                turn_run.enter_context(telemetry.run(
                    "conversation_turn", trace_id=trace.trace_id,
                    attributes={"ingress": "agent_web", "attachments": len(attached)}))
                matrix_intent = self._market_matrix_intent(item.message)
                named_knowledge = self._named_knowledge(routed_message)
                if named_knowledge is None and matrix_intent:
                    installed_knowledge = self.assets()["knowledge"]
                    if len(installed_knowledge) == 1:
                        named_knowledge = installed_knowledge[0]
                command_match = self.runtime.agent.gateway.router.commands.match(context)
                explicit_command = bool(DOT_COMMAND.match(item.message.strip()))
                if attached:
                    # Files are for the conversation and its tools to work on.
                    named_knowledge, command_match, explicit_command = None, None, False
                route = (
                    "command" if command_match is not None and explicit_command
                    else ("market_matrix" if matrix_intent else "knowledge_direct")
                    if named_knowledge is not None
                    else "command_rule" if command_match is not None
                    else "converse")
                telemetry.emit("routing.completed", state="routing", attributes={
                    "router": "agent_web", "route": route})
                if command_match is not None and explicit_command:
                    with self._one_at_a_time:
                        direct = asyncio.run(self.runtime.agent.handle(local))
                    answer = {
                        "ok": direct.refusal is None,
                        "answer": readable(direct),
                        "status": (
                            "needs_input"
                            if direct.decision is not None and direct.decision.kind == "needs_input"
                            else ("answered" if direct.refusal is None else "failed")
                        ),
                        "outcome": json.loads(direct.model_dump_json()),
                    }
                elif named_knowledge is not None:
                    answer = (
                        self._market_matrix_reply(named_knowledge)
                        if matrix_intent
                        else self._knowledge_reply(named_knowledge, routed_message)
                    )
                elif command_match is not None:
                    with self._one_at_a_time:
                        direct = asyncio.run(self.runtime.agent.handle(local))
                    answer = {
                        "ok": direct.refusal is None,
                        "answer": readable(direct),
                        "status": (
                            "needs_input"
                            if direct.decision is not None and direct.decision.kind == "needs_input"
                            else ("answered" if direct.refusal is None else "failed")
                        ),
                        "outcome": json.loads(direct.model_dump_json()),
                    }
                elif not attached and (
                    inferred_knowledge := self._skill_intended_knowledge(routed_message)
                ) is not None:
                    answer = self._knowledge_reply(inferred_knowledge, routed_message)
                elif history_error:
                    answer = context_too_large
                else:
                    conversational = asyncio.run(
                        self.runtime.agent.converse(
                            local,
                            history,
                            persona_guidance=self.persona.load().prompt_guidance(),
                            max_history_messages=context_settings.recent_messages,
                        )
                    )
                    result = conversational.conversation
                    answer = {
                        "tool_summary": tool_summary(result),
                        "ok": result is not None and result.status == "answered",
                        "answer": (
                            self._gateway_conversation_text(result)
                            if result is not None
                            else f"The request was refused ({conversational.refusal})."
                        ),
                        "status": result.status if result is not None else "failed",
                        "outcome": json.loads(conversational.model_dump_json()),
                    }
                telemetry.set_run(
                    outcome=answer.get("status"),
                    status="failed" if answer.get("status") == "failed" else "succeeded")
                turn_run.close()
            finished = datetime.now(UTC)
            outcome = answer.get("outcome")
            status = (
                answer.get("status")
                if answer.get("status") in {"answered", "needs_input", "failed"}
                else ("answered" if answer.get("ok") else "failed")
            )
            trace_data = outcome.get("trace") if isinstance(outcome, dict) else None
            # Append to the record as it is now: while this turn ran, the user
            # may have rated an answer, switched the backend or deleted it.
            record_lock = self._record_lock(item.session_id)
            record_lock.acquire()
            try:
                fresh = self.runtime.state.conversation(item.session_id, self.runtime.actor)
            except BaseException:
                record_lock.release()
                raise
            if fresh is None:
                record_lock.release()
                return {"ok": False, "code": "conversation_unknown"}
            record = fresh
            title = (
                item.message[:72] + ("…" if len(item.message) > 72 else "")
                if not record.messages
                else record.title
            )
            updated = record.model_copy(
                update={
                    "title": title,
                    "updated_at": max(finished, record.updated_at),
                    "messages": (
                        record.messages
                        + (
                            ConversationMessage(
                                message_id=f"message-{uuid.uuid4().hex}",
                                role="user",
                                text=item.message,
                                created_at=started,
                                status="submitted",
                                reply_to=None if quoted is None else quoted[1].message_id,
                                attachments=tuple(
                                    {"filename": file.filename, "kind": file.kind,
                                     "path": file.path}
                                    for file in attached
                                ),
                            ),
                            ConversationMessage(
                                message_id=f"message-{uuid.uuid4().hex}",
                                role="assistant",
                                text=str(answer["answer"]),
                                created_at=finished,
                                status=status,
                                tool_summary=answer.get("tool_summary"),
                                trace=(
                                    None
                                    if trace_data is None
                                    else TraceIdentifiers.model_validate(trace_data)
                                ),
                            ),
                        )
                    )[-MAX_STORED_MESSAGES:],
                }
            )
            try:
                saved = self.runtime.state.save_conversation(updated)
            finally:
                record_lock.release()
            problem = answer.pop("problem", None)
            draft = None
            if isinstance(problem, str):
                drafted = self.create_contribution_draft(
                    ContributionDraftCreateRequest(
                        session_id=saved.session_id,
                        request_kind="problem",
                        summary=problem,
                        expected_behavior=(
                            "A reviewer can identify and reproduce the expected behavior."
                        ),
                        actual_behavior=problem,
                        acceptance_criteria=(
                            "A reviewer can triage this report from its evidence.",
                        ),
                    )
                )
                draft = drafted.get("draft")
        return {
            "ok": answer.get("ok", False),
            "conversation": json.loads(saved.model_dump_json()),
            "answer": answer,
            "draft": draft,
            "approvals": self.approvals(item.session_id)["approvals"],
        }

    def _named_knowledge(self, message: str) -> dict[str, Any] | None:
        """Resolve an explicitly named installed source without model tool selection."""
        matches = []
        for item in self.assets()["knowledge"]:
            parts = [re.escape(part) for part in re.split(r"[-_\s]+", item["name"]) if part]
            if parts and re.search(
                r"(?<![A-Za-z0-9])" + r"[-_\s]*".join(parts) + r"(?![A-Za-z0-9])",
                message,
                re.IGNORECASE,
            ):
                matches.append(item)
        return matches[0] if len(matches) == 1 else None

    def _skill_intended_knowledge(self, message: str) -> dict[str, Any] | None:
        """Use one installed Skill's declared intent only with one exact Vault.

        A message that names local work (a URL, a local path or a file) is a
        task for the model and its tools, not a Knowledge question: the intent
        words a spec question shares with such a task ("product", "price")
        sent coding_v1's web tasks to the Knowledge harness (defect D1,
        2026-10-06). Questions without such references route as before."""
        if names_local_work(message):
            return None
        eligible = [
            item for item in self.assets()["skills"] if item["knowledge_harness_selectable"]
        ]
        knowledge = self.assets()["knowledge"]
        if len(eligible) != 1 or len(knowledge) != 1:
            return None
        candidate = eligible[0]
        skill = self.runtime.agent.gateway.router.commands.skills.get(
            candidate["namespace"], candidate["alias"]
        )
        if skill is None or not skill.procedure:
            return None
        try:
            procedure = KnowledgeProcedure.model_validate(skill.procedure)
        except ValueError:
            return None
        return (
            knowledge[0]
            if procedure.matches_intent(message)
            else None
        )

    def _knowledge_reply(self, selected: dict[str, Any], question: str) -> dict[str, Any]:
        eligible_skills = [
            item for item in self.assets()["skills"]
            if item["knowledge_harness_selectable"]
        ]
        selected_skill = (
            AssetIdentity(
                namespace=eligible_skills[0]["namespace"],
                name=eligible_skills[0]["name"],
                version=eligible_skills[0]["version"],
            )
            if len(eligible_skills) == 1 else None
        )
        result = self.ask_knowledge(
            KnowledgeAskRequest(
                asset=AssetIdentity(
                    namespace=selected["namespace"],
                    name=selected["name"],
                    version=selected["version"],
                ),
                question=question,
                skill=selected_skill,
            )
        )
        if not result["ok"]:
            return {
                "ok": False,
                "answer": result["answer"],
                "status": (
                    "needs_input"
                    if (result.get("harness") or {}).get("phase") == "needs_input"
                    else "failed"
                ),
                "outcome": result["outcome"],
                "harness": result.get("harness"),
                "evidence": result.get("evidence"),
            }
        record = KnowledgeAnswerRecord.model_validate(result["record"])
        answer = record.answer.text
        wiki_primary = record.citation_policy == "wiki_primary"
        if wiki_primary:
            sources = knowledge_source_lines(record.model_dump(mode="json"))
            if sources:
                answer += "\n\n來源：\n" + "\n".join(sources)
        else:
            sources = []
            for number in sorted(cited_numbers(record.answer.text)):
                citation = record.answer.passages[number - 1].citation
                if citation.raw_ref is not None:
                    sources.append(f"[{number}] {citation.raw_ref}")
            if sources:
                answer += "\n\nSources (Raw):\n" + "\n".join(sources)
        if result.get("harness") is not None:
            facet_status = (result.get("evidence") or {}).get("facet_status")
            kind = "Wiki/Raw" if wiki_primary else "Raw"
            answer += (
                f"\n\nEvidence check: {kind} citations and requested facets verified."
                if facet_status == "covered"
                else f"\n\nEvidence check: {kind} citations verified; facet coverage not assessed."
            )
        return {
            "ok": True,
            "answer": answer,
            "status": "answered",
            "outcome": result["outcome"],
            "harness": result.get("harness"),
            "evidence": result.get("evidence"),
        }

    @staticmethod
    def _market_matrix_intent(message: str) -> bool:
        lowered = message.casefold()
        return any(
            term in lowered
            for term in (
                "市場矩陣", "知識缺口矩陣", "產品市場對標", "產品與市場對標",
                "market matrix", "market alignment matrix",
            )
        )

    def _market_matrix_reply(self, selected: dict[str, Any]) -> dict[str, Any]:
        asset = AssetIdentity(
            namespace=selected["namespace"],
            name=selected["name"],
            version=selected["version"],
        )
        local = LocalCapabilityRequest(
            ingress="local",
            actor=self.runtime.actor,
            bridge_id=self.runtime.config.device.bridge_id,
            target=MARKET_MATRIX_SPEC.identity,
            arguments=MarketMatrixRequest(asset=asset).model_dump(mode="json"),
            trace=_trace(),
        )
        import asyncio

        outcome = asyncio.run(self.runtime.agent.execute_capability(local))
        if (
            outcome.refusal is not None
            or outcome.capability is None
            or outcome.capability.status != "succeeded"
        ):
            return {
                "ok": False,
                "answer": self.knowledge_harness._knowledge_failure_text(outcome),
                "status": "failed",
                "outcome": json.loads(outcome.model_dump_json()),
            }
        record = MarketMatrixRecord.model_validate(outcome.capability.data)
        assessments = tuple(
            assess_market_cell(record, cell.product_family, cell.market)
            for cell in record.cells
        )
        unresolved = sum(item.status == "needs_evidence" for item in assessments)
        labels = {item[0]: item[1] for item in PRODUCT_FAMILIES}
        markets = {item[0]: item[1] for item in TARGET_MARKETS}
        lines = [
            "RS Knowledge product × market evidence matrix (Raw discovery, not verified fit)",
            "",
            f"證據充分性：{unresolved}/{len(assessments)} 格仍需補證據；目前沒有已驗證的產品適配。",
            "",
            "| Product family | " + " | ".join(markets[item[0]] for item in TARGET_MARKETS) + " |",
            "| --- | " + " | ".join("---" for _ in TARGET_MARKETS) + " |",
        ]
        references: dict[tuple[str, int], int] = {}
        sources: list[str] = []
        by_pair = {(cell.product_family, cell.market): cell for cell in record.cells}
        for family, _label, _products in PRODUCT_FAMILIES:
            cells = []
            for market, _market_label, _aliases in TARGET_MARKETS:
                cell = by_pair[(family, market)]
                marks = []
                for evidence in cell.evidence:
                    key = (evidence.raw_ref, evidence.section)
                    if key not in references:
                        references[key] = len(sources) + 1
                        sources.append(
                            f"[{len(sources) + 1}] {evidence.raw_ref} §{evidence.section}"
                        )
                    marks.append(f"[{references[key]}]")
                lead = {
                    "nearby_mention": "附近提及",
                    "separate_passages": "分開段落",
                    "no_raw_match": "缺 Raw",
                }[cell.evidence_level]
                cells.append(lead + (" " + " ".join(marks) if marks else ""))
            lines.append("| " + labels[family] + " | " + " | ".join(cells) + " |")
        lines.extend(
            [
                "",
                "共同提及只代表檢索線索，尚不能證明產品或 option 適用該市場。"
                "每格仍需客戶情境與獨立驗證。",
                "",
                "按市場需補的知識：",
                *(
                    f"- {label}: {MARKET_QUESTIONS[key]}"
                    for key, label, _aliases in TARGET_MARKETS
                ),
                "按產品類別需補的規格與 option：",
                *(
                    f"- {label}: {PRODUCT_QUESTIONS[key]}"
                    for key, label, _products in PRODUCT_FAMILIES
                ),
                "請指定一格與具體需求，再深入查證及提出建議。",
            ]
        )
        if sources:
            lines.extend(["", "Sources (Raw):", *sources])
        return {
            "ok": True,
            "answer": "\n".join(lines),
            "status": "answered",
            "outcome": json.loads(outcome.model_dump_json()),
        }

    def _slash_command(self, command: SlashCommandInvocation) -> dict[str, Any]:
        """Dispatch known commands without model intent selection."""

        if command.name == "help":
            listing = "\n".join(f"{item.invocation} — {item.description}" for item in COMMANDS)
            return {"ok": True, "answer": listing, "status": "answered"}
        if command.name == "problem":
            summary = command.argument or "Problem reported from this conversation."
            return {
                "ok": True,
                "answer": "Saved a governed local problem draft for human review.",
                "status": "answered",
                "problem": summary,
            }
        if command.name == "wiki_query":
            if not command.argument:
                return self._command_needs_input("Usage: /wiki-query <question>")
            available = self.assets()["knowledge"]
            if len(available) != 1:
                return self._command_needs_input(
                    "Select exactly one installed Knowledge asset before using /wiki-query."
                )
            selected = available[0]
            return self._knowledge_reply(selected, command.argument)
        if command.name == "run_workflow":
            target_text, _, raw_arguments = command.argument.partition(" ")
            try:
                if target_text.isascii() and target_text.isdecimal() and int(target_text) > 0:
                    matches = [
                        manifest.metadata.identity
                        for manifest in manifests(self.runtime.layout.workflows, WorkflowManifest)
                        if manifest.run_alias == int(target_text)
                        and manifest.metadata.identity.namespace == self.namespace
                    ]
                    if len(matches) != 1:
                        return self._command_needs_input(
                            "Install exactly one Workflow with that number, or use its exact "
                            "<namespace>/<name>@<version> identity."
                        )
                    target = matches[0]
                else:
                    path, separator, version = target_text.rpartition("@")
                    namespace, slash, name = path.partition("/")
                    if not separator or not slash:
                        raise ValueError("missing exact workflow version")
                    target = AssetIdentity(namespace=namespace, name=name, version=version)
                arguments = self._command_arguments(raw_arguments)
            except (ValueError, TypeError, json.JSONDecodeError):
                return self._command_needs_input(
                    "Usage: /run [workflow] <number|namespace/name@version> {JSON arguments}"
                )
        else:
            workflow_name = {
                "wiki_convert": "wiki-convert",
                "wiki_ingest": "wiki-ingest",
                "wiki_lint": "wiki-lint",
            }[command.name]
            matches = [
                manifest.metadata.identity
                for manifest in manifests(self.runtime.layout.workflows, WorkflowManifest)
                if manifest.metadata.identity.name == workflow_name
            ]
            if len(matches) != 1:
                return self._command_needs_input(
                    f"Install exactly one {workflow_name} Workflow before using this command."
                )
            target = matches[0]
            try:
                arguments = self._command_arguments(command.argument)
            except (ValueError, TypeError, json.JSONDecodeError):
                return self._command_needs_input("Command arguments must be one JSON object.")
        result = self.launch_workflow(
            WorkflowLaunchRequest(
                workflow=target,
                arguments=arguments,
                idempotency_key=f"web-{uuid.uuid4().hex}",
            )
        )
        return {
            "ok": result["ok"],
            "answer": result["answer"],
            "status": "answered" if result["ok"] else "failed",
            "outcome": result["outcome"],
        }

    @staticmethod
    def _command_arguments(raw: str) -> dict[str, Any]:
        text = raw.strip()
        if not text:
            return {}
        if not text.startswith("{"):
            return {"args": text}
        decoded = json.loads(text)
        if not isinstance(decoded, dict):
            raise ValueError("workflow arguments are an object")
        return decoded

    @staticmethod
    def _command_needs_input(message: str) -> dict[str, Any]:
        return {"ok": False, "answer": message, "status": "needs_input"}

    def assets(self) -> dict[str, Any]:
        """What this machine has installed, and what it has run.

        Generic on purpose: a Skill and a Workflow are described by their own
        manifests, so a new one appears here the day it is installed without
        a line being written for it.
        """
        layout = self.runtime.layout
        authorization = load_authorization(self.runtime.config, layout)
        try:
            installed_script_tools = {
                item.manifest.metadata.identity.key: item
                for item in load_script_tools(layout.script_tools)
            }
        except (OSError, ValueError):
            installed_script_tools = {}

        def script_tool_projection(identity: AssetIdentity) -> dict[str, Any]:
            installed = installed_script_tools.get(identity.key)
            authorized = authorization is None or authorization.allows("capability", identity)
            if installed is None:
                return {
                    "identity": identity.model_dump(mode="json"),
                    "status": "not_installed",
                }
            manifest = installed.manifest
            return {
                "identity": identity.model_dump(mode="json"),
                "description": manifest.description,
                "runtime": manifest.runtime,
                "path": manifest.entrypoint,
                "side_effect": manifest.capability.side_effect,
                "approval_required": manifest.capability.policy.approval_required,
                "status": "installed" if authorized else "not_authorized",
            }

        active_skills = self.runtime.agent.gateway.router.commands.skills

        def harness_selectable(item: SkillManifest) -> bool:
            active = active_skills.get(item.metadata.identity.namespace, item.alias)
            return bool(
                active is not None
                and active.metadata.identity == item.metadata.identity
                and item.metadata.lifecycle in {"validated", "published"}
                and item.harness_guidance is not None
                and "knowledge" in item.harness_guidance.domains
                and any(
                    command.kind == "capability"
                    and command.target == KNOWLEDGE_QUERY_SPEC.identity
                    for command in item.commands
                )
            )

        skills = [
            {
                "namespace": item.metadata.identity.namespace,
                "name": item.metadata.identity.name,
                "version": item.metadata.identity.version,
                "alias": item.alias,
                "description": item.instructions,
                "procedure_markdown": item.instructions,
                "script_tools": [
                    script_tool_projection(identity) for identity in item.script_tools
                ],
                "commands": [
                    {
                        "name": command.name,
                        "kind": command.kind,
                        "target": (
                            f"{command.target.namespace}/{command.target.name}"
                            f"@{command.target.version}"
                        ),
                        "invocation": f"{item.alias}.{command.name} ",
                    }
                    for command in item.commands
                ],
                "default_command": item.default_command or "",
                "harness_guidance": (
                    None if item.harness_guidance is None
                    else item.harness_guidance.model_dump(mode="json")
                ),
                "knowledge_harness_selectable": harness_selectable(item),
            }
            for item in manifests(layout.skills, SkillManifest)
        ]
        workflows = [
            {
                "namespace": item.metadata.identity.namespace,
                "name": item.metadata.identity.name,
                "version": item.metadata.identity.version,
                "description": item.description,
                "steps": len(item.steps),
                "capabilities": list(item.dependencies.local_capabilities),
                "input_contract": item.input_contract,
                "output_contract": item.output_contract,
                "parameters": {
                    "editor": "fields" if item.parameters else "json_object",
                    "input_contract": item.input_contract,
                    **(
                        {
                            "fields": form_fields(item, "web")
                        }
                        if item.parameters
                        else {}
                    ),
                },
            }
            for item in manifests(layout.workflows, WorkflowManifest)
        ]
        knowledge_locations = {
            binding.asset.key: binding.vault_root for binding in self.runtime.config.knowledge
        }
        configured_knowledge = set(knowledge_locations)
        if authorization is not None:
            configured_knowledge.update(
                selection.asset.key
                for selection in authorization.selections
                if selection.kind == "knowledge"
            )
        knowledge = [
            {
                "namespace": item.metadata.identity.namespace,
                "name": item.metadata.identity.name,
                "version": item.metadata.identity.version,
                "domain": item.domain,
                "owner": f"{item.metadata.owner.type}:{item.metadata.owner.id}",
                "visibility": item.metadata.visibility,
                "location": knowledge_locations.get(
                    item.metadata.identity.key, "Installed by synchronized selection"
                ),
                "vault_ref": item.vault_ref,
            }
            for item in manifests(layout.knowledge, KnowledgeManifest)
            if item.metadata.identity.key in configured_knowledge
        ]
        active_key = None
        if layout.active_profile.is_file():
            try:
                active_key = ActiveAgentProfile.model_validate_json(
                    layout.active_profile.read_text(encoding="utf-8-sig")
                ).profile.key
            except Exception:  # noqa: BLE001 - doctor owns malformed local state
                active_key = None
        selected_profiles = set()
        if authorization is not None:
            selected_profiles = {
                item.asset.key for item in authorization.selections if item.kind == "agent"
            }
        profiles = [
            {
                "namespace": item.metadata.identity.namespace,
                "name": item.metadata.identity.name,
                "version": item.metadata.identity.version,
                "description": item.description,
                "active": item.metadata.identity.key == active_key,
            }
            for item in manifests(layout.agents, AgentProfile)
            if item.metadata.identity.key in selected_profiles
        ]
        snapshot = self.runtime.agent.snapshot(observed_at=datetime.now(UTC))
        runs = [
            {
                "run_id": run.run_id,
                "workflow": f"{run.workflow.namespace}/{run.workflow.name}",
                "status": run.status,
                "actor": run.actor,
            }
            for run in snapshot.runs[-25:]
        ]
        runs.reverse()
        return {
            "profiles": profiles,
            "skills": skills,
            "workflows": workflows,
            "knowledge": knowledge,
            "extensions": [
                {
                    **item.model_dump(mode="json"),
                    "documentation": item.description,
                    "lifecycle": (
                        "Staged locally; activation requires an explicit device approval."
                    ),
                }
                for item in extension_lifecycle(self.runtime)
            ],
            "runs": runs,
        }

    def activate_profile(self, request: AgentProfileActivationRequest) -> dict[str, Any]:
        """Persist one validated profile choice; restart applies its narrowed runtime."""
        item = AgentProfileActivationRequest.model_validate(request)
        authorization = load_authorization(self.runtime.config, self.runtime.layout)
        with self._one_at_a_time:
            try:
                active = activate_profile(
                    self.runtime.config,
                    self.runtime.layout,
                    authorization,
                    item.profile,
                    actor=self.runtime.actor,
                )
            except ProfileError as failure:
                return {"ok": False, "code": failure.code, "restart_required": False}
        return {
            "ok": True,
            "active": json.loads(active.model_dump_json()),
            "restart_required": True,
        }

    def platform(self) -> dict[str, Any]:
        """Published assets plus this Bridge's separate local state."""
        with self._one_at_a_time:
            return self._platform_projection().model_dump(mode="json")

    def _platform_projection(self) -> PlatformProjection:
        """Build one snapshot while the caller owns `_one_at_a_time`."""
        if self.runtime.platform is None:
            return PlatformProjection(
                configured=False,
                note="No shared platform is configured on this machine.",
            )
        import asyncio

        discovered = asyncio.run(self.runtime.platform.catalog())

        try:
            installed_assets = self.runtime.state.installed()
        except Exception:  # noqa: BLE001 - doctor owns the detailed diagnosis
            installed_assets = ()
        installed = {item.identity.key for item in installed_assets}

        decided = self.runtime.layout.authorization
        authorization = None
        if not decided.is_file():
            decisions_note = (
                "This machine has not synchronized its selections yet. Published assets "
                "are visible but are not authorized or installed by discovery."
            )
        else:
            from common.authorization import DeviceAuthorization

            try:
                authorization = DeviceAuthorization.model_validate_json(
                    decided.read_text(encoding="utf-8-sig")
                )
                decisions_note = (
                    "Published, authorized and installed are separate states. "
                    "Execution still requires Bridge policy permission."
                )
            except Exception:  # noqa: BLE001 - doctor owns the detailed diagnosis
                decisions_note = (
                    "The decisions this machine was given cannot be read; run `doctor`."
                )

        selected = {
            (item.kind, item.asset.key)
            for item in (() if authorization is None else authorization.selections)
        }
        catalog: list[PlatformCatalogProjection] = []
        if discovered.status == "answered" and discovered.reply is not None:
            for package in discovered.reply.packages:
                metadata = package.metadata
                identity = metadata.identity
                catalog.append(
                    PlatformCatalogProjection(
                        kind=package.kind,
                        namespace=identity.namespace,
                        name=identity.name,
                        version=identity.version,
                        description=package.description or "",
                        owner=f"{metadata.owner.type}:{metadata.owner.id}",
                        visibility=metadata.visibility,
                        lifecycle=metadata.lifecycle,
                        categories=metadata.categories,
                        dependencies=tuple(
                            f"{item.namespace}/{item.name}@{item.version}"
                            for item in metadata.dependencies
                        ),
                        runtime=metadata.compatibility.runtime or "",
                        platforms=metadata.compatibility.platforms,
                        published=True,
                        authorized=(package.kind, identity.key) in selected,
                        installed=identity.key in installed,
                    )
                )
            note = decisions_note
        else:
            code = discovered.failure.code if discovered.failure is not None else discovered.status
            note = (
                f"The shared catalog is unavailable ({code}). "
                "Already installed local assets remain available."
            )

        rows: list[PlatformDecisionProjection] = []
        # Every selection here is in force: the contract refuses to carry a
        # revoked one, so nothing has to read a status to know what applies.
        for selection in () if authorization is None else authorization.selections:
            asset = selection.asset
            key = (asset.namespace, asset.name, asset.version)
            rows.append(
                PlatformDecisionProjection(
                    kind=selection.kind,
                    namespace=asset.namespace,
                    name=asset.name,
                    version=asset.version,
                    actor=selection.actor,
                    installed=key in installed,
                )
            )
        binding = self.runtime.config.platform
        return PlatformProjection(
            configured=True,
            member_portal_url=(binding.member_portal_url or "") if binding is not None else "",
            connection=discovered.status,
            note=note,
            catalog=tuple(catalog),
            decisions=tuple(rows),
        )

    def synchronize(self) -> dict[str, Any]:
        """Run the existing verified sync only after this explicit action."""
        import asyncio

        with self._one_at_a_time:
            before = self._platform_projection()
            if self.runtime.platform is None:
                outcome = PlatformSyncResult(
                    status="refused",
                    failure=Failure(
                        code="platform_not_configured",
                        message="no shared platform is configured on this machine",
                    ),
                    before=before,
                    after=before,
                )
            else:
                synchronized = asyncio.run(
                    self.runtime.platform.synchronize(self.runtime.layout, self.runtime.state)
                )
                outcome = PlatformSyncResult(
                    status=synchronized.status,
                    failure=synchronized.failure,
                    installed=synchronized.installed,
                    selections=synchronized.selections,
                    before=before,
                    after=self._platform_projection(),
                )
        return outcome.model_dump(mode="json")

    def ask(
        self,
        message: str,
        namespace: str | None = None,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        chosen = namespace or self.namespace
        if not chosen:
            return {
                "ok": False,
                "answer": (
                    "No namespace is configured. Set `namespace` in host.json, "
                    "or name one with the request."
                ),
            }
        request = LocalAgentRequest(
            ingress="local",
            actor=self.runtime.actor,
            bridge_id=self.runtime.config.device.bridge_id,
            namespace=chosen,
            message=message,
            trace=_trace(),
            session_id=session_id,
        )
        import asyncio

        with self._one_at_a_time:
            outcome = asyncio.run(self.runtime.agent.handle(request))
        return {
            "ok": outcome.refusal is None,
            "answer": readable(outcome),
            "outcome": json.loads(outcome.model_dump_json()),
        }

    def launch_workflow(self, request: WorkflowLaunchRequest) -> dict[str, Any]:
        """Run one exact installed Workflow through the resident Agent."""
        item = WorkflowLaunchRequest.model_validate(request)
        manifest = next(
            (
                installed
                for installed in manifests(self.runtime.layout.workflows, WorkflowManifest)
                if installed.metadata.identity == item.workflow
            ),
            None,
        )
        arguments = (
            validate_run_parameters(manifest, item.arguments)
            if manifest is not None
            else item.arguments
        )
        device = self.runtime.config.device
        local = LocalWorkflowRequest(
            actor=self.runtime.actor,
            bridge_id=device.bridge_id,
            workflow=item.workflow,
            arguments=arguments,
            idempotency_key=item.idempotency_key,
            trace=_trace(),
        )
        import asyncio

        with self._one_at_a_time:
            outcome = asyncio.run(self.runtime.agent.execute_workflow(local))
        succeeded = (
            outcome.refusal is None
            and outcome.workflow is not None
            and outcome.workflow.run.status == "succeeded"
        )
        return {
            "ok": succeeded,
            "answer": readable(outcome),
            "outcome": json.loads(outcome.model_dump_json()),
        }

    def knowledge_pipeline(self) -> dict[str, Any]:
        """What the Knowledge tab may offer: the configured base vaults."""
        binding = self.runtime.config.knowledge_pipeline
        return {"enabled": binding is not None,
                "bases": [item.name for item in binding.vaults] if binding else []}

    def pipeline_call(self, step: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """One pipeline step through the Agent, as the person who pressed it."""
        spec = PIPELINE_STEPS.get(step)
        if spec is None or self.runtime.config.knowledge_pipeline is None:
            return {"ok": False, "code": "unknown_pipeline_step"}
        local = LocalCapabilityRequest(
            ingress="local", actor=self.runtime.actor,
            bridge_id=self.runtime.config.device.bridge_id, target=spec.identity,
            arguments=arguments, trace=_trace())
        import asyncio

        outcome = asyncio.run(self.runtime.agent.execute_capability(local))
        if outcome.refusal is not None:
            return {"ok": False, "code": str(outcome.refusal)}
        capability = outcome.capability
        if capability is None or capability.status != "succeeded":
            failure = capability.failure if capability is not None else None
            return {"ok": False, "code": failure.code if failure else "pipeline_step_failed"}
        return {"ok": True, "data": capability.data}

    def publish_knowledge(self, base: str, candidate_root: str) -> dict[str, Any]:
        """Publish a merged candidate as the base's new version (K3.4). Only a
        person's confirmed click reaches this; the model has no such tool."""
        if self.config_path is None or self.runtime.config.knowledge_pipeline is None:
            return {"ok": False, "code": "publish_unavailable"}
        with self._one_at_a_time:
            try:
                result = publish_candidate(self.config_path, self.runtime.layout, base,
                                           candidate_root, self.runtime.actor)
            except PublishError as error:
                return {"ok": False, "code": error.code}
        return {"ok": True, "restart_required": True, "data": result.model_dump(mode="json")}

    def _sandboxes(self) -> Sandboxes | None:
        binding = self.runtime.config.knowledge_pipeline
        if binding is None:
            return None
        return Sandboxes(self.runtime.layout.workspace_root,
                         root=Path(binding.sandbox_root) if binding.sandbox_root else None)

    def start_benchmark(self, sandbox_id: str, sets: list[str]) -> dict[str, Any]:
        """Run the chosen question sets in the background (collaboration C3)."""
        boxes = self._sandboxes()
        binding = self.runtime.config.knowledge_pipeline
        if boxes is None or binding is None:
            return {"ok": False, "code": "knowledge_pipeline_disabled"}
        try:
            info, sandbox = boxes.open(sandbox_id)
        except SandboxError as error:
            return {"ok": False, "code": error.code}
        if not sets or not all(isinstance(name, str) for name in sets):
            return {"ok": False, "code": "no_question_sets"}
        entry = next((v for v in binding.vaults if v.name == info.base_name), None)
        fallback = (Path(entry.questions_root) if entry and entry.questions_root
                    else Path(info.base_root) / "checks" / "questions")
        skill = harness_skill(self.runtime.agent.gateway.router.commands.skills)
        run_id = f"bench-{datetime.now(UTC).strftime('%Y%m%dT%H%M%S')}-{uuid.uuid4().hex[:4]}"
        thread = threading.Thread(target=run_benchmark, daemon=True, kwargs={
            "ask": lambda request, catalog: self.knowledge_harness.ask(request, catalog=catalog),
            "sandbox_id": sandbox_id, "sandbox": sandbox, "project": Vault(Path(info.base_root)),
            "sets": tuple(sets), "actor": self.runtime.actor, "skill": skill,
            "questions_fallback": fallback, "run_id": run_id})
        thread.start()
        return {"ok": True, "run_id": run_id}

    def _pipeline(self) -> KnowledgePipeline | None:
        """The pipeline for merge and push; no model is needed for either."""
        binding = self.runtime.config.knowledge_pipeline
        boxes = self._sandboxes()
        if binding is None or boxes is None:
            return None
        return KnowledgePipeline(
            boxes, {item.name: Path(item.root) for item in binding.vaults},
            questions_roots={item.name: Path(item.questions_root)
                             for item in binding.vaults if item.questions_root},
            maintainers={item.name: tuple(item.maintainers) for item in binding.vaults})

    def start_push(self, sandbox_id: str, sets: list[str],
                   resolutions: dict[str, str]) -> dict[str, Any]:
        """Merge, benchmark and, when the gate passes, write into the project
        vault, in the background (collaboration C4)."""
        pipeline = self._pipeline()
        if pipeline is None:
            return {"ok": False, "code": "knowledge_pipeline_disabled"}
        try:
            info, _ = pipeline.sandboxes.open(sandbox_id)
        except SandboxError as error:
            return {"ok": False, "code": error.code}
        if not pipeline.may_push(info.base_name, self.runtime.actor):
            return {"ok": False, "code": "not_a_maintainer"}
        chosen = {key: value for key, value in resolutions.items()
                  if value in ("sandbox", "published")}
        push_id = f"push-{datetime.now(UTC).strftime('%Y%m%dT%H%M%S')}-{uuid.uuid4().hex[:4]}"
        skill = harness_skill(self.runtime.agent.gateway.router.commands.skills)
        thread = threading.Thread(target=run_push, daemon=True, args=(pipeline,), kwargs={
            "ask": lambda request, catalog: self.knowledge_harness.ask(request, catalog=catalog),
            "sandbox_id": sandbox_id, "actor": self.runtime.actor, "sets": tuple(sets),
            "resolutions": chosen, "skill": skill, "push_id": push_id,
            "questions_fallback": pipeline.questions_roots.get(info.base_name)})
        thread.start()
        return {"ok": True, "push_id": push_id}

    def push_status(self, sandbox_id: str) -> dict[str, Any]:
        boxes = self._sandboxes()
        if boxes is None:
            return {"ok": False, "code": "knowledge_pipeline_disabled"}
        try:
            _, sandbox = boxes.open(sandbox_id)
        except SandboxError as error:
            return {"ok": False, "code": error.code}
        return {"ok": True, "push": latest_push(sandbox)}

    def refresh_knowledge(self, base: str) -> dict[str, Any]:
        """Stage the project vault as the Agent's next Knowledge version."""
        if self.config_path is None:
            return {"ok": False, "code": "refresh_unavailable"}
        with self._one_at_a_time:
            try:
                result = refresh_from_project(self.config_path, self.runtime.layout, base,
                                              self.runtime.actor)
            except PublishError as error:
                return {"ok": False, "code": error.code}
        return {"ok": True, "restart_required": True, "data": result.model_dump(mode="json")}

    def skill_assist(self, sandbox_id: str, path: str, current: str,
                     turns: list[dict[str, Any]]) -> dict[str, Any]:
        """One reply of the Skill assistant; it proposes, the person saves."""
        pipeline = self._pipeline()
        if pipeline is None:
            return {"ok": False, "code": "knowledge_pipeline_disabled"}
        if not (path == "CLAUDE.md" or re.fullmatch(
                r"skills/[A-Za-z0-9][A-Za-z0-9._-]*/SKILL\.md", path)):
            return {"ok": False, "code": "not_a_rule_file"}
        try:
            _, vault = pipeline.sandboxes.open(sandbox_id)
            chat = [Turn.model_validate(turn) for turn in turns]
        except (SandboxError, ValueError):
            return {"ok": False, "code": "skill_assist_request_invalid"}
        installed = self.runtime.agent.gateway.bridge.installed.get(KNOWLEDGE_QUERY_SPEC.identity)
        model = getattr(getattr(installed, "handler", None), "model", None)
        alias = getattr(getattr(installed, "handler", None), "alias", None)
        if model is None or alias is None:
            return {"ok": False, "code": "skill_assist_unavailable"}
        guide = pipeline.skill_guide()
        answering = "mode: answer" in current or path.startswith("skills/ask-")
        scope = re.search(r"^applies_to:\s*(raw/\S+)", current, re.MULTILINE)
        sample = None
        if scope and not answering:
            folder = vault.root / scope.group(1)
            first = next(iter(sorted(folder.rglob("*.md"))), None) if folder.is_dir() else None
            if first is not None:
                sample = first.read_text(encoding="utf-8", errors="ignore")
        try:
            reply = assist(model, alias, guide=guide.guide,
                           template=guide.answer_template if answering else guide.ingest_template,
                           path=path, current=current, sample=sample, turns=chat, trace=_trace())
        except (RuntimeError, ValueError) as error:
            return {"ok": False, "code": f"skill_assist_failed:{error}"[:80]}
        return {"ok": True, **reply.model_dump(mode="json")}

    def benchmark_status(self, sandbox_id: str) -> dict[str, Any]:
        boxes = self._sandboxes()
        if boxes is None:
            return {"ok": False, "code": "knowledge_pipeline_disabled"}
        try:
            _, sandbox = boxes.open(sandbox_id)
        except SandboxError as error:
            return {"ok": False, "code": error.code}
        return {"ok": True, "report": latest_benchmark(sandbox)}

    def ask_knowledge(self, request: KnowledgeAskRequest) -> dict[str, Any]:
        """Ask one exact installed Knowledge version through Bridge policy."""
        with telemetry.run("knowledge_query", attributes={"ingress": "agent_web"}):
            result = self._ask_knowledge(request)
            telemetry.set_run(outcome=result.get("status"),
                              status="succeeded" if result.get("ok") else "failed")
            return result

    def _ask_knowledge(self, request: KnowledgeAskRequest) -> dict[str, Any]:
        # The Knowledge Harness is shared with the conversation's tool route
        # (harness unification U5): host_runtime/knowledge_harness.py.
        return self.knowledge_harness.ask(request)


class _Handler(BaseHTTPRequestHandler):
    server: "AgentWebServer"  # noqa: UP037 - the class is defined below
    protocol_version = "HTTP/1.1"

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - base signature
        """Nothing. A request here carries the team's own words."""
        return None

    # -- the guards ----------------------------------------------------

    def _host_is_loopback(self) -> bool:
        host = (self.headers.get("Host") or "").rsplit(":", 1)[0].strip("[]")
        return host in ("127.0.0.1", "localhost", "::1")

    def _authorized(self) -> bool:
        header = self.headers.get("Authorization") or ""
        if not header.startswith(BEARER):
            return False
        return hmac.compare_digest(header[len(BEARER) :].strip(), self.server.token)

    def _send(self, status: int, body: bytes, kind: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        # Nothing here may be framed, embedded or sniffed into something else.
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: int, payload: Mapping[str, Any]) -> None:
        self._send(
            status,
            json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8"),
            "application/json; charset=utf-8",
        )

    def _refuse_unread(self, status: int, payload: Mapping[str, Any]) -> None:
        """Refuse a POST whose body has not been read, reading it first.

        Closing a connection with request bytes still unread makes Windows
        send a reset instead of a normal close, and the reset can reach the
        client before it has read this answer: it then sees "connection
        aborted" rather than the refusal. A body within the normal limit is
        read and dropped; anything else is not read, and the connection is
        closed after the answer.
        """
        try:
            length = int(self.headers.get("Content-Length") or "0")
        except ValueError:
            length = -1
        if 0 <= length <= MAX_BODY_BYTES:
            self.rfile.read(length)
        else:
            self.close_connection = True
        self._json(status, payload)

    def _schedule_route(self, method: str, path: str, query: str) -> None:
        """Scheduled-task routes, after the loopback and token guards."""
        from host_runtime.schedule_web import origin_allowed

        if not origin_allowed(self.headers.get("Origin")):
            refusal = {"error": "this interface answers its own page only"}
            if method == "POST":
                self._refuse_unread(403, refusal)
            else:
                self._json(403, refusal)
            return
        body: object = None
        if method == "POST":
            try:
                length = int(self.headers.get("Content-Length") or "0")
            except ValueError:
                self._json(400, {"error": "the request did not say how long it was"})
                return
            if length > MAX_BODY_BYTES:
                self._json(413, {"error": "that is larger than a request to an Agent"})
                return
            try:
                body = json.loads(self.rfile.read(length) or b"{}")
            except (ValueError, TypeError):
                self._json(400, {"error": "the request was not valid JSON"})
                return
        try:
            status, payload = self.server.web.schedules_request(
                method, path, parse_qs(query), body
            )
        except Exception as failure:  # noqa: BLE001 - a page shows everything
            status, payload = 500, {"error": f"schedules: {type(failure).__name__}"}
        self._json(status, payload)

    # -- the routes ----------------------------------------------------

    def do_GET(self) -> None:  # noqa: N802 - the base class's spelling
        if not self._host_is_loopback():
            self._json(403, {"error": "this interface answers on the loopback address only"})
            return
        parsed = urlparse(self.path)
        if parsed.path in ("/", "/index.html"):
            # The page itself is let in by the token in the address, because
            # a browser cannot be asked to set a header on its first visit.
            # Everything the page then asks for needs the header.
            given = parse_qs(parsed.query).get("token", [""])[0]
            if not hmac.compare_digest(given, self.server.token):
                self._send(401, b"Open the address this command printed.", "text/plain")
                return
            self._send(200, self.server.page(), "text/html; charset=utf-8")
            return
        # Redacted harness telemetry, read by Atlas without the page token
        # (owner 2026-10-08); see host_runtime/telemetry_api.py.
        if telemetry_api.handle(self, parsed.path, parsed.query):
            return
        if not self._authorized():
            self._json(401, {"error": "this request carried no usable token"})
            return
        if parsed.path.startswith("/api/schedules"):
            self._schedule_route("GET", parsed.path, parsed.query)
            return
        web = self.server.web
        if parsed.path == "/api/about":
            self._json(200, web.about())
        elif parsed.path == "/api/readiness":
            self._json(200, web.readiness())
        elif parsed.path == "/api/knowledge/pipeline":
            self._json(200, web.knowledge_pipeline())
        elif parsed.path == "/api/experience":
            self._json(200, web.experience())
        elif parsed.path == "/api/knowledge/push":
            query = parse_qs(parsed.query)
            self._json(200, web.push_status((query.get("sandbox_id") or [""])[0]))
        elif parsed.path == "/api/knowledge/benchmark":
            query = parse_qs(parsed.query)
            self._json(200, web.benchmark_status((query.get("sandbox_id") or [""])[0]))
        elif parsed.path == "/api/settings":
            self._json(200, web.settings())
        elif parsed.path == "/api/avatars":
            self._json(200, web.avatars())
        elif parsed.path == "/api/preferences":
            self._json(200, web.user_preferences())
        elif parsed.path == "/api/settings/models":
            self._json(200, web.available_models())
        elif parsed.path == "/api/authoring":
            self._json(200, web.authoring_sessions())
        elif parsed.path == "/api/drafts":
            self._json(200, web.drafts())
        elif parsed.path == "/api/approvals/external":
            self._json(200, web.external_approvals())
        elif parsed.path == "/api/approvals":
            session_id = parse_qs(parsed.query).get("session_id", [None])[0]
            self._json(200, web.approvals(session_id))
        elif parsed.path == "/api/mcp":
            self._json(200, web.mcp_servers())
        elif parsed.path == "/api/settings/workflows":
            self._json(200, web.workflow_settings())
        elif parsed.path == "/api/backends":
            self._json(200, web.conversation_backends())
        elif parsed.path == "/api/commands":
            self._json(200, web.slash_commands())
        elif parsed.path == "/api/conversations":
            session_id = parse_qs(parsed.query).get("session_id", [None])[0]
            self._json(200, web.conversations(session_id))
        elif parsed.path == "/api/contributions":
            self._json(200, web.contribution_drafts())
        elif parsed.path == "/api/assets":
            self._json(200, web.assets())
        elif parsed.path == "/api/platform":
            self._json(200, web.platform())
        else:
            self._json(404, {"error": "no such page"})

    def do_POST(self) -> None:  # noqa: N802 - the base class's spelling
        if not self._host_is_loopback():
            refusal = {"error": "this interface answers on the loopback address only"}
            self._refuse_unread(403, refusal)
            return
        if not self._authorized():
            self._refuse_unread(401, {"error": "this request carried no usable token"})
            return
        path = urlparse(self.path).path
        if path.startswith("/api/schedules"):
            self._schedule_route("POST", path, "")
            return
        if path not in (
            "/api/ask",
            "/api/platform/sync",
            "/api/profiles/activate",
            "/api/workflows/run",
            "/api/knowledge/ask",
            "/api/knowledge/pipeline/call",
            "/api/knowledge/pipeline/publish",
            "/api/knowledge/benchmark/start",
            "/api/knowledge/push/start",
            "/api/knowledge/refresh",
            "/api/knowledge/skill-assist",
            "/api/experience/settings",
            "/api/experience/review",
            "/api/settings/model",
            "/api/settings/telegram",
            "/api/mcp/save",
            "/api/mcp/delete",
            "/api/mcp/reconnect",
            "/api/settings/workflows",
            "/api/workflow-options",
            "/api/settings/persona",
            "/api/settings/context",
            "/api/preferences",
            "/api/attachments",
            "/api/conversations",
            "/api/conversations/delete",
            "/api/conversations/turn",
            "/api/conversations/feedback",
            "/api/conversations/backend",
            "/api/backends/authenticate",
            "/api/contributions",
            "/api/approvals/decide",
            "/api/drafts/install",
            "/api/drafts/delete",
            *AUTHORING_ROUTES,
        ):
            self._refuse_unread(404, {"error": "no such page"})
            return
        try:
            length = int(self.headers.get("Content-Length") or "0")
        except ValueError:
            self._json(400, {"error": "the request did not say how long it was"})
            return
        limit = (
            MAX_SOP_UPLOAD_BYTES if path == "/api/authoring/start"
            else MAX_ATTACHMENT_REQUEST_BYTES
            if path in ("/api/attachments", "/api/knowledge/pipeline/call")
            else MAX_BODY_BYTES
        )
        if length > limit:
            self._json(413, {"error": "that is larger than a request to an Agent"})
            return
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except (ValueError, TypeError):
            self._json(400, {"error": "the request was not valid JSON"})
            return
        if path == "/api/knowledge/pipeline/call":
            if not isinstance(body, dict) or not isinstance(body.get("arguments", {}), dict):
                self._json(400, {"ok": False, "code": "pipeline_request_invalid"})
                return
            try:
                result = self.server.web.pipeline_call(
                    str(body.get("step") or ""), dict(body.get("arguments") or {}))
            except Exception as failure:  # noqa: BLE001 - a page shows everything
                result = {"ok": False, "code": f"pipeline_error:{type(failure).__name__}"}
            self._json(200, result)
            return
        if path == "/api/knowledge/push/start":
            if not isinstance(body, dict) or not isinstance(body.get("sets"), list) \
                    or not isinstance(body.get("resolutions", {}), dict):
                self._json(400, {"ok": False, "code": "push_request_invalid"})
                return
            self._json(200, self.server.web.start_push(
                str(body.get("sandbox_id") or ""), [str(x) for x in body["sets"]],
                {str(k): str(v) for k, v in dict(body.get("resolutions") or {}).items()}))
            return
        if path == "/api/experience/settings":
            self._json(200, self.server.web.update_experience_settings(
                body if isinstance(body, dict) else {}))
            return
        if path == "/api/experience/review":
            self._json(200, self.server.web.start_experience_review())
            return
        if path == "/api/knowledge/skill-assist":
            if not isinstance(body, dict) or not isinstance(body.get("turns"), list):
                self._json(400, {"ok": False, "code": "skill_assist_request_invalid"})
                return
            self._json(200, self.server.web.skill_assist(
                str(body.get("sandbox_id") or ""), str(body.get("path") or ""),
                str(body.get("current") or ""), list(body["turns"])))
            return
        if path == "/api/knowledge/refresh":
            if not isinstance(body, dict):
                self._json(400, {"ok": False, "code": "refresh_request_invalid"})
                return
            self._json(200, self.server.web.refresh_knowledge(str(body.get("base") or "")))
            return
        if path == "/api/knowledge/benchmark/start":
            if not isinstance(body, dict) or not isinstance(body.get("sets"), list):
                self._json(400, {"ok": False, "code": "benchmark_request_invalid"})
                return
            self._json(200, self.server.web.start_benchmark(
                str(body.get("sandbox_id") or ""), list(body["sets"])))
            return
        if path == "/api/knowledge/pipeline/publish":
            if not isinstance(body, dict):
                self._json(400, {"ok": False, "code": "publish_request_invalid"})
                return
            self._json(200, self.server.web.publish_knowledge(
                str(body.get("base") or ""), str(body.get("candidate_root") or "")))
            return
        if path in ("/api/drafts/install", "/api/drafts/delete"):
            if not isinstance(body, dict):
                self._json(400, {"ok": False, "code": "draft_request_invalid"})
                return
            result = self.server.web.draft_action(
                path.rsplit("/", 1)[1], str(body.get("candidate_id") or ""))
            self._json(200 if result.get("ok") else 409, result)
            return
        if path == "/api/approvals/decide":
            if not isinstance(body, dict):
                self._json(400, {"ok": False, "code": "approval_request_invalid"})
                return
            result = self.server.web.decide_approval(
                str(body.get("approval_id") or ""), str(body.get("decision") or ""))
            self._json(200 if result.get("ok") else 409, result)
            return
        if path in AUTHORING_ROUTES:
            if not isinstance(body, dict):
                self._json(400, {"ok": False, "code": "authoring_request_invalid"})
                return
            result = self.server.web.authoring_action(path.rsplit("/", 1)[1], body)
            self._json(200 if result.get("ok") else 409, result)
            return
        if path == "/api/settings/model":
            try:
                settings = ModelSettingsUpdateRequest.model_validate(body)
                result = self.server.web.update_model_settings(settings)
            except (OSError, ValueError, TypeError):
                self._json(400, {"error": "the request was not valid model settings"})
                return
            self._json(200 if result.get("ok") else 409, result)
            return
        if path in ("/api/mcp/save", "/api/mcp/delete", "/api/mcp/reconnect"):
            if not isinstance(body, dict):
                self._json(400, {"ok": False, "code": "mcp_request_invalid"})
                return
            result = self.server.web.mcp_action(path.rsplit("/", 1)[1], body)
            self._json(200 if result.get("ok") else 409, result)
            return
        if path == "/api/settings/telegram":
            try:
                telegram = TelegramSettingsForm.model_validate(body)
            except (ValueError, TypeError):
                self._json(400, {"ok": False, "code": "telegram_sender_invalid"})
                return
            result = self.server.web.update_telegram_settings(telegram)
            self._json(200 if result.get("ok") else 409, result)
            return
        if path == "/api/workflow-options":
            try:
                options = WorkflowOptionsRequest.model_validate(body)
            except (ValueError, TypeError):
                self._json(400, {"error": "the request was not a valid options query"})
                return
            result = self.server.web.workflow_options(options)
            self._json(200 if result["ok"] else 404, result)
            return
        if path == "/api/settings/workflows":
            try:
                update = WorkflowSettingsUpdateRequest.model_validate(body)
            except (ValueError, TypeError):
                self._json(400, {"error": "the request was not valid workflow settings"})
                return
            result = self.server.web.save_workflow_settings(update)
            self._json(200 if result["ok"] else 400, result)
            return
        if path == "/api/attachments":
            if not isinstance(body, dict):
                self._json(400, {"ok": False, "code": "attachment_request_invalid"})
                return
            try:
                data = base64.b64decode(str(body.get("data") or ""), validate=True)
            except (ValueError, binascii.Error):
                self._json(400, {"ok": False, "code": "attachment_request_invalid"})
                return
            result = self.server.web.add_attachment(
                str(body.get("session_id") or ""), str(body.get("filename") or ""), data)
            self._json(200 if result["ok"] else 400, result)
            return
        if path == "/api/preferences":
            try:
                preferences = UserPreferences.model_validate(body)
                result = self.server.web.update_user_preferences(preferences)
            except (OSError, ValueError, TypeError):
                self._json(400, {"error": "the request was not a known avatar"})
                return
            self._json(200, result)
            return
        if path == "/api/settings/persona":
            try:
                persona = AgentPersonaUpdateRequest.model_validate(body)
                result = self.server.web.update_persona_settings(persona)
            except (OSError, ValueError, TypeError):
                self._json(400, {"error": "the request was not valid persona settings"})
                return
            self._json(200, result)
            return
        if path == "/api/settings/context":
            try:
                context_settings = ConversationContextSettings.model_validate(body)
                result = self.server.web.update_context_settings(context_settings)
            except (OSError, ValueError, TypeError):
                self._json(400, {"error": "the request was not valid context settings"})
                return
            self._json(200, result)
            return
        if path == "/api/conversations":
            try:
                ConversationCreateRequest.model_validate(body)
            except (ValueError, TypeError):
                self._json(400, {"error": "conversation creation requires an empty request"})
                return
            self._json(201, self.server.web.create_conversation())
            return
        if path == "/api/conversations/delete":
            try:
                deletion = ConversationDeleteRequest.model_validate(body)
            except (ValueError, TypeError):
                self._json(400, {"error": "the request was not a valid conversation deletion"})
                return
            result = self.server.web.delete_conversation(deletion)
            self._json(200 if result["ok"] else 404, result)
            return
        if path == "/api/conversations/turn":
            try:
                turn = ConversationTurnRequest.model_validate(body)
            except (ValueError, TypeError):
                self._json(400, {"error": "the request was not a valid conversation turn"})
                return
            result = self.server.web.conversation_turn(turn)
            self._json(200 if result.get("code") is None else 404, result)
            return
        if path == "/api/conversations/feedback":
            try:
                feedback = ConversationFeedbackRequest.model_validate(body)
            except (ValueError, TypeError):
                self._json(400, {"error": "the request was not valid answer feedback"})
                return
            result = self.server.web.conversation_feedback(feedback)
            self._json(200 if result["ok"] else 404, result)
            return
        if path == "/api/conversations/backend":
            try:
                selection = ConversationBackendSelectRequest.model_validate(body)
            except (ValueError, TypeError):
                self._json(400, {"error": "the request was not a valid backend selection"})
                return
            result = self.server.web.select_conversation_backend(selection)
            self._json(200 if result.get("ok") else 409, result)
            return
        if path == "/api/backends/authenticate":
            try:
                authentication = ConversationBackendAuthenticationRequest.model_validate(body)
            except (ValueError, TypeError):
                self._json(400, {"error": "the request was not a valid backend authentication"})
                return
            result = self.server.web.authenticate_conversation_backend(authentication)
            self._json(200 if result.get("ok") else 409, result)
            return
        if path == "/api/contributions":
            try:
                contribution = ContributionDraftCreateRequest.model_validate(body)
            except (ValueError, TypeError):
                self._json(400, {"error": "the request was not a valid contribution draft"})
                return
            result = self.server.web.create_contribution_draft(contribution)
            self._json(201 if result.get("ok") else 409, result)
            return
        if path == "/api/platform/sync":
            try:
                PlatformSyncRequest.model_validate(body)
            except (ValueError, TypeError):
                self._json(
                    400,
                    {"error": "synchronization requires an empty synchronization request"},
                )
                return
            try:
                self._json(200, self.server.web.synchronize())
            except Exception as failure:  # noqa: BLE001 - a page shows everything
                self._json(
                    500,
                    {"error": f"synchronization did not finish: {type(failure).__name__}"},
                )
            return
        if path == "/api/profiles/activate":
            try:
                activation = AgentProfileActivationRequest.model_validate(body)
            except (ValueError, TypeError):
                self._json(400, {"error": "the request was not a valid profile activation"})
                return
            try:
                self._json(200, self.server.web.activate_profile(activation))
            except Exception as failure:  # noqa: BLE001 - a page shows everything
                self._json(
                    500,
                    {"error": (f"profile activation did not finish: {type(failure).__name__}")},
                )
            return
        if path == "/api/workflows/run":
            try:
                launch = WorkflowLaunchRequest.model_validate(body)
            except (ValueError, TypeError):
                self._json(400, {"error": "the request was not a valid Workflow launch"})
                return
            try:
                self._json(200, self.server.web.launch_workflow(launch))
            except WorkflowParameterError as failure:
                self._json(400, {"code": "workflow_parameters_invalid", "error": str(failure)})
            except Exception as failure:  # noqa: BLE001 - a page shows everything
                self._json(
                    500,
                    {"error": f"the Workflow did not finish: {type(failure).__name__}"},
                )
            return
        if path == "/api/knowledge/ask":
            try:
                question = KnowledgeAskRequest.model_validate(body)
            except (ValueError, TypeError):
                self._json(400, {"error": "the request was not a valid Knowledge question"})
                return
            try:
                self._json(200, self.server.web.ask_knowledge(question))
            except Exception as failure:  # noqa: BLE001 - a page shows everything
                self._json(
                    500,
                    {"error": f"the Knowledge question did not finish: {type(failure).__name__}"},
                )
            return
        try:
            message = str(body["message"]).strip()
        except (ValueError, KeyError, TypeError):
            self._json(400, {"error": "the request was not a message"})
            return
        if not message:
            self._json(400, {"error": "an empty request asks nothing"})
            return
        namespace = body.get("namespace") or None
        try:
            self._json(200, self.server.web.ask(message, namespace))
        except Exception as failure:  # noqa: BLE001 - a page shows everything
            self._json(
                200,
                {
                    "ok": False,
                    "answer": f"The request did not finish: {type(failure).__name__}: {failure}",
                },
            )


class AgentWebServer(ThreadingHTTPServer):
    """The loopback server, its token and the page it serves."""

    daemon_threads = True
    allow_reuse_address = False

    def __init__(
        self,
        web: AgentWeb,
        *,
        port: int = 0,
        token: str | None = None,
        page: Callable[[], bytes] | None = None,
    ) -> None:
        self.web = web
        # Made afresh each run: a token that outlived the process would be a
        # standing key to this machine's Agent lying in somebody's history.
        self.token = token if token is not None else secrets.token_urlsafe(32)
        self._page = page
        super().__init__(("127.0.0.1", port), _Handler)

    def page(self) -> bytes:
        if self._page is not None:
            return self._page()
        from host_runtime.web_page import PAGE

        return PAGE.encode("utf-8")

    @property
    def address(self) -> str:
        host, port = self.server_address[0], self.server_address[1]
        name = host.decode() if isinstance(host, bytes) else host
        return f"http://{name}:{port}/?token={self.token}"

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.shutdown()
        self.server_close()
