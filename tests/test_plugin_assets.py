"""Bundled Skills/Workflows of a plugin go through the existing asset ledger:
user-modified, switched-off and removed choices survive, only owned unchanged
files leave, and review metadata is never invented (Slice 1)."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from test_plugin_manager import ORIGIN, code, found, manifest_data

from agent.skills import SkillManifest
from capabilities.runtime import InstalledCapabilities
from common.assets import WorkflowManifest
from common.plugins import PluginManifest, PluginPackage, PluginReadRequest
from host_runtime.contracts import HostLayout
from plugins import PluginManager
from plugins import assets as bundled

NS = "hello-lab"


def skill_bytes(name: str = "hello-skill", version: str = "1.0.0", **metadata: Any) -> bytes:
    manifest = SkillManifest.model_validate(
        {
            "metadata": {
                "identity": {"namespace": NS, "name": name, "version": version},
                "owner": {"type": "team", "id": "synthetic"},
                "visibility": "private",
                **metadata,
            },
            "alias": name.replace("-", "_"),
            "instructions": "Synthetic instructions.",
        }
    )
    return manifest.model_dump_json(indent=2).encode()


def file_name(name: str = "hello-skill", version: str = "1.0.0") -> str:
    return f"{NS}__{name}__{version}.json"


def package(
    *,
    version: str = "1.0.0",
    skills: tuple[tuple[str, str], ...] = (("hello-skill", "1.0.0"),),
    switched_on: bool = True,
    raw: dict[str, bytes] | None = None,
) -> bytes:
    files: dict[str, bytes] = {}
    assets = []
    for name, skill_version in skills:
        path = f"assets/skills/{file_name(name, skill_version)}"
        content = (raw or {}).get(name) or skill_bytes(name, skill_version)
        files[path] = content
        assets.append(
            {
                "kind": "skill",
                "identity": {"namespace": NS, "name": name, "version": skill_version},
                "path": path,
                "sha256": hashlib.sha256(content).hexdigest(),
                "switched_on": switched_on,
            }
        )
    data = manifest_data(version=version, worker=False, assets=tuple(assets))
    return PluginPackage.build(PluginManifest.model_validate(data), files).to_bytes()


@pytest.fixture
def layout(tmp_path: Path) -> HostLayout:
    return HostLayout.under(tmp_path / "ws")


@pytest.fixture
def changed() -> list[str]:
    return []


@pytest.fixture
def manager(layout: HostLayout, changed: list[str]) -> Iterator[PluginManager]:
    item = PluginManager(layout, InstalledCapabilities(), assets_changed=changed.append)
    yield item
    item.close()


def test_bundled_skill_installs_switched_on_and_leaves_on_uninstall(
    manager: PluginManager, layout: HostLayout, changed: list[str]
) -> None:
    result = manager.install(package(), ORIGIN)
    assert result.status == "succeeded", result.failure
    installed = layout.skills / file_name()
    stored = SkillManifest.model_validate_json(installed.read_text(encoding="utf-8"))
    assert stored.metadata.business_approval.status == "pending"
    assert stored.metadata.business_approval.reviewer is None
    assert changed == [NS]
    assert manager.uninstall("hello-lab.hello", ORIGIN).status == "succeeded"
    assert not installed.exists()
    assert changed == [NS, NS]


def test_switched_on_false_installs_into_disabled(
    manager: PluginManager, layout: HostLayout
) -> None:
    manager.install(package(switched_on=False), ORIGIN)
    assert (layout.skills / "disabled" / file_name()).is_file()
    assert not (layout.skills / file_name()).exists()


def test_user_modified_file_is_never_overwritten_or_removed(
    manager: PluginManager, layout: HostLayout
) -> None:
    manager.install(package(), ORIGIN)
    path = layout.skills / file_name()
    edited = path.read_text(encoding="utf-8").replace("Synthetic instructions.", "Mine.")
    path.write_text(edited, encoding="utf-8")
    assert manager.disable("hello-lab.hello", ORIGIN).status == "succeeded"
    assert path.read_text(encoding="utf-8") == edited
    assert manager.enable("hello-lab.hello", ORIGIN).status == "succeeded"
    assert path.read_text(encoding="utf-8") == edited
    assert manager.uninstall("hello-lab.hello", ORIGIN).status == "succeeded"
    assert path.read_text(encoding="utf-8") == edited


def test_a_switched_off_choice_survives_disable_enable_and_update(
    manager: PluginManager, layout: HostLayout
) -> None:
    manager.install(package(), ORIGIN)
    on = layout.skills / file_name()
    off = layout.skills / "disabled" / file_name()
    off.parent.mkdir(parents=True, exist_ok=True)
    on.replace(off)  # the person switched it off
    manager.disable("hello-lab.hello", ORIGIN)
    assert not off.exists() and not on.exists()
    manager.enable("hello-lab.hello", ORIGIN)
    assert off.is_file() and not on.exists()
    assert manager.install(package(version="1.1.0"), ORIGIN).status == "succeeded"
    assert off.is_file() and not on.exists()


def test_a_removed_asset_is_not_brought_back(manager: PluginManager, layout: HostLayout) -> None:
    journal = layout.workspace_root / "removed" / "removed.jsonl"
    journal.parent.mkdir(parents=True)
    journal.write_text(
        json.dumps({"kind": "skill", "asset": f"{NS}/hello-skill@1.0.0"}) + "\n", encoding="utf-8"
    )
    assert manager.install(package(), ORIGIN).status == "succeeded"
    assert not (layout.skills / file_name()).exists()
    assert not (layout.skills / "disabled" / file_name()).exists()


def test_update_replaces_only_owned_unchanged_assets(
    manager: PluginManager, layout: HostLayout
) -> None:
    manager.install(package(skills=(("hello-skill", "1.0.0"), ("old-skill", "1.0.0"))), ORIGIN)
    updated = package(version="1.1.0", skills=(("hello-skill", "1.1.0"),))
    assert manager.install(updated, ORIGIN).status == "succeeded"
    assert (layout.skills / file_name(version="1.1.0")).is_file()
    assert not (layout.skills / file_name("old-skill")).exists()
    assert not (layout.skills / file_name()).exists()
    assert not (layout.skills / "disabled" / file_name()).exists()


@pytest.mark.parametrize(
    "content",
    [
        skill_bytes(business_approval={"status": "approved", "reviewer": "x", "evidence": "y"}),
        skill_bytes(name="other-name"),
        b"{not json",
    ],
)
def test_claimed_review_or_mismatched_asset_is_refused_before_anything(
    manager: PluginManager, layout: HostLayout, content: bytes
) -> None:
    result = manager.install(package(raw={"hello-skill": content}), ORIGIN)
    assert code(result) == "plugin_package_invalid"
    assert not layout.skills.exists() or not any(layout.skills.rglob("*.json"))
    assert manager.snapshot().plugins == ()


# -- upgrade failure and interruption keep the previous bundle -----------------------------


class Crash(BaseException):
    """A process ending in the middle of an update."""


def flow_bytes(version: str) -> bytes:
    from capabilities.coding_change.manifest import run_python_workflow

    data = run_python_workflow().model_dump(mode="json")
    data["metadata"]["identity"] = {"namespace": NS, "name": "hello-flow", "version": version}
    data["metadata"]["business_approval"] = {"status": "pending"}
    data["metadata"]["technical_policy"] = {"status": "pending"}
    data["metadata"]["lifecycle"] = "draft"
    return WorkflowManifest.model_validate(data).model_dump_json(indent=2).encode()


def bundle(version: str, skills: tuple[str, ...], flow: str) -> bytes:
    files: dict[str, bytes] = {}
    assets = []
    for kind, name, item_version, content in (
        *(("skill", name, version, skill_bytes(name, version)) for name in skills),
        ("workflow", "hello-flow", flow, flow_bytes(flow)),
    ):
        path = f"assets/{kind}s/{file_name(name, item_version)}"
        files[path] = content
        assets.append(
            {
                "kind": kind,
                "identity": {"namespace": NS, "name": name, "version": item_version},
                "path": path,
                "sha256": hashlib.sha256(content).hexdigest(),
            }
        )
    data = manifest_data(version=version, worker=False, assets=tuple(assets))
    return PluginPackage.build(PluginManifest.model_validate(data), files).to_bytes()


V1 = ("1.0.0", ("hello-skill", "old-skill"), "1.0.0")
V2 = ("1.1.0", ("hello-skill",), "1.1.0")


def tree(layout: HostLayout) -> dict[str, bytes]:
    folder = layout.workspace_root / "assets"
    return {p.relative_to(folder).as_posix(): p.read_bytes() for p in folder.rglob("*.json")}


def ledger_plugins(layout: HostLayout) -> Any:
    document = json.loads((layout.workspace_root / "plugins" / "ledger.json").read_text("utf-8"))
    return document["plugins"]


def _fail_second_write(monkeypatch: pytest.MonkeyPatch, error: BaseException) -> None:
    real = PluginManager._write
    calls: list[int] = []

    def failing(self: PluginManager, ledger: Any) -> None:
        calls.append(1)
        if len(calls) == 2:  # 1 = pending, 2 = final commit
            raise error
        real(self, ledger)

    monkeypatch.setattr(PluginManager, "_write", failing)


def test_a_failed_upgrade_keeps_the_previous_bundle_in_place(
    manager: PluginManager, layout: HostLayout, changed: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    assert manager.install(bundle(*V1), ORIGIN).status == "succeeded"
    before, recorded = tree(layout), ledger_plugins(layout)
    assert f"skills/{file_name()}" in before and f"workflows/{file_name('hello-flow')}" in before
    _fail_second_write(monkeypatch, OSError("synthetic disk failure"))
    assert code(manager.install(bundle(*V2), ORIGIN)) == "plugin_environment_failed"
    assert tree(layout) == before  # same bytes, same on/off places, no 1.1.0 files
    assert ledger_plugins(layout) == recorded
    assert found(manager.snapshot(), "hello-lab.hello").identity.version == "1.0.0"
    assert changed[-1] == NS
    assert not (layout.workspace_root / "plugins/packages/hello-lab/hello/1.1.0").exists()


def test_an_interrupted_upgrade_is_undone_at_the_next_start(
    layout: HostLayout, monkeypatch: pytest.MonkeyPatch
) -> None:
    manager = PluginManager(layout, InstalledCapabilities())
    assert manager.install(bundle(*V1), ORIGIN).status == "succeeded"
    before, recorded = tree(layout), ledger_plugins(layout)
    _fail_second_write(monkeypatch, Crash())
    with pytest.raises(Crash):
        manager.install(bundle(*V2), ORIGIN)
    manager.close()
    monkeypatch.undo()
    assert ledger_plugins(layout)[0]["pending"] is not None
    changed: list[str] = []
    fresh = PluginManager(layout, InstalledCapabilities(), assets_changed=changed.append)
    try:
        assert found(fresh.restore(), "hello-lab.hello").identity.version == "1.0.0"
        assert tree(layout) == before
        assert ledger_plugins(layout) == recorded
        assert changed == [NS]
        assert not (layout.workspace_root / "plugins/packages/hello-lab/hello/1.1.0").exists()
    finally:
        fresh.close()


def test_retired_files_of_a_committed_upgrade_are_removed_after_a_crash(
    layout: HostLayout, monkeypatch: pytest.MonkeyPatch
) -> None:
    manager = PluginManager(layout, InstalledCapabilities())
    assert manager.install(bundle(*V1), ORIGIN).status == "succeeded"

    def crash(*args: Any, **kwargs: Any) -> Any:
        raise Crash()

    monkeypatch.setattr(bundled, "remove_owned", crash)
    with pytest.raises(Crash):
        manager.install(bundle(*V2), ORIGIN)
    manager.close()
    monkeypatch.undo()
    assert [a["file"] for a in ledger_plugins(layout)[0]["retiring"]]
    fresh = PluginManager(layout, InstalledCapabilities())
    try:
        assert found(fresh.restore(), "hello-lab.hello").identity.version == "1.1.0"
        files = tree(layout)
        assert f"skills/{file_name(version='1.1.0')}" in files
        assert f"workflows/{file_name('hello-flow', '1.1.0')}" in files
        assert not any("1.0.0" in name for name in files)
        assert ledger_plugins(layout)[0]["retiring"] == []
    finally:
        fresh.close()


# -- the live refresh is part of the change; ledger first, then teardown ---------------------


def test_a_failing_live_refresh_rolls_the_upgrade_back(layout: HostLayout) -> None:
    calls: list[str] = []
    failing = {"on": False}

    def refresh(namespace: str) -> None:
        calls.append(namespace)
        if failing["on"]:
            raise ValueError("synthetic registry refresh failure")

    manager = PluginManager(layout, InstalledCapabilities(), assets_changed=refresh)
    try:
        assert manager.install(bundle(*V1), ORIGIN).status == "succeeded"
        before, recorded = tree(layout), ledger_plugins(layout)
        failing["on"] = True
        result = manager.install(bundle(*V2), ORIGIN)
        assert code(result) == "plugin_environment_failed"
        assert result.failure is not None and "refresh" in result.failure.message
        assert tree(layout) == before
        assert ledger_plugins(layout) == recorded
        assert found(manager.snapshot(), "hello-lab.hello").identity.version == "1.0.0"
        assert calls == [NS, NS, NS]  # install, the failed refresh, the rollback refresh
    finally:
        manager.close()


def test_a_failing_refresh_during_recovery_does_not_stop_the_start(
    layout: HostLayout, monkeypatch: pytest.MonkeyPatch
) -> None:
    manager = PluginManager(layout, InstalledCapabilities())
    assert manager.install(bundle(*V1), ORIGIN).status == "succeeded"
    before = tree(layout)
    _fail_second_write(monkeypatch, Crash())
    with pytest.raises(Crash):
        manager.install(bundle(*V2), ORIGIN)
    manager.close()
    monkeypatch.undo()

    def refresh(namespace: str) -> None:
        raise ValueError("synthetic registry refresh failure")

    fresh = PluginManager(layout, InstalledCapabilities(), assets_changed=refresh)
    try:
        assert found(fresh.restore(), "hello-lab.hello").identity.version == "1.0.0"
        assert tree(layout) == before
    finally:
        fresh.close()


@pytest.mark.parametrize("action", ["disable", "uninstall"])
def test_a_failed_ledger_write_leaves_the_plugin_as_it_was(
    layout: HostLayout, monkeypatch: pytest.MonkeyPatch, action: str
) -> None:
    from test_plugin_manager import identity, payload

    installed = InstalledCapabilities()
    manager = PluginManager(layout, installed)
    try:
        assert manager.install(bundle(*V1), ORIGIN).status == "succeeded"
        assert manager.install(payload(namespace="work-lab", name="tool"), ORIGIN).status == (
            "succeeded"
        )
        before, recorded = tree(layout), ledger_plugins(layout)

        def failing(self: PluginManager, ledger: Any) -> None:
            raise OSError("synthetic disk failure")

        monkeypatch.setattr(PluginManager, "_write", failing)
        for plugin_id in ("hello-lab.hello", "work-lab.tool"):
            result = getattr(manager, action)(plugin_id, ORIGIN)
            assert code(result) == "plugin_environment_failed"
        monkeypatch.undo()
        assert tree(layout) == before
        assert ledger_plugins(layout) == recorded
        assert {p.state for p in manager.snapshot().plugins} == {"active"}
        assert installed.get(identity("work-lab")) is not None
        response = manager.call_read(
            PluginReadRequest(
                request_id="r-1",
                plugin_id="work-lab.tool",
                version="1.0.0",
                route_id="summary",
                arguments={"text": "ok"},
            ),
            timeout_seconds=10,
        )
        assert response.status == "succeeded"
    finally:
        manager.close()


def test_unfinished_retirements_carry_into_the_next_upgrade(
    layout: HostLayout, monkeypatch: pytest.MonkeyPatch
) -> None:
    manager = PluginManager(layout, InstalledCapabilities())
    try:
        assert manager.install(bundle(*V1), ORIGIN).status == "succeeded"
        real_write, real_remove = PluginManager._write, bundled.remove_owned
        writes: list[int] = []
        removals: list[int] = []

        def write(self: PluginManager, ledger: Any) -> None:
            writes.append(1)
            if len(writes) == 3:  # 1 = pending, 2 = final commit, 3 = retirement cleared
                raise OSError("synthetic disk failure")
            real_write(self, ledger)

        def remove(*args: Any) -> Any:
            removals.append(1)
            return () if len(removals) == 1 else real_remove(*args)  # a locked file stays

        monkeypatch.setattr(PluginManager, "_write", write)
        monkeypatch.setattr(bundled, "remove_owned", remove)
        assert manager.install(bundle(*V2), ORIGIN).status == "succeeded"
        monkeypatch.undo()
        assert any("1.0.0" in name for name in tree(layout))
        v3 = bundle("1.2.0", ("hello-skill",), "1.2.0")
        assert manager.install(v3, ORIGIN).status == "succeeded"
    finally:
        manager.close()
    fresh = PluginManager(layout, InstalledCapabilities())
    try:
        assert found(fresh.restore(), "hello-lab.hello").identity.version == "1.2.0"
        files = tree(layout)
        assert not any("1.0.0" in name or "1.1.0" in name for name in files), sorted(files)
        assert ledger_plugins(layout)[0]["retiring"] == []
    finally:
        fresh.close()
