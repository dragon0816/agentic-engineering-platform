"""Fixtures and golden answers of the default analysis pack (BI P2, P5).

The coded Dashboard (`dashboard.py`, `market.py`, `coverage.py`) was the oracle
the pack's analyses were checked against. Its answers on these fixtures are kept
in `tests/fixtures/bi_default_pack/golden/<fixture>.json`, so the parity tests
keep their reference after the coded sections are removed (P5).

Every fixture is built under a fixed clock and seeded ids
(`scripts/bi_feed_fixtures.frozen`), so a rebuild gives the same tables:

- `robotics`: the robotics demo dataset (schema v4);
- `market`: a small market dataset on schema 2.0.0 with a sample card;
- `feed`: a copy of the feed fixture vault (`tests/fixtures/bi_feed/vault/`);
- `chains`: a vault on schema 3.0.0 with a domain configuration (chains, segments,
  areas); the coded chains were read before the domain migration (D3) and the
  analyses run after it.

All data is fictional.
"""

from __future__ import annotations

import json
import shutil
import sqlite3
import tempfile
from datetime import date
from pathlib import Path
from typing import Any

from test_bi_vault import _call, _commit, _ok

from capabilities.bi_cards import analyses, catalog, domains, packs, service, vault, vault_skills
from capabilities.bi_cards.store import BiStore, PlannedRow
from host_runtime.bi_cards_api import route
from scripts import bi_feed_fixtures as feed_fixtures

TODAY = date(2026, 10, 29)
GOLDEN = Path(__file__).parent / "fixtures" / "bi_default_pack" / "golden"
GOLDEN_FORMAT = "aep.bi.pack_golden/v1"
FIXTURES = ("robotics", "market", "feed", "chains")
V2 = "bi.schema/v1.1@2.0.0"
#: The sections whose golden answers come from the `chains` fixture.
CHAINS = ("chain-summary", "chain-view", "chain-overlap")
CHAIN_DOMAINS = ("AIDC", "wireless", "robotics")


class Runner:
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


# -- building the fixtures ----------------------------------------------------------------


def _put(store: BiStore, entity_type: str, *rows: dict[str, Any]) -> None:
    planned = [
        PlannedRow(row=n, entity_type=entity_type, canonical_key=values["name"],
                   name=values["name"], values={"domain": ["AIDC"], **values}, synthetic=False)
        for n, values in enumerate(rows, start=1)
    ]  # fmt: skip
    store.apply(planned, filename="fixture.csv", entity_type=entity_type, actor="tester")


def robotics(tmp_path: Path) -> BiStore:
    store = BiStore(tmp_path / "robotics")
    service.load_demo(store)
    return store


def market(ws: Path) -> BiStore:
    status, reply = route(ws, "tester", "POST", "/api/bi/datasets", {},
                          {"name": "m", "schema": V2})  # fmt: skip
    assert status == 200, reply
    store = BiStore(ws, "m")
    _put(
        store,
        "Node",
        {"name": "L1-CMP-Accelerator", "layer": "L1"},
        {"name": "L3-PWR-Rack", "layer": "L3"},
        {"name": "X-Shared-Lab", "layer": "X"},
    )
    _put(store, "Technology", {"name": "800VDC"})
    _put(
        store,
        "Ecosystem",
        {
            "name": "Power Co",
            "node": "L3-PWR-Rack",
            "technologies": ["800VDC"],
            "role": "power-system",
        },
        {"name": "Lab Co", "nodes": ["L1-CMP-Accelerator", "L3-PWR-Rack"], "role": "chipset"},
    )
    _put(store, "Account", {"name": "ODM Co"}, {"name": "Quiet Co"})
    _put(store, "Competitor", {"name": "Rival"})
    _put(store, "Application", {"name": "Rack power test"})
    _put(store, "TestSolution",
         {"name": "Our power suite", "applications": ["Rack power test"], "status": "planning"},
         {"name": "Rival suite", "vendor": "Rival", "applications": ["Rack power test"]},
         {"name": "Odd suite", "vendor": "R&S"})  # fmt: skip
    _put(store, "Trend",
         {"name": "800V racks", "affected_nodes": ["L3-PWR-Rack"], "related_tech": ["800VDC"],
          "related_ecosystem": ["Power Co"], "time_to_demand": "0-6m", "measurement_impact": 3,
          "our_fit": 2})  # fmt: skip
    _put(
        store,
        "CustomerProduct",
        {
            "name": "AI Rack 1",
            "account": "ODM Co",
            "node": "L3-PWR-Rack",
            "technologies": ["800VDC"],
            "launch_date": "2027-01-15",
            "inferred_applications": ["Rack power test"],
            "ecosystem": ["Power Co", "Ghost Co"],
        },
    )
    _put(store, "SupplyLink",
         {"name": "Power Co → ODM Co", "supplier": "Power Co", "customer": "ODM Co",
          "customer_products": ["AI Rack 1"], "evidence_grade": "B", "supply_stage": "pilot",
          "source": "報告 §7"},
         {"name": "Lab Co → ODM Co", "supplier": "Lab Co", "customer": "ODM Co",
          "evidence_grade": "D", "nodes": ["L1-CMP-Accelerator"]})  # fmt: skip
    _put(store, "RevenueFact",
         {"name": "ODM Co 2025", "company": "ODM Co", "rev_layer": "company", "amount": 100.0,
          "basis": "reported", "period": "2025"})  # fmt: skip
    _put(store, "Opportunity",
         {"name": "Deal open", "deal_stage": "proposal", "our_solutions": ["Rival suite"],
          "applications": ["Rack power test"]},
         {"name": "Deal lost", "deal_stage": "lost", "our_solutions": ["Our power suite"],
          "applications": ["Rack power test"], "competitors": ["Rival"]})  # fmt: skip
    _put(store, "WinLoss", {"name": "Lost to Rival", "competitors": ["Rival"], "outcome": "lost",
                            "primary_reason": "price"})  # fmt: skip
    _put(store, "RoadmapRequest", {"name": "Faster sweep", "impact": 4, "customer_count": 3,
                                   "request_status": "submitted"})  # fmt: skip
    _put(
        store,
        "VisitLog",
        {
            "name": "",
            "date": "2026-07-01",
            "title": "Kick-off",
            "opportunity": "Deal open",
            "follow_up_date": "2026-08-01",
        },
    )
    _put(store, "Battlecard",
         {"name": "vs Rival", "competitor": "Rival", "content_status": "draft"})  # fmt: skip
    _put(store, "Ecosystem", {"name": "SAMPLE-Fake Co", "node": "L3-PWR-Rack"})
    return store


