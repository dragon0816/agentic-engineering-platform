"""Schema changes that merge when they do not overlap (`docs/phases/BI_CARD_MODEL.md` §4.3).

The `schema` unit still names one immutable version, the base. A compatible change on top
of it is not a new version: it is a unit of its own, so two PCs' changes are two units and
the engine has nothing to conflict on, and the same key with another value conflicts as any
unit does. `overlay` applies the units in an order that depends only on their keys, so
every PC gets byte-identical schema whichever order commits arrive in, and the version it
reads is the base's plus a digest of the units: `5.0.0+a1b2c3d4e5f6`. No number is taken.

A change that is not an addition is still a new version, for a person (`changes_between`
answers None). What units cannot see, a unit against a version that no longer fits it, is
a clash: `overlay` leaves that unit out, the same on every PC, and says so.

This module also says which skills a change touches (`skill_verdict`).
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from capabilities.bi_cards import catalog
from capabilities.bi_cards.store import BiStoreError
from knowledge.repo.repository import SCHEMA_UNIT, canonical

PREFIX = "schema_change:"
#: In the order they apply: what a later kind refers to already exists.
KINDS = ("domain", "type", "field", "enum", "label", "used_by")
#: What two definitions of one field may differ in and still be the same field.
_WORDING = {"name", "label", "used_by"}
_MEMO: dict[tuple[str, str], tuple[dict[str, Any], list[dict[str, str]]]] = {}
_MEMO_LIMIT = 32


def domain_key(name: str) -> str:
    return f"{PREFIX}domain:{name}"


def type_key(name: str) -> str:
    return f"{PREFIX}type:{name}"


def field_key(type_name: str, field: str) -> str:
    return f"{PREFIX}field:{type_name}.{field}"


def enum_key(type_name: str, field: str, value: str) -> str:
    return f"{PREFIX}enum:{type_name}.{field}:{value}"


def label_key(type_name: str, field: str | None = None) -> str:
    return f"{PREFIX}label:{type_name}.{field}" if field else f"{PREFIX}label:{type_name}"


def used_by_key(type_name: str, field: str, home: str) -> str:
    return f"{PREFIX}used_by:{type_name}.{field}:{home}"


def unit_problem(key: str, value: Any) -> str | None:
    kind = key[len(PREFIX) :].partition(":")[0]
    if kind not in KINDS:
        return "not a schema change"
    if value is not None and not isinstance(value, dict):
        return "a schema change must be an object"
    return None


def changes_of(units: Mapping[str, Any]) -> dict[str, Any]:
    return {k: units[k] for k in sorted(units) if k.startswith(PREFIX) and units[k] is not None}


def describe(key: str) -> str:
    """A change in words, for the conflict list."""
    kind, _, rest = key[len(PREFIX) :].partition(":")
    words = {
        "domain": "領域",
        "type": "類型",
        "field": "欄位",
        "enum": "允許值",
        "label": "顯示名稱",
        "used_by": "使用者",
    }
    return f"schema 的{words.get(kind, kind)} {rest}"


# -- a change as units ----------------------------------------------------------------


def _types(document: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {t["name"]: t for t in document.get("types") or [] if isinstance(t, dict)}


def _fields(entity: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {f["name"]: f for f in entity.get("fields") or [] if isinstance(f, dict)}


def _without(mapping: Mapping[str, Any], *keys: str) -> dict[str, Any]:
    return {k: v for k, v in mapping.items() if k not in keys}


def changes_between(old: Mapping[str, Any], new: Mapping[str, Any]) -> dict[str, Any] | None:
    """`new` as units on top of `old`; None when it is more than additions, and is a new
    version for a person. An addition of a required field is more: cards lack it."""
    units: dict[str, Any] = {}
    if canonical(_without(old, "version", "domains", "types")) != canonical(
        _without(new, "version", "domains", "types")
    ):
        return None
    old_domains = list(old.get("domains") or [])
    if not set(old_domains) <= set(new.get("domains") or []):
        return None
    for name in new.get("domains") or []:
        if name not in old_domains:
            units[domain_key(name)] = {"domain": name}
    before, after = _types(old), _types(new)
    if not set(before) <= set(after):
        return None
    for name, entity in after.items():
        was = before.get(name)
        if was is None:
            units[type_key(name)] = copy.deepcopy(entity)
            continue
        if canonical(_without(was, "fields", "label")) != canonical(
            _without(entity, "fields", "label")
        ):
            return None
        if was.get("label") != entity.get("label"):
            units[label_key(name)] = {"label": entity.get("label")}
        moved = _field_changes(name, _fields(was), _fields(entity))
        if moved is None:
            return None
        units.update(moved)
    if not units:
        # Only an order or nothing moved: an order is not an addition.
        return None if canonical(old) != canonical({**new, "version": old.get("version")}) else {}
    return units


def _field_changes(
    type_name: str, before: Mapping[str, Any], after: Mapping[str, Any]
) -> dict[str, Any] | None:
    units: dict[str, Any] = {}
    if not set(before) <= set(after):
        return None
    for name, item in after.items():
        was = before.get(name)
        if was is None:
            if item.get("required"):
                return None
            units[field_key(type_name, name)] = _without(item, "used_by")
            for home in item.get("used_by") or []:
                units[used_by_key(type_name, name, home)] = {"home": home}
            continue
        if canonical(_without(was, "label", "enum", "used_by")) != canonical(
            _without(item, "label", "enum", "used_by")
        ):
            return None
        if was.get("label") != item.get("label"):
            units[label_key(type_name, name)] = {"label": item.get("label")}
        old_enum, new_enum = list(was.get("enum") or []), list(item.get("enum") or [])
        if not set(old_enum) <= set(new_enum):
            return None
        for value in new_enum:
            if value not in old_enum:
                units[enum_key(type_name, name, value)] = {"value": value}
        old_homes, new_homes = list(was.get("used_by") or []), list(item.get("used_by") or [])
        if not set(old_homes) <= set(new_homes):
            return None
        for home in new_homes:
            if home not in old_homes:
                units[used_by_key(type_name, name, home)] = {"home": home}
    return units


# -- units on a version ---------------------------------------------------------------


def _target(key: str) -> tuple[str, str, str]:
    """(type, field, what follows) from a change's key."""
    rest = key[len(PREFIX) :].partition(":")[2]
    head, _, tail = rest.partition(":")
    type_name, _, field = head.partition(".")
    return type_name, field, tail


