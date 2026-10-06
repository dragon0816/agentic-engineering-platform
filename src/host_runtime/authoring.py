"""Workflow authoring sessions (owner design B, 2026-10-06; SOP_TO_WORKFLOW W5).

One durable record per effort to turn an SOP into a Workflow, under
`<workspace>/authoring/<id>/`: the SOP (an uploaded PDF is kept beside the
record), the discussion, the current draft, the open questions, the settings
the owner entered for this computer and the last preview.

    drafting -> needs_input -> ready -> previewed -> installed

The model drafts and asks; it never approves or installs. `install` is a
host action reached only from the owner's Agent Web page: it requires a
preview of exactly the current draft that changed nothing and failed
nowhere, writes the Workflow as published with the owner's approval, its
settings, and the grants its steps need, and asks for a restart.
"""

from __future__ import annotations

import hashlib
import json
import secrets
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import Field, JsonValue

from capabilities.runtime import CapabilityGrant, InstalledCapabilities, LocalPolicy
from capabilities.workflow_author.conversation import AuthoringTurn, author_turn
from capabilities.workflow_author.handlers import sop_pdf_text
from common.assets import WorkflowManifest, WorkflowStep
from common.base import Contract, Symbol, Text
from common.execution import TraceIdentifiers
from host_runtime.workflow_settings import WorkflowSettingsStore
from host_runtime.workspace import documents, write_atomically
from models.contracts import ModelClient
from workflow.dispatch import BridgeExecutor
from workflow.engine import InstalledWorkflows, WorkflowEngine, WorkflowPreview

AuthoringStatus = Literal["drafting", "needs_input", "ready", "previewed", "installed"]
MAX_SOP_BYTES = 20 * 1024 * 1024
SESSION_FILE = "session.json"


