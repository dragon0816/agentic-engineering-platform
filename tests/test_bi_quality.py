"""BI vault V13 (owner 2026-10-29; `docs/phases/BI_VAULT.md` §12): the quality
checks of the manager's `validate.py`, built in and general.

One fictional dataset on schema 2.0.0 with one fault per check; the report
names each card, the dashboard shows it as section Q, the chat can ask for
it, and an import marks `SAMPLE-` rows as samples. All data is fictional.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from capabilities.bi_cards import catalog, dashboard, quality
from capabilities.bi_cards.store import BiStore, PlannedRow
from host_runtime.bi_cards_api import route

V2 = "bi.schema/v1.1@2.0.0"


def _call(ws: Path, method: str, path: str, body: Any = None, **query: str) -> dict[str, Any]:
    status, reply = route(ws, "tester", method, path, query, body)
    assert status == 200, reply
    return dict(reply)


def _put(store: BiStore, entity_type: str, *rows: dict[str, Any], synthetic: bool = False) -> None:
    planned = [
        PlannedRow(
            row=n,
            entity_type=entity_type,
            canonical_key=values["name"],
            name=values["name"],
            values={"domain": ["AIDC"], **values},
            synthetic=synthetic,
        )
        for n, values in enumerate(rows, start=1)
    ]
    store.apply(planned, filename="fixture.csv", entity_type=entity_type, actor="tester")


def _faulty(ws: Path) -> BiStore:
    _call(ws, "POST", "/api/bi/datasets", {"name": "m", "schema": V2})
    config = {
        "node_name_pattern": r"^(L[1-5]|X)-",
        "domains": [{"id": "AIDC", "nodes": ["L1-CMP-Chip"]}],
    }
    _call(ws, "POST", "/api/bi/domains", {"dataset": "m", "config": config, "base_revision": 0})
    store = BiStore(ws, "m")
    _put(store, "Node", {"name": "L1-CMP-Chip"}, {"name": "L2-CMP-Board"}, {"name": "Rack"})
    _put(store, "Account", {"name": "ODM Co"}, {"name": "Twin Co"})
    _put(store, "Ecosystem", {"name": "Twin Co", "node": "L1-CMP-Chip"})
    _put(store, "Competitor", {"name": "Rival"})
    _put(store, "SupplyLink",
         {"name": "A without source", "supplier": "Ghost Co", "customer": "ODM Co",
          "evidence_grade": "A"},
         {"name": "B with pending date", "supplier": "Twin Co", "customer": "ODM Co",
          "evidence_grade": "B", "source": "報告 §3", "body": "來源日期待補"})  # fmt: skip
    _put(store, "RevenueFact",
         {"name": "Customer layer", "company": "ODM Co", "rev_layer": "customer", "source": "x"},
         {"name": "Company with customer", "company": "ODM Co", "rev_layer": "company",
          "customer": "Rival", "source": "x"})  # fmt: skip
    _put(store, "CustomerProduct", {"name": "Box", "account": "ODM Co"})
    _put(store, "Battlecard", {"name": "vs Account", "competitor": "ODM Co"})
    _put(store, "Ecosystem", {"name": "SAMPLE-Unmarked Co"})
    _put(store, "Ecosystem", {"name": "SAMPLE-Marked Co"}, synthetic=True)
    return store


def _messages(report: dict[str, Any]) -> dict[str, list[str]]:
    return {c["id"]: [i["message"] for i in c["items"]] for c in report["checks"]}


def test_each_check_finds_its_fault_and_names_the_card(tmp_path: Path) -> None:
    store = _faulty(tmp_path)
    report = _call(tmp_path, "GET", "/api/bi/quality", dataset="m")
    found = _messages(report)
    assert any("「Ghost Co」還沒有卡片" in m for m in found["link_unresolved"])
    assert any("「ODM Co」是 Account，應該是 Competitor" in m for m in found["link_wrong_type"])
    assert found["same_name"] == ["「twin co」同時是 Account、Ecosystem；請合併或改名"]
    assert found["sample_not_marked"] == ["名稱是 SAMPLE-，但沒有標成示範資料，可能被當成真實資料"]
    assert sorted(found["evidence_source"]) == [
        "A 級證據沒有來源日期，內文也沒有註明「來源日期待補」",
        "A 級證據沒有來源（source）",
    ]  # the B link explains its blank date
    assert sorted(found["revenue_layer"]) == ["company 層不該填客戶", "客戶層卻沒有填客戶"]
    assert found["node_format"] == ["名稱不符合 ^(L[1-5]|X)-"]
    assert len(found["node_not_listed"]) == 2  # L2-CMP-Board and Rack were proposed
    assert found["product_without_node"]
    item = next(c for c in report["checks"] if c["id"] == "node_format")["items"][0]
    assert item["card"]["label"] == "Rack" and item["card"]["cite"] == "Node:Rack"
    assert report["totals"]["warn"] == 3 and report["totals"]["issue"] >= 10
    assert store.card_rows()  # read only: the cards are as they were


def test_a_number_must_be_written_in_its_fact_quote(tmp_path: Path) -> None:
    store = _faulty(tmp_path)
    fact = store.find("RevenueFact", "Customer layer")
    assert fact is not None
    store.set_field(fact["id"], "amount", 11586.0, base_version=fact["version"], actor="tester")
    with store._db(write=True) as db:  # noqa: SLF001 - evidence as an AI run would record it
        for excerpt in ("營收 1兆1,586億元", "營收約 75–80 億元"):
            db.execute(
                "INSERT INTO evidence (card_id, field, run_id, source_id, source_name, locator, "
                "excerpt, basis, at) "
                "VALUES (?, 'amount', 'r1', 's1', 'r.md', '{}', ?, 'fact', 'x')",
                (fact["id"], excerpt),
            )
    assert not _messages(quality.check(store, catalog.for_store(store)))["number_ungrounded"]
    other = store.find("RevenueFact", "Company with customer")
    assert other is not None
    store.set_field(other["id"], "amount", 77.5, base_version=other["version"], actor="tester")
    with store._db(write=True) as db:  # noqa: SLF001
        db.execute(
            "INSERT INTO evidence (card_id, field, run_id, source_id, source_name, locator, "
            "excerpt, basis, at) VALUES (?, 'amount', 'r1', 's1', 'r.md', '{}', '約 75–80 億元', "
            "'fact', 'x')",
            (other["id"],),
        )
    (message,) = _messages(quality.check(store, catalog.for_store(store)))["number_ungrounded"]
    assert "77.5 不在引用的原文「約 75–80 億元」裡" in message


def test_the_dashboard_and_the_chat_show_the_report(tmp_path: Path) -> None:
    store = _faulty(tmp_path)
    sections = dashboard.dashboard(store, "AIDC")["sections"]
    assert sections[-1]["id"] == "Q" and sections[-1]["rows"]
    assert {f["level"] for f in sections[-1]["flags"]} == {"red", "warn"}
    assert "quality" in dashboard.analysis_names()
    (asked,) = dashboard.analysis(store, "quality", "AIDC")
    assert asked["id"] == "Q" and asked["rows"] == sections[-1]["rows"]


def test_an_import_marks_sample_rows_as_samples(tmp_path: Path) -> None:
    _call(tmp_path, "POST", "/api/bi/datasets", {"name": "m", "schema": V2})
    csv = "name,role\nSAMPLE-Fake Co,chipset\nReal Co,chipset\n"
    preview = _call(tmp_path, "POST", "/api/bi/import/preview",
                    {"dataset": "m", "entity_type": "Ecosystem", "filename": "e.csv",
                     "csv_text": csv})  # fmt: skip
    _call(tmp_path, "POST", "/api/bi/import/apply", {"preview_id": preview["preview_id"]})
    rows = {r["name"]: r["synthetic"] for r in BiStore(tmp_path, "m").card_rows()}
    assert rows == {"SAMPLE-Fake Co": 1, "Real Co": 0}
    report = _call(tmp_path, "GET", "/api/bi/quality", dataset="m")
    assert not _messages(report)["sample_not_marked"]
