"""The read-only BI analysis feed for Atlas (`aep.bi.analysis_feed/v1`).

`docs/phases/BI_ANALYSIS_DASHBOARD.md` §5. This module builds the answers; the
HTTP routes (`aep_bi/host/bi_feed_api.py`) only serve them. The feed shows a
vault's **published** version (what the Agent reads, `Vault.reads`), never
this PC's unpushed work.

No script runs because of a feed request: results are computed by AEP (on
publish, on sync when the published version changed, when the person runs an
analysis) and cached by (analysis digest, published commit, parameters). A
request for parameters not computed yet is queued (`enqueue`, run by
`drain`) and answered `result_not_ready`. A read-only SQL result is computed
on request, since it runs no code beyond the statement on a read-only copy.
"""

from __future__ import annotations

import hashlib
import json
import re
import threading
import uuid
from collections import OrderedDict
from collections.abc import Callable, Mapping
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote

from aep_bi.cards import analyses, catalog, schema_merge
from aep_bi.cards.store import DB_FILE, BiStoreError, vault_registry
from knowledge.repo import repository as repo_engine

FORMAT = "aep.bi.analysis_feed/v1"
DASHBOARD_UNIT = analyses.DASHBOARD_UNIT
RESULTS_DIR = "feed_results"
MAX_BYTES = 8 * 1024 * 1024
MAX_QUEUE = 200


class FeedError(Exception):
    """An answer other than 200: `{"ok": false, "code", "message"}` with `status`."""

    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message

    def payload(self) -> dict[str, Any]:
        return {"ok": False, "code": self.code, "message": self.message}


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


#: When a result was computed. The fixture server and the contract test set a
#: fixed clock so their answers equal the golden files.
clock: Callable[[], str] = _now


def _today() -> str:
    return clock()[:10]


# -- what is published -----------------------------------------------------------------


def _vault(workspace: Path, vault_id: str) -> Any:
    from aep_bi.cards import vault

    if vault.registry_entry(workspace, vault_id) is None:
        raise FeedError(404, "vault_unknown", f"no vault {vault_id!r} on this PC")
    try:
        return vault.Vault(workspace, vault_id)
    except BiStoreError as failure:
        raise FeedError(404, "vault_unknown", failure.message) from None


