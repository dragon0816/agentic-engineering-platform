# dashboard.py `node_technology`, moved into the pack (BI P2).


def node_technology(c: dict[str, list[Card]], d: str) -> dict[str, Any]:
    nodes = sorted(
        (n for n in c.get("Node", []) if _in(n, d) or n.get("layer") == "X"),
        key=lambda n: n["_name"],
    )
    techs = sorted((t for t in c.get("Technology", []) if _in(t, d)), key=lambda t: t["_name"])
    cps = [x for x in c.get("CustomerProduct", []) if _in(x, d)]
    rows = [
        [
            _ref(n),
            *[
                sum(
                    1
                    for cp in cps
                    if n["_key"] in _nodes_of(cp) and t["_key"] in _list(cp.get("technologies"))
                )
                for t in techs
            ],
        ]
        for n in nodes
    ]
    return _section(
        "4",
        "節點 × 技術 矩陣（客戶產品數）",
        ["節點", *[t["_name"] for t in techs]],
        rows,
        kind="matrix",
    )


result = out(node_technology(cards(), D), level=False)
