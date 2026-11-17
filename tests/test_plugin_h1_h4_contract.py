"""H1/H4 plugin contract extensions (owner consent 2026-11-15, FEATURE_PLUGIN_BI_OVERVIEW_PLAN):
`PluginData.reads` (declared existing-BI context) and `PluginCapability.expose_as_tool`
(a page-only read service). Old v1 wire bytes and digests stay exactly as they were."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError
from test_plugin_manifest import files, manifest, manifest_data

import common.plugins as plugins
from common.plugins import (
    CORE_PLUGIN_API_VERSION,
    PluginManifest,
    PluginPackage,
    core_api_supported,
    parse_plugin_package,
)

GOLDEN = Path(__file__).parent / "fixtures" / "plugins_v1" / "hello.aep-plugin.v1.json"
GOLDEN_DIGEST = "4bb06aca80372e299de4cf34e08411fab696d0d13a2cdb774ec67b8285956d2d"
NEW_API = {"minimum": "1.1.0", "below": "2.0.0"}


def service_data(**changes: Any) -> dict[str, Any]:
    """The test manifest with its read route's capability as a page-only service."""
    data = manifest_data(**{"core_api": NEW_API, **changes})
    data["capabilities"][0]["expose_as_tool"] = False
    return data


# -- old wire bytes and digests ---------------------------------------------------------------


def test_the_core_offers_plugin_api_1_1_and_old_ranges_still_include_it() -> None:
    assert CORE_PLUGIN_API_VERSION == "1.2.0"
    assert core_api_supported(manifest())  # an old {1.0.0, 2.0.0} manifest
    assert core_api_supported(PluginManifest.model_validate(manifest_data(core_api=NEW_API)))


def test_the_golden_v1_package_keeps_its_exact_bytes_and_digest() -> None:
    raw = GOLDEN.read_bytes()
    package = parse_plugin_package(raw)
    assert package.content_sha256 == GOLDEN_DIGEST
    assert PluginPackage.digest_of(package.manifest, package.files) == GOLDEN_DIGEST
    rebuilt = PluginPackage.build(package.manifest, {f.path: f.raw for f in package.files})
    assert rebuilt.content_sha256 == GOLDEN_DIGEST
    assert rebuilt.to_bytes() == raw  # byte for byte, as the v1 core wrote it
    assert package.manifest.data.reads == ()
    assert all(item.expose_as_tool for item in package.manifest.capabilities)


def test_only_the_new_keys_are_left_out_at_their_defaults() -> None:
    dumped = manifest().model_dump(mode="json")
    assert dumped["data"] == {"schema_version": 1}
    for capability in dumped["capabilities"]:
        assert "expose_as_tool" not in capability
    # Pre-existing defaults stay canonical, as they were in v1.
    assert dumped["requires"] == []
    assert dumped["runtime"]["health"] == {
        "startup_timeout_seconds": 15,
        "request_timeout_seconds": 30,
        "max_crashes": 3,
    }
    assert dumped["capabilities"][1]["inputs"][0]["required"] is True
    assert dumped["assets"][0]["switched_on"] is True
    unchanged = PluginPackage.build(manifest(), files())
    assert unchanged.content_sha256 == PluginPackage.build(manifest(), files()).content_sha256


# -- the new fields -----------------------------------------------------------------------------


def test_declared_bi_context_and_page_services_are_kept_on_the_wire() -> None:
    item = PluginManifest.model_validate(service_data(data={"schema_version": 1, "reads": ["bi"]}))
    assert item.data.reads == ("bi",)
    service = item.capability("hello-lab.echo")
    assert service.expose_as_tool is False
    assert item.capability("hello-lab.save_note").expose_as_tool is True
    assert [c.spec.name for c in item.tool_capabilities] == ["hello-lab.save_note"]
    assert [c.spec.name for c in item.page_services] == ["hello-lab.echo"]
    dumped = item.model_dump(mode="json")
    assert dumped["data"]["reads"] == ["bi"]
    assert dumped["capabilities"][0]["expose_as_tool"] is False
    assert "expose_as_tool" not in dumped["capabilities"][1]
    assert PluginManifest.model_validate_json(item.model_dump_json()) == item
    plain = PluginManifest.model_validate(manifest_data(core_api=NEW_API))
    assert PluginPackage.digest_of(item, ()) != PluginPackage.digest_of(plain, ())
    with pytest.raises(ValidationError):
        item.data.reads = ()  # type: ignore[misc]


@pytest.mark.parametrize(
    "reads",
    [["wiki"], ["bi", "bi"], ["BI"], "bi", [None]],
)
def test_only_the_bi_area_can_be_declared_once(reads: Any) -> None:
    with pytest.raises(ValidationError):
        PluginManifest.model_validate(
            manifest_data(core_api=NEW_API, data={"schema_version": 1, "reads": reads})
        )


def test_a_page_service_is_a_read_capability_that_a_route_uses() -> None:
    write = service_data()
    write["capabilities"][1]["expose_as_tool"] = False  # a write capability
    with pytest.raises(ValidationError):
        PluginManifest.model_validate(write)
    unrouted = service_data(routes=[], pages=[])
    with pytest.raises(ValidationError):
        PluginManifest.model_validate(unrouted)
    for value in ("false", 0, None):
        loose = service_data()
        loose["capabilities"][0]["expose_as_tool"] = value
        with pytest.raises(ValidationError):
            PluginManifest.model_validate(loose)


def test_new_features_require_plugin_api_1_1_as_their_minimum() -> None:
    with pytest.raises(ValidationError):
        PluginManifest.model_validate(service_data(core_api={"minimum": "1.0.0", "below": "2.0.0"}))
    with pytest.raises(ValidationError):
        PluginManifest.model_validate(
            manifest_data(data={"schema_version": 1, "reads": ["bi"]})  # minimum 1.0.0
        )
    assert plugins.FEATURE_API_MINIMUM == "1.1.0"
    item = PluginManifest.model_validate(service_data())
    assert core_api_supported(item)
    assert not core_api_supported(item, core="1.0.0")


def test_a_package_with_new_fields_round_trips_and_stays_closed() -> None:
    item = PluginManifest.model_validate(service_data(data={"schema_version": 1, "reads": ["bi"]}))
    package = PluginPackage.build(item, files())
    assert parse_plugin_package(package.to_bytes()) == package
    document = json.loads(package.to_bytes())
    document["manifest"]["data"]["reads_more"] = ["bi"]
    with pytest.raises(plugins.PluginContractError) as raised:
        parse_plugin_package(json.dumps(document).encode())
    assert raised.value.code == "plugin_package_invalid"
