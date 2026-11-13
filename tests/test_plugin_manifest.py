"""Feature plugin contract: closed manifest, inert package envelope and the
typed manager/Web messages (Slice 1, docs/phases/FEATURE_PLUGIN_SLICE1_PLAN_20261113.md)."""

from __future__ import annotations

import ast
import base64
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

import common.plugins as plugins
from common.assets import AssetIdentity
from common.plugins import (
    CORE_PLUGIN_API_VERSION,
    PluginActionResult,
    PluginContractError,
    PluginDataMarker,
    PluginManifest,
    PluginOrigin,
    PluginPackage,
    PluginReadRequest,
    PluginReadResponse,
    PluginSnapshot,
    PluginStatus,
    capability_models,
    core_api_supported,
    data_marker_problem,
    parse_plugin_package,
    plugin_path_problem,
)

VERSION = "1.0.0"


def spec(local: str = "echo", *, side_effect: str = "read", **policy: Any) -> dict[str, Any]:
    name = f"hello-lab.{local}"
    return {
        "identity": {"namespace": "hello-lab", "name": local.replace("_", "-"), "version": VERSION},
        "name": name,
        "description": f"{local} capability",
        "input_contract": f"{name}.input",
        "output_contract": f"{name}.output",
        "side_effect": side_effect,
        "policy": {"risk": "low", "approval_required": True, **policy},
    }


def manifest_data(**changes: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "format": "aep-plugin/1",
        "identity": {"namespace": "hello-lab", "name": "hello", "version": VERSION},
        "title": "Hello lab",
        "description": "Synthetic fixture plugin.",
        "core_api": {"minimum": "1.0.0", "below": "2.0.0"},
        "runtime": {"module": "aep_plugin_hello_lab.worker"},
        "capabilities": [
            {
                "spec": spec("echo"),
                "inputs": [{"name": "text", "type": "string", "required": False, "max_length": 20}],
                "outputs": [
                    {"name": "count", "type": "integer"},
                    {"name": "items", "type": "rows", "columns": ["label", "value"]},
                ],
            },
            {
                "spec": spec("save_note", side_effect="write"),
                "inputs": [{"name": "note", "type": "string"}],
                "outputs": [{"name": "saved", "type": "boolean"}],
            },
        ],
        "routes": [{"route_id": "summary", "capability": "hello-lab.echo"}],
        "pages": [
            {
                "page_id": "overview",
                "title": "Overview",
                "blocks": [
                    {"kind": "text", "text": "Synthetic data only."},
                    {"kind": "metric", "label": "Items", "route_id": "summary", "field": "count"},
                    {
                        "kind": "table",
                        "route_id": "summary",
                        "field": "items",
                        "columns": [{"key": "label", "label": "Label"}],
                    },
                ],
            }
        ],
        "assets": [
            {
                "kind": "skill",
                "identity": {"namespace": "hello-lab", "name": "hello-skill", "version": VERSION},
                "path": "assets/skills/hello-lab__hello-skill__1.0.0.json",
                "sha256": hashlib.sha256(b"{}").hexdigest(),
            }
        ],
        "data": {"schema_version": 1},
    }
    data.update(changes)
    return data


def manifest(**changes: Any) -> PluginManifest:
    return PluginManifest.model_validate(manifest_data(**changes))


def files(**extra: bytes) -> dict[str, bytes]:
    return {
        "worker/aep_plugin_hello_lab/__init__.py": b"",
        "worker/aep_plugin_hello_lab/worker.py": b"print('synthetic')\n",
        "assets/skills/hello-lab__hello-skill__1.0.0.json": b"{}",
        **extra,
    }


# -- manifest ------------------------------------------------------------------------


def test_valid_manifest_derives_stable_owned_names() -> None:
    item = manifest()
    assert item.plugin_id == "hello-lab.hello"
    assert item.worker_package == "aep_plugin_hello_lab"
    assert item.route("summary").capability == "hello-lab.echo"
    assert item.capability("hello-lab.echo").spec.side_effect == "read"
    assert PluginManifest.model_validate_json(item.model_dump_json()) == item


@pytest.mark.parametrize("key", ["html", "script", "url", "href", "src", "iframe", "action"])
def test_unknown_executable_or_link_fields_are_refused_everywhere(key: str) -> None:
    with pytest.raises(ValidationError):
        manifest(**{key: "x"})
    data = manifest_data()
    data["pages"][0]["blocks"][0][key] = "javascript:alert(1)"
    with pytest.raises(ValidationError):
        PluginManifest.model_validate(data)
    data = manifest_data()
    data["capabilities"][0]["inputs"][0][key] = "x"
    with pytest.raises(ValidationError):
        PluginManifest.model_validate(data)


