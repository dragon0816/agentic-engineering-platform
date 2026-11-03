"""A published card as a read-only Markdown page (`cards/<id>.md`).

Design: `docs/phases/BI_CARD_MODEL.md` §6.1. Pure: the same database and schema give
the same bytes on every PC, so a publish writes only the pages that really changed.
Pages are for people and Obsidian. Nothing ever reads one back, and no value in them
is authority; the units are.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Collection, Mapping
from typing import Any

from capabilities.bi_cards import card_model
from capabilities.bi_cards.schema import Registry

#: Shown as their own sections rather than among the attributes.
TEXT_SECTIONS = (("summary", "摘要"), ("usage", "用途"), ("scope", "範圍"))
#: Shown under 時間.
TIME_FIELDS = frozenset({"last_confirmed", "review_due", "updated", "source_date", "date"})
STATE_LABELS = {
    card_model.UNKNOWN: "未知",
    card_model.NOT_APPLICABLE: "不適用",
    card_model.PENDING_CONFIRMATION: "待確認",
    card_model.CONFIRMED_NONE: "確認沒有",
}


def _text(value: Any) -> str:
    if isinstance(value, list):
        return "、".join(_text(item) for item in value)
    return "" if value is None else str(value)


def _quoted(text: str) -> str:
    return json.dumps(text, ensure_ascii=False)


def _one_line(text: str) -> str:
    return " ".join(text.split())


def _locator(raw: str) -> str:
    try:
        found = json.loads(raw)
    except ValueError:
        return ""
    if not isinstance(found, dict):
        return ""
    return "、".join(f"{key}={found[key]}" for key in sorted(found) if found[key] is not None)


def render_card(
    card: Mapping[str, Any],
    reg: Registry,
    *,
    fields: Mapping[str, Any],
    states: Mapping[str, Mapping[str, Any]],
    evidence: list[Mapping[str, Any]],
    relations: list[Mapping[str, Any]],
    aliases: list[str],
    names: Mapping[str, str],
    withdrawn: Collection[str] = (),
) -> str:
    """One card's page. `fields` is field to shown value; `relations` touch this card."""
    entity = reg.types.get(str(card["entity_type"]))
    labels = {d.name: d.label for d in entity.fields} if entity is not None else {}
    order = [d.name for d in entity.fields] if entity is not None else sorted(fields)
    order += sorted(set(fields) - set(order))
    lines = ["---", f"id: {card['id']}", f"type: {_quoted(str(card['entity_type']))}"]
    lines.append(f"key: {_quoted(str(card['canonical_key']))}")
    if aliases:
        lines.append("aliases:")
        lines.extend(f"  - {_quoted(name)}" for name in aliases)
    if card["synthetic"]:
        lines.append("sample: true")
    lines += ["generated: true", "---", "", f"# {card['name']}", ""]
    lines.append(f"> {card['entity_type']}。由發佈產生，請勿編輯：要改值請提更正單。")
    lines.append("")
    if card["synthetic"]:
        lines += ["> 這是樣本資料，不是事實。", ""]
    for name, title in TEXT_SECTIONS:
        if fields.get(name) not in (None, "", []):
            lines += [f"## {title}", "", _text(fields[name]), ""]
    shown = {n for n, _ in TEXT_SECTIONS} | TIME_FIELDS
    rows = []
    for name in order:
        if name in shown:
            continue
        label = labels.get(name, name)
        if fields.get(name) not in (None, "", []):
            rows.append(f"- **{label}**：{_text(fields[name])}")
        elif name in states:
            rows.append(f"- **{label}**：（{_state_text(states[name])}）")
    if rows:
        lines += ["## 屬性", "", *rows, ""]
    lines += _relations(str(card["id"]), relations, names)
    lines += _references(evidence, labels, withdrawn)
    times = [f"- **建立**：{card['created']}", f"- **更新**：{card['updated']}"]
    times += [
        f"- **{labels.get(name, name)}**：{_text(fields[name])}"
        for name in order
        if name in TIME_FIELDS and fields.get(name) not in (None, "", [])
    ]
    lines += ["## 時間", "", *times, ""]
    return "\n".join(lines)


