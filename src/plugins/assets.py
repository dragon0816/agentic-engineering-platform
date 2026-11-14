"""A plugin's bundled Skills and Workflows, through the existing asset ledger.

Installation is `host_runtime.skill_packs.install`, unchanged: a file the
person changed is never overwritten, one they switched off stays off, one
they removed is not brought back, and an alias another Skill uses keeps the
new one off. A plugin owns a file only when the asset ledger shows AEP wrote
exactly its content and the file still holds it; removing a plugin removes
only such files. Bundled manifests are parsed as the real Skill/Workflow
contracts and stored as they are: a package cannot claim a business or
technical review, and installing one never records a review.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from agent.skills import SkillManifest
from common.assets import AssetIdentity, AssetMetadata, Review, WorkflowManifest
from common.plugins import PluginPackage
from host_runtime import skill_packs
from host_runtime.contracts import HostLayout
from plugins.ledger import OwnedAsset
from plugins.package import PluginStageError, owned_path


@dataclass(frozen=True)
class BundledAsset:
    kind: str
    manifest: SkillManifest | WorkflowManifest
    switched_on: bool

    @property
    def file(self) -> str:
        return file_name(self.manifest.metadata.identity)

    @property
    def key(self) -> tuple[str, str]:
        return self.kind, self.file


def file_name(identity: AssetIdentity) -> str:
    """The name `skill_packs` gives an installed manifest."""
    return f"{identity.namespace}__{identity.name}__{identity.version}.json"


def content(manifest: SkillManifest | WorkflowManifest) -> bytes:
    """The exact bytes `skill_packs.install_manifest` writes."""
    payload = json.dumps(manifest.model_dump(mode="json"), indent=2, ensure_ascii=False)
    return payload.encode("utf-8") + b"\n"


def _digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _unclaimed(review: Review) -> bool:
    return review.status == "pending" and review.reviewer is None and review.evidence is None


def _honest(metadata: AssetMetadata) -> bool:
    return _unclaimed(metadata.business_approval) and _unclaimed(metadata.technical_policy)


def parse_assets(package: PluginPackage) -> tuple[BundledAsset, ...]:
    """Every declared asset as its real contract, or `plugin_package_invalid`."""
    found: list[BundledAsset] = []
    for declared in package.manifest.assets:
        raw = package.file(declared.path).raw
        model = SkillManifest if declared.kind == "skill" else WorkflowManifest
        try:
            manifest = model.model_validate_json(raw)
        except (ValidationError, ValueError):
            raise PluginStageError("plugin_package_invalid") from None
        if manifest.metadata.identity != declared.identity or not _honest(manifest.metadata):
            raise PluginStageError("plugin_package_invalid")
        found.append(BundledAsset(declared.kind, manifest, declared.switched_on))
    return tuple(found)


def folders_problem(layout: HostLayout) -> str | None:
    """Whether a folder or file `skill_packs.install` writes is redirected away
    from the workspace (a link or junction on the way)."""
    anchor = layout.workspace_root
    for path in (
        layout.skills / skill_packs.DISABLED,
        layout.workflows / skill_packs.DISABLED,
        anchor / skill_packs.LEDGER,
        anchor / skill_packs.REPLACED,
    ):
        try:
            owned_path(anchor, path)
        except PluginStageError as error:
            return error.code
    return None


def _folder(layout: HostLayout, kind: str) -> Path:
    return layout.skills if kind == "skill" else layout.workflows


def locate(layout: HostLayout, kind: str, file: str) -> Path | None:
    folder = _folder(layout, kind)
    for path in (folder / file, folder / skill_packs.DISABLED / file):
        if path.is_file():
            return path
    return None


def expected(assets: Iterable[BundledAsset]) -> tuple[OwnedAsset, ...]:
    """What an install of `assets` may write, for interrupted-install recovery."""
    return tuple(
        OwnedAsset(
            kind="skill" if item.kind == "skill" else "workflow",
            identity=item.manifest.metadata.identity,
            file=item.file,
            sha256=_digest(content(item.manifest)),
            switched_on=item.switched_on,
        )
        for item in assets
    )


def install_assets(
    layout: HostLayout,
    assets: tuple[BundledAsset, ...],
    choices: Mapping[tuple[str, str], bool],
) -> tuple[OwnedAsset, ...]:
    """Install through `skill_packs`; return the files this plugin now owns.
    `choices` keeps an earlier on/off location of a file this plugin owned."""
    if not assets:
        return ()
    on = [item.manifest for item in assets if choices.get(item.key, item.switched_on)]
    off = [item.manifest for item in assets if not choices.get(item.key, item.switched_on)]
    skill_packs.install(layout, switched_on=on, switched_off=off)
    ledger = skill_packs.read_ledger(layout)
    owned: list[OwnedAsset] = []
    for item in expected(assets):
        path = locate(layout, item.kind, item.file)
        if path is None or ledger.get(f"{item.kind}/{item.file}") != item.sha256:
            continue
        if _digest(path.read_bytes()) != item.sha256:
            continue
        owned.append(
            item.model_copy(update={"switched_on": path.parent == _folder(layout, item.kind)})
        )
    return tuple(owned)


def present(layout: HostLayout, owned: Iterable[OwnedAsset]) -> set[tuple[str, str]]:
    """Keys of owned files that are on disk now (on or off)."""
    return {item.key for item in owned if locate(layout, item.kind, item.file) is not None}


def restore_places(layout: HostLayout, owned: Iterable[OwnedAsset]) -> None:
    """Put owned, unchanged files back where the ledger last recorded them (on
    or off): an interrupted or failed update may have set an older version
    aside. A changed file, or a place already taken, is left as it is."""
    for item in owned:
        path = locate(layout, item.kind, item.file)
        if path is None:
            continue
        folder = _folder(layout, item.kind)
        place = (
            folder / item.file if item.switched_on else folder / skill_packs.DISABLED / item.file
        )
        if path == place or place.exists():
            continue
        try:
            owned_path(layout.workspace_root, path)
            owned_path(layout.workspace_root, place)
            if _digest(path.read_bytes()) != item.sha256:
                continue
            place.parent.mkdir(parents=True, exist_ok=True)
            path.replace(place)
        except (OSError, PluginStageError):
            continue


def planned_removal(layout: HostLayout, owned: Iterable[OwnedAsset]) -> tuple[OwnedAsset, ...]:
    """What `remove_owned` would return now, without removing anything: the
    ledger records it before the files go."""
    planned: list[OwnedAsset] = []
    for item in owned:
        path = locate(layout, item.kind, item.file)
        if path is None:
            planned.append(item)
            continue
        try:
            owned_path(layout.workspace_root, path)
            if _digest(path.read_bytes()) != item.sha256:
                continue
        except (OSError, PluginStageError):
            continue
        on = path.parent == _folder(layout, item.kind)
        planned.append(item.model_copy(update={"switched_on": on}))
    return tuple(planned)


def remove_owned(layout: HostLayout, owned: Iterable[OwnedAsset]) -> tuple[OwnedAsset, ...]:
    """Remove files still exactly as this plugin wrote them; return them with
    where they were (on or off). A changed file is left and no longer owned."""
    removed: list[OwnedAsset] = []
    for item in owned:
        path = locate(layout, item.kind, item.file)
        if path is None:
            removed.append(item)  # already gone; keep the last known choice
            continue
        try:
            owned_path(layout.workspace_root, path)
            if _digest(path.read_bytes()) != item.sha256:
                continue
            on = path.parent == _folder(layout, item.kind)
            path.unlink()
        except (OSError, PluginStageError):
            continue
        removed.append(item.model_copy(update={"switched_on": on}))
    return tuple(removed)
