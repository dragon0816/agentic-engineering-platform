# coverage.py `compute`, moved into the pack: the coverage matrix as an analysis
# (BI_ANALYSIS_DASHBOARD.md §4.3). Rows are the schema's market segments (`segment`) x
# technology areas (`tech_areas`), in the schema's order; every card is counted (all
# domains, sample cards too), in each of its cells. A card value names an entry by its
# value, label or an alias, compared loosely.
import re

SCHEMA_VALUES: dict[str, Any] = {}  # the schema's allowed values, filled on import
SEGMENT_FIELD = "segment"
AREA_FIELD = "tech_areas"
EMPTY_SHOWN = 5
EMPTY_CELL: dict[str, Any] = {"cards": 0, "filled": 0, "sourced": 0, "newest": None}


def _loose(text: Any) -> str:
    return re.sub(r"[\s_\-　()（）:：/／.]", "", str(text)).lower()


def _resolver(entries: list[list[str]]) -> dict[str, str]:
    return {_loose(name): entry[0] for entry in entries for name in entry}


def _placed(value: Any, names: dict[str, str]) -> list[str]:
    found: list[str] = []
    for part in value if isinstance(value, list) else [value]:
        hit = names.get(_loose(part)) if part not in (None, "") else None
        if hit is not None and hit not in found:
            found.append(hit)
    return found


def coverage() -> dict[str, Any]:
    allowed = SCHEMA_VALUES.get("allowed", {})
    own = SCHEMA_VALUES.get("fields", {})
    segments, areas = allowed.get(SEGMENT_FIELD, []), allowed.get(AREA_FIELD, [])
    seg_names, area_names = _resolver(segments), _resolver(areas)
    fact = {(r["card_id"], r["field"]) for r in query(
        "SELECT DISTINCT card_id, field FROM evidence WHERE basis = 'fact'")}  # fmt: skip
    values: dict[str, dict[str, dict[str, Any]]] = {}
    for row in query("SELECT card_id, field, value, ref FROM fields"):
        value = None if row["value"] is None else json.loads(row["value"])
        values.setdefault(row["card_id"], {})[row["field"]] = {"value": value, "ref": row["ref"]}
    cells: dict[tuple[str, str], dict[str, Any]] = {}
    for card in query("SELECT id, entity_type, updated FROM cards ORDER BY rowid"):
        kind = card["entity_type"]
        fields = values.get(card["id"], {})
        if kind in own:
            fields = {n: v for n, v in fields.items() if n in own[kind]}
        segs = _placed((fields.get(SEGMENT_FIELD) or {}).get("value"), seg_names)
        hits = _placed((fields.get(AREA_FIELD) or {}).get("value"), area_names)
        names = own.get(kind, [])
        filled = [n for n in names if (fields.get(n) or {}).get("value") not in (None, "", [])]
        sourced = [n for n in filled if fields[n].get("ref") or (card["id"], n) in fact]
        empty = [n for n in names if n not in filled and n not in (SEGMENT_FIELD, AREA_FIELD)]
        for seg in segs:
            for area in hits:
                cell = cells.setdefault((seg, area), dict(EMPTY_CELL, types={}, empty={}))
                cell["cards"] += 1
                cell["types"][kind] = cell["types"].get(kind, 0) + 1
                cell["filled"] += len(filled)
                cell["sourced"] += len(sourced)
                if cell["newest"] is None or card["updated"] > cell["newest"]:
                    cell["newest"] = card["updated"]
                for name in empty:
                    cell["empty"][f"{kind}.{name}"] = cell["empty"].get(f"{kind}.{name}", 0) + 1
    rows: list[list[Any]] = []
    for seg in segments:
        for area in areas:
            found = cells.get((seg[0], area[0]))
            if found is None:
                rows.append([seg[0], area[0], 0, "", None, None, ""])
                continue
            top = sorted(found["empty"].items(), key=lambda kv: (-kv[1], kv[0]))[:EMPTY_SHOWN]
            share = round(found["sourced"] / found["filled"], 3) if found["filled"] else None
            rows.append([
                seg[0], area[0], found["cards"],
                "、".join(f"{t} {n}" for t, n in sorted(found["types"].items())),
                share, found["newest"], "、".join(f"{k} {n}" for k, n in top),
            ])  # fmt: skip
    return {
        "columns": ["區段", "技術領域", "卡片數", "類型", "有來源比例", "最新更新",
                    "最常空白的欄位（前 5）"],
        "rows": rows,
    }  # fmt: skip


result = coverage()
