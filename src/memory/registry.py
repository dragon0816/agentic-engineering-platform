"""Which asset may do what in which memory space (docs/phases/ACCUMULATED_MEMORY.md §3.4).

Built by the Host from the `memory_spaces` declarations of the Skills and
Workflows it has, plus the merge rules the managers ship as data. An asset is
known by namespace and name: every version of a Skill keeps the same access.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from common.assets import AssetIdentity
from common.memory import (
    MemoryRole,
    MemorySpaceDeclaration,
    MergeRules,
    declarations_of,
    manager_conflicts,
)

AssetKey = tuple[str, str]


def asset_key(asset: AssetIdentity | AssetKey) -> AssetKey:
    if isinstance(asset, AssetIdentity):
        return asset.namespace, asset.name
    return asset


def asset_label(asset: AssetIdentity | AssetKey) -> str:
    namespace, name = asset_key(asset)
    return f"{namespace}/{name}"


class MemoryRegistryError(ValueError):
    """A declaration the registry cannot take, by code."""

    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        super().__init__(f"{code}: {detail}" if detail else code)


@dataclass(frozen=True)
class _Managed:
    manager: AssetKey
    declaration: MemorySpaceDeclaration


class MemoryRegistry:
    """Declarations by space and asset, and the managers' merge rules."""

    def __init__(self) -> None:
        self._roles: dict[str, dict[AssetKey, MemoryRole]] = {}
        self._managed: dict[str, _Managed] = {}
        self._rules: dict[str, MergeRules] = {}

    def declare(
        self, asset: AssetIdentity | AssetKey, declarations: Iterable[MemorySpaceDeclaration]
    ) -> None:
        """One asset's declarations. A space has one manager: a second asset
        declaring itself manager is refused (`memory_space_has_a_manager`)."""
        key = asset_key(asset)
        items = tuple(declarations)
        installed = [(item.manager, (item.declaration,)) for item in self._managed.values()]
        taken = manager_conflicts(installed, key, items)
        if taken:
            raise MemoryRegistryError("memory_space_has_a_manager", ", ".join(taken))
        for item in items:
            roles = self._roles.setdefault(item.space, {})
            held = roles.get(key)
            if held is None or item.allows(held):
                roles[key] = item.role
            if item.role == "manager":
                self._managed[item.space] = _Managed(manager=key, declaration=item)

    def provide_rules(self, rules: MergeRules) -> None:
        """Merge rules a manager ships as data, by their id."""
        self._rules[rules.rules_id] = rules

    def role(self, space: str, asset: AssetIdentity | AssetKey) -> MemoryRole | None:
        return self._roles.get(space, {}).get(asset_key(asset))

    def managed(self) -> tuple[tuple[AssetKey, MemorySpaceDeclaration, MergeRules | None], ...]:
        """Every managed space, its manager, its declaration and its rules
        (None while the manager shipped none under the declared id)."""
        return tuple(
            (item.manager, item.declaration, self._rules.get(item.declaration.merge_rules or ""))
            for item in self._managed.values()
        )

    @classmethod
    def from_manifests(
        cls,
        manifests: Iterable[object],
        *,
        rules: Iterable[MergeRules] = (),
        first: Iterable[tuple[AssetKey, Iterable[MemorySpaceDeclaration]]] = (),
    ) -> MemoryRegistry:
        """A registry from Skill and Workflow manifests. A manifest whose
        declarations conflict with one taken earlier is left out: its asset
        then reaches no memory, and the earlier manager keeps the space.
        `first` is declared before any manifest (the Host's own spaces)."""
        registry = cls()
        for item in rules:
            registry.provide_rules(item)
        for asset, declared in first:
            registry.declare(asset, declared)
        for manifest in manifests:
            declared = declarations_of(manifest)
            if not declared:
                continue
            identity = getattr(getattr(manifest, "metadata", None), "identity", None)
            if not isinstance(identity, AssetIdentity):
                continue
            try:
                registry.declare(identity, declared)
            except MemoryRegistryError:
                continue
        return registry
