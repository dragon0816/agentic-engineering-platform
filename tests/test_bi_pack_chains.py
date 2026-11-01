"""The chains A–A3 and the coverage matrix as analyses of the default pack (BI P2/D3).

`docs/phases/BI_ANALYSIS_DASHBOARD.md` §3–§4.3: the chain sections read Node
`chain` (labels from the schema's `chain` aliases) and the coverage matrix reads
`segment` x `tech_areas`. Parity: on the `chains` fixture of `bi_pack_fixtures`
(a vault with a domain configuration), the analyses after the domain migration
(D3) return the golden answers, which are the coded chains before the migration
and `coverage.compute` with the configuration's matrix on the same cards, for
every domain and with/without sample cards. All data is fictional.
"""

from __future__ import annotations

from pathlib import Path

from bi_pack_fixtures import build, chain_cards, golden, new_vault, pack_results
from test_bi_vault import _call, _ok

from capabilities.bi_cards import board, migrate, vault
from capabilities.bi_cards.store import BiStore


def test_chains_and_coverage_after_the_migration_give_the_golden_answers(
    tmp_path: Path,
) -> None:
    expected = golden("chains")["results"]
    assert set(expected) == {"chain-summary", "chain-view", "chain-overlap", "coverage"}
    store = build("chains", tmp_path)
    assert not migrate.has_legacy(store)  # migrated
    nodes = {r["name"]: r["id"] for r in store.card_rows() if r["entity_type"] == "Node"}
    chain = {n: store.fields(i).get("chain", {}).get("value") for n, i in nodes.items()}
    assert chain == {"L1-CMP-Accelerator": ["CMP"], "L3-PWR-Rack": ["PWR"],
                     "L2-THM-Cold plate": ["THM"], "X-Shared-Lab": ["PWR", "THM"],
                     "SAMPLE-L1-CMP-Fake": ["CMP"], "W-Antenna": None}  # fmt: skip
    found = pack_results(store, expected)
    for slug, tables in expected.items():
        for where, table in tables.items():
            assert found[slug][where] == table, (slug, where)
    # The answers compared are not empty.
    summary = expected["chain-summary"]["AIDC|real"]["rows"]
    assert [r[:3] for r in summary] == [["CMP 運算鏈", 1, 0], ["PWR 電力鏈", 2, 1],
                                        ["THM 散熱鏈", 2, 1]]  # fmt: skip
    overlap = [r[:3] for r in expected["chain-overlap"]["AIDC|real"]["rows"]]
    assert ["共用節點", "X-Shared-Lab", "PWR+THM"] in overlap
    assert ["共用公司", "Cool Co", "PWR+THM"] in overlap
    assert ["共用公司", "Lab Co", "CMP+PWR"] in overlap
    assert any(r[-1] for r in expected["chain-view"]["AIDC|real"]["rows"])
    cells = {(r[0], r[1]): r[2] for r in expected["coverage"]["*"]["rows"] if r[2]}
    assert cells == {("aidc-computing", "high-speed-io"): 1, ("aidc-power", "emc"): 1,
                     ("aidc-power", "rf"): 1, ("aidc-power", "power-generic-io"): 3}  # fmt: skip


def test_the_board_draws_the_chain_analyses_instead_of_the_coded_chains(tmp_path: Path) -> None:
    ws, vault_id = new_vault(tmp_path, "bi.schema/v1.1", "board")
    store = BiStore(ws, vault.dataset_name(vault_id))
    chain_cards(store)
    for row in store.card_rows():
        if row["entity_type"] == "Node" and "PWR" in row["name"]:
            card = store.card(row["id"])
            assert card is not None
            store.set_field(row["id"], "chain", ["PWR"], base_version=int(card["version"]),
                            actor="tester", reason="鏈")  # fmt: skip
    _ok(_call(ws, "POST", f"/api/bi/vaults/{vault_id}/packs", {"import": "bi-market-default"}))
    drawn = board.board(ws, store, "AIDC", False, {})
    ids = [s["id"] for s in drawn["sections"]]
    assert ids[:3] == ["chain-summary", "chain-view", "chain-overlap"]
    assert not {"A", "A2", "A3"} & set(ids) and "coverage" in ids
    summary = next(s for s in drawn["sections"] if s["id"] == "chain-summary")
    assert summary["rows"][0][:2] == ["PWR 電力鏈", 1]