class AuthoringError(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class AuthoringSession(Contract):
    session_id: Symbol
    actor: Symbol
    created_at: Text
    updated_at: Text
    title: Text
    sop_kind: Literal["pdf", "text"]
    sop_sha256: Text
    sop_text: Text
    turns: tuple[AuthoringTurn, ...] = ()
    questions: tuple[Text, ...] = ()
    problems: tuple[Text, ...] = ()
    draft: WorkflowManifest | None = None
    settings: dict[Symbol, JsonValue] = Field(default_factory=dict)
    preview: WorkflowPreview | None = None
    preview_arguments: dict[Symbol, JsonValue] = Field(default_factory=dict)
    preview_of: Text | None = None
    status: AuthoringStatus = "drafting"
    installed_as: Text | None = None


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _digest(manifest: WorkflowManifest) -> str:
    return hashlib.sha256(manifest.model_dump_json().encode("utf-8")).hexdigest()


class AuthoringStudio:
    def __init__(
        self,
        root: Path,
        *,
        installed: InstalledCapabilities,
        model: Callable[[], ModelClient | None],
        model_alias: str,
        local_only: bool,
        namespace: str,
        workflows_dir: Path,
        grants_file: Path,
        settings_store: WorkflowSettingsStore,
    ) -> None:
        self.root = root
        self.installed = installed
        self._model = model
        self.model_alias = model_alias
        self.local_only = local_only
        self.namespace = namespace
        self.workflows_dir = workflows_dir
        self.grants_file = grants_file
        self.settings_store = settings_store

    # -- records ---------------------------------------------------------

    def _path(self, session_id: str) -> Path:
        if not session_id.replace("-", "").isalnum():
            raise AuthoringError("authoring_session_unknown")
        return self.root / session_id / SESSION_FILE

    def load(self, session_id: str, actor: str) -> AuthoringSession:
        path = self._path(session_id)
        if not path.is_file():
            raise AuthoringError("authoring_session_unknown")
        session = AuthoringSession.model_validate_json(path.read_text(encoding="utf-8"))
        if session.actor != actor:
            raise AuthoringError("authoring_session_unknown")
        return session

    def _save(self, session: AuthoringSession) -> AuthoringSession:
        stamped = session.model_copy(update={"updated_at": _now()})
        path = self._path(stamped.session_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        write_atomically(path, stamped.model_dump_json(indent=2).encode("utf-8"))
        return stamped

    def sessions(self, actor: str) -> list[AuthoringSession]:
        found = []
        for path in sorted(self.root.glob(f"*/{SESSION_FILE}")):
            try:
                session = AuthoringSession.model_validate_json(path.read_text(encoding="utf-8"))
            except ValueError:
                continue
            if session.actor == actor:
                found.append(session)
        return sorted(found, key=lambda item: item.updated_at, reverse=True)

    # -- the flow ----------------------------------------------------------

    def start(
        self, actor: str, *, title: str, sop_text: str | None = None,
        pdf: bytes | None = None,
    ) -> AuthoringSession:
        if (sop_text is None) == (pdf is None):
            raise AuthoringError("authoring_sop_missing")
        session_id = f"sop-{datetime.now(UTC):%Y%m%d-%H%M%S}-{secrets.token_hex(3)}"
        folder = self.root / session_id
        folder.mkdir(parents=True)
        if pdf is not None:
            if len(pdf) > MAX_SOP_BYTES or not pdf.startswith(b"%PDF"):
                raise AuthoringError("authoring_sop_not_a_pdf")
            stored = folder / "sop.pdf"
            stored.write_bytes(pdf)
            text = sop_pdf_text(stored)
            if not text:
                raise AuthoringError("authoring_sop_unreadable")
            raw, kind = pdf, "pdf"
        else:
            assert sop_text is not None
            text = sop_text.strip()
            if not text:
                raise AuthoringError("authoring_sop_missing")
            raw, kind = text.encode("utf-8"), "text"
        session = AuthoringSession(
            session_id=session_id, actor=actor, created_at=_now(), updated_at=_now(),
            title=title.strip() or "SOP", sop_kind=kind,
            sop_sha256=hashlib.sha256(raw).hexdigest(), sop_text=text,
        )
        return self.discuss(self._save(session).session_id, actor, None)

    def discuss(self, session_id: str, actor: str, message: str | None) -> AuthoringSession:
        session = self.load(session_id, actor)
        if session.status == "installed":
            raise AuthoringError("authoring_session_installed")
        model = self._model()
        if model is None:
            raise AuthoringError("authoring_model_unavailable")
        turns = session.turns + (
            (AuthoringTurn(role="owner", text=message.strip()),) if message and message.strip()
            else ()
        )
        answer = author_turn(
            session.sop_text, turns, session.draft, self.installed, model=model,
            model_alias=self.model_alias, local_only=self.local_only,
            trace=TraceIdentifiers(trace_id=f"authoring-{session_id}",
                                   request_id=f"authoring-{len(turns)}", span_id="authoring"),
            namespace=self.namespace,
        )
        reply = answer.reply + (
            "\n" + "\n".join(f"- {question}" for question in answer.questions)
            if answer.questions else ""
        )
        draft = answer.workflow or session.draft
        status: AuthoringStatus = (
            "needs_input" if answer.questions or draft is None else "ready"
        )
        return self._save(session.model_copy(update={
            "turns": (*turns, AuthoringTurn(role="agent", text=reply)),
            "questions": answer.questions, "problems": answer.problems, "draft": draft,
            "status": status,
            # A changed draft needs a new preview before it can be installed.
            "preview": session.preview if draft == session.draft else None,
        }))

    def preview(
        self, session_id: str, actor: str, arguments: dict[str, JsonValue],
        settings: dict[str, JsonValue], bridge: BridgeExecutor,
    ) -> AuthoringSession:
        session = self.load(session_id, actor)
        if session.draft is None:
            raise AuthoringError("authoring_no_draft")
        draft = session.draft
        workflows = InstalledWorkflows()
        workflows.register(draft)
        # The grants install would add, and nothing else: the preview shows
        # what the installed Workflow would do, for this actor only.
        trial = BridgeExecutor(
            bridge.installed,
            LocalPolicy(self._grants(draft, actor, f"authoring-preview:{session_id}")),
            timeout_seconds=bridge.timeout_seconds,
        )
        engine = WorkflowEngine(workflows, trial, settings_provider=lambda _manifest: settings)
        import asyncio

        from common.execution import RequestContext

        context = RequestContext(
            trace=TraceIdentifiers(trace_id=f"authoring-{session_id}",
                                   request_id="preview", span_id="preview"),
            actor=actor, namespace=self.namespace, channel="agent-web",
            message="preview a drafted Workflow",
        )
        shown = asyncio.run(engine.preview(context, draft.metadata.identity, arguments))
        return self._save(session.model_copy(update={
            "preview": shown, "preview_arguments": arguments, "settings": settings,
            "preview_of": _digest(draft),
            "status": "previewed" if shown.status == "previewed" else session.status,
        }))

    def install(self, session_id: str, actor: str) -> tuple[AuthoringSession, Path]:
        """The owner's approval. Never reachable by the model."""
        session = self.load(session_id, actor)
        draft = session.draft
        if (
            draft is None or session.preview is None or session.status != "previewed"
            or session.preview.status != "previewed" or session.preview_of != _digest(draft)
        ):
            raise AuthoringError("authoring_preview_required")
        identity = draft.metadata.identity
        name = f"{identity.namespace}__{identity.name}__{identity.version}.json"
        target = self.workflows_dir / name
        if target.exists():
            raise AuthoringError("authoring_workflow_exists")
        metadata = draft.metadata.model_dump(mode="json")
        metadata.update({
            "lifecycle": "published",
            "business_approval": {"status": "approved", "reviewer": actor,
                                  "evidence": f"authoring-session:{session_id}"},
            "validation_refs": [f"authoring-preview:{session_id}:{session.preview_of}"],
        })
        published = WorkflowManifest.model_validate(
            {**draft.model_dump(mode="json"), "metadata": metadata})
        self.workflows_dir.mkdir(parents=True, exist_ok=True)
        write_atomically(target, (json.dumps(published.model_dump(mode="json"),
                                             ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
        if session.settings:
            self.settings_store.save(identity, session.settings)
        self._add_grants(published, actor, f"authoring-session:{session_id}")
        installed = self._save(session.model_copy(update={
            "status": "installed",
            "installed_as": f"{identity.namespace}/{identity.name}@{identity.version}",
        }))
        return installed, target

    # -- grants ------------------------------------------------------------

    def _grants(
        self, manifest: WorkflowManifest, actor: str, ref: str
    ) -> tuple[CapabilityGrant, ...]:
        grants: dict[tuple[str, str, str], CapabilityGrant] = {}
        for step in manifest.steps:
            if not isinstance(step, WorkflowStep):
                raise AuthoringError("authoring_nested_workflow")
            binding = self.installed.get(step.capability)
            if binding is None:
                raise AuthoringError("authoring_capability_missing")
            grants[step.capability.key] = CapabilityGrant(
                actor=actor, asset=binding.spec.identity,
                permissions=binding.spec.policy.required_permissions,
                policy_refs=binding.spec.policy.policy_refs, approval_ref=ref,
            )
        return tuple(grants.values())

    def _add_grants(self, manifest: WorkflowManifest, actor: str, ref: str) -> None:
        existing = (
            [CapabilityGrant.model_validate(item) for item in documents(self.grants_file)]
            if self.grants_file.is_file() else []
        )
        have = {(grant.actor, grant.asset.key) for grant in existing}
        added = [grant for grant in self._grants(manifest, actor, ref)
                 if (grant.actor, grant.asset.key) not in have]
        if not added:
            return
        payload = [grant.model_dump(mode="json") for grant in (*existing, *added)]
        write_atomically(self.grants_file, (json.dumps(payload, ensure_ascii=False, indent=2)
                                            + "\n").encode("utf-8"))
