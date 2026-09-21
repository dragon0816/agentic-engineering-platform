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
WRITABLE_AREAS = ("wiki/",)
WRITABLE_FILES = ("index.md", "log.md", "decisions.md")
REQUIRED = ("index.md", "log.md", "raw", "wiki")
BACKUP_DIR = ".ingest-backup"
CACHE_DIR = ".ingest-cache"
_SHA256 = re.compile(r"^[a-f0-9]{64}$")
SOURCES_AREA = "wiki/sources/"
CONFLICT_HEADING = "## ⚠️ 待裁決的衝突"

_WIKILINK = re.compile(r"\[\[([^\]|#]+)\]\]")
_PATHY_LINK = re.compile(r"\[\[[^\]]*/[^\]]*\]\]")
_DRIVE = re.compile(r"^[A-Za-z]:")
# One path component: a backup stamp names a directory under the backup area
# and nothing else.
_STAMP = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")

WriteRefusalCode = Literal[
    "not_a_vault",
    "escapes_vault",
    "immutable_area",
    "outside_writable",
    "unwritable_target",
    "write_failed",
    "outside_raw",
    "raw_exists",
    "outside_drop",
    "missing_original",
]
PlanProblemCode = Literal[
    "no_pages",
    "no_sources_page",
    "missing_provenance",
    "outside_wiki",
    "escapes_vault",
    "empty_content",
    "path_in_wikilink",
    "duplicate_path",
    "create_exists",
    "update_missing",
    "unwritable_target",
]


class VaultError(Exception):
    """A refused write. The code is closed; the path is the caller's own input."""

    def __init__(self, code: WriteRefusalCode, path: str | None = None) -> None:
        self.code: WriteRefusalCode = code
        self.path = path
        super().__init__(code if path is None else f"{code}: {path}")


def normalize(rel: str) -> str:
    """One spelling per path: forward slashes, no leading slash, no `.` segments
    or doubled separators, so equal paths compare equal. `..` is kept for the
    layout check to refuse."""
    clean = rel.replace("\\", "/").lstrip("/")
    return PurePosixPath(clean).as_posix() if clean else ""


def refusal_for(rel: str) -> WriteRefusalCode | None:
    """Why a relative path may not be written, by the layout alone. Areas match
    by prefix; the root-level files match exactly, so `index.md.bak` is not
    `index.md`."""
    clean = normalize(rel)
    if not clean or _DRIVE.match(clean) or ".." in PurePosixPath(clean).parts:
        return "escapes_vault"
    if clean.startswith(IMMUTABLE_AREAS):
        return "immutable_area"
    if clean.startswith(WRITABLE_AREAS) or clean in WRITABLE_FILES:
        return None
    return "outside_writable"


def check_stamp(stamp: str) -> str:
    if not _STAMP.match(stamp):
        raise ValueError("a backup stamp is a single path component")
    return stamp


class PlannedPage(Contract):
    """A whole page, never a diff: an update replaces the file. `create` must
    not find the page already there, and `update` must find it."""

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

    @property
    def notes(self) -> tuple[str, ...]:
        """Contradictions as the source records them: stripped, blanks dropped."""
        return tuple(note.strip() for note in self.contradictions if note.strip())


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
    """Every rule the plan breaks on its own. Any problem rejects the plan whole;
    what depends on the vault's current state is checked by `Vault.apply`."""
    problems: list[PlanProblem] = []
    if not plan.pages:
        problems.append(PlanProblem(code="no_pages"))
    sources = [page for page in plan.pages if normalize(page.path).startswith(SOURCES_AREA)]
    if plan.pages and not sources:
        problems.append(PlanProblem(code="no_sources_page"))
    for page in sources:
        if not carries_provenance(page.content, plan.source):
            problems.append(PlanProblem(code="missing_provenance", path=page.path))
    seen: set[str] = set()
    for page in plan.pages:
        clean = normalize(page.path)
        if refusal_for(clean) == "escapes_vault":
            problems.append(PlanProblem(code="escapes_vault", path=page.path))
        elif not clean.startswith(WRITABLE_AREAS):
            problems.append(PlanProblem(code="outside_wiki", path=page.path))
        # Two writes to one page in one plan would back the first write up over
        # the original, and "every overwrite is backed up" would be a lie.
        if clean in seen:
            problems.append(PlanProblem(code="duplicate_path", path=page.path))
        seen.add(clean)
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
    notes = plan.notes
    if not notes or not plan.pages:
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
    block = f"\n\n{CONFLICT_HEADING}\n\n" + "\n".join(f"⚠️ {note}" for note in notes)
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
    for note in plan.notes:
        block += f"- ⚠️ {note}\n"
    return block


