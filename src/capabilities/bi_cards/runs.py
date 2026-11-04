"""Ingest runs of a BI dataset: candidates, review and commit.

BI ingest phase 1 (`docs/phases/BI_INGEST.md` §4, §8; contract in
`docs/CONTRACTS.md` "BI ingest runs"). A run turns one source into candidate
cards in the staging store; nothing reaches the dataset's cards until the
person accepts candidates and commits. Phase 1 has the rule path for a CSV or
TSV source, built on the Case A importer, so every value carries its cell as
evidence. Phase 3 adds recipes (`recipes.py`): one Markdown report, Excel
workbook or CSV/TSV read as several tables (`readers.py`), several passes,
and the run's tables and passes kept as its layout. The AI path comes later;
every path produces the same candidates.

Since BI vault phase V2 (`docs/phases/BI_VAULT.md` §5) the rule path reads
the source's current Markdown revision (`source_markdown.py`), not the
original file, and the run records that revision (`markdown_rev`). Evidence
of a CSV/TSV or Excel value therefore points at the line of its row in that
revision (`{"table", "line", "column"}`, plus `"sheet"` for Excel), as a
Markdown report's already did.

Every candidate is evaluated against the cards as they are now: whether it
matches a card (exactly, or only loosely, which needs the person's choice),
the card version the review saw, the diff per field and the hard errors. A
commit writes all accepted candidates at once or nothing, refused when a card
moved on after the review (`cards_changed`), and a run commits only once.
"""

from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import Any

from capabilities.bi_cards import (
    catalog,
    importer,
    names,
    readers,
    recipes,
    schema_versions,
    source_markdown,
)
from capabilities.bi_cards.card_model import reference_id
from capabilities.bi_cards.schema import FieldDef, Registry, TypeDef, norm_key
from capabilities.bi_cards.staging import Staging, parse_kind
from capabilities.bi_cards.store import BiStore, BiStoreError, PlannedRow, new_states, now

MAX_EXCERPT = 500
WRITABLE = ("create", "update")


#: The method of a run started by a re-run (`rerun.py`).
RERUN_PREFIX = "rerun:"


def _table_csv(table: dict[str, Any]) -> tuple[str, list[int]]:
    """A Markdown table as CSV text for the Case A reader, and the Markdown
    line of each data row it will number from 2 (blank rows are skipped, as
    the reader skips them)."""
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    columns = [str(c) for c in table["columns"]]
    writer.writerow(columns)
    lines = []
    for row in table["rows"]:
        values = [str(row["cells"].get(c, "")) for c in columns]
        if not any(v.strip() for v in values):
            continue
        writer.writerow(values)
        lines.append(int(row["row"]))
    return out.getvalue(), lines


# -- evaluation ------------------------------------------------------------


def _values(candidate: dict[str, Any]) -> dict[str, Any]:
    return {f["field"]: f["value"] for f in candidate["fields"] if f["value"] is not None}


def _similar(store: BiStore, entity_type: str, key: str) -> list[Any]:
    """Cards of the type whose key equals `key` ignoring spaces, punctuation and case."""
    wanted = norm_key(key)
    return [
        card
        for card in store.card_rows()
        if card["entity_type"] == entity_type
        and card["canonical_key"] != key
        and norm_key(card["canonical_key"]) == wanted
    ]


#: An AI run never settles these on a card that exists: a person does, on the proposal.
PROTECTED_FIELDS = ("confidence", "evidence_grade")
VERIFIED = "verified"
SAME_NAME = "same_name_other_type"
MERGES = ("fill", "join", "proposal", "same", "human_kept", "bookkeeping", "take", "capped")


def _fill(definition: Any, item: dict[str, Any]) -> None:
    """An empty value is filled, but an AI run never writes `verified`: the highest level
    below it is stored, and the model's claim is a proposal for a person."""
    item["merge"] = "fill"
    if item["field"] == "confidence" and item["value"] == VERIFIED:
        lower = [v for v in (definition.enum or ()) if v != VERIFIED] if definition else []
        item["capped"] = lower[0] if lower else None
        item["merge"] = "capped"


def _merge_field(definition: Any, item: dict[str, Any], stored: Any) -> None:
    """How an AI run's value meets the card, as an import's does (`BI_CARD_PAGE_IMPORT.md`
    §4): an empty value is filled, a list joined, a differing value becomes a proposal,
    never an overwrite. `take` is a person choosing this value, on this field."""
    from capabilities.bi_cards.page_import import _joined, _later

    name, value = item["field"], item["value"]
    protected = name in PROTECTED_FIELDS
    item["protected"] = protected
    item.pop("merged", None)
    item.pop("capped", None)
    chosen = (item.get("take_new") or item.get("basis") == "human") and not protected
    is_list = stored is not None and (
        (definition is not None and definition.is_list) or isinstance(stored["value"], list)
    )
    if stored is None:
        _fill(definition, item)
    elif stored["value"] == value:
        item["merge"] = "same"
    elif chosen:
        item["merge"] = "take"
    elif is_list and _joined(stored["value"], value) == stored["value"]:
        # All of it is on the card already, whoever set it: nothing to write or propose.
        item["merge"] = "same"
        item["merged"] = stored["value"]
    elif stored["kind"] == "human":
        item["merge"] = "human_kept"
    elif protected:
        item["merge"] = "proposal"
    elif definition is not None and definition.klass == "derived":
        item["merge"] = "bookkeeping"
        item["later"] = _later(value, stored["value"])
    elif is_list:
        item["merge"] = "join"
        item["merged"] = _joined(stored["value"], value)
    else:
        item["merge"] = "proposal"


