"""Synthetic feature-plugin packages for integration tests (Slice 1).

Packages are built with the frozen contract's `PluginPackage.build` from a real
stdlib JSON-lines worker (`tests/fixtures/plugins/worker.py`) and real Skill /
Workflow manifests in the plugin's own namespace. Nothing here touches company
data, the network, a resident AEP or the shared environment.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from agent.skills import SkillManifest
from common.assets import WorkflowManifest
from common.plugins import (
    PluginManifest,
    PluginOrigin,
    PluginPackage,
    worker_package_for,
)

FIXTURES = Path(__file__).parent / "fixtures" / "plugins"
WorkerKind = Literal["ok", "bad_health", "crash"]
_WORKER_FILES: dict[WorkerKind, str] = {
    "ok": "worker.py",
    "bad_health": "worker_bad_health.py",
    "crash": "worker_crash.py",
}


def origin(channel: str = "test") -> PluginOrigin:
    return PluginOrigin(actor="fixture-owner", channel=channel, source="synthetic fixture")


def _spec(namespace: str, version: str, local: str, side_effect: str) -> dict[str, Any]:
    name = f"{namespace}.{local}"
    return {
        "identity": {"namespace": namespace, "name": local.replace("_", "-"), "version": version},
        "name": name,
        "description": f"Synthetic {local} capability.",
        "input_contract": f"{name}.input",
        "output_contract": f"{name}.output",
        "side_effect": side_effect,
        "policy": {"risk": "low", "approval_required": True},
    }


def capability_identity(namespace: str, local: str, version: str = "1.0.0") -> dict[str, str]:
    return {"namespace": namespace, "name": local.replace("_", "-"), "version": version}


def skill_manifest(namespace: str, version: str) -> SkillManifest:
    """A real Skill in the plugin namespace whose command targets the plugin's read tool.

    Metadata stays draft/pending: a package cannot claim a review."""
    from host_runtime.assets import manifests

    base = next(
        item
        for item in manifests(include_personal=False)
        if isinstance(item, SkillManifest) and item.alias == "knowledge"
    )
    data = json.loads(base.model_dump_json())
    data["metadata"]["identity"] = {
        "namespace": namespace,
        "name": "summary-skill",
        "version": version,
    }
    data["metadata"]["lifecycle"] = "draft"
    data["metadata"]["business_approval"] = {
        "status": "pending",
        "reviewer": None,
        "evidence": None,
    }
    data["metadata"]["validation_refs"] = []
    data["alias"] = namespace.replace("-", "_") + "_summary"
    data["instructions"] = "Read the synthetic plugin summary with the summary command."
    data["commands"] = [
        {
            "name": "summary",
            "kind": "capability",
            "target": capability_identity(namespace, "read_summary", version),
        }
    ]
    data["default_command"] = "summary"
    return SkillManifest.model_validate(data)


def workflow_manifest(namespace: str, version: str) -> WorkflowManifest:
    """A real one-step Workflow in the plugin namespace that runs the plugin's read tool."""
    from host_runtime.assets import manifests

    base = next(
        item
        for item in manifests(include_personal=False)
        if isinstance(item, WorkflowManifest) and len(item.steps) == 1 and not item.parameters
    )
    data = json.loads(base.model_dump_json())
    data["metadata"]["identity"] = {
        "namespace": namespace,
        "name": "summary-flow",
        "version": version,
    }
    data["metadata"]["lifecycle"] = "draft"
    data["metadata"]["business_approval"] = {
        "status": "pending",
        "reviewer": None,
        "evidence": None,
    }
    data["metadata"]["validation_refs"] = []
    data["description"] = "Read the synthetic plugin summary."
    data["dependencies"]["local_capabilities"] = [f"{namespace}.read_summary"]
    data["input_contract"] = f"{namespace}.read_summary.input"
    data["output_contract"] = f"{namespace}.read_summary.output"
    data["run_alias"] = None
    data["steps"] = [
        {
            "capability": capability_identity(namespace, "read_summary", version),
            "inputs": {},
            "retry": {"max_attempts": 1, "delay_ms": 100},
        }
    ]
    return WorkflowManifest.model_validate(data)


