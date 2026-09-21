"""Migration adapter for an existing vault: adopt what is already there under
typed provenance without treating it as a greenfield corpus, and never
rewrite `raw/`.

Adapted from the pinned tooling's `snapshot.py` and from the sharp edge its
README documents (dedup by path). A legacy Raw file — one without provenance
frontmatter — is adopted by recording its content hash in a ledger the Raw
index consults, so it becomes a `KnowledgeSource` for lint, planning and query
while its bytes stay untouched; a later change to the file is drift, reported
and never silently accepted. A sources page that still says `source_path:`
gains the typed `source_id`/`source_sha256` lines when its path resolves to an
adopted or ingested Raw — through `Vault.write`, with a backup. Every apply
that writes is preceded by a snapshot of the generated half so it can be
undone, and writes all of its files or none.
"""

import hashlib
import shutil
from collections.abc import Iterable
from datetime import date
from pathlib import Path
from typing import Literal, Self

from pydantic import model_validator

from common.base import Contract, Text
from knowledge.contracts import KnowledgeSource
from knowledge.lint import head_fields
from knowledge.raw import RawIndex, looks_typed, one_line_ending
from knowledge.vault import (
    LEDGER_FILE,
    SNAPSHOT_DIR,
    STATE_FILE,
    Vault,
    VaultError,
    WriteRefusalCode,
    check_stamp,
    normalize,
    provenance_lines,
)

MANAGED_DIRS = ("wiki",)
MANAGED_FILES = ("index.md", "log.md", "decisions.md", STATE_FILE, LEDGER_FILE)

Mode = Literal["dry_run", "apply"]
SkipReason = Literal["undecodable", "empty", "duplicate", "invalid_provenance"]


class AdoptedRaw(Contract):
    raw_ref: Text
    source: KnowledgeSource


class DriftedRaw(Contract):
    """An adopted Raw whose bytes no longer match the ledger. Raw is
    immutable by rule, so this is a person's change, reported and kept out of
    the index until adopted again on purpose (`readopt`)."""

    raw_ref: Text
    recorded_sha256: Text
    current_sha256: Text


class SkippedRaw(Contract):
    """A file adoption leaves alone: not UTF-8, no text, the same bytes as a
    Raw already known (the first path wins, as a duplicate drop would), or a
    head that claims this platform's provenance but does not validate."""

    raw_ref: Text
    reason: SkipReason


class MigratedPage(Contract):
    page: Text
    source: KnowledgeSource


class UnresolvedPage(Contract):
    """A `source_path:` page whose path names no Raw the index knows."""

    page: Text
    source_path: Text


class UnwritablePage(Contract):
    """A page that resolves but that the vault would refuse to write."""

    page: Text
    code: WriteRefusalCode


class AdoptionReport(Contract):
    """What adopting a vault did, or would do. `written` is exactly what an
    apply writes; a dry run names it without touching anything."""

    mode: Mode
    snapshot: Text | None = None
    raw_adopted: tuple[AdoptedRaw, ...] = ()
    raw_readopted: tuple[AdoptedRaw, ...] = ()
    raw_drifted: tuple[DriftedRaw, ...] = ()
    raw_missing: tuple[Text, ...] = ()
    raw_skipped: tuple[SkippedRaw, ...] = ()
    pages_migrated: tuple[MigratedPage, ...] = ()
    pages_unresolved: tuple[UnresolvedPage, ...] = ()
    pages_unwritable: tuple[UnwritablePage, ...] = ()
    pages_skipped: tuple[Text, ...] = ()
    written: tuple[Text, ...] = ()

    @model_validator(mode="after")
    def snapshot_only_when_applied(self) -> Self:
        if self.snapshot is not None and (self.mode != "apply" or not self.written):
            raise ValueError("a snapshot precedes an apply that writes")
        return self


def source_for_legacy(raw_ref: str, data: bytes) -> KnowledgeSource:
    """Identity by content, as for a dropped original; the Raw file is its own
    original, since nothing older is known."""
    digest = hashlib.sha256(data).hexdigest()
    rel = normalize(raw_ref)
    return KnowledgeSource(
        source_id=f"src-{digest[:16]}", original_ref=rel, sha256=digest, raw_ref=rel
    )