def _apply(document: dict[str, Any], key: str, value: Mapping[str, Any]) -> str | None:
    """Apply one change in place; why it does not fit, or None."""
    kind = key[len(PREFIX) :].partition(":")[0]
    type_name, field, tail = _target(key)
    if kind == "domain":
        domains = document.setdefault("domains", [])
        if type_name not in domains:
            domains.append(type_name)
        return None
    types = _types(document)
    if kind == "type":
        existing = types.get(type_name)
        if existing is None:
            document["types"].append(copy.deepcopy(dict(value)))
            return None
        if canonical(existing) != canonical(dict(value)):
            return f"類型 {type_name} 已經有另一個定義"
        return None
    entity = types.get(type_name)
    if entity is None:
        return f"類型 {type_name} 已經不在這個版本"
    if kind == "label" and not field:
        entity["label"] = value.get("label")
        return None
    item = _fields(entity).get(field)
    if kind == "field":
        wanted = _without(value, *_WORDING)
        if item is None:
            entity["fields"].append({**copy.deepcopy(dict(value)), "name": field})
            return None
        if canonical(_without(item, *_WORDING)) != canonical(wanted):
            return f"{type_name}.{field} 已經有另一個定義"
        return None
    if item is None:
        return f"欄位 {type_name}.{field} 已經不在這個版本"
    if kind == "label":
        item["label"] = value.get("label")
    elif kind == "enum":
        allowed = item.get("enum")
        if not isinstance(allowed, list):
            return f"欄位 {type_name}.{field} 沒有允許值清單"
        if tail not in allowed:
            allowed.append(tail)
    elif kind == "used_by":
        item["used_by"] = sorted({*(item.get("used_by") or []), tail})
    return None


def _in_order(changes: Mapping[str, Any]) -> list[tuple[str, Any]]:
    return sorted(
        changes.items(),
        key=lambda pair: (KINDS.index(pair[0][len(PREFIX) :].partition(":")[0]), pair[0]),
    )


