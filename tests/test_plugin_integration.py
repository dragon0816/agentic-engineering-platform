"""Feature plugins end to end with real synthetic workers (Slice 1,
docs/phases/FEATURE_PLUGIN_SLICE1_PLAN_20261113.md, task 4).

Real subprocess workers speak the existing JSON-lines protocol; tools run
through the real Bridge with the existing per-turn receipts; on-disk counters
prove how many times a write actually happened. Synthetic local data only.
"""

from __future__ import annotations

import asyncio
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from plugin_fixture_helpers import (
    build_manager,
    build_package,
    capability_identity,
    origin,
    package_bytes,
)
from test_chat_authoring import context

from agent.turn_effects import turn_scope
from capabilities.runtime import CapabilityInvocation, InstalledCapabilities
from common.assets import AssetIdentity
from common.plugins import PluginReadRequest
from extensions.runtime import ExtensionRequest, JsonLineSubprocessSession
from workflow.dispatch import BridgeExecutor

A, B = "alpha-lab", "beta-lab"
_BOOT = (
    "import runpy, sys; sys.path.insert(0, sys.argv[1]); "
    "runpy.run_module(sys.argv[2], run_name='__main__')"
)


def _identity(namespace: str, local: str, version: str = "1.0.0") -> AssetIdentity:
    return AssetIdentity.model_validate(capability_identity(namespace, local, version))


def _run(installed: InstalledCapabilities, target: AssetIdentity, **arguments: Any) -> Any:
    bridge = BridgeExecutor(installed)
    invocation = CapabilityInvocation(context=context(), target=target, arguments=arguments)
    return asyncio.run(bridge.execute(invocation))


def _read(manager: Any, namespace: str, version: str = "1.0.0", route: str = "summary") -> Any:
    request = PluginReadRequest(
        request_id="read-1", plugin_id=f"{namespace}.fixture", version=version, route_id=route
    )
    return manager.call_read(request, timeout_seconds=10)


def _counter(workspace: Path, namespace: str) -> int:
    path = workspace / "plugin-data" / namespace / "fixture" / "counter.txt"
    return int(path.read_text(encoding="utf-8")) if path.is_file() else 0


def _registered(installed: InstalledCapabilities, target: AssetIdentity) -> bool:
    try:
        return installed.get(target) is not None
    except (KeyError, LookupError):
        return False


@pytest.fixture
def started(tmp_path: Path) -> Any:
    workspace = tmp_path / "ws"
    installed = InstalledCapabilities()
    manager = build_manager(workspace, installed)
    yield workspace, installed, manager
    manager.close()


# -- the fixture itself speaks the existing protocol (no production manager) ---------------


def test_fixture_worker_speaks_the_existing_jsonl_protocol(tmp_path: Path) -> None:
    package = build_package(A)
    staged = tmp_path / "staged"
    for item in package.files:
        target = staged / item.path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(item.raw)
    (staged / "package.json").write_bytes(package.to_bytes())
    data = tmp_path / "data"
    data.mkdir()
    env = {
        "AEP_PLUGIN_PACKAGE_FILE": str(staged / "package.json"),
        "AEP_PLUGIN_DATA_ROOT": str(data),
        "SystemRoot": __import__("os").environ.get("SystemRoot", ""),
    }
    runtime = package.manifest.runtime
    assert runtime is not None
    process = subprocess.Popen(
        [sys.executable, "-I", "-u", "-c", _BOOT, str(staged / "worker"), runtime.module],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
        env=env,
    )
    session = JsonLineSubprocessSession(process)
    try:
        health = session.exchange(ExtensionRequest(request_id="h", operation="health"), 10)
        assert health.status == "healthy"
        assert list(health.capabilities) == [c.spec.identity for c in package.manifest.capabilities]
        write = _identity(A, "write_note")
        saved = session.exchange(
            ExtensionRequest(
                request_id="w", operation="invoke", capability=write, arguments={"note": "n1"}
            ),
            10,
        )
        assert (saved.status, saved.data) == ("succeeded", {"saved": True, "counter": 1})
        refused = session.exchange(
            ExtensionRequest(
                request_id="f", operation="invoke", capability=write, arguments={"note": "FAIL"}
            ),
            10,
        )
        assert (refused.status, refused.code) == ("failed", "fixture_failure")
        read = session.exchange(
            ExtensionRequest(
                request_id="r", operation="invoke", capability=_identity(A, "read_summary")
            ),
            10,
        )
        assert read.data == {"count": 1, "items": [{"label": "note-1", "value": "n1"}]}
        assert (data / "counter.txt").read_text(encoding="utf-8") == "1"
    finally:
        session.close()


