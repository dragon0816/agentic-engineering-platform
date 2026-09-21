import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from agent.contracts import AgentProfile
from agent.registry import AssetNotFound, DuplicateAsset, InMemoryTaskRegistry, TaskRegistry
from common.assets import AssetIdentity, TaskManifest
from common.evaluation import EvaluationCase
from common.execution import ExecutionAuthorization
from workflow.host_bridge import BridgeRegistration
from workflow.proof import advertise_sample

ROOT = Path(__file__).resolve().parents[1]


def sample() -> TaskManifest:
    return TaskManifest.model_validate_json((ROOT / "tasks/inspect.json").read_text())


def test_vertical_proof() -> None:
    manifest = sample()
    bridge = BridgeRegistration.model_validate_json((ROOT / "examples/bridge.json").read_text())
    registry: TaskRegistry = InMemoryTaskRegistry()
    advertisement = advertise_sample(manifest, registry, bridge)
    assert registry.discover(namespace="sample") == (manifest,)
    assert advertisement.installed_tasks == (manifest.metadata.identity,)
    assert advertisement.capabilities[0].identity == manifest.capability
    assert advertisement.capabilities[0].side_effect == "read"
    assert not ExecutionAuthorization().allowed
    assert not hasattr(registry, "execute")
    assert not hasattr(advertisement, "execute")
    assert BridgeRegistration.model_validate_json(advertisement.model_dump_json()) == advertisement


def test_scoped_versions_and_duplicate_conflicts() -> None:
    registry = InMemoryTaskRegistry()
    original = sample()
    for namespace, version in [("sample", "1.0.0"), ("other", "1.0.0"), ("sample", "2.0.0")]:
        data = original.model_dump()
        data["metadata"]["identity"].update(namespace=namespace, version=version)
        registry.register(TaskManifest.model_validate(data))
    assert len(registry.discover()) == 3
    assert len(registry.discover(namespace="sample")) == 2
    assert registry.get(original.metadata.identity) == original
    with pytest.raises(DuplicateAsset):
        registry.register(original)
    with pytest.raises(AssetNotFound):
        registry.get(AssetIdentity(namespace="missing", name="inspect", version="1.0.0"))


def test_publication_is_only_discovery_state() -> None:
    registry = InMemoryTaskRegistry()
    data = sample().model_dump()
    data["metadata"]["lifecycle"] = "validated"
    validated = TaskManifest.model_validate(data)
    registry.register(validated)
    assert registry.discover() == ()
    assert registry.get(validated.metadata.identity) == validated
    for lifecycle in ("draft", "deprecated"):
        data["metadata"]["lifecycle"] = lifecycle
        data["metadata"]["deprecation_reason"] = "test"
        with pytest.raises(ValueError):
            InMemoryTaskRegistry().register(TaskManifest.model_validate(data))


def test_registry_revalidates_even_constructed_models() -> None:
    data = sample().model_dump()
    invalid = TaskManifest.model_construct(**{**data, "description": "password=synthetic"})
    with pytest.raises(ValidationError):
        InMemoryTaskRegistry().register(invalid)


def test_discovery_filters_and_snapshot_isolation() -> None:
    registry = InMemoryTaskRegistry()
    task = sample()
    registry.register(task)
    assert registry.discover(name="missing") == ()
    assert registry.discover(visibility="private") == ()
    assert registry.discover(visibility="public") == (task,)
    returned = registry.get(task.metadata.identity)
    object.__setattr__(returned, "description", "changed")
    assert registry.get(task.metadata.identity).description == task.description


def test_advertisement_requires_installed_capability() -> None:
    bridge = BridgeRegistration.model_validate_json((ROOT / "examples/bridge.json").read_text())
    empty = BridgeRegistration.model_validate({**bridge.model_dump(), "capabilities": []})
    with pytest.raises(ValueError, match="installed capability"):
        advertise_sample(sample(), InMemoryTaskRegistry(), empty)


def test_engineering_profile_and_evaluation_case() -> None:
    profile = AgentProfile.model_validate_json((ROOT / "agents/engineering.json").read_text())
    assert profile.metadata.identity.name == "engineering"
    assert profile.may_delegate_to == ()
    case = EvaluationCase.model_validate_json(
        (ROOT / "evaluation/cases/discover-task.json").read_text()
    )
    # A discovery case names no route: what must hold is stated as assertions,
    # and `tests/test_evaluation.py` grades them against the proof itself.
    assert case.expected_route is None
    assert "bridge_advertisement" in case.assertions
    assert set(case.forbidden_side_effects) == {"write", "execute", "external_side_effect"}
    assert json.loads(case.model_dump_json())["category"] == "deterministic"


def test_proof_rejects_unfulfilled_dependencies_before_registration() -> None:
    bridge = BridgeRegistration.model_validate_json((ROOT / "examples/bridge.json").read_text())
    changes: list[dict[str, object]] = [
        {"dependencies": {"local_capabilities": ["missing"], "central_required": False}},
        {
            "dependencies": {
                "central_required": True,
                "central_services": [{"name": "service", "required": True}],
            }
        },
        {"secrets": [{"name": "reference_only"}]},
        {"input_contract": "mismatch.v1"},
    ]
    for change in changes:
        task = TaskManifest.model_validate({**sample().model_dump(), **change})
        registry = InMemoryTaskRegistry()
        with pytest.raises(ValueError):
            advertise_sample(task, registry, bridge)
        assert registry.discover() == ()


def test_proof_does_not_access_external_resources(monkeypatch: pytest.MonkeyPatch) -> None:
    import builtins
    import socket
    import subprocess

    manifest = sample()
    bridge = BridgeRegistration.model_validate_json((ROOT / "examples/bridge.json").read_text())

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("proof attempted an external side effect")

    with monkeypatch.context() as patch:
        patch.setattr(builtins, "open", forbidden)
        patch.setattr(Path, "open", forbidden)
        patch.setattr(socket, "socket", forbidden)
        patch.setattr(subprocess, "Popen", forbidden)
        result = advertise_sample(manifest, InMemoryTaskRegistry(), bridge)
    assert result.installed_tasks == (manifest.metadata.identity,)


def test_bridge_rejects_duplicate_capabilities() -> None:
    data = json.loads((ROOT / "examples/bridge.json").read_text())
    data["capabilities"] *= 2
    with pytest.raises(ValidationError):
        BridgeRegistration.model_validate(data)
