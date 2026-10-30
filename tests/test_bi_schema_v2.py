"""BI vault V9 (owner 2026-10-29; `docs/phases/BI_VAULT.md` §12): the schema
shapes the owner's manager used, and schema v8 shipped as `bi.schema/v1.1@2.0.0`.

- the committed `bi_schema_v2.json` is what the generator makes from the v8
  fixture, and it is a compatible newer version of the shipped 1.1.0;
- `float` fields read plain numbers and refuse units, 約 and ranges;
- a list may name its allowed values: unknown parts are dropped with a warning;
- a one-value field may widen to a list (or int to float): not breaking, and a
  dataset upgrade turns each stored value into its list form with history, on
  every PC of a vault;
- a local file can never shadow a shipped version.

All data is fictional.
"""

from __future__ import annotations

import json
import shutil
import sqlite3
from pathlib import Path
from typing import Any

from capabilities.bi_cards import catalog, schema_versions, vault
from capabilities.bi_cards.schema import SHIPPED_FILES, shipped, widens
from capabilities.bi_cards.store import BiStore, PlannedRow
from host_runtime.bi_cards_api import route
from scripts.build_bi_schema_v2 import V8, build

V1 = "bi.schema/v1.1@1.1.0"
V2 = "bi.schema/v1.1@2.0.0"


def _call(ws: Path, method: str, path: str, body: Any = None, actor: str = "tester") -> Any:
    return route(ws, actor, method, path, {}, body)


def _ok(answer: Any) -> dict[str, Any]:
    status, payload = answer
    assert status == 200, payload
    return dict(payload)


def _node(key: str, domain: str) -> PlannedRow:
    return PlannedRow(
        row=1,
        entity_type="Node",
        canonical_key=key,
        name=key,
        values={"name": key, "domain": domain, "layer": "L1"},
        synthetic=False,
    )


# -- the shipped 2.0.0 -----------------------------------------------------------


def test_the_shipped_v2_is_generated_from_schema_v8_and_extends_1_1_0() -> None:
    committed = json.loads(SHIPPED_FILES[1].read_text(encoding="utf-8"))
    assert committed == build()
    assert committed["source"]["primary"] == "tests/fixtures/bi_schema_v8/bi_schema.py"
    assert V8.is_file()
    normalised, problems = catalog.validate(committed)
    assert problems == [] and normalised is not None
    base, v2 = shipped()
    assert (base.ref, v2.ref) == (V1, V2)
    assert set(base.types) < set(v2.types) and len(v2.types) == 21
    for added in ("SupplyLink", "RevenueFact", "WinLoss", "Battlecard", "VisitLog"):
        assert added in v2.types
    assert set(base.domains) < set(v2.domains) and "aerospace" in v2.domains
    # Every v1.1 field is kept with its kind, or widened.
    for name, entity in base.types.items():
        for item in entity.fields:
            later = v2.types[name].get(item.name)
            assert later is not None, f"{name}.{item.name}"
            assert later.kind == item.kind or widens(item.kind, later.kind)
    node = v2.types["Node"]
    assert node.domain == "multi" and node.get("domain").kind == "list"  # type: ignore[union-attr]
    supply = v2.types["SupplyLink"]
    assert supply.get("supplier").link_to == ("Ecosystem", "Account")  # type: ignore[union-attr]


def test_float_reads_plain_numbers_only() -> None:
    v2 = shipped()[1]
    revenue = v2.types["RevenueFact"]
    amount, share = revenue.get("amount"), revenue.get("share_pct")
    assert amount is not None and share is not None
    assert v2.normalize(amount, "11,586") == (11586.0, [])
    assert v2.normalize(amount, "2.53") == (2.53, [])
    assert v2.normalize(amount, "-3") == (-3.0, [])
    assert v2.normalize(share, "59%") == (59.0, [])  # a percent sign is read
    for text in ("約20", "75–80%", "1兆1,586億元", "20 億USD"):
        value, warnings = v2.normalize(amount, text)
        assert value is None and warnings[0][0] == "type_mismatch", text
    value, warnings = v2.normalize(share, "120")
    assert value is None and "超出 0–100" in warnings[0][1]
    assert v2.normalize(share, "37.5") == (37.5, [])


