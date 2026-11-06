"""The BI card model's storage shape (`docs/phases/BI_CARD_MODEL.md` §3, task T1).

Later work builds on these ids, units and tables, so the hashes are pinned here:
two PCs, and a commit written today and read next year, must agree. All data is
fictional.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

import pytest
from test_bi_vault import _commit, _push, _row, _sync, _two_pcs

from capabilities.bi_cards import card_model, catalog, schema_versions, vault
from capabilities.bi_cards.schema import Registry
from capabilities.bi_cards.store import BiStore
from knowledge.repo.repository import RepoError
from scripts.build_bi_schema_v5 import ADDED, OUT, build

V4, V5 = "bi.schema/v1.1@4.0.0", "bi.schema/v1.1@5.0.0"
NEW_TABLES = {"relations", "relation_evidence", "field_states", "card_names", "card_app_folders"}
EVIDENCE_ADDED = {"reference_id", "stance", "reference_at", "reference_time_basis"}
RELATION = {
    "from": "aaa",
    "type": "requires_test",
    "to": "bbb",
    "origin": "ai_inferred",
    "status": "confirmed",
}


def _names(db: sqlite3.Connection) -> set[str]:
    return {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}


def _columns(db: sqlite3.Connection, table: str) -> set[str]:
    return {r[1] for r in db.execute(f"PRAGMA table_info({table})")}


def test_ids_are_pinned_and_a_hash_of_what_they_name() -> None:
    assert card_model.relation_id("aaa", "has_supplier", "bbb") == "59a5dc35a5e9"
    assert card_model.reference_id("src", {"line": 3, "key": "name"}) == "e3f3c0bb384e"
    assert card_model.evidence_link_id("r", "c", "x") == "f7ae0826e145"
    # A locator's key order is not part of its identity.
    assert card_model.reference_id("s", {"a": 1, "b": 2}) == card_model.reference_id(
        "s", {"b": 2, "a": 1}
    )
    assert card_model.default_relation_type("supplier") == "has_supplier"


def test_a_stored_link_renders_the_current_name_and_text_as_written() -> None:
    item = card_model.link_item("aaa", "Old Name")
    assert card_model.render_link(item, {"aaa": "New Name"}) == "New Name"
    assert card_model.render_link(item, {}) == "Old Name"  # the card is gone
    assert card_model.render_link("as typed", {"aaa": "New Name"}) == "as typed"
    assert card_model.render_link([item, "text"], {"aaa": "N"}) == ["N", "text"]


@pytest.mark.parametrize(
    ("key", "value", "problem"),
    [
        ("state:c:f", {"state": "not_applicable"}, None),
        ("state:c:f", {"state": "n/a"}, "state unknown"),
        ("state:c", {"state": "unknown"}, "state key is state:<card>:<field>"),
        ("relation:r", RELATION, None),
        ("relation:r", {**RELATION, "status": "maybe"}, "relation status unknown"),
        ("relation:r", {**RELATION, "origin": "x"}, "relation origin unknown"),
        ("relation:r", {"from": "aaa"}, "relation needs from, type and to"),
        (
            "relation_evidence:l",
            {"relation": "r", "basis_card": "c", "reference_id": "x", "stance": "refutes"},
            None,
        ),
        (
            "relation_evidence:l",
            {"relation": "r", "basis_card": "c", "reference_id": "x", "stance": "?"},
            "stance unknown",
        ),
        ("profile:aidc", {"revision": 1, "author": "a", "path": "p", "sha256": "s"}, None),
        (
            "tool:aidc/x",
            {"revision": 0, "author": "a", "path": "p", "sha256": "s"},
            "revision must be a positive number",
        ),
        ("relation:r", "text", "value must be an object"),
    ],
)
def test_the_type_checks_each_new_unit(key: str, value: Any, problem: str | None) -> None:
    assert vault.BiType().unit_problem(key, value) == problem


def test_the_shipped_5_0_0_is_generated_and_only_adds(tmp_path: Path) -> None:
    assert json.loads(OUT.read_text(encoding="utf-8")) == build()
    old, new = catalog.resolve(tmp_path, V4), catalog.resolve(tmp_path, V5)
    assert catalog.resolve(tmp_path, "bi.schema/v1.1").version == "5.0.0"
    changes = schema_versions.diff(old.document, new.document)
    assert {c["change"] for c in changes} == {"field_added"}
    assert not any(c["breaking"] for c in changes)
    # 21 types × 5 fields, less the `summary` that Signal and VisitLog already have.
    assert len(changes) == 21 * len(ADDED) - 2
    for entity in new.types.values():
        for name, *_ in ADDED:
            item = entity.get(name)
            assert item is not None
            assert not item.required or (name, entity.name) in (
                ("summary", "Signal"),
                ("summary", "VisitLog"),
            )
    signal = new.types["Signal"].get("summary")
    assert signal is not None and signal.klass == "sourced"
    assert not any(e.get("event_date") or e.get("priority") for e in new.types.values())
    assert [r["name"] for r in new.relation_types] == ["requires_test"]


def test_the_validator_keeps_the_new_keys_and_refuses_bad_ones() -> None:
    document = build()
    entity = next(t for t in document["types"] if t["name"] == "SupplyLink")
    supplier = next(f for f in entity["fields"] if f["name"] == "supplier")
    summary = next(f for f in entity["fields"] if f["name"] == "summary")
    supplier.update(relation_type="supplied_by", used_by=["aidc"])
    normalised, errors = catalog.validate(document)
    assert errors == [] and normalised is not None
    kept = next(t for t in normalised["types"] if t["name"] == "SupplyLink")
    found = next(f for f in kept["fields"] if f["name"] == "supplier")
    assert found["relation_type"] == "supplied_by" and found["used_by"] == ["aidc"]
    other = next(f for f in kept["fields"] if f["name"] == "summary")
    assert "relation_type" not in other and "used_by" not in other  # none means no key
    item = Registry(normalised).types["SupplyLink"].get("supplier")
    assert item is not None and item.relation_type == "supplied_by" and item.used_by == ("aidc",)

    summary["relation_type"] = "nope"
    document["relation_types"] = [
        {"name": "x", "label": "x", "from": ["NoSuchType"], "to": ["Account"]},
        {"name": "x", "label": "x", "from": ["Account"], "to": []},
    ]
    _, errors = catalog.validate(document)
    paths = {e["path"] for e in errors}
    assert "relation_types[0].from" in paths and "relation_types[1].name" in paths
    assert "relation_types[1].to" in paths
    assert any(p.endswith(".relation_type") for p in paths)


def test_a_local_dataset_gets_the_tables_and_an_older_one_the_columns(tmp_path: Path) -> None:
    store = BiStore(tmp_path, "lab")
    store.apply([_row("FAKE-OLD")], filename="t.csv", entity_type="Technology", actor="x")
    with closing(sqlite3.connect(store.path)) as db:
        assert NEW_TABLES <= _names(db) and EVIDENCE_ADDED <= _columns(db, "evidence")
        # As a dataset from before the card model.
        db.execute("DROP TABLE evidence")
        db.execute(
            "CREATE TABLE evidence (seq INTEGER PRIMARY KEY AUTOINCREMENT, card_id TEXT, "
            "field TEXT, run_id TEXT, source_id TEXT, source_name TEXT, locator TEXT, "
            "excerpt TEXT, basis TEXT, at TEXT)"
        )
        db.execute(
            "INSERT INTO evidence (card_id, field, run_id, source_id, source_name, locator, "
            "excerpt, basis, at) VALUES ('c', 'f', 'r', 's', 'n', '{}', 'e', 'fact', 't')"
        )
        for table in NEW_TABLES:
            db.execute(f"DROP TABLE {table}")
        db.commit()
    store.apply([_row("FAKE-NEW")], filename="t.csv", entity_type="Technology", actor="x")
    with closing(sqlite3.connect(store.path)) as db:
        assert NEW_TABLES <= _names(db) and EVIDENCE_ADDED <= _columns(db, "evidence")
        row = db.execute("SELECT stance, reference_id, excerpt FROM evidence").fetchone()
        assert row == ("supports", "", "e")  # the old row stays


def test_an_older_local_database_of_a_vault_rebuilds_once(tmp_path: Path) -> None:
    _, _, dataset, a, _ = _two_pcs(tmp_path)
    store = BiStore(a, dataset)
    store.apply([_row("FAKE-CARD")], filename="t.csv", entity_type="Technology", actor="alice")
    with closing(sqlite3.connect(store.path)) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == card_model.MODEL_VERSION
        for table in NEW_TABLES:
            db.execute(f"DROP TABLE {table}")
        db.execute("PRAGMA user_version = 0")
        db.commit()
    again = BiStore(a, dataset)
    with closing(sqlite3.connect(again.path)) as db:
        assert NEW_TABLES <= _names(db)
        assert db.execute("PRAGMA user_version").fetchone()[0] == card_model.MODEL_VERSION
    assert again.find("Technology", "FAKE-CARD") is not None


def test_the_published_copy_is_rebuilt_for_a_new_model(tmp_path: Path) -> None:
    _, vault_id, _, a, _ = _two_pcs(tmp_path)
    target = vault.Vault(a, vault_id)
    folder = target.refresh_published()
    marker = folder / "version.json"
    built = json.loads(marker.read_text(encoding="utf-8"))
    assert built["model"] == card_model.MODEL_VERSION
    # As a copy an older AEP built, without the model in its marker.
    del built["model"]
    marker.write_text(json.dumps(built), encoding="utf-8")
    with closing(sqlite3.connect(folder / "bi.sqlite")) as db:
        db.execute("DROP TABLE relations")
        db.commit()
    with closing(sqlite3.connect(target.refresh_published() / "bi.sqlite")) as db:
        assert "relations" in _names(db)


def test_new_units_travel_between_pcs_and_a_store_write_keeps_them(tmp_path: Path) -> None:
    drive, vault_id, dataset, a, b = _two_pcs(tmp_path)
    target = vault.Vault(a, vault_id)
    target.repo.stage_many(
        {
            "relation:r1": RELATION,
            "state:c1:f": {"state": "confirmed_none", "reason": "fictional"},
        }
    )
    # A store write captures only what it changed.
    store = BiStore(a, dataset)
    store.apply([_row("FAKE-CARD")], filename="t.csv", entity_type="Technology", actor="alice")
    assert target.repo.working_units()["relation:r1"] == RELATION
    # F19: the import commits its own units; unrelated staged work stays pending.
    assert target.repo._pending()["sets"]["relation:r1"] == RELATION
    assert target.repo._pending()["sets"]["state:c1:f"] == {
        "state": "confirmed_none",
        "reason": "fictional",
    }
    _push(a, vault_id)
    drive.deliver("a", "b", vault_id)
    _sync(b, vault_id)
    assert "relation:r1" not in vault.Vault(b, vault_id).repo.units()
    assert "state:c1:f" not in vault.Vault(b, vault_id).repo.units()
    assert target.repo._pending()["sets"]["relation:r1"] == RELATION
    # The person's next commit carries both units to their colleague.
    _commit(a, vault_id, "Confirm the staged relation")
    _push(a, vault_id)
    drive.deliver("a", "b", vault_id)
    _sync(b, vault_id)
    assert vault.Vault(b, vault_id).repo.units()["relation:r1"] == RELATION
    assert vault.Vault(b, vault_id).repo.units()["state:c1:f"] == {
        "state": "confirmed_none",
        "reason": "fictional",
    }
    # An invalid one is refused before it is staged.
    with pytest.raises(RepoError):
        target.repo.stage("relation:r2", {"from": "aaa"})
