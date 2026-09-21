"""Vault safety model: where the platform may write, what a write plan must
satisfy, and how a plan is applied.

Adapted from the pinned `knowledge_management` vault tooling
(docs/PHASE_4_MIGRATION.md). The properties are the source's, enforced in code:
`drop/` and `raw/` are never written; a dry run is the default and shows exactly
what an apply would do; every overwrite is backed up first; a plan that breaks a
rule is rejected whole. Nothing here calls a model — a `WritePlan` is data that
a later slice will have a model propose.
"""

import re
from datetime import date, datetime
from pathlib import Path, PurePosixPath
from typing import Literal, Self

from pydantic import model_validator

from common.base import Contract, Text
from knowledge.contracts import KnowledgeSource

IMMUTABLE_AREAS = ("drop/", "raw/")
WRITABLE = ("wiki/", "index.md", "log.md", "decisions.md")
REQUIRED = ("index.md", "log.md", "raw", "wiki")
BACKUP_DIR = ".ingest-backup"
SOURCES_AREA = "wiki/sources/"
CONFLICT_HEADING = "## ⚠️ 待裁決的衝突"

_WIKILINK = re.compile(r"\[\[([^\]|#]+)\]\]")
_PATHY_LINK = re.compile(r"\[\[[^\]]*/[^\]]*\]\]")
_DRIVE = re.compile(r"^[A-Za-z]:")

WriteRefusalCode = Literal["not_a_vault", "escapes_vault", "immutable_area", "outside_writable"]
PlanProblemCode = Literal[
    "no_pages",
    "no_sources_page",
    "missing_provenance",
    "outside_wiki",
    "escapes_vault",
    "empty_content",
    "path_in_wikilink",
]


class VaultError(Exception):
    """A refused write. The code is closed; the path is the caller's own input."""

    def __init__(self, code: WriteRefusalCode, path: str | None = None) -> None:
        self.code: WriteRefusalCode = code
        self.path = path
        super().__init__(code if path is None else f"{code}: {path}")


def normalize(rel: str) -> str:
    return rel.replace("\\", "/").lstrip("/")


def refusal_for(rel: str) -> WriteRefusalCode | None:
    """Why a relative path may not be written, by the layout alone."""
    clean = normalize(rel)
    if not clean or _DRIVE.match(clean) or ".." in PurePosixPath(clean).parts:
        return "escapes_vault"
    if clean.startswith(IMMUTABLE_AREAS):
        return "immutable_area"
    if not clean.startswith(WRITABLE):
        return "outside_writable"
    return None


class PlannedPage(Contract):
    """A whole page, never a diff: an update replaces the file."""

    path: Text
    action: Literal["create", "update"]
    content: str = ""


class IndexEntry(Contract):
    section: Text
    line: Text


class WritePlan(Contract):
    """Everything one ingest proposes. `source` is the provenance the sources
    page must carry; index and log changes are described, not written, so the
    vault can insert and append them itself."""

    source: KnowledgeSource
    summary: str = ""
    pages: tuple[PlannedPage, ...] = ()
    index_entries: tuple[IndexEntry, ...] = ()
    log_body: str = ""
    contradictions: tuple[Text, ...] = ()


class PlanProblem(Contract):
    code: PlanProblemCode
    path: str | None = None
    detail: str | None = None


class LinkRepair(Contract):
    path: Text
    before: Text
    after: Text


class VaultOutcome(Contract):
    """What an apply did, or what a dry run would do. A rejected plan writes
    nothing, and a dry run backs nothing up."""

    mode: Literal["dry_run", "apply"]
    problems: tuple[PlanProblem, ...] = ()
    written: tuple[Text, ...] = ()
    backed_up: tuple[Text, ...] = ()
    repairs: tuple[LinkRepair, ...] = ()
    conflict_marker_added: bool = False

    @model_validator(mode="after")
    def rejected_writes_nothing(self) -> Self:
        if self.problems and (self.written or self.backed_up):
            raise ValueError("a rejected plan writes nothing")
        if self.mode == "dry_run" and self.backed_up:
            raise ValueError("a dry run backs nothing up")
        return self

    @property
    def accepted(self) -> bool:
        return not self.problems


