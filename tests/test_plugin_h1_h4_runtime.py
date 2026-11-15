"""H1/H4 runtime (owner consent 2026-11-15): the declared existing-BI context reaches
only declaring workers, as the manager's own path; page-only services answer page
reads without a Bridge registration. Synthetic data only."""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from test_plugin_manager import ORIGIN, code, found, identity, invoke, manifest_data

from capabilities.runtime import CapabilityRefused, InstalledCapabilities
from common.plugins import PluginManifest, PluginPackage, PluginReadRequest
from host_runtime.contracts import HostLayout
from plugins import PluginManager
from plugins.process import READ_BI_ENV

NEW_API = {"minimum": "1.1.0", "below": "2.0.0"}

WORKER = r"""
import json, os, sys
from pathlib import Path

PACKAGE = json.loads(Path(os.environ["AEP_PLUGIN_PACKAGE_FILE"]).read_text(encoding="utf-8"))
CAPS = [c["spec"]["identity"] for c in PACKAGE["manifest"]["capabilities"]]
MODE = "__MODE__"


def reply(**fields):
    sys.stdout.write(json.dumps({"protocol": "aep-extension-jsonl/v1", **fields}) + "\n")
    sys.stdout.flush()


if MODE == "exit":
    sys.exit(3)
for line in sys.stdin:
    request = json.loads(line)
    rid = request["request_id"]
    if request["operation"] == "health":
        reply(request_id=rid, status="healthy", capabilities=CAPS)
        continue
    if request["operation"] == "shutdown":
        break
    name = request["capability"]["name"]
    text = request["arguments"].get("text") or request["arguments"].get("note") or ""
    if text == "crash":
        os._exit(5)
    if name == "echo":
        normal = os.environ.get("AEP_PLUGIN_SENTINEL") == "present" and bool(os.environ.get("PATH"))
        bi = os.environ.get("AEP_PLUGIN_READ_BI")
        reply(
            request_id=rid,
            status="succeeded",
            data={"count": int(normal), "items": [{"label": bi or "none", "value": 1}]},
        )
    else:
        reply(request_id=rid, status="succeeded", data={"saved": True})
"""


def package(
    *,
    namespace: str = "hello-lab",
    name: str = "hello",
    version: str = "1.0.0",
    reads: bool = False,
    service: bool = False,
    only_service: bool = False,
    mode: str = "ok",
) -> bytes:
    data = manifest_data(namespace=namespace, name=name, version=version)
    if reads or service or only_service:
        data["core_api"] = NEW_API
    if reads:
        data["data"]["reads"] = ["bi"]
    if service or only_service:
        data["capabilities"][0]["expose_as_tool"] = False
    if only_service:
        data["capabilities"] = data["capabilities"][:1]
    manifest = PluginManifest.model_validate(data)
    root = f"worker/{manifest.worker_package}"
    files = {
        f"{root}/__init__.py": b"",
        f"{root}/worker.py": WORKER.replace("__MODE__", mode).encode(),
    }
    return PluginPackage.build(manifest, files).to_bytes()


def read(
    manager: PluginManager,
    *,
    plugin: str = "hello-lab.hello",
    version: str = "1.0.0",
    text: str = "",
) -> Any:
    return manager.call_read(
        PluginReadRequest(
            request_id="read-1",
            plugin_id=plugin,
            version=version,
            route_id="summary",
            arguments={"text": text} if text else {},
        ),
        timeout_seconds=10,
    )


def label(response: Any) -> str:
    assert response.status == "succeeded", response.failure
    return str(response.data["items"][0]["label"])


@pytest.fixture
def layout(tmp_path: Path) -> HostLayout:
    return HostLayout.under(tmp_path / "ws")


@pytest.fixture
def installed() -> InstalledCapabilities:
    return InstalledCapabilities()


@pytest.fixture
def manager(layout: HostLayout, installed: InstalledCapabilities) -> Iterator[PluginManager]:
    item = PluginManager(layout, installed)
    yield item
    item.close()


