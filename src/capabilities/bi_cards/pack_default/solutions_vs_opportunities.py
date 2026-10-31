# dashboard.py `solutions_vs_opportunities`, moved into the pack (BI P2).


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


result = out(solutions_vs_opportunities(cards(), D), level=True)
