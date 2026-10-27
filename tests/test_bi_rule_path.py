"""BI ingest phase 3, the rule path (owner 2026-10-27; `docs/phases/BI_INGEST.md`
§6, §11 item 11; the engine design of `docs/phases/BI_CASE_B.md` §3–§5, §7).

Readers for Markdown reports, Excel workbooks and CSV; recipes with several
passes and their strict validation; the transforms of the fixture's
`bi_ingest.py`, reimplemented and compared here against what upstream would
produce on its own samples (worked out from its code, never imported); the
benchmark cases VE-05 (聯發科 and MediaTek are one card) and VE-06 (中磊 is
never a Competitor); and the run guarantees: re-running creates no
duplicates, undo restores every pass, a run writes nothing to `bi.sqlite`.
"""

from __future__ import annotations

import base64
import datetime as dt
import io
import json
from pathlib import Path
from typing import Any

import openpyxl
import pytest

from capabilities.bi_cards import readers, recipes
from capabilities.bi_cards.schema import registry
from capabilities.bi_cards.store import BiStore, BiStoreError
from host_runtime.bi_cards_api import route

ACTOR = "tester"
REAL = Path(__file__).parent / "fixtures" / "bi_vault_example" / "tools" / "samples" / "real"

ROLES_MD = """# 客戶與儀器（測試資料）

## 客戶

| 公司 | 代號 |
|---|---|
| **中磊 Sercomm** | 5388 |
| **啟碁 WNC** | 6285 |

## 儀器

| 儀器類別 | 代表廠 |
|:---|:---|
| 無線綜測儀 | LitePoint(Teradyne)、中磊 |

## 附錄

| 項目 | 說明 |
|---|---|
| 資料時間 | 2026-10 |
"""

ROLES_RECIPE: dict[str, Any] = {
    "schema_version": "aep.bi.recipe/v1",
    "name": "roles",
    "name_aliases": {"中磊 Sercomm": "中磊", "啟碁 WNC": "啟碁"},
    "passes": [
        {
            "id": "accounts",
            "tables": "has:公司",
            "entity_type": "Account",
            "mapping": {"columns": {"公司": "name", "代號": "ticker"}},
        },
        {
            "id": "instruments",
            "tables": "has:儀器類別",
            "entity_type": "Competitor",
            "mapping": {
                "explode": [{"column": "代表廠", "into": "name"}],
                "columns": {"儀器類別": "product_lines"},
            },
        },
    ],
}


def _call(tmp_path: Path, method: str, path: str, body: Any = None, **query: str) -> Any:
    return route(tmp_path, ACTOR, method, path, query, body)


def _ok(answer: Any) -> dict[str, Any]:
    status, payload = answer
    assert status == 200, payload
    return dict(payload)


def _mapping(name: str) -> dict[str, Any]:
    return dict(json.loads((REAL / name).read_text(encoding="utf-8")))


def _supply_recipe() -> dict[str, Any]:
    """The README's four runs on the supply-chain extract as one recipe.
    Account has no `confidence` in `bi.schema/v1.1`, so that default is left
    out (a recipe naming a field the type lacks is refused)."""
    accounts = _mapping("mapping_account_midstream.json")
    del accounts["defaults"]
    return {
        "schema_version": "aep.bi.recipe/v1",
        "name": "supply-chain-study",
        "dataset_schema": "bi.schema/v1.1",
        "name_aliases": _mapping("name_aliases.json"),
        "passes": [
            {
                "id": "suppliers",
                "tables": "has:全球代表廠|台系代表廠",
                "entity_type": "Ecosystem",
                "mapping": _mapping("mapping_ecosystem_suppliers.json"),
            },
            {
                "id": "certlabs",
                "tables": "has:認證類別",
                "entity_type": "Ecosystem",
                "mapping": _mapping("mapping_ecosystem_certlabs.json"),
            },
            {
                "id": "instruments",
                "tables": "has:儀器類別",
                "entity_type": "Competitor",
                "mapping": _mapping("mapping_competitor_instruments.json"),
            },
            {"id": "accounts", "tables": "has:公司", "entity_type": "Account", "mapping": accounts},
        ],
    }


