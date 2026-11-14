"""Feature plugin manager (Slice 1): several active plugins with real stdlib
JSON-lines workers, owned capability bindings, honest failures and restart
recovery. Synthetic data only."""

from __future__ import annotations

import ast
import asyncio
import json
import sys
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from agent.turn_effects import TurnEffects, use_effects
from capabilities.runtime import CapabilityRefused, InstalledCapabilities
from common.assets import AssetIdentity
from common.base import Contract
from common.execution import RequestContext, TraceIdentifiers
from common.plugins import (
    PluginContractError,
    PluginManagerProtocol,
    PluginManifest,
    PluginOrigin,
    PluginPackage,
    PluginReadRequest,
    PluginSnapshot,
    PluginStatus,
    TextBlock,
)
from host_runtime.contracts import HostLayout
from plugins import PluginManager

WORKER = r"""
import json, os, sys, time
from pathlib import Path

DATA = Path(os.environ["AEP_PLUGIN_DATA_ROOT"])
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
        if MODE == "unhealthy":
            reply(request_id=rid, status="failed", code="synthetic_unhealthy")
        else:
            reply(request_id=rid, status="healthy", capabilities=CAPS)
        continue
    if request["operation"] == "shutdown":
        break
    name = request["capability"]["name"]
    text = request["arguments"].get("text") or request["arguments"].get("note") or ""
    with open(DATA / "calls.log", "a", encoding="utf-8") as log:
        log.write(f"{name}:{text}\n")
    if text == "crash":
        os._exit(5)
    if text == "sleep":
        time.sleep(30)
    if text == "huge":
        sys.stdout.write("x" * (600 * 1024) + "\n")
        sys.stdout.flush()
        continue
    if text == "env":
        normal = os.environ.get("AEP_PLUGIN_SENTINEL") == "present" and bool(os.environ.get("PATH"))
        reply(request_id=rid, status="succeeded", data={"count": int(normal), "items": []})
        continue
    if text == "refuse":
        reply(request_id=rid, status="refused", code="synthetic_refusal")
        continue
    if text == "badshape":
        reply(request_id=rid, status="succeeded", data={"count": "one"})
        continue
    if name == "echo":
        data = {"count": len(text), "items": [{"label": text or "none", "value": 1}]}
    else:
        data = {"saved": True}
    reply(request_id=rid, status="succeeded", data=data)
"""

ORIGIN = PluginOrigin(actor="person-1", channel="web", source="synthetic")


def capability(namespace: str, version: str, local: str, side_effect: str) -> dict[str, Any]:
    name = f"{namespace}.{local}"
    inputs = (
        [{"name": "text", "type": "string", "required": False, "max_length": 40}]
        if local == "echo"
        else [{"name": "note", "type": "string"}]
    )
    outputs = (
        [
            {"name": "count", "type": "integer"},
            {"name": "items", "type": "rows", "columns": ["label", "value"]},
        ]
        if local == "echo"
        else [{"name": "saved", "type": "boolean"}]
    )
    return {
        "spec": {
            "identity": {
                "namespace": namespace,
                "name": local.replace("_", "-"),
                "version": version,
            },
            "name": name,
            "description": f"Synthetic {local}",
            "input_contract": f"{name}.input",
            "output_contract": f"{name}.output",
            "side_effect": side_effect,
            "policy": {"risk": "low", "approval_required": False},
        },
        "inputs": inputs,
        "outputs": outputs,
    }