def merge_counts(candidates: list[dict[str, Any]]) -> dict[str, int]:
    """What an AI run would do to cards that exist, and the conflicts inside the run."""
    counts = dict.fromkeys(MERGES, 0)
    for candidate in candidates:
        if candidate.get("review") == "rejected" or candidate.get("action") == "skip":
            continue
        for item in candidate["fields"]:
            if item.get("merge") == "capped":
                counts["capped"] += 1
                counts["proposal"] += 1  # the model's claim, wherever the card is new or not
            elif candidate.get("match") == "existing" and item.get("merge") in counts:
                counts[item["merge"]] += 1
            counts["proposal"] += len(item.get("alternatives") or ())
    return counts


def evaluate(store: BiStore, reg: Registry, candidate: dict[str, Any]) -> dict[str, Any]:
    """Recompute match, base version, per-field diff, action and errors
    against the cards now; the review state and edits are kept."""
    entity = reg.type(candidate["entity_type"])
    values = _values(candidate)
    choice = candidate.get("choice") or {}
    errors: list[dict[str, Any]] = []
    key = importer.canonical_key(entity, values)
    card = None
    match, match_ids = "new", []
    if choice.get("action") == "update" and choice.get("card_id"):
        card = store.card(str(choice["card_id"]))
        if card is None or card["entity_type"] != entity.name:
            errors.append(
                {"code": "match_unresolved", "message": "選擇的卡片不存在", "field": None}
            )
            card = None
        else:
            key = str(card["canonical_key"])
            match, match_ids = "existing", [card["id"]]
    elif key:
        card = store.find(entity.name, key)
        if card is not None:
            match, match_ids = "existing", [card["id"]]
        elif choice.get("action") != "create":
            similar = _similar(store, entity.name, key)
            if similar:
                match, match_ids = "ambiguous", [c["id"] for c in similar]
                errors.append(
                    {
                        "code": "match_unresolved",
                        "message": "有名稱相近的卡片，請選擇新建、合併到既有卡片或略過",
                        "field": None,
                    }
                )
    candidate["canonical_key"] = key
    candidate["match"], candidate["match_ids"] = match, match_ids
    candidate["base_version"] = None if card is None else int(card["version"])
    current = store.fields(card["id"]) if card is not None else {}
    changes = 0
    for item in candidate["fields"]:
        stored = current.get(item["field"])
        item["current"] = None if stored is None else stored["value"]
        if card is None:
            item["protected"], _ = False, item.pop("capped", None)
            _fill(entity.get(item["field"]), item)
        else:
            _merge_field(entity.get(item["field"]), item, stored)
        if stored is None:
            item["change"] = "add"
            changes += 1
        elif stored["value"] == item["value"]:
            item["change"] = "same"
        elif stored["kind"] == "human":
            item["change"] = "human_kept"
            changes += 1  # written as a proposal next to the person's value
        else:
            item["change"] = "change"
            changes += 1
    if card is not None:
        changes += len(
            new_states(
                candidate.get("states") or {},
                {name: item["value"] for name, item in current.items()},
                store.field_states(card["id"]),
            )
        )
    if choice.get("action") == "skip":
        action = "skip"
        errors = []  # the person chose to leave it out
    elif not key:
        action = "skip"
        errors.append(
            {"code": "name_missing", "message": f"沒有{entity.naming_field}", "field": None}
        )
    elif card is None:
        action = "create"
        for definition in entity.fields:
            if definition.required and values.get(definition.name) in (None, "", []):
                errors.append(
                    {
                        "code": "required_missing",
                        "message": f"新卡片缺少必填欄位：{definition.label}",
                        "field": definition.name,
                    }
                )
    else:
        action = "update" if changes else "unchanged"
    candidate["action"] = action
    # Values the model gave that do not fit the schema (AI path) stay errors
    # until the person edits the field.
    errors.extend(candidate.get("value_errors") or [])
    candidate["errors"] = errors
    _mark_same_name(store, candidate)
    return candidate


def unconfirmed_same_name(candidate: dict[str, Any]) -> list[dict[str, str]]:
    """The cards of another type a new card's name also answers, not yet looked at."""
    confirmed = candidate.get("same_name_confirmed") or []
    return [c for c in candidate.get("same_name") or [] if c["id"] not in confirmed]


