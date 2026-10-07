"""Publish a fully written staging directory under its final name.

Several stores (extension packages, Knowledge packages, query stages) write
every file into a private ``.part-*`` directory and then expose it with one
rename, so a reader sees the whole version or nothing.

On Windows a directory cannot be renamed while any file inside it is open
without delete sharing. Antivirus scanners, the search indexer and editor file
watchers open files right after they are written, which makes the rename fail
with ``ERROR_ACCESS_DENIED`` (5) or ``ERROR_SHARING_VIOLATION`` (32) for a
short moment even though nothing is wrong with the staged content. Measured on
a development machine with Defender real-time protection, 1-3% of extension
stagings were refused this way and the handle was gone within 16-68 ms when
idle; under a loaded test run it lasts longer. Only those two errors are retried, and
only on Windows, within a bounded time budget; any other failure, or the same
failure after the budget, is raised unchanged so the caller still cleans up
and reports it.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

_TRANSIENT_WINERRORS = frozenset({5, 32})
_FIRST_DELAY_SECONDS = 0.02
_MAX_DELAY_SECONDS = 0.5
RENAME_BUDGET_SECONDS = 10.0


def _is_transient(error: OSError) -> bool:
    return sys.platform == "win32" and getattr(error, "winerror", None) in _TRANSIENT_WINERRORS


def publish_directory(
    stage: Path, target: Path, *, budget_seconds: float = RENAME_BUDGET_SECONDS
) -> None:
    """Rename ``stage`` to ``target``, waiting out brief Windows file locks.

    ``target`` must not exist; the rename is the single atomic step that makes
    the staged directory visible.
    """
    deadline = time.monotonic() + budget_seconds
    delay = _FIRST_DELAY_SECONDS
    while True:
        try:
            os.replace(stage, target)
            return
        except OSError as error:
            if not _is_transient(error) or time.monotonic() + delay > deadline:
                raise
        time.sleep(delay)
        delay = min(delay * 2, _MAX_DELAY_SECONDS)
