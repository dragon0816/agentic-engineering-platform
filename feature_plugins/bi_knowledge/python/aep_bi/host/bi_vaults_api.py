"""The `/api/bi/vaults*` routes of Agent Web (BI vaults V4, knowledge repositories R2).

Contracts: `docs/CONTRACTS.md` "Knowledge repositories: the BI type (R2)". A
vault is used through every other `/api/bi/*` route as the dataset
`vault-<id>`; these routes list, create, join, convert and sync vaults and run
the version operations: commit, push, resolve, discard, history, diff, revert,
tag and publish, and say what a share would carry (`share`); and list or save a
skill revision (R3); and import a Dashboard order from Atlas (BI K2, a dry run
first); and preview, apply or drop a skill/tool package (`package`; a zip is uploaded
and exported as raw bytes by `bi_cards_api`). Publish needs `confirm: true` and is
an Agent Web action, never a capability the model can call. Errors are raised as
`BiStoreError` and answered by `bi_cards_api.route`.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from aep_bi.cards import (
    analyses,
    correction,
    domain_assign,
    homes,
    migrate,
    packages,
    packs,
    profile_merge,
    tool_runs,
    vault,
    vault_checks,
    vault_sources,
)
from aep_bi.cards.capability import QUERY_SPEC
from aep_bi.cards.store import DB_FILE, BiStoreError, vault_registry
from aep_bi.host import bi_atlas_import, bi_bench, bi_feed_api
from aep_bi.host.bi_cards_tools import bi_skill_on
from knowledge.repo.repository import RepoError

Answer = tuple[int, dict[str, Any]]

PREFIX = "/api/bi/vaults"


def _error(status: int, code: str, message: str) -> Answer:
    return status, {"ok": False, "code": code, "message": message}


def _start_bench(
    workspace: Path,
    actor: str,
    vault_id: str,
    bench: bi_bench.BenchRuntime | None,
    home: Any = None,
) -> dict[str, Any]:
    vault.Vault(workspace, vault_id)._require_folder()
    home = home or None
    if home is not None and homes.home_problem(home):
        raise BiStoreError("home_invalid", "領域必須是應用資料夾或 library 的項目")
    listed = vault_checks.listing(workspace, vault_id)
    if not any(vault_checks.in_scope(home, q["home"]) for q in listed["questions"]) and not any(
        vault_checks.in_scope(home, vault_checks.case_home(c)) for c in listed["cases"]
    ):
        raise BiStoreError(
            "bench_empty",
            f"「{home}」還沒有測試題或擷取測試，請先新增"
            if home
            else "這個知識庫還沒有測試題或擷取測試，請先新增",
        )
    if any(r.get("status") == "running" for r in bi_bench.reports(workspace, vault_id)[:1]):
        raise BiStoreError("bench_running", "上一次測試還在跑")
    if bench is None:
        raise BiStoreError("bench_unavailable", "這裡不能跑測試（Agent Web 才能跑）")
    run_id = bi_bench.new_run_id()
    ask, extract = bench.ask_for(vault_id, actor), bench.extract_for(vault_id, actor)

    def work() -> None:
        bi_bench.run(
            workspace, vault_id, ask=ask, extract=extract, actor=actor, run_id=run_id, home=home
        )

    bench.background(f"BI 測試：{vault_id}", work)
    return {"run_id": run_id}


def _with_staleness(
    workspace: Path, vault_id: str, report: dict[str, Any] | None, running: bool
) -> dict[str, Any] | None:
    """A finished report with what makes it an old result today (acceptance F24); not while a
    run goes, as the page reads this every 2 s then."""
    if report is None or running or report.get("status") == "running":
        return report
    repo = vault.Vault(workspace, vault_id).repo
    return {**report, "stale": bi_bench.staleness(report, repo.working_units(), repo.published())}


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
        if parts == ["folder-check"]:
            return 200, vault.folder_check(
                str(query.get("path") or ""), str(query.get("mode") or "new")
            )
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
        if len(parts) == 2 and parts[1] == "package":
            # What 「匯出」 can put in a package: the working domain's skills and tools.
            return 200, {"items": packages.exportable(workspace, parts[0], query.get("home"))}
        if len(parts) == 2 and parts[1] == "checks":
            newest = bi_bench.latest(workspace, parts[0])
            # The page reads this every 2 s during a run; a run changes nothing about it until
            # it ends, and on a real vault the digest costs a second each time.
            running = newest is not None and newest.get("status") == "running"
            return 200, {
                **vault_checks.listing(workspace, parts[0]),
                "latest": _with_staleness(
                    workspace,
                    parts[0],
                    bi_bench.latest_for(workspace, parts[0], query.get("home") or None),
                    running,
                ),
                "newest": None
                if newest is None
                else {
                    **{k: newest.get(k) for k in ("run_id", "status", "error")},
                    "progress": bi_bench.progress(newest),
                },
                "standing": {"blocking": [], "notes": []}
                if running
                else bi_bench.standing(workspace, parts[0]),
            }
        if len(parts) == 2 and parts[1] == "share":
            # The share step's table (`BI_PAGE_SIMPLE.md` S6); the page sequences commit, push,
            # tag and publish itself, and the push check stays in `repo.push`.
            newest = bi_bench.latest(workspace, parts[0])
            running = newest is not None and newest.get("status") == "running"
            state = vault.share_state(workspace, parts[0])
            checked = (
                {"domains": [], "standing": {"blocking": [], "notes": []}}
                if running
                else bi_bench.share_check(
                    workspace, state.head, state.working, state.changed, state.plan["published"]
                )
            )
            return 200, {**state.plan, "running": running, **checked}
        if len(parts) == 2 and parts[1] == "analyses":
            return 200, analyses.listing(workspace, parts[0], query.get("home"))
        if len(parts) == 2 and parts[1] == "assign-plan":
            return 200, domain_assign.plan(workspace, parts[0])
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
        if synced.get("moved"):
            bi_feed_api.refresh(workspace, vault_id)  # the published version may have changed
        return 200, {"ok": True, "sync": synced}
    if action == "commit":
        return 200, {"ok": True, **vault.commit(workspace, vault_id, given)}
    if action == "push":
        return 200, {"ok": True, **vault.push(workspace, vault_id)}
    if action == "finalize":
        return 200, {"ok": True, **correction.finalize(workspace, vault_id, given, actor)}
    if action == "resolve":
        return 200, {"ok": True, **vault.resolve(workspace, vault_id, given)}
    if action == "fill-domains":
        return 200, {"ok": True, **vault.fill_domains(workspace, vault_id, given, actor)}
    if action == "relations":
        return 200, {"ok": True, **vault.decide_relation(workspace, vault_id, given, actor)}
    if action == "schema-conflicts":
        return 200, {"ok": True, **vault.decide_schema_conflict(workspace, vault_id, given)}
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
    if action == "skill-default":
        # The shipped text as the next revision, on the person's press after comparing.
        return 200, {"ok": True, **vault.restore_default_skill(workspace, vault_id, given)}
    if action == "profiles":
        return 200, {"ok": True, **vault.save_profile(workspace, vault_id, given)}
    if action == "profile-proposals":
        return 200, {"ok": True, **profile_merge.decide(workspace, vault_id, given, actor)}
    if action == "tool-approve":
        return 200, {"ok": True, **tool_runs.approve(workspace, vault_id, given, actor)}
    if action == "tool-try":
        # The editor's code on one source, shown only (the page's 「試跑」).
        return 200, {"ok": True, **tool_runs.try_code(workspace, vault_id, given)}
    if action == "tool-run":
        return 200, {"ok": True, **tool_runs.run(workspace, vault_id, given, actor)}
    if action == "tools":
        return 200, {"ok": True, **vault.save_tool(workspace, vault_id, given)}
    if action == "publish":
        published = vault.publish(workspace, vault_id, given)
        bi_feed_api.refresh(workspace, vault_id)
        return 200, {"ok": True, **published}
    if action == "assign":
        return 200, {"ok": True, **domain_assign.apply(workspace, vault_id, given)}
    if action == "homes":
        return 200, {"ok": True, **vault.create_home(workspace, vault_id, given)}
    if action == "checks":
        if given.get("delete"):
            return 200, {"ok": True, **vault_checks.delete(workspace, vault_id, given["delete"])}
        if given.get("kind") == "case":
            return 200, {"ok": True, **vault_checks.save_case(workspace, vault_id, given)}
        return 200, {"ok": True, **vault_checks.save_question(workspace, vault_id, given)}
    if action == "bench":
        return 200, {
            "ok": True,
            **_start_bench(workspace, actor, vault_id, bench, given.get("home")),
        }
    if action == "migrate-domains":
        # BI D3/D4: a dry run unless `apply` with the dry run's token.
        dataset = vault.dataset_name(vault_id)
        return 200, {"ok": True, **migrate.migrate_domains(workspace, dataset, given, actor)}
    if action == "atlas-import":
        # BI K2: a dry run of an Atlas dashboard's order, or `apply` with its token.
        return 200, {"ok": True, **bi_atlas_import.import_order(workspace, vault_id, given)}
    if action == "package":
        return 200, {"ok": True, **_package(workspace, vault_id, given)}
    if action == "packs":
        if isinstance(given.get("export"), dict):
            return 200, {
                "ok": True,
                "pack": packs.export_pack(workspace, vault_id, given["export"]),
            }
        if given.get("update") == packs.DEFAULT_ID:
            return 200, {"ok": True, **packs.update_default(workspace, vault_id)}
        return 200, {"ok": True, **packs.import_pack(workspace, vault_id, given.get("import"))}
    if action == "analyses":
        if given.get("delete"):
            return 200, {"ok": True, **analyses.delete(workspace, vault_id, given["delete"])}
        if isinstance(given.get("save"), dict):
            return 200, {"ok": True, **analyses.save(workspace, vault_id, given["save"])}
        if "dashboard" in given:
            return 200, {
                "ok": True,
                **analyses.set_dashboard(
                    workspace, vault_id, given["dashboard"], given.get("home")
                ),
            }
        params = given.get("params") if isinstance(given.get("params"), dict) else {}
        ran = analyses.run_saved(workspace, vault_id, given.get("run"), params, given.get("home"))
        bi_feed_api.refresh(workspace, vault_id)
        return 200, {"ok": True, **ran}
    return _error(404, "route_unknown", "沒有這個 BI 路徑")


def _package(workspace: Path, vault_id: str, given: Mapping[str, Any]) -> dict[str, Any]:
    """A skill/tool package: a folder's preview, one batch of an apply, or dropping it."""
    if isinstance(given.get("preview"), dict):
        asked = given["preview"]
        unpacked = packages.read_files(asked.get("files"))
        return packages.preview(
            workspace, vault_id, asked.get("home"), unpacked, str(asked.get("name") or "")
        )
    if isinstance(given.get("apply"), dict):
        return packages.apply_batch(workspace, vault_id, given["apply"])
    if "discard" in given:
        return packages.discard(workspace, vault_id, given["discard"])
    raise BiStoreError("package_invalid", "要給 preview、apply 或 discard")


