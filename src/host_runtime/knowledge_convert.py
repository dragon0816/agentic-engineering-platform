"""Convert a sandbox's drop/ in the background, one original at a time (owner 2026-10-13).

Converting a PDF asks the model to describe every picture in it; five decks held
248 pictures, so one request for the whole drop outlived the Bridge's step limit
and the page heard nothing. The person's click starts this run instead: each
original is converted on its own, the page reads how far it is (document, then
pictures), and Stop ends it after the original in progress. Preview runs the same
way and spends no model calls.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import Field

from common.base import Contract

#: convert(sandbox_id, paths, mode, progress_key) -> ConvertResult
Convert = Callable[[str, tuple[str, ...], str, str], Any]


class ConvertedItem(Contract):
    path: str
    status: str
    raw_ref: str | None = None
    images: int = Field(default=0, ge=0)
    described: int = Field(default=0, ge=0)


class ConvertRun(Contract):
    run_id: str
    sandbox_id: str
    mode: Literal["dry_run", "apply"]
    paths: tuple[str, ...]
    progress_key: str
    status: Literal["running", "stopping", "stopped", "finished", "failed"] = "running"
    current: str | None = None
    items: tuple[ConvertedItem, ...] = ()
    error: str | None = None
    started: str
    ended: str | None = None


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def run_convert(convert: Convert, run: ConvertRun, stop: threading.Event,
                on_change: Callable[[ConvertRun], None]) -> ConvertRun:
    on_change(run)
    for path in run.paths:
        if stop.is_set():
            break
        run = run.model_copy(update={"current": path})
        on_change(run)
        try:
            result = convert(run.sandbox_id, (path,), run.mode, run.progress_key)
            found = [ConvertedItem.model_validate(item.model_dump()) for item in result.items]
        except Exception as failure:  # noqa: BLE001 - one original never ends the run
            found = [ConvertedItem(path=path, status=str(getattr(failure, "code", "")
                                                          or type(failure).__name__))]
        run = run.model_copy(update={"items": (*run.items, *found)})
        on_change(run)
    done = len(run.items) >= len(run.paths)
    run = run.model_copy(update={"status": "finished" if done else "stopped",
                                 "current": None, "ended": _now()})
    on_change(run)
    return run
