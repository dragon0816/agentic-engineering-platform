"""Productization 3 slice 1: Bridge Extensions and Applications stay distinct."""

import hashlib
from typing import Any

import pytest
from pydantic import ValidationError

from common.distribution import PublishedAssetPackage
from common.member import MemberCatalogEntry
from extensions.contracts import BridgeExtensionManifest
from software.evolution import SoftwareManifest
from software.marketplace import (
    ApplicationCatalogEntry,
    ApplicationIntegration,
    project_application,
)

REVISION = "1" * 64


def capability() -> dict[str, Any]:
    return {
        "identity": {"namespace": "lab", "name": "measure-temperature", "version": "1.0.0"},
        "name": "measure_temperature",
        "description": "Read one temperature measurement from the local fixture.",
        "input_contract": "lab.measure-temperature.input.v1",
        "output_contract": "lab.measure-temperature.output.v1",
        "side_effect": "read",
        "policy": {
            "status": "approved",
            "reviewer": "platform-security",
            "evidence": "bounded fixture read reviewed",
            "risk": "medium",
            "approval_required": True,
            "required_permissions": ["instrument.read"],
            "policy_refs": ["extension-instrument-read-policy"],
        },
    }


def extension(**changes: Any) -> BridgeExtensionManifest:
    values: dict[str, Any] = {
        "metadata": {
            "identity": {"namespace": "lab", "name": "temperature-extension", "version": "1.0.0"},
            "owner": {"type": "team", "id": "lab-automation"},
            "visibility": "organization",
            "lifecycle": "published",
            "technical_policy": {
                "status": "approved",
                "reviewer": "platform-security",
                "evidence": "out-of-process boundary reviewed",
                "risk": "high",
                "approval_required": True,
                "required_permissions": ["process.execute"],
                "policy_refs": ["bridge-extension-policy"],
            },
            "validation_refs": ["extension-validation:temperature-v1"],
        },
        "description": "Temperature fixture integration",
        "compatibility": {},
        "process": {"module": "aep_temperature_extension"},
        "capabilities": [capability()],
        "publisher_key": {"key_id": "lab-automation-release-key"},
    }
    values.update(changes)
    return BridgeExtensionManifest.model_validate(values)


def software() -> SoftwareManifest:
    return SoftwareManifest.model_validate(
        {
            "metadata": {
                "identity": {
                    "namespace": "engineering",
                    "name": "report-portal",
                    "version": "2.0.0",
                },
                "owner": {"type": "team", "id": "reporting"},
                "visibility": "organization",
                "lifecycle": "published",
                "business_approval": {
                    "status": "approved",
                    "reviewer": "report-owner",
                    "evidence": "release accepted",
                },
                "validation_refs": ["report-portal:2.0.0"],
                "evaluation_refs": ["report-portal:e2e"],
            },
            "repository": {
                "provider": "github",
                "locator": "dragon0816/report-portal",
                "revision": REVISION,
            },
            "interfaces": [
                {
                    "name": "report_api",
                    "input_contract": "report.request.v1",
                    "output_contract": "report.response.v1",
                }
            ],
            "release": {
                "release_ref": "release://report-portal/2.0.0",
                "source_revision": REVISION,
                "evidence_refs": ["ci://report-portal/2.0.0"],
            },
        }
    )


def test_extension_declares_only_out_of_process_typed_capabilities() -> None:
    manifest = extension()
    assert manifest.compatibility.python == "3.12"
    assert manifest.process.protocol == "aep-extension-jsonl/v1"
    assert manifest.rollback.retain_versions == 2
    assert manifest.capabilities[0].policy.required_permissions == ("instrument.read",)
    payload = manifest.model_dump(mode="json")
    assert "callable" not in payload and "in_process" not in payload
    with pytest.raises(ValidationError):
        BridgeExtensionManifest.model_validate({**payload, "in_process": True})


def test_extension_publication_requires_policy_evidence_and_unique_capabilities() -> None:
    manifest = extension()
    unapproved = manifest.model_dump(mode="json")
    unapproved["metadata"]["technical_policy"] = {
        "status": "pending",
        "risk": "high",
        "approval_required": True,
    }
    with pytest.raises(ValidationError, match="technical approval"):
        BridgeExtensionManifest.model_validate(unapproved)
    with pytest.raises(ValidationError, match="each capability once"):
        BridgeExtensionManifest.model_validate(
            {**manifest.model_dump(mode="json"), "capabilities": [capability(), capability()]}
        )


def test_extension_package_is_not_an_agent_add_on() -> None:
    manifest = extension()
    content = manifest.model_dump_json().encode()
    package = PublishedAssetPackage.model_validate(
        {
            "kind": "bridge_extension",
            "metadata": {
                **manifest.metadata.model_dump(mode="json"),
                "package": {
                    "artifact_ref": "registry://lab/temperature-extension/1.0.0",
                    "sha256": hashlib.sha256(content).hexdigest(),
                },
            },
        }
    )
    with pytest.raises(ValidationError, match="Agent Add-ons"):
        MemberCatalogEntry(package=package)


def test_application_projects_external_software_without_becoming_bridge_code() -> None:
    entry = ApplicationCatalogEntry(
        software=software(),
        integrations=(
            ApplicationIntegration(
                name="portal", kind="web_ui", url="https://reports.example.invalid"
            ),
            ApplicationIntegration(
                name="reports",
                kind="api",
                interface="report_api",
                url="https://reports.example.invalid/api",
            ),
        ),
    )
    projection = project_application(entry)
    assert projection.identity == software().metadata.identity
    assert projection.repository_locator == "dragon0816/report-portal"
    payload = projection.model_dump(mode="json")
    assert "process" not in payload and "package" not in payload and "install" not in payload


def test_application_integrations_are_declared_and_secure() -> None:
    with pytest.raises(ValidationError, match="requires HTTPS"):
        ApplicationIntegration(name="portal", kind="web_ui", url="http://reports.example.invalid")
    with pytest.raises(ValidationError, match="declared Software interface"):
        ApplicationCatalogEntry(
            software=software(),
            integrations=(
                ApplicationIntegration(
                    name="unknown",
                    kind="api",
                    interface="missing",
                    url="https://reports.example.invalid/api",
                ),
            ),
        )
