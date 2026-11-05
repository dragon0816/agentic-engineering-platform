"""A person says a card marked as a sample is real: carried in units, so it survives sync and
rebuild on another PC, with who and why. And 「待查證」 no longer marks a card. All fictional."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from test_bi_vault import _call, _ok, _two_pcs

from capabilities.bi_cards import catalog, importer, quality, vault
from capabilities.bi_cards.store import BiStore


def _csv(ws: Path, dataset: str, text: str) -> None:
    body = {"dataset": dataset, "entity_type": "Technology", "filename": "t.csv", "csv_text": text}
    preview = _ok(_call(ws, "POST", "/api/bi/import/preview", body))
    _ok(_call(ws, "POST", "/api/bi/import/apply", {"preview_id": preview["preview_id"]}))


def _card(ws: Path, dataset: str, name: str) -> Any:
    found = BiStore(ws, dataset).find("Technology", name)
    assert found is not None
    return found


def _clear(ws: Path, dataset: str, name: str, reason: str = "擁有者確認是真的") -> tuple[int, Any]:
    card = _card(ws, dataset, name)
    body = {"dataset": dataset, "base_version": card["version"], "reason": reason}
    status, answer = _call(ws, "POST", f"/api/bi/cards/{card['id']}/unmark", body)
    return int(status), answer


def test_a_cleared_mark_survives_sync_and_rebuild_with_its_reason(tmp_path: Path) -> None:
    drive, vault_id, dataset, a, b = _two_pcs(tmp_path)
    _csv(a, dataset, "name,standard_body,note\nFAKE-TSN,IEEE,虛構範例\n")
    card = _card(a, dataset, "FAKE-TSN")
    assert card["synthetic"] == 1
    before = BiStore(a, dataset).fields(card["id"])
    _ok(_call(a, "POST", f"/api/bi/vaults/{vault_id}/push", {}))

    _ok(_clear(a, dataset, "FAKE-TSN"))
    after = _card(a, dataset, "FAKE-TSN")
    assert after["synthetic"] == 0 and after["version"] == card["version"]
    assert BiStore(a, dataset).fields(card["id"]) == before

    pending = _ok(_call(a, "GET", f"/api/bi/vaults/{vault_id}/pending"))
    assert [u["unit"] for u in pending["uncommitted"]] == [f"card:{card['id']}"]
    _ok(_call(a, "POST", f"/api/bi/vaults/{vault_id}/commit", {"purpose": "這張是真的"}))
    unit = vault.Vault(a, vault_id).repo.working_units()[f"card:{card['id']}"]
    assert unit["synthetic"] is False and unit["mark_cleared"]["reason"] == "擁有者確認是真的"
    _ok(_call(a, "POST", f"/api/bi/vaults/{vault_id}/push", {}))

    # The same on the other PC, by sync and by a rebuild from nothing.
    drive.deliver("a", "b", vault_id)
    _ok(_call(b, "POST", f"/api/bi/vaults/{vault_id}/sync", {}))
    for pc in (b, a):
        vault.Vault(pc, vault_id).rebuild()
        assert _card(pc, dataset, "FAKE-TSN")["synthetic"] == 0
        history = _ok(_call(pc, "GET", f"/api/bi/cards/{card['id']}/history", dataset=dataset))
        (entry,) = [h for h in history["history"] if h["field"] == "synthetic"]
        assert (entry["old"], entry["new"], entry["reason"]) == (True, False, "擁有者確認是真的")
        # A rebuild restates the units exactly: nothing waits to be committed afterwards.
        assert _ok(_call(pc, "GET", f"/api/bi/vaults/{vault_id}/pending"))["uncommitted"] == []


def test_a_name_saying_sample_cannot_be_cleared_and_the_refusals(tmp_path: Path) -> None:
    _, _vault_id, dataset, a, _ = _two_pcs(tmp_path)
    _csv(a, dataset, "name,note\nSAMPLE-FAKE,x\nFAKE-REAL,y\nFAKE-MARKED,虛構\n")
    status, body = _clear(a, dataset, "SAMPLE-FAKE")
    assert (status, body["code"]) == (400, "sample_by_name")
    assert _card(a, dataset, "SAMPLE-FAKE")["synthetic"] == 1
    status, body = _clear(a, dataset, "FAKE-REAL")
    assert (status, body["code"]) == (400, "not_a_sample")
    status, body = _clear(a, dataset, "FAKE-MARKED", reason=" ")
    assert (status, body["code"]) == (400, "reason_required")
    card = _card(a, dataset, "FAKE-MARKED")
    stale = {"dataset": dataset, "base_version": card["version"] + 1, "reason": "x"}
    status, body = _call(a, "POST", f"/api/bi/cards/{card['id']}/unmark", stale)
    assert (status, body["code"]) == (409, "stale_edit")
    assert _card(a, dataset, "FAKE-MARKED")["synthetic"] == 1


def test_a_later_row_saying_it_is_an_example_marks_it_again(tmp_path: Path) -> None:
    _, vault_id, dataset, a, _ = _two_pcs(tmp_path)
    _csv(a, dataset, "name,note\nFAKE-TSN,虛構範例\n")
    _ok(_clear(a, dataset, "FAKE-TSN"))
    card = _card(a, dataset, "FAKE-TSN")
    assert BiStore(a, dataset).marks_cleared()[card["id"]]["reason"]
    _csv(a, dataset, "name,note\nFAKE-TSN,虛構範例\n")
    assert _card(a, dataset, "FAKE-TSN")["synthetic"] == 1
    assert BiStore(a, dataset).marks_cleared() == {}
    assert "mark_cleared" not in vault.Vault(a, vault_id).repo.working_units()[f"card:{card['id']}"]


def test_quality_does_not_ask_again_about_a_card_a_person_cleared(tmp_path: Path) -> None:
    _, _vault_id, dataset, a, _ = _two_pcs(tmp_path)
    _csv(a, dataset, "name,note\nFAKE-TSN,虛構範例\n")
    store = BiStore(a, dataset)
    card = _card(a, dataset, "FAKE-TSN")
    store.set_field(card["id"], "body", "示範一段內文", base_version=card["version"], actor="x")
    _ok(_clear(a, dataset, "FAKE-TSN"))
    checks = quality.check(store, catalog.for_store(store))["checks"]
    assert next(c for c in checks if c["id"] == "sample_not_marked")["count"] == 0


@pytest.mark.parametrize(
    ("text", "marks"),
    [
        ("IEEE 標準時程(待查證)", False),
        ("待業務/FAE 驗證", False),
        ("(待 BDM 驗證)", False),
        ("(虛構範例)", True),
        ("[範例資料,待業務/FAE 驗證]", True),
        ("示範失單", True),
        ("SAMPLE-X", True),
        ("IEEE 802.1", False),
    ],
)
def test_what_marks_a_card(text: str, marks: bool) -> None:
    assert bool(importer.FICTIONAL.search(text)) is marks


def test_a_value_to_be_checked_leaves_the_card_real_and_stays_as_written(tmp_path: Path) -> None:
    _, _vault_id, dataset, a, _ = _two_pcs(tmp_path)
    _csv(a, dataset, "name,standard_body\nFAKE-TSN,IEEE(待查證)\n")
    card = _card(a, dataset, "FAKE-TSN")
    assert card["synthetic"] == 0
    assert BiStore(a, dataset).fields(card["id"])["standard_body"]["value"] == "IEEE(待查證)"
