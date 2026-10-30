"""The `wiki` repository type on the common version layer (R4 core).

Design: `docs/phases/KNOWLEDGE_REPO.md` §3, §8, §11. A wiki page becomes units
the common engine merges one by one:

    page:<path>#(preamble)        {"body": text}                  text before the first `## `
    page:<path>#<section key>     {"pos": n, "heading": "## …", "body": text,
                                   "correction"?: {"reason", "source"}}
    front:<path>:<field>          {"pos": n, "text": "field: …"}  one top-level frontmatter field,
                                                                  continuation lines included
    front:<path>:(other)          {"pos": -1, "text": …}          frontmatter lines before any field

Section keys are K3.2's (heading text, duplicates numbered `Heading (2)`).
`pos` orders a page's sections and fields; an edit keeps the positions of the
units it does not move, so two people changing different sections never touch
the same unit. Pages are `index.md`, `log.md`, `decisions.md` and Markdown
files under `wiki/`; `wiki/paths/` is written by people only (K3) and refused.

The push checks are K3.2's deletion guard (a sourced line present before and
missing after blocks the push, unless the section carries a correction with
reason and source) and the benchmark gate (KNOWLEDGE_COLLAB.md §6), a callable
registered with `set_benchmark`; without one the push notes that it did not run.
"""

from __future__ import annotations

import hashlib
import re
import shutil
import uuid
from collections.abc import Callable, Mapping
from pathlib import Path, PurePosixPath
from typing import Any

from knowledge.repo.repository import (
    SCHEMA_UNIT,
    SKILL_UNIT_PREFIX,
    CheckReport,
    RepoError,
    Repository,
    canonical,
    register_type,
)
from knowledge.sections import HUMAN_AREAS, correction_of, parse, sourced_lines

NAME = "wiki"
ROOT_PAGES = ("index.md", "log.md", "decisions.md")
PAGE_PREFIX = "page:"
FRONT_PREFIX = "front:"
PREAMBLE = "(preamble)"
OTHER = "(other)"
SOURCES_AREA = "wiki/sources/"
SCHEMA_FILE = "CLAUDE.md"
SCHEMA_PATH = "schemas/wiki.schema@1.0.0.md"
ORIGINAL_AREAS = ("raw", "drop")
#: The marker a materialized folder carries; only such a folder is replaced.
READ_ONLY_NOTE = "README-AEP.md"
FIELD_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_-]*):")
SKILL_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")

#: The benchmark gate: (pages before, pages after) -> a report whose
#: `blocking` lists the questions that regressed.
Benchmark = Callable[[Mapping[str, str], Mapping[str, str]], CheckReport]


def page_path_problem(path: str) -> str | None:
    """Why `path` cannot be a wiki page; None when it can."""
    if path in ROOT_PAGES:
        return None
    if "\\" in path or ":" in path or "#" in path or not path.endswith(".md"):
        return "page path invalid"
    parts = PurePosixPath(path).parts
    if len(parts) < 2 or parts[0] != "wiki":
        return "a page is index.md, log.md, decisions.md or under wiki/"
    if any(p in ("", ".", "..") or p.startswith(".") for p in parts):
        return "page path invalid"
    if any(path.startswith(area) for area in HUMAN_AREAS):
        return "wiki/paths/ is written by people only"
    return None


def split_key(key: str) -> tuple[str, str, str] | None:
    """(`page` | `front`, path, section key or field) of a page unit key."""
    if key.startswith(PAGE_PREFIX):
        path, sep, section = key[len(PAGE_PREFIX) :].partition("#")
        return ("page", path, section) if sep and section else None
    if key.startswith(FRONT_PREFIX):
        path, sep, name = key[len(FRONT_PREFIX) :].rpartition(":")
        return ("front", path, name) if sep and path and name else None
    return None


def _number(value: Any) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


