"""Whether the schema needs a new type, field or allowed value, from the sources just added
(`docs/phases/BI_PAGE_SIMPLE.md` S2, acceptance F5).

The owner's step 2, part 1: 「根據新增的資料來建議是否要在schema新增類別，做法可以讓使用者按一
個button，系統給出建議」. It asks the model the schema-fit question alone, with the rules and
checks of `schema_fit`, so it does not depend on the extraction method an ingest will use and
writes no card. It costs the model only when a person presses the button.

Every suggestion carries a quote found in the source; what the model could not quote is left
out and counted. A row is a change or nothing (owner 2026-11-20: 「有就有，沒有就沒有」):
the model is not asked for questions, and an item that is only a question (an invented type
that already exists, say) is no row. 「不用改」 is an answer. A person applies a row or rejects
it, and a rejected row leaves the table at once with 復原 (`reopen`) as the way back: a new
field or allowed value goes through a draft, publish and upgrade, which a vault turns into
units on its version, not a new version (`schema_merge`); anything else is a draft edit.

The latest suggestion of a dataset is kept in its folder, so a reload shows it again.
"""

from __future__ import annotations

import copy
import json
import shutil
import threading
import time
import uuid
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any

from aep_bi.cards import catalog, extract, schema_fit, schema_versions
from aep_bi.cards.answer_cache import CachingModel
from aep_bi.cards.schema import Registry, norm_key
from aep_bi.cards.staging import Staging
from aep_bi.cards.store import BiStore, BiStoreError, now
from common.execution import TraceIdentifiers
from models.contracts import ModelClient, ModelMessage, ModelRequest, ModelRequirements

FILE = "schema-suggest.json"
OUTPUT_CONTRACT = "aep.bi.schema_suggest.v1"
#: Sources read per press: what a person can review, and a bound on what it costs.
MAX_SOURCES = 10
MAX_ATTEMPTS = 2
#: A row being added: one press at a time, and nothing decides it under the add.
APPLYING = "applying"
#: After this long an add is taken as stopped (the host restarted in the middle).
STUCK_SECONDS = 15 * 60
#: What a row may be: the three schema changes. A question is never a row (owner 2026-11-20).
KINDS = (
    schema_fit.EXTEND_SCHEMA,
    schema_fit.DICTIONARY_CHANGE,
    schema_fit.PROPOSE_TYPE,
)
_LOCK = threading.Lock()

SYSTEM = """You check whether the knowledge in one excerpt of a source fits a BI card schema.
You write no cards here: a person decides whether the schema needs a new type, field or
allowed value, and most sources need none.

The schema's card types and their fields:
{types}{notes}

Answer with one JSON object only: {{"items": [...]}}. For an item that fits (update_card or
create_card) give only "summary", "action", "card" and a short "quote". "quote" is always
copied exactly from the excerpt. Here do not answer needs_clarification: either the schema
needs a change you can name, or the item fits."""


def _path(store: BiStore) -> Path:
    return store.dir / FILE


def _read(store: BiStore) -> dict[str, Any] | None:
    try:
        held = json.loads(_path(store).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return held if isinstance(held, dict) else None


def _write(store: BiStore, value: Mapping[str, Any]) -> None:
    path = _path(store)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex[:8]}.tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=1), encoding="utf-8")
    schema_versions.replace(temporary, path)


def view(workspace: Path, dataset: str) -> dict[str, Any] | None:
    """The dataset's latest suggestion, or None."""
    return _read(BiStore(workspace, dataset))


def _read_by_runs(staging: Staging) -> set[str]:
    return {
        source_id
        for run in staging.run_rows()
        if run.get("kind") == "ingest"
        for source_id in run.get("source_ids") or ()
    }


def _chosen(staging: Staging, source_ids: Any, only_new: bool) -> tuple[list[dict[str, Any]], int]:
    """The sources to read, in the order given, and how many were left over the limit."""
    wanted = [str(s) for s in source_ids] if isinstance(source_ids, list) else []
    read = _read_by_runs(staging) if only_new else set()
    found = []
    for source_id in dict.fromkeys(wanted):
        source = staging.source(source_id)
        if source is None or not source.get("markdown_rev") or source_id in read:
            continue
        found.append(source)
    return found[:MAX_SOURCES], max(0, len(found) - MAX_SOURCES)


