# market.py `enablement`, moved into the pack (BI P2).


def enablement(c: dict[str, list[Card]], d: str) -> dict[str, Any]:
    cards = _of(c, "Battlecard", d)
    pitches, demos = _of(c, "Pitch", d), _of(c, "DemoScript", d)
    rows: list[list[Any]] = []
    flags: list[dict[str, Any]] = []
    for comp in sorted(_of(c, "Competitor", d), key=lambda x: x["_name"]):
        mine = [b for b in cards if b.get("competitor") == comp["_key"]]
        reviewed = sum(1 for b in mine if b.get("content_status") not in (None, "draft"))
        status = _status(flags, rows, [] if mine else ["無 Battlecard"])
        rows.append([_ref(comp), "對手", len(mine), reviewed, status])
    for sol in sorted(_of(c, "TestSolution", d), key=lambda x: x["_name"]):
        if sol.get("vendor"):
            continue

        def using(items: list[Card], s: Card = sol) -> int:
            return sum(
                1 for x in items if s["_key"] in {str(v) for v in _list(x.get("our_solutions"))}
            )

        missing = [
            label
            for label, count in (
                ("Pitch", using(pitches)),
                ("Demo", using(demos)),
                ("Battlecard", using(cards)),
            )
            if not count
        ]
        status = _status(flags, rows, [f"缺 {'、'.join(missing)}"] if missing else [])
        rows.append([_ref(sol), "我方方案", using(pitches), using(demos), status])
    return _section(
        "23",
        "Sales Enablement 覆蓋（對手 Battlecard / 我方方案 Pitch 與 Demo）",
        ["對象", "類別", "Battlecard 數 / Pitch", "已審閱 / Demo 腳本", "檢查"],
        rows,
        flags=flags,
    )


result = out(enablement(cards(), D), level=True)
