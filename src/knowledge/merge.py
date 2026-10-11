"""Three-way merge of a sandbox into its published vault (K3.3, owner 2026-10-11).

`docs/phases/KNOWLEDGE_K3.md` section 4. The base is the published vault as the
sandbox copied it (`.base/` in the sandbox, or the published vault itself when it
has not changed since). Per page and per `## ` section:

- changed only in the sandbox -> taken; changed only in published -> kept;
- changed on both sides, differently -> a conflict, merged only once a person
  picks `sandbox` or `published` for it;
- new pages and new Raw are a union (Raw is immutable: the same path with other
  bytes is a conflict); a page the sandbox removed is kept.

Frontmatter merges field by field; `updated` takes the later date. `index.md`
takes the lines the sandbox added; `log.md` takes the entries it appended;
`decisions.md` merges as one unit. The merge writes a new candidate vault and
never edits the published one.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from common.base import Contract
from knowledge.sections import Page, like_endings, parse

# The schema and category rules (K3.1) merge like pages, so a domain owner's
# rule change in a sandbox reaches the published vault.
ROOT_FILES = ("index.md", "log.md", "decisions.md", "CLAUDE.md")
AREAS = ("wiki", "raw", "skills")
TEXT_AREAS = ("wiki", "skills")
PREAMBLE = "(preamble)"
Resolution = Literal["sandbox", "published"]


class MergeConflict(Contract):
    path: str
    part: str  # a section heading, "(preamble)", "frontmatter:<field>" or "page"
    sandbox: str
    published: str

    @property
    def key(self) -> str:
        return f"{self.path}#{self.part}"


class MergeChange(Contract):
    path: str
    change: Literal["added", "taken", "merged"]
    parts: tuple[str, ...] = ()
    proposal: bool = False  # outside the sandbox's domain or a shared page


@dataclass
class MergeResult:
    files: dict[str, bytes] = field(default_factory=dict)  # what changes in published
    changes: list[MergeChange] = field(default_factory=list)
    conflicts: list[MergeConflict] = field(default_factory=list)
    kept_removed: list[str] = field(default_factory=list)


def read_tree(root: Path, *, raw: bool = True) -> dict[str, bytes]:
    files: dict[str, bytes] = {}
    for area in AREAS if raw else TEXT_AREAS:
        folder = root / area
        if folder.is_dir():
            for path in sorted(folder.rglob("*")):
                if path.is_file():
                    files[path.relative_to(root).as_posix()] = path.read_bytes()
    for name in ROOT_FILES:
        if (root / name).is_file():
            files[name] = (root / name).read_bytes()
    return files


def _text(data: bytes | None) -> str | None:
    return None if data is None else data.decode("utf-8").replace("\r\n", "\n")


def _front_fields(front: str) -> dict[str, str]:
    """Top-level frontmatter fields with their continuation lines."""
    fields: dict[str, str] = {}
    key = None
    for line in front.split("\n")[1:-2] if front else []:
        if line and not line.startswith((" ", "\t", "- ")) and ":" in line:
            key = line.split(":", 1)[0].strip()
            fields[key] = line
        elif key is not None:
            fields[key] += "\n" + line
    return fields


def _pick(base: str | None, sandbox: str | None, published: str | None,
          ) -> tuple[str | None, bool]:
    """(result, conflict) for one part; None is an absent part."""
    if sandbox == base or sandbox == published:
        return published, False
    if published == base:
        return (published if sandbox is None else sandbox), False
    return published, True


def _merge_parts(
    path: str, order: list[str], b: dict[str, str], s: dict[str, str], p: dict[str, str],
    resolutions: dict[str, Resolution], label: str = "",
) -> tuple[dict[str, str], list[str], list[MergeConflict]]:
    merged: dict[str, str] = {}
    taken: list[str] = []
    conflicts: list[MergeConflict] = []
    for key in order:
        result, conflict = _pick(b.get(key), s.get(key), p.get(key))
        part = f"{label}{key}"
        if conflict:
            choice = resolutions.get(f"{path}#{part}")
            if choice == "sandbox":
                result = s.get(key)
                taken.append(part)
            elif choice != "published":
                conflicts.append(MergeConflict(path=path, part=part, sandbox=s.get(key) or "",
                                               published=p.get(key) or ""))
        elif result != p.get(key):
            taken.append(part)
        if result is not None:
            merged[key] = result
    return merged, taken, conflicts


def _later(a: str, b: str) -> str:
    def date(line: str) -> str:
        return line.split(":", 1)[1].strip().strip("\"'")
    return a if date(a) >= date(b) else b


def _parts(page: Page) -> dict[str, str]:
    found = {PREAMBLE: "\n".join(page.preamble)}
    for key, (heading, body) in zip(page.keys(), page.sections, strict=True):
        found[key] = "\n".join([heading, *body])
    return found


def merge_page(path: str, base: str, sandbox: str, published: str,
               resolutions: dict[str, Resolution]) -> tuple[str, list[str], list[MergeConflict]]:
    """A page changed on both sides, merged by frontmatter field and section."""
    pb, ps, pp = parse(base), parse(sandbox), parse(published)
    fb, fs, fp = _front_fields(pb.front), _front_fields(ps.front), _front_fields(pp.front)
    if "updated" in fs and "updated" in fp and fs["updated"] != fp["updated"]:
        fs = {**fs, "updated": _later(fs["updated"], fp["updated"])}
        fp = {**fp, "updated": fs["updated"]}
    order = [*fp, *(k for k in fs if k not in fp)]
    front, taken, conflicts = _merge_parts(path, order, fb, fs, fp, resolutions, "frontmatter:")

    sb, ss, sp = _parts(pb), _parts(ps), _parts(pp)
    order = [*sp, *(k for k in ss if k not in sp)]
    body, more_taken, more_conflicts = _merge_parts(path, order, sb, ss, sp, resolutions)
    head = "---\n" + "\n".join(front.values()) + "\n---\n" if front else ""
    preamble = body.pop(PREAMBLE, "").strip("\n")
    blocks = [block.strip("\n") for block in (preamble, *body.values()) if block.strip()]
    text = head + "\n\n".join(blocks) + "\n"
    return text, taken + more_taken, conflicts + more_conflicts


def _merge_index(base: str, sandbox: str, published: str) -> str:
    """The lines the sandbox added, under the same heading in published."""
    known = set(base.split("\n")) | set(published.split("\n"))
    lines = published.rstrip("\n").split("\n")
    heading = ""
    for line in sandbox.split("\n"):
        if line.startswith("#"):
            heading = line
            continue
        if not line.strip() or line in known:
            continue
        at = lines.index(heading) + 1 if heading in lines else len(lines)
        while at < len(lines) and not lines[at].startswith("#"):
            at += 1
        while at > 0 and not lines[at - 1].strip():
            at -= 1
        lines.insert(at, line)
        known.add(line)
    return "\n".join(lines) + "\n"


def _merge_log(base: str, sandbox: str, published: str) -> str:
    added = sandbox[len(base):] if sandbox.startswith(base) else ""
    return published.rstrip("\n") + "\n" + added.lstrip("\n") if added.strip() else published


def three_way(
    base: dict[str, bytes], sandbox: dict[str, bytes], published: dict[str, bytes],
    resolutions: dict[str, Resolution] | None = None,
    in_scope: Iterable[str] | None = None,
) -> MergeResult:
    """`base` holds wiki and root files; Raw needs no base because it is a union.
    `in_scope` lists the sandbox's in-domain pages; others become proposals."""
    chosen = resolutions or {}
    scope = set(in_scope) if in_scope is not None else None
    result = MergeResult()
    for rel in sorted(set(sandbox) | set(base)):
        b, s, p = base.get(rel), sandbox.get(rel), published.get(rel)
        if s == p or (s == b and not rel.startswith("raw/")):
            continue
        proposal = scope is not None and rel.startswith("wiki/") and rel not in scope
        if s is None:
            result.kept_removed.append(rel)
            continue
        if rel.startswith("raw/") or not rel.endswith(".md"):
            if p is None:
                result.files[rel] = s
                result.changes.append(MergeChange(path=rel, change="added"))
            elif b is not None and p == b and not rel.startswith("raw/"):
                result.files[rel] = s
                result.changes.append(MergeChange(path=rel, change="taken"))
            elif chosen.get(f"{rel}#page") == "sandbox" and not rel.startswith("raw/"):
                result.files[rel] = s
            else:
                result.conflicts.append(MergeConflict(path=rel, part="page", sandbox="(binary)",
                                                      published="(binary)"))
            continue
        bt, st, pt = _text(b), _text(s) or "", _text(p)
        if pt is None:  # new in the sandbox, or removed from published
            result.files[rel] = s
            result.changes.append(MergeChange(path=rel, change="added", proposal=proposal))
        elif bt is None or bt == pt:  # both added it, or only the sandbox changed it
            if bt is None:
                choice = chosen.get(f"{rel}#page")
                if choice == "sandbox":
                    result.files[rel] = s
                elif choice != "published":
                    result.conflicts.append(MergeConflict(path=rel, part="page", sandbox=st,
                                                          published=pt))
                continue
            result.files[rel] = s
            result.changes.append(MergeChange(path=rel, change="taken", proposal=proposal))
        elif rel == "index.md":
            result.files[rel] = _merge_index(bt, st, pt).encode("utf-8")
            result.changes.append(MergeChange(path=rel, change="merged"))
        elif rel == "log.md":
            result.files[rel] = _merge_log(bt, st, pt).encode("utf-8")
            result.changes.append(MergeChange(path=rel, change="merged"))
        elif rel == "decisions.md":
            choice = chosen.get(f"{rel}#page")
            if choice == "sandbox":
                result.files[rel] = s
            elif choice != "published":
                result.conflicts.append(MergeConflict(path=rel, part="page", sandbox=st,
                                                      published=pt))
        else:
            text, parts, conflicts = merge_page(rel, bt, st, pt, chosen)
            result.conflicts.extend(conflicts)
            if text != pt:
                original = (p or b"").decode("utf-8")
                result.files[rel] = like_endings(text, original).encode("utf-8")
                result.changes.append(MergeChange(path=rel, change="merged", parts=tuple(parts),
                                                  proposal=proposal))
    return result


def decode_key(key: str) -> tuple[str, str]:
    path, _, part = key.partition("#")
    if not path or not part or re.search(r"[\0]", key):
        raise ValueError("a resolution key is <path>#<part>")
    return path, part
