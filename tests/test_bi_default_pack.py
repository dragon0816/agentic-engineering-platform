"""The default analysis pack equals the coded Dashboard, section by section (BI P2).

`docs/phases/BI_ANALYSIS_DASHBOARD.md` §4.2–§4.3. Every section of
`dashboard.py` (§1–§19) and `market.py` (§20–§31) became a pack script; on the
fixtures (the robotics demo on schema v4, the market fixture on schema 2.0.0
with a sample card, the feed fixture vault) each returns the Python section's
rows for every domain, with and without sample cards. A card cell becomes its
name and a flagged row gets `level` (`gap` for red, `warning` otherwise).
Sections not in the pack are listed in its report. Packs import (what the
schema satisfies) and export. All data is fictional.
"""

from __future__ import annotations

import json
import shutil
import sqlite3
import tempfile
from collections.abc import Callable, Iterator
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from test_bi_market import _market
from test_bi_vault import _call, _ok, _refused

from capabilities.bi_cards import analyses, catalog, dashboard, market, packs, service, vault
from capabilities.bi_cards.store import BiStore
from scripts import bi_feed_fixtures as fixtures

TODAY = date(2026, 10, 29)
#: slug -> (the coded section, whether it flags rows, what else it takes).
CODED: dict[str, tuple[Callable[..., dict[str, Any]], bool, str]] = {
    "gaps": (dashboard.gaps, True, ""),
    "trend-coverage": (dashboard.trend_coverage, True, ""),
    "demand-without-opportunity": (dashboard.demand_without_opportunity, True, ""),
    "solutions-vs-opportunities": (dashboard.solutions_vs_opportunities, True, ""),
    "funnel": (dashboard.funnel, False, ""),
    "technologies-without-concept": (dashboard.technologies_without_concept, True, ""),
    "product-completeness": (dashboard.product_completeness, True, ""),
    "trend-priority": (dashboard.trend_priority, False, ""),
    "launch-timeline": (dashboard.launch_timeline, False, ""),
    "node-technology": (dashboard.node_technology, False, ""),
    "recent-signals": (dashboard.recent_signals, False, ""),
    "competitor-coverage": (dashboard.competitor_coverage, False, ""),
    "assumed-share": (dashboard.assumed_share, False, ""),
    "stale": (dashboard.stale, False, "today"),
    "supplier-dependency": (dashboard.supplier_dependency, False, ""),
    "trend-links": (market.trend_links, True, ""),
    "win-loss": (market.win_loss, True, ""),
    "roadmap-gaps": (market.roadmap_gaps, True, ""),
    "enablement": (market.enablement, True, ""),
    "customer-contact": (market.customer_contact, True, "today"),
    "supply-evidence": (market.supply_evidence, True, ""),
    "timing-gaps": (market.timing_gaps, True, "today"),
    "supply-grades": (market.supply_grades, True, ""),
    "revenue-layers": (market.revenue_layers, True, ""),
    "chain-integrity": (market.chain_integrity, True, ""),
    "same-names": (market.same_names, True, ""),
    "pending-links": (market.pending_links, False, "links"),
}


def _coded_table(section: dict[str, Any], level: bool) -> dict[str, Any]:
    """The oracle: a coded section as the table its analysis must return."""
    levels = {f["row"]: "gap" if f["level"] == "red" else "warning" for f in section["flags"]}
    rows = []
    for number, row in enumerate(section["rows"]):
        cells = [c["label"] if isinstance(c, dict) else c for c in row]
        rows.append([*cells, levels.get(number)] if level else cells)
    assert level or not section["flags"], section["id"]
    return {"columns": [*section["columns"], *(["level"] if level else [])], "rows": rows}


class _Runner:
    """Runs pack scripts in this process on a read-only copy (the same code the
    guarded process runs; the guard is checked separately)."""

    def __init__(self, store: BiStore) -> None:
        self.folder = Path(tempfile.mkdtemp(prefix="aep-pack-parity-"))
        self.db = analyses._copy(store.path, self.folder)

    def __call__(self, code: str, params: dict[str, Any]) -> dict[str, Any]:
        db = sqlite3.connect(f"file:{self.db.as_posix()}?mode=ro", uri=True)
        db.row_factory = sqlite3.Row

        def query(sql: str, values: Any = ()) -> list[dict[str, Any]]:
            return [dict(r) for r in db.execute(sql, values)]

        space: dict[str, Any] = {"__name__": "__analysis__", "query": query, "PARAMS": params}
        try:
            exec(compile(code, "script.py", "exec"), space)  # noqa: S102 - the pack's own scripts
        finally:
            db.close()
        return {"columns": list(space["result"]["columns"]), "rows": space["result"]["rows"]}

    def close(self) -> None:
        shutil.rmtree(self.folder, ignore_errors=True)


def _robotics(tmp_path: Path) -> BiStore:
    store = BiStore(tmp_path / "robotics")
    service.load_demo(store)
    return store


def _feed_vault(tmp_path: Path) -> BiStore:
    ws = tmp_path / "feed"
    ws.mkdir()
    copy = tmp_path / "feed-shared" / "vault"
    shutil.copytree(fixtures.VAULT_DIR, copy)
    fixtures.join(ws, copy)
    return BiStore(ws, vault.dataset_name(fixtures.VAULT_ID))


