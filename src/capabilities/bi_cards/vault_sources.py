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
import stat
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from capabilities.bi_cards import homes
from capabilities.bi_cards.store import BiStoreError
from knowledge.repo import repository as repo_engine
from knowledge.repo.repository import RepoError

PREFIX = "source:"
MARKDOWN_DIR = "markdown"
#: Windows: a file's content is not on this PC (a OneDrive placeholder).
_CLOUD_ONLY = 0x00400000 | 0x00040000 | stat.FILE_ATTRIBUTE_OFFLINE
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
    if not homes.LAYOUT.is_source_path(str(value["file"])):
        return "source file must be in a source folder"
    return None if isinstance(value.get("markdown"), list) else "source needs markdown"


def file_path(folder: str, sha256: str, name: str) -> str:
    return f"{folder}/{sha256[:8]}-{_UNSAFE.sub('_', name).strip(' .') or 'source'}"


def markdown_path(folder: str, sha256: str, rev: int, author: str) -> str:
    return f"{folder}/{MARKDOWN_DIR}/{sha256[:8]}/rev-{rev}-{author}.md"


def withdrawn_shas(repo: Any) -> set[str]:
    return {str(item["sha256"]) for item in repo.withdrawn().values()}


def refuse_withdrawn(repo: Any, sha256: str) -> None:
    if sha256 in withdrawn_shas(repo):
        raise BiStoreError("source_withdrawn", "這份檔案已經撤回，不能再放回這個知識庫")


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
    from capabilities.bi_cards import answer_cache
    from capabilities.bi_cards.staging import Staging

    staging = Staging(workspace, dataset)
    gone = withdrawn_shas(repo)
    if gone:
        repo.forget_withdrawn()
        staging.purge_withdrawn(gone)
        answer_cache.clear(staging.store.dir)  # kept answers quote their sources
    units = [
        value
        for key, value in repo.working_units().items()
        if key.startswith(PREFIX) and isinstance(value, dict) and value.get("sha256") not in gone
    ]
    return dict(staging.sync_from_units(units))


def cloud_only(path: Path) -> bool:
    """Whether a file's content is only in the cloud; asks for the attributes and
    does not read the file, so OneDrive downloads nothing."""
    try:
        return bool(getattr(path.lstat(), "st_file_attributes", 0) & _CLOUD_ONLY)
    except OSError:
        return False


def listed(repo: Any, sources: list[dict[str, Any]]) -> dict[str, Any]:
    """The source list for the page with where each one stands: `local` (only on
    this PC), `staged` (waits for a commit and push), `pushed` or `cloud_only`,
    plus the files of commits still waiting for OneDrive."""
    working, pushed = repo.working_units(), repo.units()
    found = []
    for source in sources:
        key = unit_key(source["sha256"])
        value = working.get(key)
        if not isinstance(value, dict):
            state = "local"
        elif key not in pushed:
            state = "staged"
        elif cloud_only(Path(repo.folder) / str(value["file"])):
            state = "cloud_only"
        else:
            state = "pushed"
        folder = value.get("folder") if isinstance(value, dict) else None
        found.append({**source, "shared": state, "folder": folder})
    waiting = sorted({f for item in repo.status()["waiting"] for f in item["files"]})
    withdrawn = [
        {"file": path, **item}
        for path, item in sorted(repo.withdrawn().items())
        if MARKDOWN_DIR not in path.split("/")
    ]
    return {"sources": found, "waiting": waiting, "withdrawn": withdrawn}


def folder_of(units: Mapping[str, Any], sha256: str) -> str | None:
    value = units.get(unit_key(sha256))
    return str(value["folder"]) if isinstance(value, dict) else None


def is_source_change(key_or_path: str) -> bool:
    """Whether a staged unit or file belongs to a source."""
    return key_or_path.startswith(PREFIX) or homes.LAYOUT.is_source_path(key_or_path)


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


def _with_derived(units: Mapping[str, Any], value: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    """A source and what a tool made from it, and from that: they hold its content."""
    found = [value]
    shas = {value["sha256"]}
    others = [v for k, v in units.items() if k.startswith(PREFIX) and isinstance(v, dict)]
    grew = True
    while grew:
        grew = False
        for other in others:
            parent = (other.get("derived_from") or {}).get("sha256")
            if parent in shas and other["sha256"] not in shas:
                found.append(other)
                shas.add(other["sha256"])
                grew = True
    return found


def withdraw(workspace: Path, vault_id: str, given: Mapping[str, Any]) -> dict[str, Any]:
    """Withdraw a pushed source (design §5). Only a person's confirm calls this. It
    removes the file and its Markdown from the shared folder and AEP's copies as
    each PC syncs; not OneDrive's own versions, nor what commits already hold."""
    from capabilities.bi_cards import vault
    from capabilities.bi_cards.staging import Staging

    if given.get("confirm") is not True:
        raise BiStoreError("confirm_required", "撤回要由人按確認")
    target = vault.Vault(workspace, vault_id)
    target._require_folder()
    staging = Staging(workspace, target.dataset)
    source = staging.source(str(given.get("source_id") or ""))
    if source is None:
        raise BiStoreError("source_unknown", "找不到這個來源")
    with target.lock:
        value = target.repo.units().get(unit_key(source["sha256"]))
        if not isinstance(value, dict):
            raise BiStoreError("source_not_pushed", "這個來源還沒有 push，不用撤回")
        files = [
            entry
            for unit in _with_derived(target.repo.units(), value)
            for entry in (
                {"path": unit["file"], "sha256": unit["sha256"]},
                *({"path": item["file"], "sha256": item["sha256"]} for item in unit["markdown"]),
            )
        ]
        try:
            record = target.repo.withdraw(files, str(given.get("reason") or ""))
        except RepoError as failure:
            raise BiStoreError(failure.code, failure.message) from None
    target.sync()
    target.write_cards()  # its excerpts leave the pages now, not at the next publish
    return {"withdrawn": record}


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
