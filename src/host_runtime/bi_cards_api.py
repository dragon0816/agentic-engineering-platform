"""The `/api/bi/*` routes of Agent Web (BI Knowledge Case A, owner 2026-10-21).

Mounted in `web.py` after the loopback and Bearer-token guards, like every
other `/api/*` route. The contract is in `docs/CONTRACTS.md` ("BI cards
API"). Errors are `{"ok": false, "code", "message"}` with a 4xx status.
Imports and edits are recorded as `<actor> via web`.

Each dataset follows the schema it was created with (owner 2026-10-21):
cards, import, detail, edits and history use that schema; the Dashboard and
the demo are BI-only and refuse a dataset whose schema is not `bi.schema/*`.

Ingest runs (BI ingest phase 1, owner 2026-10-27; contract "BI ingest runs"):
`/api/bi/sources` and `/api/bi/runs/*` keep sources, runs and candidates in
the dataset's staging store; only a run's commit writes cards.

Schema versions (BI ingest phase 2, owner 2026-10-27; contract "BI schema
drafts and dataset upgrade"): `/api/bi/schema-drafts/*` keeps revisions of a
draft and publishes one as a new version; `/api/bi/datasets/<name>/schema/*`
previews and applies moving a dataset to another version of its schema.

The rule path (BI ingest phase 3, owner 2026-10-27; contract "BI rule path:
recipes and multi-table sources"): `/api/bi/recipes` keeps versioned recipes
per dataset, and `POST /api/bi/runs` accepts a recipe for a Markdown, Excel
or CSV/TSV source with several tables.

Methods and Session B (BI ingest phase 5; contract "BI method sessions"):
`/api/bi/methods/*` keeps versioned ingest methods per dataset, `POST
/api/bi/runs` accepts `method_id`, `/api/bi/runs/compare` sets two runs side
by side, and `/api/bi/sessions/*` keeps the AI conversations (one model call
per turn, no tools; `/api/bi/ai` says which model is available).

Session A (BI ingest phase 6; contract "BI schema sessions"): a `schema`
session suggests operations on a schema draft, applied to a copy and
validated before 「套用到草稿」; `POST /api/bi/runs` with `draft_id` tries a
draft revision on samples without installing it (trial only).
"""

from __future__ import annotations

import json
import re
import threading
import uuid
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import ParseResult, parse_qs

from capabilities.bi_cards import (
    ai_runs,
    catalog,
    dashboard,
    importer,
    methods,
    runs,
    schema_session,
    schema_versions,
    service,
    sessions,
)
from capabilities.bi_cards.staging import Staging
from capabilities.bi_cards.store import (
    DATASET_RE,
    DEFAULT_DATASET,
    READ_ONLY_MESSAGE,
    BiStore,
    BiStoreError,
    datasets,
    is_subscribed,
)
from host_runtime import bi_subscriptions

#: A CSV travels in the JSON body; larger than an ordinary request.
MAX_BI_BODY_BYTES = 8 * 1024 * 1024

Answer = tuple[int, dict[str, Any]]


def _error(status: int, code: str, message: str) -> Answer:
    return status, {"ok": False, "code": code, "message": message}


def _dataset(value: Any) -> str:
    return str(value or DEFAULT_DATASET)


#: The Dashboard is BI-only: a dataset of another schema gets this empty state
#: (200, not an error), so the page can say so instead of failing.
NO_DASHBOARD = "這個 schema 沒有 Dashboard"
NOT_BI = "示範資料是 BI 資料，只能載入使用 bi.schema/* 的資料集"


def route(
    workspace: Path,
    actor: str,
    method: str,
    path: str,
    query: Mapping[str, str],
    body: Any,
    platform: bi_subscriptions.SubscriptionPlatform | None = None,
    ai: ai_runs.AiRuntime | None = None,
) -> Answer:
    """One request; pure apart from the dataset files (and, for the
    subscription routes, `platform`; for AI runs, `ai`)."""
    try:
        if path == "/api/bi/subscriptions" or path.startswith("/api/bi/subscriptions/"):
            given = body if isinstance(body, dict) else {}
            return bi_subscriptions.route(workspace, platform, method, path, query, given)
        return _route(workspace, actor, method, path, query, body, ai)
    except catalog.SchemaInstallError as error:
        # An installed id@version is immutable: different content is a conflict.
        return 409 if error.code == "schema_version_exists" else 400, {
            "ok": False,
            "code": error.code,
            "message": error.message,
            "errors": error.errors,
        }
    except BiStoreError as error:
        # A recipe's unknown key is a bad request, not a missing resource.
        missing = error.code.endswith("_unknown") and error.code != "mapping_key_unknown"
        status = 404 if missing else 400
        if error.code == "dataset_read_only":
            return 409, {"ok": False, "code": error.code, "message": error.message}
        if error.code == "dataset_exists":
            return 409, {"ok": False, "code": error.code, "message": error.message, **error.detail}
        if error.code in CONFLICTS:
            status = 409
        return status, {"ok": False, "code": error.code, "message": error.message, **error.detail}
    except importer.ImportError_ as error:
        return _error(400, error.code, error.message)


