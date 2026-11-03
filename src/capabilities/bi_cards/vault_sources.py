"""A vault's originals in the repository (`docs/phases/BI_SOURCES_IN_REPOSITORY.md`).

Adding a source to a vault stages its file and a unit `source:<sha256>` (name,
folder, classification, its Markdown revisions), so the list, the history and a
revert go through the version layer and a push delivers the file to the shared
folder. Every classification may be pushed (owner 2026-11-02). They go in their
own commit (`commit_split`): the engine makes a whole commit wait for its files,
and one slow file must not hold back a colleague's cards.

This module knows units and paths; `Staging` calls it after keeping a source on
this PC, and a source a vault could not stage (its shared folder is out of reach)
stays on this PC until `share` is called.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from capabilities.bi_cards.store import BiStoreError
from knowledge.repo import repository as repo_engine
from knowledge.repo.repository import RepoError

PREFIX = "source:"
FILES_ROOT = "sources"
MARKDOWN_DIR = "markdown"
#: The per-file limit in bytes, when one is set; the owner sets the number from
#: the measured sizes, and without it nothing is refused for its size.
LIMIT_UNIT = "meta:source_max_bytes"
_UNSAFE = re.compile(r'[\\/:*?"<>|\x00-\x1f]')


def unit_key(sha256: str) -> str:
    return PREFIX + sha256


def stable_id(sha256: str) -> str:
    """A new source's id, the same on every PC, so evidence means the same."""
    return sha256[:12]


def unit_problem(value: Any) -> str | None:
    if not isinstance(value, dict):
        return "source must be an object"
    if not all(
        isinstance(value.get(k), str) and value[k] for k in ("id", "name", "folder", "file")
    ):
        return "source needs id, name, folder and file"
    if not isinstance(value.get("bytes"), int) or value["bytes"] < 0:
        return "source needs bytes"
    if not str(value["file"]).startswith(FILES_ROOT + "/"):
        return "source file must be under sources/"
    return None if isinstance(value.get("markdown"), list) else "source needs markdown"


def file_path(folder: str, sha256: str, name: str) -> str:
    return f"{folder}/{sha256[:8]}-{_UNSAFE.sub('_', name).strip(' .') or 'source'}"


def markdown_path(folder: str, sha256: str, rev: int, author: str) -> str:
    return f"{folder}/{MARKDOWN_DIR}/{sha256[:8]}/rev-{rev}-{author}.md"


def limit_of(units: Mapping[str, Any]) -> int | None:
    value = units.get(LIMIT_UNIT)
    return int(value) if isinstance(value, str) and value.isdigit() else None


def too_large(size: int, limit: int) -> BiStoreError:
    return BiStoreError(
        "source_too_large",
        f"這個檔案有 {size:,} bytes，超過這個知識庫每個檔案的上限 {limit:,} bytes",
    )


def refuse_over_limit(units: Mapping[str, Any], size: int) -> None:
    limit = limit_of(units)
    if limit is not None and size > limit:
        raise too_large(size, limit)


def over_limit(before: Mapping[str, Any], after: Mapping[str, Any]) -> list[str]:
    """The push check: new sources over the limit, in words."""
    limit = limit_of(after)
    if limit is None:
        return []
    return [
        f"來源「{value['name']}」有 {value['bytes']:,} bytes，超過每個檔案的上限 {limit:,} bytes"
        for key, value in sorted(after.items())
        if key.startswith(PREFIX)
        and key not in before
        and isinstance(value, dict)
        and value.get("bytes", 0) > limit
    ]


def _revision(repo: Any, staging: Any, source_id: str, folder: str, record: dict[str, Any]) -> Any:
    source = staging.source(source_id)
    path = markdown_path(folder, source["sha256"], record["rev"], repo.author)
    repo.stage_file(path, staging.markdown_file(source_id, record["rev"]))
    return {**record, "file": path}


