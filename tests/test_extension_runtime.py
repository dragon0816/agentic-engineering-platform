"""Productization 3 slice 3: bounded activation, health and rollback."""

import base64
import hashlib
import json
import os
import subprocess
import venv
from pathlib import Path
from typing import Any

import pytest

from common.assets import AssetIdentity
from extensions.contracts import BridgeExtensionManifest
from extensions.package import (
    ExtensionPackageFile,
    ExtensionSignature,
    ExtensionTrustPolicy,
    PortableExtensionPackage,
    StagedExtension,
    stage_extension_package,
)
from extensions.runtime import (
    ExtensionActivationApproval,
    ExtensionInvocationError,
    ExtensionManager,
    ExtensionRequest,
    ExtensionResponse,
    SubprocessExtensionFactory,
)

PUBLIC_KEY = b"r" * 32


class Verifier:
    def verify(self, *, public_key: bytes, message: bytes, signature: bytes) -> bool:
        return signature == hashlib.sha256(public_key + message).digest() * 2


def manifest(version: str) -> BridgeExtensionManifest:
    return BridgeExtensionManifest.model_validate(
        {
            "metadata": {
                "identity": {"namespace": "lab", "name": "fixture-extension", "version": version},
                "owner": {"type": "team", "id": "lab-automation"},
                "visibility": "organization",
                "lifecycle": "published",
                "technical_policy": {
                    "status": "approved",
                    "reviewer": "platform-security",
                    "evidence": "external process reviewed",
                    "risk": "high",
                    "approval_required": True,
                    "required_permissions": ["process.execute"],
                    "policy_refs": ["bridge-extension-policy"],
                },
                "validation_refs": [f"extension-validation:{version}"],
            },
            "description": "Fixture integration",
            "compatibility": {},
            "process": {"module": "aep_fixture_extension"},
            "capabilities": [
                {
                    "identity": {"namespace": "lab", "name": "read-fixture", "version": version},
                    "name": "read_fixture",
                    "description": "Read a bounded fixture.",
                    "input_contract": "lab.fixture.input.v1",
                    "output_contract": "lab.fixture.output.v1",
                    "side_effect": "read",
                    "policy": {
                        "status": "approved",
                        "reviewer": "platform-security",
                        "evidence": "fixture read reviewed",
                        "risk": "medium",
                        "approval_required": True,
                        "required_permissions": ["fixture.read"],
                        "policy_refs": ["fixture-read-policy"],
                    },
                }
            ],
            "publisher_key": {"key_id": "lab-release-key"},
        }
    )


def staged(tmp_path: Path, version: str) -> StagedExtension:
    extension = manifest(version)
    files = (
        ExtensionPackageFile.of("requirements.lock", f"fixture=={version}\n".encode()),
        ExtensionPackageFile.of(f"wheels/fixture-{version}-py3-none-any.whl", b"wheel"),
    )
    placeholder = ExtensionSignature(
        key_id="lab-release-key", value=base64.b64encode(b"0" * 64).decode("ascii")
    )
    unsigned = PortableExtensionPackage.unsigned(
        manifest=extension, files=files, signature=placeholder
    )
    signed = unsigned.model_copy(
        update={
            "signature": ExtensionSignature(
                key_id="lab-release-key",
                value=base64.b64encode(
                    hashlib.sha256(PUBLIC_KEY + unsigned.signed_content).digest() * 2
                ).decode("ascii"),
            )
        }
    )
    trust = ExtensionTrustPolicy.model_validate(
        {
            "keys": [
                {
                    "key_id": "lab-release-key",
                    "public_key": base64.b64encode(PUBLIC_KEY).decode("ascii"),
                }
            ]
        }
    )
    return stage_extension_package(
        signed.model_dump_json().encode(), tmp_path / "extensions", trust, Verifier()
    )


def approval(version: str, **changes: Any) -> ExtensionActivationApproval:
    values: dict[str, Any] = {
        "approval_id": f"activate-{version.replace('.', '-')}",
        "actor": "device-admin",
        "device_id": "bridge-lab",
        "device_kind": "shared_test_computer",
        "extension": {"namespace": "lab", "name": "fixture-extension", "version": version},
        "policy_ref": "bridge-extension-policy",
    }
    values.update(changes)
    return ExtensionActivationApproval.model_validate(values)


