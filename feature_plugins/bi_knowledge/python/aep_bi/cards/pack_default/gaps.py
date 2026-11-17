# dashboard.py `gaps`, moved into the pack (BI P2).


def gaps(c: dict[str, list[Card]], d: str) -> dict[str, Any]:
    sols = c.get("TestSolution", [])
    rows: list[list[Any]] = []
    flags: list[dict[str, Any]] = []
    for app in sorted((a for a in c.get("Application", []) if _in(a, d)), key=lambda a: a["_name"]):
        mine = sum(1 for s in sols if not s.get("vendor") and _covers(s, app))
        theirs = sum(1 for s in sols if s.get("vendor") and _covers(s, app))
        status = "OK" if mine else ("對手有、我方無" if theirs else "全無")
        if not mine:
            flags.append({"row": len(rows), "level": "red" if theirs else "warn", "text": status})
        rows.append([_ref(app), app.get("lifecycle") or "", mine, theirs, status])
    return _section(
        "6",
        "缺口：Application × 我方方案 / 對手方案",
        ["應用", "階段", "我方方案", "對手方案", "狀態"],
        rows,
        flags=flags,
        note="我方方案 = TestSolution 的 vendor 空白。優先度不存資料，由 Skill 依事實判斷。",
    )


result = out(gaps(cards(), D), level=True)
