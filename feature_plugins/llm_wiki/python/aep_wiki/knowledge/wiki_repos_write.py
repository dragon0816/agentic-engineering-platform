"""Wiki knowledge repositories on this PC: what the maintenance writes
(knowledge repositories R4a).

Design: `docs/phases/KNOWLEDGE_REPO.md` §4–§11. The read side (the folder the
Agent reads, the listing) is `knowledge.wiki_repos`, which the Knowledge
asking path uses; this module adds what maintaining a wiki needs around the
common engine's version operations:

- create a new repository (a first schema, `index.md` and `log.md`), import a
  **copy** of an existing wiki folder as one `import` commit (the folder given
  is only read), or join a shared folder;
- words for units on the page (`unit_label`);
- the version operations as the page uses them, and this PC's intake and
  question folders of a repository.

Errors are `RepoError`; the routes answer them.
"""

from __future__ import annotations

import re
import tempfile
import uuid
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from aep_wiki.knowledge import wiki_work
from knowledge.repo import readme, wiki
from knowledge.repo import repository as engine
from knowledge.repo.repository import RepoError, Repository
from knowledge.wiki_repos import KIND, reading_folder, reads, repository

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


def _captured(workspace: Path, repo_id: str) -> Repository:
    """The repository, with what was changed in its working folder staged
    (before anything that reads or moves the working units)."""
    repo = repository(workspace, repo_id)
    wiki_work.capture(repo)
    return repo


def status(workspace: Path, repo_id: str) -> dict[str, Any]:
    repo = _captured(workspace, repo_id)
    try:
        repo.sync()
        state = repo.status()
    except RepoError as failure:
        if failure.code != "repo_unreachable":
            raise
        return {"repo": {"id": repo.id, "path": str(repo.folder)}, "reachable": False}
    return {**state, "repo": describe(repo), "reachable": True, "reads": reads(repo)}


def pending(workspace: Path, repo_id: str) -> dict[str, Any]:
    repo = _captured(workspace, repo_id)
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
    repo = _captured(workspace, repo_id)
    return {"commit": repo.commit(str(given.get("purpose") or ""))}


def discard(workspace: Path, repo_id: str) -> dict[str, Any]:
    """Drop the uncommitted changes, including what was edited in the working
    folder and not captured yet."""
    repo = repository(workspace, repo_id)
    with repo.lock:
        repo.discard()
        wiki_work.reset(repo)
    return {"discarded": True}


def push(workspace: Path, repo_id: str) -> dict[str, Any]:
    repo = _captured(workspace, repo_id)
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
    _captured(workspace, repo_id).resolve(
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
    repo = _captured(workspace, repo_id)
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


def work_settings(workspace: Path, repo_id: str) -> dict[str, Any]:
    """This PC's intake and question folders for the repository."""
    return {"settings": wiki_work.settings(repository(workspace, repo_id))}


def save_work_settings(workspace: Path, repo_id: str, given: Mapping[str, Any]) -> dict[str, Any]:
    chosen = {k: given[k] for k in ("intake", "questions") if k in given}
    return {"settings": wiki_work.save_settings(repository(workspace, repo_id), chosen)}
