"""Durable shared catalog without moving execution into the platform."""

import json
import sqlite3
from pathlib import Path

import pytest
from test_host_wiring import workflow_manifest
from test_platform_transport import SECRET, SKILL, WORKFLOW, Platform, package

from common.sync import CatalogRequest, SyncRequest
from control_plane.app import SharedPlatformConfiguration, application_from_config
from control_plane.cli import main
from control_plane.distribution import ControlError
from control_plane.registry_sqlite import RegistryStoreError, SqliteRegistry
from control_plane.service import ControlPlaneService


def workflow_bytes() -> bytes:
    return json.dumps(workflow_manifest()).encode("utf-8")


def test_packages_and_artifacts_survive_a_new_registry_process(tmp_path: Path) -> None:
    path = tmp_path / "registry.sqlite"
    content = workflow_bytes()
    published = package(WORKFLOW, "workflow", content)

    SqliteRegistry(path).publish(published, artifact=content)
    reopened = SqliteRegistry(path)

    assert reopened.discover() == (published,)
    assert reopened.get(WORKFLOW) == published
    assert reopened.plan(
        actor="engineer", bridge_id="bridge-company", requested=(WORKFLOW,)
    ).packages == (published,)
    assert published.metadata.package is not None
    assert reopened.artifacts[published.metadata.package.artifact_ref] == content


def test_duplicate_identity_is_refused_across_restarts(tmp_path: Path) -> None:
    path = tmp_path / "registry.sqlite"
    content = workflow_bytes()
    published = package(WORKFLOW, "workflow", content)
    SqliteRegistry(path).publish(published, artifact=content)

    with pytest.raises(ControlError, match="duplicate_package"):
        SqliteRegistry(path).publish(published, artifact=content)


def test_artifact_digest_is_checked_before_any_catalog_row_is_committed(tmp_path: Path) -> None:
    registry = SqliteRegistry(tmp_path / "registry.sqlite")
    published = package(WORKFLOW, "workflow", workflow_bytes())

    with pytest.raises(ControlError, match="artifact_hash_mismatch"):
        registry.publish(published, artifact=b"different bytes")

    assert registry.discover() == ()
    assert len(registry.artifacts) == 0


def test_namespace_filter_and_artifact_mapping_keep_existing_contracts(tmp_path: Path) -> None:
    registry = SqliteRegistry(tmp_path / "registry.sqlite")
    workflow = workflow_bytes()
    skill = b'{"kind":"skill"}'
    registry.publish(package(WORKFLOW, "workflow", workflow), artifact=workflow)
    registry.publish(package(SKILL, "skill", skill), artifact=skill)

    assert {item.metadata.identity for item in registry.discover(namespace="engineering")} == {
        WORKFLOW,
        SKILL,
    }
    assert registry.discover(namespace="another-team") == ()
    assert set(iter(registry.artifacts)) == {
        "registry://engineering/read-local-file/1.0.0",
        "registry://engineering/file-skill/1.0.0",
    }


def test_unknown_or_corrupt_schema_is_refused_before_serving(tmp_path: Path) -> None:
    path = tmp_path / "registry.sqlite"
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE registry_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        connection.execute("INSERT INTO registry_meta VALUES ('schema_version', '999')")

    with pytest.raises(RegistryStoreError, match="unsupported_schema"):
        SqliteRegistry(path)


def test_corrupt_package_record_is_never_served(tmp_path: Path) -> None:
    path = tmp_path / "registry.sqlite"
    SqliteRegistry(path)
    with sqlite3.connect(path) as connection:
        connection.execute(
            "INSERT INTO packages(namespace, name, version, payload) VALUES (?, ?, ?, ?)",
            ("engineering", "damaged", "1.0.0", "not-json"),
        )

    with pytest.raises(RegistryStoreError, match="corrupt_record"):
        SqliteRegistry(path).discover()


def test_cli_reports_an_unusable_registry_without_starting(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "registry.sqlite"
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE registry_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        connection.execute("INSERT INTO registry_meta VALUES ('schema_version', '999')")
    configuration = tmp_path / "platform.json"
    configuration.write_text(
        SharedPlatformConfiguration(
            administrators=("platform-admin",),
            registry_path=str(path.resolve()),
            control_port=0,
            member_port=0,
        ).model_dump_json(),
        encoding="utf-8",
    )

    assert main(("serve", "--config", str(configuration))) == 2
    assert (
        "shared platform configuration is unusable: unsupported_schema" in capsys.readouterr().err
    )


def test_deployable_composition_reopens_the_configured_registry(tmp_path: Path) -> None:
    path = tmp_path / "registry.sqlite"
    configuration = SharedPlatformConfiguration(
        administrators=("platform-admin",),
        registry_path=str(path.resolve()),
        control_port=0,
        member_port=0,
    )
    first, _ = application_from_config(configuration)
    try:
        assert isinstance(first.state.packages, SqliteRegistry)
        registry = first.state.packages
        assert first.state.artifacts is registry.artifacts
        content = workflow_bytes()
        registry.publish(package(WORKFLOW, "workflow", content), artifact=content)
    finally:
        first.stop()

    second, _ = application_from_config(configuration)
    try:
        assert second.state.packages.get(WORKFLOW) is not None
        assert len(second.state.artifacts) == 1
    finally:
        second.stop()


def test_existing_catalog_and_sync_service_use_reopened_durable_records(tmp_path: Path) -> None:
    platform = Platform()
    path = tmp_path / "registry.sqlite"
    stored = SqliteRegistry(path)
    for published in platform.packages.discover():
        artifact = published.metadata.package
        assert artifact is not None
        stored.publish(published, artifact=platform.artifacts[artifact.artifact_ref])

    reopened = SqliteRegistry(path)
    platform.authorization.packages = reopened
    platform.service = ControlPlaneService(
        enrollment=platform.enrollment,
        tokens=platform.tokens,
        packages=reopened,
        authorization=platform.authorization,
        control=platform.control,
        artifacts=reopened.artifacts,
    )

    catalog = platform.service.catalog(
        platform.company_token.grant.token_id,
        SECRET,
        CatalogRequest(),
    )
    assert {item.metadata.identity for item in catalog.packages} == {WORKFLOW, SKILL}

    synchronized = platform.service.synchronize(
        platform.company_token.grant.token_id,
        SECRET,
        SyncRequest(installed=()),
    )
    assert synchronized.plan is not None
    assert {item.metadata.identity for item in synchronized.plan.packages} == {WORKFLOW, SKILL}
    assert len(synchronized.artifacts) == 2


def test_registry_path_is_absolute_when_configured() -> None:
    with pytest.raises(Exception, match="registry_path must be absolute"):
        SharedPlatformConfiguration(
            administrators=("platform-admin",),
            registry_path="relative/registry.sqlite",
        )