# -- whether the chat can ask a vault (BI_VAULT_ASKING.md V2) ------------------------------


def askable_vaults(
    web: Any,
    granted: Callable[[Any, Any], bool],
    entry: Callable[[str, str, str, Any, list[str]], dict[str, Any]],
) -> list[dict[str, Any]]:
    """Each BI vault on this PC, for `host_runtime.knowledge_binding`, which names no
    BI type (ADR-K10) and supplies the entry's shape. Its grant check `granted` is
    not used: a BI vault shared to this person is askable (owner 2026-11-17)."""
    workspace = Path(web.runtime.layout.workspace_root)
    return [_askable(web, item, entry) for item in vault_registry(workspace)]


def _askable(
    web: Any,
    item: Mapping[str, Any],
    entry: Callable[[str, str, str, Any, list[str]], dict[str, Any]],
) -> dict[str, Any]:
    gateway = web.runtime.agent.gateway
    workspace = Path(web.runtime.layout.workspace_root)
    vault_id = str(item["id"])
    codes: list[str] = []
    if gateway.bridge.installed.get(QUERY_SPEC.identity) is None:
        codes.append("capability_missing")
    else:
        # The BI Skill switch is the owner's feature switch, not a permission.
        if not bi_skill_on(gateway):
            codes.append("skill_off")
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