# -- manager, Bridge and API end to end ----------------------------------------------------


def test_two_plugins_run_side_by_side_through_bridge_and_api(started: Any) -> None:
    workspace, installed, manager = started
    for namespace in (A, B):
        result = manager.install(package_bytes(namespace), origin())
        assert result.status == "succeeded", result.failure
        assert result.plugin.state == "active"
    snapshot = manager.snapshot()
    assert {p.plugin_id for p in snapshot.plugins if p.state == "active"} == {
        f"{A}.fixture",
        f"{B}.fixture",
    }
    for namespace in (A, B):
        assert _registered(installed, _identity(namespace, "read_summary"))
        assert _registered(installed, _identity(namespace, "write_note"))

    written = _run(installed, _identity(A, "write_note"), note="hello")
    assert written.status == "succeeded" and written.data == {"saved": True, "counter": 1}
    assert _counter(workspace, A) == 1 and _counter(workspace, B) == 0

    a = _read(manager, A)
    assert a.status == "succeeded"
    assert a.data == {"count": 1, "items": [{"label": "note-1", "value": "hello"}]}
    b = _read(manager, B)
    assert b.status == "succeeded" and b.data == {"count": 0, "items": []}
    unknown = _read(manager, A, route="missing")
    assert unknown.status == "failed" and unknown.data is None
    stale = _read(manager, A, version="9.9.9")
    assert stale.status == "failed" and stale.data is None


def test_a_successful_write_runs_once_per_turn_and_failures_are_not_cached(started: Any) -> None:
    workspace, installed, manager = started
    assert manager.install(package_bytes(A), origin()).status == "succeeded"
    write = _identity(A, "write_note")
    with turn_scope():
        first = _run(installed, write, note="once")
        again = _run(installed, write, note="once")
        assert first.status == again.status == "succeeded"
        assert first.handler_invoked and not again.handler_invoked
        assert _counter(workspace, A) == 1
        failed = _run(installed, write, note="FAIL")
        failed_again = _run(installed, write, note="FAIL")
        assert failed.status == failed_again.status == "failed"
        assert failed.handler_invoked and failed_again.handler_invoked
        assert _counter(workspace, A) == 1
    with turn_scope():
        assert _run(installed, write, note="once").handler_invoked
    assert _counter(workspace, A) == 2


