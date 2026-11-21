"""Describe the pictures in a source's Markdown (owner 2026-11-20).

A conversion keeps a document's pictures as `assets/<name>` and references them
as `![圖 n](assets/<name>)` (`convert`). When this Host's model can see images,
each picture still without a description is described by the same core
`knowledge.describe.ImageDescriber` the LLM Wiki intake uses, and the result is
saved as the next Markdown revision (origin `conversion`, note `圖片說明`), the
description on the line under its picture:

    ![圖 1](assets/0123456789abcdef.png)

    > 圖片說明（<model alias>）：what the picture shows

The description is marked with the alias that wrote it, so a model's words are
never mistaken for the source's. A run happens in the background; `progress`
answers where it is (n of N pictures, seconds) for the page's progress line.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from aep_bi.cards import convert
from aep_bi.cards.staging import Staging
from aep_bi.cards.store import BiStoreError
from common.execution import TraceIdentifiers
from knowledge.describe import ImageDescriber
from models.contracts import ModelClient

DESCRIPTION_PREFIX = "> 圖片說明"

_lock = threading.RLock()
_runs: dict[tuple[str, str, str], dict[str, Any]] = {}


def pending(text: str) -> list[str]:
    """The pictures (`assets/<name>`) in a Markdown text with no description under them."""
    lines = text.split("\n")
    found: list[str] = []
    for index, line in enumerate(lines):
        match = convert.IMAGE_LINE.match(line.strip())
        if match is None:
            continue
        following = next((item for item in lines[index + 1 :] if item.strip()), "")
        if not following.startswith(DESCRIPTION_PREFIX) and match["ref"] not in found:
            found.append(match["ref"])
    return found


def with_descriptions(text: str, descriptions: dict[str, str], alias: str) -> str:
    """`text` with each described picture followed by its description line."""
    lines = text.split("\n")
    out: list[str] = []
    for index, line in enumerate(lines):
        out.append(line)
        match = convert.IMAGE_LINE.match(line.strip())
        if match is None or match["ref"] not in descriptions:
            continue
        following = next((item for item in lines[index + 1 :] if item.strip()), "")
        if following.startswith(DESCRIPTION_PREFIX):
            continue
        said = " ".join(descriptions[match["ref"]].split())
        out += ["", f"{DESCRIPTION_PREFIX}（{alias}）：{said}"]
    return "\n".join(out)


def _key(workspace: Path, dataset: str, source_id: str) -> tuple[str, str, str]:
    return (str(workspace), dataset, source_id)


def progress(workspace: Path, dataset: str, source_id: str) -> dict[str, Any]:
    """Where describing this source's pictures is: `idle` with how many are still
    without a description, or the run (`running`, `finished`, `failed`)."""
    with _lock:
        run = _runs.get(_key(workspace, dataset, source_id))
        if run is not None:
            shown = dict(run)
            if shown["status"] == "running":
                shown["elapsed"] = round(time.monotonic() - shown.pop("_started"), 1)
            else:
                shown.pop("_started", None)
            return shown
    staging = Staging(workspace, dataset)
    source = staging.source(source_id)
    if source is None:
        raise BiStoreError("source_unknown", "找不到這個來源")
    rev = int(source["markdown_rev"] or 0)
    left = len(pending(staging.markdown_text(source_id, rev))) if rev else 0
    return {"status": "idle", "done": 0, "total": left, "pending": left}


def describe(
    workspace: Path,
    dataset: str,
    source_id: str,
    model: ModelClient,
    alias: str,
    *,
    actor: str,
    on_image: Callable[[int, int], None] | None = None,
) -> dict[str, Any]:
    """Describe every picture still without a description; the saved revision
    (or None when there was nothing to describe or nothing was described)."""
    staging = Staging(workspace, dataset)
    source = staging.source(source_id)
    if source is None:
        raise BiStoreError("source_unknown", "找不到這個來源")
    rev = int(source["markdown_rev"] or 0)
    if not rev:
        return {"revision": None, "described": 0, "failed": 0}
    text = staging.markdown_text(source_id, rev)
    refs = pending(text)
    describer = ImageDescriber(model, alias=alias)
    said: dict[str, str] = {}
    failed = 0
    for number, ref in enumerate(refs, start=1):
        try:
            data = staging.asset_file(source_id, ref.split("/", 1)[1]).read_bytes()
        except (BiStoreError, OSError):
            failed += 1
        else:
            trace = TraceIdentifiers(
                trace_id=f"bi-describe-{source_id}",
                request_id=f"describe-{number}",
                span_id=f"image-{number}",
            )
            outcome = describer.describe(ref, data, trace=trace)
            if outcome.status == "described":
                said[ref] = outcome.text
            else:
                failed += 1
        if on_image is not None:
            on_image(number, len(refs))
    if not said:
        return {"revision": None, "described": 0, "failed": failed}
    record, _ = staging.add_markdown(
        source_id,
        with_descriptions(text, said, alias),
        origin="conversion",
        note="圖片說明",
        actor=actor,
        base_rev=rev,
        converter=convert.CONVERTER,
    )
    from aep_bi.cards import search_index

    search_index.sync_quietly(staging.store)
    return {"revision": record, "described": len(said), "failed": failed}


def start(
    workspace: Path,
    dataset: str,
    source_id: str,
    model: ModelClient,
    alias: str,
    *,
    actor: str,
    background: Callable[[str, Callable[[], None]], None],
) -> dict[str, Any]:
    """Start describing in the background; the run as `progress` shows it. A run
    already going for this source is answered, not started twice."""
    key = _key(workspace, dataset, source_id)
    total = len(pending_of(workspace, dataset, source_id))
    with _lock:
        known = _runs.get(key)
        if known is not None and known["status"] == "running":
            return progress(workspace, dataset, source_id)
        if not total:
            _runs.pop(key, None)
            return {"status": "idle", "done": 0, "total": 0, "pending": 0}
        _runs[key] = {
            "status": "running",
            "done": 0,
            "total": total,
            "_started": time.monotonic(),
        }

    def step(done: int, of: int) -> None:
        with _lock:
            _runs[key].update(done=done, total=of)

    def work() -> None:
        started = _runs[key]["_started"]
        try:
            result = describe(
                workspace, dataset, source_id, model, alias, actor=actor, on_image=step
            )
        except Exception as failure:  # noqa: BLE001 - the page shows the failure
            update: dict[str, Any] = {"status": "failed", "error": type(failure).__name__}
        else:
            revision = result["revision"]
            update = {
                "status": "finished",
                "described": result["described"],
                "failed": result["failed"],
                "rev": revision["rev"] if revision else None,
            }
        with _lock:
            _runs[key].update(update, elapsed=round(time.monotonic() - started, 1))

    background(f"圖片說明：{source_id}", work)
    return progress(workspace, dataset, source_id)


def pending_of(workspace: Path, dataset: str, source_id: str) -> list[str]:
    staging = Staging(workspace, dataset)
    source = staging.source(source_id)
    rev = int(source["markdown_rev"] or 0) if source is not None else 0
    return pending(staging.markdown_text(source_id, rev)) if rev else []
