# market.py `pending_links`, moved into the pack (BI P2).


def pending_links(
    c: dict[str, list[Card]], d: str, link_fields: dict[str, dict[str, list[str]]]
) -> dict[str, Any]:
    known = {card["_key"].lower() for cards in c.values() for card in cards} | {
        card["_name"].lower() for cards in c.values() for card in cards
    }
    pending: dict[str, dict[str, Any]] = {}
    for type_name, cards in c.items():
        for card in cards:
            for field_name, targets in link_fields.get(type_name, {}).items():
                for target in _list(card.get(field_name)):
                    name = str(target)
                    if not name or name.lower() in known:
                        continue
                    entry = pending.setdefault(name, {"refs": [], "types": {}})
                    if card["_name"] not in entry["refs"]:
                        entry["refs"].append(card["_name"])
                    hint = " / ".join(targets) or "?"
                    entry["types"][hint] = entry["types"].get(hint, 0) + 1
    rows: list[list[Any]] = []
    for name, entry in sorted(pending.items(), key=lambda kv: (-len(kv[1]["refs"]), kv[0]))[:40]:
        hint = max(entry["types"].items(), key=lambda kv: kv[1])[0]
        rows.append([name, len(entry["refs"]), hint, "、".join(entry["refs"][:3])])
    return _section(
        "31",
        "待補的連結目標（後補清單）",
        ["待補目標", "被引用卡數", "建議卡種", "引用來源（前 3）"],
        rows,
        note="卡片已連到、但對應的卡還沒建立的名稱；建立同名卡後連結自動接上。同一家公司有多種叫法時，"
        "在「領域設定」的 name_aliases 統一。",
    )


result = out(pending_links(cards(), D, LINK_FIELDS), level=False)
