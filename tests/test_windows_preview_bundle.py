"""Offline bundle integrity and reproducibility checks."""

import hashlib
import json
import zipfile
from pathlib import Path

from scripts.build_windows_preview import BUNDLE_NAME, build


def test_builder_emits_reproducible_closed_manifest(tmp_path: Path) -> None:
    repo = Path(__file__).resolve().parents[1]
    platform_wheel = tmp_path / "agentic_engineering_platform-0.1.0-py3-none-any.whl"
    platform_wheel.write_bytes(b"platform-wheel")
    dependencies = tmp_path / "dependencies"
    dependencies.mkdir()
    for name in (
        "annotated_types-0.1-py3-none-any.whl",
        "pydantic-2.0-py3-none-any.whl",
        "pydantic_core-2.0-cp312-cp312-win_amd64.whl",
        "typing_extensions-4.0-py3-none-any.whl",
        "typing_inspection-0.1-py3-none-any.whl",
    ):
        (dependencies / name).write_bytes(name.encode())
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
        for item in manifest["files"]:
            content = bundle.read(prefix + item["path"])
            assert hashlib.sha256(content).hexdigest() == item["sha256"]
