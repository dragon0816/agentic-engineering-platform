"""Productization 3 slice 2: signed extension packages stage inertly."""

import base64
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from extensions.contracts import BridgeExtensionManifest, ExtensionCompatibility
from extensions.package import (
    ExtensionPackageFile,
    ExtensionSignature,
    ExtensionTrustPolicy,
    PortableExtensionPackage,
    stage_extension_package,
)

PUBLIC_KEY = b"p" * 32


class DeterministicVerifier:
    """Test double that proves staging verifies the exact canonical bytes."""

    def verify(self, *, public_key: bytes, message: bytes, signature: bytes) -> bool:
        return signature == hashlib.sha256(public_key + message).digest() * 2


class RejectingVerifier:
    def verify(self, *, public_key: bytes, message: bytes, signature: bytes) -> bool:
        return False


def manifest(**changes: Any) -> BridgeExtensionManifest:
    values: dict[str, Any] = {
        "metadata": {
            "identity": {"namespace": "lab", "name": "fixture-extension", "version": "1.0.0"},
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
            "validation_refs": ["extension-validation:fixture-v1"],
        },
        "description": "Fixture integration",
        "compatibility": {},
        "process": {"module": "aep_fixture_extension"},
        "capabilities": [
            {
                "identity": {"namespace": "lab", "name": "read-fixture", "version": "1.0.0"},
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
    values.update(changes)
    return BridgeExtensionManifest.model_validate(values)


def files() -> tuple[ExtensionPackageFile, ...]:
    return (
        ExtensionPackageFile.of("requirements.lock", b"fixture-extension==1.0.0\n"),
        ExtensionPackageFile.of("wheels/fixture_extension-1.0.0-py3-none-any.whl", b"wheel"),
    )


def package(manifest_value: BridgeExtensionManifest | None = None) -> PortableExtensionPackage:
    actual = manifest_value or manifest()
    placeholder = ExtensionSignature(
        key_id="lab-release-key", value=base64.b64encode(b"0" * 64).decode("ascii")
    )
    unsigned = PortableExtensionPackage.unsigned(
        manifest=actual, files=files(), signature=placeholder
    )
    signature = hashlib.sha256(PUBLIC_KEY + unsigned.signed_content).digest() * 2
    return unsigned.model_copy(
        update={
            "signature": ExtensionSignature(
                key_id="lab-release-key", value=base64.b64encode(signature).decode("ascii")
            )
        }
    )


def trust(*, revoked: bool = False) -> ExtensionTrustPolicy:
    return ExtensionTrustPolicy.model_validate(
        {
            "keys": [
                {
                    "key_id": "lab-release-key",
                    "public_key": base64.b64encode(PUBLIC_KEY).decode("ascii"),
                    "revoked": revoked,
                }
            ]
        }
    )


def test_signed_package_stages_exact_inert_bytes_atomically(tmp_path: Path) -> None:
    value = package()
    staged = stage_extension_package(
        value.model_dump_json().encode(), tmp_path / "extensions", trust(), DeterministicVerifier()
    )

    root = Path(staged.root)
    assert root == (tmp_path / "extensions" / "lab" / "fixture-extension" / "1.0.0")
    assert (root / "requirements.lock").read_bytes() == b"fixture-extension==1.0.0\n"
    assert (root / "wheels" / "fixture_extension-1.0.0-py3-none-any.whl").read_bytes() == b"wheel"
    assert (
        json.loads((root / "extension.json").read_text(encoding="utf-8"))["kind"]
        == "bridge_extension"
    )
    assert not list((tmp_path / "extensions").rglob(".part-*"))
    assert not (root / ".venv").exists()


@pytest.mark.parametrize(
    "path",
    ("../escape.whl", "/absolute.whl", "C:/escape.whl", "wheels\\bad.whl", "run.py"),
)
def test_extension_file_rejects_noncanonical_or_executable_paths(path: str) -> None:
    with pytest.raises(ValidationError):
        ExtensionPackageFile.of(path, b"content")


def test_staging_fails_closed_for_signature_trust_and_compatibility(tmp_path: Path) -> None:
    value = package()
    payload = value.model_dump_json().encode()

    with pytest.raises(ValueError, match="signature is invalid"):
        stage_extension_package(payload, tmp_path / "bad-signature", trust(), RejectingVerifier())
    with pytest.raises(ValueError, match="revoked"):
        stage_extension_package(
            payload, tmp_path / "revoked", trust(revoked=True), DeterministicVerifier()
        )
    incompatible = ExtensionCompatibility.model_validate(
        {
            "bridge_contract": "1",
            "platform": "windows",
            "python": "3.12",
            "abi": "cp312-win_amd64",
            "protocol": "aep-extension-jsonl/v1",
        }
    ).model_copy(update={"abi": "unsupported"})
    with pytest.raises(ValueError, match="incompatible"):
        stage_extension_package(
            payload,
            tmp_path / "incompatible",
            trust(),
            DeterministicVerifier(),
            compatibility=incompatible,
        )


def test_invalid_or_existing_stage_leaves_no_partial_version(tmp_path: Path) -> None:
    value = package()
    changed = json.loads(value.model_dump_json())
    changed["files"][0]["content"] = base64.b64encode(b"changed").decode("ascii")
    root = tmp_path / "extensions"
    with pytest.raises(ValueError, match="invalid extension package"):
        stage_extension_package(
            json.dumps(changed).encode(), root, trust(), DeterministicVerifier()
        )
    assert not root.exists()

    target = root / "lab" / "fixture-extension" / "1.0.0"
    target.mkdir(parents=True)
    with pytest.raises(ValueError, match="already exists"):
        stage_extension_package(
            value.model_dump_json().encode(), root, trust(), DeterministicVerifier()
        )