@pytest.fixture(params=["robotics", "market", "feed"])
def fixture_store(request: pytest.FixtureRequest, tmp_path: Path) -> Iterator[BiStore]:
    build = {"robotics": _robotics, "market": lambda p: _market(p / "market"),
             "feed": _feed_vault}[request.param]  # fmt: skip
    yield build(tmp_path)


def _pack_code(store: BiStore) -> dict[str, str]:
    links = packs.link_fields(catalog.for_store(store))
    return {a["slug"]: packs._filled(a["code"], links) for a in packs.default_pack()["analyses"]}


def test_every_section_returns_the_coded_rows(fixture_store: BiStore) -> None:
    store = fixture_store
    registry = catalog.for_store(store)
    links = packs.link_fields(registry)
    code = _pack_code(store)
    assert set(code) == set(CODED)
    domains = sorted({*registry.domains, "robotics", "wireless", "AIDC"})
    run = _Runner(store)
    compared = 0
    try:
        for include_sample in (False, True):
            cards = dashboard._cards(store, include_sample)
            for domain in domains:
                params = {"domain": domain, "include_sample": include_sample,
                          "today": TODAY.isoformat()}  # fmt: skip
                for slug, (build, level, extra) in CODED.items():
                    args: tuple[Any, ...] = (cards, domain)
                    if extra == "today":
                        args = (*args, TODAY)
                    elif extra == "links":
                        args = (*args, links)
                    expected = _coded_table(build(*args), level)
                    found = run(code[slug], params)
                    assert found == expected, (slug, domain, include_sample)
                    compared += 1
    finally:
        run.close()
    assert compared == len(CODED) * len(domains) * 2


def test_the_market_fixture_is_not_empty_where_it_matters(tmp_path: Path) -> None:
    """The parity above compares real rows, not empty tables, on the market fixture."""
    store = _market(tmp_path)
    run = _Runner(store)
    try:
        code = _pack_code(store)
        params = {"domain": "AIDC", "include_sample": False, "today": TODAY.isoformat()}
        filled = {s for s in CODED if run(code[s], params)["rows"]}
        flagged = {
            s for s in CODED if any(r[-1] for r in run(code[s], params)["rows"]) and CODED[s][1]
        }
    finally:
        run.close()
    assert {"trend-links", "win-loss", "supply-evidence", "timing-gaps", "chain-integrity",
            "supply-grades", "revenue-layers", "pending-links", "gaps"} <= filled  # fmt: skip
    assert {"timing-gaps", "chain-integrity", "supply-evidence"} <= flagged


def test_pack_scripts_run_in_the_guarded_process(tmp_path: Path) -> None:
    store = _market(tmp_path)
    run = _Runner(store)
    params = {"domain": "AIDC", "include_sample": True, "today": TODAY.isoformat()}
    try:
        for slug, code in _pack_code(store).items():
            guarded = analyses.run_python(store.path, code, params=params)
            assert {"columns": guarded["columns"], "rows": guarded["rows"]} == json.loads(
                json.dumps(run(code, params))
            ), slug
    finally:
        run.close()


def test_the_pack_lists_what_it_does_not_hold_yet() -> None:
    pack = packs.default_pack()
    assert pack["format"] == packs.FORMAT and pack["id"] == "bi-market-default"
    kept = {k["section"] for k in pack["report"]["kept"]}
    assert kept == {"A", "A2", "A3", "coverage", "Q"}
    for item in pack["analyses"]:
        assert analyses.unit_problem(f"analysis:{item['slug']}", item) is None, item["slug"]
        assert len(item["code"]) <= analyses.MAX_CODE
    # Every coded section is either in the pack or listed as kept.
    coded = {b.__name__ for b in dashboard.SECTIONS} | {b.__name__ for b, _ in market.SECTIONS}
    coded |= {"pending_links"} | {b.__name__ for b in market.CHAIN_SECTIONS}
    held = {source for _, source, *_ in packs.SECTIONS}
    assert coded - held == {b.__name__ for b in market.CHAIN_SECTIONS}


# -- import and export ----------------------------------------------------------------


def _vault(tmp_path: Path, schema: str, name: str, *, pack: bool = False) -> tuple[Path, str]:
    ws = tmp_path / f"ws-{name}"
    ws.mkdir()
    shared = tmp_path / f"shared-{name}"
    shared.mkdir()
    made = _ok(_call(ws, "POST", "/api/bi/vaults", {
        "path": str(shared), "title": f"Pack {name}", "purpose": "虛構", "schema": schema,
        "author": "alice", "id": f"pack-{name}", "default_pack": pack}))  # fmt: skip
    return ws, str(made["vault"]["id"])


def test_a_new_vault_starts_with_the_default_pack_committed(tmp_path: Path) -> None:
    ws, vault_id = _vault(tmp_path, "bi.schema/v1.1", "fresh", pack=True)
    target = vault.Vault(ws, vault_id)
    units = target.repo.units()  # pushed in the first commit, nothing pending
    assert {k for k in units if k.startswith("analysis:")} == {
        f"analysis:{s}" for s, *_ in packs.SECTIONS
    }
    assert json.loads(units["meta:dashboard"])["order"][:2] == ["gaps", "trend-coverage"]
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
    assert listed["id"] == "bi-market-default" and len(listed["usable"]) == len(CODED)
    done = _ok(_call(ws, "POST", url, {"import": "bi-market-default"}))
    assert len(done["staged"]) == len(CODED) and done["skipped"] == []
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
