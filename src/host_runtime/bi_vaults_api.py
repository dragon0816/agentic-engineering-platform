"""The `/api/bi/vaults*` routes of Agent Web (BI vaults phase V4).

Contract: `docs/CONTRACTS.md` "BI vaults: folder, change files, sync". A vault
is used through every other `/api/bi/*` route as the dataset `vault-<id>`;
these routes only list, create, join, sync, convert and report on vaults.
Errors are raised as `BiStoreError` and answered by `bi_cards_api.route`.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from capabilities.bi_cards import vault

Answer = tuple[int, dict[str, Any]]

PREFIX = "/api/bi/vaults"


def _error(status: int, code: str, message: str) -> Answer:
    return status, {"ok": False, "code": code, "message": message}


def route(
    workspace: Path,
    actor: str,
    method: str,
    path: str,
    query: Mapping[str, str],
    given: dict[str, Any],
) -> Answer:
    """One request under `/api/bi/vaults`."""
    parts = path.split("/")[4:]  # after "", "api", "bi", "vaults"
    if method == "GET":
        if not parts:
            return 200, {"vaults": vault.listing(workspace)}
        if len(parts) == 2 and parts[1] == "status":
            return 200, vault.status(workspace, parts[0])
        return _error(404, "route_unknown", "沒有這個 BI 路徑")
    if method != "POST":
        return _error(405, "method_not_allowed", "只接受 GET 與 POST")
    if not parts:
        return 200, {"ok": True, **vault.create(workspace, given, actor)}
    if parts == ["join"]:
        return 200, {"ok": True, **vault.join(workspace, given, actor)}
    if parts == ["convert"]:
        return 200, {"ok": True, **vault.convert(workspace, given, actor)}
    if len(parts) == 2 and parts[1] == "sync":
        return 200, {"ok": True, "sync": vault.sync(workspace, parts[0])}
    return _error(404, "route_unknown", "沒有這個 BI 路徑")
