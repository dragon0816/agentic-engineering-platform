"""Make a Windows release for colleagues in one command (owner, 2026-10-13).

    .venv\\Scripts\\python.exe scripts\\release_windows.py [--publish-dir <shared folder>]

Steps, each of which stops the release when it fails:

1. The working tree must have no uncommitted changes to tracked files: the bundle is
   built from the committed revision (`git archive HEAD`), so what colleagues install
   is exactly what the revision names.
2. Verification: ruff, mypy and the test suite (`--quick` skips the tests,
   `--skip-checks` skips all three; use either only for a re-build).
3. The platform wheel is built from that export; the dependency wheels are
   downloaded for 64-bit Windows Python 3.12 (the same list the CI build uses).
4. `scripts/build_windows_preview.py` makes the hash-verified offline bundle.
5. A release folder `dist/releases/<date>-<revision>/` gets the zip, its SHA-256,
   release notes (commits since the previous release) and the installation manual.
6. `--publish-dir` copies that folder to a shared location (never deletes anything).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from scripts.build_windows_preview import BUNDLE_NAME, build  # noqa: E402

#: The dependency wheels the bundle carries; `.github/workflows/verify.yml` downloads
#: the same list, and a test holds the two together.
DEPENDENCIES = (
    "pydantic>=2.10,<3", "tzdata>=2025.2,<2028", "openpyxl>=3.1,<4", "pypdf>=6,<7",
    "pywin32>=306", "matplotlib>=3.11,<4", "numpy>=1.26,<2", "contourpy>=1.3,<1.4",
)
MANUAL = "INSTALL.zh-TW.md"
LATEST = "latest.json"


class ReleaseError(Exception):
    pass


def run(command: list[str], cwd: Path = REPO) -> str:
    print("  $ " + " ".join(command), flush=True)
    done = subprocess.run(command, cwd=cwd, text=True, encoding="utf-8", errors="replace",
                          capture_output=True)
    if done.returncode != 0:
        tail = "\n".join((done.stdout + done.stderr).strip().splitlines()[-25:])
        raise ReleaseError(f"failed: {' '.join(command[:4])}\n{tail}")
    return done.stdout


def git(*args: str) -> str:
    return run(["git", *args]).strip()


def previous_revision(releases: Path) -> str | None:
    latest = releases / LATEST
    if not latest.is_file():
        return None
    revision = json.loads(latest.read_text(encoding="utf-8")).get("revision")
    return revision if isinstance(revision, str) else None


def release_notes(*, release: str, revision: str, previous: str | None,
                  commits: list[str], created: str) -> str:
    lines = [
        f"# AEP Windows release {release}", "",
        f"- Source revision: `{revision}`",
        f"- Built: {created}",
        f"- Previous release: `{previous}`" if previous else "- Previous release: (first release)",
        "", "## How to install or update", "",
        "- First installation: unzip to a short path such as `C:\\aep`, run `install.cmd`.",
        "- Update: close Agent Web, unzip the new release, run `update.cmd` (settings kept).",
        f"- Details: `{MANUAL}` in this folder and inside the zip.",
        "", "## Changes since the previous release", "",
    ]
    lines += [f"- {commit}" for commit in commits] or ["- (no new commits)"]
    return "\n".join(lines) + "\n"


def sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(block)
    return hasher.hexdigest()


def verify(quick: bool) -> None:
    python = sys.executable
    print("Verifying ...", flush=True)
    run([python, "-m", "ruff", "check", "src", "tests"])
    run([python, "-m", "mypy", "src"])
    if not quick:
        run([python, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-x"])


def wheels(work: Path, revision: str) -> tuple[Path, Path]:
    """The platform wheel built from the committed revision, and the dependencies."""
    python = sys.executable
    source = work / "source"
    archive = work / "source.zip"
    print("Exporting the committed revision ...", flush=True)
    git("archive", "--format=zip", "-o", str(archive), revision)
    with zipfile.ZipFile(archive) as bundle:
        bundle.extractall(source)
    print("Building the platform wheel ...", flush=True)
    run([python, "-m", "pip", "wheel", "--no-deps", "--no-build-isolation",
         "--disable-pip-version-check", "-w", str(work / "wheel"), str(source)])
    built = sorted((work / "wheel").glob("agentic_engineering_platform-*.whl"))
    if len(built) != 1:
        raise ReleaseError("the platform wheel was not built")
    print("Downloading dependency wheels for 64-bit Windows Python 3.12 ...", flush=True)
    run([python, "-m", "pip", "download", "--disable-pip-version-check",
         "--only-binary=:all:", "--platform", "win_amd64", "--python-version", "3.12",
         "--implementation", "cp", "--dest", str(work / "dependencies"), *DEPENDENCIES])
    return built[0], work / "dependencies"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--output-dir", type=Path, default=REPO / "dist" / "releases")
    parser.add_argument("--publish-dir", type=Path,
                        help="also copy the release folder here, e.g. a shared OneDrive folder")
    parser.add_argument("--quick", action="store_true", help="skip the test suite")
    parser.add_argument("--skip-checks", action="store_true", help="skip ruff, mypy and tests")
    parser.add_argument("--allow-dirty", action="store_true",
                        help="release although tracked files have uncommitted changes "
                             "(they are NOT in the bundle)")
    parser.add_argument("--notes-since", help="list commits since this revision")
    args = parser.parse_args()
    try:
        revision = git("rev-parse", "HEAD")
        dirty = git("status", "--porcelain", "--untracked-files=no")
        if dirty and not args.allow_dirty:
            raise ReleaseError("commit or stash these changes first; the bundle is built "
                               "from the committed revision:\n" + dirty)
        if not args.skip_checks:
            verify(args.quick)
        releases = args.output_dir.resolve()
        created = datetime.now().astimezone()
        release = f"{created:%Y%m%d-%H%M}-{revision[:8]}"
        folder = releases / release
        folder.mkdir(parents=True, exist_ok=False)
        with tempfile.TemporaryDirectory() as temporary:
            platform_wheel, dependencies = wheels(Path(temporary), revision)
            print("Building the offline bundle ...", flush=True)
            archive = build(repo=REPO, platform_wheel=platform_wheel,
                            dependency_dir=dependencies, output_dir=folder, revision=revision)
        digest = sha256(archive)
        (folder / "SHA256SUMS.txt").write_text(f"{digest}  {archive.name}\n", encoding="utf-8")
        previous = args.notes_since or previous_revision(releases)
        log_range = f"{previous}..{revision}" if previous else revision
        commits = git("log", "--no-merges", "--format=%h %s", *(
            [log_range] if previous else ["-30", revision])).splitlines()
        (folder / "RELEASE_NOTES.md").write_text(release_notes(
            release=release, revision=revision, previous=previous, commits=commits,
            created=created.isoformat(timespec="minutes")), encoding="utf-8")
        shutil.copy2(REPO / "deploy" / "windows-preview" / MANUAL, folder / MANUAL)
        (releases / LATEST).write_text(json.dumps({
            "release": release, "revision": revision, "zip": archive.name, "sha256": digest,
            "created": created.isoformat(timespec="seconds")}, indent=2) + "\n",
            encoding="utf-8")
        published = None
        if args.publish_dir is not None:
            published = args.publish_dir / release
            shutil.copytree(folder, published)
    except ReleaseError as error:
        print(f"Release stopped: {error}", file=sys.stderr)
        return 1
    print(f"\nRelease {release} ({BUNDLE_NAME}) is ready:\n  {folder}")
    print(f"  {archive.name}  sha256 {digest}")
    if published is not None:
        print(f"Copied to {published}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
