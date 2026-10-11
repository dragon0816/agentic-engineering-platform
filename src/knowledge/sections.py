"""Section-level page edits and the deletion guard (K3.2, owner 2026-10-11).

`docs/phases/KNOWLEDGE_K3.md` section 3. An ingest plan changes an existing
page by sections, not by rewriting it: the Host builds the new page from the
current one, so the model cannot drop what it did not mean to touch. The guard
is the Host's, not the prompt's: a change that loses a sourced line (one that
links a source page, or a ⚠️ contradiction line) is refused unless it is a
correction that names its reason and source.

A section is a `## ` heading and the lines under it up to the next `## `;
deeper headings belong to their section. Duplicate headings are told apart as
`Heading (2)`, `Heading (3)`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from common.base import Contract

WIKILINK = re.compile(r"\[\[([^\]|#]+)(?:[|#][^\]]*)?\]\]")
FRONTMATTER = re.compile(r"\A---\n.*?\n---\n", re.DOTALL)
OPS = ("add_section", "append_to_section", "replace_section", "set_frontmatter")
HUMAN_AREAS = ("wiki/paths/",)


class SectionError(ValueError):
    """An operation that cannot apply to this page; the code is closed."""

    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}" if detail else code)


@dataclass
class Page:
    front: str  # the frontmatter block, delimiters included, or ""
    preamble: list[str] = field(default_factory=list)
    sections: list[tuple[str, list[str]]] = field(default_factory=list)  # (heading line, body)

    def keys(self) -> list[str]:
        seen: dict[str, int] = {}
        keys = []
        for heading, _ in self.sections:
            name = heading[3:].strip()
            seen[name] = seen.get(name, 0) + 1
            keys.append(name if seen[name] == 1 else f"{name} ({seen[name]})")
        return keys

    def find(self, heading: str) -> int:
        wanted = heading.strip().lstrip("#").strip()
        for number, key in enumerate(self.keys()):
            if key == wanted:
                return number
        raise SectionError("section_missing", wanted)

    def render(self) -> str:
        lines = [*self.preamble]
        for heading, body in self.sections:
            lines.extend([heading, *body])
        text = "\n".join(lines).rstrip("\n") + "\n"
        return self.front + text


def parse(text: str) -> Page:
    text = text.replace("\r\n", "\n")
    match = FRONTMATTER.match(text)
    front = match.group(0) if match else ""
    page = Page(front=front)
    current: list[str] = page.preamble
    for line in text[len(front):].split("\n"):
        if line.startswith("## "):
            body: list[str] = []
            page.sections.append((line.rstrip(), body))
            current = body
        else:
            current.append(line)
    return page


def _body(content: str) -> list[str]:
    lines = content.replace("\r\n", "\n").strip("\n").split("\n")
    return ["", *lines, ""] if content.strip() else [""]


def _set_fields(front: str, fields: dict[str, object]) -> str:
    """Replace or add top-level frontmatter fields; other lines stay as they are."""
    lines = front.split("\n")[1:-2] if front else []
    for key, value in fields.items():
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]*", key) or key == "title":
            raise SectionError("bad_field", key)
        rendered = f"{key}: {_yaml(value)}"
        start = next((i for i, line in enumerate(lines) if line.startswith(f"{key}:")), None)
        if start is None:
            lines.append(rendered)
            continue
        end = start + 1
        while end < len(lines) and lines[end].startswith((" ", "\t", "- ")):
            end += 1
        lines[start:end] = [rendered]
    return "---\n" + "\n".join(lines) + "\n---\n"


def _yaml(value: object) -> str:
    if isinstance(value, list):
        return "[" + ", ".join(_yaml(item) for item in value) + "]"
    text = str(value).replace("\n", " ")
    return '"' + text.replace('"', "'") + '"' if re.search(r"[:#\[\]{},]", text) else text


def apply_op(text: str, op: dict[str, object]) -> str:
    """The page after one section operation."""
    kind = op.get("op")
    page = parse(text)
    heading = str(op.get("heading") or "").strip().lstrip("#").strip()
    content = str(op.get("content") or "")
    if kind == "set_frontmatter":
        fields = op.get("fields")
        if not isinstance(fields, dict) or not fields:
            raise SectionError("bad_operation", "set_frontmatter needs fields")
        page.front = _set_fields(page.front, fields)
        return page.render()
    if not heading:
        raise SectionError("bad_operation", f"{kind} needs a heading")
    if kind == "add_section":
        if not content.strip():
            raise SectionError("bad_operation", "empty section")
        if page.sections and page.sections[-1][1] and page.sections[-1][1][-1].strip():
            page.sections[-1][1].append("")
        elif not page.sections and page.preamble and page.preamble[-1].strip():
            page.preamble.append("")
        page.sections.append((f"## {heading}", _body(content)))
    elif kind == "append_to_section":
        body = page.sections[page.find(heading)][1]
        while body and not body[-1].strip():
            body.pop()
        body.extend([*_body(content)[1:]] if body else _body(content))
    elif kind == "replace_section":
        number = page.find(heading)
        page.sections[number] = (page.sections[number][0], _body(content))
    else:
        raise SectionError("bad_operation", str(kind))
    return page.render()


def sourced_lines(text: str, source_titles: set[str]) -> list[str]:
    """Body lines that carry evidence: they link a source page or record a
    contradiction (⚠️). Compared stripped, so re-indenting is not a loss."""
    body = text[len(parse(text).front):]
    found = []
    for line in body.split("\n"):
        clean = line.strip()
        if not clean:
            continue
        links = {m.group(1).strip().casefold() for m in WIKILINK.finditer(clean)}
        if "⚠️" in clean or links & source_titles:
            found.append(clean)
    return found


def lost_lines(before: str, after: str, source_titles: set[str]) -> list[str]:
    kept = {line.strip() for line in after.replace("\r\n", "\n").split("\n")}
    return [line for line in sourced_lines(before, source_titles) if line not in kept]


def like_endings(text: str, original: str) -> str:
    """`text` with the line endings `original` uses, so a section edit of a
    Windows (CRLF) page changes only the lines it meant to change."""
    plain = text.replace("\r\n", "\n")
    return plain.replace("\n", "\r\n") if "\r\n" in original else plain


class Correction(Contract):
    reason: str
    source: str


def correction_of(op: dict[str, object]) -> Correction | None:
    raw = op.get("correction")
    if not isinstance(raw, dict):
        return None
    try:
        found = Correction.model_validate(raw)
    except ValueError:
        return None
    return found if found.reason.strip() and found.source.strip() else None