class Vault:
    """One vault directory. Every write goes through the layout check on both
    the requested and the resolved path; every overwrite is backed up under
    `.ingest-backup/<stamp>/<path>`; a plan is applied whole or not at all."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        if not self.root.is_dir() or any(not (self.root / name).exists() for name in REQUIRED):
            raise VaultError("not_a_vault")

    def _resolve(self, rel: str) -> tuple[str, Path]:
        """The real location of a relative path, refused if it leaves the vault."""
        clean = normalize(rel)
        if refusal_for(clean) == "escapes_vault":
            raise VaultError("escapes_vault", rel)
        root = self.root.resolve()
        target = (root / clean).resolve()
        if root not in target.parents:
            raise VaultError("escapes_vault", rel)
        return target.relative_to(root).as_posix(), target

    def read(self, rel: str) -> str:
        _, target = self._resolve(rel)
        return target.read_text(encoding="utf-8") if target.is_file() else ""

    def exists(self, rel: str) -> bool:
        return self._resolve(rel)[1].exists()

    def read_head(self, rel: str, *, max_lines: int = 64) -> str:
        """The frontmatter of a file, read line by line and stopped at the
        closing `---`, so a large or oddly encoded body is never touched."""
        _, target = self._resolve(rel)
        if not target.is_file():
            return ""
        head: list[bytes] = []
        with target.open("rb") as handle:
            for number, raw in enumerate(handle):
                line = raw.rstrip(b"\r\n")
                head.append(line)
                if (number > 0 and line == b"---") or number + 1 >= max_lines:
                    break
        try:
            return b"\n".join(head).decode("utf-8") + "\n"
        except UnicodeDecodeError:
            return ""

    def original_ref(self, rel: str) -> str:
        """The canonical spelling of an original's path under drop/: the
        resolved, relative, forward-slash form that identity is recorded with."""
        clean = normalize(rel)
        if not clean.startswith("drop/"):
            raise VaultError("outside_drop", rel)
        resolved, _ = self._resolve(clean)
        if not resolved.startswith("drop/"):
            raise VaultError("outside_drop", rel)
        return resolved

    def read_original(self, rel: str) -> bytes:
        """The bytes of one original under drop/. Drop is read, never written."""
        _, target = self._resolve(self.original_ref(rel))
        if not target.is_file():
            raise VaultError("missing_original", rel)
        return target.read_bytes()

    def wiki_pages(self) -> tuple[tuple[str, str], ...]:
        """Every wiki page as (relative path, title) — the title from the
        frontmatter, else the file's stem — in path order."""
        pages = []
        for path in sorted((self.root / "wiki").rglob("*.md")):
            if not path.is_file():
                continue
            rel = path.relative_to(self.root).as_posix()
            try:
                head = self.read_head(rel)
            except VaultError:
                # A link that leaves the vault is not a page of it.
                continue
            title = path.stem
            for line in head.split("\n"):
                if line.startswith("title:") and line[6:].strip():
                    title = line[6:].strip().strip("\"'")
                    break
            pages.append((rel, title))
        return tuple(pages)

    def _cache_path(self, key: str) -> Path:
        # The cache is keyed by a content hash and lives in its own directory;
        # anything else is a programming error, not a path to resolve.
        if not _SHA256.fullmatch(key):
            raise ValueError("a cache key is a content hash")
        return self.root / CACHE_DIR / f"{key}.md"

    def cache_read(self, key: str) -> str | None:
        path = self._cache_path(key)
        return path.read_text(encoding="utf-8") if path.is_file() else None

    def cache_write(self, key: str, text: str) -> None:
        path = self._cache_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")

    def raw_files(self) -> tuple[str, ...]:
        """Every Markdown file under raw/ except assets, in path order."""
        root = self.root / "raw"
        found = []
        for path in sorted(root.rglob("*.md")):
            rel = path.relative_to(self.root).as_posix()
            if "/assets/" not in rel:
                found.append(rel)
        return tuple(found)

    def _raw_target(self, rel: str) -> Path:
        clean = normalize(rel)
        if not clean.startswith("raw/"):
            raise VaultError("outside_raw", rel)
        resolved, target = self._resolve(clean)
        if not resolved.startswith("raw/") or target.is_dir():
            raise VaultError("outside_raw", rel)
        target.parent.mkdir(parents=True, exist_ok=True)
        return target

    def write_raw(self, rel: str, content: str) -> None:
        """The one way raw/ is written: create, never replace. Raw is immutable
        in the only sense a pipeline can honour — write once, never change."""
        target = self._raw_target(rel)
        try:
            # Exclusive creation: two writers cannot both succeed, and the
            # bytes on disk are exactly the text, whatever the platform.
            with target.open("x", encoding="utf-8", newline="\n") as handle:
                handle.write(content)
        except FileExistsError:
            raise VaultError("raw_exists", rel) from None

    def write_raw_bytes(self, rel: str, data: bytes) -> bool:
        """An asset under raw/, named by its content: creating it again with the
        same bytes is a no-op (False); different bytes at that name are
        `raw_exists`, because raw is never replaced."""
        target = self._raw_target(rel)
        try:
            with target.open("xb") as handle:
                handle.write(data)
        except FileExistsError:
            if target.read_bytes() == data:
                return False
            raise VaultError("raw_exists", rel) from None
        return True

    def _target(self, rel: str) -> Path:
        code = refusal_for(rel)
        if code is not None:
            raise VaultError(code, rel)
        resolved, target = self._resolve(rel)
        # A link inside wiki/ may point anywhere, so the place the bytes would
        # actually land must pass the same layout check.
        code = refusal_for(resolved)
        if code is not None:
            raise VaultError(code, rel)
        if target.is_dir():
            raise VaultError("unwritable_target", rel)
        return target

    def write(self, rel: str, content: str, *, stamp: str) -> bool:
        """Write one file; returns whether an existing file was backed up first."""
        target = self._target(rel)
        backed_up = self._backup(target, rel, check_stamp(stamp))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return backed_up

    def _backup(self, target: Path, rel: str, stamp: str) -> bool:
        if not target.exists():
            return False
        backup = self.root / BACKUP_DIR / stamp / normalize(rel)
        backup.parent.mkdir(parents=True, exist_ok=True)
        backup.write_bytes(target.read_bytes())
        return True

    def append(self, rel: str, block: str) -> None:
        """Append to an append-only file; the layout check still applies."""
        target = self._target(rel)
        existing = target.read_text(encoding="utf-8") if target.exists() else ""
        target.write_text(existing.rstrip() + "\n" + block, encoding="utf-8")

    def check_against(self, plan: WritePlan) -> tuple[PlanProblem, ...]:
        """The rules that depend on this vault: a target that cannot be written
        (a directory, or a link that lands outside the writable areas), a
        `create` that would replace a page, an `update` of a page that is not
        there. Checked before anything is written."""
        problems: list[PlanProblem] = []
        for page in plan.pages:
            try:
                target = self._target(page.path)
            except VaultError as error:
                problems.append(
                    PlanProblem(code="unwritable_target", path=page.path, detail=error.code)
                )
                continue
            if page.action == "create" and target.exists():
                problems.append(PlanProblem(code="create_exists", path=page.path))
            if page.action == "update" and not target.exists():
                problems.append(PlanProblem(code="update_missing", path=page.path))
        return tuple(problems)

    def apply(
        self,
        plan: WritePlan,
        *,
        mode: Literal["dry_run", "apply"] = "dry_run",
        today: date | None = None,
        stamp: str | None = None,
    ) -> VaultOutcome:
        """Repair what is certain, make conflicts visible, validate against the
        plan and then against this vault, then write — or, in a dry run, report
        exactly what an apply would write. A write that fails part-way is rolled
        back to what the vault held before, and the failure is raised."""
        label = check_stamp(stamp) if stamp is not None else _new_stamp()
        checked = WritePlan.model_validate(plan)
        checked, repairs = repair_wikilinks(checked)
        checked, marked = ensure_conflicts_visible(checked)
        problems = check_plan(checked) or self.check_against(checked)
        if problems:
            return VaultOutcome(mode=mode, problems=problems, repairs=repairs)
        planned = [normalize(page.path) for page in checked.pages]
        if checked.index_entries:
            planned.append("index.md")
        planned.append("log.md")
        if mode == "dry_run":
            return VaultOutcome(
                mode=mode, written=tuple(planned), repairs=repairs, conflict_marker_added=marked
            )
        when = today if today is not None else date.today()
        backed_up = self._write_all(checked, when, label)
        return VaultOutcome(
            mode=mode,
            written=tuple(planned),
            backed_up=backed_up,
            repairs=repairs,
            conflict_marker_added=marked,
        )

    def _write_all(self, plan: WritePlan, when: date, stamp: str) -> tuple[str, ...]:
        """All of the plan's writes, or none: what each target held before is
        kept in memory and put back if any write fails."""
        previous: list[tuple[Path, bytes | None]] = []
        backed_up: list[str] = []

        def remember(rel: str) -> None:
            target = self._target(rel)
            previous.append((target, target.read_bytes() if target.exists() else None))

        try:
            for page in plan.pages:
                remember(page.path)
                if self.write(page.path, page.content.rstrip() + "\n", stamp=stamp):
                    backed_up.append(normalize(page.path))
            if plan.index_entries:
                remember("index.md")
                text = insert_index_entries(self.read("index.md"), plan.index_entries)
                if self.write("index.md", text, stamp=stamp):
                    backed_up.append("index.md")
            remember("log.md")
            self.append("log.md", log_block(plan, when))
        except (OSError, VaultError) as error:
            for target, before in reversed(previous):
                if before is None:
                    target.unlink(missing_ok=True)
                else:
                    target.write_bytes(before)
            raise VaultError("write_failed") from error
        return tuple(backed_up)


def _new_stamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S-%f")
