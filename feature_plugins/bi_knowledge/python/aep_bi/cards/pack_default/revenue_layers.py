# market.py `revenue_layers`, moved into the pack (BI P2).


def revenue_layers(c: dict[str, list[Card]], d: str) -> dict[str, Any]:
    facts = _of(c, "RevenueFact", d)
    by_company: dict[str, list[Card]] = {}
    for fact in facts:
        by_company.setdefault(str(fact.get("company") or "-"), []).append(fact)
    rows: list[list[Any]] = []
    flags: list[dict[str, Any]] = []
    for company in sorted(by_company):
        mine = by_company[company]

        def layer(name: str, m: list[Card] = mine) -> int:
            return sum(1 for f in m if f.get("rev_layer") == name)

        def basis(name: str, m: list[Card] = mine) -> int:
            return sum(1 for f in m if (f.get("basis") or "estimated") == name)

        missing = [
            label
            for label, name in (
                ("公司層", "company"),
                ("區段層", "segment"),
                ("客戶層未揭露", "customer"),
            )
            if not layer(name)
        ]
        status = _status(flags, rows, [f"缺 {'、'.join(missing)}"] if missing else [])
        periods = "、".join(sorted({str(f.get("period")) for f in mine if f.get("period")}))
        rows.append(
            [
                company,
                periods,
                layer("company"),
                layer("segment"),
                layer("customer"),
                basis("reported"),
                basis("media"),
                basis("estimated"),
                basis("target"),
                status,
            ]
        )
    for account in sorted(_of(c, "Account", d), key=lambda a: a["_name"]):
        if account["_key"] not in by_company:
            flags.append({"row": len(rows), "level": "warn", "text": "無任何 RevenueFact"})
            rows.append([_ref(account), "", "", "", "", "", "", "", "", "⚠ 無任何 RevenueFact"])
    return _section(
        "28",
        "收入事實三層完整度（RevenueFact）",
        [
            "公司",
            "期間",
            "公司層",
            "區段層",
            "客戶層",
            "reported",
            "media",
            "estimated",
            "target",
            "檢查",
        ],
        rows,
        flags=flags,
        note="口徑：reported 財報、media 媒體、estimated 推算、target 目標（target 不可當實績）。",
    )


result = out(revenue_layers(cards(), D), level=True)
