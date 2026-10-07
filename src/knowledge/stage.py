"""Copy a legacy Vault's queryable corpus before adopting its provenance.

This is a local query staging step, not a full original-document backup or a
publication decision. Source files are read only. The copied Raw is adopted by
the existing migration adapter, which never rewrites it.
"""

from __future__ import annotations

import hashlib
import os
import shutil
from argparse import ArgumentParser
from collections.abc import Sequence
from datetime import date
from pathlib import Path
from uuid import uuid4

from pydantic import Field

from common.base import Contract, Sha256, Text
from common.filesystem import publish_directory
from knowledge.conflicts import DECISIONS_HEADER
from knowledge.evolution import decision_digest, knowledge_digest, raw_digest
from knowledge.migrate import adopt
from knowledge.vault import Vault


class LegacyQueryStageReport(Contract):
    vault_root: Text
    raw_files: int = Field(ge=0)
    wiki_pages: int = Field(ge=0)
    adopted_raw: int = Field(ge=0)
    migrated_pages: int = Field(ge=0)
    unresolved_pages: int = Field(ge=0)
    originals_copied: bool = False
    raw_sha256: Sha256
    decisions_sha256: Sha256
    content_sha256: Sha256


def _io_path(path: Path) -> Path:
    """Use Windows' extended path spelling for long source-page names."""
    return Path("\\\\?\\" + str(path)) if os.name == "nt" else path


def _files_in(source: Path, area: str) -> tuple[Path, ...]:
    root = source / area
    if not root.is_dir() or root.is_symlink():
        raise ValueError(f"legacy Vault is missing a safe {area}/ directory")
    found: list[Path] = []
    for current, directories, files in os.walk(root, followlinks=False):
        for name in directories:
            path = Path(current) / name
            checked = _io_path(path)
            if checked.is_symlink() or (hasattr(checked, "is_junction") and checked.is_junction()):
                raise ValueError(f"legacy Vault {area}/ contains a directory link")
        for name in files:
            path = Path(current) / name
            checked = _io_path(path)
            if checked.is_symlink() or not checked.is_file():
                raise ValueError(f"legacy Vault {area}/ contains a non-file link")
            if not checked.resolve().is_relative_to(_io_path(source).resolve()):
                raise ValueError(f"legacy Vault {area}/ contains an escaping file")
            found.append(path)
    return tuple(sorted(found))


def _copy_verified(source: Path, destination: Path) -> None:
    source, destination = _io_path(source), _io_path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    before = source.stat()
    copied = hashlib.sha256()
    with source.open("rb") as incoming, destination.open("xb") as outgoing:
        while chunk := incoming.read(1024 * 1024):
            copied.update(chunk)
            outgoing.write(chunk)
    after = source.stat()
    if (
        before.st_size != after.st_size
        or before.st_mtime_ns != after.st_mtime_ns
        or copied.digest() != hashlib.sha256(destination.read_bytes()).digest()
    ):
        raise ValueError("legacy source changed while staging")


def stage_legacy_query_vault(
    source_root: Path,
    target_root: Path,
    *,
    today: date,
    stamp: str,
) -> LegacyQueryStageReport:
    """Stage all current Raw/Wiki text for local querying, without Drop originals.

    The target must be new and disjoint from the source. A failed stage is
    removed only if it is the private temporary directory created here.
    Publication, evaluation and Host binding remain separate explicit steps.
    """
    source = Path(source_root).resolve(strict=True)
    target = Path(target_root).resolve()
    Vault(source)
    if source == target or source in target.parents or target in source.parents:
        raise ValueError("source and query stage must be disjoint")
    if target.exists():
        raise ValueError("query stage target already exists")
    raw_files = _files_in(source, "raw")
    wiki_files = _files_in(source, "wiki")
    roots = tuple(source / name for name in ("index.md", "log.md"))
    for path in roots:
        if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(source):
            raise ValueError("legacy Vault has an unsafe root file")
    decisions = source / "decisions.md"
    if decisions.exists() and (
        decisions.is_symlink()
        or not decisions.is_file()
        or not decisions.resolve().is_relative_to(source)
    ):
        raise ValueError("legacy Vault has an unsafe decisions file")

    target.parent.mkdir(parents=True, exist_ok=True)
    stage = target.with_name(f".{target.name}.part-{uuid4().hex[:8]}")
    stage.mkdir()
    try:
        for path in (*raw_files, *wiki_files, *roots):
            _copy_verified(path, stage / path.relative_to(source))
        if decisions.is_file():
            _copy_verified(decisions, stage / "decisions.md")
        else:
            (stage / "decisions.md").write_text(DECISIONS_HEADER + "\n", encoding="utf-8")
        (stage / "drop").mkdir()
        vault = Vault(_io_path(stage))
        adoption = adopt(vault, mode="apply", today=today, stamp=stamp)
        report = LegacyQueryStageReport(
            vault_root=str(target),
            raw_files=len(raw_files),
            wiki_pages=len(vault.wiki_files()),
            adopted_raw=len(adoption.raw_adopted),
            migrated_pages=len(adoption.pages_migrated),
            unresolved_pages=len(adoption.pages_unresolved),
            raw_sha256=raw_digest(vault),
            decisions_sha256=decision_digest(vault),
            content_sha256=knowledge_digest(vault),
        )
        publish_directory(stage, target)
        return report
    except BaseException:
        if stage.exists() and stage.resolve().parent == target.parent.resolve():
            shutil.rmtree(_io_path(stage))
        raise


def main(argv: Sequence[str] | None = None) -> int:
    """Stage a legacy Vault locally and print exact binding digests as JSON."""
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path, help="read-only legacy Vault")
    parser.add_argument("--target", required=True, type=Path, help="new query Vault directory")
    parser.add_argument("--stamp", required=True, help="unique migration ledger stamp")
    parser.add_argument("--today", type=date.fromisoformat, default=date.today())
    arguments = parser.parse_args(argv)
    try:
        report = stage_legacy_query_vault(
            arguments.source,
            arguments.target,
            today=arguments.today,
            stamp=arguments.stamp,
        )
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(report.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
