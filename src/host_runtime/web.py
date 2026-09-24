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

from agent.skills import SkillManifest
from common.assets import WorkflowManifest
from common.execution import TraceIdentifiers
from common.local_agent import LocalAgentRequest
from host_runtime.answers import readable
from host_runtime.host import HostRuntime
from host_runtime.workspace import documents

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


class AgentWeb:
    """What the pages ask for, with no HTTP in it.

    Separated so every answer this serves can be tested without a socket,
    and so a different front end could be built on the same answers.
    """

    def __init__(self, runtime: HostRuntime, *, namespace: str | None = None) -> None:
        self.runtime = runtime
        self.namespace = namespace if namespace is not None else runtime.config.namespace
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
                "commands": [command.name for command in item.commands],
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
            }
            for item in manifests(layout.workflows, WorkflowManifest)
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
        return {"skills": skills, "workflows": workflows, "runs": runs}

    def platform(self) -> dict[str, Any]:
        """What the shared platform has decided this machine may run.

        This is not a catalogue of everything the team has published, and it
        does not pretend to be: the wire this Bridge speaks has `probe`,
        `advertise`, `sync`, `report`, `poll` and `settle`, and none of them
        lists the Registry. Showing the decisions in force is the true answer
        available today; browsing what other people published needs an
        operation the control plane does not yet have.
        """
        if self.runtime.platform is None:
            return {
                "configured": False,
                "note": "No shared platform is configured on this machine.",
                "decisions": [],
            }
        decided = self.runtime.layout.authorization
        if not decided.is_file():
            return {
                "configured": True,
                "note": (
                    "This machine is configured for a shared platform but has not "
                    "synchronised yet, so nothing has been decided for it."
                ),
                "decisions": [],
            }
        installed = {
            (item.identity.namespace, item.identity.name, item.identity.version)
            for item in self.runtime.agent.snapshot(observed_at=datetime.now(UTC)).installed
        }
        try:
            from common.authorization import DeviceAuthorization

            authorization = DeviceAuthorization.model_validate_json(
                decided.read_text(encoding="utf-8-sig")
            )
        except Exception:  # noqa: BLE001 - reported, not raised, to a listing
            return {
                "configured": True,
                "note": "The decisions this machine was given cannot be read; run `doctor`.",
                "decisions": [],
            }
        rows = []
        # Every selection here is in force: the contract refuses to carry a
        # revoked one, so nothing has to read a status to know what applies.
        for selection in authorization.selections:
            asset = selection.asset
            key = (asset.namespace, asset.name, asset.version)
            rows.append(
                {
                    "kind": selection.kind,
                    "namespace": asset.namespace,
                    "name": asset.name,
                    "version": asset.version,
                    "actor": selection.actor,
                    "installed": key in installed,
                }
            )
        return {
            "configured": True,
            "note": (
                "What the members of this machine decided it may run. Browsing "
                "everything the team has published is not something this Bridge can "
                "ask for yet."
            ),
            "decisions": rows,
        }

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
        if urlparse(self.path).path != "/api/ask":
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
