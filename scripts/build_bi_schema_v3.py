"""Generate the shipped BI schema `bi.schema/v1.1@3.0.0` from 2.0.0 (BI D1).

`docs/phases/BI_ANALYSIS_DASHBOARD.md` §3 (retiring the domain configuration):
the technology areas and the value chains, until now in the domain
configuration (`aep.bi.domains/v1`), become schema fields with allowed values
and their labels as aliases:

- `tech_areas` (a list) on the types placed by `segment` (the coverage matrix is
  segment × technology area); allowed values = the shipped coverage matrix's
  areas (`scripts/bi_coverage_matrix.json`, the owner's chart, kept as input);
- `chain` (a list: a shared node is in several chains) on Node; allowed values =
  the AIDC chains of the manager's knowledge bases (CMP, PWR, THM);
- `aliases` (a list of other names) on every type named by `name`: matching by
  name reads the cards' aliases instead of the configuration's `name_aliases`
  (D2), so a pushed card brings its aliases.

3.0.0 adds fields only, so a 2.0.0 dataset or vault upgrades to it without moving
any value. It is 3.0.0, not the design's 2.1.0: a Session A version made from 2.0.0
is 2.1.0 (`schema_versions._next_version`), and a shipped 2.1.0 with other content
would make such a PC or vault refuse its schema (decision 2026-11-01, D1).

    python scripts/build_bi_schema_v3.py

`tests/test_bi_schema_v3.py` checks the committed JSON against this output.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
for path in (REPO, REPO / "src"):  # run as a script: neither is importable then
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from typing import Any  # noqa: E402

from scripts import build_bi_schema_v2 as v2  # noqa: E402

OUT = REPO / "src" / "capabilities" / "bi_cards" / "bi_schema_v3.json"
MATRIX = REPO / "scripts" / "bi_coverage_matrix.json"
#: The manager's AIDC chains (his chain sections A–A3: 運算鏈, 電力鏈, 散熱鏈).
CHAINS = (("CMP", "運算鏈"), ("PWR", "電力鏈"), ("THM", "散熱鏈"))


def _field(name: str, label: str, enum: list[str] | None, aliases: list[str]) -> dict[str, Any]:
    return {
        "name": name,
        "label": label,
        "kind": "list",
        "class": "sourced",
        "enum": enum,
        "aliases": aliases,
        "required": False,
        "default": None,
        "range": None,
        "link_to": [],
        "list": True,
    }


def _after(fields: list[dict[str, Any]], anchor: str, added: dict[str, Any]) -> None:
    """Insert `added` after field `anchor` (at the end when there is none)."""
    names = [f["name"] for f in fields]
    at = names.index(anchor) + 1 if anchor in names else len(fields)
    fields.insert(at, added)


def build() -> dict[str, Any]:
    document = v2.build()
    document["version"] = "3.0.0"
    document["title"] = (
        "BI Knowledge Schema 3.0 (2.0 plus technology areas, value chains and aliases; 2026-11-01)"
    )
    document["source"] = {**document["source"], "generator": "scripts/build_bi_schema_v3.py"}
    areas = json.loads(MATRIX.read_text(encoding="utf-8"))["areas"]
    area_ids = [a["id"] for a in areas]
    for entity in document["types"]:
        names = {f["name"] for f in entity["fields"]}
        if "segment" in names and "tech_areas" not in names:
            _after(
                entity["fields"],
                "segment",
                _field(
                    "tech_areas", "技術領域", area_ids, ["技術領域", "tech areas", "tech_areas"]
                ),
            )
        if entity["name"] == "Node" and "chain" not in names:
            _after(
                entity["fields"],
                "layer",
                _field("chain", "鏈別", [c for c, _ in CHAINS], ["鏈別", "鏈", "chain", "chains"]),
            )
        if entity["naming"] == ["name"] and "aliases" not in names:
            _after(
                entity["fields"],
                "name",
                _field("aliases", "別名", None, ["別名", "其他名稱", "aliases", "aka"]),
            )
    aliases = document["enum_aliases"]
    aliases["tech_areas"] = {a["label"]: a["id"] for a in areas}
    aliases["chain"] = {label: code for code, label in CHAINS}
    return document


def main() -> None:
    text = json.dumps(build(), ensure_ascii=False, indent=1) + "\n"
    OUT.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {OUT.relative_to(REPO)}")


if __name__ == "__main__":
    main()