def _published(target: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    """(version `{"tag", "commit"}`, the units of that version)."""
    try:
        reads = target.reads()
    except (BiStoreError, repo_engine.RepoError, OSError):
        raise FeedError(409, "vault_unreadable", "the vault cannot be read now") from None
    commit = reads.get("commit")
    if not commit:
        raise FeedError(409, "not_published", "the vault has no pushed version yet")
    return {"tag": reads.get("tag"), "commit": commit}, _units_at(target, commit)


#: The units of recent published versions, shared and never changed by a reader. One
#: `state_at` replays every commit, and each analysis of a listing asks for the same one.
_UNITS: OrderedDict[tuple[str, str, int], dict[str, Any]] = OrderedDict()
_UNITS_LOCK = threading.Lock()
MAX_UNITS = 4


def _units_at(target: Any, commit: str) -> dict[str, Any]:
    key = (str(target.folder), commit, len(target.repo.applied_ids()))
    with _UNITS_LOCK:
        if key in _UNITS:
            _UNITS.move_to_end(key)
            return _UNITS[key]
    units: dict[str, Any] = target.repo.state_at(commit)
    with _UNITS_LOCK:
        _UNITS[key] = units
        while len(_UNITS) > MAX_UNITS:
            _UNITS.popitem(last=False)
    return units


def _registry(units: Mapping[str, Any], workspace: Path) -> Any | None:
    ref = units.get(repo_engine.SCHEMA_UNIT)
    if not isinstance(ref, str) or not ref:
        return None
    try:
        return catalog.resolve(workspace, schema_merge.effective_ref(workspace, units))
    except Exception:  # noqa: BLE001 - an unknown schema offers nothing that requires one
        return None


def _offered(units: Mapping[str, Any], registry: Any | None) -> dict[str, dict[str, Any]]:
    """The published analyses the schema satisfies, by slug."""
    found = {}
    for item in analyses.saved(units):
        key = item["unit"]
        if analyses.unit_problem(key, units[key]) is not None:
            continue
        if analyses.requires_met(item.get("requires"), registry):
            found[item["slug"]] = item
    return found


dashboard_layout = analyses.dashboard_layout
order = analyses.order


def _value(item: Mapping[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in item.items() if k not in ("unit", "slug")}


# -- the answers -----------------------------------------------------------------------


def health() -> dict[str, Any]:
    return {"format": FORMAT, "ok": True}


def vaults(workspace: Path) -> dict[str, Any]:
    found = []
    for entry in vault_registry(workspace):
        try:
            target = _vault(workspace, str(entry["id"]))
            version, units = _published(target)
        except FeedError:
            continue
        described = target.describe()
        found.append(
            {
                "id": target.id,
                "dataset": target.dataset,
                "title": described.get("title"),
                "purpose": described.get("purpose"),
                "schema": units.get(repo_engine.SCHEMA_UNIT),
                "reads": version,
            }
        )
    return {"vaults": found}


def listing(workspace: Path, vault_id: str) -> dict[str, Any]:
    target = _vault(workspace, vault_id)
    version, units = _published(target)
    registry = _registry(units, workspace)
    offered = _offered(units, registry)
    ordered = order(units, list(offered))
    rest = sorted(s for s in offered if s not in ordered)
    items = []
    for slug in ordered + rest:
        item = offered[slug]
        items.append(
            {
                "slug": slug,
                "title": item["title"],
                "question": item.get("question") or "",
                "kind": item["kind"],
                "chart": item.get("chart") or {"type": "table"},
                "params": analyses.described_params(item.get("params"), registry),
                "requires": {
                    "types": list((item.get("requires") or {}).get("types") or []),
                    "fields": list((item.get("requires") or {}).get("fields") or []),
                },
                "digest": analyses.digest(_value(item)),
            }
        )
    return {"vault": vault_id, "version": version, "order": ordered, "analyses": items}


def _params_key(values: Mapping[str, Any]) -> str:
    text = json.dumps(values, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _cache_path(target: Any, digest: str, commit: str, values: Mapping[str, Any]) -> Path:
    return Path(target.local) / RESULTS_DIR / digest / commit[:16] / f"{_params_key(values)}.json"


class _Request:
    """One result request, resolved against the published version."""

    def __init__(self, workspace: Path, vault_id: str, slug: str, given: Mapping[str, Any]):
        self.workspace = workspace
        self.target = _vault(workspace, vault_id)
        self.version, units = _published(self.target)
        registry = _registry(units, workspace)
        item = _offered(units, registry).get(slug)
        if item is None:
            raise FeedError(404, "analysis_unknown", f"no published analysis {slug!r}")
        self.slug = slug
        self.item = item
        self.digest = analyses.digest(_value(item))
        try:
            self.values = analyses.resolve_params(
                item.get("params"), given, registry, today=_today()
            )
        except BiStoreError as failure:
            raise FeedError(400, "param_invalid", failure.message) from None
        self.path = _cache_path(self.target, self.digest, self.version["commit"], self.values)

    def cached(self) -> dict[str, Any] | None:
        try:
            return dict(json.loads(self.path.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            return None

    def compute(self) -> dict[str, Any]:
        """Run the analysis on the published copy and cache what it gave."""
        folder = self.target.refresh_published()
        try:
            table = analyses.run(
                folder / DB_FILE, self.item["kind"], self.item["code"], self.values
            )
            record: dict[str, Any] = {
                "slug": self.slug,
                "digest": self.digest,
                "version": self.version,
                "params": self.values,
                "columns": table["columns"],
                "rows": table["rows"],
                "truncated": bool(table["truncated"]),
                "computed_at": clock(),
            }
            if len(json.dumps(record, ensure_ascii=False, default=str).encode()) > MAX_BYTES:
                record = {"error": {"code": "result_too_large", "message": "over 8 MiB"}}
        except BiStoreError as failure:
            record = {"error": {"code": "result_failed", "message": failure.message}}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        scratch = self.path.with_suffix(f".{uuid.uuid4().hex[:8]}.tmp")
        scratch.write_text(json.dumps(record, ensure_ascii=False, default=str), encoding="utf-8")
        repo_engine.replace_retrying(scratch, self.path)
        return record


def _answer(record: Mapping[str, Any]) -> dict[str, Any]:
    error = record.get("error")
    if isinstance(error, dict):
        raise FeedError(409, str(error.get("code")), str(error.get("message")))
    return dict(record)


def result(workspace: Path, vault_id: str, slug: str, given: Mapping[str, Any]) -> dict[str, Any]:
    """A cached result; SQL is computed on request, a script is queued (409)."""
    request = _Request(workspace, vault_id, slug, given)
    record = request.cached()
    if record is None and request.item["kind"] == "sql":
        record = request.compute()
    if record is None:
        enqueue(workspace, vault_id, slug, request.values)
        raise FeedError(
            409, "result_not_ready", "this result is being computed; ask again in a moment"
        )
    return _answer(record)


def compute(
    workspace: Path, vault_id: str, slug: str, given: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    """Compute (or recompute) one result now; what the person's run and the queue call."""
    return _Request(workspace, vault_id, slug, given or {}).compute()


def compute_defaults(workspace: Path, vault_id: str) -> int:
    """Compute every published analysis's default result not cached yet (on
    publish and on sync); returns how many were computed."""
    done = 0
    for item in listing(workspace, vault_id)["analyses"]:
        request = _Request(workspace, vault_id, item["slug"], {})
        if request.cached() is None:
            request.compute()
            done += 1
    return done


def enqueue_defaults(workspace: Path, vault_id: str) -> int:
    """Queue every published analysis's default result not cached yet (for
    the worker, so a publish or sync does not wait for scripts)."""
    queued_now = 0
    for item in listing(workspace, vault_id)["analyses"]:
        request = _Request(workspace, vault_id, item["slug"], {})
        if request.cached() is None:
            enqueue(workspace, vault_id, item["slug"], request.values)
            queued_now += 1
    return queued_now


# -- the routes ------------------------------------------------------------------------

PREFIX = "/api/v1/bi/"
LOCAL_ORIGIN = re.compile(r"^https?://(127\.0\.0\.1|localhost|\[::1\])(:\d+)?$")


def local_origin(origin: str | None) -> bool:
    """No `Origin` (not a browser page) or a page on this machine."""
    return not origin or LOCAL_ORIGIN.match(origin) is not None


def answer(
    workspace: Path, method: str, path: str, query: str, origin: str | None
) -> tuple[int, dict[str, Any]]:
    """(status, JSON body) of a feed request; the HTTP layer only writes it."""
    try:
        if not local_origin(origin):
            raise FeedError(403, "origin_refused", "the feed is read only by pages on this machine")
        if method != "GET":
            raise FeedError(405, "method_not_allowed", "the feed answers GET only")
        rest = path[len(PREFIX) :] if path.startswith(PREFIX) else None
        parts = [unquote(p) for p in (rest or "").split("/")]
        given = {k: v[0] for k, v in parse_qs(query, keep_blank_values=True).items()}
        if rest == "health":
            return 200, health()
        if rest == "vaults":
            return 200, vaults(workspace)
        if len(parts) == 3 and parts[0] == "vaults" and parts[2] == "analyses":
            return 200, listing(workspace, parts[1])
        if len(parts) == 5 and parts[0] == "vaults" and parts[2:5:2] == ["analyses", "result"]:
            return 200, result(workspace, parts[1], parts[3], given)
        raise FeedError(404, "route_unknown", "no such feed route")
    except FeedError as failure:
        return failure.status, failure.payload()


# -- the queue -------------------------------------------------------------------------

_QUEUE: list[tuple[Path, str, str, dict[str, Any]]] = []
_QUEUE_LOCK = threading.Lock()
#: Called after something was queued (the web server wakes its worker).
on_queued: Callable[[], None] | None = None


def enqueue(workspace: Path, vault_id: str, slug: str, values: Mapping[str, Any]) -> None:
    item = (workspace, vault_id, slug, dict(values))
    with _QUEUE_LOCK:
        if item in _QUEUE or len(_QUEUE) >= MAX_QUEUE:
            return
        _QUEUE.append(item)
    if on_queued is not None:
        on_queued()


def queued() -> int:
    with _QUEUE_LOCK:
        return len(_QUEUE)


def drain(limit: int | None = None) -> int:
    """Compute queued results in order; returns how many ran."""
    done = 0
    while limit is None or done < limit:
        with _QUEUE_LOCK:
            if not _QUEUE:
                break
            workspace, vault_id, slug, values = _QUEUE.pop(0)
        try:
            compute(workspace, vault_id, slug, values)
        except (FeedError, BiStoreError, repo_engine.RepoError, OSError):
            pass  # the vault or analysis changed since; the next request asks again
        done += 1
    return done
