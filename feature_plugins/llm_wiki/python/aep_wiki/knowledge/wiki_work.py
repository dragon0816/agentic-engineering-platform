"""The working folder of a wiki repository (knowledge repositories R4a, R4b).

The ingest pipeline (convert, plan, apply, the rule editor) works on a wiki
folder. Instead of a sandbox copied from a live vault, each repository has a
working folder `<workspace>/knowledge-repos/<id>/work-view/vault`, built from
the working copy's units (`open_work`). After a step writes there, `capture`
stages what changed back into the working copy, to be committed with a
purpose and pushed like any change:

- a page (`index.md`, `log.md`, `decisions.md`, `wiki/**.md`) → the section
  and frontmatter units that differ from the page as it was built; a deleted
  page → its built units removed;
- a new file under `raw/` → an original under `sources/<folder>/` and its
  `raw:<path>` unit; Raw is immutable, so a changed or removed Raw file is
  reported, never staged;
- a new file under `drop/` → an original under `sources/<folder>/`;
- an edited `skills/<folder>/SKILL.md` → the next revision of that skill
  (role `ingest`, bound to the current schema);
- an edited `CLAUDE.md` → the next schema version (`wiki.schema@<x.y.z+1>`):
  skills written for the old version then show 「需要更新」 (decision 3).

Changes are found against what the folder was built from (`work-view/base/`
holds the built pages, `state.json` the built Raw, skill and schema digests),
not against the working units: a sync that brought someone else's change in
the meantime is never undone by a capture. The folder is rebuilt whenever the
working units differ from the ones it was built from; what was edited in it
is captured first, and `drop/` and hidden files (`.ingest-state.json`,
`.plans/`, `.benchmarks/` …) are carried into the rebuilt folder; they stay on
this PC. `reset` rebuilds without capturing (after a discard).

Each PC also keeps, per repository, where the 「拉資料」 step pulls originals
from and where the question sets are (`settings`, owner 2026-10-31).
"""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import uuid
from collections.abc import Mapping
from pathlib import Path, PurePosixPath
from typing import Any

from knowledge.repo import skills, wiki
from knowledge.repo.repository import SCHEMA_UNIT, RepoError, Repository, canonical

WORK_VIEW = "work-view"
VIEW = "vault"
BASE = "base"
STATE = "state.json"
SETTINGS = "settings.json"
#: Local entries of the working folder carried into a rebuilt one.
KEPT = ("drop",)


def _units_key(repo: Repository) -> str:
    return hashlib.sha256(canonical(repo.working_units()).encode("utf-8")).hexdigest()


def _text_sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _plain(path: Path) -> str:
    return path.read_text(encoding="utf-8").replace("\r\n", "\n")


def work_folder(repo: Repository) -> Path:
    return repo.local / WORK_VIEW / VIEW


