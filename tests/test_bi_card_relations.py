"""Relations: derived from link fields, or units a person decided (`BI_CARD_MODEL.md` §3.3).

All data is fictional.
"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

from test_bi_card_links import ACME, OPP, _put, _rename, _row, _start
from test_bi_vault import _call, _commit, _ok, _push, _sync, _two_pcs

from aep_bi.cards import card_model, vault
from aep_bi.cards.schema import Registry
from aep_bi.cards.store import BiStore, card_id_for
from scripts.build_bi_schema_v5 import build

HAS_ACCOUNT = card_model.relation_id(OPP, "has_account", ACME)
PRODUCT = card_id_for("CustomerProduct", "FAKE-PRODUCT")
TEST = card_id_for("TestSolution", "FAKE-TEST")


def _rows(ws: Path, dataset: str, table: str = "relations") -> list[tuple[Any, ...]]:
    with closing(sqlite3.connect(BiStore(ws, dataset).path)) as db:
        return sorted(tuple(r) for r in db.execute(f"SELECT * FROM {table}"))  # noqa: S608


def _decide(ws: Path, vault_id: str, **given: Any) -> tuple[int, dict[str, Any]]:
    answer: tuple[int, dict[str, Any]] = _call(
        ws, "POST", f"/api/bi/vaults/{vault_id}/relations", given
    )
    return answer


def _inferable(ws: Path, dataset: str) -> None:
    _put(ws, dataset, _row("CustomerProduct", "FAKE-PRODUCT"), _row("TestSolution", "FAKE-TEST"))


def test_a_link_that_resolves_makes_a_relation_and_no_unit(tmp_path: Path) -> None:
    _, vault_id, dataset, a, _ = _start(tmp_path)
    store = BiStore(a, dataset)
    mine = store.relations(OPP)
    assert [(r["type"], r["direction"], r["other_name"], r["status"]) for r in mine] == [
        ("has_account", "out", "FAKE-ACME", "unreviewed"),
        ("has_competitors", "out", "FAKE-RIVAL", "unreviewed"),
    ]
    assert mine[0]["relation_id"] == HAS_ACCOUNT and mine[0]["source_field"] == "account"
    assert mine[0]["origin"] == "schema_field"
    # Read from the other end, for "who links to this".
    assert [(r["type"], r["direction"]) for r in store.relations(ACME)] == [("has_account", "in")]
    # FAKE-NONE has no card: no relation, and nothing invented for it.
    assert not [r for r in mine if r["other_name"] == "FAKE-NONE"]
    units = vault.Vault(a, vault_id).repo.working_units()
    assert not [k for k in units if k.startswith("relation")]


def test_a_rename_keeps_the_relation_and_a_new_card_completes_a_text_link(tmp_path: Path) -> None:
    _, _, dataset, a, _ = _start(tmp_path)
    _rename(a, dataset, ACME, "FAKE-ACME-NEW")
    found = BiStore(a, dataset).relations(OPP)[0]
    assert found["relation_id"] == HAS_ACCOUNT and found["other_name"] == "FAKE-ACME-NEW"
    # The text link gets its relation when its card arrives.
    _put(a, dataset, _row("Competitor", "FAKE-NONE"))
    assert "FAKE-NONE" in {r["other_name"] for r in BiStore(a, dataset).relations(OPP)}


def test_a_field_may_name_its_relation() -> None:
    document = build()
    entity = next(t for t in document["types"] if t["name"] == "Opportunity")
    next(f for f in entity["fields"] if f["name"] == "account")["relation_type"] = "sold_to"
    reg = Registry(document)
    with closing(sqlite3.connect(":memory:", isolation_level=None)) as db:
        units = {
            "card:acc": {"type": "Account", "key": "A", "name": "A", "synthetic": False},
            "card:opp": {"type": "Opportunity", "key": "O", "name": "O", "synthetic": False},
            "field:opp:account": {"value": {"card": "acc", "name": "A"}, "source": None},
            "relation:gone": {
                "from": "nobody",
                "type": "requires_test",
                "to": "acc",
                "origin": "registered",
                "status": "confirmed",
            },
        }
        vault.materialize(db, units, [], [], reg)
        rows = db.execute("SELECT relation_id, relation_type FROM relations").fetchall()
    assert [tuple(r) for r in rows] == [
        (card_model.relation_id("opp", "sold_to", "acc"), "sold_to")
    ]


def test_a_registered_relation_travels_and_evidence_adds_without_conflict(tmp_path: Path) -> None:
    drive, vault_id, dataset, a, b = _two_pcs(tmp_path)
    _inferable(a, dataset)
    _push(a, vault_id)
    drive.deliver("a", "b", vault_id)
    _sync(b, vault_id)

    relation = {"from": PRODUCT, "type": "requires_test", "to": TEST, "status": "confirmed"}
    decided = _ok(
        _decide(
            a,
            vault_id,
            **relation,
            origin="ai_inferred",
            evidence=[{"reference_id": "ref-a"}],
        )
    )
    rid = card_model.relation_id(PRODUCT, "requires_test", TEST)
    assert decided["relation_id"] == rid
    _commit(a, vault_id, "Confirm a fictional relation")
    _push(a, vault_id)
    drive.deliver("a", "b", vault_id)
    _sync(b, vault_id)
    assert _rows(a, dataset) == _rows(b, dataset)
    assert _rows(a, dataset, "relation_evidence") == _rows(b, dataset, "relation_evidence")

    # Both add evidence to the relation they both see: no conflict.
    _ok(
        _decide(a, vault_id, **relation, origin="ai_inferred", evidence=[{"reference_id": "ref-b"}])
    )
    second = _ok(
        _decide(b, vault_id, **relation, origin="ai_inferred", evidence=[{"reference_id": "ref-c"}])
    )
    assert not [k for k in second["staged"] if k.startswith("relation:")]
    _commit(a, vault_id, "Add evidence")
    _commit(b, vault_id, "Add other evidence")
    assert _push(a, vault_id)["status"] == "pushed"
    drive.deliver("a", "b", vault_id)
    assert _push(b, vault_id)["status"] == "pushed"
    drive.deliver("b", "a", vault_id)
    _sync(a, vault_id)
    found = BiStore(a, dataset).relations(PRODUCT)[0]
    assert {e["reference_id"] for e in found["evidence"]} == {"ref-a", "ref-b", "ref-c"}


def test_a_decision_is_checked_against_the_schema(tmp_path: Path) -> None:
    _, vault_id, dataset, a, _ = _start(tmp_path)
    _inferable(a, dataset)
    good = {"from": PRODUCT, "type": "requires_test", "to": TEST, "status": "confirmed"}
    for change, code in (
        ({"type": "invented"}, "relation_type_unknown"),
        ({"from": ACME}, "relation_type_mismatch"),
        ({"to": "nosuchcard"}, "card_unknown"),
        ({"status": "unreviewed"}, "relation_status_invalid"),
        ({"origin": "schema_field"}, "relation_origin_invalid"),
        ({"origin": "ai_inferred"}, "relation_evidence_required"),
        ({"evidence": [{"reference_id": "r", "stance": "maybe"}]}, "relation_evidence_invalid"),
        ({"evidence": [{}]}, "relation_evidence_invalid"),
    ):
        status, body = _decide(a, vault_id, **{**good, **change})
        assert status in (400, 404) and body["code"] == code, change
    assert not vault.Vault(a, vault_id).repo._pending()["sets"]


def test_a_derived_relation_takes_a_status_and_a_rejected_one_is_hidden(tmp_path: Path) -> None:
    _, vault_id, dataset, a, _ = _start(tmp_path)
    _push(a, vault_id)
    relation = {"from": OPP, "type": "has_account", "to": ACME}
    _ok(_decide(a, vault_id, **relation, status="confirmed"))
    found = BiStore(a, dataset).relations(OPP)[0]
    assert (found["status"], found["origin"], found["source_field"]) == (
        "confirmed",
        "schema_field",
        "account",
    )
    _ok(_decide(a, vault_id, **relation, status="rejected"))
    assert HAS_ACCOUNT not in {r["relation_id"] for r in BiStore(a, dataset).relations(OPP)}
    # It stays a unit, so a re-run does not ask again.
    units = vault.Vault(a, vault_id).repo.working_units()
    assert units[f"relation:{HAS_ACCOUNT}"]["status"] == "rejected"


def test_the_card_detail_carries_relations_and_a_local_dataset_has_none(tmp_path: Path) -> None:
    _, _, dataset, a, _ = _start(tmp_path)
    detail = _ok(_call(a, "GET", f"/api/bi/cards/{OPP}", dataset=dataset))
    assert [r["type"] for r in detail["relations"]] == ["has_account", "has_competitors"]
    local = BiStore(tmp_path / "local", "lab")
    local.apply([_row("Account", "FAKE-L")], filename="t.csv", entity_type="Account", actor="x")
    assert local.relations("nothing") == []
