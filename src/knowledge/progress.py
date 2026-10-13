"""Progress of long Knowledge steps, for the page to show while it waits (owner 2026-10-13).

Creating a sandbox copies the whole project vault and a pull hashes every original,
so both can take a minute. The page names a random key with the request and reads
`read(key)` while the request runs; the step reports through `reporter(key)`. Entries
hold counts and a file name only, live in this process and expire on their own.
"""

from __future__ import annotations

import re
import threading
import time
from collections.abc import Callable
from typing import Any

KEY = re.compile(r"[A-Za-z0-9_-]{8,64}")
#: An entry nobody updated for this long is dropped.
TTL_SECONDS = 600
Reporter = Callable[[str, int, int, str], None]

_lock = threading.Lock()
_entries: dict[str, dict[str, Any]] = {}


def _expire(now: float) -> None:
    for key in [k for k, v in _entries.items() if now - v["updated"] > TTL_SECONDS]:
        del _entries[key]


def report(key: str, phase: str, done: int, total: int, current: str = "") -> None:
    now = time.monotonic()
    with _lock:
        _expire(now)
        _entries[key] = {"phase": phase, "done": done, "total": total,
                         "current": current[-160:], "updated": now}


def reporter(key: str | None) -> Reporter | None:
    """A callback for a valid key, or None so the step reports nothing."""
    if key is None or not KEY.fullmatch(key):
        return None

    def update(phase: str, done: int, total: int, current: str = "") -> None:
        report(key, phase, done, total, current)

    return update


def read(key: str) -> dict[str, Any] | None:
    if not KEY.fullmatch(key):
        return None
    with _lock:
        entry = _entries.get(key)
        return None if entry is None else {k: v for k, v in entry.items() if k != "updated"}
