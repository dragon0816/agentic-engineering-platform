"""The schemas a dataset can use: the shipped `bi.schema/v1.1` plus schemas
installed on this PC (owner 2026-10-21: 「只讓資料集換 schema」).

An installed schema lives at `<workspace>/bi/schemas/<schema_id>@<version>.json`
(a `/` in the id is a sub-folder). It uses the registry's JSON format; the
minimum a person writes is `schema_id`, `version`, `title` and `types`, each
type with `name`, `label` and `fields`, each field with `name`, `label`,
`kind` and `class`. Everything else has a default and is filled in before the
document reaches the `Registry`. Install validates strictly and names the
place and the problem of every error. An installed id@version is immutable:
the same content again is a no-op, different content is refused.

Only `bi.schema/*` ids are BI schemas (the Dashboard and the chat's
`bi__query` work on them). Under that prefix only a newer version of the
shipped `bi.schema/v1.1` installs, and only when it keeps every shipped type
and field as it is (BI ingest §5.2, owner 2026-10-27): it may add types,
fields, enum values and aliases, so "BI" always contains the shipped, tested
types. A version may declare `migrations.renames` (`{"Type.old": "new"}`),
which a dataset upgrade uses to move values (§5.3).
"""

from __future__ import annotations

import json
import re
from importlib import resources
from pathlib import Path
from typing import Any

from capabilities.bi_cards.schema import BI_PREFIX, Registry, registry, shipped, widens
from capabilities.bi_cards.store import BiStore, BiStoreError

SCHEMAS_DIR = "schemas"
#: The shipped example of a non-BI schema (「產品規格」) and its sample CSVs, in
#: the order they import so every link resolves. Offered, never installed.
EXAMPLE_SCHEMA = "product-spec@1.0.0.json"
EXAMPLE_CSVS = (
    ("Supplier", "product-spec_suppliers.csv"),
    ("Component", "product-spec_components.csv"),
    ("Product", "product-spec_products.csv"),
    ("SpecItem", "product-spec_spec_items.csv"),
)
MAX_SCHEMA_BYTES = 1024 * 1024
ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,39}(/[a-z0-9][a-z0-9._-]{0,39}){0,2}$")
VERSION_RE = re.compile(r"^(0|[1-9]\d{0,5})\.(0|[1-9]\d{0,5})\.(0|[1-9]\d{0,5})$")
TYPE_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,39}$")
FIELD_RE = re.compile(r"^[a-z][a-z0-9_]{0,59}$")
KINDS = ("str", "int", "float", "bool", "date", "enum", "list", "link", "linklist")
CLASSES = ("sourced", "judgement", "derived")
TYPE_DOMAINS = ("one", "multi", "none")
TOP_KEYS = {
    "schema_id",
    "version",
    "title",
    "description",
    "status",
    "source",
    "id_rules",
    "field_classes",
    "domains",
    "enum_aliases",
    "ignored_fields",
    "computed_fields",
    "migrations",
    "types",
}
TYPE_KEYS = {
    "name",
    "label",
    "description",
    "code_key",
    "naming",
    "domain",
    "has_confidence",
    "fields",
    "name_pattern",
}
#: A type's `name_pattern`: a card name should match it (a quality check, BI D4).
MAX_NAME_PATTERN = 200
FIELD_KEYS = {
    "name",
    "label",
    "description",
    "kind",
    "class",
    "enum",
    "aliases",
    "required",
    "default",
    "range",
    "link_to",
    "list",
}