def start(
    workspace: Path,
    dataset: str,
    ai: Any,
    *,
    source_ids: Any,
    only_new: Any,
    actor: str,
) -> dict[str, Any]:
    """Read the sources in the background; the suggestion is `running` until it ends."""

    staging = Staging(workspace, dataset)
    store = staging.store
    store.refuse_write()
    held = _read(store)
    if held is not None and held.get("status") == "running":
        raise BiStoreError("suggest_running", "上一次的建議還在進行，請等它完成")
    sources, left = _chosen(staging, source_ids, only_new is True)
    if not sources:
        raise BiStoreError(
            "suggest_no_sources",
            "沒有可以看的來源：這個領域的來源都已經 ingest 過，或還沒轉檔；可以改選「選的來源」",
        )
    chosen = ai.model() if ai is not None else None
    if chosen is None:
        raise BiStoreError("model_unavailable", "沒有可用的模型：到 Settings 設定模型後再試")
    model, alias = chosen
    reg = catalog.for_store(store)
    state = {
        "id": uuid.uuid4().hex[:12],
        "status": "running",
        "at": now(),
        "by": actor,
        "schema": reg.ref,
        "model": alias,
        "sources": [{"id": s["id"], "name": s["name"]} for s in sources],
        "left_out": left,
        "done": 0,
        "seconds": None,
        "answers": {"asked": 0, "reused": 0, "input_tokens": 0, "output_tokens": 0},
        "items": [],
        "fits": 0,
        "unquoted": 0,
        "failures": [],
    }
    with _LOCK:
        _write(store, state)
    ai.background("BI 建議 schema", lambda: _work(workspace, dataset, state, model, alias, sources))
    return state


def _messages(
    reg: Registry, notes: str, chunk: extract.Chunk, name: str, problems: list[str]
) -> Any:
    system = SYSTEM.format(
        types=extract.describe_types(reg, list(reg.types)),
        notes="\n\nThe knowledge base's own rules for this source:\n" + notes.strip()
        if notes.strip()
        else "",
    )
    body = (
        f"Source: {name}, lines {chunk.line_start}-{chunk.line_end}\n\n"
        f"{extract.DATA_FENCE}\n{chunk.text}\n{extract.DATA_END}"
    )
    found = [
        ModelMessage(role="system", text=system + schema_fit.RULES),
        ModelMessage(role="user", text=body),
    ]
    if problems:
        found.append(
            ModelMessage(
                role="user",
                text="Your last answer could not be used: "
                + "; ".join(problems)
                + ". Answer again with the JSON object only.",
            )
        )
    return tuple(found)


def _shape(answer: Any) -> list[str]:
    if not isinstance(answer, dict):
        return ["the answer was not a JSON object"]
    if not isinstance(answer.get("items"), list):
        return ["`items` must be a list"]
    return []


def _usable(response: Any) -> bool:
    answer = response.structured_output
    if not isinstance(answer, dict):
        answer = extract._salvage(response.text)  # noqa: SLF001
    return not _shape(answer)


def _ask(
    model: ModelClient, alias: str, reg: Registry, notes: str, chunk: extract.Chunk, name: str
) -> tuple[dict[str, Any] | None, str]:
    """The model's answer for one chunk, or None and why."""
    problems: list[str] = []
    for _ in range(MAX_ATTEMPTS):
        response = model.generate(
            ModelRequest(
                trace=TraceIdentifiers(
                    trace_id=f"bi-suggest-{uuid.uuid4().hex}",
                    request_id=f"bi-suggest-{uuid.uuid4().hex}",
                    span_id=f"bi-chunk-{uuid.uuid4().hex[:16]}",
                ),
                model_alias=alias,
                messages=_messages(reg, notes, chunk, name, problems),
                requirements=ModelRequirements(structured_output=True),
                output_contract=OUTPUT_CONTRACT,
                max_output_tokens=extract.MAX_OUTPUT_TOKENS,
            )
        )
        if response.failure is not None:
            return None, f"模型沒有回應（{response.failure.code}）"
        answer = response.structured_output
        if not isinstance(answer, dict):
            answer = extract._salvage(response.text)  # noqa: SLF001
        problems = _shape(answer)
        if not problems:
            assert isinstance(answer, dict)
            return answer, ""
    return None, f"模型的回答 {MAX_ATTEMPTS} 次都不符合格式：{'; '.join(problems)}"


