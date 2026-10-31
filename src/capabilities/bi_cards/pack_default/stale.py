# dashboard.py `stale`, moved into the pack (BI P2).


def stale(c: dict[str, list[Card]], d: str, today: date | None = None) -> dict[str, Any]:
    limit = (today or datetime.now(UTC).date()) - timedelta(days=STALE_DAYS)
    rows = []
    for cards in c.values():
        for card in cards:
            if not _in(card, d):
                continue
            stamp = str(card.get("updated") or card["_updated"])[:10]
            try:
                when = date.fromisoformat(stamp)
            except ValueError:
                continue
            if when < limit:
                rows.append([_ref(card), card["_type"], stamp])
    rows.sort(key=lambda r: str(r[2]))
    return _section(
        "8",
        "資料過期提醒（超過 90 天未更新）",
        ["卡片", "類型", "更新日"],
        rows,
        note="用卡片的 updated，沒有時用最後一次被接受的變更日期；適用所有類型。",
    )


result = out(stale(cards(), D, TODAY), level=False)
