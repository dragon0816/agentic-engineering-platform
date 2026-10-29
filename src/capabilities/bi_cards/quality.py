"""Quality checks of a BI dataset (BI vault V13, `docs/phases/BI_VAULT.md` §12,
owner 2026-10-29).

The manager's `validate.py` grew with every knowledge base; these are its
checks made general: from the schema (links, names, samples, evidence grades,
numbers against their quotes, revenue layers) and from the dataset's domain
configuration (node name format, nodes outside a domain's node list). Read
only: nothing is changed, every finding names the card to open.

`issue` is something wrong that a person must fix; `warn` is a gap the data
admits (a product without a node, a node proposed but not on the list).
"""

from __future__ import annotations

import re
from typing import Any

from capabilities.bi_cards import domains
from capabilities.bi_cards.extract import number_written
from capabilities.bi_cards.schema import Registry
from capabilities.bi_cards.store import BiStore

SAMPLE_PREFIX = "SAMPLE-"
#: A blank source date the body explains (the manager's convention).
DATE_PENDING = "來源日期待補"
MAX_ITEMS = 200

CHECKS = (
    ("link_unresolved", "連結找不到卡片", "issue"),
    ("link_wrong_type", "連結到的卡片類型不對", "issue"),
    ("same_name", "同一個名字出現在兩種類型", "issue"),
    ("sample_not_marked", "SAMPLE 卡沒有標成示範資料", "issue"),
    ("evidence_source", "A/B 級證據缺來源或來源日期", "issue"),
    ("number_ungrounded", "數字不在引用的原文裡", "issue"),
    ("revenue_layer", "收入事實的層級與客戶不一致或缺來源", "issue"),
    ("node_format", "節點名稱不符合格式", "issue"),
    ("node_not_listed", "節點不在領域的節點清單", "warn"),
    ("product_without_node", "客戶產品沒有節點", "warn"),
)


def _list(value: Any) -> list[Any]:
    if value is None:
        return []
    return list(value) if isinstance(value, list) else [value]


def _ref(card: Any) -> dict[str, str]:
    return {
        "card_id": card["id"],
        "label": card["name"],
        "cite": f"{card['entity_type']}:{card['canonical_key']}",
    }


