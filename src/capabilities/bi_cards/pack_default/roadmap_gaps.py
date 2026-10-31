# market.py `roadmap_gaps`, moved into the pack (BI P2).


def roadmap_gaps(c: dict[str, list[Card]], d: str) -> dict[str, Any]:
    open_requests = [
        r
        for r in _of(c, "RoadmapRequest", d)
        if r.get("request_status") not in ("shipped", "declined")
    ]

    def score(r: Card) -> int:
        return int(r.get("impact") or 0) * int(r.get("customer_count") or 1)

    rows: list[list[Any]] = []
    flags: list[dict[str, Any]] = []
    for r in sorted(open_requests, key=lambda r: (-score(r), r["_name"])):
        evidence = len(_list(r.get("source_win_loss"))) + len(_list(r.get("source_opportunities")))
        status = _status(flags, rows, [] if evidence else ["無證據來源"])
        rows.append(
            [
                _ref(r),
                r.get("gap_type") or "-",
                r.get("impact") or "-",
                r.get("customer_count") or "-",
                score(r),
                r.get("request_status") or "-",
                len(_list(r.get("source_win_loss"))),
                _join(r.get("our_solutions")),
                status,
            ]
        )
    return _section(
        "22",
        "Roadmap Request 缺口排行",
        ["需求", "缺口類型", "影響", "客戶數", "分數", "狀態", "來源案例", "方案", "檢查"],
        rows,
        flags=flags,
        note="排序：影響程度 × 受影響客戶數；沒有 Win-Loss 或商機來源的需求標「無證據來源」。",
    )


result = out(roadmap_gaps(cards(), D), level=True)