def provenance_lines(source: KnowledgeSource) -> tuple[str, str]:
    """The frontmatter a sources page carries so a reader, a lint and a later
    ingest can all find the same source without a path."""
    return f"source_id: {source.source_id}", f"source_sha256: {source.sha256}"


def carries_provenance(content: str, source: KnowledgeSource) -> bool:
    lines = {line.strip() for line in content.splitlines()}
    return all(expected in lines for expected in provenance_lines(source))


def check_plan(plan: WritePlan) -> tuple[PlanProblem, ...]:
    """Every rule the plan breaks. Any problem rejects the plan whole."""
    problems: list[PlanProblem] = []
    if not plan.pages:
        problems.append(PlanProblem(code="no_pages"))
    sources = [page for page in plan.pages if normalize(page.path).startswith(SOURCES_AREA)]
    if plan.pages and not sources:
        problems.append(PlanProblem(code="no_sources_page"))
    for page in sources:
        if not carries_provenance(page.content, plan.source):
            problems.append(PlanProblem(code="missing_provenance", path=page.path))
    for page in plan.pages:
        clean = normalize(page.path)
        if refusal_for(clean) == "escapes_vault":
            problems.append(PlanProblem(code="escapes_vault", path=page.path))
        elif not clean.startswith("wiki/"):
            problems.append(PlanProblem(code="outside_wiki", path=page.path))
        if not page.content.strip():
            problems.append(PlanProblem(code="empty_content", path=page.path))
        # The schema wants bare page names: a path inside a wikilink resolves
        # to the wrong note. `[[CLAUDE.md]]` has no slash and is left alone.
        for bad in _PATHY_LINK.findall(page.content):
            problems.append(PlanProblem(code="path_in_wikilink", path=page.path, detail=bad))
    return tuple(problems)


def repair_wikilinks(plan: WritePlan) -> tuple[WritePlan, tuple[LinkRepair, ...]]:
    """The two link mistakes with an unambiguous correction, and only those.

    A path becomes the bare page name; a slash-separated enumeration becomes
    separate links. Anything else with a slash is left for `check_plan` to
    reject, because guessing would silently link the wrong page.
    """
    repairs: list[LinkRepair] = []
    pages: list[PlannedPage] = []
    for page in plan.pages:

        def fix(match: re.Match[str], path: str = page.path) -> str:
            inner = match.group(1).strip()
            if "/" not in inner:
                return match.group(0)
            if inner.startswith(("wiki/", "raw/")) or inner.endswith(".md"):
                fixed = f"[[{PurePosixPath(inner).stem}]]"
            elif " / " in inner:
                parts = [part.strip() for part in inner.split("/") if part.strip()]
                fixed = " / ".join(f"[[{part}]]" for part in parts)
            else:
                return match.group(0)
            repairs.append(LinkRepair(path=path, before=inner, after=fixed))
            return fixed

        content = _WIKILINK.sub(fix, page.content)
        pages.append(
            page if content == page.content else page.model_copy(update={"content": content})
        )
    return plan.model_copy(update={"pages": tuple(pages)}), tuple(repairs)


def ensure_conflicts_visible(plan: WritePlan) -> tuple[WritePlan, bool]:
    """A reported contradiction must appear on a page a reader meets, not only
    in the log. Prefer an entity or concept page; else the first page."""
    if not plan.contradictions or not plan.pages:
        return plan, False
    if any("⚠️" in page.content for page in plan.pages):
        return plan, False
    target = next(
        (
            page
            for page in plan.pages
            if normalize(page.path).startswith(("wiki/entities/", "wiki/concepts/"))
        ),
        plan.pages[0],
    )
    block = f"\n\n{CONFLICT_HEADING}\n\n" + "\n".join(f"⚠️ {note}" for note in plan.contradictions)
    updated = target.model_copy(update={"content": target.content.rstrip() + block + "\n"})
    pages = tuple(updated if page is target else page for page in plan.pages)
    return plan.model_copy(update={"pages": pages}), True