class Session:
    def __init__(self, identities: tuple[AssetIdentity, ...], *, healthy: bool = True) -> None:
        self.identities = identities
        self.healthy = healthy
        self.closed = False
        self.fail_invoke = False

    def exchange(self, request: ExtensionRequest, timeout_seconds: int) -> ExtensionResponse:
        if request.operation == "health":
            if not self.healthy:
                return ExtensionResponse(
                    request_id=request.request_id, status="failed", code="unhealthy"
                )
            return ExtensionResponse(
                request_id=request.request_id,
                status="healthy",
                capabilities=self.identities,
            )
        if self.fail_invoke:
            raise RuntimeError("process exited")
        return ExtensionResponse(
            request_id=request.request_id,
            status="succeeded",
            data={"observed": request.arguments},
        )

    def poll(self) -> int | None:
        return 1 if self.closed else None

    def close(self) -> None:
        self.closed = True


class Factory:
    def __init__(self) -> None:
        self.sessions: list[Session] = []
        self.next_healthy = True
        self.start_count = 0

    def start(
        self, staged_value: StagedExtension, manifest_value: BridgeExtensionManifest
    ) -> Session:
        self.start_count += 1
        session = Session(
            tuple(item.identity for item in manifest_value.capabilities),
            healthy=self.next_healthy,
        )
        self.next_healthy = True
        self.sessions.append(session)
        return session


def manager(factory: Factory) -> ExtensionManager:
    return ExtensionManager(
        device_id="bridge-lab", device_kind="shared_test_computer", factory=factory
    )


def test_only_healthy_approved_extension_is_advertised_and_invoked(tmp_path: Path) -> None:
    factory = Factory()
    runtime = manager(factory)
    version = staged(tmp_path, "1.0.0")

    record = runtime.activate(version, approval("1.0.0"))
    advertised = runtime.advertised_capabilities
    result = runtime.invoke(advertised[0].identity, {"sample": 7}, request_id="invoke-1")

    assert record.state == "active"
    assert [item.identity for item in advertised] == list(record.advertised_capabilities)
    assert result == {"observed": {"sample": 7}}


def test_wrong_device_approval_is_refused_before_process_start(tmp_path: Path) -> None:
    factory = Factory()
    runtime = manager(factory)

    with pytest.raises(ValueError, match="does not match"):
        runtime.activate(staged(tmp_path, "1.0.0"), approval("1.0.0", device_id="another-bridge"))

    assert factory.start_count == 0
    assert runtime.advertised_capabilities == ()


def test_unhealthy_upgrade_keeps_previous_healthy_version(tmp_path: Path) -> None:
    factory = Factory()
    runtime = manager(factory)
    runtime.activate(staged(tmp_path, "1.0.0"), approval("1.0.0"))
    original = factory.sessions[-1]
    factory.next_healthy = False

    record = runtime.activate(staged(tmp_path, "2.0.0"), approval("2.0.0"))

    assert record.state == "rolled_back"
    assert record.extension.version == "1.0.0"
    assert runtime.advertised_capabilities[0].identity.version == "1.0.0"
    assert not original.closed
    assert factory.sessions[-1].closed


def test_process_failure_removes_new_version_and_automatically_rolls_back(
    tmp_path: Path,
) -> None:
    factory = Factory()
    runtime = manager(factory)
    runtime.activate(staged(tmp_path, "1.0.0"), approval("1.0.0"))
    runtime.activate(staged(tmp_path, "2.0.0"), approval("2.0.0"))
    factory.sessions[-1].fail_invoke = True
    target = AssetIdentity(namespace="lab", name="read-fixture", version="2.0.0")

    with pytest.raises(ExtensionInvocationError, match="extension_process_failure"):
        runtime.invoke(target, {}, request_id="invoke-crash")

    assert runtime.record is not None and runtime.record.state == "rolled_back"
    assert runtime.advertised_capabilities[0].identity.version == "1.0.0"
    assert factory.start_count == 3


