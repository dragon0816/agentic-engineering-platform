# dashboard.py `launch_timeline`, moved into the pack (BI P2).


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


result = out(launch_timeline(cards(), D), level=False)
