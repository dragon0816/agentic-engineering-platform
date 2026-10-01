"""Signed, inert Bridge Extension packages and atomic local staging."""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import os
import re
import shutil
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Literal, Protocol, Self
from uuid import uuid4

from pydantic import Field, ValidationError, field_validator, model_validator

from common.assets import AssetIdentity, RegistryContract
from common.base import Contract, Sha256, Symbol, Text
from extensions.contracts import BridgeExtensionManifest, ExtensionCompatibility

_DRIVE = re.compile(r"^[A-Za-z]:")
_LOCK = "requirements.lock"


def _package_path(value: str) -> str:
    if (
        not value
        or "\\" in value
        or value.startswith("/")
        or _DRIVE.match(value)
        or PureWindowsPath(value).is_absolute()
    ):
        raise ValueError("extension package paths are canonical relative POSIX paths")
    parsed = PurePosixPath(value)
    if parsed.as_posix() != value or any(part in {"", ".", ".."} for part in parsed.parts):
        raise ValueError("extension package paths are canonical relative POSIX paths")
    if value == _LOCK:
        return value
    if len(parsed.parts) == 2 and parsed.parts[0] == "wheels" and value.endswith(".whl"):
        return value
    raise ValueError("extension packages contain only a lock file and offline wheels")


def _decode(value: str, *, what: str, length: int | None = None) -> bytes:
    try:
        decoded = base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError):
        raise ValueError(f"{what} is base64") from None
    if length is not None and len(decoded) != length:
        raise ValueError(f"{what} has the required length")
    return decoded


class ExtensionPackageFile(Contract):
    path: Text
    sha256: Sha256
    content: str

    @field_validator("path")
    @classmethod
    def safe_path(cls, value: str) -> str:
        return _package_path(value)

    @field_validator("content")
    @classmethod
    def base64_content(cls, value: str) -> str:
        _decode(value, what="extension package content")
        return value

    @model_validator(mode="after")
    def matching_digest(self) -> Self:
        if hashlib.sha256(self.raw).hexdigest() != self.sha256:
            raise ValueError("extension package file digest does not match")
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
        return _decode(self.content, what="extension package content")


class ExtensionSignature(Contract):
    algorithm: Literal["ed25519"] = "ed25519"
    key_id: Symbol
    value: str

    @field_validator("value")
    @classmethod
    def ed25519_signature(cls, value: str) -> str:
        _decode(value, what="Ed25519 signature", length=64)
        return value

    @property
    def raw(self) -> bytes:
        return _decode(self.value, what="Ed25519 signature", length=64)


class TrustedPublisherKey(Contract):
    algorithm: Literal["ed25519"] = "ed25519"
    key_id: Symbol
    public_key: str
    revoked: bool = False

    @field_validator("public_key")
    @classmethod
    def ed25519_public_key(cls, value: str) -> str:
        _decode(value, what="Ed25519 public key", length=32)
        return value

    @property
    def raw(self) -> bytes:
        return _decode(self.public_key, what="Ed25519 public key", length=32)


