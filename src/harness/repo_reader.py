"""What the change author may read in a run's worktree (`docs/phases/CODING_AT_SCALE.md`).

Read-only and bounded: list a folder, outline a Python file, read a line
range, search text. The model chooses what to read so a large file never has
to fit in one prompt; the host caps every answer. `.git` and credential-shaped
files are never shown. `overlay` holds the author's unsaved versions of the
files it is changing, so it reads what it has written so far.
"""

from __future__ import annotations

import ast
import fnmatch
from collections.abc import Mapping
from pathlib import Path, PurePosixPath

MAX_LIST_ENTRIES = 200
MAX_READ_LINES = 400
MAX_READ_CHARS = 30_000
MAX_SEARCH_HITS = 60
MAX_SEARCH_FILE_BYTES = 2_000_000
MAX_LINE_CHARS = 240
SKIPPED_FOLDERS = frozenset(
    {".git", "__pycache__", ".venv", "venv", "node_modules", ".mypy_cache", ".ruff_cache"}
)
HIDDEN_NAMES = (".env", ".env.*", "*.pem", "*.key", "*.pfx", "*.p12", "id_rsa*", "*.kdbx")


class ReadRefused(Exception):
    """A read the author may not make; the message goes back to the model."""


def _hidden(relative: PurePosixPath) -> bool:
    return (
        bool(SKIPPED_FOLDERS.intersection(relative.parts[:-1]))
        or any(fnmatch.fnmatch(relative.name.lower(), pattern) for pattern in HIDDEN_NAMES)
        or relative.name in SKIPPED_FOLDERS
    )


def _lf(raw: bytes) -> str:
    return raw.decode("utf-8", errors="replace").lstrip("﻿").replace("\r\n", "\n")


class RepoReader:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def _relative(self, raw: str) -> PurePosixPath:
        text = (raw or ".").strip().replace("\\", "/")
        relative = PurePosixPath(text)
        if relative.is_absolute() or ".." in relative.parts or ":" in text:
            raise ReadRefused(f"{raw!r} is not a path inside the repository")
        if relative.parts and _hidden(relative):
            raise ReadRefused(f"{relative.as_posix()} cannot be read")
        return relative

    def _path(self, relative: PurePosixPath) -> Path:
        path = (self.root / relative).resolve()
        if not path.is_relative_to(self.root):
            raise ReadRefused(f"{relative.as_posix()} is outside the repository")
        return path

    def text(self, raw: str, overlay: Mapping[str, str] | None = None) -> str:
        relative = self._relative(raw)
        key = relative.as_posix()
        if overlay and key in overlay:
            return overlay[key]
        path = self._path(relative)
        if not path.is_file():
            raise ReadRefused(f"{key} is not a file")
        return _lf(path.read_bytes())

    def listing(self, raw: str) -> str:
        relative = self._relative(raw)
        path = self._path(relative)
        if not path.is_dir():
            raise ReadRefused(f"{relative.as_posix()} is not a folder")
        lines: list[str] = []
        for item in sorted(path.iterdir(), key=lambda entry: (entry.is_file(), entry.name)):
            child = relative / item.name
            if _hidden(child):
                continue
            if len(lines) >= MAX_LIST_ENTRIES:
                lines.append("(more entries not shown)")
                break
            if item.is_dir():
                lines.append(f"{child.as_posix()}/")
            else:
                lines.append(f"{child.as_posix()}  ({item.stat().st_size} bytes)")
        return "\n".join(lines) or "(empty folder)"

    def outline(self, raw: str, overlay: Mapping[str, str] | None = None) -> str:
        text = self.text(raw, overlay)
        total = text.count("\n") + (0 if text.endswith("\n") or not text else 1)
        head = f"{self._relative(raw).as_posix()}: {total} lines, {len(text)} characters"
        if not raw.strip().endswith(".py"):
            return f"{head}\n(no outline for this file type; read line ranges instead)"
        try:
            tree = ast.parse(text)
        except SyntaxError as error:
            return f"{head}\n(the file does not parse: line {error.lineno}: {error.msg})"
        lines = [head]
        for node in tree.body:
            lines.extend(_outline(node, ""))
        outline = "\n".join(lines)
        if len(outline) > MAX_READ_CHARS:
            cut = outline[:MAX_READ_CHARS].rsplit("\n", 1)[0]
            return f"{cut}\n(outline cut at the answer size limit; search for a name instead)"
        return outline

    def read(self, raw: str, start: int, end: int, overlay: Mapping[str, str] | None = None) -> str:
        rows = self.text(raw, overlay).removesuffix("\n").split("\n")
        first = max(1, start)
        last = min(len(rows), max(first, end), first + MAX_READ_LINES - 1)
        if first > len(rows):
            return f"(the file has {len(rows)} lines)"
        out: list[str] = []
        size = 0
        for number in range(first, last + 1):
            line = f"{number}: {rows[number - 1]}"
            if size + len(line) > MAX_READ_CHARS:
                out.append(f"(stopped at line {number - 1}: answer size limit; read on from here)")
                break
            out.append(line)
            size += len(line) + 1
        else:
            if last < len(rows):
                out.append(f"(lines {last + 1}-{len(rows)} not shown)")
        return "\n".join(out)

    def search(
        self, needle: str, pattern: str = "**/*", overlay: Mapping[str, str] | None = None
    ) -> str:
        if not needle:
            raise ReadRefused('"text" must not be empty')
        lowered = needle.lower()
        hits: list[str] = []
        for path in sorted(self.root.rglob("*")):
            if not path.is_file():
                continue
            relative = PurePosixPath(path.relative_to(self.root).as_posix())
            if _hidden(relative) or not _matches(relative, pattern):
                continue
            key = relative.as_posix()
            if overlay and key in overlay:
                text = overlay[key]
            else:
                if path.stat().st_size > MAX_SEARCH_FILE_BYTES:
                    continue
                raw = path.read_bytes()
                if b"\0" in raw[:8192]:
                    continue
                text = _lf(raw)
            for number, line in enumerate(text.split("\n"), start=1):
                if lowered in line.lower():
                    hits.append(f"{key}:{number}: {line.strip()[:MAX_LINE_CHARS]}")
                    if len(hits) >= MAX_SEARCH_HITS:
                        hits.append("(more matches not shown; narrow the text or the glob)")
                        return "\n".join(hits)
        return "\n".join(hits) or "(no matches)"


def _matches(relative: PurePosixPath, pattern: str) -> bool:
    """fnmatch's `*` crosses folders; `**/` may also match no folder at all."""
    pattern = (pattern or "**/*").strip().replace("\\", "/")
    key = relative.as_posix()
    return fnmatch.fnmatchcase(key, pattern) or fnmatch.fnmatchcase(key, pattern.replace("**/", ""))


def _outline(node: ast.stmt, indent: str) -> list[str]:
    if isinstance(node, ast.ClassDef):
        lines = [f"{indent}class {node.name}: lines {node.lineno}-{node.end_lineno}"]
        for child in node.body:
            lines.extend(_outline(child, indent + "  "))
        return lines
    if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
        return [f"{indent}def {node.name}: lines {node.lineno}-{node.end_lineno}"]
    if not indent and isinstance(node, ast.Assign | ast.AnnAssign):
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        names = [target.id for target in targets if isinstance(target, ast.Name)]
        if names and node.end_lineno is not None and node.end_lineno - node.lineno >= 5:
            return [f"{', '.join(names)} = ...: lines {node.lineno}-{node.end_lineno}"]
    return []
