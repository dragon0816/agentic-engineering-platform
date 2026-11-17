"""The Dashboard order from an Atlas dashboard (BI K2).

`docs/phases/BI_CHAT_CHARTS_AND_DASHBOARD_SOURCES.md` K2 and Atlas's
`docs/AEP_DASHBOARD_READ_CONTRACT.md` (revision 2026-11-01; goldens vendored in
`tests/fixtures/atlas_dashboard_golden/`). Only the order is imported: a panel
of the vault is one whose `datasource.id` is `aep.bi.result`, whose
`query.vault` is the vault's id and whose `query.slug` is a nonempty string.
Those panels are sorted by their stored `(layout.y, layout.x, id)`; each
`(vault, slug)` keeps its first panel and later ones are listed as duplicates.
A slug the vault has no analysis for is listed, never invented. `hidden` is the
vault's other analyses. Positions, sizes, titles, parameters, transforms and
chart specs stay Atlas's (its layouts are personal). Pure: the reading of
Atlas's API is the Host's (`aep_bi/host/bi_atlas_import.py`).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any

from aep_bi.cards.store import BiStoreError

AEP_DATASOURCE = "aep.bi.result"


def _number(value: Any) -> float:
    if isinstance(value, int | float) and not isinstance(value, bool):
        return float(value)
    return float("inf")  # no stored coordinate: after every placed panel


def _key(panel: Mapping[str, Any]) -> tuple[float, float, str]:
    found = panel.get("layout")
    layout: Mapping[str, Any] = found if isinstance(found, Mapping) else {}
    return (_number(layout.get("y")), _number(layout.get("x")), str(panel.get("id") or ""))


def _ours(panel: Any, vault_id: str) -> str | None:
    """The panel's slug when it shows an analysis of this vault, else None."""
    if not isinstance(panel, Mapping):
        return None
    source = panel.get("datasource")
    query = panel.get("query")
    if not isinstance(source, Mapping) or source.get("id") != AEP_DATASOURCE:
        return None
    if not isinstance(query, Mapping) or query.get("vault") != vault_id:
        return None
    slug = query.get("slug")
    return slug if isinstance(slug, str) and slug else None


def _why_not(panel: Any) -> str:
    if not isinstance(panel, Mapping):
        return "not_a_panel"
    source = panel.get("datasource")
    if not isinstance(source, Mapping) or source.get("id") != AEP_DATASOURCE:
        return "not_aep"
    return "other_vault"


def plan(
    document: Any, vault_id: str, saved: Sequence[str], current: Mapping[str, Any]
) -> dict[str, Any]:
    """The import's preview: the new order and hidden, and every panel with
    what became of it (`kept`, `duplicate`, `unknown_analysis`, `other_vault`,
    `not_aep`). `saved` are the vault's analyses, `current` its
    `meta:dashboard`; `token` names exactly this preview."""
    if not isinstance(document, Mapping) or document.get("schemaVersion") != 2:
        raise BiStoreError("atlas_invalid", "這不是 Atlas 的 Dashboard（schemaVersion 2）")
    panels = document.get("panels")
    if not isinstance(panels, list):
        raise BiStoreError("atlas_invalid", "Atlas 的 Dashboard 沒有 panels")
    ours = sorted(
        ((panel, slug) for panel in panels if (slug := _ours(panel, vault_id)) is not None),
        key=lambda pair: _key(pair[0]),
    )
    seen: set[str] = set()
    order: list[str] = []
    listed: list[dict[str, Any]] = []
    for panel, slug in ours:
        if slug in seen:
            status = "duplicate"
        elif slug not in saved:
            status = "unknown_analysis"
        else:
            status = "kept"
            order.append(slug)
        seen.add(slug)
        listed.append({"id": str(panel.get("id") or ""), "slug": slug, "status": status})
    for panel in panels:
        if _ours(panel, vault_id) is None:
            query = panel.get("query") if isinstance(panel, Mapping) else None
            listed.append({
                "id": str(panel.get("id") or "") if isinstance(panel, Mapping) else "",
                "slug": query.get("slug") if isinstance(query, Mapping) else None,
                "status": _why_not(panel),
            })  # fmt: skip
    hidden = [s for s in saved if s not in order]
    preview = {
        "dashboard": str(document.get("title") or document.get("id") or ""),
        "order": order,
        "hidden": hidden,
        "before": {
            "order": list(current.get("order") or []),
            "hidden": list(current.get("hidden") or []),
        },  # fmt: skip
        "panels": listed,
        "duplicates": [p["id"] for p in listed if p["status"] == "duplicate"],
        "unmatched": [p for p in listed if p["status"] not in ("kept", "duplicate")],
    }
    marker = json.dumps([vault_id, preview, list(saved)], ensure_ascii=False, sort_keys=True)
    preview["token"] = hashlib.sha256(marker.encode("utf-8")).hexdigest()[:24]
    return preview
