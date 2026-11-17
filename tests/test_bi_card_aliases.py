"""Matching by name reads the cards' own aliases (BI D2).

`docs/phases/BI_ANALYSIS_DASHBOARD.md` §3: an Account's other names are on the
card (`aliases`, schema 3.0.0), so an import or an AI candidate that writes
another name lands on that card, and a pushed card brings its aliases to every
PC. Since D4 nothing else answers (the domain configuration's `name_aliases`
move onto the cards). All data is fictional.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from test_bi_schema_v2 import _call, _ok

from aep_bi.cards import ai_runs, catalog, importer, names
from aep_bi.cards.store import BiStore, PlannedRow

V3 = "bi.schema/v1.1@3.0.0"


def _market(tmp_path: Path) -> BiStore:
    _ok(_call(tmp_path, "POST", "/api/bi/datasets", {"name": "market", "schema": V3}))
    store = BiStore(tmp_path, "market")
    row = PlannedRow(row=1, entity_type="Account", canonical_key="harbor-co", name="Harbor Co",
                     values={"name": "Harbor Co", "aliases": ["港灣", "Harbour Corp"]},
                     synthetic=False)  # fmt: skip
    store.apply([row], filename="a.csv", entity_type="Account", actor="tester")
    return store


def _planned(store: BiStore, entity_type: str, csv_text: str) -> list[Any]:
    prepared = importer.preview(store, entity_type=entity_type, filename="x.csv", csv_text=csv_text)
    return list(prepared.planned.values())


def test_an_import_names_the_card_its_alias_stands_for(tmp_path: Path) -> None:
    store = _market(tmp_path)
    (product,) = _planned(store, "CustomerProduct", "product_name,account\nRack One,港灣\n")
    assert product.values["account"] == "Harbor Co"
    (again,) = _planned(store, "Account", "name,region\nharbour corp,TW\n")
    assert again.values["name"] == "Harbor Co"  # the same card's name, not a new card
    (other,) = _planned(store, "Account", "name\nQuay Co\n")
    assert other.values["name"] == "Quay Co"


def test_only_the_cards_aliases_answer(tmp_path: Path) -> None:
    store = _market(tmp_path)
    found = names.from_store(store)
    assert found.canon("港灣") == "Harbor Co"
    assert found.canon("Nobody") == "Nobody"


def test_an_ai_candidate_takes_the_cards_name(tmp_path: Path) -> None:
    store = _market(tmp_path)
    item: dict[str, Any] = {"entity_type": "CustomerProduct", "name": "Rack Two",
            "fields": [{"field": "account", "value": "Harbour Corp"},
                       {"field": "name", "value": "Rack Two"}]}  # fmt: skip
    ai_runs._canonical_names(names.from_store(store), catalog.for_store(store), item)
    assert item["fields"][0]["value"] == "Harbor Co"
    account: dict[str, Any] = {"entity_type": "Account", "name": "港灣", "fields": []}
    ai_runs._canonical_names(names.from_store(store), catalog.for_store(store), account)
    assert account["name"] == "Harbor Co"
