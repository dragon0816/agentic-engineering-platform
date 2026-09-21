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
undone.
"""

import hashlib
import shutil
from collections.abc import Iterable
from datetime import date
from typing import Literal, Self

from pydantic import model_validator

from common.base import Contract, Text
from knowledge.contracts import KnowledgeSource
from knowledge.lint import head_fields, line_ending, read_pages
from knowledge.raw import RawIndex, one_line_ending
from knowledge.vault import (
    LEDGER_FILE,
    SNAPSHOT_DIR,
    STATE_FILE,
    Vault,
    VaultError,
    check_stamp,
    normalize,
    provenance_lines,
)

MANAGED_DIRS = ("wiki",)
MANAGED_FILES = ("index.md", "log.md", "decisions.md", STATE_FILE, LEDGER_FILE)

Mode = Literal["dry_run", "apply"]
SkipReason = Literal["undecodable", "empty"]


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
    raw_ref: Text
    reason: SkipReason


class MigratedPage(Contract):
    page: Text
    source: KnowledgeSource


class UnresolvedPage(Contract):
    """A `source_path:` page whose path names no Raw the index knows."""

    page: Text
    source_path: Text


class AdoptionReport(Contract):
    """What adopting a vault did, or would do. `written` is exactly what an
    apply writes; a dry run names it without touching anything."""

    mode: Mode
    snapshot: Text | None = None
    raw_adopted: tuple[AdoptedRaw, ...] = ()
    raw_readopted: tuple[AdoptedRaw, ...] = ()
    raw_drifted: tuple[DriftedRaw, ...] = ()
    raw_skipped: tuple[SkippedRaw, ...] = ()
    pages_migrated: tuple[MigratedPage, ...] = ()
    pages_unresolved: tuple[UnresolvedPage, ...] = ()
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
    adopted or not."""
    typed = {entry.raw_ref for entry in RawIndex.scan(vault, ledger=False).entries}
    return tuple(rel for rel in vault.raw_files() if rel not in typed)


def snapshots(vault: Vault) -> tuple[str, ...]:
    root = vault.root / SNAPSHOT_DIR
    if not root.is_dir():
        return ()
    return tuple(sorted(path.name for path in root.iterdir() if path.is_dir()))


def snapshot(vault: Vault, *, stamp: str, label: str = "") -> str:
    """Copy the generated half — `wiki/`, the root files and the platform's
    state — under `.ingest-snapshot/<stamp[-label]>`. `raw/` and `drop/` are
    the immutable half and are never copied or touched."""
    name = check_stamp(f"{stamp}-{label}" if label else stamp)
    target = vault.root / SNAPSHOT_DIR / name
    if target.exists():
        raise VaultError("write_failed", name)
    target.mkdir(parents=True)
    for directory in MANAGED_DIRS:
        if (vault.root / directory).is_dir():
            shutil.copytree(vault.root / directory, target / directory)
    for file in MANAGED_FILES:
        if (vault.root / file).is_file():
            shutil.copy2(vault.root / file, target / file)
    return name


def restore(vault: Vault, name: str, *, stamp: str) -> str:
    """Replace the generated half with a snapshot. The current state is
    snapshotted first, so a restore is itself undoable."""
    source = vault.root / SNAPSHOT_DIR / check_stamp(name)
    if not source.is_dir():
        raise VaultError("missing_original", name)
    kept = snapshot(vault, stamp=stamp, label="before-restore")
    for directory in MANAGED_DIRS:
        live = vault.root / directory
        if live.is_dir():
            shutil.rmtree(live)
        if (source / directory).is_dir():
            shutil.copytree(source / directory, live)
        else:
            live.mkdir()
    for file in MANAGED_FILES:
        live = vault.root / file
        if (source / file).is_file():
            shutil.copy2(source / file, live)
        elif live.is_file():
            live.unlink()
    return kept


def _with_provenance(text: str, ending: str, source: KnowledgeSource) -> str | None:
    """The page with the typed provenance lines added before the closing
    fence; None when the frontmatter never closes. `source_path:` stays for
    the person reading the page."""
    lines = one_line_ending(text).split("\n")
    end = next((i for i, line in enumerate(lines[1:], 1) if line.strip() == "---"), None)
    if end is None:
        return None
    lines[end:end] = list(provenance_lines(source))
    return ending.join(lines)


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
    unless named in `readopt`; `source_path:` sources pages gain typed
    provenance when the path resolves to a Raw the index knows. An apply that
    writes snapshots the generated half first."""
    check_stamp(stamp)
    wanted = {normalize(rel) for rel in readopt}
    ledger = vault.ledger_read()
    adopted: list[AdoptedRaw] = []
    readopted: list[AdoptedRaw] = []
    drifted: list[DriftedRaw] = []
    skipped: list[SkippedRaw] = []
    known: dict[str, KnowledgeSource] = {}
    for rel in legacy_raw(vault):
        data = vault.read_bytes(rel)
        if not data.strip():
            skipped.append(SkippedRaw(raw_ref=rel, reason="empty"))
            continue
        try:
            data.decode("utf-8")
        except UnicodeDecodeError:
            skipped.append(SkippedRaw(raw_ref=rel, reason="undecodable"))
            continue
        source = source_for_legacy(rel, data)
        record = ledger.get(rel)
        recorded = record.get("sha256") if isinstance(record, dict) else None
        if isinstance(recorded, str) and recorded == source.sha256:
            known[rel] = source
            continue
        if isinstance(recorded, str) and rel not in wanted:
            drifted.append(
                DriftedRaw(raw_ref=rel, recorded_sha256=recorded, current_sha256=source.sha256)
            )
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
    for entry in RawIndex.scan(vault, ledger=False).entries:
        known[entry.raw_ref] = entry.source

    migrated: list[MigratedPage] = []
    unresolved: list[UnresolvedPage] = []
    malformed: list[str] = []
    pages: dict[str, str] = {}
    texts, _ = read_pages(vault, vault.wiki_files())
    for rel, text in texts.items():
        head = head_fields(text)
        if head is None or head.get("source_id") or not head.get("source_path"):
            continue
        resolved = known.get(normalize(head["source_path"]))
        if resolved is None:
            unresolved.append(UnresolvedPage(page=rel, source_path=head["source_path"]))
            continue
        content = _with_provenance(text, line_ending(vault, rel), resolved)
        if content is None:
            malformed.append(rel)
            continue
        pages[rel] = content
        migrated.append(MigratedPage(page=rel, source=resolved))

    written = tuple(pages) + ((LEDGER_FILE,) if adopted or readopted else ())
    name = None
    if mode == "apply" and written:
        name = snapshot(vault, stamp=stamp, label="before-adopt")
        for rel, content in pages.items():
            vault.write(rel, content, stamp=stamp)
        if adopted or readopted:
            vault.ledger_write(ledger)
    return AdoptionReport(
        mode=mode,
        snapshot=name,
        raw_adopted=tuple(adopted),
        raw_readopted=tuple(readopted),
        raw_drifted=tuple(drifted),
        raw_skipped=tuple(skipped),
        pages_migrated=tuple(migrated),
        pages_unresolved=tuple(unresolved),
        pages_skipped=tuple(malformed),
        written=written,
    )