def test_markup_in_text_is_kept_as_inert_text_and_ids_refuse_markup() -> None:
    hostile = "<script>alert(TOKEN)</script><img src=x onerror=alert(1)>"
    data = manifest_data(title="<b>t</b>")
    data["pages"][0]["blocks"][0]["text"] = hostile
    item = PluginManifest.model_validate(data)
    assert item.pages[0].blocks[0].text == hostile  # type: ignore[union-attr]
    assert item.title == "<b>t</b>"
    data["pages"][0]["page_id"] = "<script>"
    with pytest.raises(ValidationError):
        PluginManifest.model_validate(data)


@pytest.mark.parametrize("namespace", ["aep", "host", "core", "plugins", "mcp", "9lab"])
def test_reserved_or_unaddressable_namespaces_are_refused(namespace: str) -> None:
    with pytest.raises(ValidationError):
        manifest(identity={"namespace": namespace, "name": "hello", "version": VERSION})


def test_capabilities_are_owned_by_the_plugin_namespace_and_version() -> None:
    def broken(change: dict[str, Any]) -> None:
        data = manifest_data()
        data["capabilities"][0]["spec"].update(change)
        with pytest.raises(ValidationError):
            PluginManifest.model_validate(data)

    broken({"identity": {"namespace": "other", "name": "echo", "version": VERSION}})
    broken({"identity": {"namespace": "hello-lab", "name": "echo", "version": "2.0.0"}})
    broken({"name": "other.echo"})
    broken({"name": "hello-lab.echo.deep"})
    broken({"input_contract": "anything"})
    data = manifest_data()
    data["capabilities"][1]["spec"]["name"] = "hello-lab.echo"
    with pytest.raises(ValidationError):
        PluginManifest.model_validate(data)
    data = manifest_data()
    data["capabilities"][1]["spec"]["identity"] = data["capabilities"][0]["spec"]["identity"]
    with pytest.raises(ValidationError):
        PluginManifest.model_validate(data)


def test_a_package_cannot_claim_a_review_but_needs_no_approval() -> None:
    data = manifest_data()
    data["capabilities"][0]["spec"] = spec(
        "echo", status="approved", reviewer="someone", evidence="claimed"
    )
    with pytest.raises(ValidationError):
        PluginManifest.model_validate(data)
    # An unreviewed, approval_required=True policy is plain metadata, not a gate.
    assert manifest().capabilities[0].spec.policy.status == "pending"


def test_runtime_and_capabilities_come_together_in_the_owned_worker_package() -> None:
    with pytest.raises(ValidationError):
        manifest(runtime=None)
    with pytest.raises(ValidationError):
        manifest(capabilities=[], routes=[], pages=[], runtime={"module": "aep_plugin_hello_lab"})
    for module in ("json", "host_runtime.web", "aep_plugin_other.worker", "aep_plugin_hello_lab_x"):
        with pytest.raises(ValidationError):
            manifest(runtime={"module": module})
    static = manifest(capabilities=[], routes=[], pages=[], runtime=None)
    assert static.runtime is None
    with pytest.raises(ValidationError):
        manifest(runtime={"module": "aep_plugin_hello_lab.worker", "interpreter": "python3"})


def test_routes_name_existing_read_capabilities_only() -> None:
    with pytest.raises(ValidationError):
        manifest(routes=[{"route_id": "summary", "capability": "hello-lab.missing"}])
    with pytest.raises(ValidationError):
        manifest(routes=[{"route_id": "save", "capability": "hello-lab.save_note"}], pages=[])
    with pytest.raises(ValidationError):
        manifest(
            routes=[
                {"route_id": "summary", "capability": "hello-lab.echo"},
                {"route_id": "summary", "capability": "hello-lab.echo"},
            ]
        )


