"""Build a credential-free, hash-verified Windows offline preview bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

#: Short on purpose. Windows refuses a path of 260 characters or more, and
#: this bundle is downloaded as a CI artefact and extracted twice before it is
#: run: once for the artefact folder, once for the bundle's own. The former
#: name cost 51 characters of that budget and pushed the two longest wheel
#: names over the limit in an ordinary Downloads folder, where Explorer left
#: them out silently and the installer reported a missing file.
BUNDLE_NAME = "aep-windows-preview-0.1.0"
#: The longest path any file in the bundle may need once it is extracted the
#: way people actually get it. Windows allows 259.
MAX_EXTRACTED_PATH = 259
#: The artefact name in `.github/workflows/verify.yml`, which GitHub turns
#: into a folder around the zip when the artefact is downloaded. Renaming the
#: artefact there without changing this would make the guard below under-count
#: and re-open the incident it exists to prevent, so a test reads the workflow
#: and holds the two together.
ARTEFACT_PREFIX = "aep-windows-preview-"
TEXT_SUFFIXES = {".cmd", ".json", ".md", ".ps1", ".txt"}
SECRET_ASSIGNMENT = re.compile(
    r"(?:password|api[_-]?key|access[_-]?token|secret[_-]?value)\s*[=:]\s*(?:\"[^\"]+\"|'[^']+'|\S+)",
    re.IGNORECASE,
)
#: Every wheel the installed extras need. The bundle is offline, so a
#: missing one is a failed install on a company computer rather than a
#: download, and the builder refuses to produce a bundle that would do that.
REQUIRED_DEPENDENCIES = (
    "annotated_types-",
    "pydantic-",
    "pydantic_core-",
    "typing_extensions-",
    "typing_inspection-",
    # The `excel` extra: reading the weekly workbook without Excel.
    "openpyxl-",
    "et_xmlfile-",
    # The `windows` extra: writing it through Excel.
    "pywin32-",
)
#: What `install.ps1` installs the platform wheel with.
BUNDLED_EXTRAS = ("excel", "windows")


def worst_case_path(relative: str) -> int:
    """How long a file's path becomes once the bundle has been downloaded and
    extracted the way people actually get it.

    Measured from the install that failed on 2026-09-23: a Windows Downloads
    folder, the artefact folder GitHub wraps the zip in (its name and a
    40-character commit), the folder an extraction makes from the zip's own
    name, and the bundle's own root inside it. Two of the wheels needed more
    than 259 characters there, Explorer left them out without saying so, and
    the installer could only report a missing file.
    """
    downloads = len(r"C:\Users\employee.name\Downloads") + 1
    artefact = len(ARTEFACT_PREFIX) + 40 + 1
    zip_folder = len(BUNDLE_NAME) + 1 + 12 + 1
    bundle_root = len(BUNDLE_NAME) + 1
    return downloads + artefact + zip_folder + bundle_root + len(relative)


def digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(block)
    return hasher.hexdigest()


def source_revision(repo: Path) -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=repo, text=True, encoding="utf-8"
    ).strip()


def build(
    *,
    repo: Path,
    platform_wheel: Path,
    dependency_dir: Path,
    output_dir: Path,
    revision: str,
) -> Path:
    if not platform_wheel.is_file() or platform_wheel.suffix != ".whl":
        raise ValueError("platform wheel is missing")
    dependencies = sorted(dependency_dir.glob("*.whl"))
    names = tuple(item.name.lower() for item in dependencies)
    missing = [
        prefix for prefix in REQUIRED_DEPENDENCIES if not any(n.startswith(prefix) for n in names)
    ]
    if missing:
        raise ValueError("dependency wheel directory is incomplete")
    template = repo / "deploy" / "windows-preview"
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary) / BUNDLE_NAME
        shutil.copytree(template, root)
        wheels = root / "wheels"
        wheels.mkdir()
        shutil.copy2(platform_wheel, wheels / platform_wheel.name)
        for item in dependencies:
            shutil.copy2(item, wheels / item.name)
        payload = sorted(path for path in root.rglob("*") if path.is_file())
        for path in payload:
            if path.suffix.lower() in TEXT_SUFFIXES:
                text = path.read_text(encoding="utf-8")
                if SECRET_ASSIGNMENT.search(text):
                    raise ValueError(f"credential-like assignment found in {path.name}")
        relatives = [path.relative_to(root).as_posix() for path in payload]
        # A name nobody can extract is a bundle nobody can install, and the
        # failure surfaces on the company computer rather than here. Name the
        # file and its length: whoever sees this has to know which name to
        # shorten and by how much.
        too_long = [
            (relative, worst_case_path(relative))
            for relative in relatives
            if worst_case_path(relative) > MAX_EXTRACTED_PATH
        ]
        if too_long:
            worst, length = max(too_long, key=lambda item: item[1])
            raise ValueError(
                f"{worst} would need a {length} character path once the bundle is "
                f"downloaded and extracted, and Windows allows {MAX_EXTRACTED_PATH}"
            )
        files = [
            {
                "path": relative,
                "sha256": digest(path),
                "size": path.stat().st_size,
            }
            for path, relative in zip(payload, relatives, strict=True)
        ]
        manifest = {
            "schema_version": "1",
            "bundle": BUNDLE_NAME,
            "source_revision": revision,
            "python_minor": "3.12",
            "platform": "windows-amd64",
            "files": files,
        }
        (root / "manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        output_dir.mkdir(parents=True, exist_ok=True)
        archive = output_dir / f"{BUNDLE_NAME}-{revision[:12]}.zip"
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as target:
            for path in sorted(item for item in root.rglob("*") if item.is_file()):
                relative = Path(BUNDLE_NAME) / path.relative_to(root)
                info = zipfile.ZipInfo(relative.as_posix(), date_time=(2026, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o644 << 16
                target.writestr(info, path.read_bytes())
    return archive


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--wheel", required=True, type=Path)
    parser.add_argument("--dependency-dir", required=True, type=Path)
    parser.add_argument("--output-dir", default=Path("dist"), type=Path)
    parser.add_argument("--source-revision")
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    archive = build(
        repo=repo,
        platform_wheel=args.wheel.resolve(),
        dependency_dir=args.dependency_dir.resolve(),
        output_dir=args.output_dir.resolve(),
        revision=args.source_revision or source_revision(repo),
    )
    print(archive)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
