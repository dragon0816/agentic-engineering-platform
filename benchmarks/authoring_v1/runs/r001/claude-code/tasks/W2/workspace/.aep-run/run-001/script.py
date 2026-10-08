"""Sum sales amounts per region inside an inclusive date window."""
import csv
import json
import os
from pathlib import Path

WORKSPACE = Path(
    "C:/Users/Chi_L/Documents/ChatGPT/agentic-engineering-platform/benchmarks"
    "/authoring_v1/runs/r001/claude-code/tasks/W2/workspace"
)
if not WORKSPACE.is_dir():
    WORKSPACE = Path.cwd()

params = json.loads(
    Path(os.environ["AEP_WORKFLOW_PARAMS"]).read_text(encoding="utf-8")
)
from_date = str(params["from_date"]).strip()
to_date = str(params["to_date"]).strip()
min_amount = int(params["min_amount"])

totals = {}
source = WORKSPACE / "input" / "sales.csv"
with source.open(newline="", encoding="utf-8-sig") as handle:
    for row in csv.DictReader(handle):
        date = (row.get("date") or "").strip()
        region = (row.get("region") or "").strip()
        raw_amount = (row.get("amount") or "").strip()
        if not date or not region or not raw_amount:
            continue
        if date < from_date or date > to_date:
            continue
        amount = int(raw_amount)
        if amount < min_amount:
            continue
        totals[region] = totals.get(region, 0) + amount

output_dir = WORKSPACE / "output"
output_dir.mkdir(parents=True, exist_ok=True)
target = output_dir / f"summary-{from_date}-{to_date}.json"
summary = {region: totals[region] for region in sorted(totals)}
target.write_text(
    json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
)
print(f"wrote {target.name} covering {len(summary)} region(s)")
