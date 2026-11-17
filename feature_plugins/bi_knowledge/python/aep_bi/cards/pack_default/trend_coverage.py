# dashboard.py `trend_coverage`, moved into the pack (BI P2).


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


result = out(trend_coverage(cards(), D), level=True)
