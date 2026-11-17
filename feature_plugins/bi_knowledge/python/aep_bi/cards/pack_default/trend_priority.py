# dashboard.py `trend_priority`, moved into the pack (BI P2).


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


result = out(trend_priority(cards(), D), level=False)
