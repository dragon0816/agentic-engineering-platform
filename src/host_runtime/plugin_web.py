"""Agent Web's generic Feature Plugin routes (Slice 1,
`docs/phases/FEATURE_PLUGIN_SLICE1_PLAN_20261113.md` §3).

Two prefixes, both served only after Agent Web's loopback and page-token
guards, and checked here again for a loopback `Origin`:

- `/api/plugin-manager/plugins` (GET) lists installed plugins;
  `/api/plugin-manager/{install,update,enable,disable,uninstall}` (POST) act
  on them. `update` is `install` of a newer package. The actor is the
  server's own; nothing in a request names who asked.
- `/api/plugins/<plugin_id>/<route_id>?version=<x.y.z>` (GET) reads one
  declared route of one active plugin at one exact installed version.

Only `PluginManagerProtocol` is used: no Host runtime, Web object or token
reaches this module or a plugin. A read carries just the typed
`PluginReadRequest`; no inbound header is forwarded, and the answer must name
the same request, plugin, version and route. A worker's failure is reported
with its actual code. Plugin data is returned as JSON and is never treated as
an instruction to install, approve or call anything.
"""

from __future__ import annotations

import json
import re
import secrets
from typing import Any, Protocol
from urllib.parse import ParseResult, parse_qs

from pydantic import ValidationError

from common.plugins import (
    MAX_PACKAGE_BYTES,
    PluginActionResult,
    PluginContractError,
    PluginErrorCode,
    PluginManagerProtocol,
    PluginOrigin,
    PluginReadRequest,
    PluginReadResponse,
)

MANAGER_ROOT = "/api/plugin-manager"
LIST_PATH = MANAGER_ROOT + "/plugins"
READ_ROOT = "/api/plugins"
#: Agent Web's channel name in a plugin's install record.
CHANNEL = "agent-web"
#: `update` installs a newer package of an installed plugin.
ACTIONS = {
    "install": "install",
    "update": "install",
    "enable": "enable",
    "disable": "disable",
    "uninstall": "uninstall",
}
#: An enable/disable/uninstall body is `{"plugin_id": ...}` and nothing else.
MAX_ACTION_BODY_BYTES = 4 * 1024
#: The manager bounds a read by the plugin's own declared timeout as well.
READ_TIMEOUT_SECONDS = 30.0

# The contract's id shapes, matched on the raw (still percent-encoded) path, so
# `%2e%2e`, `..`, backslashes, upper case and empty segments never resolve.
_PLUGIN_ID = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*\.[a-z0-9]+(?:-[a-z0-9]+)*$")
_ROUTE_ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

#: The HTTP status for each manager failure code.
STATUS_BY_CODE: dict[str, int] = {
    "plugin_package_too_large": 413,
    "plugin_package_invalid": 400,
    "plugin_path_invalid": 400,
    "plugin_digest_mismatch": 400,
    "plugin_staged_changed": 409,
    "plugin_version_exists": 409,
    "plugin_version_conflict": 409,
    "plugin_downgrade_refused": 409,
    "plugin_core_api_incompatible": 422,
    "plugin_runtime_incompatible": 422,
    "plugin_dependency_missing": 409,
    "plugin_dependency_inactive": 409,
    "plugin_dependent_active": 409,
    "plugin_namespace_owned": 409,
    "plugin_contribution_collision": 409,
    "plugin_data_newer": 409,
    "plugin_data_foreign": 409,
    "plugin_migration_unsupported": 409,
    "plugin_environment_failed": 502,
    "plugin_health_failed": 502,
    "plugin_worker_failed": 502,
    "plugin_invocation_failed": 502,
    "plugin_timeout": 504,
    "plugin_request_too_large": 413,
    "plugin_response_too_large": 502,
    "plugin_busy": 409,
    "plugin_not_installed": 404,
    "plugin_not_active": 409,
    "plugin_version_stale": 409,
    "plugin_route_unknown": 404,
    "plugin_load_failed": 503,
}

Reply = tuple[int, dict[str, Any]]


class _Handler(Protocol):
    """The parts of Agent Web's request handler this module uses."""

    headers: Any
    rfile: Any

    def _json(self, status: int, payload: dict[str, Any]) -> None: ...

    def _refuse_unread(self, status: int, payload: dict[str, Any]) -> None: ...


def _refusal(status: int, code: str, message: str) -> Reply:
    return status, {"ok": False, "code": code, "message": message}