def _state_text(state: Mapping[str, Any]) -> str:
    label = STATE_LABELS.get(str(state["state"]), str(state["state"]))
    reason = _one_line(str(state.get("reason") or ""))
    return f"{label}：{reason}" if reason else label


def _relations(
    card_id: str, relations: list[Mapping[str, Any]], names: Mapping[str, str]
) -> list[str]:
    """Both ways, as `BiStore.relations` reads them; a rejected one is left out."""
    rows = []
    for item in relations:
        if item["status"] == "rejected":
            continue
        outgoing = item["from_card_id"] == card_id
        other = str(item["to_card_id"] if outgoing else item["from_card_id"])
        status = "" if item["status"] == card_model.UNREVIEWED else f"（{item['status']}）"
        arrow = "" if outgoing else "← "
        rows.append(
            f"- {arrow}{item['relation_type']}：[[{other}|{names.get(other, other)}]]{status}"
        )
    return ["## 相關卡片", "", *rows, ""] if rows else []


def _references(
    evidence: list[Mapping[str, Any]], labels: Mapping[str, str], withdrawn: Collection[str]
) -> list[str]:
    rows = []
    for item in evidence:
        place = _locator(str(item["locator"] or ""))
        where = f"{item['source_name']}" + (f"（{place}）" if place else "")
        field = labels.get(str(item["field"]), str(item["field"]))
        excerpt = "" if item["source_id"] in withdrawn else _one_line(str(item["excerpt"] or ""))
        rows.append(f"- {field}：{where}" + (f"：「{excerpt}」" if excerpt else ""))
    return ["## 參考來源", "", *rows, ""] if rows else []


def _rows(db: sqlite3.Connection, sql: str) -> list[sqlite3.Row]:
    try:
        return list(db.execute(sql))
    except sqlite3.OperationalError:  # a database from before the card model
        return []


def render_all(
    db: sqlite3.Connection, reg: Registry, withdrawn: Collection[str] = ()
) -> dict[str, str]:
    """Every card's page in a built database, by card id."""
    db.row_factory = sqlite3.Row
    cards = list(db.execute("SELECT * FROM cards ORDER BY id"))
    names = {str(c["id"]): str(c["name"]) for c in cards}
    fields: dict[str, dict[str, Any]] = {}
    for row in _rows(db, "SELECT card_id, field, value FROM fields ORDER BY card_id, field"):
        fields.setdefault(row["card_id"], {})[row["field"]] = json.loads(row["value"])
    states: dict[str, dict[str, Any]] = {}
    for row in _rows(db, "SELECT * FROM field_states ORDER BY card_id, field"):
        states.setdefault(row["card_id"], {})[row["field"]] = dict(row)
    evidence: dict[str, list[Mapping[str, Any]]] = {}
    for row in _rows(db, "SELECT * FROM evidence ORDER BY card_id, field, seq"):
        evidence.setdefault(row["card_id"], []).append(dict(row))
    relations: dict[str, list[Mapping[str, Any]]] = {}
    for row in _rows(
        db, "SELECT * FROM relations ORDER BY from_card_id, relation_type, to_card_id"
    ):
        relations.setdefault(row["from_card_id"], []).append(dict(row))
        if row["to_card_id"] != row["from_card_id"]:
            relations.setdefault(row["to_card_id"], []).append(dict(row))
    aliases: dict[str, list[str]] = {}
    for row in _rows(db, "SELECT card_id, name FROM card_names ORDER BY card_id, name"):
        aliases.setdefault(row["card_id"], []).append(str(row["name"]))
    return {
        str(card["id"]): render_card(
            dict(card),
            reg,
            fields=fields.get(card["id"], {}),
            states=states.get(card["id"], {}),
            evidence=evidence.get(card["id"], []),
            relations=relations.get(card["id"], []),
            aliases=aliases.get(card["id"], []),
            names=names,
            withdrawn=withdrawn,
        )
        for card in cards
    }
