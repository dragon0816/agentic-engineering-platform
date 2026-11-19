"""A person's 刪除 of sources in step 1 (owner 2026-11-19).

A source added by mistake can be taken back. Each id gets its own result and one
refusal never stops the others:

- `deleted`: a source only on this PC (a dataset not in a vault, or a vault source
  never committed) goes with its copies, Markdown revisions, conversion record and
  index passages; nothing of it is pushed.
- `staged_removal`: a source committed or pushed in a vault has its removal staged;
  the next commit and push carry it, and the vault's history keeps every earlier
  version, so it can be restored. It leaves this PC when that removal is committed
  (`vault_sources.settle_removals`).
- `refused`: a source a card cites as evidence, or one an open Ingest run reads,
  stays; card evidence is never deleted or rewritten (AGENTS rule 7).
- `not_found`: no such source here (or deleted already).

A repeated request changes nothing: a deleted source is `not_found`, a staged
removal is `staged_removal` with `already: true`.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

from aep_bi.cards import vault_sources
from aep_bi.cards.staging import Staging
from aep_bi.cards.store import BiStoreError
from knowledge.repo.repository import RepoError

MAX_IDS = 500
#: Card names a refusal lists before it only counts the rest.
NAMES_SHOWN = 3
CLOSED_RUNS = ("committed", "cancelled", "failed")


def checked_ids(given: Any) -> list[str]:
    if isinstance(given, str):
        given = [given]
    if not isinstance(given, list) or not given:
        raise BiStoreError("ids_missing", "要刪除哪些來源：ids 必須是來源 id 的清單")
    if len(given) > MAX_IDS:
        raise BiStoreError("ids_too_many", f"一次最多刪除 {MAX_IDS} 份來源")
    ids: list[str] = []
    for item in given:
        if not isinstance(item, str) or not item.strip():
            raise BiStoreError("ids_invalid", "每個來源 id 都必須是文字")
        if item.strip() not in ids:
            ids.append(item.strip())
    return ids


def _citing_cards(staging: Staging, ids: set[str]) -> dict[str, list[str]]:
    """Source id to the names of the cards that cite it as evidence, or would once a
    pending proposal is accepted."""
    found: dict[str, set[str]] = {}
    store = staging.store
    if not store.exists:
        return {}
    with closing(sqlite3.connect(f"file:{store.path}?mode=ro", uri=True)) as db:
        db.row_factory = sqlite3.Row
        tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "evidence" in tables:
            marks = ",".join("?" for _ in ids)
            for row in db.execute(
                "SELECT DISTINCT e.source_id, c.name FROM evidence e "
                f"JOIN cards c ON c.id = e.card_id WHERE e.source_id IN ({marks})",
                tuple(ids),
            ):
                found.setdefault(str(row["source_id"]), set()).add(str(row["name"]))
        if "proposals" in tables:
            for row in db.execute(
                "SELECT p.evidence, c.name FROM proposals p JOIN cards c ON c.id = p.card_id "
                "WHERE p.status = 'pending' AND p.evidence IS NOT NULL"
            ):
                for source_id in _evidence_sources(row["evidence"]) & ids:
                    found.setdefault(source_id, set()).add(str(row["name"]))
    return {k: sorted(v) for k, v in found.items()}


def _evidence_sources(text: Any) -> set[str]:
    try:
        items = json.loads(text) if isinstance(text, str) else []
    except ValueError:
        return set()
    if isinstance(items, dict):
        items = [x for group in items.values() if isinstance(group, list) for x in group]
    return {
        str(item["source_id"])
        for item in (items if isinstance(items, list) else ())
        if isinstance(item, dict) and item.get("source_id")
    }


def _open_runs(staging: Staging, ids: set[str]) -> dict[str, list[str]]:
    """Source id to the open Ingest runs (not committed, cancelled or failed) that read
    it or whose candidates cite it."""
    found: dict[str, list[str]] = {}
    for run in staging.run_rows():
        if run["status"] in CLOSED_RUNS:
            continue
        cited = set(run["source_ids"])
        for candidate in staging.candidates(run["id"]):
            for field in candidate.get("fields") or ():
                for proof in field.get("evidence") or ():
                    if isinstance(proof, dict) and proof.get("source_id"):
                        cited.add(str(proof["source_id"]))
        for source_id in cited & ids:
            found.setdefault(source_id, []).append(str(run["id"]))
    return found


def _refusal(code: str, reason: str, **detail: Any) -> dict[str, Any]:
    return {"status": "refused", "code": code, "reason": reason, **detail}


def _cards_reason(names: list[str]) -> str:
    shown = "、".join(f"「{n}」" for n in names[:NAMES_SHOWN])
    more = f"等 {len(names)} 張卡片" if len(names) > NAMES_SHOWN else ""
    return f"卡片 {shown}{more}以它為證據；刪除會讓證據失去出處，所以保留"


def delete(workspace: Path, dataset: str, given_ids: Any, actor: str) -> dict[str, Any]:
    """Delete or stage the removal of each source; see the module docstring."""
    ids = checked_ids(given_ids)
    staging = Staging(workspace, dataset)
    staging.store.refuse_write()
    repo = staging._vault_repo()
    if staging.store.vault_id is not None and repo is None:
        raise BiStoreError(
            "source_unreachable", "讀不到共用資料夾，現在不能刪除；確認 OneDrive 已同步後再試"
        )
    if repo is not None:
        with repo.lock:
            vault_sources.settle_removals(repo, staging)
    sources = {i: staging.source(i) for i in ids}
    known = {i for i, s in sources.items() if s is not None}
    cards = _citing_cards(staging, known)
    running = _open_runs(staging, known)
    results: list[dict[str, Any]] = []
    for source_id in ids:
        source = sources[source_id]
        base: dict[str, Any] = {"id": source_id}
        if source is None:
            results.append(
                {**base, "status": "not_found", "reason": "找不到這份來源（可能已刪除）"}
            )
            continue
        base["name"] = source["name"]
        if source_id in cards:
            names = cards[source_id]
            results.append(
                {
                    **base,
                    **_refusal(
                        "source_cited",
                        _cards_reason(names),
                        cards=names[:NAMES_SHOWN],
                        count=len(names),
                    ),
                }
            )
            continue
        if source_id in running:
            results.append(
                {
                    **base,
                    **_refusal(
                        "source_in_open_run",
                        "有一次 Ingest 還在進行或等審核，正在讀這份來源；先寫入或取消那次 Ingest",
                        runs=running[source_id],
                    ),
                }
            )
            continue
        try:
            results.append({**base, **_delete_one(staging, repo, source, actor)})
        except (BiStoreError, RepoError, OSError, sqlite3.Error) as failure:
            code = getattr(failure, "code", type(failure).__name__)
            message = getattr(failure, "message", None) or str(failure)
            results.append({**base, **_refusal(str(code), str(message))})
    counts = {
        name: sum(1 for r in results if r["status"] == name)
        for name in ("deleted", "staged_removal", "refused", "not_found")
    }
    return {"results": results, "counts": counts}


def _delete_one(staging: Staging, repo: Any, source: dict[str, Any], actor: str) -> dict[str, Any]:
    if repo is None:
        staging.remove_source(str(source["id"]))
        return {"status": "deleted"}
    with repo.lock:
        done = vault_sources.remove_from_vault(repo, source)
        if done == "unstaged":
            staging.remove_source(str(source["id"]))
            return {"status": "deleted"}
        fresh = staging.mark_removal(str(source["id"]), str(source["sha256"]), actor)
    return {"status": "staged_removal", "already": done == "already" and not fresh}
