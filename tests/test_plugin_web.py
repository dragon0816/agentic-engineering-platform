"""Agent Web's generic plugin routes and text-only renderer (Feature Plugin Slice 1).

`docs/phases/FEATURE_PLUGIN_SLICE1_PLAN_20261113.md` §3. A fake manager stands in
for `PluginManagerProtocol`: these tests prove the Web side's namespace routing,
bounds, correlation and refusals, and that plugin text never becomes markup.
"""

from __future__ import annotations

import inspect
import io
import json
import shutil
import subprocess
import urllib.error
import urllib.request
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any, get_args
from urllib.parse import urlparse

import pytest
from test_draft_install_cards import served  # noqa: F401 - the real Agent Web fixture

from common.assets import AssetIdentity
from common.plugins import (
    MAX_PACKAGE_BYTES,
    MAX_TABLE_ROWS,
    PluginActionResult,
    PluginContractError,
    PluginErrorCode,
    PluginFailure,
    PluginOrigin,
    PluginPage,
    PluginReadRequest,
    PluginReadResponse,
    PluginSnapshot,
    PluginStatus,
)
from host_runtime import plugin_renderer, plugin_web

TOKEN = "page-token-never-forwarded"
HOSTILE = "<img src=x onerror=alert(1)><script>alert(2)</script>"
DIGEST = "a" * 64


def _page(title: str = "Overview", text: str = "Synthetic hello data") -> PluginPage:
    return PluginPage.model_validate(
        {
            "page_id": "overview",
            "title": title,
            "blocks": [
                {"kind": "text", "text": text},
                {"kind": "metric", "label": "Count", "route_id": "summary", "field": "count"},
                {
                    "kind": "table",
                    "title": "Items",
                    "route_id": "summary",
                    "field": "items",
                    "columns": [{"key": "name", "label": "Name"}],
                },
            ],
        }
    )


def _status(
    namespace: str = "hello",
    *,
    state: str = "active",
    version: str = "1.0.0",
    title: str = "Hello",
    page: PluginPage | None = None,
) -> PluginStatus:
    active = state == "active"
    return PluginStatus(
        plugin_id=f"{namespace}.app",
        identity=AssetIdentity(namespace=namespace, name="app", version=version),
        title=title,
        state=state,
        content_sha256=DIGEST,
        installed_by=PluginOrigin(actor="engineer", channel="agent-web"),
        failure=(
            PluginFailure(code="plugin_health_failed", message="worker did not answer")
            if state == "failed"
            else None
        ),
        routes=("summary",) if active else (),
        pages=((page or _page()),) if active else (),
    )


class FakeManager:
    """Records exactly what the Web side hands the manager."""

    def __init__(self, *plugins: PluginStatus) -> None:
        self.plugins = list(plugins)
        self.calls: list[tuple[str, Any]] = []
        self.read: Callable[[PluginReadRequest], PluginReadResponse] | None = None
        self.action_failure: PluginFailure | None = None
        self.raise_on_read: BaseException | None = None

    def snapshot(self) -> PluginSnapshot:
        self.calls.append(("snapshot", None))
        return PluginSnapshot(plugins=tuple(self.plugins))

    def _action(
        self, action: str, plugin_id: str | None, origin: PluginOrigin
    ) -> PluginActionResult:
        self.calls.append((action, (plugin_id, origin)))
        if self.action_failure is not None:
            return PluginActionResult(
                action=action,
                status="failed",
                plugin_id=plugin_id,
                failure=self.action_failure,
            )
        found = next((item for item in self.plugins if item.plugin_id == plugin_id), None)
        if action == "uninstall":
            self.plugins = [item for item in self.plugins if item.plugin_id != plugin_id]
            return PluginActionResult(action="uninstall", status="succeeded", plugin_id=plugin_id)
        status = found or self.plugins[0]
        return PluginActionResult(
            action=action,
            status="succeeded",
            plugin_id=status.plugin_id,
            plugin=status,
        )

    def install(self, payload: bytes, origin: PluginOrigin) -> PluginActionResult:
        self.calls.append(("install-bytes", payload))
        return self._action("install", self.plugins[0].plugin_id, origin)

    def enable(self, plugin_id: str, origin: PluginOrigin) -> PluginActionResult:
        return self._action("enable", plugin_id, origin)

    def disable(self, plugin_id: str, origin: PluginOrigin) -> PluginActionResult:
        return self._action("disable", plugin_id, origin)

    def uninstall(self, plugin_id: str, origin: PluginOrigin) -> PluginActionResult:
        return self._action("uninstall", plugin_id, origin)

    def call_read(
        self, request: PluginReadRequest, *, timeout_seconds: float
    ) -> PluginReadResponse:
        self.calls.append(("call_read", (request, timeout_seconds)))
        if self.raise_on_read is not None:
            raise self.raise_on_read
        if self.read is not None:
            return self.read(request)
        return PluginReadResponse(
            request_id=request.request_id,
            plugin_id=request.plugin_id,
            version=request.version,
            route_id=request.route_id,
            status="succeeded",
            data={"count": 3, "items": [{"name": HOSTILE}]},
        )

    def set_busy_probe(self, probe: Callable[[], bool] | None) -> None:
        self.calls.append(("set_busy_probe", probe))

    def close(self) -> None:
        self.calls.append(("close", None))

    def names(self) -> list[str]:
        return [name for name, _ in self.calls]


