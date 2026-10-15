"""When each Bridge last called the platform, for the administrator's overview.

Platform overview (owner 2026-10-15, `docs/phases/PLATFORM_OVERVIEW.md`). The
Bridge API records the time and operation of every call a token proved, so an
administrator can tell a computer that still talks to the platform from one
that went quiet. It is a fact about the device, never an authorization.

The latest call is always kept in memory. A durable platform also writes it to
its SQLite file, at most once a minute per Bridge, so a frequent poll does not
turn into a write per request.
"""

from __future__ import annotations

import threading
from datetime import datetime, timedelta

from pydantic import AwareDatetime

from common.base import Contract, Symbol
from control_plane.identity_store import SqliteIdentityStorage

# How often one Bridge's last call is written to the durable store.
PERSIST_EVERY = timedelta(minutes=1)


class BridgeLastSeen(Contract):
    bridge_id: Symbol
    operation: Symbol
    at: AwareDatetime


class BridgeActivity:
    """The last authenticated call of each Bridge."""

    def __init__(self, *, storage: SqliteIdentityStorage | None = None) -> None:
        self._storage = storage
        self._lock = threading.Lock()
        self._last: dict[str, BridgeLastSeen] = {
            item.bridge_id: item
            for item in (
                BridgeLastSeen.model_validate_json(raw)
                for raw in (() if storage is None else storage.records("bridge_activity"))
            )
        }
        self._persisted: dict[str, datetime] = {key: item.at for key, item in self._last.items()}

    def seen(self, bridge_id: str, operation: str, at: datetime) -> None:
        item = BridgeLastSeen(bridge_id=bridge_id, operation=operation, at=at)
        with self._lock:
            previous = self._last.get(bridge_id)
            if previous is not None and previous.at > at:
                return
            self._last[bridge_id] = item
            written = self._persisted.get(bridge_id)
            if self._storage is None or (written is not None and at - written < PERSIST_EVERY):
                return
            self._persisted[bridge_id] = at
        self._storage.put("bridge_activity", bridge_id, item)

    def last(self, bridge_id: str) -> BridgeLastSeen | None:
        with self._lock:
            item = self._last.get(bridge_id)
        return None if item is None else item.model_copy()