class ExtensionTrustPolicy(Contract):
    keys: tuple[TrustedPublisherKey, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_keys(self) -> Self:
        ids = [item.key_id for item in self.keys]
        if len(ids) != len(set(ids)):
            raise ValueError("publisher key identifiers are unique")
        return self

    def trusted(self, key_id: str) -> TrustedPublisherKey:
        key = next((item for item in self.keys if item.key_id == key_id), None)
        if key is None:
            raise ValueError("extension publisher key is not trusted")
        if key.revoked:
            raise ValueError("extension publisher key is revoked")
        return key


class ExtensionSignatureVerifier(Protocol):
    """Injected Ed25519 boundary; there is deliberately no permissive default."""

    def verify(self, *, public_key: bytes, message: bytes, signature: bytes) -> bool: ...


class PortableExtensionPackage(RegistryContract):
    schema_version: Literal["1"] = "1"
    identity: AssetIdentity
    manifest: BridgeExtensionManifest
    files: tuple[ExtensionPackageFile, ...] = Field(min_length=2)
    content_sha256: Sha256
    signature: ExtensionSignature

    @model_validator(mode="after")
    def complete_and_governed(self) -> Self:
        if self.identity != self.manifest.metadata.identity:
            raise ValueError("extension package identity must match its manifest")
        if self.manifest.metadata.lifecycle != "published":
            raise ValueError("only published extensions may be packaged")
        if self.signature.key_id != self.manifest.publisher_key.key_id:
            raise ValueError("extension signature key must match its manifest")
        names = [item.path for item in self.files]
        if len(names) != len(set(names)):
            raise ValueError("extension package paths must be unique")
        if _LOCK not in names or not any(name.startswith("wheels/") for name in names):
            raise ValueError("extension package requires a lock file and offline wheel")
        if self.content_sha256 != hashlib.sha256(self.signed_content).hexdigest():
            raise ValueError("extension package content digest does not match")
        return self

    @property
    def signed_content(self) -> bytes:
        value = {
            "schema_version": self.schema_version,
            "identity": self.identity.model_dump(mode="json"),
            "manifest": self.manifest.model_dump(mode="json"),
            "files": [item.model_dump(mode="json") for item in self.files],
        }
        return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")

    @classmethod
    def unsigned(
        cls,
        *,
        manifest: BridgeExtensionManifest,
        files: tuple[ExtensionPackageFile, ...],
        signature: ExtensionSignature,
    ) -> Self:
        """Construct a signed package envelope after a publisher signs the content."""
        seed = cls.model_construct(
            identity=manifest.metadata.identity,
            manifest=manifest,
            files=files,
            content_sha256="0" * 64,
            signature=signature,
        )
        return cls(
            identity=manifest.metadata.identity,
            manifest=manifest,
            files=files,
            content_sha256=hashlib.sha256(seed.signed_content).hexdigest(),
            signature=signature,
        )


class StagedExtension(Contract):
    state: Literal["staged"] = "staged"
    identity: AssetIdentity
    root: Text
    content_sha256: Sha256
    publisher_key_id: Symbol


def stage_extension_package(
    payload: bytes,
    extensions_root: Path,
    trust: ExtensionTrustPolicy,
    verifier: ExtensionSignatureVerifier,
    *,
    compatibility: ExtensionCompatibility | None = None,
) -> StagedExtension:
    """Verify every package boundary, then atomically expose inert files."""
    try:
        package = PortableExtensionPackage.model_validate_json(payload)
    except ValidationError:
        raise ValueError("invalid extension package") from None
    supported = compatibility or ExtensionCompatibility()
    if package.manifest.compatibility != supported:
        raise ValueError("extension package is incompatible with this Bridge")
    key = trust.trusted(package.signature.key_id)
    if not verifier.verify(
        public_key=key.raw,
        message=package.signed_content,
        signature=package.signature.raw,
    ):
        raise ValueError("extension package signature is invalid")
    root = Path(extensions_root)
    if not root.is_absolute():
        raise ValueError("extension staging root must be absolute")
    identity = package.identity
    target = root / identity.namespace / identity.name / identity.version
    if target.exists():
        raise ValueError("extension version already exists")
    target.parent.mkdir(parents=True, exist_ok=True)
    stage = target.with_name(f".part-{uuid4().hex[:8]}")
    try:
        for item in package.files:
            destination = stage / PurePosixPath(item.path)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(item.raw)
        (stage / "extension.json").write_text(
            package.manifest.model_dump_json(indent=2) + "\n", encoding="utf-8"
        )
        (stage / "package.json").write_bytes(payload)
        reloaded = PortableExtensionPackage.model_validate_json(
            (stage / "package.json").read_bytes()
        )
        if reloaded.content_sha256 != package.content_sha256:
            raise ValueError("staged extension package changed")
        for item in reloaded.files:
            written = stage / PurePosixPath(item.path)
            if hashlib.sha256(written.read_bytes()).hexdigest() != item.sha256:
                raise ValueError("staged extension file digest does not match")
        os.replace(stage, target)
    except (OSError, ValidationError, ValueError):
        if stage.exists():
            shutil.rmtree(stage)
        raise
    return StagedExtension(
        identity=identity,
        root=str(target.resolve()),
        content_sha256=package.content_sha256,
        publisher_key_id=key.key_id,
    )
