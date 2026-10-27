"""Ingest runs on the AI path (BI ingest phase 4, owner 2026-10-27).

`docs/phases/BI_INGEST.md` §7: a text or Markdown source is read by the
model through `extract` in a background job; the run shows `extracting` with
chunks done and total, then `review` (every chunk answered), `partial` (some
chunks failed: the rest can be reviewed, the failed ones retried) or
`failed`. The candidates are the same as the rule path's, evaluated against
the cards with `runs.evaluate`, reviewed and committed the same way.

The model is the one the Knowledge features use (Settings, with its data
approval); without one the run is refused with `model_unavailable` and the
rule path keeps working. The run records the model alias, the method
(`llm:default` for the shipped instructions, `llm:inline` for edited ones)
and the instructions and types it used.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from capabilities.bi_cards import catalog, extract, runs
from capabilities.bi_cards.schema import Registry, norm_key
from capabilities.bi_cards.staging import Staging, parse_kind
from capabilities.bi_cards.store import BiStoreError
from models.contracts import ModelClient

MAX_INSTRUCTIONS = 8000


@dataclass(frozen=True)
class AiRuntime:
    """What an AI run needs from the Host: the Knowledge model (None when
    none is set up) and a way to run work in the background."""

    model: Callable[[], tuple[ModelClient, str] | None]
    background: Callable[[str, Callable[[], None]], None]


def _types(reg: Registry, given: Any) -> list[str]:
    if given in (None, []):
        chosen = [t for t in extract.DEFAULT_TYPES if t in reg.types] or list(reg.types)
        return chosen
    if not isinstance(given, list) or not all(isinstance(t, str) for t in given):
        raise BiStoreError("types_invalid", "types 必須是卡片類型名稱清單")
    unknown = [t for t in given if t not in reg.types]
    if unknown:
        raise BiStoreError("types_invalid", f"schema 沒有這些類型：{'、'.join(unknown)}")
    return list(dict.fromkeys(given))


def start(
    workspace: Path,
    dataset: str,
    ai: AiRuntime | None,
    *,
    kind: str,
    source_id: str,
    instructions: Any,
    types: Any,
    actor: str,
) -> dict[str, Any]:
    """Start the AI path on a text source; the run is `extracting` until the
    background job ends."""
    staging = Staging(workspace, dataset)
    staging.store.refuse_write()
    source = staging.source(source_id)
    if source is None:
        raise BiStoreError("source_unknown", "找不到這個來源")
    if parse_kind(source["name"]) != "text":
        raise BiStoreError("source_not_text", "AI 判讀只讀文字或 Markdown 來源")
    reg = catalog.for_store(staging.store)
    scope = _types(reg, types)
    edited = isinstance(instructions, str) and instructions.strip()
    text = str(instructions).strip() if edited else extract.DEFAULT_INSTRUCTIONS
    if len(text) > MAX_INSTRUCTIONS:
        raise BiStoreError("instructions_too_long", f"判讀規則最多 {MAX_INSTRUCTIONS} 個字")
    chosen = ai.model() if ai is not None else None
    if chosen is None:
        raise BiStoreError(
            "model_unavailable",
            "沒有可用的模型：到 Settings 設定 Knowledge 使用的模型後再試；表格來源仍可用規則轉換",
        )
    model, alias = chosen
    run_id = staging.create_run(
        kind=kind,
        schema_ref=reg.ref,
        source_ids=[source_id],
        actor=actor,
        method_ref="llm:inline" if edited else "llm:default",
        model=alias,
    )
    staging.put_layout(
        run_id,
        {
            "mode": "llm",
            "types": scope,
            "instructions": text,
            "chunks": 0,
            "done": 0,
            "failures": [],
            "warnings": [],
        },
    )
    staging.set_status(run_id, "extracting")
    assert ai is not None
    ai.background(
        f"BI 判讀 {source['name']}",
        lambda: _work(workspace, dataset, run_id, model, alias, only=None),
    )
    return runs.run_view(staging, run_id)


def retry(workspace: Path, dataset: str, ai: AiRuntime | None, run_id: str) -> dict[str, Any]:
    """Run the failed chunks again; candidates already found are kept."""
    staging = Staging(workspace, dataset)
    staging.store.refuse_write()
    run = staging.run_row(run_id)
    layout = staging.layout(run_id) or {}
    if run is None:
        raise BiStoreError("run_unknown", "找不到這次執行")
    if layout.get("mode") != "llm" or run["status"] not in ("partial", "failed"):
        raise BiStoreError("run_closed", "這次執行沒有可以重試的段落")
    failed = [int(f["chunk"]) for f in layout.get("failures") or []]
    if not failed:
        raise BiStoreError("run_closed", "這次執行沒有可以重試的段落")
    chosen = ai.model() if ai is not None else None
    if chosen is None:
        raise BiStoreError("model_unavailable", "沒有可用的模型：到 Settings 設定後再試")
    model, alias = chosen
    staging.set_status(run_id, "extracting")
    assert ai is not None
    ai.background(
        f"BI 判讀重試 {run_id}",
        lambda: _work(workspace, dataset, run_id, model, alias, only=failed),
    )
    return runs.run_view(staging, run_id)


def _key(reg: Registry, candidate: dict[str, Any]) -> tuple[str, str]:
    return candidate["entity_type"], norm_key(extract.card_name(reg, candidate))


def _work(
    workspace: Path,
    dataset: str,
    run_id: str,
    model: ModelClient,
    alias: str,
    *,
    only: Sequence[int] | None,
) -> None:
    staging = Staging(workspace, dataset)
    try:
        _extract(staging, run_id, model, alias, only=only)
    except Exception as failure:  # noqa: BLE001 - the run shows every failure
        staging.set_status(run_id, "failed", error=f"extract_failed: {type(failure).__name__}")


def _extract(
    staging: Staging,
    run_id: str,
    model: ModelClient,
    alias: str,
    *,
    only: Sequence[int] | None,
) -> None:
    run = staging.run_row(run_id)
    layout = staging.layout(run_id) or {}
    assert run is not None
    reg = catalog.for_store(staging.store)
    source = staging.source(run["source_ids"][0]) or {}
    text = staging.source_bytes(run["source_ids"][0]).decode("utf-8-sig", errors="replace")

    def progress(done: int, total: int) -> None:
        layout.update(done=done, chunks=total)
        staging.put_layout(run_id, layout)

    result = extract.extract(
        model,
        alias,
        reg,
        text=text,
        source_id=str(source.get("id") or run["source_ids"][0]),
        source_name=str(source.get("name") or ""),
        types=layout["types"],
        instructions=layout["instructions"],
        known=extract.known_names(staging.store.card_rows()),
        only=only,
        on_chunk=progress,
    )
    found = staging.candidates(run_id) if only else []
    by_key = {_key(reg, c): c for c in found}
    for item in result.candidates:
        key = _key(reg, item)
        if key in by_key:
            extract.merge(by_key[key], item)
        else:
            item["id"] = f"c{len(by_key) + 1}"
            by_key[key] = item
    merged = [runs.evaluate(staging.store, reg, c) for c in by_key.values()]
    staging.put_candidates(run_id, merged)
    retried = set(only or [])
    kept = [f for f in layout.get("failures") or [] if int(f["chunk"]) not in retried]
    layout.update(
        chunks=result.chunks,
        done=result.chunks,
        failures=[*kept, *result.failures],
        warnings=[*(layout.get("warnings") or []), *result.warnings],
    )
    staging.put_layout(run_id, layout)
    if (staging.run_row(run_id) or {}).get("status") == "cancelled":
        return
    if not layout["failures"]:
        staging.set_status(run_id, "review")
    elif len(layout["failures"]) < result.chunks or merged:
        staging.set_status(run_id, "partial")
    else:
        staging.set_status(run_id, "failed", error="所有段落都沒有成功判讀")