@pytest.mark.parametrize(
    "block",
    [
        {"kind": "metric", "label": "x", "route_id": "missing", "field": "count"},
        {"kind": "metric", "label": "x", "route_id": "summary", "field": "missing"},
        {"kind": "metric", "label": "x", "route_id": "summary", "field": "items"},
        {
            "kind": "table",
            "route_id": "summary",
            "field": "count",
            "columns": [{"key": "label", "label": "L"}],
        },
        {
            "kind": "table",
            "route_id": "summary",
            "field": "items",
            "columns": [{"key": "secret_col", "label": "L"}],
        },
        {"kind": "table", "route_id": "summary", "field": "items", "columns": []},
        {"kind": "image", "src": "https://example.invalid/x.png"},
        {"kind": "text", "text": "x" * 4001},
    ],
)
def test_page_blocks_are_closed_and_cross_checked(block: dict[str, Any]) -> None:
    data = manifest_data()
    data["pages"][0]["blocks"] = [block]
    with pytest.raises(ValidationError):
        PluginManifest.model_validate(data)


def test_pages_only_use_routes_callable_without_input_and_ids_are_unique() -> None:
    data = manifest_data()
    data["capabilities"][0]["inputs"][0]["required"] = True
    with pytest.raises(ValidationError):
        PluginManifest.model_validate(data)
    data = manifest_data()
    data["pages"].append(dict(data["pages"][0]))
    with pytest.raises(ValidationError):
        PluginManifest.model_validate(data)
    data = manifest_data()
    data["pages"][0]["blocks"] = [{"kind": "text", "text": "x"}] * (plugins.MAX_BLOCKS + 1)
    with pytest.raises(ValidationError):
        PluginManifest.model_validate(data)


def test_bundled_assets_are_owned_unique_and_in_their_area() -> None:
    def broken(change: dict[str, Any]) -> None:
        data = manifest_data()
        data["assets"][0].update(change)
        with pytest.raises(ValidationError):
            PluginManifest.model_validate(data)

    broken({"identity": {"namespace": "other", "name": "hello-skill", "version": VERSION}})
    broken({"path": "assets/workflows/hello-lab__hello-skill__1.0.0.json"})
    broken({"path": "assets/skills/../x.json"})
    broken({"kind": "agent"})
    data = manifest_data()
    data["assets"].append(dict(data["assets"][0], path="assets/skills/second.json"))
    with pytest.raises(ValidationError):
        PluginManifest.model_validate(data)
    data = manifest_data()
    data["assets"].append(
        dict(
            data["assets"][0],
            identity={"namespace": "hello-lab", "name": "other", "version": VERSION},
        )
    )
    with pytest.raises(ValidationError):
        PluginManifest.model_validate(data)


def test_dependencies_are_exact_unique_and_not_self() -> None:
    other = {"namespace": "other-lab", "name": "base", "version": "1.2.3"}
    assert manifest(requires=[other]).requires == (AssetIdentity.model_validate(other),)
    with pytest.raises(ValidationError):
        manifest(requires=[other, dict(other, version="1.2.4")])
    with pytest.raises(ValidationError):
        manifest(requires=[{"namespace": "hello-lab", "name": "base", "version": "1.0.0"}])
    with pytest.raises(ValidationError):
        manifest(requires=[dict(other, version="1.2")])


def test_core_api_range_is_ordered_and_checked_against_the_core() -> None:
    assert CORE_PLUGIN_API_VERSION == "1.0.0"
    assert core_api_supported(manifest())
    assert not core_api_supported(manifest(core_api={"minimum": "1.1.0", "below": "2.0.0"}))
    assert not core_api_supported(manifest(), core="2.0.0")
    with pytest.raises(ValidationError):
        manifest(core_api={"minimum": "2.0.0", "below": "2.0.0"})


def test_embedded_credentials_are_refused() -> None:
    with pytest.raises(ValidationError):
        manifest(description="password=hunter2")


def test_data_marker_compatibility_has_no_migration() -> None:
    item = manifest()
    owner = item.identity
    assert data_marker_problem(item, None) is None
    same = PluginDataMarker(plugin_id=item.plugin_id, schema_version=1, written_by=owner)
    assert data_marker_problem(item, same) is None
    newer = same.model_copy(update={"schema_version": 2})
    assert data_marker_problem(item, PluginDataMarker.model_validate(newer)) == "plugin_data_newer"
    older = PluginDataMarker(plugin_id=item.plugin_id, schema_version=0, written_by=owner)
    assert data_marker_problem(item, older) == "plugin_migration_unsupported"
    foreign = PluginDataMarker(plugin_id="other-lab.base", schema_version=1, written_by=owner)
    assert data_marker_problem(item, foreign) == "plugin_data_foreign"
    with pytest.raises(ValidationError):
        manifest(data={"schema_version": 1, "migrations": []})


