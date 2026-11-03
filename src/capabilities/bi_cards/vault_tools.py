"""A home's tools (`docs/phases/BI_CARD_MODEL.md` §4): stored and listed, never run.

A revision is a file `<home>/tools/<name>/rev-<n>-<author>.<ext>`, written once;
`tool:<home>/<name>` names the current one. Running a tool in an ingest is Phase 2.
"""

from __future__ import annotations

import hashlib
import re
import uuid
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from capabilities.bi_cards import card_model, homes
from capabilities.bi_cards.store import BiStoreError

_SUFFIX = re.compile(r"^\.[a-z0-9]{1,10}$")
MAX_TEXT = 200_000


def unit_key(home: str, name: str) -> str:
    return f"{card_model.TOOL_PREFIX}{home}/{name}"


def stage_file(repo: Any, home: str, name: str, source: Path) -> dict[str, Any]:
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
    repo.stage(key, value)
    return {"name": f"{home}/{name}", **value}


def stage_text(repo: Any, given: Mapping[str, Any]) -> dict[str, Any]:
    """`stage_file` for a tool sent as text: `home`, `name`, `suffix`, `text`."""
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
        return stage_file(repo, str(given.get("home") or ""), str(given.get("name") or ""), draft)
    finally:
        draft.unlink(missing_ok=True)


def current_tools(units: Mapping[str, Any]) -> list[dict[str, Any]]:
    """The current tools, as a list for people; nothing here runs one."""
    return [
        {"name": key.removeprefix(card_model.TOOL_PREFIX), **value}
        for key, value in sorted(units.items())
        if key.startswith(card_model.TOOL_PREFIX) and isinstance(value, dict)
    ]
