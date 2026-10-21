"""The `/api/bi/*` routes of Agent Web (BI Knowledge Case A, owner 2026-10-21).

Mounted in `web.py` after the loopback and Bearer-token guards, like every
other `/api/*` route. The contract is in `docs/CONTRACTS.md` ("BI cards
API"). Errors are `{"ok": false, "code", "message"}` with a 4xx status.
Imports and edits are recorded as `<actor> via web`.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from urllib.parse import ParseResult, parse_qs

from capabilities.bi_cards import dashboard, importer, service
from capabilities.bi_cards.schema import registry
from capabilities.bi_cards.store import DEFAULT_DATASET, BiStore, BiStoreError

#: A CSV travels in the JSON body; larger than an ordinary request.
MAX_BI_BODY_BYTES = 8 * 1024 * 1024

Answer = tuple[int, dict[str, Any]]


def _error(status: int, code: str, message: str) -> Answer:
    return status, {"ok": False, "code": code, "message": message}


def _dataset(value: Any) -> str:
    return str(value or DEFAULT_DATASET)


def route(
    workspace: Path,
    actor: str,
    method: str,
    path: str,
    query: Mapping[str, str],
    body: Any,
) -> Answer:
    """One request; pure apart from the dataset files."""
    try:
        return _route(workspace, actor, method, path, query, body)
    except BiStoreError as error:
        status = 404 if error.code.endswith("_unknown") else 400
        if error.code == "stale_edit":
            return 409, {
                "ok": False,
                "code": "stale_edit",
                "message": error.message,
                **error.detail,
            }
        return _error(status, error.code, error.message)
    except importer.ImportError_ as error:
        return _error(400, error.code, error.message)


def _route(
    workspace: Path,
    actor: str,
    method: str,
    path: str,
    query: Mapping[str, str],
    body: Any,
) -> Answer:
    given: dict[str, Any] = body if isinstance(body, dict) else {}
    who = f"{actor} via web"
    if method == "GET":
        store = BiStore(workspace, _dataset(query.get("dataset")))
        if path == "/api/bi/schema":
            return 200, service.schema_api()
        if path == "/api/bi/datasets":
            return 200, {"datasets": service.dataset_list(workspace)}
        if path == "/api/bi/dashboard":
            return 200, dashboard.dashboard(store, str(query.get("domain") or "robotics"))
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
    if path == "/api/bi/demo/load":
        store = BiStore(workspace, _dataset(given.get("dataset")))
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
    parts = path.split("/")
    if len(parts) == 6 and parts[:4] == ["", "api", "bi", "cards"] and parts[5] == "field":
        return _set_field(workspace, who, parts[4], given)
    return _error(404, "route_unknown", "沒有這個 BI 路徑")


def _set_field(workspace: Path, who: str, card_id: str, given: dict[str, Any]) -> Answer:
    store = BiStore(workspace, _dataset(given.get("dataset")))
    card = store.card(card_id)
    if card is None:
        return _error(404, "card_unknown", "找不到這張卡片")
    entity = registry().type(card["entity_type"])
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
        value = [str(v).strip() for v in raw if str(v).strip()] if item.is_list else None
        if value is None:
            return _error(400, "value_invalid", f"{item.label} 不是清單欄位")
    else:
        value, problems = registry().normalize(item, str(raw))
        if value is None:
            message = problems[0][1] if problems else f"{item.label} 的值無法採用"
            return _error(400, "value_invalid", message)
    version = store.set_field(card_id, name, value, base_version=base, actor=who, reason=reason)
    return 200, {"ok": True, "version": version}


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
    runtime = handler.server.web.runtime
    try:
        status, payload = route(
            runtime.layout.workspace_root, str(runtime.actor), method, parsed.path, query, body
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
