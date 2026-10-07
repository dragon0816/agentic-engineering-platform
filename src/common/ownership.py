"""Who owns a Skill or Workflow name, who may publish its next version, and
what that version is.

Owner decisions of 2026-10-07 (`docs/phases/ASSET_OWNERSHIP.md`):

1. The first person or team to publish a name `(namespace, name)` owns it,
   and ownership can be transferred.
2. The owner names co-editors, who publish new versions directly. The owner
   deprecates versions and removes co-editors.
3. The platform assigns version numbers by increasing the highest existing
   one; the publisher chooses a patch, minor or major change. A version the
   publisher supplies must be higher than every existing one.

Published versions stay immutable, so a deprecation is recorded here, beside
the name, and never by rewriting a published package. Everything in this
module is a pure rule over contracts; the Registry applies it atomically.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Literal, Self

from pydantic import field_validator, model_validator

from common.assets import SEMVER, Owner, RegistryContract
from common.base import Slug, Symbol, Text
from common.identity import owns

VersionChange = Literal["patch", "minor", "major"]
FIRST_VERSION = "1.0.0"

_PrereleasePart = tuple[int, int, str]
VersionKey = tuple[int, int, int, int, tuple[_PrereleasePart, ...]]


def _semantic(value: str) -> str:
    if not SEMVER.fullmatch(value):
        raise ValueError("version must be a full semantic version")
    return value


def version_key(version: str) -> VersionKey:
    """Semantic-version precedence as a sortable key. Build metadata does not
    count, and a pre-release sorts below its release (SemVer 2.0.0 §11)."""
    match = SEMVER.fullmatch(version)
    if match is None:
        raise ValueError("version must be a full semantic version")
    major, minor, patch, prerelease = (
        int(match.group(1)), int(match.group(2)), int(match.group(3)), match.group(4)
    )
    if prerelease is None:
        return major, minor, patch, 1, ()
    parts = tuple(
        (0, int(part), "") if part.isdigit() else (1, 0, part) for part in prerelease.split(".")
    )
    return major, minor, patch, 0, parts


def highest_version(versions: Iterable[str]) -> str | None:
    existing = tuple(versions)
    return max(existing, key=version_key) if existing else None


def next_version(versions: Iterable[str], change: VersionChange) -> str:
    """The version the platform assigns: the highest existing one increased
    at the chosen level, or 1.0.0 for a name that has none."""
    highest = highest_version(versions)
    if highest is None:
        return FIRST_VERSION
    major, minor, patch, _, _ = version_key(highest)
    if change == "major":
        return f"{major + 1}.0.0"
    if change == "minor":
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"


def above_all(version: str, versions: Iterable[str]) -> bool:
    """Whether a supplied version is strictly higher than every existing one.
    Two versions that differ only in build metadata have equal precedence,
    so neither is above the other."""
    key = version_key(version)
    return all(key > version_key(existing) for existing in versions)


class VersionDeprecation(RegistryContract):
    """The owner's statement that one version should no longer be chosen.

    It mirrors `AssetMetadata.deprecation_reason` and `replacement`, but lives
    beside the name: the published package stays byte-for-byte what was
    published. Existing selections and installs keep working, for rollback."""

    version: Text
    reason: Text
    replacement: Text | None = None
    deprecated_by: Symbol

    @field_validator("version", "replacement")
    @classmethod
    def semantic_versions(cls, value: str | None) -> str | None:
        return value if value is None else _semantic(value)

    @model_validator(mode="after")
    def not_replaced_by_itself(self) -> Self:
        if self.replacement is not None and version_key(self.replacement) == version_key(
            self.version
        ):
            raise ValueError("a version cannot replace itself")
        return self


class AssetNameOwnership(RegistryContract):
    """Who is accountable for one Skill or Workflow name across its versions."""

    namespace: Slug
    name: Slug
    owner: Owner
    # Members (user actor ids) the owner lets publish new versions directly.
    co_editors: tuple[Symbol, ...] = ()
    deprecations: tuple[VersionDeprecation, ...] = ()

    @model_validator(mode="after")
    def coherent(self) -> Self:
        if len(set(self.co_editors)) != len(self.co_editors):
            raise ValueError("co-editors must be unique")
        if self.owner.type == "user" and self.owner.id in self.co_editors:
            raise ValueError("the owner is not also a co-editor")
        versions = [version_key(item.version) for item in self.deprecations]
        if len(set(versions)) != len(versions):
            raise ValueError("a version is deprecated once")
        return self

    @property
    def key(self) -> tuple[str, str]:
        return self.namespace, self.name

    def deprecation(self, version: str) -> VersionDeprecation | None:
        key = version_key(version)
        return next((item for item in self.deprecations if version_key(item.version) == key), None)

    def manages(self, actor: str, groups: tuple[str, ...]) -> bool:
        """The owner, or a member of an owning team, manages the name:
        co-editors, transfer and deprecation."""
        return owns(self.owner, actor, groups)

    def may_publish(self, actor: str, groups: tuple[str, ...]) -> bool:
        """The owner, a member of an owning team, or a named co-editor."""
        return self.manages(actor, groups) or actor in self.co_editors
