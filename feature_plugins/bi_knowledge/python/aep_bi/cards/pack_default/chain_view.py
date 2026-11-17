# market.py `chain_view`, moved into the pack: chains from Node `chain` (BI D3).
SCHEMA_VALUES: dict[str, Any] = {}  # the schema's allowed values, filled on import


def chain_view(c: dict[str, list[Card]], d: str) -> dict[str, Any]:
    index = _chain_index(c)
    trends = _of(c, "Trend", d)
    rows: list[list[Any]] = []
    flags: list[dict[str, Any]] = []
    for chain in _domain_chains(c, d, index):
        code = chain["id"]
        for node in sorted(_of(c, "Node", d), key=lambda n: n["_name"]):
            belongs = index.get(node["_key"].lower(), [])
            if code not in belongs:
                continue
            key = node["_key"]
            ecos = [e for e in _of(c, "Ecosystem", d) if key in _nodes(e)]
            products = [p for p in _of(c, "CustomerProduct", d) if key in _nodes(p)]
            links = [x for x in _of(c, "SupplyLink", d) if key in _nodes(x)]
            via_node = [
                t for t in trends if key in {str(n) for n in _list(t.get("affected_nodes"))}
            ]
            techs = {str(t) for e in ecos for t in _list(e.get("technologies"))}
            via_tech = [
                t
                for t in trends
                if t not in via_node and techs & {str(x) for x in _list(t.get("related_tech"))}
            ]
            problems = []
            if not ecos:
                problems.append("無 Ecosystem")
            elif not via_node and not via_tech:
                problems.append("有 Ecosystem 無 Trend")
            status = _status(flags, rows, problems)
            rows.append(
                [
                    code,
                    _ref(node),
                    node.get("layer") or "",
                    "共用 " + "+".join(belongs) if len(belongs) > 1 else code,
                    "、".join(e["_name"] for e in ecos) or "-",
                    len(products),
                    f"{sum(1 for x in links if x.get('evidence_grade') in CONFIRMED)}"
                    f" / {len(links)}",
                    "、".join(t["_name"] for t in via_node) or "-",
                    "、".join(t["_name"] for t in via_tech) or "-",
                    status,
                ]
            )
    return _section(
        "A2",
        "分鏈視圖：節點 × Ecosystem × 客戶產品 × 趨勢",
        [
            "鏈",
            "節點",
            "層",
            "鏈別",
            "Ecosystem",
            "客戶產品",
            "SupplyLink 已確認/全部",
            "趨勢（affected_nodes）",
            "趨勢（僅經技術）",
            "缺口",
        ],  # fmt: skip
        rows,
        flags=flags,
        note="缺口：有 Ecosystem 卻沒有任何 Trend，或完全沒有 Ecosystem。共用節點在每條鏈都出現。",
    )


result = out(chain_view(cards(), D), level=True)
