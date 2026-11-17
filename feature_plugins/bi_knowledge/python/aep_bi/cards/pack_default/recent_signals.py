# dashboard.py `recent_signals`, moved into the pack (BI P2).


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


result = out(recent_signals(cards(), D), level=False)
