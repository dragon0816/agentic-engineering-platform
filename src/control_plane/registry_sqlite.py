"""Small durable shared catalog for published packages and their bytes.

This is Registry storage only. It does not store Bridge runs, member sessions,
device authorization or execution grants, and it never executes an artifact.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Literal

from pydantic import TypeAdapter, ValidationError

from common.assets import AssetIdentity, Owner
from common.base import Symbol
from common.distribution import InstallationPlan, PublishedAssetPackage
from common.ownership import AssetNameOwnership, VersionChange, version_key
from control_plane.distribution import (
    ControlError,
    admit_member_version,
    admit_trusted_version,
)

# The name-ownership table (2026-10-07) is additive: a database written by
# this version still opens under the previous code, which ignores the table,
# and a name the previous code published is given its record the next time
# this code opens the database or publishes that name.
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
                connection.execute(
                    "CREATE TABLE IF NOT EXISTS name_owners ("
                    "namespace TEXT NOT NULL, name TEXT NOT NULL, payload TEXT NOT NULL, "
                    "PRIMARY KEY(namespace, name))"
                )
                unowned = connection.execute(
                    "SELECT DISTINCT p.namespace, p.name FROM packages p "
                    "LEFT JOIN name_owners o ON o.namespace = p.namespace AND o.name = p.name "
                    "WHERE o.namespace IS NULL ORDER BY p.namespace, p.name"
                ).fetchall()
                for namespace, name in unowned:
                    self._ensure_record(connection, namespace, name)
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
    def _versions(connection: sqlite3.Connection, namespace: str, name: str) -> tuple[str, ...]:
        rows = connection.execute(
            "SELECT version FROM packages WHERE namespace = ? AND name = ?", (namespace, name)
        ).fetchall()
        return tuple(row[0] for row in rows)

    @staticmethod
    def _ensure_record(
        connection: sqlite3.Connection, namespace: str, name: str
    ) -> AssetNameOwnership | None:
        """The name's record, deriving and storing it from the owner its
        earliest version declares when the name was published before records
        existed. None only for a name with no versions."""
        row = connection.execute(
            "SELECT payload FROM name_owners WHERE namespace = ? AND name = ?", (namespace, name)
        ).fetchone()
        if row is not None:
            try:
                return AssetNameOwnership.model_validate_json(row[0])
            except (ValidationError, ValueError, TypeError) as error:
                raise RegistryStoreError("corrupt_record") from error
        rows = connection.execute(
            "SELECT version, payload FROM packages WHERE namespace = ? AND name = ?",
            (namespace, name),
        ).fetchall()
        if not rows:
            return None
        try:
            _, earliest = min(rows, key=lambda entry: version_key(entry[0]))
            owner = Owner.model_validate(json.loads(earliest)["metadata"]["owner"])
            record = AssetNameOwnership(namespace=namespace, name=name, owner=owner)
        except (ValidationError, ValueError, TypeError, KeyError) as error:
            raise RegistryStoreError("corrupt_record") from error
        connection.execute(
            "INSERT INTO name_owners(namespace, name, payload) VALUES (?, ?, ?)",
            (namespace, name, record.model_dump_json()),
        )
        return record

    @staticmethod
    def _package(payload: str) -> PublishedAssetPackage:
        try:
            return PublishedAssetPackage.model_validate_json(payload)
        except (ValidationError, ValueError, TypeError) as error:
            raise RegistryStoreError("corrupt_record") from error

    def publish(
        self, package: PublishedAssetPackage, *, artifact: bytes | None = None
    ) -> PublishedAssetPackage:
        """The platform's own publish (preview seed, migration); see
        `admit_trusted_version`."""
        return self._publish(package, artifact=artifact, admit=None)

    def publish_as(
        self,
        package: PublishedAssetPackage,
        *,
        publisher: Symbol,
        groups: tuple[str, ...],
        change: VersionChange | None = None,
        artifact: bytes | None = None,
    ) -> PublishedAssetPackage:
        """A member publishes a version under the ownership rules; see
        `admit_member_version`. The rule is applied inside the same
        transaction as the insert, so two publishers cannot both pass it."""
        member = TypeAdapter(Symbol).validate_python(publisher)
        return self._publish(
            package, artifact=artifact, admit=(member, tuple(groups), change)
        )

    def _publish(
        self,
        package: PublishedAssetPackage,
        *,
        artifact: bytes | None,
        admit: tuple[str, tuple[str, ...], VersionChange | None] | None,
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
                current = self._ensure_record(connection, identity.namespace, identity.name)
                if admit is None:
                    if identity.version in self._versions(
                        connection, identity.namespace, identity.name
                    ):
                        raise ControlError("duplicate_package")
                    record = admit_trusted_version(item, current)
                else:
                    publisher, groups, change = admit
                    record = admit_member_version(
                        item,
                        current,
                        self._versions(connection, identity.namespace, identity.name),
                        publisher=publisher,
                        groups=groups,
                        change=change,
                    )
                if current is None:
                    connection.execute(
                        "INSERT INTO name_owners(namespace, name, payload) VALUES (?, ?, ?)",
                        (identity.namespace, identity.name, record.model_dump_json()),
                    )
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

    def ownership(self, namespace: str, name: str) -> AssetNameOwnership | None:
        try:
            with self._connect() as connection:
                row = connection.execute(
                    "SELECT payload FROM name_owners WHERE namespace = ? AND name = ?",
                    (namespace, name),
                ).fetchone()
        except sqlite3.DatabaseError as error:
            raise RegistryStoreError("storage_unavailable") from error
        if row is None:
            return None
        try:
            return AssetNameOwnership.model_validate_json(row[0])
        except (ValidationError, ValueError, TypeError) as error:
            raise RegistryStoreError("corrupt_record") from error

    def save_ownership(
        self, updated: AssetNameOwnership, *, previous: AssetNameOwnership
    ) -> AssetNameOwnership:
        """Replace a name's record only if it is still the one the change was
        decided against, so two concurrent owner actions cannot lose one."""
        item = AssetNameOwnership.model_validate(updated)
        before = AssetNameOwnership.model_validate(previous)
        if item.key != before.key:
            raise ControlError("ownership_changed")
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                current = self._ensure_record(connection, *item.key)
                if current is None:
                    raise ControlError("name_missing")
                if current != before:
                    raise ControlError("ownership_changed")
                connection.execute(
                    "UPDATE name_owners SET payload = ? WHERE namespace = ? AND name = ?",
                    (item.model_dump_json(), *item.key),
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