def test_health_identity_mismatch_never_advertises(tmp_path: Path) -> None:
    class WrongFactory(Factory):
        def start(
            self, staged_value: StagedExtension, manifest_value: BridgeExtensionManifest
        ) -> Session:
            self.start_count += 1
            session = Session((AssetIdentity(namespace="other", name="unknown", version="1.0.0"),))
            self.sessions.append(session)
            return session

    factory = WrongFactory()
    runtime = manager(factory)
    record = runtime.activate(staged(tmp_path, "1.0.0"), approval("1.0.0"))

    assert record.state == "unhealthy"
    assert runtime.advertised_capabilities == ()
    assert factory.sessions[0].closed


def test_crash_limit_disables_reactivation_inside_the_window(tmp_path: Path) -> None:
    factory = Factory()
    runtime = manager(factory)
    value = staged(tmp_path, "1.0.0")
    target = AssetIdentity(namespace="lab", name="read-fixture", version="1.0.0")

    for index in range(3):
        runtime.activate(value, approval("1.0.0"))
        factory.sessions[-1].fail_invoke = True
        with pytest.raises(ExtensionInvocationError):
            runtime.invoke(target, {}, request_id=f"crash-{index}")

    refused = runtime.activate(value, approval("1.0.0"))
    assert refused.state == "disabled"
    assert refused.code == "extension_crash_limit"
    assert runtime.advertised_capabilities == ()
    assert factory.start_count == 3


def test_environment_preparation_uses_only_staged_wheels(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    value = staged(tmp_path, "1.0.0")
    calls: list[list[str]] = []

    class Builder:
        def create(self, target: Path) -> None:
            (target / "Scripts").mkdir(parents=True)
            (target / "Scripts" / "python.exe").write_bytes(b"python")

    def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(venv, "EnvBuilder", lambda **_: Builder())
    monkeypatch.setattr(subprocess, "run", run)

    SubprocessExtensionFactory._prepare(value)
    SubprocessExtensionFactory._prepare(value)

    assert len(calls) == 1
    assert "--no-index" in calls[0] and "--no-deps" in calls[0]
    assert all(
        argument.startswith(str(Path(value.root)))
        for argument in calls[0]
        if argument.endswith(".whl")
    )
    assert json.loads(
        (Path(value.root) / ".venv" / ".aep-prepared.json").read_text(encoding="utf-8")
    ) == {"content_sha256": value.content_sha256}


@pytest.mark.skipif(os.name != "nt", reason="the supported extension runner is Windows-only")
def test_subprocess_factory_uses_the_json_lines_protocol(tmp_path: Path) -> None:
    value = staged(tmp_path, "1.0.0")
    root = Path(value.root)
    environment = root / ".venv"
    venv.EnvBuilder(with_pip=False).create(environment)
    module = environment / "Lib" / "site-packages" / "aep_fixture_extension.py"
    identity = manifest("1.0.0").capabilities[0].identity.model_dump(mode="json")
    module.write_text(
        "import json, sys\n"
        f"capability = {identity!r}\n"
        "for line in sys.stdin:\n"
        "    request = json.loads(line)\n"
        "    if request['operation'] == 'health':\n"
        "        response = {'protocol':'aep-extension-jsonl/v1',"
        "'request_id':request['request_id'],"
        "'status':'healthy','capabilities':[capability],'data':None,'code':None}\n"
        "    else:\n"
        "        response = {'protocol':'aep-extension-jsonl/v1',"
        "'request_id':request['request_id'],"
        "'status':'succeeded','capabilities':[],'data':request['arguments'],'code':None}\n"
        "    print(json.dumps(response), flush=True)\n",
        encoding="utf-8",
    )
    (environment / ".aep-prepared.json").write_text(
        json.dumps({"content_sha256": value.content_sha256}), encoding="utf-8"
    )
    session = SubprocessExtensionFactory().start(value, manifest("1.0.0"))
    try:
        response = session.exchange(
            ExtensionRequest(request_id="wire-health", operation="health"), 5
        )
    finally:
        session.close()

    assert response.status == "healthy"
    assert response.capabilities == (manifest("1.0.0").capabilities[0].identity,)


def test_wire_contract_is_closed_and_correlates_request_identity() -> None:
    with pytest.raises(ValueError):
        ExtensionRequest.model_validate(
            {"request_id": "health-1", "operation": "health", "arguments": {"bad": True}}
        )
    response = ExtensionResponse.model_validate_json(
        json.dumps(
            {
                "request_id": "invoke-1",
                "status": "refused",
                "code": "not_allowed",
            }
        )
    )
    assert response.code == "not_allowed"
