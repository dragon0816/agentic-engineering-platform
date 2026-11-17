"""Generic plugin hooks keep the no-plugin Host unchanged and close resources."""

import sys
from pathlib import Path

import pytest
from test_host_wiring import ready, skill_manifest

from agent.skills import SkillManifest
from common.plugins import PluginContractError, PluginReadRequest
from host_runtime.host import _refresh_plugin_assets, build_runtime


def test_an_empty_host_exposes_no_plugin_contributions_and_writes_no_plugin_store(
    tmp_path: Path,
) -> None:
    config, layout = ready(tmp_path)
    with build_runtime(config, layout=layout) as runtime:
        manager = getattr(runtime, "plugins", None)
        assert manager is not None
        assert manager.snapshot().plugins == ()
        assert not (layout.workspace_root / "plugins").exists()
    assert not (layout.workspace_root / "plugins").exists()


def test_closing_the_host_closes_its_plugin_process_manager(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class ClosingManager:
        def __init__(self) -> None:
            self.calls = 0

        def close(self) -> None:
            self.calls += 1

    config, layout = ready(tmp_path)
    closing = ClosingManager()
    with build_runtime(config, layout=layout) as runtime:
        existing = getattr(runtime, "plugins", None)
        if existing is not None:
            existing.close()
        monkeypatch.setattr(runtime, "plugins", closing, raising=False)
    assert closing.calls == 1


def plugin_skill(name: str, alias: str = "plugin_files") -> SkillManifest:
    raw = skill_manifest()
    raw["metadata"]["identity"].update(namespace="example-plugin", name=name)
    raw["alias"] = alias
    return SkillManifest.model_validate(raw)


def test_asset_refresh_changes_only_the_plugin_namespace(tmp_path: Path) -> None:
    config, layout = ready(tmp_path)
    with build_runtime(config, layout=layout) as runtime:
        gateway = runtime.agent.gateway
        registry = gateway.router.commands.skills
        before = {
            item.metadata.identity.key: item.model_dump_json() for item in registry.manifests()
        }
        manifest = plugin_skill("example")
        path = layout.skills / "example-plugin__example__1.0.0.json"
        path.write_text(manifest.model_dump_json(), encoding="utf-8")
        _refresh_plugin_assets(gateway, layout, "example-plugin")
        assert registry.get("example-plugin", "plugin_files") == manifest
        for item in registry.manifests():
            if item.metadata.identity.namespace != "example-plugin":
                assert item.model_dump_json() == before[item.metadata.identity.key]
        path.unlink()
        _refresh_plugin_assets(gateway, layout, "example-plugin")
        assert registry.get("example-plugin", "plugin_files") is None
        assert {
            item.metadata.identity.key: item.model_dump_json() for item in registry.manifests()
        } == before


def test_invalid_new_asset_does_not_remove_live_plugin_procedures(tmp_path: Path) -> None:
    config, layout = ready(tmp_path)
    with build_runtime(config, layout=layout) as runtime:
        gateway = runtime.agent.gateway
        first = plugin_skill("first")
        (layout.skills / "example-plugin__first__1.0.0.json").write_text(
            first.model_dump_json(), encoding="utf-8"
        )
        _refresh_plugin_assets(gateway, layout, "example-plugin")
        registry = gateway.router.commands.skills
        before = tuple(item.model_dump_json() for item in registry.manifests())
        second = plugin_skill("second")
        (layout.skills / "example-plugin__second__1.0.0.json").write_text(
            second.model_dump_json(), encoding="utf-8"
        )
        with pytest.raises(ValueError, match="alias"):
            _refresh_plugin_assets(gateway, layout, "example-plugin")
        assert tuple(item.model_dump_json() for item in registry.manifests()) == before


@pytest.mark.skipif(sys.platform != "win32", reason="NTFS junctions")
def test_redirected_plugin_store_cannot_break_host_startup_or_delete_other_files(
    tmp_path: Path,
) -> None:
    import _winapi

    config, layout = ready(tmp_path / "host")
    outside = tmp_path / "other-files" / "unrelated" / "data" / "1.0.0"
    outside.mkdir(parents=True)
    sentinel = outside / "keep.txt"
    sentinel.write_bytes(b"synthetic files outside the configured workspace")
    package_root = layout.workspace_root / "plugins" / "packages"
    package_root.parent.mkdir(parents=True)
    _winapi.CreateJunction(str(tmp_path / "other-files"), str(package_root))
    with build_runtime(config, layout=layout) as runtime:
        manager = runtime.plugins
        assert manager is not None
        with pytest.raises(PluginContractError, match="plugin_path_invalid"):
            manager.snapshot()
        assert sentinel.read_bytes() == b"synthetic files outside the configured workspace"
    assert sentinel.read_bytes() == b"synthetic files outside the configured workspace"


def test_worker_restart_rechecks_the_installed_file_digest(tmp_path: Path) -> None:
    from plugin_fixture_helpers import build_package, origin

    config, layout = ready(tmp_path)
    package = build_package("alpha-lab")
    with build_runtime(config, layout=layout) as runtime:
        manager = runtime.plugins
        assert manager is not None
        assert manager.install(package.to_bytes(), origin()).status == "succeeded"
        active = manager._active[package.manifest.plugin_id]
        assert active.session is not None
        active.session.close()
        worker = active.root / "worker" / "aep_plugin_alpha_lab" / "worker.py"
        worker.write_bytes(worker.read_bytes() + b"\n# changed after initial activation\n")
        result = manager.call_read(
            PluginReadRequest(
                request_id="restart-file-check",
                plugin_id=package.manifest.plugin_id,
                version=package.manifest.identity.version,
                route_id="summary",
            ),
            timeout_seconds=5,
        )
        assert result.status == "failed"
        assert result.failure is not None
        assert result.failure.code == "plugin_staged_changed"