def manifest_data(
    namespace: str = "hello-lab",
    name: str = "hello",
    version: str = "1.0.0",
    *,
    worker: bool = True,
    requires: tuple[dict[str, str], ...] = (),
    assets: tuple[dict[str, Any], ...] = (),
    schema_version: int = 1,
    request_timeout: int = 30,
) -> dict[str, Any]:
    package = "aep_plugin_" + namespace.replace("-", "_")
    data: dict[str, Any] = {
        "format": "aep-plugin/1",
        "identity": {"namespace": namespace, "name": name, "version": version},
        "title": f"Synthetic {namespace}",
        "description": "Synthetic fixture plugin.",
        "core_api": {"minimum": "1.0.0", "below": "2.0.0"},
        "requires": list(requires),
        "assets": list(assets),
        "data": {"schema_version": schema_version},
    }
    if worker:
        data["runtime"] = {
            "module": f"{package}.worker",
            "health": {"startup_timeout_seconds": 20, "request_timeout_seconds": request_timeout},
        }
        data["capabilities"] = [
            capability(namespace, version, "echo", "read"),
            capability(namespace, version, "save_note", "write"),
        ]
        data["routes"] = [{"route_id": "summary", "capability": f"{namespace}.echo"}]
        data["pages"] = [
            {
                "page_id": "overview",
                "title": "Overview",
                "blocks": [
                    {"kind": "text", "text": "<script>alert(1)</script>"},
                    {"kind": "metric", "label": "Count", "route_id": "summary", "field": "count"},
                ],
            }
        ]
    return data


def build(
    *,
    mode: str = "ok",
    files: dict[str, bytes] | None = None,
    **options: Any,
) -> PluginPackage:
    manifest = PluginManifest.model_validate(manifest_data(**options))
    content = dict(files or {})
    if manifest.runtime is not None:
        root = f"worker/{manifest.worker_package}"
        content.setdefault(f"{root}/__init__.py", b"")
        content.setdefault(f"{root}/worker.py", WORKER.replace("__MODE__", mode).encode())
    return PluginPackage.build(manifest, content)


def payload(**options: Any) -> bytes:
    return build(**options).to_bytes()


def identity(
    namespace: str = "hello-lab", local: str = "echo", version: str = "1.0.0"
) -> AssetIdentity:
    return AssetIdentity(namespace=namespace, name=local, version=version)


def context() -> RequestContext:
    return RequestContext(
        trace=TraceIdentifiers(trace_id="trace-1", request_id="request-1", span_id="span-1"),
        actor="person-1",
        namespace="team",
        message="synthetic",
        channel="web",
    )


def invoke(
    installed: InstalledCapabilities, target: AssetIdentity, arguments: dict[str, Any]
) -> Contract:
    binding = installed.get(target)
    assert binding is not None
    inputs = binding.input_model.model_validate_json(json.dumps(arguments), strict=True)

    async def run() -> Contract:
        return await binding.handler(context(), inputs)

    return asyncio.run(run())


def calls(layout: HostLayout, namespace: str = "hello-lab", name: str = "hello") -> list[str]:
    log = layout.workspace_root / "plugin-data" / namespace / name / "calls.log"
    return log.read_text(encoding="utf-8").splitlines() if log.is_file() else []


def read(manager: PluginManager, text: str | None = None, **changes: Any) -> Any:
    request = {
        "request_id": "read-1",
        "plugin_id": "hello-lab.hello",
        "version": "1.0.0",
        "route_id": "summary",
        "arguments": {} if text is None else {"text": text},
    } | changes
    return manager.call_read(PluginReadRequest.model_validate(request), timeout_seconds=10)


def found(snapshot: PluginSnapshot, plugin_id: str) -> PluginStatus:
    status = snapshot.get(plugin_id)
    assert status is not None, plugin_id
    return status


def code(result: Any) -> str:
    """The failure code of a typed plugin result; fails when it succeeded."""
    assert result.failure is not None, result
    return str(result.failure.code)


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


# -- startup -----------------------------------------------------------------------------


def test_empty_manager_restore_creates_no_files(tmp_path: Path) -> None:
    layout = HostLayout.under(tmp_path / "ws")
    manager = PluginManager(layout, InstalledCapabilities())
    protocol: PluginManagerProtocol = manager
    assert manager.restore().plugins == ()
    assert protocol.snapshot().plugins == ()
    manager.close()
    assert not (tmp_path / "ws").exists()


