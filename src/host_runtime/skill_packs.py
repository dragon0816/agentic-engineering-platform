"""Skills and Workflows that come with the Windows bundle, installed without
overwriting anyone's choices (owner 2026-10-15/16,
`docs/phases/HERMES_SKILL_PACK.md`).

Two kinds arrive with a bundle:

- AEP's in-use Skills and the Workflows they call (the shipped manifests and
  the bundle's `aep-skills/`), installed **switched on**;
- skill packs (the Hermes skill pack, `hermes/manifests/`), installed
  **switched off**, in `assets/skills/disabled/`, with their coding-agent
  folders (`hermes/agent/<folder>`) in AEP's own store,
  `workspace/agent-skills/`.

Rules, the same on a first install and on every update:

- a manifest whose exact identity is already here, switched on or off, is
  left as it is: never overwritten, never switched on again;
- one the person removed (`workspace/removed/removed.jsonl`) is not brought
  back;
- a Skill meant to be on stays off when the person switched an earlier
  version of it off, or when a newer version is already here; a newer Skill
  that goes on sets its older versions aside in `disabled/`, as installing a
  Skill always does; a Skill whose alias another switched-on Skill of its
  namespace already uses goes in switched off.

The coding-agent copy of a pack skill goes into Claude Code's and Copilot's
skills folders only while its Skill is switched on
(`host_runtime.agent_setup.link_pack_skill`), and comes out when it is
switched off or removed.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from agent.skills import SkillManifest
from common.assets import AssetIdentity, WorkflowManifest
from host_runtime import agent_setup
from host_runtime.contracts import HostLayout
from host_runtime.workspace import write_atomically

Kind = Literal["skill", "workflow"]
STORE = "agent-skills"
DISABLED = "disabled"
REMOVED_JOURNAL = Path("removed") / "removed.jsonl"
#: Where a bundle keeps what this module installs.
BUNDLE_IN_USE = "aep-skills"
BUNDLE_PACK = "hermes"
_ASSET = re.compile(r"^([a-z0-9-]+)/([a-z0-9-]+)@(.+)$")


@dataclass
class Report:
    """What an installation did, for the installer's output."""

    switched_on: list[str] = field(default_factory=list)
    switched_off: list[str] = field(default_factory=list)
    kept: list[str] = field(default_factory=list)
    lines: list[str] = field(default_factory=list)

    def summary(self) -> list[str]:
        return [
            f"Skills and Workflows installed switched on: {len(self.switched_on)}",
            f"Installed switched off (switch on in Agent Web > Capabilities): "
            f"{len(self.switched_off)}",
            f"Already here, left as they are: {len(self.kept)}",
            *self.lines,
        ]


def store_dir(layout: HostLayout) -> Path:
    return layout.workspace_root / STORE


def agent_folder_name(identity: AssetIdentity) -> str:
    """The coding-agent folder of a pack Skill: `<namespace>-<name>`."""
    return f"{identity.namespace}-{identity.name}"


def _file(identity: AssetIdentity) -> str:
    return f"{identity.namespace}__{identity.name}__{identity.version}.json"


def _label(identity: AssetIdentity) -> str:
    return f"{identity.namespace}/{identity.name}@{identity.version}"


def _version(identity: AssetIdentity) -> tuple[int, int, int]:
    core = identity.version.split("-", 1)[0].split("+", 1)[0]
    major, minor, patch = (int(part) for part in core.split("."))
    return major, minor, patch


def removed_by_person(layout: HostLayout) -> set[tuple[str, str]]:
    """(kind, namespace/name@version) of everything the person removed."""
    journal = layout.workspace_root / REMOVED_JOURNAL
    found: set[tuple[str, str]] = set()
    if not journal.is_file():
        return found
    for line in journal.read_text(encoding="utf-8").splitlines():
        try:
            record = json.loads(line)
        except ValueError:
            continue
        if isinstance(record, dict) and isinstance(record.get("asset"), str):
            found.add((str(record.get("kind")), record["asset"]))
    return found


def _versions_here(folder: Path, identity: AssetIdentity) -> tuple[list[Path], list[Path]]:
    pattern = f"{identity.namespace}__{identity.name}__*.json"
    return sorted(folder.glob(pattern)), sorted((folder / DISABLED).glob(pattern))


def _identity_of(path: Path) -> AssetIdentity | None:
    parts = path.stem.split("__")
    if len(parts) != 3:
        return None
    try:
        return AssetIdentity(namespace=parts[0], name=parts[1], version=parts[2])
    except ValueError:
        return None


