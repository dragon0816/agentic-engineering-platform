"""How each knowledge item of a source fits the schema (Phase 2, proposal §8.1).

An AI run of a vault records, per item of the source, an action and why. Update and
create go through the run's candidates, which say which of the two it really is.
Content the schema cannot hold yet is kept here, on the run, for a person: nothing
registers without review. An approved `extend_schema` becomes a proposal in the home's
profile, for the existing merge (`profile_merge`). An approved `dictionary_change` or
`propose_type` is a recorded design decision; a schema version is still Session A's.
A `propose_type` without its four answers, or anything the model cannot back with the
source, is `needs_clarification`, never dropped.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from aep_bi.cards import catalog, profile
from aep_bi.cards.schema import Registry, norm_key
from aep_bi.cards.staging import Staging
from aep_bi.cards.store import BiStoreError, now

UPDATE_CARD, CREATE_CARD = "update_card", "create_card"
DICTIONARY_CHANGE, EXTEND_SCHEMA = "dictionary_change", "extend_schema"
PROPOSE_TYPE, NEEDS_CLARIFICATION = "propose_type", "needs_clarification"
ACTIONS = (
    UPDATE_CARD,
    CREATE_CARD,
    DICTIONARY_CHANGE,
    EXTEND_SCHEMA,
    PROPOSE_TYPE,
    NEEDS_CLARIFICATION,
)
#: The actions a person reviews here; the others are the candidates' review.
REVIEWED = frozenset({DICTIONARY_CHANGE, EXTEND_SCHEMA, PROPOSE_TYPE, NEEDS_CLARIFICATION})
PROPOSED, THROUGH_CANDIDATE = "proposed", "through_candidate"
DECISIONS = ("approved", "rejected", NEEDS_CLARIFICATION)
#: A new type's four necessary answers (proposal §8.1 B).
FOUR_ANSWERS = {
    "unit_boundary": "一張卡代表什麼、何時算同一張",
    "why_not_existing": "為何既有卡型無法沿用或擴充",
    "why_independent": "為何需要獨立管理",
    "business_use": "支援哪個查詢、分析或決策",
}
NO_REASON = "模型沒有說明理由"

RULES = """

Schema fit: also add to your JSON answer an entry for every knowledge item of the excerpt:
  "items": [{"summary": "...", "action": ["..."], "reason": "...", "quote": "...",
             "card": "<card name, for update_card or create_card>", "questions": ["..."],
             "proposal": {...}}]