def _value_problem(kind: str, name: str, value: Any) -> str | None:
    if not isinstance(value, dict):
        return "value must be an object"
    if kind == "front":
        if name != OTHER and FIELD_RE.match(f"{name}:") is None:
            return "frontmatter field invalid"
        if set(value) != {"pos", "text"} or not _number(value["pos"]):
            return "frontmatter value is {pos, text}"
        return None if isinstance(value["text"], str) else "frontmatter text must be text"
    if name == PREAMBLE:
        if set(value) != {"body"} or not isinstance(value["body"], str):
            return "preamble value is {body}"
        return None
    allowed = {"pos", "heading", "body", "correction"}
    if not {"pos", "heading", "body"} <= set(value) or not set(value) <= allowed:
        return "section value is {pos, heading, body, correction?}"
    heading = value["heading"]
    if not _number(value["pos"]) or not isinstance(value["body"], str):
        return "section value is {pos, heading, body, correction?}"
    if not isinstance(heading, str) or not heading.startswith("## ") or "\n" in heading:
        return "heading must be one `## ` line"
    if "correction" in value and correction_of(value) is None:
        return "correction needs a reason and a source"
    return None


# -- pages <-> units --------------------------------------------------------------


def _front_groups(front: str) -> list[tuple[str, str]]:
    """A frontmatter block as (field, text) groups in order; lines before the
    first field are `(other)`, later lines belong to the field above them."""
    lines = front.split("\n")[1:-2] if front else []
    groups: list[tuple[str, list[str]]] = []
    for line in lines:
        matched = FIELD_RE.match(line)
        if matched:
            groups.append((matched.group(1), [line]))
        elif groups:
            groups[-1][1].append(line)
        else:
            groups.append((OTHER, [line]))
    seen: dict[str, int] = {}
    found = []
    for name, group in groups:
        seen[name] = seen.get(name, 0) + 1
        key = name if seen[name] == 1 else f"{name}-{seen[name]}"
        found.append((key, "\n".join(group)))
    return found


def page_units(path: str, text: str) -> dict[str, Any]:
    """The units of one page, positions numbered from 0."""
    page = parse(text)
    units: dict[str, Any] = {}
    for number, (name, group) in enumerate(_front_groups(page.front)):
        pos = -1 if name == OTHER else number
        units[f"{FRONT_PREFIX}{path}:{name}"] = {"pos": pos, "text": group}
    if page.preamble:
        units[f"{PAGE_PREFIX}{path}#{PREAMBLE}"] = {"body": "\n".join(page.preamble)}
    for number, (key, (heading, body)) in enumerate(zip(page.keys(), page.sections, strict=True)):
        units[f"{PAGE_PREFIX}{path}#{key}"] = {
            "pos": number,
            "heading": heading,
            "body": "\n".join(body),
        }
    return units


def _order(item: tuple[str, Any]) -> tuple[float, str]:
    return (float(item[1].get("pos", 0)), item[0])


def render_page(units: Mapping[str, Any]) -> str:
    """One page's text from its units (keys of one path only)."""
    fronts, sections, preamble = [], [], None
    for key, value in units.items():
        parts = split_key(key)
        if parts is None:
            continue
        kind, _, name = parts
        if kind == "front":
            fronts.append((name, value))
        elif name == PREAMBLE:
            preamble = value
        else:
            sections.append((name, value))
    lines = [] if preamble is None else str(preamble["body"]).split("\n")
    for _, value in sorted(sections, key=_order):
        lines.extend([str(value["heading"]), *str(value["body"]).split("\n")])
    text = "\n".join(lines).rstrip("\n") + "\n"
    if fronts:
        block = "\n".join(str(v["text"]) for _, v in sorted(fronts, key=_order))
        text = "---\n" + block + "\n---\n" + text
    return text


def pages(units: Mapping[str, Any]) -> dict[str, str]:
    """Every page of a state: path -> text."""
    grouped: dict[str, dict[str, Any]] = {}
    for key, value in units.items():
        parts = split_key(key)
        if parts is not None:
            grouped.setdefault(parts[1], {})[key] = value
    return {path: render_page(grouped[path]) for path in sorted(grouped)}