def test_disable_enable_restart_and_uninstall_keep_user_data(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    installed = InstalledCapabilities()
    manager = build_manager(workspace, installed)
    try:
        assert manager.install(package_bytes(A), origin()).status == "succeeded"
        assert _run(installed, _identity(A, "write_note"), note="kept").status == "succeeded"
        assert manager.disable(f"{A}.fixture", origin()).status == "succeeded"
        assert not _registered(installed, _identity(A, "write_note"))
        assert _read(manager, A).status == "failed"
        assert manager.enable(f"{A}.fixture", origin()).status == "succeeded"
        assert _read(manager, A).data["count"] == 1
    finally:
        manager.close()

    restarted = InstalledCapabilities()
    again = build_manager(workspace, restarted)
    try:
        again.restore()
        status = again.snapshot().get(f"{A}.fixture")
        assert status is not None and status.state == "active"
        assert _registered(restarted, _identity(A, "read_summary"))
        assert _read(again, A).data["count"] == 1
        assert again.uninstall(f"{A}.fixture", origin()).status == "succeeded"
        assert again.snapshot().get(f"{A}.fixture") is None
        assert not _registered(restarted, _identity(A, "read_summary"))
        assert _counter(workspace, A) == 1  # uninstall keeps the plugin's data
        assert again.install(package_bytes(A), origin()).status == "succeeded"
        assert _read(again, A).data["count"] == 1
    finally:
        again.close()


def _asset_files(workspace: Path, namespace: str) -> list[Path]:
    """Installed asset manifests of `namespace` in the workspace's Skill/Workflow folders."""
    from host_runtime.contracts import HostLayout

    layout = HostLayout.under(workspace)
    return sorted(
        path
        for folder in (layout.skills, layout.workflows)
        if folder.is_dir()
        for path in folder.rglob(f"{namespace}__*.json")
    )


def test_bundled_assets_are_installed_honestly_and_removed_with_the_plugin(started: Any) -> None:
    workspace, installed, manager = started
    assert manager.install(package_bytes(A), origin()).status == "succeeded"
    found = _asset_files(workspace, A)
    names = [path.name for path in found]
    assert any("summary-skill" in name for name in names), names
    assert any("summary-flow" in name for name in names), names
    for path in found:
        metadata = json.loads(path.read_text(encoding="utf-8"))["metadata"]
        assert metadata["business_approval"]["status"] == "pending"
        assert metadata["business_approval"]["reviewer"] is None
    assert manager.uninstall(f"{A}.fixture", origin()).status == "succeeded"
    # Unmodified assets the plugin owned are removed with it; nothing else is touched.
    assert _asset_files(workspace, A) == []


def test_a_user_modified_bundled_asset_survives_uninstall(started: Any) -> None:
    workspace, installed, manager = started
    assert manager.install(package_bytes(A), origin()).status == "succeeded"
    skill = next(p for p in _asset_files(workspace, A) if "summary-skill" in p.name)
    changed = json.loads(skill.read_text(encoding="utf-8"))
    changed["instructions"] = "Changed on this PC by the person."
    skill.write_text(json.dumps(changed, indent=2), encoding="utf-8")
    assert manager.uninstall(f"{A}.fixture", origin()).status == "succeeded"
    assert skill.is_file()
    assert (
        json.loads(skill.read_text(encoding="utf-8"))["instructions"]
        == "Changed on this PC by the person."
    )


def test_active_work_blocks_a_version_switch_and_keeps_the_old_bindings(started: Any) -> None:
    workspace, installed, manager = started
    assert manager.install(package_bytes(A), origin()).status == "succeeded"
    manager.set_busy_probe(lambda: True)
    blocked = manager.install(package_bytes(A, "1.0.1"), origin())
    assert blocked.status == "failed" and blocked.failure.code == "plugin_busy"
    assert manager.snapshot().get(f"{A}.fixture").identity.version == "1.0.0"
    assert _registered(installed, _identity(A, "write_note", "1.0.0"))
    assert not _registered(installed, _identity(A, "write_note", "1.0.1"))
    manager.set_busy_probe(lambda: False)
    switched = manager.install(package_bytes(A, "1.0.1"), origin())
    assert switched.status == "succeeded", switched.failure
    assert _registered(installed, _identity(A, "write_note", "1.0.1"))
    assert not _registered(installed, _identity(A, "write_note", "1.0.0"))


def test_version_identity_is_exact_and_downgrades_are_refused(started: Any) -> None:
    _, _, manager = started
    assert manager.install(package_bytes(A), origin()).status == "succeeded"
    other = manager.install(package_bytes(A, worker="bad_health"), origin())
    assert other.status == "failed" and other.failure.code == "plugin_version_conflict"
    older = manager.install(package_bytes(A, "0.9.0"), origin())
    assert older.status == "failed" and older.failure.code == "plugin_downgrade_refused"


@pytest.mark.parametrize("worker", ["bad_health", "crash"])
def test_an_unhealthy_worker_leaves_nothing_registered(started: Any, worker: str) -> None:
    workspace, installed, manager = started
    result = manager.install(package_bytes(A, worker=worker), origin())
    assert result.status == "failed"
    assert result.failure.code in {"plugin_health_failed", "plugin_worker_failed"}
    assert not _registered(installed, _identity(A, "read_summary"))
    assert not _registered(installed, _identity(A, "write_note"))
    status = manager.snapshot().get(f"{A}.fixture")
    assert status is None or (status.state != "active" and not status.capabilities)
    assert _asset_files(workspace, A) == []  # a failed install leaves no bundled assets


def test_tampered_envelope_and_changed_staged_bytes_are_refused(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    installed = InstalledCapabilities()
    manager = build_manager(workspace, installed)
    try:
        envelope = json.loads(package_bytes(A))
        envelope["files"][0]["content"] = "AAAA"
        refused = manager.install(json.dumps(envelope).encode("utf-8"), origin())
        assert refused.status == "failed"
        assert refused.failure.code in {"plugin_package_invalid", "plugin_digest_mismatch"}
        assert not _registered(installed, _identity(A, "read_summary"))
        assert manager.install(package_bytes(A), origin()).status == "succeeded"
    finally:
        manager.close()
    staged_workers = [p for p in workspace.rglob("worker.py") if "aep_plugin_alpha_lab" in p.parts]
    assert staged_workers, "the staged worker is kept in the workspace"
    for path in staged_workers:
        path.write_bytes(path.read_bytes() + b"\n# changed after verification\n")
    restarted = InstalledCapabilities()
    again = build_manager(workspace, restarted)
    try:
        again.restore()
        status = again.snapshot().get(f"{A}.fixture")
        assert status is not None and status.state == "failed"
        assert status.failure.code == "plugin_staged_changed"
        assert not _registered(restarted, _identity(A, "read_summary"))
    finally:
        again.close()


# -- real local Agent Web: authentication, direct install, read, page mount ---------------


class _Served:
    """A real loopback Agent Web on a fresh synthetic workspace."""

    def __init__(self, tmp_path: Path) -> None:
        import threading
        from urllib.parse import parse_qs, urlsplit

        from test_host_wiring import ready

        from host_runtime.host import build_runtime
        from host_runtime.web import AgentWeb, AgentWebServer

        config, layout = ready(tmp_path)
        self.workspace = Path(layout.workspace_root)
        self._built = build_runtime(config, layout=layout)
        self.runtime = self._built.__enter__()
        self.server = AgentWebServer(AgentWeb(self.runtime))
        place = urlsplit(self.server.address)
        self.base = f"{place.scheme}://{place.netloc}"
        self.token = parse_qs(place.query)["token"][0]
        self._thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self._thread.start()

    def call(
        self,
        method: str,
        path: str,
        body: bytes | None = None,
        *,
        token: bool = True,
        origin: str | None = None,
    ) -> tuple[int, Any]:
        import urllib.error
        import urllib.request

        headers = {"Origin": origin or self.base}
        if token:
            headers["Authorization"] = "Bearer " + self.token
        if body is not None:
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(
            self.base + path, data=body, headers=headers, method=method
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                raw = response.read()
                status = response.status
        except urllib.error.HTTPError as error:
            raw, status = error.read(), error.code
        try:
            return status, json.loads(raw)
        except ValueError:
            return status, raw.decode("utf-8", "replace")

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self._built.__exit__(None, None, None)


@pytest.fixture
def served(tmp_path: Path) -> Any:
    host = _Served(tmp_path)
    yield host
    host.close()


def test_without_plugins_agent_web_starts_and_lists_nothing(served: _Served) -> None:
    status, listed = served.call("GET", "/api/plugin-manager/plugins")
    assert status == 200 and listed["ok"] is True and listed["plugins"] == []
    status, page = served.call("GET", "/?token=" + served.token)
    assert status == 200 and 'id="panel-plugin"' in page and 'id="nav-plugins"' in page


def test_plugin_routes_require_the_core_token_and_a_loopback_origin(served: _Served) -> None:
    for method, path, body in (
        ("GET", "/api/plugin-manager/plugins", None),
        ("POST", "/api/plugin-manager/install", package_bytes(A)),
        ("GET", f"/api/plugins/{A}.fixture/summary?version=1.0.0", None),
    ):
        status, _ = served.call(method, path, body, token=False)
        assert status == 401, (method, path)
    status, refused = served.call(
        "POST", "/api/plugin-manager/install", package_bytes(A), origin="http://example.com"
    )
    assert status == 403 and refused["code"] == "origin_refused"
    manager = served.runtime.plugins
    assert manager is not None
    assert manager.snapshot().get(f"{A}.fixture") is None


def test_direct_install_over_http_serves_declared_data_without_an_approval(served: _Served) -> None:
    status, installed = served.call("POST", "/api/plugin-manager/install", package_bytes(A))
    assert status == 200, installed
    assert installed["ok"] is True and installed["plugin"]["state"] == "active"
    assert installed["plugin"]["installed_by"]["channel"] == "agent-web"
    status, approvals = served.call("GET", "/api/approvals")
    assert status == 200 and approvals.get("approvals", []) == []

    read = f"/api/plugins/{A}.fixture/summary?version=1.0.0"
    status, empty = served.call("GET", read)
    assert status == 200 and empty["data"] == {"count": 0, "items": []}
    bridge = served.runtime.agent.gateway.bridge.installed
    assert _run(bridge, _identity(A, "write_note"), note="over-http").status == "succeeded"
    status, one = served.call("GET", read)
    assert status == 200
    assert one["data"] == {"count": 1, "items": [{"label": "note-1", "value": "over-http"}]}

    status, listed = served.call("GET", "/api/plugin-manager/plugins")
    page = next(p for p in listed["plugins"] if p["plugin_id"] == f"{A}.fixture")["pages"][0]
    assert page["page_id"] == "overview"
    assert page["blocks"][0] == {"kind": "text", "text": "<b>Synthetic</b> data only."}
    status, html = served.call("GET", "/?token=" + served.token)
    assert status == 200 and "<b>Synthetic</b>" not in html  # page data is never baked in as HTML


def test_plugin_read_paths_and_errors_are_exact(served: _Served) -> None:
    assert served.call("POST", "/api/plugin-manager/install", package_bytes(A))[0] == 200
    base = f"/api/plugins/{A}.fixture"
    cases = {
        f"{base}/summary": (400, "plugin_request_invalid"),
        f"{base}/summary?version=1.0.0&x=1": (400, "plugin_request_invalid"),
        f"{base}/summary?version=2.0.0": (409, "plugin_version_stale"),
        f"{base}/missing?version=1.0.0": (404, "plugin_route_unknown"),
        f"/api/plugins/{B}.fixture/summary?version=1.0.0": (404, "plugin_not_installed"),
        f"/api/plugins/%2e%2e/{A}.fixture/summary?version=1.0.0": (404, "plugin_route_unknown"),
        f"{base}/Summary?version=1.0.0": (404, "plugin_route_unknown"),
    }
    for path, (expected, code) in cases.items():
        status, answer = served.call("GET", path)
        assert (status, answer.get("code")) == (expected, code), path
    status, unknown = served.call("POST", "/api/plugin-manager/upgrade-all", b"{}")
    assert (status, unknown["code"]) == (404, "no_such_page")
    body = json.dumps({"plugin_id": f"{A}.fixture"}).encode("utf-8")
    status, disabled = served.call("POST", "/api/plugin-manager/disable", body)
    assert status == 200 and disabled["plugin"]["state"] == "disabled"
    status, inactive = served.call("GET", f"{base}/summary?version=1.0.0")
    assert (status, inactive["code"]) == (409, "plugin_not_active")


def test_a_corrupt_ledger_is_reported_unavailable_not_an_empty_list(served: _Served) -> None:
    status, installed = served.call("POST", "/api/plugin-manager/install", package_bytes(A))
    assert status == 200, installed
    ledger = served.workspace / "plugins" / "ledger.json"
    assert ledger.is_file()
    corrupt = b'{"not": "a plugin ledger"'
    ledger.write_bytes(corrupt)
    status, listed = served.call("GET", "/api/plugin-manager/plugins")
    # A broken record is never presented as "no plugins installed".
    assert (status, listed.get("code")) == (503, "plugin_unavailable"), listed
    assert ledger.read_bytes() == corrupt  # nothing rewrote or "repaired" it
    status, page = served.call("GET", "/?token=" + served.token)
    assert status == 200 and 'id="panel-plugin"' in page  # the core page still works


# -- coexistence: a published-Wiki Knowledge answer is unchanged by an installed plugin ----


def _tree(root: Path) -> dict[str, str]:
    """Every file under `root` with its digest: proof that nothing was written."""
    import hashlib

    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def test_an_installed_plugin_leaves_a_published_wiki_answer_and_its_sources_unchanged(
    tmp_path: Path,
) -> None:
    import test_vault_asking_e2e as asking

    publisher, drive, repo_id = asking._wiki_published(tmp_path)
    config, layout = asking._wiki_host(tmp_path, repo_id)
    reader = Path(layout.workspace_root)
    asking._wiki_join(reader, drive / repo_id)
    sources = {"drive": drive, "reader": reader / "knowledge-repos"}
    assert all(folder.is_dir() and any(folder.rglob("*")) for folder in sources.values())
    model = asking._Model(asking.WIKI_TOOL, asking.WIKI_ARGUMENTS)
    with asking._served(config, layout, model) as server:
        baseline = asking._ask(server)
        before = {name: _tree(folder) for name, folder in sources.items()}
        manager = server.web.runtime.plugins
        assert manager is not None
        result = manager.install(package_bytes(A), origin())
        assert result.status == "succeeded", result.failure
        assert result.plugin is not None and result.plugin.state == "active"
        with_plugin = asking._ask(server)
    # The same fact, from the same published version, cited the same way.
    assert "FACT-PUBLISHED" in baseline
    assert "資料來源：知識庫 tester-knowledge 發佈版本 v1" in baseline
    assert with_plugin == baseline
    assert set(asking.FACT.findall(with_plugin)) == {"FACT-PUBLISHED"}
    # Asking did not run the plugin's write tool, and Raw/Wiki stayed byte-for-byte.
    assert _counter(reader, A) == 0
    assert not (reader / "plugin-data" / A / "fixture" / "notes.jsonl").exists()
    assert {name: _tree(folder) for name, folder in sources.items()} == before


def _found(value: Any, wanted: Any) -> bool:
    """Whether `wanted` appears anywhere in a JSON result (a step's actual output)."""
    if value == wanted:
        return True
    if isinstance(value, dict):
        return any(_found(item, wanted) for item in value.values())
    if isinstance(value, list):
        return any(_found(item, wanted) for item in value)
    return False


def test_bundled_skill_and_workflow_are_live_and_run_without_a_restart(served: _Served) -> None:
    package = build_package(A)
    flow = next(item for item in package.manifest.assets if item.kind == "workflow").identity
    skill = next(item for item in package.manifest.assets if item.kind == "skill")
    gateway = served.runtime.agent.gateway
    assert gateway.engine.workflows.get(flow) is None
    status, installed = served.call("POST", "/api/plugin-manager/install", package.to_bytes())
    assert status == 200, installed

    # Live in the running Host: the Workflow engine and the Skill registry, no restart.
    assert gateway.engine.workflows.get(flow) is not None
    alias = A.replace("-", "_") + "_summary"
    live_skill = gateway.router.commands.skills.get(A, alias)
    assert live_skill is not None and live_skill.metadata.identity == skill.identity

    # The bundled Workflow runs through the existing route and returns the worker's answer.
    bridge = gateway.bridge.installed
    assert _run(bridge, _identity(A, "write_note"), note="via-flow").status == "succeeded"
    launch = {
        "workflow": flow.model_dump(mode="json"),
        "arguments": {},
        "idempotency_key": "plugin-flow-run-1",
    }
    status, ran = served.call("POST", "/api/workflows/run", json.dumps(launch).encode("utf-8"))
    assert status == 200, ran
    assert ran["ok"] is True, ran.get("answer")
    assert ran["outcome"]["workflow"]["run"]["status"] == "succeeded"
    expected = {"count": 1, "items": [{"label": "note-1", "value": "via-flow"}]}
    assert _found(ran["outcome"], expected), "the run carries the worker's actual output"

    # Uninstall removes only this plugin's live entries.
    skills = gateway.router.commands.skills

    def others() -> tuple[set[Any], set[Any]]:
        return (
            {m.metadata.identity for m in skills.manifests() if m.metadata.identity.namespace != A},
            {
                w.metadata.identity
                for w in gateway.engine.workflows.manifests()
                if w.metadata.identity.namespace != A
            },
        )

    before = others()
    body = json.dumps({"plugin_id": f"{A}.fixture"}).encode("utf-8")
    assert served.call("POST", "/api/plugin-manager/uninstall", body)[0] == 200
    assert gateway.engine.workflows.get(flow) is None
    assert skills.get(A, alias) is None
    assert others() == before