def legacy_raw(vault: Vault) -> tuple[str, ...]:
    """Raw Markdown files without this platform's provenance frontmatter,
    adopted or not. A head that claims provenance but does not validate is
    neither typed nor legacy and is left out."""
    return tuple(rel for rel in vault.raw_files() if not looks_typed(vault.read_head(rel)))


def snapshots(vault: Vault) -> tuple[str, ...]:
    root = vault.root / SNAPSHOT_DIR
    if not root.is_dir():
        return ()
    return tuple(sorted(path.name for path in root.iterdir() if path.is_dir()))


def snapshot(vault: Vault, *, stamp: str, label: str = "") -> str:
    """Copy the generated half — `wiki/`, the root files and the platform's
    state — under `.ingest-snapshot/<stamp[-label]>`. Links are copied as
    links, never followed, so nothing outside the vault is duplicated into
    it. `raw/` and `drop/` are the immutable half and are never copied or
    touched. A name already taken is `write_failed`, before anything is
    written."""
    name = check_stamp(f"{stamp}-{label}" if label else stamp)
    target = vault.root / SNAPSHOT_DIR / name
    if target.exists():
        raise VaultError("write_failed", name)
    target.mkdir(parents=True)
    for directory in MANAGED_DIRS:
        if (vault.root / directory).is_dir():
            shutil.copytree(vault.root / directory, target / directory, symlinks=True)
    for file in MANAGED_FILES:
        if (vault.root / file).is_file():
            shutil.copy2(vault.root / file, target / file)
    return name


def restore(vault: Vault, name: str, *, stamp: str) -> str:
    """Replace the generated half with a snapshot. The current state is
    snapshotted first, so a restore is itself undoable. A managed directory
    that is itself a link is refused before anything is touched: replacing
    it would write where the vault rules do not reach."""
    source = vault.root / SNAPSHOT_DIR / check_stamp(name)
    if not source.is_dir():
        raise VaultError("missing_original", name)
    for directory in MANAGED_DIRS:
        if (vault.root / directory).is_symlink():
            raise VaultError("unwritable_target", directory)
    kept = snapshot(vault, stamp=stamp, label="before-restore")
    for directory in MANAGED_DIRS:
        live = vault.root / directory
        if live.is_dir():
            shutil.rmtree(live)
        if (source / directory).is_dir():
            shutil.copytree(source / directory, live, symlinks=True)
        else:
            live.mkdir()
    for file in MANAGED_FILES:
        live = vault.root / file
        if (source / file).is_file():
            shutil.copy2(source / file, live)
        elif live.is_file():
            live.unlink()
    return kept


def _with_provenance(data: bytes, source: KnowledgeSource) -> str | None:
    """The page with the typed provenance lines added before the closing
    fence, in the page's own line endings; None when the frontmatter never
    closes. `source_path:` stays for the person reading the page."""
    ending = "\r\n" if b"\r\n" in data else "\n"
    lines = one_line_ending(data.decode("utf-8")).split("\n")
    end = next((i for i, line in enumerate(lines[1:], 1) if line.strip() == "---"), None)
    if end is None:
        return None
    lines[end:end] = list(provenance_lines(source))
    return ending.join(lines)


def _write_all(
    vault: Vault, pages: dict[str, str], ledger: dict[str, object] | None, stamp: str
) -> None:
    """Every write or none: what each target held before is kept in memory
    and put back if any write fails, as `Vault.apply` does."""
    previous: list[tuple[Path, bytes | None]] = []

    def remember(path: Path) -> None:
        previous.append((path, path.read_bytes() if path.exists() else None))

    try:
        for rel, content in pages.items():
            remember(vault.root / rel)
            vault.write(rel, content, stamp=stamp)
        if ledger is not None:
            remember(vault.root / LEDGER_FILE)
            vault.ledger_write(dict(ledger))
    except (OSError, VaultError) as error:
        for target, before in reversed(previous):
            if before is None:
                target.unlink(missing_ok=True)
            else:
                target.write_bytes(before)
        raise VaultError("write_failed") from error


