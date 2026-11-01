"""The golden answers of the default pack are the coded Dashboard's (before P5).

`docs/phases/BI_ANALYSIS_DASHBOARD.md` §4.3: the coded sections (`dashboard.py`
§1–§19, `market.py` §20–§31 and A–A3, `coverage.py`) are removed in P5; their
answers on the fixtures of `bi_pack_fixtures` are kept in
`tests/fixtures/bi_default_pack/golden/` first, so the pack's parity tests keep a
reference. This test rebuilds the coded answers and compares them with the files;
`AEP_WRITE_PACK_GOLDEN=1` writes them instead. It goes with the coded sections in
P5. A card cell becomes its name and a flagged row gets `level` (`gap` for red,
`warning` otherwise), as the analyses return them. All data is fictional.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from bi_pack_fixtures import (
    CHAIN_DOMAINS,
    FIXTURES,
    GOLDEN,
    GOLDEN_FORMAT,
    TODAY,
    build,
    domains_of,
    golden,
    key,
)

from capabilities.bi_cards import catalog, coverage, dashboard, domains, market, packs
from capabilities.bi_cards.store import BiStore

#: slug -> (the coded section, whether it flags rows, what else it takes).
CODED: dict[str, tuple[Callable[..., dict[str, Any]], bool, str]] = {
    "gaps": (dashboard.gaps, True, ""),
    "trend-coverage": (dashboard.trend_coverage, True, ""),
    "demand-without-opportunity": (dashboard.demand_without_opportunity, True, ""),
    "solutions-vs-opportunities": (dashboard.solutions_vs_opportunities, True, ""),
    "funnel": (dashboard.funnel, False, ""),
    "technologies-without-concept": (dashboard.technologies_without_concept, True, ""),
    "product-completeness": (dashboard.product_completeness, True, ""),
    "trend-priority": (dashboard.trend_priority, False, ""),
    "launch-timeline": (dashboard.launch_timeline, False, ""),
    "node-technology": (dashboard.node_technology, False, ""),
    "recent-signals": (dashboard.recent_signals, False, ""),
    "competitor-coverage": (dashboard.competitor_coverage, False, ""),
    "assumed-share": (dashboard.assumed_share, False, ""),
    "stale": (dashboard.stale, False, "today"),
    "supplier-dependency": (dashboard.supplier_dependency, False, ""),
    "trend-links": (market.trend_links, True, ""),
    "win-loss": (market.win_loss, True, ""),
    "roadmap-gaps": (market.roadmap_gaps, True, ""),
    "enablement": (market.enablement, True, ""),
    "customer-contact": (market.customer_contact, True, "today"),
    "supply-evidence": (market.supply_evidence, True, ""),
    "timing-gaps": (market.timing_gaps, True, "today"),
    "supply-grades": (market.supply_grades, True, ""),
    "revenue-layers": (market.revenue_layers, True, ""),
    "chain-integrity": (market.chain_integrity, True, ""),
    "same-names": (market.same_names, True, ""),
    "pending-links": (market.pending_links, False, "links"),
}
CHAINED: dict[str, tuple[Callable[..., dict[str, Any]], bool]] = {
    "chain-summary": (market.chain_summary, False),
    "chain-view": (market.chain_view, True),
    "chain-overlap": (market.chain_overlap, False),
}


def _table(section: dict[str, Any], level: bool) -> dict[str, Any]:
    levels = {f["row"]: "gap" if f["level"] == "red" else "warning" for f in section["flags"]}
    rows = []
    for number, row in enumerate(section["rows"]):
        cells = [c["label"] if isinstance(c, dict) else c for c in row]
        rows.append([*cells, levels.get(number)] if level else cells)
    assert level or not section["flags"], section["id"]
    return {"columns": [*section["columns"], *(["level"] if level else [])], "rows": rows}


def _coverage_table(report: dict[str, Any]) -> dict[str, Any]:
    rows = [
        [c["segment"], c["area"], c["cards"],
         "、".join(f"{t} {n}" for t, n in c["types"].items()), c["sourced_share"], c["newest"],
         "、".join(f"{e['field']} {e['cards']}" for e in c["empty"])]
        for c in report["cells"]
    ]  # fmt: skip
    return {"columns": ["區段", "技術領域", "卡片數", "類型", "有來源比例", "最新更新",
                        "最常空白的欄位（前 5）"], "rows": rows}  # fmt: skip


def _sections(store: BiStore) -> tuple[list[str], dict[str, dict[str, Any]]]:
    registry = catalog.for_store(store)
    links = packs.link_fields(registry)
    names = domains_of(registry)
    results: dict[str, dict[str, Any]] = {}
    for include_sample in (False, True):
        cards = dashboard._cards(store, include_sample)
        for domain in names:
            for slug, (section, level, extra) in CODED.items():
                args: tuple[Any, ...] = (cards, domain)
                if extra == "today":
                    args = (*args, TODAY)
                elif extra == "links":
                    args = (*args, links)
                table = _table(section(*args), level)
                results.setdefault(slug, {})[key(domain, include_sample)] = table
    return names, results


def _chains(tmp_path: Path) -> tuple[list[str], dict[str, dict[str, Any]]]:
    """The coded chains before the domain migration; the coded coverage matrix
    after it, with the configuration's matrix on the same cards."""
    before = build("chains", tmp_path / "before", migrated=False)
    config = domains.read(before)
    assert config is not None
    matrix = coverage.validate(config.matrix())
    results: dict[str, dict[str, Any]] = {}
    for include_sample in (False, True):
        cards = dashboard._cards(before, include_sample)
        for domain in CHAIN_DOMAINS:
            for slug, (section, level) in CHAINED.items():
                table = _table(section(cards, domain, config), level)
                results.setdefault(slug, {})[key(domain, include_sample)] = table
    after = build("chains", tmp_path / "after")
    report = coverage.compute(after, catalog.for_store(after), matrix)
    results["coverage"] = {"*": _coverage_table(report)}
    return list(CHAIN_DOMAINS), results


def coded(name: str, tmp_path: Path) -> dict[str, Any]:
    if name == "chains":
        names, results = _chains(tmp_path)
    else:
        names, results = _sections(build(name, tmp_path))
    return dict(json.loads(json.dumps({
        "format": GOLDEN_FORMAT, "fixture": name, "today": TODAY.isoformat(), "domains": names,
        "made_from": "the coded Dashboard (dashboard.py, market.py, coverage.py) before BI P5",
        "results": results}, ensure_ascii=False)))  # fmt: skip


@pytest.mark.parametrize("name", FIXTURES)
def test_the_golden_answers_are_the_coded_sections(name: str, tmp_path: Path) -> None:
    found = coded(name, tmp_path)
    if os.environ.get("AEP_WRITE_PACK_GOLDEN") == "1":
        GOLDEN.mkdir(parents=True, exist_ok=True)
        text = json.dumps(found, ensure_ascii=False, indent=1, sort_keys=True) + "\n"
        (GOLDEN / f"{name}.json").write_text(text, encoding="utf-8")
    assert golden(name) == found