def check(store: BiStore, reg: Registry) -> dict[str, Any]:
    """Every check's findings: `{"checks": [{"id", "title", "level", "count",
    "items": [{"card", "message"}]}], "totals": {"issue", "warn"}}`."""
    rows = store.card_rows()
    values = {
        card_id: {k: v["value"] for k, v in fields.items()}
        for card_id, fields in store.all_fields().items()
    }
    excerpts = store.fact_excerpts()
    config = domains.read(store)
    found: dict[str, list[dict[str, Any]]] = {cid: [] for cid, _, _ in CHECKS}

    def add(check_id: str, card: Any, message: str) -> None:
        found[check_id].append({"card": _ref(card) if card else None, "message": message})

    by_name: dict[str, list[Any]] = {}
    for card in rows:
        for key in {card["canonical_key"].lower(), card["name"].lower()}:
            by_name.setdefault(key, []).append(card)
    seen_names: dict[str, set[str]] = {}
    for card in rows:
        seen_names.setdefault(card["name"].lower(), set()).add(card["entity_type"])
    for name, types in sorted(seen_names.items()):
        if len(types) > 1:
            add("same_name", None, f"「{name}」同時是 {'、'.join(sorted(types))}；請合併或改名")

    node_pattern = (config.document.get("node_name_pattern") if config else None) or None
    for card in rows:
        entity = reg.types.get(card["entity_type"])
        mine = values.get(card["id"], {})
        if entity is None:
            continue
        for item in entity.fields:
            if item.is_link:
                for target in _list(mine.get(item.name)):
                    hits = by_name.get(str(target).lower(), [])
                    if not hits:
                        add("link_unresolved", card, f"{item.label}：「{target}」還沒有卡片")
                    elif item.link_to and not any(h["entity_type"] in item.link_to for h in hits):
                        kinds = "、".join(sorted({h["entity_type"] for h in hits}))
                        add(
                            "link_wrong_type",
                            card,
                            f"{item.label}：「{target}」是 {kinds}，"
                            f"應該是 {'、'.join(item.link_to)}",
                        )
            if item.kind in ("int", "float") and isinstance(mine.get(item.name), (int, float)):
                quotes = excerpts.get((card["id"], item.name), [])
                if quotes and not any(number_written(mine[item.name], q) for q in quotes):
                    add(
                        "number_ungrounded",
                        card,
                        f"{item.label}：{mine[item.name]:g} 不在引用的原文「{quotes[-1][:80]}」裡",
                    )
        if card["name"].startswith(SAMPLE_PREFIX) and not card["synthetic"]:
            add("sample_not_marked", card, "名稱是 SAMPLE-，但沒有標成示範資料，可能被當成真實資料")
        if mine.get("evidence_grade") in ("A", "B"):
            if entity.get("source") is not None and not mine.get("source"):
                add("evidence_source", card, f"{mine['evidence_grade']} 級證據沒有來源（source）")
            if (
                entity.get("source_date") is not None
                and not mine.get("source_date")
                and DATE_PENDING not in str(mine.get("body") or "")
            ):
                add(
                    "evidence_source",
                    card,
                    f"{mine['evidence_grade']} 級證據沒有來源日期，"
                    f"內文也沒有註明「{DATE_PENDING}」",
                )
        if card["entity_type"] == "RevenueFact":
            layer = mine.get("rev_layer")
            if layer == "customer" and not mine.get("customer"):
                add("revenue_layer", card, "客戶層卻沒有填客戶")
            if layer not in (None, "customer") and mine.get("customer"):
                add("revenue_layer", card, f"{layer} 層不該填客戶")
            if entity.get("source") is not None and not mine.get("source"):
                add("revenue_layer", card, "收入事實沒有來源（source）")
        if card["entity_type"] == "CustomerProduct" and not (mine.get("node") or mine.get("nodes")):
            add("product_without_node", card, "沒有節點，掛不到價值鏈（可能是刻意留白）")
        if card["entity_type"] == "Node":
            if node_pattern and not re.search(node_pattern, card["name"]):
                add("node_format", card, f"名稱不符合 {node_pattern}")
            if config is not None:
                for domain_id in _list(mine.get("domain")):
                    domain = config.domain(str(domain_id))
                    listed = [n.lower() for n in (domain or {}).get("nodes") or []]
                    if listed and card["name"].lower() not in listed:
                        add(
                            "node_not_listed",
                            card,
                            f"不在「{domain['label'] if domain else domain_id}」"
                            "的節點清單（提案的節點？）",
                        )
    checks = []
    totals = {"issue": 0, "warn": 0}
    for check_id, title, level in CHECKS:
        items = found[check_id]
        totals[level] += len(items)
        checks.append(
            {
                "id": check_id,
                "title": title,
                "level": level,
                "count": len(items),
                "items": items[:MAX_ITEMS],
            }
        )
    return {"dataset": store.dataset, "checks": checks, "totals": totals}


def section(report: dict[str, Any]) -> dict[str, Any]:
    """The report as a dashboard section (`Q`), so the page and the chat show it."""
    rows: list[list[Any]] = []
    flags: list[dict[str, Any]] = []
    for item in report["checks"]:
        for finding in item["items"]:
            flags.append(
                {
                    "row": len(rows),
                    "level": "red" if item["level"] == "issue" else "warn",
                    "text": item["title"],
                }
            )
            rows.append([item["title"], finding["card"] or "-", finding["message"]])
    totals = report["totals"]
    return {
        "id": "Q",
        "title": "Q. 資料品質檢查",
        "kind": "table",
        "columns": ["檢查", "卡片", "說明"],
        "rows": rows,
        "flags": flags,
        "note": f"問題 {totals['issue']} 項、提醒 {totals['warn']} 項。"
        "問題需要修正；提醒是資料承認的缺口。",
    }
