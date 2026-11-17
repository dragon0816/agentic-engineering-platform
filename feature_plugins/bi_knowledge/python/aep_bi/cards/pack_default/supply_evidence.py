# market.py `supply_evidence`, moved into the pack (BI P2).


def supply_evidence(c: dict[str, list[Card]], d: str) -> dict[str, Any]:
    trends = _of(c, "Trend", d)
    links = _of(c, "SupplyLink", d)
    rows: list[list[Any]] = []
    flags: list[dict[str, Any]] = []
    products = sorted(_of(c, "CustomerProduct", d), key=lambda p: _day(p.get("launch_date")) or "~")
    for product in products:
        nodes, techs = _nodes(product), {str(t) for t in _list(product.get("technologies"))}
        confirmed = _supply(c, d, product, CONFIRMED)
        pending = [s for s in _supply(c, d, product, ("C", "D")) if s not in confirmed]
        carded = {str(x.get("supplier")) for x in links if product["_key"] in {
            str(p) for p in _list(x.get("customer_products"))}}  # fmt: skip
        no_card = [e for e in (str(x) for x in _list(product.get("ecosystem"))) if e not in carded]
        inferred = [
            t
            for t in trends
            if techs & {str(x) for x in _list(t.get("related_tech"))}
            or nodes & {str(x) for x in _list(t.get("affected_nodes"))}
        ]
        via_supplier = [
            t
            for t in trends
            if set(confirmed) & {str(x) for x in _list(t.get("related_ecosystem"))}
        ]
        both = [t for t in inferred if t in via_supplier]
        every = sorted(
            {t["_key"]: t for t in [*inferred, *via_supplier]}.values(), key=lambda t: -_prio(t)
        )
        problems = []
        if not confirmed:
            problems.append("無 A/B 供應商")
        if not every:
            problems.append("無趨勢")
        if confirmed and not via_supplier:
            problems.append("供應商未連趨勢")
        if no_card:
            problems.append(f"ecosystem 欄 {len(no_card)} 筆無證據卡")
        status = _status(flags, rows, problems)
        rows.append(
            [
                _ref(product),
                _day(product.get("launch_date")) or product.get("launch_window") or "-",
                "、".join(confirmed) or "-",
                "、".join(pending) or "-",
                len(inferred),
                len(via_supplier),
                len(both),
                _ref(every[0]) if every else "-",
                status,
            ]
        )
    return _section(
        "25",
        "客戶產品 × 生態系 × 趨勢（以供貨證據為準）",
        [
            "客戶產品",
            "上市",
            "已確認供應商（A/B）",
            "待確認（C/D）",
            "趨勢（推算）",
            "趨勢（供應商連結）",
            "兩者皆中",
            "最高優先趨勢",
            "檢查",
        ],
        rows,
        flags=flags,
        note="生態系只計 SupplyLink 證據 A/B 的供應商；C/D 列為待確認。兩條路都命中是最強掛勾。",
    )


result = out(supply_evidence(cards(), D), level=True)
