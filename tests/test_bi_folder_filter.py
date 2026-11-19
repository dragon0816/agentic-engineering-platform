"""Analyses narrow to the working domain's folder (owner 2026-11-19, 「改成依資料夾篩選」).

A library entry (`library/products`) has no card domain: its Dashboard shows the cards with
evidence from its folder (`card_app_folders`). The default pack does from 1.1.0, and a vault's
older copies come up to date as a pending change; a custom analysis that narrows only by the
card `domain` field says 「不支援依資料夾篩選」 instead of drawing an empty chart. A working
domain with a card domain (`wireless`) keeps narrowing by it. All data is fictional.
"""

from __future__ import annotations

import json
import shutil
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

from test_bi_vault import _call, _ok, _refused

from aep_bi.cards import analyses, board, packs, vault
from aep_bi.cards.store import BiStore
from scripts import bi_feed_fixtures as fixtures

VAULT = fixtures.VAULT_ID
DATASET = f"vault-{VAULT}"
URL = f"/api/bi/vaults/{VAULT}"
TECH = "technologies-without-concept"
PRODUCTS = "library/products"
IN_PRODUCTS = {"EtherCAT G", "48V Busbar"}


def _joined(tmp_path: Path) -> Path:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    copy = tmp_path / "shared" / "vault"
    shutil.copytree(fixtures.VAULT_DIR, copy)
    fixtures.join(workspace, copy)
    return workspace


def _place(ws: Path) -> None:
    """Two technologies with evidence from `library/products`, as a rebuild records it."""
    target = vault.Vault(ws, VAULT)
    with closing(sqlite3.connect(target.db_path)) as db:
        ids = [
            r[0]
            for r in db.execute(
                "SELECT id FROM cards WHERE name IN (?, ?)", sorted(IN_PRODUCTS)
            ).fetchall()
        ]
        assert len(ids) == 2
        db.executemany(
            "INSERT INTO card_app_folders (card_id, application) VALUES (?, ?)",
            [(card, PRODUCTS) for card in ids],
        )
        db.commit()


def _names(section: dict[str, Any]) -> set[str]:
    return {row[0]["label"] if isinstance(row[0], dict) else str(row[0]) for row in section["rows"]}


def _old_prelude(code: str) -> str:
    """The pack's code as 1.0.0 wrote it: the prelude without the folder."""
    lines = [line for line in code.split("\n") if "HOME" not in line and "folders" not in line]
    return "\n".join(lines).replace("        tables = query(", "        query(")


def test_a_library_entry_shows_the_cards_of_its_folder(tmp_path: Path) -> None:
    ws = _joined(tmp_path)
    _ok(_call(ws, "POST", f"{URL}/packs", {"import": packs.DEFAULT_ID}))
    _place(ws)
    layout = {"order": [TECH, "accounts-by-region"], "hidden": []}
    _ok(_call(ws, "POST", f"{URL}/analyses", {"dashboard": layout, "home": PRODUCTS}))
    drawn = board.board(ws, BiStore(ws, DATASET), "products", False, {}, PRODUCTS)
    by_id = {s["id"]: s for s in drawn["sections"]}
    assert _names(by_id[TECH]) == IN_PRODUCTS  # non-empty, and only its folder's
    # The fixture's own analysis narrows by the card domain only: said, not drawn empty.
    custom = by_id["accounts-by-region"]
    assert custom["unsupported"] is True and custom["note"] == analyses.UNSUPPORTED
    listed = _ok(_call(ws, "GET", f"{URL}/analyses", home=PRODUCTS))
    flags = {a["slug"]: a["folder_filter"] for a in listed["analyses"]}
    assert flags[TECH] is True and flags["accounts-by-region"] is False
    # Run alone from step 3 the same way.
    ran = _ok(_call(ws, "POST", f"{URL}/analyses",
                    {"run": TECH, "params": {"domain": "products"}, "home": PRODUCTS}))  # fmt: skip
    assert {r[0] for r in ran["table"]["rows"]} == IN_PRODUCTS
    _refused(_call(ws, "POST", f"{URL}/analyses",
                   {"run": "accounts-by-region", "params": {"domain": "products"},
                    "home": PRODUCTS}), 400, "folder_filter_unsupported")  # fmt: skip


def test_a_card_domain_working_domain_still_narrows_by_it(tmp_path: Path) -> None:
    ws = _joined(tmp_path)
    _ok(_call(ws, "POST", f"{URL}/packs", {"import": packs.DEFAULT_ID}))
    _place(ws)
    layout = {"order": [TECH, "accounts-by-region"], "hidden": []}
    _ok(_call(ws, "POST", f"{URL}/analyses", {"dashboard": layout, "home": "wireless"}))
    drawn = board.board(ws, BiStore(ws, DATASET), "wireless", False, {}, "wireless")
    by_id = {s["id"]: s for s in drawn["sections"]}
    wireless = {name for name, domains, *_ in fixtures.TECHNOLOGIES if "wireless" in domains}
    assert _names(by_id[TECH]) == wireless
    assert not by_id["accounts-by-region"].get("unsupported")
    assert by_id["accounts-by-region"]["rows"]


def test_older_pack_copies_come_up_to_date_as_a_pending_change(tmp_path: Path) -> None:
    ws = _joined(tmp_path)
    _ok(_call(ws, "POST", f"{URL}/packs", {"import": packs.DEFAULT_ID}))
    repo = vault.Vault(ws, VAULT).repo
    units = repo.working_units()
    tech_key, other_key = f"{analyses.PREFIX}{TECH}", f"{analyses.PREFIX}gaps"
    old = {k: {**units[k], "code": _old_prelude(units[k]["code"])} for k in (tech_key, other_key)}
    assert not analyses.supports_home(old[tech_key])
    # Someone edited the other one's own code: it is theirs and stays as it is.
    old[other_key]["code"] += "\n# 我自己改的\n"
    repo.stage_many(old)
    listed = _ok(_call(ws, "GET", f"{URL}/analyses"))
    assert listed["pack_updates"] == 1
    updated = _ok(_call(ws, "POST", f"{URL}/packs", {"update": packs.DEFAULT_ID}))
    assert updated["updated"] == [TECH] and updated["pack_updates"] == 0
    after = repo.working_units()
    assert analyses.supports_home(after[tech_key])
    assert after[other_key]["code"].endswith("# 我自己改的\n")
    assert json.dumps(after[tech_key]["params"]) == json.dumps(units[tech_key]["params"])
    pending = _ok(_call(ws, "GET", f"{URL}/pending"))
    assert any(c["unit"] == tech_key for c in pending["uncommitted"])
