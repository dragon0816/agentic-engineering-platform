"""The BI dashboard, computed in Python from the store.

Follows the robotics sample's `Dashboard-Robotics.md` (Dataview queries),
section by section, for one domain. A card without `domain` counts as
wireless (v4). Trend priority is computed (measurement_impact x our_fit) for
display and never stored; Application priority is not shown at all (#222:
the Skill judges it from the facts).

BI vault V12: the manager's later sections (§20–§31, the chains A–A3) come
from `market.py` when the dataset's schema has their types; cards named
`SAMPLE-…` are left out unless `include_sample` (his dashboards' switch).
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any

from capabilities.bi_cards.store import BiStore

MINE = "R&S(我方)"
#: The manager names fictional demonstration cards `SAMPLE-…`.
SAMPLE_PREFIX = "SAMPLE-"
STALE_DAYS = 90
DEAL_STAGES = ("lead", "qualified", "proposal", "eval", "negotiation", "won", "lost")
CLOSED = ("won", "lost")


class Card(dict[str, Any]):
    """One card's values plus `_name`, `_id`, `_type`, `_updated`."""


def _list(value: Any) -> list[Any]:
    if value is None:
        return []
    return list(value) if isinstance(value, list) else [value]


def _in(card: Card, domain: str) -> bool:
    values = _list(card.get("domain") or "wireless")
    return domain.lower() in {str(v).lower() for v in values}


def _cards(store: BiStore, include_sample: bool = True) -> dict[str, list[Card]]:
    everything = store.all_fields()
    result: dict[str, list[Card]] = {}
    for row in store.card_rows():
        if not include_sample and str(row["name"]).startswith(SAMPLE_PREFIX):
            continue
        card = Card({k: v["value"] for k, v in everything.get(row["id"], {}).items()})
        card["_name"] = row["canonical_key"] if row["entity_type"] == "Signal" else row["name"]
        card["_key"] = row["canonical_key"]
        card["_id"] = row["id"]
        card["_type"] = row["entity_type"]
        card["_updated"] = row["updated"]
        result.setdefault(row["entity_type"], []).append(card)
    return result


def _ref(card: Card) -> dict[str, str]:
    """A cell naming a card: the page links it to the card."""
    return {
        "card_id": card["_id"],
        "label": card["_name"],
        "cite": f"{card['_type']}:{card['_key']}",
    }


def _prio(trend: Card) -> int:
    return int(trend.get("measurement_impact") or 0) * int(trend.get("our_fit") or 0)


def _covers(solution: Card, app: Card) -> bool:
    return app["_key"] in _list(solution.get("applications"))


def _section(
    sid: str,
    title: str,
    columns: list[str],
    rows: list[list[Any]],
    *,
    kind: str = "table",
    flags: list[dict[str, Any]] | None = None,
    note: str = "",
) -> dict[str, Any]:
    return {
        "id": sid,
        "title": f"{sid}. {title}",
        "kind": kind,
        "columns": columns,
        "rows": rows,
        "flags": flags or [],
        "note": note,
    }


def _join(value: Any) -> str:
    return "、".join(str(v) for v in _list(value))


def gaps(c: dict[str, list[Card]], d: str) -> dict[str, Any]:
    sols = c.get("TestSolution", [])
    rows: list[list[Any]] = []
    flags: list[dict[str, Any]] = []
    for app in sorted((a for a in c.get("Application", []) if _in(a, d)), key=lambda a: a["_name"]):
        mine = sum(1 for s in sols if not s.get("vendor") and _covers(s, app))
        theirs = sum(1 for s in sols if s.get("vendor") and _covers(s, app))
        status = "OK" if mine else ("對手有、我方無" if theirs else "全無")
        if not mine:
            flags.append({"row": len(rows), "level": "red" if theirs else "warn", "text": status})
        rows.append([_ref(app), app.get("lifecycle") or "", mine, theirs, status])
    return _section(
        "6",
        "缺口：Application × 我方方案 / 對手方案",
        ["應用", "階段", "我方方案", "對手方案", "狀態"],
        rows,
        flags=flags,
        note="我方方案 = TestSolution 的 vendor 空白。優先度不存資料，由 Skill 依事實判斷。",
    )