def feed(tmp_path: Path) -> BiStore:
    ws = tmp_path / "feed"
    ws.mkdir()
    copy = tmp_path / "feed-shared" / "vault"
    shutil.copytree(feed_fixtures.VAULT_DIR, copy)
    feed_fixtures.join(ws, copy)
    return BiStore(ws, vault.dataset_name(feed_fixtures.VAULT_ID))


def new_vault(tmp_path: Path, schema: str, name: str, *, pack: bool = False) -> tuple[Path, str]:
    ws = tmp_path / f"ws-{name}"
    ws.mkdir(parents=True)
    shared = tmp_path / f"shared-{name}"
    shared.mkdir()
    made = _ok(_call(ws, "POST", "/api/bi/vaults", {
        "path": str(shared), "title": f"Pack {name}", "purpose": "虛構", "schema": schema,
        "author": "alice", "id": f"pack-{name}", "default_pack": pack}))  # fmt: skip
    return ws, str(made["vault"]["id"])


def chain_cards(store: BiStore) -> None:
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


def chain_config(registry: Any) -> dict[str, Any]:
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


def chains(tmp_path: Path, *, migrated: bool) -> tuple[BiStore, str]:
    """The `chains` vault with its domain configuration, migrated (D3) or not."""
    ws, vault_id = new_vault(tmp_path, "bi.schema/v1.1", "chains")
    store = BiStore(ws, vault.dataset_name(vault_id))
    chain_cards(store)
    registry = catalog.for_store(store)
    target = vault.Vault(ws, vault_id)
    with target.lock:
        saved = domains.validate(chain_config(registry), registry)
        target.repo.stage(vault_skills.DOMAINS_UNIT, json.dumps(saved, ensure_ascii=False))
    _commit(ws, vault_id, "領域設定")
    if migrated:
        url = f"/api/bi/vaults/{vault_id}/migrate-domains"
        plan = _ok(_call(ws, "POST", url, {}))
        _ok(_call(ws, "POST", url, {"apply": True, "token": plan["token"]}))
    return store, vault_id


def build(name: str, tmp_path: Path, *, migrated: bool = True) -> BiStore:
    """A fixture under a fixed clock and seeded ids."""
    with feed_fixtures.frozen():
        if name == "robotics":
            return robotics(tmp_path)
        if name == "market":
            return market(tmp_path / "market")
        if name == "feed":
            return feed(tmp_path)
        return chains(tmp_path, migrated=migrated)[0]


# -- golden answers -----------------------------------------------------------------------


def key(domain: str, include_sample: bool) -> str:
    return f"{domain}|{'sample' if include_sample else 'real'}"


def domains_of(registry: Any) -> list[str]:
    return sorted({*registry.domains, "robotics", "wireless", "AIDC"})


def golden(name: str) -> dict[str, Any]:
    return dict(json.loads((GOLDEN / f"{name}.json").read_text(encoding="utf-8")))


def pack_results(store: BiStore, expected: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """The pack's answers for every (slug, parameters) the golden file holds."""
    registry = catalog.for_store(store)
    code = {a["slug"]: packs.fill(a["code"], registry) for a in packs.default_pack()["analyses"]}
    run = Runner(store)
    found: dict[str, dict[str, Any]] = {}
    try:
        for slug, tables in expected.items():
            for where in tables:
                params: dict[str, Any] = {}
                if where != "*":
                    domain, sample = where.split("|")
                    params = {"domain": domain, "include_sample": sample == "sample",
                              "today": TODAY.isoformat()}  # fmt: skip
                found.setdefault(slug, {})[where] = json.loads(json.dumps(run(code[slug], params)))
    finally:
        run.close()
    return found
