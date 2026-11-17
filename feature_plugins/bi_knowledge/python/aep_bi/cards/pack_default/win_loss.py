# market.py `win_loss`, moved into the pack (BI P2).


def win_loss(c: dict[str, list[Card]], d: str) -> dict[str, Any]:
    records = _of(c, "WinLoss", d)
    rows: list[list[Any]] = []
    for name in sorted({str(x) for w in records for x in _list(w.get("competitors"))}):
        mine = [w for w in records if name in {str(x) for x in _list(w.get("competitors"))}]
        lost = [w for w in mine if w.get("outcome") == "lost"]
        reasons: dict[str, int] = {}
        for w in lost:
            if w.get("primary_reason"):
                reasons[str(w["primary_reason"])] = reasons.get(str(w["primary_reason"]), 0) + 1
        top = max(reasons.items(), key=lambda kv: (kv[1], kv[0])) if reasons else None
        won = sum(1 for w in mine if w.get("outcome") == "won")
        rows.append([name, len(mine), won, len(lost), f"{top[0]} ×{top[1]}" if top else "-"])
    reviewed = {str(w.get("opportunity")) for w in records if w.get("opportunity")}
    flags: list[dict[str, Any]] = []
    for opp in _of(c, "Opportunity", d):
        if opp.get("deal_stage") in ("won", "lost") and opp["_key"] not in reviewed:
            flags.append({"row": len(rows), "level": "warn", "text": "尚未復盤"})
            rows.append([_ref(opp), "-", "", "", f"{opp.get('deal_stage')}：⚠ 尚未復盤"])
    return _section(
        "21",
        "Win-Loss 原因統計（依對手）",
        ["對手 / 已結案商機", "案例數", "贏", "輸", "輸單最常見原因"],
        rows,
        flags=flags,
        note="結果與主因來自 WinLoss 卡；已結案但沒有 WinLoss 卡的商機列在最後（尚未復盤）。",
    )


result = out(win_loss(cards(), D), level=True)