def _read_state(repo: Repository) -> dict[str, Any]:
    try:
        state = json.loads((repo.local / WORK_VIEW / STATE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return state if isinstance(state, dict) else {}


def _write_state(repo: Repository, state: Mapping[str, Any]) -> None:
    (repo.local / WORK_VIEW / STATE).write_text(json.dumps(dict(state)), encoding="utf-8")


# -- per-PC settings ------------------------------------------------------------------


def settings(repo: Repository) -> dict[str, Any]:
    """This PC's intake folder (pulled from), question folder and pulled folders."""
    try:
        saved = json.loads((repo.local / SETTINGS).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        saved = {}
    if not isinstance(saved, dict):
        saved = {}
    return {
        "intake": saved.get("intake") or None,
        "questions": saved.get("questions") or None,
        "pulled": [str(p) for p in saved.get("pulled") or []],
    }


def _folder_setting(value: Any, label: str) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    folder = Path(text)
    if not folder.is_absolute() or not folder.is_dir():
        raise RepoError("path_missing", f"找不到{label} {folder}")
    return str(folder)


def save_settings(repo: Repository, given: Mapping[str, Any]) -> dict[str, Any]:
    """Set the folders named in `given` (an empty value clears one)."""
    current = settings(repo)
    if "intake" in given:
        current["intake"] = _folder_setting(given.get("intake"), "收件資料夾")
    if "questions" in given:
        current["questions"] = _folder_setting(given.get("questions"), "題目資料夾")
    if "pulled" in given:
        current["pulled"] = [str(p) for p in given.get("pulled") or []]
    repo.local.mkdir(parents=True, exist_ok=True)
    (repo.local / SETTINGS).write_text(
        json.dumps(current, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    return current


# -- building the folder --------------------------------------------------------------


def _skill_bodies(folder: Path) -> dict[str, str]:
    return {
        path.parent.name: _text_sha(_plain(path).strip("\n"))
        for path in sorted((folder / "skills").glob("*/SKILL.md"))
    }


def _build(repo: Repository, key: str) -> None:
    folder = work_folder(repo)
    units = repo.working_units()
    stash = folder.parent / f".kept-{uuid.uuid4().hex[:8]}"
    if (folder / wiki.READ_ONLY_NOTE).is_file():
        for entry in list(folder.iterdir()):
            if entry.name in KEPT or entry.name.startswith("."):
                stash.mkdir(parents=True, exist_ok=True)
                entry.rename(stash / entry.name)
    try:
        wiki.materialize(units, folder, repo_folder=repo.folder, staged_files=repo.work / "files")
    finally:
        if stash.is_dir():
            for entry in list(stash.iterdir()):
                target = folder / entry.name
                if target.exists():
                    shutil.rmtree(target) if target.is_dir() else target.unlink()
                entry.rename(target)
            stash.rmdir()
    (folder / "drop").mkdir(exist_ok=True)
    base = folder.parent / BASE
    if base.exists():
        shutil.rmtree(base)
    for path, text in wiki.pages(units).items():
        out = base / path
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8", newline="\n")
    claude = folder / wiki.SCHEMA_FILE
    _write_state(
        repo,
        {
            "units": key,
            "raw": {
                k[len(wiki.RAW_PREFIX) :]: v.get("sha256")
                for k, v in units.items()
                if k.startswith(wiki.RAW_PREFIX) and isinstance(v, dict)
            },
            "skills": _skill_bodies(folder),
            "schema": _text_sha(_plain(claude)) if claude.is_file() else None,
        },
    )


def open_work(repo: Repository) -> Path:
    """The working folder, built from the working units when it is missing or
    was built from other units (what was edited in it is captured first)."""
    folder = work_folder(repo)
    with repo.lock:
        key = _units_key(repo)
        built = (folder / wiki.READ_ONLY_NOTE).is_file()
        if built and _read_state(repo).get("units") == key:
            return folder
        if built:
            capture(repo)
            key = _units_key(repo)
        _build(repo, key)
        return folder


def reset(repo: Repository) -> Path:
    """Rebuild the working folder from the working units, dropping what was
    edited in it and not captured (`drop/` and hidden files stay)."""
    with repo.lock:
        _build(repo, _units_key(repo))
        return work_folder(repo)


# -- capture ------------------------------------------------------------------------


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _visible(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    return sorted(
        p
        for p in root.rglob("*")
        if p.is_file() and not any(part.startswith(".") for part in p.relative_to(root).parts)
    )


def _original(rel: PurePosixPath, digest: str) -> str:
    folder = rel.parent.as_posix()
    return f"sources/{folder if folder != '.' else 'uncategorized'}/{digest[:8]}-{rel.name}"


def _next_schema(ref: str) -> str:
    stem, _, version = ref.partition("@")
    numbers = version.split(".")
    if len(numbers) == 3 and all(n.isdigit() for n in numbers):
        return f"{stem}@{numbers[0]}.{numbers[1]}.{int(numbers[2]) + 1}"
    return f"{stem}@{version}.1"


def _stored_schema(repo: Repository, ref: Any) -> str | None:
    """The text of schema version `ref` (staged first, then pushed)."""
    if not isinstance(ref, str):
        return None
    for root in (repo.work / "files", repo.folder):
        if (root / f"schemas/{ref}.md").is_file():
            return _plain(root / f"schemas/{ref}.md")
    return None


def _skills_by_folder(repo: Repository, units: Mapping[str, Any]) -> dict[str, skills.Skill]:
    found: dict[str, skills.Skill] = {}
    for item in skills.current_skills(repo, units):
        try:
            skill = skills.read_skill(repo, item["name"], units)
        except Exception:  # noqa: BLE001 - a missing file is shown by the skills list
            continue
        found[skill.extra.get("folder") or skill.name] = skill
    return found


def capture(repo: Repository) -> dict[str, Any]:
    """Stage what was changed in the working folder since it was built;
    returns what was staged and what was refused (`raw_changed`)."""
    folder = work_folder(repo)
    summary: dict[str, Any] = {
        "pages": [],
        "raw": [],
        "originals": [],
        "skills": [],
        "schema": None,
        "raw_changed": [],
    }
    if not (folder / wiki.READ_ONLY_NOTE).is_file():
        return summary
    with repo.lock:
        units = repo.working_units()
        state = _read_state(repo)
        current_folder = state.get("units") == _units_key(repo)
        base = folder.parent / BASE
        legacy = "raw" not in state  # a folder built before the base was kept
        # Pages: only the units that differ from the page as it was built.
        if legacy or not base.is_dir():
            built_pages = wiki.pages(units)
        else:
            built_pages = {p: _plain(base / p) for p in wiki.page_files(base)}
        on_disk = {p: _plain(folder / p) for p in wiki.page_files(folder)}
        for page in sorted(set(built_pages) | set(on_disk)):
            text, old = on_disk.get(page), built_pages.get(page)
            if text == old:
                continue
            mine = wiki.page_changes(wiki.page_units(page, old) if old else {}, page, text)
            now = repo.working_units()
            changes = {k: v for k, v in mine.items() if canonical(now.get(k)) != canonical(v)}
            if changes:
                repo.stage_many(changes)
                summary["pages"].append(page)
            out = base / page
            if text is None:
                out.unlink(missing_ok=True)
            else:
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text(text, encoding="utf-8", newline="\n")
        # Raw: new files only.
        known = {
            k[len(wiki.RAW_PREFIX) :]: v.get("sha256")
            for k, v in units.items()
            if k.startswith(wiki.RAW_PREFIX) and isinstance(v, dict)
        }
        built_raw: dict[str, Any] = dict(known if legacy else state.get("raw") or {})
        present = set()
        for path in _visible(folder / "raw"):
            rel = PurePosixPath(path.relative_to(folder / "raw").as_posix())
            name = rel.as_posix()
            present.add(name)
            digest = _sha(path)
            if name in built_raw or name in known:
                if built_raw.get(name, known.get(name)) != digest:
                    summary["raw_changed"].append(f"raw/{rel}")
                continue
            target = _original(rel, digest)
            repo.stage_file(target, path)
            repo.stage(f"{wiki.RAW_PREFIX}{rel}", {"file": target, "sha256": digest})
            built_raw[name] = digest
            summary["raw"].append(f"raw/{rel}")
        summary["raw_changed"] += [f"raw/{p}" for p in sorted(set(built_raw) - present)]
        # Originals dropped here.
        for path in _visible(folder / "drop"):
            rel = PurePosixPath(path.relative_to(folder / "drop").as_posix())
            target = _original(rel, _sha(path))
            if (repo.folder / target).is_file() or (repo.work / "files" / target).is_file():
                continue
            repo.stage_file(target, path)
            summary["originals"].append(target)
        # The schema (`CLAUDE.md`).
        schema = units.get(SCHEMA_UNIT)
        claude = folder / wiki.SCHEMA_FILE
        built_schema = state.get("schema")
        if legacy:
            stored = _stored_schema(repo, schema)
            built_schema = _text_sha(stored) if stored is not None else None
        if isinstance(schema, str) and claude.is_file():
            text = _plain(claude)
            if _text_sha(text) != built_schema:
                schema = _next_schema(schema)
                with tempfile.TemporaryDirectory() as scratch:
                    draft = Path(scratch) / "schema.md"
                    draft.write_text(text, encoding="utf-8", newline="\n")
                    repo.stage_file(f"schemas/{schema}.md", draft)
                repo.stage(SCHEMA_UNIT, schema)
                summary["schema"] = schema
                built_schema = _text_sha(text)
        # Skills (`skills/<folder>/SKILL.md`).
        by_folder = _skills_by_folder(repo, units)
        built_skills: dict[str, Any] = (
            {f: _text_sha(s.body) for f, s in by_folder.items()}
            if legacy
            else dict(state.get("skills") or {})
        )
        for path in sorted((folder / "skills").glob("*/SKILL.md")):
            name = path.parent.name
            text = _plain(path).strip("\n")
            if built_skills.get(name) == _text_sha(text):
                continue
            built_skills[name] = _text_sha(text)
            existing = by_folder.get(name)
            if existing is not None and existing.body == text:
                continue
            slug = name.lower()
            if not skills.NAME_RE.match(slug) or len(slug) > skills.MAX_NAME:
                continue
            skills.stage_skill(
                repo,
                skills.Skill(
                    name=existing.name if existing is not None else slug,
                    revision=1,
                    schema=str(schema),
                    role="ingest",
                    applies_to=existing.applies_to if existing is not None else (),
                    body=text,
                    extra={"folder": name} if slug != name else {},
                ),
            )
            summary["skills"].append(slug)
        if legacy:
            # Keep the pages as captured, so the next capture compares with them.
            for page, text in on_disk.items():
                out = base / page
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text(text, encoding="utf-8", newline="\n")
        _write_state(
            repo,
            {
                # The folder still shows the working units only when it did
                # before; otherwise the next `open_work` rebuilds it.
                "units": _units_key(repo) if current_folder else state.get("units"),
                "raw": built_raw,
                "skills": built_skills,
                "schema": built_schema,
            },
        )
    return summary
