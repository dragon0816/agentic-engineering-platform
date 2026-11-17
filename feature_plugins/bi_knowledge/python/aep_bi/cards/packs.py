"""Analysis packs: a vault's analyses as one file (`aep.bi.analysis_pack/v1`, BI P2).

`docs/phases/BI_ANALYSIS_DASHBOARD.md` §4.2. A pack is `{"format", "id",
"title", "version", "analyses": [<analysis unit values with slug>]}` (and an
optional `report`). AEP ships one pack, `bi-market-default`: every section of
the coded Dashboard (`dashboard.py` §1–§19, `market.py` §20–§31) moved into a
guarded script under `pack_default/` (the shared `_prelude.py` before each), so a
vault's Dashboard is its analyses. The chain sections (A–A3) read Node `chain`
and the coverage matrix reads `segment` x `tech_areas` (schema 3.0.0, D1–D3);
the schema's allowed values and their labels are filled into those scripts on
import (`SCHEMA_VALUES`), like the link fields (`LINK_FIELDS`).

Importing a pack stages the analyses the vault's schema satisfies (`requires`)
and lists the rest; exporting writes the vault's analyses as a pack another
vault (another project) can import.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from functools import cache
from pathlib import Path
from typing import Any

from aep_bi.cards import analyses
from aep_bi.cards.store import BiStoreError

FORMAT = "aep.bi.analysis_pack/v1"
DEFAULT_ID = "bi-market-default"
DEFAULT_VERSION = "1.0.0"
SOURCE = Path(__file__).with_name("pack_default")
MAX_ANALYSES = 200
LINK_LINE = re.compile(r"^LINK_FIELDS: dict\[str, dict\[str, list\[str\]\]\] = \{.*\}.*$", re.M)
VALUES_LINE = re.compile(r"^SCHEMA_VALUES: dict\[str, Any\] = \{.*\}.*$", re.M)
#: Fields whose allowed values (with labels and aliases) a script may read.
ALLOWED_FIELDS = ("chain", "segment", "tech_areas")

DOMAIN = {"type": "enum", "values_from": "Application.domain", "default": "robotics",
          "label": "領域"}  # fmt: skip
SAMPLE = {"type": "bool", "default": False, "label": "含範例卡（SAMPLE-）"}
TODAY = {"type": "date", "default": "today", "label": "今天"}

#: (slug, source file, title, question, chart, types required, takes `today`).
#: In the Dashboard's order: the chains A–A3 first (as in the manager's
#: dashboards), §1–§19 as the page showed them, §20–§31, then the coverage matrix.
SECTIONS: tuple[tuple[str, str, str, str, dict[str, Any], tuple[str, ...], bool], ...] = (
    ("chain-summary", "chain_summary", "A. 分鏈總表",
     "各條鏈有多少節點、公司、產品與供貨證據？", {"type": "table"}, ("Node",), False),
    ("chain-view", "chain_view", "A2. 分鏈視圖：節點 × Ecosystem × 客戶產品 × 趨勢",
     "每條鏈的節點缺 Ecosystem 或趨勢嗎？", {"type": "table"}, ("Node",), False),
    ("chain-overlap", "chain_overlap", "A3. 跨鏈檢查（只列共用節點與共用公司）",
     "哪些節點與公司橫跨兩條以上的鏈？", {"type": "table"}, ("Node",), False),
    ("gaps", "gaps", "6. 缺口：Application × 我方方案 / 對手方案",
     "哪些應用我方沒有方案、對手卻有？", {"type": "table"}, ("Application", "TestSolution"), False),
    ("trend-coverage", "trend_coverage", "10. 趨勢 → 應用 → 方案 覆蓋檢查",
     "哪些趨勢沒有對應的應用或我方方案？", {"type": "table"},
     ("Trend", "Application", "TestSolution"), False),
    ("demand-without-opportunity", "demand_without_opportunity",
     "19. 有客戶產品需求、但沒有商機的 Application", "哪些應用有需求卻沒有商機？",
     {"type": "table"}, ("Application", "CustomerProduct", "Opportunity"), False),
    ("solutions-vs-opportunities", "solutions_vs_opportunities", "18. 我方方案 × 進行中商機",
     "哪些我方方案沒有進行中的商機？", {"type": "table"}, ("TestSolution", "Opportunity"), False),
    ("funnel", "funnel", "17. 商機漏斗（依階段）", "各階段有幾筆商機？",
     {"type": "bar", "x": "階段", "y": "筆數"}, ("Opportunity",), False),
    ("technologies-without-concept", "technologies_without_concept",
     "14. 缺少 Concept 解釋的 Technology", "哪些技術還沒有（已審閱的）Concept？",
     {"type": "table"}, ("Technology", "Concept"), False),
    ("product-completeness", "product_completeness",
     "16. 客戶產品 × 生態系 × 趨勢 掛勾總表（含資料完整度）",
     "客戶產品的節點、技術、生態系齊了嗎？",
     {"type": "table"}, ("CustomerProduct", "Trend"), False),
    ("trend-priority", "trend_priority", "1. 趨勢優先度（量測影響 × 我方契合度）",
     "哪些趨勢最值得投入？", {"type": "table"}, ("Trend",), False),
    ("launch-timeline", "launch_timeline", "2. 客戶產品上市時程", "客戶產品什麼時候上市？",
     {"type": "table"}, ("CustomerProduct",), False),
    ("node-technology", "node_technology", "4. 節點 × 技術 矩陣（客戶產品數）",
     "各節點用到哪些技術？", {"type": "table"}, ("Node", "Technology", "CustomerProduct"), False),
    ("recent-signals", "recent_signals", "5. 近期訊號", "最近有哪些訊號？", {"type": "table"},
     ("Signal",), False),
    ("competitor-coverage", "competitor_coverage",
     "6b. 競品覆蓋矩陣（每格 = 該廠商在此應用的方案數）", "各廠商在每個應用有幾個方案？",
     {"type": "table"},
     ("Application", "TestSolution", "Competitor"), False),
    ("assumed-share", "assumed_share", "7. 推測內容比例（待驗證）", "多少內容還是推測？",
     {"type": "bar", "x": "信心度", "y": "筆數"}, (), False),
    ("stale", "stale", "8. 資料過期提醒（超過 90 天未更新）", "哪些卡超過 90 天沒更新？",
     {"type": "table"}, (), True),
    ("supplier-dependency", "supplier_dependency", "12. 供應商依賴排行", "最多人依賴哪些供應商？",
     {"type": "table"}, ("Account", "CustomerProduct"), False),
    ("trend-links", "trend_links", "20. 趨勢 × 生態系 × 客戶產品 三方掛勾檢查",
     "哪些趨勢缺生態系或客戶產品？", {"type": "table"},
     ("Trend", "Ecosystem", "CustomerProduct"), False),
    ("win-loss", "win_loss", "21. Win-Loss 原因統計（依對手）", "輸給各對手的主因是什麼？",
     {"type": "table"}, ("WinLoss", "Opportunity"), False),
    ("roadmap-gaps", "roadmap_gaps", "22. Roadmap Request 缺口排行", "哪些產品需求最該先做？",
     {"type": "table"}, ("RoadmapRequest",), False),
    ("enablement", "enablement",
     "23. Sales Enablement 覆蓋（對手 Battlecard / 我方方案 Pitch 與 Demo）",
     "哪些對手沒有 Battlecard、哪些方案缺 Pitch 或 Demo？", {"type": "table"},
     ("Battlecard", "Pitch", "DemoScript", "Competitor", "TestSolution"), False),
    ("customer-contact", "customer_contact", "24. 客戶接觸：進行中商機的最近拜訪與逾期跟進",
     "哪些進行中商機很久沒拜訪、哪些跟進逾期？", {"type": "table"},
     ("VisitLog", "Opportunity"), True),
    ("supply-evidence", "supply_evidence", "25. 客戶產品 × 生態系 × 趨勢（以供貨證據為準）",
     "客戶產品的供應商與趨勢有證據嗎？", {"type": "table"},
     ("SupplyLink", "CustomerProduct", "Trend"), False),
    ("timing-gaps", "timing_gaps",
     "26. 時程缺口：趨勢需求早於產品上市、但我方方案尚未 available",
     "哪些產品上市時需求已到、我方方案卻還沒好？", {"type": "table"},
     ("CustomerProduct", "Trend", "TestSolution"), True),
    ("supply-grades", "supply_grades", "27. 供貨證據等級分布（SupplyLink）",
     "供貨證據各等級有多少？", {"type": "table"}, ("SupplyLink",), False),
    ("revenue-layers", "revenue_layers", "28. 收入事實三層完整度（RevenueFact）",
     "各公司的收入事實三層齊了嗎？", {"type": "table"}, ("RevenueFact", "Account"), False),
    ("chain-integrity", "chain_integrity",
     "29. 鏈路完整性：Application → 我方方案 → Opportunity（含競品連結）",
     "方案與商機的連結哪裡斷了？", {"type": "table"},
     ("Opportunity", "TestSolution", "Competitor"), False),
    ("same-names", "same_names", "30. 同名卡衝突（同一個名字出現在不同類型）",
     "哪些名字在不同類型重複？", {"type": "table"}, (), False),
    ("pending-links", "pending_links", "31. 待補的連結目標（後補清單）",
     "哪些連結指向還沒建立的卡？", {"type": "table"}, (), False),
    ("coverage", "coverage", "覆蓋矩陣：市場區段 × 技術領域",
     "每個區段 × 技術領域有幾張卡、來源齊不齊？", {"type": "table"}, (), False),
)  # fmt: skip
#: Fields an analysis reads beyond its types (`requires.fields`).
FIELDS: dict[str, tuple[str, ...]] = {
    "chain-summary": ("Node.chain",),
    "chain-view": ("Node.chain",),
    "chain-overlap": ("Node.chain",),
    "coverage": ("CustomerProduct.segment", "CustomerProduct.tech_areas"),
}
#: Analyses over every card, not one domain's (no `domain`, no `include_sample`).
UNSCOPED = ("coverage",)

#: Sections of the coded Dashboard not in the pack, and why (design §4.3: none
#: is dropped silently).
KEPT = (
    {"section": "Q", "name": "quality",
     "reason": "品質檢查留在它自己的檢查（/api/bi/quality），不是分析"},
)  # fmt: skip


@cache
def _prelude() -> str:
    return (SOURCE / "_prelude.py").read_text(encoding="utf-8")


def section_code(source: str) -> str:
    """One section's script: the prelude, then the section."""
    return _prelude() + "\n\n" + (SOURCE / f"{source}.py").read_text(encoding="utf-8")