def trend_coverage(c: dict[str, list[Card]], d: str) -> dict[str, Any]:
    apps = [a for a in c.get("Application", []) if _in(a, d)]
    sols = [s for s in c.get("TestSolution", []) if not s.get("vendor")]
    trends = sorted((t for t in c.get("Trend", []) if _in(t, d)), key=lambda t: -_prio(t))
    rows: list[list[Any]] = []
    flags: list[dict[str, Any]] = []
    for trend in trends:
        linked = [a for a in apps if trend["_key"] in _list(a.get("trends"))]
        covering = [s for s in sols if any(_covers(s, a) for a in linked)]
        status = "無對應 Application" if not linked else ("無對應方案" if not covering else "OK")
        if status != "OK":
            flags.append({"row": len(rows), "level": "warn", "text": status})
        rows.append(
            [
                _ref(trend),
                _prio(trend),
                trend.get("stage") or "",
                len(linked),
                len(covering),
                status,
            ]
        )
    return _section(
        "10",
        "趨勢 → 應用 → 方案 覆蓋檢查",
        ["趨勢", "優先度（計算）", "階段", "Application 數", "我方方案數", "狀態"],
        rows,
        flags=flags,
        note="優先度 = 量測影響 × 我方契合度，即時計算，不儲存。",
    )


def demand_without_opportunity(c: dict[str, list[Card]], d: str) -> dict[str, Any]:
    cps = [x for x in c.get("CustomerProduct", []) if _in(x, d)]
    opps = [x for x in c.get("Opportunity", []) if _in(x, d)]
    rows: list[list[Any]] = []
    flags: list[dict[str, Any]] = []
    for app in sorted((a for a in c.get("Application", []) if _in(a, d)), key=lambda a: a["_name"]):
        demand = sum(1 for x in cps if app["_key"] in _list(x.get("inferred_applications")))
        if not demand:
            continue
        count = sum(1 for x in opps if app["_key"] in _list(x.get("applications")))
        status = "OK" if count else "有需求無商機"
        if not count:
            flags.append({"row": len(rows), "level": "warn", "text": status})
        rows.append([_ref(app), demand, count, status])
    return _section(
        "19",
        "有客戶產品需求、但沒有商機的 Application",
        ["應用", "客戶產品需求數", "商機數", "檢查"],
        rows,
        flags=flags,
    )


def solutions_vs_opportunities(c: dict[str, list[Card]], d: str) -> dict[str, Any]:
    opps = [o for o in c.get("Opportunity", []) if _in(o, d) and o.get("deal_stage") not in CLOSED]
    rows: list[list[Any]] = []
    flags: list[dict[str, Any]] = []
    mine = (s for s in c.get("TestSolution", []) if not s.get("vendor") and _in(s, d))
    for sol in sorted(mine, key=lambda s: s["_name"]):
        count = sum(1 for o in opps if sol["_key"] in _list(o.get("our_solutions")))
        status = "OK" if count else "無進行中商機"
        if not count:
            flags.append({"row": len(rows), "level": "warn", "text": status})
        rows.append([_ref(sol), sol.get("status") or "", count, status])
    return _section(
        "18",
        "我方方案 × 進行中商機",
        ["我方方案", "狀態", "進行中商機", "檢查"],
        rows,
        flags=flags,
        note="進行中 = deal_stage 不是 won / lost。",
    )


def funnel(c: dict[str, list[Card]], d: str) -> dict[str, Any]:
    opps = [o for o in c.get("Opportunity", []) if _in(o, d)]
    rows = []
    for stage in DEAL_STAGES:
        names = sorted(o["_name"] for o in opps if o.get("deal_stage") == stage)
        rows.append([stage, len(names), "、".join(names)])
    return _section("17", "商機漏斗（依階段）", ["階段", "筆數", "商機"], rows, kind="funnel")


