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
from collections.abc import Collection, Mapping
from dataclasses import replace
from typing import Any

from aep_bi.cards import homes, profile
from aep_bi.cards.schema import Registry
from aep_bi.cards.store import BiStoreError
from knowledge.repo import skills
from knowledge.repo.repository import SCHEMA_UNIT, RepoError, Repository

CLASSIFY = "classify"
SOURCES = homes.SOURCES
#: Where a vault before the homes (`homes`) kept its segments' sources.
OLD_APPLICATIONS = "sources/applications"
DOMAINS_UNIT = "meta:domains"  # the old domain configuration (retired, BI D4)
SEGMENTS_UNIT = "meta:vault_segments"
LIBRARY_UNIT = "meta:vault_library"
#: A home a person created: one unit each, so two people adding different homes never meet
#: and two adding the same one write the same key (`docs/phases/BI_PAGE_SIMPLE.md` §10).
HOME_PREFIX = "meta:home:"
MAX_HOME_LABEL = 40
MAX_HOME_ID = 40


def _schema_ref(units: Mapping[str, Any]) -> str:
    value = units.get(SCHEMA_UNIT)
    return str(value.get("ref") if isinstance(value, dict) else value or "")


def _segments(units: Mapping[str, Any]) -> list[dict[str, str]]:
    try:
        found = json.loads(str(units.get(SEGMENTS_UNIT) or "[]"))
    except ValueError:
        return []
    return [s for s in found if isinstance(s, dict) and s.get("folder")]


def _library(units: Mapping[str, Any]) -> list[str]:
    """The vault's library entries; a vault from before them has the defaults."""
    try:
        found = json.loads(str(units.get(LIBRARY_UNIT) or "null"))
    except ValueError:
        found = None
    return found if isinstance(found, list) else list(homes.LIBRARY_ENTRIES)


def created_homes(units: Mapping[str, Any]) -> list[dict[str, str]]:
    """The applications people created: `{"home", "label", "domain"}`, the domain empty when
    the schema already has the home's own (`mobile`)."""
    found = []
    for key, value in sorted(units.items()):
        if not key.startswith(HOME_PREFIX) or not isinstance(value, str):
            continue
        try:
            document = json.loads(value)
        except ValueError:
            continue
        home = key[len(HOME_PREFIX) :]
        if isinstance(document, dict) and homes.id_problem(home) is None:
            found.append(
                {
                    "home": home,
                    "label": str(document.get("label") or home),
                    "domain": str(document.get("domain") or ""),
                }
            )
    return found


def created_domains(units: Mapping[str, Any]) -> list[str]:
    return [item["domain"] for item in created_homes(units) if item["domain"]]


def home_list(units: Mapping[str, Any]) -> list[dict[str, str]]:
    """The vault's applications and library entries, by their short forms."""
    listed = [
        *({"home": s["folder"], "label": s.get("label") or s["folder"]} for s in _segments(units)),
        *({"home": item["home"], "label": item["label"]} for item in created_homes(units)),
        *({"home": f"{homes.LIBRARY}/{e}", "label": e} for e in _library(units)),
    ]
    return list({item["home"]: item for item in reversed(listed)}.values())[::-1]


def _same(text: Any) -> str:
    """What makes two names one: `AIDC`, `aidc` and `a-idc` are the same domain."""
    return re.sub(r"[\s_-]+", "", str(text)).casefold()


