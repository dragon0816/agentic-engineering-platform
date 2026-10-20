"""The Host's memory registry: who may do what in which memory space
(docs/phases/ACCUMULATED_MEMORY.md §3.1, §3.4).

Built from the `memory_spaces` declarations of the manifests AEP ships (the
Host's own code, so they win for their identities) and of the Skills and
Workflows installed here, switched on or off (a switched-off Skill's space
stays; §3.6). Merge rules are data the managers ship. The Host itself
manages the personal spaces (`personal/preferences`, `personal/notes`;
accumulated memory M3), declared before any manifest.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from agent.skills import SkillManifest
from common.assets import WorkflowManifest
from common.memory import MergeRules, declarations_of, manager_conflicts
from host_runtime.contracts import HostLayout
from memory import personal
from memory.registry import MemoryRegistry, asset_key

DISABLED = "disabled"


def shipped_rules() -> tuple[MergeRules, ...]:
    """The merge rules of the spaces shipped managers own."""
    from capabilities.business_cards.space import MERGE_RULES

    return (MERGE_RULES, *personal.RULES)


def _installed(layout: HostLayout) -> list[SkillManifest | WorkflowManifest]:
    found: list[SkillManifest | WorkflowManifest] = []
    folders: tuple[tuple[Path, type[SkillManifest] | type[WorkflowManifest]], ...] = (
        (layout.skills, SkillManifest),
        (layout.skills / DISABLED, SkillManifest),
        (layout.workflows, WorkflowManifest),
        (layout.workflows / DISABLED, WorkflowManifest),
    )
    for folder, model in folders:
        if not folder.is_dir():
            continue
        for path in sorted(folder.glob("*__*__*.json")):
            try:
                found.append(model.model_validate_json(path.read_text(encoding="utf-8-sig")))
            except (OSError, ValueError):
                continue
    return found


def registry(layout: HostLayout) -> MemoryRegistry:
    """The memory registry of this Host."""
    from host_runtime.assets import shipped

    ours = list(shipped())
    known = {item.metadata.identity.key for item in ours}
    others = [item for item in _installed(layout) if item.metadata.identity.key not in known]
    return MemoryRegistry.from_manifests(
        [*ours, *others], rules=shipped_rules(), first=personal.HOST_DECLARED
    )


def conflicts(layout: HostLayout, candidate: SkillManifest | WorkflowManifest) -> tuple[str, ...]:
    """Spaces `candidate` would manage that another asset here (or shipped)
    already manages: a space has one manager, so the install is refused."""
    from host_runtime.assets import shipped

    declared = declarations_of(candidate)
    if not declared:
        return ()
    present: Iterable[SkillManifest | WorkflowManifest] = [*shipped(), *_installed(layout)]
    return manager_conflicts(
        [
            *personal.HOST_DECLARED,
            *((asset_key(item.metadata.identity), declarations_of(item)) for item in present),
        ],
        asset_key(candidate.metadata.identity),
        declared,
    )


def manager_states(layout: HostLayout) -> dict[str, str]:
    """`<namespace>/<name>` of every Skill or Workflow installed here that
    declares itself a space's manager, `on` or `off` (switched off): a space
    whose manager is neither (nor the Host) is an orphan (§3.6, the memory
    page). A Skill or Workflow installed here whose file declares no manager
    role (an older copy, written before its manifest declared its spaces) is
    `outdated`: installed, waiting for an update, not an orphan (live check
    2026-10-21)."""
    found: dict[str, str] = {}
    installed: set[str] = set()
    folders: tuple[tuple[Path, type[SkillManifest] | type[WorkflowManifest], str], ...] = (
        (layout.skills, SkillManifest, "on"),
        (layout.skills / DISABLED, SkillManifest, "off"),
        (layout.workflows, WorkflowManifest, "on"),
        (layout.workflows / DISABLED, WorkflowManifest, "off"),
    )
    for folder, model, state in folders:
        if not folder.is_dir():
            continue
        for path in sorted(folder.glob("*__*__*.json")):
            try:
                manifest = model.model_validate_json(path.read_text(encoding="utf-8-sig"))
            except (OSError, ValueError):
                continue
            namespace, name = asset_key(manifest.metadata.identity)
            installed.add(f"{namespace}/{name}")
            if any(item.role == "manager" for item in declarations_of(manifest)):
                if found.get(f"{namespace}/{name}") != "on":
                    found[f"{namespace}/{name}"] = state
    for key in installed - found.keys():
        found[key] = "outdated"
    return found
