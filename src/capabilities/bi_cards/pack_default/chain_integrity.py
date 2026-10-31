# market.py `chain_integrity`, moved into the pack (BI P2).


def chain_integrity(c: dict[str, list[Card]], d: str) -> dict[str, Any]:
    competitors = {x["_key"]: x for x in c.get("Competitor", [])}
    solutions = {x["_key"]: x for x in c.get("TestSolution", [])}
    rows: list[list[Any]] = []
    flags: list[dict[str, Any]] = []
    for sol in sorted(_of(c, "TestSolution", d), key=lambda x: x["_name"]):
        vendor = str(sol.get("vendor") or "")
        if not vendor:
            continue
        found = competitors.get(vendor)
        problem = (
            "我方方案請清空 vendor"
            if _is_mine(vendor)
            else "vendor 不是 Competitor 卡"
            if found is None
            else f"Competitor 卡的 domain 未含 {d}"
            if not _in(found, d)
            else ""
        )
        status = _status(flags, rows, [problem] if problem else [])
        rows.append([_ref(sol), "對手方案", vendor, "", status])
    for opp in sorted(_of(c, "Opportunity", d), key=lambda x: x["_name"]):
        ours = [str(x) for x in _list(opp.get("our_solutions"))]
        apps = [str(x) for x in _list(opp.get("applications"))]
        rivals = [str(x) for x in _list(opp.get("competitors"))]
        problems = []
        if not ours:
            problems.append("無我方方案")
        wrong = [n for n in ours if n in solutions and solutions[n].get("vendor")]
        ghost = [n for n in ours if n not in solutions]
        if wrong:
            problems.append("our_solutions 連到對手方案：" + "、".join(wrong))
        if ghost:
            problems.append("方案卡不存在：" + "、".join(ghost))
        if not apps:
            problems.append("無 Application")
        covered = {
            str(a)
            for n in ours
            if n in solutions and not solutions[n].get("vendor")
            for a in _list(solutions[n].get("applications"))
        }
        uncovered = [a for a in apps if a not in covered]
        if ours and apps and uncovered and not wrong:
            problems.append("我方方案未涵蓋：" + "、".join(uncovered))
        bad = [n for n in rivals if n not in competitors or _is_mine(n)]
        if bad:
            problems.append("competitors 不是 Competitor 卡：" + "、".join(bad))
        status = _status(flags, rows, problems)
        if wrong:
            flags[-1]["level"] = "red"
        rows.append([_ref(opp), opp.get("deal_stage") or "-", "、".join(ours) or "-",
                     "、".join(rivals) or "-", status])  # fmt: skip
    return _section(
        "29",
        "鏈路完整性：Application → 我方方案 → Opportunity（含競品連結）",
        ["方案 / 商機", "類別 / 階段", "vendor / 我方方案", "對手", "檢查"],
        rows,
        flags=flags,
        note="我方 = vendor 空白的 TestSolution；對手方案的 vendor 要連到 Competitor 卡。",
    )


result = out(chain_integrity(cards(), D), level=True)