def _route(
    manager: Any,
    method: str,
    target: str,
    body: bytes | None = None,
    *,
    actor: str = "engineer",
) -> tuple[int, dict[str, Any]]:
    parsed = urlparse(target)
    return plugin_web.route(
        manager, actor=actor, method=method, path=parsed.path, query=parsed.query, body=body
    )


# -- the pure route ---------------------------------------------------------------------


def test_list_returns_the_snapshot_and_the_package_bound() -> None:
    manager = FakeManager(_status(), _status("other", state="failed"))
    status, payload = _route(manager, "GET", "/api/plugin-manager/plugins")
    assert status == 200 and payload["ok"] is True
    assert payload["max_package_bytes"] == MAX_PACKAGE_BYTES
    assert [item["plugin_id"] for item in payload["plugins"]] == ["hello.app", "other.app"]
    assert payload["plugins"][1]["failure"]["code"] == "plugin_health_failed"


def test_no_manager_lists_nothing_and_refuses_actions() -> None:
    assert _route(None, "GET", "/api/plugin-manager/plugins")[1]["plugins"] == []
    status, payload = _route(None, "POST", "/api/plugin-manager/enable", b'{"plugin_id":"a.b"}')
    assert status == 503 and payload["code"] == "plugins_unavailable"
    assert _route(None, "GET", "/api/plugins/hello.app/summary?version=1.0.0")[0] == 503


def test_read_pins_the_version_and_correlates_the_answer() -> None:
    manager = FakeManager(_status())
    status, payload = _route(manager, "GET", "/api/plugins/hello.app/summary?version=1.0.0")
    assert status == 200, payload
    assert payload == {
        "ok": True,
        "plugin_id": "hello.app",
        "version": "1.0.0",
        "route_id": "summary",
        "data": {"count": 3, "items": [{"name": HOSTILE}]},
    }
    (request, timeout) = next(value for name, value in manager.calls if name == "call_read")
    assert isinstance(request, PluginReadRequest)
    assert (request.plugin_id, request.version, request.route_id) == (
        "hello.app",
        "1.0.0",
        "summary",
    )
    assert request.arguments == {} and 0 < timeout <= 120


def test_each_read_gets_a_fresh_request_id() -> None:
    manager = FakeManager(_status())
    for _ in range(2):
        _route(manager, "GET", "/api/plugins/hello.app/summary?version=1.0.0")
    ids = [value[0].request_id for name, value in manager.calls if name == "call_read"]
    assert len(set(ids)) == 2


@pytest.mark.parametrize(
    "field",
    ["request_id", "plugin_id", "version", "route_id"],
)
def test_an_answer_for_another_request_is_a_protocol_error(field: str) -> None:
    manager = FakeManager(_status())

    def wrong(request: PluginReadRequest) -> PluginReadResponse:
        values = {
            "request_id": request.request_id,
            "plugin_id": request.plugin_id,
            "version": request.version,
            "route_id": request.route_id,
        }
        values[field] = {
            "request_id": "other-request",
            "plugin_id": "other.app",
            "version": "9.9.9",
            "route_id": "elsewhere",
        }[field]
        return PluginReadResponse(**values, status="succeeded", data={"count": 1})

    manager.read = wrong
    status, payload = _route(manager, "GET", "/api/plugins/hello.app/summary?version=1.0.0")
    assert status == 502 and payload == {
        "ok": False,
        "code": "plugin_protocol_error",
        "message": "the plugin answered a different request",
    }


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("plugin_timeout", 504),
        ("plugin_worker_failed", 502),
        ("plugin_invocation_failed", 502),
        ("plugin_response_too_large", 502),
        ("plugin_busy", 409),
        ("plugin_version_stale", 409),
        ("plugin_not_active", 409),
    ],
)
def test_actual_worker_failures_are_reported_not_turned_into_success(
    code: PluginErrorCode, expected: int
) -> None:
    manager = FakeManager(_status())
    manager.read = lambda request: PluginReadResponse(
        request_id=request.request_id,
        plugin_id=request.plugin_id,
        version=request.version,
        route_id=request.route_id,
        status="failed",
        failure=PluginFailure(code=code, message="actual failure"),
    )
    status, payload = _route(manager, "GET", "/api/plugins/hello.app/summary?version=1.0.0")
    assert status == expected
    assert payload == {"ok": False, "code": code, "message": "actual failure"}


