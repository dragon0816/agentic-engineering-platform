"""Generate the shipped BI schema `bi.schema/v1.1@5.0.0` from 4.0.0 (card model, 2026-11-03).

`docs/phases/BI_CARD_MODEL.md` §3.6. Additions only, so a dataset upgrades in place:

- `summary` on the 19 types without it (`Signal` and `VisitLog` keep theirs, required);
  `usage` and `scope` on all 21. A person's or a model's reading of the card, so
  `judgement`; text a model wrote carries `basis: inference` on its evidence.
- `last_confirmed` (derived: the later date stays) and `review_due` on all 21. Only
  the missing time fields: no generic `event_date`.
- `relation_types`, the relations a model or a person may register. A link field's
  own relation needs no entry: it is `has_<field>` unless the field names a
  `relation_type`. New types come through a schema version, never from a model.

`priority` stays as it was: not stored (decision 2026-11-03).

It is 5.0.0, not 4.1.0: a Session A version made from 4.0.0 is 4.1.0, as for 3.0.0
and 4.0.0.

    python scripts/build_bi_schema_v5.py

`tests/test_bi_card_model_shape.py` checks the committed JSON against this output.
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

from scripts import build_bi_schema_v4 as v4  # noqa: E402

OUT = BI / "aep_bi" / "cards" / "bi_schema_v5.json"
#: name, label, kind, class, aliases. In this order, after a type's own fields.
ADDED = (
    ("summary", "摘要", "str", "judgement", ["摘要", "summary"]),
    ("usage", "用途", "str", "judgement", ["用途", "usage"]),
    ("scope", "適用範圍", "str", "judgement", ["適用範圍", "範圍", "scope"]),
    ("last_confirmed", "最後確認日期", "date", "derived", ["最後確認", "last_confirmed"]),
    ("review_due", "複查期限", "date", "judgement", ["複查期限", "review_due"]),
)
RELATION_TYPES = [
    {
        "name": "requires_test",
        "label": "需要測試",
        "from": ["CustomerProduct", "Application"],
        "to": ["TestSolution"],
    },
]


def _field(name: str, label: str, kind: str, klass: str, aliases: list[str]) -> dict[str, Any]:
    return {
        "name": name,
        "label": label,
        "kind": kind,
        "class": klass,
        "enum": None,
        "aliases": aliases,
        "required": False,
        "default": None,
        "range": None,
        "link_to": [],
        "list": False,
    }


def build() -> dict[str, Any]:
    document = v4.build()
    document["version"] = "5.0.0"
    document["title"] = "BI Knowledge Schema 5.0 (4.0 with card summaries and relation types)"
    document["source"] = {**document["source"], "generator": "scripts/build_bi_schema_v5.py"}
    document["relation_types"] = RELATION_TYPES
    for entity in document["types"]:
        have = {f["name"] for f in entity["fields"]}
        entity["fields"].extend(_field(*item) for item in ADDED if item[0] not in have)
    return document


def main() -> None:
    text = json.dumps(build(), ensure_ascii=False, indent=1) + "\n"
    OUT.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {OUT.relative_to(REPO)}")


if __name__ == "__main__":
    main()
