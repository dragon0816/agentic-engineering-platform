"""Quality checks of a BI dataset (BI vault V13, `docs/phases/BI_VAULT.md` §12,
owner 2026-10-29).

The manager's `validate.py` grew with every knowledge base; these are its
checks made general: from the schema (links, names, samples, evidence grades,
numbers against their quotes, revenue layers, the Node `name_pattern`). Read
only: nothing is changed, every finding names the card to open. (The domain
configuration's node list check went with the configuration, BI D4: a Node card
is the list.)

`issue` is something wrong that a person must fix; `warn` is a gap the data
admits (a product without a node).
"""

from __future__ import annotations

import re
from typing import Any

from aep_bi.cards.extract import number_written
from aep_bi.cards.schema import Registry
from aep_bi.cards.staging import Staging
from aep_bi.cards.store import BiStore, BiStoreError

SAMPLE_PREFIX = "SAMPLE-"
#: What a card's own text says when it is not about anything real. Not 範例, which a real
#: page's prose uses too; a page's body never reaches the card's mark at import.
SAID_NOT_REAL = re.compile(r"虛構|示範")
#: A source's first such line by its id, a hash of its bytes: a source never changes, and
#: this runs with every Dashboard.
_PAGE_SAYS: dict[str, str] = {}
#: A blank source date the body explains (the manager's convention).
DATE_PENDING = "來源日期待補"
MAX_ITEMS = 200

CHECKS = (
    ("link_unresolved", "連結找不到卡片", "issue"),
    ("link_wrong_type", "連結到的卡片類型不對", "issue"),
    ("same_name", "同一個名字出現在兩種類型", "issue"),
    ("key_conflict", "兩張卡片用了同一個名字", "issue"),
    ("sample_not_marked", "看起來是範例，卻沒有標成示範資料", "issue"),
    ("evidence_source", "A/B 級證據缺來源或來源日期", "issue"),
    ("number_ungrounded", "數字不在引用的原文裡", "issue"),
    ("revenue_layer", "收入事實的層級與客戶不一致或缺來源", "issue"),
    ("node_format", "節點名稱不符合格式", "issue"),
    ("product_without_node", "客戶產品沒有節點", "warn"),
)


def _list(value: Any) -> list[Any]:
    if value is None:
        return []
    return list(value) if isinstance(value, list) else [value]


def _page_says(staging: Staging, source: dict[str, Any], stored: str) -> str:
    """The line of a card page's body that says it is not real, or nothing. A report is many
    cards' source, so what it says is about none of them."""
    source_id = str(source["id"])
    if source_id not in _PAGE_SAYS:
        from aep_bi.cards.reading_runs import readable_lines

        said = ""
        if str(source["name"]).lower().endswith(".md"):
            try:
                raw = staging.read_stored(stored).decode("utf-8-sig", "replace")
            except (BiStoreError, OSError):
                return ""
            if raw.startswith("---"):
                said = next((x for x in readable_lines(raw) if SAID_NOT_REAL.search(x)), "")
        _PAGE_SAYS[source_id] = said
    return _PAGE_SAYS[source_id]


def _said_not_real(store: BiStore) -> dict[str, str]:
    """Per card, what its own pages say that makes it look like an example."""
    staging = Staging(store.workspace, store.dataset)
    if not staging.exists:
        return {}
    sources = {s["id"]: s for s in staging.sources()}
    stored = staging.stored_paths()
    found: dict[str, str] = {}
    for card_id, source_id in store.evidence_sources():
        if card_id not in found and source_id in sources and source_id in stored:
            said = _page_says(staging, sources[source_id], stored[source_id])
            if said:
                found[card_id] = said
    return found


def _ref(card: Any) -> dict[str, str]:
    return {
        "card_id": card["id"],
        "label": card["name"],
        "cite": f"{card['entity_type']}:{card['canonical_key']}",
    }


def check(store: BiStore, reg: Registry, *, read_pages: bool = False) -> dict[str, Any]:
    """Every check's findings: `{"checks": [{"id", "title", "level", "count",
    "items": [{"card", "message"}]}], "totals": {"issue", "warn"}}`. `read_pages` also reads
    the card pages, for the report a person opens: never with every Dashboard, since on a
    colleague's PC each may be a file OneDrive has to fetch."""
    rows = store.card_rows()
    values = {
        card_id: {k: v["value"] for k, v in fields.items()}
        for card_id, fields in store.all_fields().items()
    }
    excerpts = store.fact_excerpts()
    not_real = _said_not_real(store) if read_pages else {}
    # A person has said these are real: their text no longer asks the question.
    told_real = store.marks_cleared()
    found: dict[str, list[dict[str, Any]]] = {cid: [] for cid, _, _ in CHECKS}

    def add(check_id: str, card: Any, message: str) -> None:
        found[check_id].append({"card": _ref(card) if card else None, "message": message})

    by_name: dict[str, list[Any]] = {}
    for card in rows:
        for key in {card["canonical_key"].lower(), card["name"].lower()}:
            by_name.setdefault(key, []).append(card)
    # A link through an alias or a former name does resolve (`BI_CARD_MODEL.md` §3.2).
    known = {card["id"]: card for card in rows}
    for card_id, name in store.other_names():
        if card_id in known and known[card_id] not in by_name.setdefault(name.lower(), []):
            by_name[name.lower()].append(known[card_id])
    seen_names: dict[str, set[str]] = {}
    for card in rows:
        seen_names.setdefault(card["name"].lower(), set()).add(card["entity_type"])
    for name, types in sorted(seen_names.items()):
        if len(types) > 1:
            add("same_name", None, f"「{name}」同時是 {'、'.join(sorted(types))}；請合併或改名")

    for card in rows:
        if str(card["canonical_key"]).endswith(f"#{card['id']}"):
            add("key_conflict", card, f"「{card['name']}」已被另一張卡片使用；請把這張改名")

    node_type = reg.types.get("Node")
    node_pattern = node_type.name_pattern if node_type is not None else ""
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
        elif (
            not card["synthetic"]
            and card["id"] not in told_real
            and (
                said := not_real.get(card["id"])
                or next((x for x in [str(mine.get("body") or "")] if SAID_NOT_REAL.search(x)), "")
            )
        ):
            add(
                "sample_not_marked",
                card,
                f"內容寫著「{said[:60]}」，但沒有標成示範資料，可能被當成事實；"
                "如果真的是範例，請用 CSV 匯入一列註明虛構範例來標記",
            )
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
