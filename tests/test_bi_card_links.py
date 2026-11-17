"""Links are stored by card id and shown as names (`docs/phases/BI_CARD_MODEL.md` §3.2).

All data is fictional.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

from test_bi_vault import _call, _commit, _Drive, _ok, _push, _sync, _two_pcs

from aep_bi.cards import card_model, catalog, quality, vault
from aep_bi.cards.store import BiStore, PlannedRow, card_id_for

ACME = card_id_for("Account", "FAKE-ACME")
OPP = card_id_for("Opportunity", "FAKE-OPP")


def _row(kind: str, key: str, **values: Any) -> PlannedRow:
    return PlannedRow(
        row=1,
        entity_type=kind,
        canonical_key=key,
        name=key,
        values={"name": key, **values},
        synthetic=False,
    )


def _put(ws: Path, dataset: str, *rows: PlannedRow) -> None:
    BiStore(ws, dataset).apply(list(rows), filename="t.csv", entity_type="Account", actor="alice")


def _unit(ws: Path, vault_id: str, key: str) -> Any:
    return vault.Vault(ws, vault_id).repo.working_units()[key]


def _shown(ws: Path, dataset: str, card: str, field: str) -> Any:
    return BiStore(ws, dataset).fields(card)[field]["value"]


def _rename(ws: Path, dataset: str, card: str, name: str) -> None:
    found = BiStore(ws, dataset).card(card)
    assert found is not None
    _ok(
        _call(
            ws,
            "POST",
            f"/api/bi/cards/{card}/rename",
            {
                "dataset": dataset,
                "name": name,
                "base_version": found["version"],
                "reason": "the vendor renamed it",
            },
        )
    )


def _start(tmp_path: Path) -> tuple[Any, str, str, Path, Path]:
    made = _two_pcs(tmp_path)
    _, _, dataset, a, _ = made
    _put(
        a,
        dataset,
        _row("Account", "FAKE-ACME"),
        _row("Competitor", "FAKE-RIVAL"),
        _row(
            "Opportunity", "FAKE-OPP", account="FAKE-ACME", competitors=["FAKE-RIVAL", "FAKE-NONE"]
        ),
    )
    return made


def test_a_link_is_stored_by_id_and_shown_as_a_name(tmp_path: Path) -> None:
    _, vault_id, dataset, a, _ = _start(tmp_path)
    rival = card_id_for("Competitor", "FAKE-RIVAL")
    assert _unit(a, vault_id, f"field:{OPP}:account")["value"] == {
        "card": ACME,
        "name": "FAKE-ACME",
    }
    # An item no card answers stays text, in its place.
    assert _unit(a, vault_id, f"field:{OPP}:competitors")["value"] == [
        {"card": rival, "name": "FAKE-RIVAL"},
        "FAKE-NONE",
    ]
    assert _shown(a, dataset, OPP, "account") == "FAKE-ACME"
    assert _shown(a, dataset, OPP, "competitors") == ["FAKE-RIVAL", "FAKE-NONE"]
    # Not a link field: an equal text stays text.
    _put(a, dataset, _row("Account", "FAKE-TEXT", body="FAKE-ACME"))
    other = card_id_for("Account", "FAKE-TEXT")
    assert _unit(a, vault_id, f"field:{other}:body")["value"] == "FAKE-ACME"


def test_a_rename_reaches_the_links_without_touching_their_cards(tmp_path: Path) -> None:
    drive, vault_id, dataset, a, b = _start(tmp_path)
    _push(a, vault_id)
    drive.deliver("a", "b", vault_id)
    _sync(b, vault_id)
    before = _unit(a, vault_id, f"field:{OPP}:account")

    _rename(a, dataset, ACME, "FAKE-ACME-NEW")
    staged = set(vault.Vault(a, vault_id).repo._pending()["sets"])
    assert not any(OPP in key for key in staged)  # nothing on the card linking to it
    assert _unit(a, vault_id, f"field:{OPP}:account") == before
    assert _shown(a, dataset, OPP, "account") == "FAKE-ACME-NEW"

    # The other PC changes the linking card meanwhile: no conflict with the rename.
    _put(b, dataset, _row("Opportunity", "FAKE-OPP", deal_stage="won"))
    _push(b, vault_id)
    drive.deliver("b", "a", vault_id)
    _commit(a, vault_id, "Rename a fictional account")
    assert _push(a, vault_id)["status"] == "pushed"
    drive.deliver("a", "b", vault_id)
    _sync(b, vault_id)
    assert _shown(b, dataset, OPP, "account") == "FAKE-ACME-NEW"


def test_a_capture_with_no_change_to_a_link_keeps_its_unit(tmp_path: Path) -> None:
    _, vault_id, dataset, a, _ = _start(tmp_path)
    _push(a, vault_id)
    # Stored as text by an older AEP, which must stay text until the value changes.
    target = vault.Vault(a, vault_id)
    old = {**_unit(a, vault_id, f"field:{OPP}:account"), "value": "FAKE-ACME"}
    target.repo.stage(f"field:{OPP}:account", old)
    target.rebuild()
    _put(a, dataset, _row("Opportunity", "FAKE-OPP", deal_stage="won"))
    assert _unit(a, vault_id, f"field:{OPP}:account")["value"] == "FAKE-ACME"
    # A real change is stored by id.
    _put(a, dataset, _row("Account", "FAKE-OTHER"))
    store = BiStore(a, dataset)
    card = store.card(OPP)
    assert card is not None
    store.set_field(OPP, "account", "FAKE-OTHER", base_version=card["version"], actor="alice")
    assert _unit(a, vault_id, f"field:{OPP}:account")["value"] == {
        "card": card_id_for("Account", "FAKE-OTHER"),
        "name": "FAKE-OTHER",
    }


def test_only_a_single_answer_of_the_right_type_makes_an_id(tmp_path: Path) -> None:
    _, vault_id, dataset, a, _ = _two_pcs(tmp_path)
    _put(
        a,
        dataset,
        _row("Account", "FAKE-SAME"),
        _row("Competitor", "FAKE-SAME"),
        _row("Account", "FAKE-ONLY-ACCOUNT"),
    )
    _put(a, dataset, _row("Opportunity", "FAKE-O1", account="FAKE-SAME"))
    o1 = card_id_for("Opportunity", "FAKE-O1")
    assert _unit(a, vault_id, f"field:{o1}:account")["value"] == {
        "card": card_id_for("Account", "FAKE-SAME"),
        "name": "FAKE-SAME",
    }
    # `lost_to` links to Competitor only: an Account of that name is no answer.
    _put(a, dataset, _row("Opportunity", "FAKE-O2", lost_to="FAKE-ONLY-ACCOUNT"))
    o2 = card_id_for("Opportunity", "FAKE-O2")
    assert _unit(a, vault_id, f"field:{o2}:lost_to")["value"] == "FAKE-ONLY-ACCOUNT"
    # `Signal.related` links to any type: two answers is no answer.
    signal = PlannedRow(
        row=1,
        entity_type="Signal",
        canonical_key="2026-01-02-FAKE-S",
        name="FAKE-S",
        values={"date": "2026-01-02", "title": "FAKE-S", "related": ["FAKE-SAME"]},
        synthetic=False,
    )
    _put(a, dataset, signal)
    s = card_id_for("Signal", "2026-01-02-FAKE-S")
    assert _unit(a, vault_id, f"field:{s}:related")["value"] == ["FAKE-SAME"]


def test_a_link_through_an_alias_or_a_former_name_makes_an_id(tmp_path: Path) -> None:
    _, vault_id, dataset, a, _ = _two_pcs(tmp_path)
    _put(a, dataset, _row("Account", "FAKE-ACME", aliases=["FAKE-ACME-INC"]))
    _put(a, dataset, _row("Opportunity", "FAKE-O1", account="FAKE-ACME-INC"))
    o1 = card_id_for("Opportunity", "FAKE-O1")
    assert _unit(a, vault_id, f"field:{o1}:account")["value"]["card"] == ACME
    assert _shown(a, dataset, o1, "account") == "FAKE-ACME"  # its current name

    _rename(a, dataset, ACME, "FAKE-ACME-NEW")
    _put(a, dataset, _row("Opportunity", "FAKE-O2", account="FAKE-ACME"))
    o2 = card_id_for("Opportunity", "FAKE-O2")
    assert _unit(a, vault_id, f"field:{o2}:account")["value"]["card"] == ACME


def test_text_links_are_shown_as_written_and_a_quality_check_resolves_them(tmp_path: Path) -> None:
    _, vault_id, dataset, a, _ = _start(tmp_path)
    target = vault.Vault(a, vault_id)
    old = {**_unit(a, vault_id, f"field:{OPP}:account"), "value": "FAKE-ACME"}
    target.repo.stage(f"field:{OPP}:account", old)
    target.rebuild()
    _rename(a, dataset, ACME, "FAKE-ACME-NEW")
    assert _shown(a, dataset, OPP, "account") == "FAKE-ACME"  # as written, as analyses saw it

    store = BiStore(a, dataset)
    report = quality.check(store, catalog.for_store(store))
    found = next(c for c in report["checks"] if c["id"] == "link_unresolved")
    said = json.dumps(found, ensure_ascii=False)
    assert "FAKE-ACME」" not in said  # resolved through its former name
    assert "FAKE-NONE" in said  # the check still finds what is really missing


def test_a_person_never_sees_a_raw_link(tmp_path: Path) -> None:
    drive, vault_id, dataset, a, b = _start(tmp_path)
    _put(a, dataset, _row("Account", "FAKE-A2"), _row("Account", "FAKE-B2"))
    _push(a, vault_id)
    drive.deliver("a", "b", vault_id)
    _sync(b, vault_id)

    for ws, new in ((a, "FAKE-A2"), (b, "FAKE-B2")):
        store = BiStore(ws, dataset)
        card = store.card(OPP)
        assert card is not None
        store.set_field(OPP, "account", new, base_version=card["version"], actor="alice")
    pending = _ok(_call(a, "GET", f"/api/bi/vaults/{vault_id}/pending"))
    assert '"card"' not in json.dumps(pending["uncommitted"][0]["after"]["value"])

    _commit(b, vault_id, "Change an account")
    _push(b, vault_id)
    drive.deliver("b", "a", vault_id)
    _commit(a, vault_id, "Change an account too")
    pushed = _push(a, vault_id)
    assert pushed["status"] == "conflicts"
    assert '{"card"' not in json.dumps(pushed["conflicts"])

    history = BiStore(a, dataset).history(OPP)
    assert '{"card"' not in json.dumps(history)
    with closing(sqlite3.connect(BiStore(a, dataset).path)) as db:
        for table in ("fields", "history", "proposals"):
            for row in db.execute(f"SELECT * FROM {table}"):  # noqa: S608
                assert '{"card"' not in json.dumps(row)


def test_a_link_to_a_card_that_is_gone_shows_the_name_at_write() -> None:
    names = card_model.card_names_of({"card:aaa": {"name": "NOW"}, "field:aaa:x": {"value": 1}})
    assert names == {"aaa": "NOW"}
    item = card_model.link_item("gone", "AT WRITE")
    assert card_model.render_link(item, names) == "AT WRITE"
    # Inside a unit too, and a proposal's own `card` is left alone.
    proposal = {"card": "aaa", "field": "x", "value": item, "kind": "import"}
    assert card_model.render_links_within(proposal, names) == {**proposal, "value": "AT WRITE"}


def test_a_vault_on_an_older_schema_keeps_writing_text(tmp_path: Path) -> None:
    drive = _Drive(tmp_path)
    ws = drive.workspace("a")
    made = _ok(
        _call(
            ws,
            "POST",
            "/api/bi/vaults",
            {
                "path": str(drive.parent("a")),
                "title": "Old Schema",
                "purpose": "fictional",
                "schema": "bi.schema/v1.1@4.0.0",
                "author": "alice",
                "default_pack": False,
            },
        )
    )
    vault_id = made["vault"]["id"]
    dataset = vault.dataset_name(vault_id)
    _put(ws, dataset, _row("Account", "FAKE-ACME"))
    _put(ws, dataset, _row("Opportunity", "FAKE-OPP", account="FAKE-ACME"))
    assert _unit(ws, vault_id, f"field:{OPP}:account")["value"] == "FAKE-ACME"