def _route(
    workspace: Path,
    actor: str,
    method: str,
    path: str,
    query: Mapping[str, str],
    body: Any,
    ai: ai_runs.AiRuntime | None = None,
) -> Answer:
    given: dict[str, Any] = body if isinstance(body, dict) else {}
    who = f"{actor} via web"
    if method == "POST" and is_subscribed(_dataset(given.get("dataset"))):
        # A subscribed copy is read only: import, edit, undo and demo load.
        return _error(409, "dataset_read_only", READ_ONLY_MESSAGE)
    if method == "GET":
        store = BiStore(workspace, _dataset(query.get("dataset")))
        if (path in DATASET_READS or path.startswith("/api/bi/cards/")) and _unknown_dataset(
            store, path, query
        ):
            # A name that is neither an own dataset nor a subscribed one
            # (live test 2026-10-24: it read as an empty dataset); `demo`
            # before anything is loaded stays an empty dataset.
            return _error(404, "dataset_unknown", f"沒有這個資料集「{store.dataset}」")
        if path == "/api/bi/schema":
            # No dataset: the shipped bi.schema/v1.1, as before per-dataset schemas.
            given_dataset = "dataset" in query
            return 200, service.schema_api(catalog.for_store(store) if given_dataset else None)
        if path == "/api/bi/schemas":
            return 200, {"schemas": catalog.listing(workspace)}
        if path == "/api/bi/schemas/example":
            return 200, catalog.example()
        if path == "/api/bi/datasets":
            return 200, {"datasets": service.dataset_list(workspace)}
        if path == "/api/bi/dashboard":
            reg = catalog.for_store(store)
            if not reg.is_bi:
                return 200, {
                    "dashboard": False,
                    "code": "no_dashboard",
                    "message": NO_DASHBOARD,
                    "schema": reg.ref,
                    "domain": None,
                    "sections": [],
                }
            return 200, dashboard.dashboard(store, str(query.get("domain") or "robotics"))
        if path == "/api/bi/sources":
            return 200, {"sources": Staging(workspace, store.dataset).sources()}
        if path == "/api/bi/schema-drafts":
            return 200, {"drafts": schema_versions.drafts(workspace)}
        if path.startswith("/api/bi/schema-drafts/"):
            return _draft_read(workspace, path.split("/")[4:], query)
        if path == "/api/bi/recipes":
            return 200, {"recipes": Staging(workspace, store.dataset).recipes()}
        if path.startswith("/api/bi/recipes/") and path.count("/") == 4:
            return 200, runs.recipe_detail(workspace, store.dataset, path.rsplit("/", 1)[1])
        if path == "/api/bi/runs":
            return 200, {"runs": runs.runs(workspace, store.dataset)}
        if path == "/api/bi/runs/compare":
            return 200, methods.compare(
                workspace, store.dataset, query.get("left"), query.get("right")
            )
        if path == "/api/bi/ai":
            return 200, sessions.model_state(ai)
        if path == "/api/bi/methods":
            return 200, {"methods": methods.listing(workspace, store.dataset)}
        if path.startswith("/api/bi/methods/") and path.count("/") == 4:
            method_id = path.rsplit("/", 1)[1]
            return 200, methods.detail(workspace, store.dataset, method_id, query.get("rev"))
        if path == "/api/bi/sessions":
            listed = Staging(workspace, store.dataset).sessions(query.get("target") or None)
            return 200, {"sessions": listed}
        if path.startswith("/api/bi/sessions/") and path.count("/") == 4:
            staging = Staging(workspace, store.dataset)
            return 200, {"session": sessions.load(staging, path.rsplit("/", 1)[1])}
        if path.startswith("/api/bi/runs/") and path.count("/") == 4:
            return 200, runs.run_detail(workspace, store.dataset, path.rsplit("/", 1)[1])
        if path == "/api/bi/cards":
            found = service.search(
                store,
                entity_type=query.get("type") or None,
                text=query.get("q") or None,
                domain=query.get("domain") or None,
            )
            return 200, {"cards": [service.card_summary(c, f) for c, f in found]}
        parts = path.split("/")
        if len(parts) in (5, 6) and parts[:4] == ["", "api", "bi", "cards"]:
            card_id = parts[4]
            if len(parts) == 6 and parts[5] == "history":
                if store.card(card_id) is None:
                    return _error(404, "card_unknown", "找不到這張卡片")
                return 200, {"history": store.history(card_id)}
            if len(parts) == 5:
                detail = service.card_detail(store, card_id)
                if detail is None:
                    return _error(404, "card_unknown", "找不到這張卡片")
                return 200, detail
        return _error(404, "route_unknown", "沒有這個 BI 路徑")
    if method != "POST":
        return _error(405, "method_not_allowed", "只接受 GET 與 POST")
    if path == "/api/bi/schemas/install":
        return 200, catalog.install(
            workspace, str(given.get("filename") or ""), given.get("json_text")
        )
    if path == "/api/bi/datasets":
        return _create_dataset(workspace, given)
    if path == "/api/bi/demo/load":
        store = BiStore(workspace, _dataset(given.get("dataset")))
        if not catalog.for_store(store).is_bi:
            return _error(400, "schema_not_bi", NOT_BI)
        return 200, {"ok": True, "imported": service.load_demo(store)}
    if path == "/api/bi/import/preview":
        store = BiStore(workspace, _dataset(given.get("dataset")))
        csv_text = given.get("csv_text")
        if not isinstance(csv_text, str) or not csv_text.strip():
            return _error(400, "csv_missing", "沒有 CSV 內容")
        mapping = given.get("mapping")
        if mapping is not None and not isinstance(mapping, dict):
            return _error(400, "mapping_invalid", "mapping 必須是 JSON 物件")
        prepared = importer.preview(
            store,
            entity_type=given.get("entity_type") or None,
            filename=str(given.get("filename") or "upload.csv"),
            csv_text=csv_text,
            mapping=mapping,
        )
        importer.remember(prepared)
        return 200, prepared.to_api()
    if path == "/api/bi/import/apply":
        pending = importer.recall(str(given.get("preview_id") or ""))
        if pending is None:
            return _error(404, "preview_unknown", "找不到這份預覽（可能已過期），請重新預覽")
        rows = given.get("rows")
        if rows is not None and (
            not isinstance(rows, list) or not all(isinstance(r, int) for r in rows)
        ):
            return _error(400, "rows_invalid", "rows 必須是列號清單或 null")
        store = BiStore(workspace, pending.dataset)
        result = importer.apply(store, pending, rows, actor=who)
        importer.forget(pending.preview_id)
        return 200, {
            "ok": True,
            "import_id": result.import_id,
            "applied": {
                "created": result.created,
                "updated": result.updated,
                "unchanged": result.unchanged,
                "proposals": result.proposals,
            },
        }
    if path == "/api/bi/import/undo":
        store = BiStore(workspace, _dataset(given.get("dataset")))
        store.undo_import(str(given.get("import_id") or ""), actor=who)
        return 200, {"ok": True}
    if path == "/api/bi/sources":
        source = Staging(workspace, _dataset(given.get("dataset"))).add_source(
            given.get("name"),
            text=given.get("text"),
            content_base64=given.get("content_base64"),
            media_type=given.get("media_type"),
            classification=given.get("classification"),
            actor=who,
        )
        return 200, {"ok": True, "source": source}
    if path == "/api/bi/runs":
        return _start_run(workspace, who, given, ai)
    if path == "/api/bi/recipes":
        saved = runs.save_recipe(
            workspace, _dataset(given.get("dataset")), given.get("recipe"), actor=who
        )
        return 200, {"ok": True, "recipe": saved}
    parts = path.split("/")
    if path == "/api/bi/methods":
        made = methods.create(workspace, _dataset(given.get("dataset")), given.get("method"), who)
        return 200, {"ok": True, **made}
    if len(parts) == 6 and parts[:4] == ["", "api", "bi", "methods"]:
        return _method_write(workspace, who, parts[4], parts[5], given)
    if path == "/api/bi/sessions":
        return _session_create(workspace, who, given)
    if len(parts) == 6 and parts[:4] == ["", "api", "bi", "sessions"]:
        return _session_write(workspace, who, parts[4], parts[5], given, ai)
    if path == "/api/bi/schema-drafts":
        made = schema_versions.create_draft(
            workspace, str(given.get("base") or ""), given.get("title"), who
        )
        return 200, {"ok": True, **made}
    if len(parts) == 6 and parts[:4] == ["", "api", "bi", "schema-drafts"]:
        return _draft_write(workspace, who, parts[4], parts[5], given)
    if len(parts) == 7 and parts[:4] == ["", "api", "bi", "datasets"] and parts[5] == "schema":
        if parts[6] == "preview":
            return 200, {
                "ok": True,
                **schema_versions.upgrade_preview(workspace, parts[4], given.get("to")),
            }
        if parts[6] == "apply":
            done = schema_versions.upgrade_apply(
                workspace, parts[4], given.get("to"), given.get("preview_token"), who
            )
            return 200, {"ok": True, **done}
    if len(parts) >= 6 and parts[:4] == ["", "api", "bi", "runs"]:
        return _run_action(workspace, who, parts[4], parts[5:], given, ai)
    if len(parts) == 6 and parts[:4] == ["", "api", "bi", "cards"] and parts[5] == "field":
        return _set_field(workspace, who, parts[4], given)
    if len(parts) == 7 and parts[:4] == ["", "api", "bi", "cards"] and parts[5] == "proposals":
        return _decide_proposal(workspace, who, parts[4], parts[6], given)
    return _error(404, "route_unknown", "沒有這個 BI 路徑")


