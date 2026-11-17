# dashboard.py `supplier_dependency`, moved into the pack (BI P2).


def supplier_dependency(c: dict[str, list[Card]], d: str) -> dict[str, Any]:
    counts: dict[str, list[str]] = {}
    for account in c.get("Account", []):
        if _in(account, d):
            for supplier in _list(account.get("key_suppliers")):
                counts.setdefault(str(supplier), []).append(account["_name"])
    for cp in c.get("CustomerProduct", []):
        if _in(cp, d):
            for member in _list(cp.get("ecosystem")):
                counts.setdefault(str(member), []).append(cp["_name"])
    rows = [
        [name, len(users), "、".join(users)]
        for name, users in sorted(counts.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    ]
    return _section(
        "12",
        "供應商依賴排行",
        ["Ecosystem / 供應商", "依賴數", "客戶或客戶產品"],
        rows,
        note="合併 Account 的主要供應商與 CustomerProduct 的供應鏈成員（§12、§12b）。",
    )


result = out(supplier_dependency(cards(), D), level=False)
