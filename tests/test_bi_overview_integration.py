"""BI overview plugin (H1/H4) end to end on a real local Host and HTTP.

Owner consent 2026-11-15, `docs/phases/FEATURE_PLUGIN_BI_OVERVIEW_PLAN_20261114.md`
acceptance 3-5: the overview page reads the real synthetic BI dataset through a
page service that is not an Agent tool; installing it changes no model-offered
tool, existing BI API/Skill/data, or published-Wiki answer and citation.
Synthetic data only (the built-in fictional demo cards and a test Wiki), no
company data, real model, network or resident AEP.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import threading
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import test_vault_asking_e2e as asking
from test_agent_web import base
from test_host_models import GatewayReply

from common.plugins import PluginCapability, PluginField, PluginManifest, parse_plugin_package
from host_runtime.bi_cards_api import route as bi_route
from host_runtime.host import build_runtime
from host_runtime.tool_access import ToolAccess
from host_runtime.web import AgentWeb, AgentWebServer

PLUGIN_ID = "bi-overview.overview"
BUILDER = Path(__file__).resolve().parents[1] / "scripts" / "build_bi_overview_plugin.py"
DEMO_CARDS = 104


# -- the package under test (built by the plugin's own builder) -----------------------------


def _overview_bytes() -> bytes:
    """Envelope bytes from `scripts/build_bi_overview_plugin.py` (`package_bytes()`)."""
    spec = importlib.util.spec_from_file_location("build_bi_overview_plugin", BUILDER)
    assert spec is not None and spec.loader is not None, "the overview builder is missing"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    built = module.package_bytes()
    assert isinstance(built, bytes)
    return built


def _page_service(manifest: PluginManifest) -> tuple[PluginCapability, str, PluginField]:
    """The page service, the route that reads it and its dataset rows field,
    taken from the declaration itself rather than assumed names."""
    services = manifest.page_services
    assert len(services) == 1, "the overview declares exactly one page service"
    service = services[0]
    route = next(item for item in manifest.routes if item.capability == service.spec.name)
    rows = [field for field in service.outputs if field.type == "rows"]
    assert len(rows) == 1, "one rows field lists the datasets"
    assert {"name", "cards", "status"} <= set(rows[0].columns), rows[0].columns
    return service, route.route_id, rows[0]


# -- observation helpers --------------------------------------------------------------------


class _RecordingModel(asking._Model):
    """The scripted Wiki model, recording the tool names offered on EVERY request
    (the base records only the first)."""

    def __init__(self, tool: str, arguments: Mapping[str, Any]) -> None:
        super().__init__(tool, arguments)
        self.offered_each: list[frozenset[str]] = []

    def send(
        self, url: str, body: bytes, headers: Mapping[str, str], timeout_s: float
    ) -> GatewayReply:
        payload = json.loads(body)
        tools = payload.get("tools")
        if tools:
            self.offered_each.append(frozenset(t["function"]["name"] for t in tools))
        return super().send(url, body, headers, timeout_s)


def _tree(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _catalog(runtime: Any) -> set[str]:
    """Every target in the ToolAccess catalog, across all pages."""
    access = ToolAccess(runtime.agent.gateway.bridge, mcp=runtime.mcp)
    targets: set[str] = set()
    cursor: int | None = 0
    while cursor is not None:
        page = access.catalog(cursor=cursor, limit=100)
        targets |= {item["target"] for item in page["tools"]}
        cursor = page["next_cursor"]
    return targets


def _registered(runtime: Any) -> set[tuple[str, str, str]]:
    return {
        (spec.identity.namespace, spec.identity.name, spec.identity.version)
        for spec in runtime.agent.gateway.bridge.installed.discover()
    }


def _skills(runtime: Any) -> set[tuple[str, str, str]]:
    return {
        (m.metadata.identity.namespace, m.metadata.identity.name, m.metadata.identity.version)
        for m in runtime.agent.gateway.router.commands.skills.manifests()
    }


def _http(
    server: AgentWebServer, method: str, path: str, body: bytes | None = None
) -> tuple[int, Any]:
    import urllib.error
    import urllib.request

    request = urllib.request.Request(
        base(server) + path,
        data=body,
        method=method,
        headers={
            "Authorization": "Bearer " + server.token,
            "Origin": base(server),
            **({"Content-Type": "application/json"} if body is not None else {}),
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read())


@contextmanager
def _served(config: Any, layout: Any, model: Any) -> Iterator[AgentWebServer]:
    with build_runtime(config, layout=layout, model_transport=model) as runtime:
        web = AgentWeb(runtime)
        web.start_laya_tunnel = lambda settings=None: None  # type: ignore[method-assign]
        server = AgentWebServer(web)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield server
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


def _install(server: AgentWebServer, raw: bytes) -> dict[str, Any]:
    status, installed = _http(server, "POST", "/api/plugin-manager/install", raw)
    assert status == 200, installed
    assert installed["plugin"]["state"] == "active"
    status, approvals = _http(server, "GET", "/api/approvals")
    assert status == 200 and approvals.get("approvals", []) == []  # direct, no card
    return dict(installed["plugin"])


def _read_page(server: AgentWebServer, route_id: str, version: str) -> tuple[int, Any]:
    return _http(server, "GET", f"/api/plugins/{PLUGIN_ID}/{route_id}?version={version}")


# -- acceptance ------------------------------------------------------------------------------


def test_the_installed_overview_shows_real_bi_and_changes_no_tool_answer_or_data(
    tmp_path: Path,
) -> None:
    raw = _overview_bytes()
    manifest = parse_plugin_package(raw).manifest
    assert manifest.plugin_id == PLUGIN_ID and manifest.data.reads == ("bi",)
    service, route_id, rows_field = _page_service(manifest)
    version = manifest.identity.version

    publisher, drive, repo_id = asking._wiki_published(tmp_path)
    config, layout = asking._wiki_host(tmp_path, repo_id)
    reader = Path(layout.workspace_root)
    asking._wiki_join(reader, drive / repo_id)
    status, loaded = bi_route(
        reader, "tester", "POST", "/api/bi/demo/load", {}, {"dataset": "demo"}
    )
    assert status == 200 and loaded["imported"]["created"] == DEMO_CARDS
    bi_root = reader / "bi"
    model = _RecordingModel(asking.WIKI_TOOL, asking.WIKI_ARGUMENTS)

    with _served(config, layout, model) as server:
        runtime = server.web.runtime
        baseline_answer = asking._ask(server)
        baseline_offered = list(model.offered_each)
        assert baseline_offered, "the conversation offered tools"
        baseline_catalog = _catalog(runtime)
        baseline_registered = _registered(runtime)
        baseline_skills = _skills(runtime)
        status, baseline_datasets = _http(server, "GET", "/api/bi/datasets")
        assert status == 200
        baseline_bi = _tree(bi_root)

        plugin = _install(server, raw)
        assert plugin["plugin_id"] == PLUGIN_ID
        status, page = _read_page(server, route_id, version)
        assert status == 200, page
        rows = page["data"][rows_field.name]
        demo = next(row for row in rows if row["name"] == "demo")
        assert demo["status"] == "ready" and demo["cards"] == str(DEMO_CARDS)
        assert str(demo["schema_ref"]).startswith("bi.")  # declared column carries the value
        assert page["data"]["bi_status"] == "ready" and page["data"]["coverage"] == "完整"
        assert page["data"]["cards_total"] == str(DEMO_CARDS)

        # The page service is not an Agent tool anywhere.
        service_identity = service.spec.identity
        assert runtime.agent.gateway.bridge.installed.get(service_identity) is None
        key = (service_identity.namespace, service_identity.name, service_identity.version)
        assert key not in _registered(runtime)
        assert _registered(runtime) == baseline_registered
        assert _catalog(runtime) == baseline_catalog
        assert not [t for t in _catalog(runtime) if t.startswith("bi-overview/")]

        with_plugin_answer = asking._ask(server)
        later_offered = model.offered_each[len(baseline_offered) :]
        assert later_offered, "the second question offered tools too"
        assert set(later_offered) == set(baseline_offered)  # identical names, every request
        assert not [n for names in later_offered for n in names if "overview" in n]

        status, datasets = _http(server, "GET", "/api/bi/datasets")
        assert (status, datasets) == (200, baseline_datasets)
        assert {key for key in _skills(runtime) if key[0] != "bi-overview"} == baseline_skills
        assert _tree(bi_root) == baseline_bi  # the read changed no BI byte

        body = json.dumps({"plugin_id": PLUGIN_ID}).encode("utf-8")
        status, removed = _http(server, "POST", "/api/plugin-manager/uninstall", body)
        assert status == 200, removed
        assert _tree(bi_root) == baseline_bi  # uninstall keeps BI
        status, after = _http(server, "GET", "/api/bi/datasets")
        assert (status, after) == (200, baseline_datasets)
        assert _registered(runtime) == baseline_registered

    # The same published-Wiki answer, version and citation before and after.
    assert "FACT-PUBLISHED" in baseline_answer
    assert "資料來源：知識庫 tester-knowledge 發佈版本 v1" in baseline_answer
    assert with_plugin_answer == baseline_answer


def _plain_host(tmp_path: Path) -> tuple[Any, Any]:
    from test_host_wiring import ready

    return ready(tmp_path)


def test_without_any_bi_folder_the_page_says_missing_not_an_empty_complete_list(
    tmp_path: Path,
) -> None:
    raw = _overview_bytes()
    manifest = parse_plugin_package(raw).manifest
    _, route_id, rows_field = _page_service(manifest)
    config, layout = _plain_host(tmp_path)
    with _served(config, layout, None) as server:
        _install(server, raw)
        assert not (Path(layout.workspace_root) / "bi").exists()
        status, page = _read_page(server, route_id, manifest.identity.version)
        assert status == 200, page
        data = page["data"]
        assert data["bi_status"] == "missing" and data[rows_field.name] == []
        assert data["datasets_found"] == 0 and data["cards_total"] == "—"
        assert data["coverage"] != "完整"
        assert not (Path(layout.workspace_root) / "bi").exists()  # installation created nothing


def test_a_dataset_being_written_is_busy_with_no_count_and_the_list_is_not_complete(
    tmp_path: Path,
) -> None:
    raw = _overview_bytes()
    manifest = parse_plugin_package(raw).manifest
    _, route_id, rows_field = _page_service(manifest)
    config, layout = _plain_host(tmp_path)
    workspace = Path(layout.workspace_root)
    status, loaded = bi_route(
        workspace, "tester", "POST", "/api/bi/demo/load", {}, {"dataset": "demo"}
    )
    assert status == 200 and loaded["imported"]["created"] == DEMO_CARDS
    database = workspace / "bi" / "demo" / "bi.sqlite"
    assert database.is_file()
    journal = database.with_name(database.name + "-journal")
    journal.write_bytes(b"")
    before = _tree(workspace / "bi")
    with _served(config, layout, None) as server:
        _install(server, raw)
        status, page = _read_page(server, route_id, manifest.identity.version)
    assert status == 200, page
    demo = next(row for row in page["data"][rows_field.name] if row["name"] == "demo")
    assert demo["status"] == "busy" and demo["reason"] == "write_in_progress"
    assert demo["cards"] == "—"  # unknown, never reported as zero
    data = page["data"]
    assert data["datasets_unavailable"] == 1 and data["cards_known"] == 0
    assert data["cards_total"] == "—" and data["coverage"].startswith("不完整")
    assert _tree(workspace / "bi") == before  # the reader recovered or removed nothing