def _row_key(item: Mapping[str, Any]) -> tuple[str, ...]:
    """One row per proposed change, however many places say it."""
    raw = item.get("proposal")
    given: dict[str, Any] = raw if isinstance(raw, dict) else {}
    kind = next(k for k in KINDS if k in item["actions"])
    if kind == schema_fit.PROPOSE_TYPE:
        return (kind, norm_key(str(given.get("name") or "")))
    if kind in (schema_fit.EXTEND_SCHEMA, schema_fit.DICTIONARY_CHANGE):
        parts = (given.get("type"), given.get("field"), given.get("value"))
        return (kind, *(norm_key(str(p or "")) for p in parts))
    return (kind, norm_key(item["summary"]))


def _work(
    workspace: Path,
    dataset: str,
    state: dict[str, Any],
    model: ModelClient,
    alias: str,
    sources: list[dict[str, Any]],
) -> None:
    from aep_bi.cards import ai_runs, source_markdown

    started = time.monotonic()
    staging = Staging(workspace, dataset)
    store = staging.store
    reg = catalog.for_store(store)
    cached = CachingModel(model, store.dir, usable=_usable)
    rows: dict[tuple[str, ...], dict[str, Any]] = {}
    try:
        for done, source in enumerate(sources, start=1):
            _, text = source_markdown.current(staging, source["id"])
            rules = ai_runs._vault_rules(staging, ai_runs._folder_of(staging, source))  # noqa: SLF001
            notes = str((rules or {}).get("text") or "")
            for chunk in extract.chunks(text):
                answer, why = _ask(cached, alias, reg, notes, chunk, str(source["name"]))
                if answer is None:
                    state["failures"].append(
                        {
                            "source": source["name"],
                            "lines": [chunk.line_start, chunk.line_end],
                            "message": why,
                        }
                    )
                    continue
                for item in schema_fit.read_items(reg, answer, extract.locate, chunk, source["id"]):
                    if not item["locator"]:
                        state["unquoted"] += 1  # no quote in the source: never a suggestion
                        continue
                    if schema_fit.NEEDS_CLARIFICATION in item["actions"] and not set(
                        item["actions"]
                    ) & set(KINDS):
                        continue  # a question, not a change: no row (owner 2026-11-20)
                    if not set(item["actions"]) & set(KINDS):
                        state["fits"] += 1
                        continue
                    key = _row_key(item)
                    if key in rows:
                        rows[key]["places"] += 1
                        continue
                    rows[key] = _row(reg, item, source, len(rows) + 1)
            state["done"] = done
            state["items"] = list(rows.values())
            with _LOCK:
                _write(store, state)
        state["status"] = "done"
    except Exception as failure:  # noqa: BLE001 - said on the suggestion, never lost
        state["status"] = "failed"
        state["failures"].append({"source": "", "lines": [], "message": str(failure)[:300]})
    state["items"] = list(rows.values())
    state["seconds"] = round(time.monotonic() - started, 1)
    state["answers"] = {
        "asked": cached.misses,
        "reused": cached.hits,
        "input_tokens": cached.input_tokens,
        "output_tokens": cached.output_tokens,
    }
    with _LOCK:
        _write(store, state)


def _row(
    reg: Registry, item: Mapping[str, Any], source: Mapping[str, Any], number: int
) -> dict[str, Any]:
    kind = next(k for k in KINDS if k in item["actions"])
    raw = item.get("proposal")
    given: dict[str, Any] = raw if isinstance(raw, dict) else {}
    return {
        "id": f"s{number}",
        "kind": kind,
        "what": _what(kind, given, item),
        "proposal": given or None,
        "summary": item["summary"],
        "reason": item["reason"],
        "questions": item["questions"],
        "quote": item["excerpt"],
        "locator": item["locator"],
        "source_id": source["id"],
        "source": source["name"],
        "places": 1,
        "applies": _applies(reg, kind, given),
        "status": "proposed",
    }


def _what(kind: str, given: Mapping[str, Any], item: Mapping[str, Any]) -> str:
    """The suggestion in a few words, for the table."""
    if kind == schema_fit.EXTEND_SCHEMA:
        label = (
            (given.get("definition") or {}).get("label")
            if isinstance(given.get("definition"), dict)
            else ""
        )
        return f"新增欄位 {given.get('type')}.{given.get('field')}" + (
            f"（{label}）" if label else ""
        )
    if kind == schema_fit.DICTIONARY_CHANGE:
        mapped = f" → {given.get('maps_to')}" if given.get("maps_to") else ""
        return f"用語 {given.get('type') or ''}.{given.get('field')}：{given.get('value')}{mapped}"
    if kind == schema_fit.PROPOSE_TYPE:
        return f"新增類型 {given.get('name')}"
    return str(item["summary"])