def default_pack() -> dict[str, Any]:
    found = []
    for slug, source, title, question, chart, types, dated in SECTIONS:
        params: dict[str, Any] = {}
        if slug not in UNSCOPED:
            params = {"domain": dict(DOMAIN), "include_sample": dict(SAMPLE)}
        if dated:
            params["today"] = dict(TODAY)
        found.append(
            {
                "slug": slug,
                "title": title,
                "question": question,
                "kind": "python",
                "code": section_code(source),
                "chart": dict(chart),
                "params": params,
                "requires": {"types": list(types), "fields": list(FIELDS.get(slug, ()))},
            }
        )
    return {
        "format": FORMAT,
        "id": DEFAULT_ID,
        "title": "BI 市場分析（預設）",
        "version": DEFAULT_VERSION,
        "analyses": found,
        "report": {"kept": [dict(k) for k in KEPT]},
    }


def checked_pack(pack: Any) -> list[tuple[str, dict[str, Any]]]:
    """The pack's analyses as (unit key, value), each checked; refused whole when one is wrong."""
    if not isinstance(pack, dict) or pack.get("format") != FORMAT:
        raise BiStoreError("pack_invalid", f"分析包的 format 必須是 {FORMAT}")
    items = pack.get("analyses")
    if not isinstance(items, list) or not items or len(items) > MAX_ANALYSES:
        raise BiStoreError("pack_invalid", f"分析包要有 1 到 {MAX_ANALYSES} 個分析")
    found = []
    for item in items:
        if not isinstance(item, dict):
            raise BiStoreError("pack_invalid", "分析包裡的每個分析都必須是物件")
        try:
            found.append(analyses.checked(item))
        except BiStoreError as failure:
            raise BiStoreError(
                "pack_invalid", f"分析「{item.get('slug')}」：{failure.message}"
            ) from None
    keys = [k for k, _ in found]
    if len(set(keys)) != len(keys):
        raise BiStoreError("pack_invalid", "分析包裡有重複的代號")
    return found


