"""The read-only BI analysis feed for Atlas, served by Agent Web (BI feed F2).

`docs/phases/BI_ANALYSIS_DASHBOARD.md` §5; the answers come from
`aep_bi/cards/feed.py`. Same rules as the telemetry reads
(`telemetry_api.py`): GET only, loopback only (the Host-header guard of every
Agent Web route still applies), no token, and cross-origin reads only for
pages on this machine; any other `Origin` is refused. Every other Agent Web
route keeps its token.

    GET /api/v1/bi/health
    GET /api/v1/bi/vaults
    GET /api/v1/bi/vaults/{id}/analyses
    GET /api/v1/bi/vaults/{id}/analyses/{slug}/result?<param>=<value>...

A worker thread computes what the feed queued (scripts never run because of a
request) and the default results after publish and sync (`refresh`).
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any

from aep_bi.cards import feed

#: Seconds the worker waits before computing what was queued (the fixture
#: server sets a delay so a client sees `result_not_ready` first).
QUEUE_DELAY = 0.0

_wake = threading.Event()
_started = threading.Lock()
_worker: threading.Thread | None = None


def is_feed(path: str) -> bool:
    return path.startswith(feed.PREFIX) or path == feed.PREFIX.rstrip("/")


def _work() -> None:
    while True:
        _wake.wait()
        _wake.clear()
        if QUEUE_DELAY:
            time.sleep(QUEUE_DELAY)
        try:
            feed.drain()
        except Exception:  # noqa: BLE001, S110 - the worker outlives one bad item; a request asks again
            pass


def ensure_worker() -> None:
    """Start the worker once; `feed.enqueue` wakes it."""
    global _worker
    with _started:
        if _worker is not None and _worker.is_alive():
            return
        feed.on_queued = _wake.set
        _worker = threading.Thread(target=_work, name="bi-feed-results", daemon=True)
        _worker.start()
        if feed.queued():
            _wake.set()


def refresh(workspace: Path, vault_id: str) -> None:
    """Queue the default results of the version the feed shows (after publish,
    sync or a person's run); quiet when the vault cannot be read."""
    try:
        ensure_worker()
        feed.enqueue_defaults(workspace, vault_id)
    except Exception:  # noqa: BLE001, S110 - the feed never fails the person's sync or publish
        return


def _cors(handler: Any) -> None:
    origin = handler.headers.get("Origin") or ""
    if origin and feed.local_origin(origin):
        handler.send_header("Access-Control-Allow-Origin", origin)
        handler.send_header("Vary", "Origin")


def _reply(handler: Any, status: int, payload: Any) -> None:
    body = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("X-Content-Type-Options", "nosniff")
    _cors(handler)
    handler.end_headers()
    handler.wfile.write(body)


def handle(handler: Any, method: str, path: str, query: str, workspace: Path) -> bool:
    """Answer a feed route; False when the path is not one."""
    if not is_feed(path):
        return False
    ensure_worker()
    status, payload = feed.answer(workspace, method, path, query, handler.headers.get("Origin"))
    _reply(handler, status, payload)
    return True
