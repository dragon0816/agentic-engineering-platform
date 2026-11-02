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

Since BI vault phase V2 (`docs/phases/BI_VAULT.md` §5) the model reads the
source's current Markdown revision, recorded on the run (`markdown_rev`), so
evidence line numbers point into that revision; a retry reads the same one.
Documents (PDF, Word, PowerPoint) come here through their Markdown, and a
person may send a table source here too (`path: "ai"`, owner 2026-10-28).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from capabilities.bi_cards import catalog, extract, names, runs, source_markdown
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
    #: The data classes the host administrator approved for that model
    #: (`models.data_approval.approved_classes`); None when not checked here
    #: (tests that build a runtime by hand).
    approved: Callable[[], tuple[str, ...]] | None = field(default=None)


def check_classification(ai: AiRuntime | None, classification: str) -> None:
    """A source goes to the model only when its data class is approved for
    that model (owner proposal §3, §6: data classes and allowed models)."""
    if ai is None or ai.approved is None:
        return
    allowed = ai.approved()
    if classification not in allowed:
        shown = "、".join(allowed) or "沒有"
        raise BiStoreError(
            "classification_not_approved",
            f"來源的機密等級是 {classification}，但這個模型只核准 {shown} 的資料；"
            "請改用核准等級的來源，或請管理員在 Settings 核准這個等級",
        )


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
    method_ref: str | None = None,
    schema: tuple[Registry, str] | None = None,
    checks: list[dict[str, Any]] | None = None,
    folder: Any = None,
    skill_draft: Any = None,
    trial_schema: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Start the AI path on a text source; the run is `extracting` until the
    background job ends. A method run (phase 5) gives its `method_ref` and
    `checks`; a draft trial (phase 6) gives `schema` = (the draft's registry,
    its `draft:` ref). In a vault the source's `folder` picks the extract
    skill (knowledge repositories R3); the run keeps the skills' text, so a
    retry reads the same rules. `skill_draft` (a `knowledge.repo.skills.Skill`,
    BI T2) is a rule being tried, used in place of the vault's for this run.
    `trial_schema` is an unsaved schema being tried by Session A on the harness,
    kept with the run so a retry reads the same (`BI_BUILD_FLOW.md` §5)."""
    staging = Staging(workspace, dataset)
    staging.store.refuse_write()
    source = staging.source(source_id)
    if source is None:
        raise BiStoreError("source_unknown", "找不到這個來源")
    if parse_kind(source["name"]) == "unsupported":
        raise BiStoreError(
            "source_not_text", "AI 判讀只讀能轉成 Markdown 的來源（文件、文字或表格）"
        )
    if schema is None:
        reg = catalog.for_store(staging.store)
        schema = (reg, reg.ref)
    reg = schema[0]
    rules = _vault_rules(staging, folder, skill_draft)
    if rules is not None and types in (None, []) and rules["card_types"]:
        types = [t for t in rules["card_types"] if t in reg.types] or None
    scope = _types(reg, types)
    edited = isinstance(instructions, str) and instructions.strip()
    text = str(instructions).strip() if edited else extract.DEFAULT_INSTRUCTIONS
    if len(text) > MAX_INSTRUCTIONS:
        raise BiStoreError("instructions_too_long", f"判讀規則最多 {MAX_INSTRUCTIONS} 個字")
    check_classification(ai, source["classification"])
    chosen = ai.model() if ai is not None else None
    if chosen is None:
        raise BiStoreError(
            "model_unavailable",
            "沒有可用的模型：到 Settings 設定 Knowledge 使用的模型後再試；表格來源仍可用規則轉換",
        )
    model, alias = chosen
    rev, _ = source_markdown.current(staging, source_id)
    run_id = staging.create_run(
        kind=kind,
        schema_ref=schema[1],
        source_ids=[source_id],
        actor=actor,
        method_ref=method_ref or ("llm:inline" if edited else "llm:default"),
        model=alias,
        markdown_rev=rev,
    )
    staging.put_layout(
        run_id,
        {
            "mode": "llm",
            "types": scope,
            "instructions": text,
            "checks": checks or [],
            "chunks": 0,
            "done": 0,
            "failures": [],
            "warnings": [],
            **({"skills": rules} if rules is not None else {}),
            **({"trial_schema": trial_schema} if trial_schema is not None else {}),
        },
    )
    staging.set_status(run_id, "extracting")
    assert ai is not None
    ai.background(
        f"BI 判讀 {source['name']}",
        lambda: _work(workspace, dataset, run_id, model, alias, only=None),
    )
    return runs.run_view(staging, run_id)


def _vault_rules(staging: Staging, folder: Any, draft: Any = None) -> dict[str, Any] | None:
    """A vault's skills for a source in `folder`; None for a plain dataset,
    which keeps its domain notes (BI vault V11)."""
    vault_id = staging.store.vault_id
    if vault_id is None:
        return None
    from capabilities.bi_cards import vault, vault_skills

    return vault_skills.run_rules(
        vault.Vault(staging.store.workspace, vault_id).repo,
        vault_skills.checked_folder(folder),
        draft,
    )


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
    reg = runs.registry_for(staging, run)
    source = staging.source(run["source_ids"][0]) or {}
    if run.get("markdown_rev"):
        text = staging.markdown_text(run["source_ids"][0], int(run["markdown_rev"]))
    else:  # a run from before BI vault V2 read the original file
        text = staging.source_bytes(run["source_ids"][0]).decode("utf-8-sig", errors="replace")

    def progress(done: int, total: int) -> None:
        layout.update(done=done, chunks=total)
        staging.put_layout(run_id, layout)

    canonical = names.from_store(staging.store)  # the cards' aliases (BI D2)
    # A vault's run reads its skills; elsewhere the method's instructions carry the rules.
    notes = (
        str(layout["skills"].get("text") or "") if isinstance(layout.get("skills"), dict) else ""
    )
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
        domain_notes=notes,
    )
    found = staging.candidates(run_id) if only else []
    by_key = {_key(reg, c): c for c in found}
    for item in result.candidates:
        if canonical:
            _canonical_names(canonical, reg, item)
        key = _key(reg, item)
        if key in by_key:
            extract.merge(by_key[key], item)
        else:
            item["id"] = f"c{len(by_key) + 1}"
            by_key[key] = item
    checked = runs.apply_checks(list(by_key.values()), layout.get("checks"))
    merged = [runs.evaluate(staging.store, reg, c) for c in checked]
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


def _canonical_names(configured: names.Names, reg: Registry, item: dict[str, Any]) -> None:
    """A model candidate's name and link targets in their canonical spelling
    (the cards' `aliases`, then the configuration's `name_aliases`), before
    merging by name."""
    entity = reg.types.get(str(item.get("entity_type")))
    if entity is None:
        return
    for entry in item.get("fields") or []:
        definition = entity.get(str(entry.get("field")))
        if definition is None or not (definition.is_link or definition.name == entity.naming_field):
            continue
        value = entry.get("value")
        if isinstance(value, list):
            entry["value"] = list(dict.fromkeys(configured.canon(v) for v in value))
        elif isinstance(value, str):
            entry["value"] = configured.canon(value)
    if isinstance(item.get("name"), str):
        item["name"] = configured.canon(item["name"])
