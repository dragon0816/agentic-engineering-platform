# market.py `supply_grades`, moved into the pack (BI P2).


def supply_grades(c: dict[str, list[Card]], d: str) -> dict[str, Any]:
    links = _of(c, "SupplyLink", d)
    rows: list[list[Any]] = []
    for grade in ("A", "B", "C", "D"):
        mine = [x for x in links if (x.get("evidence_grade") or "D") == grade]
        rows.append(
            [
                GRADE_LABELS[grade],
                *(sum(1 for x in mine if x.get("supply_stage") == s) for s in SUPPLY_STAGES),
                sum(1 for x in mine if not x.get("supply_stage")),
                len(mine),
            ]
        )
    flags: list[dict[str, Any]] = []
    for link in links:
        if link.get("evidence_grade") in CONFIRMED and not (
            link.get("source") and link.get("source_date")
        ):
            lacking = [k for k in ("source", "source_date") if not link.get(k)]
            flags.append({"row": len(rows), "level": "warn", "text": "缺 " + "、".join(lacking)})
            rows.append(
                [_ref(link), link["evidence_grade"], *([""] * 5), "⚠ 缺 " + "、".join(lacking)]
            )
    return _section(
        "27",
        "供貨證據等級分布（SupplyLink）",
        ["等級", *SUPPLY_STAGES, "未標階段", "合計"],
        rows,
        flags=flags,
        note="A/B 級缺 source 或 source_date 的列在表後；D 級不可當成已確認的供貨線。",
    )


result = out(supply_grades(cards(), D), level=True)
