"""Re-run a skill over a chosen scope and confirm only what differs.

Design: `docs/phases/BI_CARD_MODEL.md` §5.3. An expert changes a skill, re-runs it over
some sources, sees only differing values, and confirms a subset. Each source is an
ordinary AI run, kept as a trial so that it can never be committed by the run's own
review and adds no proposals. A value the same as the card's, and a value the model
did not find, are not listed: a model that found less must not clear anything. What
is confirmed goes through `commit_run` in one commit; a listed card that moved since
the list was made refuses the whole (`cards_changed`).

The first answer without `start` only counts the sources, since each costs model calls.
"""

from __future__ import annotations

import json
import re
import uuid
from pathlib import Path
from typing import Any

from capabilities.bi_cards import ai_runs, catalog, runs, vault
from capabilities.bi_cards.schema import Registry
from capabilities.bi_cards.staging import Staging, parse_kind
from capabilities.bi_cards.store import BiStoreError, PlannedRow, now
from knowledge.repo import repository as repo_engine

METHOD_PREFIX = runs.RERUN_PREFIX
_ID = re.compile(r"^[0-9a-f]{12}$")
#: A run in these states will not get more candidates.
_FINISHED = ("review", "partial", "failed", "cancelled")


def _path(staging: Staging, rerun_id: str) -> Path:
    if not _ID.match(rerun_id):
        raise BiStoreError("rerun_unknown", "找不到這次重跑")
    return Path(staging.dir) / "reruns" / f"{rerun_id}.json"


def _load(staging: Staging, rerun_id: str) -> dict[str, Any]:
    path = _path(staging, rerun_id)
    if not path.is_file():
        raise BiStoreError("rerun_unknown", "找不到這次重跑")
    found: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return found


def _save(staging: Staging, record: dict[str, Any]) -> None:
    path = _path(staging, record["id"])
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
    temporary.replace(path)


def _in_application(folder: str | None, application: str) -> bool:
    """A source folder in this home, in the layout of design §4 or the older one."""
    if folder is None:
        return False
    roots = (
        (f"{application}/sources",)
        if application.startswith("library/")
        else (f"applications/{application}/sources", f"sources/applications/{application}")
    )
    return any(folder == root or folder.startswith(root + "/") for root in roots)


def _scope(staging: Staging, given: dict[str, Any]) -> list[dict[str, Any]]:
    """The sources asked for that a model can read."""
    named = given.get("sources")
    if given.get("all") is True:
        application = str(given.get("application") or "").strip()
        vaulted = staging.store.vault_id is not None
        if vaulted and not application:
            raise BiStoreError("application_missing", "要重跑全部來源，請先選應用資料夾")
        chosen = [
            s
            for s in staging.sources()
            if not vaulted or _in_application(ai_runs._folder_of(staging, s), application)
        ]
    elif isinstance(named, list) and named:
        chosen = []
        for source_id in named:
            source = staging.source(str(source_id))
            if source is None:
                raise BiStoreError("source_unknown", "找不到這個來源", source_id=source_id)
            chosen.append(source)
    else:
        raise BiStoreError("sources_missing", "請選來源，或選全部")
    readable = [s for s in chosen if parse_kind(s["name"]) != "unsupported"]
    if not readable:
        raise BiStoreError("sources_missing", "這個範圍沒有 AI 能判讀的來源")
    return readable


def _refuse_old_skill(staging: Staging, sources: list[dict[str, Any]], revision: Any) -> None:
    """The person chose a revision: the sources' current extract skill must be it."""
    if revision is None:
        return
    for source in sources:
        rules = ai_runs._vault_rules(staging, ai_runs._folder_of(staging, source))
        used = [] if rules is None else [s for s in rules["skills"] if s["role"] == "extract"]
        if any(s["revision"] != revision for s in used):
            raise BiStoreError(
                "skill_changed", "這個 skill 已經有新版本，請重新選擇後再重跑", source=source["id"]
            )


