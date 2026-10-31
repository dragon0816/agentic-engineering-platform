# The bi-market-default pack's shared helpers, put before each analysis's code (BI P2).
# Moved from capabilities/bi_cards/dashboard.py and market.py. A script reads query()
# and PARAMS (domain, include_sample, today) and sets `result`.
from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta  # noqa: F401 - the sections use it
from typing import Any

query = globals()["query"]
PARAMS = globals()["PARAMS"]
D = str(PARAMS.get("domain") or "robotics")
TODAY = date.fromisoformat(PARAMS["today"]) if PARAMS.get("today") else datetime.now(UTC).date()
LINK_FIELDS: dict[str, dict[str, list[str]]] = {}  # the schema's link fields, filled on import

MINE = "R&S(我方)"
SAMPLE_PREFIX = "SAMPLE-"
STALE_DAYS = 90
DEAL_STAGES = ("lead", "qualified", "proposal", "eval", "negotiation", "won", "lost")
CLOSED = ("won", "lost")
GRADE_LABELS = {
    "A": "A 原廠/具名確認",
    "B": "B 可信報導/公司說明",
    "C": "C 產品能力",
    "D": "D 傳聞/待確認",
}
CONFIRMED = ("A", "B")
SUPPLY_STAGES = ("demo", "sample", "cert", "pilot", "mass")
DEMAND_START = {"0-6m": 0, "6-18m": 6, "18-36m": 18, "36m+": 36}
VISIT_DAYS = 60
MINE_RE = ("rohde", "r&s", "羅德")


class Card(dict[str, Any]):
    """One card's values plus `_name`, `_key`, `_id`, `_type`, `_updated`."""


def cards() -> dict[str, list[Card]]:
    """Every card by type; `SAMPLE-…` cards only when include_sample."""
    values: dict[str, dict[str, Any]] = {}
    for row in query("SELECT card_id, field, value FROM fields"):
        text = row["value"]
        values.setdefault(row["card_id"], {})[row["field"]] = (
            None if text is None else json.loads(text)
        )
    found: dict[str, list[Card]] = {}
    sql = "SELECT id, entity_type, canonical_key, name, updated FROM cards"
    for row in query(sql + " ORDER BY entity_type, canonical_key"):
        if not PARAMS.get("include_sample") and str(row["name"]).startswith(SAMPLE_PREFIX):
            continue
        card = Card(values.get(row["id"], {}))
        card["_name"] = row["canonical_key"] if row["entity_type"] == "Signal" else row["name"]
        card["_key"] = row["canonical_key"]
        card["_id"] = row["id"]
        card["_type"] = row["entity_type"]
        card["_updated"] = row["updated"]
        found.setdefault(row["entity_type"], []).append(card)
    return found


def out(section: dict[str, Any], level: bool) -> dict[str, Any]:
    """The section as a table: a card cell becomes its name; a flagged row's
    `level` is `gap` (red) or `warning`."""
    levels = {f["row"]: "gap" if f["level"] == "red" else "warning" for f in section["flags"]}
    rows = []
    for number, row in enumerate(section["rows"]):
        cells = [cell["label"] if isinstance(cell, dict) else cell for cell in row]
        rows.append(cells + [levels.get(number)] if level else cells)
    return {"columns": list(section["columns"]) + (["level"] if level else []), "rows": rows}


def _today() -> date:
    return TODAY


def _list(value: Any) -> list[Any]:
    if value is None:
        return []
    return list(value) if isinstance(value, list) else [value]


def _in(card: Card, domain: str) -> bool:
    values = _list(card.get("domain") or "wireless")
    return domain.lower() in {str(v).lower() for v in values}


def _ref(card: Card) -> dict[str, str]:
    return {
        "card_id": card["_id"],
        "label": card["_name"],
        "cite": f"{card['_type']}:{card['_key']}",
    }


def _prio(trend: Card) -> int:
    return int(trend.get("measurement_impact") or 0) * int(trend.get("our_fit") or 0)


def _covers(solution: Card, app: Card) -> bool:
    return app["_key"] in _list(solution.get("applications"))


def _section(
    sid: str,
    title: str,
    columns: list[str],
    rows: list[list[Any]],
    *,
    kind: str = "table",
    flags: list[dict[str, Any]] | None = None,
    note: str = "",
) -> dict[str, Any]:
    return {"id": sid, "title": f"{sid}. {title}", "kind": kind, "columns": columns,
            "rows": rows, "flags": flags or [], "note": note}  # fmt: skip


def _join(value: Any) -> str:
    return "、".join(str(v) for v in _list(value))


def _nodes(card: Card) -> set[str]:
    found = {str(n) for n in _list(card.get("nodes"))}
    if card.get("node"):
        found.add(str(card["node"]))
    return found


_nodes_of = _nodes


def _of(c: dict[str, list[Card]], type_name: str, d: str) -> list[Card]:
    return [x for x in c.get(type_name, []) if _in(x, d)]


def _status(flags: list[dict[str, Any]], rows: list[list[Any]], problems: list[str]) -> str:
    if problems:
        flags.append({"row": len(rows), "level": "warn", "text": "；".join(problems)})
        return "⚠ " + "；".join(problems)
    return "OK"


def _day(value: Any) -> str:
    return str(value)[:10] if value else ""


def _months_to(day: str, today: date) -> float | None:
    try:
        when = date.fromisoformat(day)
    except ValueError:
        return None
    return (when - today).days / 30.44


def _supply(c: dict[str, list[Card]], d: str, product: Card, grades: tuple[str, ...]) -> list[str]:
    found: list[str] = []
    for link in _of(c, "SupplyLink", d):
        if link.get("evidence_grade") not in grades:
            continue
        if product["_key"] in {str(x) for x in _list(link.get("customer_products"))}:
            supplier = str(link.get("supplier") or "")
            if supplier and supplier not in found:
                found.append(supplier)
    return found


def _is_mine(name: str) -> bool:
    return any(word in name.lower() for word in MINE_RE)
