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

BUNDLE_NAME = "agentic-engineering-platform-windows-preview-0.1.0"
TEXT_SUFFIXES = {".cmd", ".json", ".md", ".ps1", ".txt"}
SECRET_ASSIGNMENT = re.compile(
    r"(?:password|api[_-]?key|access[_-]?token|secret[_-]?value)\s*[=:]\s*(?:\"[^\"]+\"|'[^']+'|\S+)",
    re.IGNORECASE,
)
REQUIRED_DEPENDENCIES = (
    "annotated_types-",
    "pydantic-",
    "pydantic_core-",
    "typing_extensions-",
    "typing_inspection-",
)


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
        files = [
            {
                "path": path.relative_to(root).as_posix(),
                "sha256": digest(path),
                "size": path.stat().st_size,
            }
            for path in payload
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
