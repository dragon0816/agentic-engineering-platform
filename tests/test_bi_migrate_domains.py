"""A vault's domain configuration moves into its schema and cards (BI D3).

`docs/phases/BI_ANALYSIS_DASHBOARD.md` §3: a dry run lists the changes; applying
with its token makes one change commit that upgrades the schema to 3.0.0, puts
each name alias on its card (a missing card is listed, never invented), sets
Node `chain` from the old patterns and removes `meta:domains`; the other PC gets
it by push and sync. All data is fictional.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from test_bi_vault import _call, _commit, _ok, _push, _refused, _sync, _two_pcs

from capabilities.bi_cards import catalog, domains, vault, vault_skills
from capabilities.bi_cards.store import BiStore, PlannedRow

CONFIG = {
    "format": "aep.bi.domains/v1",
    "domains": [{"id": "AIDC", "label": "AI 資料中心", "segments": [],
                 "chains": [{"id": "CMP", "label": "運算鏈", "node_pattern": "^L\\d-CMP-"},
                            {"id": "PWR", "label": "電力鏈", "node_pattern": "^L\\d-PWR-"},
                            {"id": "XYZ", "label": "不存在的鏈", "nodes": ["L3-PWR-Rack"]}]}],
    "areas": [{"id": "rf", "label": "RF"}, {"id": "moon", "label": "Moon"}],
    "name_aliases": {"港灣": "Harbor Co", "Ghost": "Nobody Co"},
}  # fmt: skip


def _put(store: BiStore, entity_type: str, *names: str) -> None:
    rows = [PlannedRow(row=n, entity_type=entity_type, canonical_key=name, name=name,
                       values={"name": name, "domain": ["AIDC"]}, synthetic=False)
            for n, name in enumerate(names, start=1)]  # fmt: skip
    store.apply(rows, filename=f"{entity_type}.csv", entity_type=entity_type, actor="tester")


def _vault_with_config(tmp_path: Path) -> tuple[Any, str, str, Path, Path]:
    drive, vault_id, dataset, a, b = _two_pcs(tmp_path)  # schema 3.0.0 (bare)
    store = BiStore(a, dataset)
    _put(store, "Account", "Harbor Co")
    _put(store, "Node", "L1-CMP-GPU", "L3-PWR-Rack", "X-Lab")
    target = vault.Vault(a, vault_id)
    with target.lock:
        saved = domains.validate(CONFIG, catalog.for_store(store))  # as 「領域設定」 saves it
        target.repo.stage(vault_skills.DOMAINS_UNIT, json.dumps(saved, ensure_ascii=False))
    _commit(a, vault_id, "領域設定")
    _push(a, vault_id)
    return drive, vault_id, dataset, a, b


def test_a_dry_run_lists_the_changes_and_writes_nothing(tmp_path: Path) -> None:
    drive, vault_id, dataset, a, b = _vault_with_config(tmp_path)
    url = f"/api/bi/vaults/{vault_id}/migrate-domains"
    plan = _ok(_call(a, "POST", url, {}))
    assert plan["dry_run"] is True and plan["schema"] is None  # 3.0.0 already
    assert [(x["card"], x["add"]) for x in plan["aliases"]] == [("Harbor Co", ["港灣"])]
    assert plan["missing"] == [{"alias": "Ghost", "name": "Nobody Co"}]
    assert {c["node"]: c["chain"] for c in plan["chains"]} == {
        "L1-CMP-GPU": ["CMP"], "L3-PWR-Rack": ["PWR"]}  # fmt: skip
    assert plan["dropped_chains"] == ["XYZ"] and plan["unknown_areas"] == ["moon"]
    assert _ok(_call(a, "GET", f"/api/bi/vaults/{vault_id}/pending"))["uncommitted"] == []
    _refused(_call(a, "POST", url, {"apply": True, "token": "old"}), 409, "preview_stale")


def test_applying_makes_one_commit_that_reaches_the_other_pc(tmp_path: Path) -> None:
    drive, vault_id, dataset, a, b = _vault_with_config(tmp_path)
    url = f"/api/bi/vaults/{vault_id}/migrate-domains"
    plan = _ok(_call(a, "POST", url, {}))
    done = _ok(_call(a, "POST", url, {"apply": True, "token": plan["token"]}))
    assert done["commit"]["purpose"] == "把領域設定搬進 schema 與卡片"
    assert _ok(_call(a, "GET", f"/api/bi/vaults/{vault_id}/pending"))["commits"][0]["purpose"] == (
        "把領域設定搬進 schema 與卡片"
    )
    _push(a, vault_id)
    drive.deliver("a", "b", vault_id)
    _sync(b, vault_id)
    store = BiStore(b, dataset)
    harbor = store.find("Account", "Harbor Co")
    gpu = store.find("Node", "L1-CMP-GPU")
    assert harbor is not None and gpu is not None
    assert store.fields(harbor["id"])["aliases"]["value"] == ["港灣"]
    assert store.fields(gpu["id"])["chain"]["value"] == ["CMP"]
    assert vault_skills.DOMAINS_UNIT not in vault.Vault(b, vault_id).repo.units()
    _refused(_call(b, "POST", url, {}), 400, "domains_missing")
