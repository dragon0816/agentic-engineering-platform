# market.py `chain_summary`, moved into the pack: chains from Node `chain` (BI D3).
SCHEMA_VALUES: dict[str, Any] = {}  # the schema's allowed values, filled on import


def chain_summary(c: dict[str, list[Card]], d: str) -> dict[str, Any]:
    index = _chain_index(c)
    chains = _domain_chains(c, d, index)
    nodes = _of(c, "Node", d)

    def chains_of(name: str) -> list[str]:
        return index.get(str(name).lower(), [])

    def in_chain(card: Card, code: str) -> bool:
        return any(code in chains_of(n) for n in _nodes(card))

    rows: list[list[Any]] = []
    for chain in chains:
        code = chain["id"]
        mine = [n for n in nodes if code in chains_of(n["_key"])]
        products = [p for p in _of(c, "CustomerProduct", d) if in_chain(p, code)]
        links = [x for x in _of(c, "SupplyLink", d) if in_chain(x, code)]
        rows.append(
            [
                f"{code} {chain['label']}",
                len(mine),
                sum(1 for n in mine if len(chains_of(n["_key"])) > 1),
                sum(1 for e in _of(c, "Ecosystem", d) if in_chain(e, code)),
                len(products),
                len({str(p.get("account")) for p in products if p.get("account")}),
                sum(
                    1
                    for t in _of(c, "Trend", d)
                    if any(code in chains_of(str(n)) for n in _list(t.get("affected_nodes")))
                ),
                len(links),
                sum(1 for x in links if x.get("evidence_grade") in CONFIRMED),
                sum(1 for x in links if x.get("evidence_grade") not in CONFIRMED),
            ]
        )
    shared = sum(1 for n in nodes if len(chains_of(n["_key"])) > 1)
    return _section(
        "A",
        f"{d} 分鏈總表",
        [
            "鏈",
            "節點",
            "（其中共用）",
            "Ecosystem",
            "CustomerProduct",
            "Account（經產品）",
            "Trend",
            "SupplyLink",
            "已確認（A/B）",
            "未確認（C/D）",
        ],  # fmt: skip
        rows,
        note=f"鏈別來自 Node 卡的 chain 欄位，標籤取自 schema。共用節點 {shared} 個，"
        "在每條所屬鏈都計一次。",
    )


result = out(chain_summary(cards(), D), level=False)
