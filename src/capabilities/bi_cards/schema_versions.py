"""Schema drafts, versions and dataset upgrades (BI ingest phase 2).

`docs/phases/BI_INGEST.md` §5, owner 2026-10-27 (「目前還在開發中尚未啟用，
為什麼不做，我想現在做」). A draft is a folder of immutable revisions under
`<workspace>/bi/schema-drafts/<id>/`: every save, every applied AI
suggestion and every revert writes a new revision, so nothing a person did is
lost. A revision may be invalid while someone works on it; it can be tried
or published only when valid. Publishing installs it through
`catalog.install`, where installed versions stay immutable.

A dataset can move to another version of the same schema id. The preview
reports what happens to the cards and writes nothing; applying it checks a
token so the cards cannot have changed since the preview, and runs in one
transaction. Nothing is silently rewritten: a removed field keeps its values
(hidden while the schema lacks it, shown again after moving back), a retired
enum value is listed for review, and only a rename the version declares
(`migrations.renames`) moves values, with a `migration` history row. A kind
change or a removed type that still has cards, or a changed card key, is
refused: that needs a new dataset.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
import uuid
from pathlib import Path
from typing import Any

from capabilities.bi_cards import catalog
from capabilities.bi_cards.schema import SCHEMA_FILE, Registry
from capabilities.bi_cards.store import BiStore, BiStoreError, now

DRAFTS_DIR = "schema-drafts"
DRAFT_FILE = "draft.json"
DRAFT_RE = re.compile(r"^[0-9a-f]{12}$")
MAX_NOTE = 200
REVISION_SOURCES = ("edit", "ai", "revert", "base")
DRAFT_REF_PREFIX = "draft:"
DRAFT_REF_RE = re.compile(r"^draft:([0-9a-f]{12})@rev(\d+)$")


# -- diffs -------------------------------------------------------------------


def _types(document: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(document, dict) or not isinstance(document.get("types"), list):
        return {}
    return {
        str(t.get("name")): t
        for t in document["types"]
        if isinstance(t, dict) and isinstance(t.get("name"), str)
    }


def _fields(raw: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(f.get("name")): f
        for f in raw.get("fields") or []
        if isinstance(f, dict) and isinstance(f.get("name"), str)
    }


def _links(value: Any) -> list[str]:
    return [value] if isinstance(value, str) else list(value or [])


def diff(old: Any, new: Any) -> list[dict[str, Any]]:
    """What changed between two schema documents, per type and field. Each
    change is `{"type", "field", "change", "detail", "breaking"}`; breaking
    changes can lose meaning for existing cards (removals, kind, key, links)."""
    changes: list[dict[str, Any]] = []
    renames = {}
    if isinstance(new, dict) and isinstance(new.get("migrations"), dict):
        renames = dict(new["migrations"].get("renames") or {})

    def add(type_name: str, field: str | None, change: str, detail: str, breaking: bool) -> None:
        changes.append(
            {
                "type": type_name,
                "field": field,
                "change": change,
                "detail": detail,
                "breaking": breaking,
            }
        )

    before, after = _types(old), _types(new)
    for name in after:
        if name not in before:
            add(name, None, "type_added", f"新增類型 {name}", False)
    for name, raw in before.items():
        if name not in after:
            add(name, None, "type_removed", f"移除類型 {name}", True)
            continue
        other = after[name]
        if list(raw.get("naming") or ["name"]) != list(other.get("naming") or ["name"]):
            add(name, None, "naming", "卡片的命名欄位改變", True)
        if raw.get("label") != other.get("label"):
            add(name, None, "label", f"顯示名稱 {raw.get('label')} → {other.get('label')}", False)
        old_fields, new_fields = _fields(raw), _fields(other)
        renamed = {
            old_name.split(".", 1)[1]: target
            for old_name, target in renames.items()
            if old_name.startswith(f"{name}.") and target in new_fields
        }
        for field, item in new_fields.items():
            if field not in old_fields and field not in renamed.values():
                note = "（必填）" if item.get("required") else ""
                add(name, field, "field_added", f"新增欄位 {field}{note}", False)
        for field, item in old_fields.items():
            if field in renamed:
                add(name, field, "renamed", f"{field} 改名為 {renamed[field]}", False)
                target = new_fields[renamed[field]]
            elif field not in new_fields:
                add(name, field, "field_removed", f"移除欄位 {field}", True)
                continue
            else:
                target = new_fields[field]
            if item.get("kind") != target.get("kind"):
                add(name, field, "kind", f"型別 {item.get('kind')} → {target.get('kind')}", True)
            if item.get("class") != target.get("class"):
                add(
                    name, field, "class", f"類別 {item.get('class')} → {target.get('class')}", False
                )
            if bool(item.get("required")) != bool(target.get("required")):
                state = "必填" if target.get("required") else "選填"
                add(name, field, "required", f"改為{state}", False)
            old_enum, new_enum = set(item.get("enum") or []), set(target.get("enum") or [])
            for value in sorted(new_enum - old_enum):
                add(name, field, "enum_added", f"新增允許值 {value}", False)
            for value in sorted(old_enum - new_enum):
                add(name, field, "enum_removed", f"移除允許值 {value}", True)
            if _links(item.get("link_to")) != _links(target.get("link_to")):
                add(name, field, "link_to", "連結目標類型改變", True)
            if item.get("label") != target.get("label"):
                add(
                    name,
                    field,
                    "label",
                    f"顯示名稱 {item.get('label')} → {target.get('label')}",
                    False,
                )
            if list(item.get("aliases") or []) != list(target.get("aliases") or []):
                add(name, field, "aliases", "欄名別名改變", False)
    return changes


# -- drafts ------------------------------------------------------------------


def drafts_root(workspace: Path) -> Path:
    return workspace / "bi" / DRAFTS_DIR


def _draft_dir(workspace: Path, draft_id: str) -> Path:
    if not DRAFT_RE.match(str(draft_id)):
        raise BiStoreError("draft_unknown", "找不到這份 schema 草稿")
    folder = drafts_root(workspace) / draft_id
    if not (folder / DRAFT_FILE).is_file():
        raise BiStoreError("draft_unknown", "找不到這份 schema 草稿")
    return folder


def replace(temporary: Path, path: Path, attempts: int = 5) -> None:
    """`os.replace` that waits out Windows refusing it while a virus scanner or
    the search indexer briefly holds either file."""
    for attempt in range(attempts):
        try:
            temporary.replace(path)
            return
        except PermissionError:
            if attempt == attempts - 1:
                raise
            time.sleep(0.05 * (attempt + 1))


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex[:8]}.tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=1, sort_keys=False) + "\n", encoding="utf-8"
    )
    replace(temporary, path)


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def base_document(workspace: Path, ref: str) -> tuple[Registry, dict[str, Any]]:
    """The schema a draft starts from, as its stored document."""
    reg = catalog.resolve(workspace, ref)
    if reg.source == "shipped":
        return reg, json.loads(SCHEMA_FILE.read_text(encoding="utf-8"))
    path = catalog.schema_path(workspace, reg.schema_id, reg.version)
    return reg, json.loads(path.read_text(encoding="utf-8"))


def _next_version(workspace: Path, schema_id: str, version: str) -> str:
    """The next minor version above every known version of the id."""
    known = [r.version for r in catalog.available(workspace) if r.schema_id == schema_id]
    major, minor = max(
        (catalog._version_tuple(v) for v in [*known, version]),  # noqa: SLF001
        default=(1, 0, 0),
    )[:2]
    return f"{major}.{minor + 1}.0"


def _check(document: Any) -> list[dict[str, str]]:
    _, problems = catalog.validate(document)
    return problems


def create_draft(workspace: Path, base: str, title: Any, actor: str) -> dict[str, Any]:
    reg, document = base_document(workspace, base)
    document = dict(document)
    document["version"] = _next_version(workspace, reg.schema_id, reg.version)
    draft_id = uuid.uuid4().hex[:12]
    folder = drafts_root(workspace) / draft_id
    at = now()
    meta = {
        "id": draft_id,
        "title": str(title or f"{reg.title} 草稿").strip()[:120],
        "base_ref": reg.ref,
        "schema_id": reg.schema_id,
        "by": actor,
        "at": at,
        "revisions": [],
        "published": [],
    }
    _write_json(folder / DRAFT_FILE, meta)
    _add_revision(workspace, draft_id, document, actor=actor, note="從基礎版本建立", source="base")
    return draft(workspace, draft_id)


def _add_revision(
    workspace: Path,
    draft_id: str,
    document: Any,
    *,
    actor: str,
    note: Any,
    source: str,
    copied_from: int | None = None,
) -> int:
    folder = _draft_dir(workspace, draft_id)
    meta = _read_json(folder / DRAFT_FILE)
    number = len(meta["revisions"]) + 1
    _write_json(folder / f"rev-{number}.json", document)
    entry: dict[str, Any] = {
        "rev": number,
        "at": now(),
        "by": actor,
        "note": str(note or "").strip()[:MAX_NOTE],
        "source": source,
        "valid": not _check(document),
    }
    if copied_from is not None:
        entry["copied_from"] = copied_from
    meta["revisions"].append(entry)
    _write_json(folder / DRAFT_FILE, meta)
    return number


def revision_document(workspace: Path, draft_id: str, rev: int | None = None) -> Any:
    folder = _draft_dir(workspace, draft_id)
    meta = _read_json(folder / DRAFT_FILE)
    number = len(meta["revisions"]) if rev is None else int(rev)
    if not 1 <= number <= len(meta["revisions"]):
        raise BiStoreError("revision_unknown", f"沒有第 {rev} 版")
    return _read_json(folder / f"rev-{number}.json")


def draft(workspace: Path, draft_id: str, rev: int | None = None) -> dict[str, Any]:
    """A draft with one revision (the latest by default): its document, its
    errors, and its diff against the base schema."""
    folder = _draft_dir(workspace, draft_id)
    meta = _read_json(folder / DRAFT_FILE)
    number = len(meta["revisions"]) if rev is None else int(rev)
    document = revision_document(workspace, draft_id, number)
    try:
        _, base = base_document(workspace, meta["base_ref"])
    except BiStoreError:
        base = None
    return {
        "draft": meta,
        "revision": number,
        "document": document,
        "errors": _check(document),
        "diff": diff(base, document) if base is not None else [],
    }


def drafts(workspace: Path) -> list[dict[str, Any]]:
    root = drafts_root(workspace)
    if not root.is_dir():
        return []
    found = []
    for folder in root.iterdir():
        try:
            meta = _read_json(folder / DRAFT_FILE)
        except (OSError, ValueError):
            continue
        last = meta["revisions"][-1] if meta["revisions"] else {}
        found.append(
            {
                "id": meta["id"],
                "title": meta["title"],
                "base_ref": meta["base_ref"],
                "schema_id": meta["schema_id"],
                "revisions": len(meta["revisions"]),
                "valid": bool(last.get("valid")),
                "updated": last.get("at") or meta["at"],
                "published": meta["published"],
            }
        )
    return sorted(found, key=lambda d: str(d["updated"]), reverse=True)


def save_revision(
    workspace: Path,
    draft_id: str,
    *,
    document: Any,
    json_text: Any,
    note: Any,
    source: Any,
    actor: str,
) -> dict[str, Any]:
    if document is None and isinstance(json_text, str):
        try:
            document = json.loads(json_text.lstrip("﻿"))
        except ValueError as failure:
            line = getattr(failure, "lineno", None)
            raise BiStoreError(
                "schema_json_invalid",
                f"不是有效的 JSON（第 {line} 行）" if line else "不是有效的 JSON",
            ) from None
    if not isinstance(document, dict):
        raise BiStoreError("document_missing", "需要 schema 內容（JSON 物件）")
    if len(json.dumps(document, ensure_ascii=False).encode("utf-8")) > catalog.MAX_SCHEMA_BYTES:
        raise BiStoreError("schema_too_large", "schema 太大（上限 1 MB）")
    kind = str(source or "edit")
    if kind not in ("edit", "ai"):
        raise BiStoreError("source_invalid", "source 只能是 edit 或 ai")
    meta = _read_json(_draft_dir(workspace, draft_id) / DRAFT_FILE)
    if document.get("schema_id") != meta["schema_id"]:
        raise BiStoreError(
            "schema_id_changed",
            f"草稿的 schema_id 必須維持 {meta['schema_id']}；要換 id 請另建草稿",
        )
    number = _add_revision(workspace, draft_id, document, actor=actor, note=note, source=kind)
    return draft(workspace, draft_id, number)


def draft_ref(draft_id: str, rev: int) -> str:
    """How a run names the draft revision whose schema it used (phase 6)."""
    return f"{DRAFT_REF_PREFIX}{draft_id}@rev{rev}"


def parse_draft_ref(ref: str) -> tuple[str, int]:
    found = DRAFT_REF_RE.match(ref)
    if found is None:
        raise BiStoreError("draft_unknown", "找不到這份 schema 草稿")
    return found.group(1), int(found.group(2))


def draft_registry(workspace: Path, draft_id: str, rev: Any = None) -> tuple[Registry, str]:
    """(a draft revision as a registry, its `draft:` ref), to try the draft on
    samples without installing it (BI ingest §9.1 「用樣本試跑」). Only a valid
    revision can be tried."""
    meta = _read_json(_draft_dir(workspace, draft_id) / DRAFT_FILE)
    if rev in (None, ""):
        number = len(meta["revisions"])
    elif isinstance(rev, int) and not isinstance(rev, bool):
        number = rev
    else:
        raise BiStoreError("revision_unknown", "draft_rev 必須是整數")
    document = revision_document(workspace, draft_id, number)
    normalised, problems = catalog.validate(document)
    if problems or normalised is None:
        raise BiStoreError(
            "draft_invalid",
            f"草稿第 {number} 版有 {len(problems)} 個問題，修正後才能試跑",
            errors=problems,
        )
    return Registry(normalised, "draft"), draft_ref(draft_id, number)


def revert(workspace: Path, draft_id: str, rev: Any, actor: str) -> dict[str, Any]:
    if not isinstance(rev, int) or isinstance(rev, bool):
        raise BiStoreError("revision_unknown", "需要要回復的版次 rev")
    document = revision_document(workspace, draft_id, rev)
    number = _add_revision(
        workspace,
        draft_id,
        document,
        actor=actor,
        note=f"回復到第 {rev} 版",
        source="revert",
        copied_from=rev,
    )
    return draft(workspace, draft_id, number)


def compare(workspace: Path, draft_id: str, left: Any, right: Any) -> dict[str, Any]:
    """The diff between two revisions, or the base (`left` = "base")."""
    meta = _read_json(_draft_dir(workspace, draft_id) / DRAFT_FILE)
    if left in (None, "", "base"):
        _, old = base_document(workspace, meta["base_ref"])
    else:
        old = revision_document(workspace, draft_id, int(left))
    new = revision_document(workspace, draft_id, None if right in (None, "") else int(right))
    return {"diff": diff(old, new)}


def publish(workspace: Path, draft_id: str, rev: Any, actor: str) -> dict[str, Any]:
    """Install a valid revision as a new, immutable version."""
    folder = _draft_dir(workspace, draft_id)
    meta = _read_json(folder / DRAFT_FILE)
    number = len(meta["revisions"]) if rev in (None, "") else int(rev)
    document = revision_document(workspace, draft_id, number)
    version = str(document.get("version") or "")
    newer = [
        r.version
        for r in catalog.available(workspace)
        if r.schema_id == meta["schema_id"]
        and catalog._version_tuple(r.version) >= catalog._version_tuple(version)  # noqa: SLF001
    ]
    if newer and not catalog.schema_path(workspace, meta["schema_id"], version).is_file():
        raise BiStoreError(
            "schema_version_not_newer",
            f"version {version} 不比已有的 {max(newer, key=catalog._version_tuple)} 新；"  # noqa: SLF001
            "請把 version 改大",
        )
    installed = catalog.install(
        workspace, f"{draft_id}.json", json.dumps(document, ensure_ascii=False)
    )
    ref = f"{installed['id']}@{installed['version']}"
    if not installed["already"]:
        meta["published"].append({"rev": number, "ref": ref, "at": now(), "by": actor})
        _write_json(folder / DRAFT_FILE, meta)
    return {**installed, "ref": ref, "draft": meta}


# -- dataset upgrade ---------------------------------------------------------


def _token(from_ref: str, to_ref: str, marker: str) -> str:
    """Changes whenever the cards change (`BiStore.change_marker`)."""
    text = f"{from_ref}|{to_ref}|{marker}"
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:24]


def _renames(target: Registry) -> dict[str, dict[str, str]]:
    found: dict[str, dict[str, str]] = {}
    migrations = target.document.get("migrations") or {}
    for old, new in dict(migrations.get("renames") or {}).items():
        type_name, _, field = str(old).partition(".")
        found.setdefault(type_name, {})[field] = str(new)
    return found


def impact(store: BiStore, current: Registry, target: Registry) -> dict[str, Any]:
    """What moving `store` from `current` to `target` does to its cards."""
    cards = store.card_rows()
    everything = store.all_fields()
    renames = _renames(target)
    types: list[dict[str, Any]] = []
    blocked: list[dict[str, str]] = []
    totals = {"hidden": 0, "retired": 0, "renamed": 0, "required_missing": 0}
    for type_name in sorted({c["entity_type"] for c in cards} | set(target.types)):
        of_type = [c for c in cards if c["entity_type"] == type_name]
        old_type = current.types.get(type_name)
        new_type = target.types.get(type_name)
        entry: dict[str, Any] = {
            "type": type_name,
            "cards": len(of_type),
            "hidden": [],
            "renamed": [],
            "retired": [],
            "required_missing": [],
        }
        if new_type is None:
            if of_type:
                blocked.append(
                    {"code": "type_removed", "message": f"{type_name} 還有 {len(of_type)} 張卡片"}
                )
            types.append(entry)
            continue
        if old_type is not None and of_type and old_type.naming != new_type.naming:
            blocked.append(
                {"code": "naming_changed", "message": f"{type_name} 的命名欄位改變，卡片鍵會變"}
            )
        moved = renames.get(type_name, {})
        counts: dict[str, int] = {}
        for card in of_type:
            for name in everything.get(card["id"], {}):
                counts[name] = counts.get(name, 0) + 1
        for name, count in sorted(counts.items()):
            target_name = moved.get(name, name)
            definition = new_type.get(target_name)
            if name in moved and definition is not None:
                entry["renamed"].append({"from": name, "to": target_name, "cards": count})
                totals["renamed"] += count
            if definition is None:
                entry["hidden"].append({"field": name, "cards": count})
                totals["hidden"] += count
                continue
            old_definition = old_type.get(name) if old_type is not None else None
            if old_definition is not None and old_definition.kind != definition.kind:
                blocked.append(
                    {
                        "code": "kind_changed",
                        "message": f"{type_name}.{name} 的型別 {old_definition.kind} → "
                        f"{definition.kind}，有 {count} 張卡片有值",
                    }
                )
            if definition.enum:
                for card in of_type:
                    item = everything.get(card["id"], {}).get(name)
                    if item is None:
                        continue
                    values = item["value"] if isinstance(item["value"], list) else [item["value"]]
                    for value in values:
                        if value not in definition.enum:
                            entry["retired"].append(
                                {
                                    "card_id": card["id"],
                                    "name": card["name"],
                                    "field": target_name,
                                    "value": value,
                                }
                            )
                            totals["retired"] += 1
        for definition in new_type.fields:
            if not definition.required:
                continue
            lacking = [
                c
                for c in of_type
                if definition.name not in everything.get(c["id"], {})
                and not any(
                    moved.get(old) == definition.name for old in everything.get(c["id"], {})
                )
            ]
            if lacking:
                entry["required_missing"].append({"field": definition.name, "cards": len(lacking)})
                totals["required_missing"] += len(lacking)
        types.append(entry)
    return {"types": types, "blocked": blocked, "totals": totals}


def _target(workspace: Path, store: BiStore, to: Any) -> tuple[Registry, Registry]:
    store.refuse_write()
    if not store.exists:
        raise BiStoreError("dataset_unknown", f"沒有這個資料集「{store.dataset}」")
    current = catalog.for_store(store)
    target = catalog.resolve(workspace, str(to or ""))
    if target.schema_id != current.schema_id:
        raise BiStoreError(
            "schema_id_different",
            f"只能升級到同一個 schema（{current.schema_id}）的其他版本；換 schema 請另建資料集",
        )
    if target.version == current.version:
        raise BiStoreError("schema_same", f"資料集已經使用 {current.ref}")
    return current, target


def upgrade_preview(workspace: Path, dataset: str, to: Any) -> dict[str, Any]:
    store = BiStore(workspace, dataset)
    current, target = _target(workspace, store, to)
    found = impact(store, current, target)
    return {
        "from": current.ref,
        "to": target.ref,
        "diff": diff(current.document, target.document),
        **found,
        "preview_token": _token(current.ref, target.ref, store.change_marker()),
    }


def upgrade_apply(workspace: Path, dataset: str, to: Any, token: Any, actor: str) -> dict[str, Any]:
    store = BiStore(workspace, dataset)
    current, target = _target(workspace, store, to)
    marker = store.change_marker()
    if token != _token(current.ref, target.ref, marker):
        raise BiStoreError("preview_stale", "資料集在預覽後有變動，請重新預覽")
    found = impact(store, current, target)
    if found["blocked"]:
        raise BiStoreError(
            "schema_upgrade_breaking",
            "這次升級會讓既有卡片失去意義，沒有套用；請另建資料集",
            blocked=found["blocked"],
        )
    moved = store.upgrade_schema(
        current.ref,
        target.ref,
        _renames(target),
        marker=marker,
        actor=actor,
        totals=found["totals"],
    )
    return {"from": current.ref, "to": target.ref, "moved": moved, **found}
