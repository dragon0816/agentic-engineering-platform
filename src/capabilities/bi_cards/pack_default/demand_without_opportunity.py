# dashboard.py `demand_without_opportunity`, moved into the pack (BI P2).


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


result = out(demand_without_opportunity(cards(), D), level=True)