def stage_source(repo: Any, staging: Any, source_id: str, folder: Any = None) -> dict[str, Any]:
    """Stage a source kept on this PC: its original, its Markdown, its unit."""
    from capabilities.bi_cards import vault_skills  # it imports the vault module

    source = staging.source(source_id)
    if source is None:
        raise BiStoreError("source_unknown", "找不到這個來源")
    units = repo.working_units()
    refuse_over_limit(units, int(source["size"]))
    key = unit_key(source["sha256"])
    known = units.get(key)
    if known is not None:
        return dict(known)
    chosen = vault_skills.checked_folder(folder)
    path = file_path(chosen, source["sha256"], source["name"])
    repo.stage_file(path, staging.stored_file(source_id))
    revisions = [
        _revision(repo, staging, source_id, chosen, record)
        for record in sorted(staging.markdown_revisions(source_id), key=lambda r: r["rev"])
    ]
    value = {
        "id": source["id"],
        "name": source["name"],
        "folder": chosen,
        "file": path,
        "sha256": source["sha256"],
        "bytes": int(source["size"]),
        "media_type": source["media_type"],
        "classification": source["classification"],
        "by": source["by"],
        "at": source["at"],
        "markdown": revisions,
    }
    repo.stage(key, value)
    return value


def stage_revision(repo: Any, staging: Any, source_id: str, rev: int) -> None:
    """Stage a new Markdown revision of a source already in the repository."""
    source = staging.source(source_id)
    if source is None:
        return
    key = unit_key(source["sha256"])
    value = repo.working_units().get(key)
    if not isinstance(value, dict):
        stage_source(repo, staging, source_id)
        return
    if any(item.get("rev") == rev for item in value["markdown"]):
        return
    record = next(r for r in staging.markdown_revisions(source_id) if r["rev"] == rev)
    added = _revision(repo, staging, source_id, value["folder"], record)
    repo.stage(key, {**value, "markdown": [*value["markdown"], added]})


def sync_staging(repo: Any, workspace: Path, dataset: str) -> dict[str, int]:
    """This PC's source list from the repository (a colleague's sources read
    through); it writes nothing to the shared folder."""
    from capabilities.bi_cards.staging import Staging

    units = [
        value
        for key, value in repo.working_units().items()
        if key.startswith(PREFIX) and isinstance(value, dict)
    ]
    return dict(Staging(workspace, dataset).sync_from_units(units))


def folder_of(units: Mapping[str, Any], sha256: str) -> str | None:
    value = units.get(unit_key(sha256))
    return str(value["folder"]) if isinstance(value, dict) else None


def is_source_change(key_or_path: str) -> bool:
    """Whether a staged unit or file belongs to a source."""
    return key_or_path.startswith((PREFIX, FILES_ROOT + "/"))


def commit_split(repo: Any, purpose: str) -> dict[str, Any]:
    """Commit what is staged, the sources in a commit of their own when there is
    anything else, so a colleague's cards never wait for a slow file."""
    pending = repo._pending()
    names = [v["name"] for k, v in pending["sets"].items() if k.startswith(PREFIX) and v]
    sources = any(is_source_change(k) for k in (*pending["sets"], *pending["files"]))
    others = any(not is_source_change(k) for k in (*pending["sets"], *pending["files"]))
    if sources and others:
        repo.commit(_sources_purpose(names), only=is_source_change)
    return dict(repo.commit(purpose))


def _sources_purpose(names: list[str]) -> str:
    listed = "、".join(names[:5]) + ("…" if len(names) > 5 else "")
    return f"加入來源：{listed}"[: repo_engine.MAX_PURPOSE] if listed else "更新來源的 Markdown"


def share(workspace: Path, vault_id: str, source_id: str, folder: Any) -> dict[str, Any]:
    """Stage a source that is only on this PC (added while the shared folder was
    out of reach, or dropped with a discard)."""
    from capabilities.bi_cards import vault
    from capabilities.bi_cards.staging import Staging

    target = vault.Vault(workspace, vault_id)
    target._require_folder()
    try:
        with target.lock:
            return stage_source(target.repo, Staging(workspace, target.dataset), source_id, folder)
    except RepoError as failure:
        raise BiStoreError(failure.code, failure.message) from None
