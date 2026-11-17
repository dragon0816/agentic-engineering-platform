"""A card name in its canonical spelling, from the cards' own aliases (BI D2).

`docs/phases/BI_ANALYSIS_DASHBOARD.md` §3: an entity matched by name (an
Account, a Competitor, ...) carries its other names in its `aliases` field
(schema 3.0.0), so a pushed card brings its aliases and every PC matches the
same way. Imports and AI candidates resolve card names and link targets through
this lookup, built from the store. Until the domain configuration is removed
(D4), its `name_aliases` still answer what no card's aliases do.
"""

from __future__ import annotations

import json
from typing import Any

from aep_bi.cards.schema import norm_key
from aep_bi.cards.store import BiStore

FIELD = "aliases"


class Names:
    """`canon(name)`: the card name an alias (compared loosely) stands for."""

    def __init__(
        self, table: dict[str, str], former: dict[tuple[str, str], tuple[str, str]] | None = None
    ) -> None:
        self.table = table
        #: (type, former key) -> the renamed card's (key, name).
        self.former = former or {}

    def __bool__(self) -> bool:
        return bool(self.table or self.former)

    def canon(self, name: Any) -> str:
        text = str(name).strip()
        return self.table.get(norm_key(text), text)


def every_name(store: BiStore) -> dict[str, list[dict[str, str]]]:
    """Each loose name or alias -> the cards answering it, of any type."""
    found: dict[str, list[dict[str, str]]] = {}
    if not store.exists:
        return found
    cards = {str(r["id"]): r for r in store.card_rows()}

    def add(name: Any, card: Any) -> None:
        key = norm_key(name)
        entry = {"id": str(card["id"]), "name": str(card["name"]), "type": str(card["entity_type"])}
        if key and entry not in found.setdefault(key, []):
            found[key].append(entry)

    for card in cards.values():
        add(card["name"], card)
        add(card["canonical_key"], card)
    with store._db() as db:
        rows = db.execute("SELECT card_id, value FROM fields WHERE field = ?", (FIELD,)).fetchall()
    for row in rows:
        owner = cards.get(str(row["card_id"]))
        value = json.loads(row["value"]) if owner is not None and row["value"] else []
        for alias in value if isinstance(value, list) else [value]:
            add(alias, owner)
    return found


def from_store(store: BiStore) -> Names:
    """Every card's aliases and former names -> its name."""
    table: dict[str, str] = {}
    former: dict[tuple[str, str], tuple[str, str]] = {}
    if not store.exists:
        return Names(table)
    cards = store.card_rows()
    names = {r["id"]: str(r["name"]) for r in cards}
    by_id = {r["id"]: r for r in cards}
    with store._db() as db:
        rows = db.execute("SELECT card_id, value FROM fields WHERE field = ?", (FIELD,)).fetchall()
        known = db.execute("SELECT 1 FROM sqlite_master WHERE name = 'card_names'").fetchone()
        renamed = (
            db.execute("SELECT card_id, name FROM card_names WHERE kind = 'former'").fetchall()
            if known
            else []
        )
    for row in rows:
        try:
            value = json.loads(row["value"]) if row["value"] is not None else None
        except ValueError:
            continue
        name = names.get(row["card_id"])
        if name is None:
            continue
        for alias in value if isinstance(value, list) else [value]:
            if isinstance(alias, str) and alias.strip():
                table[norm_key(alias)] = name
    for row in renamed:
        card = by_id.get(row["card_id"])
        if card is not None:
            former[(str(card["entity_type"]), str(row["name"]))] = (
                str(card["canonical_key"]),
                str(card["name"]),
            )
    return Names(table, former)