def test_a_manager_exception_is_unavailable_without_its_text() -> None:
    manager = FakeManager(_status())
    manager.raise_on_read = RuntimeError("C:/secret/path " + TOKEN)
    status, payload = _route(manager, "GET", "/api/plugins/hello.app/summary?version=1.0.0")
    assert status == 503 and payload["code"] == "plugin_unavailable"
    assert TOKEN not in json.dumps(payload) and "secret" not in json.dumps(payload)


@pytest.mark.parametrize(
    ("target", "status", "code"),
    [
        ("/api/plugins/missing.app/summary?version=1.0.0", 404, "plugin_not_installed"),
        ("/api/plugins/hello.app/elsewhere?version=1.0.0", 404, "plugin_route_unknown"),
        ("/api/plugins/hello.app/summary?version=0.9.0", 409, "plugin_version_stale"),
        ("/api/plugins/hello.app/summary", 400, "plugin_request_invalid"),
        (
            "/api/plugins/hello.app/summary?version=1.0.0&version=1.0.0",
            400,
            "plugin_request_invalid",
        ),
        ("/api/plugins/hello.app/summary?version=latest", 400, "plugin_request_invalid"),
        ("/api/plugins/hello.app/summary?version=1.0.0&actor=boss", 400, "plugin_request_invalid"),
        ("/api/plugins/hello.app/summary?version=1.0.0&token=x", 400, "plugin_request_invalid"),
        ("/api/plugins/hello.app/../../about?version=1.0.0", 404, "plugin_route_unknown"),
        ("/api/plugins/hello.app/%2e%2e?version=1.0.0", 404, "plugin_route_unknown"),
        ("/api/plugins/hello.app/summary/extra?version=1.0.0", 404, "plugin_route_unknown"),
        ("/api/plugins/hello.app?version=1.0.0", 404, "plugin_route_unknown"),
        ("/api/plugins/hello.app/?version=1.0.0", 404, "plugin_route_unknown"),
        ("/api/plugins/HELLO.app/summary?version=1.0.0", 404, "plugin_route_unknown"),
        ("/api/plugins/hello.app/Summary?version=1.0.0", 404, "plugin_route_unknown"),
        ("/api/plugins/http:%2F%2Fevil/summary?version=1.0.0", 404, "plugin_route_unknown"),
        ("/api/plugins/hello.app\\summary?version=1.0.0", 404, "plugin_route_unknown"),
        ("/api/plugins/", 404, "plugin_route_unknown"),
    ],
)
def test_namespace_routing_refuses_without_calling_the_worker(
    target: str, status: int, code: str
) -> None:
    manager = FakeManager(_status())
    got_status, payload = _route(manager, "GET", target)
    assert (got_status, payload["ok"], payload["code"]) == (status, False, code)
    assert "call_read" not in manager.names()


@pytest.mark.parametrize("state", ["disabled", "failed"])
def test_an_inactive_plugin_is_not_called(state: str) -> None:
    manager = FakeManager(_status(state=state))
    status, payload = _route(manager, "GET", "/api/plugins/hello.app/summary?version=1.0.0")
    assert (status, payload["code"]) == (409, "plugin_not_active")
    assert "call_read" not in manager.names()


def test_uninstalling_one_plugin_leaves_the_other_working() -> None:
    manager = FakeManager(_status(), _status("other"))
    status, payload = _route(
        manager, "POST", "/api/plugin-manager/uninstall", b'{"plugin_id":"hello.app"}'
    )
    assert status == 200 and payload["ok"] is True and payload["plugin_id"] == "hello.app"
    listed = _route(manager, "GET", "/api/plugin-manager/plugins")[1]["plugins"]
    assert [item["plugin_id"] for item in listed] == ["other.app"]
    assert _route(manager, "GET", "/api/plugins/hello.app/summary?version=1.0.0")[0] == 404
    assert _route(manager, "GET", "/api/plugins/other.app/summary?version=1.0.0")[0] == 200


