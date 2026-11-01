"""The default analysis pack gives the coded Dashboard's answers, section by section (BI P2).

`docs/phases/BI_ANALYSIS_DASHBOARD.md` §4.2–§4.3. Every section of
`dashboard.py` (§1–§19) and `market.py` (§20–§31) became a pack script; on the
fixtures of `bi_pack_fixtures` (the robotics demo on schema v4, the market
fixture on schema 2.0.0 with a sample card, the feed fixture vault) each returns
the coded section's answer kept in `tests/fixtures/bi_default_pack/golden/` for
every domain, with and without sample cards (the chains and the coverage matrix:
`test_bi_pack_chains`). The pack lists what it does not hold. Packs import (what
the schema satisfies) and export. All data is fictional.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from bi_pack_fixtures import (
    CHAINS,
    TODAY,
    Runner,
    build,
    golden,
    new_vault,
    pack_results,
)
from test_bi_vault import _call, _ok, _refused

from capabilities.bi_cards import analyses, catalog, packs, service, vault
from capabilities.bi_cards.store import BiStore

#: Sections whose answers come from the `chains` fixture (`test_bi_pack_chains`).
LATER = {*CHAINS, "coverage"}


@pytest.fixture(params=["robotics", "market", "feed"])
def fixture_name(request: pytest.FixtureRequest) -> Iterator[str]:
    yield str(request.param)


def _pack_code(store: BiStore) -> dict[str, str]:
    registry = catalog.for_store(store)
    return {a["slug"]: packs.fill(a["code"], registry) for a in packs.default_pack()["analyses"]}


def test_every_section_returns_the_golden_answer(fixture_name: str, tmp_path: Path) -> None:
    expected = golden(fixture_name)
    store = build(fixture_name, tmp_path)
    assert expected["domains"] == sorted(
        {*catalog.for_store(store).domains, "robotics", "wireless", "AIDC"}
    )
    assert set(_pack_code(store)) == set(expected["results"]) | LATER
    found = pack_results(store, expected["results"])
    for slug, tables in expected["results"].items():
        assert len(tables) == len(expected["domains"]) * 2, slug
        for where, table in tables.items():
            assert found[slug][where] == table, (slug, where)


def test_the_market_fixture_is_not_empty_where_it_matters() -> None:
    """The parity above compares real rows, not empty tables, on the market fixture."""
    results = golden("market")["results"]
    filled = {s for s, t in results.items() if t["AIDC|real"]["rows"]}
    flagged = {
        s
        for s, t in results.items()
        if t["AIDC|real"]["columns"][-1] == "level" and any(r[-1] for r in t["AIDC|real"]["rows"])
    }
    assert {"trend-links", "win-loss", "supply-evidence", "timing-gaps", "chain-integrity",
            "supply-grades", "revenue-layers", "pending-links", "gaps"} <= filled  # fmt: skip
    assert {"timing-gaps", "chain-integrity", "supply-evidence"} <= flagged


def test_pack_scripts_run_in_the_guarded_process(tmp_path: Path) -> None:
    store = build("market", tmp_path)
    run = Runner(store)
    params = {"domain": "AIDC", "include_sample": True, "today": TODAY.isoformat()}
    try:
        for slug, code in _pack_code(store).items():
            guarded = analyses.run_python(store.path, code, params=params)
            assert {"columns": guarded["columns"], "rows": guarded["rows"]} == json.loads(
                json.dumps(run(code, params))
            ), slug
    finally:
        run.close()


def test_the_pack_lists_what_it_does_not_hold() -> None:
    pack = packs.default_pack()
    assert pack["format"] == packs.FORMAT and pack["id"] == "bi-market-default"
    kept = {k["section"] for k in pack["report"]["kept"]}
    assert kept == {"Q"}
    for item in pack["analyses"]:
        assert analyses.unit_problem(f"analysis:{item['slug']}", item) is None, item["slug"]
        assert len(item["code"]) <= analyses.MAX_CODE
    # Every coded section with a golden answer is in the pack.
    held = {slug for slug, *_ in packs.SECTIONS}
    for name in ("robotics", "market", "feed", "chains"):
        assert set(golden(name)["results"]) <= held, name


# -- import and export ----------------------------------------------------------------


_vault = new_vault


def test_a_new_vault_starts_with_the_default_pack_committed(tmp_path: Path) -> None:
    ws, vault_id = _vault(tmp_path, "bi.schema/v1.1", "fresh", pack=True)
    target = vault.Vault(ws, vault_id)
    units = target.repo.units()  # pushed in the first commit, nothing pending
    assert {k for k in units if k.startswith("analysis:")} == {
        f"analysis:{s}" for s, *_ in packs.SECTIONS
    }
    assert json.loads(units["meta:dashboard"])["order"][:4] == [
        "chain-summary", "chain-view", "chain-overlap", "gaps"]  # fmt: skip
    assert _ok(_call(ws, "GET", f"/api/bi/vaults/{vault_id}/pending"))["uncommitted"] == []
    # A converted dataset gets it too.
    service.load_demo(BiStore(ws, "demo"))
    done = _ok(_call(ws, "POST", "/api/bi/vaults/convert", {
        "dataset": "demo", "path": str(tmp_path / "shared-fresh"), "author": "alice"}))  # fmt: skip
    converted = vault.Vault(ws, done["vault"]["id"]).repo.units()
    assert "analysis:gaps" in converted and "analysis:win-loss" not in converted  # v4 schema


def test_importing_stages_what_the_schema_satisfies(tmp_path: Path) -> None:
    ws, vault_id = _vault(tmp_path, "bi.schema/v1.1", "new")
    url = f"/api/bi/vaults/{vault_id}/packs"
    listed = _ok(_call(ws, "GET", url))["packs"][0]
    assert listed["id"] == "bi-market-default" and len(listed["usable"]) == len(packs.SECTIONS)
    done = _ok(_call(ws, "POST", url, {"import": "bi-market-default"}))
    assert len(done["staged"]) == len(packs.SECTIONS) and done["skipped"] == []
    assert done["order"] == [s for s, *_ in packs.SECTIONS]  # the pack's order
    saved = {a["slug"]: a for a in done["analyses"]}
    assert '"Account": {' in saved["pending-links"]["code"]  # the schema's link fields filled in
    pending = _ok(_call(ws, "GET", f"/api/bi/vaults/{vault_id}/pending"))
    assert "Dashboard 的順序" in {c["label"] for c in pending["uncommitted"]}
    _refused(_call(ws, "POST", url, {"import": {"format": "x"}}), 400, "pack_invalid")


def test_a_schema_without_the_types_skips_those_analyses(tmp_path: Path) -> None:
    ws, vault_id = _vault(tmp_path, "bi.schema/v1.1@1.1.0", "old")
    done = _ok(
        _call(ws, "POST", f"/api/bi/vaults/{vault_id}/packs", {"import": "bi-market-default"})
    )
    skipped = {s["slug"]: s["missing"] for s in done["skipped"]}
    assert "win-loss" in skipped and "WinLoss" in skipped["win-loss"]
    assert "gaps" in done["staged"] and "win-loss" not in {a["slug"] for a in done["analyses"]}


def test_a_vaults_analyses_export_and_import_into_another_project(tmp_path: Path) -> None:
    ws, source = _vault(tmp_path, "bi.schema/v1.1", "from")
    one = {"title": "卡片數", "slug": "card-count", "kind": "sql",
           "code": "SELECT count(*) AS n FROM cards", "chart": {"type": "table"}}  # fmt: skip
    _call(ws, "POST", f"/api/bi/vaults/{source}/analyses", {"save": one})
    url = f"/api/bi/vaults/{source}/packs"
    _refused(_call(ws, "POST", url, {"export": {"id": "Bad Id"}}), 400, "pack_invalid")
    exported = _ok(_call(ws, "POST", url, {"export": {"id": "team-pack", "title": "團隊分析"}}))
    pack = exported["pack"]
    assert pack["format"] == packs.FORMAT and [a["slug"] for a in pack["analyses"]] == [
        "card-count"
    ]
    other_ws, target = _vault(tmp_path, "bi.schema/v1.1", "to")
    done = _ok(_call(other_ws, "POST", f"/api/bi/vaults/{target}/packs", {"import": pack}))
    assert done["staged"] == ["card-count"]
    (saved,) = [a for a in done["analyses"] if a["slug"] == "card-count"]
    assert saved["code"] == one["code"]
