"""Portable Knowledge packages preserve evidence without trusting publisher paths."""

import base64
import hashlib
import json
import shutil
from pathlib import Path

import pytest
from pydantic import ValidationError

from common.assets import AssetIdentity, AssetMetadata, BusinessApproval, Owner
from knowledge.evolution import (
    KnowledgeManifest,
    decision_digest,
    knowledge_digest,
    raw_digest,
)
from knowledge.package import (
    PORTABLE_VAULT_REF,
    KnowledgePackageFile,
    PortableKnowledgePackage,
    install_knowledge_package,
    package_knowledge,
)
from knowledge.vault import Vault

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "e2e_05" / "vault"
IDENTITY = AssetIdentity(namespace="engineering", name="widget-guide", version="1.0.0")


def copied_vault(tmp_path: Path) -> Vault:
    root = tmp_path / "source"
    shutil.copytree(FIXTURE, root)
    return Vault(root)


def manifest(vault: Vault) -> KnowledgeManifest:
    return KnowledgeManifest(
        metadata=AssetMetadata(
            identity=IDENTITY,
            owner=Owner(type="team", id="engineering-knowledge"),
            visibility="team",
            lifecycle="published",
            business_approval=BusinessApproval(
                status="approved", reviewer="domain-owner", evidence="reviewed"
            ),
            validation_refs=("knowledge-eval:baseline",),
        ),
        domain="engineering",
        vault_ref=str(vault.root.resolve()),
        raw_sha256=raw_digest(vault),
        decisions_sha256=decision_digest(vault),
        content_sha256=knowledge_digest(vault),
    )


def test_package_round_trip_uses_a_portable_ref_and_preserves_governed_content(
    tmp_path: Path,
) -> None:
    source = copied_vault(tmp_path)
    package = package_knowledge(manifest(source), source)

    assert package.manifest.vault_ref == PORTABLE_VAULT_REF
    assert {item.path for item in package.files} == {
        "decisions.md",
        "index.md",
        "log.md",
        "raw/guide.md",
        "wiki/entities/Widget.md",
        "wiki/sources/Guide.md",
    }
    assert all(not item.path.startswith("drop/") for item in package.files)

    target = tmp_path / "installed" / "engineering" / "widget-guide" / "1.0.0"
    installed = install_knowledge_package(package.model_dump_json().encode(), target)
    vault = Vault(target)

    assert installed.metadata.identity == IDENTITY
    assert installed.vault_ref == str(target.resolve())
    assert raw_digest(vault) == installed.raw_sha256
    assert decision_digest(vault) == installed.decisions_sha256
    assert knowledge_digest(vault) == installed.content_sha256
    assert not (target / "drop").exists()


@pytest.mark.parametrize(
    "path",
    (
        "../outside.md",
        "/absolute.md",
        "C:/outside.md",
        "raw\\guide.md",
        "drop/original.pdf",
        ".ingest-state.json",
        "wiki/not-markdown.txt",
    ),
)
def test_package_file_rejects_noncanonical_or_unowned_paths(path: str) -> None:
    with pytest.raises(ValidationError):
        KnowledgePackageFile.of(path, b"content")


def test_package_rejects_digest_drift_identity_ambiguity_and_embedded_secrets(
    tmp_path: Path,
) -> None:
    source = copied_vault(tmp_path)
    package = package_knowledge(manifest(source), source)
    payload = package.model_dump(mode="json")

    changed = json.loads(json.dumps(payload))
    changed["files"][0]["content"] = KnowledgePackageFile.of(
        changed["files"][0]["path"], b"changed"
    ).content
    with pytest.raises(ValidationError):
        PortableKnowledgePackage.model_validate(changed)

    wrong = json.loads(json.dumps(payload))
    wrong["identity"] = {"namespace": "other", "name": "guide", "version": "1.0.0"}
    with pytest.raises(ValidationError):
        PortableKnowledgePackage.model_validate(wrong)

    secret = json.loads(json.dumps(payload))
    secret_bytes = b"api_key=do-not-package-this"
    secret["files"].append(
        {
            "path": "wiki/secret.md",
            "sha256": hashlib.sha256(secret_bytes).hexdigest(),
            "content": base64.b64encode(secret_bytes).decode("ascii"),
        }
    )
    with pytest.raises(ValidationError):
        PortableKnowledgePackage.model_validate(secret)


def test_failed_install_leaves_no_target_or_partial_vault(tmp_path: Path) -> None:
    source = copied_vault(tmp_path)
    package = package_knowledge(manifest(source), source)
    invalid = json.loads(package.model_dump_json())
    invalid["files"] = [item for item in invalid["files"] if item["path"] != "index.md"]
    target = tmp_path / "installed"

    with pytest.raises(ValueError, match="invalid Knowledge package"):
        install_knowledge_package(json.dumps(invalid).encode(), target)

    assert not target.exists()
    assert not list(tmp_path.glob("installed.part-*"))


def test_install_refuses_to_replace_an_existing_version(tmp_path: Path) -> None:
    source = copied_vault(tmp_path)
    package = package_knowledge(manifest(source), source)
    target = tmp_path / "installed"
    target.mkdir()

    with pytest.raises(ValueError, match="already exists"):
        install_knowledge_package(package.model_dump_json().encode(), target)
