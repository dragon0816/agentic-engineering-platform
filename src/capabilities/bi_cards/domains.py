"""Per-domain configuration of a BI dataset or vault (BI vault V10,
`docs/phases/BI_VAULT.md` §12, owner 2026-10-29).

One market vault holds every domain (wireless, AIDC, robotics, …); what
differs per domain is configuration, not schema and not code: its market
segments, its value-chain nodes, its chains (AIDC CMP / PWR / THM are read
from node names, never stored as a field), and the aliases its sources use.
The manager's knowledge bases kept these in `bi_schema.py` constants,
`chain_config.py` and `name-aliases.json`, changed by hand for every new base.

The document (`aep.bi.domains/v1`) is kept in the dataset's `meta` table under
`domains`, so in a vault it travels as a change file like every other write
(a concurrent edit becomes a vault conflict, never a silent overwrite). Every
save bumps `revision`; a save must name the revision it was made from.

When a dataset has domain segments, its coverage matrix is derived from them
(`coverage.matrix_for`); without a configuration nothing changes.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from capabilities.bi_cards.schema import Registry, norm_key
from capabilities.bi_cards.store import BiStore, BiStoreError, now

FORMAT = "aep.bi.domains/v1"
META_KEY = "domains"
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,39}$")
MAX_BYTES = 256 * 1024
MAX_PATTERN = 200
#: A domain's extraction notes (BI vault V11): its own classification rules,
#: added after the fixed evidence rules in every AI extraction of the dataset.
MAX_NOTES = 2000


def _invalid(message: str) -> BiStoreError:
    return BiStoreError("domains_invalid", message)


def _entries(items: Any, what: str, *, required: bool = False) -> list[dict[str, Any]]:
    """`[{"id", "label", "aliases"?, ...}]` with unique ids; extra keys kept."""
    if items is None and not required:
        return []
    if not isinstance(items, list) or (required and not items):
        raise _invalid(f"{what} 必須是{'非空的' if required else ''}清單")
    seen: set[str] = set()
    out = []
    for item in items:
        if not isinstance(item, dict):
            raise _invalid(f"{what} 的每一項都要是物件")
        key = str(item.get("id") or "").strip()
        if not ID_RE.match(key):
            raise _invalid(f"{what} 的 id「{key}」只能用英數字、_ 與 -（最多 40 個字）")
        if key in seen:
            raise _invalid(f"{what} 的 id「{key}」重複")
        seen.add(key)
        aliases = item.get("aliases", [])
        if not isinstance(aliases, list) or not all(isinstance(a, str) for a in aliases):
            raise _invalid(f"{what}「{key}」的 aliases 必須是文字清單")
        out.append({**item, "id": key, "label": str(item.get("label") or key), "aliases": aliases})
    return out


def _names(items: Any, what: str) -> list[str]:
    if items is None:
        return []
    if not isinstance(items, list) or not all(isinstance(x, str) and x.strip() for x in items):
        raise _invalid(f"{what} 必須是名稱清單")
    return [x.strip() for x in items]


def validate(document: Any, reg: Registry) -> dict[str, Any]:
    """The configuration checked against the dataset's schema and normalised;
    raises `domains_invalid` naming what is wrong."""
    if not isinstance(document, dict):
        raise _invalid("設定必須是 JSON 物件")
    if document.get("format") not in (None, FORMAT):
        raise _invalid(f"format 必須是 {FORMAT}")
    unknown = sorted(
        set(document)
        - {
            "format",
            "revision",
            "updated",
            "updated_by",
            "domains",
            "areas",
            "segment_field",
            "area_field",
            "name_aliases",
            "enum_aliases",
            "node_name_pattern",
        }
    )
    if unknown:
        raise _invalid(f"不認得的欄位：{'、'.join(unknown)}")
    domains = _entries(document.get("domains"), "domains", required=True)
    known = {d.lower(): d for d in reg.domains}
    segment_ids: set[str] = set()
    for domain in domains:
        canonical = known.get(domain["id"].lower())
        if canonical is None:
            raise _invalid(
                f"領域「{domain['id']}」不在 schema 的 domains {list(reg.domains)}；"
                "要新增領域請先升級 schema"
            )
        domain["id"] = canonical
        domain["segments"] = _entries(domain.get("segments"), f"領域「{canonical}」的 segments")
        for segment in domain["segments"]:
            if segment["id"] in segment_ids:
                raise _invalid(f"segment「{segment['id']}」出現在兩個領域")
            segment_ids.add(segment["id"])
            segment["priority"] = bool(segment.get("priority"))
        domain["nodes"] = _names(domain.get("nodes"), f"領域「{canonical}」的 nodes")
        notes = domain.get("notes", "")
        if not isinstance(notes, str) or len(notes) > MAX_NOTES:
            raise _invalid(f"領域「{canonical}」的 notes 必須是文字（最多 {MAX_NOTES} 字）")
        domain["notes"] = notes.strip()
        chains = _entries(domain.get("chains"), f"領域「{canonical}」的 chains")
        for chain in chains:
            pattern = chain.get("node_pattern")
            if pattern is not None:
                if not isinstance(pattern, str) or len(pattern) > MAX_PATTERN:
                    raise _invalid(f"鏈「{chain['id']}」的 node_pattern 必須是文字（最多 200 字）")
                try:
                    re.compile(pattern)
                except re.error as error:
                    raise _invalid(
                        f"鏈「{chain['id']}」的 node_pattern 不是有效的規則：{error}"
                    ) from None
            chain["nodes"] = _names(chain.get("nodes"), f"鏈「{chain['id']}」的 nodes")
            if pattern is None and not chain["nodes"]:
                raise _invalid(f"鏈「{chain['id']}」需要 node_pattern 或 nodes")
        domain["chains"] = chains
    areas = _entries(document.get("areas"), "areas")
    if segment_ids and not areas:
        raise _invalid("有 segments 時也要列出 areas（技術領域），覆蓋矩陣才有列")
    name_aliases = document.get("name_aliases", {})
    if not isinstance(name_aliases, dict) or not all(
        isinstance(k, str) and isinstance(v, str) and k.strip() and v.strip()
        for k, v in name_aliases.items()
    ):
        raise _invalid("name_aliases 必須是 {別名: 正式名稱}")
    enum_aliases = document.get("enum_aliases", {})
    if not isinstance(enum_aliases, dict):
        raise _invalid("enum_aliases 必須是 {欄位: {別名: 允許值}}")
    allowed: dict[str, set[str]] = {}
    for entity in reg.types.values():
        for item in entity.fields:
            if item.enum:
                allowed.setdefault(item.name, set()).update(item.enum)
    for field_name, table in enum_aliases.items():
        if field_name not in allowed:
            raise _invalid(f"enum_aliases：schema 沒有叫「{field_name}」的列舉欄位")
        if not isinstance(table, dict):
            raise _invalid(f"enum_aliases.{field_name} 必須是 {{別名: 允許值}}")
        for alias, value in table.items():
            if value not in allowed[field_name]:
                raise _invalid(f"enum_aliases.{field_name}：「{alias}」指向的「{value}」不是允許值")
    node_name_pattern = document.get("node_name_pattern")
    if node_name_pattern is not None:
        if not isinstance(node_name_pattern, str) or len(node_name_pattern) > MAX_PATTERN:
            raise _invalid("node_name_pattern 必須是文字（最多 200 字）")
        try:
            re.compile(node_name_pattern)
        except re.error as error:
            raise _invalid(f"node_name_pattern 不是有效的規則：{error}") from None
    return {
        "format": FORMAT,
        "node_name_pattern": node_name_pattern,
        "domains": domains,
        "areas": areas,
        "segment_field": str(document.get("segment_field") or "segments"),
        "area_field": str(document.get("area_field") or "tech_areas"),
        "name_aliases": {k.strip(): v.strip() for k, v in name_aliases.items()},
        "enum_aliases": enum_aliases,
    }


@dataclass(frozen=True)
class Config:
    """A dataset's saved configuration, read for use."""

    document: dict[str, Any]

    @property
    def revision(self) -> int:
        return int(self.document.get("revision") or 0)

    @property
    def enum_aliases(self) -> dict[str, dict[str, str]]:
        return dict(self.document.get("enum_aliases") or {})

    def canon(self, name: str) -> str:
        """A card name in its canonical spelling (`name_aliases`, loosely)."""
        text = str(name).strip()
        table = {norm_key(k): v for k, v in (self.document.get("name_aliases") or {}).items()}
        return str(table.get(norm_key(text), text))

    def extraction_notes(self) -> str:
        """Every domain's notes, one block each, for the AI extraction prompt."""
        return "\n".join(
            f"- {d['label']}（{d['id']}）：{d['notes']}"
            for d in self.document["domains"]
            if d.get("notes")
        )

    def domain(self, domain_id: str) -> dict[str, Any] | None:
        return next(
            (d for d in self.document["domains"] if d["id"].lower() == str(domain_id).lower()),
            None,
        )

    def chains_of(self, node_name: str, domain_id: str | None = None) -> list[str]:
        """The chains a value-chain node belongs to: listed by name or matched
        by its `node_pattern`. A node may be in several chains (a shared node)."""
        found: list[str] = []
        for domain in self.document["domains"]:
            if domain_id is not None and domain["id"].lower() != domain_id.lower():
                continue
            for chain in domain["chains"]:
                listed = any(norm_key(n) == norm_key(node_name) for n in chain["nodes"])
                pattern = chain.get("node_pattern")
                if (listed or (pattern and re.search(pattern, node_name))) and (
                    chain["id"] not in found
                ):
                    found.append(chain["id"])
        return found

    def matrix(self) -> dict[str, Any] | None:
        """The coverage matrix (`aep.bi.coverage_matrix/v1`) the domains define:
        one market per domain with segments; None when none has segments."""
        markets = [
            {"id": d["id"], "label": d["label"], "segments": d["segments"]}
            for d in self.document["domains"]
            if d["segments"]
        ]
        if not markets:
            return None
        return {
            "format": "aep.bi.coverage_matrix/v1",
            "title": "領域設定",
            "segment_field": self.document["segment_field"],
            "area_field": self.document["area_field"],
            "markets": markets,
            "areas": self.document["areas"],
        }