def _start_run(
    workspace: Path, who: str, given: dict[str, Any], ai: ai_runs.AiRuntime | None
) -> Answer:
    kind = given.get("kind")
    if kind not in ("trial", "ingest"):
        return _error(400, "run_kind_invalid", "kind 只能是 trial 或 ingest")
    dataset = _dataset(given.get("dataset"))
    source_id = str(given.get("source_id") or "")
    source = Staging(workspace, dataset).source(source_id)
    schema = None
    if given.get("draft_id"):
        # 「用樣本試跑」 (BI ingest phase 6): a draft revision's schema, not installed.
        if kind != "trial":
            return _error(
                400, "draft_trial_only", "草稿的 schema 只能試跑；發布並升級後才能正式匯入"
            )
        schema = schema_versions.draft_registry(
            workspace, str(given["draft_id"]), given.get("draft_rev")
        )
    if given.get("method_id"):
        # A saved method (BI ingest phase 5) decides the path.
        run = methods.start_run(
            workspace,
            dataset,
            ai,
            kind=str(kind),
            source_id=source_id,
            method_id=str(given["method_id"]),
            method_rev=given.get("method_rev"),
            actor=who,
            schema=schema,
        )
        return 200, {"ok": True, "run": run}
    no_recipe = given.get("recipe") is None and not given.get("recipe_id")
    if source is not None and source["parse"] == "text" and no_recipe:
        # A text source is read by the model (BI ingest phase 4).
        run = ai_runs.start(
            workspace,
            dataset,
            ai,
            kind=str(kind),
            source_id=source_id,
            instructions=given.get("instructions"),
            types=given.get("types"),
            actor=who,
            schema=schema,
        )
        return 200, {"ok": True, "run": run}
    mapping = given.get("mapping")
    if mapping is not None and not isinstance(mapping, dict):
        return _error(400, "mapping_invalid", "mapping 必須是 JSON 物件")
    recipe = given.get("recipe")
    if recipe is not None and not isinstance(recipe, dict):
        return _error(400, "recipe_invalid", "recipe 必須是 JSON 物件")
    version = given.get("recipe_version")
    if version is not None and (isinstance(version, bool) or not isinstance(version, int)):
        return _error(400, "recipe_invalid", "recipe_version 必須是整數")
    run = runs.start_rule_run(
        workspace,
        _dataset(given.get("dataset")),
        kind=str(kind),
        source_id=str(given.get("source_id") or ""),
        entity_type=given.get("entity_type") or None,
        mapping=mapping,
        actor=who,
        recipe=recipe,
        recipe_id=str(given.get("recipe_id") or "") or None,
        recipe_version=version,
        schema=schema,
    )
    return 200, {"ok": True, "run": run}