def _mark_same_name(store: BiStore, candidate: dict[str, Any]) -> None:
    """An AI run tends to make a card beside one of another type for the same company.
    Never merged: a person says whether it is another thing (V on R6: 0 → 9 on 3 chunks).
    Only a model's candidates hold `value_errors`: an import's rows are the person's."""
    if "value_errors" not in candidate:
        return
    candidate["warnings"] = [w for w in candidate["warnings"] if w["code"] != SAME_NAME]
    candidate["same_name"] = []
    if candidate["action"] != "create":
        return
    table = names.every_name(store)
    aliases: Any = next((f["value"] for f in candidate["fields"] if f["field"] == names.FIELD), [])
    wanted = [
        candidate.get("name"),
        candidate["canonical_key"],
        *(aliases if isinstance(aliases, list) else [aliases]),
    ]
    others = {
        card["id"]: card
        for name in wanted
        for card in table.get(norm_key(name or ""), [])
        if card["type"] != candidate["entity_type"]
    }
    candidate["same_name"] = sorted(others.values(), key=lambda c: (c["type"], c["name"]))
    for card in candidate["same_name"]:
        candidate["warnings"].append(
            {
                "code": SAME_NAME,
                "message": f"已經有同名的 {card['type']} 卡「{card['name']}」："
                "同一個對象就不要新建；確認是不同的對象才接受",
            }
        )
    if candidate["review"] == "accepted" and unconfirmed_same_name(candidate):
        candidate["review"] = "pending"  # the card appeared after the person accepted


def _diff_view(candidate: dict[str, Any]) -> Any:
    return (
        candidate["match"],
        candidate["match_ids"],
        candidate["base_version"],
        candidate["action"],
        [c["id"] for c in unconfirmed_same_name(candidate)],
        [(f["field"], f["current"], f["change"]) for f in candidate["fields"]],
    )


# -- the rule path -----------------------------------------------------------


def _candidates_from_preview(
    prepared: importer.Preview, source: dict[str, Any], lines: list[int]
) -> list[dict[str, Any]]:
    header_of = {c["field"]: c["source"] for c in prepared.columns if c["field"]}
    found = []
    for row in prepared.rows:
        planned = prepared.planned.get(row["row"])
        fields = []
        for cell in row["fields"]:
            if cell["normalized"] is None:
                continue
            raw = str(cell["raw"] or "")
            from_source = bool(raw.strip()) and cell["field"] in header_of
            fields.append(
                {
                    "field": cell["field"],
                    "value": cell["normalized"],
                    "basis": "fact" if from_source else "unknown",
                    "evidence": (
                        [
                            {
                                "source_id": source["id"],
                                "locator": {
                                    "table": 0,
                                    "line": lines[row["row"] - 2],
                                    "column": header_of[cell["field"]],
                                },
                                "excerpt": raw[:MAX_EXCERPT],
                            }
                        ]
                        if from_source
                        else []
                    ),
                    "current": None,
                    "change": "add",
                }
            )
        skipped = any(w["code"] == "row_skipped" for w in row["warnings"])
        found.append(
            {
                "id": f"r{row['row']}",
                "entity_type": prepared.entity_type,
                "canonical_key": row["canonical_key"],
                "name": planned.name if planned is not None else "",
                "synthetic": bool(planned.synthetic) if planned is not None else False,
                "match": "new",
                "match_ids": [],
                "action": "skip",
                "review": "rejected" if skipped else "pending",
                "choice": {"action": "skip"} if skipped else None,
                "base_version": None,
                "fields": fields,
                "states": dict(planned.states) if planned is not None else {},
                "errors": [],
                "warnings": [
                    {"code": w["code"], "message": w["message"]}
                    for w in row["warnings"]
                    if w["code"] != "name_missing"
                ],
                "edits": [],
            }
        )
    return found


