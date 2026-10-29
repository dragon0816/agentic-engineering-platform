"""BI vault V12 (owner 2026-10-29; `docs/phases/BI_VAULT.md` §12): the
manager's dashboard sections §20–§31 and the chains A–A3, built in.

A small fictional market on schema 2.0.0: evidence grades, revenue layers,
win-loss, roadmap, enablement, contact, timing and chain integrity, the chains
from the domain configuration, sample cards left out unless asked for, and a
schema v4 dataset that only gets the sections its types allow. All data is
fictional.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from capabilities.bi_cards import dashboard, market
from capabilities.bi_cards.store import BiStore, PlannedRow
from host_runtime.bi_cards_api import route

V2 = "bi.schema/v1.1@2.0.0"
TODAY = date(2026, 10, 29)


def _call(ws: Path, method: str, path: str, body: Any = None, **query: str) -> dict[str, Any]:
    status, reply = route(ws, "tester", method, path, query, body)
    assert status == 200, reply
    return dict(reply)


def _put(store: BiStore, entity_type: str, *rows: dict[str, Any]) -> None:
    planned = [
        PlannedRow(
            row=n,
            entity_type=entity_type,
            canonical_key=values["name"],
            name=values["name"],
            values={"domain": ["AIDC"], **values},
            synthetic=False,
        )
        for n, values in enumerate(rows, start=1)
    ]
    store.apply(planned, filename="fixture.csv", entity_type=entity_type, actor="tester")


def _market(ws: Path) -> BiStore:
    _call(ws, "POST", "/api/bi/datasets", {"name": "m", "schema": V2})
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
    _put(
        store,
        "TestSolution",
        {"name": "Our power suite", "applications": ["Rack power test"], "status": "planning"},
        {"name": "Rival suite", "vendor": "Rival", "applications": ["Rack power test"]},
        {"name": "Odd suite", "vendor": "R&S"},
    )
    _put(
        store,
        "Trend",
        {"name": "800V racks", "affected_nodes": ["L3-PWR-Rack"], "related_tech": ["800VDC"],
         "related_ecosystem": ["Power Co"], "time_to_demand": "0-6m", "measurement_impact": 3,
         "our_fit": 2},
    )  # fmt: skip
    _put(
        store,
        "CustomerProduct",
        {"name": "AI Rack 1", "account": "ODM Co", "node": "L3-PWR-Rack",
         "technologies": ["800VDC"],
         "launch_date": "2027-01-15", "inferred_applications": ["Rack power test"],
         "ecosystem": ["Power Co", "Ghost Co"]},
    )  # fmt: skip
    _put(
        store,
        "SupplyLink",
        {"name": "Power Co → ODM Co", "supplier": "Power Co", "customer": "ODM Co",
         "customer_products": ["AI Rack 1"], "evidence_grade": "B", "supply_stage": "pilot",
         "source": "報告 §7"},
        {"name": "Lab Co → ODM Co", "supplier": "Lab Co", "customer": "ODM Co",
         "evidence_grade": "D", "nodes": ["L1-CMP-Accelerator"]},
    )  # fmt: skip
    _put(
        store,
        "RevenueFact",
        {"name": "ODM Co 2025", "company": "ODM Co", "rev_layer": "company", "amount": 100.0,
         "basis": "reported", "period": "2025"},
    )  # fmt: skip
    _put(
        store,
        "Opportunity",
        {"name": "Deal open", "deal_stage": "proposal", "our_solutions": ["Rival suite"],
         "applications": ["Rack power test"]},
        {"name": "Deal lost", "deal_stage": "lost", "our_solutions": ["Our power suite"],
         "applications": ["Rack power test"], "competitors": ["Rival"]},
    )  # fmt: skip
    _put(store, "WinLoss", {"name": "Lost to Rival", "competitors": ["Rival"], "outcome": "lost",
                            "primary_reason": "price"})  # fmt: skip
    _put(store, "RoadmapRequest", {"name": "Faster sweep", "impact": 4, "customer_count": 3,
                                   "request_status": "submitted"})  # fmt: skip
    _put(store, "VisitLog", {"name": "", "date": "2026-07-01", "title": "Kick-off",
                             "opportunity": "Deal open",
                             "follow_up_date": "2026-08-01"})  # fmt: skip
    _put(
        store, "Battlecard", {"name": "vs Rival", "competitor": "Rival", "content_status": "draft"}
    )
    _put(store, "Ecosystem", {"name": "SAMPLE-Fake Co", "node": "L3-PWR-Rack"})
    return store


def _sections(store: BiStore, **options: Any) -> dict[str, dict[str, Any]]:
    board = dashboard.dashboard(store, "AIDC", **options)
    return {s["id"]: s for s in board["sections"]}


def _label(cell: Any) -> str:
    return str(cell["label"]) if isinstance(cell, dict) else str(cell)


def test_market_sections_follow_the_managers_rules(tmp_path: Path) -> None:
    store = _market(tmp_path)
    found = _sections(store)
    assert {"20", "21", "22", "23", "24", "25", "26", "27", "28", "29", "30", "31"} <= set(found)
    assert not {"A", "A2", "A3"} & set(found)  # no chains configured yet
    grades = {r[0]: r[-1] for r in found["27"]["rows"][:4]}
    assert grades == {"A 原廠/具名確認": 0, "B 可信報導/公司說明": 1, "C 產品能力": 0,
                      "D 傳聞/待確認": 1}  # fmt: skip
    assert any("缺 source_date" in str(r[-1]) for r in found["27"]["rows"][4:])
    layers = {_label(r[0]): r[-1] for r in found["28"]["rows"]}
    assert layers["ODM Co"] == "⚠ 缺 區段層、客戶層未揭露"
    assert layers["Quiet Co"] == "⚠ 無任何 RevenueFact"
    assert found["21"]["rows"][0] == ["Rival", 1, 0, 1, "price ×1"]
    assert found["22"]["rows"][0][4] == 12 and "無證據來源" in found["22"]["rows"][0][-1]
    enable = {_label(r[0]): r[-1] for r in found["23"]["rows"]}
    assert enable["Rival"] == "OK" and "缺 Pitch、Demo、Battlecard" in enable["Our power suite"]
    supply = found["25"]["rows"][0]
    assert supply[2] == "Power Co" and "1 筆無證據卡" in supply[-1]  # Ghost Co has no SupplyLink
    integrity = {_label(r[0]): r[-1] for r in found["29"]["rows"]}
    assert integrity["Odd suite"] == "⚠ 我方方案請清空 vendor"
    assert "our_solutions 連到對手方案" in integrity["Deal open"]
    assert next(f for f in found["29"]["flags"] if "對手方案" in f["text"])["level"] == "red"
    assert found["20"]["rows"][0][2:5] == [1, 1, 1]  # by technology, by node, products


def test_dated_sections_take_today() -> None:
    cards: dict[str, list[dashboard.Card]] = {}

    def card(type_name: str, **values: Any) -> None:
        item = dashboard.Card({"domain": ["AIDC"], **values})
        item.update(_name=values["name"], _key=values["name"], _id=values["name"], _type=type_name)
        cards.setdefault(type_name, []).append(item)

    card("Opportunity", name="Deal open", deal_stage="proposal")
    card("VisitLog", name="v1", date="2026-07-01", opportunity="Deal open",
         follow_up_date="2026-08-01")  # fmt: skip
    contact = market.customer_contact(cards, "AIDC", today=TODAY)
    assert contact["rows"][0][-1] == "⚠ 超過 60 天" and contact["rows"][1][-1] == "⚠ 跟進逾期"
    card("Trend", name="T", affected_nodes=["N"], time_to_demand="0-6m")
    card("CustomerProduct", name="P", node="N", launch_date="2027-01-15",
         inferred_applications=["App"])  # fmt: skip
    card("TestSolution", name="S", applications=["App"], status="planning")
    timing = market.timing_gaps(cards, "AIDC", today=TODAY)
    assert timing["rows"][0][2] == 2.6 and timing["rows"][0][-1] == "🟡 方案規劃中"


def test_chains_come_from_the_domain_configuration(tmp_path: Path) -> None:
    store = _market(tmp_path)
    config = {"domains": [{"id": "AIDC", "chains": [
        {"id": "CMP", "label": "運算鏈", "node_pattern": r"^(L\d|X)-CMP-"},
        {"id": "PWR", "label": "電力鏈", "node_pattern": r"^(L\d|X)-PWR-",
         "nodes": ["X-Shared-Lab"]},
        {"id": "LAB", "label": "實驗室", "nodes": ["X-Shared-Lab"]}]}]}  # fmt: skip
    _call(
        tmp_path, "POST", "/api/bi/domains", {"dataset": "m", "config": config, "base_revision": 0}
    )
    found = _sections(store)
    ids = [s["id"] for s in dashboard.dashboard(store, "AIDC")["sections"]]
    assert ids[:3] == ["A", "A2", "A3"]  # the chains first, as in the manager's dashboards
    summary = {r[0]: r for r in found["A"]["rows"]}
    assert summary["CMP 運算鏈"][1] == 1 and summary["PWR 電力鏈"][1] == 2
    assert summary["PWR 電力鏈"][2] == 1  # X-Shared-Lab is shared with LAB
    # A SupplyLink is in a chain through its own nodes: only Lab Co's names one.
    assert summary["CMP 運算鏈"][7] == 1 and summary["PWR 電力鏈"][7] == 0
    overlap = {(r[0], _label(r[1])): r[2] for r in found["A3"]["rows"]}
    assert overlap[("共用節點", "X-Shared-Lab")] == "PWR+LAB"  # in configuration order
    assert overlap[("共用公司", "Lab Co")] == "CMP+PWR"
    view = [r for r in found["A2"]["rows"] if r[0] == "CMP"]
    assert _label(view[0][1]) == "L1-CMP-Accelerator" and view[0][-1] == "⚠ 有 Ecosystem 無 Trend"


def test_sample_cards_are_left_out_unless_asked_for(tmp_path: Path) -> None:
    store = _market(tmp_path)
    names = {r[0] for r in _sections(store)["30"]["rows"]}
    assert "sample-fake co" not in names
    with_samples = dashboard.dashboard(store, "AIDC", include_sample=True)
    a2 = _call(tmp_path, "GET", "/api/bi/dashboard", dataset="m", domain="AIDC", include_sample="1")
    assert a2["include_sample"] is True and with_samples["include_sample"] is True
    rows = next(s for s in with_samples["sections"] if s["id"] == "20")["rows"]
    assert rows[0][3] == 2  # the sample ecosystem now counts by node


def test_a_v4_dataset_gets_only_what_its_types_allow(tmp_path: Path) -> None:
    _call(tmp_path, "POST", "/api/bi/demo/load", {"dataset": "demo"})
    ids = [s["id"] for s in dashboard.dashboard(BiStore(tmp_path), "robotics")["sections"]]
    # §20, §26 and §29–§31 read v4 types; the others need 2.0.0's.
    assert {"20", "26", "29", "30", "31"} <= set(ids)
    assert not {"21", "22", "23", "24", "25", "27", "28", "A"} & set(ids)


def test_the_chat_can_ask_for_a_market_section(tmp_path: Path) -> None:
    store = _market(tmp_path)
    assert "supply_grades" in dashboard.analysis_names()
    (grades,) = dashboard.analysis(store, "supply_grades", "AIDC")
    assert grades["id"] == "27"
    assert [s["id"] for s in dashboard.analysis(store, "gaps", "AIDC")] == ["6"]
