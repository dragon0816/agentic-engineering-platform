"""References on evidence rows (`docs/phases/BI_CARD_MODEL.md` §3.5, task T6).

Two PCs as in `test_bi_vault.py`. A new row's unit holds its reference; a row
written before the card model keeps its unit as it was and gets its id at each
rebuild. All data is fictional.
"""

from __future__ import annotations

import copy
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

from test_bi_card_page_import import _apply, _preview
from test_bi_vault import _push, _sync, _two_pcs

from aep_bi.cards import card_model, extract, vault
from aep_bi.cards.schema import registry
from aep_bi.cards.store import BiStore, PlannedRow

LOCATOR = {"line": 3, "key": "maturity"}


def _commit_run(ws: Path, dataset: str, run_id: str = "run-1", **item: Any) -> None:
    proof = {
        "source_id": "src-1",
        "source_name": "fictional.md",
        "locator": LOCATOR,
        "excerpt": "growth",
        "basis": "fact",
        **item,
    }
    row = PlannedRow(
        row=1,
        entity_type="Technology",
        canonical_key="FAKE-A",
        name="FAKE-A",
        values={"name": "FAKE-A", "maturity": "growth"},
        synthetic=False,
        ref="run",
        evidence={"maturity": [proof]},
    )
    store = BiStore(ws, dataset)
    card = store.find("Technology", "FAKE-A")
    version = None if card is None else int(card["version"])
    store.commit_run(run_id, [(row, "c1", version)], filename="f.md", actor="alice")


def _unit(ws: Path, vault_id: str) -> tuple[str, list[dict[str, Any]]]:
    units = vault.Vault(ws, vault_id).repo.working_units()
    return next((k, v) for k, v in units.items() if k.startswith("evidence:"))


def test_a_new_row_holds_its_reference_and_round_trips(tmp_path: Path) -> None:
    _, vault_id, dataset, a, _ = _two_pcs(tmp_path)
    _commit_run(a, dataset)
    _, rows = _unit(a, vault_id)
    assert rows[0]["reference_id"] == card_model.reference_id("src-1", LOCATOR)
    assert rows[0]["stance"] == "supports"
    assert rows[0]["reference_at"] == rows[0]["at"]
    assert rows[0]["reference_time_basis"] == "submission_fallback"
    v = vault.Vault(a, vault_id)
    with closing(sqlite3.connect(v.db_path)) as db:
        read = vault.units_from_db(db, keep_ids=True)
    key, held = _unit(a, vault_id)
    assert read[key] == held


def test_a_source_date_is_the_reference_time_with_no_fallback_basis(tmp_path: Path) -> None:
    _, vault_id, dataset, a, _ = _two_pcs(tmp_path)
    _commit_run(a, dataset, reference_at="2026-03-01", stance="refutes")
    _, rows = _unit(a, vault_id)
    assert rows[0]["reference_at"] == "2026-03-01"
    assert "reference_time_basis" not in rows[0]
    assert rows[0]["stance"] == "refutes"
    card = BiStore(a, dataset).find("Technology", "FAKE-A")
    assert card is not None
    shown = BiStore(a, dataset).evidence(card["id"])[0]
    assert shown["stance"] == "refutes"
    assert shown["reference_at"] == "2026-03-01"
    assert shown["reference_time_basis"] is None


def test_an_unknown_stance_reads_as_supports(tmp_path: Path) -> None:
    _, vault_id, dataset, a, _ = _two_pcs(tmp_path)
    _commit_run(a, dataset, stance="maybe")
    assert _unit(a, vault_id)[1][0]["stance"] == "supports"


def test_an_old_row_keeps_its_unit_and_gets_its_id_at_rebuild(tmp_path: Path) -> None:
    _, vault_id, dataset, a, _ = _two_pcs(tmp_path)
    _commit_run(a, dataset)
    v = vault.Vault(a, vault_id)
    with closing(sqlite3.connect(v.db_path)) as db:
        units = vault.units_from_db(db, keep_ids=True)
        key = next(k for k in units if k.startswith("evidence:"))
        old = copy.deepcopy(units)
        for row in old[key]:
            for part in ("reference_id", "stance", "reference_at", "reference_time_basis"):
                row.pop(part, None)
        vault.materialize(db, old, [], [])
        stored = db.execute("SELECT reference_id, stance, reference_at FROM evidence").fetchone()
        assert stored[0] == card_model.reference_id("src-1", LOCATOR)
        assert stored[1] == "supports"
        assert stored[2] is None
        # Read back it is the same old unit, so a capture has nothing to stage.
        assert vault.units_from_db(db, keep_ids=True)[key] == old[key]


