"""Static lint: everything about the wiki that can be established by reading it.

Adapted from the pinned `brain.py` scan (docs/PHASE_4_MIGRATION.md): what is
countable is computed here — exactly, instantly and for free — and only
judgement is ever sent to a model, in a later pass that takes this report as
context. Nothing here calls a model, and nothing a page contains can abort the
report: a broken page is a finding. The one write, `fix_links`, is the
mechanical repair the source made too, and it goes through the vault with a
backup like any other page write.
"""

import hashlib
import re
from collections import Counter, defaultdict
from datetime import date
from pathlib import PurePosixPath

from pydantic import Field

from common.base import Contract, Text
from knowledge.raw import RawIndex
from knowledge.vault import SOURCES_AREA, Vault, VaultError, normalize

WIKILINK = re.compile(r"\[\[([^\]|#]+)((?:[|#][^\]]*)?)\]\]")
# A conflict a page carries until a person settles it; plain markdown so it
# survives being edited in Obsidian. Horizontal whitespace only: `\s` would
# start the match on the preceding blank line.
CONFLICT = re.compile(r"^[ \t]*(?:[-*][ \t]*)?⚠️[ \t]*(.*?)[ \t]*$", re.M)
# A page has frontmatter when it opens with a fence; what is inside is read
# leniently, line by line, because Obsidian frontmatter holds lists, blank
# lines and comments that are not `key: value`.
FRONTMATTER_OPEN = re.compile(r"^---[ \t]*\n")
FIELD = re.compile(r"^([A-Za-z_][A-Za-z0-9_-]*):[ \t]*(.*?)[ \t]*$")
# Entry points; nothing links to them by design.
ENTRY_POINTS = frozenset({"wiki/overview.md", "index.md"})
EMPTY_MARKER = "(marker without text)"


def page_name(rel: str) -> str:
    """Page name from a path or a wikilink target. Only `.md` is stripped,
    never the whole suffix: `Continue.dev` is a page name."""
    name = PurePosixPath(normalize(rel)).name
    return name[:-3] if name.endswith(".md") else name


