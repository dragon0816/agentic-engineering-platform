"""Independent validators for coding_v1 (version 1.0). Never shown to the Agent.

`validate(task, ctx)` returns checks: {name, passed (True/False/None),
expected, actual, evidence_path}. `passed=None` means the evidence needed to
decide is missing; it never counts as a pass.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import re
import subprocess
import sys
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# 1.1 (2026-10-06): T20's fault-injection check reads the operator's injection
# evidence now that a platform Workflow run exists (G4); every other check and
# every expected answer is unchanged from 1.0.
# 1.2 (2026-10-06): T12 reads the merged rows from a workbook, CSV or JSON file;
# the owner's acceptance for T12 names rows and values, not a file format.
# 1.3 (2026-10-06): T13 counts the 500 page's requests during the delivered
# program's final run (the session total is reported beside it), and T09 checks
# data.json as the success scenario left it, before the always_fail run.
VALIDATOR_VERSION = "1.3"


@dataclass
class Ctx:
    task: str
    workspace: Path
    base_url: str = ""
    requests: Callable[[str], list[dict[str, Any]]] = lambda _prefix: []
    conversation: dict[str, Any] = field(default_factory=dict)
    source_hashes: dict[str, str] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def output(self) -> Path:
        return self.workspace / "output"


def check(name: str, passed: bool | None, expected: Any = None, actual: Any = None,
          evidence: str | None = None) -> dict[str, Any]:
    return {"name": name, "passed": passed, "expected": expected, "actual": _short(actual),
            "evidence_path": evidence}


def _short(value: Any) -> Any:
    text = json.dumps(value, ensure_ascii=False, default=str)
    return value if len(text) <= 600 else text[:597] + "..."


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def hashes(root: Path) -> dict[str, str]:
    return {p.relative_to(root).as_posix(): sha256(p) for p in sorted(root.rglob("*")) if p.is_file()}


def _find(ctx: Ctx, name: str) -> Path | None:
    for base in (ctx.output, ctx.workspace):
        candidate = base / name
        if candidate.is_file():
            return candidate
    return None


def _missing(name: str) -> list[dict[str, Any]]:
    return [check(f"{name} exists", False, name, None)]


def _sources_unchanged(ctx: Ctx) -> dict[str, Any]:
    now = hashes(ctx.workspace / "input")
    return check("input files unchanged", now == ctx.source_hashes, "same SHA-256",
                 {k: v[:12] for k, v in now.items() if ctx.source_hashes.get(k) != v} or "same")


def _sheet(path: Path, name: str | None = None) -> tuple[list[str], list[list[Any]]] | None:
    from openpyxl import load_workbook

    book = load_workbook(path, data_only=True)
    if name is not None and name not in book.sheetnames:
        return None
    ws = book[name] if name else book.worksheets[0]
    rows = [list(row) for row in ws.iter_rows(values_only=True)]
    rows = [row for row in rows if any(cell not in (None, "") for cell in row)]
    if not rows:
        return [], []
    header = [str(cell).strip() if cell is not None else "" for cell in rows[0]]
    return header, rows[1:]


def _records(path: Path, name: str | None = None) -> list[dict[str, Any]] | None:
    found = _sheet(path, name)
    if found is None:
        return None
    header, rows = found
    return [{header[i]: row[i] if i < len(row) else None for i in range(len(header)) if header[i]}
            for row in rows]


def _num(value: Any) -> float | None:
    if isinstance(value, bool) or value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _close(a: Any, b: float, tol: float = 1e-9) -> bool:
    n = _num(a)
    return n is not None and math.isclose(n, b, abs_tol=tol)


def _blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and value.strip() == "")


def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


# -- T01 ----------------------------------------------------------------------

def t01(ctx: Ctx) -> list[dict[str, Any]]:
    path = _find(ctx, "combined.md")
    if path is None:
        return _missing("combined.md") + [_sources_unchanged(ctx)]
    text = path.read_text(encoding="utf-8-sig").replace("\r\n", "\n")
    parts = re.split(r"^## (.+)$", text, flags=re.M)
    titles = [parts[i].strip() for i in range(1, len(parts), 2)]
    bodies = {parts[i].strip(): parts[i + 1].strip("\n") for i in range(1, len(parts), 2)}
    return [
        check("sections a, b, empty in order", titles == ["a", "b", "empty"], ["a", "b", "empty"], titles),
        check("a.txt kept", bodies.get("a", "").rstrip() == "第一行中文內容\n第二行：測試資料",
              "第一行中文內容\\n第二行：測試資料", bodies.get("a")),
        check("b.txt kept with blank line",
              bodies.get("b", "").rstrip() == "Hello world\n\nThe line above is blank.",
              "Hello world\\n\\nThe line above is blank.", bodies.get("b")),
        check("empty.txt has a heading and no body", "empty" in bodies and bodies["empty"].strip() == "",
              "", bodies.get("empty")),
        check("csv and nested file excluded",
              "nested file" not in text and "x,y" not in text, "absent", None),
        _sources_unchanged(ctx),
    ]


# -- T02 ----------------------------------------------------------------------

def t02(ctx: Ctx) -> list[dict[str, Any]]:
    path = _find(ctx, "failed_items.xlsx")
    if path is None:
        return _missing("failed_items.xlsx") + [_sources_unchanged(ctx)]
    found = _sheet(path, "failed_items")
    if found is None:
        return [check("sheet failed_items exists", False, "failed_items", None), _sources_unchanged(ctx)]
    header, rows = found
    ids = [row[0] for row in rows]
    return [
        check("columns kept", header == ["Device ID", "Status", "Value"], ["Device ID", "Status", "Value"], header),
        check("only 002, 003, 004 in order", ids == ["002", "003", "004"], ["002", "003", "004"], ids),
        check("IDs are text", all(isinstance(i, str) for i in ids), "str", [type(i).__name__ for i in ids]),
        check("status values kept", [str(r[1]).strip() for r in rows] == ["Fail", "fail", "FAIL"],
              ["Fail", "fail", "FAIL"], [r[1] for r in rows]),
        check("values kept", [_num(r[2]) for r in rows] == [20, 30, 40], [20, 30, 40], [r[2] for r in rows]),
        _sources_unchanged(ctx),
    ]


# -- T03 ----------------------------------------------------------------------

OWNERS = {"Alice": (2, 1, 1, ["T-1", "T-2"]), "Bob": (1, 1, 0, ["T-3"]),
          "Unassigned": (1, 0, 1, ["T-4"]), "A/B": (1, 1, 0, ["T-5"]),
          "A:B": (1, 0, 1, ["T-6"]), "X" * 40: (1, 1, 0, ["T-7"])}


def _legal_sheet(name: str) -> bool:
    return 0 < len(name) <= 31 and not re.search(r"[\[\]:*?/\\]", name) and name.lower() != "history"


def t03(ctx: Ctx) -> list[dict[str, Any]]:
    path = _find(ctx, "owners.xlsx")
    if path is None:
        return _missing("owners.xlsx") + [_sources_unchanged(ctx)]
    from openpyxl import load_workbook

    names = load_workbook(path).sheetnames
    summary = _records(path, "Summary")
    if summary is None:
        return [check("Summary sheet exists", False, "Summary", names), _sources_unchanged(ctx)]
    by_owner = {str(r.get("Owner")): r for r in summary}
    counts_ok = all(
        owner in by_owner and _close(by_owner[owner].get("Total"), total)
        and _close(by_owner[owner].get("Pass"), passed) and _close(by_owner[owner].get("Fail"), failed)
        for owner, (total, passed, failed, _tasks) in OWNERS.items())
    sheet_names = [str(r.get("SheetName")) for r in summary]
    seen: list[str] = []
    located = True
    for owner, (_t, _p, _f, tasks) in OWNERS.items():
        row = by_owner.get(owner)
        sheet = str(row.get("SheetName")) if row else ""
        records = _records(path, sheet) if sheet in names else None
        got = sorted(str(r.get("Task")) for r in records) if records is not None else None
        located = located and got == sorted(tasks)
        seen.extend(got or [])
    return [
        check("six owner groups in Summary", set(by_owner) == set(OWNERS), sorted(OWNERS), sorted(by_owner)),
        check("Total/Pass/Fail correct", counts_ok, {k: v[:3] for k, v in OWNERS.items()},
              {k: [v.get("Total"), v.get("Pass"), v.get("Fail")] for k, v in by_owner.items()}),
        check("sheet names legal, unique, <=31",
              len(set(sheet_names)) == len(sheet_names) and all(_legal_sheet(n) for n in sheet_names),
              "legal", sheet_names),
        check("SheetName locates each group's rows", located, "each group's tasks", None),
        check("each source row exactly once", sorted(seen) == sorted(f"T-{i}" for i in range(1, 8)),
              7, len(seen)),
        _sources_unchanged(ctx),
    ]


# -- T04 ----------------------------------------------------------------------

T04_EXPECTED = {"dir1/report.PDF": "PDF", "dir2/report.PDF": "PDF", "budget.xls": "Excel",
                "plan.xlsx": "Excel", "logo.png": "Image", "photo.JPG": "Image",
                "notes.txt": "Other", "README": "Other"}


def t04(ctx: Ctx) -> list[dict[str, Any]]:
    root = next((base / "classified" for base in (ctx.output, ctx.workspace)
                 if (base / "classified").is_dir()), None)
    if root is None:
        return _missing("classified/") + [_sources_unchanged(ctx)]
    source = ctx.workspace / "input" / "files"
    placed = all((root / cls / rel).is_file() and sha256(root / cls / rel) == sha256(source / rel)
                 for rel, cls in T04_EXPECTED.items())
    copies = [p for p in root.rglob("*") if p.is_file()]
    manifest_path = _find(ctx, "manifest.csv") or (root / "manifest.csv" if (root / "manifest.csv").is_file() else None)
    manifest_ok: bool | None = None
    rows: list[list[str]] = []
    if manifest_path is not None:
        with manifest_path.open(encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.reader(handle))
        body = " ".join(" ".join(row) for row in rows[1:]).replace("\\", "/")
        manifest_ok = len(rows) - 1 == 8 and all(
            sha256(source / rel) in body and rel.split("/")[-1] in body for rel in T04_EXPECTED)
    return [
        check("8 files in the right class with the relative path", placed, T04_EXPECTED,
              sorted(p.relative_to(root).as_posix() for p in copies)),
        check("no extra or overwritten copies", len(copies) == 8, 8, len(copies)),
        check("manifest.csv maps each file with SHA-256", manifest_ok if manifest_path else False,
              "8 rows with source, target, sha256", len(rows) - 1 if rows else None),
        _sources_unchanged(ctx),
    ]


# -- T05 ----------------------------------------------------------------------

def t05(ctx: Ctx) -> list[dict[str, Any]]:
    from openpyxl import load_workbook

    books = [p for p in ctx.output.glob("*.xlsx")] if ctx.output.is_dir() else []
    book = next((p for p in books if {"matched", "unmatched"} <= set(load_workbook(p).sheetnames)), None)
    if book is None:
        return [check("a workbook with matched and unmatched sheets", False, "matched+unmatched",
                      [p.name for p in books]), _sources_unchanged(ctx)]
    matched = _records(book, "matched") or []
    unmatched = _records(book, "unmatched") or []
    m_ids = sorted(str(r.get("Device ID")) for r in matched)
    tests = sorted(str(r.get("Test")) for r in matched)
    sources = sorted((str(r.get("Source")).strip().lower(), str(r.get("Device ID"))) for r in unmatched)
    names = {str(r.get("Device ID")): r.get("Name") for r in matched}
    return [
        check("matched has the 3 tests", m_ids == ["001", "001", "002"] and tests == ["RF-1", "RF-1", "RF-2"],
              ["001", "001", "002"], m_ids),
        check("matched rows carry device data", names.get("001") == "Alpha" and names.get("002") == "Beta",
              {"001": "Alpha", "002": "Beta"}, names),
        check("unmatched is device 003 and test 999", sources == [("devices", "003"), ("tests", "999")],
              [("devices", "003"), ("tests", "999")], sources),
        check("IDs keep leading zeros as text",
              all(isinstance(r.get("Device ID"), str) for r in matched + unmatched), "str", None),
        _sources_unchanged(ctx),
    ]


# -- T06 ----------------------------------------------------------------------

T06 = [
    {"step_id": 1, "action": "開啟量測儀器電源", "input": "主電源開關", "expected_result": "儀器開機畫面出現"},
    {"step_id": 2, "action": "執行自我校正", "input": None, "expected_result": "校正狀態顯示 OK"},
    {"step_id": 3, "action": "記錄環境溫度", "input": "溫度計讀值", "expected_result": None},
]


def _list_in(data: Any) -> list[Any] | None:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        lists = [v for v in data.values() if isinstance(v, list)]
        return lists[0] if len(lists) == 1 else None
    return None


def t06(ctx: Ctx) -> list[dict[str, Any]]:
    path = _find(ctx, "sop.json")
    if path is None:
        return _missing("sop.json") + [_sources_unchanged(ctx)]
    steps = _list_in(_json(path))
    return [
        check("three steps with the exact fields and values", steps == T06, T06, steps),
        check("no preface or notes mixed in", "注意" not in json.dumps(steps, ensure_ascii=False)
              and "本文件" not in json.dumps(steps, ensure_ascii=False), "absent", None),
        _sources_unchanged(ctx),
    ]


# -- T07 ----------------------------------------------------------------------

def t07(ctx: Ctx) -> list[dict[str, Any]]:
    path = _find(ctx, "specs.xlsx")
    if path is None:
        return _missing("specs.xlsx") + [_sources_unchanged(ctx)]
    rows = _records(path) or []
    by = {str(r.get("Model")): r for r in rows}

    def bw(r: dict[str, Any]) -> Any:
        return next((v for k, v in r.items() if k.lower().startswith("bandwidth")), None)

    def iface(r: dict[str, Any]) -> str:
        return re.sub(r"\s*;\s*", ";", str(r.get("Interface") or ""))

    freq = all(_close(by.get(m, {}).get("FrequencyMinMHz"), lo) and _close(by.get(m, {}).get("FrequencyMaxMHz"), hi)
               for m, lo, hi in (("RX-100", 2400, 2500), ("RX-200", 900, 930), ("RX-300", 5000, 6000)))
    band = (_close(bw(by.get("RX-100", {})), 80) and _close(bw(by.get("RX-200", {})), 20)
            and _blank(bw(by.get("RX-300", {}))))
    return [
        check("three models", sorted(by) == ["RX-100", "RX-200", "RX-300"], ["RX-100", "RX-200", "RX-300"], sorted(by)),
        check("frequency min/max in MHz", freq, "2400/2500, 900/930, 5000/6000", None),
        check("bandwidth MHz with the missing one blank", band, "80, 20, blank",
              [bw(by.get(m, {})) for m in ("RX-100", "RX-200", "RX-300")]),
        check("interfaces joined by semicolons",
              [iface(by.get(m, {})) for m in ("RX-100", "RX-200", "RX-300")] in (["USB;LAN", "LAN", "USB"],),
              ["USB;LAN", "LAN", "USB"], [iface(by.get(m, {})) for m in ("RX-100", "RX-200", "RX-300")]),
        _sources_unchanged(ctx),
    ]


# -- T08 ----------------------------------------------------------------------

T08 = [
    {"device_id": "D001", "test_name": "TxPower", "status": "Pass", "value": 12.5, "unit": "dBm"},
    {"device_id": "D002", "test_name": "TxPower", "status": "Fail", "value": None, "unit": "dBm"},
    {"device_id": "D003", "test_name": "EVM", "status": "Pass", "value": -35.2, "unit": "dB"},
    {"device_id": "D004", "test_name": "EVM", "status": "Fail", "value": -20.1, "unit": None},
    {"device_id": "D005", "test_name": "Sensitivity", "status": "Pass", "value": -90, "unit": "dBm"},
    {"device_id": "D006", "test_name": "Sensitivity", "status": "Fail", "value": -70, "unit": "dBm"},
]


def t08(ctx: Ctx) -> list[dict[str, Any]]:
    path = _find(ctx, "reports.json")
    if path is None:
        return _missing("reports.json") + [_sources_unchanged(ctx)]
    items = _list_in(_json(path)) or []
    keys_ok = all(isinstance(i, dict) and set(i) == set(T08[0]) for i in items)
    types_ok = all(isinstance(i.get("device_id"), str) and (i.get("value") is None or (
        isinstance(i.get("value"), (int, float)) and not isinstance(i.get("value"), bool))) for i in items)

    def norm(i: dict[str, Any]) -> tuple[Any, ...]:
        v = i.get("value")
        return (i.get("device_id"), i.get("test_name"), i.get("status"),
                None if v is None else round(float(v), 6), i.get("unit"))

    got = sorted(norm(i) for i in items if isinstance(i, dict))
    want = sorted(norm(i) for i in T08)
    return [
        check("six records", len(items) == 6, 6, len(items)),
        check("exact schema keys", keys_ok, sorted(T08[0]), None),
        check("types: id text, value number or null", types_ok, "str / number|null", None),
        check("each record matches the manifest", got == want, want, got),
        _sources_unchanged(ctx),
    ]


# -- T09 ----------------------------------------------------------------------

def t09(ctx: Ctx) -> list[dict[str, Any]]:
    runs = ctx.extra.get("t09_runs", {})
    ok_run = runs.get("succeed_third")
    fail_run = runs.get("always_fail")
    data_path = _find(ctx, "data.json")
    want = {"items": [{"id": "A1", "value": 42}, {"id": "A2", "value": 7}]}
    snapshot = ctx.extra.get("t09_success_output")
    data_ok = snapshot == want if snapshot is not None else (
        data_path is not None and _json(data_path) == want)
    if snapshot is not None:
        data_path = data_path or ctx.output / "data.json (success-scenario snapshot)"
    runtime = ctx.extra.get("aep_workflow_runs") or []
    return [
        check("a platform workflow ran in the AEP runtime", bool(runtime) or None, "AEP run id",
              runtime or "no AEP workflow run in the trace"),
        check("success scenario: 3 logins, 1 data", None if ok_run is None else
              (ok_run["login"] == 3 and ok_run["data"] == 1), {"login": 3, "data": 1}, ok_run),
        check("data.json written with the service data", data_ok if data_path else False,
              "service payload", str(data_path) if data_path else None),
        check("failure scenario: 3 logins, 0 data, reason reported", None if fail_run is None else
              (fail_run["login"] == 3 and fail_run["data"] == 0 and fail_run.get("reported")),
              {"login": 3, "data": 0}, fail_run),
        _sources_unchanged(ctx),
    ]


# -- T10-T13 ------------------------------------------------------------------

def _hits(ctx: Ctx, path: str) -> int:
    return sum(1 for r in ctx.requests(path) if r["path"].split("?")[0] == path)


CURRENCY = {"TWD": {"TWD", "NTD", "NT$"}, "USD": {"USD", "US$", "$"}, "EUR": {"EUR", "€"}}


def _currency(value: Any, code: str) -> bool:
    return str(value or "").strip().upper() in {c.upper() for c in CURRENCY[code]}


def t10(ctx: Ctx) -> list[dict[str, Any]]:
    path = _find(ctx, "products.xlsx")
    if path is None:
        return _missing("products.xlsx") + [check("catalog fetched", _hits(ctx, "/t10/catalog") > 0, ">0",
                                                  _hits(ctx, "/t10/catalog")), _sources_unchanged(ctx)]
    rows = _records(path) or []
    want = [("Router A", 1299, "/p/router-a"), ("Switch B", 2450, "/p/switch-b"), ("Cable C", 99, "/p/cable-c"),
            ("Adapter D", 560, "/p/adapter-d"), ("Antenna E", 12000, "/p/antenna-e")]

    def col(r: dict[str, Any], *names: str) -> Any:
        for k, v in r.items():
            if k.lower().replace(" ", "") in names:
                return v
        return None

    got = [(col(r, "name", "productname", "產品名稱", "名稱"), col(r, "price", "價格"),
            col(r, "currency", "幣別"), col(r, "url", "producturl", "產品網址", "網址")) for r in rows]
    return [
        check("exactly five catalog products, no ads", [g[0] for g in got] == [w[0] for w in want],
              [w[0] for w in want], [g[0] for g in got]),
        check("prices are numbers", all(_close(g[1], w[1]) and not isinstance(g[1], str)
                                        for g, w in zip(got, want, strict=False)) and len(got) == 5,
              [w[1] for w in want], [g[1] for g in got]),
        check("currency TWD", len(got) == 5 and all(_currency(g[2], "TWD") for g in got), "TWD", [g[2] for g in got]),
        check("full product URLs", len(got) == 5 and all(str(g[3]) == ctx.base_url + w[2] for g, w in zip(got, want, strict=False)),
              [ctx.base_url + w[2] for w in want], [g[3] for g in got]),
        check("catalog fetched from the fixture server", _hits(ctx, "/t10/catalog") > 0, ">0", _hits(ctx, "/t10/catalog")),
        _sources_unchanged(ctx),
    ]


def t11(ctx: Ctx) -> list[dict[str, Any]]:
    visits = {n: _hits(ctx, f"/t11/item/{n}") for n in range(1, 5)}
    path = _find(ctx, "details.xlsx")
    if path is None:
        return _missing("details.xlsx") + [check("4 detail pages visited", all(visits.values()), "all", visits)]
    rows = _records(path) or []
    want = [("Laptop 13", 32900, "Intel i5-1340P", 16, "/t11/item/1"), ("Laptop 15", 45500, "Intel i7-1360P", 32, "/t11/item/2"),
            ("Mini PC", 18800, None, 16, "/t11/item/3"), ("Tablet 11", 12300, "ARM A78", 8, "/t11/item/4")]
    ok = len(rows) == 4 and all(
        r.get("Name") == n and _close(r.get("Price"), p) and _currency(r.get("Currency"), "TWD")
        and ((_blank(r.get("CPU")) if c is None else r.get("CPU") == c)) and _close(r.get("MemoryGB"), m)
        and str(r.get("URL")) == ctx.base_url + u for r, (n, p, c, m, u) in zip(rows, want, strict=False))
    return [
        check("four rows matching the detail pages", ok, want, rows),
        check("missing CPU left blank", len(rows) == 4 and _blank(rows[2].get("CPU")), "blank",
              rows[2].get("CPU") if len(rows) > 2 else None),
        check("4 detail pages visited (access log)", all(visits.values()), "all >0", visits),
    ]


def _table_rows(path: Path) -> list[dict[str, Any]]:
    """Rows of a workbook, a CSV file or a JSON list (or {"...": [rows]})."""
    if path.suffix.lower() == ".xlsx":
        return _records(path) or []
    if path.suffix.lower() == ".csv":
        import csv

        with path.open(encoding="utf-8-sig", newline="") as handle:
            return list(csv.DictReader(handle))
    data = _list_in(_json(path))
    return [row for row in data or [] if isinstance(row, dict)]


def t12(ctx: Ctx) -> list[dict[str, Any]]:
    found = (sorted(ctx.output.glob("*.xlsx")) + sorted(ctx.output.glob("*.csv"))
             + sorted(ctx.output.glob("*.json"))) if ctx.output.is_dir() else []
    preferred = _find(ctx, "products.xlsx")
    candidates = ([preferred] if preferred else []) + found
    path = next((p for p in candidates if len(_table_rows(p)) > 0), None)
    if path is None:
        return [check("an output table (xlsx, csv or json)", False, "a table of rows", None)]
    rows = _table_rows(path)
    want = [("NX-1", 12000, "TWD", 16, "/t12/a"), ("NX-2", 8500, "TWD", 8, "/t12/a"),
            ("NX-1", 399.5, "USD", 16, "/t12/b"), ("NX-3", 1250, "USD", 32, "/t12/b"),
            ("NX-4", 499, "EUR", 4, "/t12/c"), ("NX-5", 1299, "EUR", 64, "/t12/c")]
    matched = 0
    for model, price, cur, mem, src in want:
        if any(r.get("Model") == model and _close(r.get("Price"), price) and _currency(r.get("Currency"), cur)
               and _close(r.get("MemoryGB"), mem) and str(r.get("SourceURL")) == ctx.base_url + src for r in rows):
            matched += 1
    return [
        check("six rows", len(rows) == 6, 6, len(rows)),
        check("each source product with price, currency, GB and source", matched == 6, 6, matched),
        check("three sources fetched", all(_hits(ctx, f"/t12/{x}") for x in "abc"), "a, b, c",
              {x: _hits(ctx, f"/t12/{x}") for x in "abc"}),
    ]


def t13(ctx: Ctx) -> list[dict[str, Any]]:
    window = ctx.extra.get("final_run_window")
    session_total = _hits(ctx, "/t13/item/5")
    if window:
        start, end = window
        tries = sum(1 for r in ctx.requests("/t13/item/5")
                    if r["path"].split("?")[0] == "/t13/item/5" and start <= r.get("t", start) <= end)
    else:
        tries = session_total
    path = _find(ctx, "robust_products.xlsx")
    if path is None:
        return _missing("robust_products.xlsx") + [check("500 page tried 3 times", tries == 3, 3, tries)]
    rows = _records(path) or []
    by = {str(r.get("Name")): r for r in rows}

    def na(v: Any) -> bool:
        return str(v).strip().upper() == "N/A"

    full = all(_close(by.get(n, {}).get("Price"), p) and by.get(n, {}).get("CPU") == c
               and str(by.get(n, {}).get("FetchStatus")).lower() == "ok"
               for n, p, c in (("Phone A", 9900, "Snap 7"), ("Phone B", 12900, "Snap 8")))
    missing = (na(by.get("Phone C", {}).get("Price")) and by.get("Phone C", {}).get("CPU") == "Dim 9"
               and na(by.get("Phone D", {}).get("CPU")) and _close(by.get("Phone D", {}).get("Price"), 7500))
    err = by.get("Phone E", {})
    error_ok = (str(err.get("FetchStatus")).lower() == "error" and na(err.get("Price")) and na(err.get("CPU"))
                and str(err.get("URL")) == ctx.base_url + "/t13/item/5")
    warnings_path = _find(ctx, "warnings.json")
    located = warnings_path is not None and "/t13/item/5" in warnings_path.read_text(encoding="utf-8-sig")
    return [
        check("five rows kept", len(rows) == 5, 5, len(rows)),
        check("complete pages correct", full, "Phone A/B with price, CPU, ok", None),
        check("missing values are N/A", missing, "Phone C price N/A, Phone D CPU N/A", None),
        check("500 page kept as error with N/A", error_ok, "error, N/A, URL kept", err),
        check("500 page tried exactly 3 times", tries == 3, 3,
              {"delivered program's run": tries, "whole session": session_total}),
        check("warnings.json locates the failed URL", located, "/t13/item/5", str(warnings_path) if warnings_path else None),
    ]


# -- T14 ----------------------------------------------------------------------

def t14(ctx: Ctx) -> list[dict[str, Any]]:
    path = _find(ctx, "summary.xlsx")
    if path is None:
        return _missing("summary.xlsx") + [_sources_unchanged(ctx)]
    from openpyxl import load_workbook

    names = load_workbook(path).sheetnames
    per_model = None
    for name in names:
        rec = _records(path, name) or []
        if rec and any(str(k).replace(" ", "").lower() in ("devicemodel", "model") for k in rec[0]):
            per_model = rec
            break
    overall = _records(path, "Overall") if "Overall" in names else None
    ok_models = per_model is not None and len(per_model) == 5 and all(
        _close(r.get("Total"), 2000) and _close(r.get("PassCount"), 1500) and _close(r.get("FailCount"), 500)
        and _close(r.get("PassRate"), 0.75) and _close(r.get("AvgDurationSeconds"), 3.5 + i)
        for i, r in enumerate(sorted(per_model, key=lambda r: str(r.get("Device Model") or r.get("Model")))))
    ov = (overall or [{}])[0]
    ok_overall = overall is not None and _close(ov.get("Total"), 10000) and _close(ov.get("PassCount"), 7500) \
        and _close(ov.get("FailCount"), 2500) and _close(ov.get("PassRate"), 0.75) and _close(ov.get("AvgDurationSeconds"), 5.5)
    return [
        check("per-model statistics", ok_models, "2000/1500/500/0.75 and 3.5..7.5", per_model),
        check("Overall sheet", ok_overall, "10000/7500/2500/0.75/5.5", overall),
        _sources_unchanged(ctx),
    ]


# -- T15 / T16 ------------------------------------------------------------------

T15 = [("2026-01-05T08:00:00", "DUT-01", "TxPower", "Pass"), ("2026-01-05T08:00:05", "DUT-01", "EVM", "Fail"),
       ("2026-01-05T08:01:00", "DUT-02", "TxPower", "Pass"), ("2026-01-05T08:02:00", "DUT-03", "TxPower", "Pass"),
       ("2026-01-05T08:03:00", "DUT-04", "TxPower", "Fail"), ("2026-01-05T08:04:00", "DUT-05", "EVM", "Pass")]


def t15(ctx: Ctx) -> list[dict[str, Any]]:
    parsed_path, warnings_path = _find(ctx, "parsed.json"), _find(ctx, "warnings.json")
    if parsed_path is None:
        return _missing("parsed.json") + [_sources_unchanged(ctx)]
    items = _list_in(_json(parsed_path)) or []
    got = [(i.get("timestamp"), i.get("device_id"), i.get("test_name"), i.get("status")) for i in items if isinstance(i, dict)]
    warns = _list_in(_json(warnings_path)) if warnings_path else None
    lines: list[Any] = []
    for w in warns or []:
        if isinstance(w, dict):
            lines.append(next((v for k, v in w.items() if "line" in k.lower() and isinstance(v, int)), None))
    raw_ok = bool(warns) and all(isinstance(w, dict) and any(isinstance(v, str) and v.startswith("[2026") for v in w.values())
                                 and any("reason" in k.lower() or "error" in k.lower() for k in w) for w in warns or [])
    return [
        check("six records parsed correctly", got == T15, T15, got),
        check("warnings for lines 5, 7, 9", sorted(x for x in lines if x is not None) == [5, 7, 9], [5, 7, 9], lines),
        check("warnings keep the raw text and a reason", raw_ok, "raw + reason", warns),
        _sources_unchanged(ctx),
    ]


T16 = {("2026-02-01T10:00:00", "DUT-11", "TxPower", "Pass", "run_a.log", "V1"),
       ("2026-02-01T10:00:05", "DUT-11", "EVM", "Fail", "run_a.log", "V1"),
       ("2026-02-01T10:01:00", "DUT-12", "TxPower", "Pass", "run_a.log", "V1"),
       ("2026-02-02T09:00:00", "DUT-21", "Sensitivity", "Pass", "run_b.log", "V2"),
       ("2026-02-02T09:00:10", "DUT-21", "EVM", "Fail", "run_b.log", "V2"),
       ("2026-02-02T09:01:00", "DUT-22", "TxPower", "Pass", "run_b.log", "V2")}


def t16(ctx: Ctx) -> list[dict[str, Any]]:
    path = _find(ctx, "unified.json")
    if path is None:
        return _missing("unified.json") + [_sources_unchanged(ctx)]
    data = _json(path)
    items = _list_in(data) if not (isinstance(data, dict) and "records" in data) else data["records"]
    got = {(i.get("timestamp"), i.get("device_id"), i.get("test_name"), i.get("status"),
            Path(str(i.get("source_file"))).name, str(i.get("format_version")).upper().replace("VERSION", "V").strip())
           for i in items or [] if isinstance(i, dict)}
    warned = any("run_c" in p.read_text(encoding="utf-8-sig", errors="ignore")
                 for p in (ctx.output.glob("*") if ctx.output.is_dir() else []) if p.is_file())
    return [
        check("six records with source and version", got == T16 and len(items or []) == 6, sorted(T16), sorted(got)),
        check("unknown-format file produced a warning", warned, "run_c.log mentioned in a warning", None),
        _sources_unchanged(ctx),
    ]


# -- T17 ----------------------------------------------------------------------

def t17_expected(original: dict[str, Any]) -> dict[str, Any]:
    out = json.loads(json.dumps(original))
    for band, mhz in zip(out["bands"], (2400, 5000, 2400), strict=True):
        band["frequency"] = mhz
        band["frequency_unit"] = "MHz"
    return out


def t17(ctx: Ctx) -> list[dict[str, Any]]:
    original = _json(ctx.workspace / "input" / "testplan.json")
    candidates = [p for p in (ctx.output.glob("*.json") if ctx.output.is_dir() else [])
                  if isinstance(_safe_json(p), dict) and "bands" in _safe_json(p)]
    if not candidates:
        return [check("converted testplan JSON in output", False, "a JSON with bands", None), _sources_unchanged(ctx)]
    converted = _safe_json(candidates[0])
    want = t17_expected(original)
    texts = " ".join(p.read_text(encoding="utf-8-sig", errors="ignore") for p in ctx.output.glob("*") if p.is_file()
                     and p != candidates[0])
    return [
        check("deep comparison with the expected conversion", converted == want, "only 3 frequency fields converted", converted),
        check("unknown unit 100kHz kept and warned", converted.get("sub", {}).get("nested", [{}, {}])[1].get("frequency") == "100kHz"
              and "100kHz" in texts, "kept + warning", None),
        _sources_unchanged(ctx),
    ]


def _safe_json(path: Path) -> Any:
    try:
        return _json(path)
    except (ValueError, OSError):
        return None


# -- T18 ----------------------------------------------------------------------

def t18(ctx: Ctx) -> list[dict[str, Any]]:
    script = ctx.output / "export.py"
    if not script.is_file():
        return _missing("output/export.py") + [_sources_unchanged(ctx)]
    with tempfile.TemporaryDirectory() as folder:
        target = Path(folder) / "summary.xlsx"
        run = subprocess.run([sys.executable, str(script), "--input", str(ctx.workspace / "input" / "input.csv"),
                              "--output", str(target)], capture_output=True, text=True, timeout=120,
                             cwd=ctx.workspace)
        rows = _records(target) if target.is_file() else None
    by = {str(r.get("Model")): r for r in rows or []}
    values_ok = (_close(by.get("M1", {}).get("Average"), 15) and _close(by.get("M1", {}).get("ValidCount"), 2)
                 and _close(by.get("M2", {}).get("Average"), 10) and _close(by.get("M2", {}).get("ValidCount"), 2))
    return [
        check("CLI exits 0", run.returncode == 0, 0, run.returncode),
        check("M1 15/2 and M2 10/2", values_ok, {"M1": [15, 2], "M2": [10, 2]}, rows),
        check("the Agent ran it (output/summary.xlsx present)", (ctx.output / "summary.xlsx").is_file(), True,
              (ctx.output / "summary.xlsx").is_file()),
        _sources_unchanged(ctx),
    ]


# -- T19 ----------------------------------------------------------------------

def t19(ctx: Ctx) -> list[dict[str, Any]]:
    path = _find(ctx, "converted.xlsx")
    if path is None:
        return _missing("converted.xlsx") + [_sources_unchanged(ctx)]
    found = _sheet(path)
    header, rows = found if found else ([], [])
    want = [["0001", "測試機甲", "正常", 10], ["0002", "測試機乙", "含, 逗號", 20], ["0003", "測試機丙", "第一行\n第二行", None],
            ["0001", "測試機甲", "正常", 10], ["0005", None, None, 50], ["0006", "測試機己", "說明", 60]]

    def same(a: Any, b: Any) -> bool:
        if b is None:
            return _blank(a)
        if isinstance(b, int):
            return _close(a, b)
        return str(a).replace("\r\n", "\n") == b

    ok = len(rows) == 6 and all(len(r) >= 4 and all(same(r[i], w[i]) for i in range(4)) for r, w in zip(rows, want, strict=False))
    return [
        check("header kept without BOM and no index column", header == ["Device ID", "名稱", "備註", "Value"],
              ["Device ID", "名稱", "備註", "Value"], header),
        check("six rows in order with duplicates, blanks and multi-line text", ok, want, rows),
        check("IDs are text with leading zeros", len(rows) == 6 and all(isinstance(r[0], str) for r in rows), "str",
              [r[0] for r in rows]),
        _sources_unchanged(ctx),
    ]


# -- T20 ----------------------------------------------------------------------

def _fault_recovered(ctx: Ctx) -> bool | None:
    """The operator locked failures.xlsx during the first approved platform
    run, as an open workbook would; None when no platform run was asked for."""
    fault = ctx.extra.get("t20_fault") or {}
    if not fault.get("injected"):
        return None
    return bool(fault.get("first_failed")) and bool(fault.get("recovered"))


def t20(ctx: Ctx) -> list[dict[str, Any]]:
    convo = ctx.conversation
    asked = bool(convo.get("asked_threshold"))
    failures = _find(ctx, "failures.xlsx")
    rows = _records(failures) if failures else None
    urgent = {str(r.get("Device ID")): str(r.get("Urgent")).strip().lower() for r in rows or []}
    rows_ok = urgent == {"D01": "false", "D03": "false", "D05": "true"}
    summary = _find(ctx, "summary.md")
    text = summary.read_text(encoding="utf-8-sig") if summary else ""
    numbers = {k: re.search(rf"{k}\D{{0,10}}(\d+)", text, flags=re.I) for k in ("Total", "Pass", "Fail", "Urgent")}
    summary_ok = summary is not None and all(
        m is not None and int(m.group(1)) == v for (k, m), v in zip(numbers.items(), (5, 2, 3, 1), strict=True))
    runtime = ctx.extra.get("aep_workflow_runs") or []
    return [
        check("asked for the threshold before using one", asked, "a question about the threshold",
              convo.get("first_reply", "")[:300]),
        check("failures.xlsx has 3 Fail rows, only D05 urgent", rows_ok if failures else False,
              {"D01": "false", "D03": "false", "D05": "true"}, urgent),
        check("summary.md Total=5 Pass=2 Fail=3 Urgent=1", summary_ok, "5/2/3/1", text[:300]),
        check("platform workflow ran in the AEP runtime", bool(runtime) or None, "AEP run id", runtime or None),
        check("injected write fault observed and recovered", _fault_recovered(ctx),
              "first approved run fails on the locked output, a later run succeeds",
              ctx.extra.get("t20_fault")),
        _sources_unchanged(ctx),
    ]


VALIDATORS: dict[str, Callable[[Ctx], list[dict[str, Any]]]] = {
    f"T{n:02d}": globals()[f"t{n:02d}"] for n in range(1, 21)
}


def validate(task: str, ctx: Ctx) -> list[dict[str, Any]]:
    try:
        return VALIDATORS[task](ctx)
    except Exception as error:  # noqa: BLE001 - a malformed output is a failed check, not a crash
        return [check("output readable", False, "parseable outputs", f"{type(error).__name__}: {error}")]
