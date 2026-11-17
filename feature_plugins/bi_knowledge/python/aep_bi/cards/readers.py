"""Read a BI source into tables: Markdown reports, Excel workbooks, CSV/TSV.

BI ingest phase 3, the rule path (`docs/phases/BI_INGEST.md` §6, design of
`docs/phases/BI_CASE_B.md` §3; owner 2026-10-27). One report often holds
several tables (a supply-chain study with a chipset table, an RF table and a
cert-lab table); a recipe's passes pick tables by index, by a column they
contain or by sheet name, so every table keeps its place in the file.

Each table is `{"index", "title", "columns", "rows": [{"row", "cells"}],
"locator"}`. `row` is where the row is in the source, so evidence can point
at it: the line number of a Markdown row (`locator: "line"`), the sheet row
of an Excel row (`"sheet"`), or the CSV line (`"row"`, header = 1). Cell
values are text; an Excel date becomes ISO `YYYY-MM-DD`.

Markdown parsing follows the fixture's `bi_ingest.py` (`parse_md_tables`,
`clean_md`): pipe blocks whose second line is a separator, links reduced to
their text, `<br>` to 「; 」, bold and code marks removed. It is
reimplemented here, never imported.

Since BI vault phase V2 (`docs/phases/BI_VAULT.md` §5) a run reads the
source's current Markdown revision (`convert.py`). A CSV/TSV or Excel source
is read from its converted tables in the exact mode (`markdown_tables(...,
exact=True)`): cells are split on unescaped pipes and unescaped as
`convert.table_cell` wrote them, so a cell reads back as the file had it,
and `row` is the line in that revision.
"""

from __future__ import annotations

import csv
import datetime as dt
import io
import re
from pathlib import PurePath
from typing import Any

from aep_bi.cards.store import BiStoreError

MARKDOWN = (".md", ".markdown")
EXCEL = (".xlsx", ".xlsm")
DELIMITED = (".csv", ".tsv")
SUPPORTED = (*MARKDOWN, *EXCEL, *DELIMITED)

_SEPARATOR_CELL = re.compile(r":?-+:?")
_HEADING = re.compile(r"^\s{0,3}(#{1,6})\s+(.*?)\s*#*\s*$")
_BREAK = re.compile(r"<br\s*/?>", re.I)


def suffix(name: str) -> str:
    return PurePath(name).suffix.lower()


def readable(name: str) -> bool:
    return suffix(name) in SUPPORTED


def read_tables(name: str, data: bytes) -> list[dict[str, Any]]:
    """Every table in the source, numbered from 0 in file order."""
    kind = suffix(name)
    if kind in MARKDOWN:
        return markdown_tables(decode(data), PurePath(name).name)
    if kind in EXCEL:
        return excel_tables(data)
    if kind in DELIMITED:
        return [delimited_table(name, decode(data), "\t" if kind == ".tsv" else ",")]
    raise BiStoreError(
        "file_type_unsupported", "規則轉換只能讀 Markdown（.md）、Excel（.xlsx）或 CSV/TSV"
    )


def decode(data: bytes) -> str:
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise BiStoreError("source_decode_failed", "來源不是 UTF-8 文字，請另存為 UTF-8") from error


# -- Markdown ----------------------------------------------------------------


def clean_md(text: str) -> str:
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"<br\s*/?>", "; ", text, flags=re.I)
    return text.replace("**", "").replace("`", "").strip()


def _cells(line: str) -> list[str]:
    return [clean_md(c) for c in line.strip().strip("|").split("|")]


def split_row(line: str) -> list[str]:
    """The cells of a converted table row, exactly: a backslash before a pipe
    or a backslash escapes it, and `<br>` is a line break
    (`convert.table_cell` writes them)."""
    text = line.strip()
    if text.startswith("|"):
        text = text[1:]
    cells: list[str] = []
    current: list[str] = []
    index = 0
    while index < len(text):
        char = text[index]
        if char == "\\" and index + 1 < len(text) and text[index + 1] in ("\\", "|"):
            current.append(text[index + 1])
            index += 2
            continue
        if char == "|":
            cells.append("".join(current))
            current = []
        else:
            current.append(char)
        index += 1
    if "".join(current).strip():
        cells.append("".join(current))
    return [_BREAK.sub("\n", c).strip() for c in cells]


