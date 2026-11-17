"""Frozen v1 feature-plugin compatibility (golden fixture, core revision a0496ae0).

The package bytes and the workspace an actual v1 install produced are kept in
`tests/fixtures/plugins_v1/`. These tests prove that the current manager still
accepts the same package with the same content digest, and still restores the
materialized v1 workspace as active, with its ledger unchanged and its old
tools registered, without recalculating anything under a newer schema.
Synthetic data only.
"""

from __future__ import annotations

import base64
import hashlib
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from capabilities.runtime import InstalledCapabilities
from common.assets import AssetIdentity
from common.plugins import PluginOrigin, PluginReadRequest, parse_plugin_package
from host_runtime.contracts import HostLayout
from plugins.manager import PluginManager

FIXTURES = Path(__file__).parent / "fixtures" / "plugins_v1"
PACKAGE = FIXTURES / "hello.aep-plugin.v1.json"
WORKSPACE = FIXTURES / "golden-workspace.v1.json"

PLUGIN_ID = "demo-hello.fixture"
SOURCE_REVISION = "a0496ae0"
PACKAGE_SHA256 = "2fd27dd8799602e19ed29a7c79ad2f56469b01021a9618daab8d6f2642897413"
CONTENT_SHA256 = "4bb06aca80372e299de4cf34e08411fab696d0d13a2cdb774ec67b8285956d2d"
WORKSPACE_FIXTURE_SHA256 = "f61827911ebab7ddd3854f14fc215c7d12a26feec0f7555360958a31f809fa67"
LEDGER = "plugins/ledger.json"
LEDGER_SHA256 = "8d2e04df2e9e41161f34474aa88dd2a6b74c227fdb4039767dc812e9e501ad8a"
BUNDLE_LEDGER_SHA256 = "177cf46b67c1b8c297bfbbb705468ba34b665507bd8632bc0ed6e72b86407081"
DATA_MARKER_SHA256 = "94e5db162ac6c3c72643eebfd5be1e3e058c15f358a41dde67183ffff0b59065"
STAGED = "plugins/packages/demo-hello/fixture/1.0.0/"
ORIGIN = PluginOrigin(actor="fixture-owner", channel="compatibility-fixture")
TOOLS = ("read-summary", "write-note")


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _golden() -> dict[str, Any]:
    document: dict[str, Any] = json.loads(WORKSPACE.read_text(encoding="utf-8"))
    return document


def _materialize(root: Path) -> dict[str, str]:
    """Write the golden v1 workspace into `root`; returns path -> sha256."""
    written: dict[str, str] = {}
    for rel, item in _golden()["files"].items():
        data = base64.b64decode(item["content"], validate=True)
        assert _sha(data) == item["sha256"] and len(data) == item["size"], rel
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        written[rel] = item["sha256"]
    return written


def _identity(local: str) -> AssetIdentity:
    return AssetIdentity(namespace="demo-hello", name=local, version="1.0.0")


def _read_summary(manager: PluginManager) -> Any:
    request = PluginReadRequest(
        request_id="v1-read", plugin_id=PLUGIN_ID, version="1.0.0", route_id="summary"
    )
    return manager.call_read(request, timeout_seconds=15)


@pytest.fixture
def manager_in(tmp_path: Path) -> Iterator[Any]:
    opened: list[PluginManager] = []

    def build(root: Path) -> tuple[PluginManager, InstalledCapabilities]:
        installed = InstalledCapabilities()
        manager = PluginManager(HostLayout.under(root), installed)
        opened.append(manager)
        return manager, installed

    yield build
    for manager in opened:
        manager.close()


def test_the_golden_v1_bytes_are_frozen() -> None:
    raw = PACKAGE.read_bytes()
    assert _sha(raw) == PACKAGE_SHA256
    assert _sha(WORKSPACE.read_bytes()) == WORKSPACE_FIXTURE_SHA256
    golden = _golden()
    assert golden["source_revision"] == SOURCE_REVISION
    assert golden["plugin_id"] == PLUGIN_ID
    assert golden["package_sha256"] == PACKAGE_SHA256
    assert golden["content_sha256"] == CONTENT_SHA256
    files = golden["files"]
    assert files[LEDGER]["sha256"] == LEDGER_SHA256
    assert files["bundled-assets.json"]["sha256"] == BUNDLE_LEDGER_SHA256
    assert files["plugin-data/demo-hello/fixture/.aep-data.json"]["sha256"] == DATA_MARKER_SHA256
    assert files[STAGED + "package.json"]["sha256"] == PACKAGE_SHA256
    assert {rel for rel in files if rel.startswith(STAGED + "worker/")} == {
        STAGED + "worker/aep_plugin_demo_hello/__init__.py",
        STAGED + "worker/aep_plugin_demo_hello/worker.py",
    }
    for item in files.values():
        assert _sha(base64.b64decode(item["content"], validate=True)) == item["sha256"]


def test_the_golden_workspace_holds_no_absolute_paths() -> None:
    for rel, item in _golden()["files"].items():
        assert not Path(rel).is_absolute() and ".." not in Path(rel).parts, rel
        text = base64.b64decode(item["content"]).decode("utf-8", "replace")
        for needle in ("C:\\", "C:/", "C:\\\\", "/TEMP/", "\\TEMP\\"):
            assert needle not in text, (rel, needle)


def test_the_v1_package_parses_and_installs_with_the_same_content_digest(
    tmp_path: Path, manager_in: Any
) -> None:
    raw = PACKAGE.read_bytes()
    assert parse_plugin_package(raw).content_sha256 == CONTENT_SHA256
    manager, installed = manager_in(tmp_path / "fresh")
    result = manager.install(raw, ORIGIN)
    assert result.status == "succeeded", result.failure
    assert result.plugin is not None
    assert (result.plugin.state, result.plugin.content_sha256) == ("active", CONTENT_SHA256)
    for local in TOOLS:
        assert installed.get(_identity(local)) is not None
    read = _read_summary(manager)
    assert read.status == "succeeded" and read.data == {"count": 0, "items": []}


def test_the_golden_v1_workspace_restores_active_with_its_old_tools(
    tmp_path: Path, manager_in: Any
) -> None:
    root = tmp_path / "restored"
    written = _materialize(root)
    manager, installed = manager_in(root)
    manager.restore()
    status = manager.snapshot().get(PLUGIN_ID)
    assert status is not None, "the v1 ledger was not readable by the current manager"
    assert status.state == "active", status.failure
    assert status.content_sha256 == CONTENT_SHA256
    assert status.installed_by.channel == "compatibility-fixture"
    assert _sha((root / LEDGER).read_bytes()) == LEDGER_SHA256
    for local in TOOLS:
        binding = installed.get(_identity(local))
        assert binding is not None, local
        policy = binding.spec.policy
        assert policy.status == "pending" and policy.reviewer is None and not policy.evidence
    read = _read_summary(manager)
    assert read.status == "succeeded" and read.data == {"count": 0, "items": []}
    changed = {
        rel: digest
        for rel, digest in written.items()
        if rel != LEDGER and _sha((root / rel).read_bytes()) != digest
    }
    assert changed == {}, "restore rewrote golden files"