@pytest.mark.parametrize("method", ["POST", "PUT", "DELETE"])
def test_reads_answer_get_only(method: str) -> None:
    manager = FakeManager(_status())
    status, payload = _route(manager, method, "/api/plugins/hello.app/summary?version=1.0.0", b"{}")
    assert (status, payload["code"]) == (405, "method_not_allowed")
    assert "call_read" not in manager.names()


def test_manager_paths_are_closed() -> None:
    manager = FakeManager(_status())
    assert _route(manager, "POST", "/api/plugin-manager/plugins", b"{}")[0] == 405
    assert _route(manager, "GET", "/api/plugin-manager/install")[0] == 405
    assert _route(manager, "POST", "/api/plugin-manager/approve", b"{}")[0] == 404
    assert _route(manager, "POST", "/api/plugin-manager/install/extra", b"{}")[0] == 404
    assert _route(manager, "GET", "/api/plugin-manager")[0] == 404


@pytest.mark.parametrize("action", ["enable", "disable", "uninstall"])
def test_actions_take_the_actor_from_the_server(action: str) -> None:
    manager = FakeManager(_status())
    status, payload = _route(
        manager,
        "POST",
        f"/api/plugin-manager/{action}",
        b'{"plugin_id":"hello.app"}',
        actor="engineer",
    )
    assert status == 200 and payload["ok"] is True and payload["action"] == action
    (plugin_id, origin) = next(value for name, value in manager.calls if name == action)
    assert plugin_id == "hello.app"
    assert origin == PluginOrigin(actor="engineer", channel="agent-web")


@pytest.mark.parametrize(
    "body",
    [
        b'{"plugin_id":"hello.app","actor":"boss"}',
        b'{"plugin_id":"hello.app","channel":"cli"}',
        b'{"plugin_id":"../hello"}',
        b'{"plugin_id":7}',
        b"{}",
        b"[]",
        b"not json",
        b"",
    ],
)
def test_action_bodies_are_closed(body: bytes) -> None:
    manager = FakeManager(_status())
    status, payload = _route(manager, "POST", "/api/plugin-manager/enable", body)
    assert (status, payload["code"]) == (400, "plugin_request_invalid")
    assert "enable" not in manager.names()


@pytest.mark.parametrize("path", ["/api/plugin-manager/install", "/api/plugin-manager/update"])
def test_install_hands_the_exact_bytes_to_the_manager(path: str) -> None:
    manager = FakeManager(_status())
    body = b'{"format":"aep-plugin-package/1"}'
    status, payload = _route(manager, "POST", path, body)
    assert status == 200 and payload["ok"] is True and payload["action"] == "install"
    assert ("install-bytes", body) in manager.calls
    (_, origin) = next(value for name, value in manager.calls if name == "install")
    assert origin.actor == "engineer" and origin.channel == "agent-web"


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("plugin_package_invalid", 400),
        ("plugin_digest_mismatch", 400),
        ("plugin_package_too_large", 413),
        ("plugin_namespace_owned", 409),
        ("plugin_downgrade_refused", 409),
        ("plugin_busy", 409),
        ("plugin_core_api_incompatible", 422),
        ("plugin_health_failed", 502),
        ("plugin_not_installed", 404),
    ],
)
def test_action_failures_keep_their_actual_code(code: PluginErrorCode, expected: int) -> None:
    manager = FakeManager(_status())
    manager.action_failure = PluginFailure(code=code, message="actual refusal")
    status, payload = _route(manager, "POST", "/api/plugin-manager/install", b"{}")
    assert status == expected
    assert payload["ok"] is False and payload["status"] == "failed"
    assert (payload["code"], payload["message"]) == (code, "actual refusal")


def test_a_raised_contract_error_keeps_its_code() -> None:
    manager = FakeManager(_status())

    def refuse(payload: bytes, origin: PluginOrigin) -> PluginActionResult:
        raise PluginContractError("plugin_package_too_large")

    manager.install = refuse  # type: ignore[method-assign]
    status, payload = _route(manager, "POST", "/api/plugin-manager/install", b"{}")
    assert (status, payload["code"]) == (413, "plugin_package_too_large")