Check in this order, and prefer reusing what exists:
1. update_card: the same thing, with new data or evidence. 2. create_card: a new thing of a
kind the schema has. 3. dictionary_change: only a name, synonym or allowed value differs;
proposal {"type", "field", "value", "maps_to"}. 4. extend_schema: the kind is right but a needed
field is missing; proposal {"type", "field", "definition": {"label", "kind", "class", ...}},
with "kind" one of
str, int, float, bool, date, enum, list, link, linklist and "class" one of sourced, judgement.
5. propose_type: no type can reasonably hold it and it needs managing on its own; proposal
{"name", "definition", "unit_boundary", "why_not_existing", "why_independent", "business_use"},
each answered specifically. needs_clarification: you cannot tell; say what to ask in "questions".
A new market, company or word, missing data, or many empty values never justify a new type.
Actions may combine, such as ["update_card", "extend_schema"]. Keep content that does not fit
here with its quote; do not force it into a card. A person reviews every schema change.
Write "summary", "reason" and "questions" in the language of the source."""


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _clarify(item: dict[str, Any], gone: str, question: str) -> None:
    item["actions"] = [a for a in item["actions"] if a != gone]
    if NEEDS_CLARIFICATION not in item["actions"]:
        item["actions"].append(NEEDS_CLARIFICATION)
    item["questions"].append(question)


def _checked_proposal(reg: Registry, item: dict[str, Any], raw: Any) -> None:
    """Turn an action whose proposal cannot stand into a question. The proposal stays
    on the item either way, for the person: approving needs the question settled."""
    given = raw if isinstance(raw, dict) else {}
    item["proposal"] = given or None
    if PROPOSE_TYPE in item["actions"]:
        missing = [label for key, label in FOUR_ANSWERS.items() if not _text(given.get(key))]
        name = _text(given.get("name"))
        if missing or not name:
            what = "、".join(missing) or "新卡型的名稱"
            _clarify(item, PROPOSE_TYPE, f"新卡型提案缺少必要說明：{what}")
        elif name in reg.types:
            _clarify(item, PROPOSE_TYPE, f"schema 已經有類型 {name}，要不要沿用？")
    if EXTEND_SCHEMA in item["actions"]:
        entity = reg.types.get(_text(given.get("type")))
        field = _text(given.get("field"))
        if entity is None or not field or not isinstance(given.get("definition"), dict):
            _clarify(item, EXTEND_SCHEMA, "欄位提案要有既有類型、欄位名稱和定義")
        elif entity.get(field) is not None:
            _clarify(item, EXTEND_SCHEMA, f"{entity.name} 已經有欄位 {field}，要不要沿用？")
        elif given["definition"].get("kind") not in catalog.KINDS or given["definition"].get(
            "class"
        ) not in ("sourced", "judgement"):
            _clarify(item, EXTEND_SCHEMA, "欄位定義的 kind 或 class 不是 schema 允許的值")
    if DICTIONARY_CHANGE in item["actions"]:
        if not _text(given.get("field")) or not _text(given.get("value")):
            _clarify(item, DICTIONARY_CHANGE, "字典調整要有欄位和用語")


def read_items(
    reg: Registry, answer: Mapping[str, Any], locate: Any, chunk: Any, source_id: str
) -> list[dict[str, Any]]:
    """The model's items, checked. Nothing the model said is dropped: what cannot be
    backed by the source or lacks its answers becomes a question for a person."""
    found: list[dict[str, Any]] = []
    raw = answer.get("items")
    for entry in raw if isinstance(raw, list) else []:
        if not isinstance(entry, dict):
            continue
        said = entry.get("action")
        said = said if isinstance(said, list) else [said]
        actions = list(dict.fromkeys(str(a) for a in said if a in ACTIONS))
        item: dict[str, Any] = {
            "summary": _text(entry.get("summary"))[:500],
            "actions": actions or [NEEDS_CLARIFICATION],
            "reason": _text(entry.get("reason"))[:1000] or NO_REASON,
            "questions": [_text(q)[:300] for q in entry.get("questions") or () if _text(q)]
            if isinstance(entry.get("questions"), list)
            else [],
            "card": _text(entry.get("card"))[:200],
            "model_actions": [str(a) for a in said if a is not None],
            "proposal": None,
            "source_id": source_id,
            "locator": None,
            "excerpt": "",
            "schema": reg.ref,
        }
        if not actions:
            item["questions"].append(f"模型提出的判定「{said}」無法辨識")
        place = locate(entry.get("quote"), chunk)
        if place is not None:
            item["locator"] = place
            item["excerpt"] = _text(entry.get("quote"))[:500]
        elif set(item["actions"]) & REVIEWED:
            item["actions"] = [
                a
                if a not in (EXTEND_SCHEMA, DICTIONARY_CHANGE, PROPOSE_TYPE)
                else NEEDS_CLARIFICATION
                for a in item["actions"]
            ]
            item["actions"] = list(dict.fromkeys(item["actions"]))
            item["questions"].append("模型引用的原文不在來源中，請對照來源確認")
        _checked_proposal(reg, item, entry.get("proposal"))
        if item["questions"] and not set(item["actions"]) & REVIEWED:
            # A question on a plain update or create would go unseen in the candidates' review.
            item["actions"].append(NEEDS_CLARIFICATION)
        found.append(item)
    return found


def merge_items(
    held: list[dict[str, Any]], found: list[dict[str, Any]], candidates: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """A run's items with these added, one per (actions, summary), each candidate
    with an item saying whether it updates or creates. Decisions already made stay."""
    keys = {(tuple(i["actions"]), norm_key(i["summary"]), norm_key(i["card"])) for i in held}
    items = list(held)
    for item in found:
        key = (tuple(item["actions"]), norm_key(item["summary"]), norm_key(item["card"]))
        if key not in keys:
            keys.add(key)
            items.append({**item, "id": "", "status": None})
    by_name = {norm_key(c.get("name") or ""): c for c in candidates}
    told = set()
    for item in items:
        candidate = by_name.get(norm_key(item["card"])) if item["card"] else None
        if candidate is not None:
            told.add(norm_key(item["card"]))
            _settle(item, candidate)
        elif set(item["actions"]) & {UPDATE_CARD, CREATE_CARD}:
            # It named no card the run proposes, so its content has no other home.
            item["actions"] = [a for a in item["actions"] if a in REVIEWED] or [NEEDS_CLARIFICATION]
            item["questions"] = [*item["questions"], "模型沒有為這項知識提出候選卡"]
    for name, candidate in by_name.items():
        if name and name not in told:
            item = {
                "summary": str(candidate.get("name") or ""),
                "actions": [],
                "reason": NO_REASON,
                "questions": [],
                "card": str(candidate.get("name") or ""),
                "proposal": None,
                "source_id": "",
                "locator": None,
                "excerpt": "",
                "schema": "",
                "id": "",
                "status": None,
            }
            _settle(item, candidate)
            items.append(item)
    for number, item in enumerate(items, start=1):
        item["id"] = item["id"] or f"i{number}"
        if item["status"] is None or item["status"] in (PROPOSED, THROUGH_CANDIDATE):
            item["status"] = PROPOSED if set(item["actions"]) & REVIEWED else THROUGH_CANDIDATE
    return items


def _settle(item: dict[str, Any], candidate: Mapping[str, Any]) -> None:
    """The candidate says which of update and create it is, whatever the model thought."""
    real = CREATE_CARD if candidate.get("action") == "create" else UPDATE_CARD
    others = [a for a in item["actions"] if a not in (UPDATE_CARD, CREATE_CARD)]
    item["actions"] = [real, *others]
    matched = candidate.get("match_ids") or ()
    item["target_card"] = matched[0] if real == UPDATE_CARD and matched else None


def decide(
    workspace: Path,
    dataset: str,
    run_id: str,
    item_id: str,
    status: Any,
    reason: Any,
    *,
    actor: str,
) -> dict[str, Any]:
    """A person's review of one item. Only this registers anything, and only an
    approved `extend_schema` goes further: into the profile, for its own merge."""
    staging = Staging(workspace, dataset)
    run = staging.run_row(run_id)
    if run is None:
        raise BiStoreError("run_unknown", "找不到這次執行")
    if run["kind"] == "trial":
        raise BiStoreError("run_trial", "試跑的結果不能寫入；請用同樣的來源正式匯入")
    layout = staging.layout(run_id) or {}
    item = next((i for i in layout.get("items") or [] if i["id"] == item_id), None)
    if item is None:
        raise BiStoreError("fit_item_unknown", "這次執行沒有這個知識項目")
    if status not in DECISIONS:
        raise BiStoreError("fit_status_invalid", "決定只能是核准、退回或待釐清")
    if item["status"] == THROUGH_CANDIDATE:
        raise BiStoreError("fit_item_not_reviewed", "這一項由候選卡審核")
    if item["status"] in ("approved", "rejected"):
        raise BiStoreError("fit_item_decided", "這一項已經決定了")
    why = _text(reason)
    if status != "approved" and not why:
        raise BiStoreError("reason_required", "退回或待釐清要寫理由")
    if status == "approved":
        if NEEDS_CLARIFICATION in item["actions"]:
            raise BiStoreError("fit_needs_clarification", "這一項還有待釐清的問題，不能核准")
        if EXTEND_SCHEMA in item["actions"]:
            _to_profile(staging, layout, item)
    item.update(status=status, decided_by=actor, decided_at=now(), decision_reason=why)
    staging.put_layout(run_id, layout)
    return {"item": item}


def _to_profile(staging: Staging, layout: Mapping[str, Any], item: Mapping[str, Any]) -> None:
    """The field proposal in the home's profile, staged for the person's commit."""
    from aep_bi.cards import vault

    store = staging.store
    rules = layout.get("skills") if isinstance(layout.get("skills"), dict) else {}
    home = str((rules or {}).get("home") or "")
    if store.vault_id is None or not home:
        raise BiStoreError("fit_home_unknown", "這份來源不屬於任何 application，欄位提案沒有地方放")
    target = vault.Vault(store.workspace, store.vault_id)
    with target.lock:
        units = target.repo.working_units()
        document = profile.read(target.repo, home, units)
        if document is None:
            raise BiStoreError("profile_missing", f"{home} 還沒有 profile，請先建立")
        proposal = item["proposal"]
        held = list(document.get("proposals") or [])
        if not any(p["type"] == proposal["type"] and p["field"] == proposal["field"] for p in held):
            held.append(
                {
                    "type": proposal["type"],
                    "field": proposal["field"],
                    "definition": proposal["definition"],
                    "reason": item["reason"],
                }
            )
            kept = {k: document[k] for k in ("format", "application", "types") if k in document}
            profile.stage(target.repo, home, {**kept, "proposals": held}, catalog.for_store(store))
    target.rebuild()