# -- paths and package ---------------------------------------------------------------


@pytest.mark.parametrize(
    "path",
    [
        "",
        "../x.py",
        "/worker/a.py",
        "C:/worker/a.py",
        "c:worker.py",
        "worker\\a.py",
        "worker/./a.py",
        "worker//a.py",
        "worker/a/",
        "worker/.hidden.py",
        "assets/skills/a.json:evil",
        "assets/skills/con.json",
        "assets/skills/nul.txt.json",
        "assets/skills/com1.json",
        "assets/skills/a.json.",
        "assets/skills/a .json",
        "Worker/A.py",
        "assets/skills/x.exe",
        "assets/skills/deep/x.json",
        "assets/agents/x.json",
        "other/x.json",
        "worker/x.dll",
        "worker/" + "a" * 200 + ".py",
        "assets/skills/caf\u00e9.json",
    ],
)
def test_package_paths_are_canonical_lowercase_inert_areas(path: str) -> None:
    assert plugin_path_problem(path) is not None


@pytest.mark.parametrize(
    "path",
    ["worker/aep_plugin_x/__init__.py", "worker/aep_plugin_x/data.json", "assets/skills/a__b.json"],
)
def test_ordinary_package_paths_are_accepted(path: str) -> None:
    assert plugin_path_problem(path) is None


def test_package_round_trips_with_exact_content_digest() -> None:
    package = PluginPackage.build(manifest(), files())
    payload = package.to_bytes()
    parsed = parse_plugin_package(payload)
    assert parsed == package
    assert parsed.file("worker/aep_plugin_hello_lab/worker.py").raw == b"print('synthetic')\n"
    assert parsed.content_sha256 == PluginPackage.build(manifest(), files()).content_sha256
    other = PluginPackage.build(manifest(), files(**{"worker/aep_plugin_hello_lab/x.json": b"1"}))
    assert other.content_sha256 != package.content_sha256


def _tampered(package: PluginPackage, mutate: Any) -> bytes:
    document = json.loads(package.to_bytes())
    mutate(document)
    return json.dumps(document).encode()


def test_tampered_envelopes_are_refused_without_echoing_content() -> None:
    package = PluginPackage.build(manifest(), files())

    def content(document: dict[str, Any]) -> None:
        document["files"][1]["content"] = base64.b64encode(b"print('evil')\n").decode()

    def digest(document: dict[str, Any]) -> None:
        document["content_sha256"] = "0" * 64

    def title(document: dict[str, Any]) -> None:
        document["manifest"]["title"] = "Changed"

    def size(document: dict[str, Any]) -> None:
        document["files"][1]["size"] = 1

    for mutate in (content, digest, title, size):
        with pytest.raises(PluginContractError) as raised:
            parse_plugin_package(_tampered(package, mutate))
        assert raised.value.code == "plugin_package_invalid"
        assert "evil" not in str(raised.value)
    with pytest.raises(PluginContractError) as raised:
        parse_plugin_package(b"PK\x03\x04 not a zip installer")
    assert raised.value.code == "plugin_package_invalid"


@pytest.mark.parametrize(
    "extra",
    [
        {"assets/skills/undeclared.json": b"{}"},
        {"worker/aep_plugin_other/x.py": b""},
        {"worker/aep_plugin_hello_lab/worker.py/x.py": b""},
    ],
)
def test_package_files_must_match_the_manifest(extra: dict[str, bytes]) -> None:
    with pytest.raises((ValidationError, ValueError)):
        PluginPackage.build(manifest(), files(**extra))


def test_asset_digest_runtime_module_and_worker_files_are_cross_checked() -> None:
    with pytest.raises((ValidationError, ValueError)):
        PluginPackage.build(
            manifest(), files(**{"assets/skills/hello-lab__hello-skill__1.0.0.json": b"[]"})
        )
    missing_module = files()
    del missing_module["worker/aep_plugin_hello_lab/worker.py"]
    with pytest.raises((ValidationError, ValueError)):
        PluginPackage.build(manifest(), missing_module)
    static = manifest(capabilities=[], routes=[], pages=[], runtime=None)
    with pytest.raises((ValidationError, ValueError)):
        PluginPackage.build(static, files())


def test_duplicate_paths_are_refused() -> None:
    package = PluginPackage.build(manifest(), files())

    def duplicate(document: dict[str, Any]) -> None:
        document["files"].append(document["files"][0])

    with pytest.raises(PluginContractError):
        parse_plugin_package(_tampered(package, duplicate))