def read(store: BiStore) -> Config | None:
    """The dataset's configuration; None when it has none (or no database)."""
    text = store.meta_value(META_KEY)
    if not text:
        return None
    try:
        document = json.loads(text)
    except ValueError:
        return None
    return Config(document) if isinstance(document, dict) else None


def warnings(config: Config, reg: Registry) -> list[dict[str, str]]:
    """What the configuration names that the schema cannot hold yet: a
    segment or area the placing field does not allow, or a placing field no
    type has. Saved anyway; the coverage matrix reports such cards unplaced."""
    found: list[dict[str, str]] = []
    for key, entries in (
        ("segment_field", [s for d in config.document["domains"] for s in d["segments"]]),
        ("area_field", config.document["areas"]),
    ):
        name = config.document[key]
        fields = [t.get(name) for t in reg.types.values() if t.get(name) is not None]
        if entries and not fields:
            found.append(
                {"code": "field_missing", "message": f"schema 沒有欄位 {name}，卡片無法放進矩陣"}
            )
            continue
        allowed = {v for f in fields if f is not None and f.enum for v in f.enum}
        if not allowed:
            continue
        for entry in entries:
            if entry["id"] not in allowed:
                found.append(
                    {
                        "code": "value_not_allowed",
                        "message": f"「{entry['id']}」不在欄位 {name} 的允許值；"
                        "先用 Session A 在 schema 新增，卡片才能放進這一格",
                    }
                )
    return found


