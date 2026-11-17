# dashboard.py `assumed_share`, moved into the pack (BI P2).


def assumed_share(c: dict[str, list[Card]], d: str) -> dict[str, Any]:
    counts = {"verified": 0, "assumed": 0, "（沒有信心度欄位）": 0}
    for cards in c.values():
        for card in cards:
            if not _in(card, d):
                continue
            counts[str(card.get("confidence") or "（沒有信心度欄位）")] = (
                counts.get(str(card.get("confidence") or "（沒有信心度欄位）"), 0) + 1
            )
    total = sum(counts.values())
    rows = [[k, v, f"{(v * 100 // total) if total else 0}%"] for k, v in counts.items()]
    return _section(
        "7",
        "推測內容比例（待驗證）",
        ["信心度", "筆數", "比例"],
        rows,
        note="分母含沒有信心度欄位的卡（Account、Node、Signal）。範例資料一律不視為已驗證。",
    )


result = out(assumed_share(cards(), D), level=False)