def new_home(
    given: Mapping[str, Any],
    units: Mapping[str, Any],
    reg: Registry | None,
    in_use: Collection[str] | None = None,
) -> dict[str, str]:
    """A new application's `{"home", "label", "domain"}`, or why not. A name, a case variant
    or an alias of what exists is that one, so a vault cannot hold it twice. An application of
    the vault's default list with nothing in it (`in_use` lacks it) is not listed, so naming it
    takes it up instead (acceptance F22)."""
    label = str(given.get("name") or "").strip()
    if not label:
        raise BiStoreError("home_name_missing", "請寫領域名稱")
    if len(label) > MAX_HOME_LABEL or any(ord(c) < 32 or c in "/\\" for c in label):
        raise BiStoreError("home_name_invalid", f"領域名稱最多 {MAX_HOME_LABEL} 字，不能有斜線")
    folder = str(given.get("folder") or "").strip().lower() or _slug(label)
    domains = reg.domains if reg is not None else ()
    aliases = reg.enum_aliases.get("domain", {}) if reg is not None else {}
    meant = {_same(d): d for d in domains} | {
        _same(alias): domain for alias, domain in aliases.items()
    }
    # The schema already knows this word, so it is that domain, whatever folder was typed.
    known = meant.get(_same(label)) or meant.get(_same(folder))
    if known:
        folder = _slug(known)
    if not folder:
        raise BiStoreError(
            "home_folder_needed", "中文名稱要另外寫資料夾名稱（小寫英數字與 -），例如 automotive"
        )
    if homes.id_problem(folder) or len(folder) > MAX_HOME_ID:
        raise BiStoreError(
            "home_folder_invalid", f"資料夾名稱只能用小寫英數字與 -，最多 {MAX_HOME_ID} 字"
        )
    if folder in homes.RESERVED_APPLICATIONS:
        raise BiStoreError("home_reserved", f"「{folder}」保留給系統，請換一個名稱")
    for item in home_list(units):
        if in_use is not None and item["home"] == folder and folder not in in_use:
            continue
        short = item["home"].rpartition("/")[2]
        if {_same(short), _same(item["label"])} & {_same(label), _same(folder)}:
            raise BiStoreError(
                "home_exists", f"已經有領域「{item['label']}」（{item['home']}）", home=item["home"]
            )
    return {"home": folder, "label": label, "domain": "" if known else folder}


def home_unit(item: Mapping[str, str]) -> tuple[str, str]:
    return f"{HOME_PREFIX}{item['home']}", json.dumps(
        {"label": item["label"], "domain": item["domain"]}, ensure_ascii=False, sort_keys=True
    )


def _card_type_lines(reg: Registry) -> list[str]:
    lines = [
        f"這個知識庫用 schema {reg.ref}。判讀來源時，先決定每段內容屬於哪一種卡片，",
        "只用下面的類型；看不出是哪一種的內容不要做成卡片。",
        "",
        "卡片類型：",
    ]
    for entity in reg.types.values():
        domain = f"（領域 {entity.domain}）" if entity.domain else ""
        lines.append(f"- {entity.name}：{entity.label}{domain}")
    return lines


def classify_body(reg: Registry, segments: list[dict[str, str]], library: list[str]) -> str:
    """The generated classify skill's text: which card types the schema has
    and which folder a source of each application goes in."""
    lines = _card_type_lines(reg)
    if segments:
        lines += ["", "應用（來源放在 applications/<資料夾>/sources）："]
        lines += [f"- {s['folder']}：{s.get('label') or s['folder']}" for s in segments]
    lines += [
        "",
        "產品、技術與競爭者的通用資料放在 library/<項目>/sources，不屬於任何一個應用。",
        f"項目：{'、'.join(library)}",
    ]
    return "\n".join(lines)


def _old_classify_body(reg: Registry, segments: list[dict[str, str]]) -> str:
    """The text generated before the homes, so a vault holding it still counts
    as nobody having edited it."""
    lines = _card_type_lines(reg)
    if segments:
        lines += ["", "市場區隔（來源放在 sources/applications/<資料夾>）："]
        lines += [f"- {s['folder']}：{s.get('label') or s['folder']}" for s in segments]
    lines += [
        "",
        "產品、競爭者與技術的通用資料放在 sources/library/，不屬於任何一個區隔。",
    ]
    return "\n".join(lines)


def classify_skill(
    reg: Registry, segments: list[dict[str, str]], library: list[str]
) -> skills.Skill:
    return skills.Skill(
        name=CLASSIFY,
        revision=1,
        schema=reg.ref,
        role="classify",
        applies_to=(),
        body=classify_body(reg, segments, library),
        extra={"generated": "true"},
    )


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-")


def _keeps_old_folders(units: Mapping[str, Any]) -> bool:
    """Whether a vault has sources in the folders from before the homes."""
    return any(
        key.startswith("source:")
        and isinstance(value, dict)
        and str(value.get("folder") or "").startswith(OLD_APPLICATIONS + "/")
        for key, value in units.items()
    )


def domain_folders(
    domain: Mapping[str, Any], segments: list[dict[str, str]], *, old_folders: bool = False
) -> list[str]:
    """The vault folders of a domain: the applications its segments name (by id
    or label), else an application of its own. `old_folders` adds the same
    application's folder from before the homes, whose sources stay there."""
    wanted = {_slug(s.get("id", "")) for s in domain.get("segments") or []}
    wanted |= {_slug(s.get("label", "")) for s in domain.get("segments") or []}
    wanted.discard("")
    found = [
        s["folder"]
        for s in segments
        if _slug(s["folder"]) in wanted or _slug(s.get("label", "")) in wanted
    ] or [_slug(domain["id"]) or "domain"]
    folders = [homes.sources_dir(folder) for folder in found]
    return (
        folders + [f"{OLD_APPLICATIONS}/{folder}" for folder in found] if old_folders else folders
    )


