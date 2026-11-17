# dashboard.py `technologies_without_concept`, moved into the pack (BI P2).


def technologies_without_concept(c: dict[str, list[Card]], d: str) -> dict[str, Any]:
    concepts = c.get("Concept", [])
    rows: list[list[Any]] = []
    flags: list[dict[str, Any]] = []
    for tech in sorted((t for t in c.get("Technology", []) if _in(t, d)), key=lambda t: t["_name"]):
        linked = [x for x in concepts if tech["_key"] in _list(x.get("technologies"))]
        reviewed = sum(1 for x in linked if x.get("review_status") == "reviewed")
        status = "缺 Concept" if not linked else ("尚無已審閱" if not reviewed else "OK")
        if status != "OK":
            flags.append({"row": len(rows), "level": "warn", "text": status})
        rows.append([_ref(tech), len(linked), reviewed, status])
    return _section(
        "14",
        "缺少 Concept 解釋的 Technology",
        ["技術", "Concept 數", "已審閱", "狀態"],
        rows,
        flags=flags,
    )


result = out(technologies_without_concept(cards(), D), level=True)
