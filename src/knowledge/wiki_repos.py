"""Wiki knowledge repositories on this PC (knowledge repositories R4a).

Design: `docs/phases/KNOWLEDGE_REPO.md` §4–§11; owner decisions of 2026-10-30
("Wiring the wiki type (R4)"). A wiki repository is registered in the
workspace (`knowledge.repo.repository` registry, type `wiki`), never in
`host.json`; publishing never moves a folder. The version operations are the
common engine's. This module is the read side the Knowledge asking path uses
(it stays in core, owner 2026-11-18 D3): the repositories this PC uses, and
the folder the Agent reads (`reading_folder`): `<local>/published/vault`,
rebuilt with `wiki.materialize` from the published commit, or the pushed head
when never published, whenever that target changes (`version.json`). This
PC's local commits and uncommitted changes never reach it. Creating,
importing, joining and the version operations are the Wiki maintenance's
(`knowledge.wiki_repos_write`).

Errors are `RepoError`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from knowledge.repo import repository as engine
from knowledge.repo import wiki
from knowledge.repo.repository import RepoError, Repository

KIND = wiki.NAME
PUBLISHED_DIR = "published"
VIEW_DIR = "vault"
MARKER = "version.json"


def repository(workspace: Path, repo_id: str) -> Repository:
    repo = Repository(workspace, repo_id)
    if repo.kind.name != KIND:
        raise RepoError("repo_type_mismatch", f"知識庫「{repo_id}」不是 wiki")
    return repo


def listing(workspace: Path) -> list[dict[str, Any]]:
    """The wiki repositories this PC uses."""
    found = []
    for item in engine.repositories(workspace):
        if item.get("type") != KIND:
            continue
        entry = {"id": item["id"], "path": item["path"], "author": item["author"]}
        try:
            document = Repository(workspace, str(item["id"])).document
            entry.update(title=document["title"], purpose=document.get("purpose") or "")
            entry["reachable"] = True
        except RepoError:
            entry["reachable"] = False
        found.append(entry)
    return found


# -- what the Agent reads ----------------------------------------------------------


def reads(repo: Repository) -> dict[str, Any]:
    """The published tag, or the pushed head of a repository never published
    (a published commit not applied here yet is read as the head)."""
    record = repo.published()
    applied = {c["id"] for c in repo.history(limit=10**9)}
    if record is not None and record["commit"] in applied:
        return {"tag": record["tag"], "commit": record["commit"]}
    return {"tag": None, "commit": repo.head()}


def reading_folder(workspace: Path, repo_id: str) -> Path:
    """The wiki folder the Agent reads, rebuilt when the version it reads has
    changed. An unreachable shared folder gives the last copy built here, or
    `repo_unreachable` when there is none."""
    repo = repository(workspace, repo_id)
    root = repo.local / PUBLISHED_DIR
    view = root / VIEW_DIR
    try:
        repo.sync()
        target = reads(repo)
    except RepoError as failure:
        if failure.code == "repo_unreachable" and (view / wiki.READ_ONLY_NOTE).is_file():
            return view
        raise
    with repo.lock:
        try:
            built = json.loads((root / MARKER).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            built = None
        if built == target and (view / wiki.READ_ONLY_NOTE).is_file():
            return view
        units = repo.state_at(target["commit"]) if target["commit"] else {}
        wiki.materialize(units, view, repo_folder=repo.folder)
        (root / MARKER).write_text(json.dumps(target), encoding="utf-8")
        return view


def agent_source(workspace: Path, repo_id: str) -> tuple[Path, str]:
    """For the Agent's catalog (`KnowledgeCatalog.register_live`): the folder
    to read and the version built there."""
    view = reading_folder(workspace, repo_id)
    # Its pages and originals keep their names, which can pass Windows' 260 characters.
    return engine.extended(view), (view.parent / MARKER).read_text(encoding="utf-8")