def technologies_without_concept(c: dict[str, list[Card]], d: str) -> dict[str, Any]:
    concepts = c.get("Concept", [])
    rows: list[list[Any]] = []
    flags: list[dict[str, Any]] = []
    for tech in sorted((t for t in c.get("Technology", []) if _in(t, d)), key=lambda t: t["_name"]):
        linked = [x for x in concepts if tech["_key"] in _list(x.get("technologies"))]
        reviewed = sum(1 for x in linked if x.get("review_status") == "reviewed")
        status = "缺 Concept" if not linked else ("尚無已審閱" if not reviewed else "OK")
        if status != "OK":
            flags.append({"row": len(rows), "level": "warn", "text": status})
        rows.append([_ref(tech), len(linked), reviewed, status])
    return _section(
        "14",
        "缺少 Concept 解釋的 Technology",
        ["技術", "Concept 數", "已審閱", "狀態"],
        rows,
        flags=flags,
    )


def _nodes_of(card: Card) -> set[str]:
    found = {str(n) for n in _list(card.get("nodes"))}
    if card.get("node"):
        found.add(str(card["node"]))
    return found


def product_completeness(c: dict[str, list[Card]], d: str) -> dict[str, Any]:
    trends = [t for t in c.get("Trend", []) if _in(t, d)]
    cps = sorted(
        (x for x in c.get("CustomerProduct", []) if _in(x, d)),
        key=lambda x: str(x.get("launch_date") or "9999"),
    )
    rows: list[list[Any]] = []
    flags: list[dict[str, Any]] = []
    for cp in cps:
        nodes, techs = _nodes_of(cp), {str(t) for t in _list(cp.get("technologies"))}
        hit = sorted(
            (
                t
                for t in trends
                if techs & {str(x) for x in _list(t.get("related_tech"))}
                or nodes & {str(x) for x in _list(t.get("affected_nodes"))}
            ),
            key=lambda t: -_prio(t),
        )
        missing = [
            label
            for label, empty in (
                ("節點", not nodes),
                ("技術", not techs),
                ("生態系", not _list(cp.get("ecosystem"))),
            )
            if empty
        ]
        status = "缺 " + "、".join(missing) if missing else "OK"
        if missing:
            flags.append({"row": len(rows), "level": "warn", "text": status})
        rows.append(
            [
                _ref(cp),
                cp.get("account") or "",
                cp.get("launch_date") or cp.get("launch_window") or "",
                len(_list(cp.get("ecosystem"))),
                len(hit),
                hit[0]["_name"] if hit else "-",
                status,
            ]
        )
    return _section(
        "16",
        "客戶產品 × 生態系 × 趨勢 掛勾總表（含資料完整度）",
        ["客戶產品", "客戶", "上市", "生態系成員數", "相關趨勢數", "最高優先趨勢", "資料完整度"],
        rows,
        flags=flags,
        note="趨勢由技術、節點與 Trend 的相關技術、影響節點交集推得。",
    )


def trend_priority(c: dict[str, list[Card]], d: str) -> dict[str, Any]:
    trends = sorted(
        (t for t in c.get("Trend", []) if _in(t, d) and t.get("stage") != "fading"),
        key=lambda t: -_prio(t),
    )
    rows = [
        [
            _ref(t),
            t.get("stage") or "",
            t.get("time_to_demand") or "",
            t.get("measurement_impact"),
            t.get("our_fit"),
            _prio(t),
        ]
        for t in trends
    ]
    return _section(
        "1",
        "趨勢優先度（量測影響 × 我方契合度）",
        ["趨勢", "階段", "需求時間", "量測影響", "我方契合度", "優先度（計算）"],
        rows,
        note="優先度即時計算，不儲存；量測影響與契合度是卡片上的事實欄位。",
    )