def _source(tmp_path: Path, name: str, text: str | None = None, data: bytes | None = None) -> str:
    body: dict[str, Any] = {"dataset": "demo", "name": name}
    if data is not None:
        body["content_base64"] = base64.b64encode(data).decode("ascii")
    else:
        body["text"] = text if text is not None else (REAL / name).read_text(encoding="utf-8")
    return str(_ok(_call(tmp_path, "POST", "/api/bi/sources", body))["source"]["id"])


def _run(tmp_path: Path, source_id: str, **extra: Any) -> dict[str, Any]:
    body = {"dataset": "demo", "kind": "ingest", "source_id": source_id, **extra}
    return dict(_ok(_call(tmp_path, "POST", "/api/bi/runs", body))["run"])


def _candidates(tmp_path: Path, run_id: str) -> list[dict[str, Any]]:
    detail = _ok(_call(tmp_path, "GET", f"/api/bi/runs/{run_id}", dataset="demo"))
    return list(detail["candidates"])


def _review(tmp_path: Path, run_id: str, cid: str, **body: Any) -> dict[str, Any]:
    return _ok(
        _call(
            tmp_path,
            "POST",
            f"/api/bi/runs/{run_id}/candidates/{cid}",
            {"dataset": "demo", **body},
        )
    )


def _accept_all(tmp_path: Path, run_id: str) -> None:
    for candidate in _candidates(tmp_path, run_id):
        if candidate["action"] in ("create", "update"):
            _review(tmp_path, run_id, candidate["id"], review="accepted")


def _commit(tmp_path: Path, run_id: str) -> dict[str, Any]:
    return _ok(_call(tmp_path, "POST", f"/api/bi/runs/{run_id}/commit", {"dataset": "demo"}))


