#!/usr/bin/env python3
"""Read input.csv, calculate average Value by Model, and write summary.xlsx.

CLI intentionally remains compatible with the original interface:
    python export.py --input input.csv --output summary.xlsx
"""

from __future__ import annotations

import argparse
import csv
from collections import OrderedDict
from pathlib import Path
from typing import Optional

from openpyxl import Workbook


def _parse_value(value: object) -> Optional[float]:
    """Return a numeric Value, or None when the source cell is blank.

    Blank Value cells are excluded from both Average and ValidCount. Nonblank
    nonnumeric values are rejected because silently treating them as zero would
    corrupt the average.
    """
    if value is None:
        return None
    text = str(value).strip()
    if text == "":
        return None
    try:
        return float(text)
    except ValueError as exc:
        raise ValueError(f"Value must be numeric or blank, got {value!r}") from exc


def build_summary(input_csv: str | Path) -> list[tuple[str, Optional[float], int]]:
    groups: "OrderedDict[str, list[float]]" = OrderedDict()
    input_csv = Path(input_csv)

    with input_csv.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError("Input CSV is missing a header row")
        missing = {"Model", "Value"} - set(reader.fieldnames)
        if missing:
            raise ValueError(f"Input CSV missing required column(s): {', '.join(sorted(missing))}")

        for row in reader:
            model = row["Model"]
            groups.setdefault(model, [])
            parsed = _parse_value(row.get("Value"))
            if parsed is not None:
                groups[model].append(parsed)

    summary: list[tuple[str, Optional[float], int]] = []
    for model, values in groups.items():
        average = (sum(values) / len(values)) if values else None
        summary.append((model, average, len(values)))
    return summary


def write_summary_xlsx(rows: list[tuple[str, Optional[float], int]], output_xlsx: str | Path) -> None:
    output_xlsx = Path(output_xlsx)
    output_xlsx.parent.mkdir(parents=True, exist_ok=True)

    wb = Workbook()
    ws = wb.active
    ws.title = "summary"
    ws.append(["Model", "Average", "ValidCount"])
    for model, average, valid_count in rows:
        ws.append([model, average, valid_count])
    wb.save(output_xlsx)


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize average Value by Model")
    parser.add_argument("--input", required=True, help="Path to input CSV")
    parser.add_argument("--output", required=True, help="Path to output XLSX")
    args = parser.parse_args()

    rows = build_summary(args.input)
    write_summary_xlsx(rows, args.output)


if __name__ == "__main__":
    main()
