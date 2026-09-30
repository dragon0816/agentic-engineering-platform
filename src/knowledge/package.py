"""Portable, inert Knowledge packages and their path-safe local installation."""

from __future__ import annotations

import base64
import binascii
import hashlib
import os
import re
import shutil
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Literal, Self
from uuid import uuid4

from pydantic import Field, ValidationError, field_validator, model_validator

from common.assets import AssetIdentity, RegistryContract, reject_embedded_secrets
from common.base import Contract, Sha256, Text
from knowledge.evolution import (
    KnowledgeManifest,
    decision_digest,
    knowledge_digest,
    raw_digest,
)
from knowledge.vault import Vault, VaultError

PORTABLE_VAULT_REF = "package://vault"
_ROOT_FILES = frozenset({"index.md", "log.md", "decisions.md"})
_DRIVE = re.compile(r"^[A-Za-z]:")


def _path(value: str) -> str:
    """Accept one canonical package-relative path and no platform aliases."""
    if (
        not value
        or "\\" in value
        or value.startswith("/")
        or _DRIVE.match(value)
        or PureWindowsPath(value).is_absolute()
    ):
        raise ValueError("Knowledge package paths are canonical relative POSIX paths")
    parsed = PurePosixPath(value)
    if parsed.as_posix() != value or any(part in {"", ".", ".."} for part in parsed.parts):
        raise ValueError("Knowledge package paths are canonical relative POSIX paths")
    if value in _ROOT_FILES:
        return value
    if value.startswith("raw/") and len(parsed.parts) > 1:
        return value
    if value.startswith("wiki/") and len(parsed.parts) > 1 and value.endswith(".md"):
        return value
    raise ValueError("Knowledge packages contain only governed Raw and Wiki content")


class KnowledgePackageFile(Contract):
    path: Text
    sha256: Sha256
    content: str

    @field_validator("path")
    @classmethod
    def safe_path(cls, value: str) -> str:
        return _path(value)

    @field_validator("content")
    @classmethod
    def base64_content(cls, value: str) -> str:
        try:
            base64.b64decode(value, validate=True)
        except (binascii.Error, ValueError):
            raise ValueError("Knowledge package content is base64") from None
        return value

    @model_validator(mode="after")
    def matching_digest(self) -> Self:
        if hashlib.sha256(self.raw).hexdigest() != self.sha256:
            raise ValueError("Knowledge package file digest does not match")
        try:
            reject_embedded_secrets(self.raw.decode("utf-8"))
        except UnicodeDecodeError:
            pass
        return self

    @classmethod
    def of(cls, path: str, raw: bytes) -> Self:
        return cls(
            path=path,
            sha256=hashlib.sha256(raw).hexdigest(),
            content=base64.b64encode(raw).decode("ascii"),
        )

    @property
    def raw(self) -> bytes:
        return base64.b64decode(self.content, validate=True)


def _digest(parts: list[tuple[str, bytes]]) -> str:
    value = hashlib.sha256()
    for name, data in sorted(parts):
        value.update(name.encode("utf-8"))
        value.update(b"\0")
        value.update(data)
        value.update(b"\0")
    return value.hexdigest()


