# dashboard.py `funnel`, moved into the pack (BI P2).


def funnel(c: dict[str, list[Card]], d: str) -> dict[str, Any]:
    opps = [o for o in c.get("Opportunity", []) if _in(o, d)]
    rows = []
    for stage in DEAL_STAGES:
        names = sorted(o["_name"] for o in opps if o.get("deal_stage") == stage)
        rows.append([stage, len(names), "、".join(names)])
    return _section("17", "商機漏斗（依階段）", ["階段", "筆數", "商機"], rows, kind="funnel")


result = out(funnel(cards(), D), level=False)