def owns(path: str) -> bool:
    """Whether `path` is one of this module's (not a prefix look-alike)."""
    return any(path == root or path.startswith(root + "/") for root in (MANAGER_ROOT, READ_ROOT))


def origin_allowed(origin: str | None) -> bool:
    """No `Origin` (a same-origin GET or a non-browser client) or a loopback one."""
    from host_runtime.schedule_web import origin_allowed as loopback_origin

    return loopback_origin(origin)


# -- the pure route --------------------------------------------------------------------


def route(
    manager: PluginManagerProtocol | None,
    *,
    actor: str,
    method: str,
    path: str,
    query: str,
    body: bytes | None,
) -> Reply:
    """Answer one already-authenticated plugin request; `body` is bounded."""
    if path == LIST_PATH:
        if method != "GET":
            return _refusal(405, "method_not_allowed", "the plugin list answers GET only")
        return _list(manager)
    if path.startswith(MANAGER_ROOT + "/"):
        action = ACTIONS.get(path[len(MANAGER_ROOT) + 1 :])
        if action is None:
            return _refusal(404, "no_such_page", "no such plugin management page")
        if method != "POST":
            return _refusal(405, "method_not_allowed", "a plugin action answers POST only")
        return _act(manager, actor, action, body or b"")
    if path.startswith(READ_ROOT + "/"):
        if method != "GET":
            return _refusal(405, "method_not_allowed", "a plugin route answers GET only")
        return _read(manager, path[len(READ_ROOT) + 1 :], query)
    return _refusal(404, "no_such_page", "no such plugin page")


def _list(manager: PluginManagerProtocol | None) -> Reply:
    plugins: list[dict[str, Any]] = []
    shipped: list[dict[str, Any]] = []
    if manager is not None:
        try:
            snapshot = manager.snapshot()
        except Exception:  # noqa: BLE001 - reported as unavailable, never as an empty list
            return _refusal(503, "plugin_unavailable", "the plugin manager did not answer")
        plugins = [item.model_dump(mode="json") for item in snapshot.plugins]
        shipped = [item.model_dump(mode="json") for item in snapshot.bundled]
    return 200, {
        "ok": True,
        "plugins": plugins,
        **({"bundled": shipped} if shipped else {}),
        "max_package_bytes": MAX_PACKAGE_BYTES,
    }


def _act(manager: PluginManagerProtocol | None, actor: str, action: str, body: bytes) -> Reply:
    if manager is None:
        return _refusal(503, "plugins_unavailable", "plugins are not available on this host")
    try:
        origin = PluginOrigin(actor=actor, channel=CHANNEL)
    except ValidationError:
        return _refusal(500, "plugin_actor_invalid", "this host's actor cannot be recorded")
    try:
        if action == "install":
            if len(body) > MAX_PACKAGE_BYTES:
                return _refusal(413, "plugin_package_too_large", "the package is too large")
            result = manager.install(body, origin)
        else:
            plugin_id = _named_plugin(body)
            if plugin_id is None:
                return _refusal(
                    400, "plugin_request_invalid", 'the body is {"plugin_id": "<namespace>.<name>"}'
                )
            result = getattr(manager, action)(plugin_id, origin)
        result = PluginActionResult.model_validate(result)
    except PluginContractError as refused:
        return _refusal(STATUS_BY_CODE.get(refused.code, 409), refused.code, refused.code)
    except Exception:  # noqa: BLE001 - its text may name local paths; the code is enough
        return _refusal(500, "plugin_manager_error", "the plugin manager could not finish")
    payload: dict[str, Any] = {"ok": result.status == "succeeded", **result.model_dump(mode="json")}
    if result.failure is None:
        return 200, payload
    payload["code"] = result.failure.code
    payload["message"] = result.failure.message
    return STATUS_BY_CODE.get(result.failure.code, 409), payload


def _named_plugin(body: bytes) -> str | None:
    try:
        value = json.loads(body)
    except (ValueError, UnicodeDecodeError):
        return None
    if not isinstance(value, dict) or set(value) != {"plugin_id"}:
        return None
    plugin_id = value["plugin_id"]
    if not isinstance(plugin_id, str) or not _PLUGIN_ID.fullmatch(plugin_id):
        return None
    return plugin_id


