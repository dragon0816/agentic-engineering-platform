"""The `/api/bi/vaults*` routes of Agent Web (BI vaults V4, knowledge repositories R2).

Contracts: `docs/CONTRACTS.md` "Knowledge repositories: the BI type (R2)". A
vault is used through every other `/api/bi/*` route as the dataset
`vault-<id>`; these routes list, create, join, convert and sync vaults and run
the version operations: commit, push, resolve, discard, history, diff, revert,
tag and publish; and list or save a skill revision (R3). Publish needs
`confirm: true` and is an Agent Web action, never a capability the model can
call. Errors are raised as `BiStoreError` and answered by `bi_cards_api.route`.
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
        if len(parts) == 2 and parts[1] == "pending":
            return 200, vault.pending(workspace, parts[0])
        if len(parts) == 2 and parts[1] == "history":
            limit = (
                int(query.get("limit") or 50) if str(query.get("limit") or "50").isdigit() else 50
            )
            return 200, vault.history(workspace, parts[0], limit)
        if len(parts) == 2 and parts[1] == "skills":
            return 200, vault.skills(workspace, parts[0])
        if len(parts) == 2 and parts[1] == "diff":
            return 200, vault.diff(workspace, parts[0], str(query.get("commit") or ""))
        return _error(404, "route_unknown", "沒有這個 BI 路徑")
    if method != "POST":
        return _error(405, "method_not_allowed", "只接受 GET 與 POST")
    if not parts:
        return 200, {"ok": True, **vault.create(workspace, given, actor)}
    if parts == ["join"]:
        return 200, {"ok": True, **vault.join(workspace, given, actor)}
    if parts == ["convert"]:
        return 200, {"ok": True, **vault.convert(workspace, given, actor)}
    if len(parts) != 2:
        return _error(404, "route_unknown", "沒有這個 BI 路徑")
    vault_id, action = parts
    if action == "sync":
        return 200, {"ok": True, "sync": vault.sync(workspace, vault_id)}
    if action == "commit":
        return 200, {"ok": True, **vault.commit(workspace, vault_id, given)}
    if action == "push":
        return 200, {"ok": True, **vault.push(workspace, vault_id)}
    if action == "resolve":
        return 200, {"ok": True, **vault.resolve(workspace, vault_id, given)}
    if action == "discard":
        return 200, {"ok": True, **vault.discard(workspace, vault_id)}
    if action == "revert":
        return 200, {"ok": True, **vault.revert(workspace, vault_id, given)}
    if action == "tag":
        return 200, {"ok": True, **vault.tag(workspace, vault_id, given)}
    if action == "skills":
        return 200, {"ok": True, **vault.save_skill(workspace, vault_id, given)}
    if action == "publish":
        return 200, {"ok": True, **vault.publish(workspace, vault_id, given)}
    return _error(404, "route_unknown", "沒有這個 BI 路徑")
