# market.py `trend_links`, moved into the pack (BI P2).


def trend_links(c: dict[str, list[Card]], d: str) -> dict[str, Any]:
    ecos, cps = _of(c, "Ecosystem", d), _of(c, "CustomerProduct", d)
    rows: list[list[Any]] = []
    flags: list[dict[str, Any]] = []
    for trend in sorted(_of(c, "Trend", d), key=lambda t: -_prio(t)):
        nodes = {str(n) for n in _list(trend.get("affected_nodes"))}
        techs = {str(t) for t in _list(trend.get("related_tech"))}
        by_tech = [e for e in ecos if techs & {str(t) for t in _list(e.get("technologies"))}]
        by_node = [e for e in ecos if e not in by_tech and _nodes(e) & nodes]
        products = [
            p
            for p in cps
            if _nodes(p) & nodes or techs & {str(t) for t in _list(p.get("technologies"))}
        ]
        missing = []
        if not by_tech and not by_node:
            missing.append("缺生態系")
        if not products:
            missing.append("缺客戶產品")
        status = _status(flags, rows, missing)
        rows.append([_ref(trend), _prio(trend), len(by_tech), len(by_node), len(products), status])
    return _section(
        "20",
        "趨勢 × 生態系 × 客戶產品 三方掛勾檢查",
        ["趨勢", "優先度", "生態系（技術掛勾）", "生態系（節點掛勾）", "客戶產品數", "檢查"],
        rows,
        flags=flags,
        note="生態系由技術相同（強）或節點相同（弱）推得；任一欄為 0 代表那條鏈斷了。",
    )


result = out(trend_links(cards(), D), level=True)