def launch_timeline(c: dict[str, list[Card]], d: str) -> dict[str, Any]:
    cps = sorted(
        (x for x in c.get("CustomerProduct", []) if _in(x, d)),
        key=lambda x: str(x.get("launch_date") or "9999"),
    )
    rows = [
        [
            _ref(x),
            x.get("account") or "",
            x.get("node") or "",
            _join(x.get("technologies")),
            x.get("launch_date") or "",
            x.get("launch_window") or "",
            x.get("test_stage_now") or "",
        ]
        for x in cps
    ]
    return _section(
        "2",
        "客戶產品上市時程",
        ["客戶產品", "客戶", "節點", "技術", "上市日", "上市時程", "目前階段"],
        rows,
    )


def node_technology(c: dict[str, list[Card]], d: str) -> dict[str, Any]:
    nodes = sorted(
        (n for n in c.get("Node", []) if _in(n, d) or n.get("layer") == "X"),
        key=lambda n: n["_name"],
    )
    techs = sorted((t for t in c.get("Technology", []) if _in(t, d)), key=lambda t: t["_name"])
    cps = [x for x in c.get("CustomerProduct", []) if _in(x, d)]
    rows = [
        [
            _ref(n),
            *[
                sum(
                    1
                    for cp in cps
                    if n["_key"] in _nodes_of(cp) and t["_key"] in _list(cp.get("technologies"))
                )
                for t in techs
            ],
        ]
        for n in nodes
    ]
    return _section(
        "4",
        "節點 × 技術 矩陣（客戶產品數）",
        ["節點", *[t["_name"] for t in techs]],
        rows,
        kind="matrix",
    )


def recent_signals(c: dict[str, list[Card]], d: str) -> dict[str, Any]:
    signals = sorted(
        (s for s in c.get("Signal", []) if _in(s, d)),
        key=lambda s: str(s.get("date") or ""),
        reverse=True,
    )[:10]
    rows = [
        [
            s.get("date") or "",
            {"card_id": s["_id"], "label": s.get("title") or s["_name"]},
            s.get("summary") or "",
            s.get("so_what") or "",
            s.get("reliability") or "",
        ]
        for s in signals
    ]
    return _section("5", "近期訊號", ["日期", "主題", "摘要", "所以呢", "可靠度"], rows)


def competitor_coverage(c: dict[str, list[Card]], d: str) -> dict[str, Any]:
    sols = c.get("TestSolution", [])
    vendors = [MINE, *sorted(x["_name"] for x in c.get("Competitor", []) if _in(x, d))]
    apps = sorted((a for a in c.get("Application", []) if _in(a, d)), key=lambda a: a["_name"])

    def vendor(solution: Card) -> str:
        return str(solution.get("vendor") or MINE)

    rows = [
        [_ref(a), *[sum(1 for s in sols if vendor(s) == v and _covers(s, a)) for v in vendors]]
        for a in apps
    ]
    return _section(
        "6b",
        "競品覆蓋矩陣（每格 = 該廠商在此應用的方案數）",
        ["應用", *vendors],
        rows,
        kind="matrix",
    )


def assumed_share(c: dict[str, list[Card]], d: str) -> dict[str, Any]:
    counts = {"verified": 0, "assumed": 0, "（沒有信心度欄位）": 0}
    for cards in c.values():
        for card in cards:
            if not _in(card, d):
                continue
            counts[str(card.get("confidence") or "（沒有信心度欄位）")] = (
                counts.get(str(card.get("confidence") or "（沒有信心度欄位）"), 0) + 1
            )
    total = sum(counts.values())
    rows = [[k, v, f"{(v * 100 // total) if total else 0}%"] for k, v in counts.items()]
    return _section(
        "7",
        "推測內容比例（待驗證）",
        ["信心度", "筆數", "比例"],
        rows,
        note="分母含沒有信心度欄位的卡（Account、Node、Signal）。範例資料一律不視為已驗證。",
    )


