"""Skills of a BI vault (knowledge repositories R3, the BI part).

Design: `docs/phases/KNOWLEDGE_REPO.md` §8. The skill format, schema binding
and 「需要更新」 are the shared `knowledge.repo.skills`; this module is what
only BI needs:

- the **classify** skill, generated from the schema (card types) and the
  vault's source folders, staged when a vault is created or converted, and
  generated again on a schema change while nobody has edited it;
- a domain's `notes` (BI vault V11) **move into an extract skill** (owner
  decision 2): a vault's domain configuration keeps segments, chains, node
  patterns and aliases, and a domain's notes become the skill
  `<domain>-extract` for that domain's folders;
- the **rules an AI run uses**: the classify skill and the extract skill whose
  `applies_to` matches the source's folder, as text for the prompt after the
  fixed evidence rules (which stay in code, `extract.EVIDENCE_RULES`). A skill
  written for another schema version is refused (`skill_needs_update`).
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from pathlib import PurePosixPath
from typing import Any

from capabilities.bi_cards.schema import Registry
from capabilities.bi_cards.store import BiStoreError
from knowledge.repo import skills
from knowledge.repo.repository import SCHEMA_UNIT, RepoError, Repository, path_problem

CLASSIFY = "classify"
SOURCES = "sources"
APPLICATIONS = "sources/applications"
LIBRARY = "sources/library"
DOMAINS_UNIT = "meta:domains"  # the old domain configuration (retired, BI D4)
SEGMENTS_UNIT = "meta:vault_segments"


def _schema_ref(units: Mapping[str, Any]) -> str:
    value = units.get(SCHEMA_UNIT)
    return str(value.get("ref") if isinstance(value, dict) else value or "")


def _segments(units: Mapping[str, Any]) -> list[dict[str, str]]:
    try:
        found = json.loads(str(units.get(SEGMENTS_UNIT) or "[]"))
    except ValueError:
        return []
    return [s for s in found if isinstance(s, dict) and s.get("folder")]


def classify_body(reg: Registry, segments: list[dict[str, str]]) -> str:
    """The generated classify skill's text: which card types the schema has
    and which folder a source of each segment goes in."""
    lines = [
        f"這個知識庫用 schema {reg.ref}。判讀來源時，先決定每段內容屬於哪一種卡片，",
        "只用下面的類型；看不出是哪一種的內容不要做成卡片。",
        "",
        "卡片類型：",
    ]
    for entity in reg.types.values():
        domain = f"（領域 {entity.domain}）" if entity.domain else ""
        lines.append(f"- {entity.name}：{entity.label}{domain}")
    if segments:
        lines += ["", "市場區隔（來源放在 sources/applications/<資料夾>）："]
        lines += [f"- {s['folder']}：{s.get('label') or s['folder']}" for s in segments]
    lines += [
        "",
        "產品、競爭者與技術的通用資料放在 sources/library/，不屬於任何一個區隔。",
    ]
    return "\n".join(lines)


def classify_skill(reg: Registry, segments: list[dict[str, str]]) -> skills.Skill:
    return skills.Skill(
        name=CLASSIFY,
        revision=1,
        schema=reg.ref,
        role="classify",
        applies_to=(),
        body=classify_body(reg, segments),
        extra={"generated": "true"},
    )


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-")


def domain_folders(domain: Mapping[str, Any], segments: list[dict[str, str]]) -> list[str]:
    """The vault folders of a domain: the segment folders its segments name
    (by id or label), else a folder of its own under `sources/applications`."""
    wanted = {_slug(s.get("id", "")) for s in domain.get("segments") or []}
    wanted |= {_slug(s.get("label", "")) for s in domain.get("segments") or []}
    wanted.discard("")
    found = [
        f"{APPLICATIONS}/{s['folder']}"
        for s in segments
        if _slug(s["folder"]) in wanted or _slug(s.get("label", "")) in wanted
    ]
    return found or [f"{APPLICATIONS}/{_slug(domain['id']) or 'domain'}"]


def notes_skill_name(domain_id: str) -> str:
    return f"{_slug(domain_id)[: skills.MAX_NAME - len('-extract')] or 'domain'}-extract"


def stage_classify(repo: Repository, reg: Registry) -> None:
    """Stage the generated classify skill when the vault has none."""
    units = repo.working_units()
    if skills.skill_unit(CLASSIFY) not in units:
        skills.stage_skill(repo, classify_skill(reg, _segments(units)))


def regenerate_classify(repo: Repository, old: Registry, new: Registry) -> None:
    """After a schema change: a classify skill nobody edited (its text is still
    the one generated for the old schema) is generated again for the new one;
    an edited one stays as it is and shows 「需要更新」."""
    units = repo.working_units()
    if skills.skill_unit(CLASSIFY) not in units:
        return
    try:
        current = skills.read_skill(repo, CLASSIFY, units)
    except RepoError:
        return
    if current.schema == new.ref or current.body != classify_body(old, _segments(units)):
        return
    skills.stage_skill(repo, classify_skill(new, _segments(units)))


def move_notes(repo: Repository, reg: Registry) -> list[str]:
    """Move every domain's `notes` in the working domain configuration into
    its extract skill (a new revision when the text differs) and stage the
    configuration without them. Returns the skills written."""
    units = repo.working_units()
    text = units.get(DOMAINS_UNIT)
    if not isinstance(text, str) or not text:
        return []
    try:
        document = json.loads(text)
    except ValueError:
        return []
    entries = document.get("domains") if isinstance(document, dict) else None
    if not isinstance(entries, list) or not any(
        isinstance(d, dict) and d.get("notes") for d in entries
    ):
        return []
    segments = _segments(units)
    written = []
    for domain in entries:
        notes = str(domain.get("notes") or "").strip() if isinstance(domain, dict) else ""
        if not notes:
            continue
        name = notes_skill_name(str(domain["id"]))
        existing: skills.Skill | None = None
        if skills.skill_unit(name) in units:
            try:
                existing = skills.read_skill(repo, name, units)
            except RepoError:
                existing = None
        if existing is not None and existing.body == notes and existing.schema == reg.ref:
            domain["notes"] = ""
            continue
        skills.stage_skill(
            repo,
            skills.Skill(
                name=name,
                revision=1,
                schema=reg.ref,
                role="extract",
                applies_to=(
                    existing.applies_to
                    if existing is not None
                    else tuple(domain_folders(domain, segments))
                ),
                body=notes,
                card_types=existing.card_types if existing is not None else (),
                extra={"domain": str(domain["id"])},
            ),
        )
        domain["notes"] = ""
        written.append(name)
    for domain in entries:
        if isinstance(domain, dict) and "notes" in domain:
            domain["notes"] = ""
    repo.stage(DOMAINS_UNIT, json.dumps(document, ensure_ascii=False, sort_keys=True))
    return written


# -- what an AI run reads ------------------------------------------------------


def checked_folder(value: Any) -> str:
    """A source folder in a vault (`sources` or a folder under it)."""
    folder = str(value or SOURCES).strip().strip("/")
    parts = PurePosixPath(folder).parts
    if not parts or parts[0] != SOURCES or (folder != SOURCES and path_problem(folder)):
        raise BiStoreError("folder_invalid", "folder 必須是 sources/ 底下的資料夾")
    return folder


def _runnable(repo: Repository, name: str, units: Mapping[str, Any]) -> skills.Skill:
    try:
        return skills.runnable(repo, name, units)
    except RepoError as failure:
        raise BiStoreError(failure.code, failure.message, **failure.detail) from None


def run_rules(repo: Repository, folder: str, draft: skills.Skill | None = None) -> dict[str, Any]:
    """The skills an AI run of a source in `folder` uses: their text for the
    prompt, which revisions they are, and the extract skill's card types.
    `draft` (the skill AI trying a rule, BI T2) stands in for the skill of its
    name, or is the extract skill of a folder it applies to; nothing is staged."""
    units = repo.working_units()
    used: list[skills.Skill] = []
    if skills.skill_unit(CLASSIFY) in units:
        used.append(_runnable(repo, CLASSIFY, units))
    found = skills.skill_for(repo, folder, "extract", units)
    if found is not None:
        used.append(_runnable(repo, str(found["name"]), units))
    if draft is not None:
        named = [s for s in used if s.name == draft.name]
        applies = draft.role == "extract" and any(
            folder == a or folder.startswith(a + "/") for a in draft.applies_to
        )
        if named:
            used = [draft if s.name == draft.name else s for s in used]
        elif applies:
            used = [s for s in used if s.role != "extract"] + [draft]
    parts = [
        f"{'Classification' if s.role == 'classify' else 'Extraction'} "
        f"(skill {s.name}, revision {s.revision}):\n{s.body.strip()}"
        for s in used
    ]
    card_types = next((list(s.card_types) for s in used if s.role == "extract"), [])
    return {
        "folder": folder,
        "text": "\n\n".join(parts),
        "skills": [
            {"name": s.name, "revision": s.revision, "role": s.role}
            | ({"draft": True} if s is draft else {})
            for s in used
        ],
        "card_types": card_types,
        "schema": _schema_ref(units),
    }
