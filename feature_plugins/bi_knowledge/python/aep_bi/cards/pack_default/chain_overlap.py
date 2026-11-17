# market.py `chain_overlap`, moved into the pack: chains from Node `chain` (BI D3).
SCHEMA_VALUES: dict[str, Any] = {}  # the schema's allowed values, filled on import


def chain_overlap(c: dict[str, list[Card]], d: str) -> dict[str, Any]:
    index = _chain_index(c)
    order = [code for code, _label in _chain_labels()]

    def chains_of(name: str) -> list[str]:
        return index.get(str(name).lower(), [])

    rows: list[list[Any]] = []
    for node in sorted(_of(c, "Node", d), key=lambda n: n["_name"]):
        belongs = chains_of(node["_key"])
        if len(belongs) > 1:
            key = node["_key"]
            rows.append(
                [
                    "共用節點",
                    _ref(node),
                    "+".join(belongs),
                    sum(1 for e in _of(c, "Ecosystem", d) if key in _nodes(e)),
                    sum(1 for p in _of(c, "CustomerProduct", d) if key in _nodes(p)),
                ]
            )
    for type_name in ("Ecosystem", "Account"):
        for card in sorted(_of(c, type_name, d), key=lambda x: x["_name"]):
            spans = {ch for n in _nodes(card) for ch in chains_of(n)}
            if len(spans) > 1:
                ordered = [code for code in order if code in spans]
                rows.append(["共用公司", _ref(card), "+".join(ordered), type_name, ""])
    return _section(
        "A3",
        "跨鏈檢查（只列共用節點與共用公司）",
        ["類別", "名稱", "鏈別", "Ecosystem 數 / 類型", "客戶產品數"],
        rows,
        note="共用節點：同時歸屬兩條以上的鏈。共用公司：其節點橫跨兩條以上的鏈。",
    )


result = out(chain_overlap(cards(), D), level=False)
