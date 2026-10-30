"""Wiki knowledge repositories on this PC (knowledge repositories R4a).

Design: `docs/phases/KNOWLEDGE_REPO.md` §4–§11; owner decisions of 2026-10-30
("Wiring the wiki type (R4)"). A wiki repository is registered in the
workspace (`knowledge.repo.repository` registry, type `wiki`), never in
`host.json`; publishing never moves a folder. The version operations are the
common engine's; this module adds what the wiki needs around them:

- create a new repository (a first schema, `index.md` and `log.md`), import a
  **copy** of an existing wiki folder as one `import` commit (the folder given
  is only read), or join a shared folder;
- words for units on the page (`unit_label`);
- the folder the Agent reads (`reading_folder`): `<local>/published/vault`,
  rebuilt with `wiki.materialize` from the published commit, or the pushed
  head when never published, whenever that target changes (`version.json`).
  This PC's local commits and uncommitted changes never reach it.

Errors are `RepoError`; the routes answer them.
"""

from __future__ import annotations

import json
import re
import tempfile
import uuid
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from knowledge.repo import readme, wiki
from knowledge.repo import repository as engine
from knowledge.repo.repository import RepoError, Repository

KIND = wiki.NAME
PUBLISHED_DIR = "published"
VIEW_DIR = "vault"
MARKER = "version.json"
#: The schema a new wiki repository starts with (the wiki's `CLAUDE.md`).
DEFAULT_SCHEMA = """# Wiki schema

Pages live under `wiki/` (entities, concepts, sources); `index.md` lists them
and `log.md` records every ingest. Every fact on a page names its source page
under `wiki/sources/`, and every source page cites its Raw file under `raw/`.
`wiki/paths/` is written by people only.
"""


def _slug(text: str, limit: int) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:limit].strip("-")


def _parent(value: Any) -> Path:
    text = str(value or "").strip()
    if not text:
        raise RepoError("path_missing", "請填資料夾路徑")
    folder = Path(text)
    if not folder.is_absolute() or not folder.is_dir():
        raise RepoError("path_missing", f"找不到資料夾 {folder}")
    return folder


def _repo_id(given: Mapping[str, Any], title: str) -> str:
    repo_id = str(given.get("id") or "").strip().lower()
    if not repo_id:
        repo_id = f"{_slug(title, engine.MAX_ID - 7) or 'wiki'}-{uuid.uuid4().hex[:6]}"
    return repo_id


def _author(given: Mapping[str, Any], actor: str) -> str:
    return str(given.get("author") or "").strip() or engine.default_author(actor)


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


def _first_commit(repo: Repository, purpose: str, kind: str) -> dict[str, Any]:
    repo.commit(purpose, kind=kind)
    pushed = repo.push()
    readme.write_readme(repo)
    return {"repo": describe(repo), "push": pushed["status"]}


def create(workspace: Path, given: Mapping[str, Any], actor: str) -> dict[str, Any]:
    """A new, empty wiki repository under `path`: the default schema,
    `index.md` and `log.md` in one `schema` commit, pushed."""
    title = str(given.get("title") or "").strip()
    repo = engine.create(
        workspace,
        _parent(given.get("path")),
        repo_id=_repo_id(given, title),
        title=title,
        purpose=str(given.get("purpose") or ""),
        kind=KIND,
        author=_author(given, actor),
    )
    with repo.lock, tempfile.TemporaryDirectory() as scratch:
        schema = Path(scratch) / "schema.md"
        schema.write_text(DEFAULT_SCHEMA, encoding="utf-8", newline="\n")
        repo.stage_file(wiki.SCHEMA_PATH, schema)
        repo.stage(engine.SCHEMA_UNIT, wiki.SCHEMA_REF)
        wiki.stage_page(repo, "index.md", f"# {title}\n\n")
        wiki.stage_page(repo, "log.md", "# Log\n\n")
        return _first_commit(repo, f"建立知識庫，使用 schema {wiki.SCHEMA_REF}", "schema")


def import_copy(workspace: Path, given: Mapping[str, Any], actor: str) -> dict[str, Any]:
    """A new repository under `path` holding the wiki folder `source` as one
    `import` commit (pages, `raw/` and `drop/` originals, `CLAUDE.md`,
    skills). `source` is only read; it may not be inside the new repository."""
    source = Path(str(given.get("source") or "").strip())
    if not source.is_absolute() or not source.is_dir():
        raise RepoError("path_missing", f"找不到要匯入的 wiki 資料夾 {source}")
    if not (source / "index.md").is_file() and not (source / "wiki").is_dir():
        raise RepoError("source_not_wiki", f"{source} 沒有 index.md 也沒有 wiki/，不像 wiki 資料夾")
    parent = _parent(given.get("path"))
    if parent.resolve() == source.resolve() or source.resolve() in parent.resolve().parents:
        raise RepoError("path_invalid", "新知識庫不能放在要匯入的資料夾裡面")
    title = str(given.get("title") or "").strip() or source.name
    repo = engine.create(
        workspace,
        parent,
        repo_id=_repo_id(given, title),
        title=title,
        purpose=str(given.get("purpose") or ""),
        kind=KIND,
        author=_author(given, actor),
    )
    with repo.lock:
        summary = wiki.import_vault(repo, source)
        if engine.SCHEMA_UNIT not in repo.working_units():
            with tempfile.TemporaryDirectory() as scratch:
                schema = Path(scratch) / "schema.md"
                schema.write_text(DEFAULT_SCHEMA, encoding="utf-8", newline="\n")
                repo.stage_file(wiki.SCHEMA_PATH, schema)
                repo.stage(engine.SCHEMA_UNIT, wiki.SCHEMA_REF)
        result = _first_commit(repo, f"匯入 wiki 資料夾「{source.name}」", "import")
    return {**result, "imported": summary}