def _still_valid(document: dict[str, Any]) -> bool:
    return not catalog.validate(document)[1]


def overlay(
    base: Mapping[str, Any], changes: Mapping[str, Any]
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    """`base` with `changes`, and those that did not fit, `{"unit", "reason"}`. It depends
    only on what it is given, never on the order units arrived. A result that would not be
    a valid schema leaves the change out too, so a schema that loads is always the answer."""
    memo = (_digest(base), _digest(changes))
    if memo in _MEMO:
        kept, refused = _MEMO[memo]
        return copy.deepcopy(kept), list(refused)
    document = copy.deepcopy(dict(base))
    clashes: list[dict[str, str]] = []
    for key, value in _in_order(changes):
        trial = copy.deepcopy(document)
        reason = _apply(trial, key, value)
        if reason is None:
            trial_version = {
                **trial,
                "version": _derived_version(str(base.get("version")), changes),
            }
            if not _still_valid(trial_version):
                reason = "套用後 schema 不成立"
        if reason is not None:
            clashes.append({"unit": key, "reason": reason})
            continue
        document = trial
    document["version"] = _derived_version(str(base.get("version")), changes)
    if len(_MEMO) >= _MEMO_LIMIT:
        _MEMO.clear()
    _MEMO[memo] = (copy.deepcopy(document), list(clashes))
    return document, clashes


def _digest(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def _derived_version(base_version: str, changes: Mapping[str, Any]) -> str:
    return f"{catalog.base_version(base_version)}+{_digest(dict(changes))[:12]}"


# -- what a vault reads -----------------------------------------------------------------


def _base_document(workspace: Path, ref: str) -> dict[str, Any]:
    from capabilities.bi_cards import schema_versions

    return schema_versions.base_document(workspace, ref)[1]


def effective_ref(workspace: Path, units: Mapping[str, Any]) -> str:
    """The schema these units read: the `schema` unit's version, or with units on top a
    version named by their digest, installed here so that everything resolves it as any
    other. `schema_unknown` when this PC has not got the base."""
    base = str(units.get(SCHEMA_UNIT) or "")
    changes = changes_of(units)
    if not base or not changes:
        return base
    schema_id, _, version = base.partition("@")
    derived = _derived_version(version, changes)
    if not catalog.schema_path(workspace, schema_id, derived).is_file():
        document, _ = overlay(_base_document(workspace, base), changes)
        try:
            catalog.install(workspace, f"{derived}.json", json.dumps(document, ensure_ascii=False))
        except catalog.SchemaInstallError as failure:
            raise BiStoreError("schema_invalid", failure.message) from None
    return f"{schema_id}@{derived}"


def clashes(workspace: Path, units: Mapping[str, Any]) -> list[dict[str, str]]:
    """The changes these units cannot apply. Empty when the base is not on this PC."""
    base = str(units.get(SCHEMA_UNIT) or "")
    changes = changes_of(units)
    if not base or not changes:
        return []
    try:
        document = _base_document(workspace, base)
    except BiStoreError:
        return []
    return overlay(document, changes)[1]


# -- which skills a change touches --------------------------------------------------------


def _names_of(*items: Mapping[str, Any]) -> list[str]:
    found = []
    for item in items:
        for key in ("name", "label"):
            value = item.get(key)
            if isinstance(value, str) and value:
                found.append(value)
    return found


def _touched(old: Mapping[str, Any], new: Mapping[str, Any]) -> tuple[list[dict[str, Any]], bool]:
    """(what changed between two documents, whether something could not be read as a type's
    or a field's change). `used_by` says who uses a field, not what it means: not a change."""
    from capabilities.bi_cards import schema_versions

    found: list[dict[str, Any]] = []
    breaking = {
        (c["type"], c["field"]) for c in schema_versions.diff(old, new) if c.get("breaking")
    }
    if canonical(_without(old, "version", "domains", "types")) != canonical(
        _without(new, "version", "domains", "types")
    ):
        return found, True
    old_domains, new_domains = set(old.get("domains") or []), set(new.get("domains") or [])
    if old_domains - new_domains:
        return found, True
    for name in sorted(new_domains - old_domains):
        found.append({"type": None, "field": None, "names": [name], "breaking": False})
    before, after = _types(old), _types(new)
    for name in sorted(set(before) | set(after)):
        was, now = before.get(name), after.get(name)
        if was is None or now is None:
            found.append(
                {
                    "type": name,
                    "field": None,
                    "names": _names_of(*[e for e in (was, now) if e]),
                    "breaking": now is None,
                    "type_level": True,
                }
            )
            continue
        if canonical(_without(was, "fields")) != canonical(_without(now, "fields")):
            found.append(
                {
                    "type": name,
                    "field": None,
                    "names": _names_of(was, now),
                    "breaking": (name, None) in breaking,
                    "type_level": True,
                }
            )
        old_fields, new_fields = _fields(was), _fields(now)
        for field in sorted(set(old_fields) | set(new_fields)):
            a, b = old_fields.get(field), new_fields.get(field)
            if a is not None and b is not None:
                if canonical(_without(a, "used_by")) == canonical(_without(b, "used_by")):
                    continue
            names = _names_of(*[e for e in (a, b) if e])
            enums = set((a or {}).get("enum") or []) ^ set((b or {}).get("enum") or [])
            found.append(
                {
                    "type": name,
                    "field": field,
                    "names": [*names, *sorted(enums)],
                    "breaking": (name, field) in breaking,
                }
            )
    return found, False


def _mentions(body: str, names: Iterable[str]) -> str | None:
    for name in names:
        if re.fullmatch(r"[A-Za-z0-9_]+", name):
            if re.search(rf"(?<![A-Za-z0-9_]){re.escape(name)}(?![A-Za-z0-9_])", body):
                return name
        elif name and name in body:
            return name
    return None


def _thing(item: Mapping[str, Any]) -> str:
    if item["type"] is None:
        return f"領域 {item['names'][0]}"
    return f"{item['type']}.{item['field']}" if item["field"] else str(item["type"])


def skill_verdict(
    old: Mapping[str, Any] | None,
    new: Mapping[str, Any] | None,
    body: str,
    card_types: Iterable[str],
    role: str,
    *,
    gone: Iterable[str] = (),
) -> dict[str, Any]:
    """Whether a change touches a skill: `{"needs_update", "update_blocks", "update_reason"}`.

    A skill is touched when a changed type is one of its `card_types`, or its text names a
    changed type, field, label, enum value or domain. A skill with no `card_types` reads
    every type, so anything that can lose meaning touches it. An addition never stops a
    skill from running, since nothing it relied on moved; what can lose meaning does. When
    this cannot be worked out, it is flagged and stops, as every version change used to.
    `gone` are changes it was written with that a later version took in: what they said is
    no longer known, so each counts as possibly losing meaning, for its own type."""
    unknown = {
        "needs_update": True,
        "update_blocks": True,
        "update_reason": "看不出這次 schema 改動對這份規則的影響",
    }
    if old is None or new is None:
        return unknown
    found, unreadable = _touched(old, new)
    if unreadable:
        return unknown
    for key in gone:
        type_name, field, _ = _target(key)
        found.append(
            {
                "type": type_name if "." in key or field else None,
                "field": field or None,
                "names": [n for n in (type_name, field) if n],
                "breaking": True,
            }
        )
    scope = set(card_types)
    hits: list[tuple[bool, str]] = []
    for item in found:
        breaking = bool(item["breaking"])
        named = _mentions(body, item["names"])
        if role == "classify":
            # It lists types, not fields, and is generated again when it is unedited.
            if item.get("type_level") or breaking:
                hits.append((breaking, _thing(item)))
            continue
        if item["type"] in scope or named is not None or (breaking and not scope):
            hits.append((breaking, _thing(item)))
    if not hits:
        return {"needs_update": False, "update_blocks": False, "update_reason": ""}
    blocks = any(breaking for breaking, _ in hits)
    things = "、".join(sorted({thing for _, thing in hits}))
    return {
        "needs_update": True,
        "update_blocks": blocks,
        "update_reason": f"schema 改了 {things}"
        + ("，規則可能不再成立" if blocks else "；只是新增，規則照常可以用"),
    }