def notes_skill_name(domain_id: str) -> str:
    return f"{_slug(domain_id)[: skills.MAX_NAME - len('-extract')] or 'domain'}-extract"


def stage_classify(repo: Repository, reg: Registry) -> None:
    """Stage the generated classify skill when the vault has none."""
    units = repo.working_units()
    if skills.skill_unit(CLASSIFY) not in units:
        skills.stage_skill(repo, classify_skill(reg, _segments(units), _library(units)))


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
    segments, library = _segments(units), _library(units)
    unedited = (classify_body(old, segments, library), _old_classify_body(old, segments))
    if current.schema == new.ref or current.body not in unedited:
        return
    skills.stage_skill(repo, classify_skill(new, segments, library))


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
    old_folders = _keeps_old_folders(units)
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
                    else tuple(domain_folders(domain, segments, old_folders=old_folders))
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
    """A source folder in a vault: a home's `sources` or a folder under it; or,
    for what a vault kept before the homes, `sources` or a folder under that."""
    folder = str(value or SOURCES).strip().strip("/")
    problem = homes.LAYOUT.source_folder_problem(folder)
    if problem:
        raise BiStoreError("folder_invalid", f"folder {problem}")
    return folder


def _runnable(repo: Repository, name: str, units: Mapping[str, Any]) -> skills.Skill:
    try:
        return skills.runnable(repo, name, units)
    except RepoError as failure:
        raise BiStoreError(failure.code, failure.message, **failure.detail) from None


def _still_generated(skill: skills.Skill, current: str) -> bool:
    """Whether a classify skill holds only what generating it says, the schema's name
    aside: additions add lines, and a line of a person's own means it was edited."""
    if skill.role != "classify" or skill.extra.get("generated") != "true":
        return False
    known = set(current.splitlines())
    return all(line in known for line in skill.body.splitlines()[1:])


def run_rules(
    repo: Repository,
    folder: str,
    draft: skills.Skill | None = None,
    reg: Registry | None = None,
) -> dict[str, Any]:
    """The skills an AI run of a source in `folder` uses: their text for the
    prompt, which revisions they are, and the extract skill's card types.
    `draft` (the skill AI trying a rule, BI T2) stands in for the skill of its
    name, or is the extract skill of a folder it applies to; nothing is staged.
    Under a profile the model sees only the profile's types, so the generated classify
    skill, which lists them all, stays out (`reg` tells it from one a person edited)."""
    units = repo.working_units()
    used: list[skills.Skill] = []
    if skills.skill_unit(CLASSIFY) in units:
        used.append(_runnable(repo, CLASSIFY, units))
    found = skills.skill_for(repo, folder, "extract", units)
    if found is not None:
        used.append(_runnable(repo, str(found["name"]), units))
    if draft is not None:
        named = [s for s in used if s.unit_name == draft.unit_name]
        applies = draft.role == "extract" and any(
            folder == a or folder.startswith(a + "/") for a in draft.applies_to
        )
        if named:
            used = [draft if s.unit_name == draft.unit_name else s for s in used]
        elif applies:
            used = [s for s in used if s.role != "extract"] + [draft]
    from_profile = profile.rules_part(repo, folder, units)
    if from_profile.get("profile") and reg is not None:
        generated = classify_body(reg, _segments(units), _library(units)).strip()
        used = [s for s in used if s.role != "classify" or s.body.strip() != generated]
    if reg is not None:
        # Two PCs' merged additions never write this file, so nobody edited it means now.
        current = classify_body(reg, _segments(units), _library(units))
        used = [replace(s, body=current) if _still_generated(s, current) else s for s in used]
    parts = [
        f"{'Classification' if s.role == 'classify' else 'Extraction'} "
        f"(skill {s.unit_name}, revision {s.revision}):\n{s.body.strip()}"
        for s in used
    ]
    card_types = next((list(s.card_types) for s in used if s.role == "extract"), [])
    return {
        "folder": folder,
        "text": "\n\n".join(parts),
        "skills": [
            {"name": s.unit_name, "revision": s.revision, "role": s.role}
            | ({"draft": True} if s is draft else {})
            for s in used
        ],
        "card_types": card_types,
        "schema": _schema_ref(units),
        **from_profile,
    }
