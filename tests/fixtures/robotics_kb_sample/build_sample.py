#!/usr/bin/env python3
"""從 tools/samples/robotics 的 CSV 重建完整範例 vault(BI/ 資料夾)。
用法: py build_sample.py [輸出資料夾,預設 ./BI]
"""
import subprocess, sys, pathlib
root = pathlib.Path(__file__).resolve().parent
tools = root / "tools"
vault = pathlib.Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else root / "BI"
vault.mkdir(parents=True, exist_ok=True)
S = "samples/robotics/"
STEPS = [  # (csv, type, extra args)
    ("nodes_robotics.csv", "node", []),
    ("ecosystem_robotics.csv", "ecosystem", []),
    ("accounts_core_robotics.csv", "account", []),
    ("competitors_robotics.csv", "competitor", []),
    ("technology_robotics.csv", "technology", []),
    ("trend_robotics.csv", "trend", []),
    ("application_robotics.csv", "application", []),
    ("test_solutions_robotics.csv", "test_solution", []),
    ("customer_products_robotics.csv", "customer_product", []),
    ("opportunities_robotics.csv", "opportunity", []),
    ("signals_robotics.csv", "signal", []),
    ("concepts_robotics.csv", "concept", []),
]
for csv_name, typ, extra in STEPS:
    cmd = [sys.executable, "bi_ingest.py", S + csv_name, "--type", typ, "--vault", str(vault), "-q"] + extra
    print(">>", typ, csv_name)
    r = subprocess.run(cmd, cwd=tools)
    if r.returncode: sys.exit(r.returncode)
subprocess.run([sys.executable, "bi_ingest.py", "--emit-templates", str(vault / "_Templates")], cwd=tools, check=True)
print("完成:", vault)