def test_a_list_with_allowed_values_drops_unknown_parts() -> None:
    v2 = shipped()[1]
    segment = v2.types["Account"].get("segment")
    assert segment is not None and segment.enum is not None
    # Aerospace's own values, then the owner's market chart segments (owner 2026-10-29).
    assert segment.enum[:5] == ("space", "gateway", "ut", "launch", "mro")
    assert {"aidc-computing", "aidc-power", "robotics-amr", "osat"} <= set(segment.enum)
    assert v2.normalize(segment, "AIDC Power")[0] == ["aidc-power"]  # the label is an alias
    value, warnings = v2.normalize(segment, "space；UT；moon")
    assert value == ["space", "ut"]
    assert warnings and "moon" in warnings[0][1]
    assert v2.normalize(segment, "moon")[0] is None


def test_a_type_named_in_the_file_name_wins_over_the_headers() -> None:
    v2 = shipped()[1]
    # Tables keyed by field names fit many types; the manager names files by type.
    assert v2.type_in_filename("13_competitor.csv") == "Competitor"
    assert v2.type_in_filename("11_supply_link.csv") == "SupplyLink"
    assert v2.type_in_filename("08_customer_product.csv") == "CustomerProduct"
    assert v2.type_in_filename("06_test_solution_SAMPLE.csv") == "TestSolution"
    assert v2.type_in_filename("market.csv") is None


def test_a_local_file_never_shadows_a_shipped_version(tmp_path: Path) -> None:
    text = SHIPPED_FILES[1].read_text(encoding="utf-8")
    same = catalog.install(tmp_path, "v2.json", text)
    assert same["already"] is True
    assert not catalog.schema_path(tmp_path, "bi.schema/v1.1", "2.0.0").exists()
    changed = json.loads(text)
    changed["title"] = "另一份內容"
    try:
        catalog.install(tmp_path, "v2.json", json.dumps(changed, ensure_ascii=False))
    except catalog.SchemaInstallError as refused:
        assert refused.code == "schema_version_exists"
    else:
        raise AssertionError("a different 2.0.0 was installed")


# -- kinds in a local schema -------------------------------------------------------


def _local(base: dict[str, Any], version: str, change: Any) -> dict[str, Any]:
    document: dict[str, Any] = json.loads(json.dumps(base))
    document["version"] = version
    change(document)
    return document


def _field(document: dict[str, Any], type_name: str, name: str) -> dict[str, Any]:
    entity = next(t for t in document["types"] if t["name"] == type_name)
    return next(f for f in entity["fields"] if f["name"] == name)


def test_widening_is_allowed_and_narrowing_is_not() -> None:
    base = shipped()[0].document

    def widen(document: dict[str, Any]) -> None:
        _field(document, "Trend", "stage").update({"kind": "list", "list": True})  # enum → list
        _field(document, "Technology", "standard_body").update({"kind": "list", "list": True})
        _field(document, "Signal", "reliability").update({"kind": "list", "list": True})

    _, problems = catalog.validate(_local(base, "1.5.0", widen))
    assert problems == []
    diff = schema_versions.diff(base, _local(base, "1.5.0", widen))
    widened = [c for c in diff if c["change"] == "widened"]
    assert len(widened) == 3 and not any(c["breaking"] for c in widened)

    def narrow(document: dict[str, Any]) -> None:
        _field(document, "Technology", "standard_body").update({"kind": "int"})

    _, problems = catalog.validate(_local(base, "1.5.0", narrow))
    assert any(p["path"].endswith(".kind") for p in problems)
    assert any(c["change"] == "kind" and c["breaking"] for c in schema_versions.diff(
        base, _local(base, "1.5.0", narrow)))  # fmt: skip


def test_a_list_may_name_allowed_values_and_floats_take_ranges() -> None:
    document: dict[str, Any] = {
        "schema_id": "example/kinds",
        "version": "1.0.0",
        "title": "kinds",
        "types": [
            {
                "name": "Thing",
                "label": "東西",
                "fields": [
                    {"name": "name", "label": "名稱", "kind": "str", "class": "sourced"},
                    {"name": "colour", "label": "顏色", "kind": "list", "class": "sourced",
                     "enum": ["red", "blue"]},
                    {"name": "weight", "label": "重量", "kind": "float", "class": "sourced",
                     "range": [0, 2.5]},
                ],
            }
        ],
        "enum_aliases": {"colour": {"紅": "red"}},
    }  # fmt: skip
    normalised, problems = catalog.validate(document)
    assert problems == [] and normalised is not None
    colour = normalised["types"][0]["fields"][1]
    assert colour["enum"] == ["red", "blue"] and colour["list"] is True
    document["types"][0]["fields"][2]["kind"] = "int"  # a float range on an int
    _, problems = catalog.validate(document)
    assert any(p["path"].endswith(".range") for p in problems)


