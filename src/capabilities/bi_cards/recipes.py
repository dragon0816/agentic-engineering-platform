"""Recipes of the BI rule path: several passes over one multi-table source.

BI ingest phase 3 (`docs/phases/BI_INGEST.md` §6; the engine design of
`docs/phases/BI_CASE_B.md` §3–§5; contract in `docs/CONTRACTS.md` "BI rule
path: recipes and multi-table sources"). Upstream runs its CLI once per card
type on one report, each run with its own `--table` filter and mapping; a
recipe (`aep.bi.recipe/v1`) puts those runs into one file so one run covers
the whole report and the order of the passes is fixed.

The mapping keys and transforms are those of the fixture's `bi_ingest.py`
(`transform_rows`, `explode_cell`, `apply_derive`, `render_line`,
`select_tables`, `name_aliases`), reimplemented here and compared in tests,
never imported. Applied per pass in upstream's order: `skip_rows` →
`text_replace` → `explode` → `exclude_names` → `derive` → `compose`; then the
Case A importer maps and normalises the rows, so values, enums, links and
warnings behave exactly as a CSV import does.

Where AEP differs from upstream (BI_CASE_B §5, owner 2026-10-27): rows that
name the same card are merged into one candidate, lists unioned and every
row's cell kept as evidence; a name that two passes would make two types is
a `role_conflict`: the earlier pass is the default and the later candidate
waits for the person (default 略過, they may still choose 新建).

A recipe is checked strictly when saved and when run: an unknown key is
refused (`mapping_key_unknown`; upstream ignores it silently), every regular
expression is length-capped and compiled (`recipe_invalid` names the pass and
key), and every type and mapped field must exist in the dataset's schema.
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field
from typing import Any

from capabilities.bi_cards import importer
from capabilities.bi_cards.schema import EMPTY, Registry, TypeDef, norm_key, split_list
from capabilities.bi_cards.store import BiStore, BiStoreError

RECIPE_FORMAT = "aep.bi.recipe/v1"
MAX_REGEX = 300
MAX_PASSES = 50
MAX_EXCERPT = 500
TOP_KEYS = {"schema_version", "name", "description", "dataset_schema", "name_aliases", "passes"}
PASS_KEYS = {"id", "tables", "entity_type", "mapping", "description"}
MAPPING_KEYS = {
    "columns",
    "entity_type",
    "enum_aliases",
    "defaults",
    "skip_rows",
    "text_replace",
    "explode",
    "exclude_names",
    "derive",
    "compose",
    "name_aliases",
}
_PASS_ID = re.compile(r"[A-Za-z0-9_-]{1,40}")
_INDEXES = re.compile(r"\d+(?:\s*-\s*\d+)?(?:\s*,\s*\d+(?:\s*-\s*\d+)?)*")
#: Upstream's explode separators (`SEPS`): commas too, unlike a list cell.
_EXPLODE_SEPARATORS = set(";；,，、|\n")
_OPEN, _CLOSE = set("(（"), set(")）")
_PAREN_TAIL = re.compile(r"\s*[(（]([^()（）]*)[)）]\s*等?\s*$")
_PLACEHOLDER = re.compile(r"\{([^{}]+)\}")
#: Fields whose value is a card name, resolved through `name_aliases`.
NAME_FIELDS = ("name", "product_name")


# -- validation ------------------------------------------------------------


def _invalid(pass_id: str | None, key: str | None, message: str) -> BiStoreError:
    where = f"配方步驟 {pass_id}" if pass_id else "配方"
    if key:
        where += f" 的 {key}"
    return BiStoreError("recipe_invalid", f"{where}：{message}", pass_id=pass_id, key=key)


def _unknown(pass_id: str | None, key: str) -> BiStoreError:
    where = f"配方步驟 {pass_id}" if pass_id else "配方"
    return BiStoreError(
        "mapping_key_unknown",
        f"{where} 有不認得的設定「{key}」（請檢查拼字）",
        pass_id=pass_id,
        key=key,
    )


def _keys(given: dict[str, Any], allowed: set[str], pass_id: str | None, prefix: str) -> None:
    for key in given:
        if key not in allowed:
            raise _unknown(pass_id, f"{prefix}{key}")


def _text_map(value: Any, pass_id: str | None, key: str) -> dict[str, str]:
    if not isinstance(value, dict) or not all(
        isinstance(k, str) and isinstance(v, str) for k, v in value.items()
    ):
        raise _invalid(pass_id, key, "必須是 {文字: 文字}")
    return dict(value)


def _text_list(value: Any, pass_id: str | None, key: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise _invalid(pass_id, key, "必須是文字清單")
    return list(value)


def _regex(pattern: Any, pass_id: str, key: str) -> str:
    if not isinstance(pattern, str) or not pattern:
        raise _invalid(pass_id, key, "正規表示式必須是非空文字")
    if len(pattern) > MAX_REGEX:
        raise _invalid(pass_id, key, f"正規表示式超過 {MAX_REGEX} 字")
    try:
        re.compile(pattern)
    except re.error as error:
        raise _invalid(pass_id, key, f"正規表示式無效：{pattern}（{error}）") from error
    return pattern


def _field(entity: TypeDef, name: Any, pass_id: str, key: str) -> str:
    if not isinstance(name, str) or entity.get(name) is None:
        raise _invalid(pass_id, key, f"{entity.name} 沒有欄位 {name}")
    return name


def _selector(value: Any, pass_id: str) -> str:
    text = str(value if value is not None else "all").strip()
    if text == "all" or _INDEXES.fullmatch(text):
        return text
    if text.startswith("has:") and any(c.strip() for c in text[4:].split("|")):
        return text
    if text.startswith("sheet:") and text[6:].strip():
        return text
    raise _invalid(
        pass_id, "tables", "表格選擇只能是 all、編號（0,2-3）、has:欄名|欄名 或 sheet:工作表名"
    )


def _mapping(raw: Any, entity: TypeDef, pass_id: str) -> dict[str, Any]:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise _invalid(pass_id, "mapping", "必須是 JSON 物件")
    _keys(raw, MAPPING_KEYS, pass_id, "mapping.")
    out: dict[str, Any] = {}
    if "columns" in raw:
        columns = _text_map(raw["columns"], pass_id, "mapping.columns")
        for target in columns.values():
            _field(entity, target, pass_id, "mapping.columns")
        out["columns"] = columns
    if "entity_type" in raw:
        if norm_key(raw["entity_type"]) != norm_key(entity.name):
            raise _invalid(pass_id, "mapping.entity_type", "與步驟的 entity_type 不同")
    if "enum_aliases" in raw:
        aliases = raw["enum_aliases"]
        if not isinstance(aliases, dict):
            raise _invalid(pass_id, "mapping.enum_aliases", "必須是 {欄位: {別名: 值}}")
        out["enum_aliases"] = {
            str(k): _text_map(v, pass_id, f"mapping.enum_aliases.{k}") for k, v in aliases.items()
        }
    if "defaults" in raw:
        defaults = raw["defaults"]
        if not isinstance(defaults, dict) or not all(
            isinstance(v, str | int | float | bool) for v in defaults.values()
        ):
            raise _invalid(pass_id, "mapping.defaults", "必須是 {欄位: 值}")
        for name in defaults:
            _field(entity, name, pass_id, "mapping.defaults")
        out["defaults"] = dict(defaults)
    if "skip_rows" in raw:
        rules = raw["skip_rows"]
        if not isinstance(rules, list):
            raise _invalid(pass_id, "mapping.skip_rows", "必須是清單")
        out["skip_rows"] = []
        for rule in rules:
            if not isinstance(rule, dict):
                raise _invalid(pass_id, "mapping.skip_rows", "每條規則必須是物件")
            _keys(rule, {"column", "contains"}, pass_id, "mapping.skip_rows.")
            if not isinstance(rule.get("column"), str):
                raise _invalid(pass_id, "mapping.skip_rows", "需要 column")
            contains = _text_list(rule.get("contains"), pass_id, "mapping.skip_rows.contains")
            out["skip_rows"].append({"column": rule["column"], "contains": contains})
    if "text_replace" in raw:
        rules = raw["text_replace"]
        if not isinstance(rules, list):
            raise _invalid(pass_id, "mapping.text_replace", "必須是清單")
        out["text_replace"] = []
        for rule in rules:
            if not isinstance(rule, dict):
                raise _invalid(pass_id, "mapping.text_replace", "每條規則必須是物件")
            _keys(rule, {"column", "pairs", "into"}, pass_id, "mapping.text_replace.")
            if not isinstance(rule.get("column"), str):
                raise _invalid(pass_id, "mapping.text_replace", "需要 column")
            pairs = rule.get("pairs")
            if not isinstance(pairs, list) or not all(
                isinstance(p, list) and len(p) == 2 and isinstance(p[1], str) for p in pairs
            ):
                raise _invalid(pass_id, "mapping.text_replace.pairs", "必須是 [[正規表示式, 取代]]")
            checked = [[_regex(p[0], pass_id, "mapping.text_replace.pairs"), p[1]] for p in pairs]
            item: dict[str, Any] = {"column": rule["column"], "pairs": checked}
            if "into" in rule:
                if not isinstance(rule["into"], str) or not rule["into"]:
                    raise _invalid(pass_id, "mapping.text_replace.into", "必須是欄名")
                item["into"] = rule["into"]
            out["text_replace"].append(item)
    if "explode" in raw:
        rules = raw["explode"]
        if not isinstance(rules, list):
            raise _invalid(pass_id, "mapping.explode", "必須是清單")
        out["explode"] = []
        for rule in rules:
            if not isinstance(rule, dict):
                raise _invalid(pass_id, "mapping.explode", "每條規則必須是物件")
            _keys(rule, {"column", "into", "strip_after", "set"}, pass_id, "mapping.explode.")
            if not isinstance(rule.get("column"), str) or not isinstance(rule.get("into"), str):
                raise _invalid(pass_id, "mapping.explode", "需要 column 與 into")
            item = {"column": rule["column"], "into": rule["into"]}
            if "strip_after" in rule:
                if not isinstance(rule["strip_after"], str) or not rule["strip_after"]:
                    raise _invalid(pass_id, "mapping.explode.strip_after", "必須是文字")
                item["strip_after"] = rule["strip_after"]
            if "set" in rule:
                item["set"] = _text_map(rule["set"], pass_id, "mapping.explode.set")
            out["explode"].append(item)
    if "exclude_names" in raw:
        out["exclude_names"] = _text_list(raw["exclude_names"], pass_id, "mapping.exclude_names")
    if "derive" in raw:
        derive = raw["derive"]
        if not isinstance(derive, dict):
            raise _invalid(pass_id, "mapping.derive", "必須是 {目標欄: 規則}")
        out["derive"] = {}
        for target, rule in derive.items():
            key = f"mapping.derive.{target}"
            if not isinstance(rule, dict):
                raise _invalid(pass_id, key, "規則必須是物件")
            _keys(rule, {"from", "map", "all"}, pass_id, f"{key}.")
            sources = _text_list(rule.get("from"), pass_id, f"{key}.from")
            patterns = _text_map(rule.get("map"), pass_id, f"{key}.map")
            for pattern in patterns:
                _regex(pattern, pass_id, f"{key}.map")
            if "all" in rule and not isinstance(rule["all"], bool):
                raise _invalid(pass_id, f"{key}.all", "必須是 true 或 false")
            out["derive"][str(target)] = {
                "from": sources,
                "map": patterns,
                "all": bool(rule.get("all")),
            }
    if "compose" in raw:
        out["compose"] = _text_map(raw["compose"], pass_id, "mapping.compose")
    if "name_aliases" in raw:
        out["name_aliases"] = _text_map(raw["name_aliases"], pass_id, "mapping.name_aliases")
    return out


def validate(recipe: Any, reg: Registry) -> dict[str, Any]:
    """The recipe, checked and normalised; raises `recipe_invalid` or
    `mapping_key_unknown` naming the pass and key."""
    if not isinstance(recipe, dict):
        raise _invalid(None, None, "必須是 JSON 物件")
    _keys(recipe, TOP_KEYS, None, "")
    given_format = recipe.get("schema_version", RECIPE_FORMAT)
    if given_format != RECIPE_FORMAT:
        raise _invalid(None, "schema_version", f"只支援 {RECIPE_FORMAT}")
    name = recipe.get("name")
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > 80:
        raise _invalid(None, "name", "需要 1–80 字的名稱")
    out: dict[str, Any] = {"schema_version": RECIPE_FORMAT, "name": name.strip()}
    if "description" in recipe:
        if not isinstance(recipe["description"], str):
            raise _invalid(None, "description", "必須是文字")
        out["description"] = recipe["description"]
    if "dataset_schema" in recipe:
        wanted = str(recipe["dataset_schema"]).split("@", 1)[0]
        if wanted != reg.schema_id:
            raise _invalid(
                None, "dataset_schema", f"配方寫給 {wanted}，這個資料集用的是 {reg.schema_id}"
            )
        out["dataset_schema"] = str(recipe["dataset_schema"])
    if "name_aliases" in recipe:
        out["name_aliases"] = _text_map(recipe["name_aliases"], None, "name_aliases")
    passes = recipe.get("passes")
    if not isinstance(passes, list) or not passes:
        raise _invalid(None, "passes", "至少需要一個步驟")
    if len(passes) > MAX_PASSES:
        raise _invalid(None, "passes", f"最多 {MAX_PASSES} 個步驟")
    seen: set[str] = set()
    out["passes"] = []
    for number, raw in enumerate(passes):
        if not isinstance(raw, dict):
            raise _invalid(None, f"passes[{number}]", "步驟必須是物件")
        pass_id = raw.get("id")
        if not isinstance(pass_id, str) or not _PASS_ID.fullmatch(pass_id):
            raise _invalid(None, f"passes[{number}].id", "每個步驟需要 id（英數、- 或 _，1–40 字）")
        if pass_id in seen:
            raise _invalid(pass_id, "id", "步驟 id 重複")
        seen.add(pass_id)
        _keys(raw, PASS_KEYS, pass_id, "")
        try:
            entity = reg.type(str(raw.get("entity_type") or ""))
        except KeyError as error:
            raise _invalid(
                pass_id, "entity_type", f"這個資料集的 schema 沒有卡片類型 {raw.get('entity_type')}"
            ) from error
        step: dict[str, Any] = {
            "id": pass_id,
            "tables": _selector(raw.get("tables"), pass_id),
            "entity_type": entity.name,
            "mapping": _mapping(raw.get("mapping"), entity, pass_id),
        }
        if isinstance(raw.get("description"), str):
            step["description"] = raw["description"]
        out["passes"].append(step)
    return out


# -- table selection ----------------------------------------------------------


def select_tables(tables: list[dict[str, Any]], selector: str) -> tuple[list[int], list[int]]:
    """(chosen indexes, indexes asked for that the source does not have)."""
    text = selector.strip()
    if text == "all":
        return [t["index"] for t in tables], []
    if text.startswith("has:"):
        wanted = [c.strip() for c in text[4:].split("|") if c.strip()]
        return [t["index"] for t in tables if any(c in t["columns"] for c in wanted)], []
    if text.startswith("sheet:"):
        name = text[6:].strip()
        return [t["index"] for t in tables if str(t["title"]).strip() == name], []
    asked: list[int] = []
    for part in text.split(","):
        part = part.strip()
        if "-" in part:
            low, high = (int(x) for x in part.split("-", 1))
            asked.extend(range(low, high + 1))
        elif part:
            asked.append(int(part))
    present = {t["index"] for t in tables}
    chosen = list(dict.fromkeys(i for i in asked if i in present))
    return chosen, sorted({i for i in asked if i not in present})


# -- transforms (upstream `transform_rows`) ----------------------------------


@dataclass
class Row:
    """One row on its way through a pass: its cells now, which source
    columns each cell came from, and where the source row is."""

    table: int
    number: int
    locator: dict[str, Any]
    source: dict[str, str]
    cells: dict[str, str]
    origin: dict[str, list[str]]
    aliased: list[tuple[str, str]] = field(default_factory=list)

    def copy(self) -> Row:
        return Row(
            self.table,
            self.number,
            dict(self.locator),
            self.source,
            dict(self.cells),
            {k: list(v) for k, v in self.origin.items()},
            list(self.aliased),
        )


class Aliases:
    """`name_aliases`: a name compared loosely (`norm_key`) → the card name."""

    def __init__(self, *maps: dict[str, str]) -> None:
        self.map: dict[str, str] = {}
        for given in maps:
            for alias, name in given.items():
                self.map[norm_key(alias)] = name

    def canon(self, text: str) -> str:
        stripped = str(text).strip()
        return self.map.get(norm_key(stripped), stripped)


def split_top(text: str) -> list[str]:
    """Split on ; ， 、 | , newline, never inside (...) or （...）."""
    parts: list[str] = []
    buf: list[str] = []
    depth = 0
    for ch in str(text):
        if ch in _OPEN:
            depth += 1
        elif ch in _CLOSE:
            depth = max(0, depth - 1)
        if depth == 0 and ch in _EXPLODE_SEPARATORS:
            parts.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    parts.append("".join(buf))
    return [p.strip() for p in parts if p.strip()]


def split_paren(part: str) -> tuple[str, str]:
    """'Qorvo(GaN)' → ('Qorvo', 'GaN'); '穩懋(3105)' → ('穩懋', '3105')."""
    found = _PAREN_TAIL.search(part)
    if found:
        return part[: found.start()].strip(), found.group(1).strip()
    return re.sub(r"等$", "", part).strip(), ""


def explode_cell(raw: str, spec: dict[str, Any], aliases: Aliases) -> list[dict[str, str]]:
    text = str(raw).strip()
    if text.lower() in EMPTY:
        return []
    items = []
    for part in split_top(text):
        if spec.get("strip_after"):
            part = part.split(spec["strip_after"])[0].strip()
        base, paren = split_paren(part)
        if not base or base.lower() in EMPTY:
            continue
        ticker = paren if re.fullmatch(r"\d{4}", paren) else ""
        items.append(
            {
                "found": base,
                "name": aliases.canon(base),
                "ticker": ticker,
                "note": "" if ticker else paren,
            }
        )
    return items


def _skip(cells: dict[str, str], rules: list[dict[str, Any]]) -> bool:
    for rule in rules:
        value = str(cells.get(rule["column"], "")).lower()
        if any(word.lower() in value for word in rule["contains"]):
            return True
    return False


def render_line(line: str, cells: dict[str, str]) -> str:
    names = _PLACEHOLDER.findall(line)
    values = {}
    for name in names:
        value = str(cells.get(name, "") or "").strip()
        values[name] = "" if value.lower() in EMPTY else value
    if names and not any(values.values()):
        return ""
    return _PLACEHOLDER.sub(lambda m: values[m.group(1)], line)


def _origin_of(row: Row, columns: list[str]) -> list[str]:
    found: list[str] = []
    for column in columns:
        for origin in row.origin.get(column, []):
            if origin not in found:
                found.append(origin)
    return found


def transform(
    rows: list[Row], mapping: dict[str, Any], aliases: Aliases
) -> tuple[list[Row], list[tuple[Row, int]]]:
    """Upstream's `transform_rows`, keeping where every cell came from.
    Returns the rows and the source rows an explode split into several."""
    skip = mapping.get("skip_rows", [])
    replace = mapping.get("text_replace", [])
    explode = mapping.get("explode", [])
    derive = mapping.get("derive", {})
    compose = mapping.get("compose", {})
    exclude = {norm_key(aliases.canon(x)) for x in mapping.get("exclude_names", [])}
    out: list[Row] = []
    exploded: list[tuple[Row, int]] = []
    for original in rows:
        row = original.copy()
        if skip and _skip(row.cells, skip):
            continue
        for rule in replace:
            column = rule["column"]
            if column not in row.cells:
                continue
            value = str(row.cells[column])
            for pattern, replacement in rule["pairs"]:
                value = re.sub(pattern, replacement, value)
            into = rule.get("into", column)
            row.cells[into] = value
            row.origin[into] = list(row.origin.get(column, [column]))
        produced: list[Row]
        if explode:
            produced = []
            for spec in explode:
                column = spec["column"]
                if column not in row.cells:
                    continue
                for item in explode_cell(row.cells[column], spec, aliases):
                    made = row.copy()
                    origin = list(row.origin.get(column, [column]))
                    made.cells[spec["into"]] = item["name"]
                    made.cells["__ticker"], made.cells["__note"] = item["ticker"], item["note"]
                    for key in (spec["into"], "__ticker", "__note"):
                        made.origin[key] = list(origin)
                    for key, value in spec.get("set", {}).items():
                        made.cells[key] = value
                        made.origin[key] = []
                    if item["name"] != item["found"]:
                        made.aliased.append((item["found"], item["name"]))
                    produced.append(made)
            if len(produced) > 1:
                exploded.append((original, len(produced)))
        else:
            produced = [row]
        for made in produced:
            if exclude and norm_key(aliases.canon(made.cells.get("name", ""))) in exclude:
                continue
            for target, rule in derive.items():
                if str(made.cells.get(target, "")).strip():
                    continue
                text = " ".join(str(made.cells.get(c, "")) for c in rule["from"])
                hits = []
                for pattern, value in rule["map"].items():
                    if re.search(pattern, text, re.I):
                        hits.append(value)
                        if not rule["all"]:
                            break
                if hits:
                    made.cells[target] = "、".join(dict.fromkeys(hits))
                    made.origin[target] = _origin_of(made, rule["from"])
            for target, template in compose.items():
                lines = (render_line(line, made.cells) for line in template.split("\n"))
                text = "\n".join(line for line in lines if line)
                if text:
                    made.cells[target] = text
                    made.origin[target] = _origin_of(made, _PLACEHOLDER.findall(template))
            out.append(made)
    return out, exploded


# -- the engine ---------------------------------------------------------------


def _link_name(text: str, aliases: Aliases) -> str:
    """Upstream `to_link_name`: `[[x]]` → x, a trailing `(…)` dropped, the
    alias resolved."""
    value = str(text).strip()
    found = re.fullmatch(r"\[\[(.+?)\]\]", value)
    if found:
        value = re.sub(r"\.md$", "", found.group(1).split("|")[0].split("/")[-1])
    else:
        value, _ = split_paren(value)
    return aliases.canon(value)


def _targets(mapping: dict[str, Any]) -> list[str]:
    """Columns a transform writes, which name a field by its own name."""
    found = [r["into"] for r in mapping.get("explode", [])]
    found += [r["into"] for r in mapping.get("text_replace", []) if "into" in r]
    found += list(mapping.get("derive", {}))
    found += list(mapping.get("compose", {}))
    return list(dict.fromkeys(found))


@dataclass
class Pass:
    spec: dict[str, Any]
    entity: TypeDef
    tables: list[int]
    missing: list[int]
    read: int
    rows: list[Row]
    exploded: list[tuple[Row, int]]
    explicit: dict[str, str]
    headers: list[str]


def _prepare(
    reg: Registry, tables: list[dict[str, Any]], spec: dict[str, Any], aliases: Aliases
) -> Pass:
    entity = reg.type(spec["entity_type"])
    mapping = spec["mapping"]
    chosen, missing = select_tables(tables, spec["tables"])
    by_index = {t["index"]: t for t in tables}
    rows = []
    for index in chosen:
        table = by_index[index]
        for item in table["rows"]:
            locator: dict[str, Any]
            if table["locator"] == "line" and table.get("sheet"):
                # An Excel sheet read from its Markdown (BI vault V2).
                locator = {"sheet": table["sheet"], "table": index, "line": item["row"]}
            elif table["locator"] == "line":
                locator = {"table": index, "line": item["row"]}
            elif table["locator"] == "sheet":
                locator = {"sheet": table["title"], "row": item["row"]}
            else:
                locator = {"table": index, "row": item["row"]}
            cells = {str(k): str(v) for k, v in item["cells"].items()}
            rows.append(Row(index, item["row"], locator, cells, dict(cells), {}))
    for row in rows:
        row.origin = {c: [c] for c in row.cells}
    # Keys of `aliases.map` are already loose keys; `norm_key` keeps them.
    pass_aliases = Aliases(aliases.map, mapping.get("name_aliases", {}))
    out, exploded = transform(rows, mapping, pass_aliases)
    explicit = {norm_key(k): v for k, v in mapping.get("columns", {}).items()}
    for target in _targets(mapping):
        if entity.get(target) is not None:
            explicit.setdefault(norm_key(target), target)
    if entity.get("ticker") is not None:
        explicit.setdefault(norm_key("__ticker"), "ticker")
    first = [t for t in _targets(mapping) if norm_key(t) in explicit]
    seen = list(dict.fromkeys([*first, *(k for r in out for k in r.cells)]))
    headers = [h for h in seen if not h.startswith("__") or norm_key(h) in explicit]
    # Card names and link targets go through `name_aliases` before keys are built.
    for row in out:
        for header in headers:
            mapped = explicit.get(norm_key(header))
            if mapped is None:
                mapped = reg.map_column(entity, header)[0]
            item = entity.get(mapped) if mapped else None
            value = row.cells.get(header, "")
            if item is None or not value.strip():
                continue
            if item.name in NAME_FIELDS:
                resolved = pass_aliases.canon(value)
                if resolved != value.strip():
                    row.aliased.append((value.strip(), resolved))
                row.cells[header] = resolved
            elif item.is_link:
                parts = split_list(value) if item.is_list else [value]
                row.cells[header] = "、".join(_link_name(p, pass_aliases) for p in parts)
    out = [r for r in out if any(str(r.cells.get(h, "")).strip() for h in headers)]
    read = sum(len(by_index[i]["rows"]) for i in chosen)
    return Pass(spec, entity, chosen, missing, read, out, exploded, explicit, headers)


def _preview(
    store: BiStore,
    reg: Registry,
    step: Pass,
    filename: str,
    extra_keys: dict[str, set[str]] | None,
) -> importer.Preview | None:
    if not step.rows or not step.headers:
        return None
    text = io.StringIO()
    writer = csv.writer(text, lineterminator="\n")
    writer.writerow(step.headers)
    for row in step.rows:
        writer.writerow([row.cells.get(h, "") for h in step.headers])
    mapping = step.spec["mapping"]
    return importer.preview(
        store,
        entity_type=step.entity.name,
        filename=filename,
        csv_text=text.getvalue(),
        mapping={
            "columns": dict(step.explicit),
            "enum_aliases": mapping.get("enum_aliases", {}),
            "defaults": mapping.get("defaults", {}),
        },
        extra_keys=extra_keys,
        schema=reg,
    )


def _evidence(source_id: str, row: Row, columns: list[str]) -> dict[str, Any] | None:
    excerpt = " / ".join(
        dict.fromkeys(row.source[c].strip() for c in columns if row.source.get(c, "").strip())
    )
    if not excerpt:
        return None
    return {
        "source_id": source_id,
        "locator": {**row.locator, "column": "、".join(columns)},
        "excerpt": excerpt[:MAX_EXCERPT],
    }


def _candidates(step: Pass, prepared: importer.Preview, source_id: str) -> list[dict[str, Any]]:
    header_of = {c["field"]: c["source"] for c in prepared.columns if c["field"]}
    found = []
    for preview_row in prepared.rows:
        row = step.rows[preview_row["row"] - 2]
        planned = prepared.planned.get(preview_row["row"])
        fields = []
        for cell in preview_row["fields"]:
            if cell["normalized"] is None:
                continue
            header = header_of.get(cell["field"])
            columns = _origin_of(row, [header]) if header else []
            proof = _evidence(source_id, row, columns) if str(cell["raw"] or "").strip() else None
            fields.append(
                {
                    "field": cell["field"],
                    "value": cell["normalized"],
                    "basis": "fact" if proof else "unknown",
                    "evidence": [proof] if proof else [],
                    "current": None,
                    "change": "add",
                }
            )
        warnings = [
            {"code": w["code"], "message": w["message"]}
            for w in preview_row["warnings"]
            if w["code"] != "name_missing"
        ]
        for found_name, name in row.aliased:
            warnings.append(
                {"code": "alias_merged", "message": f"「{found_name}」依名稱別名併入「{name}」"}
            )
        found.append(
            {
                "id": "",
                "pass_id": step.spec["id"],
                "entity_type": step.entity.name,
                "canonical_key": preview_row["canonical_key"],
                "name": planned.name if planned is not None else "",
                "synthetic": bool(planned.synthetic) if planned is not None else False,
                "match": "new",
                "match_ids": [],
                "action": "skip",
                "review": "pending",
                "choice": None,
                "base_version": None,
                "fields": fields,
                "errors": [],
                "warnings": warnings,
                "edits": [],
            }
        )
    return found


def _add_warning(candidate: dict[str, Any], warning: dict[str, str]) -> None:
    if warning not in candidate["warnings"]:
        candidate["warnings"].append(warning)


def _merge(into: dict[str, Any], other: dict[str, Any]) -> None:
    """Fold a later row naming the same card into the candidate: lists are
    unioned, an empty field is filled, `body` texts are joined, and every
    row's cell is kept as evidence. A different scalar keeps the first value
    (as upstream within one run) and says so."""
    by_name = {f["field"]: f for f in into["fields"]}
    for item in other["fields"]:
        mine = by_name.get(item["field"])
        if mine is None:
            into["fields"].append(item)
            by_name[item["field"]] = item
            continue
        same = mine["value"] == item["value"]
        if isinstance(mine["value"], list) and isinstance(item["value"], list):
            mine["value"] = [*mine["value"], *(v for v in item["value"] if v not in mine["value"])]
        elif item["field"] == "body" and not same:
            if str(item["value"]) not in str(mine["value"]):
                mine["value"] = f"{mine['value']}\n\n{item['value']}"
        elif not same:
            _add_warning(
                into,
                {
                    "code": "value_conflict",
                    "message": f"{item['field']} 另有一列寫「{item['value']}」，保留第一個值",
                },
            )
            continue
        for proof in item["evidence"]:
            if proof not in mine["evidence"]:
                mine["evidence"].append(proof)
        if mine["evidence"] and mine["basis"] == "unknown":
            mine["basis"] = "fact"
    into["synthetic"] = bool(into["synthetic"] or other["synthetic"])
    for warning in other["warnings"]:
        _add_warning(into, warning)


def build(
    store: BiStore,
    reg: Registry,
    recipe: dict[str, Any],
    tables: list[dict[str, Any]],
    *,
    source_id: str,
    filename: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Run every pass of a validated recipe over the tables. Returns the
    candidates (not yet evaluated against the cards) and the run layout:
    tables, passes and run-level warnings. Writes nothing."""
    aliases = Aliases(recipe.get("name_aliases", {}))
    steps = [_prepare(reg, tables, spec, aliases) for spec in recipe["passes"]]
    # Link targets may be made by any pass, earlier or later: collect every
    # pass's keys first, then preview again knowing all of them.
    keys: dict[str, set[str]] = {}
    for step in steps:
        prepared = _preview(store, reg, step, filename, None)
        if prepared is not None:
            keys.setdefault(step.entity.name, set()).update(
                p.canonical_key for p in prepared.planned.values()
            )
    merged: dict[tuple[str, str], dict[str, Any]] = {}
    ordered: list[dict[str, Any]] = []
    pass_views = []
    for step in steps:
        prepared = _preview(store, reg, step, filename, keys)
        warnings: list[dict[str, Any]] = []
        if step.missing:
            warnings.append(
                {
                    "code": "table_missing",
                    "message": f"來源沒有表格 {', '.join(str(i) for i in step.missing)}",
                }
            )
        if not step.tables:
            warnings.append({"code": "pass_no_table", "message": "這個步驟沒有選到任何表格"})
        for row, count in step.exploded:
            warnings.append(
                {
                    "code": "exploded_row",
                    "message": f"表格 {row.table} 第 {row.number} 列拆成 {count} 列",
                    "table": row.table,
                    "row": row.number,
                    "count": count,
                }
            )
        pass_views.append(
            {
                "id": step.spec["id"],
                "entity_type": step.entity.name,
                "tables": step.tables,
                "rows_read": step.read,
                "rows_out": len(step.rows),
                "columns": [] if prepared is None else prepared.columns,
                "warnings": warnings,
            }
        )
        if prepared is None:
            continue
        for candidate in _candidates(step, prepared, source_id):
            key = candidate["canonical_key"]
            if not key:
                ordered.append(candidate)
                continue
            earlier = merged.get((candidate["entity_type"], key))
            if earlier is None:
                merged[(candidate["entity_type"], key)] = candidate
                ordered.append(candidate)
            else:
                _merge(earlier, candidate)
    # A name two passes would make two types: the earlier pass is the
    # default; the later candidate waits for the person (owner 2026-10-27).
    first_type: dict[str, dict[str, Any]] = {}
    for candidate in ordered:
        key = candidate["canonical_key"]
        if not key:
            continue
        earlier = first_type.setdefault(key, candidate)
        if earlier is candidate or earlier["entity_type"] == candidate["entity_type"]:
            continue
        _add_warning(
            candidate,
            {
                "code": "role_conflict",
                "message": f"「{key}」在步驟 {earlier['pass_id']} 已是 {earlier['entity_type']}；"
                f"這張 {candidate['entity_type']} 預設略過，確認是不同角色才改成新建",
            },
        )
        candidate["choice"] = {"action": "skip", "card_id": None}
    for number, candidate in enumerate(ordered, start=1):
        candidate["id"] = f"c{number}"
    used: dict[int, list[str]] = {}
    for step in steps:
        for index in step.tables:
            used.setdefault(index, []).append(step.spec["id"])
    table_views = [
        {
            "index": t["index"],
            "title": t["title"],
            "columns": t["columns"],
            "rows": len(t["rows"]),
            "pass_id": next(iter(used.get(t["index"], [])), None),
            "pass_ids": used.get(t["index"], []),
        }
        for t in tables
    ]
    run_warnings = [
        {
            "code": "table_unused",
            "message": f"表格 {t['index']}「{t['title']}」沒有任何步驟讀取",
            "table": t["index"],
        }
        for t in tables
        if t["index"] not in used
    ]
    layout = {"tables": table_views, "passes": pass_views, "warnings": run_warnings}
    return ordered, layout
