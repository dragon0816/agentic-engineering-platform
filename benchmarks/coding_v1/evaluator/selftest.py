"""Validator self-test: a correct sample passes and known-wrong samples fail.

    python benchmarks/coding_v1/evaluator/selftest.py

The samples are the evaluator's own reference outputs. They exist only here
and are never given to the Agent under test.
"""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from validators import T06, T08, T15, Ctx, hashes, t17_expected, validate  # noqa: E402

FIXTURES = HERE.parent / "fixtures"
BASE = "http://127.0.0.1:9999"


def xlsx(path: Path, sheets: dict[str, list[list[Any]]], text_first: bool = False) -> None:
    from openpyxl import Workbook

    book = Workbook()
    book.remove(book.active)
    for name, rows in sheets.items():
        ws = book.create_sheet(name)
        for row in rows:
            ws.append(row)
    path.parent.mkdir(parents=True, exist_ok=True)
    book.save(path)


def workspace(task: str) -> Path:
    root = Path(tempfile.mkdtemp(prefix=f"selftest-{task}-"))
    shutil.copytree(FIXTURES / task / "input", root / "input")
    (root / "output").mkdir()
    return root


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


# -- correct samples (reference outputs; evaluator only) ---------------------

def ok_t01(o: Path, _w: Path) -> None:
    write(o / "combined.md", "## a\n第一行中文內容\n第二行：測試資料\n\n## b\nHello world\n\nThe line above is blank.\n\n## empty\n")


def ok_t02(o: Path, _w: Path) -> None:
    xlsx(o / "failed_items.xlsx", {"failed_items": [["Device ID", "Status", "Value"], ["002", "Fail", 20],
                                                    ["003", " fail ", 30], ["004", "FAIL", 40]]})


def ok_t03(o: Path, _w: Path, sheet_ab: str = "A_B") -> None:
    groups = {"Alice": ("Alice", [["T-1", "Alice", "Pass"], ["T-2", "Alice", "Fail"]]),
              "Bob": ("Bob", [["T-3", "Bob", "Pass"]]), "Unassigned": ("Unassigned", [["T-4", None, "Fail"]]),
              "A/B": (sheet_ab, [["T-5", "A/B", "Pass"]]), "A:B": ("A_B (2)", [["T-6", "A:B", "Fail"]]),
              "X" * 40: ("X" * 31, [["T-7", "X" * 40, "Pass"]])}
    sheets: dict[str, list[list[Any]]] = {}
    summary = [["Owner", "Total", "Pass", "Fail", "SheetName"]]
    for owner, (sheet, rows) in groups.items():
        sheets[sheet] = [["Task", "Owner", "Status"], *rows]
        summary.append([owner, len(rows), sum(r[2] == "Pass" for r in rows), sum(r[2] == "Fail" for r in rows), sheet])
    if sheet_ab == "A/B":   # an illegal name cannot even be saved by openpyxl; fake it in Summary only
        sheets.pop("A/B")
        sheets["A-B"] = [["Task", "Owner", "Status"], ["T-5", "A/B", "Pass"]]
    sheets["Summary"] = summary
    xlsx(o / "owners.xlsx", sheets)


def ok_t04(o: Path, w: Path) -> None:
    from validators import T04_EXPECTED

    rows = [["source", "target", "sha256"]]
    for rel, cls in T04_EXPECTED.items():
        target = o / "classified" / cls / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(w / "input" / "files" / rel, target)
        rows.append([f"input/files/{rel}", f"classified/{cls}/{rel}",
                     hashlib.sha256(target.read_bytes()).hexdigest()])
    with (o / "manifest.csv").open("w", newline="", encoding="utf-8") as handle:
        csv.writer(handle).writerows(rows)


def ok_t05(o: Path, _w: Path) -> None:
    xlsx(o / "merged.xlsx", {
        "matched": [["Device ID", "Name", "Location", "Test", "Result"], ["001", "Alpha", "Lab A", "RF-1", "Pass"],
                    ["001", "Alpha", "Lab A", "RF-2", "Fail"], ["002", "Beta", "Lab B", "RF-1", "Pass"]],
        "unmatched": [["Source", "Device ID", "Name", "Test"], ["devices", "003", "Gamma", None],
                      ["tests", "999", None, "RF-9"]]})


def ok_t06(o: Path, _w: Path) -> None:
    write(o / "sop.json", json.dumps(T06, ensure_ascii=False))


