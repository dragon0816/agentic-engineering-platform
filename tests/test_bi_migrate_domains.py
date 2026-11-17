"""A dataset's old domain configuration moves into its schema, cards and skills (BI D3, D4).

`docs/phases/BI_ANALYSIS_DASHBOARD.md` §3: a dry run lists the changes; applying
with its token moves everything that can move (owner 2026-11-01): the schema to
3.0.0 when needed, value aliases and the node name rule into a new local schema
version, each name alias onto its card (a missing card is listed, never
invented), Node `chain` from the old patterns, the extraction notes into a
vault's skills or a local dataset's ingest method, and removes the
configuration. A vault gets one change commit the other PC receives by push and
sync; a dataset only on this PC is written directly. All data is fictional.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from test_bi_vault import _call, _commit, _ok, _push, _refused, _sync, _two_pcs

from aep_bi.cards import catalog, methods, migrate, vault, vault_skills
from aep_bi.cards.store import BiStore, PlannedRow

CONFIG = {
    "format": "aep.bi.domains/v1",
    "node_name_pattern": r"^(L\d|X)-",
    "domains": [{"id": "AIDC", "label": "AI 資料中心", "segments": [],
                 "nodes": ["L1-CMP-GPU", "L4-PWR-Busbar"],
                 "notes": "ODM 是 Account。",
                 "chains": [{"id": "CMP", "label": "運算鏈", "node_pattern": "^L\\d-CMP-"},
                            {"id": "PWR", "label": "電力鏈", "node_pattern": "^L\\d-PWR-"},
                            {"id": "XYZ", "label": "不存在的鏈", "nodes": ["L3-PWR-Rack"]}]}],
    "areas": [{"id": "rf", "label": "RF"}, {"id": "moon", "label": "Moon"}],
    "name_aliases": {"港灣": "Harbor Co", "Ghost": "Nobody Co"},
    "enum_aliases": {"role": {"雲端大廠": "hyperscaler", "月球商": "moon-maker"}},
}  # fmt: skip


def _put(store: BiStore, entity_type: str, *names: str) -> None:
    rows = [PlannedRow(row=n, entity_type=entity_type, canonical_key=name, name=name,
                       values={"name": name, "domain": ["AIDC"]}, synthetic=False)
            for n, name in enumerate(names, start=1)]  # fmt: skip
    store.apply(rows, filename=f"{entity_type}.csv", entity_type=entity_type, actor="tester")


def _cards(store: BiStore) -> None:
    _put(store, "Account", "Harbor Co")
    _put(store, "Node", "L1-CMP-GPU", "L3-PWR-Rack", "X-Lab")


def _vault_with_config(tmp_path: Path) -> tuple[Any, str, str, Path, Path]:
    drive, vault_id, dataset, a, b = _two_pcs(tmp_path)  # the newest schema (bare)
    _cards(BiStore(a, dataset))
    target = vault.Vault(a, vault_id)
    with target.lock:  # as 「領域設定」 kept it before BI D4
        target.repo.stage(vault_skills.DOMAINS_UNIT, json.dumps(CONFIG, ensure_ascii=False))
    _commit(a, vault_id, "領域設定")
    _push(a, vault_id)
    return drive, vault_id, dataset, a, b


def _common(plan: dict[str, Any]) -> None:
    assert [(x["card"], x["add"]) for x in plan["aliases"]] == [("Harbor Co", ["港灣"])]
    assert plan["missing"] == [{"alias": "Ghost", "name": "Nobody Co"}]
    assert {c["node"]: c["chain"] for c in plan["chains"]} == {
        "L1-CMP-GPU": ["CMP"], "L3-PWR-Rack": ["PWR"]}  # fmt: skip
    assert plan["dropped_chains"] == ["XYZ"] and plan["unknown_areas"] == ["moon"]
    assert plan["schema_adds"] == {"enum_aliases": {"role": {"雲端大廠": "hyperscaler"}},
                                   "name_pattern": r"^(L\d|X)-"}  # fmt: skip
    assert plan["enum_aliases_dropped"] == [
        {"field": "role", "alias": "月球商", "value": "moon-maker"}]  # fmt: skip
    assert plan["missing_nodes"] == ["L4-PWR-Busbar"]
    assert plan["notes"] == [{"domain": "AIDC", "label": "AI 資料中心"}]


def test_a_dry_run_lists_the_changes_and_writes_nothing(tmp_path: Path) -> None:
    drive, vault_id, dataset, a, b = _vault_with_config(tmp_path)
    url = f"/api/bi/vaults/{vault_id}/migrate-domains"
    plan = _ok(_call(a, "POST", url, {}))
    assert plan["dry_run"] is True and plan["schema"] is None  # the newest already
    assert plan["writes"] == "commit" and plan["notes_to"] == "skills"
    _common(plan)
    assert _ok(_call(a, "GET", f"/api/bi/vaults/{vault_id}/pending"))["uncommitted"] == []
    _refused(_call(a, "POST", url, {"apply": True, "token": "old"}), 409, "preview_stale")
    board = _ok(_call(a, "GET", "/api/bi/dashboard", dataset=dataset))
    assert board["domains_left"] is True


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
    registry = catalog.for_store(store)  # the new local version reached the other PC
    # Schema merge numbers a vault's new version from its content (BI_CARD_MODEL §4.3).
    assert registry.version == "5.1.118005"
    assert registry.ref == catalog.for_store(BiStore(a, dataset)).ref
    assert registry.types["Node"].name_pattern == r"^(L\d|X)-"
    assert registry.enum_aliases["role"]["雲端大廠"] == "hyperscaler"
    skills = _ok(_call(b, "GET", f"/api/bi/vaults/{vault_id}/skills"))["skills"]
    assert next(s for s in skills if s["name"] == "aidc-extract")["body"] == "ODM 是 Account。"
    assert vault_skills.DOMAINS_UNIT not in vault.Vault(b, vault_id).repo.units()
    assert _ok(_call(b, "GET", "/api/bi/dashboard", dataset=dataset))["domains_left"] is False
    _refused(_call(b, "POST", url, {}), 400, "domains_missing")


def test_a_dataset_only_on_this_pc_is_written_directly(tmp_path: Path) -> None:
    _ok(
        _call(tmp_path, "POST", "/api/bi/datasets", {"name": "m", "schema": "bi.schema/v1.1@2.0.0"})
    )
    store = BiStore(tmp_path, "m")
    _cards(store)
    store.set_meta_value("domains", json.dumps(CONFIG, ensure_ascii=False), base=None)
    url = "/api/bi/migrate-domains"
    plan = _ok(_call(tmp_path, "POST", url, {"dataset": "m"}))
    assert plan["writes"] == "direct" and plan["notes_to"] == "method"
    assert plan["schema"] == {"from": "bi.schema/v1.1@2.0.0", "to": "bi.schema/v1.1@5.0.0"}
    _common(plan)
    _ok(_call(tmp_path, "POST", url, {"dataset": "m", "apply": True, "token": plan["token"]}))
    assert not migrate.has_legacy(store)
    registry = catalog.for_store(store)
    assert registry.version == "5.1.0" and registry.types["Node"].name_pattern == r"^(L\d|X)-"
    harbor = store.find("Account", "Harbor Co")
    assert harbor is not None and store.fields(harbor["id"])["aliases"]["value"] == ["港灣"]
    (method,) = methods.listing(tmp_path, "m")
    assert method["name"] == migrate.METHOD_NAME
    detail = methods.detail(tmp_path, "m", method["id"])
    assert "AI 資料中心（AIDC）：ODM 是 Account。" in json.dumps(detail, ensure_ascii=False)
    # The value alias now comes from the schema: an import reads 雲端大廠 as hyperscaler.
    csv = "name,role\n港灣雲,雲端大廠\n"
    given = {"dataset": "m", "entity_type": "Ecosystem", "filename": "e.csv", "csv_text": csv}
    preview = _ok(_call(tmp_path, "POST", "/api/bi/import/preview", given))
    (row,) = preview["rows"]
    assert {f["field"]: f["normalized"] for f in row["fields"]}["role"] == "hyperscaler"
