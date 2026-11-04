"""The `/api/bi/vaults*` routes of Agent Web (BI vaults V4, knowledge repositories R2).

Contracts: `docs/CONTRACTS.md` "Knowledge repositories: the BI type (R2)". A
vault is used through every other `/api/bi/*` route as the dataset
`vault-<id>`; these routes list, create, join, convert and sync vaults and run
the version operations: commit, push, resolve, discard, history, diff, revert,
tag and publish; and list or save a skill revision (R3); and import a
Dashboard order from Atlas (BI K2, a dry run first). Publish needs
`confirm: true` and is an Agent Web action, never a capability the model can
call. Errors are raised as `BiStoreError` and answered by `bi_cards_api.route`.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from capabilities.bi_cards import (
    analyses,
    migrate,
    packs,
    profile_merge,
    tool_runs,
    vault,
    vault_checks,
    vault_sources,
)
from capabilities.bi_cards.capability import QUERY_SPEC
from capabilities.bi_cards.store import DB_FILE, BiStoreError, vault_registry
from host_runtime import bi_atlas_import, bi_bench, bi_feed_api
from host_runtime.bi_cards_tools import bi_skill_on
from knowledge.repo.repository import RepoError

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
        if len(parts) == 2 and parts[1] == "tools":
            return 200, tool_runs.listing(workspace, parts[0])
        if len(parts) == 2 and parts[1] == "profiles":
            return 200, vault.profiles(workspace, parts[0])
        if len(parts) == 2 and parts[1] == "checks":
            return 200, {
                **vault_checks.listing(workspace, parts[0]),
                "latest": bi_bench.latest(workspace, parts[0]),
            }
        if len(parts) == 2 and parts[1] == "analyses":
            return 200, analyses.listing(workspace, parts[0])
        if len(parts) == 2 and parts[1] == "packs":
            return 200, packs.summary(workspace, parts[0])
        if len(parts) == 2 and parts[1] == "atlas-dashboards":
            # BI K2: the names of Atlas's dashboards (read server-side, loopback).
            port = bi_atlas_import.port_of(query.get("port"))
            return 200, {"port": port, "names": bi_atlas_import.names(port)}
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
        joined = vault.join(workspace, given, actor)
        bi_feed_api.refresh(workspace, joined["vault"]["id"])
        return 200, {"ok": True, **joined}
    if parts == ["convert"]:
        return 200, {"ok": True, **vault.convert(workspace, given, actor)}
    if len(parts) != 2:
        return _error(404, "route_unknown", "沒有這個 BI 路徑")
    vault_id, action = parts
    if action == "sync":
        synced = vault.sync(workspace, vault_id)
        bi_feed_api.refresh(workspace, vault_id)  # the published version may have changed
        return 200, {"ok": True, "sync": synced}
    if action == "commit":
        return 200, {"ok": True, **vault.commit(workspace, vault_id, given)}
    if action == "push":
        return 200, {"ok": True, **vault.push(workspace, vault_id)}
    if action == "resolve":
        return 200, {"ok": True, **vault.resolve(workspace, vault_id, given)}
    if action == "relations":
        return 200, {"ok": True, **vault.decide_relation(workspace, vault_id, given, actor)}
    if action == "discard":
        return 200, {"ok": True, **vault.discard(workspace, vault_id)}
    if action == "revert":
        return 200, {"ok": True, **vault.revert(workspace, vault_id, given)}
    if action == "tag":
        return 200, {"ok": True, **vault.tag(workspace, vault_id, given)}
    if action == "share-source":
        # A source only on this PC goes to the shared folder at the next push.
        return 200, {
            "ok": True,
            "source": vault_sources.share(
                workspace, vault_id, str(given.get("source_id") or ""), given.get("folder")
            ),
        }
    if action == "withdraw-source":
        # A person's confirm only; no capability or model reaches this.
        return 200, {"ok": True, **vault_sources.withdraw(workspace, vault_id, given)}
    if action == "skills":
        return 200, {"ok": True, **vault.save_skill(workspace, vault_id, given)}
    if action == "profiles":
        return 200, {"ok": True, **vault.save_profile(workspace, vault_id, given)}
    if action == "profile-proposals":
        return 200, {"ok": True, **profile_merge.decide(workspace, vault_id, given, actor)}
    if action == "tool-approve":
        return 200, {"ok": True, **tool_runs.approve(workspace, vault_id, given, actor)}
    if action == "tool-run":
        return 200, {"ok": True, **tool_runs.run(workspace, vault_id, given, actor)}
    if action == "tools":
        return 200, {"ok": True, **vault.save_tool(workspace, vault_id, given)}
    if action == "publish":
        published = vault.publish(workspace, vault_id, given)
        bi_feed_api.refresh(workspace, vault_id)
        return 200, {"ok": True, **published}
    if action == "checks":
        if given.get("delete"):
            return 200, {"ok": True, **vault_checks.delete(workspace, vault_id, given["delete"])}
        if given.get("kind") == "case":
            return 200, {"ok": True, **vault_checks.save_case(workspace, vault_id, given)}
        return 200, {"ok": True, **vault_checks.save_question(workspace, vault_id, given)}
    if action == "bench":
        return 200, {"ok": True, **_start_bench(workspace, actor, vault_id, bench)}
    if action == "migrate-domains":
        # BI D3/D4: a dry run unless `apply` with the dry run's token.
        dataset = vault.dataset_name(vault_id)
        return 200, {"ok": True, **migrate.migrate_domains(workspace, dataset, given, actor)}
    if action == "atlas-import":
        # BI K2: a dry run of an Atlas dashboard's order, or `apply` with its token.
        return 200, {"ok": True, **bi_atlas_import.import_order(workspace, vault_id, given)}
    if action == "packs":
        if isinstance(given.get("export"), dict):
            return 200, {
                "ok": True,
                "pack": packs.export_pack(workspace, vault_id, given["export"]),
            }
        return 200, {"ok": True, **packs.import_pack(workspace, vault_id, given.get("import"))}
    if action == "analyses":
        if given.get("delete"):
            return 200, {"ok": True, **analyses.delete(workspace, vault_id, given["delete"])}
        if isinstance(given.get("save"), dict):
            return 200, {"ok": True, **analyses.save(workspace, vault_id, given["save"])}
        if "dashboard" in given:
            return 200, {
                "ok": True,
                **analyses.set_dashboard(workspace, vault_id, given["dashboard"]),
            }
        params = given.get("params") if isinstance(given.get("params"), dict) else {}
        ran = analyses.run_saved(workspace, vault_id, given.get("run"), params)
        bi_feed_api.refresh(workspace, vault_id)
        return 200, {"ok": True, **ran}
    return _error(404, "route_unknown", "沒有這個 BI 路徑")


# -- whether the chat can ask a vault (BI_VAULT_ASKING.md V2) ------------------------------


def askable_vaults(
    web: Any,
    granted: Callable[[Any, Any], bool],
    entry: Callable[[str, str, str, Any, list[str]], dict[str, Any]],
) -> list[dict[str, Any]]:
    """Each BI vault on this PC, for `host_runtime.knowledge_binding`, which names no
    BI type (ADR-K10) and supplies its grant check and the entry's shape."""
    workspace = Path(web.runtime.layout.workspace_root)
    return [_askable(web, item, granted, entry) for item in vault_registry(workspace)]