def test_size_and_count_limits_are_explicit(monkeypatch: pytest.MonkeyPatch) -> None:
    assert plugins.MAX_PACKAGE_BYTES == 8 * 1024 * 1024
    assert plugins.MAX_FILE_BYTES <= plugins.MAX_TOTAL_FILE_BYTES < plugins.MAX_PACKAGE_BYTES
    payload = PluginPackage.build(manifest(), files()).to_bytes()
    monkeypatch.setattr(plugins, "MAX_PACKAGE_BYTES", len(payload) - 1)
    with pytest.raises(PluginContractError) as raised:
        parse_plugin_package(payload)
    assert raised.value.code == "plugin_package_too_large"
    monkeypatch.undo()
    monkeypatch.setattr(plugins, "MAX_TOTAL_FILE_BYTES", 10)
    with pytest.raises((ValidationError, ValueError)):
        PluginPackage.build(manifest(), files())
    monkeypatch.undo()
    monkeypatch.setattr(plugins, "MAX_FILES", 2)
    with pytest.raises((ValidationError, ValueError)):
        PluginPackage.build(manifest(), files())


# -- typed Bridge models ---------------------------------------------------------------


def test_capability_models_are_closed_typed_and_need_no_publisher_import() -> None:
    echo = manifest().capability("hello-lab.echo")
    inputs, outputs = capability_models(echo)
    assert inputs.model_validate({}).model_dump() == {"text": None}
    assert inputs.model_validate({"text": "hi"}).model_dump() == {"text": "hi"}
    bad_inputs: tuple[dict[str, Any], ...] = ({"text": 3}, {"text": "x" * 21}, {"other": 1})
    for bad in bad_inputs:
        with pytest.raises(ValidationError):
            inputs.model_validate(bad)
    assert set(inputs.model_json_schema()["properties"]) == {"text"}
    result = outputs.model_validate({"count": 1, "items": [{"label": "a", "value": 2}]})
    assert result.model_dump() == {"count": 1, "items": ({"label": "a", "value": 2},)}
    bad_outputs: tuple[dict[str, Any], ...] = (
        {"count": "1", "items": []},
        {"count": 1, "items": [{"label": "a", "other": 1}]},
        {"count": 1, "items": [{"label": {"nested": 1}}]},
        {"count": 1, "items": [{"label": "a"}] * (plugins.MAX_TABLE_ROWS + 1)},
        {"items": []},
    )
    for bad in bad_outputs:
        with pytest.raises(ValidationError):
            outputs.model_validate(bad)
    save_in, _ = capability_models(manifest().capability("hello-lab.save_note"))
    with pytest.raises(ValidationError):
        save_in.model_validate({})


# -- manager and Web messages ------------------------------------------------------------


def origin() -> PluginOrigin:
    return PluginOrigin(actor="person-1", channel="web", source="hello.aep-plugin.json")


def status(**changes: Any) -> PluginStatus:
    item = manifest()
    data: dict[str, Any] = {
        "plugin_id": item.plugin_id,
        "identity": item.identity,
        "title": item.title,
        "state": "active",
        "content_sha256": "a" * 64,
        "installed_by": origin(),
        "capabilities": tuple(c.spec.identity for c in item.capabilities),
        "routes": ("summary",),
        "pages": item.pages,
    }
    data.update(changes)
    return PluginStatus.model_validate(data)


def test_status_snapshot_and_action_results_are_consistent() -> None:
    active = status()
    assert active.failure is None
    failure = {"code": "plugin_health_failed", "message": "worker exited with code 1"}
    with pytest.raises(ValidationError):
        status(failure=failure)
    with pytest.raises(ValidationError):
        status(state="failed")
    failed = status(state="failed", failure=failure, capabilities=(), routes=(), pages=())
    with pytest.raises(ValidationError):
        status(state="disabled")  # inactive plugins expose no contributions
    with pytest.raises(ValidationError):
        status(plugin_id="other-lab.base")
    snapshot = PluginSnapshot(plugins=(active,))
    assert snapshot.get("hello-lab.hello") == active
    with pytest.raises(ValidationError):
        PluginSnapshot(plugins=(active, failed))
    other = status(
        plugin_id="hello-lab.other",
        identity={"namespace": "hello-lab", "name": "other", "version": VERSION},
    )
    with pytest.raises(ValidationError):  # one plugin owns a namespace
        PluginSnapshot(plugins=(active, other))
    PluginActionResult(
        action="install", status="succeeded", plugin_id=active.plugin_id, plugin=active
    )
    PluginActionResult(action="uninstall", status="succeeded", plugin_id=active.plugin_id)
    PluginActionResult(action="install", status="failed", failure=failure)
    with pytest.raises(ValidationError):
        PluginActionResult(action="install", status="succeeded", plugin_id=active.plugin_id)
    with pytest.raises(ValidationError):
        PluginActionResult(action="enable", status="failed", plugin_id=active.plugin_id)
    with pytest.raises(ValidationError):
        PluginActionResult(
            action="enable", status="failed", failure={"code": "made_up", "message": "x"}
        )