def _positions(
    new: list[tuple[str, dict[str, Any]]], old: Mapping[str, Any]
) -> list[tuple[str, dict[str, Any]]]:
    """`new` (in page order) with positions that keep every unit's old
    position while the order allows it; moved and added units fit between."""
    kept: list[float | None] = []
    last = float("-inf")
    for key, _ in new:
        earlier = old.get(key)
        pos = (
            float(earlier["pos"])
            if isinstance(earlier, dict) and _number(earlier.get("pos"))
            else None
        )
        if pos is not None and pos > last:
            kept.append(pos)
            last = pos
        else:
            kept.append(None)
    result = []
    low = -1.0
    index = 0
    while index < len(new):
        here = kept[index]
        if here is not None:
            low = here
            result.append((new[index][0], {**new[index][1], "pos": _whole(low)}))
            index += 1
            continue
        end = index
        while end < len(new) and kept[end] is None:
            end += 1
        following = kept[end] if end < len(new) else None
        high = following if following is not None else low + (end - index) + 1
        step = (high - low) / (end - index + 1)
        for offset in range(index, end):
            spot = low + step * (offset - index + 1)
            result.append((new[offset][0], {**new[offset][1], "pos": _whole(spot)}))
        index = end
    return result


def _whole(value: float) -> int | float:
    return int(value) if float(value).is_integer() else value


def page_changes(current: Mapping[str, Any], path: str, text: str | None) -> dict[str, Any]:
    """The unit changes that turn `path` in `current` into `text` (None
    removes the page); untouched units keep their positions."""
    problem = page_path_problem(path)
    if problem:
        raise RepoError("page_invalid", f"{path}: {problem}")
    mine = {k: v for k, v in current.items() if (split_key(k) or ("", "", ""))[1] == path}
    wanted: dict[str, Any] = {}
    if text is not None:
        fresh = page_units(path, text)
        sections = [(k, v) for k, v in fresh.items() if k.startswith(PAGE_PREFIX) and "pos" in v]
        fields = [(k, v) for k, v in fresh.items() if k.startswith(FRONT_PREFIX) and v["pos"] >= 0]
        wanted.update(
            {
                k: v
                for k, v in fresh.items()
                if k.endswith(f"#{PREAMBLE}") or k.endswith(f":{OTHER}")
            }
        )
        for key, value in _positions(sections, mine) + _positions(fields, mine):
            old = mine.get(key)
            if (
                isinstance(old, dict)
                and "correction" in old
                and old.get("body") == value.get("body")
            ):
                value = {**value, "correction": old["correction"]}
            wanted[key] = value
    changes: dict[str, Any] = {}
    for key in sorted(set(mine) | set(wanted)):
        if canonical(mine.get(key)) != canonical(wanted.get(key)):
            changes[key] = wanted.get(key)
    return changes


def stage_page(repo: Repository, path: str, text: str | None) -> int:
    """Stage one page's new text (None removes it) in the working copy;
    returns the number of units changed."""
    changes = page_changes(repo.working_units(), path, text)
    for key, value in changes.items():
        repo.stage(key, value)
    return len(changes)


# -- the type -----------------------------------------------------------------------


