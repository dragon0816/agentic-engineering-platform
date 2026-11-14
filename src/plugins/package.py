"""Inert, versioned staging of a plugin package envelope.

A version is written into a private `.part-*` folder, re-read and checked,
then exposed under `<root>/<namespace>/<name>/<version>` with one rename
(`common.filesystem.publish_directory`). Nothing is imported or executed.
Every folder on the way is refused when it is a symbolic link or a junction,
so a planted link cannot move the staged files elsewhere. Every path the
manager writes below or deletes is first checked by `owned_path` against the
workspace it owns: each step from that anchor down must be a plain folder and
the resolved path must stay under the resolved anchor. Removal (`remove_tree`)
deletes a link found inside the tree as a link, never following it. `verify_staged`
re-checks the exact bytes before each activation: a changed, missing or added
file (a planted module in the worker folder included) refuses the version.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path, PurePosixPath
from uuid import uuid4

import common.plugins as contract
from common.filesystem import publish_directory
from common.plugins import PluginContractError, PluginErrorCode, PluginPackage

PACKAGE_FILE = "package.json"
PART_PREFIX = ".part-"


class PluginStageError(Exception):
    """The code is the whole message; no path or byte is echoed."""

    def __init__(self, code: PluginErrorCode) -> None:
        self.code: PluginErrorCode = code
        super().__init__(code)


def linked(path: Path) -> bool:
    """A symbolic link or an NTFS junction (`Path.is_junction`, Python 3.12+)."""
    junction = getattr(path, "is_junction", None)
    if path.is_symlink():
        return True
    if junction is not None:
        return bool(junction())
    try:
        tag = getattr(path.lstat(), "st_reparse_tag", 0)
    except OSError:
        return False
    return tag == getattr(stat, "IO_REPARSE_TAG_MOUNT_POINT", 0xA0000003)


def owned_path(anchor: Path, path: Path) -> Path:
    """`path`, when it lies strictly below `anchor` and no step from the anchor
    down to it (or to its deepest existing folder) is a link or a junction, and
    its resolved form stays under the resolved anchor. The anchor is the folder
    the caller owns (the workspace); a link below it is never ownership proof."""
    base = Path(os.path.abspath(anchor))
    target = Path(os.path.abspath(path))
    try:
        relative = target.relative_to(base)
    except ValueError:
        raise PluginStageError("plugin_path_invalid") from None
    if not relative.parts or any(part in {"", ".", ".."} for part in relative.parts):
        raise PluginStageError("plugin_path_invalid")
    current = base
    deepest = base
    for part in relative.parts:
        current = current / part
        if linked(current):
            raise PluginStageError("plugin_path_invalid")
        if not current.exists():
            break
        deepest = current
    try:
        inside = deepest.resolve().is_relative_to(base.resolve())
    except (OSError, RuntimeError):
        inside = False
    if not inside:
        raise PluginStageError("plugin_path_invalid")
    return target


def safe_directory(base: Path, *parts: str, anchor: Path | None = None) -> Path:
    """`base/parts...`, created folder by folder; refused when `base` or any
    existing step is a link, a junction or not a folder. With `anchor`, `base`
    must also be an owned path below it (`owned_path`)."""
    current = Path(base)
    if anchor is not None:
        owned_path(anchor, current)
    if current.exists() and (linked(current) or not current.is_dir()):
        raise PluginStageError("plugin_path_invalid")
    current.mkdir(parents=True, exist_ok=True)
    if linked(current):
        raise PluginStageError("plugin_path_invalid")
    if anchor is not None:
        owned_path(anchor, current)
    for part in parts:
        current = current / part
        if current.exists() or linked(current):
            if linked(current) or not current.is_dir():
                raise PluginStageError("plugin_path_invalid")
        else:
            current.mkdir()
    return current


def version_dir(root: Path, package: PluginPackage) -> Path:
    identity = package.manifest.identity
    return Path(root) / identity.namespace / identity.name / identity.version


def stage_package(package: PluginPackage, root: Path, *, anchor: Path | None = None) -> Path:
    """Write the exact envelope and files; return the published version folder.
    With `anchor`, `root` must be an owned path below it."""
    identity = package.manifest.identity
    parent = safe_directory(Path(root), identity.namespace, identity.name, anchor=anchor)
    target = parent / identity.version
    if target.exists() or linked(target):
        raise PluginStageError("plugin_version_exists")
    stage = parent / f"{PART_PREFIX}{uuid4().hex[:8]}"
    try:
        stage.mkdir()
        (stage / PACKAGE_FILE).write_bytes(package.to_bytes())
        for item in package.files:
            destination = stage / PurePosixPath(item.path)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(item.raw)
        _check(stage, package)
        publish_directory(stage, target)
    except BaseException:
        if stage.exists() and not linked(stage):
            _delete(stage)
        raise
    return target


def _check(folder: Path, package: PluginPackage) -> None:
    files = {item.path: item for item in package.files}
    expected = {PACKAGE_FILE, *files}
    found: set[str] = set()
    folders = {
        "/".join(PurePosixPath(path).parts[:depth])
        for path in expected
        for depth in range(1, len(PurePosixPath(path).parts))
    }
    for path in folder.rglob("*"):
        relative = path.relative_to(folder).as_posix()
        if linked(path):
            raise PluginStageError("plugin_path_invalid")
        if path.is_dir():
            if relative not in folders:
                raise PluginStageError("plugin_staged_changed")
            continue
        if relative not in expected:
            raise PluginStageError("plugin_staged_changed")
        item = files.get(relative)
        if item is not None and path.read_bytes() != item.raw:
            raise PluginStageError("plugin_staged_changed")
        found.add(relative)
    if found != expected:
        raise PluginStageError("plugin_staged_changed")


def verify_staged(
    target: Path, content_sha256: str, *, anchor: Path | None = None
) -> PluginPackage:
    """The staged package, when every byte is still what was installed. With
    `anchor`, the folder must be an owned path below it."""
    folder = Path(target)
    if anchor is not None:
        owned_path(anchor, folder)
    for step in (folder, *folder.parents[:3]):
        if linked(step):
            raise PluginStageError("plugin_path_invalid")
    if not folder.is_dir():
        raise PluginStageError("plugin_staged_changed")
    envelope = folder / PACKAGE_FILE
    try:
        if envelope.stat().st_size > contract.MAX_PACKAGE_BYTES:
            raise PluginStageError("plugin_staged_changed")
        package = contract.parse_plugin_package(envelope.read_bytes())
    except (OSError, PluginContractError):
        raise PluginStageError("plugin_staged_changed") from None
    if package.content_sha256 != content_sha256 or folder.name != package.manifest.identity.version:
        raise PluginStageError("plugin_staged_changed")
    try:
        _check(folder, package)
    except OSError:
        raise PluginStageError("plugin_staged_changed") from None
    return package


def _delete(path: Path) -> None:
    """Best-effort removal that removes links as links and never descends into one."""
    try:
        if linked(path):
            if path.is_symlink() and not path.is_dir():
                path.unlink()
            else:
                os.rmdir(path)  # a junction or directory link: removes the link only
            return
        mode = path.lstat().st_mode
    except OSError:
        return
    if not stat.S_ISDIR(mode):
        try:
            path.unlink()
        except OSError:
            pass
        return
    try:
        children = [Path(entry.path) for entry in os.scandir(path)]
    except OSError:
        return
    for child in children:
        _delete(child)
    try:
        path.rmdir()
    except OSError:
        pass


def remove_tree(path: Path, *, anchor: Path) -> None:
    """Remove a folder the manager owns below `anchor`. A redirected path or
    ancestor raises `plugin_path_invalid` before anything is deleted."""
    target = owned_path(anchor, path)
    if target.exists():
        _delete(target)
