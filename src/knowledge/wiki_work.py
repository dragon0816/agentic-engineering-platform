"""The working folder of a wiki repository (knowledge repositories R4a).

The ingest pipeline (convert, plan, apply, the rule editor) works on a wiki
folder. Instead of a sandbox copied from a live vault, each repository has a
working folder `<workspace>/knowledge-repos/<id>/work-view/vault`, built from
the working copy's units (`open_work`). After a step writes there, `capture`
stages what changed back into the working copy, to be committed with a
purpose and pushed like any change:

- a page (`index.md`, `log.md`, `decisions.md`, `wiki/**.md`) → its section
  and frontmatter units (`wiki.stage_page`); a deleted page → removed;
- a new file under `raw/` → an original under `sources/<folder>/` and its
  `raw:<path>` unit; Raw is immutable, so a changed or removed Raw file is
  reported, never staged;
- a new file under `drop/` → an original under `sources/<folder>/`;
- an edited `skills/<folder>/SKILL.md` → the next revision of that skill
  (role `ingest`, bound to the current schema);
- an edited `CLAUDE.md` → the next schema version (`wiki.schema@<x.y.z+1>`):
  skills written for the old version then show 「需要更新」 (decision 3).

Hidden files and folders (`.ingest-state.json`, `.plans/` …) stay local. The
folder is rebuilt whenever the working units differ from the ones it was
built from (after a sync, commit of someone else's work, discard or revert).
"""

from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any

from knowledge.repo import skills, wiki
from knowledge.repo.repository import SCHEMA_UNIT, Repository, canonical

WORK_VIEW = "work-view"
VIEW = "vault"
STATE = "state.json"


def _units_key(repo: Repository) -> str:
    return hashlib.sha256(canonical(repo.working_units()).encode("utf-8")).hexdigest()


def work_folder(repo: Repository) -> Path:
    return repo.local / WORK_VIEW / VIEW


def open_work(repo: Repository) -> Path:
    """The working folder, built from the working units when it is missing or
    was built from other units."""
    folder = work_folder(repo)
    state = folder.parent / STATE
    with repo.lock:
        key = _units_key(repo)
        try:
            built = json.loads(state.read_text(encoding="utf-8")).get("units")
        except (OSError, ValueError, AttributeError):
            built = None
        if built == key and (folder / wiki.READ_ONLY_NOTE).is_file():
            return folder
        wiki.materialize(
            repo.working_units(),
            folder,
            repo_folder=repo.folder,
            staged_files=repo.work / "files",
        )
        (folder / "drop").mkdir(exist_ok=True)
        state.write_text(json.dumps({"units": key}), encoding="utf-8")
        return folder


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


def capture(repo: Repository) -> dict[str, Any]:
    """Stage what changed in the working folder; returns what was staged and
    what was refused (`raw_changed`)."""
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
        current = wiki.pages(units)
        on_disk = {p: (folder / p).read_text(encoding="utf-8") for p in wiki.page_files(folder)}
        for page in sorted(set(current) | set(on_disk)):
            text = on_disk.get(page)
            if text is not None:
                text = text.replace("\r\n", "\n")
            if text != current.get(page):
                wiki.stage_page(repo, page, text)
                summary["pages"].append(page)
        known = {
            k[len(wiki.RAW_PREFIX) :]: v
            for k, v in units.items()
            if k.startswith(wiki.RAW_PREFIX) and isinstance(v, dict)
        }
        for path in _visible(folder / "raw"):
            rel = PurePosixPath(path.relative_to(folder / "raw").as_posix())
            digest = _sha(path)
            if rel.as_posix() in known:
                if known[rel.as_posix()].get("sha256") != digest:
                    summary["raw_changed"].append(f"raw/{rel}")
                continue
            target = _original(rel, digest)
            repo.stage_file(target, path)
            repo.stage(f"{wiki.RAW_PREFIX}{rel}", {"file": target, "sha256": digest})
            summary["raw"].append(f"raw/{rel}")
        present = {p.relative_to(folder / "raw").as_posix() for p in _visible(folder / "raw")}
        summary["raw_changed"] += [f"raw/{p}" for p in sorted(set(known) - present)]
        for path in _visible(folder / "drop"):
            rel = PurePosixPath(path.relative_to(folder / "drop").as_posix())
            target = _original(rel, _sha(path))
            if (repo.folder / target).is_file() or (repo.work / "files" / target).is_file():
                continue
            repo.stage_file(target, path)
            summary["originals"].append(target)
        schema = units.get(SCHEMA_UNIT)
        claude = folder / wiki.SCHEMA_FILE
        if isinstance(schema, str) and claude.is_file():
            text = claude.read_text(encoding="utf-8").replace("\r\n", "\n")
            stored = next(
                (
                    root / f"schemas/{schema}.md"
                    for root in (repo.work / "files", repo.folder)
                    if (root / f"schemas/{schema}.md").is_file()
                ),
                None,
            )
            old = stored.read_text(encoding="utf-8").replace("\r\n", "\n") if stored else None
            if text != old:
                schema = _next_schema(schema)
                with tempfile.TemporaryDirectory() as scratch:
                    draft = Path(scratch) / "schema.md"
                    draft.write_text(text, encoding="utf-8", newline="\n")
                    repo.stage_file(f"schemas/{schema}.md", draft)
                repo.stage(SCHEMA_UNIT, schema)
                summary["schema"] = schema
        by_folder: dict[str, skills.Skill] = {}
        for item in skills.current_skills(repo, units):
            try:
                skill = skills.read_skill(repo, item["name"], units)
            except Exception:  # noqa: BLE001 - a missing file is shown by the skills list
                continue
            by_folder[skill.extra.get("folder") or skill.name] = skill
        for path in sorted((folder / "skills").glob("*/SKILL.md")):
            name = path.parent.name
            text = path.read_text(encoding="utf-8").replace("\r\n", "\n").strip("\n")
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
        state = folder.parent / STATE
        state.write_text(json.dumps({"units": _units_key(repo)}), encoding="utf-8")
    return summary
