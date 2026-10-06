#!/usr/bin/env python3
"""Summarize average Value by Model from a CSV into an Excel workbook."""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path

from openpyxl import Workbook


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize average Value by Model.")
    parser.add_argument("--input", required=True, help="Path to input CSV")
    parser.add_argument("--output", required=True, help="Path to output XLSX")
    return parser.parse_args()


def read_summary(input_path: str | Path) -> list[tuple[str, float | None, int]]:
    """Return (Model, Average, ValidCount) rows.

    Blank Value cells are ignored. Models are emitted in sorted order for stable
    output. If a model has no valid numeric Value cells, Average is left blank
    in the workbook and represented here as None.
    """
    totals: dict[str, float] = defaultdict(float)
    counts: dict[str, int] = defaultdict(int)
    models: set[str] = set()

    with open(input_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        required = {"Model", "Value"}
        missing = required.difference(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Input CSV missing required column(s): {', '.join(sorted(missing))}")

        for line_number, row in enumerate(reader, start=2):
            model = row.get("Model", "")
            models.add(model)
            raw_value = row.get("Value", "")
            if raw_value is None or str(raw_value).strip() == "":
                continue
            try:
                value = float(str(raw_value).strip())
            except ValueError as exc:
                raise ValueError(f"Invalid numeric Value at CSV line {line_number}: {raw_value!r}") from exc
            totals[model] += value
            counts[model] += 1

    rows: list[tuple[str, float | None, int]] = []
    for model in sorted(models):
        valid_count = counts[model]
        average = totals[model] / valid_count if valid_count else None
        rows.append((model, average, valid_count))
    return rows


def write_workbook(rows: list[tuple[str, float | None, int]], output_path: str | Path) -> None:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    wb = Workbook()
    ws = wb.active
    ws.title = "Summary"
    ws.append(["Model", "Average", "ValidCount"])
    for model, average, valid_count in rows:
        ws.append([model, average, valid_count])
    wb.save(output_path)


def main() -> None:
    args = parse_args()
    rows = read_summary(args.input)
    write_workbook(rows, args.output)


if __name__ == "__main__":
    main()