def test_install_bytes_over_the_bound_never_reach_the_manager() -> None:
    manager = FakeManager(_status())
    status, payload = _route(
        manager, "POST", "/api/plugin-manager/install", b" " * (MAX_PACKAGE_BYTES + 1)
    )
    assert (status, payload["code"]) == (413, "plugin_package_too_large")
    assert "install-bytes" not in manager.names()


def test_every_contract_error_code_has_an_http_status() -> None:
    for code in get_args(PluginErrorCode):
        assert code in plugin_web.STATUS_BY_CODE, code
    assert plugin_web.STATUS_BY_CODE["plugin_busy"] == 409


def test_an_invalid_server_actor_is_refused_not_guessed() -> None:
    manager = FakeManager(_status())
    status, payload = _route(
        manager, "POST", "/api/plugin-manager/enable", b'{"plugin_id":"hello.app"}', actor="a b"
    )
    assert (status, payload["code"]) == (500, "plugin_actor_invalid")
    assert "enable" not in manager.names()


def test_the_module_needs_only_the_manager_protocol() -> None:
    source = inspect.getsource(plugin_web)
    for coupled in ("HostRuntime", "AgentWeb", ".runtime", "server.web", "server.token"):
        assert coupled not in source, coupled


# -- the handler adapter ------------------------------------------------------------------


class FakeHandler:
    """The parts of `web._Handler` the adapter uses."""

    def __init__(self, headers: dict[str, str], body: bytes = b"") -> None:
        self.headers = headers
        self.rfile = io.BytesIO(body)
        self.replies: list[tuple[int, dict[str, Any]]] = []
        self.unread: list[tuple[int, dict[str, Any]]] = []

    def _json(self, status: int, payload: dict[str, Any]) -> None:
        self.replies.append((status, dict(payload)))

    def _refuse_unread(self, status: int, payload: dict[str, Any]) -> None:
        self.unread.append((status, dict(payload)))


def _handle(
    manager: Any, method: str, target: str, headers: dict[str, str], body: bytes = b""
) -> tuple[bool, FakeHandler]:
    handler = FakeHandler(headers, body)
    owned = plugin_web.handle(handler, method, urlparse(target), manager, actor="engineer")
    return owned, handler


def test_other_paths_are_not_ours() -> None:
    for path in ("/api/about", "/api/pluginsx", "/api/bi/datasets", "/api/plugin-managerx"):
        owned, handler = _handle(FakeManager(), "GET", path, {})
        assert owned is False and not handler.replies


@pytest.mark.parametrize("origin", ["https://evil.example", "null", "http://192.168.1.5:9000"])
def test_a_foreign_origin_is_refused(origin: str) -> None:
    manager = FakeManager(_status())
    owned, handler = _handle(
        manager, "GET", "/api/plugins/hello.app/summary?version=1.0.0", {"Origin": origin}
    )
    assert owned and handler.replies == [
        (
            403,
            {
                "ok": False,
                "code": "origin_refused",
                "message": "this interface answers its own page only",
            },
        )
    ]
    owned, handler = _handle(
        manager,
        "POST",
        "/api/plugin-manager/enable",
        {"Origin": origin, "Content-Length": "24"},
        b'{"plugin_id":"hello.app"}',
    )
    assert owned and handler.unread and handler.unread[0][0] == 403
    assert manager.names() == []


def test_inbound_authorization_and_headers_are_not_forwarded() -> None:
    manager = FakeManager(_status())
    owned, handler = _handle(
        manager,
        "GET",
        "/api/plugins/hello.app/summary?version=1.0.0",
        {
            "Authorization": "Bearer " + TOKEN,
            "Cookie": "session=" + TOKEN,
            "X-AEP-Client": TOKEN,
            "Origin": "http://127.0.0.1:8770",
        },
    )
    assert owned and handler.replies[0][0] == 200
    (request, _) = next(value for name, value in manager.calls if name == "call_read")
    assert TOKEN not in request.model_dump_json()
    assert set(PluginReadRequest.model_fields) == {
        "request_id",
        "plugin_id",
        "version",
        "route_id",
        "arguments",
    }


