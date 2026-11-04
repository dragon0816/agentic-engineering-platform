"""A home's profile (`docs/phases/BI_CARD_MODEL.md` §4.2): what one expert uses.

    <home>/profile/rev-<n>-<author>.json     written once
    profile:<home>                           {"revision", "author", "path", "sha256", "schema"}

A profile lists which types and fields a home uses, with the expert's notes. A
type or field not listed is not asked for there, and reads as unknown; only what a
type lists under `not_applicable` is 不適用. It never defines anything: a new
field goes in `proposals` until it is merged into the schema (§4.3). So
validation stays against the merged schema, and a value outside the profile is a
candidate marked `outside_profile`, not dropped.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from capabilities.bi_cards import card_model, homes
from capabilities.bi_cards.schema import Registry
from capabilities.bi_cards.store import BiStoreError

FORMAT = "aep.bi.profile/v1"
USES = ("required", "optional")
PROPOSED = "proposed"
MERGED = "merged"
REJECTED = "rejected"
PROPOSAL_STATUSES = (PROPOSED, MERGED, REJECTED)
#: Every card may have these, whatever a home uses: a card's other names, and what
#: §3.6 gives every card, a missing summary being a warning at publish. So the model
#: is always asked and a profile cannot call them 不適用.
ALWAYS_FIELDS = ("aliases", "summary", "usage", "scope")
_TOP_KEYS = {"format", "application", "revision", "schema", "types", "proposals"}
_TYPE_KEYS = {"category", "fields", "not_applicable"}
_FIELD_KEYS = {"use", "note"}
_PROPOSAL_KEYS = {"type", "field", "definition", "reason", "status"}


def unit_key(home: str) -> str:
    return card_model.PROFILE_PREFIX + home


def _invalid(message: str) -> BiStoreError:
    return BiStoreError("profile_invalid", message)


def _checked_field(type_name: str, name: str, entry: Any) -> dict[str, Any]:
    if not isinstance(entry, dict):
        raise _invalid(f"{type_name}.{name} 必須是物件")
    extra = sorted(set(entry) - _FIELD_KEYS)
    if extra:
        # A definition (kind, enum) belongs in a proposal, reviewed into the schema.
        raise _invalid(f"{type_name}.{name} 不能寫 {'、'.join(extra)}；新欄位請放在 proposals")
    if entry.get("use") not in USES:
        raise _invalid(f"{type_name}.{name} 的 use 必須是 {'、'.join(USES)} 之一")
    note = entry.get("note")
    if note is not None and not isinstance(note, str):
        raise _invalid(f"{type_name}.{name} 的 note 必須是文字")
    return {"use": entry["use"], **({"note": note} if note else {})}


def _checked_not_applicable(entity: Any, raw: Any, used: Mapping[str, Any]) -> list[dict[str, str]]:
    """`not_applicable: [field]`, an item being a name or `{"field", "reason"}`."""
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise _invalid(f"{entity.name} 的 not_applicable 必須是清單")
    found: list[dict[str, str]] = []
    for entry in raw:
        given = {"field": entry} if isinstance(entry, str) else entry
        if not isinstance(given, dict) or set(given) - {"field", "reason"}:
            raise _invalid(f"{entity.name} 的 not_applicable 每項是欄位名或 field 和 reason")
        name, reason = given.get("field"), given.get("reason")
        item = entity.get(name) if isinstance(name, str) else None
        if item is None:
            raise _invalid(f"schema 的 {entity.name} 沒有欄位 {name}")
        if reason is not None and not isinstance(reason, str):
            raise _invalid(f"{entity.name}.{name} 的 reason 必須是文字")
        never = item.klass == "derived" or item.required or name in entity.naming
        if never or name in ALWAYS_FIELDS:
            raise _invalid(f"{entity.name}.{name} 不能標成不適用")
        if name in used:
            raise _invalid(f"{entity.name}.{name} 已列為使用，不能同時標成不適用")
        found.append({"field": str(name), **({"reason": reason} if reason else {})})
    return found


def _checked_types(reg: Registry, raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise _invalid("types 必須是物件")
    found: dict[str, Any] = {}
    for type_name, entry in raw.items():
        entity = reg.types.get(type_name)
        if entity is None:
            raise _invalid(f"schema 沒有類型 {type_name}")
        if not isinstance(entry, dict) or set(entry) - _TYPE_KEYS:
            raise _invalid(f"{type_name} 只能有 category、fields 和 not_applicable")
        category = entry.get("category")
        if category is not None and not isinstance(category, str):
            raise _invalid(f"{type_name} 的 category 必須是文字")
        fields = entry.get("fields")
        if not isinstance(fields, dict):
            raise _invalid(f"{type_name} 的 fields 必須是物件")
        checked = {}
        for name, value in fields.items():
            if entity.get(name) is None:
                raise _invalid(f"schema 的 {type_name} 沒有欄位 {name}；新欄位請放在 proposals")
            checked[name] = _checked_field(type_name, name, value)
        stated = _checked_not_applicable(entity, entry.get("not_applicable"), checked)
        found[type_name] = {
            **({"category": category} if category else {}),
            "fields": checked,
            **({"not_applicable": stated} if stated else {}),
        }
    return found


def _checked_proposals(reg: Registry, raw: Any) -> list[dict[str, Any]]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise _invalid("proposals 必須是清單")
    found = []
    for entry in raw:
        if not isinstance(entry, dict) or set(entry) - _PROPOSAL_KEYS:
            raise _invalid("proposal 只能有 type、field、definition、reason、status")
        if entry.get("type") not in reg.types:
            raise _invalid(f"schema 沒有類型 {entry.get('type')}")
        if not isinstance(entry.get("field"), str) or not entry["field"]:
            raise _invalid("proposal 要有 field")
        if not isinstance(entry.get("definition"), dict):
            raise _invalid(f"proposal {entry['field']} 的 definition 必須是物件")
        status = entry.get("status", PROPOSED)
        if status not in PROPOSAL_STATUSES:
            raise _invalid(f"proposal {entry['field']} 的 status 無效")
        found.append(
            {
                "type": entry["type"],
                "field": entry["field"],
                "definition": entry["definition"],
                "reason": str(entry.get("reason") or ""),
                "status": status,
            }
        )
    return found


def checked(document: Any, home: str, reg: Registry) -> dict[str, Any]:
    """A profile `document` for `home` on schema `reg`, reduced to what it may say."""
    problem = homes.home_problem(home)
    if problem:
        raise _invalid(f"home「{home}」{problem}")
    if not isinstance(document, dict) or set(document) - _TOP_KEYS:
        raise _invalid(f"profile 只能有 {'、'.join(sorted(_TOP_KEYS))}")
    if document.get("format", FORMAT) != FORMAT:
        raise _invalid(f"format 必須是 {FORMAT}")
    if document.get("application", home) != home:
        raise _invalid(f"application 必須是 {home}")
    return {
        "format": FORMAT,
        "application": home,
        "schema": reg.ref,
        "types": _checked_types(reg, document.get("types")),
        "proposals": _checked_proposals(reg, document.get("proposals")),
    }


def stage(repo: Any, home: str, document: Any, reg: Registry) -> dict[str, Any]:
    """Stage the next revision of `home`'s profile and make it current."""
    good = checked(document, home, reg)
    key = unit_key(home)
    current = repo.working_units().get(key)
    revision = int(current["revision"]) + 1 if isinstance(current, dict) else 1
    good["revision"] = revision
    data = (json.dumps(good, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()
    draft = repo.local / "drafts" / f"{uuid.uuid4().hex[:8]}.json"
    draft.parent.mkdir(parents=True, exist_ok=True)
    draft.write_bytes(data)
    path = homes.profile_path(home, revision, repo.author)
    try:
        repo.stage_file(path, draft)
    finally:
        draft.unlink(missing_ok=True)
    value = {
        "revision": revision,
        "author": repo.author,
        "path": path,
        "sha256": hashlib.sha256(data).hexdigest(),
        "schema": reg.ref,
    }
    repo.stage(key, value)
    return value


def read(repo: Any, home: str, units: Mapping[str, Any]) -> dict[str, Any] | None:
    """`home`'s current profile; None when it has none. A profile that cannot be
    read now (OneDrive still syncing) is `profile_missing`, not the whole schema."""
    value = units.get(unit_key(home))
    if not isinstance(value, dict):
        return None
    for root in (Path(repo.folder), Path(repo.work) / "files"):
        candidate = root / str(value["path"])
        if candidate.is_file():
            data = candidate.read_bytes()
            if hashlib.sha256(data).hexdigest() == value["sha256"]:
                document = json.loads(data)
                return document if isinstance(document, dict) else None
    raise BiStoreError("profile_missing", f"讀不到 {value['path']}（OneDrive 是否還在同步？）")


def load_all(repo: Any, units: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    """Every home's profile that can be read now. One that cannot counts as none,
    so a rebuild reads `unknown` until it arrives, and never fails for it."""
    found: dict[str, dict[str, Any]] = {}
    for key in units:
        if key.startswith(card_model.PROFILE_PREFIX):
            home = key.removeprefix(card_model.PROFILE_PREFIX)
            try:
                document = read(repo, home, units)
            except (BiStoreError, OSError, ValueError):
                continue
            if document is not None:
                found[home] = document
    return found


def listed(repo: Any, units: Mapping[str, Any]) -> list[dict[str, Any]]:
    """The current profiles, as the page and the API show them."""
    return [{"home": home, **document} for home, document in sorted(load_all(repo, units).items())]


def rules_part(repo: Any, folder: str, units: Mapping[str, Any]) -> dict[str, Any]:
    """What an AI run of a source in `folder` keeps of its home's profile, so a
    retry reads the same: `profile` (None for no profile), and `home`."""
    home = homes.home_of(folder)
    document = read(repo, home, units) if home else None
    if document is None:
        return {"home": home, "profile": None}
    return {
        "home": home,
        "profile": {
            "revision": document.get("revision"),
            "types": document.get("types") or {},
        },
    }


def used_fields(entity: Any, profile: Mapping[str, Any]) -> set[str] | None:
    """The fields of `entity` the profile uses, with those no card goes without (its
    name, what the schema requires, `ALWAYS_FIELDS`); None when the profile does not
    use the type at all."""
    view = (profile.get("types") or {}).get(entity.name)
    if view is None:
        return None
    required = {item.name for item in entity.fields if item.required}
    return {*view.get("fields", {}), *entity.naming, *required, *ALWAYS_FIELDS}


def mark_candidate(reg: Registry, candidate: dict[str, Any], profile: Mapping[str, Any]) -> None:
    """Mark what lies outside the profile, and warn of what it requires and the
    candidate lacks. Both only inform the review: only the schema's `required` refuses."""
    entity = reg.types.get(str(candidate.get("entity_type")))
    if entity is None:
        return
    used = used_fields(entity, profile)
    outside = []
    for entry in candidate.get("fields") or []:
        if used is None or entry.get("field") not in used:
            entry["outside_profile"] = True
            outside.append(str(entry.get("field")))
        else:
            entry.pop("outside_profile", None)
    candidate["outside_profile"] = sorted(outside)
    candidate["outside_profile_type"] = used is None
    present = {str(entry.get("field")) for entry in candidate.get("fields") or []}
    view = (profile.get("types") or {}).get(entity.name) or {}
    warnings = [
        w for w in candidate.get("warnings") or [] if w.get("code") != "profile_required_missing"
    ]
    for name, field in sorted((view.get("fields") or {}).items()):
        if field.get("use") == "required" and name not in present:
            warnings.append(
                {
                    "code": "profile_required_missing",
                    "message": f"這個應用的 profile 要求 {name}，這張卡沒有（不會擋下）",
                }
            )
    candidate["warnings"] = warnings


def missing_required(db: Any, profiles: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Per home, type and field: how many of its cards lack what its profile requires.
    A warning at publish, never a block."""
    found = []
    for home, document in sorted(profiles.items()):
        for type_name, view in sorted((document.get("types") or {}).items()):
            for name, field in sorted((view.get("fields") or {}).items()):
                if field.get("use") != "required":
                    continue
                count = db.execute(
                    "SELECT COUNT(*) FROM card_app_folders a JOIN cards c ON c.id = a.card_id "
                    "WHERE a.application = ? AND c.entity_type = ? AND NOT EXISTS ("
                    "SELECT 1 FROM fields f WHERE f.card_id = c.id AND f.field = ?)",
                    (home, type_name, name),
                ).fetchone()[0]
                if count:
                    found.append(
                        {"home": home, "type": type_name, "field": name, "cards": int(count)}
                    )
    return found
