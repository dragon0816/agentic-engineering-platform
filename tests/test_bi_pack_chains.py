"""The chains A–A3 and the coverage matrix as analyses of the default pack (BI P2/D3).

`docs/phases/BI_ANALYSIS_DASHBOARD.md` §3–§4.3: the chain sections read Node
`chain` (labels from the schema's `chain` aliases) and the coverage matrix reads
`segment` x `tech_areas`. Parity: on a vault with a domain configuration, the
coded sections before the domain migration (D3) equal the pack analyses after
it, for every domain and with/without sample cards; the coverage matrix equals
`coverage.compute` with the configuration's matrix on the same cards. All data
is fictional.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from test_bi_default_pack import TODAY, _coded_table, _Runner, _vault
from test_bi_vault import _call, _commit, _ok

from capabilities.bi_cards import (
    board,
    catalog,
    coverage,
    dashboard,
    domains,
    market,
    packs,
    vault,
    vault_skills,
)
from capabilities.bi_cards.store import BiStore, PlannedRow

CHAINS = {
    "chain-summary": (market.chain_summary, False),
    "chain-view": (market.chain_view, True),
    "chain-overlap": (market.chain_overlap, False),
}


def _put(store: BiStore, entity_type: str, *rows: dict[str, Any]) -> None:
    planned = [
        PlannedRow(row=n, entity_type=entity_type, canonical_key=values["name"],
                   name=values["name"], values={"domain": ["AIDC"], **values}, synthetic=False)
        for n, values in enumerate(rows, start=1)
    ]  # fmt: skip
    store.apply(planned, filename=f"{entity_type}.csv", entity_type=entity_type, actor="tester")


def _cards(store: BiStore) -> None:
    _put(store, "Node",
         {"name": "L1-CMP-Accelerator", "layer": "L1"},
         {"name": "L3-PWR-Rack", "layer": "L3"},
         {"name": "L2-THM-Cold plate", "layer": "L2"},
         {"name": "X-Shared-Lab", "layer": "X"},
         {"name": "SAMPLE-L1-CMP-Fake", "layer": "L1"},
         {"name": "W-Antenna", "domain": ["wireless"]})  # fmt: skip
    _put(store, "Technology", {"name": "800VDC"}, {"name": "Liquid cooling"})
    _put(store, "Ecosystem",
         {"name": "Power Co", "node": "L3-PWR-Rack", "technologies": ["800VDC"],
          "segment": ["AIDC Power"], "tech_areas": ["Power / Generic IO", "emc"]},
         {"name": "Lab Co", "nodes": ["L1-CMP-Accelerator", "L3-PWR-Rack"],
          "segment": ["aidc-computing"], "tech_areas": ["high-speed-io"]},
         {"name": "Cool Co", "nodes": ["L2-THM-Cold plate", "X-Shared-Lab"],
          "technologies": ["Liquid cooling"]},
         {"name": "SAMPLE-Fake Co", "node": "SAMPLE-L1-CMP-Fake"})  # fmt: skip
    _put(store, "Account", {"name": "ODM Co", "nodes": ["L3-PWR-Rack", "L2-THM-Cold plate"],
                            "segment": ["aidc-power"], "tech_areas": ["rf"]})  # fmt: skip
    _put(store, "Trend",
         {"name": "800V racks", "affected_nodes": ["L3-PWR-Rack"], "related_tech": ["800VDC"],
          "measurement_impact": 3, "our_fit": 2},
         {"name": "Cold plates", "affected_nodes": ["X-Shared-Lab"],
          "related_tech": ["Liquid cooling"]})  # fmt: skip
    _put(store, "CustomerProduct",
         {"name": "AI Rack 1", "account": "ODM Co", "node": "L3-PWR-Rack",
          "segment": ["aidc-power", "Moon base"], "tech_areas": ["power-generic-io"]},
         {"name": "Cold Rack", "account": "Quiet Co", "nodes": ["X-Shared-Lab"],
          "segment": ["aidc-power"], "tech_areas": ["Power / Generic IO"]})  # fmt: skip
    _put(store, "SupplyLink",
         {"name": "Power Co → ODM Co", "supplier": "Power Co", "nodes": ["L3-PWR-Rack"],
          "evidence_grade": "B"},
         {"name": "Lab Co → ODM Co", "supplier": "Lab Co", "nodes": ["L1-CMP-Accelerator"],
          "evidence_grade": "D"},
         {"name": "Cool Co → ODM Co", "supplier": "Cool Co", "nodes": ["X-Shared-Lab"],
          "evidence_grade": "A"})  # fmt: skip


def _config(registry: Any) -> dict[str, Any]:
    """A domain configuration whose segments and areas are the schema's own."""
    allowed = packs.schema_values(registry)["allowed"]

    def entries(name: str) -> list[dict[str, Any]]:
        return [{"id": v, "label": label, "aliases": rest}
                for v, label, *rest in allowed[name]]  # fmt: skip

    return {
        "format": "aep.bi.domains/v1",
        "domains": [{"id": "AIDC", "label": "AI 資料中心", "segments": entries("segment"),
                     "chains": [
                         {"id": "CMP", "label": "運算鏈", "node_pattern": r"^L\d-CMP-"},
                         {"id": "PWR", "label": "電力鏈", "node_pattern": r"^L\d-PWR-",
                          "nodes": ["X-Shared-Lab"]},
                         {"id": "THM", "label": "散熱鏈", "node_pattern": r"^L\d-THM-",
                          "nodes": ["x-shared-lab"]}]}],
        "areas": entries("tech_areas"),
        "segment_field": "segment",
        "area_field": "tech_areas",
    }  # fmt: skip


