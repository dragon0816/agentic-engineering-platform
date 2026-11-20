"""A home's tools (`docs/phases/BI_CARD_MODEL.md` §4): the immutable revisions.

A revision is a file `<home>/tools/<name>/rev-<n>-<author>.<ext>`, written once;
`tool:<home>/<name>` names the current one. Running one in an ingest: `tool_runs`.

A Python revision's unit also carries `description`, the first paragraph of its module
docstring, when it has one; a revision imported from a package that does not follow the
INPUT/OUTPUT contract yet carries `needs_rewrite` (owner 2026-11-19: 「需改寫」), which
`tool_runs.run` refuses until a rewritten revision replaces it.
"""

from __future__ import annotations

import ast
import hashlib
import re
import uuid
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from aep_bi.cards import card_model, homes
from aep_bi.cards.store import BiStoreError

_SUFFIX = re.compile(r"^\.[a-z0-9]{1,10}$")
MAX_TEXT = 200_000
MAX_DESCRIPTION = 300


def unit_key(home: str, name: str) -> str:
    return f"{card_model.TOOL_PREFIX}{home}/{name}"


def description_of(text: str) -> str:
    """The first paragraph of a Python tool's module docstring; empty without one."""
    try:
        doc = ast.get_docstring(ast.parse(text)) or ""
    except (SyntaxError, ValueError):
        return ""
    first = doc.strip().split("\n\n", 1)[0]
    return " ".join(first.split())[:MAX_DESCRIPTION]


def stage_file(
    repo: Any,
    home: str,
    name: str,
    source: Path,
    *,
    description: str = "",
    needs_rewrite: bool = False,
) -> dict[str, Any]:
    """Stage `source` as the next revision of the tool `name` of `home`."""
    problem = homes.home_problem(home)
    if problem:
        raise BiStoreError("tool_invalid", f"home「{home}」{problem}")
    if homes.id_problem(name):
        raise BiStoreError("tool_invalid", "工具名稱只能用小寫英數字與 -")
    suffix = source.suffix.lower()
    if not _SUFFIX.match(suffix):
        raise BiStoreError("tool_invalid", "工具檔案要有副檔名")
    key = unit_key(home, name)
    current = repo.working_units().get(key)
    revision = int(current["revision"]) + 1 if isinstance(current, dict) else 1
    path = homes.tool_path(home, name, revision, repo.author, suffix)
    repo.stage_file(path, source)
    value = {
        "revision": revision,
        "author": repo.author,
        "path": path,
        "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
    }
    description = " ".join(str(description or "").split())[:MAX_DESCRIPTION]
    if suffix == ".py":
        description = (
            description_of(source.read_text(encoding="utf-8", errors="replace")) or description
        )
    if description:
        value["description"] = description
    if needs_rewrite:
        value["needs_rewrite"] = True
    repo.stage(key, value)
    return {"name": f"{home}/{name}", **value}


def stage_text(repo: Any, given: Mapping[str, Any]) -> dict[str, Any]:
    """`stage_file` for a tool sent as text: `home`, `name`, `suffix`, `text`; optional
    `description` (used when the code has no docstring) and `needs_rewrite`."""
    text = given.get("text")
    if not isinstance(text, str) or not text.strip():
        raise BiStoreError("tool_invalid", "工具內容不能是空的")
    if len(text) > MAX_TEXT:
        raise BiStoreError("tool_invalid", f"工具內容最多 {MAX_TEXT} 字")
    suffix = str(given.get("suffix") or "").lower()
    if not _SUFFIX.match(suffix):
        raise BiStoreError("tool_invalid", "suffix 必須是副檔名，例如 .py")
    draft = repo.local / "drafts" / f"{uuid.uuid4().hex[:8]}{suffix}"
    draft.parent.mkdir(parents=True, exist_ok=True)
    draft.write_bytes(text.encode())
    try:
        return stage_file(
            repo,
            str(given.get("home") or ""),
            str(given.get("name") or ""),
            draft,
            description=str(given.get("description") or ""),
            needs_rewrite=given.get("needs_rewrite") is True,
        )
    finally:
        draft.unlink(missing_ok=True)


def current_tools(units: Mapping[str, Any]) -> list[dict[str, Any]]:
    """The current tools, as a list for people."""
    return [
        {"name": key.removeprefix(card_model.TOOL_PREFIX), **value}
        for key, value in sorted(units.items())
        if key.startswith(card_model.TOOL_PREFIX) and isinstance(value, dict)
    ]
