#!/usr/bin/env python3
"""Create an Excel summary by Model from an input CSV.

CLI is intentionally kept compatible with the original script:
    python export.py --input input.csv --output summary.xlsx
"""

from __future__ import annotations

import argparse
import csv
from collections import OrderedDict
from pathlib import Path
from typing import Iterable

from openpyxl import Workbook


def _parse_value(raw: object) -> float | None:
    """Return a numeric value, or None for blank/missing cells.

    Blank Value cells are ignored by the average and ValidCount as required.
    Non-blank, non-numeric values are treated as invalid data and raise a clear
    error instead of being silently counted incorrectly.
    """
    if raw is None:
        return None
    text = str(raw).strip()
    if text == "":
        return None
    try:
        return float(text)
    except ValueError as exc:
        raise ValueError(f"Value must be numeric or blank, got {raw!r}") from exc


def build_summary(input_csv: str | Path) -> list[tuple[str, float | None, int]]:
    """Read CSV and return rows: (Model, Average, ValidCount)."""
    groups: "OrderedDict[str, list[float]]" = OrderedDict()
    with open(input_csv, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError("Input CSV is missing a header row")
        required = {"Model", "Value"}
        missing = required.difference(reader.fieldnames)
        if missing:
            raise ValueError(f"Input CSV missing required column(s): {', '.join(sorted(missing))}")

        for row_num, row in enumerate(reader, start=2):
            model = (row.get("Model") or "").strip()
            if model == "":
                raise ValueError(f"Row {row_num}: Model is blank")
            groups.setdefault(model, [])
            value = _parse_value(row.get("Value"))
            if value is not None:
                groups[model].append(value)

    summary: list[tuple[str, float | None, int]] = []
    for model, values in groups.items():
        count = len(values)
        average = (sum(values) / count) if count else None
        summary.append((model, average, count))
    return summary


def write_workbook(rows: Iterable[tuple[str, float | None, int]], output_xlsx: str | Path) -> None:
    output_path = Path(output_xlsx)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    wb = Workbook()
    ws = wb.active
    ws.title = "Summary"
    ws.append(["Model", "Average", "ValidCount"])
    for model, average, count in rows:
        ws.append([model, average, count])
    wb.save(output_path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Summarize average Value by Model")
    parser.add_argument("--input", required=True, help="Input CSV path")
    parser.add_argument("--output", required=True, help="Output XLSX path")
    args = parser.parse_args(argv)

    rows = build_summary(args.input)
    write_workbook(rows, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