def start_rule_run(
    workspace: Path,
    dataset: str,
    *,
    kind: str,
    source_id: str,
    entity_type: str | None,
    mapping: dict[str, Any] | None,
    actor: str,
    recipe: Any = None,
    recipe_id: str | None = None,
    recipe_version: int | None = None,
    method_ref: str | None = None,
    schema: tuple[Registry, str] | None = None,
    checks: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Run the rule path on a table source; the run ends in `review`.

    With a recipe (inline, or saved: `recipe_id` and optionally its version)
    the source may be a Markdown report, an Excel workbook or a CSV/TSV, read
    as several tables (BI ingest phase 3). Without one, a CSV/TSV is one
    Case A pass, as in phase 1. A method run (phase 5) names itself in
    `method_ref` and adds its `checks`; a draft trial (phase 6) gives
    `schema` = (the draft's registry, its `draft:` ref) in place of the
    dataset's schema."""
    if recipe is not None or recipe_id:
        return _start_recipe_run(
            workspace,
            dataset,
            kind=kind,
            source_id=source_id,
            recipe=recipe,
            recipe_id=recipe_id,
            recipe_version=recipe_version,
            actor=actor,
            method_ref=method_ref,
            schema=schema,
            checks=checks,
        )
    staging = Staging(workspace, dataset)
    staging.store.refuse_write()
    source = staging.source(source_id)
    if source is None:
        raise BiStoreError("source_unknown", "找不到這個來源")
    if readers.suffix(source["name"]) in readers.EXCEL:
        raise BiStoreError("recipe_required", "Excel 活頁簿要用配方（recipe）指定每個工作表的轉換")
    if parse_kind(source["name"]) != "table":
        raise BiStoreError("source_not_table", "規則轉換只能讀 CSV / TSV 表格；這個來源不是表格")
    reg, schema_ref = schema or _dataset_schema(staging)
    rev, markdown = source_markdown.current(staging, source_id)
    found_tables = source_markdown.tables(source, markdown)
    if not found_tables:
        raise BiStoreError("source_not_table", "這個來源的 Markdown 裡沒有表格")
    text, lines = _table_csv(found_tables[0])
    run_id = staging.create_run(
        kind=kind,
        schema_ref=schema_ref,
        source_ids=[source_id],
        actor=actor,
        method_ref=method_ref,
        markdown_rev=rev,
    )
    try:
        prepared = importer.preview(
            staging.store,
            entity_type=entity_type,
            filename=source["name"],
            csv_text=text,
            mapping=mapping,
            schema=reg,
        )
        built = apply_checks(_candidates_from_preview(prepared, source, lines), checks)
        found = [evaluate(staging.store, reg, c) for c in built]
    except (BiStoreError, importer.ImportError_) as error:
        staging.set_status(run_id, "failed", error=f"{error.code}: {error.message}")
        raise
    staging.put_candidates(run_id, found)
    staging.set_status(run_id, "review")
    return run_view(staging, run_id)


def resolve_recipe(
    staging: Staging,
    reg: Registry,
    *,
    recipe: Any,
    recipe_id: str | None,
    recipe_version: int | None,
) -> tuple[dict[str, Any], str]:
    """(the checked recipe, the run's `method_ref`)."""
    if recipe is not None:
        return recipes.validate(recipe, reg), "recipe:inline"
    versions = staging.recipe_versions(str(recipe_id))
    if not versions:
        raise BiStoreError("recipe_unknown", "找不到這個配方")
    chosen = versions[0]
    if recipe_version is not None:
        found = next((v for v in versions if v["version"] == recipe_version), None)
        if found is None:
            raise BiStoreError("recipe_version_unknown", f"這個配方沒有第 {recipe_version} 版")
        chosen = found
    # Checked again: the dataset's schema may have moved since it was saved.
    return recipes.validate(chosen["recipe"], reg), f"recipe:{chosen['id']}@{chosen['version']}"


def _start_recipe_run(
    workspace: Path,
    dataset: str,
    *,
    kind: str,
    source_id: str,
    recipe: Any,
    recipe_id: str | None,
    recipe_version: int | None,
    actor: str,
    method_ref: str | None = None,
    schema: tuple[Registry, str] | None = None,
    checks: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    staging = Staging(workspace, dataset)
    staging.store.refuse_write()
    source = staging.source(source_id)
    if source is None:
        raise BiStoreError("source_unknown", "找不到這個來源")
    if not readers.readable(source["name"]):
        raise BiStoreError(
            "file_type_unsupported", "規則轉換只能讀 Markdown（.md）、Excel（.xlsx）或 CSV/TSV"
        )
    reg, schema_ref = schema or _dataset_schema(staging)
    checked, recipe_ref = resolve_recipe(
        staging, reg, recipe=recipe, recipe_id=recipe_id, recipe_version=recipe_version
    )
    rev, markdown = source_markdown.current(staging, source_id)
    run_id = staging.create_run(
        kind=kind,
        schema_ref=schema_ref,
        source_ids=[source_id],
        actor=actor,
        method_ref=method_ref or recipe_ref,
        markdown_rev=rev,
    )
    try:
        tables = source_markdown.tables(source, markdown)
        built, layout = recipes.build(
            staging.store,
            reg,
            checked,
            tables,
            source_id=source_id,
            filename=source["name"],
        )
        found = [evaluate(staging.store, reg, c) for c in apply_checks(built, checks)]
    except (BiStoreError, importer.ImportError_) as error:
        staging.set_status(run_id, "failed", error=f"{error.code}: {error.message}")
        raise
    staging.put_candidates(run_id, found)
    staging.put_layout(run_id, layout)
    staging.set_status(run_id, "review")
    return run_view(staging, run_id)


def _dataset_schema(staging: Staging) -> tuple[Registry, str]:
    reg = catalog.for_store(staging.store)
    return reg, reg.ref


def registry_for(staging: Staging, run: dict[str, Any]) -> Registry:
    """The schema a run's candidates follow: a schema draft's revision for a
    draft trial (`draft:<id>@rev<n>`, BI ingest phase 6), else the dataset's."""
    ref = str(run.get("schema_ref") or "")
    if ref.startswith(schema_versions.DRAFT_REF_PREFIX):
        # Session A's unsaved draft, tried on the harness (`BI_BUILD_FLOW.md` §5).
        tried = (staging.layout(run["id"]) or {}).get("trial_schema")
        if tried is not None:
            return Registry(tried, "draft")
        draft_id, rev = schema_versions.parse_draft_ref(ref)
        return schema_versions.draft_registry(staging.store.workspace, draft_id, rev)[0]
    return catalog.for_store(staging.store)


def apply_checks(
    candidates: list[dict[str, Any]], checks: list[dict[str, Any]] | None
) -> list[dict[str, Any]]:
    """A method's extra hard rules (BI ingest phase 5): a candidate of the
    rule's type lacking a required field gets the error `method_check` on that
    field, kept (as a value error) until the person fills the field."""
    for rule in checks or []:
        for candidate in candidates:
            if candidate["entity_type"] != rule["entity_type"]:
                continue
            values = _values(candidate)
            known = candidate.setdefault("value_errors", [])
            for name in rule["require"]:
                if values.get(name) not in (None, "", []):
                    continue
                message = rule.get("message") or f"方法規定 {rule['entity_type']} 需要 {name}"
                error = {"code": "method_check", "message": str(message), "field": name}
                if error not in known:
                    known.append(error)
    return candidates


# -- recipes ---------------------------------------------------------------


def save_recipe(workspace: Path, dataset: str, recipe: Any, *, actor: str) -> dict[str, Any]:
    """Check a recipe against the dataset's schema and save it as the next
    version of its name."""
    staging = Staging(workspace, dataset)
    staging.store.refuse_write()
    checked = recipes.validate(recipe, catalog.for_store(staging.store))
    return staging.save_recipe(checked, actor=actor)


def recipe_detail(workspace: Path, dataset: str, recipe_id: str) -> dict[str, Any]:
    versions = Staging(workspace, dataset).recipe_versions(recipe_id)
    if not versions:
        raise BiStoreError("recipe_unknown", "找不到這個配方")
    return {
        "recipe": versions[0],
        "versions": [{k: v[k] for k in ("version", "by", "at")} for v in versions],
    }


# -- reading ---------------------------------------------------------------


def summary(candidates: list[dict[str, Any]]) -> dict[str, int]:
    counts = {
        "candidates": len(candidates),
        "create": 0,
        "update": 0,
        "unchanged": 0,
        "skip": 0,
        "accepted": 0,
        "rejected": 0,
        "pending": 0,
        "errors": 0,
        "warnings": 0,
    }
    for candidate in candidates:
        counts[candidate["action"]] += 1
        counts[candidate["review"]] += 1
        counts["errors"] += len(candidate["errors"])
        counts["warnings"] += len(candidate["warnings"])
    return counts


def public(candidate: dict[str, Any]) -> dict[str, Any]:
    """A candidate as the API shows it (without the stored internals)."""
    return {k: v for k, v in candidate.items() if k not in ("choice", "synthetic", "value_errors")}


def listed(run: dict[str, Any]) -> bool:
    """A re-run's runs are shown by the re-run, not among the runs to review."""
    return not str(run.get("method_ref") or "").startswith(RERUN_PREFIX)


def run_view(staging: Staging, run_id: str) -> dict[str, Any]:
    run = staging.run_row(run_id)
    if run is None:
        raise BiStoreError("run_unknown", "找不到這次執行")
    found = staging.candidates(run_id)
    view = {**run, "summary": summary(found)}
    layout = staging.layout(run_id)
    if layout is not None and layout.get("mode") == "llm":
        # An AI run: its progress, failed chunks (retryable) and warnings.
        view.update(
            progress={"done": layout.get("done", 0), "chunks": layout.get("chunks", 0)},
            failures=layout.get("failures") or [],
            warnings=layout.get("warnings") or [],
            types=layout.get("types") or [],
            relations=layout.get("relations") or [],
            merge=merge_counts(found),
        )
        rules = layout.get("skills")
        if isinstance(rules, dict):  # a vault's run: what its home's profile said, or none
            view.update(profile=rules.get("profile"), home=rules.get("home"))
    elif layout is not None:
        # A recipe run: its tables, passes (with counts as reviewed now) and
        # run-level warnings such as `table_unused`.
        passes = []
        for item in layout["passes"]:
            mine = [c for c in found if c.get("pass_id") == item["id"]]
            counts = summary(mine)
            passes.append({**item, "counts": counts})
        view.update(tables=layout["tables"], passes=passes, warnings=layout["warnings"])
    return view


def runs(workspace: Path, dataset: str) -> list[dict[str, Any]]:
    staging = Staging(workspace, dataset)
    return [run_view(staging, run["id"]) for run in staging.run_rows() if listed(run)]


def run_detail(workspace: Path, dataset: str, run_id: str) -> dict[str, Any]:
    staging = Staging(workspace, dataset)
    return {
        "run": run_view(staging, run_id),
        "candidates": [public(c) for c in staging.candidates(run_id)],
    }


# -- review ----------------------------------------------------------------


def _open_run(staging: Staging, run_id: str) -> dict[str, Any]:
    run = staging.run_row(run_id)
    if run is None:
        raise BiStoreError("run_unknown", "找不到這次執行")
    if run["status"] not in ("review", "partial"):
        raise BiStoreError("run_closed", "這次執行已經結束，不能再修改")
    _same_schema(staging, run)
    return run


def _same_schema(staging: Staging, run: dict[str, Any]) -> None:
    """A run's candidates follow the schema it ran with; after a dataset
    schema upgrade they need a new run (BI ingest §5.3)."""
    current = staging.store.schema_ref()
    if run["schema_ref"] != current:
        raise BiStoreError(
            "schema_changed",
            f"資料集的 schema 已從 {run['schema_ref']} 改為 {current}；請用同樣的來源重新執行",
        )


def _normalize(reg: Registry, item: FieldDef, raw: Any) -> Any:
    if raw is None or raw == "" or raw == []:
        return None
    if isinstance(raw, list):
        if not item.is_list:
            raise BiStoreError("value_invalid", f"{item.label} 不是清單欄位")
        if item.enum:
            # A list with allowed values (BI vault V9) takes only those values.
            allowed, problems = reg.normalize(item, "；".join(str(v) for v in raw))
            if problems:
                raise BiStoreError("value_invalid", problems[0][1])
            return allowed
        values = [str(v).strip() for v in raw if str(v).strip()]
        return values or None
    value, problems = reg.normalize(item, str(raw))
    if value is None:
        raise BiStoreError(
            "value_invalid", problems[0][1] if problems else f"{item.label} 的值無法採用"
        )
    return value


def _edit_fields(
    reg: Registry, entity: TypeDef, candidate: dict[str, Any], edits: dict[str, Any], actor: str
) -> None:
    by_name = {f["field"]: f for f in candidate["fields"]}
    for name, raw in edits.items():
        item = entity.get(str(name))
        if item is None:
            raise BiStoreError("field_unknown", f"{entity.name} 沒有欄位 {name}")
        if item.klass == "derived":
            raise BiStoreError("field_derived", f"{item.label} 是推導欄位，不能直接修改")
        value = _normalize(reg, item, raw)
        candidate["value_errors"] = [
            e for e in candidate.get("value_errors") or [] if e.get("field") != item.name
        ]
        entry = by_name.get(item.name)
        old = None if entry is None else entry["value"]
        if old == value:
            continue
        if entry is None:
            entry = {
                "field": item.name,
                "value": None,
                "basis": "human",
                "evidence": [],
                "current": None,
                "change": "add",
            }
            candidate["fields"].append(entry)
            by_name[item.name] = entry
        if value is None:
            candidate["fields"].remove(entry)
            del by_name[item.name]
        else:
            entry["value"], entry["basis"] = value, "human"
        candidate["edits"].append(
            {"field": item.name, "old": old, "new": value, "by": actor, "at": now()}
        )


def review(
    workspace: Path,
    dataset: str,
    run_id: str,
    candidate_id: str,
    *,
    decision: Any,
    fields: Any,
    match: Any,
    actor: str,
    take_new: Any = None,
    confirm_same_name: Any = None,
) -> dict[str, Any]:
    staging = Staging(workspace, dataset)
    staging.store.refuse_write()
    _open_run(staging, run_id)
    candidate = next((c for c in staging.candidates(run_id) if c["id"] == candidate_id), None)
    if candidate is None:
        raise BiStoreError("candidate_unknown", "找不到這張候選卡")
    reg = catalog.for_store(staging.store)
    entity = reg.type(candidate["entity_type"])
    if fields is not None:
        if not isinstance(fields, dict):
            raise BiStoreError("fields_invalid", "fields 必須是 {欄位: 值}")
        _edit_fields(reg, entity, candidate, fields, actor)
    if take_new is not None:
        if not isinstance(take_new, dict):
            raise BiStoreError("take_new_invalid", "take_new 必須是 {欄位: true 或 false}")
        by_name = {f["field"]: f for f in candidate["fields"]}
        for name, chosen in take_new.items():
            if name not in by_name:
                raise BiStoreError("field_unknown", f"這張候選卡沒有欄位 {name}")
            if name in PROTECTED_FIELDS and chosen:
                raise BiStoreError(
                    "field_protected", f"{name} 不能由 AI 匯入改寫；請到待審提案決定"
                )
            by_name[name]["take_new"] = bool(chosen)
    if match is not None:
        if not isinstance(match, dict) or match.get("action") not in ("create", "update", "skip"):
            raise BiStoreError("match_invalid", "match.action 只能是 create、update 或 skip")
        if match["action"] == "update" and not match.get("card_id"):
            raise BiStoreError("match_invalid", "合併到既有卡片需要 card_id")
        candidate["choice"] = {"action": match["action"], "card_id": match.get("card_id")}
    evaluate(staging.store, reg, candidate)
    if confirm_same_name is True:
        candidate["same_name_confirmed"] = [c["id"] for c in candidate.get("same_name") or []]
    if decision is not None:
        if decision not in ("accepted", "rejected", "pending"):
            raise BiStoreError("review_invalid", "review 只能是 accepted、rejected 或 pending")
        if decision == "accepted" and candidate["errors"]:
            raise BiStoreError(
                "candidate_invalid",
                "這張候選卡還有錯誤，修正後才能接受",
                errors=candidate["errors"],
            )
        others = unconfirmed_same_name(candidate)
        if decision == "accepted" and others:
            raise BiStoreError(
                "same_name_unconfirmed",
                "已經有同名的卡片（" + "、".join(f"{c['type']}「{c['name']}」" for c in others)
                + "）：確認是不同的對象才能接受",
                cards=others,
            )  # fmt: skip
        candidate["review"] = decision
    elif candidate["review"] == "accepted" and candidate["errors"]:
        candidate["review"] = "pending"
    staging.put_candidates(run_id, [candidate])
    return {"candidate": public(candidate), "run": run_view(staging, run_id)}


def merge_relations(
    store: BiStore, held: list[dict[str, Any]], found: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """A run's inferred relations with these added: one per (type, from, to), and
    none a person already decided, so a re-run does not ask again."""
    from capabilities.bi_cards import vault

    seen = {(r["type"], norm_key(r["from"]), norm_key(r["to"])) for r in held}
    merged = list(held)
    for item in found:
        key = (item["type"], norm_key(item["from"]), norm_key(item["to"]))
        if key in seen or vault.relation_decided(store, item):
            continue
        seen.add(key)
        merged.append({**item, "id": f"r{len(merged) + 1}", "decision": None})
    return merged


def decide_relation(
    workspace: Path, dataset: str, run_id: str, relation: str, status: Any, *, actor: str
) -> dict[str, Any]:
    """A person's decision on one inferred relation. Confirmed needs both cards to
    exist, so it comes after the run is written. Rejecting one whose cards never
    came to be needs nothing stored; it stays on the run."""
    from capabilities.bi_cards import vault

    staging = Staging(workspace, dataset)
    run = staging.run_row(run_id)
    if run is None:
        raise BiStoreError("run_unknown", "找不到這次執行")
    if run["kind"] == "trial":
        raise BiStoreError("run_trial", "試跑的結果不能寫入；請用同樣的來源正式匯入")
    if staging.store.vault_id is None:
        raise BiStoreError("relation_vault_only", "只有共用知識庫有推論關係")
    layout = staging.layout(run_id) or {}
    item = next((r for r in layout.get("relations") or [] if r["id"] == relation), None)
    if item is None:
        raise BiStoreError("relation_unknown", "這次執行沒有這筆關係")
    if status not in ("confirmed", "rejected"):
        raise BiStoreError("relation_status_invalid", "決定只能是確認或否決")
    ends = vault.relation_ends(staging.store, item)
    if ends is None and status == "confirmed":
        raise BiStoreError(
            "relation_card_unknown", f"「{item['from']}」或「{item['to']}」還不是唯一一張卡片"
        )
    if ends is not None:
        vault.decide_relation(
            workspace,
            staging.store.vault_id,
            {
                "from": ends[0],
                "type": item["type"],
                "to": ends[1],
                "status": status,
                "origin": "ai_inferred",
                "note": item.get("reason"),
                "evidence": [{"reference_id": reference_id(item["source_id"], item["locator"])}],
            },
            actor,
        )
    item["decision"] = status
    staging.put_layout(run_id, layout)
    return {"relation": item}


def recheck(workspace: Path, dataset: str, run_id: str) -> dict[str, Any]:
    """Evaluate every candidate again against the cards now."""
    staging = Staging(workspace, dataset)
    staging.store.refuse_write()
    _open_run(staging, run_id)
    reg = catalog.for_store(staging.store)
    changed = []
    found = staging.candidates(run_id)
    for candidate in found:
        before = _diff_view(candidate)
        evaluate(staging.store, reg, candidate)
        if _diff_view(candidate) != before:
            changed.append(candidate["id"])
            if candidate["review"] == "accepted":
                candidate["review"] = "pending"
    staging.put_candidates(run_id, found)
    return {
        "run": run_view(staging, run_id),
        "candidates": [public(c) for c in found],
        "changed": changed,
    }


def cancel(workspace: Path, dataset: str, run_id: str) -> dict[str, Any]:
    staging = Staging(workspace, dataset)
    staging.store.refuse_write()
    run = staging.run_row(run_id)
    if run is None:
        raise BiStoreError("run_unknown", "找不到這次執行")
    if run["status"] in ("committed", "cancelled", "failed"):
        raise BiStoreError("run_closed", "這次執行已經結束")
    staging.set_status(run_id, "cancelled")
    return run_view(staging, run_id)


# -- commit ----------------------------------------------------------------


def commit(workspace: Path, dataset: str, run_id: str, *, actor: str) -> dict[str, Any]:
    staging = Staging(workspace, dataset)
    store = staging.store
    store.refuse_write()
    run = staging.run_row(run_id)
    if run is None:
        raise BiStoreError("run_unknown", "找不到這次執行")
    found = staging.candidates(run_id)
    counts = {
        "skipped": sum(1 for c in found if c["review"] == "rejected" or c["action"] == "skip"),
        "pending": sum(1 for c in found if c["review"] == "pending" and c["action"] != "skip"),
    }
    if run["status"] == "committed" and run["commit"] is not None:
        return _committed(staging, run_id, run["commit"], counts, already=True)
    if run["kind"] == "trial":
        raise BiStoreError("run_trial", "試跑的結果不能寫入；請用同樣的來源開始正式匯入")
    if run["status"] not in ("review", "partial"):
        raise BiStoreError("run_closed", "這次執行已經結束，不能寫入")
    _same_schema(staging, run)
    earlier = store.committed_run(run_id)
    if earlier is not None:
        # The write happened but its reply was lost: record it, write nothing.
        found_earlier = {"import_id": earlier, "at": now(), "by": actor}
        staging.set_status(run_id, "committed", commit_result=found_earlier)
        return _committed(staging, run_id, found_earlier, counts, already=True)
    chosen = [c for c in found if c["review"] == "accepted" and c["action"] in WRITABLE]
    invalid = [c for c in chosen if c["errors"]]
    if invalid:
        raise BiStoreError(
            "candidates_invalid",
            "有已接受的候選卡還有錯誤",
            candidates=[c["id"] for c in invalid],
        )
    if not chosen:
        raise BiStoreError("nothing_accepted", "沒有已接受、需要寫入的候選卡")
    names = {s: (staging.source(s) or {}).get("name", "") for s in run["source_ids"]}
    merge = _is_ai(staging, run_id)
    rows = [
        (
            _planned(candidate, number, run_id, names, merge),
            candidate["id"],
            candidate["base_version"],
        )
        for number, candidate in enumerate(chosen, start=1)
    ]
    applied = store.commit_run(
        run_id, rows, filename=", ".join(n for n in names.values() if n), actor=actor
    )
    result: dict[str, Any] = {
        "import_id": applied.import_id,
        "created": applied.created,
        "updated": applied.updated,
        "unchanged": applied.unchanged,
        "proposals": applied.proposals,
        "at": now(),
        "by": actor,
    }
    staging.set_status(run_id, "committed", commit_result=result)
    return _committed(staging, run_id, result, counts, already=False)


def _is_ai(staging: Staging, run_id: str) -> bool:
    return (staging.layout(run_id) or {}).get("mode") == "llm"


def _planned(
    candidate: dict[str, Any], number: int, run_id: str, names: dict[str, Any], merge: bool = False
) -> PlannedRow:
    values = _values(candidate)
    propose: set[str] = set()
    overwrite: set[str] = set()
    alternatives: dict[str, list[dict[str, Any]]] = {}
    for item in candidate["fields"] if merge else ():
        name, how = item["field"], item.get("merge")
        if how == "proposal":
            propose.add(name)
        elif how == "join" or (how == "same" and "merged" in item):
            # Never the model's list as it came: a shorter one would drop what the card holds.
            values[name] = item["merged"]
        elif how == "capped":
            # What is written is not what the evidence said: that goes with the proposal.
            if item.get("capped") is None:
                values.pop(name, None)
            else:
                values[name] = item["capped"]
            alternatives[name] = [
                {"value": item["value"], "basis": item["basis"], "evidence": item["evidence"]}
            ]
        elif how == "take":
            overwrite.add(name)
        elif how == "bookkeeping" and not item.get("later"):
            values.pop(name, None)
        if item.get("alternatives") or name in alternatives:
            alternatives[name] = [
                {
                    **other,
                    "evidence": [
                        {
                            **e,
                            "source_name": names.get(e["source_id"], ""),
                            "basis": other.get("basis"),
                        }
                        for e in other.get("evidence") or ()
                    ],
                }
                for other in [*alternatives.get(name, ()), *(item.get("alternatives") or ())]
            ]
    return PlannedRow(
        row=number,
        entity_type=candidate["entity_type"],
        canonical_key=candidate["canonical_key"],
        name=str(candidate.get("name") or candidate["canonical_key"]),
        values=values,
        propose=frozenset(propose),
        overwrite=frozenset(overwrite),
        alternatives=alternatives,
        synthetic=bool(candidate.get("synthetic")),
        ref=f"run:{run_id}/{candidate['id']}",
        states=candidate.get("states") or {},
        evidence={
            f["field"]: [
                {
                    **item,
                    "source_name": names.get(item["source_id"], ""),
                    "basis": f["basis"],
                }
                for item in f["evidence"]
            ]
            for f in candidate["fields"]
            if f["evidence"] and not (merge and f.get("merge") == "capped")
        },
    )


def clean_rows(staging: Staging, run_id: str) -> list[PlannedRow]:
    """A run's writable candidates without errors, as rows, for a scratch copy
    of the cards (`bi_skill__benchmark`, `BI_BUILD_FLOW.md` §6); no review."""
    run = staging.run_row(run_id)
    if run is None:
        raise BiStoreError("run_unknown", "找不到這次執行")
    names = {s: (staging.source(s) or {}).get("name", "") for s in run["source_ids"]}
    clean = [c for c in staging.candidates(run_id) if c["action"] in WRITABLE and not c["errors"]]
    merge = _is_ai(staging, run_id)
    return [_planned(c, number, run_id, names, merge) for number, c in enumerate(clean, start=1)]


def index_state(store: BiStore) -> dict[str, Any]:
    """The search index after a write (BI vault V3), for the result step."""
    from capabilities.bi_cards import search_index

    state = search_index.status(store)
    if state["behind"]:
        message = "搜尋索引還沒跟上，請到「結果」重建索引"
    else:
        message = f"搜尋索引已更新：{state['cards']} 張卡片、{state['chunks']} 段 Markdown"
    return {"status": "behind" if state["behind"] else "current", "message": message, **state}


def _committed(
    staging: Staging,
    run_id: str,
    result: dict[str, Any],
    counts: dict[str, int],
    *,
    already: bool,
) -> dict[str, Any]:
    return {
        "run": run_view(staging, run_id),
        "import_id": result["import_id"],
        "applied": {k: result.get(k, 0) for k in ("created", "updated", "unchanged", "proposals")},
        "skipped": counts["skipped"],
        "pending": counts["pending"],
        "index": index_state(staging.store),
        "already": already,
    }
