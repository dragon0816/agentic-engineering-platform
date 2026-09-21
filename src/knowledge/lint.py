"""Static lint: everything about the wiki that can be established by reading it.

Adapted from the pinned `brain.py` scan (docs/PHASE_4_MIGRATION.md): what is
countable is computed here — exactly, instantly and for free — and only
judgement is ever sent to a model, in a later pass that takes this report as
context. Nothing here calls a model. The one write, `fix_links`, is the
mechanical repair the source made too, and it goes through the vault with a
backup like any other page write.
"""

import re
from collections import Counter, defaultdict
from pathlib import PurePosixPath

from pydantic import Field

from common.base import Contract, Symbol, Text
from knowledge.raw import RawIndex, frontmatter
from knowledge.vault import SOURCES_AREA, Vault, VaultError, normalize

WIKILINK = re.compile(r"\[\[([^\]|#]+)((?:[|#][^\]]*)?)\]\]")
# A conflict a page carries until a person settles it; plain markdown so it
# survives being edited in Obsidian. Horizontal whitespace only: `\s` would
# start the match on the preceding blank line.
CONFLICT = re.compile(r"^[ \t]*(?:[-*][ \t]*)?⚠️[ \t]*(.+?)[ \t]*$", re.M)
# Entry points; nothing links to them by design.
ENTRY_POINTS = frozenset({"wiki/overview.md", "index.md"})


def page_name(rel: str) -> str:
    """Page name from a path or a wikilink target. Only `.md` is stripped,
    never the whole suffix: `Continue.dev` is a page name."""
    name = PurePosixPath(normalize(rel)).name
    return name[:-3] if name.endswith(".md") else name


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
    page: Text
    source_id: Symbol


class OpenConflict(Contract):
    page: Text
    line: int = Field(ge=1, strict=True)
    text: Text


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
            )
        )


def _pages(vault: Vault) -> dict[str, str]:
    """Every wiki page's text plus `index.md`, which shares the link rules;
    `log.md` is append-only history and is left alone."""
    texts: dict[str, str] = {}
    for rel, _ in vault.wiki_pages():
        try:
            texts[rel] = vault.read(rel)
        except VaultError:
            continue
    if vault.exists("index.md"):
        texts["index.md"] = vault.read("index.md")
    return texts


def _field(text: str, key: str) -> str:
    head = frontmatter(text)
    return head[0].get(key, "") if head is not None else ""


def scan(vault: Vault) -> LintReport:
    texts = _pages(vault)
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
    missing_frontmatter = tuple(
        rel for rel, text in wiki_pages.items() if frontmatter(text) is None
    )
    types = Counter(_field(text, "type") or "(untyped)" for text in wiki_pages.values())

    index = RawIndex.scan(vault)
    known_sources = {entry.source.source_id for entry in index.entries}
    carried: set[str] = set()
    broken_paths: list[BrokenSourcePath] = []
    unknown: list[UnknownSource] = []
    for rel, text in wiki_pages.items():
        source_id = _field(text, "source_id")
        if source_id:
            if rel.startswith(SOURCES_AREA):
                carried.add(source_id)
            if source_id not in known_sources:
                unknown.append(UnknownSource(page=rel, source_id=source_id))
        source_path = _field(text, "source_path").strip("\"'")
        if source_path:
            try:
                present = vault.exists(source_path)
            except VaultError:
                present = False
            if not present:
                broken_paths.append(BrokenSourcePath(page=rel, source_path=source_path))
    pending = tuple(
        entry.raw_ref for entry in index.entries if entry.source.source_id not in carried
    )

    conflicts = []
    for rel, text in wiki_pages.items():
        for match in CONFLICT.finditer(text):
            line = text.count("\n", 0, match.start()) + 1
            conflicts.append(OpenConflict(page=rel, line=line, text=match.group(1).strip()))

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
    )


def fix_links(vault: Vault, report: LintReport, *, stamp: str) -> tuple[str, ...]:
    """Rewrite the flagged `[[wiki/x/Foo]]`-style links to the bare `[[Foo]]`
    the schema asks for. Mechanical, so no model. Where a page with that name
    exists under a different case, the real page name is used, so `[[Openhands]]`
    does not end up dangling beside `OpenHands`. Only links the scan flagged are
    touched; a legitimate link to a root file is left alone. Every rewritten
    page is backed up first."""
    texts = _pages(vault)
    by_lower = {page_name(rel).lower(): page_name(rel) for rel in texts}
    offenders = {(item.page, item.link) for item in report.path_links}
    changed: list[str] = []
    for rel in sorted({item.page for item in report.path_links}):
        text = texts.get(rel)
        if text is None:
            continue

        def replace(match: re.Match[str], page: str = rel) -> str:
            inner = match.group(1).strip()
            alias = match.group(2)  # keep any |alias or #anchor
            if (page, inner) not in offenders:
                return match.group(0)
            bare = page_name(inner)
            return f"[[{by_lower.get(bare.lower(), bare)}{alias}]]"

        fixed = WIKILINK.sub(replace, text)
        if fixed != text:
            vault.write(rel, fixed, stamp=stamp)
            changed.append(rel)
    return tuple(changed)
