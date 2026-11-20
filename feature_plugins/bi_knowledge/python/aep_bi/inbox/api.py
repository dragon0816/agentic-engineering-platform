"""The page's inbox routes, under BI 「管理」 → 「Telegram 收集」.

    GET  /api/bi/inbox?dataset=<vault dataset>   the vault's domains with bot and times,
                                                 and the Host's BI collection bots
    POST /api/bi/inbox/settings                  {domain, bot, enabled, collect_at, review_at}

A bot is one configured in the Host's Telegram settings (`collection_bots`, feature
`bi-knowledge`); its token stays a secret reference there. Every answer is immediate.
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
FEATURE_NAME = "bi-knowledge"
Answer = tuple[int, dict[str, Any]]


def _error(status: int, code: str, message: str) -> Answer:
    return status, {"ok": False, "code": code, "message": message}


def _row(setting: store.Setting | None, domain: dom.Domain, inbox: Inbox) -> dict[str, Any]:
    now = datetime.now(UTC)
    waiting = len(inbox.due(domain.key))
    return {
        "domain": domain.key,
        "label": domain.label,
        "bot": setting.bot if setting else None,
        "enabled": bool(setting and setting.enabled),
        "collect_at": setting.collect_at if setting else None,
        "review_at": setting.review_at if setting else None,
        "waiting": waiting,
        "next": dom.when(setting.collect_at if setting and setting.enabled else None, now),
    }


def bots() -> list[dict[str, str]]:
    """The Host's collection bots for BI, as the page lists them."""
    from aep_bi.inbox.runtime import RUNTIME

    messenger = RUNTIME.messenger
    listed = messenger.bots() if messenger is not None else ()
    return [{"name": b.name, "target": b.target} for b in listed if b.feature == FEATURE_NAME]


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
        return 200, {
            "ok": True,
            "domains": [_row(settings.get(d.key), d, inbox) for d in mine],
            "bots": bots(),
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
        bot = str(body.get("bot") or "") or None
        if bot is not None and bot not in {b["name"] for b in bots()}:
            return _error(404, "bot_unknown", "這台電腦沒有設定這個收集 bot")
        enabled = body.get("enabled") is True
        if enabled and collect_at is None:
            return _error(400, "collect_time_missing", "開啟前先填收集時間")
        saved = inbox.save_setting(
            domain.key, enabled=enabled, collect_at=collect_at, review_at=review_at, bot=bot
        )
        return 200, {"ok": True, "domain": _row(saved, domain, inbox)}
    return _error(404, "route_unknown", "沒有這個 BI 路徑")
