# market.py `same_names`, moved into the pack (BI P2).


def same_names(c: dict[str, list[Card]], d: str) -> dict[str, Any]:
    where: dict[str, list[str]] = {}
    for type_name, cards in c.items():
        for card in cards:
            where.setdefault(card["_name"].lower(), []).append(type_name)
    rows: list[list[Any]] = []
    flags: list[dict[str, Any]] = []
    for name, types in sorted(where.items()):
        if len(types) > 1:
            flags.append({"row": len(rows), "level": "warn", "text": "同名卡"})
            rows.append([name, "、".join(sorted(types)), "⚠ 同名卡，請合併或改名"])
    return _section(
        "30",
        "同名卡衝突（同一個名字出現在不同類型）",
        ["名稱", "類型", "檢查"],
        rows,
        flags=flags,
        note="典型情況：同一家公司同時建了 Account 與 Ecosystem，"
        "或 Keysight 同時是 Competitor 與 Ecosystem。",
    )


result = out(same_names(cards(), D), level=True)
