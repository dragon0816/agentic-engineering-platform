"""Generate the shipped BI schema `bi.schema/v1.1@2.0.0` from schema v8.

BI vault V9 (docs/phases/BI_VAULT.md §12): the owner's manager's schema v8
(`tests/fixtures/bi_schema_v8/bi_schema.py`, read with `ast`, never imported
or run) becomes the second shipped version of `bi.schema/v1.1`, a compatible
superset of 1.1.0 (2.0.0 so it never meets a local Session A version,
which are 1.x minor steps): nine more types, `segment` taking the owner's
market chart segments beside aerospace's own, `float` fields, allowed values on list
fields, and Node `domain` widened to a list.

    python scripts/build_bi_schema_v2.py

`tests/test_bi_schema_v2.py` checks the committed JSON against this output.
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

from capabilities.bi_cards.vault import SEGMENTS  # noqa: E402
from scripts import build_bi_schema_v1_1 as base  # noqa: E402

V8 = REPO / "tests" / "fixtures" / "bi_schema_v8" / "bi_schema.py"
OUT = REPO / "src" / "capabilities" / "bi_cards" / "bi_schema_v2.json"

TYPE_LABELS = {
    **base.TYPE_LABELS,
    "WinLoss": "輸贏分析",
    "RoadmapRequest": "產品需求",
    "Pitch": "簡報",
    "DemoScript": "展示腳本",
    "Battlecard": "對戰卡",
    "Contact": "聯絡人",
    "VisitLog": "拜訪紀錄",
    "SupplyLink": "供貨關係",
    "RevenueFact": "收入事實",
}
#: v1.1's targets plus the v6/v7 link fields; `Type.field` where one name
#: links differently per type.
LINK_TARGETS: dict[str, list[str]] = {
    **base.LINK_TARGETS,
    "opportunity": ["Opportunity"],
    "winner": ["Competitor", "Ecosystem", "Account"],
    "source_win_loss": ["WinLoss"],
    "source_opportunities": ["Opportunity"],
    "concepts": ["Concept"],
    "accounts": ["Account"],
    "competitor": ["Competitor"],
    "reports_to": ["Contact"],
    "contacts": ["Contact"],
    "supplier": ["Ecosystem", "Account"],
    "customer": ["Account", "Ecosystem"],
    "customer_products": ["CustomerProduct"],
    "company": ["Account", "Ecosystem", "Competitor"],
    "related_ecosystem": ["Ecosystem", "Account"],
    "RevenueFact.customer": ["Account", "Ecosystem"],
}
#: v1.1's judgement fields plus the v6/v7 assessments a person makes.
JUDGEMENT = {
    *base.JUDGEMENT,
    "Contact.relationship_status",
    "Contact.decision_role",
    "RoadmapRequest.impact",
    "Battlecard.our_advantages",
    "Battlecard.our_weaknesses",
    "SupplyLink.evidence_grade",
    "WinLoss.lessons",
}


def build() -> dict[str, Any]:
    document = base.build_from(
        V8,
        labels=TYPE_LABELS,
        links=LINK_TARGETS,
        judgement=JUDGEMENT,
        meta={
            "schema_id": "bi.schema/v1.1",
            "version": "2.0.0",
            "status": "poc-contract",
            "title": (
                "BI Knowledge Schema 2.0 "
                "(schema v8 of the market knowledge bases; owner 2026-10-29)"
            ),
            "primary": "tests/fixtures/bi_schema_v8/bi_schema.py",
            "generator": "scripts/build_bi_schema_v2.py",
        },
    )
    _add_chart_segments(document)
    return document


def _add_chart_segments(document: dict[str, Any]) -> None:
    """The owner's market chart segments (the vault's 11 application folders)
    as allowed values of `segment` beside aerospace's own, with their labels
    as aliases (owner 2026-10-29: AIDC and every other domain place cards by
    `segment` too, so no domain needs a schema upgrade for it)."""
    added = [segment_id for segment_id, _ in SEGMENTS]
    for entity in document["types"]:
        for field in entity["fields"]:
            if field["name"] == "segment" and field["enum"]:
                field["enum"] = [*field["enum"], *(s for s in added if s not in field["enum"])]
    aliases = document["enum_aliases"].setdefault("segment", {})
    for segment_id, label in SEGMENTS:
        aliases.setdefault(label, segment_id)


def main() -> None:
    text = json.dumps(build(), ensure_ascii=False, indent=1) + "\n"
    OUT.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {OUT.relative_to(REPO)}")


if __name__ == "__main__":
    main()