def _asset_bytes(model: SkillManifest | WorkflowManifest) -> bytes:
    return model.model_dump_json(indent=2).encode("utf-8")


def asset_path(kind: str, namespace: str, name: str, version: str) -> str:
    return f"assets/{kind}s/{namespace}__{name}__{version}.json"


def manifest_data(
    namespace: str, version: str = "1.0.0", *, with_assets: bool = True
) -> tuple[dict[str, Any], dict[str, bytes]]:
    """Manifest data and the asset files it declares (digests computed from the bytes)."""
    import hashlib

    package = worker_package_for(namespace)
    assets: list[dict[str, Any]] = []
    asset_files: dict[str, bytes] = {}
    if with_assets:
        for kind, model in (
            ("skill", skill_manifest(namespace, version)),
            ("workflow", workflow_manifest(namespace, version)),
        ):
            identity = model.metadata.identity
            path = asset_path(kind, namespace, identity.name, version)
            raw = _asset_bytes(model)
            asset_files[path] = raw
            assets.append(
                {
                    "kind": kind,
                    "identity": identity.model_dump(mode="json"),
                    "path": path,
                    "sha256": hashlib.sha256(raw).hexdigest(),
                }
            )
    data: dict[str, Any] = {
        "format": "aep-plugin/1",
        "identity": {"namespace": namespace, "name": "fixture", "version": version},
        "title": f"Fixture {namespace}",
        "description": "Synthetic fixture plugin; local test data only.",
        "core_api": {"minimum": "1.0.0", "below": "2.0.0"},
        "runtime": {"module": f"{package}.worker"},
        "capabilities": [
            {
                "spec": _spec(namespace, version, "read_summary", "read"),
                "outputs": [
                    {"name": "count", "type": "integer"},
                    {"name": "items", "type": "rows", "columns": ["label", "value"]},
                ],
            },
            {
                "spec": _spec(namespace, version, "write_note", "write"),
                "inputs": [{"name": "note", "type": "string", "max_length": 200}],
                "outputs": [
                    {"name": "saved", "type": "boolean"},
                    {"name": "counter", "type": "integer"},
                ],
            },
        ],
        "routes": [{"route_id": "summary", "capability": f"{namespace}.read_summary"}],
        "pages": [
            {
                "page_id": "overview",
                "title": "Overview",
                "blocks": [
                    {"kind": "text", "text": "<b>Synthetic</b> data only."},
                    {"kind": "metric", "label": "Notes", "route_id": "summary", "field": "count"},
                    {
                        "kind": "table",
                        "route_id": "summary",
                        "field": "items",
                        "columns": [
                            {"key": "label", "label": "Label"},
                            {"key": "value", "label": "Value"},
                        ],
                    },
                ],
            }
        ],
        "assets": assets,
        "data": {"schema_version": 1},
    }
    return data, asset_files


def build_package(
    namespace: str,
    version: str = "1.0.0",
    *,
    worker: WorkerKind = "ok",
    with_assets: bool = True,
) -> PluginPackage:
    data, asset_files = manifest_data(namespace, version, with_assets=with_assets)
    package = worker_package_for(namespace)
    files = {
        f"worker/{package}/__init__.py": b"",
        f"worker/{package}/worker.py": (FIXTURES / _WORKER_FILES[worker]).read_bytes(),
        **asset_files,
    }
    return PluginPackage.build(PluginManifest.model_validate(data), files)


def package_bytes(namespace: str, version: str = "1.0.0", **options: Any) -> bytes:
    return build_package(namespace, version, **options).to_bytes()


def build_manager(workspace: Path, installed: Any, **options: Any) -> Any:
    """The one place the integration tests construct the production manager:
    `PluginManager(layout, installed, *, reserved_names, assets_changed, busy,
    interpreter)` as stated by the manager worker. Until `plugins.manager`
    exists this import fails, which is the expected red state."""
    from host_runtime.contracts import HostLayout
    from plugins.manager import PluginManager

    return PluginManager(HostLayout.under(workspace), installed, **options)
