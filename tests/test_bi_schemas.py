"""Per-dataset schemas for BI cards (owner 2026-10-21: 「只讓資料集換 schema」).

A dataset is bound to one schema id@version when it is created. Cards,
import, detail, field edits and history follow that schema; the Dashboard,
the demo load and the chat's `bi__query` stay BI-only. Installed schemas
live under `<workspace>/bi/schemas/` and are immutable. Every test uses a
temporary workspace; the shipped example 「產品規格」 drives the non-BI path.
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from capabilities.bi_cards import catalog, service
from capabilities.bi_cards.capability import QueryHandler, QueryRequest
from capabilities.bi_cards.manifest import PROCEDURE
from capabilities.bi_cards.store import LEGACY_SCHEMA, BiStore
from capabilities.runtime import CapabilityRefused
from common.execution import RequestContext, TraceIdentifiers
from host_runtime.bi_cards_api import route
from host_runtime.bi_cards_tools import FAILURE_TEXT

ACTOR = "tester"
EXAMPLE = "example/product-spec@1.0.0"


def _call(root: Path, method: str, path: str, body: Any = None, **query: str) -> Any:
    return route(root, ACTOR, method, path, query, body)


def _example_text() -> str:
    text: str = catalog.example()["schema"]["json_text"]
    return text


def _install(root: Path, text: str | None = None, filename: str = "spec.json") -> Any:
    return _call(
        root,
        "POST",
        "/api/bi/schemas/install",
        {"filename": filename, "json_text": _example_text() if text is None else text},
    )


def _minimal(**changes: Any) -> dict[str, Any]:
    document: dict[str, Any] = {
        "schema_id": "team/notes",
        "version": "1.0.0",
        "title": "筆記",
        "types": [
            {
                "name": "Note",
                "label": "筆記",
                "fields": [{"name": "name", "label": "標題", "kind": "str", "class": "sourced"}],
            }
        ],
    }
    document.update(changes)
    return document


def _spec_dataset(root: Path, name: str = "spec") -> None:
    assert _install(root)[0] == 200
    status, created = _call(root, "POST", "/api/bi/datasets", {"name": name, "schema": EXAMPLE})
    assert status == 200, created


def _import(root: Path, dataset: str, filename: str, text: str, entity: str | None) -> Any:
    status, preview = _call(
        root,
        "POST",
        "/api/bi/import/preview",
        {"dataset": dataset, "filename": filename, "csv_text": text, "entity_type": entity},
    )
    assert status == 200, preview
    return preview


def _apply(root: Path, preview: dict[str, Any]) -> dict[str, Any]:
    status, applied = _call(
        root, "POST", "/api/bi/import/apply", {"preview_id": preview["preview_id"]}
    )
    assert status == 200, applied
    return dict(applied)


def _load_example(root: Path, dataset: str = "spec") -> None:
    for item in catalog.example()["csv"]:
        _apply(root, _import(root, dataset, item["filename"], item["text"], item["entity_type"]))


def _cards(root: Path, dataset: str, **query: str) -> list[dict[str, Any]]:
    status, found = _call(root, "GET", "/api/bi/cards", dataset=dataset, **query)
    assert status == 200, found
    return list(found["cards"])


# -- schema sources ------------------------------------------------------------


def test_the_shipped_schema_is_listed_and_the_example_is_not_installed(tmp_path: Path) -> None:
    status, listed = _call(tmp_path, "GET", "/api/bi/schemas")
    assert status == 200
    # Five shipped versions: v4's 1.1.0, v8's 2.0.0 (BI vault V9), 3.0.0 (BI D1),
    # 4.0.0 (a list of domains on three more types) and 5.0.0 (the card model).
    shipped, v8, v3, v4, v5 = listed["schemas"]
    assert shipped["id"] == "bi.schema/v1.1" and shipped["version"] == "1.1.0"
    assert shipped["source"] == "shipped" and shipped["ref"] == LEGACY_SCHEMA
    assert len(shipped["types"]) == 12 and {"name", "label"} == set(shipped["types"][0])
    assert (v8["ref"], v8["source"], len(v8["types"])) == ("bi.schema/v1.1@2.0.0", "shipped", 21)
    assert (v3["ref"], v3["source"], len(v3["types"])) == ("bi.schema/v1.1@3.0.0", "shipped", 21)
    assert (v4["ref"], v4["source"], len(v4["types"])) == ("bi.schema/v1.1@4.0.0", "shipped", 21)
    assert (v5["ref"], v5["source"], len(v5["types"])) == ("bi.schema/v1.1@5.0.0", "shipped", 21)
    assert {"id", "version", "title", "types", "source"} <= set(shipped)
    assert not (tmp_path / "bi").exists()  # listing writes nothing


def test_a_valid_schema_installs_once_and_is_listed(tmp_path: Path) -> None:
    status, answer = _install(tmp_path)
    assert status == 200
    assert answer["ok"] is True and answer["id"] == "example/product-spec"
    assert answer["version"] == "1.0.0" and answer["already"] is False
    stored = tmp_path / "bi" / "schemas" / "example" / "product-spec@1.0.0.json"
    assert stored.is_file()
    status, listed = _call(tmp_path, "GET", "/api/bi/schemas")
    installed = [s for s in listed["schemas"] if s["source"] == "installed"]
    assert [s["ref"] for s in installed] == [EXAMPLE]
    assert [t["name"] for t in installed[0]["types"]] == [
        "Supplier",
        "Component",
        "Product",
        "SpecItem",
    ]
    assert installed[0]["title"] == "產品規格（範例）" and installed[0]["dashboard"] is False
    # The same content again, even re-formatted, is a no-op.
    again = json.dumps(json.loads(_example_text()), ensure_ascii=False)
    status, repeated = _install(tmp_path, again)
    assert status == 200 and repeated["already"] is True


def test_an_installed_version_is_immutable(tmp_path: Path) -> None:
    _install(tmp_path)
    stored = tmp_path / "bi" / "schemas" / "example" / "product-spec@1.0.0.json"
    before = stored.read_bytes()
    changed = json.loads(_example_text())
    changed["title"] = "產品規格（改過）"
    status, refused = _install(tmp_path, json.dumps(changed, ensure_ascii=False))
    assert status == 409 and refused["ok"] is False
    assert refused["code"] == "schema_version_exists"
    assert "不能修改" in refused["message"]
    assert refused["errors"][0]["path"] == "version"
    assert stored.read_bytes() == before
    # A new version installs beside it.
    changed["version"] = "1.0.1"
    status, newer = _install(tmp_path, json.dumps(changed, ensure_ascii=False))
    assert status == 200 and newer["version"] == "1.0.1"


def test_an_invalid_schema_is_refused_with_errors_naming_each_field(tmp_path: Path) -> None:
    bad = _minimal(title="", colour="red")
    bad["types"][0]["fields"].append(
        {"name": "parent", "label": "上層", "kind": "link", "class": "sourced", "link_to": "Nope"}
    )
    bad["types"][0]["fields"].append({"name": "size", "label": "大小", "kind": "decimal"})
    status, refused = _install(tmp_path, json.dumps(bad, ensure_ascii=False))
    assert status == 400 and refused["ok"] is False and refused["code"] == "schema_invalid"
    paths = {e["path"]: e["message"] for e in refused["errors"]}
    assert "title" in paths and "colour" in paths
    assert "目標類型「Nope」" in paths["types[0]（Note）.fields[1]（parent）.link_to"]
    assert "'str'" in paths["types[0]（Note）.fields[2]（size）.kind"]  # lists the allowed kinds
    assert "types[0]（Note）.fields[2]（size）.class" in paths
    assert all(e["message"] for e in refused["errors"])
    assert not (tmp_path / "bi" / "schemas").exists()


@pytest.mark.parametrize(
    ("text", "code"),
    [
        ("{not json", "schema_json_invalid"),
        ("", "schema_missing_text"),
        (json.dumps(_minimal(schema_id="bi.schema/v9")), "schema_bi_not_compatible"),
        (json.dumps(_minimal(version="1.0")), "schema_invalid"),
        (json.dumps(_minimal(types=[])), "schema_invalid"),
    ],
)
def test_malformed_schema_files_are_refused(tmp_path: Path, text: str, code: str) -> None:
    status, refused = _install(tmp_path, text)
    assert status == 400 and refused["code"] == code
    assert refused["message"] and isinstance(refused["errors"], list)


def test_only_json_files_are_accepted(tmp_path: Path) -> None:
    status, refused = _install(tmp_path, json.dumps(_minimal()), filename="notes.csv")
    assert status == 400 and refused["code"] == "schema_not_json"


def test_the_bi_prefix_is_reserved_for_the_shipped_schema(tmp_path: Path) -> None:
    status, refused = _install(tmp_path, json.dumps(_minimal(schema_id="bi.schema/v2")))
    assert status == 400
    assert any(e["path"] == "schema_id" and "保留" in e["message"] for e in refused["errors"])


# -- datasets and their binding ----------------------------------------------------


def test_a_dataset_is_created_with_a_schema_and_keeps_it(tmp_path: Path) -> None:
    _install(tmp_path)
    status, created = _call(
        tmp_path, "POST", "/api/bi/datasets", {"name": "spec-2026", "schema": EXAMPLE}
    )
    assert status == 200 and created["ok"] is True
    assert created["dataset"] == {
        "name": "spec-2026",
        "cards": 0,
        "updated": None,
        "schema": EXAMPLE,
        "dashboard": False,
        "subscribed": False,
        "read_only": False,
    }
    assert BiStore(tmp_path, "spec-2026").schema_ref() == EXAMPLE  # persisted in bi.sqlite
    with sqlite3.connect(tmp_path / "bi" / "spec-2026" / "bi.sqlite") as db:
        assert db.execute("SELECT value FROM meta WHERE key = 'schema'").fetchone() == (EXAMPLE,)
    status, listed = _call(tmp_path, "GET", "/api/bi/datasets")
    assert listed["datasets"] == [created["dataset"]]
    # A BI dataset: the bare id picks its newest version (the shipped 3.0.0).
    status, bi = _call(
        tmp_path, "POST", "/api/bi/datasets", {"name": "market", "schema": "bi.schema/v1.1"}
    )
    assert status == 200 and bi["dataset"]["schema"] == "bi.schema/v1.1@5.0.0"
    assert bi["dataset"]["dashboard"] is True


def test_a_dataset_schema_cannot_be_changed(tmp_path: Path) -> None:
    _spec_dataset(tmp_path)
    status, refused = _call(
        tmp_path, "POST", "/api/bi/datasets", {"name": "spec", "schema": LEGACY_SCHEMA}
    )
    assert status == 409 and refused["code"] == "dataset_exists"
    assert refused["schema"] == EXAMPLE and "不能更換 schema" in refused["message"]
    assert BiStore(tmp_path, "spec").schema_ref() == EXAMPLE
    # Writing through the import does not re-bind it either.
    _load_example(tmp_path)
    assert BiStore(tmp_path, "spec").schema_ref() == EXAMPLE


@pytest.mark.parametrize(
    ("name", "status", "code"),
    [
        ("", 400, "dataset_invalid"),
        ("中文", 400, "dataset_invalid"),
        ("a b", 400, "dataset_invalid"),
        ("x" * 41, 400, "dataset_invalid"),
        ("schemas", 400, "dataset_invalid"),
        ("../up", 400, "dataset_invalid"),
    ],
)
def test_dataset_names_follow_the_rules(tmp_path: Path, name: str, status: int, code: str) -> None:
    answer = _call(tmp_path, "POST", "/api/bi/datasets", {"name": name, "schema": LEGACY_SCHEMA})
    assert answer[0] == status and answer[1]["code"] == code, answer
    assert not any((tmp_path / "bi").glob("*/bi.sqlite"))


def test_dataset_names_are_unique_ignoring_case_and_need_a_known_schema(tmp_path: Path) -> None:
    ok = _call(tmp_path, "POST", "/api/bi/datasets", {"name": "Sales_1", "schema": LEGACY_SCHEMA})
    assert ok[0] == 200
    assert (
        _call(tmp_path, "POST", "/api/bi/datasets", {"name": "x" * 40, "schema": LEGACY_SCHEMA})[0]
        == 200
    )
    clash = _call(
        tmp_path, "POST", "/api/bi/datasets", {"name": "sales_1", "schema": LEGACY_SCHEMA}
    )
    assert clash[0] == 409 and clash[1]["code"] == "dataset_exists"
    unknown = _call(tmp_path, "POST", "/api/bi/datasets", {"name": "n", "schema": "nope@1.0.0"})
    assert unknown[0] == 404 and unknown[1]["code"] == "schema_unknown"
    assert not BiStore(tmp_path, "n").exists


def test_a_legacy_dataset_without_a_binding_is_bi_v1_1(tmp_path: Path) -> None:
    store = BiStore(tmp_path, "demo")
    service.load_demo(store)
    path = tmp_path / "bi" / "demo" / "bi.sqlite"
    with sqlite3.connect(path) as db:  # as written before per-dataset schemas
        db.execute("DROP TABLE meta")
    assert store.schema_ref() == LEGACY_SCHEMA
    status, listed = _call(tmp_path, "GET", "/api/bi/datasets")
    (demo,) = listed["datasets"]
    assert demo["schema"] == LEGACY_SCHEMA and demo["dashboard"] is True and demo["cards"] == 104
    status, board = _call(tmp_path, "GET", "/api/bi/dashboard", dataset="demo", domain="robotics")
    assert status == 200 and board["sections"] and board["domain"] == "robotics"
    status, schema = _call(tmp_path, "GET", "/api/bi/schema", dataset="demo")
    assert schema["ref"] == LEGACY_SCHEMA and len(schema["types"]) == 12
    # Its next write records the binding it always had.
    assert service.load_demo(store)["unchanged"] == 104
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT value FROM meta").fetchall() == [(LEGACY_SCHEMA,)]


def test_the_schema_route_follows_the_dataset(tmp_path: Path) -> None:
    _spec_dataset(tmp_path)
    status, plain = _call(tmp_path, "GET", "/api/bi/schema")
    assert status == 200 and plain["schema_id"] == "bi.schema/v1.1" and plain["bi"] is True
    status, spec = _call(tmp_path, "GET", "/api/bi/schema", dataset="spec")
    assert spec["ref"] == EXAMPLE and spec["bi"] is False and spec["domains"] == []
    assert [t["label"] for t in spec["types"]] == ["供應商", "零組件", "產品", "規格項目"]
    field = spec["types"][1]["fields"][3]
    assert field == {
        "name": "supplier",
        "label": "供應商",
        "type": "link",
        "class": "sourced",
        "enum": None,
        "link_to": "Supplier",
        "list": False,
    }


def test_a_missing_schema_file_is_reported_not_guessed(tmp_path: Path) -> None:
    _spec_dataset(tmp_path)
    (tmp_path / "bi" / "schemas" / "example" / "product-spec@1.0.0.json").unlink()
    status, refused = _call(tmp_path, "GET", "/api/bi/cards", dataset="spec")
    assert status == 400 and refused["code"] == "schema_missing"
    assert EXAMPLE in refused["message"]
    status, listed = _call(tmp_path, "GET", "/api/bi/datasets")
    assert listed["datasets"][0]["schema"] == EXAMPLE  # the list still loads


# -- import, detail and edits follow the dataset's schema -------------------------------


def test_import_into_the_example_schema_previews_applies_and_undoes(tmp_path: Path) -> None:
    _spec_dataset(tmp_path)
    example = {item["entity_type"]: item for item in catalog.example()["csv"]}
    suppliers = _import(tmp_path, "spec", "suppliers.csv", example["Supplier"]["text"], entity=None)
    assert suppliers["entity_type"] == "Supplier"  # guessed from the example's aliases
    columns = {c["source"]: (c["field"], c["status"]) for c in suppliers["columns"]}
    assert columns["供應商名稱"] == ("name", "alias") and columns["等級"] == ("tier", "alias")
    tiers = {
        row["canonical_key"]: next(f["normalized"] for f in row["fields"] if f["field"] == "tier")
        for row in suppliers["rows"]
    }
    assert tiers == {"台達電子": "strategic", "村田製作所": "approved", "新創感測": "trial"}
    assert not BiStore(tmp_path, "spec").card_rows()  # the preview wrote nothing
    assert _apply(tmp_path, suppliers)["applied"]["created"] == 3

    components = _import(
        tmp_path, "spec", "c.csv", example["Component"]["text"], entity="Component"
    )
    rows = {row["canonical_key"]: row for row in components["rows"]}
    power = {f["field"]: f["normalized"] for f in rows["48V 電源模組"]["fields"]}
    assert power["category"] == "power" and power["qualification"] == "approved"
    assert power["rohs"] is True and power["unit_price"] == 1200
    assert power["supplier"] == "台達電子" and not rows["48V 電源模組"]["warnings"]
    missing = [w["code"] for w in rows["主控 MCU"]["warnings"]]
    assert missing == ["link_missing"]  # 恩智浦 is not a supplier card
    _apply(tmp_path, components)
    _apply(tmp_path, _import(tmp_path, "spec", "p.csv", example["Product"]["text"], "Product"))

    specs = _import(tmp_path, "spec", "spec_items.csv", example["SpecItem"]["text"], None)
    assert specs["entity_type"] == "SpecItem"
    assert [row["canonical_key"] for row in specs["rows"]] == [
        "協作機械手臂 A1-最大負重",
        "協作機械手臂 A1-重複精度",
    ]
    assert all(not row["warnings"] for row in specs["rows"])  # the product link resolves
    applied = _apply(tmp_path, specs)
    assert applied["applied"]["created"] == 2
    assert len(_cards(tmp_path, "spec", type="SpecItem")) == 2
    status, undone = _call(
        tmp_path,
        "POST",
        "/api/bi/import/undo",
        {"import_id": applied["import_id"], "dataset": "spec"},
    )
    assert status == 200 and undone["ok"] is True
    assert _cards(tmp_path, "spec", type="SpecItem") == []
    assert len(_cards(tmp_path, "spec")) == 3 + 3 + 1


def test_a_bi_type_is_unknown_in_the_example_dataset(tmp_path: Path) -> None:
    _spec_dataset(tmp_path)
    status, refused = _call(
        tmp_path,
        "POST",
        "/api/bi/import/preview",
        {"dataset": "spec", "csv_text": "應用名稱\nX\n", "entity_type": "Application"},
    )
    assert status == 400 and refused["code"] == "entity_type_unknown"


def test_card_detail_edits_and_history_follow_the_dataset_schema(tmp_path: Path) -> None:
    _spec_dataset(tmp_path)
    _load_example(tmp_path)
    (product,) = _cards(tmp_path, "spec", type="Product")
    # The domain filter the page always sends does not hide non-BI cards.
    assert len(_cards(tmp_path, "spec", domain="robotics")) == 3 + 3 + 1 + 2
    status, detail = _call(tmp_path, "GET", f"/api/bi/cards/{product['id']}", dataset="spec")
    assert status == 200
    assert [f["field"] for f in detail["fields"]] == [
        "name",
        "model",
        "status",
        "launch_date",
        "components",
        "owner",
    ]
    labels = {f["field"]: f["label"] for f in detail["fields"]}
    assert labels["launch_date"] == "上市日期" and labels["components"] == "使用零件"
    values = {f["field"]: f["value"] for f in detail["fields"]}
    assert values["status"] == "development" and values["launch_date"] == "2027-03-01"
    assert [link["target_key"] for link in detail["links"]] == [
        "48V 電源模組",
        "IMU 慣性感測器",
        "主控 MCU",
    ]
    assert not any(link["missing"] for link in detail["links"])
    edit = {
        "dataset": "spec",
        "field": "status",
        "value": "量產",
        "base_version": detail["card"]["version"],
        "reason": "已量產",
    }
    note = {**edit, "card": product["id"]}
    status, previewed = _call(tmp_path, "POST", "/api/bi/corrections/preview", note)
    assert status == 200 and previewed["value"] == "mass_production"
    status, saved = _call(
        tmp_path,
        "POST",
        "/api/bi/corrections/apply",
        {"dataset": "spec", "text": previewed["text"], "base_version": detail["card"]["version"]},
    )
    assert status == 200 and saved["ok"] is True
    bad = {**note, "value": "unknown", "base_version": saved["version"]}
    status, refused = _call(tmp_path, "POST", "/api/bi/corrections/preview", bad)
    assert status == 400 and refused["code"] == "value_invalid" and "狀態" in refused["message"]
    status, history = _call(
        tmp_path, "GET", f"/api/bi/cards/{product['id']}/history", dataset="spec"
    )
    last = history["history"][-1]
    assert (last["field"], last["old"], last["new"]) == ("status", "development", "mass_production")
    assert last["reason"] == "已量產" and last["by"] == f"{ACTOR} via web"


# -- BI-only: Dashboard, demo and the chat ----------------------------------------------


def test_the_dashboard_of_a_non_bi_dataset_is_an_empty_state(tmp_path: Path) -> None:
    _spec_dataset(tmp_path)
    status, board = _call(tmp_path, "GET", "/api/bi/dashboard", dataset="spec", domain="robotics")
    assert status == 200
    assert board == {
        "dashboard": False,
        "code": "no_dashboard",
        "message": "這個 schema 沒有 Dashboard",
        "schema": EXAMPLE,
        "domain": None,
        "sections": [],
    }


def test_the_demo_loads_only_into_a_bi_dataset(tmp_path: Path) -> None:
    _spec_dataset(tmp_path)
    status, refused = _call(tmp_path, "POST", "/api/bi/demo/load", {"dataset": "spec"})
    assert status == 400 and refused["code"] == "schema_not_bi"
    assert BiStore(tmp_path, "spec").card_rows() == []


def _context() -> RequestContext:
    return RequestContext(
        trace=TraceIdentifiers(trace_id="t1", request_id="r1", span_id="s1"),
        actor=ACTOR,
        namespace="engineering",
        message="bi",
        channel="local",
        session_id="s-1",
    )


def test_bi_query_refuses_a_non_bi_dataset(tmp_path: Path) -> None:
    _spec_dataset(tmp_path)
    _load_example(tmp_path)
    with pytest.raises(CapabilityRefused) as refused:
        asyncio.run(QueryHandler(tmp_path)(_context(), QueryRequest(dataset="spec", text="A1")))
    assert refused.value.code == "schema_not_bi"
    with pytest.raises(CapabilityRefused) as analysis:
        asyncio.run(
            QueryHandler(tmp_path)(_context(), QueryRequest(dataset="spec", analysis="gaps"))
        )
    assert analysis.value.code == "schema_not_bi"
    assert "BI schema" in FAILURE_TEXT["schema_not_bi"]
    assert "schema_not_bi" in PROCEDURE
    # A BI dataset still answers.
    service.load_demo(BiStore(tmp_path, "demo"))
    result = asyncio.run(QueryHandler(tmp_path)(_context(), QueryRequest(text="BMS")))
    assert result.model_dump()["total"] >= 1


def test_the_example_route_returns_the_shipped_files(tmp_path: Path) -> None:
    status, example = _call(tmp_path, "GET", "/api/bi/schemas/example")
    assert status == 200
    assert example["schema"]["filename"] == "product-spec@1.0.0.json"
    assert json.loads(example["schema"]["json_text"])["schema_id"] == "example/product-spec"
    assert [c["entity_type"] for c in example["csv"]] == [
        "Supplier",
        "Component",
        "Product",
        "SpecItem",
    ]
    assert not (tmp_path / "bi").exists()
