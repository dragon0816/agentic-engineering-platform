"""Coverage by market segment and technology area (`docs/phases/BI_VAULT.md` §6.2).

A local BI schema version adds `segments` and `tech_areas` to Technology; a
fictional table is imported through the rule path; `/api/bi/coverage` then
places each card in every segment x area cell it names, counts unplaced cards
apart, reports values that name no segment, and says when the schema has no
field to place cards with. The matrix is the shipped owner chart unless the
dataset has its own `coverage.json`, which must be valid.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from capabilities.bi_cards import coverage
from capabilities.bi_cards.schema import SCHEMA_FILE
from host_runtime.bi_cards_api import route

ACTOR = "tester"
# 虛構範例: fictional rows, not market data.
TABLE = (
    "技術,應用領域,技術領域,標準組織\n"
    "Wi-Fi 7,Cell Phone；AP/CPE,Wireless & Comm.；RF,IEEE\n"
    "800G 光模組,AIDC Computing,High Speed I/O,\n"
    "未分類技術,,,\n"
    "火星通訊,Mars Base,RF,\n"
)


def _call(workspace: Path, method: str, path: str, body: Any = None, **q: str) -> Any:
    return route(workspace, ACTOR, method, path, q, body, None)


def _ok(answer: Any) -> dict[str, Any]:
    status, payload = answer
    assert status == 200, payload
    return dict(payload)


def _schema_with_placement() -> str:
    document = json.loads(SCHEMA_FILE.read_text(encoding="utf-8"))
    document["version"] = "1.2.0"
    tech = next(t for t in document["types"] if t["name"] == "Technology")
    base = {"class": "sourced", "enum": None, "required": False, "default": None}
    tech["fields"] += [
        {**base, "name": "segments", "label": "應用領域", "kind": "list",
         "aliases": ["應用領域", "segments"], "range": None, "link_to": [], "list": True},
        {**base, "name": "tech_areas", "label": "技術領域", "kind": "list",
         "aliases": ["技術領域", "tech_areas"], "range": None, "link_to": [], "list": True},
    ]  # fmt: skip
    return json.dumps(document, ensure_ascii=False)


def _dataset(workspace: Path) -> None:
    _ok(_call(workspace, "POST", "/api/bi/schemas/install",
              {"filename": "bi.json", "json_text": _schema_with_placement()}))  # fmt: skip
    _ok(_call(workspace, "POST", "/api/bi/datasets",
              {"name": "market", "schema": "bi.schema/v1.1@1.2.0"}))  # fmt: skip
    body = {"dataset": "market", "name": "tech.csv", "text": TABLE}
    source = _ok(_call(workspace, "POST", "/api/bi/sources", body))["source"]["id"]
    start = {"dataset": "market", "kind": "ingest", "source_id": source,
             "entity_type": "Technology"}  # fmt: skip
    run = _ok(_call(workspace, "POST", "/api/bi/runs", start))["run"]
    detail = _ok(_call(workspace, "GET", f"/api/bi/runs/{run['id']}", dataset="market"))
    for candidate in detail["candidates"]:
        path = f"/api/bi/runs/{run['id']}/candidates/{candidate['id']}"
        _ok(_call(workspace, "POST", path, {"dataset": "market", "review": "accepted"}))
    _ok(_call(workspace, "POST", f"/api/bi/runs/{run['id']}/commit", {"dataset": "market"}))


def _cell(report: dict[str, Any], segment: str, area: str) -> dict[str, Any]:
    return next(c for c in report["cells"] if c["segment"] == segment and c["area"] == area)


def test_cards_are_placed_in_every_cell_they_name(tmp_path: Path) -> None:
    _dataset(tmp_path)
    report = _ok(_call(tmp_path, "GET", "/api/bi/coverage", dataset="market"))
    assert report["matrix_source"] == "shipped" and report["schema_missing_fields"] == []
    assert len(report["cells"]) == 11 * 5
    for segment in ("cell-phone", "ap-cpe"):
        for area in ("wireless-comm", "rf"):
            cell = _cell(report, segment, area)
            assert cell["cards"] == 1 and cell["types"] == {"Technology": 1}
            assert [c["name"] for c in cell["card_list"]] == ["Wi-Fi 7"]
            assert cell["sourced_share"] == 1.0  # every value came from a table cell
            assert cell["newest"]
    optical = _cell(report, "aidc-computing", "high-speed-io")
    assert optical["cards"] == 1
    # The cell's most often empty fields, at most EMPTY_SHOWN, by count then name.
    assert len(optical["empty"]) == coverage.EMPTY_SHOWN
    assert optical["empty"][0] == {"field": "Technology.affects_nodes", "cards": 1}
    assert "Technology.segments" not in [e["field"] for e in optical["empty"]]
    empty = _cell(report, "osat", "emc")
    assert empty == {"segment": "osat", "area": "emc", "cards": 0, "types": {},
                     "sourced_share": None, "newest": None, "empty": [],
                     "card_list": []}  # fmt: skip
    assert report["totals"] == {"cards": 4, "no_segment": 2, "no_area": 1}
    assert report["unknown_values"] == {"Mars Base": 1}
    priority = [
        s["id"] for m in report["matrix"]["markets"] for s in m["segments"] if s["priority"]
    ]
    assert priority == [
        "cell-phone", "ap-cpe", "aidc-computing", "aidc-power", "robotics-amr", "space-satellite",
    ]  # fmt: skip


def test_a_schema_without_placement_fields_says_so(tmp_path: Path) -> None:
    _ok(_call(tmp_path, "POST", "/api/bi/demo/load", {"dataset": "demo"}))
    report = _ok(_call(tmp_path, "GET", "/api/bi/coverage", dataset="demo"))
    assert report["schema_missing_fields"] == ["segments", "tech_areas"]
    assert report["totals"]["cards"] > 0
    assert report["totals"]["no_segment"] == report["totals"]["cards"]
    assert all(c["cards"] == 0 for c in report["cells"])


def test_a_dataset_matrix_replaces_the_shipped_one_and_is_checked(tmp_path: Path) -> None:
    _dataset(tmp_path)
    own: dict[str, list[dict[str, Any]]] = {
        "markets": [{"id": "m", "segments": [{"id": "cell-phone", "label": "Cell Phone"}]}],
        "areas": [{"id": "rf", "label": "RF"}],
    }
    folder = tmp_path / "bi" / "market"
    (folder / coverage.DATASET_FILE).write_text(json.dumps(own), encoding="utf-8")
    report = _ok(_call(tmp_path, "GET", "/api/bi/coverage", dataset="market"))
    assert report["matrix_source"] == "dataset" and len(report["cells"]) == 1
    assert report["cells"][0]["cards"] == 1
    assert report["unknown_values"] == {
        "AIDC Computing": 1, "AP/CPE": 1, "High Speed I/O": 1, "Mars Base": 1,
        "Wireless & Comm.": 1,
    }  # fmt: skip
    own["areas"].append({"id": "rf"})
    (folder / coverage.DATASET_FILE).write_text(json.dumps(own), encoding="utf-8")
    status, payload = _call(tmp_path, "GET", "/api/bi/coverage", dataset="market")
    assert (status, payload["code"]) == (400, "coverage_matrix_invalid")


def test_an_unknown_dataset_is_refused(tmp_path: Path) -> None:
    status, payload = _call(tmp_path, "GET", "/api/bi/coverage", dataset="nope")
    assert (status, payload["code"]) == (404, "dataset_unknown")