def insert_index_entries(text: str, entries: tuple[IndexEntry, ...]) -> str:
    """Each line under its `## Section` heading, before the section's trailing
    blank lines; exact duplicates skipped; a missing section added at the end."""
    lines = text.splitlines()
    for entry in entries:
        section, line = entry.section.strip(), entry.line.strip()
        if line in lines:
            continue
        heading = next(
            (
                index
                for index, item in enumerate(lines)
                if item.startswith("## ") and section.lower() in item.lower()
            ),
            None,
        )
        if heading is None:
            lines += ["", f"## {section}", line]
            continue
        insert = heading + 1
        while insert < len(lines) and not lines[insert].startswith("## "):
            insert += 1
        while insert > heading + 1 and not lines[insert - 1].strip():
            insert -= 1
        lines.insert(insert, line)
    return "\n".join(lines).rstrip() + "\n"


def log_block(plan: WritePlan, today: date) -> str:
    title = PurePosixPath(plan.source.raw_ref or plan.source.original_ref).stem
    block = f"\n## [{today.isoformat()}] ingest | {title}\n{plan.log_body.rstrip()}\n"
    for note in plan.contradictions:
        block += f"- ⚠️ {note}\n"
    return block


class Vault:
    """One vault directory. Every write goes through the layout check; every
    overwrite is backed up under `.ingest-backup/<stamp>/<path>`."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        if not self.root.is_dir() or any(not (self.root / name).exists() for name in REQUIRED):
            raise VaultError("not_a_vault")

    def read(self, rel: str) -> str:
        path = self.root / normalize(rel)
        return path.read_text(encoding="utf-8") if path.exists() else ""

    def _target(self, rel: str) -> Path:
        clean = normalize(rel)
        code = refusal_for(clean)
        if code is not None:
            raise VaultError(code, rel)
        root = self.root.resolve()
        target = (root / clean).resolve()
        if root not in target.parents:
            raise VaultError("escapes_vault", rel)
        return target

    def write(self, rel: str, content: str, *, stamp: str) -> bool:
        """Write one file; returns whether an existing file was backed up first."""
        target = self._target(rel)
        backed_up = False
        if target.exists():
            backup = self.root / BACKUP_DIR / stamp / normalize(rel)
            backup.parent.mkdir(parents=True, exist_ok=True)
            backup.write_bytes(target.read_bytes())
            backed_up = True
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return backed_up

    def append(self, rel: str, block: str) -> None:
        """Append to an append-only file; the layout check still applies."""
        target = self._target(rel)
        existing = target.read_text(encoding="utf-8") if target.exists() else ""
        target.write_text(existing.rstrip() + "\n" + block, encoding="utf-8")

    def apply(
        self,
        plan: WritePlan,
        *,
        mode: Literal["dry_run", "apply"] = "dry_run",
        today: date | None = None,
        stamp: str | None = None,
    ) -> VaultOutcome:
        """Repair what is certain, make conflicts visible, validate, then write
        — or, in a dry run, report exactly what an apply would write."""
        checked = WritePlan.model_validate(plan)
        checked, repairs = repair_wikilinks(checked)
        checked, marked = ensure_conflicts_visible(checked)
        problems = check_plan(checked)
        if problems:
            return VaultOutcome(mode=mode, problems=problems, repairs=repairs)
        planned = [normalize(page.path) for page in checked.pages] + ["index.md", "log.md"]
        if mode == "dry_run":
            return VaultOutcome(
                mode=mode, written=tuple(planned), repairs=repairs, conflict_marker_added=marked
            )
        when = today if today is not None else date.today()
        label = stamp if stamp is not None else datetime.now().strftime("%Y%m%d-%H%M%S")
        backed_up: list[str] = []
        for page in checked.pages:
            if self.write(page.path, page.content.rstrip() + "\n", stamp=label):
                backed_up.append(normalize(page.path))
        if checked.index_entries:
            if self.write(
                "index.md",
                insert_index_entries(self.read("index.md"), checked.index_entries),
                stamp=label,
            ):
                backed_up.append("index.md")
        self.append("log.md", log_block(checked, when))
        return VaultOutcome(
            mode=mode,
            written=tuple(planned),
            backed_up=tuple(backed_up),
            repairs=repairs,
            conflict_marker_added=marked,
        )