# -- install, read, tools ----------------------------------------------------------------


def test_install_registers_typed_tools_routes_and_pages(
    manager: PluginManager, installed: InstalledCapabilities, layout: HostLayout
) -> None:
    result = manager.install(payload(), ORIGIN)
    assert result.status == "succeeded", result.failure
    status = result.plugin
    assert status is not None and status.state == "active"
    assert status.routes == ("summary",)
    block = status.pages[0].blocks[0]
    assert isinstance(block, TextBlock) and block.text == "<script>alert(1)</script>"
    assert status.installed_by == ORIGIN
    binding = installed.get(identity())
    assert binding is not None and binding.spec.name == "hello-lab.echo"
    assert set(binding.input_model.model_json_schema()["properties"]) == {"text"}
    output = invoke(installed, identity(), {"text": "abc"})
    assert output.model_dump(mode="json") == {"count": 3, "items": [{"label": "abc", "value": 1}]}
    response = read(manager, "hi")
    assert response.status == "succeeded"
    assert response.data == {"count": 2, "items": [{"label": "hi", "value": 1}]}
    assert calls(layout) == ["echo:abc", "echo:hi"]
    assert manager.snapshot().get("hello-lab.hello") == status


def test_two_plugins_are_active_together(
    manager: PluginManager, installed: InstalledCapabilities
) -> None:
    assert manager.install(payload(), ORIGIN).status == "succeeded"
    assert (
        manager.install(payload(namespace="other-lab", name="base"), ORIGIN).status == "succeeded"
    )
    assert {p.plugin_id for p in manager.snapshot().plugins} == {
        "hello-lab.hello",
        "other-lab.base",
    }
    assert invoke(installed, identity("other-lab"), {"text": "x"}).model_dump()["count"] == 1
    assert invoke(installed, identity(), {"text": "yy"}).model_dump()["count"] == 2


def test_read_failures_are_typed_and_not_success(
    manager: PluginManager, layout: HostLayout
) -> None:
    assert code(read(manager)) == "plugin_not_active"
    manager.install(payload(), ORIGIN)
    assert code(read(manager, version="0.9.0")) == "plugin_version_stale"
    assert code(read(manager, route_id="missing")) == "plugin_route_unknown"
    refused = read(manager, "refuse")
    assert (refused.status, refused.data) == ("failed", None)
    assert "synthetic_refusal" in refused.failure.message
    assert code(read(manager, "badshape")) == "plugin_invocation_failed"
    assert code(read(manager, "x" * 41)) == "plugin_invocation_failed"
    assert code(read(manager, "huge")) == "plugin_response_too_large"
    assert read(manager, "after").status == "succeeded"  # a new worker answers the next call