def ok_t07(o: Path, _w: Path, bw2: float = 20) -> None:
    xlsx(o / "specs.xlsx", {"specs": [["Model", "FrequencyMinMHz", "FrequencyMaxMHz", "BandwidthMHz", "Interface"],
                                      ["RX-100", 2400, 2500, 80, "USB;LAN"], ["RX-200", 900, 930, bw2, "LAN"],
                                      ["RX-300", 5000, 6000, None, "USB"]]})


def ok_t08(o: Path, _w: Path, rows: list[dict[str, Any]] | None = None) -> None:
    write(o / "reports.json", json.dumps(rows if rows is not None else T08))


def ok_t09(o: Path, _w: Path) -> None:
    write(o / "data.json", json.dumps({"items": [{"id": "A1", "value": 42}, {"id": "A2", "value": 7}]}))


def ok_t10(o: Path, _w: Path, with_ad: bool = False) -> None:
    rows = [["Name", "Price", "Currency", "URL"]]
    if with_ad:
        rows.append(["Sponsored Router", 99, "TWD", BASE + "/ad/1"])
    rows += [["Router A", 1299, "TWD", BASE + "/p/router-a"], ["Switch B", 2450, "TWD", BASE + "/p/switch-b"],
             ["Cable C", 99, "TWD", BASE + "/p/cable-c"], ["Adapter D", 560, "TWD", BASE + "/p/adapter-d"],
             ["Antenna E", 12000, "TWD", BASE + "/p/antenna-e"]]
    xlsx(o / "products.xlsx", {"products": rows})


def ok_t11(o: Path, _w: Path) -> None:
    xlsx(o / "details.xlsx", {"details": [["Name", "Price", "Currency", "CPU", "MemoryGB", "URL"],
                                          ["Laptop 13", 32900, "TWD", "Intel i5-1340P", 16, BASE + "/t11/item/1"],
                                          ["Laptop 15", 45500, "TWD", "Intel i7-1360P", 32, BASE + "/t11/item/2"],
                                          ["Mini PC", 18800, "TWD", None, 16, BASE + "/t11/item/3"],
                                          ["Tablet 11", 12300, "TWD", "ARM A78", 8, BASE + "/t11/item/4"]]})


def ok_t12(o: Path, _w: Path, mem_mb: bool = False) -> None:
    xlsx(o / "products.xlsx", {"products": [["Model", "Price", "Currency", "MemoryGB", "SourceURL"],
                                            ["NX-1", 12000, "TWD", 16, BASE + "/t12/a"],
                                            ["NX-2", 8500, "TWD", 8192 if mem_mb else 8, BASE + "/t12/a"],
                                            ["NX-1", 399.5, "USD", 16, BASE + "/t12/b"],
                                            ["NX-3", 1250, "USD", 32, BASE + "/t12/b"],
                                            ["NX-4", 499, "EUR", 4, BASE + "/t12/c"],
                                            ["NX-5", 1299, "EUR", 64, BASE + "/t12/c"]]})


def ok_t13(o: Path, _w: Path) -> None:
    xlsx(o / "robust_products.xlsx", {"p": [["Name", "Price", "Currency", "CPU", "URL", "FetchStatus"],
                                            ["Phone A", 9900, "TWD", "Snap 7", BASE + "/t13/item/1", "ok"],
                                            ["Phone B", 12900, "TWD", "Snap 8", BASE + "/t13/item/2", "ok"],
                                            ["Phone C", "N/A", "N/A", "Dim 9", BASE + "/t13/item/3", "ok"],
                                            ["Phone D", 7500, "TWD", "N/A", BASE + "/t13/item/4", "ok"],
                                            ["Phone E", "N/A", "N/A", "N/A", BASE + "/t13/item/5", "error"]]})
    write(o / "warnings.json", json.dumps([{"url": BASE + "/t13/item/5", "status": "error"}]))


def ok_t14(o: Path, _w: Path, avg_shift: float = 0) -> None:
    head = ["Device Model", "Total", "PassCount", "FailCount", "PassRate", "AvgDurationSeconds"]
    xlsx(o / "summary.xlsx", {"summary": [head] + [[f"M{i}", 2000, 1500, 500, 0.75, 3.5 + i + avg_shift] for i in range(5)],
                              "Overall": [head[1:], [10000, 7500, 2500, 0.75, 5.5]]})