def _alias_taken(folder: Path, manifest: SkillManifest) -> str | None:
    identity = manifest.metadata.identity
    for path in folder.glob(f"{identity.namespace}__*.json"):
        try:
            other = SkillManifest.model_validate_json(path.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            continue
        if other.metadata.identity.name != identity.name and other.alias == manifest.alias:
            return _label(other.metadata.identity)
    return None


def install_manifest(
    layout: HostLayout,
    manifest: SkillManifest | WorkflowManifest,
    *,
    enabled: bool,
    removed: set[tuple[str, str]],
    report: Report,
) -> None:
    kind: Kind = "skill" if isinstance(manifest, SkillManifest) else "workflow"
    folder = layout.skills if kind == "skill" else layout.workflows
    identity = manifest.metadata.identity
    name = _file(identity)
    label = f"{kind} {_label(identity)}"
    if (folder / name).exists() or (folder / DISABLED / name).exists():
        report.kept.append(label)
        return
    if (kind, _label(identity)) in removed:
        report.kept.append(label)
        report.lines.append(f"  not brought back (you removed it): {label}")
        return
    on = enabled
    active, shelved = _versions_here(folder, identity)
    if on and kind == "skill":
        here = [i for i in map(_identity_of, active + shelved) if i is not None]
        newer = [i for i in here if _version(i) > _version(identity)]
        if newer:
            on = False
            report.lines.append(f"  {label}: a newer version is here, so this one is kept off")
        elif shelved and not active:
            on = False
            report.lines.append(
                f"  {label}: you switched an earlier version off, so this one stays off"
            )
    if on and isinstance(manifest, SkillManifest):
        older = [p for p in active if p.name != name]
        taken = _alias_taken(folder, manifest)
        if taken is not None:
            on = False
            report.lines.append(f"  {label}: its alias is used by {taken}, so it is kept off")
        else:
            for path in older:
                (folder / DISABLED).mkdir(parents=True, exist_ok=True)
                path.replace(folder / DISABLED / path.name)
                older_identity = _identity_of(path)
                older_label = f"{kind} {_label(older_identity)}" if older_identity else ""
                if older_label in report.switched_on:
                    report.switched_on.remove(older_label)
                    report.switched_off.append(older_label)
                report.lines.append(f"  set aside the older {path.stem} in disabled")
    target = folder / name if on else folder / DISABLED / name
    payload = json.dumps(manifest.model_dump(mode="json"), indent=2, ensure_ascii=False)
    write_atomically(target, payload.encode("utf-8") + b"\n")
    (report.switched_on if on else report.switched_off).append(label)


def _load(path: Path) -> SkillManifest | WorkflowManifest:
    text = path.read_text(encoding="utf-8-sig")
    data = json.loads(text)
    if isinstance(data, dict) and "steps" in data:
        return WorkflowManifest.model_validate(data)
    return SkillManifest.model_validate(data)


def manifests_in(directory: Path) -> list[SkillManifest | WorkflowManifest]:
    """Every manifest under `directory` (flat, or in skills/ and workflows/)."""
    found: list[SkillManifest | WorkflowManifest] = []
    if directory.is_dir():
        for path in sorted(directory.rglob("*.json")):
            if "__" in path.name:
                found.append(_load(path))
    return found


def tree_version(folder: Path) -> str:
    """A digest of a skill folder's files, so an update replaces exactly the
    copies that changed."""
    digest = hashlib.sha256()
    for path in sorted(folder.rglob("*")):
        if path.is_file() and path.name != agent_setup.MARKER_FILE:
            digest.update(path.relative_to(folder).as_posix().encode("utf-8") + b"\0")
            digest.update(path.read_bytes() + b"\0")
    return digest.hexdigest()[:16]


def install_agent_store(layout: HostLayout, source: Path, *, pack: str, report: Report) -> None:
    """Copy a pack's coding-agent folders into AEP's store. The store is
    AEP's own, so a changed folder is replaced."""
    if not source.is_dir():
        return
    store = store_dir(layout)
    changed = 0
    for folder in sorted(p for p in source.iterdir() if p.is_dir()):
        version = tree_version(folder)
        target = store / folder.name
        marker = target / agent_setup.MARKER_FILE
        if marker.is_file():
            try:
                present = json.loads(marker.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                present = {}
            if present.get("version") == version:
                continue
            if present.get("pack") not in (None, pack):
                # Another pack's folder of the same name (this PC's own
                # internal copy, say) stays as it is.
                report.lines.append(f"  kept {target.name} from the {present.get('pack')} pack")
                continue
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(folder, target)
        marker.write_text(
            json.dumps(
                {"managed_by": "aep", "skill": folder.name, "pack": pack, "version": version}
            )
            + "\n",
            encoding="utf-8",
        )
        changed += 1
    report.lines.append(f"  {pack}: {changed} coding-agent skill folder(s) updated in {store}")


def is_switched_on(layout: HostLayout, identity: AssetIdentity) -> bool:
    """Some version of this Skill is switched on."""
    return any(layout.skills.glob(f"{identity.namespace}__{identity.name}__*.json"))


def sync_agent_copy(
    layout: HostLayout,
    identity: AssetIdentity,
    environment: agent_setup.Environment,
) -> list[str]:
    """Put the coding-agent copy of a pack Skill in, or take it out, to match
    whether the Skill is switched on. Nothing for a Skill without one."""
    source = store_dir(layout) / agent_folder_name(identity)
    if agent_setup._pack_marker(source) is None:
        return []
    on = is_switched_on(layout, identity)
    lines: list[str] = []
    for agent in agent_setup.PACK_AGENTS:
        if not agent_setup.aep_setup_present(agent, environment):
            continue
        try:
            changes = (
                agent_setup.link_pack_skill(agent, environment, source)
                if on
                else agent_setup.unlink_pack_skill(agent, environment, source.name)
            )
        except (OSError, ValueError) as error:
            lines.append(f"  {agent_setup.LABELS[agent]}: not changed ({error})")
            continue
        lines.extend(changes.lines)
    return lines


def sync_all_agent_copies(layout: HostLayout, environment: agent_setup.Environment) -> list[str]:
    """Every pack skill in the store, matched to its Skill's state."""
    lines: list[str] = []
    store = store_dir(layout)
    if not store.is_dir():
        return lines
    known = {
        agent_folder_name(identity): identity
        for path in [*layout.skills.glob("*.json"), *(layout.skills / DISABLED).glob("*.json")]
        if (identity := _identity_of(path)) is not None
    }
    for folder in sorted(store.iterdir()):
        identity = known.get(folder.name)
        if identity is not None:
            lines.extend(sync_agent_copy(layout, identity, environment))
    return lines


def install(
    layout: HostLayout,
    *,
    switched_on: Iterable[SkillManifest | WorkflowManifest] = (),
    switched_off: Iterable[SkillManifest | WorkflowManifest] = (),
    agent_stores: Iterable[tuple[Path, str]] = (),
    environment: agent_setup.Environment | None = None,
) -> Report:
    """Install manifests on the rules above, copy coding-agent folders into
    the store and, with an `environment`, match the agents' copies."""
    report = Report()
    removed = removed_by_person(layout)
    layout.skills.mkdir(parents=True, exist_ok=True)
    layout.workflows.mkdir(parents=True, exist_ok=True)
    # Lower versions first, so a newer one sets the older aside.
    on = sorted(
        switched_on, key=lambda m: (m.metadata.identity.key[:2], _version(m.metadata.identity))
    )
    for manifest in on:
        install_manifest(layout, manifest, enabled=True, removed=removed, report=report)
    for manifest in switched_off:
        install_manifest(layout, manifest, enabled=False, removed=removed, report=report)
    for source, pack in agent_stores:
        install_agent_store(layout, source, pack=pack, report=report)
    if environment is not None:
        report.lines.extend(sync_all_agent_copies(layout, environment))
    return report


def install_bundle(
    layout: HostLayout,
    bundle: Path | None,
    *,
    shipped: Iterable[SkillManifest | WorkflowManifest] = (),
    extra_off: Iterable[Path] = (),
    extra_agent_skills: Iterable[Path] = (),
    extra_pack: str = BUNDLE_PACK,
    environment: agent_setup.Environment | None = None,
) -> Report:
    """What `install.ps1` runs: the shipped manifests and the bundle's
    in-use ones switched on, its packs switched off."""
    on: list[SkillManifest | WorkflowManifest] = list(shipped)
    off: list[SkillManifest | WorkflowManifest] = []
    stores: list[tuple[Path, str]] = []
    if bundle is not None:
        on.extend(manifests_in(bundle / BUNDLE_IN_USE))
        off.extend(manifests_in(bundle / BUNDLE_PACK / "manifests"))
        stores.append((bundle / BUNDLE_PACK / "agent", BUNDLE_PACK))
    for directory in extra_off:
        off.extend(manifests_in(directory))
    for directory in extra_agent_skills:
        stores.append((directory, extra_pack))
    return install(
        layout, switched_on=on, switched_off=off, agent_stores=stores, environment=environment
    )