def preview(
    workspace: Path, dataset: str, ai: ai_runs.AiRuntime | None, given: dict[str, Any], actor: str
) -> dict[str, Any]:
    """Count the sources; with `start`, run them. Writes no card."""
    staging = Staging(workspace, dataset)
    staging.store.refuse_write()
    sources = _scope(staging, given)
    listed = [{"id": s["id"], "name": s["name"]} for s in sources]
    if given.get("start") is not True:
        return {"started": False, "count": len(sources), "sources": listed}
    _refuse_old_skill(staging, sources, given.get("skill_revision"))
    # Nothing starts unless all of it can: a refusal here costs no model call.
    for source in sources:
        ai_runs.check_classification(ai, source["classification"])
    if ai is None or ai.model() is None:
        raise BiStoreError("model_unavailable", "沒有可用的模型：到 Settings 設定模型後再試")
    rerun_id = uuid.uuid4().hex[:12]
    record: dict[str, Any] = {
        "id": rerun_id,
        "dataset": dataset,
        "application": given.get("application"),
        "skill_revision": given.get("skill_revision"),
        "schema": catalog.for_store(staging.store).ref,
        "by": actor,
        "at": now(),
        "status": "running",
        "runs": [],
    }
    for source in sources:
        run = ai_runs.start(
            workspace,
            dataset,
            ai,
            kind="trial",
            source_id=source["id"],
            instructions=given.get("instructions"),
            types=given.get("types"),
            actor=actor,
            method_ref=f"{METHOD_PREFIX}{rerun_id}",
        )
        record["runs"].append(
            {"run_id": run["id"], "source_id": source["id"], "name": source["name"]}
        )
        _save(staging, record)
    return {
        "started": True,
        "count": len(sources),
        "sources": listed,
        "rerun": view(staging, record),
    }


def _same(a: Any, b: Any) -> bool:
    """The same value, whatever order a model lists it in."""
    if isinstance(a, list) and isinstance(b, list):
        return sorted(map(str, a)) == sorted(map(str, b))
    return bool(a == b)


def _items(staging: Staging, record: dict[str, Any], reg: Registry) -> list[dict[str, Any]]:
    """Only the values that differ from the cards now, the same value from several
    sources once. A field the model found nothing for is not a difference."""
    store = staging.store
    found: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for entry in record["runs"]:
        run_id = entry["run_id"]
        layout = staging.layout(run_id) or {}
        rules = layout.get("skills")
        skills = rules.get("skills", []) if isinstance(rules, dict) else []
        for candidate in staging.candidates(run_id):
            judged = runs.evaluate(store, reg, candidate)
            if judged["action"] == "skip":
                continue
            entity = reg.type(judged["entity_type"])
            card = store.find(entity.name, judged["canonical_key"])
            stored = store.fields(card["id"]) if card is not None else {}
            blocked = next((e["message"] for e in judged["errors"] if e.get("field") is None), None)
            for item in judged["fields"]:
                name, value = item["field"], item["value"]
                definition = entity.get(name)
                if value is None or definition is None or definition.klass == "derived":
                    continue
                current = stored.get(name)
                if current is not None and _same(current["value"], value):
                    continue
                if card is not None and name in entity.naming:
                    continue  # found by this name; a new name is a rename, not a difference
                problem = next(
                    (e["message"] for e in judged["errors"] if e.get("field") == name), blocked
                )
                proof = [
                    {**e, "source_name": entry["name"], "basis": item.get("basis")}
                    for e in item.get("evidence") or []
                ]
                key = (
                    entity.name,
                    judged["canonical_key"],
                    name,
                    json.dumps(value, ensure_ascii=False, sort_keys=True),
                )
                if key in found:
                    found[key]["evidence"].extend(proof)
                    continue
                found[key] = {
                    "id": f"{run_id}:{judged['id']}:{name}",
                    "entity_type": entity.name,
                    "canonical_key": judged["canonical_key"],
                    "name": str(judged.get("name") or judged["canonical_key"]),
                    "card_id": None if card is None else card["id"],
                    "base_version": judged["base_version"],
                    "field": name,
                    "label": definition.label,
                    "current": None if current is None else current["value"],
                    "new": value,
                    "person_set": current is not None and current["kind"] == "human",
                    "new_card": card is None,
                    "source": entry["name"],
                    "skills": skills,
                    "evidence": proof,
                    "problem": problem,
                }
    return list(found.values())


def view(staging: Staging, record: dict[str, Any]) -> dict[str, Any]:
    """Where the re-run is. Once every run ended, the list is made and kept: the
    confirm compares with the card versions that list was made on."""
    states = [staging.run_row(e["run_id"]) or {} for e in record["runs"]]
    if record["status"] == "running" and all(s.get("status") in _FINISHED for s in states):
        record["items"] = _items(staging, record, catalog.for_store(staging.store))
        record["status"] = "ready"
        _save(staging, record)
    return {
        "id": record["id"],
        "status": record["status"],
        "by": record["by"],
        "at": record["at"],
        "application": record.get("application"),
        "skill_revision": record.get("skill_revision"),
        "runs": [
            {
                "run_id": e["run_id"],
                "source": e["name"],
                "status": s.get("status"),
                "error": s.get("error"),
                "failures": len((staging.layout(e["run_id"]) or {}).get("failures") or []),
            }
            for e, s in zip(record["runs"], states, strict=True)
        ],
        "items": record.get("items", []),
        "commit": record.get("commit"),
    }