def test_worker_keeps_the_ordinary_environment(
    manager: PluginManager, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AEP_PLUGIN_SENTINEL", "present")
    manager.install(payload(), ORIGIN)
    assert read(manager, "env").data == {"count": 1, "items": []}


def test_worker_crash_is_a_failure_and_is_not_retried(
    manager: PluginManager, installed: InstalledCapabilities, layout: HostLayout
) -> None:
    manager.install(payload(), ORIGIN)
    with pytest.raises(CapabilityRefused) as raised:
        invoke(installed, identity(local="save-note"), {"note": "crash"})
    assert raised.value.code == "plugin_worker_failed"
    assert calls(layout) == ["save-note:crash"]
    assert invoke(installed, identity(local="save-note"), {"note": "ok"}).model_dump() == {
        "saved": True
    }


def test_timeout_kills_the_worker_within_its_bound(
    manager: PluginManager, layout: HostLayout
) -> None:
    manager.install(payload(request_timeout=1), ORIGIN)
    started = time.monotonic()
    response = read(manager, "sleep")
    assert code(response) == "plugin_timeout"
    assert time.monotonic() - started < 10
    assert calls(layout) == ["echo:sleep"]


# -- refusals before any contribution ------------------------------------------------------


def _nothing_from(layout: HostLayout, installed: InstalledCapabilities, namespace: str) -> None:
    assert not any(s.identity.namespace == namespace for s in installed.discover())
    packages = layout.workspace_root / "plugins" / "packages" / namespace
    assert not packages.exists() or not any(packages.rglob("package.json"))


def test_collisions_and_namespace_ownership_refuse_without_half_install(
    layout: HostLayout, installed: InstalledCapabilities
) -> None:
    manager = PluginManager(layout, installed, reserved_names=lambda: {"other-lab.echo"})
    try:
        assert manager.install(payload(), ORIGIN).status == "succeeded"
        clash = manager.install(payload(namespace="other-lab", name="base"), ORIGIN)
        assert code(clash) == "plugin_contribution_collision"
        _nothing_from(layout, installed, "other-lab")
        owned = manager.install(payload(name="second"), ORIGIN)
        assert code(owned) == "plugin_namespace_owned"
        assert installed.get(identity()) is not None
    finally:
        manager.close()


def test_a_live_core_binding_owns_its_namespace(
    manager: PluginManager, installed: InstalledCapabilities, layout: HostLayout
) -> None:
    other = PluginManager(layout.under(layout.workspace_root.parent / "ws2"), installed)
    try:
        assert other.install(payload(), ORIGIN).status == "succeeded"
        refused = manager.install(payload(), ORIGIN)
        assert code(refused) == "plugin_namespace_owned"
    finally:
        other.close()


def test_versions_are_exact_and_never_silently_replaced(manager: PluginManager) -> None:
    first = manager.install(payload(), ORIGIN)
    assert first.status == "succeeded"
    again = manager.install(payload(), ORIGIN)
    assert again.status == "succeeded" and again.plugin == first.plugin
    changed = manager.install(payload(mode="other"), ORIGIN)
    assert code(changed) == "plugin_version_conflict"
    assert code(manager.install(payload(version="0.9.0"), ORIGIN)) == "plugin_downgrade_refused"


def test_incompatible_core_api_dependency_and_data_are_refused(
    manager: PluginManager, layout: HostLayout
) -> None:
    data = manifest_data()
    data["core_api"] = {"minimum": "1.5.0", "below": "2.0.0"}
    package = PluginPackage.build(
        PluginManifest.model_validate(data),
        {
            "worker/aep_plugin_hello_lab/__init__.py": b"",
            "worker/aep_plugin_hello_lab/worker.py": WORKER.replace("__MODE__", "ok").encode(),
        },
    )
    assert code(manager.install(package.to_bytes(), ORIGIN)) == "plugin_core_api_incompatible"
    needs = payload(requires=({"namespace": "base-lab", "name": "base", "version": "1.0.0"},))
    assert code(manager.install(needs, ORIGIN)) == "plugin_dependency_missing"
    marker = layout.workspace_root / "plugin-data" / "hello-lab" / "hello" / ".aep-data.json"
    marker.parent.mkdir(parents=True)
    marker.write_text(
        json.dumps(
            {
                "plugin_id": "hello-lab.hello",
                "schema_version": 7,
                "written_by": {"namespace": "hello-lab", "name": "hello", "version": "3.0.0"},
            }
        ),
        encoding="utf-8",
    )
    assert code(manager.install(payload(), ORIGIN)) == "plugin_data_newer"
    assert code(manager.install(b"PK\x03\x04", ORIGIN)) == "plugin_package_invalid"


def test_failed_health_leaves_no_contribution_and_keeps_the_previous_version(
    manager: PluginManager, installed: InstalledCapabilities, layout: HostLayout
) -> None:
    unhealthy = manager.install(payload(mode="unhealthy"), ORIGIN)
    assert code(unhealthy) == "plugin_health_failed"
    _nothing_from(layout, installed, "hello-lab")
    assert manager.snapshot().plugins == ()
    assert manager.install(payload(), ORIGIN).status == "succeeded"
    exits = manager.install(payload(version="1.1.0", mode="exit"), ORIGIN)
    assert code(exits) == "plugin_health_failed"
    assert found(manager.snapshot(), "hello-lab.hello").identity.version == "1.0.0"
    assert invoke(installed, identity(), {"text": "still"}).model_dump()["count"] == 5
    assert not (
        layout.workspace_root / "plugins" / "packages" / "hello-lab" / "hello" / "1.1.0"
    ).exists()


# -- busy, versions and per-turn effects -----------------------------------------------------


def test_busy_refuses_version_switch_and_removal_but_not_new_install(
    manager: PluginManager, installed: InstalledCapabilities
) -> None:
    manager.install(payload(), ORIGIN)
    manager.set_busy_probe(lambda: True)
    assert code(manager.install(payload(version="1.1.0"), ORIGIN)) == "plugin_busy"
    assert code(manager.disable("hello-lab.hello", ORIGIN)) == "plugin_busy"
    assert code(manager.uninstall("hello-lab.hello", ORIGIN)) == "plugin_busy"
    assert installed.get(identity()) is not None
    assert (
        manager.install(payload(namespace="other-lab", name="base"), ORIGIN).status == "succeeded"
    )

    def broken() -> bool:
        raise RuntimeError("probe failed")

    manager.set_busy_probe(broken)
    assert code(manager.disable("hello-lab.hello", ORIGIN)) == "plugin_busy"
    manager.set_busy_probe(None)
    updated = manager.install(payload(version="1.1.0"), ORIGIN)
    assert updated.status == "succeeded", updated.failure
    assert installed.get(identity()) is None
    assert installed.get(identity(version="1.1.0")) is not None


def test_a_write_is_not_repeated_under_a_new_version_in_the_same_turn(
    manager: PluginManager, installed: InstalledCapabilities, layout: HostLayout
) -> None:
    manager.install(payload(), ORIGIN)
    old = installed.get(identity(local="save-note"))
    assert old is not None
    effects = TurnEffects()
    with use_effects(effects):
        assert invoke(installed, identity(local="save-note"), {"note": "n1"}).model_dump() == {
            "saved": True
        }
        assert manager.install(payload(version="1.1.0"), ORIGIN).status == "succeeded"
        with pytest.raises(CapabilityRefused) as raised:
            invoke(installed, identity(local="save-note", version="1.1.0"), {"note": "n1"})
        assert raised.value.code == "plugin_version_stale"
        inputs = old.input_model.model_validate({"note": "n2"})
        with pytest.raises(CapabilityRefused) as stale:
            asyncio.run(old.handler(context(), inputs))
        assert stale.value.code == "plugin_version_stale"
    assert calls(layout) == ["save-note:n1"]
    assert effects.recorded == 0  # the manager adds no counted side effect of its own


# -- disable, enable, uninstall, dependencies --------------------------------------------------


def test_disable_enable_uninstall_keep_data_and_respect_dependents(
    manager: PluginManager, installed: InstalledCapabilities, layout: HostLayout
) -> None:
    manager.install(payload(namespace="base-lab", name="base"), ORIGIN)
    needs = {"namespace": "base-lab", "name": "base", "version": "1.0.0"}
    assert manager.install(payload(requires=(needs,)), ORIGIN).status == "succeeded"
    assert code(manager.disable("base-lab.base", ORIGIN)) == "plugin_dependent_active"
    assert code(manager.uninstall("base-lab.base", ORIGIN)) == "plugin_dependent_active"
    invoke(installed, identity(), {"text": "keep"})
    disabled = manager.disable("hello-lab.hello", ORIGIN)
    assert disabled.plugin is not None and disabled.plugin.state == "disabled"
    assert installed.get(identity()) is None
    assert code(read(manager)) == "plugin_not_active"
    enabled = manager.enable("hello-lab.hello", ORIGIN)
    assert enabled.status == "succeeded" and installed.get(identity()) is not None
    removed = manager.uninstall("hello-lab.hello", ORIGIN)
    assert removed.status == "succeeded" and removed.plugin is None
    assert installed.get(identity()) is None
    assert manager.snapshot().get("hello-lab.hello") is None
    assert calls(layout) == ["echo:keep"]  # private data kept
    assert not (layout.workspace_root / "plugins" / "packages" / "hello-lab").exists() or not any(
        (layout.workspace_root / "plugins" / "packages" / "hello-lab").iterdir()
    )
    assert code(manager.enable("hello-lab.hello", ORIGIN)) == "plugin_not_installed"


# -- restart and recovery -----------------------------------------------------------------------


def test_restart_restores_enabled_plugins_and_refuses_changed_bytes(
    layout: HostLayout, tmp_path: Path
) -> None:
    first = PluginManager(layout, InstalledCapabilities())
    first.install(payload(), ORIGIN)
    first.install(payload(namespace="other-lab", name="base"), ORIGIN)
    first.disable("other-lab.base", ORIGIN)
    first.close()
    installed = InstalledCapabilities()
    second = PluginManager(layout, installed)
    try:
        snapshot = second.restore()
        assert {(p.plugin_id, p.state) for p in snapshot.plugins} == {
            ("hello-lab.hello", "active"),
            ("other-lab.base", "disabled"),
        }
        assert invoke(installed, identity(), {"text": "back"}).model_dump()["count"] == 4
    finally:
        second.close()
    worker = (
        layout.workspace_root
        / "plugins/packages/hello-lab/hello/1.0.0/worker/aep_plugin_hello_lab/worker.py"
    )
    worker.write_text("print('tampered')\n", encoding="utf-8")
    third_installed = InstalledCapabilities()
    third = PluginManager(layout, third_installed)
    try:
        status = third.restore().get("hello-lab.hello")
        assert status is not None and status.state == "failed"
        assert code(status) == "plugin_staged_changed"
        assert third_installed.get(identity()) is None
    finally:
        third.close()


def test_an_unreadable_ledger_is_reported_and_never_overwritten(layout: HostLayout) -> None:
    first_installed = InstalledCapabilities()
    first = PluginManager(layout, first_installed)
    try:
        first.install(payload(), ORIGIN)
        ledger = layout.workspace_root / "plugins" / "ledger.json"
        corrupted = b'{"format": "aep-plugin-ledger/1", "plugins": [trunc'
        ledger.write_bytes(corrupted)
        # Already active registrations stay as they are: a read failure is not an uninstall.
        with pytest.raises(PluginContractError) as raised:
            first.snapshot()
        assert raised.value.code == "plugin_environment_failed"
        assert invoke(first_installed, identity(), {"text": "on"}).model_dump()["count"] == 2
        assert code(first.install(payload(namespace="other-lab", name="base"), ORIGIN)) == (
            "plugin_environment_failed"
        )
        assert code(first.disable("hello-lab.hello", ORIGIN)) == "plugin_environment_failed"
        assert first_installed.get(identity()) is not None
    finally:
        first.close()
    orphan = layout.workspace_root / "plugins" / "packages" / "zz-orphan" / "x" / "1.0.0"
    orphan.mkdir(parents=True)
    installed = InstalledCapabilities()
    again = PluginManager(layout, installed)
    try:
        again.restore()  # keeps the Host starting; touches nothing
        with pytest.raises(PluginContractError):
            again.snapshot()
        assert ledger.read_bytes() == corrupted
        assert orphan.is_dir()
        assert (layout.workspace_root / "plugins" / "packages" / "hello-lab").is_dir()
        assert installed.discover() == ()
    finally:
        again.close()


def test_restore_clears_interrupted_install_and_partial_staging(layout: HostLayout) -> None:
    manager = PluginManager(layout, InstalledCapabilities())
    manager.install(payload(), ORIGIN)
    manager.close()
    root = layout.workspace_root / "plugins"
    ledger = json.loads((root / "ledger.json").read_text(encoding="utf-8"))
    record = ledger["plugins"][0]
    record["pending"] = {
        "version": "1.1.0",
        "content_sha256": "b" * 64,
        "new_record": False,
        "assets": [],
    }
    (root / "ledger.json").write_text(json.dumps(ledger), encoding="utf-8")
    (root / "packages" / "hello-lab" / "hello" / "1.1.0").mkdir()
    (root / "packages" / "hello-lab" / "hello" / ".part-deadbeef").mkdir()
    (root / "packages" / "zz-orphan" / "x" / "1.0.0").mkdir(parents=True)
    installed = InstalledCapabilities()
    again = PluginManager(layout, installed)
    try:
        snapshot = again.restore()
        assert found(snapshot, "hello-lab.hello").state == "active"
        assert installed.get(identity()) is not None
        assert sorted(p.name for p in (root / "packages" / "hello-lab" / "hello").iterdir()) == [
            "1.0.0"
        ]
        assert not (root / "packages" / "zz-orphan" / "x" / "1.0.0").exists()
        stored = json.loads((root / "ledger.json").read_text(encoding="utf-8"))
        assert stored["plugins"][0]["pending"] is None
    finally:
        again.close()


# -- boundaries ------------------------------------------------------------------------------------


def test_plugin_modules_have_no_approval_signer_or_feature_imports() -> None:
    root = Path(__file__).resolve().parents[1] / "src" / "plugins"
    forbidden_names = {
        "ExtensionActivationApproval",
        "ExtensionManager",
        "ExtensionTrustPolicy",
        "TrustedPublisherKey",
        "ExtensionSignature",
        "HostRuntime",
        "approval",
    }
    for path in root.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                assert not module.startswith(
                    (
                        "host_runtime.web",
                        "host_runtime.bi",
                        "capabilities.bi",
                        "knowledge",
                        "agent.gateway",
                    )
                ), (path.name, module)
                assert {alias.name for alias in node.names}.isdisjoint(forbidden_names), path.name
            if isinstance(node, ast.Name):
                assert node.id not in forbidden_names, (path.name, node.id)


# -- redirected folders (NTFS junctions) ------------------------------------------------------

windows_only = pytest.mark.skipif(sys.platform != "win32", reason="NTFS junctions")


def _outside(tmp_path: Path) -> tuple[Path, Path]:
    outside = tmp_path / "outside"
    keep = outside / "hello-lab" / "hello" / "1.0.0" / "keep.txt"
    keep.parent.mkdir(parents=True)
    keep.write_bytes(b"sentinel")
    (outside / "zz-other" / "x" / "1.0.0").mkdir(parents=True)
    (outside / "zz-other" / "x" / "1.0.0" / "keep.txt").write_bytes(b"sentinel")
    return outside, keep


def _junction(target: Path, link: Path) -> None:
    import _winapi

    link.parent.mkdir(parents=True, exist_ok=True)
    _winapi.CreateJunction(str(target), str(link))


def _intact(outside: Path) -> None:
    assert (outside / "hello-lab" / "hello" / "1.0.0" / "keep.txt").read_bytes() == b"sentinel"
    assert (outside / "zz-other" / "x" / "1.0.0" / "keep.txt").read_bytes() == b"sentinel"


@windows_only
@pytest.mark.parametrize("redirected", ["plugins/packages", "plugins"])
def test_a_redirected_plugin_root_is_refused_and_nothing_outside_is_deleted(
    tmp_path: Path, redirected: str
) -> None:
    outside, _ = _outside(tmp_path)
    layout = HostLayout.under(tmp_path / "ws")
    _junction(outside, layout.workspace_root / redirected)
    installed = InstalledCapabilities()
    manager = PluginManager(layout, installed)
    try:
        assert code(manager.install(payload(), ORIGIN)) == "plugin_path_invalid"
        _intact(outside)
        assert manager.restore().plugins == ()
        _intact(outside)
        with pytest.raises(PluginContractError) as raised:
            manager.snapshot()
        assert raised.value.code == "plugin_path_invalid"
        assert code(manager.uninstall("hello-lab.hello", ORIGIN)) == "plugin_path_invalid"
        assert installed.discover() == ()
        _intact(outside)
    finally:
        manager.close()
    _intact(outside)


@windows_only
def test_redirected_folders_inside_the_plugin_tree_are_never_followed(tmp_path: Path) -> None:
    outside, _ = _outside(tmp_path)
    layout = HostLayout.under(tmp_path / "ws")
    manager = PluginManager(layout, InstalledCapabilities())
    try:
        assert manager.install(payload(), ORIGIN).status == "succeeded"
    finally:
        manager.close()
    packages = layout.workspace_root / "plugins" / "packages"
    _junction(outside / "zz-other", packages / "zz-other")  # an orphan namespace
    name_dir = packages / "hello-lab" / "hello"
    staged = name_dir / "1.0.0"
    staged.rename(tmp_path / "moved")
    _junction(outside / "hello-lab" / "hello" / "1.0.0", staged)  # the staged version
    installed = InstalledCapabilities()
    again = PluginManager(layout, installed)
    try:
        status = again.restore().get("hello-lab.hello")
        assert status is not None and code(status) == "plugin_path_invalid"
        assert installed.discover() == ()
        _intact(outside)
        assert code(again.uninstall("hello-lab.hello", ORIGIN)) == "plugin_path_invalid"
        assert found(again.snapshot(), "hello-lab.hello").state == "failed"
        _intact(outside)
    finally:
        again.close()
    _intact(outside)


@windows_only
@pytest.mark.parametrize("redirected", ["plugin-data/hello-lab", "assets/skills"])
def test_redirected_data_or_asset_folders_refuse_install(tmp_path: Path, redirected: str) -> None:
    from test_plugin_assets import package as asset_package

    outside, _ = _outside(tmp_path)
    layout = HostLayout.under(tmp_path / "ws")
    _junction(outside, layout.workspace_root / redirected)
    installed = InstalledCapabilities()
    manager = PluginManager(layout, installed)
    try:
        content = payload() if redirected.startswith("plugin-data") else asset_package()
        assert code(manager.install(content, ORIGIN)) == "plugin_path_invalid"
        assert installed.discover() == ()
        assert manager.snapshot().plugins == ()
        _intact(outside)
        assert sorted(p.name for p in outside.iterdir()) == ["hello-lab", "zz-other"]
    finally:
        manager.close()
    _intact(outside)


def test_a_required_plugin_is_not_upgraded_under_an_active_dependent(layout: HostLayout) -> None:
    manager = PluginManager(layout, InstalledCapabilities())
    try:
        manager.install(payload(namespace="base-lab", name="base"), ORIGIN)
        needs = {"namespace": "base-lab", "name": "base", "version": "1.0.0"}
        assert manager.install(payload(requires=(needs,)), ORIGIN).status == "succeeded"
        upgrade = payload(namespace="base-lab", name="base", version="1.1.0")
        assert code(manager.install(upgrade, ORIGIN)) == "plugin_dependent_active"
        states = {(p.plugin_id, p.identity.version, p.state) for p in manager.snapshot().plugins}
        assert states == {
            ("base-lab.base", "1.0.0", "active"),
            ("hello-lab.hello", "1.0.0", "active"),
        }
    finally:
        manager.close()
    fresh = PluginManager(layout, InstalledCapabilities())
    try:
        assert {p.state for p in fresh.restore().plugins} == {"active"}
    finally:
        fresh.close()
