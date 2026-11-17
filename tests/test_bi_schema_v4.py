"""BI schema 4.0.0: three more types hold a list of domains (owner 2026-11-03).

`Application`, `Trend` and `CustomerProduct`: a card can belong to several domains. A
widening, so a dataset upgrades in place; the allowed values stay, so the default pack's
`values_from` does not move; the feed's goldens are pinned to 2.0.0 and do not change.
All data is fictional.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from test_bi_schema_v2 import _call, _ok
from test_bi_vault_published import CONTEXT

from aep_bi.cards import analyses, catalog, packs, schema_versions
from aep_bi.cards.capability import QueryHandler, QueryRequest
from aep_bi.cards.store import BiStore, PlannedRow
from scripts.build_bi_schema_v4 import OUT, WIDENED, build

V3, V4 = "bi.schema/v1.1@3.0.0", "bi.schema/v1.1@4.0.0"


def _dataset(tmp_path: Path, schema: str = V4) -> Path:
    ws = tmp_path / "ws"
    ws.mkdir()
    _ok(_call(ws, "POST", "/api/bi/datasets", {"name": "lab", "schema": schema}))
    return ws


def _csv(ws: Path, text: str, entity_type: str = "Application") -> dict[str, Any]:
    given = {"dataset": "lab", "csv_text": text, "entity_type": entity_type}
    prepared = _ok(_call(ws, "POST", "/api/bi/import/preview", given))
    _ok(_call(ws, "POST", "/api/bi/import/apply", {"preview_id": prepared["preview_id"]}))
    return prepared


def test_the_shipped_4_0_0_is_generated_and_only_widens_those_fields(tmp_path: Path) -> None:
    assert json.loads(OUT.read_text(encoding="utf-8")) == build()
    old, new = catalog.resolve(tmp_path, V3), catalog.resolve(tmp_path, V4)
    changes = schema_versions.diff(old.document, new.document)
    assert sorted((c["type"], c["field"], c["change"]) for c in changes) == sorted(
        (name, "domain", "widened") for name in WIDENED
    )
    for name in WIDENED:
        field = new.types[name].get("domain")
        assert field is not None and field.is_list and field.default is None
    # Other types keep theirs: this is not a general change.
    signal = new.types["Signal"].get("domain")
    assert signal is not None and not signal.is_list


def test_the_default_packs_domain_parameter_keeps_its_values(tmp_path: Path) -> None:
    old, new = catalog.resolve(tmp_path, V3), catalog.resolve(tmp_path, V4)
    assert analyses.enum_values(packs.DOMAIN, new) == analyses.enum_values(packs.DOMAIN, old)
    assert analyses.enum_values(packs.DOMAIN, new) == list(new.domains)


def test_the_feed_goldens_stay_on_their_pinned_schema() -> None:
    source = (Path(__file__).parents[1] / "scripts" / "bi_feed_fixtures.py").read_text("utf-8")
    assert '"bi.schema/v1.1@2.0.0"' in source and V4 not in source


def test_a_card_can_hold_several_domains_and_is_found_under_each(tmp_path: Path) -> None:
    ws = _dataset(tmp_path)
    prepared = _csv(
        ws, "應用名稱,領域\nFAKE-APP,AIDC;robotics\nFAKE-BAD,no-such-domain\nFAKE-NONE,\n"
    )
    said = json.dumps(prepared["rows"], ensure_ascii=False)
    assert "domain_unknown" in said  # an invalid value is listed, never kept
    store = BiStore(ws, "lab")
    card = store.find("Application", "FAKE-APP")
    assert card is not None
    assert store.fields(card["id"])["domain"]["value"] == ["AIDC", "robotics"]
    none = store.find("Application", "FAKE-NONE")
    assert none is not None and "domain" not in store.fields(none["id"])

    def found(domain: str) -> set[str]:
        request = QueryRequest(dataset="lab", entity_type="Application", domain=domain)
        answer = asyncio.run(QueryHandler(ws)(CONTEXT, request)).model_dump()
        return {c["name"] for c in answer["cards"]}

    assert "FAKE-APP" in found("AIDC") and "FAKE-APP" in found("robotics")
    assert "FAKE-APP" not in found("aerospace")
    assert "FAKE-NONE" in found("wireless")  # no domain still means wireless


def test_a_card_in_two_domains_counts_in_both_in_the_default_pack(tmp_path: Path) -> None:
    ws = _dataset(tmp_path)
    _csv(ws, "應用名稱,領域\nFAKE-TWO,AIDC;robotics\n")
    request = QueryRequest
    for domain, expected in (("AIDC", True), ("robotics", True), ("aerospace", False)):
        answer = asyncio.run(
            QueryHandler(ws)(CONTEXT, request(dataset="lab", analysis="all", domain=domain))
        ).model_dump()
        rows = json.dumps([s["rows"] for s in answer["analysis"]], ensure_ascii=False)
        assert ("FAKE-TWO" in rows) is expected, domain


def test_a_3_0_0_dataset_upgrades_in_place_with_each_value_a_one_item_list(tmp_path: Path) -> None:
    ws = _dataset(tmp_path, V3)
    store = BiStore(ws, "lab")
    store.apply(
        [
            PlannedRow(row=1, entity_type="Application", canonical_key="OLD-APP", name="OLD-APP",
                       values={"name": "OLD-APP", "domain": "AIDC"}, synthetic=False),
            PlannedRow(row=2, entity_type="Trend", canonical_key="OLD-TREND", name="OLD-TREND",
                       values={"name": "OLD-TREND"}, synthetic=False),
        ],
        filename="t.csv", entity_type="Application", actor="x",
    )  # fmt: skip
    plan = schema_versions.upgrade_preview(ws, "lab", V4)
    assert plan["totals"]["widened"] == 1  # the one card holding a domain
    schema_versions.upgrade_apply(ws, "lab", V4, plan["preview_token"], "alice")
    upgraded = BiStore(ws, "lab")
    assert upgraded.schema_ref() == V4
    app = upgraded.find("Application", "OLD-APP")
    assert app is not None and upgraded.fields(app["id"])["domain"]["value"] == ["AIDC"]
    trend = upgraded.find("Trend", "OLD-TREND")
    assert trend is not None  # it held no domain and needs none