def link_fields(registry: Any | None) -> dict[str, dict[str, list[str]]]:
    if registry is None:
        return {}
    return {
        name: {f.name: list(f.link_to) for f in entity.fields if f.is_link}
        for name, entity in registry.types.items()
    }


def schema_values(registry: Any | None) -> dict[str, Any]:
    """What a pack script may read of the schema: the allowed values of
    `ALLOWED_FIELDS` in the schema's order, each `[value, label, *aliases]` (the
    label is the value's first alias, else the value), and each type's own
    (not derived) field names."""
    if registry is None:
        return {"allowed": {}, "fields": {}}
    allowed: dict[str, list[list[str]]] = {}
    for name in ALLOWED_FIELDS:
        values: list[str] = []
        for entity in registry.types.values():
            item = entity.get(name)
            for value in (item.enum or ()) if item is not None else ():
                if value not in values:
                    values.append(value)
        table = registry.enum_aliases.get(name, {})
        for value in values:
            aliases = [a for a, v in table.items() if v == value]
            allowed.setdefault(name, []).append([value, aliases[0] if aliases else value, *aliases])
    fields = {
        n: [f.name for f in t.fields if f.klass != "derived"] for n, t in registry.types.items()
    }
    return {"allowed": allowed, "fields": fields}


def fill(code: str, registry: Any | None) -> str:
    """A pack script with its `LINK_FIELDS` (and `SCHEMA_VALUES`) line set from this schema."""
    links = "LINK_FIELDS: dict[str, dict[str, list[str]]] = " + json.dumps(
        link_fields(registry), ensure_ascii=False, sort_keys=True
    )
    code = LINK_LINE.sub(lambda _m: links, code, count=1)
    if VALUES_LINE.search(code):
        values = "SCHEMA_VALUES: dict[str, Any] = " + json.dumps(
            schema_values(registry), ensure_ascii=False, sort_keys=True
        )
        code = VALUES_LINE.sub(lambda _m: values, code, count=1)
    return code


