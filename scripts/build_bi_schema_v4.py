"""Generate the shipped BI schema `bi.schema/v1.1@4.0.0` from 3.0.0 (owner 2026-11-03).

`Application.domain`, `Trend.domain` and `CustomerProduct.domain` become lists, so a
card can belong to several domains. The allowed values stay, so the default pack's
`values_from: Application.domain` keeps its list. The default `wireless` goes, as on
`Node.domain` since 2.0.0: readers already take a missing domain as wireless, and a
default on a list would store a scalar. An enum becoming a list is a widening
(`schema.WIDENINGS`), so a dataset upgrades in place, each value a one-item list.

It is 4.0.0, not 3.1.0: a Session A version made from 3.0.0 is 3.1.0
(`schema_versions._next_version`), as for 3.0.0 (decision 2026-11-01, D1).

    python scripts/build_bi_schema_v4.py

`tests/test_bi_schema_v4.py` checks the committed JSON against this output.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
BI = REPO / "feature_plugins" / "bi_knowledge" / "python"  # the BI Knowledge plugin
for entry in (REPO, REPO / "src", BI):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from typing import Any  # noqa: E402

from scripts import build_bi_schema_v3 as v3  # noqa: E402

OUT = BI / "aep_bi" / "cards" / "bi_schema_v4.json"
#: The types whose `domain` becomes a list.
WIDENED = ("Application", "Trend", "CustomerProduct")


def build() -> dict[str, Any]:
    document = v3.build()
    document["version"] = "4.0.0"
    document["title"] = "BI Knowledge Schema 4.0 (3.0 with a list of domains on three more types)"
    document["source"] = {**document["source"], "generator": "scripts/build_bi_schema_v4.py"}
    for entity in document["types"]:
        if entity["name"] not in WIDENED:
            continue
        field = next(f for f in entity["fields"] if f["name"] == "domain")
        field.update(kind="list", list=True, default=None)
    return document


def main() -> None:
    text = json.dumps(build(), ensure_ascii=False, indent=1) + "\n"
    OUT.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {OUT.relative_to(REPO)}")


if __name__ == "__main__":
    main()