def adopt(
    vault: Vault,
    *,
    mode: Mode = "dry_run",
    today: date,
    stamp: str,
    readopt: Iterable[str] = (),
) -> AdoptionReport:
    """Adopt an existing vault. Legacy Raw files enter the ledger by content
    hash (their bytes untouched); adopted files that changed since are drift
    unless named in `readopt`; ledger records whose file is gone are dropped;
    `source_path:` sources pages gain typed provenance when the path resolves
    to a Raw the index knows. An apply that writes snapshots the generated
    half first, then writes everything or nothing. A stamp names one apply:
    a second apply under the same stamp is refused as `write_failed` before
    anything is written."""
    check_stamp(stamp)
    wanted = {normalize(rel) for rel in readopt}
    ledger: dict[str, object] = dict(vault.ledger_read())
    typed = RawIndex.scan(vault, ledger=False)
    known: dict[str, KnowledgeSource] = {e.raw_ref: e.source for e in typed.entries}
    seen = {e.source.sha256 for e in typed.entries}
    adopted: list[AdoptedRaw] = []
    readopted: list[AdoptedRaw] = []
    drifted: list[DriftedRaw] = []
    skipped: list[SkippedRaw] = []
    present: set[str] = set()
    for rel in vault.raw_files():
        present.add(rel)
        if rel in known:
            continue
        if looks_typed(vault.read_head(rel)):
            skipped.append(SkippedRaw(raw_ref=rel, reason="invalid_provenance"))
            continue
        data = vault.read_bytes(rel)
        source = source_for_legacy(rel, data)
        record = ledger.get(rel)
        recorded = record.get("sha256") if isinstance(record, dict) else None
        if isinstance(recorded, str) and recorded == source.sha256:
            known[rel] = source
            seen.add(source.sha256)
            continue
        if isinstance(recorded, str) and rel not in wanted:
            drifted.append(
                DriftedRaw(raw_ref=rel, recorded_sha256=recorded, current_sha256=source.sha256)
            )
            continue
        if not data.strip():
            skipped.append(SkippedRaw(raw_ref=rel, reason="empty"))
            continue
        try:
            data.decode("utf-8")
        except UnicodeDecodeError:
            skipped.append(SkippedRaw(raw_ref=rel, reason="undecodable"))
            continue
        if source.sha256 in seen:
            skipped.append(SkippedRaw(raw_ref=rel, reason="duplicate"))
            continue
        (readopted if isinstance(recorded, str) else adopted).append(
            AdoptedRaw(raw_ref=rel, source=source)
        )
        ledger[rel] = {
            "source_id": source.source_id,
            "sha256": source.sha256,
            "adopted": today.isoformat(),
        }
        known[rel] = source
        seen.add(source.sha256)
    missing = tuple(sorted(rel for rel in ledger if rel not in present))
    for rel in missing:
        del ledger[rel]

    migrated: list[MigratedPage] = []
    unresolved: list[UnresolvedPage] = []
    unwritable: list[UnwritablePage] = []
    malformed: list[str] = []
    pages: dict[str, str] = {}
    for rel in vault.wiki_files():
        try:
            head = head_fields(vault.read_head(rel))
        except VaultError:
            # A link that leaves the vault is not a page of it.
            malformed.append(rel)
            continue
        if head is None or head.get("source_id") or not head.get("source_path"):
            continue
        resolved = known.get(normalize(head["source_path"]))
        if resolved is None:
            unresolved.append(UnresolvedPage(page=rel, source_path=head["source_path"]))
            continue
        try:
            vault.check_writable(rel)
        except VaultError as error:
            unwritable.append(UnwritablePage(page=rel, code=error.code))
            continue
        content = _with_provenance(vault.read_bytes(rel), resolved)
        if content is None:
            malformed.append(rel)
            continue
        pages[rel] = content
        migrated.append(MigratedPage(page=rel, source=resolved))

    ledger_changed = bool(adopted or readopted or missing)
    written = tuple(pages) + ((LEDGER_FILE,) if ledger_changed else ())
    name = None
    if mode == "apply" and written:
        name = snapshot(vault, stamp=stamp, label="before-adopt")
        _write_all(vault, pages, ledger if ledger_changed else None, stamp)
    return AdoptionReport(
        mode=mode,
        snapshot=name,
        raw_adopted=tuple(adopted),
        raw_readopted=tuple(readopted),
        raw_drifted=tuple(drifted),
        raw_missing=missing,
        raw_skipped=tuple(skipped),
        pages_migrated=tuple(migrated),
        pages_unresolved=tuple(unresolved),
        pages_unwritable=tuple(unwritable),
        pages_skipped=tuple(malformed),
        written=written,
    )
