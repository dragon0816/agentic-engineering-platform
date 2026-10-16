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
#: The Hermes skill pack (docs/phases/HERMES_SKILL_PACK.md): the bundle's
#: `hermes/` holds its manifests, index and NOTICE, and its coding-agent skill
#: folders under `hermes/agent/`. `install.ps1` installs it switched off.
HERMES_PACK = Path("packages") / "hermes-skill-pack"
BUNDLE_HERMES = "hermes"
#: The LLM gateway (docs/phases/LLM_GATEWAY.md): its exact dependency lock,
#: copied with the template as `gateway/requirements.txt`, and every wheel it
#: names in `wheels-gateway/`, installed by `install.ps1` into its own venv.
GATEWAY_LOCK = Path("gateway") / "requirements.txt"
BUNDLE_GATEWAY_WHEELS = "wheels-gateway"
#: Documented placeholders in the Hermes pack that look like an assignment
#: to the credential scan, accepted one by one (file, exact text). Anything
#: else that looks like a credential still stops the build.
ALLOWED_PLACEHOLDERS = frozenset(
    {
        ("hermes/agent/hermes-airtable/SKILL.md", "API_KEY=pat_your_token_here"),
        ("hermes/agent/hermes-gif-search/SKILL.md", "API_KEY=your_key_here"),
        ("hermes/agent/hermes-notion/SKILL.md", "API_KEY=ntn_your_key_here"),
        ("hermes/agent/hermes-github/references/auth.md", "Password: <paste"),
        # JSON text: `\n` here is the two characters of an escaped line end.
        ("hermes/manifests/hermes__airtable__1.1.0.json", r"API_KEY=[redacted]\n"),
        ("hermes/manifests/hermes__gif-search__1.1.0.json", r"API_KEY=[redacted]\n```\n\nGet"),
        ("hermes/manifests/hermes__notion__2.0.0.json", r"API_KEY=[redacted]\n"),
    }
)
#: Every wheel the installed extras need. The bundle is offline, so a
#: missing one is a failed install on a company computer rather than a
#: download, and the builder refuses to produce a bundle that would do that.
REQUIRED_DEPENDENCIES = (
    "annotated_types-",
    "pydantic-",
    "pydantic_core-",
    "tzdata-",
    "typing_extensions-",
    "typing_inspection-",
    # The `excel` extra: reading the weekly workbook without Excel.
    "openpyxl-",
    "et_xmlfile-",
    # The `office` extra: controlled SOP PDF extraction.
    "pypdf-",
    # The `windows` extra: writing it through Excel.
    "pywin32-",
    # The `weekly-mail` extra: the source W2's composite chart and its wheels.
    "matplotlib-",
    "numpy-",
    "pillow-",
    "contourpy-",
    "cycler-",
    "fonttools-",
    "kiwisolver-",
    "packaging-",
    "pyparsing-",
    "python_dateutil-",
    "six-",
)
#: What `install.ps1` installs the platform wheel with.
BUNDLED_EXTRAS = ("excel", "windows", "weekly-mail")
#: These operator guides are part of the installable product.  A release that
#: cannot tell its tester how to install and validate it is not a usable bundle.
REQUIRED_OPERATOR_GUIDES = ("START-HERE.md", "README.md", "INSTALL.zh-TW.md")


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


def copy_hermes_pack(pack: Path, target: Path) -> None:
    """The pack's manifests, `pack.json` and `NOTICE.md`, and its skill
    folders flattened to `agent/<folder>` (shorter paths in the bundle)."""
    if not (pack / "pack.json").is_file():
        raise ValueError("the Hermes skill pack is missing")
    target.mkdir(parents=True)
    shutil.copy2(pack / "pack.json", target / "pack.json")
    shutil.copy2(pack / "NOTICE.md", target / "NOTICE.md")
    shutil.copytree(pack / "manifests", target / "manifests")
    shutil.copytree(
        pack / "skills" / "vendor",
        target / "agent",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )


def locked_requirements(lock: Path) -> list[tuple[str, str]]:
    """(name, version) for every `name==version` line of the gateway lock."""
    pinned = []
    for raw in lock.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        name, separator, version = line.partition("==")
        if not separator or not name.strip() or not version.strip() or "[" in name:
            raise ValueError(f"the gateway lock pins every package exactly: {line}")
        pinned.append((name.strip(), version.strip()))
    return pinned


def wheel_prefix(name: str, version: str) -> str:
    """How a wheel file for `name==version` starts (PEP 427 / 503 spelling)."""
    return re.sub(r"[-_.]+", "_", name).lower() + "-" + version.lower() + "-"


def gateway_wheels(lock: Path, wheel_dir: Path) -> list[Path]:
    """Exactly one wheel per locked package; a missing one stops the build
    (the bundle installs offline, so it would stop the install instead)."""
    available = sorted(wheel_dir.glob("*.whl"))
    chosen: list[Path] = []
    missing: list[str] = []
    for name, version in locked_requirements(lock):
        prefix = wheel_prefix(name, version)
        found = [item for item in available if item.name.lower().startswith(prefix)]
        if not found:
            missing.append(f"{name}=={version}")
        else:
            chosen.append(found[0])
    if missing:
        raise ValueError("gateway wheel directory is incomplete: " + ", ".join(missing))
    return chosen


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
    gateway_dependency_dir: Path,
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
    missing_guides = [name for name in REQUIRED_OPERATOR_GUIDES if not (template / name).is_file()]
    if missing_guides:
        raise ValueError("Windows preview operator guide is missing: " + ", ".join(missing_guides))
    locked_gateway = gateway_wheels(template / GATEWAY_LOCK, gateway_dependency_dir)
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary) / BUNDLE_NAME
        shutil.copytree(template, root)
        copy_hermes_pack(repo / HERMES_PACK, root / BUNDLE_HERMES)
        wheels = root / "wheels"
        wheels.mkdir()
        shutil.copy2(platform_wheel, wheels / platform_wheel.name)
        for item in dependencies:
            shutil.copy2(item, wheels / item.name)
        gateway = root / BUNDLE_GATEWAY_WHEELS
        gateway.mkdir()
        for item in locked_gateway:
            shutil.copy2(item, gateway / item.name)
        payload = sorted(path for path in root.rglob("*") if path.is_file())
        for path in payload:
            if path.suffix.lower() in TEXT_SUFFIXES:
                text = path.read_text(encoding="utf-8")
                in_bundle = path.relative_to(root).as_posix()
                for found in SECRET_ASSIGNMENT.finditer(text):
                    if (in_bundle, found.group(0)) not in ALLOWED_PLACEHOLDERS:
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
    parser.add_argument(
        "--gateway-wheel-dir",
        required=True,
        type=Path,
        help="the wheels of deploy/windows-preview/gateway/requirements.txt",
    )
    parser.add_argument("--output-dir", default=Path("dist"), type=Path)
    parser.add_argument("--source-revision")
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    archive = build(
        repo=repo,
        platform_wheel=args.wheel.resolve(),
        dependency_dir=args.dependency_dir.resolve(),
        gateway_dependency_dir=args.gateway_wheel_dir.resolve(),
        output_dir=args.output_dir.resolve(),
        revision=args.source_revision or source_revision(repo),
    )
    print(archive)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