def detail(workspace: Path, dataset: str, rerun_id: str) -> dict[str, Any]:
    staging = Staging(workspace, dataset)
    return {"rerun": view(staging, _load(staging, rerun_id))}


def _refuse_incomplete(reg: Registry, items: list[dict[str, Any]]) -> None:
    """A new card takes its naming and required fields with it, or none of it."""
    chosen: dict[tuple[str, str], set[str]] = {}
    for item in items:
        if item["new_card"]:
            chosen.setdefault((item["entity_type"], item["canonical_key"]), set()).add(
                item["field"]
            )
    for (entity_type, key), fields in chosen.items():
        entity = reg.type(entity_type)
        needed = {d.name for d in entity.fields if d.required} | {entity.naming_field}
        missing = sorted(needed - fields)
        if missing:
            raise BiStoreError(
                "items_incomplete",
                f"新卡片「{key}」還要一起確認：{'、'.join(missing)}",
                card=key,
                fields=missing,
            )


def _rows(items: list[dict[str, Any]], rerun_id: str) -> list[tuple[PlannedRow, str, int | None]]:
    """One row per card, with only its confirmed values, which replace what is there:
    the person has just seen and confirmed each one, so a person's value is not
    turned into a proposal."""
    cards: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for item in items:
        cards.setdefault((item["entity_type"], item["canonical_key"]), []).append(item)
    rows = []
    for number, ((entity_type, key), chosen) in enumerate(sorted(cards.items()), start=1):
        planned = PlannedRow(
            row=number,
            entity_type=entity_type,
            canonical_key=key,
            name=chosen[0]["name"],
            values={i["field"]: i["new"] for i in chosen},
            synthetic=False,
            ref=f"rerun:{rerun_id}",
            evidence={i["field"]: i["evidence"] for i in chosen if i["evidence"]},
            overwrite=frozenset(i["field"] for i in chosen),
        )
        rows.append((planned, chosen[0]["id"], chosen[0]["base_version"]))
    return rows


def confirm(
    workspace: Path, dataset: str, rerun_id: str, given: dict[str, Any], actor: str
) -> dict[str, Any]:
    """Commit only the items named, in one commit. Nothing else is written."""
    staging = Staging(workspace, dataset)
    store = staging.store
    store.refuse_write()
    record = _load(staging, rerun_id)
    view(staging, record)
    if record["status"] == "confirmed":
        raise BiStoreError("run_committed", "這次重跑已經寫入過了", commit=record.get("commit"))
    if record["status"] != "ready":
        raise BiStoreError("run_closed", "這次重跑還沒有結束")
    wanted = given.get("items")
    if not isinstance(wanted, list) or not wanted:
        raise BiStoreError("items_missing", "請選要確認的差異")
    listed = {item["id"]: item for item in record["items"]}
    unknown = [i for i in wanted if i not in listed]
    if unknown:
        raise BiStoreError("item_unknown", "這筆差異不在清單裡", items=unknown)
    items = [listed[i] for i in dict.fromkeys(wanted)]
    blocked = [i["id"] for i in items if i["problem"]]
    if blocked:
        raise BiStoreError("item_blocked", "有差異無法直接寫入，請先處理", items=blocked)
    seen = [(i["entity_type"], i["canonical_key"], i["field"]) for i in items]
    if len(set(seen)) != len(seen):
        raise BiStoreError("items_conflict", "同一個欄位只能確認一個新值")
    reg = catalog.for_store(store)
    if reg.ref != record["schema"]:
        raise BiStoreError("schema_changed", "schema 在重跑後改了，請重跑")
    _refuse_incomplete(reg, items)
    run_id = staging.create_run(
        kind="ingest",
        method_ref=f"{METHOD_PREFIX}{rerun_id}",
        schema_ref=reg.ref,
        model=None,
        source_ids=[e["source_id"] for e in record["runs"]],
        actor=actor,
    )
    skills = {f"{s['name']} rev {s['revision']}" for i in items for s in i["skills"]}
    purpose = f"重跑差異確認：{len(items)} 個值" + (
        f"（{'、'.join(sorted(skills))}）" if skills else ""
    )
    with vault.purpose(purpose[: repo_engine.MAX_PURPOSE]):
        applied = store.commit_run(
            run_id, _rows(items, rerun_id), filename=f"重跑 {rerun_id}", actor=actor
        )
    result = {
        "import_id": applied.import_id,
        "created": applied.created,
        "updated": applied.updated,
        "values": len(items),
        "at": now(),
        "by": actor,
    }
    staging.set_status(run_id, "committed", commit_result=result)
    record.update(status="confirmed", commit=result)
    _save(staging, record)
    return {"commit": result}
