"""Coverage of a BI knowledge base by market segment and technology area
(`docs/phases/BI_VAULT.md` §6.2, owner chart of 2026-10-28).

A matrix (`aep.bi.coverage_matrix/v1`) names markets with their segments
(the chart's columns, some marked priority) and technology areas (its rows),
and the two card fields that place a card in them (`segments`, `tech_areas`
by default). Coverage is read-only and computed from the cards as they are
now: for every segment × area cell, how many cards, of which types, which
share of their filled fields has a source (a cell or line the value came
from, or fact evidence), the newest update, and which fields are still
empty. A card with several segments or areas counts in each of its cells;
cards with no segment or no area are counted apart, never guessed into one.

The matrix comes from the vault's `vault.json` `coverage` block for a vault,
else the dataset's `coverage.json`, else the shipped `coverage_matrix.json`
(the owner's chart; its segment ids are the vault's default folders).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from capabilities.bi_cards.schema import Registry, norm_key
from capabilities.bi_cards.service import current_fields
from capabilities.bi_cards.store import BiStore, BiStoreError, dataset_dir, vault_of

MATRIX_FORMAT = "aep.bi.coverage_matrix/v1"
SHIPPED = Path(__file__).with_name("coverage_matrix.json")
DATASET_FILE = "coverage.json"
#: How many of a cell's most often empty fields are listed.
EMPTY_SHOWN = 5
#: How many of a cell's cards are named (to open them from the matrix).
CARDS_SHOWN = 200


def _invalid(message: str) -> BiStoreError:
    return BiStoreError("coverage_matrix_invalid", message)


def _ids(items: Any, what: str) -> list[dict[str, Any]]:
    if not isinstance(items, list) or not items:
        raise _invalid(f"{what} 必須是非空的清單")
    seen: set[str] = set()
    out = []
    for item in items:
        if not isinstance(item, dict) or not str(item.get("id") or "").strip():
            raise _invalid(f"{what} 的每一項都要有 id")
        key = str(item["id"]).strip()
        if key in seen:
            raise _invalid(f"{what} 的 id「{key}」重複")
        seen.add(key)
        out.append({**item, "id": key, "label": str(item.get("label") or key)})
    return out


def validate(document: Any) -> dict[str, Any]:
    """A matrix document checked and normalised; raises `coverage_matrix_invalid`."""
    if not isinstance(document, dict):
        raise _invalid("矩陣必須是 JSON 物件")
    if document.get("format") not in (None, MATRIX_FORMAT):
        raise _invalid(f"format 必須是 {MATRIX_FORMAT}")
    markets = _ids(document.get("markets"), "markets")
    segment_ids: set[str] = set()
    for market in markets:
        market["segments"] = _ids(market.get("segments"), f"市場「{market['id']}」的 segments")
        for segment in market["segments"]:
            if segment["id"] in segment_ids:
                raise _invalid(f"segment「{segment['id']}」出現在兩個市場")
            segment_ids.add(segment["id"])
            segment["priority"] = bool(segment.get("priority"))
    return {
        "format": MATRIX_FORMAT,
        "title": str(document.get("title") or ""),
        "segment_field": str(document.get("segment_field") or "segments"),
        "area_field": str(document.get("area_field") or "tech_areas"),
        "markets": markets,
        "areas": _ids(document.get("areas"), "areas"),
    }


def matrix_for(workspace: Path, dataset: str) -> tuple[dict[str, Any], str]:
    """The dataset's matrix and where it came from (`vault`, `dataset` or `shipped`)."""
    vault_id = vault_of(workspace, dataset)
    if vault_id is not None:
        from capabilities.bi_cards import vault

        entry = vault.registry_entry(workspace, vault_id) or {}
        try:
            block = vault.read_vault_json(Path(str(entry.get("path")))).get("coverage")
        except BiStoreError:
            block = None  # the folder is not reachable now: fall back like a dataset
        if isinstance(block, dict):
            return validate(block), "vault"
    own = dataset_dir(workspace, dataset) / DATASET_FILE
    if own.is_file():
        return validate(json.loads(own.read_text(encoding="utf-8"))), "dataset"
    return validate(json.loads(SHIPPED.read_text(encoding="utf-8"))), "shipped"


def _resolver(entries: list[dict[str, Any]]) -> dict[str, str]:
    """Card values match an entry by id or label, loosely (`norm_key`)."""
    names: dict[str, str] = {}
    for entry in entries:
        for name in (entry["id"], entry["label"], *entry.get("aliases", ())):
            names[norm_key(name)] = entry["id"]
    return names


