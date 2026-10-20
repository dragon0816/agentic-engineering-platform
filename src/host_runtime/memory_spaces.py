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

import threading
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from functools import cache

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


#: Where installed Skills and Workflows are, and whether one there is `on`
#: or `off` (switched off).
_FOLDERS: tuple[tuple[str, str, type[SkillManifest] | type[WorkflowManifest], str], ...] = (
    ("skills", "", SkillManifest, "on"),
    ("skills", DISABLED, SkillManifest, "off"),
    ("workflows", "", WorkflowManifest, "on"),
    ("workflows", DISABLED, WorkflowManifest, "off"),
)
#: One parsed manifest per file, kept while the file's size and modification
#: time stay the same (live check B3, 2026-10-21: the memory page parsed every
#: installed manifest several times per call; `docs/DECISIONS.md`).
_PARSED: dict[str, tuple[tuple[int, int], SkillManifest | WorkflowManifest | None]] = {}
#: The registry built from one set of installed files, by their signature.
_REGISTRIES: dict[str, tuple[tuple[object, ...], MemoryRegistry]] = {}
_LOCK = threading.Lock()
#: A bound on both caches (a test run makes many workspaces).
_MAX_KEPT = 2000


@cache
def _shipped() -> tuple[SkillManifest | WorkflowManifest, ...]:
    """The manifests AEP ships: code, so built once per process."""
    from host_runtime.assets import shipped

    return tuple(shipped())


_Scan = tuple[tuple[tuple[object, ...], ...], list[tuple["SkillManifest | WorkflowManifest", str]]]
#: The scan a thread reuses inside `one_scan()`, by workspace.
_SCANS = threading.local()


@contextmanager
def one_scan(layout: HostLayout) -> Iterator[None]:
    """Inside the block, this thread looks at the installed Skill and
    Workflow files once (one Agent Web request: the memory page builds the
    registry and the managers' states several times)."""
    held: dict[str, _Scan] | None = getattr(_SCANS, "held", None)
    if held is None:
        held = {}
        _SCANS.held = held
    root = str(layout.workspace_root)
    if root in held:
        yield
        return
    held[root] = _scan(layout)
    try:
        yield
    finally:
        held.pop(root, None)


def _installed_files(layout: HostLayout) -> _Scan:
    held: dict[str, _Scan] | None = getattr(_SCANS, "held", None)
    if held:
        found = held.get(str(layout.workspace_root))
        if found is not None:
            return found
    return _scan(layout)


def _scan(layout: HostLayout) -> _Scan:
    """Every installed Skill and Workflow file with its state (`on`/`off`),
    and the files' signature (name, size, modification time). A file is parsed
    again only when its size or modification time changed; an unreadable or
    invalid file is left out, as before."""
    signature: list[tuple[object, ...]] = []
    found: list[tuple[SkillManifest | WorkflowManifest, str]] = []
    for kind, sub, model, state in _FOLDERS:
        base = getattr(layout, kind)
        folder = base / sub if sub else base
        if not folder.is_dir():
            continue
        for path in sorted(folder.glob("*__*__*.json")):
            try:
                info = path.stat()
            except OSError:
                continue
            stamp = (info.st_size, info.st_mtime_ns)
            signature.append((str(path), *stamp))
            key = f"{model.__name__}:{path}"
            with _LOCK:
                held = _PARSED.get(key)
            if held is not None and held[0] == stamp:
                manifest = held[1]
            else:
                try:
                    manifest = model.model_validate_json(path.read_text(encoding="utf-8-sig"))
                except (OSError, ValueError):
                    manifest = None
                with _LOCK:
                    if len(_PARSED) >= _MAX_KEPT:
                        _PARSED.clear()
                    _PARSED[key] = (stamp, manifest)
            if manifest is not None:
                found.append((manifest, state))
    return tuple(signature), found


def _installed(layout: HostLayout) -> list[SkillManifest | WorkflowManifest]:
    return [manifest for manifest, _ in _installed_files(layout)[1]]


def registry(layout: HostLayout) -> MemoryRegistry:
    """The memory registry of this Host: built again only when an installed
    Skill or Workflow file changed (the shipped ones are code)."""
    signature, installed = _installed_files(layout)
    root = str(layout.workspace_root)
    with _LOCK:
        held = _REGISTRIES.get(root)
    if held is not None and held[0] == signature:
        return held[1]
    ours = list(_shipped())
    known = {item.metadata.identity.key for item in ours}
    others = [item for item, _ in installed if item.metadata.identity.key not in known]
    built = MemoryRegistry.from_manifests(
        [*ours, *others], rules=shipped_rules(), first=personal.HOST_DECLARED
    )
    with _LOCK:
        if len(_REGISTRIES) >= _MAX_KEPT:
            _REGISTRIES.clear()
        _REGISTRIES[root] = (signature, built)
    return built


def conflicts(layout: HostLayout, candidate: SkillManifest | WorkflowManifest) -> tuple[str, ...]:
    """Spaces `candidate` would manage that another asset here (or shipped)
    already manages: a space has one manager, so the install is refused."""
    declared = declarations_of(candidate)
    if not declared:
        return ()
    present: Iterable[SkillManifest | WorkflowManifest] = [*_shipped(), *_installed(layout)]
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
    for manifest, state in _installed_files(layout)[1]:
        namespace, name = asset_key(manifest.metadata.identity)
        installed.add(f"{namespace}/{name}")
        if any(item.role == "manager" for item in declarations_of(manifest)):
            if found.get(f"{namespace}/{name}") != "on":
                found[f"{namespace}/{name}"] = state
    for key in installed - found.keys():
        found[key] = "outdated"
    return found
