"""The page's inbox routes, under BI 「管理」 → 「Telegram 收集」.

    GET  /api/bi/inbox?dataset=<vault dataset>   the vault's domains with their times, and 未分類
    POST /api/bi/inbox/settings                  {domain, enabled, collect_at, review_at}
    POST /api/bi/inbox/assign                    {item, domain}: a 未分類 item to a domain

Every answer is immediate: saving two times or assigning an item waits on nothing.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from aep_bi.inbox import domains as dom
from aep_bi.inbox import store
from aep_bi.inbox.store import Inbox

PREFIX = "/api/bi/inbox"
Answer = tuple[int, dict[str, Any]]


def _error(status: int, code: str, message: str) -> Answer:
    return status, {"ok": False, "code": code, "message": message}


def _row(setting: store.Setting | None, domain: dom.Domain, inbox: Inbox) -> dict[str, Any]:
    now = datetime.now(UTC)
    waiting = len(inbox.due(domain.key))
    return {
        "domain": domain.key,
        "label": domain.label,
        "enabled": bool(setting and setting.enabled),
        "collect_at": setting.collect_at if setting else None,
        "review_at": setting.review_at if setting else None,
        "waiting": waiting,
        "next": dom.when(setting.collect_at if setting and setting.enabled else None, now),
    }


def route(
    workspace: Path, actor: str, method: str, path: str, query: Mapping[str, str], given: Any
) -> Answer:
    body: dict[str, Any] = given if isinstance(given, dict) else {}
    inbox = Inbox(workspace)
    listed = dom.listed(workspace)
    if method == "GET" and path == PREFIX:
        dataset = str(query.get("dataset") or "")
        mine = [d for d in listed if not dataset or d.dataset == dataset]
        settings = inbox.settings()
        unassigned = [
            {
                "id": item["id"],
                "title": item["title"] or item["file_name"] or item["url"] or "",
                "url": item["url"],
                "sender": item["actor"],
                "received_at": item["received_at"],
                "suggested": item["suggested"],
            }
            for item in inbox.items(statuses=(store.UNASSIGNED,), limit=100)
        ]
        return 200, {
            "ok": True,
            "domains": [_row(settings.get(d.key), d, inbox) for d in mine],
            "all_domains": [{"domain": d.key, "label": d.label} for d in listed],
            "unassigned": unassigned,
        }
    if method != "POST":
        return _error(404, "route_unknown", "沒有這個 BI 路徑")
    if path == PREFIX + "/settings":
        domain = dom.by_key(listed, str(body.get("domain") or ""))
        if domain is None:
            return _error(404, "domain_unknown", "沒有這個領域")
        collect_at = dom.parse_clock(body.get("collect_at")) if body.get("collect_at") else None
        review_at = dom.parse_clock(body.get("review_at")) if body.get("review_at") else None
        if (body.get("collect_at") and collect_at is None) or (
            body.get("review_at") and review_at is None
        ):
            return _error(400, "time_invalid", "時間要寫成 HH:MM（24 小時制），例如 07:30")
        enabled = body.get("enabled") is True
        if enabled and collect_at is None:
            return _error(400, "collect_time_missing", "開啟前先填收集時間")
        saved = inbox.save_setting(
            domain.key, enabled=enabled, collect_at=collect_at, review_at=review_at
        )
        return 200, {"ok": True, "domain": _row(saved, domain, inbox)}
    if path == PREFIX + "/assign":
        domain = dom.by_key(listed, str(body.get("domain") or ""))
        number = body.get("item")
        item = inbox.item(number) if isinstance(number, int) else None
        if domain is None or item is None:
            return _error(404, "item_unknown", "找不到這一筆或這個領域")
        if item["status"] != store.UNASSIGNED:
            return _error(409, "item_not_unassigned", "這一筆已經不在未分類")
        inbox.pick(int(item["id"]), domain.key, "person")
        inbox.note_recent(str(item["actor"]), domain.key)
        return 200, {"ok": True, "item": inbox.item(int(item["id"]))}
    return _error(404, "route_unknown", "沒有這個 BI 路徑")
