"""Why a field holds no value (`docs/phases/BI_CARD_MODEL.md` §3.4, task T5).

Two PCs as in `test_bi_vault.py`. `fields` never holds a sentinel: `n/a`, `tbd`
and `待定` become a `state:` unit, the same on every PC. All data is fictional.
"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

import pytest
from test_bi_card_page_import import _apply, _preview
from test_bi_vault import _call, _ok, _push, _sync, _two_pcs

from aep_bi.cards import importer, manifest, recipes, service, vault
from aep_bi.cards.catalog import for_store
from aep_bi.cards.schema import missing_state
from aep_bi.cards.store import BiStore, PlannedRow

CSV = "技術,成熟度,標準組織\nFAKE-A,n/a,TBD\nFAKE-B,nan,-\nFAKE-C,待定,\n"


def _store(ws: Path, dataset: str) -> BiStore:
    return BiStore(ws, dataset)


def _csv(ws: Path, dataset: str, text: str = CSV) -> importer.Preview:
    store = _store(ws, dataset)
    prepared = importer.preview(store, entity_type="Technology", filename="t.csv", csv_text=text)
    importer.apply(store, prepared, None, actor="alice")
    return prepared


def _states(ws: Path, dataset: str, key: str) -> dict[str, dict[str, Any]]:
    store = _store(ws, dataset)
    card = store.find("Technology", key)
    assert card is not None
    return store.field_states(card["id"])


def _state_units(ws: Path, vault_id: str) -> dict[str, Any]:
    repo = vault.Vault(ws, vault_id).repo
    return {k: v for k, v in repo.working_units().items() if k.startswith("state:")}


def _rule_run(ws: Path, dataset: str, text: str) -> tuple[dict[str, Any], dict[str, Any]]:
    given = {"dataset": dataset, "name": "t.csv", "text": text}
    source = _ok(_call(ws, "POST", "/api/bi/sources", given))["source"]
    body = {
        "dataset": dataset,
        "kind": "ingest",
        "source_id": source["id"],
        "entity_type": "Technology",
    }
    run = _ok(_call(ws, "POST", "/api/bi/runs", body))["run"]
    return run, _ok(_call(ws, "GET", f"/api/bi/runs/{run['id']}", dataset=dataset))


def _rows(ws: Path, vault_id: str) -> list[tuple[Any, ...]]:
    with closing(sqlite3.connect(vault.Vault(ws, vault_id).db_path)) as db:
        return list(db.execute("SELECT * FROM field_states ORDER BY card_id, field"))


@pytest.mark.parametrize(
    ("text", "state"),
    [
        ("n/a", "not_applicable"),
        ("N/A", "not_applicable"),
        (" na ", "not_applicable"),
        ("tbd", "pending_confirmation"),
        ("待定", "pending_confirmation"),
        (["待定"], "pending_confirmation"),
        ("", None),
        ("nan", None),
        ("none", None),
        ("null", None),
        ("-", None),
        ("—", None),
        ("a value", None),
    ],
)
def test_only_the_words_that_give_a_reason_are_a_state(text: Any, state: str | None) -> None:
    assert missing_state(text) == state


def test_a_csv_keeps_the_reason_and_never_stores_the_word(tmp_path: Path) -> None:
    _, vault_id, dataset, a, _ = _two_pcs(tmp_path)
    prepared = _csv(a, dataset)
    store = _store(a, dataset)
    first = store.find("Technology", "FAKE-A")
    assert first is not None
    assert not {"maturity", "standard_body"} & set(store.fields(first["id"]))
    states = store.field_states(first["id"])
    assert {name: s["state"] for name, s in states.items()} == {
        "maturity": "not_applicable",
        "standard_body": "pending_confirmation",
    }
    assert _states(a, dataset, "FAKE-C")["maturity"]["state"] == "pending_confirmation"
    assert _states(a, dataset, "FAKE-C")["maturity"]["raw"] == "待定"
    assert states["maturity"]["raw"] == "n/a"
    assert states["maturity"]["origin"] == "unit"
    assert states["standard_body"]["raw"] == "TBD"
    # `nan`, `-` and `—` say nothing: unknown, so no row.
    assert _states(a, dataset, "FAKE-B") == {}
    # The preview shows what it will record.
    row = next(r for r in prepared.rows if r["canonical_key"] == "FAKE-A")
    assert {c["field"]: c.get("state") for c in row["fields"] if c["normalized"] is None} == {
        "maturity": "not_applicable",
        "standard_body": "pending_confirmation",
    }
    card_id = first["id"]
    unit = _state_units(a, vault_id)[f"state:{card_id}:maturity"]
    assert unit["state"] == "not_applicable"
    assert unit["raw"] == "n/a"
    assert unit["by"] == "alice"
    assert "origin" not in unit  # only a unit row reads back, so it needs no origin


def test_a_state_round_trips_and_a_repeat_stages_nothing(tmp_path: Path) -> None:
    _, vault_id, dataset, a, _ = _two_pcs(tmp_path)
    _csv(a, dataset)
    v = vault.Vault(a, vault_id)
    units = v.repo.working_units()
    held = {k: x for k, x in units.items() if k.startswith("state:")}
    assert len(held) == 3  # FAKE-A's two and FAKE-C's one
    with closing(sqlite3.connect(v.db_path)) as db:
        assert {k: x for k, x in vault.units_from_db(db).items() if k.startswith("state:")} == held
    # The same words again, even written differently, change nothing at all.
    before = v.repo.status()
    prepared = importer.preview(
        _store(a, dataset),
        entity_type="Technology",
        filename="again.csv",
        csv_text="技術,成熟度\nFAKE-A,N/A\n",
    )
    assert prepared.rows[0]["action"] == "unchanged"
    assert v.repo.working_units() == units
    with vault.capture(_store(a, dataset)):
        pass
    assert v.repo.status()["uncommitted"] == before["uncommitted"]


def test_a_value_stays_when_a_row_says_na_and_the_preview_lists_it(tmp_path: Path) -> None:
    _, _, dataset, a, _ = _two_pcs(tmp_path)
    _csv(a, dataset, "技術,成熟度\nFAKE-A,growth\n")
    prepared = _csv(a, dataset, "技術,成熟度\nFAKE-A,n/a\n")
    store = _store(a, dataset)
    card = store.find("Technology", "FAKE-A")
    assert card is not None
    assert store.fields(card["id"])["maturity"]["value"] == "growth"
    assert store.field_states(card["id"]) == {}
    assert prepared.rows[0]["action"] == "unchanged"
    assert [w["code"] for w in prepared.rows[0]["warnings"]] == ["state_value_kept"]


def test_a_later_value_clears_a_state(tmp_path: Path) -> None:
    _, vault_id, dataset, a, _ = _two_pcs(tmp_path)
    _csv(a, dataset, "技術,成熟度,標準組織\nFAKE-A,n/a,TBD\n")
    _csv(a, dataset, "技術,成熟度\nFAKE-A,growth\n")
    assert "maturity" not in _states(a, dataset, "FAKE-A")
    assert not [k for k in _state_units(a, vault_id) if k.endswith(":maturity")]
    # A proposal's accept writes through `set_field`, and clears it the same way.
    store = _store(a, dataset)
    card = store.find("Technology", "FAKE-A")
    assert card is not None
    store.set_field(
        card["id"], "standard_body", "IEEE", base_version=int(card["version"]), actor="alice"
    )
    assert "standard_body" not in _states(a, dataset, "FAKE-A")
    assert not [k for k in _state_units(a, vault_id) if k.endswith(":standard_body")]


def test_a_different_state_replaces_the_one_there(tmp_path: Path) -> None:
    _, _, dataset, a, _ = _two_pcs(tmp_path)
    _csv(a, dataset, "技術,成熟度\nFAKE-A,tbd\n")
    prepared = _csv(a, dataset, "技術,成熟度\nFAKE-A,n/a\n")
    assert prepared.rows[0]["action"] == "update"
    assert _states(a, dataset, "FAKE-A")["maturity"]["state"] == "not_applicable"


def test_undo_takes_the_imports_states_with_it(tmp_path: Path) -> None:
    _, vault_id, dataset, a, _ = _two_pcs(tmp_path)
    _csv(a, dataset, "技術,標準組織\nFAKE-A,IEEE\n")
    store = _store(a, dataset)
    result = store.apply(
        [PlannedRow(1, "Technology", "FAKE-A", "FAKE-A", {"name": "FAKE-A"}, False,
                    states={"maturity": {"state": "not_applicable", "raw": "n/a"}})],
        filename="later.csv", entity_type="Technology", actor="alice",
    )  # fmt: skip
    assert "maturity" in _states(a, dataset, "FAKE-A")
    store.undo_import(result.import_id, actor="alice")
    assert _states(a, dataset, "FAKE-A") == {}
    assert _state_units(a, vault_id) == {}


def test_a_state_reaches_the_other_pc_and_the_tables_agree(tmp_path: Path) -> None:
    drive, vault_id, dataset, a, b = _two_pcs(tmp_path)
    _csv(a, dataset)
    _push(a, vault_id)
    drive.deliver("a", "b", vault_id)
    _sync(b, vault_id)
    assert _states(b, dataset, "FAKE-A")["maturity"]["state"] == "not_applicable"
    assert _rows(a, vault_id) == _rows(b, vault_id)


def test_a_value_on_one_pc_beats_a_state_on_the_other_on_both(tmp_path: Path) -> None:
    drive, vault_id, dataset, a, b = _two_pcs(tmp_path)
    _csv(a, dataset, "技術,標準組織\nFAKE-A,IEEE\n")
    _push(a, vault_id)
    drive.deliver("a", "b", vault_id)
    _sync(b, vault_id)
    _csv(a, dataset, "技術,成熟度\nFAKE-A,n/a\n")
    _csv(b, dataset, "技術,成熟度\nFAKE-A,growth\n")
    _push(a, vault_id)
    drive.deliver("a", "b", vault_id)
    _sync(b, vault_id)
    _push(b, vault_id)
    drive.deliver("b", "a", vault_id)
    _sync(a, vault_id)
    for ws in (a, b):
        store = _store(ws, dataset)
        card = store.find("Technology", "FAKE-A")
        assert card is not None
        assert store.fields(card["id"])["maturity"]["value"] == "growth"
        assert store.field_states(card["id"]) == {}
    assert _rows(a, vault_id) == _rows(b, vault_id)


def test_a_pending_proposal_on_an_empty_field_awaits_confirmation(tmp_path: Path) -> None:
    _, vault_id, dataset, a, _ = _two_pcs(tmp_path)
    store = _store(a, dataset)
    store.apply(
        [PlannedRow(1, "Technology", "FAKE-A", "FAKE-A", {"name": "FAKE-A", "maturity": "growth"},
                    False, propose=frozenset({"maturity"}))],
        filename="t.csv", entity_type="Technology", actor="alice",
    )  # fmt: skip
    state = _states(a, dataset, "FAKE-A")["maturity"]
    assert state["state"] == "pending_confirmation"
    assert state["origin"] == "proposal"
    # Computed at rebuild, so it never becomes a unit, and nothing is staged by it.
    assert _state_units(a, vault_id) == {}
    card = store.find("Technology", "FAKE-A")
    assert card is not None
    proposal = store.proposals(card["id"])[0]
    answer = _call(
        a, "POST", f"/api/bi/cards/{card['id']}/proposals/{proposal['id']}",
        {"dataset": dataset, "action": "accept", "base_version": int(card["version"]),
         "reason": "the source says so"},
    )  # fmt: skip
    assert answer[0] == 200, answer[1]
    assert _states(a, dataset, "FAKE-A") == {}


def test_an_explicit_state_stays_beside_a_pending_proposal(tmp_path: Path) -> None:
    _, _, dataset, a, _ = _two_pcs(tmp_path)
    _csv(a, dataset, "技術,成熟度\nFAKE-A,n/a\n")
    _store(a, dataset).apply(
        [PlannedRow(1, "Technology", "FAKE-A", "FAKE-A", {"name": "FAKE-A", "maturity": "growth"},
                    False, propose=frozenset({"maturity"}))],
        filename="t.csv", entity_type="Technology", actor="alice",
    )  # fmt: skip
    state = _states(a, dataset, "FAKE-A")["maturity"]
    assert (state["state"], state["origin"]) == ("not_applicable", "unit")


def test_a_card_page_says_it_and_a_later_page_on_the_card_does_not_undo_a_value(
    tmp_path: Path,
) -> None:
    _, _, dataset, a, _ = _two_pcs(tmp_path)
    page = "---\ntype: technology\nname: FAKE-A\nmaturity: n/a\nstandard_body: 待定\n---\n"
    made = _preview(a, dataset, [{"path": "a.md", "text": page}])
    _apply(a, made["preview_id"])
    states = _states(a, dataset, "FAKE-A")
    assert states["maturity"]["state"] == "not_applicable"
    assert states["standard_body"]["state"] == "pending_confirmation"
    # A new state on a card with nothing else new is still a write.
    again = "---\ntype: technology\nname: FAKE-A\nmaturity: tbd\nstandard_body: 待定\n---\n"
    made = _preview(a, dataset, [{"path": "b.md", "text": again}])
    assert made["types"][0]["rows"][0]["action"] == "update"
    assert made["types"][0]["rows"][0]["merge"]["state"] == ["maturity"]
    assert made["summary"]["merge"]["state"] == 1
    _apply(a, made["preview_id"])
    assert _states(a, dataset, "FAKE-A")["maturity"]["state"] == "pending_confirmation"
    filled = "---\ntype: technology\nname: FAKE-A\nmaturity: growth\n---\n"
    _apply(a, _preview(a, dataset, [{"path": "c.md", "text": filled}])["preview_id"])
    late = "---\ntype: technology\nname: FAKE-A\nmaturity: n/a\n---\n"
    _apply(a, _preview(a, dataset, [{"path": "d.md", "text": late}])["preview_id"])
    assert "maturity" not in _states(a, dataset, "FAKE-A")


def test_a_page_marked_differently_from_its_card_records_no_state(tmp_path: Path) -> None:
    _, _, dataset, a, _ = _two_pcs(tmp_path)
    real = "---\ntype: technology\nname: FAKE-A\nstandard_body: IEEE\n---\n"
    _apply(a, _preview(a, dataset, [{"path": "a.md", "text": real}])["preview_id"])
    sample = "---\ntype: technology\nname: FAKE-A\nmaturity: n/a\nnote: (虛構範例)\n---\n"
    prepared = _preview(a, dataset, [{"path": "b.md", "text": sample}])
    assert prepared["mark_conflicts"]
    _apply(a, prepared["preview_id"])
    assert "maturity" not in _states(a, dataset, "FAKE-A")


def test_a_csv_run_carries_a_state_through_review(tmp_path: Path) -> None:
    _, _, dataset, a, _ = _two_pcs(tmp_path)
    run, detail = _rule_run(a, dataset, "技術,成熟度\nFAKE-A,n/a\n")
    candidate = detail["candidates"][0]
    assert candidate["states"]["maturity"]["state"] == "not_applicable"
    _ok(_call(a, "POST", f"/api/bi/runs/{run['id']}/candidates/{candidate['id']}",
              {"dataset": dataset, "review": "accepted"}))  # fmt: skip
    _ok(_call(a, "POST", f"/api/bi/runs/{run['id']}/commit", {"dataset": dataset}))
    assert _states(a, dataset, "FAKE-A")["maturity"]["state"] == "not_applicable"


def test_a_state_only_row_on_a_known_card_is_writable_in_a_run(tmp_path: Path) -> None:
    _, _, dataset, a, _ = _two_pcs(tmp_path)
    _csv(a, dataset, "技術,標準組織\nFAKE-A,IEEE\n")
    _, detail = _rule_run(a, dataset, "技術,成熟度\nFAKE-A,tbd\n")
    assert detail["candidates"][0]["action"] == "update"


def test_a_recipe_candidate_holds_the_state_and_a_later_row_merges_it(tmp_path: Path) -> None:
    _, _, dataset, a, _ = _two_pcs(tmp_path)
    store = _store(a, dataset)
    reg = for_store(store)
    recipe = recipes.validate(
        {
            "name": "fictional",
            "passes": [
                {
                    "id": "p1",
                    "entity_type": "Technology",
                    "tables": "has:技術",
                    "mapping": {
                        "columns": {"技術": "name", "成熟度": "maturity", "組織": "standard_body"}
                    },
                }
            ],
        },
        reg,
    )
    table = {
        "index": 0,
        "title": "t",
        "columns": ["技術", "成熟度", "組織"],
        "locator": "line",
        "rows": [
            {"row": 2, "cells": {"技術": "FAKE-A", "成熟度": "n/a", "組織": ""}},
            {"row": 3, "cells": {"技術": "FAKE-A", "成熟度": "", "組織": "tbd"}},
            {"row": 4, "cells": {"技術": "FAKE-B", "成熟度": "", "組織": "nan"}},
        ],
    }
    found, _ = recipes.build(store, reg, recipe, [table], source_id="s", filename="r.md")
    by_key = {c["canonical_key"]: c for c in found}
    assert {k: v["state"] for k, v in by_key["FAKE-A"]["states"].items()} == {
        "maturity": "not_applicable",
        "standard_body": "pending_confirmation",
    }
    assert by_key["FAKE-B"]["states"] == {}


def test_bi_query_tells_not_applicable_from_unknown(tmp_path: Path) -> None:
    _, _, dataset, a, _ = _two_pcs(tmp_path)
    _csv(a, dataset)
    answer = service.query_cards(
        _store(a, dataset),
        entity_type="Technology",
        text=None,
        domain=None,
        field=None,
        value=None,
        follow_links=False,
        limit=10,
    )
    cards = {c["name"]: c for c in answer["cards"]}
    assert cards["FAKE-A"]["field_states"]["maturity"] == {
        "state": "not_applicable",
        "origin": "unit",
    }
    assert cards["FAKE-B"]["field_states"] == {}  # an empty field not listed is unknown
    assert "field_states" in manifest.PROCEDURE and "未知" in manifest.PROCEDURE


def test_a_plain_dataset_keeps_its_new_tables_empty(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    _ok(_call(ws, "POST", "/api/bi/datasets", {"name": "lab", "schema": "bi.schema/v1.1"}))
    store = BiStore(ws, "lab")
    prepared = importer.preview(
        store, entity_type="Technology", filename="t.csv", csv_text="技術,成熟度\nFAKE-A,n/a\n"
    )
    importer.apply(store, prepared, None, actor="x")
    card = store.find("Technology", "FAKE-A")
    assert card is not None
    assert store.field_states(card["id"]) == {}


def test_a_state_unit_is_named_for_the_person(tmp_path: Path) -> None:
    units = {"card:abc": {"type": "Technology", "key": "FAKE-A", "name": "FAKE-A"}}
    assert vault.unit_label(units, "state:abc:maturity") == "Technology「FAKE-A」 的 maturity 狀態"


def test_a_row_for_a_card_gone_from_the_units_is_dropped(tmp_path: Path) -> None:
    _, vault_id, dataset, a, _ = _two_pcs(tmp_path)
    _csv(a, dataset)
    v = vault.Vault(a, vault_id)
    card = _store(a, dataset).find("Technology", "FAKE-A")
    assert card is not None
    with closing(sqlite3.connect(v.db_path)) as db:
        units = vault.units_from_db(db)
        without = {k: x for k, x in units.items() if not k.endswith(card["id"])}
        vault.materialize(db, without, [], [])
        left = [r[0] for r in db.execute("SELECT card_id FROM field_states")]
    assert card["id"] not in left