class SchemaInstallError(Exception):
    def __init__(self, code: str, message: str, errors: list[dict[str, str]] | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.errors = errors or []


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _strings(value: Any) -> bool:
    return isinstance(value, list) and all(_text(v) for v in value)


def _version_tuple(text: str) -> tuple[int, ...]:
    return tuple(int(p) for p in str(text).split(".") if p.isdigit())


def bi_problems(document: dict[str, Any]) -> list[dict[str, str]]:
    """Why a `bi.schema/*` document is not a compatible newer version of the
    shipped one; empty when it is."""
    base = registry()
    problems: list[dict[str, str]] = []
    if document.get("schema_id") != base.schema_id:
        problems.append(
            {
                "path": "schema_id",
                "message": f"「{BI_PREFIX}」開頭保留給內建的 BI schema，"
                f"只能安裝 {base.schema_id} 的相容新版本；請換一個 id",
            }
        )
        return problems
    version = str(document.get("version") or "")
    if VERSION_RE.match(version) and _version_tuple(version) <= _version_tuple(base.version):
        problems.append(
            {"path": "version", "message": f"必須比內建的 {base.version} 新，例如 1.2.0"}
        )
    types = {t.get("name"): t for t in document.get("types") or [] if isinstance(t, dict)}
    domains = set(document.get("domains") or [])
    for missing in [d for d in base.domains if d not in domains]:
        problems.append({"path": "domains", "message": f"不能移除內建的領域「{missing}」"})
    for entity in base.types.values():
        raw = types.get(entity.name)
        if raw is None:
            problems.append({"path": "types", "message": f"不能移除內建類型「{entity.name}」"})
            continue
        where = f"types（{entity.name}）"
        if list(raw.get("naming") or ["name"]) != list(entity.naming):
            problems.append({"path": f"{where}.naming", "message": "不能改內建類型的命名欄位"})
        fields = {f.get("name"): f for f in raw.get("fields") or [] if isinstance(f, dict)}
        for item in entity.fields:
            at = f"{where}.fields（{item.name}）"
            given = fields.get(item.name)
            if given is None:
                problems.append({"path": at, "message": "不能移除內建欄位"})
                continue
            kind = given.get("kind")
            if kind != item.kind and not widens(item.kind, str(kind)):
                problems.append(
                    {
                        "path": f"{at}.kind",
                        "message": f"內建欄位必須維持 {item.kind}（只可放寬成清單或小數）",
                    }
                )
            if given.get("class") != item.klass:
                problems.append(
                    {"path": f"{at}.class", "message": f"內建欄位必須維持 {item.klass}"}
                )
            link_to = given.get("link_to") or []
            if list([link_to] if isinstance(link_to, str) else link_to) != list(item.link_to):
                problems.append({"path": f"{at}.link_to", "message": "不能改內建欄位的連結目標"})
            # A list without allowed values loosens an enum (Node `domain` in 2.0.0).
            unrestricted = kind == "list" and not given.get("enum")
            if (
                item.enum
                and not unrestricted
                and not set(item.enum) <= set(given.get("enum") or [])
            ):
                problems.append(
                    {"path": f"{at}.enum", "message": "可以新增允許值，但不能移除內建的允許值"}
                )
    return problems


def validate(document: Any) -> tuple[dict[str, Any] | None, list[dict[str, str]]]:
    """(the document with every default filled in, errors). Each error is
    `{"path", "message"}`: where in the file, and what is wrong there."""
    errors: list[dict[str, str]] = []

    def error(path: str, message: str) -> None:
        errors.append({"path": path, "message": message})

    if not isinstance(document, dict):
        error("$", "schema 檔必須是一個 JSON 物件 {…}")
        return None, errors
    for key in sorted(set(document) - TOP_KEYS):
        error(key, f"不認得的欄位「{key}」（拼錯了嗎？）")
    schema_id = document.get("schema_id")
    if not isinstance(schema_id, str) or not ID_RE.match(schema_id):
        error(
            "schema_id",
            "必填；小寫英數字與 . _ -，可用 / 分段（最多 3 段），例如 example/product-spec",
        )
    bi = isinstance(schema_id, str) and schema_id.startswith(BI_PREFIX)
    kinds = (*KINDS, "virtual") if bi else KINDS  # the shipped Signal title is virtual
    version = document.get("version")
    if not isinstance(version, str) or not VERSION_RE.match(version):
        error("version", "必填；格式是 主.次.修訂，例如 1.0.0")
    title = document.get("title")
    if not _text(title) or len(str(title)) > 120:
        error("title", "必填；1–120 個字的名稱，例如 產品規格")
    domains = document.get("domains", [])
    if not _strings(domains) or len(set(domains)) != len(domains):
        error("domains", '必須是不重複的文字清單，例如 ["robotics", "wireless"]')
        domains = []
    raw_types = document.get("types")
    if not isinstance(raw_types, list) or not raw_types:
        error("types", "必填；至少一種卡片類型的清單")
        raw_types = []
    if len(raw_types) > 50:
        error("types", "最多 50 種卡片類型")
    type_names = [t.get("name") for t in raw_types if isinstance(t, dict)]
    types: list[dict[str, Any]] = []
    seen_types: set[str] = set()
    enum_fields: dict[str, set[str]] = {}
    for i, raw in enumerate(raw_types):
        where = f"types[{i}]"
        if not isinstance(raw, dict):
            error(where, "每種類型必須是 JSON 物件")
            continue
        for key in sorted(set(raw) - TYPE_KEYS):
            error(f"{where}.{key}", f"不認得的欄位「{key}」")
        name = raw.get("name")
        if not isinstance(name, str) or not TYPE_RE.match(name):
            error(f"{where}.name", "必填；英文字母開頭，只用英數字與 _，例如 Product")
            name = f"#{i}"
        elif name in seen_types:
            error(f"{where}.name", f"類型「{name}」重複")
        seen_types.add(name)
        where = f"types[{i}]（{name}）"
        if not _text(raw.get("label")):
            error(f"{where}.label", "必填；顯示用的名稱，例如 產品")
        domain_mode = raw.get("domain", "none")
        if domain_mode not in TYPE_DOMAINS:
            error(f"{where}.domain", f"只能是 {list(TYPE_DOMAINS)}")
        has_confidence = raw.get("has_confidence", False)
        if not isinstance(has_confidence, bool):
            error(f"{where}.has_confidence", "必須是 true 或 false")
        name_pattern = raw.get("name_pattern") or ""
        if not isinstance(name_pattern, str) or len(name_pattern) > MAX_NAME_PATTERN:
            error(f"{where}.name_pattern", f"必須是文字（最多 {MAX_NAME_PATTERN} 字）")
            name_pattern = ""
        else:
            try:
                re.compile(name_pattern)
            except re.error as failure:
                error(f"{where}.name_pattern", f"不是有效的規則：{failure}")
                name_pattern = ""
        raw_fields = raw.get("fields")
        if not isinstance(raw_fields, list) or not raw_fields:
            error(f"{where}.fields", "必填；至少一個欄位的清單")
            raw_fields = []
        if len(raw_fields) > 100:
            error(f"{where}.fields", "每種類型最多 100 個欄位")
        fields: list[dict[str, Any]] = []
        seen_fields: dict[str, str] = {}
        for j, item in enumerate(raw_fields):
            at = f"{where}.fields[{j}]"
            if not isinstance(item, dict):
                error(at, "每個欄位必須是 JSON 物件")
                continue
            for key in sorted(set(item) - FIELD_KEYS):
                error(f"{at}.{key}", f"不認得的欄位「{key}」")
            fname = item.get("name")
            if not isinstance(fname, str) or not FIELD_RE.match(fname):
                error(f"{at}.name", "必填；小寫英文字母開頭，只用小寫英數字與 _，例如 lead_time")
                fname = f"#{j}"
            elif fname in seen_fields:
                error(f"{at}.name", f"欄位「{fname}」在這個類型重複")
            at = f"{where}.fields[{j}]（{fname}）"
            kind = item.get("kind")
            if kind not in kinds:
                error(f"{at}.kind", f"必填；只能是 {list(KINDS)}")
            seen_fields[fname] = str(kind)
            if not _text(item.get("label")):
                error(f"{at}.label", "必填；顯示用的名稱")
            if item.get("class") not in CLASSES:
                error(
                    f"{at}.class",
                    f"必填；只能是 {list(CLASSES)}（事實／判斷／衍生）",
                )
            enum = item.get("enum")
            if kind == "enum" or (kind == "list" and enum not in (None, [])):
                # A list may name its allowed values too (BI vault V9).
                if not _strings(enum) or not enum or len(set(enum)) != len(enum):
                    error(f"{at}.enum", "列舉欄位（kind enum）需要不重複的允許值清單")
                    enum = None
                else:
                    enum_fields.setdefault(fname, set()).update(enum)
            elif enum not in (None, []):
                error(f"{at}.enum", "只有 kind 是 enum 或 list 的欄位可以有 enum")
            aliases = item.get("aliases", [])
            if not isinstance(aliases, list) or not all(isinstance(a, str) for a in aliases):
                error(f"{at}.aliases", "必須是文字清單（CSV 欄名的別名）")
                aliases = []
            required = item.get("required", False)
            if not isinstance(required, bool):
                error(f"{at}.required", "必須是 true 或 false")
            default = item.get("default")
            if kind == "enum" and default is not None and enum and default not in enum:
                error(f"{at}.default", f"預設值「{default}」不在 enum 允許值裡")
            value_range = item.get("range")
            if value_range is not None:
                numbers = (int, float) if kind == "float" else (int,)
                ok = (
                    kind in ("int", "float")
                    and isinstance(value_range, list)
                    and len(value_range) == 2
                    and all(isinstance(v, numbers) and not isinstance(v, bool) for v in value_range)
                    and value_range[0] <= value_range[1]
                )
                if not ok:
                    error(f"{at}.range", "只有 int 或 float 欄位可以有 range，格式是 [最小, 最大]")
            link_to = item.get("link_to", [])
            if isinstance(link_to, str):
                link_to = [link_to]
            if kind in ("link", "linklist"):
                if bi and link_to in (None, []):
                    link_to = []  # the shipped Signal `related` links to any type
                elif not _strings(link_to) or not link_to:
                    error(f"{at}.link_to", "連結欄位（link / linklist）需要目標類型清單")
                    link_to = []
                for target in link_to:
                    if target not in type_names:
                        error(f"{at}.link_to", f"目標類型「{target}」不在這份 schema 的 types")
            elif link_to not in (None, []):
                error(f"{at}.link_to", "只有 link / linklist 欄位可以有 link_to")
                link_to = []
            is_list = kind in ("list", "linklist")
            if "list" in item and item["list"] is not is_list:
                error(f"{at}.list", f"kind {kind} 的 list 必須是 {str(is_list).lower()}")
            if fname == "domain" and not domains:
                error(f"{at}.name", "有 domain 欄位時，最上層需要 domains 清單")
            fields.append(
                {
                    "name": fname,
                    "label": str(item.get("label") or fname),
                    "kind": kind,
                    "class": item.get("class"),
                    "enum": list(enum) if kind in ("enum", "list") and enum else None,
                    "aliases": [a for a in aliases if a.strip()],
                    "required": bool(required),
                    "default": default,
                    "range": value_range,
                    "link_to": list(link_to or []),
                    "list": is_list,
                }
            )
        naming = raw.get("naming", ["name"])
        if not _strings(naming) or not naming:
            error(f"{where}.naming", '必須是欄位名稱清單，例如 ["name"]')
            naming = []
        for part in naming:
            if part not in seen_fields:
                error(f"{where}.naming", f"命名欄位「{part}」不在這個類型的 fields（預設是 name）")
            elif seen_fields[part] in ("list", "linklist"):
                error(f"{where}.naming", f"命名欄位「{part}」不能是清單欄位")
        types.append(
            {
                "name": name,
                "label": str(raw.get("label") or name),
                "naming": list(naming),
                "domain": domain_mode,
                "has_confidence": bool(has_confidence),
                "fields": fields,
                **({"name_pattern": name_pattern} if name_pattern else {}),
            }
        )
    enum_aliases = document.get("enum_aliases", {})
    if not isinstance(enum_aliases, dict):
        error("enum_aliases", "必須是 {欄位: {別名: 允許值}}")
        enum_aliases = {}
    for fname, table in enum_aliases.items():
        at = f"enum_aliases.{fname}"
        allowed = set(domains) if fname == "domain" else enum_fields.get(fname)
        if allowed is None:
            error(at, f"沒有叫「{fname}」的 enum 欄位")
            continue
        if not isinstance(table, dict):
            error(at, "必須是 {別名: 允許值}")
            continue
        for alias, value in table.items():
            if value not in allowed:
                error(f"{at}.{alias}", f"別名「{alias}」指向的「{value}」不在允許值裡")
    ignored = document.get("ignored_fields", {})
    if not isinstance(ignored, dict):
        error("ignored_fields", "必須是 {類型: [{field, aliases, reason}]}")
        ignored = {}
    for type_name, items in ignored.items():
        at = f"ignored_fields.{type_name}"
        if type_name not in seen_types:
            error(at, f"類型「{type_name}」不在 types")
        if not isinstance(items, list) or not all(
            isinstance(x, dict)
            and _text(x.get("field"))
            and _text(x.get("reason"))
            and isinstance(x.get("aliases", []), list)
            for x in items
        ):
            error(at, "每一項需要 field、reason 與 aliases 清單")
    migrations = document.get("migrations", {})
    renames = migrations.get("renames", {}) if isinstance(migrations, dict) else None
    if (
        not isinstance(migrations, dict)
        or set(migrations) - {"renames"}
        or not isinstance(renames, dict)
    ):
        error("migrations", '格式是 {"renames": {"類型.舊欄位": "新欄位"}}')
        renames = {}
    by_type = {t["name"]: {f["name"] for f in t["fields"]} for t in types}
    for old, new in renames.items():
        type_name, _, old_field = str(old).partition(".")
        if type_name not in by_type or not FIELD_RE.match(old_field):
            error(f"migrations.renames.{old}", "鍵的格式是「類型.舊欄位」，類型要在 types 裡")
        elif not isinstance(new, str) or new not in by_type[type_name]:
            error(f"migrations.renames.{old}", f"新欄位「{new}」不在 {type_name} 的 fields")
        elif old_field in by_type[type_name]:
            error(f"migrations.renames.{old}", f"舊欄位「{old_field}」還在 {type_name} 裡")
    if bi and not errors:
        errors.extend(bi_problems(document))
    if errors:
        return None, errors
    normalised = {key: value for key, value in document.items() if key != "types"}
    normalised.update(
        {
            "domains": list(domains),
            "enum_aliases": enum_aliases,
            "ignored_fields": {
                t: [{"aliases": [], **x} for x in items] for t, items in ignored.items()
            },
            "types": types,
        }
    )
    return normalised, []


# -- where installed schemas live ---------------------------------------------


def schemas_root(workspace: Path) -> Path:
    return workspace / "bi" / SCHEMAS_DIR


def schema_path(workspace: Path, schema_id: str, version: str) -> Path:
    return schemas_root(workspace).joinpath(*f"{schema_id}@{version}.json".split("/"))


def canonical(document: Any) -> str:
    """The stored text: content compared without formatting or key order."""
    return json.dumps(document, ensure_ascii=False, sort_keys=True, indent=1) + "\n"


_CACHE: dict[str, tuple[tuple[int, int], Registry | None]] = {}


def _load(path: Path) -> Registry | None:
    """An installed schema file as a registry, or None when it is unreadable
    or no longer valid (it is then not offered)."""
    try:
        stat = path.stat()
    except OSError:
        return None
    stamp = (stat.st_mtime_ns, stat.st_size)
    cached = _CACHE.get(str(path))
    if cached is not None and cached[0] == stamp:
        return cached[1]
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        found = None
    else:
        normalised, problems = validate(document)
        found = None if problems or normalised is None else Registry(normalised, "installed")
    _CACHE[str(path)] = (stamp, found)
    return found


def installed(workspace: Path) -> list[Registry]:
    root = schemas_root(workspace)
    if not root.is_dir():
        return []
    found = []
    for path in sorted(root.rglob("*.json")):
        reg = _load(path)
        # The file's place must match its content (a renamed file is not offered).
        if reg is not None and schema_path(workspace, reg.schema_id, reg.version) == path:
            found.append(reg)
    return found


def available(workspace: Path) -> list[Registry]:
    """The shipped versions first, then the installed ones by id and version
    (an installed copy of a shipped version is not listed twice)."""
    builtin = list(shipped())
    refs = {reg.ref for reg in builtin}
    return [*builtin, *(reg for reg in installed(workspace) if reg.ref not in refs)]


def _version_key(reg: Registry) -> tuple[int, ...]:
    return _version_tuple(reg.version)


def resolve(workspace: Path, ref: str) -> Registry:
    """`<id>@<version>`, or a bare `<id>` for its newest version."""
    text = str(ref or "").strip()
    schema_id, _, version = text.partition("@")
    matches = [r for r in available(workspace) if r.schema_id == schema_id]
    if version:
        matches = [r for r in matches if r.version == version]
    if not matches:
        raise BiStoreError("schema_unknown", f"找不到 schema「{text}」；先安裝，或選一個已有的")
    return max(matches, key=_version_key)


def for_store(store: BiStore) -> Registry:
    """The registry of the schema the dataset is bound to."""
    ref = store.schema_ref()
    try:
        return resolve(store.workspace, ref)
    except BiStoreError:
        raise BiStoreError(
            "schema_missing",
            f"資料集「{store.dataset}」使用的 schema「{ref}」不在這台電腦上（檔案被移走或改壞了）；"
            "請重新安裝同一個版本",
        ) from None


def listing(workspace: Path) -> list[dict[str, Any]]:
    return [
        {
            "id": reg.schema_id,
            "version": reg.version,
            "ref": reg.ref,
            "title": reg.title,
            "types": [{"name": t.name, "label": t.label} for t in reg.types.values()],
            "source": reg.source,
            "dashboard": reg.is_bi,
        }
        for reg in available(workspace)
    ]


def install(workspace: Path, filename: str, json_text: Any) -> dict[str, Any]:
    """Validate and install one schema file; idempotent for the same content."""
    if not isinstance(json_text, str) or not json_text.strip():
        raise SchemaInstallError("schema_missing_text", "沒有 schema 內容")
    if len(json_text.encode("utf-8")) > MAX_SCHEMA_BYTES:
        raise SchemaInstallError("schema_too_large", "schema 檔太大（上限 1 MB）")
    if filename and not str(filename).lower().endswith(".json"):
        raise SchemaInstallError("schema_not_json", "請選 .json 檔")
    try:
        document = json.loads(json_text.lstrip("﻿"))
    except ValueError as failure:
        line = getattr(failure, "lineno", None)
        where = f"第 {line} 行" if line else "$"
        raise SchemaInstallError(
            "schema_json_invalid",
            "不是有效的 JSON",
            [{"path": where, "message": str(getattr(failure, "msg", failure))}],
        ) from None
    if isinstance(document, dict):
        # A vault carries even a shipped version's file (KNOWLEDGE_REPO
        # decision 1); the same content is already installed, not "too old".
        same = next(
            (
                reg
                for reg in shipped()
                if (reg.schema_id, reg.version)
                == (document.get("schema_id"), document.get("version"))
            ),
            None,
        )
        if same is not None and canonical(same.document) == canonical(document):
            return {"ok": True, "id": same.schema_id, "version": same.version, "already": True}
    normalised, problems = validate(document)
    if problems or normalised is None:
        bi_only = str(document.get("schema_id") or "").startswith(BI_PREFIX) and problems == (
            bi_problems(document) if isinstance(document, dict) else []
        )
        raise SchemaInstallError(
            "schema_bi_not_compatible" if bi_only else "schema_invalid",
            (
                "這不是內建 BI schema 相容的新版本：只能新增，不能移除或修改內建的類型與欄位"
                if bi_only
                else f"schema 有 {len(problems)} 個問題，沒有安裝"
            ),
            problems,
        )
    schema_id, version = str(document["schema_id"]), str(document["version"])
    path = schema_path(workspace, schema_id, version)
    text = canonical(document)
    builtin = next(
        (reg for reg in shipped() if (reg.schema_id, reg.version) == (schema_id, version)), None
    )
    if builtin is not None:
        # A shipped version is never shadowed by a file (it would be ignored).
        if canonical(builtin.document) == text:
            return {"ok": True, "id": schema_id, "version": version, "already": True}
        raise SchemaInstallError(
            "schema_version_exists",
            f"{schema_id}@{version} 是內建的版本，不能用另一份內容安裝；請改用新的版本號",
            [{"path": "version", "message": f"{version} 是內建版本"}],
        )
    if path.is_file():
        if path.read_text(encoding="utf-8") == text:
            return {"ok": True, "id": schema_id, "version": version, "already": True}
        raise SchemaInstallError(
            "schema_version_exists",
            f"{schema_id}@{version} 已經安裝，而且內容不同。已安裝的版本不能修改；"
            "請把 version 改成新版本（例如 1.0.1）再安裝",
            [{"path": "version", "message": f"{version} 已被另一份內容使用"}],
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)
    return {"ok": True, "id": schema_id, "version": version, "already": False}


def _sample(name: str) -> str:
    return (resources.files("capabilities.bi_cards") / "samples" / name).read_text(
        encoding="utf-8-sig"
    )


def example() -> dict[str, Any]:
    """The shipped example schema file and its CSVs, for a person to install
    and import; nothing is written."""
    return {
        "schema": {"filename": EXAMPLE_SCHEMA, "json_text": _sample(EXAMPLE_SCHEMA)},
        "csv": [
            {"entity_type": entity_type, "filename": name, "text": _sample(name)}
            for entity_type, name in EXAMPLE_CSVS
        ],
    }
