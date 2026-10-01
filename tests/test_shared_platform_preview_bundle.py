"""The Shared Platform is a separate, offline-installable Windows role."""

import hashlib
import json
import zipfile
from pathlib import Path

import pytest

from scripts.build_shared_platform_preview import (
    ARTEFACT_PREFIX,
    BUNDLE_NAME,
    REQUIRED_OPERATOR_GUIDES,
    build,
)

BUNDLED_WHEELS = (
    "annotated_types-0.1-py3-none-any.whl",
    "pydantic-2.0-py3-none-any.whl",
    "pydantic_core-2.0-cp312-cp312-win_amd64.whl",
    "typing_extensions-4.0-py3-none-any.whl",
    "typing_inspection-0.1-py3-none-any.whl",
)


def dependency_dir(root: Path, *, omit: str = "") -> Path:
    directory = root / "dependencies"
    directory.mkdir(parents=True, exist_ok=True)
    for name in BUNDLED_WHEELS:
        if not omit or not name.startswith(omit):
            (directory / name).write_bytes(name.encode())
    return directory


def test_shared_platform_bundle_is_reproducible_and_role_specific(tmp_path: Path) -> None:
    repo = Path(__file__).resolve().parents[1]
    wheel = tmp_path / "agentic_engineering_platform-0.1.0-py3-none-any.whl"
    wheel.write_bytes(b"platform-wheel")
    output = tmp_path / "output"
    revision = "d" * 40

    archive = build(
        repo=repo,
        platform_wheel=wheel,
        dependency_dir=dependency_dir(tmp_path),
        output_dir=output,
        revision=revision,
    )
    first_digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    rebuilt = build(
        repo=repo,
        platform_wheel=wheel,
        dependency_dir=dependency_dir(tmp_path),
        output_dir=output,
        revision=revision,
    )
    assert hashlib.sha256(rebuilt.read_bytes()).hexdigest() == first_digest

    with zipfile.ZipFile(archive) as bundle:
        prefix = f"{BUNDLE_NAME}/"
        names = set(bundle.namelist())
        manifest = json.loads(bundle.read(prefix + "manifest.json"))
        assert manifest["role"] == "shared_platform"
        assert manifest["source_revision"] == revision
        for name in (
            *REQUIRED_OPERATOR_GUIDES,
            "install.cmd",
            "install.ps1",
            "start-platform.cmd",
            "start-platform.ps1",
            "verify.cmd",
            "uninstall.cmd",
            "uninstall.ps1",
        ):
            assert prefix + name in names
        assert prefix + "wheels/" + wheel.name in names
        assert all("host.json" not in name for name in names)
        assert all("token" not in name.lower() for name in names)
        installer = bundle.read(prefix + "install.ps1").decode("utf-8")
        assert "--no-index" in installer
        assert "aep-host*" in installer
        assert "aep-platform.exe" in installer
        start_here = bundle.read(prefix + "START-HERE.md").decode("utf-8")
        assert "Shared Platform" in start_here
        assert "Personal Agent + Bridge" in start_here
        assert "Expected result" in start_here
        assert "Evidence" in start_here
        for item in manifest["files"]:
            content = bundle.read(prefix + item["path"])
            assert hashlib.sha256(content).hexdigest() == item["sha256"]


def test_shared_platform_bundle_refuses_an_incomplete_dependency_set(tmp_path: Path) -> None:
    repo = Path(__file__).resolve().parents[1]
    wheel = tmp_path / "agentic_engineering_platform-0.1.0-py3-none-any.whl"
    wheel.write_bytes(b"platform-wheel")

    with pytest.raises(ValueError, match="incomplete"):
        build(
            repo=repo,
            platform_wheel=wheel,
            dependency_dir=dependency_dir(tmp_path, omit="pydantic_core-"),
            output_dir=tmp_path / "output",
            revision="e" * 40,
        )


def test_source_distribution_includes_shared_platform_bundle_sources() -> None:
    manifest = (Path(__file__).resolve().parents[1] / "MANIFEST.in").read_text(encoding="utf-8")
    assert "recursive-include deploy/shared-platform-preview" in manifest
    assert "include scripts/build_shared_platform_preview.py" in manifest


def test_ci_uploads_the_shared_platform_as_a_separate_artifact() -> None:
    workflow = (
        Path(__file__).resolve().parents[1] / ".github" / "workflows" / "verify.yml"
    ).read_text(encoding="utf-8")
    assert f"name: {ARTEFACT_PREFIX}${{{{ github.sha }}}}" in workflow
    assert "path: dist/aep-shared-platform-preview-*.zip" in workflow
    assert "name: aep-windows-preview-${{ github.sha }}" in workflow