class WikiType:
    """The `wiki` type: page sections and frontmatter fields as units."""

    name = NAME

    def __init__(self) -> None:
        self.benchmark: Benchmark | None = None

    def unit_problem(self, key: str, value: Any) -> str | None:
        if key == SCHEMA_UNIT or key.startswith(SKILL_UNIT_PREFIX):
            if not isinstance(value, str) or not value.strip():
                return "value must be a repository file path"
            if key.startswith(SKILL_UNIT_PREFIX) and not SKILL_NAME_RE.match(
                key[len(SKILL_UNIT_PREFIX) :]
            ):
                return "skill name invalid"
            area = "schemas/" if key == SCHEMA_UNIT else "skills/"
            return None if value.startswith(area) else f"value must be under {area}"
        parts = split_key(key)
        if parts is None:
            return "unknown wiki unit"
        kind, path, name = parts
        return page_path_problem(path) or _value_problem(kind, name, value)

    def check(self, before: Mapping[str, Any], after: Mapping[str, Any]) -> CheckReport:
        old, new = pages(before), pages(after)
        blocking = self._lost(before, after, old, new)
        added = sorted(set(new) - set(old))
        removed = sorted(set(old) - set(new))
        changed = sorted(p for p in set(old) & set(new) if old[p] != new[p])
        notes = [f"pages added {len(added)}, changed {len(changed)}, removed {len(removed)}"]
        if self.benchmark is None:
            notes.append("benchmark did not run (no benchmark is set up for this repository)")
        else:
            report = self.benchmark(old, new)
            blocking += report.blocking
            notes += report.notes
        return CheckReport(blocking=blocking, notes=notes)

    @staticmethod
    def _lost(
        before: Mapping[str, Any],
        after: Mapping[str, Any],
        old: Mapping[str, str],
        new: Mapping[str, str],
    ) -> list[str]:
        """The deletion guard per section: a sourced line of a section before
        that no longer appears anywhere on its page, unless the section now
        carries a correction."""
        titles = {
            PurePosixPath(p).stem.casefold() for p in (*old, *new) if p.startswith(SOURCES_AREA)
        }
        found = []
        for key, value in before.items():
            parts = split_key(key)
            if parts is None or parts[0] != "page":
                continue
            path = parts[1]
            text = str(value.get("heading", "")) + "\n" + str(value["body"])
            lines = sourced_lines(text, titles)
            if not lines:
                continue
            later = after.get(key)
            if isinstance(later, dict) and correction_of(later) is not None:
                continue
            kept = {line.strip() for line in new.get(path, "").split("\n")}
            for line in lines:
                if line not in kept:
                    found.append(f"{path}: 有來源的內容會遺失：{line}")
        return found


WIKI = WikiType()
register_type(WIKI)


def set_benchmark(benchmark: Benchmark | None) -> None:
    """Set (or clear) the benchmark gate run on every wiki push."""
    WIKI.benchmark = benchmark


# -- import and materialize -----------------------------------------------------------


def import_vault(repo: Repository, folder: Path) -> dict[str, Any]:
    """Stage an existing wiki vault folder in `repo`'s working copy, for one
    `import` commit (`repo.commit(purpose, kind="import")`): its pages as
    units, `raw/` and `drop/` originals under `sources/`, `CLAUDE.md` as the
    first wiki schema and `skills/*/SKILL.md` as first skill revisions."""
    if repo.kind.name != NAME:
        raise RepoError("repo_type_mismatch", "只有 wiki 類型的知識庫可以匯入 wiki 資料夾")
    if not folder.is_dir():
        raise RepoError("path_missing", f"找不到資料夾 {folder}")
    current = repo.working_units()
    staged_pages = 0
    skipped: list[str] = []
    for path in sorted(_page_files(folder)):
        text = (folder / path).read_text(encoding="utf-8")
        if page_path_problem(path) is not None:
            skipped.append(path)
            continue
        for key, value in page_changes(current, path, text).items():
            repo.stage(key, value)
        staged_pages += 1
    originals = 0
    seen: set[str] = set()
    for area in ORIGINAL_AREAS:
        root = folder / area
        if not root.is_dir():
            continue
        for source in sorted(p for p in root.rglob("*") if p.is_file()):
            rel = source.relative_to(root)
            if any(part.startswith(".") for part in rel.parts):
                continue
            sha8 = _sha(source)[:8]
            parent = rel.parent.as_posix()
            category = parent if parent != "." else "uncategorized"
            target = f"sources/{category}/{sha8}-{rel.name}"
            if target in seen:
                continue
            seen.add(target)
            repo.stage_file(target, source)
            originals += 1
    schema = folder / SCHEMA_FILE
    if schema.is_file():
        repo.stage_file(SCHEMA_PATH, schema)
        repo.stage(SCHEMA_UNIT, SCHEMA_PATH)
    skills = []
    skills_root = folder / "skills"
    if skills_root.is_dir():
        for skill in sorted(p for p in skills_root.iterdir() if (p / "SKILL.md").is_file()):
            if not SKILL_NAME_RE.match(skill.name):
                skipped.append(f"skills/{skill.name}")
                continue
            target = f"skills/{skill.name}/rev-1-{repo.author}.md"
            repo.stage_file(target, skill / "SKILL.md")
            repo.stage(f"{SKILL_UNIT_PREFIX}{skill.name}", target)
            skills.append(skill.name)
    return {
        "pages": staged_pages,
        "originals": originals,
        "schema": SCHEMA_PATH if schema.is_file() else None,
        "skills": skills,
        "skipped": skipped,
    }


