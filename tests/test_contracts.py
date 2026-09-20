import json

import pytest
from pydantic import ValidationError

from common.assets import (
    AssetIdentity,
    AssetMetadata,
    BusinessApproval,
    ExecutionDependencies,
    SecretRef,
    TaskManifest,
    TechnicalPolicy,
    WorkflowManifest,
)
from common.execution import ExecutionAuthorization, RouteDecision


def task_data() -> dict[str, object]:
    return {
        "metadata": {
            "identity": {"namespace": "sample", "name": "inspect", "version": "1.0.0"},
            "owner": {"type": "user", "id": "engineer"},
            "visibility": "private",
            "lifecycle": "published",
        },
        "description": "Inspect sample metadata",
        "capability": {"namespace": "sample", "name": "inspect", "version": "1.0.0"},
        "execution": {"mode": "local"},
        "dependencies": {
            "local_capabilities": ["sample.inspect"],
            "central_services": [],
            "central_required": False,
        },
        "input_contract": "sample.inspect.input.v1",
        "output_contract": "sample.inspect.output.v1",
    }


def test_manifest_round_trip_and_separate_governance() -> None:
    task = TaskManifest.model_validate(task_data())
    assert TaskManifest.model_validate_json(task.model_dump_json()) == task
    assert task.metadata.identity.namespace != task.metadata.owner.id
    assert task.metadata.visibility == "private"
    assert task.metadata.business_approval.status == "pending"
    assert task.metadata.technical_policy.status == "pending"
    assert not ExecutionAuthorization().allowed
    with pytest.raises(ValidationError):
        ExecutionAuthorization(allowed=True)


@pytest.mark.parametrize("version", ["1", "v1.0.0", "01.0.0", "1.0.0-01", "1.0.0+", "1.0.0\n"])
def test_invalid_semver(version: str) -> None:
    with pytest.raises(ValidationError):
        AssetIdentity(namespace="sample", name="inspect", version=version)


@pytest.mark.parametrize("version", ["0.1.0", "1.2.3-rc.1", "1.0.0+build.01"])
def test_valid_semver(version: str) -> None:
    assert AssetIdentity(namespace="sample", name="inspect", version=version).version == version


@pytest.mark.parametrize("name", ["", "../escape", "a/b", "a@b", "Upper", "a:b"])
def test_identity_has_no_ambiguous_delimiters(name: str) -> None:
    with pytest.raises(ValidationError):
        AssetIdentity(namespace=name, name="inspect", version="1.0.0")


@pytest.mark.parametrize("field", ["password", "token", "secret_value", "api_key", "value"])
def test_secret_ref_rejects_value_fields(field: str) -> None:
    with pytest.raises(ValidationError):
        SecretRef.model_validate({"name": "github_token", field: "synthetic-secret"})


@pytest.mark.parametrize(
    "text",
    [
        "password=synthetic",
        "Bearer synthetic-token",
        "-----BEGIN PRIVATE KEY-----",
        "api_key: synthetic",
    ],
)
def test_embedded_secrets_rejected(text: str) -> None:
    data = task_data()
    data["description"] = text
    with pytest.raises(ValidationError):
        TaskManifest.model_validate(data)


def test_arbitrary_registry_fields_rejected() -> None:
    data = task_data()
    data["configuration"] = {"token": "synthetic"}
    with pytest.raises(ValidationError):
        TaskManifest.model_validate(data)
    data = json.loads(json.dumps(task_data()))
    data["metadata"]["owner"]["credentials"] = "synthetic"
    with pytest.raises(ValidationError):
        TaskManifest.model_validate(data)


def test_explicit_central_requirements() -> None:
    with pytest.raises(ValidationError):
        ExecutionDependencies.model_validate({})
    for central_required in (True, False):
        with pytest.raises(ValidationError):
            ExecutionDependencies.model_validate(
                {
                    "central_required": central_required,
                    "central_services": [{"name": "registry", "required": not central_required}],
                }
            )
    dependencies = ExecutionDependencies.model_validate(
        {
            "central_required": False,
            "central_services": [{"name": "registry", "required": False}],
        }
    )
    assert not dependencies.central_required
    assert ExecutionDependencies.model_validate(
        {
            "central_required": True,
            "central_services": [{"name": "knowledge", "required": True}],
        }
    ).central_required


def test_approval_and_risk_validation() -> None:
    with pytest.raises(ValidationError):
        BusinessApproval(status="approved")
    with pytest.raises(ValidationError):
        TechnicalPolicy(risk="high", approval_required=False)
    with pytest.raises(ValidationError):
        TechnicalPolicy(status="approved")
    business = BusinessApproval(status="approved", reviewer="domain-owner", evidence="review-1")
    metadata = AssetMetadata.model_validate(
        {
            **TaskManifest.model_validate(task_data()).metadata.model_dump(),
            "business_approval": business,
        }
    )
    assert metadata.technical_policy.status == "pending"


def test_route_requires_explicit_target() -> None:
    with pytest.raises(ValidationError):
        RouteDecision(kind="capability", reason="known command")


def test_workflow_and_secret_requirements_round_trip() -> None:
    data = task_data()
    data.pop("capability")
    data["steps"] = [{"namespace": "sample", "name": "inspect", "version": "1.0.0"}]
    data["secrets"] = [{"name": "github_token"}]
    workflow = WorkflowManifest.model_validate(data)
    assert WorkflowManifest.model_validate_json(workflow.model_dump_json()) == workflow
    assert workflow.secrets[0].name == "github_token"
    data["steps"] = []
    with pytest.raises(ValidationError):
        WorkflowManifest.model_validate(data)


def test_central_mode_cannot_claim_offline_execution() -> None:
    data = task_data()
    data["execution"] = {"mode": "central"}
    with pytest.raises(ValidationError):
        TaskManifest.model_validate(data)


def test_governance_enums_and_nested_secret_scanning() -> None:
    metadata = TaskManifest.model_validate(task_data()).metadata.model_dump()
    for field, value in [("lifecycle", "trusted"), ("visibility", "department")]:
        with pytest.raises(ValidationError):
            AssetMetadata.model_validate({**metadata, field: value})
    with pytest.raises(ValidationError):
        AssetMetadata.model_validate({**metadata, "provenance": [{"source": "password=synthetic"}]})
    with pytest.raises(ValidationError):
        AssetMetadata.model_validate({**metadata, "lifecycle": "deprecated"})


def test_dependency_duplicates_and_boolean_coercion_rejected() -> None:
    with pytest.raises(ValidationError):
        ExecutionDependencies.model_validate({"central_required": "false"})
    with pytest.raises(ValidationError):
        ExecutionDependencies.model_validate(
            {"central_required": False, "local_capabilities": ["a", "a"]}
        )
    with pytest.raises(ValidationError):
        ExecutionDependencies.model_validate(
            {
                "central_required": False,
                "central_services": [{"name": "a", "required": False}] * 2,
            }
        )
