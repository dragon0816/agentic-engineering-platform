"""Offline bundle integrity and reproducibility checks."""

import hashlib
import json
import zipfile
from pathlib import Path

import pytest

from scripts.build_windows_preview import BUNDLE_NAME, BUNDLED_EXTRAS, build

#: One wheel per name the builder insists on, named as pip names them.
BUNDLED_WHEELS = (
    "annotated_types-0.1-py3-none-any.whl",
    "pydantic-2.0-py3-none-any.whl",
    "pydantic_core-2.0-cp312-cp312-win_amd64.whl",
    "typing_extensions-4.0-py3-none-any.whl",
    "typing_inspection-0.1-py3-none-any.whl",
    "openpyxl-3.1.5-py2.py3-none-any.whl",
    "et_xmlfile-2.0.0-py3-none-any.whl",
    "pywin32-312-cp312-cp312-win_amd64.whl",
)


def dependency_dir(root: Path, *, omit: str = "") -> Path:
    directory = root / "dependencies"
    directory.mkdir(parents=True, exist_ok=True)
    for name in BUNDLED_WHEELS:
        if omit and name.startswith(omit):
            continue
        (directory / name).write_bytes(name.encode())
    return directory


def test_builder_emits_reproducible_closed_manifest(tmp_path: Path) -> None:
    repo = Path(__file__).resolve().parents[1]
    platform_wheel = tmp_path / "agentic_engineering_platform-0.1.0-py3-none-any.whl"
    platform_wheel.write_bytes(b"platform-wheel")
    dependencies = dependency_dir(tmp_path)
    output = tmp_path / "output"
    revision = "a" * 40
    archive = build(
        repo=repo,
        platform_wheel=platform_wheel,
        dependency_dir=dependencies,
        output_dir=output,
        revision=revision,
    )
    first_digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    rebuilt = build(
        repo=repo,
        platform_wheel=platform_wheel,
        dependency_dir=dependencies,
        output_dir=output,
        revision=revision,
    )
    assert hashlib.sha256(rebuilt.read_bytes()).hexdigest() == first_digest
    with zipfile.ZipFile(archive) as bundle:
        prefix = f"{BUNDLE_NAME}/"
        names = set(bundle.namelist())
        manifest = json.loads(bundle.read(prefix + "manifest.json"))
        assert manifest["python_minor"] == "3.12"
        assert manifest["platform"] == "windows-amd64"
        assert prefix + "install.ps1" in names
        assert prefix + "uninstall.ps1" in names
        assert prefix + "wheels/" + platform_wheel.name in names
        assert all("config" not in name.lower() for name in names)
        assert all("token" not in name.lower() for name in names)
        # The extras the installer asks for are carried, not fetched: the
        # bundle installs with --no-index on a machine whose pip may point
        # at a company index, or at nothing.
        for wheel in BUNDLED_WHEELS:
            assert prefix + "wheels/" + wheel in names
        installer = bundle.read(prefix + "install.ps1").decode("utf-8")
        install_line = next(line for line in installer.splitlines() if "-m pip install" in line)
        assert "--no-index" in install_line
        extras = ",".join(BUNDLED_EXTRAS)
        assert f'"agentic-engineering-platform[{extras}]"' in install_line
        for item in manifest["files"]:
            content = bundle.read(prefix + item["path"])
            assert hashlib.sha256(content).hexdigest() == item["sha256"]


def test_a_bundle_missing_a_wheel_its_extras_need_is_refused(tmp_path: Path) -> None:
    """An incomplete bundle is a failed install on a company computer, where
    there is no index to fall back on, so it is refused where it is built."""
    repo = Path(__file__).resolve().parents[1]
    platform_wheel = tmp_path / "agentic_engineering_platform-0.1.0-py3-none-any.whl"
    platform_wheel.write_bytes(b"platform-wheel")
    for omitted in ("openpyxl-", "pywin32-", "et_xmlfile-", "pydantic_core-"):
        with pytest.raises(ValueError, match="incomplete"):
            build(
                repo=repo,
                platform_wheel=platform_wheel,
                dependency_dir=dependency_dir(tmp_path / omitted, omit=omitted),
                output_dir=tmp_path / "output",
                revision="b" * 40,
            )
