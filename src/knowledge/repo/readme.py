"""`REPO.md`: what a maintainer reads first (knowledge repositories, design §9).

Generated from the pushed commits, the tags and the publish records, and
rewritten by the PC that pushes or publishes. It is derived: the same records
give the same text (no clock time in it), so a lost copy or an OneDrive
conflict copy is harmless and is rewritten at the next push. It is the only
file in a repository folder that is ever rewritten, and never the source of
truth.
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import Any

from knowledge.repo.repository import (
    README_FILE,
    SCHEMA_UNIT,
    Repository,
    _write_atomic,
    layout_of,
)
from knowledge.repo.skills import current_skills

#: The newest commits listed under "Versions".
RECENT = 5


def _schema_ref(value: Any) -> str | None:
    if isinstance(value, dict):
        ref = value.get("ref")
        return str(ref) if ref else None
    return str(value) if value else None


def _schema_files(repo: Repository, value: Any, ref: str) -> tuple[str | None, str | None]:
    """The schema file and its readable `.md` in `schemas/`, when present."""
    schema_id, _, version = ref.rpartition("@")
    stem = f"{schema_id.replace('/', '__')}@{version}"
    named = value.get("file") if isinstance(value, dict) else None
    candidates = [str(named)] if named else []
    candidates += [f"schemas/{stem}.json", f"schemas/{stem}.md"]
    main = next((c for c in candidates if (repo.folder / c).is_file()), None)
    readable = None
    if main is not None and not main.endswith(".md"):
        doc = str(PurePosixPath(main).with_suffix(".md"))
        readable = doc if (repo.folder / doc).is_file() else None
    return main, readable


def _all_commits(repo: Repository) -> list[dict[str, Any]]:
    """Every applied commit, newest first."""
    return repo.history(limit=1_000_000)


def readme_text(repo: Repository) -> str:
    """The text of `REPO.md` for the repository's head as of the last sync."""
    document = repo.document
    units = repo.units()
    commits = _all_commits(repo)
    lines = [f"# {document['title']}", ""]
    if document.get("purpose"):
        lines += [str(document["purpose"]), ""]
    lines += [
        f"- Type: `{document['type']}`",
        f"- Repository id: `{document['id']}`",
        "",
        "This folder is maintained through AEP. Nobody edits or deletes a file here; every file "
        "is added once by its author. This page is generated: do not edit it.",
        "",
        "## Schema in use",
        "",
    ]
    schema = units.get(SCHEMA_UNIT)
    ref = _schema_ref(schema)
    if ref is None:
        lines += ["No schema has been committed yet.", ""]
    else:
        main, readable = _schema_files(repo, schema, ref)
        lines.append(f"- Version: `{ref}`")
        if main:
            lines.append(f"- File: `{main}`")
        if readable:
            lines.append(f"- Readable description: `{readable}`")
        if isinstance(schema, dict) and schema.get("from"):
            lines.append(f"- Upgraded from: `{schema['from']}`")
        lines.append("")

    lines += ["## Skills in use", ""]
    skills = current_skills(repo, units)
    if not skills:
        lines += ["No skill has been committed yet.", ""]
    else:
        lines += [
            "| Skill | Revision | Role | Applies to | Schema | State |",
            "|---|---|---|---|---|---|",
        ]
        for item in skills:
            scope = ", ".join(f"`{p}/`" for p in item["applies_to"]) or "every source"
            state = "needs update" if item["needs_update"] else "ok"
            lines.append(
                f"| `{item['name']}` | {item['revision']} | {item['role']} | {scope} | "
                f"`{item['schema']}` | {state} |"
            )
        lines.append("")
        stale = [s["name"] for s in skills if s["needs_update"]]
        if stale:
            lines += [
                f"Skills marked *needs update* were written for another schema version than "
                f"`{ref}` and are not run until they are updated: {', '.join(stale)}.",
                "",
            ]

    lines += ["## Versions", ""]
    published = repo.published()
    if published is None:
        lines.append("- Published: nothing yet; the Agent reads the maintenance head.")
    else:
        ids = [c["id"] for c in commits]
        ahead = ids.index(published["commit"]) if published["commit"] in ids else None
        lines.append(f"- Published: tag `{published['tag']}` (by {published['author']})")
        if ahead is not None:
            lines.append(f"- The maintenance head is {ahead} commit(s) ahead of it.")
    tags = sorted(repo.tags(), key=lambda t: t["name"])
    if tags:
        names = ", ".join("`" + str(t["name"]) + "`" for t in tags)
        lines.append(f"- Tags: {names}")
    lines.append("")
    if commits:
        lines += ["| Date | Author | Purpose |", "|---|---|---|"]
        for commit in commits[:RECENT]:
            purpose = str(commit["purpose"]).replace("|", "\\|").replace("\n", " ")
            lines.append(f"| {str(commit['created'])[:10]} | {commit['author']} | {purpose} |")
        lines.append("")
    else:
        lines += ["No commit has been pushed yet.", ""]

    lines += ["## How to maintain", ""]
    layout = layout_of(repo.kind)
    folders = sorted(
        {
            str(PurePosixPath(path).parent)
            for commit in commits
            for path in commit["files"]
            if layout.is_source_path(path)
        }
    )
    readers = [s for s in skills if s["role"] in ("extract", "ingest")]
    if readers:
        lines.append("- **New sources.** Put a file in the folder of its skill:")
        for item in readers:
            for prefix in item["applies_to"] or ["sources"]:
                lines.append(f"  - `{prefix}/` → read by `{item['name']}`")
    else:
        lines.append(f"- **New sources.** Add them under `{layout.source_hint}` through AEP.")
    if folders:
        lines.append(f"- Source folders in use: {', '.join(f'`{f}/`' for f in folders)}")
    lines += [
        "- **Add a field or a type.** Upgrade the schema with Session A (a new version), then "
        "update every skill listed as needing an update.",
        "- **Change a rule.** Edit the skill in AEP; it is saved as a new revision and committed.",
        "- **Share your work.** Commit with its purpose, then push.",
        "- **Release.** Tag the version and publish it (one person confirms); the Agent reads "
        "the published version.",
        "- **Undo.** Revert to an earlier tag or commit; history is kept.",
    ]
    return "\n".join(lines).rstrip("\n") + "\n"


def write_readme(repo: Repository) -> Path:
    """Rewrite `REPO.md` from the records (the only file ever rewritten)."""
    path = repo.folder / README_FILE
    _write_atomic(path, readme_text(repo).encode("utf-8"))
    return path
