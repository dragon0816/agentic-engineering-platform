"""Which in-process feature plugins a Host loads at start (Plugin API 1.2).

Two places hold them. *Bundled* ones ship with AEP as a folder with
`plugin.json` (the manifest) and `python/`; *installed* ones are staged packages
in the workspace ledger, installed from the Plugins page. For each plugin id
the newest enabled copy wins: an installed newer version replaces the bundled
one, and a newer AEP's bundled version replaces an older installed one. A
disabled ledger record, or a bundled plugin switched off here, loads nothing.

Nothing here imports plugin code; `host_runtime.features` does that.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from common.ownership import version_key
from common.plugins import (
    CORE_PLUGIN_API_VERSION,
    PluginContractError,
    PluginErrorCode,
    PluginManifest,
    core_api_supported,
)
from plugins.ledger import LedgerUnreadable, read_ledger
from plugins.package import PluginStageError, verify_staged

#: Folders of bundled feature plugins, separated by `os.pathsep`; when unset,
#: `default_bundled_roots()` applies.
BUNDLED_ENV = "AEP_BUNDLED_PLUGINS"
#: Where the Windows installer puts the bundle's `feature-plugins/` (beside
#: the venv's own files, so an update replaces it with the venv).
INSTALLED_BUNDLE = "aep-feature-plugins"
#: Bundled plugin ids switched off on this workspace (the Plugins page).
BUNDLED_OFF = "bundled-off.json"
MANIFEST_FILE = "plugin.json"


@dataclass(frozen=True)
class FeatureSource:
    """One in-process plugin to load: its manifest and its `python/` folder."""

    manifest: PluginManifest
    python_root: Path
    origin: Literal["bundled", "installed"]

    @property
    def plugin_id(self) -> str:
        return self.manifest.plugin_id

    @property
    def version(self) -> str:
        return self.manifest.identity.version


@dataclass(frozen=True)
class Skipped:
    """A plugin found but not loaded, and why (shown on the Plugins page)."""

    plugin_id: str
    code: PluginErrorCode
    message: str


def default_bundled_roots() -> tuple[Path, ...]:
    """The source tree's `feature_plugins/`, then the installed bundle's."""
    found = [
        Path(__file__).resolve().parents[2] / "feature_plugins",
        Path(sys.prefix) / INSTALLED_BUNDLE,
    ]
    return tuple(path for path in found if path.is_dir())


def bundled_roots() -> tuple[Path, ...]:
    configured = os.environ.get(BUNDLED_ENV)
    if configured is not None:
        return tuple(Path(item) for item in configured.split(os.pathsep) if item)
    return default_bundled_roots()


def bundled(roots: tuple[Path, ...] | None = None) -> tuple[list[FeatureSource], list[Skipped]]:
    """Every bundled in-process plugin under `roots` (each a folder of plugin folders)."""
    sources: list[FeatureSource] = []
    skipped: list[Skipped] = []
    seen: set[str] = set()
    for root in bundled_roots() if roots is None else roots:
        for folder in sorted(path for path in root.iterdir() if path.is_dir()):
            manifest_file = folder / MANIFEST_FILE
            if not manifest_file.is_file():
                continue
            try:
                manifest = PluginManifest.model_validate_json(manifest_file.read_bytes())
            except (OSError, ValueError) as error:
                skipped.append(Skipped(folder.name, "plugin_package_invalid", str(error)[:200]))
                continue
            if manifest.in_process is None or manifest.plugin_id in seen:
                continue
            seen.add(manifest.plugin_id)
            sources.append(FeatureSource(manifest, folder / "python", "bundled"))
    return sources, skipped


def bundled_off(workspace_root: Path) -> frozenset[str]:
    path = workspace_root / "plugins" / BUNDLED_OFF
    try:
        listed = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return frozenset()
    except (OSError, ValueError):
        return frozenset()
    if not isinstance(listed, list):
        return frozenset()
    return frozenset(str(item) for item in listed)


def set_bundled_off(workspace_root: Path, plugin_id: str, off: bool) -> None:
    current = set(bundled_off(workspace_root))
    if off:
        current.add(plugin_id)
    else:
        current.discard(plugin_id)
    folder = workspace_root / "plugins"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / BUNDLED_OFF
    temporary = path.with_suffix(".json.part")
    temporary.write_text(json.dumps(sorted(current), indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def installed(workspace_root: Path) -> tuple[dict[str, FeatureSource | None], list[Skipped]]:
    """In-process plugins in the workspace ledger: their staged copy when
    enabled, None when installed but disabled."""
    plugins = workspace_root / "plugins"
    found: dict[str, FeatureSource | None] = {}
    skipped: list[Skipped] = []
    ledger_path = plugins / "ledger.json"
    if not ledger_path.is_file():
        return found, skipped
    try:
        ledger = read_ledger(ledger_path)
    except LedgerUnreadable as error:
        skipped.append(Skipped("*", error.code, "The plugin ledger could not be read."))
        return found, skipped
    for record in ledger.plugins:
        identity = record.identity
        folder = plugins / "packages" / identity.namespace / identity.name / identity.version
        try:
            package = verify_staged(folder, record.content_sha256, anchor=workspace_root)
        except (PluginStageError, PluginContractError, OSError) as error:
            code: PluginErrorCode = (
                error.code
                if isinstance(error, (PluginStageError, PluginContractError))
                else "plugin_environment_failed"
            )
            if record.enabled:
                skipped.append(Skipped(record.plugin_id, code, "The staged copy changed."))
            continue
        if package.manifest.in_process is None:
            continue
        found[record.plugin_id] = (
            FeatureSource(package.manifest, folder / "python", "installed")
            if record.enabled and record.pending is None
            else None
        )
    return found, skipped


def resolve(
    workspace_root: Path | None, roots: tuple[Path, ...] | None = None
) -> tuple[list[FeatureSource], list[Skipped]]:
    """What to load, newest enabled copy per plugin id, in plugin id order."""
    shipped, skipped = bundled(roots)
    chosen: dict[str, FeatureSource] = {}
    off: frozenset[str] = frozenset()
    local: dict[str, FeatureSource | None] = {}
    if workspace_root is not None:
        off = bundled_off(workspace_root)
        local, problems = installed(workspace_root)
        skipped.extend(problems)
    for source in shipped:
        if source.plugin_id in off or (
            source.plugin_id in local and local[source.plugin_id] is None
        ):
            continue
        chosen[source.plugin_id] = source
    for plugin_id, maybe in local.items():
        if maybe is None:
            continue
        held = chosen.get(plugin_id)
        if held is None or version_key(maybe.version) > version_key(held.version):
            chosen[plugin_id] = maybe
    ready: list[FeatureSource] = []
    for plugin_id in sorted(chosen):
        source = chosen[plugin_id]
        if not core_api_supported(source.manifest):
            skipped.append(
                Skipped(
                    plugin_id,
                    "plugin_core_api_incompatible",
                    f"It needs Plugin API {source.manifest.core_api.minimum} up to "
                    f"{source.manifest.core_api.below}; this AEP has {CORE_PLUGIN_API_VERSION}.",
                )
            )
            continue
        ready.append(source)
    return ready, skipped


def ensure_bundled_importable(roots: tuple[Path, ...] | None = None) -> None:
    """Put each bundled feature's `python/` on the import path without loading
    it as a Host feature: for code outside the Host that reads a feature's
    formats (the Shared Platform's BI dataset snapshots)."""
    sources, _ = bundled(roots)
    for source in sources:
        root = str(source.python_root)
        if root not in sys.path:
            sys.path.append(root)
