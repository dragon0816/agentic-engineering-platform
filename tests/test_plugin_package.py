"""Inert, versioned staging of plugin package envelopes (Slice 1)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from test_plugin_manager import build

import plugins.package as staging
from plugins.package import PluginStageError, remove_tree, stage_package, verify_staged


def test_stage_writes_exact_inert_files_atomically(tmp_path: Path) -> None:
    package = build()
    target = stage_package(package, tmp_path / "packages")
    assert target == tmp_path / "packages" / "hello-lab" / "hello" / "1.0.0"
    assert (target / "package.json").read_bytes() == package.to_bytes()
    for item in package.files:
        assert (target / item.path).read_bytes() == item.raw
    assert verify_staged(target, package.content_sha256) == package
    assert not [p for p in target.parent.iterdir() if p.name.startswith(".part-")]
    with pytest.raises(PluginStageError) as raised:
        stage_package(package, tmp_path / "packages")
    assert raised.value.code == "plugin_version_exists"


@pytest.mark.parametrize("change", ["modify", "add", "remove", "envelope", "folder"])
def test_changed_staged_bytes_are_refused(tmp_path: Path, change: str) -> None:
    package = build()
    target = stage_package(package, tmp_path / "packages")
    worker = target / "worker" / "aep_plugin_hello_lab"
    if change == "modify":
        (worker / "worker.py").write_text("print('evil')\n", encoding="utf-8")
    elif change == "add":
        (worker / "json.py").write_text("print('planted')\n", encoding="utf-8")
    elif change == "remove":
        (worker / "__init__.py").unlink()
    elif change == "envelope":
        (target / "package.json").write_bytes(build(mode="other").to_bytes())
    else:
        (worker / "extra").mkdir()
    with pytest.raises(PluginStageError) as raised:
        verify_staged(target, package.content_sha256)
    assert raised.value.code == "plugin_staged_changed"


def test_failed_publish_leaves_no_partial_version(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def refuse(stage: Path, target: Path) -> None:
        raise OSError("synthetic rename failure")

    monkeypatch.setattr(staging, "publish_directory", refuse)
    with pytest.raises(OSError):
        stage_package(build(), tmp_path / "packages")
    parent = tmp_path / "packages" / "hello-lab" / "hello"
    assert not parent.exists() or not any(parent.iterdir())


@pytest.mark.skipif(sys.platform != "win32", reason="NTFS junctions")
def test_junctions_in_the_staging_path_are_refused(tmp_path: Path) -> None:
    import _winapi

    outside = tmp_path / "outside"
    outside.mkdir()
    root = tmp_path / "packages"
    root.mkdir()
    _winapi.CreateJunction(str(outside), str(root / "hello-lab"))
    with pytest.raises(PluginStageError) as raised:
        stage_package(build(), root)
    assert raised.value.code == "plugin_path_invalid"
    assert not any(outside.iterdir())
    package = build()
    target = stage_package(package, tmp_path / "clean")
    moved = tmp_path / "moved"
    target.rename(moved)
    _winapi.CreateJunction(str(moved), str(target))
    with pytest.raises(PluginStageError) as changed:
        verify_staged(target, package.content_sha256)
    assert changed.value.code == "plugin_path_invalid"


def test_a_symlinked_root_is_refused(tmp_path: Path) -> None:
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    try:
        link.symlink_to(real, target_is_directory=True)
    except OSError:
        pytest.skip("symbolic links need a privilege here")
    with pytest.raises(PluginStageError) as raised:
        stage_package(build(), link)
    assert raised.value.code == "plugin_path_invalid"


def test_oversized_envelope_on_disk_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    package = build()
    target = stage_package(package, tmp_path / "packages")
    import common.plugins as contract

    monkeypatch.setattr(contract, "MAX_PACKAGE_BYTES", 10)
    with pytest.raises(PluginStageError) as raised:
        verify_staged(target, package.content_sha256)
    assert raised.value.code == "plugin_staged_changed"


@pytest.mark.skipif(sys.platform != "win32", reason="NTFS junctions")
def test_cleanup_never_follows_a_redirected_ancestor(tmp_path: Path) -> None:
    import _winapi

    outside = tmp_path / "outside"
    keep = outside / "hello" / "1.0.0" / "keep.txt"
    keep.parent.mkdir(parents=True)
    keep.write_bytes(b"sentinel")
    anchor = tmp_path / "ws"
    (anchor / "plugins" / "packages").mkdir(parents=True)
    link = anchor / "plugins" / "packages" / "hello-lab"
    _winapi.CreateJunction(str(outside), str(link))
    with pytest.raises(PluginStageError) as raised:
        remove_tree(link / "hello" / "1.0.0", anchor=anchor)
    assert raised.value.code == "plugin_path_invalid"
    with pytest.raises(PluginStageError):
        remove_tree(link, anchor=anchor)
    with pytest.raises(PluginStageError):
        remove_tree(tmp_path / "elsewhere", anchor=anchor)
    with pytest.raises(PluginStageError):
        stage_package(build(), anchor / "plugins" / "packages" / "hello-lab", anchor=anchor)
    assert keep.read_bytes() == b"sentinel"
    inner = anchor / "plugins" / "packages" / "mine"
    (inner / "a").mkdir(parents=True)
    _winapi.CreateJunction(str(outside), str(inner / "a" / "link"))
    remove_tree(inner, anchor=anchor)  # a link inside is removed, never followed
    assert not inner.exists()
    assert keep.read_bytes() == b"sentinel"
