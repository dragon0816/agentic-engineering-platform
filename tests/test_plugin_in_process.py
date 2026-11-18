"""In-process feature plugins (Plugin API 1.2, proposal r3 stage B).

A feature plugin ships `python/<package>/` and names a `Feature`; the Host
imports it at start. Installing or updating one changes what the next start
loads, never the running process; a plugin that fails to load is skipped.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError
from test_host_wiring import ready

from common.plugins import (
    CORE_PLUGIN_API_VERSION,
    PluginManifest,
    PluginOrigin,
    PluginPackage,
)
from host_runtime import features
from plugins import in_process
from plugins.manager import FeatureState, PluginManager

ROOT = Path(__file__).resolve().parents[1]
ORIGIN = PluginOrigin(actor="tester", channel="test")


def _manifest(package: str, version: str = "1.0.0", **changes: Any) -> dict[str, Any]:
    raw: dict[str, Any] = {
        "format": "aep-plugin/1",
        "identity": {"namespace": package.replace("_", "-"), "name": "feature", "version": version},
        "title": "Demo feature",
        "description": "A synthetic in-process feature for tests.",
        "core_api": {"minimum": "1.2.0", "below": "2.0.0"},
        "in_process": {"package": package, "entry": f"{package}.feature"},
    }
    raw.update(changes)
    return raw


def _feature_source(package: str, mark: str) -> str:
    return (
        "from host_runtime.features import Feature\n\n\n"
        "class Demo(Feature):\n"
        f"    name = {package!r}\n\n"
        "    def finish_answer(self, text, result):\n"
        f"        return text + {mark!r}\n\n\n"
        "FEATURE = Demo()\n"
    )


def _files(package: str, mark: str) -> dict[str, bytes]:
    return {
        f"python/{package}/__init__.py": b"",
        f"python/{package}/feature.py": _feature_source(package, mark).encode(),
        f"python/{package}/data/sample.csv": b"a,b\n1,2\n",
    }


def _bundle(root: Path, package: str, mark: str, version: str = "1.0.0") -> Path:
    folder = root / package
    for path, raw in _files(package, mark).items():
        target = folder / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
    (folder / in_process.MANIFEST_FILE).write_text(
        json.dumps(_manifest(package, version)), encoding="utf-8"
    )
    return folder


def _package(package: str, mark: str, version: str) -> PluginPackage:
    manifest = PluginManifest.model_validate(_manifest(package, version))
    return PluginPackage.build(manifest, _files(package, mark))


def _name() -> str:
    return "aep_t" + uuid.uuid4().hex[:10]


# -- contract -----------------------------------------------------------------------------


def test_the_core_offers_plugin_api_1_2() -> None:
    assert CORE_PLUGIN_API_VERSION == "1.2.0"


def test_an_in_process_manifest_is_closed() -> None:
    package = _name()
    valid = PluginManifest.model_validate(_manifest(package))
    assert valid.in_process is not None and valid.in_process.entry_path.endswith("feature.py")
    bad: list[dict[str, Any]] = [
        _manifest(package, core_api={"minimum": "1.1.0", "below": "2.0.0"}),
        _manifest(package, in_process={"package": package, "entry": "other.feature"}),
        _manifest(
            "aep_plugin_x", in_process={"package": "aep_plugin_x", "entry": "aep_plugin_x.f"}
        ),
        _manifest(package, in_process={"package": "bi", "entry": "bi.feature"}),
        _manifest(package, data={"reads": ["bi"]}),
    ]
    for raw in bad:
        with pytest.raises(ValidationError):
            PluginManifest.model_validate(raw)


def test_an_older_manifest_serializes_as_before() -> None:
    raw = _manifest("aep_x")
    raw.pop("in_process")
    raw["core_api"] = {"minimum": "1.0.0", "below": "2.0.0"}
    assert "in_process" not in PluginManifest.model_validate(raw).model_dump(mode="json")


def test_a_manifest_places_its_page_parts_and_its_default_is_left_off_the_wire(
    tmp_path: Path,
) -> None:
    package = _name()
    plain = PluginManifest.model_validate(_manifest(package))
    assert plain.in_process is not None and plain.in_process.page_order == 100
    assert "page_order" not in plain.model_dump(mode="json")["in_process"]
    placed = _manifest(package, in_process={"package": package, "entry": f"{package}.feature"})
    placed["in_process"]["page_order"] = 50
    early = PluginManifest.model_validate(placed)
    assert early.model_dump(mode="json")["in_process"]["page_order"] == 50
    for wrong in (-1, 1001, "50"):
        placed["in_process"]["page_order"] = wrong
        with pytest.raises(ValidationError):
            PluginManifest.model_validate(placed)
    # Loading takes the manifest's place for the feature's page fragments.
    folder = _bundle(tmp_path, package, "!")
    placed["in_process"]["page_order"] = 7
    (folder / in_process.MANIFEST_FILE).write_text(json.dumps(placed), encoding="utf-8")
    sources, _ = in_process.resolve(None, (tmp_path,))
    assert [feature.page_order for feature in features.load_sources(sources)] == [7]


def test_python_files_belong_to_the_declared_package() -> None:
    package = _name()
    manifest = PluginManifest.model_validate(_manifest(package))
    assert _package(package, "!", "1.0.0").file(f"python/{package}/data/sample.csv")
    with pytest.raises(ValidationError):
        PluginPackage.build(manifest, {**_files(package, "!"), "python/other/x.py": b""})
    with pytest.raises(ValidationError):
        PluginPackage.build(manifest, {f"python/{package}/__init__.py": b""})
    worker_style = PluginManifest.model_validate(
        {k: v for k, v in _manifest(package).items() if k != "in_process"}
        | {"core_api": {"minimum": "1.0.0", "below": "2.0.0"}}
    )
    with pytest.raises(ValidationError):
        PluginPackage.build(worker_style, _files(package, "!"))


# -- which copy loads ------------------------------------------------------------------------


def test_bundled_switched_off_and_installed_newer_copies(tmp_path: Path) -> None:
    package = _name()
    roots = (tmp_path / "bundled",)
    _bundle(roots[0], package, "!")
    workspace = tmp_path / "ws"
    workspace.mkdir()
    chosen, _ = in_process.resolve(workspace, roots)
    assert [(s.origin, s.version) for s in chosen] == [("bundled", "1.0.0")]
    plugin_id = chosen[0].plugin_id
    in_process.set_bundled_off(workspace, plugin_id, True)
    assert in_process.resolve(workspace, roots)[0] == []
    in_process.set_bundled_off(workspace, plugin_id, False)
    config, layout = ready(tmp_path / "pc")
    manager = PluginManager(layout, _installed())
    result = manager.install(_package(package, "?", "1.1.0").to_bytes(), ORIGIN)
    assert result.status == "succeeded", result
    chosen, _ = in_process.resolve(layout.workspace_root, roots)
    assert [(s.origin, s.version) for s in chosen] == [("installed", "1.1.0")]
    assert manager.disable(plugin_id, ORIGIN).status == "succeeded"
    assert in_process.resolve(layout.workspace_root, roots)[0] == []


def test_a_plugin_for_a_newer_core_is_skipped_with_its_reason(tmp_path: Path) -> None:
    package = _name()
    folder = _bundle(tmp_path, package, "!")
    raw = _manifest(package, core_api={"minimum": "1.9.0", "below": "2.0.0"})
    (folder / in_process.MANIFEST_FILE).write_text(json.dumps(raw), encoding="utf-8")
    chosen, skipped = in_process.resolve(None, (tmp_path,))
    assert chosen == []
    assert [item.code for item in skipped] == ["plugin_core_api_incompatible"]


# -- loading --------------------------------------------------------------------------------


def test_a_broken_plugin_is_skipped_and_the_others_load(tmp_path: Path) -> None:
    good, bad = _name(), _name()
    _bundle(tmp_path, good, "+good")
    broken = _bundle(tmp_path, bad, "+bad")
    (broken / "python" / bad / "feature.py").write_text("raise ImportError('boom')\n")
    sources, _ = in_process.resolve(None, (tmp_path,))
    loaded = features.load_sources(sources)
    assert loaded.finish_answer("x", None) == "x+good"
    failure = features.failures()[f"{bad.replace('_', '-')}.feature"]
    assert failure.code == "plugin_load_failed" and "boom" in failure.message


def test_another_version_in_the_same_process_waits_for_a_restart(tmp_path: Path) -> None:
    package = _name()
    _bundle(tmp_path / "a", package, "+1")
    _bundle(tmp_path / "b", package, "+2", version="1.1.0")
    one, _ = in_process.resolve(None, (tmp_path / "a",))
    assert features.load_sources(one).finish_answer("x", None) == "x+1"
    two, _ = in_process.resolve(None, (tmp_path / "b",))
    assert list(features.load_sources(two)) == []
    assert "restart AEP" in features.failures()[two[0].plugin_id].message


def test_the_plugins_page_lists_a_bundled_feature_and_its_restart_state(tmp_path: Path) -> None:
    package = _name()
    roots = (tmp_path / "bundled",)
    _bundle(roots[0], package, "!")
    config, layout = ready(tmp_path / "pc")
    loaded: dict[str, str] = {}
    state = FeatureState(loaded=lambda: loaded, failures=lambda: {}, bundled_roots=lambda: roots)
    manager = PluginManager(layout, _installed(), features=state)
    plugin_id = f"{package.replace('_', '-')}.feature"
    shown = manager.snapshot().bundled
    assert [(s.plugin_id, s.state, s.restart_required) for s in shown] == [
        (plugin_id, "active", True)
    ]
    loaded[plugin_id] = "1.0.0"
    assert manager.snapshot().bundled[0].restart_required is False
    assert manager.disable(plugin_id, ORIGIN).status == "succeeded"
    status = manager.snapshot().bundled[0]
    assert (status.state, status.restart_required) == ("disabled", True)
    assert manager.uninstall(plugin_id, ORIGIN).status == "failed"
    assert manager.enable(plugin_id, ORIGIN).status == "succeeded"
    assert manager.snapshot().plugins == ()


def test_installing_a_new_version_changes_aep_only_after_a_restart(tmp_path: Path) -> None:
    # The owner's acceptance: AEP unchanged, install a newer feature plugin,
    # restart, and the new version runs (each start is its own process).
    package = _name()
    bundled_root = tmp_path / "bundled"
    _bundle(bundled_root, package, " v1")
    config, layout = ready(tmp_path / "pc")
    (tmp_path / "config.json").write_text(config.model_dump_json(), encoding="utf-8")

    def start() -> str:
        script = (
            "import sys; sys.path.insert(0, sys.argv[1])\n"
            "from pathlib import Path\n"
            "from host_runtime import features\n"
            "from host_runtime.contracts import CompanyHostConfiguration, HostLayout\n"
            "from host_runtime.host import build_runtime\n"
            "config = CompanyHostConfiguration.model_validate_json(Path(sys.argv[2]).read_text())\n"
            "with build_runtime(config, layout=HostLayout.under(config.workspace_root)):\n"
            "    print(features.active().finish_answer('answer', None))\n"
        )
        done = subprocess.run(
            [sys.executable, "-c", script, str(ROOT / "tests"), str(tmp_path / "config.json")],
            cwd=ROOT,
            env={
                **os.environ,
                "PYTHONPATH": str(ROOT / "src"),
                in_process.BUNDLED_ENV: str(bundled_root),
            },
            capture_output=True,
            text=True,
            timeout=600,
            check=False,
        )
        assert done.returncode == 0, done.stderr[-2000:]
        return done.stdout.strip().splitlines()[-1]

    assert start() == "answer v1"
    manager = PluginManager(layout, _installed())
    assert manager.install(_package(package, " v2", "1.1.0").to_bytes(), ORIGIN).status == (
        "succeeded"
    )
    assert start() == "answer v2"
    assert manager.disable(f"{package.replace('_', '-')}.feature", ORIGIN).status == "succeeded"
    assert start() == "answer"


def _installed() -> Any:
    from capabilities.runtime import InstalledCapabilities

    return InstalledCapabilities()


def test_python_caches_are_tolerated_cleared_and_nothing_else_is(tmp_path: Path) -> None:
    from plugins.package import PluginStageError, clear_bytecode, verify_staged

    package = _name()
    config, layout = ready(tmp_path / "pc")
    built = _package(package, "!", "1.0.0")
    manager = PluginManager(layout, _installed())
    assert manager.install(built.to_bytes(), ORIGIN).status == "succeeded"
    folder = (
        layout.workspace_root / "plugins/packages" / package.replace("_", "-") / "feature/1.0.0"
    )
    cache = folder / "python" / package / "__pycache__"
    cache.mkdir()
    (cache / "feature.cpython-312.pyc").write_bytes(b"planted")
    ws = layout.workspace_root
    assert verify_staged(folder, built.content_sha256, anchor=ws).manifest.in_process
    clear_bytecode(folder / "python")
    assert not cache.exists()
    (folder / "python" / package / "extra.py").write_text("x = 1\n")
    with pytest.raises(PluginStageError):
        verify_staged(folder, built.content_sha256, anchor=ws)


def test_the_bi_knowledge_plugin_builds_as_an_installable_in_process_package() -> None:
    import importlib.util

    from common.plugins import parse_plugin_package

    spec = importlib.util.spec_from_file_location(
        "build_bi_knowledge_plugin", ROOT / "scripts" / "build_bi_knowledge_plugin.py"
    )
    assert spec is not None and spec.loader is not None
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    payload = builder.package_bytes()
    assert payload == builder.package_bytes()  # deterministic
    package = parse_plugin_package(payload)
    assert package.manifest.plugin_id == "bi-knowledge.bi"
    assert package.manifest.in_process is not None
    assert package.manifest.in_process.entry == "aep_bi.feature"
    paths = {item.path for item in package.files}
    assert "python/aep_bi/host/bi_page.py" in paths
    assert "python/aep_bi/cards/samples/product-spec@1.0.0.json" in paths
    assert not any("__pycache__" in path for path in paths)


def test_the_llm_wiki_plugin_builds_deterministically_within_the_plugin_limits() -> None:
    import importlib.util

    from common import plugins

    spec = importlib.util.spec_from_file_location(
        "build_llm_wiki_plugin", ROOT / "scripts" / "build_llm_wiki_plugin.py"
    )
    assert spec is not None and spec.loader is not None
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    payload = builder.package_bytes()
    assert payload == builder.package_bytes()  # deterministic
    package = plugins.parse_plugin_package(payload)
    manifest = package.manifest
    assert manifest.plugin_id == "llm-wiki.wiki" and manifest.identity.version == "1.0.0"
    assert (manifest.core_api.minimum, manifest.core_api.below) == ("1.2.0", "2.0.0")
    assert manifest.in_process is not None and manifest.in_process.entry == "aep_wiki.feature"
    assert manifest.in_process.page_order == 50
    sizes = {item.path: item.size for item in package.files}
    assert len(sizes) <= plugins.MAX_FILES == 256
    assert sum(sizes.values()) <= plugins.MAX_TOTAL_FILE_BYTES == 6 * 1024 * 1024
    assert max(sizes.values()) <= plugins.MAX_FILE_BYTES == 2 * 1024 * 1024
    for path in (
        "python/aep_wiki/feature.py",
        "python/aep_wiki/host/wiki_page.py",
        "python/aep_wiki/knowledge/pipeline.py",
        "python/aep_wiki/knowledge/skill_guide/guide.zh-tw.md",
    ):
        assert path in sizes, path
    assert not any("__pycache__" in path for path in sizes)


def test_the_llm_wiki_plugin_is_bundled_and_loads_by_default() -> None:
    chosen, skipped = in_process.resolve(None)
    assert "llm-wiki.wiki" in {source.plugin_id for source in chosen}
    assert not [item for item in skipped if item.plugin_id == "llm-wiki.wiki"]
    assert "llm-wiki" in {feature.name for feature in features.active()}