def _run_action(
    workspace: Path,
    who: str,
    run_id: str,
    rest: list[str],
    given: dict[str, Any],
    ai: ai_runs.AiRuntime | None = None,
) -> Answer:
    dataset = _dataset(given.get("dataset"))
    if len(rest) == 2 and rest[0] == "candidates":
        answer = runs.review(
            workspace,
            dataset,
            run_id,
            rest[1],
            decision=given.get("review"),
            fields=given.get("fields"),
            match=given.get("match"),
            actor=who,
        )
        return 200, {"ok": True, **answer}
    if rest == ["recheck"]:
        return 200, {"ok": True, **runs.recheck(workspace, dataset, run_id)}
    if rest == ["commit"]:
        return 200, {"ok": True, **runs.commit(workspace, dataset, run_id, actor=who)}
    if rest == ["cancel"]:
        return 200, {"ok": True, "run": runs.cancel(workspace, dataset, run_id)}
    if rest == ["retry"]:
        return 200, {"ok": True, "run": ai_runs.retry(workspace, dataset, ai, run_id)}
    return _error(404, "route_unknown", "沒有這個 BI 路徑")


def _method_write(
    workspace: Path, who: str, method_id: str, action: str, given: dict[str, Any]
) -> Answer:
    dataset = _dataset(given.get("dataset"))
    if action == "revisions":
        saved = methods.save(
            workspace, dataset, method_id, given.get("method"), given.get("note"), who
        )
        return 200, {"ok": True, **saved}
    if action == "revert":
        return 200, {
            "ok": True,
            **methods.revert(workspace, dataset, method_id, given.get("rev"), who),
        }
    return _error(404, "route_unknown", "沒有這個 BI 路徑")


def _session_create(workspace: Path, who: str, given: dict[str, Any]) -> Answer:
    dataset = _dataset(given.get("dataset"))
    kind, target = given.get("kind"), str(given.get("target") or "")
    if kind == "method":
        return 200, {"ok": True, "session": methods.create_session(workspace, dataset, target, who)}
    if kind == "schema":
        made = schema_session.create_session(workspace, dataset, target, who)
        return 200, {"ok": True, "session": made}
    return _error(400, "session_kind_invalid", "kind 只能是 method 或 schema")


def _session_write(
    workspace: Path,
    who: str,
    session_id: str,
    action: str,
    given: dict[str, Any],
    ai: ai_runs.AiRuntime | None,
) -> Answer:
    dataset = _dataset(given.get("dataset"))
    session = sessions.load(Staging(workspace, dataset), session_id)
    if session["kind"] == "method" and action == "turns":
        turned = methods.session_turn(
            workspace,
            dataset,
            ai,
            session_id,
            message=given.get("message"),
            source_ids=given.get("source_ids"),
            run_ids=given.get("run_ids"),
            actor=who,
        )
        return 200, {"ok": True, "session": turned}
    if session["kind"] == "method" and action == "apply":
        applied = methods.apply_suggestion(workspace, dataset, session_id, given.get("turn"), who)
        return 200, {"ok": True, **applied}
    if session["kind"] == "schema" and action == "turns":
        turned = schema_session.session_turn(
            workspace,
            dataset,
            ai,
            session_id,
            message=given.get("message"),
            source_ids=given.get("source_ids"),
            goal=given.get("goal"),
            actor=who,
        )
        return 200, {"ok": True, "session": turned}
    if session["kind"] == "schema" and action == "apply":
        done = schema_session.apply_suggestion(
            workspace, dataset, session_id, given.get("turn"), who
        )
        return 200, {"ok": True, **done}
    return _error(404, "route_unknown", "沒有這個 BI 路徑")


def _draft_read(workspace: Path, rest: list[str], query: Mapping[str, str]) -> Answer:
    draft_id = rest[0]
    if len(rest) == 1:
        return 200, schema_versions.draft(workspace, draft_id)
    if len(rest) == 3 and rest[1] == "revisions" and rest[2].isdigit():
        return 200, schema_versions.draft(workspace, draft_id, int(rest[2]))
    if rest[1:] == ["diff"]:
        return 200, schema_versions.compare(workspace, draft_id, query.get("from"), query.get("to"))
    return _error(404, "route_unknown", "沒有這個 BI 路徑")