def offer(registry: Any | None, pack: Mapping[str, Any]) -> dict[str, Any]:
    """Which of the pack's analyses this schema satisfies, and which not (with why)."""
    usable, skipped = [], []
    for key, value in checked_pack(pack):
        slug = key[len(analyses.PREFIX) :]
        if analyses.requires_met(value.get("requires"), registry):
            usable.append(slug)
        else:
            needs = value.get("requires") or {}
            missing = [
                t for t in needs.get("types") or [] if registry is None or t not in registry.types
            ] + [
                f
                for f in needs.get("fields") or []
                if not analyses.requires_met({"fields": [f]}, registry)
            ]
            skipped.append({"slug": slug, "title": value["title"], "missing": missing})
    return {"usable": usable, "skipped": skipped}


def stage_pack(target: Any, registry: Any | None, pack: Mapping[str, Any]) -> dict[str, Any]:
    """Stage what the schema satisfies into `target` (a `vault.Vault`, locked by the
    caller); a vault without a Dashboard order takes the pack's order."""
    offered = offer(registry, pack)
    usable = set(offered["usable"])
    changes: dict[str, Any] = {}
    for key, value in checked_pack(pack):
        if key[len(analyses.PREFIX) :] in usable:
            changes[key] = {**value, "code": fill(value["code"], registry)}
    units = target.repo.working_units()
    if analyses.DASHBOARD_UNIT not in units and offered["usable"]:
        layout = {"order": offered["usable"], "hidden": []}
        changes[analyses.DASHBOARD_UNIT] = json.dumps(layout, ensure_ascii=False)
    if changes:
        target.repo.stage_many(dict(sorted(changes.items())))
    return {"staged": offered["usable"], "skipped": offered["skipped"]}


def import_pack(workspace: Path, vault_id: str, pack: Any) -> dict[str, Any]:
    """Stage a pack's analyses into a vault (uncommitted, like any change)."""
    from aep_bi.cards import vault

    if pack == DEFAULT_ID:
        pack = default_pack()
    target = vault._vault(workspace, vault_id)
    with target.lock, vault._repo_errors():
        done = stage_pack(target, target._registry(), pack)
    return {**done, **analyses.listing(workspace, vault_id)}


def export_pack(workspace: Path, vault_id: str, given: Mapping[str, Any]) -> dict[str, Any]:
    """The vault's working analyses as a pack (in the Dashboard's order)."""
    from aep_bi.cards import vault

    units = vault.Vault(workspace, vault_id).repo.working_units()
    saved = {a["slug"]: a for a in analyses.saved(units)}
    if not saved:
        raise BiStoreError("pack_empty", "這個知識庫還沒有分析")
    ordered = analyses.order(units, list(saved))
    slugs = ordered + sorted(s for s in saved if s not in ordered)
    pack_id = str(given.get("id") or f"{vault_id}-analyses").strip()
    if not analyses.NAME_RE.match(pack_id):
        raise BiStoreError("pack_invalid", "分析包代號只能用小寫英數字與 -")
    return {
        "format": FORMAT,
        "id": pack_id,
        "title": str(given.get("title") or f"{vault_id} 的分析").strip()[:200],
        "version": str(given.get("version") or "1.0.0").strip()[:40],
        "analyses": [
            {"slug": s, **{k: v for k, v in saved[s].items() if k not in ("unit", "slug")}}
            for s in slugs
        ],
    }


def summary(workspace: Path, vault_id: str) -> dict[str, Any]:
    """The built-in pack and what this vault's schema can use of it."""
    from aep_bi.cards import vault

    pack = default_pack()
    registry = vault.Vault(workspace, vault_id)._registry()
    return {
        "packs": [
            {
                "id": pack["id"],
                "title": pack["title"],
                "version": pack["version"],
                "analyses": len(pack["analyses"]),
                **offer(registry, pack),
                "kept": pack["report"]["kept"],
            }
        ]
    }
