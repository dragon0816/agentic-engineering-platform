"""The Dashboard tab as analyses (BI P3).

`docs/phases/BI_ANALYSIS_DASHBOARD.md` §4.3: the Dashboard draws the dataset's
analyses in the vault's order (`meta:dashboard`), with the parameters at the
top (`domain`, `include_sample` and any other parameter an analysis declares),
`level` badges and the counts summed for the strip. A vault shows its own
analyses (working copy, like the rest of the page); a dataset only on this PC
shows the built-in pack (`packs.default_pack`). Sections the pack does not hold
yet (the chains A–A3, quality) are still computed by the coded Dashboard.

Each analysis becomes a section in the page's shape (`id`, `title`, `kind`,
`chart`, `columns`, `rows`, `flags`, `note`). Scripts run in their guarded
processes, several at once, and results are cached by (analysis digest,
database file state, parameters).
"""

from __future__ import annotations

import json
import threading
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
from typing import Any

from capabilities.bi_cards import analyses, catalog, packs
from capabilities.bi_cards.store import BiStore, BiStoreError

WORKERS = 6
CACHE_SIZE = 600
SHARED = ("domain", "include_sample")
CODED_KEPT = ("A", "A2", "A3")

_cache: OrderedDict[tuple[str, str, str], dict[str, Any]] = OrderedDict()
_cache_lock = threading.Lock()


def _db_state(db: Path) -> str:
    try:
        stat = db.stat()
    except OSError:
        return "missing"
    return f"{db.resolve()}|{stat.st_mtime_ns}|{stat.st_size}"


def _run(db: Path, item: dict[str, Any], values: dict[str, Any]) -> dict[str, Any]:
    key = (
        analyses.digest({k: v for k, v in item.items() if k not in ("unit", "slug")}),
        _db_state(db),
        json.dumps(values, ensure_ascii=False, sort_keys=True),
    )
    with _cache_lock:
        if key in _cache:
            _cache.move_to_end(key)
            return _cache[key]
    table = analyses.run(db, item["kind"], item["code"], values)
    with _cache_lock:
        _cache[key] = table
        while len(_cache) > CACHE_SIZE:
            _cache.popitem(last=False)
    return table


def _items(
    workspace: Path, store: BiStore, registry: Any
) -> tuple[list[dict[str, Any]], Path, str]:
    """(the analyses to draw in order, the database they read, where they come from)."""
    if store.vault_id is not None:
        from capabilities.bi_cards import vault

        listed = analyses.listing(workspace, store.vault_id)
        by_slug = {a["slug"]: a for a in listed["analyses"]}
        found = [by_slug[s] for s in listed["order"]]
        return found, vault.Vault(workspace, store.vault_id).db_path, "vault"
    pack = packs.default_pack()
    links = packs.link_fields(registry)
    found = []
    for item in pack["analyses"]:
        if analyses.requires_met(item.get("requires"), registry):
            found.append({**item, "code": packs._filled(item["code"], links)})
    return found, store.path, "pack"


def _names(store: BiStore) -> dict[str, dict[str, str]]:
    """Card names that name one card only -> a cell the page links to the card."""
    seen: dict[str, list[Any]] = {}
    for row in store.card_rows():
        label = row["canonical_key"] if row["entity_type"] == "Signal" else row["name"]
        seen.setdefault(str(label), []).append(row)
    return {
        name: {"card_id": rows[0]["id"], "label": name,
               "cite": f"{rows[0]['entity_type']}:{rows[0]['canonical_key']}"}
        for name, rows in seen.items()
        if len(rows) == 1
    }  # fmt: skip


def _section(
    item: dict[str, Any],
    table: dict[str, Any] | None,
    error: str,
    names: dict[str, dict[str, str]] | None = None,
) -> dict[str, Any]:
    columns = list(table["columns"]) if table else []
    rows = [
        [(names or {}).get(c, c) if isinstance(c, str) else c for c in r]
        for r in (table["rows"] if table else [])
    ]
    flags: list[dict[str, Any]] = []
    if "level" in columns:
        at = columns.index("level")
        columns.pop(at)
        for number, row in enumerate(rows):
            level = row.pop(at)
            if level in ("gap", "warning"):
                flags.append({"row": number, "level": "red" if level == "gap" else "warn",
                              "text": "缺口" if level == "gap" else "警告"})  # fmt: skip
    note = str(item.get("question") or "")
    if error:
        note = f"沒有畫出來：{error}"
    chart = dict(item.get("chart") or {"type": "table"})
    return {
        "id": item["slug"],
        "title": item["title"],
        "kind": "table",
        "chart": chart,
        "columns": columns,
        "rows": rows,
        "flags": flags,
        "note": note,
        "analysis": True,
        "truncated": bool(table and table.get("truncated")),
    }


def _extra_params(items: list[dict[str, Any]], registry: Any) -> dict[str, Any]:
    """Parameters some analysis declares beyond the shared ones (shown at the top)."""
    found: dict[str, Any] = {}
    for item in items:
        for name, spec in analyses.described_params(item.get("params"), registry).items():
            if name not in SHARED and name != "today" and name not in found:
                found[name] = spec
    return found


def board(
    workspace: Path,
    store: BiStore,
    domain: str,
    include_sample: bool,
    given: dict[str, str],
) -> dict[str, Any]:
    """The Dashboard of a BI dataset, drawn from its analyses."""
    from capabilities.bi_cards import dashboard, market, quality

    registry = catalog.for_store(store)
    items, db, source = _items(workspace, store, registry)
    today = date.today().isoformat()
    names = _names(store)
    shared: dict[str, Any] = {"domain": domain, "include_sample": include_sample, **given}

    def draw(item: dict[str, Any]) -> dict[str, Any]:
        declared = item.get("params") or {}
        try:
            values = analyses.resolve_params(
                declared, {k: v for k, v in shared.items() if k in declared}, registry, today=today
            )
            return _section(item, _run(db, item, values), "", names)
        except BiStoreError as failure:
            return _section(item, None, failure.message)

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        drawn = list(pool.map(draw, items)) if db.is_file() else []
    cards = dashboard._cards(store, include_sample)
    types, links, config = dashboard._context(store)
    chains = [
        s
        for s in market.sections(cards, domain, types=types, link_fields=links, config=config)
        if s["id"] in CODED_KEPT
    ]
    checked = quality.section(quality.check(store, registry))
    flags = [f for s in [*chains, *drawn, checked] for f in s["flags"]]
    stale = next((len(s["rows"]) for s in drawn if s["id"] == "stale"), 0)
    return {
        "domain": domain,
        "include_sample": include_sample,
        "source": source,
        "ordered": True,
        "params": _extra_params(items, registry),
        "summary": {
            "red": sum(1 for f in flags if f["level"] == "red"),
            "warn": sum(1 for f in flags if f["level"] != "red"),
            "stale": stale,
        },
        "sections": [*chains, *drawn, checked],
    }