def _draft_write(
    workspace: Path, who: str, draft_id: str, action: str, given: dict[str, Any]
) -> Answer:
    if action == "revisions":
        saved = schema_versions.save_revision(
            workspace,
            draft_id,
            document=given.get("document"),
            json_text=given.get("json_text"),
            note=given.get("note"),
            source=given.get("source"),
            actor=who,
        )
        return 200, {"ok": True, **saved}
    if action == "revert":
        return 200, {
            "ok": True,
            **schema_versions.revert(workspace, draft_id, given.get("rev"), who),
        }
    if action == "publish":
        published = schema_versions.publish(workspace, draft_id, given.get("rev"), who)
        return 200, {"ok": True, **published}
    return _error(404, "route_unknown", "沒有這個 BI 路徑")


def _decide_proposal(
    workspace: Path, who: str, card_id: str, proposal: str, given: dict[str, Any]
) -> Answer:
    store = BiStore(workspace, _dataset(given.get("dataset")))
    if store.card(card_id) is None:
        return _error(404, "card_unknown", "找不到這張卡片")
    found = store.proposal(card_id, int(proposal)) if proposal.isdigit() else None
    if found is None:
        return _error(404, "proposal_unknown", "找不到這筆待審提議（可能已處理）")
    action = given.get("action")
    if action == "reject":
        store.reject_proposal(card_id, int(found["id"]))
        card = store.card(card_id)
        return 200, {"ok": True, "version": int(card["version"]) if card is not None else 0}
    if action != "accept":
        return _error(400, "action_invalid", "action 只能是 accept 或 reject")
    return _set_field(
        workspace,
        who,
        card_id,
        {
            "dataset": store.dataset,
            "field": found["field"],
            "value": found["value"],
            "base_version": given.get("base_version"),
            "reason": given.get("reason"),
        },
    )


#: Store refusals that are conflicts with the current state (409).
CONFLICTS = {
    "stale_edit",
    "cards_changed",
    "run_trial",
    "run_closed",
    "run_committed",
    "preview_stale",
    "schema_upgrade_breaking",
    "schema_version_not_newer",
    "schema_changed",
    "suggestion_applied",
    "suggestion_invalid",
}

#: The GET routes that read one dataset (besides `/api/bi/cards/<id>[/history]`).
DATASET_READS = ("/api/bi/cards", "/api/bi/dashboard", "/api/bi/schema")


def _unknown_dataset(store: BiStore, path: str, query: Mapping[str, str]) -> bool:
    """Whether a read names a dataset this PC does not have. `/api/bi/schema`
    without `dataset` reads the shipped schema; `demo` may not exist yet."""
    if path == "/api/bi/schema" and "dataset" not in query:
        return False
    return not store.exists and store.dataset != DEFAULT_DATASET


def _create_dataset(workspace: Path, given: dict[str, Any]) -> Answer:
    name = str(given.get("name") or "").strip()
    if not DATASET_RE.match(name):
        return _error(400, "dataset_invalid", "資料集名稱只能用英文字母、數字、- 與 _，1–40 個字")
    store = BiStore(workspace, name)  # refuses a reserved name
    if any(other.lower() == name.lower() and other != name for other in datasets(workspace)):
        return _error(409, "dataset_exists", f"已經有名稱相同（只差大小寫）的資料集「{name}」")
    reg = catalog.resolve(workspace, str(given.get("schema") or ""))
    store.create(reg.ref)
    return 200, {
        "ok": True,
        "dataset": {
            "name": name,
            "cards": 0,
            "updated": None,
            "schema": reg.ref,
            "dashboard": reg.is_bi,
            "subscribed": False,
            "read_only": False,
        },
    }


def _set_field(workspace: Path, who: str, card_id: str, given: dict[str, Any]) -> Answer:
    store = BiStore(workspace, _dataset(given.get("dataset")))
    card = store.card(card_id)
    if card is None:
        return _error(404, "card_unknown", "找不到這張卡片")
    reg = catalog.for_store(store)
    try:
        entity = reg.type(card["entity_type"])
    except KeyError:
        return _error(400, "type_unknown", f"schema 沒有類型 {card['entity_type']}")
    name = str(given.get("field") or "")
    item = entity.get(name)
    if item is None:
        return _error(400, "field_unknown", f"{entity.name} 沒有欄位 {name}")
    if item.klass == "derived":
        return _error(400, "field_derived", f"{item.label} 是推導欄位，不能直接修改")
    base = given.get("base_version")
    if not isinstance(base, int):
        return _error(400, "base_version_missing", "需要 base_version")
    reason = str(given.get("reason") or "").strip()
    if item.klass == "judgement" and not reason:
        return _error(400, "reason_required", f"{item.label} 是判斷欄位，修改時必須寫理由")
    raw = given.get("value")
    value: Any
    if raw is None or raw == "" or raw == []:
        value = None
    elif isinstance(raw, list):
        if not item.is_list:
            return _error(400, "value_invalid", f"{item.label} 不是清單欄位")
        value = _list_value(reg, item, raw)
    else:
        value, problems = reg.normalize(item, str(raw))
        if value is None:
            message = problems[0][1] if problems else f"{item.label} 的值無法採用"
            return _error(400, "value_invalid", message)
    version = store.set_field(card_id, name, value, base_version=base, actor=who, reason=reason)
    if version == base:
        # The value it already has (owner 2026-10-24): no new version, no history.
        return 200, {"ok": True, "version": version, "unchanged": True}
    return 200, {"ok": True, "version": version}


