"""An import's commit holds the import's own units, and what they cannot go without.

Acceptance F19, 2026-11-06: 確認匯入 committed a skill's new revision, a created domain and a
schema addition under 「匯入 …：5 張卡、47 個欄位」, and the purpose a person typed for the rule
had nowhere to go. All data is fictional.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from test_bi_schema_merge import _change, _new_field
from test_bi_vault import _call, _commit, _import, _ok, _row, _two_pcs

from capabilities.bi_cards import vault


def _last_commit_units(ws: Path, vault_id: str) -> tuple[str, set[str]]:
    record = vault.Vault(ws, vault_id).repo.local_commits()[-1]
    return str(record["purpose"]), {op["unit"] for op in record["ops"]}


def _waiting(ws: Path, vault_id: str) -> set[str]:
    pending = _ok(_call(ws, "GET", f"/api/bi/vaults/{vault_id}/pending"))
    return {str(c["unit"]) for c in pending["uncommitted"]}


def _rule(ws: Path, vault_id: str) -> Any:
    body = {"name": "fake-rule", "role": "extract", "body": "虛構規則", "card_types": [],
            "applies_to": ["applications/aidc/sources"]}  # fmt: skip
    return _ok(_call(ws, "POST", f"/api/bi/vaults/{vault_id}/skills", body))


def test_an_import_commits_its_own_and_leaves_the_rest_waiting(tmp_path: Path) -> None:
    _drive, vault_id, dataset, a, _b = _two_pcs(tmp_path)
    _rule(a, vault_id)
    question = {"question": "虛構題？", "must": ["好"], "slug": "q1", "home": "aidc"}
    _ok(_call(a, "POST", f"/api/bi/vaults/{vault_id}/checks", question))
    home = {"name": "海事", "folder": "otherhome"}
    _ok(_call(a, "POST", f"/api/bi/vaults/{vault_id}/homes", home))
    _change(a, dataset, _new_field("unused_note"))
    before = _waiting(a, vault_id)
    assert {"skill:fake-rule", "check:question:main/q1", "meta:home:otherhome"} <= before
    assert "schema_change:field:Technology.unused_note" in before

    _import(a, dataset, _row("FAKE-TSN", summary="虛構"), filename="fake.csv")

    purpose, units = _last_commit_units(a, vault_id)
    assert purpose.startswith("匯入 fake.csv")
    assert any(u.startswith("card:") for u in units)
    assert not units & before, units & before
    # Everything else still waits, for the person's own commit and purpose.
    assert before <= _waiting(a, vault_id)
    _commit(a, vault_id, "加規則、題目與領域")
    purpose, units = _last_commit_units(a, vault_id)
    assert purpose == "加規則、題目與領域" and before <= units


def test_a_created_domain_and_a_new_field_its_cards_use_travel_with_it(tmp_path: Path) -> None:
    _drive, vault_id, dataset, a, _b = _two_pcs(tmp_path)
    _rule(a, vault_id)
    _ok(_call(a, "POST", f"/api/bi/vaults/{vault_id}/homes", {"name": "海事", "folder": "marine"}))
    _change(a, dataset, _new_field("cooling"))
    _change(a, dataset, _new_field("unused_note"))

    _import(a, dataset, _row("FAKE-SHIP", domain=["marine"], cooling="液冷"), filename="m.csv")

    _purpose, units = _last_commit_units(a, vault_id)
    # A colleague given these cards without them would read a domain and a field they lack.
    assert {"meta:home:marine", "schema_change:field:Technology.cooling"} <= units
    waiting = _waiting(a, vault_id)
    assert {"skill:fake-rule", "schema_change:field:Technology.unused_note"} <= waiting
    assert "meta:home:marine" not in waiting