# -- moving a dataset to 2.0.0 -----------------------------------------------------


def test_a_dataset_upgrade_to_v2_widens_node_domain_with_history(tmp_path: Path) -> None:
    _ok(_call(tmp_path, "POST", "/api/bi/datasets", {"name": "market", "schema": V1}))
    store = BiStore(tmp_path, "market")
    store.apply([_node("L1-Chipset", "wireless")], filename="n.csv", entity_type="Node",
                actor="tester")  # fmt: skip
    card = store.find("Node", "L1-Chipset")
    assert card is not None and store.fields(card["id"])["domain"]["value"] == "wireless"
    path = "/api/bi/datasets/market/schema"
    preview = _ok(_call(tmp_path, "POST", f"{path}/preview", {"to": V2}))
    assert preview["blocked"] == [] and preview["totals"]["widened"] == 1
    node = next(t for t in preview["types"] if t["type"] == "Node")
    assert node["widened"] == [{"field": "domain", "from": "enum", "to": "list", "cards": 1}]
    assert any(c["change"] == "widened" and c["type"] == "Node" for c in preview["diff"])
    applied = _ok(_call(tmp_path, "POST", f"{path}/apply",
                        {"to": V2, "preview_token": preview["preview_token"]}))  # fmt: skip
    assert applied["moved"] == 1 and store.schema_ref() == V2
    after = store.find("Node", "L1-Chipset")
    assert after is not None and after["version"] == card["version"] + 1
    assert store.fields(after["id"])["domain"]["value"] == ["wireless"]
    with sqlite3.connect(store.path) as db:
        rows = db.execute(
            "SELECT old, new, kind, ref FROM history WHERE card_id = ? AND field = 'domain' "
            "AND kind = 'migration'",
            (after["id"],),
        ).fetchall()
    assert rows == [('"wireless"', '["wireless"]', "migration", f"schema:{V2}")]
    # A new card under 2.0.0 gets the list form directly, an unknown domain dropped.
    v2 = catalog.for_store(store)
    domain = v2.types["Node"].get("domain")
    assert domain is not None
    assert v2.normalize(domain, "wireless；aerospace；moon")[0] == ["wireless", "aerospace"]


def test_a_vault_upgrade_reaches_every_pc(tmp_path: Path) -> None:
    a, b = tmp_path / "a" / "ws", tmp_path / "b" / "ws"
    parent_a, parent_b = tmp_path / "a" / "drive", tmp_path / "b" / "drive"
    for folder in (a, b, parent_a, parent_b):
        folder.mkdir(parents=True)
    made = _ok(
        _call(
            a,
            "POST",
            "/api/bi/vaults",
            {"path": str(parent_a), "title": "Market", "purpose": "虛構測試", "schema": V1,
             "author": "alice"},
        )
    )  # fmt: skip
    vault_id = made["vault"]["id"]
    dataset = vault.dataset_name(vault_id)
    BiStore(a, dataset).apply([_node("L1-Chipset", "wireless")], filename="n.csv",
                              entity_type="Node", actor="alice")  # fmt: skip
    path = f"/api/bi/datasets/{dataset}/schema"
    preview = _ok(_call(a, "POST", f"{path}/preview", {"to": V2}))
    _ok(_call(a, "POST", f"{path}/apply", {"to": V2, "preview_token": preview["preview_token"]}))
    # The upgrade is staged here; a commit and a push take it to every PC.
    _ok(_call(a, "POST", f"/api/bi/vaults/{vault_id}/commit", {"purpose": "Upgrade to 2.0.0"}))
    _ok(_call(a, "POST", f"/api/bi/vaults/{vault_id}/push", {}))
    shutil.copytree(parent_a / vault_id, parent_b / vault_id)
    _ok(_call(b, "POST", "/api/bi/vaults/join", {"path": str(parent_b / vault_id),
                                                  "author": "bob"}))  # fmt: skip
    joined = BiStore(b, dataset)
    assert joined.schema_ref() == V2
    card = joined.find("Node", "L1-Chipset")
    assert card is not None and joined.fields(card["id"])["domain"]["value"] == ["wireless"]
