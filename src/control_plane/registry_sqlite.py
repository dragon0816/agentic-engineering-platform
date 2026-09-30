"""Small durable shared catalog for published packages and their bytes.

This is Registry storage only. It does not store Bridge runs, member sessions,
device authorization or execution grants, and it never executes an artifact.
"""

from __future__ import annotations

import hashlib
import sqlite3
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Literal

from pydantic import TypeAdapter, ValidationError

from common.assets import AssetIdentity
from common.base import Symbol
from common.distribution import InstallationPlan, PublishedAssetPackage
from control_plane.distribution import ControlError

SCHEMA_VERSION = "1"
RegistryStoreErrorCode = Literal["unsupported_schema", "corrupt_record", "storage_unavailable"]


class RegistryStoreError(Exception):
    def __init__(self, code: RegistryStoreErrorCode) -> None:
        self.code: RegistryStoreErrorCode = code
        super().__init__(code)


class SqliteArtifactStore(Mapping[str, bytes]):
    """Read-only artifact mapping used by the existing control-plane service."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=5.0)
        connection.execute("PRAGMA busy_timeout = 5000")
        return connection

    def __getitem__(self, reference: str) -> bytes:
        try:
            with self._connect() as connection:
                row = connection.execute(
                    "SELECT content FROM artifacts WHERE reference = ?", (reference,)
                ).fetchone()
        except sqlite3.DatabaseError as error:
            raise RegistryStoreError("storage_unavailable") from error
        if row is None:
            raise KeyError(reference)
        return bytes(row[0])

    def __iter__(self) -> Iterator[str]:
        try:
            with self._connect() as connection:
                rows = connection.execute(
                    "SELECT reference FROM artifacts ORDER BY reference"
                ).fetchall()
        except sqlite3.DatabaseError as error:
            raise RegistryStoreError("storage_unavailable") from error
        return iter(tuple(row[0] for row in rows))

    def __len__(self) -> int:
        try:
            with self._connect() as connection:
                row = connection.execute("SELECT COUNT(*) FROM artifacts").fetchone()
        except sqlite3.DatabaseError as error:
            raise RegistryStoreError("storage_unavailable") from error
        return int(row[0]) if row is not None else 0


class SqliteRegistry:
    """Durable PackageRegistry with artifact bytes in the same SQLite file."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self._connect() as connection:
                connection.execute(
                    "CREATE TABLE IF NOT EXISTS registry_meta "
                    "(key TEXT PRIMARY KEY, value TEXT NOT NULL)"
                )
                row = connection.execute(
                    "SELECT value FROM registry_meta WHERE key = 'schema_version'"
                ).fetchone()
                if row is None:
                    connection.execute(
                        "INSERT INTO registry_meta (key, value) VALUES ('schema_version', ?)",
                        (SCHEMA_VERSION,),
                    )
                elif row[0] != SCHEMA_VERSION:
                    raise RegistryStoreError("unsupported_schema")
                connection.execute(
                    "CREATE TABLE IF NOT EXISTS packages ("
                    "namespace TEXT NOT NULL, name TEXT NOT NULL, version TEXT NOT NULL, "
                    "payload TEXT NOT NULL, PRIMARY KEY(namespace, name, version))"
                )
                connection.execute(
                    "CREATE TABLE IF NOT EXISTS artifacts ("
                    "reference TEXT PRIMARY KEY, content BLOB NOT NULL)"
                )
        except RegistryStoreError:
            raise
        except sqlite3.DatabaseError as error:
            raise RegistryStoreError("storage_unavailable") from error
        self.artifacts = SqliteArtifactStore(self.path)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=5.0)
        connection.execute("PRAGMA busy_timeout = 5000")
        return connection

    @staticmethod
    def _package(payload: str) -> PublishedAssetPackage:
        try:
            return PublishedAssetPackage.model_validate_json(payload)
        except (ValidationError, ValueError, TypeError) as error:
            raise RegistryStoreError("corrupt_record") from error

    def publish(
        self, package: PublishedAssetPackage, *, artifact: bytes | None = None
    ) -> PublishedAssetPackage:
        item = PublishedAssetPackage.model_validate(package)
        described = item.metadata.package
        if described is None:  # defensive; the package contract already requires it
            raise ControlError("artifact_missing")
        if artifact is not None and hashlib.sha256(artifact).hexdigest() != described.sha256:
            raise ControlError("artifact_hash_mismatch")
        identity = item.metadata.identity
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                try:
                    connection.execute(
                        "INSERT INTO packages(namespace, name, version, payload) "
                        "VALUES (?, ?, ?, ?)",
                        (*identity.key, item.model_dump_json()),
                    )
                except sqlite3.IntegrityError:
                    raise ControlError("duplicate_package") from None
                if artifact is not None:
                    saved = connection.execute(
                        "SELECT content FROM artifacts WHERE reference = ?",
                        (described.artifact_ref,),
                    ).fetchone()
                    if saved is not None and bytes(saved[0]) != artifact:
                        raise ControlError("artifact_hash_mismatch")
                    connection.execute(
                        "INSERT OR IGNORE INTO artifacts(reference, content) VALUES (?, ?)",
                        (described.artifact_ref, artifact),
                    )
        except ControlError:
            raise
        except sqlite3.DatabaseError as error:
            raise RegistryStoreError("storage_unavailable") from error
        return item.model_copy(deep=True)

    def discover(self, *, namespace: str | None = None) -> tuple[PublishedAssetPackage, ...]:
        try:
            with self._connect() as connection:
                if namespace is None:
                    rows = connection.execute(
                        "SELECT payload FROM packages ORDER BY namespace, name, version"
                    ).fetchall()
                else:
                    checked = TypeAdapter(Symbol).validate_python(namespace)
                    rows = connection.execute(
                        "SELECT payload FROM packages WHERE namespace = ? "
                        "ORDER BY namespace, name, version",
                        (checked,),
                    ).fetchall()
        except sqlite3.DatabaseError as error:
            raise RegistryStoreError("storage_unavailable") from error
        return tuple(self._package(row[0]) for row in rows)

    def get(self, identity: AssetIdentity) -> PublishedAssetPackage | None:
        key = AssetIdentity.model_validate(identity).key
        try:
            with self._connect() as connection:
                row = connection.execute(
                    "SELECT payload FROM packages WHERE namespace = ? AND name = ? AND version = ?",
                    key,
                ).fetchone()
        except sqlite3.DatabaseError as error:
            raise RegistryStoreError("storage_unavailable") from error
        return None if row is None else self._package(row[0])

    def plan(
        self,
        *,
        actor: Symbol,
        bridge_id: Symbol,
        requested: tuple[AssetIdentity, ...],
    ) -> InstallationPlan:
        packages: list[PublishedAssetPackage] = []
        for requested_identity in requested:
            found = self.get(requested_identity)
            if found is None:
                raise ControlError("package_missing")
            packages.append(found)
        return InstallationPlan(actor=actor, bridge_id=bridge_id, packages=tuple(packages))