def _askable(
    web: Any,
    item: Mapping[str, Any],
    granted: Callable[[Any, Any], bool],
    entry: Callable[[str, str, str, Any, list[str]], dict[str, Any]],
) -> dict[str, Any]:
    gateway = web.runtime.agent.gateway
    workspace = Path(web.runtime.layout.workspace_root)
    vault_id = str(item["id"])
    codes: list[str] = []
    if gateway.bridge.installed.get(QUERY_SPEC.identity) is None:
        codes.append("capability_missing")
    else:
        if not bi_skill_on(gateway):
            codes.append("skill_off")
        if not granted(web, QUERY_SPEC):
            codes.append("not_granted")
    folder = Path(str(item.get("path") or ""))
    try:
        target = vault.Vault(workspace, vault_id)
    except (BiStoreError, RepoError):
        target = None
    if target is None or not target.reachable:
        built = target is not None and (target.local / vault.PUBLISHED_DIR / DB_FILE).is_file()
        if built:
            return entry("bi", vault_id, vault_id, None, codes)
        code = "unreadable_format" if folder.is_dir() else "unreachable"
        return entry("bi", vault_id, vault_id, None, [*codes, code])
    try:
        target.repo.sync()
        reads = target.reads()
        store = vault.reading_store(workspace, target.dataset)
        cards = len(store.card_rows())
    except (BiStoreError, RepoError):
        return entry("bi", vault_id, vault_id, None, [*codes, "unreachable"])
    if not reads["commit"] or not cards:
        codes.append("nothing_pushed")
    elif not reads["tag"]:
        codes.append("never_published")
    return entry("bi", vault_id, str(target.repo.document["title"]), reads, codes)