def join(workspace: Path, given: Mapping[str, Any], actor: str) -> dict[str, Any]:
    """Use an existing shared wiki repository folder on this PC."""
    folder = Path(str(given.get("path") or "").strip())
    document = engine.read_repo_json(folder)
    if document["type"] != KIND:
        raise RepoError("repo_type_mismatch", "這個資料夾不是 wiki 知識庫")
    repo = engine.join(workspace, folder, author=_author(given, actor))
    report = repo.sync()
    return {"repo": describe(repo), "sync": report}


def describe(repo: Repository) -> dict[str, Any]:
    document = repo.document
    return {
        "id": repo.id,
        "title": document["title"],
        "purpose": document.get("purpose") or "",
        "path": str(repo.folder),
        "author": repo.author,
    }


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
    return view, (view.parent / MARKER).read_text(encoding="utf-8")


# -- the version operations, as the page uses them ------------------------------------


def unit_label(units: Mapping[str, Any], key: str) -> str:
    """A unit in words: page and section rather than keys."""
    del units  # wiki keys already carry the page path
    if key == engine.SCHEMA_UNIT:
        return "schema 版本"
    if key.startswith(engine.SKILL_UNIT_PREFIX):
        return f"skill「{key[len(engine.SKILL_UNIT_PREFIX) :]}」"
    if key.startswith(wiki.RAW_PREFIX):
        return f"raw/{key[len(wiki.RAW_PREFIX) :]}"
    parts = wiki.split_key(key)
    if parts is None:
        return key
    kind, path, name = parts
    if kind == "front":
        return f"{path} 的 frontmatter {name}"
    if name == wiki.PREAMBLE:
        return f"{path} 的開頭"
    return f"{path} 的「{name}」"


def status(workspace: Path, repo_id: str) -> dict[str, Any]:
    repo = repository(workspace, repo_id)
    try:
        repo.sync()
        state = repo.status()
    except RepoError as failure:
        if failure.code != "repo_unreachable":
            raise
        return {"repo": {"id": repo.id, "path": str(repo.folder)}, "reachable": False}
    return {**state, "repo": describe(repo), "reachable": True, "reads": reads(repo)}


def pending(workspace: Path, repo_id: str) -> dict[str, Any]:
    repo = repository(workspace, repo_id)
    with repo.lock:
        head = repo.units()
        work = repo._pending()
        names = {**head, **work["sets"]}
        changes = [
            {"unit": k, "label": unit_label(names, k), "before": head.get(k), "after": v}
            for k, v in sorted(work["sets"].items())
        ]
        return {
            "uncommitted": changes,
            "files": sorted(work["files"]),
            "commits": repo.local_commits(),
        }


def commit(workspace: Path, repo_id: str, given: Mapping[str, Any]) -> dict[str, Any]:
    repo = repository(workspace, repo_id)
    return {"commit": repo.commit(str(given.get("purpose") or ""))}


def discard(workspace: Path, repo_id: str) -> dict[str, Any]:
    repository(workspace, repo_id).discard()
    return {"discarded": True}


def push(workspace: Path, repo_id: str) -> dict[str, Any]:
    repo = repository(workspace, repo_id)
    with repo.lock:
        result = repo.push()
        if result["status"] == "pushed":
            readme.write_readme(repo)
        if result["status"] == "conflicts":
            names = repo.working_units()
            for item in result["conflicts"]:
                item["label"] = unit_label(names, item["unit"])
        return result


def resolve(workspace: Path, repo_id: str, given: Mapping[str, Any]) -> dict[str, Any]:
    repository(workspace, repo_id).resolve(
        str(given.get("unit") or ""), str(given.get("choice") or ""), given.get("value")
    )
    return {"resolved": True}


def history(workspace: Path, repo_id: str, limit: int = 50) -> dict[str, Any]:
    repo = repository(workspace, repo_id)
    return {"commits": repo.history(limit), "tags": repo.tags(), "published": repo.published()}


def diff(workspace: Path, repo_id: str, commit_id: str) -> dict[str, Any]:
    repo = repository(workspace, repo_id)
    target = repo.resolve_version(commit_id)
    changes = repo.diff(target)
    names = {**repo.units(), **repo.state_at(target)}
    return {"changes": [{**c, "label": unit_label(names, c["unit"])} for c in changes]}


def revert(workspace: Path, repo_id: str, given: Mapping[str, Any]) -> dict[str, Any]:
    repo = repository(workspace, repo_id)
    record = repo.revert(str(given.get("version") or ""), str(given.get("purpose") or ""))
    return {"commit": record}


def tag(workspace: Path, repo_id: str, given: Mapping[str, Any]) -> dict[str, Any]:
    repo = repository(workspace, repo_id)
    version = str(given.get("version") or "") or None
    record = repo.tag(
        str(given.get("name") or ""), str(given.get("purpose") or ""), version=version
    )
    readme.write_readme(repo)
    return {"tag": record}


def publish(workspace: Path, repo_id: str, given: Mapping[str, Any]) -> dict[str, Any]:
    """Publish a tag. Only a person's confirm click calls this (design §7)."""
    if given.get("confirm") is not True:
        raise RepoError("confirm_required", "發佈要由人按確認")
    repo = repository(workspace, repo_id)
    record = repo.publish(str(given.get("tag") or ""))
    readme.write_readme(repo)
    reading_folder(workspace, repo_id)
    return {"published": record}