def ok_t15(o: Path, _w: Path) -> None:
    write(o / "parsed.json", json.dumps([dict(zip(("timestamp", "device_id", "test_name", "status"), r, strict=True)) for r in T15]))
    write(o / "warnings.json", json.dumps([
        {"line": 5, "raw": "[2026-01-05T08:01:05][DUT-02][EVM]PASS]", "reason": "missing bracket"},
        {"line": 7, "raw": "[2026-01-05T08:02:05][DUT-03][PASS]", "reason": "missing field"},
        {"line": 9, "raw": "[2026-01-05T08:03:05][DUT-04][EVM][SKIP]", "reason": "unknown result"}]))


def ok_t16(o: Path, _w: Path) -> None:
    from validators import T16

    write(o / "unified.json", json.dumps([dict(zip(("timestamp", "device_id", "test_name", "status", "source_file",
                                                    "format_version"), r, strict=True)) for r in sorted(T16)]))
    write(o / "warnings.json", json.dumps([{"file": "run_c.log", "reason": "unknown format"}]))


def ok_t17(o: Path, w: Path) -> None:
    write(o / "testplan.json", json.dumps(t17_expected(json.loads((w / "input" / "testplan.json").read_text("utf-8")))))
    write(o / "warnings.json", json.dumps([{"path": "sub.nested[1].frequency", "value": "100kHz"}]))


def ok_t18(o: Path, w: Path) -> None:
    fixed = (w / "input" / "export.py").read_text("utf-8").replace('row["DeviceModel"]', 'row["Model"]') \
        .replace('totals.get(model, "") + value', 'totals.get(model, 0.0) + float(value)')
    write(o / "export.py", fixed)
    xlsx(o / "summary.xlsx", {"summary": [["Model", "Average", "ValidCount"], ["M1", 15, 2], ["M2", 10, 2]]})


def ok_t19(o: Path, _w: Path) -> None:
    xlsx(o / "converted.xlsx", {"converted": [["Device ID", "名稱", "備註", "Value"], ["0001", "測試機甲", "正常", 10],
                                              ["0002", "測試機乙", "含, 逗號", 20], ["0003", "測試機丙", "第一行\n第二行", None],
                                              ["0001", "測試機甲", "正常", 10], ["0005", None, None, 50], ["0006", "測試機己", "說明", 60]]})


def ok_t20(o: Path, _w: Path) -> None:
    xlsx(o / "failures.xlsx", {"failures": [["Device ID", "Status", "Value", "Urgent"], ["D01", "Fail", 10, False],
                                            ["D03", "Fail", 20, False], ["D05", "Fail", 30, True]]})
    write(o / "summary.md", "Total: 5\nPass: 2\nFail: 3\nUrgent: 1\n")


SAMPLES: dict[str, Callable[..., None]] = {f"T{n:02d}": globals()[f"ok_t{n:02d}"] for n in range(1, 21)}

GOOD_LOGS = {"T10": ["/t10/catalog"], "T11": [f"/t11/item/{n}" for n in range(1, 5)],
             "T12": ["/t12/a", "/t12/b", "/t12/c"], "T13": ["/t13/item/5"] * 3}


def ctx_for(task: str, ws: Path, logs: list[str] | None = None, **extra: Any) -> Ctx:
    paths = GOOD_LOGS.get(task, []) if logs is None else logs
    log = [{"path": p, "status": 200, "method": "GET"} for p in paths]
    return Ctx(task=task, workspace=ws, base_url=BASE,
               requests=lambda prefix: [r for r in log if r["path"].startswith(prefix)],
               conversation={"asked_threshold": True, "first_reply": "門檻是多少？"},
               source_hashes=hashes(FIXTURES / task / "input"), extra=extra)


def verdict(checks: list[dict[str, Any]]) -> bool:
    return all(c["passed"] is True for c in checks)