def _by_key(found: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    return {(c["entity_type"], c["canonical_key"]): c for c in found}


def _value(candidate: dict[str, Any], name: str) -> Any:
    return next((f["value"] for f in candidate["fields"] if f["field"] == name), None)


def _cards(tmp_path: Path) -> set[tuple[str, str]]:
    return {(c["entity_type"], c["canonical_key"]) for c in BiStore(tmp_path).card_rows()}


# -- readers -------------------------------------------------------------------


def test_markdown_tables_are_numbered_with_their_headings_and_lines() -> None:
    text = (REAL / "supply_chain_extract.md").read_text(encoding="utf-8")
    tables = readers.read_tables("supply_chain_extract.md", text.encode("utf-8"))
    assert [t["title"] for t in tables] == [
        "2.1 晶片/SoC",
        "2.2 RF 前端/PA/LNA/濾波器",
        "2.3 天線/RF設計",
        "2.4 PCB / 基板 / 銅箔基板",
        "2.5 光通訊 / 光模組",
        "三、中游製造商對應表",
        "5.1 測試儀器",
        "5.2 認證/合規實驗室",
    ]
    assert [t["index"] for t in tables] == list(range(8))
    first = tables[0]
    assert first["locator"] == "line"
    assert first["columns"][:3] == ["供應鏈層級", "料件/技術", "全球代表廠"]
    assert first["rows"][0]["row"] == 10  # the line of the first data row
    # Bold marks are removed, as upstream's clean_md does.
    rf = tables[1]["rows"][0]["cells"]["台系代表廠"]
    assert rf == "穩懋(3105)、宏捷科(8086)、全新(2455)"
    # The table without 全球代表廠 has fewer columns; nothing is invented.
    assert "全球代表廠" not in tables[3]["columns"]


def test_markdown_without_a_heading_uses_the_file_name_and_skips_non_tables() -> None:
    text = "| a | b |\n|---|---|\n| 1 | 2 |\n\n| not | a table |\n| x | y |\n"
    tables = readers.read_tables("plain.md", text.encode("utf-8"))
    assert len(tables) == 1
    assert tables[0]["title"] == "plain.md"
    assert tables[0]["rows"] == [{"row": 3, "cells": {"a": "1", "b": "2"}}]


def _workbook() -> bytes:
    book = openpyxl.Workbook()
    first = book.active
    assert first is not None
    first.title = "Competitors"
    first.append([None, None])  # an empty first row: the header is the next one
    first.append(["廠商", "更新日期", "產品線"])
    first.append(["Keysight", dt.datetime(2026, 10, 7, 0, 0), "網路分析儀"])
    first.append(["Anritsu", dt.date(2026, 9, 30), "無線綜測儀"])
    accounts = book.create_sheet("Accounts")
    accounts.append(["公司", "代號"])
    accounts.append(["中磊", 5388])
    notes = book.create_sheet("Notes")
    notes.append(["說明"])
    notes.append(["這張表沒有步驟讀取"])
    out = io.BytesIO()
    book.save(out)
    return out.getvalue()


def test_excel_sheets_are_tables_with_iso_dates() -> None:
    tables = readers.read_tables("study.xlsx", _workbook())
    assert [(t["index"], t["title"], t["locator"]) for t in tables] == [
        (0, "Competitors", "sheet"),
        (1, "Accounts", "sheet"),
        (2, "Notes", "sheet"),
    ]
    competitors = tables[0]
    assert competitors["columns"] == ["廠商", "更新日期", "產品線"]
    assert [r["row"] for r in competitors["rows"]] == [3, 4]
    assert [r["cells"]["更新日期"] for r in competitors["rows"]] == ["2026-10-07", "2026-09-30"]
    assert tables[1]["rows"][0]["cells"]["代號"] == "5388"
    assert recipes.select_tables(tables, "sheet:Accounts") == ([1], [])


def test_csv_is_one_table_and_other_files_are_refused() -> None:
    tables = readers.read_tables("t.csv", "名稱,代號\nA,1\n\nB,2\n".encode())
    assert len(tables) == 1 and tables[0]["title"] == "t.csv"
    assert [r["row"] for r in tables[0]["rows"]] == [2, 4]
    with pytest.raises(BiStoreError) as caught:
        readers.read_tables("slides.pptx", b"x")
    assert caught.value.code == "file_type_unsupported"


def test_table_selectors_follow_upstream() -> None:
    text = (REAL / "supply_chain_extract.md").read_text(encoding="utf-8")
    tables = readers.read_tables("s.md", text.encode("utf-8"))
    assert recipes.select_tables(tables, "all")[0] == list(range(8))
    assert recipes.select_tables(tables, "0,2-3") == ([0, 2, 3], [])
    # `has:` matches any listed column (2.4 has only 台系代表廠).
    assert recipes.select_tables(tables, "has:全球代表廠|台系代表廠") == ([0, 1, 2, 3, 4], [])
    assert recipes.select_tables(tables, "has:認證類別") == ([7], [])
    assert recipes.select_tables(tables, "1,9") == ([1], [9])


# -- transforms (expected values worked out from upstream bi_ingest.py) ---------


def _rows(table: dict[str, Any]) -> list[recipes.Row]:
    made = []
    for item in table["rows"]:
        cells = dict(item["cells"])
        made.append(
            recipes.Row(
                table["index"],
                item["row"],
                {"table": table["index"], "line": item["row"]},
                cells,
                dict(cells),
                {c: [c] for c in cells},
            )
        )
    return made


def test_explode_splits_cells_with_tickers_notes_and_aliases() -> None:
    aliases = recipes.Aliases(_mapping("name_aliases.json"))
    items = recipes.explode_cell(
        "Intel（BE200 / BE201 / BE202）、Qualcomm、MediaTek、Realtek、Broadcom", {}, aliases
    )
    assert [i["name"] for i in items] == ["Intel", "Qualcomm", "MediaTek", "Realtek", "Broadcom"]
    assert items[0]["note"] == "BE200 / BE201 / BE202" and items[0]["ticker"] == ""
    stocks = recipes.explode_cell("聯發科(2454)、瑞昱(2379)", {}, aliases)
    assert [(i["name"], i["ticker"], i["note"]) for i in stocks] == [
        ("MediaTek", "2454", ""),
        ("Realtek", "2379", ""),
    ]
    # Separators inside brackets do not split; a trailing 等 is dropped.
    agent = recipes.explode_cell("益登（Telit Cinterion、Silicon Labs，益登科技）", {}, aliases)
    assert [(i["name"], i["note"]) for i in agent] == [
        ("益登", "Telit Cinterion、Silicon Labs，益登科技")
    ]
    assert [i["name"] for i in recipes.explode_cell("Qorvo等, Murata", {}, aliases)] == [
        "Qorvo",
        "Murata",
    ]
    lab = recipes.explode_cell(
        "Auray Technology(耀睿科技) — 台灣唯一O-RAN OTIC", {"strip_after": " — "}, aliases
    )
    assert [(i["name"], i["note"]) for i in lab] == [("Auray 耀睿科技", "耀睿科技")]
    assert recipes.explode_cell("—", {}, aliases) == []


def test_module_chain_passes_match_upstream() -> None:
    """`mapping_ecosystem_modules.json` on `module_chain_extract.md`, table 0."""
    text = (REAL / "module_chain_extract.md").read_text(encoding="utf-8")
    table = readers.read_tables("m.md", text.encode("utf-8"))[0]
    mapping = recipes.validate(
        {
            "name": "m",
            "passes": [
                {
                    "id": "modules",
                    "entity_type": "Ecosystem",
                    "mapping": _mapping("mapping_ecosystem_modules.json"),
                }
            ],
        },
        registry(),
    )["passes"][0]["mapping"]
    out, exploded = recipes.transform(_rows(table), mapping, recipes.Aliases())
    got = [(r.cells["name"], r.cells.get("role", ""), r.cells.get("node", "")) for r in out]
    # skip_rows drops 被動元件／晶振 and NB／PC ODM; exclude_names drops 正文;
    # derive takes the first matching pattern in map order.
    assert got == [
        ("Intel", "chipset", "L1-Chipset"),
        ("Qualcomm", "chipset", "L1-Chipset"),
        ("MediaTek", "chipset", "L1-Chipset"),
        ("Realtek", "chipset", "L1-Chipset"),
        ("Broadcom", "chipset", "L1-Chipset"),
        ("穩懋", "component", "L2-RF-FEM-Module"),
        ("宏捷科", "component", "L2-RF-FEM-Module"),
        ("Skyworks", "component", "L2-RF-FEM-Module"),
        ("Qorvo", "component", "L2-RF-FEM-Module"),
        ("日月光", "osat", ""),
        ("京元電", "osat", ""),
        ("矽格", "osat", ""),
        ("海華", "module", ""),
        ("正基", "module", ""),
        ("環旭", "module", ""),
    ]
    # compose drops a line whose placeholders are all empty (備註 without a note).
    assert out[0].cells["body"] == "【上游】WiFi / BT SoC\n備註:BE200 / BE201 / BE202"
    assert out[1].cells["body"] == "【上游】WiFi / BT SoC"
    assert out[6].cells["body"] == "【上游】FEM / PA\n備註:GaAs 代工"
    assert [(r.number, n) for r, n in exploded] == [(10, 5), (11, 4), (13, 3), (14, 4)]


def test_text_replace_writes_into_another_column_and_derive_all_collects() -> None:
    text = (REAL / "supply_chain_extract.md").read_text(encoding="utf-8")
    tables = readers.read_tables("s.md", text.encode("utf-8"))
    checked = recipes.validate(_supply_recipe(), registry())
    accounts = checked["passes"][3]["mapping"]
    out, _ = recipes.transform(_rows(tables[5]), accounts, recipes.Aliases())
    taiyang = next(r for r in out if r.cells["公司"] == "台揚")
    assert taiyang.cells["key_suppliers"] == "AMD、Intel、Qorvo、MACOM"
    assert taiyang.cells["主要上游依賴"] == "FPGA(Xilinx/Intel)、RF元件(Qorvo/MACOM)"
    assert taiyang.origin["key_suppliers"] == ["主要上游依賴"]
    assert taiyang.cells["body"].startswith("Small Cell:⚠️ O-RAN RU卡位\nCPE:❌\n")
    suppliers = checked["passes"][0]["mapping"]
    out, _ = recipes.transform(_rows(tables[2]), suppliers, recipes.Aliases())
    amphenol = next(r for r in out if r.cells["name"] == "Amphenol")
    # `all: true` keeps every matching value, joined with 、 like upstream.
    assert amphenol.cells["technologies"] == "5G-NR-FR2、NTN-Satellite"
    assert amphenol.cells["__origin"] == "全球"
    # exclude_names drops 啟碁 and 台揚 from the 台系 column.
    assert {r.cells["name"] for r in out if r.cells["__origin"] == "台灣"} == {"耀登"}
    certlabs = checked["passes"][1]["mapping"]
    out, _ = recipes.transform(_rows(tables[7]), certlabs, recipes.Aliases())
    assert not any("PTP" in r.cells["認證類別"] for r in out)  # skip_rows


# -- recipe validation ----------------------------------------------------------


def _refusal(recipe: Any) -> BiStoreError:
    with pytest.raises(BiStoreError) as caught:
        recipes.validate(recipe, registry())
    return caught.value


def test_recipe_validation_refuses_unknown_keys_bad_regex_and_bad_passes() -> None:
    def one(mapping: dict[str, Any], **step: Any) -> dict[str, Any]:
        return {
            "name": "r",
            "passes": [{"id": "p1", "entity_type": "Ecosystem", "mapping": mapping, **step}],
        }

    error = _refusal(one({"explod": []}))
    assert error.code == "mapping_key_unknown"
    assert error.detail == {"pass_id": "p1", "key": "mapping.explod"}
    error = _refusal(one({}, table="all"))
    assert (error.code, error.detail["key"]) == ("mapping_key_unknown", "table")
    error = _refusal(one({"derive": {"role": {"from": ["a"], "map": {"(": "x"}}}}))
    assert error.code == "recipe_invalid"
    assert error.detail == {"pass_id": "p1", "key": "mapping.derive.role.map"}
    long_regex = "a" * (recipes.MAX_REGEX + 1)
    error = _refusal(one({"text_replace": [{"column": "c", "pairs": [[long_regex, ""]]}]}))
    assert (error.code, error.detail["key"]) == ("recipe_invalid", "mapping.text_replace.pairs")
    error = _refusal({"name": "r", "passes": [{"entity_type": "Ecosystem"}]})
    assert error.code == "recipe_invalid" and "id" in error.message
    twice = {
        "name": "r",
        "passes": [
            {"id": "a", "entity_type": "Ecosystem"},
            {"id": "a", "entity_type": "Account"},
        ],
    }
    assert _refusal(twice).detail == {"pass_id": "a", "key": "id"}
    error = _refusal(one({}, entity_type="Vendor"))
    assert (error.code, error.detail["key"]) == ("recipe_invalid", "entity_type")
    error = _refusal(one({"columns": {"公司": "nmae"}}))
    assert (error.code, error.detail["key"]) == ("recipe_invalid", "mapping.columns")
    error = _refusal(one({}, tables="has:"))
    assert (error.code, error.detail["key"]) == ("recipe_invalid", "tables")
    assert _refusal({"name": "r", "passes": []}).code == "recipe_invalid"
    assert _refusal({"name": "r", "passes": [], "extra": 1}).code == "mapping_key_unknown"


def test_recipes_are_saved_per_dataset_and_versioned(tmp_path: Path) -> None:
    saved = _ok(
        _call(tmp_path, "POST", "/api/bi/recipes", {"dataset": "demo", "recipe": ROLES_RECIPE})
    )
    first = saved["recipe"]
    assert (first["version"], first["already"], first["name"]) == (1, False, "roles")
    again = _ok(
        _call(tmp_path, "POST", "/api/bi/recipes", {"dataset": "demo", "recipe": ROLES_RECIPE})
    )
    assert (again["recipe"]["version"], again["recipe"]["already"]) == (1, True)
    changed = json.loads(json.dumps(ROLES_RECIPE))
    changed["passes"][1]["mapping"]["exclude_names"] = ["中磊"]
    second = _ok(_call(tmp_path, "POST", "/api/bi/recipes", {"dataset": "demo", "recipe": changed}))
    assert (second["recipe"]["id"], second["recipe"]["version"]) == (first["id"], 2)
    listed = _ok(_call(tmp_path, "GET", "/api/bi/recipes", dataset="demo"))["recipes"]
    assert [(r["id"], r["version"]) for r in listed] == [(first["id"], 2)]
    detail = _ok(_call(tmp_path, "GET", f"/api/bi/recipes/{first['id']}", dataset="demo"))
    assert detail["recipe"]["version"] == 2
    assert [v["version"] for v in detail["versions"]] == [2, 1]
    status, payload = _call(tmp_path, "GET", "/api/bi/recipes/nope", dataset="demo")
    assert (status, payload["code"]) == (404, "recipe_unknown")
    bad = {"name": "x", "passes": [{"id": "p", "entity_type": "Ecosystem", "mapping": {"y": 1}}]}
    status, payload = _call(tmp_path, "POST", "/api/bi/recipes", {"dataset": "demo", "recipe": bad})
    assert (status, payload["code"], payload["pass_id"]) == (400, "mapping_key_unknown", "p")
    status, payload = _call(
        tmp_path, "POST", "/api/bi/recipes", {"dataset": "ns/name", "recipe": ROLES_RECIPE}
    )
    assert (status, payload["code"]) == (409, "dataset_read_only")
    # A saved version runs by id; the run records which version made it.
    source = _source(tmp_path, "roles.md", ROLES_MD)
    run = _run(tmp_path, source, recipe_id=first["id"], recipe_version=1)
    assert run["method_ref"] == f"recipe:{first['id']}@1"
    latest = _run(tmp_path, source, kind="trial", recipe_id=first["id"])
    assert latest["method_ref"] == f"recipe:{first['id']}@2"
    status, payload = _call(
        tmp_path,
        "POST",
        "/api/bi/runs",
        {"dataset": "demo", "kind": "ingest", "source_id": source, "recipe_id": "nope"},
    )
    assert (status, payload["code"]) == (404, "recipe_unknown")


# -- runs ----------------------------------------------------------------------


def test_the_supply_chain_report_runs_as_one_recipe(tmp_path: Path) -> None:
    source = _source(tmp_path, "supply_chain_extract.md")
    run = _run(tmp_path, source, recipe=_supply_recipe())
    assert run["method_ref"] == "recipe:inline" and run["status"] == "review"
    passes = {p["id"]: p for p in run["passes"]}
    assert list(passes) == ["suppliers", "certlabs", "instruments", "accounts"]
    assert passes["suppliers"]["tables"] == [0, 1, 2, 3, 4]
    assert passes["accounts"]["counts"]["candidates"] == 11
    assert passes["instruments"]["entity_type"] == "Competitor"
    assert any(w["code"] == "exploded_row" for w in passes["instruments"]["warnings"])
    assert [t["pass_id"] for t in run["tables"]] == [
        "suppliers",
        "suppliers",
        "suppliers",
        "suppliers",
        "suppliers",
        "accounts",
        "instruments",
        "certlabs",
    ]
    assert run["warnings"] == []  # every table is read
    found = _candidates(tmp_path, run["id"])
    keys = _by_key(found)
    # README: Competitor = the instrument makers; Rohde & Schwarz is excluded.
    assert sorted(k for t, k in keys if t == "Competitor") == [
        "Anritsu",
        "EMC-ESD",
        "Keysight",
        "LitePoint",
        "倚強科技",
    ]
    # README: the only missing link targets are NXP and NewPhotonics.
    missing = {
        w["message"]
        for c in found
        if c["entity_type"] == "Account"
        for w in c["warnings"]
        if w["code"] == "link_missing"
    }
    assert len(missing) == 2 and all("NXP" in m or "NewPhotonics" in m for m in missing)
    wnc = keys[("Account", "啟碁 WNC")]
    assert _value(wnc, "key_suppliers") == ["Qualcomm", "Broadcom", "NVIDIA", "穩懋", "NXP"]
    assert _value(wnc, "ticker") == "6285"
    supplier = next(f for f in wnc["fields"] if f["field"] == "key_suppliers")
    assert supplier["evidence"][0]["locator"] == {
        "table": 5,
        "line": 52,
        "column": "主要上游依賴",
    }
    assert supplier["evidence"][0]["excerpt"].startswith("Qualcomm(5G modem)")
    assert all(c["pass_id"] for c in found)


def test_ve05_mediatek_and_its_chinese_name_are_one_card(tmp_path: Path) -> None:
    source = _source(tmp_path, "supply_chain_extract.md")
    run = _run(tmp_path, source, recipe=_supply_recipe())
    found = _candidates(tmp_path, run["id"])
    keys = _by_key(found)
    assert ("Ecosystem", "聯發科") not in keys
    mediatek = keys[("Ecosystem", "MediaTek")]
    assert mediatek["pass_id"] == "suppliers"
    assert _value(mediatek, "node") == "L1-Chipset"
    assert _value(mediatek, "technologies") == ["WiFi-7"]
    assert _value(mediatek, "role") == "chipset"
    assert _value(mediatek, "ticker") == "2454"
    assert any(
        w["code"] == "alias_merged" and "聯發科" in w["message"] for w in mediatek["warnings"]
    )
    name = next(f for f in mediatek["fields"] if f["field"] == "name")
    excerpts = [e["excerpt"] for e in name["evidence"]]
    assert any("聯發科" in e for e in excerpts) and any("MediaTek" in e for e in excerpts)
    assert {e["locator"]["line"] for e in name["evidence"]} == {10, 13}
    _accept_all(tmp_path, run["id"])
    _commit(tmp_path, run["id"])
    store = BiStore(tmp_path)
    card = store.find("Ecosystem", "MediaTek")
    assert card is not None and store.find("Ecosystem", "聯發科") is None
    detail = _ok(_call(tmp_path, "GET", f"/api/bi/cards/{card['id']}", dataset="demo"))
    names = [e for e in detail["evidence"] if e["field"] == "name"]
    assert len(names) == 4 and all(e["source_name"] == "supply_chain_extract.md" for e in names)


def test_ve06_a_customer_is_never_a_competitor(tmp_path: Path) -> None:
    # The upstream sample: 中磊 is only ever an Account.
    sample = _run(tmp_path, _source(tmp_path, "supply_chain_extract.md"), recipe=_supply_recipe())
    found = _candidates(tmp_path, sample["id"])
    assert not any(c["entity_type"] == "Competitor" and "中磊" in c["canonical_key"] for c in found)
    assert ("Account", "中磊 Sercomm") in _by_key(found)
    # A report that also lists 中磊 as an instrument maker: the earlier pass
    # (Account) is the default, the Competitor waits for the person.
    run = _run(tmp_path, _source(tmp_path, "roles.md", ROLES_MD), recipe=ROLES_RECIPE)
    found = _candidates(tmp_path, run["id"])
    keys = _by_key(found)
    account = keys[("Account", "中磊")]
    assert any(w["code"] == "alias_merged" for w in account["warnings"])
    rival = keys[("Competitor", "中磊")]
    assert rival["pass_id"] == "instruments"
    assert rival["action"] == "skip" and rival["review"] == "pending"
    conflict = next(w for w in rival["warnings"] if w["code"] == "role_conflict")
    assert "accounts" in conflict["message"] and "Account" in conflict["message"]
    assert not any(w["code"] == "role_conflict" for w in account["warnings"])
    assert keys[("Competitor", "LitePoint")]["action"] == "create"
    assert run["warnings"] == [
        {"code": "table_unused", "message": "表格 2「附錄」沒有任何步驟讀取", "table": 2}
    ]
    assert run["tables"][2]["pass_id"] is None
    _accept_all(tmp_path, run["id"])
    result = _commit(tmp_path, run["id"])
    assert result["applied"]["created"] == 3 and result["skipped"] == 1
    assert _cards(tmp_path) == {
        ("Account", "中磊"),
        ("Account", "啟碁"),
        ("Competitor", "LitePoint"),
    }
    # The person may still decide it is a different role.
    again = _run(
        tmp_path, _source(tmp_path, "roles.md", ROLES_MD), kind="trial", recipe=ROLES_RECIPE
    )
    rival = _by_key(_candidates(tmp_path, again["id"]))[("Competitor", "中磊")]
    chosen = _review(tmp_path, again["id"], rival["id"], match={"action": "create"})
    assert chosen["candidate"]["action"] == "create"


def test_excel_workbook_runs_by_sheet_name(tmp_path: Path) -> None:
    source = _source(tmp_path, "study.xlsx", data=_workbook())
    recipe = {
        "name": "workbook",
        "passes": [
            {
                "id": "rivals",
                "tables": "sheet:Competitors",
                "entity_type": "Competitor",
                "mapping": {
                    "columns": {"廠商": "name", "更新日期": "updated", "產品線": "product_lines"}
                },
            },
            {
                "id": "customers",
                "tables": "sheet:Accounts",
                "entity_type": "Account",
                "mapping": {"columns": {"公司": "name", "代號": "ticker"}},
            },
        ],
    }
    run = _run(tmp_path, source, recipe=recipe)
    assert [w["code"] for w in run["warnings"]] == ["table_unused"]
    keys = _by_key(_candidates(tmp_path, run["id"]))
    keysight = keys[("Competitor", "Keysight")]
    assert _value(keysight, "updated") == "2026-10-07"
    updated = next(f for f in keysight["fields"] if f["field"] == "updated")
    assert updated["evidence"][0]["locator"] == {
        "sheet": "Competitors",
        "row": 3,
        "column": "更新日期",
    }
    assert updated["evidence"][0]["excerpt"] == "2026-10-07"
    assert _value(keys[("Account", "中磊")], "ticker") == "5388"
    # Without a recipe a workbook is refused, and a CSV keeps Case A.
    status, payload = _call(
        tmp_path, "POST", "/api/bi/runs", {"dataset": "demo", "kind": "ingest", "source_id": source}
    )
    assert (status, payload["code"]) == (400, "recipe_required")
    other = _source(tmp_path, "deck.pptx", "not a table")
    status, payload = _call(
        tmp_path,
        "POST",
        "/api/bi/runs",
        {"dataset": "demo", "kind": "ingest", "source_id": other, "recipe": recipe},
    )
    assert (status, payload["code"]) == (400, "file_type_unsupported")


def test_rerun_after_commit_creates_no_duplicates_and_undo_restores_every_pass(
    tmp_path: Path,
) -> None:
    source = _source(tmp_path, "supply_chain_extract.md")
    run = _run(tmp_path, source, recipe=_supply_recipe())
    assert not BiStore(tmp_path).exists  # running and reviewing write no card
    _accept_all(tmp_path, run["id"])
    assert not BiStore(tmp_path).exists
    result = _commit(tmp_path, run["id"])
    created = result["applied"]["created"]
    assert created == run["summary"]["create"]
    cards = _cards(tmp_path)
    assert len(cards) == created
    assert {t for t, _ in cards} == {"Ecosystem", "Competitor", "Account"}
    # The same report again: everything matches the cards it made.
    before = (BiStore(tmp_path).dir / "bi.sqlite").read_bytes()
    second = _run(tmp_path, source, recipe=_supply_recipe())
    assert second["summary"]["create"] == 0 and second["summary"]["update"] == 0
    assert second["summary"]["unchanged"] == second["summary"]["candidates"]
    for candidate in _candidates(tmp_path, second["id"])[:3]:
        _review(tmp_path, second["id"], candidate["id"], review="accepted")
    assert (BiStore(tmp_path).dir / "bi.sqlite").read_bytes() == before
    assert _cards(tmp_path) == cards
    # Undo of the multi-pass commit removes the cards of every pass.
    _ok(
        _call(
            tmp_path,
            "POST",
            "/api/bi/import/undo",
            {"dataset": "demo", "import_id": result["import_id"]},
        )
    )
    assert _cards(tmp_path) == set()


def test_a_csv_with_a_recipe_runs_its_passes(tmp_path: Path) -> None:
    text = "公司,代號,主要供應商\n中磊,5388,聯發科(晶片)\n"
    recipe = {
        "name": "csv",
        "name_aliases": {"聯發科": "MediaTek"},
        "passes": [
            {
                "id": "customers",
                "entity_type": "Account",
                "mapping": {
                    "columns": {"公司": "name", "代號": "ticker", "主要供應商": "key_suppliers"}
                },
            },
            {
                "id": "chips",
                "entity_type": "Ecosystem",
                "mapping": {"explode": [{"column": "主要供應商", "into": "name"}]},
            },
        ],
    }
    run = _run(tmp_path, _source(tmp_path, "c.csv", text), recipe=recipe)
    keys = _by_key(_candidates(tmp_path, run["id"]))
    account = keys[("Account", "中磊")]
    # A link target goes through name_aliases too, and the Ecosystem pass
    # (later in the recipe) makes it, so it is not reported missing.
    assert _value(account, "key_suppliers") == ["MediaTek"]
    assert not any(w["code"] == "link_missing" for w in account["warnings"])
    chip = keys[("Ecosystem", "MediaTek")]
    proof = next(f for f in chip["fields"] if f["field"] == "name")["evidence"][0]
    assert proof["locator"] == {"table": 0, "row": 2, "column": "主要供應商"}
