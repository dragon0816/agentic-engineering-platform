"""Sum a category,item,amount CSV into category totals."""

import csv
import json
import os
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

params = json.loads(Path(os.environ["AEP_WORKFLOW_PARAMS"]).read_text(encoding="utf-8"))
input_file = str(params["input_file"]).strip()
output_name = Path(str(params["output_name"]).strip()).name
if not output_name:
    raise SystemExit("output_name is empty")

totals: dict[str, Decimal] = {}
with open(input_file, newline="", encoding="utf-8-sig") as handle:
    reader = csv.DictReader(handle)
    missing = {"category", "amount"} - set(reader.fieldnames or ())
    if missing:
        raise SystemExit(f"input file is missing columns: {sorted(missing)}")
    for row in reader:
        category = (row.get("category") or "").strip()
        amount = (row.get("amount") or "").strip()
        if not category and not amount:
            continue
        totals[category] = totals.get(category, Decimal("0")) + Decimal(amount)

output_dir = Path.cwd() / "output"
output_dir.mkdir(exist_ok=True)
target = output_dir / f"{output_name}.csv"
with open(target, "w", newline="", encoding="utf-8") as handle:
    writer = csv.writer(handle)
    writer.writerow(["category", "total"])
    for category in sorted(totals):
        total = totals[category].quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        writer.writerow([category, f"{total:.2f}"])

print(f"wrote output/{target.name}: {len(totals)} categories")
