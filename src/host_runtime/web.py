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

import hmac
import json
import os
import secrets
import threading
import uuid
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import TracebackType
from typing import Any, Self
from urllib.parse import parse_qs, urlparse

from agent.contracts import ActiveAgentProfile, AgentProfile
from agent.skills import SkillManifest
from capabilities.knowledge_query.handlers import KNOWLEDGE_QUERY_SPEC
from common.assets import WorkflowManifest
from common.execution import Failure, TraceIdentifiers
from common.local_agent import LocalAgentRequest, LocalCapabilityRequest, LocalWorkflowRequest
from extensions.package import PortableExtensionPackage
from extensions.runtime import ExtensionLifecycleStore
from host_runtime.answers import readable
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
)
from host_runtime.host import HostRuntime, load_authorization
from host_runtime.profiles import ProfileError, activate_profile
from host_runtime.workspace import documents, write_atomically
from knowledge.evolution import KnowledgeAnswerRecord, KnowledgeManifest, KnowledgeQueryRequest

#: Anything larger than this is not a request to an Agent.
MAX_BODY_BYTES = 256 * 1024
BEARER = "Bearer "
#: The only addresses this ever binds to or answers for.
LOOPBACK = ("127.0.0.1", "localhost", "[::1]", "::1")


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
    ) -> None:
        self.runtime = runtime
        self.namespace = namespace if namespace is not None else runtime.config.namespace
        self.config_path = config_path
        # One request at a time. The Agent's state is one SQLite file and a
        # capability may hold a workbook; two at once would be two runs
        # against the same things.
        self._one_at_a_time = threading.Lock()

    # -- what the pages ask for ---------------------------------------

    def about(self) -> dict[str, Any]:
        device = self.runtime.config.device
        return {
            "bridge_id": device.bridge_id,
            "actor": self.runtime.actor,
            "namespace": self.namespace or "",
            "kind": device.device_kind,
            "telegram": self.runtime.telegram is not None,
            "platform": self.runtime.platform is not None,
        }

    def readiness(self) -> dict[str, Any]:
        """Actionable local readiness without probing an external service."""
        assets = self.assets()
        binding = self.runtime.config.models
        natural_ready = binding is not None and binding.routing_alias is not None
        return {
            "natural_language": {
                "status": "ready" if natural_ready else "setup_required",
                "action": (
                    "Natural-language routing is configured."
                    if natural_ready
                    else "Configure a routing model in Settings. Deterministic commands still work."
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
            "model": {
                "configured": endpoint is not None,
                "alias": "" if endpoint is None else endpoint.alias,
                "provider": "" if endpoint is None else endpoint.provider,
                "model": "" if endpoint is None else endpoint.model,
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

    def assets(self) -> dict[str, Any]:
        """What this machine has installed, and what it has run.

        Generic on purpose: a Skill and a Workflow are described by their own
        manifests, so a new one appears here the day it is installed without
        a line being written for it.
        """
        layout = self.runtime.layout
        skills = [
            {
                "namespace": item.metadata.identity.namespace,
                "name": item.metadata.identity.name,
                "version": item.metadata.identity.version,
                "alias": item.alias,
                "description": item.instructions,
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
            }
            for item in manifests(layout.workflows, WorkflowManifest)
        ]
        configured_knowledge = {binding.asset.key for binding in self.runtime.config.knowledge}
        authorization = load_authorization(self.runtime.config, layout)
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
                item.model_dump(mode="json") for item in extension_lifecycle(self.runtime)
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

    def ask(self, message: str, namespace: str | None = None) -> dict[str, Any]:
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
        device = self.runtime.config.device
        local = LocalWorkflowRequest(
            actor=self.runtime.actor,
            bridge_id=device.bridge_id,
            workflow=item.workflow,
            arguments=item.arguments,
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

    def ask_knowledge(self, request: KnowledgeAskRequest) -> dict[str, Any]:
        """Ask one exact installed Knowledge version through Bridge policy."""
        item = KnowledgeAskRequest.model_validate(request)
        device = self.runtime.config.device
        local = LocalCapabilityRequest(
            ingress="local",
            actor=self.runtime.actor,
            bridge_id=device.bridge_id,
            target=KNOWLEDGE_QUERY_SPEC.identity,
            arguments=KnowledgeQueryRequest(asset=item.asset, question=item.question).model_dump(
                mode="json"
            ),
            trace=_trace(),
        )
        import asyncio

        with self._one_at_a_time:
            outcome = asyncio.run(self.runtime.agent.execute_capability(local))
        record: KnowledgeAnswerRecord | None = None
        if (
            outcome.refusal is None
            and outcome.capability is not None
            and outcome.capability.status == "succeeded"
        ):
            record = KnowledgeAnswerRecord.model_validate(outcome.capability.data)
        return {
            "ok": record is not None,
            "answer": record.answer.text if record is not None else readable(outcome),
            "record": (None if record is None else json.loads(record.model_dump_json())),
            "outcome": json.loads(outcome.model_dump_json()),
        }


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
        if not self._authorized():
            self._json(401, {"error": "this request carried no usable token"})
            return
        web = self.server.web
        if parsed.path == "/api/about":
            self._json(200, web.about())
        elif parsed.path == "/api/readiness":
            self._json(200, web.readiness())
        elif parsed.path == "/api/settings":
            self._json(200, web.settings())
        elif parsed.path == "/api/assets":
            self._json(200, web.assets())
        elif parsed.path == "/api/platform":
            self._json(200, web.platform())
        else:
            self._json(404, {"error": "no such page"})

    def do_POST(self) -> None:  # noqa: N802 - the base class's spelling
        if not self._host_is_loopback():
            self._json(403, {"error": "this interface answers on the loopback address only"})
            return
        if not self._authorized():
            self._json(401, {"error": "this request carried no usable token"})
            return
        path = urlparse(self.path).path
        if path not in (
            "/api/ask",
            "/api/platform/sync",
            "/api/profiles/activate",
            "/api/workflows/run",
            "/api/knowledge/ask",
            "/api/settings/model",
        ):
            self._json(404, {"error": "no such page"})
            return
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
        if path == "/api/settings/model":
            try:
                settings = ModelSettingsUpdateRequest.model_validate(body)
                result = self.server.web.update_model_settings(settings)
            except (OSError, ValueError, TypeError):
                self._json(400, {"error": "the request was not valid model settings"})
                return
            self._json(200 if result.get("ok") else 409, result)
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