def head_fields(text: str) -> dict[str, str] | None:
    """The `key: value` lines of a page's frontmatter, or None when the page
    has no frontmatter at all. Lines that are not fields are skipped, not
    fatal; an unclosed fence reads to the end of the page."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if FRONTMATTER_OPEN.match(text) is None:
        return None
    fields: dict[str, str] = {}
    for line in text.split("\n")[1:]:
        if line.strip() == "---":
            break
        match = FIELD.match(line)
        if match is not None:
            fields[match.group(1).lower()] = match.group(2).strip("\"'")
    return fields


def body_of(text: str) -> str:
    """The page after its frontmatter block (the whole page when it has none,
    or when the fence never closes)."""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    if FRONTMATTER_OPEN.match(normalized) is None:
        return normalized
    lines = normalized.split("\n")
    for index, line in enumerate(lines[1:], 1):
        if line.strip() == "---":
            return "\n".join(lines[index + 1 :])
    return normalized


class PathLink(Contract):
    page: Text
    link: Text


class DanglingLink(Contract):
    target: Text
    count: int = Field(ge=1, strict=True)


class BrokenSourcePath(Contract):
    """A legacy `source_path:` (an existing vault's convention) that no longer
    resolves; typed provenance is checked as `UnknownSource`."""

    page: Text
    source_path: Text


class UnknownSource(Contract):
    """A `source_id:` the Raw index does not know — including one that is not
    even a well-formed identifier, which is reported, never raised."""

    page: Text
    source_id: Text


class OpenConflict(Contract):
    page: Text
    line: int = Field(ge=1, strict=True)
    text: Text


class ManualEdits(Contract):
    """Pages a person changed since the recorded state — edited, added or
    removed — and `first_run` when there is no usable state to compare against.
    A page the tool wrote and noted is not an edit; a later change to it is."""

    first_run: bool = False
    since: str | None = None
    edited: tuple[Text, ...] = ()
    added: tuple[Text, ...] = ()
    removed: tuple[Text, ...] = ()


def line_ending(vault: Vault, rel: str) -> str:
    """The line ending a page uses, so a one-line repair rewrites nothing else."""
    return "\r\n" if b"\r\n" in vault.read_bytes(rel) else "\n"


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def page_hashes(vault: Vault, texts: dict[str, str] | None = None) -> dict[str, str]:
    """A short content hash per wiki page, `index.md` and `decisions.md`;
    unreadable pages are left out rather than fatal. Texts already read by
    the caller are hashed rather than read again."""
    known = dict(texts) if texts is not None else _all_pages(vault)[0]
    if "decisions.md" not in known and vault.exists("decisions.md"):
        more, _ = read_pages(vault, ("decisions.md",))
        known.update(more)
    return {rel: _hash(text) for rel, text in known.items()}


def record_state(vault: Vault, *, today: date) -> None:
    """Record every page's hash now. Chosen over git, as the source did,
    because a vault may live in a synced folder where a `.git` directory is a
    liability."""
    vault.state_write({"updated": today.isoformat(), "hashes": page_hashes(vault)})


def note_written(vault: Vault, written: tuple[str, ...], *, today: date) -> None:
    """After the tool writes pages, refresh their recorded hashes — and only
    theirs — so its own writes are not reported as a person's while a later
    change to the same page still is."""
    state = vault.state_read()
    hashes = _clean_hashes(state.get("hashes"))
    if hashes is None:
        record_state(vault, today=today)
        return
    texts, _ = read_pages(vault, tuple(normalize(rel) for rel in written))
    for rel, text in texts.items():
        hashes[rel] = _hash(text)
    for rel in written:
        if normalize(rel) not in texts:
            hashes.pop(normalize(rel), None)
    vault.state_write({"updated": today.isoformat(), "hashes": hashes})


def _clean_hashes(value: object) -> dict[str, str] | None:
    if not isinstance(value, dict) or not value:
        return None
    cleaned = {
        key: digest
        for key, digest in value.items()
        if isinstance(key, str) and key.strip() and isinstance(digest, str)
    }
    return cleaned or None


def manual_edits(vault: Vault, texts: dict[str, str] | None = None) -> ManualEdits:
    """A corrupt, odd or absent state is a first run, never a failure."""
    state = vault.state_read()
    previous = _clean_hashes(state.get("hashes"))
    if previous is None:
        return ManualEdits(first_run=True)
    current = page_hashes(vault, texts)
    since = state.get("updated")
    return ManualEdits(
        since=since if isinstance(since, str) and since.strip() else None,
        edited=tuple(
            rel for rel, digest in current.items() if rel in previous and previous[rel] != digest
        ),
        added=tuple(rel for rel in current if rel not in previous),
        removed=tuple(rel for rel in previous if rel not in current),
    )


class LintReport(Contract):
    """The computed findings, each a closed shape. `dangling` is ranked by how
    often a missing page is referenced: the more, the sooner it deserves one."""

    pages: int = Field(ge=0, strict=True)
    types: tuple[tuple[str, int], ...] = ()
    orphans: tuple[Text, ...] = ()
    dangling: tuple[DanglingLink, ...] = ()
    path_links: tuple[PathLink, ...] = ()
    missing_frontmatter: tuple[Text, ...] = ()
    broken_source_path: tuple[BrokenSourcePath, ...] = ()
    unknown_source_id: tuple[UnknownSource, ...] = ()
    pending_sources: tuple[Text, ...] = ()
    open_conflicts: tuple[OpenConflict, ...] = ()
    unreadable: tuple[Text, ...] = ()
    # Informational: what a person changed since the last recorded state.
    manual_edits: ManualEdits = ManualEdits(first_run=True)

    @property
    def clean(self) -> bool:
        return not any(
            (
                self.orphans,
                self.dangling,
                self.path_links,
                self.missing_frontmatter,
                self.broken_source_path,
                self.unknown_source_id,
                self.pending_sources,
                self.open_conflicts,
                self.unreadable,
            )
        )


def read_pages(vault: Vault, rels: tuple[str, ...]) -> tuple[dict[str, str], tuple[str, ...]]:
    """The text of each page, and the pages that could not be read — a link
    that leaves the vault, or bytes that are not UTF-8 — as findings."""
    texts: dict[str, str] = {}
    unreadable: list[str] = []
    for rel in rels:
        try:
            texts[rel] = vault.read(rel)
        except (VaultError, UnicodeDecodeError):
            unreadable.append(rel)
    return texts, tuple(unreadable)


def _all_pages(vault: Vault) -> tuple[dict[str, str], tuple[str, ...]]:
    """Every wiki page plus `index.md`, which shares the link rules; `log.md`
    is append-only history and is left alone."""
    rels = vault.wiki_files() + (("index.md",) if vault.exists("index.md") else ())
    return read_pages(vault, rels)


def find_conflicts(rel: str, text: str) -> tuple[OpenConflict, ...]:
    """Every `⚠️` line of one page; a marker whose text was deleted is still an
    open conflict, reported as such rather than dropped."""
    return tuple(
        OpenConflict(
            page=rel,
            line=text.count("\n", 0, match.start()) + 1,
            text=match.group(1).strip() or EMPTY_MARKER,
        )
        for match in CONFLICT.finditer(text)
    )


def scan(vault: Vault) -> LintReport:
    texts, unreadable = _all_pages(vault)
    wiki_pages = {rel: text for rel, text in texts.items() if rel.startswith("wiki/")}
    by_name: dict[str, list[str]] = defaultdict(list)
    for rel in texts:
        by_name[page_name(rel)].append(rel)
    wiki_names = {page_name(rel).lower() for rel in wiki_pages}

    inbound: dict[str, set[str]] = defaultdict(set)
    dangling: Counter[str] = Counter()
    path_links: list[PathLink] = []
    for rel, text in texts.items():
        for match in WIKILINK.finditer(text):
            link = match.group(1).strip()
            if not link:
                continue  # `[[ ]]` links nowhere and names nothing
            # A path is always wrong. A trailing .md is only wrong when it names
            # a wiki page: [[CLAUDE.md]] may point at a root file and resolve.
            if "/" in link or (link.endswith(".md") and page_name(link).lower() in wiki_names):
                path_links.append(PathLink(page=rel, link=link))
            target = page_name(link)
            if target in by_name:
                for hit in by_name[target]:
                    if hit != rel:
                        inbound[hit].add(rel)
            else:
                dangling[link] += 1

    orphans = tuple(rel for rel in texts if rel not in ENTRY_POINTS and not inbound.get(rel))
    heads = {rel: head_fields(text) for rel, text in wiki_pages.items()}
    missing_frontmatter = tuple(rel for rel, head in heads.items() if head is None)
    types = Counter((head or {}).get("type") or "(untyped)" for head in heads.values())

    index = RawIndex.scan(vault)
    known_sources = {entry.source.source_id for entry in index.entries}
    carried: set[str] = set()
    broken_paths: list[BrokenSourcePath] = []
    unknown: list[UnknownSource] = []
    for rel, head in heads.items():
        fields = head or {}
        source_id = fields.get("source_id", "")
        if source_id:
            if rel.startswith(SOURCES_AREA):
                carried.add(source_id)
            if source_id not in known_sources:
                unknown.append(UnknownSource(page=rel, source_id=source_id))
        source_path = fields.get("source_path", "")
        if source_path:
            try:
                present = vault.exists(source_path)
            except VaultError:
                present = False
            if not present:
                broken_paths.append(BrokenSourcePath(page=rel, source_path=source_path))
    # A superseded Raw handed its evidence to its successor; only the current
    # version of each original can be pending.
    superseded = {entry.supersedes for entry in index.entries if entry.supersedes is not None}
    pending = tuple(
        entry.raw_ref
        for entry in index.entries
        if entry.source.source_id not in superseded and entry.source.source_id not in carried
    )

    conflicts: list[OpenConflict] = []
    for rel, text in wiki_pages.items():
        conflicts.extend(find_conflicts(rel, text))

    return LintReport(
        pages=len(wiki_pages),
        types=tuple(sorted(types.items())),
        orphans=orphans,
        dangling=tuple(DanglingLink(target=t, count=c) for t, c in dangling.most_common()),
        path_links=tuple(path_links),
        missing_frontmatter=missing_frontmatter,
        broken_source_path=tuple(broken_paths),
        unknown_source_id=tuple(unknown),
        pending_sources=pending,
        open_conflicts=tuple(conflicts),
        unreadable=unreadable,
        manual_edits=manual_edits(vault, texts),
    )


def fix_links(vault: Vault, report: LintReport, *, stamp: str) -> tuple[str, ...]:
    """Rewrite the flagged `[[wiki/x/Foo]]`-style links to the bare `[[Foo]]`
    the schema asks for. Mechanical, so no model. Where a page with that name
    exists under a different case, the real page name is used, so `[[Openhands]]`
    does not end up dangling beside `OpenHands`. Only links the scan flagged are
    touched; a legitimate link to a root file is left alone. Only the flagged
    pages are read, and every rewritten one is backed up first."""
    names = vault.wiki_files() + (("index.md",) if vault.exists("index.md") else ())
    by_lower = {page_name(rel).lower(): page_name(rel) for rel in names}
    offenders = {(item.page, item.link) for item in report.path_links}
    flagged = tuple(sorted({item.page for item in report.path_links}))
    texts, _ = read_pages(vault, flagged)
    changed: list[str] = []
    for rel, text in texts.items():

        def replace(match: re.Match[str], page: str = rel) -> str:
            inner = match.group(1).strip()
            alias = match.group(2)  # keep any |alias or #anchor
            if (page, inner) not in offenders:
                return match.group(0)
            bare = page_name(inner)
            return f"[[{by_lower.get(bare.lower(), bare)}{alias}]]"

        fixed = WIKILINK.sub(replace, text)
        if fixed != text:
            ending = line_ending(vault, rel)
            vault.write(rel, fixed.replace("\n", ending), stamp=stamp)
            changed.append(rel)
    return tuple(changed)