def _applies(reg: Registry, kind: str, given: Mapping[str, Any]) -> bool:
    """Whether a press can add it as it is: a new field or allowed value that leaves a valid
    schema. Anything else, such as a list field with no values yet, needs a person and the AI."""
    if kind not in (schema_fit.EXTEND_SCHEMA, schema_fit.DICTIONARY_CHANGE):
        return False
    if kind == schema_fit.DICTIONARY_CHANGE and given.get("maps_to"):
        return False  # a synonym changes a definition: that is a version, for a person
    try:
        document = _added(copy.deepcopy(dict(reg.document)), {"kind": kind, "proposal": given})
    except BiStoreError:
        return False
    return not catalog.validate(document)[1]


def _find_row(state: Mapping[str, Any], row_id: Any) -> dict[str, Any]:
    row: dict[str, Any] | None = next(
        (r for r in state.get("items") or [] if r["id"] == row_id), None
    )
    if row is None:
        raise BiStoreError("suggest_row_unknown", "這次建議沒有這一列")
    return row


def _stuck(row: Mapping[str, Any]) -> bool:
    """An add that has run longer than any add takes: the host stopped in the middle."""
    started = str(row.get("applying_at") or "")
    try:
        since = time.time() - datetime.fromisoformat(started).timestamp()
    except ValueError:
        return True
    return since > STUCK_SECONDS


def _row_of(state: Mapping[str, Any], row_id: Any) -> dict[str, Any]:
    row = _find_row(state, row_id)
    if row["status"] == APPLYING and not _stuck(row):
        # A second press while the first still runs (an add takes half a minute on a
        # shared vault) would add it twice, or decide the row under the running add.
        raise BiStoreError("suggest_row_busy", "這一項正在加入，請等它完成")
    if row["status"] not in ("proposed", APPLYING):
        raise BiStoreError("suggest_row_decided", "這一列已經決定了")
    return row


def _held(store: BiStore, suggestion_id: Any) -> dict[str, Any]:
    state = _read(store)
    if state is None or state.get("id") != suggestion_id:
        raise BiStoreError("suggest_stale", "建議已經換成新的一次，請重新整理")
    return state


def reject(
    workspace: Path, dataset: str, suggestion_id: Any, row_id: Any, reason: Any, actor: str
) -> dict[str, Any]:
    store = BiStore(workspace, dataset)
    store.refuse_write()
    with _LOCK:
        state = _held(store, suggestion_id)
        row = _row_of(state, row_id)
        row.update(
            status="rejected", by=actor, decided_at=now(), reason_given=str(reason or "")[:300]
        )
        _write(store, state)
    return state


def reopen(workspace: Path, dataset: str, suggestion_id: Any, row_id: Any) -> dict[str, Any]:
    """Back to undecided (the owner's 「不小心選擇不要時，沒機會退回去」): a rejected row, or
    an add that stopped with the host. An added row is in the schema already; taking it
    out again is a schema change, not an undo."""
    store = BiStore(workspace, dataset)
    store.refuse_write()
    with _LOCK:
        state = _held(store, suggestion_id)
        row = _find_row(state, row_id)
        if row["status"] == "applied":
            raise BiStoreError(
                "suggest_row_applied",
                "這一項已經加入 schema；要拿掉請在 schema 草稿裡修改",
            )
        if row["status"] == APPLYING and not _stuck(row):
            raise BiStoreError("suggest_row_busy", "這一項正在加入，請等它完成")
        for key in ("by", "decided_at", "reason_given", "applying_at"):
            row.pop(key, None)
        row["status"] = "proposed"
        _write(store, state)
    return state


def apply(
    workspace: Path, dataset: str, suggestion_id: Any, row_id: Any, actor: str
) -> dict[str, Any]:
    """Add a field or an allowed value through the compatible path: in a vault it becomes
    units on the version, staged for the person's commit, never a new version."""
    store = BiStore(workspace, dataset)
    store.refuse_write()
    if store.vault_id is None:
        raise BiStoreError(
            "suggest_apply_vault_only",
            "只有知識庫可以直接加入；這個資料集請用「和 AI 調整 schema」",
        )
    with _LOCK:
        state = _held(store, suggestion_id)
        row = _row_of(state, row_id)
        if not row["applies"]:
            raise BiStoreError("suggest_not_direct", "這一項要先和 AI 討論定義，不能直接加入")
        row.update(status=APPLYING, applying_at=now(), by=actor)
        _write(store, state)
    try:
        _apply_row(workspace, dataset, store, row, actor)
    except BaseException:
        with _LOCK:
            held = _read(store)
            if held is not None and held.get("id") == suggestion_id:
                back = _find_row(held, row_id)
                if back["status"] == APPLYING:
                    back["status"] = "proposed"
                    back.pop("applying_at", None)
                    _write(store, held)
        raise
    after = schema_versions.state(workspace, dataset)
    with _LOCK:
        state = _held(store, suggestion_id)
        row = _find_row(state, row_id)
        row.pop("applying_at", None)
        row.update(status="applied", by=actor, decided_at=now(), schema=after["label"])
        _write(store, state)
    return {"suggestion": state, "schema": after}