def test_read_request_and_response_are_bounded_and_honest(monkeypatch: pytest.MonkeyPatch) -> None:
    request = PluginReadRequest(
        request_id="r-1",
        plugin_id="hello-lab.hello",
        version=VERSION,
        route_id="summary",
        arguments={"text": "hi"},
    )
    assert request.arguments == {"text": "hi"}
    with pytest.raises(ValidationError):
        PluginReadRequest.model_validate(
            request.model_dump() | {"arguments": {"text": "x" * plugins.MAX_REQUEST_BYTES}}
        )
    with pytest.raises(ValidationError):
        PluginReadRequest.model_validate(request.model_dump() | {"version": "latest"})
    base = {"request_id": "r-1", "plugin_id": "hello-lab.hello", "version": VERSION}
    ok = PluginReadResponse(**base, route_id="summary", status="succeeded", data={"count": 1})
    assert ok.failure is None
    failure = {"code": "plugin_worker_failed", "message": "worker exited"}
    PluginReadResponse(**base, route_id="summary", status="failed", failure=failure)
    with pytest.raises(ValidationError):
        PluginReadResponse(**base, route_id="summary", status="failed")
    with pytest.raises(ValidationError):
        PluginReadResponse(
            **base, route_id="summary", status="failed", failure=failure, data={"count": 1}
        )
    with pytest.raises(ValidationError):
        PluginReadResponse(**base, route_id="summary", status="succeeded", failure=failure)
    monkeypatch.setattr(plugins, "MAX_RESPONSE_BYTES", 8)
    with pytest.raises(ValidationError):
        PluginReadResponse(**base, route_id="summary", status="succeeded", data={"count": 12345})


def test_manager_protocol_is_satisfiable_by_a_generic_implementation() -> None:
    class Fake:
        def snapshot(self) -> PluginSnapshot:
            return PluginSnapshot()

        def install(self, payload: bytes, origin: PluginOrigin) -> PluginActionResult:
            return PluginActionResult(
                action="install",
                status="failed",
                failure={"code": "plugin_package_invalid", "message": "invalid"},
            )

        def enable(self, plugin_id: str, origin: PluginOrigin) -> PluginActionResult:
            return self.install(b"", origin)

        def disable(self, plugin_id: str, origin: PluginOrigin) -> PluginActionResult:
            return self.install(b"", origin)

        def uninstall(self, plugin_id: str, origin: PluginOrigin) -> PluginActionResult:
            return self.install(b"", origin)

        def call_read(
            self, request: PluginReadRequest, *, timeout_seconds: float
        ) -> PluginReadResponse:
            raise NotImplementedError

        def set_busy_probe(self, probe: Any) -> None:
            return None

        def close(self) -> None:
            return None

    manager: plugins.PluginManagerProtocol = Fake()
    assert manager.snapshot().plugins == ()


# -- boundaries --------------------------------------------------------------------------


def test_contract_module_has_no_approval_signer_or_feature_imports() -> None:
    source = Path(plugins.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = {
        (node.module or "") if isinstance(node, ast.ImportFrom) else alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    roots = {name.split(".")[0] for name in imported}
    assert roots <= {
        "__future__",
        "base64",
        "binascii",
        "collections",
        "hashlib",
        "json",
        "re",
        "typing",
        "pydantic",
        "common",
        "capabilities",
    }
    assert {name for name in imported if name.startswith("capabilities")} == {
        "capabilities.contracts"
    }
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    names |= {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
    for forbidden in (
        "ExtensionActivationApproval",
        "ExtensionTrustPolicy",
        "TrustedPublisherKey",
        "ExtensionSignature",
        "HostRuntime",
    ):
        assert forbidden not in names
    assert "signature" not in PluginPackage.model_fields
    assert "signature" not in PluginManifest.model_fields
