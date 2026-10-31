"""The BI schema registry: `bi.schema/v1.1`, data shipped inside the package.

Schema is data (ADR-K10): types, fields, field classes (ADR-K11), enums and
their aliases, column aliases and link targets all come from
`bi_schema_v1_1.json`, generated from the robotics sample's schema v4 by
`scripts/build_bi_schema_v1_1.py`. Nothing outside `capabilities.bi_cards`
imports these types; the Harness stays type-agnostic.

Application `priority` is not a field (#222): an imported 優先度 column is
reported as ignored with `PRIORITY_REASON`. Trend priority is computed for
display (measurement_impact x our_fit), never stored.

BI vault V9 (`docs/phases/BI_VAULT.md` §12): a second shipped version,
`bi.schema/v1.1@2.0.0` (`bi_schema_v2.json`, from the owner's manager's
schema v8 by `scripts/build_bi_schema_v2.py`; 2.0.0 so it never meets a local
Session A version, which are 1.x minor steps), adds `float` fields, allowed
values on a list field (`enum` on kind `list`), and widens one-value fields to
lists (Node `domain`); a widening is not a breaking change (`WIDENINGS`).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any

SCHEMA_FILE = Path(__file__).with_name("bi_schema_v1_1.json")
#: Every shipped version of the BI schema, oldest first; the first is the base
#: every installed `bi.schema/*` version must stay compatible with.
SHIPPED_FILES = (
    SCHEMA_FILE,
    Path(__file__).with_name("bi_schema_v2.json"),
    Path(__file__).with_name("bi_schema_v3.json"),
)
SCHEMA_ID = "bi.schema/v1.1"
#: Kind changes that keep every stored value meaningful (BI vault V9): a value
#: becomes a one-item list, or an integer a decimal number.
WIDENINGS = frozenset({("enum", "list"), ("str", "list"), ("link", "linklist"), ("int", "float")})
NUMBER_RE = re.compile(r"[-+]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?")
#: Schema ids under this prefix are the shipped BI schemas: only their datasets
#: get the Dashboard and the chat's `bi__query` (owner 2026-10-21).
BI_PREFIX = "bi.schema/"
EMPTY = {"", "nan", "none", "null", "n/a", "na", "-", "—", "tbd", "待定"}
TRUE_SET = {"true", "yes", "y", "1", "是", "有", "t"}
FALSE_SET = {"false", "no", "n", "0", "否", "無", "f"}
SEPARATORS = set(";；、|\n")
OPEN, CLOSE = set("(（"), set(")）")


def widens(old: str, new: str) -> bool:
    """Whether a field may change kind `old` → `new` without breaking (V9)."""
    return (old, new) in WIDENINGS


def widen_value(value: Any, new_kind: str) -> Any:
    """A stored value under the widened kind: one-item list, or float."""
    if value is None:
        return None
    if new_kind in ("list", "linklist"):
        return value if isinstance(value, list) else [value]
    if new_kind == "float" and isinstance(value, int) and not isinstance(value, bool):
        return float(value)
    return value


def norm_key(text: object) -> str:
    """A header or alias compared loosely: no spaces, punctuation or case."""
    return re.sub(r"[\s_\-　()（）:：/／.]", "", str(text)).lower()


@dataclass(frozen=True)
class FieldDef:
    name: str
    label: str
    kind: str
    klass: str
    enum: tuple[str, ...] | None
    aliases: tuple[str, ...]
    required: bool
    default: Any
    range: tuple[float, float] | None
    link_to: tuple[str, ...]
    is_list: bool

    @property
    def is_link(self) -> bool:
        return self.kind in ("link", "linklist")


@dataclass(frozen=True)
class TypeDef:
    name: str
    label: str
    naming: tuple[str, ...]
    domain: str
    has_confidence: bool
    fields: tuple[FieldDef, ...]
    ignored: tuple[dict[str, Any], ...] = field(default=())
    code_key: str = ""

    def get(self, name: str) -> FieldDef | None:
        return next((f for f in self.fields if f.name == name), None)

    @property
    def naming_field(self) -> str:
        return self.naming[-1]


class Registry:
    """One loaded schema document (the shipped one or an installed one)."""

    def __init__(self, document: dict[str, Any], source: str = "shipped") -> None:
        self.document = document
        self.source = source
        self.schema_id = str(document["schema_id"])
        self.version = str(document.get("version") or "")
        self.title = str(document.get("title") or self.schema_id)
        self.domains: tuple[str, ...] = tuple(document.get("domains") or ())
        self.enum_aliases: dict[str, dict[str, str]] = dict(document.get("enum_aliases") or {})
        ignored = document.get("ignored_fields", {})
        types = []
        for raw in document["types"]:
            fields = tuple(
                FieldDef(
                    name=f["name"],
                    label=f["label"],
                    kind=f["kind"],
                    klass=f["class"],
                    enum=tuple(f["enum"]) if f["enum"] else None,
                    aliases=tuple(f["aliases"]),
                    required=bool(f["required"]),
                    default=f["default"],
                    range=tuple(f["range"]) if f["range"] else None,
                    link_to=tuple(f["link_to"]),
                    is_list=bool(f["list"]),
                )
                for f in raw["fields"]
            )
            types.append(
                TypeDef(
                    name=raw["name"],
                    label=raw["label"],
                    naming=tuple(raw["naming"]),
                    domain=raw["domain"],
                    has_confidence=bool(raw["has_confidence"]),
                    fields=fields,
                    ignored=tuple(ignored.get(raw["name"], ())),
                    code_key=str(raw.get("code_key") or ""),
                )
            )
        self.types: dict[str, TypeDef] = {t.name: t for t in types}

    @property
    def ref(self) -> str:
        """`<schema_id>@<version>`, what a dataset is bound to."""
        return f"{self.schema_id}@{self.version}"

    @property
    def is_bi(self) -> bool:
        """A shipped BI schema: its datasets have the Dashboard and `bi__query`."""
        return self.schema_id.startswith(BI_PREFIX)

    def type(self, name: str) -> TypeDef:
        found = self.types.get(name) or next(
            (t for t in self.types.values() if norm_key(t.name) == norm_key(name)), None
        )
        if found is None:
            raise KeyError(name)
        return found

    # -- columns ----------------------------------------------------------

    def map_column(self, entity: TypeDef, header: str) -> tuple[str | None, str, str]:
        """(field, status, note) for one source column header."""
        key = norm_key(header)
        if not key:
            return None, "unknown", "空白欄名"
        for item in entity.fields:
            if norm_key(item.name) == key:
                return item.name, "mapped", ""
        for item in entity.fields:
            if any(norm_key(alias) == key for alias in item.aliases):
                return item.name, "alias", f"別名 → {item.label}（{item.name}）"
        for skipped in entity.ignored:
            names = {norm_key(a) for a in skipped["aliases"]} | {norm_key(skipped["field"])}
            if key in names:
                return None, "ignored", str(skipped["reason"])
        return None, "unknown", "schema 沒有這個欄位，不匯入"

    def type_in_filename(self, filename: str) -> str | None:
        """The type a file is named after (`09_supply_link.csv`, `Node.xlsx`):
        tables keyed by field names (`name,domain,body`) fit many types, so a
        name that says which wins over the headers. The longest match decides."""
        stem = norm_key(Path(str(filename or "")).stem)
        found = [
            (len(key), entity.name)
            for entity in self.types.values()
            for key in {norm_key(entity.name), norm_key(entity.code_key)}
            if key and key in stem
        ]
        return max(found)[1] if found else None

    def guess_type(self, headers: list[str]) -> str | None:
        """The type whose naming field and most columns the headers match."""
        best: tuple[int, str] | None = None
        for entity in self.types.values():
            mapped = [self.map_column(entity, h) for h in headers]
            fields = {f for f, _, _ in mapped if f}
            if entity.naming_field not in fields:
                continue
            # The first column naming the card weighs most (應用名稱, 方案名稱 ...).
            first = mapped[0][0] if mapped else None
            score = len(fields) + (
                5 if first == entity.naming_field and mapped[0][1] == "mapped" else 0
            )
            naming = entity.get(entity.naming_field)
            if (
                headers
                and naming is not None
                and naming.aliases
                and (norm_key(headers[0]) == norm_key(naming.aliases[0]))
            ):
                score += 10
            if best is None or score > best[0]:
                best = (score, entity.name)
        return best[1] if best else None

    # -- values -----------------------------------------------------------

    def normalize(
        self,
        item: FieldDef,
        raw: str,
        extra_aliases: dict[str, dict[str, str]] | None = None,
    ) -> tuple[Any, list[tuple[str, str]]]:
        """(value, warnings). None means empty or not adopted (DQ-9: never a
        silent guess; a lenient reading is a warning and stays empty)."""
        text = str(raw).strip()
        if text.lower() in EMPTY:
            return None, []
        aliases = {
            **self.enum_aliases.get(item.name, {}),
            **(extra_aliases or {}).get(item.name, {}),
        }
        if item.name == "domain":
            items = split_list(text) if item.is_list else [text]
            values, bad = [], []
            for part in items:
                hit = next((d for d in self.domains if d.lower() == part.lower()), None)
                if hit is None:
                    hit = next(
                        (v for a, v in aliases.items() if norm_key(a) == norm_key(part)), None
                    )
                if hit is None:
                    bad.append(part)
                elif hit not in values:
                    values.append(hit)
            warnings = (
                [("domain_unknown", f"領域 {'、'.join(bad)} 不在 {list(self.domains)}，已略過")]
                if bad
                else []
            )
            if item.is_list:
                return (values or None), warnings
            return (values[0] if values else None), warnings
        if item.kind == "list" and item.enum:
            # Allowed values on a list (V9): each part like an enum value; an
            # unknown part is dropped with a warning, never guessed.
            kept, bad = [], []
            for part in split_list(text):
                hit = self._option(item.enum, aliases, part)
                if hit is None:
                    bad.append(part)
                elif hit not in kept:
                    kept.append(hit)
            warnings = (
                [
                    (
                        "type_mismatch",
                        f"{item.label}：{'、'.join(bad)} 不在允許值 {list(item.enum)}，已略過",
                    )
                ]
                if bad
                else []
            )
            return (kept or None), warnings
        if item.kind in ("list", "linklist"):
            parts = split_list(text)
            return (parts or None), []
        if item.kind in ("str", "virtual", "link"):
            return text, []
        if item.kind == "int":
            if re.fullmatch(r"-?\d+", text):
                return self._in_range(item, int(text))
            return None, [("type_mismatch", f"{item.label}：「{text}」不是整數，未採用")]
        if item.kind == "float":
            # Digits with optional thousands separators and an optional trailing
            # %; units, 約 and ranges are not read (the source text keeps them).
            number = text[:-1].rstrip() if text[-1:] in ("%", "％") else text
            if NUMBER_RE.fullmatch(number):
                return self._in_range(item, float(number.replace(",", "")))
            return None, [("type_mismatch", f"{item.label}：「{text}」不是數字，未採用")]
        if item.kind == "bool":
            if text.lower() in TRUE_SET:
                return True, []
            if text.lower() in FALSE_SET:
                return False, []
            return None, [("type_mismatch", f"{item.label}：「{text}」不是是/否，未採用")]
        if item.kind == "date":
            parsed = parse_date(text)
            if parsed is None:
                return None, [("type_mismatch", f"{item.label}：無法解析日期「{text}」")]
            return parsed, []
        if item.kind == "enum":
            assert item.enum is not None
            option = self._option(item.enum, aliases, text)
            if option is not None:
                return option, []
            return None, [
                ("type_mismatch", f"{item.label}：「{text}」不在允許值 {list(item.enum)}")
            ]
        return text, []

    @staticmethod
    def _option(enum: tuple[str, ...], aliases: dict[str, str], text: str) -> str | None:
        for option in enum:
            if text.lower() == option.lower():
                return option
        for alias, option in aliases.items():
            if norm_key(alias) == norm_key(text):
                return option
        return None

    @staticmethod
    def _in_range(item: FieldDef, number: float) -> tuple[Any, list[tuple[str, str]]]:
        if item.range and not item.range[0] <= number <= item.range[1]:
            low, high = item.range
            return None, [("type_mismatch", f"{item.label}：{number:g} 超出 {low:g}–{high:g}")]
        return number, []


def split_list(text: str) -> list[str]:
    """Split on ; ； 、 | newline, never inside (...) or （...）."""
    parts: list[str] = []
    buf: list[str] = []
    depth = 0
    for ch in text:
        if ch in OPEN:
            depth += 1
        elif ch in CLOSE:
            depth = max(0, depth - 1)
        if depth == 0 and ch in SEPARATORS:
            parts.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    parts.append("".join(buf))
    return [p.strip() for p in parts if p.strip()]


def parse_date(text: str) -> str | None:
    """YYYY-MM-DD from ISO, slashes, 年月日 or a ROC year (115/10/13)."""
    s = text.strip()
    match = re.match(r"(\d{4})-(\d{1,2})-(\d{1,2})$", s)
    if not match:
        t = (
            s.replace("年", "-")
            .replace("月", "-")
            .replace("日", "")
            .replace("/", "-")
            .replace(".", "-")
        )
        match = re.fullmatch(r"(\d{4})-?(\d{1,2})-?(\d{1,2})", t) or re.fullmatch(
            r"(?:民國)?(\d{2,3})-(\d{1,2})-(\d{1,2})", t
        )
    if not match:
        return None
    year, month, day = (int(x) for x in match.groups())
    if year < 200:
        year += 1911
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return None


@lru_cache(maxsize=1)
def shipped() -> tuple[Registry, ...]:
    """Every shipped version, oldest first (`SHIPPED_FILES`)."""
    return tuple(Registry(json.loads(p.read_text(encoding="utf-8"))) for p in SHIPPED_FILES)


def registry() -> Registry:
    """The base shipped version, `bi.schema/v1.1@1.1.0`."""
    return shipped()[0]
