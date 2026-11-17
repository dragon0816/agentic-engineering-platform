# market.py `timing_gaps`, moved into the pack (BI P2).


def timing_gaps(c: dict[str, list[Card]], d: str, today: date | None = None) -> dict[str, Any]:
    now = today or _today()
    trends = [t for t in _of(c, "Trend", d) if t.get("stage") != "fading"]
    mine = [s for s in _of(c, "TestSolution", d) if not s.get("vendor")]
    rows: list[list[Any]] = []
    flags: list[dict[str, Any]] = []
    products = sorted(_of(c, "CustomerProduct", d), key=lambda p: _day(p.get("launch_date")) or "~")
    for product in products:
        launch = _day(product.get("launch_date"))
        months = _months_to(launch, now) if launch else None
        if months is None:
            flags.append({"row": len(rows), "level": "warn", "text": "缺 launch_date"})
            rows.append([_ref(product), "-", "-", "-", "-", "-", "⚠ 缺 launch_date"])
            continue
        nodes, techs = _nodes(product), {str(t) for t in _list(product.get("technologies"))}
        suppliers = set(_supply(c, d, product, CONFIRMED))
        hit = [
            t
            for t in trends
            if techs & {str(x) for x in _list(t.get("related_tech"))}
            or nodes & {str(x) for x in _list(t.get("affected_nodes"))}
            or suppliers & {str(x) for x in _list(t.get("related_ecosystem"))}
        ]
        early = [
            t
            for t in hit
            if t.get("time_to_demand") in DEMAND_START
            and DEMAND_START[str(t["time_to_demand"])] <= months
        ]
        apps = {str(a) for a in _list(product.get("inferred_applications"))}
        sols = [s for s in mine if apps & {str(a) for a in _list(s.get("applications"))}]
        available = sum(1 for s in sols if s.get("status") == "available")
        planning = sum(1 for s in sols if s.get("status") == "planning")
        if not apps:
            status, level = "⚠ 缺 inferred_applications", "warn"
        elif not early:
            status, level = "OK（無早於上市的趨勢需求）", ""
        elif available:
            status, level = "OK", ""
        elif planning:
            status, level = "🟡 方案規劃中", "warn"
        else:
            status, level = "🔴 趨勢需求已到、我方無方案", "red"
        if level:
            flags.append({"row": len(rows), "level": level, "text": status})
        rows.append(
            [
                _ref(product),
                launch,
                round(months, 1),
                product.get("test_stage_now") or "-",
                "、".join(t["_name"] for t in early) or "-",
                f"{available} / {planning}",
                status,
            ]
        )
    return _section(
        "26",
        "時程缺口：趨勢需求早於產品上市、但我方方案尚未 available",
        [
            "客戶產品",
            "上市日",
            "倒數（月）",
            "目前階段",
            "上市時已有需求的趨勢",
            "我方方案（available / planning）",
            "檢查",
        ],
        rows,
        flags=flags,
        note="time_to_demand 的起點（0-6m→0、6-18m→6、18-36m→18、36m+→36 個月）≤ 上市倒數月數，"
        "視為上市時需求已存在。",
    )


result = out(timing_gaps(cards(), D, TODAY), level=True)