def test_post_bodies_are_bounded_before_reading() -> None:
    manager = FakeManager(_status())
    owned, handler = _handle(
        manager,
        "POST",
        "/api/plugin-manager/install",
        {"Content-Length": str(MAX_PACKAGE_BYTES + 1)},
    )
    assert owned and handler.unread == [
        (
            413,
            {
                "ok": False,
                "code": "plugin_package_too_large",
                "message": "the package is too large",
            },
        )
    ]
    owned, handler = _handle(
        manager, "POST", "/api/plugin-manager/enable", {"Content-Length": "5000"}
    )
    assert owned and handler.unread[0][0] == 413
    assert handler.unread[0][1]["code"] == "plugin_request_too_large"
    owned, handler = _handle(manager, "POST", "/api/plugin-manager/enable", {})
    assert owned and handler.unread[0][0] == 411
    owned, handler = _handle(
        manager, "POST", "/api/plugin-manager/enable", {"Content-Length": "abc"}
    )
    assert owned and handler.unread[0][0] == 411
    assert [name for name in manager.names() if name != "snapshot"] == []


def test_a_bounded_post_is_read_and_served() -> None:
    manager = FakeManager(_status())
    body = b'{"plugin_id":"hello.app"}'
    owned, handler = _handle(
        manager,
        "POST",
        "/api/plugin-manager/disable",
        {"Content-Length": str(len(body)), "Origin": "http://localhost:8770"},
        body,
    )
    assert owned and handler.replies[0][0] == 200 and handler.replies[0][1]["action"] == "disable"


# -- through the real Agent Web server, once the parent wires the seam -----------------------


def _wired() -> bool:
    from host_runtime import web

    return "plugin_web.handle" in inspect.getsource(web)


@pytest.fixture
def served_plugins(request: pytest.FixtureRequest) -> Iterator[tuple[Any, Any, FakeManager]]:
    if not _wired():
        pytest.skip("web.py does not route to plugin_web yet (parent-owned seam)")
    web, server, _recorder, _claude = request.getfixturevalue("served")
    manager = FakeManager(_status())
    # The seam may read the manager from Agent Web or from its Host runtime.
    holders = [web, web.runtime]
    previous = [getattr(holder, "plugins", None) for holder in holders]
    for holder in holders:
        holder.plugins = manager
    try:
        yield web, server, manager
    finally:
        for holder, value in zip(holders, previous, strict=True):
            holder.plugins = value


def _http(
    server: Any, path: str, *, token: str | None, origin: str | None = None
) -> tuple[int, Any]:
    host, port = server.server_address[:2]
    request = urllib.request.Request(f"http://127.0.0.1:{port}{path}")
    if token is not None:
        request.add_header("Authorization", "Bearer " + token)
    if origin is not None:
        request.add_header("Origin", origin)
    try:
        with urllib.request.urlopen(request, timeout=10) as reply:  # noqa: S310 - loopback
            return reply.status, json.loads(reply.read())
    except urllib.error.HTTPError as failure:
        return failure.code, json.loads(failure.read() or b"{}")


def test_through_agent_web_the_page_token_and_origin_guard_come_first(
    served_plugins: tuple[Any, Any, FakeManager],
) -> None:
    _web, server, manager = served_plugins
    read = "/api/plugins/hello.app/summary?version=1.0.0"
    assert _http(server, read, token=None)[0] == 401
    assert _http(server, read, token="wrong")[0] == 401
    assert _http(server, read, token=server.token, origin="https://evil.example")[0] == 403
    assert manager.names().count("call_read") == 0
    status, payload = _http(server, read, token=server.token)
    assert status == 200 and payload["data"]["count"] == 3
    (request, _) = next(value for name, value in manager.calls if name == "call_read")
    assert server.token not in request.model_dump_json()
    status, payload = _http(server, "/api/plugin-manager/plugins", token=server.token)
    assert status == 200 and payload["plugins"][0]["plugin_id"] == "hello.app"


# -- the core-rendered page ---------------------------------------------------------------


def test_renderer_source_builds_dom_from_text_only() -> None:
    source = plugin_renderer.PLUGIN_RENDERER_JS
    for forbidden in (
        "innerHTML",
        "outerHTML",
        "insertAdjacentHTML",
        "document.write",
        "eval(",
        "new Function",
        'setAttribute("href',
        'setAttribute("src',
        'createElement("a")',
        'createElement("img")',
        'createElement("iframe")',
        'createElement("script")',
        ".href",
        ".src",
    ):
        assert forbidden not in source, forbidden
    assert "/api/plugin-manager/plugins" in source and "/api/plugins/" in source
    assert str(MAX_PACKAGE_BYTES) in source and str(MAX_TABLE_ROWS) in source
    assert "__" not in source  # every placeholder was filled
    html = plugin_renderer.PLUGIN_PANEL_HTML + plugin_renderer.PLUGIN_NAV_HTML
    for expected in (
        'id="panel-plugin"',
        'id="plugin-page"',
        'id="plugin-list"',
        'id="plugin-install-form"',
        'id="plugin-file"',
        'id="nav-plugins"',
        'id="plugin-nav"',
    ):
        assert expected in html, expected
    assert "<script" not in html and "<iframe" not in html
    assert "{" not in plugin_renderer.PLUGIN_PANEL_HTML  # no template slots for plugin text