def _read(manager: PluginManagerProtocol | None, rest: str, query: str) -> Reply:
    parts = rest.split("/")
    if (
        len(parts) != 2
        or len(parts[0]) > 81
        or not _PLUGIN_ID.fullmatch(parts[0])
        or not _ROUTE_ID.fullmatch(parts[1])
    ):
        return _refusal(404, "plugin_route_unknown", "no such plugin route")
    plugin_id, route_id = parts
    try:
        fields = parse_qs(query, keep_blank_values=True, strict_parsing=bool(query))
    except ValueError:
        fields = {}
    versions = fields.get("version", [])
    if set(fields) != {"version"} or len(versions) != 1:
        return _refusal(
            400,
            "plugin_request_invalid",
            "a plugin route takes exactly one version= and nothing else",
        )
    if manager is None:
        return _refusal(503, "plugins_unavailable", "plugins are not available on this host")
    try:
        request = PluginReadRequest(
            request_id="web-" + secrets.token_hex(12),
            plugin_id=plugin_id,
            version=versions[0],
            route_id=route_id,
        )
    except ValidationError:
        return _refusal(400, "plugin_request_invalid", "the version is not a full semantic version")
    try:
        installed = manager.snapshot().get(plugin_id)
    except Exception:  # noqa: BLE001 - reported as unavailable
        return _refusal(503, "plugin_unavailable", "the plugin manager did not answer")
    if installed is None:
        return _refusal(404, "plugin_not_installed", "this plugin is not installed")
    if installed.state != "active":
        return _refusal(409, "plugin_not_active", "this plugin is not active")
    if route_id not in installed.routes:
        return _refusal(404, "plugin_route_unknown", "this plugin declares no such route")
    if installed.identity.version != request.version:
        return _refusal(409, "plugin_version_stale", "the plugin changed version; reload the page")
    try:
        answer = PluginReadResponse.model_validate(
            manager.call_read(request, timeout_seconds=READ_TIMEOUT_SECONDS)
        )
    except PluginContractError as refused:
        return _refusal(STATUS_BY_CODE.get(refused.code, 502), refused.code, refused.code)
    except ValidationError:
        return _refusal(502, "plugin_protocol_error", "the plugin's answer was not a plugin answer")
    except Exception:  # noqa: BLE001 - its text may name local paths; the code is enough
        return _refusal(503, "plugin_unavailable", "the plugin did not answer")
    if (answer.request_id, answer.plugin_id, answer.version, answer.route_id) != (
        request.request_id,
        request.plugin_id,
        request.version,
        request.route_id,
    ):
        return _refusal(502, "plugin_protocol_error", "the plugin answered a different request")
    if answer.failure is not None:
        code: PluginErrorCode = answer.failure.code
        return _refusal(STATUS_BY_CODE.get(code, 502), code, answer.failure.message)
    return 200, {
        "ok": True,
        "plugin_id": answer.plugin_id,
        "version": answer.version,
        "route_id": answer.route_id,
        "data": answer.data,
    }


# -- the handler adapter ------------------------------------------------------------------


def handle(
    handler: _Handler,
    method: str,
    parsed: ParseResult,
    manager: PluginManagerProtocol | None,
    *,
    actor: str,
) -> bool:
    """Serve a plugin request on Agent Web's `handler` (already loopback- and
    token-checked); False when the path is not ours. POST bodies are bounded
    before they are read."""
    path = parsed.path
    if not owns(path):
        return False
    if not origin_allowed(handler.headers.get("Origin")):
        status, payload = _refusal(
            403, "origin_refused", "this interface answers its own page only"
        )
        if method == "POST":
            handler._refuse_unread(status, payload)
        else:
            handler._json(status, payload)
        return True
    body: bytes | None = None
    if method == "POST":
        install = path in (MANAGER_ROOT + "/install", MANAGER_ROOT + "/update")
        limit = MAX_PACKAGE_BYTES if install else MAX_ACTION_BODY_BYTES
        try:
            length = int(handler.headers.get("Content-Length") or "")
        except ValueError:
            length = -1
        if length < 0:
            handler._refuse_unread(
                411,
                {
                    "ok": False,
                    "code": "length_required",
                    "message": "the request did not say how long it was",
                },
            )
            return True
        if length > limit:
            status, payload = (
                _refusal(413, "plugin_package_too_large", "the package is too large")
                if install
                else _refusal(413, "plugin_request_too_large", "the request is too large")
            )
            handler._refuse_unread(status, payload)
            return True
        body = handler.rfile.read(length)
    status, payload = route(
        manager, actor=actor, method=method, path=path, query=parsed.query, body=body
    )
    handler._json(status, payload)
    return True