def markdown_tables(text: str, name: str = "", *, exact: bool = False) -> list[dict[str, Any]]:
    """Pipe tables with the nearest heading above each as its title (the
    file name when no heading comes before it). `exact` reads a converted
    table (`split_row`) instead of cleaning a report's cells."""
    cells_of = split_row if exact else _cells
    blocks: list[tuple[str, list[tuple[int, str]]]] = []
    heading = name
    current: list[tuple[int, str]] = []
    current_heading = ""
    for number, line in enumerate(text.splitlines(), start=1):
        if line.strip().startswith("|"):
            if not current:
                current_heading = heading
            current.append((number, line.strip()))
            continue
        if current:
            blocks.append((current_heading, current))
            current = []
        found = _HEADING.match(line)
        if found:
            heading = found.group(2).strip() if exact else clean_md(found.group(2))
    if current:
        blocks.append((current_heading, current))
    tables: list[dict[str, Any]] = []
    for title, lines in blocks:
        if len(lines) < 2:
            continue
        separator = cells_of(lines[1][1])
        if not all(_SEPARATOR_CELL.fullmatch(c.strip()) for c in separator if c.strip()):
            continue
        columns = cells_of(lines[0][1])
        rows = []
        for number, line in lines[2:]:
            values = cells_of(line)
            rows.append(
                {
                    "row": number,
                    "cells": {
                        column: (values[i] if i < len(values) else "")
                        for i, column in enumerate(columns)
                    },
                }
            )
        tables.append(
            {
                "index": len(tables),
                "title": title,
                "columns": columns,
                "rows": rows,
                "locator": "line",
            }
        )
    return tables


# -- Excel -------------------------------------------------------------------


def _excel_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, dt.datetime | dt.date):
        return value.isoformat()[:10]
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def excel_tables(data: bytes) -> list[dict[str, Any]]:
    """One sheet = one table; its header is the first non-empty row."""
    try:
        import openpyxl
    except ImportError as error:  # pragma: no cover - openpyxl ships with `office`
        raise BiStoreError(
            "file_type_unsupported", "這台電腦沒有安裝 Excel 讀取元件（openpyxl）"
        ) from error
    try:
        book = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    except Exception as error:  # openpyxl raises several unrelated types
        raise BiStoreError("source_parse_failed", "無法讀取這個 Excel 檔") from error
    tables: list[dict[str, Any]] = []
    try:
        for sheet in book.worksheets:
            columns: list[str] | None = None
            rows: list[dict[str, Any]] = []
            for number, values in enumerate(sheet.iter_rows(values_only=True), start=1):
                texts = [_excel_text(v) for v in values]
                if columns is None:
                    if any(texts):
                        columns = texts
                    continue
                if not any(texts):
                    continue
                rows.append(
                    {
                        "row": number,
                        "cells": {
                            column: (texts[i] if i < len(texts) else "")
                            for i, column in enumerate(columns)
                            if column
                        },
                    }
                )
            tables.append(
                {
                    "index": len(tables),
                    "title": sheet.title,
                    "columns": [c for c in columns or [] if c],
                    "rows": rows,
                    "locator": "sheet",
                }
            )
    finally:
        book.close()
    return tables


# -- CSV / TSV ---------------------------------------------------------------


def delimited_table(name: str, text: str, delimiter: str) -> dict[str, Any]:
    reader = csv.reader(io.StringIO(text.lstrip("﻿")), delimiter=delimiter)
    columns: list[str] = []
    rows: list[dict[str, Any]] = []
    for number, values in enumerate(reader, start=1):
        if number == 1:
            columns = [v.strip() for v in values]
            continue
        if not any(v.strip() for v in values):
            continue
        rows.append(
            {
                "row": number,
                "cells": {
                    column: (values[i] if i < len(values) else "")
                    for i, column in enumerate(columns)
                },
            }
        )
    return {
        "index": 0,
        "title": PurePath(name).name,
        "columns": columns,
        "rows": rows,
        "locator": "row",
    }