def _list_value(reg: Any, item: Any, raw: list[Any]) -> list[str] | None:
    """A list edit's items, stripped; a domain item in its canonical spelling
    (as an import stores it), so the same domains in other case or an alias
    compare equal. An item the schema does not know is kept as typed."""
    values: list[str] = []
    for given in raw:
        text = str(given).strip()
        if not text:
            continue
        if item.name == "domain":
            known, _ = reg.normalize(item, text)
            if isinstance(known, list) and len(known) == 1:
                text = str(known[0])
        if text not in values or item.name != "domain":
            values.append(text)
    return values or None


# -- publishing to the Shared Platform (BI dataset sharing slice 1) ----------
# Owner 2026-10-22; `docs/proposals/BI_DATASET_SHARING.md` §7, §8.5, §8.6;
# contract in `docs/CONTRACTS.md` "BI dataset sharing" → "Agent publish API".
# The snapshot is built on this PC (`snapshot.build_snapshot`: no pending
# proposals, file names without folders, refused when a value looks like a
# secret) and sent with the member's own Personal Agent login
# (`MemberPortalPublisher.publish_bi_dataset`). The platform assigns the
# version; the first version of a new name waits for an administrator (owner
# Q5). Readers are the owner's team unless 全公司 is chosen and confirmed (owner
# Q4); there is no public option. The last publish of each dataset is kept in
# `<workspace>/bi/<dataset>/published.json` for the dataset bar.

PUBLISH_PREFIX = "/api/bi/publish"
PUBLISH_RECORD = "published.json"
PUBLISH_READERS = ("team", "organization")
#: A platform name part: lower-case words joined by single hyphens.
PLATFORM_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
MAX_PUBLISH_NOTE = 200


class BiPublisher(Protocol):
    """The member-portal calls a publish needs (`MemberPortalPublisher`)."""

    def publish_bi_dataset(
        self,
        namespace: str,
        name: str,
        snapshot: bytes,
        *,
        note: str,
        base_version: str | None,
        readers: str | None = None,
        confirm_organization: bool = False,
        team: str | None = None,
    ) -> dict[str, Any]: ...

    def bi_dataset_status(self, names: list[tuple[str, str]]) -> list[dict[str, Any]]: ...


#: What the owner reads for each refusal; never a value from the dataset.
PUBLISH_MESSAGES = {
    "dataset_read_only": "這是訂閱的資料集，不能發佈；只有你自己的資料集可以發佈",
    "dataset_unknown": "找不到這個資料集",
    "dataset_empty": "資料集還沒有卡片，沒有東西可以發佈",
    "note_required": "請寫版本說明",
    "readers_invalid": "讀者只能是「我的團隊」或「全公司」",
    "organization_unconfirmed": "開放給全公司需要先勾選確認",
    "name_invalid": "平台名稱是 <namespace>/<name>，只能用小寫英文字母、數字與 -",
    "namespace_required": "這台電腦沒有設定 namespace，請填平台名稱 <namespace>/<name>",
    "publishing_not_configured": "這台電腦還沒設定 Shared Platform：到 Settings → Shared "
    "platform 設定 Member Portal 網址與 Personal Agent code",
    "artifact_too_large": "資料集太大，超過 Shared Platform 的上限",
    "version_superseded": "平台上已有比你這份更新的版本，請先更新後再發佈",
    "review_pending": "這個名稱的第一版還在等管理員審核，核准後才能發佈下一版",
    "publisher_not_authorized": "你沒有發佈這個名稱的權限；請名稱的負責人把你加為共同維護者",
    "team_required": "你屬於多個團隊，請選擇由哪個團隊擁有這個名稱",
    "visibility_not_allowed": "讀者只能是你的團隊或全公司，不能公開",
    "kind_mismatch": "平台上這個名稱已經是另一種資產，請換一個名稱",
    "platform_unreachable": "Shared Platform 沒有回應，資料沒有送出；請稍後再試",
    "certificate_untrusted": "這台電腦不信任 Shared Platform 的憑證；到 Settings → Shared "
    "platform 確認指紋",
    "login_missing": "這台電腦還沒有 Personal Agent code；到 Settings → Shared platform 設定",
    "authentication_failed": "Shared Platform 不接受這台電腦的登入；請重新連接 Personal Agent",
    "session_expired": "Shared Platform 的登入過期了，請再試一次",
    "schema_unavailable": "這個資料集的 schema 無法打包",
    "snapshot_invalid": "Shared Platform 讀不懂這份快照",
}

PUBLISH_STATUS = {
    "dataset_read_only": 409,
    "dataset_unknown": 404,
    "artifact_too_large": 413,
    "version_superseded": 409,
    "review_pending": 409,
    "kind_mismatch": 409,
    "publisher_not_authorized": 403,
    "publishing_not_configured": 409,
    "platform_unreachable": 503,
    "certificate_untrusted": 502,
    "login_missing": 409,
    "authentication_failed": 401,
    "session_expired": 401,
}


def _publish_error(code: str, message: str | None = None, **extra: Any) -> Answer:
    status = PUBLISH_STATUS.get(code, 400)
    text = message or PUBLISH_MESSAGES.get(code) or f"Shared Platform 拒絕發佈（{code}）"
    return status, {"ok": False, "code": code, "message": text, **extra}


def _publish_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def default_platform_name(namespace: str | None, dataset: str) -> str | None:
    """`<namespace>/<dataset as a slug>`, the platform name a first publish
    suggests; None when this PC has no namespace."""
    slug = re.sub(r"[^a-z0-9]+", "-", dataset.lower()).strip("-") or "dataset"
    return f"{namespace}/{slug}" if namespace else None


def _publish_record_path(workspace: Path, dataset: str) -> Path:
    return BiStore(workspace, dataset).dir / PUBLISH_RECORD