def describe(store: BiStore, reg: Registry | None = None) -> dict[str, Any]:
    found = read(store)
    return {
        "dataset": store.dataset,
        "configured": found is not None,
        "revision": found.revision if found is not None else 0,
        "config": found.document if found is not None else None,
        "warnings": warnings(found, reg) if found is not None and reg is not None else [],
    }


def save(store: BiStore, reg: Registry, document: Any, base: Any, actor: str) -> dict[str, Any]:
    """Validate and save; `base` is the revision it was made from (0 for the
    first), else 409 `domains_stale`."""
    store.refuse_write()
    if not store.exists:
        raise BiStoreError("dataset_unknown", f"沒有這個資料集「{store.dataset}」")
    if not isinstance(base, int) or isinstance(base, bool):
        raise BiStoreError("base_revision_missing", "需要 base_revision（第一次儲存是 0）")
    if len(json.dumps(document, ensure_ascii=False).encode("utf-8")) > MAX_BYTES:
        raise _invalid("設定太大（上限 256 KB）")
    normalised = validate(document, reg)
    current = read(store)
    revision = current.revision if current is not None else 0
    if base != revision:
        raise BiStoreError("domains_stale", f"領域設定已被改到第 {revision} 版，請重新讀取後再改")
    normalised.update({"revision": revision + 1, "updated": now(), "updated_by": actor})
    text = json.dumps(normalised, ensure_ascii=False, sort_keys=True)
    store.set_meta_value(
        META_KEY, text, base=None if current is None else store.meta_value(META_KEY)
    )
    return describe(store, reg)
