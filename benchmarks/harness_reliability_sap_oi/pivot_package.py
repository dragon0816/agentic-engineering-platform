"""Missing-feature adapter: package a genuine worksheet-source OOXML PivotTable.

Sheets/formulas/styles are authored by Artifact Tool. This only adds pivot parts.
See Microsoft Working with PivotTables; no macros, external links or new runtime.
"""

from collections.abc import Sequence
from pathlib import Path
from typing import Any, cast
from xml.etree import ElementTree as ET
from zipfile import ZIP_DEFLATED, ZipFile

S = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
P = "http://schemas.openxmlformats.org/package/2006/relationships"
C = "http://schemas.openxmlformats.org/package/2006/content-types"
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


def element(tag: str, **attributes: Any) -> ET.Element:
    return ET.Element(f"{{{S}}}{tag}", {k: str(v) for k, v in attributes.items()})


def child(parent: ET.Element, tag: str, **attributes: Any) -> ET.Element:
    item = element(tag, **attributes)
    parent.append(item)
    return item


def xml(node: ET.Element) -> bytes:
    return cast(bytes, ET.tostring(node, encoding="utf-8", xml_declaration=True))


def rels(target: str, kind: str) -> bytes:
    root = ET.Element(f"{{{P}}}Relationships")
    ET.SubElement(root, f"{{{P}}}Relationship", Id="rId1", Type=f"{R}/{kind}", Target=target)
    return xml(root)


