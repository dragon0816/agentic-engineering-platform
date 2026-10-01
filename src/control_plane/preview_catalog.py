"""Harmless preview assets used to exercise Marketplace discovery and sync."""

from __future__ import annotations

import base64
import hashlib
from collections.abc import MutableMapping

from agent.skills import SkillManifest
from capabilities.files import READ_FILE_SPEC
from common.assets import (
    AssetIdentity,
    AssetMetadata,
    ExecutionDependencies,
    Owner,
    PackageMetadata,
    WorkflowManifest,
)
from common.distribution import PublishedAssetPackage
from control_plane.app_types import RegistryState
from control_plane.distribution import ControlError
from control_plane.registry_sqlite import SqliteRegistry
from extensions.contracts import BridgeExtensionManifest
from extensions.package import ExtensionPackageFile, ExtensionSignature, PortableExtensionPackage

OWNER = Owner(type="organization", id="aep-preview")


def _metadata(name: str, categories: tuple[str, ...]) -> AssetMetadata:
    return AssetMetadata(
        identity=AssetIdentity(namespace="preview", name=name, version="1.0.0"),
        owner=OWNER,
        visibility="organization",
        lifecycle="published",
        categories=categories,
        provenance=({"source": "built-in preview catalog", "revision": "1"},),
    )


def _distributed(
    kind: str, metadata: AssetMetadata, content: bytes, description: str
) -> PublishedAssetPackage:
    identity = metadata.identity
    described = metadata.model_copy(
        update={
            "package": PackageMetadata(
                artifact_ref=(
                    f"registry://{identity.namespace}/{identity.name}/{identity.version}"
                ),
                sha256=hashlib.sha256(content).hexdigest(),
            )
        }
    )
    return PublishedAssetPackage.model_validate(
        {
            "kind": kind,
            "metadata": described,
            "description": description,
        }
    )


def _workflow(
    name: str, description: str, categories: tuple[str, ...]
) -> tuple[PublishedAssetPackage, bytes]:
    manifest = WorkflowManifest(
        metadata=_metadata(name, categories),
        description=description,
        execution={"mode": "local"},
        dependencies=ExecutionDependencies(
            local_capabilities=(READ_FILE_SPEC.name,), central_required=False
        ),
        input_contract=f"preview.{name}.input.v1",
        output_contract=f"preview.{name}.output.v1",
        steps=(READ_FILE_SPEC.identity,),
    )
    content = manifest.model_dump_json(indent=2).encode("utf-8")
    return _distributed("workflow", manifest.metadata, content, description), content


def _skill(
    name: str,
    alias: str,
    instructions: str,
    workflow: AssetIdentity,
    categories: tuple[str, ...],
) -> tuple[PublishedAssetPackage, bytes]:
    manifest = SkillManifest.model_validate(
        {
            "metadata": _metadata(name, categories),
            "alias": alias,
            "instructions": instructions,
            "commands": [{"name": "run", "kind": "workflow", "target": workflow}],
            "default_command": "run",
        }
    )
    content = manifest.model_dump_json(indent=2).encode("utf-8")
    return _distributed("skill", manifest.metadata, content, instructions), content


def _extension() -> tuple[PublishedAssetPackage, bytes]:
    metadata = _metadata("fixture-health-extension", ("testing", "bridge"))
    manifest = BridgeExtensionManifest.model_validate(
        {
            "metadata": metadata.model_copy(
                update={
                    "technical_policy": {
                        "status": "approved",
                        "reviewer": "platform-admin",
                        "evidence": "Built-in inert preview fixture",
                        "risk": "low",
                        "approval_required": False,
                        "policy_refs": ["preview-extension-policy"],
                        "assessment": "manual",
                    },
                    "validation_refs": ("preview-extension-contract-test",),
                }
            ),
            "description": "Inert fixture for administrator Extension discovery and review.",
            "compatibility": {},
            "process": {"module": "aep_preview_extension"},
            "capabilities": [
                {
                    "identity": {
                        "namespace": "preview",
                        "name": "fixture-health",
                        "version": "1.0.0",
                    },
                    "name": "preview.fixture_health",
                    "description": "Return local fixture health without external side effects",
                    "input_contract": "preview.fixture-health.input.v1",
                    "output_contract": "preview.fixture-health.output.v1",
                    "side_effect": "read",
                    "policy": {
                        "status": "approved",
                        "reviewer": "platform-admin",
                        "evidence": "Built-in inert preview fixture",
                        "risk": "low",
                        "approval_required": False,
                        "policy_refs": ["preview-extension-policy"],
                        "assessment": "manual",
                    },
                }
            ],
            "publisher_key": {"key_id": "aep-preview-fixture"},
        }
    )
    files = (
        ExtensionPackageFile.of("requirements.lock", b"# inert preview fixture\n"),
        ExtensionPackageFile.of("wheels/aep_preview_extension-1.0.0-py3-none-any.whl", b"fixture"),
    )
    envelope = PortableExtensionPackage.unsigned(
        manifest=manifest,
        files=files,
        signature=ExtensionSignature(
            key_id="aep-preview-fixture",
            value=base64.b64encode(bytes(64)).decode("ascii"),
        ),
    )
    content = envelope.model_dump_json(indent=2).encode("utf-8")
    return _distributed(
        "bridge_extension", manifest.metadata, content, manifest.description
    ), content


def preview_packages() -> tuple[tuple[PublishedAssetPackage, bytes], ...]:
    """Return deterministic package metadata and bytes for the local preview."""

    triage = AssetIdentity(namespace="preview", name="incident-triage", version="1.0.0")
    review = AssetIdentity(namespace="preview", name="checklist-review", version="1.0.0")
    return (
        _workflow(
            "incident-triage",
            "Read a local incident note through the governed read-only capability.",
            ("operations", "testing"),
        ),
        _workflow(
            "checklist-review",
            "Read a local checklist through the governed read-only capability.",
            ("quality", "testing"),
        ),
        _skill(
            "incident-triage-skill",
            "triage",
            "Guide an incident-note review and route execution to the preview Workflow.",
            triage,
            ("operations", "assistant"),
        ),
        _skill(
            "checklist-review-skill",
            "checklist",
            "Guide a checklist review and route execution to the preview Workflow.",
            review,
            ("quality", "assistant"),
        ),
        _extension(),
    )


def seed_preview_catalog(state: RegistryState) -> tuple[PublishedAssetPackage, ...]:
    """Publish preview assets once without changing existing package versions."""

    published: list[PublishedAssetPackage] = []
    for package, content in preview_packages():
        if state.packages.get(package.metadata.identity) is not None:
            continue
        if isinstance(state.packages, SqliteRegistry):
            saved = state.packages.publish(package, artifact=content)
        else:
            saved = state.packages.publish(package)
            if not isinstance(state.artifacts, MutableMapping):
                raise ControlError("artifact_missing")
            described = saved.metadata.package
            if described is None:
                raise ControlError("artifact_missing")
            state.artifacts[described.artifact_ref] = content
        published.append(saved)
    return tuple(published)
