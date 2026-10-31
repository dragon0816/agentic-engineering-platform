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

from capabilities.bi_cards import vault, vault_checks
from capabilities.bi_cards.store import BiStoreError
from host_runtime import bi_bench

Answer = tuple[int, dict[str, Any]]

PREFIX = "/api/bi/vaults"


def _error(status: int, code: str, message: str) -> Answer:
    return status, {"ok": False, "code": code, "message": message}


def _start_bench(
    workspace: Path, actor: str, vault_id: str, bench: bi_bench.BenchRuntime | None
) -> dict[str, Any]:
    vault.Vault(workspace, vault_id)._require_folder()
    listed = vault_checks.listing(workspace, vault_id)
    if not listed["questions"] and not listed["cases"]:
        raise BiStoreError("bench_empty", "這個知識庫還沒有測試題或擷取測試，請先新增")
    if any(r.get("status") == "running" for r in bi_bench.reports(workspace, vault_id)[:1]):
        raise BiStoreError("bench_running", "上一次測試還在跑")
    if bench is None:
        raise BiStoreError("bench_unavailable", "這裡不能跑測試（Agent Web 才能跑）")
    run_id = bi_bench.new_run_id()
    ask, extract = bench.ask_for(vault_id, actor), bench.extract_for(vault_id, actor)

    def work() -> None:
        bi_bench.run(workspace, vault_id, ask=ask, extract=extract, actor=actor, run_id=run_id)

    bench.background(f"BI 測試：{vault_id}", work)
    return {"run_id": run_id}


def route(
    workspace: Path,
    actor: str,
    method: str,
    path: str,
    query: Mapping[str, str],
    given: dict[str, Any],
    bench: bi_bench.BenchRuntime | None = None,
) -> Answer:
    """One request under `/api/bi/vaults` (`bench` runs a benchmark, BI T1)."""
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
        if len(parts) == 2 and parts[1] == "checks":
            return 200, {
                **vault_checks.listing(workspace, parts[0]),
                "latest": bi_bench.latest(workspace, parts[0]),
            }
        if len(parts) == 2 and parts[1] == "bench":
            wanted = str(query.get("run") or "")
            found = [r for r in bi_bench.reports(workspace, parts[0]) if r["run_id"] == wanted]
            if not found:
                return _error(404, "run_unknown", "沒有這次測試")
            return 200, {"report": found[0]}
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
    if action == "checks":
        if given.get("delete"):
            return 200, {"ok": True, **vault_checks.delete(workspace, vault_id, given["delete"])}
        if given.get("kind") == "case":
            return 200, {"ok": True, **vault_checks.save_case(workspace, vault_id, given)}
        return 200, {"ok": True, **vault_checks.save_question(workspace, vault_id, given)}
    if action == "bench":
        return 200, {"ok": True, **_start_bench(workspace, actor, vault_id, bench)}
    return _error(404, "route_unknown", "沒有這個 BI 路徑")
