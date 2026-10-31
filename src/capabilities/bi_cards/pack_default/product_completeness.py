# dashboard.py `product_completeness`, moved into the pack (BI P2).


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


result = out(product_completeness(cards(), D), level=True)