# -- H1: declared existing-BI context ------------------------------------------------------------


def test_a_non_declaring_worker_never_inherits_the_reserved_binding(
    manager: PluginManager, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(READ_BI_ENV, "C:/inherited/elsewhere/bi")
    monkeypatch.setenv("AEP_PLUGIN_SENTINEL", "present")
    assert manager.install(package(), ORIGIN).status == "succeeded"
    response = read(manager)
    assert label(response) == "none"
    assert response.data["count"] == 1  # the ordinary environment is still there


def test_a_declaring_worker_gets_the_hosts_own_bi_path_and_nothing_is_created(
    manager: PluginManager, layout: HostLayout, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(READ_BI_ENV, "C:/inherited/elsewhere/bi")
    monkeypatch.setenv("AEP_PLUGIN_SENTINEL", "present")
    assert manager.install(package(reads=True), ORIGIN).status == "succeeded"
    expected = os.path.abspath(layout.workspace_root / "bi")
    response = read(manager)
    assert label(response) == expected
    assert response.data["count"] == 1
    assert not (layout.workspace_root / "bi").exists()  # missing data is context, never made


def test_the_bi_path_is_rechecked_when_the_worker_restarts(
    manager: PluginManager, layout: HostLayout, tmp_path: Path
) -> None:
    (layout.workspace_root / "bi").mkdir(parents=True)
    assert manager.install(package(reads=True), ORIGIN).status == "succeeded"
    assert code(read(manager, text="crash")) == "plugin_worker_failed"
    assert label(read(manager)) == os.path.abspath(layout.workspace_root / "bi")
    if sys.platform != "win32":
        return
    import _winapi

    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "keep.txt").write_bytes(b"sentinel")
    (layout.workspace_root / "bi").rmdir()
    _winapi.CreateJunction(str(outside), str(layout.workspace_root / "bi"))
    assert code(read(manager, text="crash")) == "plugin_worker_failed"
    assert code(read(manager)) == "plugin_path_invalid"
    assert (outside / "keep.txt").read_bytes() == b"sentinel"
    assert sorted(p.name for p in outside.iterdir()) == ["keep.txt"]


@pytest.mark.skipif(sys.platform != "win32", reason="NTFS junctions")
def test_a_redirected_bi_folder_refuses_a_declaring_install(
    manager: PluginManager, layout: HostLayout, installed: InstalledCapabilities, tmp_path: Path
) -> None:
    import _winapi

    outside = tmp_path / "outside"
    outside.mkdir()
    layout.workspace_root.mkdir(parents=True)
    _winapi.CreateJunction(str(outside), str(layout.workspace_root / "bi"))
    assert code(manager.install(package(reads=True), ORIGIN)) == "plugin_path_invalid"
    assert installed.discover() == ()
    assert manager.snapshot().plugins == ()
    assert manager.install(package(namespace="other-lab", name="base"), ORIGIN).status == (
        "succeeded"
    )  # a plugin that declares nothing does not look at it


# -- H4: page-only services --------------------------------------------------------------------


def test_a_page_service_answers_page_reads_without_a_bridge_registration(
    manager: PluginManager, installed: InstalledCapabilities
) -> None:
    result = manager.install(package(service=True), ORIGIN)
    assert result.status == "succeeded", result.failure
    assert installed.get(identity()) is None
    assert installed.get(identity(local="save-note")) is not None
    assert result.plugin is not None
    assert result.plugin.capabilities == (identity(local="save-note"),)
    assert label(read(manager)) == "none"
    assert invoke(installed, identity(local="save-note"), {"note": "n"}).model_dump() == {
        "saved": True
    }


def test_switching_a_tool_to_a_page_service_is_a_guarded_update_with_rollback(
    manager: PluginManager, installed: InstalledCapabilities
) -> None:
    assert manager.install(package(), ORIGIN).status == "succeeded"
    assert installed.get(identity()) is not None
    manager.set_busy_probe(lambda: True)
    assert code(manager.install(package(version="1.1.0", service=True), ORIGIN)) == "plugin_busy"
    assert installed.get(identity()) is not None
    manager.set_busy_probe(None)
    assert manager.install(package(version="1.1.0", service=True), ORIGIN).status == "succeeded"
    assert installed.get(identity()) is None
    assert installed.get(identity(version="1.1.0")) is None
    assert installed.get(identity(local="save-note", version="1.1.0")) is not None
    assert label(read(manager, version="1.1.0")) == "none"
    failed = manager.install(package(version="1.2.0", mode="exit"), ORIGIN)
    assert code(failed) == "plugin_health_failed"
    assert installed.get(identity(version="1.1.0")) is None  # the service stays unregistered
    assert installed.get(identity(local="save-note", version="1.1.0")) is not None
    assert installed.get(identity(version="1.2.0")) is None
    assert found(manager.snapshot(), "hello-lab.hello").identity.version == "1.1.0"
    assert label(read(manager, version="1.1.0")) == "none"
    assert manager.disable("hello-lab.hello", ORIGIN).status == "succeeded"
    assert installed.discover() == ()


def test_a_page_service_only_plugin_still_owns_its_namespace_across_restart(
    layout: HostLayout,
) -> None:
    installed = InstalledCapabilities()
    manager = PluginManager(layout, installed)
    try:
        assert manager.install(package(only_service=True), ORIGIN).status == "succeeded"
        assert installed.discover() == ()
        assert code(manager.install(package(name="second"), ORIGIN)) == "plugin_namespace_owned"
    finally:
        manager.close()
    restored = InstalledCapabilities()
    again = PluginManager(layout, restored)
    try:
        assert found(again.restore(), "hello-lab.hello").state == "active"
        assert restored.discover() == ()
        assert label(read(again)) == "none"
        assert code(again.install(package(name="second"), ORIGIN)) == "plugin_namespace_owned"
    finally:
        again.close()


def test_a_page_service_cannot_be_reached_as_a_tool(
    manager: PluginManager, installed: InstalledCapabilities
) -> None:
    manager.install(package(service=True), ORIGIN)
    with pytest.raises(AssertionError):
        invoke(installed, identity(), {"text": "x"})  # no binding exists to call
    assert json.dumps([s.name for s in installed.discover()]) == '["hello-lab.save_note"]'
    with pytest.raises(CapabilityRefused):
        raise CapabilityRefused("plugin_not_active")  # the refusal type stays importable


# -- the process binding itself -----------------------------------------------------------------


def _staged(tmp_path: Path, payload: bytes) -> tuple[PluginManifest, Path, Path]:
    from common.plugins import parse_plugin_package
    from plugins.package import stage_package

    staged_package = parse_plugin_package(payload)
    target = stage_package(staged_package, tmp_path / "packages")
    data_root = tmp_path / "data"
    data_root.mkdir()
    return staged_package.manifest, target, data_root


def _echo_label(session: Any, manifest: PluginManifest) -> str:
    from plugins.process import invoke as worker_invoke

    data: Any = worker_invoke(session, manifest.capability("hello-lab.echo").spec.identity, {}, 10)
    assert isinstance(data, dict)
    return str(data["items"][0]["label"])


def test_start_worker_binds_bi_only_for_a_declaring_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from plugins.process import WorkerFailure, start_worker

    monkeypatch.setenv(READ_BI_ENV, "C:/inherited/elsewhere/bi")
    manifest, target, data_root = _staged(tmp_path, package())
    session = start_worker(
        manifest, target, data_root, interpreter=sys.executable, bi_root=tmp_path / "given"
    )
    try:
        assert _echo_label(session, manifest) == "none"  # given, but not declared: ignored
    finally:
        session.close()
    declared, staged, data = _staged(tmp_path / "second", package(reads=True))
    with pytest.raises(WorkerFailure) as raised:
        start_worker(declared, staged, data, interpreter=sys.executable)  # no explicit path
    assert raised.value.code == "plugin_environment_failed"
