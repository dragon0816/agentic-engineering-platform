"""The Dashboard tab as analyses (BI P3).

`docs/phases/BI_ANALYSIS_DASHBOARD.md` §4.3: the Dashboard draws the dataset's
analyses in the vault's order (`meta:dashboard`), with the parameters at the
top (`domain`, `include_sample` and any other parameter an analysis declares),
`level` badges and the counts summed for the strip. A vault shows its own
analyses (working copy, like the rest of the page); a dataset only on this PC
shows the built-in pack (`packs.default_pack`), what its schema satisfies. The
quality check (`quality.py`) is the last section; nothing else is coded (P5).

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
    found = []
    for item in pack["analyses"]:
        if analyses.requires_met(item.get("requires"), registry):
            found.append({**item, "code": packs.fill(item["code"], registry)})
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
    # A spec that names no column of the result gets the default (bar or table).
    chart = analyses.chart_for(item.get("chart"), columns, rows)
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
    from capabilities.bi_cards import quality

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
    checked = quality.section(quality.check(store, registry))
    flags = [f for s in [*drawn, checked] for f in s["flags"]]
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
        "sections": [*drawn, checked],
    }


def _named(
    items: dict[str, dict[str, Any]],
    slugs: list[str],
    db: Path,
    registry: Any,
    given: dict[str, Any],
    names: dict[str, dict[str, str]],
    *,
    strict: bool,
) -> list[dict[str, Any]]:
    """The analyses `slugs` as sections with the parameters they ran with; a
    failure refuses when `strict` (one analysis asked for), else is shown."""
    today = date.today().isoformat()
    found = []
    for slug in slugs:
        item = items[slug]
        declared = item.get("params") or {}
        chosen = {k: v for k, v in given.items() if k in declared}
        for key, spec in analyses.described_params(declared, registry).items():
            # The model may write "aidc" for "AIDC": an enum value is matched without case.
            if spec["type"] == "enum" and isinstance(chosen.get(key), str):
                lower = {str(v).lower(): v for v in spec["values"]}
                chosen[key] = lower.get(chosen[key].lower(), chosen[key])
        try:
            values = analyses.resolve_params(declared, chosen, registry, today=today)
            section = _section(item, _run(db, item, values), "", names)
            section["params"] = values
        except BiStoreError as failure:
            if strict:
                raise
            section = _section(item, None, failure.message)
        found.append(section)
    return found


def pack_sections(
    workspace: Path, store: BiStore, name: str, given: dict[str, Any]
) -> list[dict[str, Any]]:
    """A dataset's analysis by name (`all`: every one in order), for `bi__query`
    on a dataset only on this PC: the built-in pack's analyses its schema
    satisfies. A coded section's old name (`trend_coverage`) finds its slug."""
    registry = catalog.for_store(store)
    listed, db, _source = _items(workspace, store, registry)
    items = {i["slug"]: i for i in listed}
    slug = name.replace("_", "-")
    slugs = list(items) if slug == "all" else [slug]
    if not items or any(s not in items for s in slugs):
        raise BiStoreError("analysis_unknown", f"這個資料集沒有分析「{name}」")
    return _named(items, slugs, db, registry, given, _names(store), strict=slug != "all")


def published_analysis(workspace: Path, vault_id: str, slug: str) -> dict[str, Any] | None:
    """A saved analysis of the version the Agent reads (its unit value and
    slug), or None; what the chat showed through `bi__query` (BI C3)."""
    from capabilities.bi_cards import feed, vault

    try:
        _version, units = feed._published(vault.Vault(workspace, vault_id))
    except (feed.FeedError, BiStoreError):
        return None
    return next((item for item in analyses.saved(units) if item["slug"] == slug), None)


def published_sections(
    workspace: Path, vault_id: str, name: str, given: dict[str, Any]
) -> list[dict[str, Any]]:
    """A saved analysis of the version the Agent reads (`all`: every one in the
    Dashboard's order), as sections; for `bi__query` `analysis` (BI P4)."""
    from capabilities.bi_cards import feed, vault
    from capabilities.bi_cards.store import DB_FILE

    target = vault.Vault(workspace, vault_id)
    try:
        _version, units = feed._published(target)
    except feed.FeedError as failure:
        raise BiStoreError(failure.code, failure.message) from None
    registry = feed._registry(units, workspace)
    offered = feed._offered(units, registry)
    slugs = analyses.order(units, list(offered)) if name == "all" else [name]
    if any(s not in offered for s in slugs):
        raise BiStoreError("analysis_unknown", f"發佈版本裡沒有分析「{name}」")
    db = target.refresh_published() / DB_FILE
    names = _names(vault.reading_store(workspace, vault.dataset_name(vault_id)))
    return _named(offered, slugs, db, registry, given, names, strict=name != "all")


def saved_name(workspace: Path, vault_id: str, name: str) -> str | None:
    """`name` as a published analysis's slug (a coded name like `trend_coverage`
    finds `trend-coverage`), or None when the published version has neither."""
    from capabilities.bi_cards import feed, vault

    try:
        _version, units = feed._published(vault.Vault(workspace, vault_id))
    except (feed.FeedError, BiStoreError):
        return None
    offered = feed._offered(units, feed._registry(units, workspace))
    if name == "all":
        return "all" if offered else None
    for slug in (name, name.replace("_", "-")):
        if slug in offered:
            return slug
    return None