def _apply_row(
    workspace: Path, dataset: str, store: BiStore, row: Mapping[str, Any], actor: str
) -> None:
    """Draft, publish and upgrade with the row's addition. The version published on the
    way is gone afterwards: the vault takes it as units (`Vault._schema_units`), and when
    the add stops before that it is removed here, so it is never offered as an upgrade."""
    before = catalog.for_store(store)
    made = schema_versions.create_draft(workspace, before.ref, f"建議：{row['what']}", actor)
    draft_id = made["draft"]["id"]
    published: dict[str, Any] | None = None
    try:
        document = _added(dict(made["document"]), row)
        saved = schema_versions.save_revision(
            workspace,
            draft_id,
            document=document,
            json_text=None,
            note=row["what"],
            source="ai",
            actor=actor,
        )
        if saved["errors"]:
            raise BiStoreError(
                "suggest_invalid",
                "加入後 schema 不成立："
                + "；".join(f"{e['path']}：{e['message']}" for e in saved["errors"][:3]),
            )
        published = schema_versions.publish(workspace, draft_id, saved["revision"], actor)
        preview = schema_versions.upgrade_preview(workspace, dataset, published["ref"])
        schema_versions.upgrade_apply(
            workspace, dataset, published["ref"], preview["preview_token"], actor
        )
    except BaseException:
        if published is not None and not published.get("already"):
            schema_id, _, version = str(published["ref"]).partition("@")
            if catalog.for_store(store).ref != published["ref"]:
                catalog.schema_path(workspace, schema_id, version).unlink(missing_ok=True)
        raise
    finally:
        # The draft was only the way in; what stays is the vault's units.
        shutil.rmtree(schema_versions.drafts_root(workspace) / draft_id, ignore_errors=True)


def _values(definition: Mapping[str, Any]) -> list[str]:
    """An enum's allowed values, under any of the names a model gives them."""
    for key in ("enum", "values", "allowed", "allowed_values"):
        given = definition.get(key)
        if isinstance(given, list) and given:
            return list(dict.fromkeys(str(v).strip() for v in given if str(v).strip()))
    return []


def _added(document: dict[str, Any], row: Mapping[str, Any]) -> dict[str, Any]:
    """`document` with the row's field or allowed value."""
    given = row["proposal"] or {}
    entity = next((t for t in document["types"] if t["name"] == given.get("type")), None)
    if entity is None:
        raise BiStoreError("suggest_type_unknown", f"schema 沒有類型 {given.get('type')}")
    fields = {f["name"]: f for f in entity["fields"]}
    if row["kind"] == schema_fit.EXTEND_SCHEMA:
        name = str(given["field"])
        if name in fields:
            raise BiStoreError("suggest_field_exists", f"{entity['name']} 已經有欄位 {name}")
        definition = dict(given.get("definition") or {})
        kind = str(definition.get("kind") or "str")
        entity["fields"].append(
            {
                "name": name,
                "label": str(definition.get("label") or name),
                "kind": kind,
                "class": str(definition.get("class") or "sourced"),
                "enum": _values(definition) if kind == "enum" else None,
                "aliases": [],
                # A required field is not an addition: existing cards lack it.
                "required": False,
                "default": None,
                "range": None,
                "link_to": list(definition.get("link_to") or []),
                "list": kind in ("list", "linklist"),
            }
        )
        return document
    item = fields.get(str(given.get("field")))
    if item is None or not isinstance(item.get("enum"), list):
        raise BiStoreError("suggest_not_enum", "這個欄位沒有允許值清單，請和 AI 討論")
    value = str(given.get("value") or "").strip()
    if not value or value in item["enum"]:
        raise BiStoreError("suggest_value_exists", f"允許值裡已經有「{value}」")
    item["enum"].append(value)
    return document
