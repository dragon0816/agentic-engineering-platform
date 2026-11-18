"""The `/api/knowledge/repos*` routes of Agent Web (knowledge repositories R4a).

Contract: `docs/CONTRACTS.md` "Knowledge repositories: wiki repositories on this
PC (R4a)". These routes list, create, import (a copy of a wiki folder) and join
wiki repositories and run the version operations: sync, status, pending,
commit, push, resolve, discard, history, diff, revert, tag and publish, and
this PC's intake and question folders of a repository (`settings`, R4b).
Publish needs `confirm: true` and is an Agent Web action, never a capability
the model can call. `route` is pure apart from the repository files; `handle`
serves it on the web handler (already token-checked).
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from urllib.parse import ParseResult, parse_qs

from aep_wiki.knowledge import wiki_repos_write
from knowledge import wiki_repos
from knowledge.repo.repository import RepoError

Answer = tuple[int, dict[str, Any]]

PREFIX = "/api/knowledge/repos"
MAX_BODY_BYTES = 1024 * 1024
#: Refusals that conflict with the current state (409).
CONFLICTS = {
    "repo_exists",
    "repo_registered",
    "repo_unreachable",
    "tag_exists",
    "work_not_clean",
    "path_taken",
    "record_exists",
    "target_not_materialized",
}


def _error(status: int, code: str, message: str, **detail: Any) -> Answer:
    return status, {"ok": False, "code": code, "message": message, **detail}


def _limit(query: Mapping[str, str]) -> int:
    text = str(query.get("limit") or "50")
    return min(int(text), 500) if text.isdigit() and int(text) > 0 else 50


def route(
    workspace: Path,
    actor: str,
    method: str,
    path: str,
    query: Mapping[str, str],
    given: Any,
) -> Answer:
    """One request under `/api/knowledge/repos`."""
    if given is not None and not isinstance(given, dict):
        return _error(400, "body_invalid", "內容必須是 JSON 物件")
    body: dict[str, Any] = given or {}
    try:
        return _route(workspace, actor, method, path, query, body)
    except RepoError as failure:
        if failure.code.endswith("_unknown") and failure.code != "commit_unknown":
            status = 404
        else:
            status = 409 if failure.code in CONFLICTS else 400
        return _error(status, failure.code, failure.message, **failure.detail)


def _route(
    workspace: Path,
    actor: str,
    method: str,
    path: str,
    query: Mapping[str, str],
    given: dict[str, Any],
) -> Answer:
    parts = [p for p in path[len(PREFIX) :].split("/") if p]
    if method == "GET":
        if not parts:
            return 200, {"repos": wiki_repos.listing(workspace)}
        if len(parts) == 2:
            repo_id, what = parts
            if what == "status":
                return 200, wiki_repos_write.status(workspace, repo_id)
            if what == "pending":
                return 200, wiki_repos_write.pending(workspace, repo_id)
            if what == "history":
                return 200, wiki_repos_write.history(workspace, repo_id, _limit(query))
            if what == "diff":
                return 200, wiki_repos_write.diff(
                    workspace, repo_id, str(query.get("commit") or "")
                )
            if what == "settings":
                return 200, wiki_repos_write.work_settings(workspace, repo_id)
        return _error(404, "route_unknown", "沒有這個知識庫路徑")
    if method != "POST":
        return _error(405, "method_not_allowed", "只接受 GET 與 POST")
    if not parts:
        return 200, {"ok": True, **wiki_repos_write.create(workspace, given, actor)}
    if parts == ["import"]:
        return 200, {"ok": True, **wiki_repos_write.import_copy(workspace, given, actor)}
    if parts == ["join"]:
        return 200, {"ok": True, **wiki_repos_write.join(workspace, given, actor)}
    if len(parts) != 2:
        return _error(404, "route_unknown", "沒有這個知識庫路徑")
    repo_id, action = parts
    if action == "sync":
        return 200, {"ok": True, "sync": wiki_repos.repository(workspace, repo_id).sync()}
    if action == "commit":
        return 200, {"ok": True, **wiki_repos_write.commit(workspace, repo_id, given)}
    if action == "push":
        return 200, {"ok": True, **wiki_repos_write.push(workspace, repo_id)}
    if action == "resolve":
        return 200, {"ok": True, **wiki_repos_write.resolve(workspace, repo_id, given)}
    if action == "discard":
        return 200, {"ok": True, **wiki_repos_write.discard(workspace, repo_id)}
    if action == "revert":
        return 200, {"ok": True, **wiki_repos_write.revert(workspace, repo_id, given)}
    if action == "tag":
        return 200, {"ok": True, **wiki_repos_write.tag(workspace, repo_id, given)}
    if action == "publish":
        return 200, {"ok": True, **wiki_repos_write.publish(workspace, repo_id, given)}
    if action == "settings":
        return 200, {"ok": True, **wiki_repos_write.save_work_settings(workspace, repo_id, given)}
    return _error(404, "route_unknown", "沒有這個知識庫路徑")


def handle(handler: Any, method: str, parsed: ParseResult) -> bool:
    """Serve a `/api/knowledge/repos` request on `handler`; False when the
    path is not ours."""
    if parsed.path != PREFIX and not parsed.path.startswith(PREFIX + "/"):
        return False
    body: Any = None
    if method == "POST":
        try:
            length = int(handler.headers.get("Content-Length") or "0")
        except ValueError:
            handler._json(400, {"ok": False, "code": "length_invalid", "message": "缺少長度"})
            return True
        if length > MAX_BODY_BYTES:
            handler._refuse_unread(
                413, {"ok": False, "code": "too_large", "message": "內容太大（上限 1 MB）"}
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
        status, payload = _error(
            500, "knowledge_repo_error", f"知識庫內部錯誤（{type(failure).__name__}）"
        )
    handler._json(status, payload)
    return True