class PortableKnowledgePackage(RegistryContract):
    """One exact published Knowledge version, without a host-controlled path."""

    schema_version: Literal["1"] = "1"
    identity: AssetIdentity
    manifest: KnowledgeManifest
    files: tuple[KnowledgePackageFile, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def complete_and_governed(self) -> Self:
        if self.identity != self.manifest.metadata.identity:
            raise ValueError("Knowledge package identity must match its manifest")
        if self.manifest.metadata.lifecycle != "published":
            raise ValueError("only published Knowledge may be packaged")
        if self.manifest.vault_ref != PORTABLE_VAULT_REF:
            raise ValueError("a portable Knowledge manifest cannot choose a local Vault path")
        names = [item.path for item in self.files]
        if len(names) != len(set(names)):
            raise ValueError("Knowledge package paths must be unique")
        if not _ROOT_FILES.issubset(names):
            raise ValueError("Knowledge package is missing required Vault files")
        if not any(name.startswith("raw/") for name in names):
            raise ValueError("Knowledge package requires immutable Raw evidence")
        if not any(name.startswith("wiki/") for name in names):
            raise ValueError("Knowledge package requires curated Wiki content")
        content = {item.path: item.raw for item in self.files}
        raw_parts = [(name, data) for name, data in content.items() if name.startswith("raw/")]
        knowledge_parts = [
            (name, data)
            for name, data in content.items()
            if (name.startswith("raw/") and name.endswith(".md") and "/assets/" not in name)
            or (name.startswith("wiki/") and name.endswith(".md"))
            or name in _ROOT_FILES
        ]
        if _digest(raw_parts) != self.manifest.raw_sha256:
            raise ValueError("Knowledge package Raw digest does not match")
        if hashlib.sha256(content["decisions.md"]).hexdigest() != self.manifest.decisions_sha256:
            raise ValueError("Knowledge package decision digest does not match")
        if _digest(knowledge_parts) != self.manifest.content_sha256:
            raise ValueError("Knowledge package content digest does not match")
        return self


def _package_files(vault: Vault) -> tuple[KnowledgePackageFile, ...]:
    root = vault.root.resolve()
    names: set[str] = set(_ROOT_FILES)
    for area in ("raw", "wiki"):
        names.update(
            path.resolve().relative_to(root).as_posix()
            for path in (root / area).rglob("*")
            if path.is_file()
        )
    return tuple(
        KnowledgePackageFile.of(name, (root / name).read_bytes()) for name in sorted(names)
    )


def package_knowledge(manifest: KnowledgeManifest, vault: Vault) -> PortableKnowledgePackage:
    """Package a verified local Vault; originals under ``drop/`` stay local."""
    checked = KnowledgeManifest.model_validate(manifest)
    if Path(checked.vault_ref).resolve() != vault.root.resolve():
        raise ValueError("Knowledge manifest names another Vault")
    if (
        raw_digest(vault) != checked.raw_sha256
        or decision_digest(vault) != checked.decisions_sha256
        or knowledge_digest(vault) != checked.content_sha256
    ):
        raise ValueError("Knowledge Vault content has drifted from its manifest")
    portable = checked.model_copy(update={"vault_ref": PORTABLE_VAULT_REF})
    return PortableKnowledgePackage(
        identity=checked.metadata.identity,
        manifest=portable,
        files=_package_files(vault),
    )


def install_knowledge_package(payload: bytes, target_root: Path) -> KnowledgeManifest:
    """Validate all bytes, then atomically expose one host-derived Vault path."""
    try:
        package = PortableKnowledgePackage.model_validate_json(payload)
    except ValidationError:
        raise ValueError("invalid Knowledge package") from None
    target = Path(target_root)
    if not target.is_absolute():
        raise ValueError("Knowledge installation target must be absolute")
    if target.exists():
        raise ValueError("Knowledge version already exists")
    target.parent.mkdir(parents=True, exist_ok=True)
    stage = target.with_name(f"{target.name}.part-{uuid4().hex}")
    try:
        (stage / "raw").mkdir(parents=True)
        (stage / "wiki").mkdir(parents=True)
        for item in package.files:
            destination = stage / PurePosixPath(item.path)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(item.raw)
        vault = Vault(stage)
        if (
            raw_digest(vault) != package.manifest.raw_sha256
            or decision_digest(vault) != package.manifest.decisions_sha256
            or knowledge_digest(vault) != package.manifest.content_sha256
        ):
            raise ValueError("invalid Knowledge package")
        os.replace(stage, target)
    except (OSError, VaultError, ValueError):
        if stage.exists():
            shutil.rmtree(stage)
        raise
    return package.manifest.model_copy(update={"vault_ref": str(target.resolve())})