def read_publish_record(workspace: Path, dataset: str) -> dict[str, Any] | None:
    try:
        record = json.loads(_publish_record_path(workspace, dataset).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return record if isinstance(record, dict) else None


def _write_publish_record(workspace: Path, dataset: str, record: dict[str, Any]) -> None:
    path = _publish_record_path(workspace, dataset)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex[:8]}.tmp")
    temporary.write_text(
        json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def _publish_counts(store: BiStore) -> tuple[int, int]:
    """Cards, and pending proposals (which are not shared)."""
    if not store.exists:
        return 0, 0
    cards = len(store.card_rows())
    with store._db() as db:  # noqa: SLF001 - one read-only count
        proposals = int(db.execute("SELECT COUNT(*) FROM proposals").fetchone()[0])
    return cards, proposals


def _own_dataset(workspace: Path, dataset: str) -> tuple[BiStore | None, Answer | None]:
    if is_subscribed(dataset):
        return None, _publish_error("dataset_read_only")
    if not DATASET_RE.match(dataset):
        return None, _publish_error("dataset_unknown")
    try:
        store = BiStore(workspace, dataset)
    except BiStoreError as error:
        return None, _publish_error(error.code, error.message)
    if not store.exists:
        return None, _publish_error("dataset_unknown")
    return store, None


def _refresh_pending_review(
    workspace: Path, dataset: str, record: dict[str, Any], publisher: BiPublisher | None
) -> None:
    """A first version waiting for review: ask the platform whether it was
    approved. Any failure leaves the record as it is."""
    last = record.get("last")
    if publisher is None or not isinstance(last, dict) or last.get("status") != "pending_review":
        return
    namespace, _, name = str(last.get("name") or "").partition("/")
    try:
        answer = publisher.bi_dataset_status([(namespace, name)])
    except Exception:  # noqa: BLE001 - the bar keeps saying 待審核
        return
    latest = answer[0].get("latest_version") if answer else None
    if latest == last.get("version"):
        last["status"] = "published"
        if answer[0].get("published_at"):
            last["at"] = answer[0]["published_at"]
        _write_publish_record(workspace, dataset, record)


def _publish_status(
    workspace: Path, dataset: str, namespace: str | None, publisher: BiPublisher | None
) -> Answer:
    store, refused = _own_dataset(workspace, dataset)
    if refused is not None:
        if refused[1]["code"] == "dataset_unknown" and DATASET_RE.match(dataset):
            # A dataset not created yet has never been published.
            return 200, {
                "ok": True,
                "dataset": dataset,
                "last": None,
                "cards": 0,
                "proposals": 0,
                "name": default_platform_name(namespace, dataset),
                "configured": publisher is not None,
            }
        return refused
    assert store is not None
    record = read_publish_record(workspace, dataset) or {}
    _refresh_pending_review(workspace, dataset, record, publisher)
    cards, proposals = _publish_counts(store)
    last = record.get("last") if isinstance(record.get("last"), dict) else None
    return 200, {
        "ok": True,
        "dataset": dataset,
        "last": last,
        "name": record.get("name") or default_platform_name(namespace, dataset),
        "cards": cards,
        "proposals": proposals,
        "configured": publisher is not None,
    }


def _publish(
    workspace: Path,
    given: Mapping[str, Any],
    namespace: str | None,
    publisher: BiPublisher | None,
) -> Answer:
    from capabilities.bi_cards import snapshot as snapshots
    from host_runtime.platform_publish import PublishError

    dataset = str(given.get("dataset") or "")
    store, refused = _own_dataset(workspace, dataset)
    if refused is not None:
        return refused
    assert store is not None
    note = str(given.get("note") or "").strip()
    if not note:
        return _publish_error("note_required")
    if len(note) > MAX_PUBLISH_NOTE:
        return _publish_error("note_required", f"版本說明最多 {MAX_PUBLISH_NOTE} 個字")
    readers = str(given.get("readers") or "team")
    if readers not in PUBLISH_READERS:
        wrong = "visibility_not_allowed" if readers == "public" else "readers_invalid"
        return _publish_error(wrong)
    confirmed = given.get("confirm_organization") is True
    if readers == "organization" and not confirmed:
        return _publish_error("organization_unconfirmed")
    record = read_publish_record(workspace, dataset) or {}
    # The name is chosen at the first publish and kept after that.
    chosen = record.get("name") or given.get("name")
    full = str(chosen or default_platform_name(namespace, dataset) or "")
    if not full:
        return _publish_error("namespace_required")
    space, _, name = full.partition("/")
    if not (PLATFORM_SLUG_RE.match(space) and PLATFORM_SLUG_RE.match(name)):
        return _publish_error("name_invalid")
    team = given.get("team")
    team = str(team) if isinstance(team, str) and team.strip() else None
    cards, _ = _publish_counts(store)
    if cards == 0:
        return _publish_error("dataset_empty")
    if publisher is None:
        return _publish_error("publishing_not_configured")
    try:
        built = snapshots.build_snapshot(store)
    except snapshots.SnapshotError as error:
        if error.code == "secret_found":
            # Where, never what: the value is not in the message.
            return _publish_error(
                "secret_found",
                f"卡片「{error.card}」的欄位「{error.field}」看起來含有密碼或 token，"
                "請先修改再發佈",
                card=error.card,
                field=error.field,
            )
        return _publish_error(error.code, PUBLISH_MESSAGES.get(error.code) or error.message)
    try:
        # The version this snapshot follows is the platform's newest one.
        known = publisher.bi_dataset_status([(space, name)])
        base = known[0].get("latest_version") if known else None
        reply = publisher.publish_bi_dataset(
            space,
            name,
            built,
            note=note,
            base_version=base if isinstance(base, str) else None,
            readers=readers,
            confirm_organization=confirmed,
            team=team,
        )
    except PublishError as error:
        if error.code == "secret_found":
            found = error.message or "Shared Platform 在快照中發現疑似秘密"
            return _publish_error("secret_found", found)
        return _publish_error(error.code, PUBLISH_MESSAGES.get(error.code) or error.message)
    given_asset = reply.get("asset")
    asset: dict[str, Any] = given_asset if isinstance(given_asset, dict) else {}
    state = "pending_review" if reply.get("status") == "pending_review" else "published"
    last = {
        "name": f"{space}/{name}",
        "version": str(asset.get("version") or ""),
        "status": state,
        "at": _publish_now(),
        "readers": readers,
        "note": note,
        "digest": reply.get("digest"),
        "submission_id": reply.get("submission_id"),
    }
    _write_publish_record(workspace, dataset, {"name": f"{space}/{name}", "last": last})
    return 200, {
        "ok": True,
        "dataset": dataset,
        "name": f"{space}/{name}",
        "version": last["version"],
        "status": state,
        "at": last["at"],
        "readers": readers,
    }


def _publish_answer(
    workspace: Path,
    method: str,
    path: str,
    query: Mapping[str, str],
    body: Any,
    namespace: str | None,
    publisher: BiPublisher | None,
) -> Answer:
    if method == "GET" and path == f"{PUBLISH_PREFIX}/status":
        return _publish_status(workspace, str(query.get("dataset") or ""), namespace, publisher)
    if method == "POST" and path == PUBLISH_PREFIX:
        return _publish(workspace, body if isinstance(body, dict) else {}, namespace, publisher)
    return 404, {"ok": False, "code": "route_unknown", "message": "沒有這個 BI 路徑"}


def publish_route(web: Any, method: str, path: str, query: Mapping[str, str], body: Any) -> Answer:
    """`/api/bi/publish*` (BI dataset sharing slice 1): publishing an own
    dataset as this PC's member, and the last publish of a dataset."""
    runtime = web.runtime
    try:
        return _publish_answer(
            runtime.layout.workspace_root,
            method,
            path,
            query,
            body,
            runtime.config.namespace,
            web._publisher(),
        )
    except BiStoreError as error:
        return _error(404 if error.code.endswith("_unknown") else 400, error.code, error.message)
    except Exception as failure:  # noqa: BLE001 - the page shows every failure
        return _error(500, "bi_error", f"BI 發佈內部錯誤（{type(failure).__name__}）")


def web_ai_runtime(web: Any) -> ai_runs.AiRuntime:
    """The Knowledge model (Settings, with its data approval) and the task
    log for AI runs: a run is a background task, so `/api/activity` shows it
    before an Agent Web restart."""
    from capabilities.knowledge_query.handlers import KNOWLEDGE_QUERY_SPEC

    def model() -> Any:
        installed = web.runtime.agent.gateway.bridge.installed.get(KNOWLEDGE_QUERY_SPEC.identity)
        handler = getattr(installed, "handler", None)
        client, alias = getattr(handler, "model", None), getattr(handler, "alias", None)
        return None if client is None or alias is None else (client, str(alias))

    def background(title: str, work: Any) -> None:
        def tracked() -> tuple[str, str]:
            work()
            return "succeeded", title

        threading.Thread(
            target=web.tasks().tracked("bi-ingest", title, "", tracked),
            name="bi-ingest",
            daemon=True,
        ).start()

    return ai_runs.AiRuntime(model=model, background=background)


def handle(handler: Any, method: str, parsed: ParseResult) -> bool:
    """Serve a `/api/bi/` request on `handler` (already token-checked);
    False when the path is not ours."""
    if not parsed.path.startswith("/api/bi/"):
        return False
    body: Any = None
    if method == "POST":
        try:
            length = int(handler.headers.get("Content-Length") or "0")
        except ValueError:
            handler._json(400, {"ok": False, "code": "length_invalid", "message": "缺少長度"})
            return True
        if length > MAX_BI_BODY_BYTES:
            handler._refuse_unread(
                413, {"ok": False, "code": "too_large", "message": "檔案太大（上限 8 MB）"}
            )
            return True
        try:
            body = json.loads(handler.rfile.read(length) or b"{}")
        except (ValueError, TypeError):
            handler._json(400, {"ok": False, "code": "json_invalid", "message": "不是有效的 JSON"})
            return True
    query = {k: v[0] for k, v in parse_qs(parsed.query).items() if v}
    web = handler.server.web
    runtime = web.runtime
    platform = bi_subscriptions.WebPlatform(web) if runtime.platform is not None else None
    if parsed.path.startswith(PUBLISH_PREFIX):
        handler._json(*publish_route(web, method, parsed.path, query, body))
        return True
    try:
        status, payload = route(
            runtime.layout.workspace_root,
            str(runtime.actor),
            method,
            parsed.path,
            query,
            body,
            platform,
            web_ai_runtime(web),
        )
    except Exception as failure:  # noqa: BLE001 - the page shows every failure
        status, payload = (
            500,
            {
                "ok": False,
                "code": "bi_error",
                "message": f"BI 卡片內部錯誤（{type(failure).__name__}）",
            },
        )
    handler._json(status, payload)
    return True
