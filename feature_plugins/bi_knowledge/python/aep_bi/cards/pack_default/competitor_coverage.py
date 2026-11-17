# dashboard.py `competitor_coverage`, moved into the pack (BI P2).


def competitor_coverage(c: dict[str, list[Card]], d: str) -> dict[str, Any]:
    sols = c.get("TestSolution", [])
    vendors = [MINE, *sorted(x["_name"] for x in c.get("Competitor", []) if _in(x, d))]
    apps = sorted((a for a in c.get("Application", []) if _in(a, d)), key=lambda a: a["_name"])

    def vendor(solution: Card) -> str:
        return str(solution.get("vendor") or MINE)

    rows = [
        [_ref(a), *[sum(1 for s in sols if vendor(s) == v and _covers(s, a)) for v in vendors]]
        for a in apps
    ]
    return _section(
        "6b",
        "競品覆蓋矩陣（每格 = 該廠商在此應用的方案數）",
        ["應用", *vendors],
        rows,
        kind="matrix",
    )


result = out(competitor_coverage(cards(), D), level=False)