def _placed(value: Any, names: dict[str, str]) -> tuple[list[str], list[str]]:
    """The entries a field value names, and the parts that name none."""
    parts = value if isinstance(value, list) else [value]
    found: list[str] = []
    unknown: list[str] = []
    for part in parts:
        if part in (None, ""):
            continue
        hit = names.get(norm_key(part))
        if hit is None:
            unknown.append(str(part))
        elif hit not in found:
            found.append(hit)
    return found, unknown


def _filled(item: dict[str, Any] | None) -> bool:
    if item is None:
        return False
    value = item.get("value")
    return value not in (None, "", [])


def compute(
    store: BiStore, reg: Registry, matrix: dict[str, Any], *, types: list[str] | None = None
) -> dict[str, Any]:
    segments = [s for m in matrix["markets"] for s in m["segments"]]
    seg_names, area_names = _resolver(segments), _resolver(matrix["areas"])
    seg_field, area_field = matrix["segment_field"], matrix["area_field"]
    fact = store.fact_evidence()
    cells: dict[tuple[str, str], dict[str, Any]] = {}
    totals = {"cards": 0, "no_segment": 0, "no_area": 0}
    unknown: dict[str, int] = {}
    everything = store.all_fields()
    for card in store.card_rows():
        if types and card["entity_type"] not in types:
            continue
        entity = reg.types.get(card["entity_type"])
        fields = current_fields(reg, card["entity_type"], everything.get(card["id"], {}))
        totals["cards"] += 1
        segs, bad_segs = _placed((fields.get(seg_field) or {}).get("value"), seg_names)
        areas, bad_areas = _placed((fields.get(area_field) or {}).get("value"), area_names)
        for value in (*bad_segs, *bad_areas):
            unknown[value] = unknown.get(value, 0) + 1
        if not segs:
            totals["no_segment"] += 1
        if not areas:
            totals["no_area"] += 1
        names = [f.name for f in entity.fields if f.klass != "derived"] if entity else []
        filled = [n for n in names if _filled(fields.get(n))]
        sourced = [n for n in filled if (fields[n].get("ref") or (card["id"], n) in fact)]
        empty = [n for n in names if n not in filled and n not in (seg_field, area_field)]
        for seg in segs:
            for area in areas:
                cell = cells.setdefault(
                    (seg, area),
                    {
                        "cards": 0,
                        "types": {},
                        "filled": 0,
                        "sourced": 0,
                        "newest": None,
                        "empty": {},
                        "ids": [],
                    },
                )
                cell["cards"] += 1
                if len(cell["ids"]) < CARDS_SHOWN:
                    cell["ids"].append({"id": card["id"], "name": card["name"],
                                        "type": card["entity_type"]})  # fmt: skip
                cell["types"][card["entity_type"]] = cell["types"].get(card["entity_type"], 0) + 1
                cell["filled"] += len(filled)
                cell["sourced"] += len(sourced)
                if cell["newest"] is None or card["updated"] > cell["newest"]:
                    cell["newest"] = card["updated"]
                for name in empty:
                    key = f"{card['entity_type']}.{name}"
                    cell["empty"][key] = cell["empty"].get(key, 0) + 1
    rows = []
    for seg in segments:
        for area in matrix["areas"]:
            found = cells.get((seg["id"], area["id"]))
            if found is None:
                rows.append(
                    {
                        "segment": seg["id"],
                        "area": area["id"],
                        "cards": 0,
                        "types": {},
                        "sourced_share": None,
                        "newest": None,
                        "empty": [],
                        "card_list": [],
                    }
                )
                continue
            top = sorted(found["empty"].items(), key=lambda kv: (-kv[1], kv[0]))[:EMPTY_SHOWN]
            rows.append(
                {
                    "segment": seg["id"],
                    "area": area["id"],
                    "cards": found["cards"],
                    "types": dict(sorted(found["types"].items())),
                    "sourced_share": round(found["sourced"] / found["filled"], 3)
                    if found["filled"]
                    else None,
                    "newest": found["newest"],
                    "empty": [{"field": k, "cards": n} for k, n in top],
                    "card_list": found["ids"],
                }
            )
    missing = [
        name
        for name in (seg_field, area_field)
        if not any(t.get(name) is not None for t in reg.types.values())
    ]
    return {
        "matrix": matrix,
        "cells": rows,
        "totals": totals,
        "unknown_values": dict(sorted(unknown.items())),
        # The schema has no field to place cards with: every card is unplaced
        # until a schema version adds it (BI_VAULT.md §6.2).
        "schema_missing_fields": missing,
    }
