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

from capabilities.bi_cards.schema import norm_key
from capabilities.bi_cards.store import BiStore

FIELD = "aliases"


class Names:
    """`canon(name)`: the card name an alias (compared loosely) stands for."""

    def __init__(self, table: dict[str, str]) -> None:
        self.table = table

    def __bool__(self) -> bool:
        return bool(self.table)

    def canon(self, name: Any) -> str:
        text = str(name).strip()
        return self.table.get(norm_key(text), text)


def from_store(store: BiStore) -> Names:
    """Every card's aliases -> its name."""
    table: dict[str, str] = {}
    if not store.exists:
        return Names(table)
    names = {r["id"]: str(r["name"]) for r in store.card_rows()}
    with store._db() as db:
        rows = db.execute("SELECT card_id, value FROM fields WHERE field = ?", (FIELD,)).fetchall()
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
    return Names(table)
