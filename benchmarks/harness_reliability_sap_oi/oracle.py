"""Independent fixture oracle, never imported by the model-generated program."""

import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, cast
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from openpyxl import load_workbook

HERE = Path(__file__).resolve().parent
NS = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
HEADERS = (
    "OI Document",
    "Line",
    "CreatedAt",
    "Sales",
    "Customer",
    "Status",
    "Currency",
    "OI Amount",
    "FX to TWD",
    "Month",
    "OI TWD",
)


def gold() -> dict[str, Any]:
    return cast(
        dict[str, Any], json.loads((HERE / "fixtures/expected.json").read_text(encoding="utf-8"))
    )


def require(condition: bool, code: str) -> None:
    if not condition:
        raise ValueError(code)


def verify_records(records: list[dict[str, Any]]) -> None:
    expected = gold()
    require(len(records) == expected["included_rows"], "normalized_row_count")
    source = json.loads((HERE / "fixtures/records.json").read_text(encoding="utf-8"))
    originals = {
        r["document"]: r for r in source if r["document"] in expected["included_documents"]
    }
    seen: set[str] = set()
    for row in records:
        doc = row["document"]
        require(doc in originals and doc not in seen, "normalized_keys")
        seen.add(doc)
        original = originals[doc]
        for field in ("line", "created_at", "sales", "customer", "status", "currency"):
            require(row[field] == original[field], f"normalized_{field}")
        require(type(row["amount"]) in (int, float), "amount_not_numeric")
        require(Decimal(str(row["amount"])) == Decimal(original["amount"]), "amount_mismatch")
        require(row["fx"] == (32 if original["currency"] == "USD" else 1), "fx_mismatch")
        require(row["month"] == original["created_at"][:7], "month_mismatch")
    require(seen == set(expected["included_documents"]), "normalized_missing_keys")


def verify_workbook(path: Path) -> dict[str, Any]:
    expected = gold()
    formulas = load_workbook(path, data_only=False)
    values = load_workbook(path, data_only=True)
    try:
        require(formulas.sheetnames == ["OI Pivot", "OI Data"], "worksheet_names")
        data, cached = formulas["OI Data"], values["OI Data"]
        require(tuple(cell.value for cell in data[1]) == HEADERS, "detail_headers")
        records: list[dict[str, Any]] = []
        total = Decimal(0)
        for index in range(2, 14):
            row = [data.cell(index, col).value for col in range(1, 12)]
            require(isinstance(row[2], datetime), "timestamp_not_typed")
            records.append(
                {
                    "document": row[0],
                    "line": row[1],
                    "created_at": cast(datetime, row[2]).strftime("%Y-%m-%d %H:%M:%S"),
                    "sales": row[3],
                    "customer": row[4],
                    "status": row[5],
                    "currency": row[6],
                    "amount": row[7],
                    "fx": row[8],
                    "month": row[9],
                }
            )
            require(row[10] == f"=H{index}*I{index}", "conversion_formula")
            amount = Decimal(str(row[7])) * Decimal(str(row[8]))
            require(Decimal(str(cached.cell(index, 11).value)) == amount, "formula_cached_value")
            total += amount
        verify_records(records)
        require(total == Decimal(expected["grand_total_twd"]), "detail_total")
        pivot = values["OI Pivot"]
        require(
            [pivot.cell(6, col).value for col in range(2, 6)]
            == ["Sales", *expected["months"], "Grand Total"],
            "pivot_headers",
        )
        for index, name in enumerate([*expected["sales"], "Grand Total"], start=7):
            require(pivot.cell(index, 2).value == name, "pivot_sales")
            require(
                [pivot.cell(index, col).value for col in range(3, 6)]
                == expected["pivot_twd"][name],
                "pivot_totals",
            )
        native = cast(Any, formulas["OI Pivot"])._pivots
        require(len(native) == 1 and native[0].name == "OIBySalesMonth", "native_pivot_missing")
        table = native[0]
        require(table.rowFields[0].x == 3 and table.colFields[0].x == 9, "pivot_axes")
        require(
            table.dataFields[0].fld == 10 and table.dataFields[0].subtotal == "sum", "pivot_measure"
        )
        require(
            table.cache.cacheSource.worksheetSource.sheet == "OI Data"
            and table.cache.cacheSource.worksheetSource.ref == "A1:K13",
            "pivot_source",
        )
        require(table.cache.recordCount == 12, "pivot_record_count")
        with ZipFile(path) as archive:
            definition = ET.fromstring(archive.read("xl/pivotCache/pivotCacheDefinition1.xml"))
            fields = definition.findall("s:cacheFields/s:cacheField", NS)
            require([field.get("name") for field in fields] == list(HEADERS), "cache_headers")
            cache = ET.fromstring(archive.read("xl/pivotCache/pivotCacheRecords1.xml"))
            cache_rows = cache.findall("s:r", NS)
            require(len(cache_rows) == 12, "cache_row_count")
            cache_totals: dict[tuple[str, str], Decimal] = {}
            cache_keys: set[tuple[str, str]] = set()
            for cached_row, source_row in zip(cache_rows, records, strict=True):
                decoded: list[Any] = []
                for i, item in enumerate(cached_row):
                    value: Any = item.get("v")
                    if item.tag.endswith("}x"):
                        shared = fields[i].findall("s:sharedItems/s:s", NS)
                        value = shared[int(value)].get("v")
                    decoded.append(value)
                require(len(decoded) == 11, "cache_field_count")
                require(
                    decoded[0] == source_row["document"] and decoded[1] == source_row["line"],
                    "cache_source_keys",
                )
                require(
                    decoded[3] == source_row["sales"] and decoded[9] == source_row["month"],
                    "cache_dimensions",
                )
                require(
                    decoded[2] == source_row["created_at"].replace(" ", "T")
                    and decoded[4] == source_row["customer"]
                    and decoded[5] == source_row["status"]
                    and decoded[6] == source_row["currency"],
                    "cache_source_metadata",
                )
                require(
                    Decimal(decoded[7]) == Decimal(str(source_row["amount"]))
                    and Decimal(decoded[8]) == Decimal(str(source_row["fx"])),
                    "cache_source_values",
                )
                amount = Decimal(decoded[10])
                require(
                    amount == Decimal(str(source_row["amount"])) * Decimal(str(source_row["fx"])),
                    "cache_amount",
                )
                cache_keys.add((decoded[0], decoded[1]))
                key = (decoded[3], decoded[9])
                cache_totals[key] = cache_totals.get(key, Decimal(0)) + amount
            require(len(cache_keys) == 12, "cache_duplicate_keys")
            for sales in expected["sales"]:
                for index, month in enumerate(expected["months"]):
                    require(
                        cache_totals.get((sales, month), Decimal(0))
                        == Decimal(expected["pivot_twd"][sales][index]),
                        "cache_pivot_total",
                    )
        return {
            "passed": True,
            "detail_rows": 12,
            "grand_total_twd": int(total),
            "native_pivot_parsed": True,
            "cache_matches_source": True,
            "excel_desktop_refresh": "unverified_not_installed",
        }
    finally:
        formulas.close()
        values.close()