def _coverage_table(report: dict[str, Any]) -> dict[str, Any]:
    """The oracle: `coverage.compute`'s cells as the table the analysis returns."""
    rows = [
        [c["segment"], c["area"], c["cards"],
         "、".join(f"{t} {n}" for t, n in c["types"].items()), c["sourced_share"], c["newest"],
         "、".join(f"{e['field']} {e['cards']}" for e in c["empty"])]
        for c in report["cells"]
    ]  # fmt: skip
    return {"columns": ["區段", "技術領域", "卡片數", "類型", "有來源比例", "最新更新",
                        "最常空白的欄位（前 5）"], "rows": rows}  # fmt: skip


def test_chains_and_coverage_after_the_migration_equal_the_coded_sections(
    tmp_path: Path,
) -> None:
    ws, vault_id = _vault(tmp_path, "bi.schema/v1.1", "chains")
    dataset = vault.dataset_name(vault_id)
    store = BiStore(ws, dataset)
    _cards(store)
    registry = catalog.for_store(store)
    target = vault.Vault(ws, vault_id)
    with target.lock:
        saved = domains.validate(_config(registry), registry)
        target.repo.stage(vault_skills.DOMAINS_UNIT, json.dumps(saved, ensure_ascii=False))
    _commit(ws, vault_id, "領域設定")
    config = domains.read(store)
    assert config is not None
    expected: dict[tuple[str, str, bool], dict[str, Any]] = {}
    for include_sample in (False, True):
        cards = dashboard._cards(store, include_sample)
        for domain in ("AIDC", "wireless", "robotics"):
            for slug, (build, level) in CHAINS.items():
                key = (slug, domain, include_sample)
                expected[key] = _coded_table(build(cards, domain, config), level)
    matrix = coverage.validate(config.matrix())

    url = f"/api/bi/vaults/{vault_id}/migrate-domains"
    plan = _ok(_call(ws, "POST", url, {}))
    assert {c["node"]: c["chain"] for c in plan["chains"]} == {
        "L1-CMP-Accelerator": ["CMP"], "L3-PWR-Rack": ["PWR"], "L2-THM-Cold plate": ["THM"],
        "X-Shared-Lab": ["PWR", "THM"], "SAMPLE-L1-CMP-Fake": ["CMP"]}  # fmt: skip
    _ok(_call(ws, "POST", url, {"apply": True, "token": plan["token"]}))
    assert domains.read(store) is None

    after = catalog.for_store(store)
    code = {a["slug"]: packs.fill(a["code"], after) for a in packs.default_pack()["analyses"]}
    run = _Runner(store)
    try:
        for (slug, domain, include_sample), table in expected.items():
            params = {"domain": domain, "include_sample": include_sample,
                      "today": TODAY.isoformat()}  # fmt: skip
            assert run(code[slug], params) == table, (slug, domain, include_sample)
        summary = expected[("chain-summary", "AIDC", False)]["rows"]
        assert [r[:3] for r in summary] == [["CMP 運算鏈", 1, 0], ["PWR 電力鏈", 2, 1],
                                            ["THM 散熱鏈", 2, 1]]  # fmt: skip
        overlap = [r[:3] for r in expected[("chain-overlap", "AIDC", False)]["rows"]]
        assert ["共用節點", "X-Shared-Lab", "PWR+THM"] in overlap
        assert ["共用公司", "Cool Co", "PWR+THM"] in overlap
        assert ["共用公司", "Lab Co", "CMP+PWR"] in overlap
        assert any(r[-1] for r in expected[("chain-view", "AIDC", False)]["rows"])

        oracle = _coverage_table(coverage.compute(store, after, matrix))
        found = run(code["coverage"], {})
        assert found == json.loads(json.dumps(oracle))
        filled = {(r[0], r[1]): r[2] for r in found["rows"] if r[2]}
        assert filled == {("aidc-computing", "high-speed-io"): 1, ("aidc-power", "emc"): 1,
                          ("aidc-power", "rf"): 1,
                          ("aidc-power", "power-generic-io"): 3}  # fmt: skip
    finally:
        run.close()


def test_the_board_draws_the_chain_analyses_instead_of_the_coded_chains(tmp_path: Path) -> None:
    ws, vault_id = _vault(tmp_path, "bi.schema/v1.1", "board")
    store = BiStore(ws, vault.dataset_name(vault_id))
    _cards(store)
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