def test_the_page_token_is_used_only_for_core_requests() -> None:
    source = plugin_renderer.PLUGIN_RENDERER_JS
    uses = [line for line in source.splitlines() if "TOKEN" in line]
    assert len(uses) == 1 and '"Authorization": "Bearer " + TOKEN' in uses[0]


def _node_harness(tmp_path: Path, body: str) -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is not installed, so the renderer cannot be exercised")
    harness = (
        r"""
const assert = require("node:assert/strict");
class FakeNode {
  constructor(tag, value = "") {
    this.tag = tag; this.value = value; this.children = []; this.attrs = {};
    this.listeners = {}; this.dataset = {}; this.className = ""; this.hidden = false;
    this.disabled = false; this.type = "";
  }
  append(...children) { this.children.push(...children); }
  replaceChildren(...children) { this.children = children; }
  setAttribute(name, value) { this.attrs[name] = String(value); }
  toggleAttribute(name, on) { if (on) this.attrs[name] = ""; else delete this.attrs[name]; }
  removeAttribute(name) { delete this.attrs[name]; }
  addEventListener(name, handler) { this.listeners[name] = handler; }
  set textContent(value) { this.children = [new FakeNode("#text", String(value))]; }
}
const ids = {};
const document = {
  createElement: tag => new FakeNode(tag),
  createTextNode: value => new FakeNode("#text", value),
  getElementById: id => ids[id] || null,
};
const text = value => document.createTextNode(value == null ? "" : String(value));
const el = id => ids[id] || null;
const fetched = [];
let answer = () => ({status: 200, body: {ok: true}});
const fetch = async (path, options) => {
  fetched.push({path, options});
  const {status, body} = answer(path, options);
  return {status, ok: status < 400, json: async () => body};
};
const TOKEN = "page-token";
const api = new Function("document", "text", "el", "fetch", "TOKEN", __SOURCE__ +
  "\nreturn {renderPluginNav, renderPluginList, renderPluginPage, pluginRead, pluginAction," +
  " pluginInstallPayload, pluginCell};")(document, text, el, fetch, TOKEN);
const all = node => [node, ...node.children.flatMap(all)];
const content = node => node.tag === "#text" ? node.value : node.children.map(content).join("");
const tags = node => all(node).map(item => item.tag);
const HOSTILE = __HOSTILE__;
const safe = root => {
  const seen = tags(root);
  for (const bad of ["img", "script", "iframe", "a", "object", "embed", "link", "style"]) {
    assert.ok(!seen.includes(bad), seen.join(","));
  }
  for (const node of all(root)) {
    for (const name of Object.keys(node.attrs)) {
      assert.ok(!name.startsWith("on") && name !== "href" && name !== "src", name);
    }
  }
};
(async () => {
"""
        + body
        + r"""
})().catch(failure => { console.error(failure); process.exit(1); });
"""
    )
    script = harness.replace("__SOURCE__", json.dumps(plugin_renderer.PLUGIN_RENDERER_JS)).replace(
        "__HOSTILE__", json.dumps(HOSTILE)
    )
    path = tmp_path / "plugin-dom.js"
    path.write_text(script, encoding="utf-8")
    checked = subprocess.run(
        [node, str(path)], capture_output=True, check=False, text=True, timeout=30
    )
    assert checked.returncode == 0, checked.stdout + checked.stderr


def _hostile_snapshot() -> dict[str, Any]:
    page = _page(title=HOSTILE, text=HOSTILE)
    active = _status(title=HOSTILE, page=page)
    failed = _status("other", state="failed", title=HOSTILE)
    snapshot = PluginSnapshot(plugins=(active, failed)).model_dump(mode="json")
    snapshot["plugins"][1]["failure"]["message"] = HOSTILE
    return snapshot