def test_the_reader_gives_an_old_row_the_same_four_keys(tmp_path: Path) -> None:
    _, vault_id, dataset, a, _ = _two_pcs(tmp_path)
    _commit_run(a, dataset)
    v = vault.Vault(a, vault_id)
    with closing(sqlite3.connect(v.db_path)) as db:
        db.execute("UPDATE evidence SET reference_at = NULL, reference_time_basis = NULL")
        db.commit()
    card = BiStore(a, dataset).find("Technology", "FAKE-A")
    assert card is not None
    shown = BiStore(a, dataset).evidence(card["id"])[0]
    assert shown["reference_id"] == card_model.reference_id("src-1", LOCATOR)
    assert shown["reference_at"] == shown["at"]
    assert shown["reference_time_basis"] == "submission_fallback"


def test_a_capture_with_no_change_stages_no_evidence(tmp_path: Path) -> None:
    _, vault_id, dataset, a, _ = _two_pcs(tmp_path)
    _commit_run(a, dataset)
    v = vault.Vault(a, vault_id)
    before = v.repo.working_units()
    with vault.capture(BiStore(a, dataset)):
        pass
    assert v.repo.working_units() == before
    assert v.repo.status()["uncommitted"] == 0


def test_a_withdrawal_blanking_an_excerpt_keeps_the_reference(tmp_path: Path) -> None:
    _, vault_id, dataset, a, _ = _two_pcs(tmp_path)
    _commit_run(a, dataset)
    v = vault.Vault(a, vault_id)
    with closing(sqlite3.connect(v.db_path)) as db:
        units = vault.units_from_db(db, keep_ids=True)
        key = next(k for k in units if k.startswith("evidence:"))
        wanted = units[key][0]["reference_id"]
        units[key][0]["excerpt"] = ""
        vault.materialize(db, units, [], [])
        assert db.execute("SELECT reference_id FROM evidence").fetchone()[0] == wanted


def test_two_pcs_agree_on_the_reference(tmp_path: Path) -> None:
    drive, vault_id, dataset, a, b = _two_pcs(tmp_path)
    _commit_run(a, dataset)
    _push(a, vault_id)
    drive.deliver("a", "b", vault_id)
    _sync(b, vault_id)
    assert _unit(a, vault_id) == _unit(b, vault_id)
    query = (
        "SELECT card_id, field, reference_id, stance, reference_at, reference_time_basis "
        "FROM evidence"
    )
    with closing(sqlite3.connect(vault.Vault(a, vault_id).db_path)) as one:
        with closing(sqlite3.connect(vault.Vault(b, vault_id).db_path)) as other:
            assert list(one.execute(query)) == list(other.execute(query))


def test_a_card_pages_own_date_dates_its_references(tmp_path: Path) -> None:
    _, _, dataset, a, _ = _two_pcs(tmp_path)
    page = "---\ntype: technology\nname: FAKE-A\nmaturity: growth\nupdated: 2026-02-03\n---\n"
    _apply(a, _preview(a, dataset, [{"path": "a.md", "text": page}])["preview_id"])
    undated = "---\ntype: technology\nname: FAKE-B\nmaturity: growth\n---\n"
    _apply(a, _preview(a, dataset, [{"path": "b.md", "text": undated}])["preview_id"])
    store = BiStore(a, dataset)
    dated_card, plain_card = store.find("Technology", "FAKE-A"), store.find("Technology", "FAKE-B")
    assert dated_card is not None and plain_card is not None
    dated = store.evidence(dated_card["id"])[0]
    assert (dated["reference_at"], dated["reference_time_basis"]) == ("2026-02-03", None)
    plain = store.evidence(plain_card["id"])[0]
    assert plain["reference_time_basis"] == "submission_fallback"
    assert plain["reference_at"] == plain["at"]
    assert dated["reference_id"] == card_model.reference_id(dated["source_id"], dated["locator"])


def test_the_model_sets_the_stance_and_a_bad_one_reads_as_supports() -> None:
    reg = registry()
    chunk = extract.chunks("FAKE-A 仍在 growth 階段。")[0]
    entity = reg.type("Technology")
    answer = {
        "name": "FAKE-A",
        "fields": {
            "name": {"value": "FAKE-A", "basis": "fact", "quote": "FAKE-A", "stance": "maybe"},
            "maturity": {
                "value": "growth",
                "basis": "fact",
                "quote": "growth",
                "stance": "refutes",
            },
        },
    }
    found = extract.candidate(reg, entity, answer, chunk, "src-1")
    stances = {f["field"]: f["evidence"][0]["stance"] for f in found["fields"]}
    assert stances == {"name": "supports", "maturity": "refutes"}
    assert '"stance"' in extract.SYSTEM and "context_only" in extract.SYSTEM