def _page_files(folder: Path) -> list[str]:
    found = [name for name in ROOT_PAGES if (folder / name).is_file()]
    wiki = folder / "wiki"
    if wiki.is_dir():
        for path in wiki.rglob("*.md"):
            rel = path.relative_to(folder).as_posix()
            if not any(part.startswith(".") for part in PurePosixPath(rel).parts):
                found.append(rel)
    return found


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _note(units: Mapping[str, Any]) -> str:
    return (
        "# 唯讀檢視（AEP 自動重建）\n\n"
        "This folder is rebuilt by AEP from the knowledge repository on every sync. Edits made "
        "here are lost: change pages in the AEP working copy, commit them with their purpose "
        "and push.\n\n"
        f"Schema: `{units.get(SCHEMA_UNIT) or '-'}`.\n"
    )


def materialize(
    units: Mapping[str, Any], target: Path, *, repo_folder: Path | None = None
) -> dict[str, Any]:
    """Write a state's pages into `target` as an Obsidian-readable wiki.

    The folder is built beside `target` and swapped in; a `target` that exists
    must be empty or carry `README-AEP.md` (a folder AEP made), so a person's
    own vault is never replaced. With `repo_folder`, the current schema is
    copied as `CLAUDE.md` and each skill's current revision as
    `skills/<name>/SKILL.md`."""
    if target.exists() and any(target.iterdir()) and not (target / READ_ONLY_NOTE).is_file():
        raise RepoError("target_not_materialized", f"{target} 不是 AEP 重建的資料夾，不會覆蓋")
    target.parent.mkdir(parents=True, exist_ok=True)
    building = target.parent / f".{target.name}.{uuid.uuid4().hex[:8]}.tmp"
    written = pages(units)
    try:
        for path, text in written.items():
            out = building / path
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(text, encoding="utf-8", newline="\n")
        for name in ("raw", "wiki"):
            (building / name).mkdir(parents=True, exist_ok=True)
        if repo_folder is not None:
            schema = units.get(SCHEMA_UNIT)
            if isinstance(schema, str) and (repo_folder / schema).is_file():
                shutil.copyfile(repo_folder / schema, building / SCHEMA_FILE)
            for key, value in units.items():
                if key.startswith(SKILL_UNIT_PREFIX) and isinstance(value, str):
                    source = repo_folder / value
                    if source.is_file():
                        out = building / "skills" / key[len(SKILL_UNIT_PREFIX) :] / "SKILL.md"
                        out.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copyfile(source, out)
        (building / READ_ONLY_NOTE).write_text(_note(units), encoding="utf-8", newline="\n")
        old = None
        if target.exists():
            old = target.parent / f".{target.name}.{uuid.uuid4().hex[:8]}.old"
            target.rename(old)
        try:
            building.rename(target)
        except OSError:
            if old is not None:
                old.rename(target)  # put the previous view back
            raise
        if old is not None:
            shutil.rmtree(old)
    finally:
        if building.exists():
            shutil.rmtree(building)
    return {"pages": len(written), "path": str(target)}
