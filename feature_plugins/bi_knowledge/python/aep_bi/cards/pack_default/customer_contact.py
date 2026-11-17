# market.py `customer_contact`, moved into the pack (BI P2).


def customer_contact(c: dict[str, list[Card]], d: str, today: date | None = None) -> dict[str, Any]:
    now = today or _today()
    limit = (now - timedelta(days=VISIT_DAYS)).isoformat()
    visits = _of(c, "VisitLog", d)
    rows: list[list[Any]] = []
    flags: list[dict[str, Any]] = []
    for opp in sorted(_of(c, "Opportunity", d), key=lambda x: x["_name"]):
        if opp.get("deal_stage") in ("won", "lost"):
            continue
        mine = sorted(
            (_day(v.get("date")) for v in visits if v.get("opportunity") == opp["_key"]),
            reverse=True,
        )
        last = mine[0] if mine else ""
        problem = "無拜訪紀錄" if not last else ("超過 60 天" if last < limit else "")
        status = _status(flags, rows, [problem] if problem else [])
        rows.append([_ref(opp), opp.get("deal_stage") or "-", len(mine), last or "-", status])
    for visit in visits:
        due = _day(visit.get("follow_up_date"))
        if due and due < now.isoformat():
            flags.append({"row": len(rows), "level": "warn", "text": "跟進逾期"})
            rows.append([_ref(visit), visit.get("account") or "-", "", due, "⚠ 跟進逾期"])
    return _section(
        "24",
        "客戶接觸：進行中商機的最近拜訪與逾期跟進",
        ["商機 / 拜訪", "階段 / 客戶", "拜訪次數", "最近拜訪 / 跟進日", "檢查"],
        rows,
        flags=flags,
        note=f"進行中商機超過 {VISIT_DAYS} 天沒有拜訪紀錄標警示；跟進日已過的拜訪也列出。",
    )


result = out(customer_contact(cards(), D, TODAY), level=True)