def test_renderer_keeps_hostile_plugin_text_as_text(tmp_path: Path) -> None:
    snapshot = json.dumps(_hostile_snapshot())
    _node_harness(
        tmp_path,
        f"""
const snapshot = {snapshot};
const nav = new FakeNode("div");
const opened = [];
api.renderPluginNav(nav, snapshot, (plugin, page) => opened.push([plugin.plugin_id, page.page_id]));
safe(nav);
assert.ok(content(nav).includes(HOSTILE));
const buttons = all(nav).filter(item => item.tag === "button");
assert.equal(buttons.length, 1);  // only the active plugin's page
assert.ok(!JSON.stringify(Object.values(buttons[0].attrs)).includes("<img"));
buttons[0].listeners.click();
assert.deepEqual(opened, [["hello.app", "overview"]]);

const list = new FakeNode("div");
const acted = [];
api.renderPluginList(list, snapshot, (action, plugin) => acted.push([action, plugin.plugin_id]));
safe(list);
assert.ok(content(list).includes(HOSTILE));
assert.ok(content(list).includes("plugin_health_failed"));
const listButtons = all(list).filter(item => item.tag === "button");
const labels = listButtons.map(content);
assert.deepEqual(labels, ["Disable", "Uninstall", "Enable", "Uninstall"]);
listButtons[0].listeners.click();
listButtons[2].listeners.click();
assert.deepEqual(acted, [["disable", "hello.app"], ["enable", "other.app"]]);

const page = new FakeNode("div");
const plugin = snapshot.plugins[0];
const reads = [];
await api.renderPluginPage(page, plugin, plugin.pages[0], async routeId => {{
  reads.push(routeId);
  const items = [{{name: HOSTILE}}, {{name: {{nested: HOSTILE}}}}];
  return {{ok: true, data: {{count: HOSTILE, items}}}};
}});
safe(page);
assert.deepEqual(reads, ["summary"]);  // one read per route, shared by blocks
const shown = content(page);
assert.ok(shown.includes(HOSTILE));
assert.ok(shown.includes(JSON.stringify({{nested: HOSTILE}})));
assert.ok(tags(page).includes("table"));
""",
    )


def test_renderer_reads_with_the_pinned_version_and_reports_failures(tmp_path: Path) -> None:
    _node_harness(
        tmp_path,
        """
answer = () => ({status: 409, body: {ok: false, code: "plugin_version_stale", message: HOSTILE}});
const pinned = {plugin_id: "hello.app", identity: {version: "1.0.0"}};
const failed = await api.pluginRead(pinned, "summary");
assert.equal(failed.ok, false);
assert.equal(failed.code, "plugin_version_stale");
assert.equal(fetched[0].path, "/api/plugins/hello.app/summary?version=1.0.0");
assert.equal(fetched[0].options.headers.Authorization, "Bearer page-token");

const page = new FakeNode("div");
const plugin = {plugin_id: "hello.app", identity: {version: "1.0.0"}};
await api.renderPluginPage(page, plugin, {page_id: "p", title: "T", blocks: [
  {kind: "metric", label: "Count", route_id: "summary", field: "count"}]},
  async () => ({ok: false, code: "plugin_timeout", message: HOSTILE}));
safe(page);
assert.ok(content(page).includes("plugin_timeout"));
assert.ok(!content(page).includes("undefined"));

// Rows beyond the bound are not drawn.
const many = Array.from({length: 500}, (_, index) => ({name: String(index)}));
const table = new FakeNode("div");
await api.renderPluginPage(table, plugin, {page_id: "p", title: "T", blocks: [
  {kind: "table", title: null, route_id: "summary", field: "items",
   columns: [{key: "name", label: "Name"}]}]}, async () => ({ok: true, data: {items: many}}));
assert.ok(all(table).filter(item => item.tag === "tr").length <= __ROWS__ + 1);

answer = () => ({status: 200, body: {ok: true, action: "disable", status: "succeeded"}});
const acted = await api.pluginAction("disable", "hello.app");
assert.equal(acted.ok, true);
const last = fetched.at(-1);
assert.equal(last.path, "/api/plugin-manager/disable");
assert.equal(last.options.method, "POST");
assert.deepEqual(JSON.parse(last.options.body), {plugin_id: "hello.app"});

assert.equal(api.pluginCell(null), "");
assert.equal(api.pluginCell(true), "true");
assert.equal(api.pluginCell({a: 1}), '{"a":1}');
assert.equal(api.pluginInstallPayload({size: __MAX__ + 1}).ok, false);
assert.equal(api.pluginInstallPayload({size: 10}).ok, true);
""".replace("__ROWS__", str(MAX_TABLE_ROWS)).replace("__MAX__", str(MAX_PACKAGE_BYTES)),
    )
