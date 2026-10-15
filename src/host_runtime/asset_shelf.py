"""Switch an installed Skill or Workflow off and on, or take it off this
computer, without losing it (owner 2026-10-15, Agent Web Capabilities).

The installed folders hold one manifest per file,
`assets/{skills,workflows}/{ns}__{name}__{version}.json`, and the host reads
only that folder's top level. A file set aside in its `disabled/` subfolder is
therefore not offered; installing a newer Skill already sets the older
versions aside there (`chat_authoring.install_skill`). Switching off uses the
same place, so both mean one thing.

Removing never deletes: the file moves to
`workspace/removed/<YYYY-MM-DD>/{skills,workflows}/` and a line is appended to
`workspace/removed/removed.jsonl` saying what, when, by whom and from where,
so the owner can put it back by moving the file. The manifests AEP ships are
refused: `aep-host export-assets`, run at install and upgrade, writes them
back, so a removal would not last. They can be switched off instead.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Literal

from agent.skills import SkillManifest
from common.assets import AssetIdentity, WorkflowManifest
from host_runtime.contracts import HostLayout
from host_runtime.platform_publish import ASSET_REFERENCE

ShelfKind = Literal["skill", "workflow"]
DISABLED = "disabled"
REMOVED = "removed"
JOURNAL = "removed.jsonl"


class ShelfError(Exception):
    """A switch or removal that cannot be done, with a code the page explains."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class Shelved:
    """Where a file went."""

    identity: AssetIdentity
    source: Path
    target: Path


def parse(kind: str, reference: str) -> tuple[ShelfKind, AssetIdentity]:
    if kind not in ("skill", "workflow"):
        raise ShelfError("kind_not_removable")
    match = ASSET_REFERENCE.match(reference.strip())
    if match is None:
        raise ShelfError("bad_reference")
    namespace, name, version = match.groups()
    return kind, AssetIdentity(namespace=namespace, name=name, version=version)  # type: ignore[return-value]


def _folder(layout: HostLayout, kind: ShelfKind) -> Path:
    return layout.skills if kind == "skill" else layout.workflows


def _file(identity: AssetIdentity) -> str:
    return f"{identity.namespace}__{identity.name}__{identity.version}.json"


@lru_cache(maxsize=1)
def shipped_keys() -> frozenset[tuple[str, str, str, str]]:
    """(kind, namespace, name, version) of every manifest AEP ships."""
    from host_runtime.assets import shipped

    return frozenset(
        ("skill" if isinstance(item, SkillManifest) else "workflow", *item.metadata.identity.key)
        for item in shipped()
    )


def is_shipped(kind: str, identity: AssetIdentity) -> bool:
    return (kind, *identity.key) in shipped_keys()


def disabled_assets(layout: HostLayout) -> list[dict[str, object]]:
    """What is switched off, as the Capabilities list shows it."""
    found: list[dict[str, object]] = []
    for kind, folder, model in (
        ("skill", layout.skills, SkillManifest),
        ("workflow", layout.workflows, WorkflowManifest),
    ):
        shelf = folder / DISABLED
        if not shelf.is_dir():
            continue
        for path in sorted(shelf.glob("*__*__*.json")):
            try:
                manifest = model.model_validate_json(path.read_text(encoding="utf-8-sig"))
            except (OSError, ValueError):
                continue
            identity = manifest.metadata.identity
            found.append(
                {
                    "kind": kind,
                    "namespace": identity.namespace,
                    "name": identity.name,
                    "version": identity.version,
                    "alias": getattr(manifest, "alias", ""),
                    "description": (
                        manifest.instructions
                        if isinstance(manifest, SkillManifest)
                        else manifest.description
                    ),
                    "shipped": is_shipped(kind, identity),
                }
            )
    return found


def switch_off(layout: HostLayout, kind: ShelfKind, identity: AssetIdentity) -> Shelved:
    folder = _folder(layout, kind)
    source = folder / _file(identity)
    if not source.is_file():
        raise ShelfError("not_installed")
    target = folder / DISABLED / _file(identity)
    if target.exists():
        raise ShelfError("disabled_copy_exists")
    target.parent.mkdir(parents=True, exist_ok=True)
    os.replace(source, target)
    return Shelved(identity, source, target)


def switch_on(layout: HostLayout, kind: ShelfKind, identity: AssetIdentity) -> Shelved:
    folder = _folder(layout, kind)
    source = folder / DISABLED / _file(identity)
    if not source.is_file():
        raise ShelfError("not_disabled")
    target = folder / _file(identity)
    if target.exists():
        raise ShelfError("already_installed")
    if kind == "skill":
        # The host registers every Skill in the folder and refuses to start
        # when two share an alias in one namespace; say so now instead.
        try:
            wanted = SkillManifest.model_validate_json(source.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            raise ShelfError("asset_unreadable") from None
        for path in folder.glob("*.json"):
            try:
                other = SkillManifest.model_validate_json(path.read_text(encoding="utf-8-sig"))
            except (OSError, ValueError):
                continue
            if (other.metadata.identity.namespace, other.alias) == (
                identity.namespace,
                wanted.alias,
            ):
                raise ShelfError("alias_in_use")
    os.replace(source, target)
    return Shelved(identity, source, target)


def remove(
    layout: HostLayout,
    kind: ShelfKind,
    identity: AssetIdentity,
    *,
    now: datetime,
    actor: str,
) -> Shelved:
    """Move the installed (or switched-off) file into today's removed folder."""
    if is_shipped(kind, identity):
        raise ShelfError("shipped_asset")
    folder = _folder(layout, kind)
    name = _file(identity)
    source = folder / name
    if not source.is_file():
        source = folder / DISABLED / name
        if not source.is_file():
            raise ShelfError("not_installed")
    bin_root = layout.workspace_root / REMOVED
    day = bin_root / now.strftime("%Y-%m-%d") / ("skills" if kind == "skill" else "workflows")
    target = day / name
    if target.exists():
        target = day / f"{Path(name).stem}.{now.strftime('%H%M%S%f')}.json"
    day.mkdir(parents=True, exist_ok=True)
    os.replace(source, target)
    record = {
        "at": now.isoformat(),
        "actor": actor,
        "kind": kind,
        "asset": f"{identity.namespace}/{identity.name}@{identity.version}",
        "from": str(source.relative_to(layout.workspace_root)),
        "to": str(target.relative_to(layout.workspace_root)),
    }
    with (bin_root / JOURNAL).open("a", encoding="utf-8") as journal:
        journal.write(json.dumps(record, ensure_ascii=False) + "\n")
    return Shelved(identity, source, target)