def add_pivot(path: Path, records: Sequence[dict[str, Any]]) -> None:
    with ZipFile(path) as source:
        parts = {name: source.read(name) for name in source.namelist()}
    sales = sorted({str(row["sales"]) for row in records})
    months = sorted({str(row["month"]) for row in records})
    values = [
        [
            r["document"],
            r["line"],
            r["created_at"].replace(" ", "T"),
            r["sales"],
            r["customer"],
            r["status"],
            r["currency"],
            r["amount"],
            r["fx"],
            r["month"],
            round(r["amount"] * r["fx"], 2),
        ]
        for r in records
    ]
    cache = element(
        "pivotCacheDefinition",
        recordCount=len(records),
        saveData="1",
        refreshOnLoad="0",
        createdVersion="6",
        refreshedVersion="6",
        minRefreshableVersion="3",
    )
    cache.set(f"{{{R}}}id", "rId1")
    child(
        child(cache, "cacheSource", type="worksheet"),
        "worksheetSource",
        ref=f"A1:K{len(records) + 1}",
        sheet="OI Data",
    )
    fields = child(cache, "cacheFields", count=len(HEADERS))
    for i, header in enumerate(HEADERS):
        field = child(fields, "cacheField", name=header, numFmtId="0")
        if i in (3, 9):
            items = sales if i == 3 else months
            shared = child(
                field,
                "sharedItems",
                count=len(items),
                containsString="1",
                containsNumber="0",
                containsBlank="0",
                containsSemiMixedTypes="0",
            )
            for value in items:
                child(shared, "s", v=value)
    cached = element("pivotCacheRecords", count=len(records))
    for row in values:
        record = child(cached, "r")
        for i, value in enumerate(row):
            if i in (3, 9):
                child(record, "x", v=(sales if i == 3 else months).index(str(value)))
            else:
                child(
                    record,
                    "n" if isinstance(value, (float, int)) else "d" if i == 2 else "s",
                    v=value,
                )
    pivot = element(
        "pivotTableDefinition",
        name="OIBySalesMonth",
        cacheId="1",
        dataCaption="OI (TWD)",
        rowHeaderCaption="Sales",
        colHeaderCaption="Month",
        rowGrandTotals="1",
        colGrandTotals="1",
        compact="0",
        compactData="0",
        outline="0",
        outlineData="0",
        showHeaders="1",
        showDrill="1",
        createdVersion="6",
        updatedVersion="6",
        minRefreshableVersion="3",
        useAutoFormatting="1",
        applyNumberFormats="1",
    )
    child(pivot, "location", ref="B6:E10", firstHeaderRow="0", firstDataRow="1", firstDataCol="1")
    pivot_fields = child(pivot, "pivotFields", count=len(HEADERS))
    for i in range(len(HEADERS)):
        attributes: dict[str, str] = {"showAll": "0", "defaultSubtotal": "0"}
        if i in (3, 9):
            attributes["axis"] = "axisRow" if i == 3 else "axisCol"
        if i == 10:
            attributes["dataField"] = "1"
        field = child(pivot_fields, "pivotField", **attributes)
        if i in (3, 9):
            unique = sales if i == 3 else months
            pivot_items = child(field, "items", count=len(unique) + 1)
            for index in range(len(unique)):
                child(pivot_items, "item", x=index)
            child(pivot_items, "item", t="default")
    child(child(pivot, "rowFields", count="1"), "field", x="3")
    row_items = child(pivot, "rowItems", count=len(sales) + 1)
    for i in range(len(sales)):
        child(child(row_items, "i"), "x", v=i)
    child(child(row_items, "i", t="grand"), "x", v="0")
    child(child(pivot, "colFields", count="1"), "field", x="9")
    col_items = child(pivot, "colItems", count=len(months) + 1)
    for i in range(len(months)):
        child(child(col_items, "i"), "x", v=i)
    child(child(col_items, "i", t="grand"), "x", v="0")
    child(
        child(pivot, "dataFields", count="1"),
        "dataField",
        name="Sum of OI TWD",
        fld="10",
        subtotal="sum",
        numFmtId="4",
    )
    child(
        pivot,
        "pivotTableStyleInfo",
        name="PivotStyleMedium9",
        showRowHeaders="1",
        showColHeaders="1",
        showRowStripes="0",
        showColStripes="0",
        showLastColumn="1",
    )
    parts["xl/pivotTables/pivotTable1.xml"] = xml(pivot)
    parts["xl/pivotCache/pivotCacheDefinition1.xml"] = xml(cache)
    parts["xl/pivotCache/pivotCacheRecords1.xml"] = xml(cached)
    parts["xl/pivotTables/_rels/pivotTable1.xml.rels"] = rels(
        "../pivotCache/pivotCacheDefinition1.xml", "pivotCacheDefinition"
    )
    parts["xl/pivotCache/_rels/pivotCacheDefinition1.xml.rels"] = rels(
        "pivotCacheRecords1.xml", "pivotCacheRecords"
    )
    workbook = ET.fromstring(parts["xl/workbook.xml"])
    caches = child(workbook, "pivotCaches")
    entry = child(caches, "pivotCache", cacheId="1")
    entry.set(f"{{{R}}}id", "rIdOIPivotCache")
    parts["xl/workbook.xml"] = xml(workbook)
    relationships = ET.fromstring(parts["xl/_rels/workbook.xml.rels"])
    ET.SubElement(
        relationships,
        f"{{{P}}}Relationship",
        Id="rIdOIPivotCache",
        Type=f"{R}/pivotCacheDefinition",
        Target="pivotCache/pivotCacheDefinition1.xml",
    )
    parts["xl/_rels/workbook.xml.rels"] = xml(relationships)
    relationships = ET.fromstring(
        parts.get("xl/worksheets/_rels/sheet1.xml.rels", f'<Relationships xmlns="{P}"/>'.encode())
    )
    ET.SubElement(
        relationships,
        f"{{{P}}}Relationship",
        Id="rIdOIPivotTable",
        Type=f"{R}/pivotTable",
        Target="../pivotTables/pivotTable1.xml",
    )
    parts["xl/worksheets/_rels/sheet1.xml.rels"] = xml(relationships)
    content = ET.fromstring(parts["[Content_Types].xml"])
    for name, kind in (
        ("xl/pivotTables/pivotTable1.xml", "pivotTable"),
        ("xl/pivotCache/pivotCacheDefinition1.xml", "pivotCacheDefinition"),
        ("xl/pivotCache/pivotCacheRecords1.xml", "pivotCacheRecords"),
    ):
        ET.SubElement(
            content,
            f"{{{C}}}Override",
            PartName=f"/{name}",
            ContentType=f"application/vnd.openxmlformats-officedocument.spreadsheetml.{kind}+xml",
        )
    parts["[Content_Types].xml"] = xml(content)
    temporary = path.with_suffix(".pivot-tmp")
    with ZipFile(temporary, "w", ZIP_DEFLATED) as output:
        for name, payload in parts.items():
            output.writestr(name, payload)
    temporary.replace(path)