def stale(c: dict[str, list[Card]], d: str, today: date | None = None) -> dict[str, Any]:
    limit = (today or datetime.now(UTC).date()) - timedelta(days=STALE_DAYS)
    rows = []
    for cards in c.values():
        for card in cards:
            if not _in(card, d):
                continue
            stamp = str(card.get("updated") or card["_updated"])[:10]
            try:
                when = date.fromisoformat(stamp)
            except ValueError:
                continue
            if when < limit:
                rows.append([_ref(card), card["_type"], stamp])
    rows.sort(key=lambda r: str(r[2]))
    return _section(
        "8",
        "資料過期提醒（超過 90 天未更新）",
        ["卡片", "類型", "更新日"],
        rows,
        note="用卡片的 updated，沒有時用最後一次被接受的變更日期；適用所有類型。",
    )


def supplier_dependency(c: dict[str, list[Card]], d: str) -> dict[str, Any]:
    counts: dict[str, list[str]] = {}
    for account in c.get("Account", []):
        if _in(account, d):
            for supplier in _list(account.get("key_suppliers")):
                counts.setdefault(str(supplier), []).append(account["_name"])
    for cp in c.get("CustomerProduct", []):
        if _in(cp, d):
            for member in _list(cp.get("ecosystem")):
                counts.setdefault(str(member), []).append(cp["_name"])
    rows = [
        [name, len(users), "、".join(users)]
        for name, users in sorted(counts.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    ]
    return _section(
        "12",
        "供應商依賴排行",
        ["Ecosystem / 供應商", "依賴數", "客戶或客戶產品"],
        rows,
        note="合併 Account 的主要供應商與 CustomerProduct 的供應鏈成員（§12、§12b）。",
    )


SECTIONS = (
    gaps,
    trend_coverage,
    demand_without_opportunity,
    solutions_vs_opportunities,
    funnel,
    technologies_without_concept,
    product_completeness,
    trend_priority,
    launch_timeline,
    node_technology,
    recent_signals,
    competitor_coverage,
    assumed_share,
    stale,
    supplier_dependency,
)


def _context(store: BiStore) -> tuple[set[str], dict[str, dict[str, list[str]]], Any]:
    """The schema's types, its link fields with their targets, and the
    dataset's domain configuration (V10), for the market sections."""
    from capabilities.bi_cards import catalog, domains

    reg = catalog.for_store(store)
    links = {
        name: {f.name: list(f.link_to) for f in entity.fields if f.is_link}
        for name, entity in reg.types.items()
    }
    return set(reg.types), links, domains.read(store)


def dashboard(
    store: BiStore, domain: str = "robotics", include_sample: bool = False
) -> dict[str, Any]:
    from capabilities.bi_cards import market

    cards = _cards(store, include_sample)
    types, links, config = _context(store)
    built = market.sections(cards, domain, types=types, link_fields=links, config=config)
    chains = [s for s in built if s["id"].startswith("A")]
    later = [s for s in built if not s["id"].startswith("A")]
    from capabilities.bi_cards import catalog, quality

    checked = quality.section(quality.check(store, catalog.for_store(store)))
    return {
        "domain": domain,
        "include_sample": include_sample,
        "sections": [*chains, *(build(cards, domain) for build in SECTIONS), *later, checked],
    }


#: The analyses the chat can ask for by name (`bi__query` `analysis`); the
#: same computation as the page's dashboard, so an answer and the page agree.
ANALYSES = {build.__name__: build for build in SECTIONS}


def analysis(store: BiStore, name: str, domain: str = "robotics") -> list[dict[str, Any]]:
    """One named dashboard section, or every section for `all` (sample cards
    left out, as on the page by default)."""
    if name == "all":
        return list(dashboard(store, domain)["sections"])
    if name in ANALYSES:
        return [ANALYSES[name](_cards(store, False), domain)]
    from capabilities.bi_cards import catalog, market, quality

    if name == "quality":
        return [quality.section(quality.check(store, catalog.for_store(store)))]

    types, links, config = _context(store)
    return market.sections(
        _cards(store, False), domain, types=types, link_fields=links, config=config, only=name
    )


def analysis_names() -> list[str]:
    """Every name `analysis` takes (the page's sections and the market ones)."""
    from capabilities.bi_cards import market

    return [*ANALYSES, *market.NAMES, "quality"]