def run() -> int:
    failures: list[str] = []

    def expect(label: str, checks: list[dict[str, Any]], should_pass: bool) -> None:
        if verdict(checks) != should_pass:
            bad = [c["name"] for c in checks if c["passed"] is not True]
            failures.append(f"{label}: expected {'pass' if should_pass else 'fail'}; not passed: {bad}")

    full_runtime = {"aep_workflow_runs": ["run-x"], "t09_runs": {
        "succeed_third": {"login": 3, "data": 1}, "always_fail": {"login": 3, "data": 0, "reported": True}},
        "t20_fault": {"injected": True, "first_failed": True, "recovered": True}}
    for task, sample in SAMPLES.items():
        ws = workspace(task)
        sample(ws / "output", ws)
        checks = validate(task, ctx_for(task, ws, **(full_runtime if task in ("T09", "T20") else {})))
        expect(f"{task} correct sample", checks, True)
        empty = workspace(task)
        expect(f"{task} empty output", validate(task, ctx_for(task, empty)), False)

    def wrong(task: str, label: str, make: Callable[[Path, Path], None], **kw: Any) -> None:
        ws = workspace(task)
        make(ws / "output", ws)
        expect(f"{task} {label}", validate(task, ctx_for(task, ws, **kw)), False)

    t12_csv = workspace("T12")
    with (t12_csv / "output").joinpath("merged.csv").open("w", encoding="utf-8", newline="") as handle:
        handle.write("Model,Price,Currency,MemoryGB,SourceURL\n" + "".join(
            f"{m},{p},{c},{g},{BASE}{u}\n" for m, p, c, g, u in (
                ("NX-1", 12000, "TWD", 16, "/t12/a"), ("NX-2", 8500, "TWD", 8, "/t12/a"),
                ("NX-1", 399.5, "USD", 16, "/t12/b"), ("NX-3", 1250, "USD", 32, "/t12/b"),
                ("NX-4", 499, "EUR", 4, "/t12/c"), ("NX-5", 1299, "EUR", 64, "/t12/c"))))
    expect("T12 correct rows as CSV", validate("T12", ctx_for("T12", t12_csv)), True)

    wrong("T20", "write fault not recovered", SAMPLES["T20"], aep_workflow_runs=["run-x"],
          t20_fault={"injected": True, "first_failed": True, "recovered": False})

    wrong("T01", "nested file merged", lambda o, w: write(o / "combined.md",
          "## a\n第一行中文內容\n第二行：測試資料\n\n## b\nHello world\n\nThe line above is blank.\n\n## c\nnested file must not be merged\n\n## empty\n"))
    wrong("T02", "leading zeros lost / missing row", lambda o, w: xlsx(o / "failed_items.xlsx", {
        "failed_items": [["Device ID", "Status", "Value"], [2, "Fail", 20], [3, " fail ", 30]]}))
    wrong("T03", "illegal sheet name in Summary", lambda o, w: ok_t03(o, w, sheet_ab="A/B"))
    wrong("T05", "product-style duplicate join", lambda o, w: xlsx(o / "merged.xlsx", {
        "matched": [["Device ID", "Name", "Test"], ["001", "Alpha", "RF-1"], ["001", "Alpha", "RF-2"],
                    ["001", "Alpha", "RF-1"], ["001", "Alpha", "RF-2"], ["002", "Beta", "RF-1"]],
        "unmatched": [["Source", "Device ID"], ["devices", "003"], ["tests", "999"]]}))
    wrong("T07", "bandwidth unit not converted", lambda o, w: ok_t07(o, w, bw2=0.02))
    wrong("T08", "a missing record", lambda o, w: ok_t08(o, w, rows=T08[:5]))
    wrong("T10", "ad included", lambda o, w: ok_t10(o, w, with_ad=True))
    wrong("T10", "catalog never fetched", ok_t10, logs=[])
    wrong("T11", "detail pages not visited", ok_t11, logs=["/t11/list"])
    wrong("T12", "MB not converted", lambda o, w: ok_t12(o, w, mem_mb=True))
    wrong("T13", "500 page tried once", ok_t13, logs=["/t13/item/5"])
    wrong("T14", "wrong average", lambda o, w: ok_t14(o, w, avg_shift=0.5))
    wrong("T18", "explanation only, no program", lambda o, w: write(o / "fix.md", "Change DeviceModel to Model."))
    wrong("T09", "no runtime evidence", ok_t09)
    wrong("T20", "threshold guessed without asking", ok_t20)
    ws = workspace("T01")
    ok_t01(ws / "output", ws)
    (ws / "input" / "texts" / "a.txt").write_text("changed", encoding="utf-8")
    expect("T01 source modified", validate("T01", ctx_for("T01", ws)), False)

    print(f"{len(failures)} self-test problem(s)")
    for item in failures:
        print(" -", item)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(run())
