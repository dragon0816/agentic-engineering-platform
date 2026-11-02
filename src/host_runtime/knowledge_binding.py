"""Whether the chat can ask a vault, and binding a wiki repository to the Agent.

`docs/phases/BI_VAULT_ASKING.md` V2. `askable` says, for each wiki repository and
BI vault on this PC, whether the general chat can ask it and each reason why not;
it changes nothing in a shared folder. Binding is `propose_change` kind
`knowledge_binding`: `host_runtime.change_proposals` keeps the card, the
fingerprint and the person's Apply, and asks this module what is current (`now`),
what the card shows (`plan`) and what Apply does (`apply`). The page's button
reaches the same card (`handle`). A binding takes effect at the next restart;
nothing here restarts Agent Web.
"""

from __future__ import annotations

import json
import shutil
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import ParseResult

from capabilities.bi_cards import vault as bi_vault
from capabilities.bi_cards.capability import QUERY_SPEC
from capabilities.bi_cards.store import DB_FILE, BiStoreError, vault_registry
from capabilities.knowledge_query.handlers import KNOWLEDGE_QUERY_SPEC
from common.assets import AssetIdentity
from common.execution import RequestContext, TraceIdentifiers
from host_runtime.bi_cards_tools import bi_skill_on
from host_runtime.contracts import CompanyHostConfiguration
from host_runtime.profiles import ProfileError, load_active_profile
from host_runtime.workspace import write_atomically
from knowledge import wiki_repos
from knowledge.evolution import KnowledgeManifest
from knowledge.repo import repository as engine
from knowledge.repo import wiki
from knowledge.repo.repository import RepoError

PREFIX = "/api/knowledge/askable"
#: The proposal's session when the page's button opened it.
PAGE_SESSION = "knowledge-page"
MAX_BODY_BYTES = 64 * 1024
VERSION = "1.0.0"
#: The values the model may give, by alias.
FIELDS = {
    "action": "action",
    "repo": "repo",
    "purpose": "purpose",
    "boundaries": "boundaries",
}
#: A manifest this module wrote names this in `validation_refs`.
REF_PREFIX = "knowledge-repo-binding-"
#: code: (what is wrong, what to do). Those in `NOTES` do not block asking.
REASONS = {
    "not_bound": ("Agent 還沒有綁定這個知識庫", "按「讓 Agent 可以問這個知識庫」"),
    "restart_pending": ("已綁定，但執行中的 Agent 還沒有載入", "重新啟動 Agent Web"),
    "no_model": ("知識查詢需要設定模型", "到 Settings 設定 Natural-language model"),
    "capability_missing": ("查詢功能沒有安裝", "到 Capabilities 安裝"),
    "skill_off": ("對話沒有可用的知識 Skill", "到 Capabilities 開啟對應的 Skill"),
    "not_granted": ("這個帳號沒有查詢功能的授權", "到 Capabilities 授權"),
    "profile_excludes": ("目前的 Agent profile 沒有列入這個知識庫", "更換或修改 Agent profile"),
    "nothing_pushed": ("還沒有已 push 的內容", "commit 後 push"),
    "unreachable": ("讀不到共用資料夾，這台電腦也沒有副本", "確認資料夾已同步"),
    "unreadable_format": ("資料夾沒有 repo.json，是舊格式（V4）", "從原始資料重建，不要手動轉換"),
    "never_published": ("還沒有發佈過：回答來自已 push 的最新版本", "要固定版本就打 tag 並發佈"),
    "several_vaults": (
        "有多個知識庫：問題由模型選擇工具，/wiki-query 要指定版本，"
        "aep_knowledge_ask 只問第一個綁定",
        "",
    ),
}
NOTES = frozenset({"never_published", "several_vaults"})


class Refused(Exception):
    """Why the proposal cannot be made; said to the model."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


@dataclass
class Planned:
    title: str
    values: dict[str, Any]
    rows: list[tuple[str, str, str]]
    effects: list[str] = field(default_factory=list)


def _config(config_path: Path) -> CompanyHostConfiguration:
    return CompanyHostConfiguration.model_validate_json(config_path.read_text(encoding="utf-8-sig"))


def identity(config: CompanyHostConfiguration, repo_id: str) -> AssetIdentity:
    """The exact identity a repository is bound under; it never moves when a
    new version is published (knowledge repositories R4a)."""
    return AssetIdentity(namespace=config.namespace or "engineering", name=repo_id, version=VERSION)


def _manifest_path(knowledge_dir: Path, asset: AssetIdentity) -> Path:
    return knowledge_dir / f"{asset.namespace}__{asset.name}__{asset.version}.json"


def now(config_path: Path, knowledge_dir: Path, values: Mapping[str, Any]) -> dict[str, Any]:
    """What a proposal rests on: the bindings and the repository's manifest."""
    config = _config(config_path)
    repo_id = str(values.get("repo") or "")
    manifest = False
    if engine.ID_RE.fullmatch(repo_id):
        manifest = _manifest_path(knowledge_dir, identity(config, repo_id)).is_file()
    return {
        "bindings": [
            {"asset": item.asset.key, "repo": item.repo, "vault_root": item.vault_root}
            for item in config.knowledge
        ],
        "manifest": manifest,
    }


def plan(
    workspace: Path,
    config_path: Path,
    knowledge_dir: Path,
    given: Mapping[str, Any],
) -> Planned:
    """The card, or `Refused`."""
    action = str(given.get("action") or "bind")
    if action not in {"bind", "unbind"}:
        raise Refused("action 只能是 bind 或 unbind。")
    repo_id = str(given.get("repo") or "").strip()
    config = _config(config_path)
    bound = next((item for item in config.knowledge if item.repo == repo_id), None)
    if action == "unbind":
        if bound is None:
            raise Refused(f"知識庫「{repo_id}」沒有綁定在這個 Agent。")
        return Planned(
            title=f"解除 Agent 與知識庫 {repo_id} 的綁定",
            values={"action": "unbind", "repo": repo_id},
            rows=[("Agent 可以問", repo_id, "（不可以）")],
            effects=[
                "只改 host.json（先備份），重新啟動 Agent Web 後生效；不會自動重新啟動。",
                "知識庫本身不動。",
            ],
        )
    if bound is not None:
        raise Refused(f"知識庫「{repo_id}」已經綁定了。")
    try:
        repo = wiki_repos.repository(workspace, repo_id)
    except RepoError:
        raise Refused(f"這台電腦沒有 wiki 知識庫「{repo_id}」。") from None
    reads = _wiki_reads(repo)
    if reads is None:
        raise Refused(f"讀不到知識庫「{repo_id}」的共用資料夾，這台電腦也沒有副本。")
    asset = identity(config, repo_id)
    path = _manifest_path(knowledge_dir, asset)
    if path.is_file() and not _ours(path):
        raise Refused(f"已有另一個同名的 Knowledge（{asset.key}），不能覆蓋。")
    purpose = str(given.get("purpose") or repo.document.get("purpose") or repo.document["title"])
    values = {"action": "bind", "repo": repo_id, "purpose": purpose[:400]}
    if given.get("boundaries"):
        values["boundaries"] = str(given["boundaries"])[:400]
    effects = [
        "寫入 host.json（先備份）和這個知識庫的 manifest，重新啟動 Agent Web 後生效；"
        "不會自動重新啟動。",
        "Agent 只讀發佈版本（沒發佈過則讀已 push 的最新版本），未 push 的內容不會被讀。",
        "這不是授權：knowledge-query/ask 的授權維持原狀。",
    ]
    if config.knowledge:
        first = config.knowledge[0].asset.name
        effects.append(
            "已經有其他知識庫：問題改由模型選擇工具，/wiki-query 要指定版本，"
            f"aep_knowledge_ask 仍只問第一個綁定（{first}）。"
        )
    return Planned(
        title=f"讓 Agent 可以問知識庫 {repo.document['title']}",
        values=values,
        rows=[
            ("知識庫", "", f"{repo.document['title']}（{repo_id}）"),
            ("Agent 讀到", "", engine.source_line(repo_id, reads).split("：", 1)[1]),
            ("用途", "", purpose[:400]),
            ("綁定成", "", f"{asset.namespace}/{asset.name}@{asset.version}"),
        ],
        effects=effects,
    )


def _ours(path: Path) -> bool:
    try:
        refs = json.loads(path.read_text(encoding="utf-8"))["metadata"]["validation_refs"]
    except (OSError, ValueError, KeyError, TypeError):
        return False
    return any(str(ref).startswith(REF_PREFIX) for ref in refs)


def apply(
    workspace: Path,
    config_path: Path,
    knowledge_dir: Path,
    values: Mapping[str, Any],
    actor: str,
    *,
    clock: datetime | None = None,
) -> tuple[bool, str]:
    """Apply a planned binding. The manifest goes first: a binding without its
    manifest stops the host from starting."""
    stamp = (clock or datetime.now()).strftime("%Y%m%d-%H%M%S")
    repo_id = str(values["repo"])
    config = _config(config_path)
    data = json.loads(config.model_dump_json())
    if values.get("action") == "unbind":
        data["knowledge"] = [item for item in data["knowledge"] if item.get("repo") != repo_id]
    else:
        repo = wiki_repos.repository(workspace, repo_id)
        asset = identity(config, repo_id)
        knowledge_dir.mkdir(parents=True, exist_ok=True)
        manifest = _manifest(asset, repo, values, actor, stamp[:8])
        write_atomically(
            _manifest_path(knowledge_dir, asset),
            manifest.model_dump_json(indent=2).encode("utf-8") + b"\n",
        )
        data["knowledge"].append({"asset": asset.model_dump(mode="json"), "repo": repo_id})
    updated = CompanyHostConfiguration.model_validate(data)
    shutil.copy2(config_path, config_path.with_name(f"{config_path.name}.bak-{stamp}-knowledge"))
    write_atomically(config_path, updated.model_dump_json(indent=2).encode("utf-8") + b"\n")
    return True, "已寫入 host.json；重新啟動 Agent Web 後生效。"


def _manifest(
    asset: AssetIdentity, repo: Any, values: Mapping[str, Any], actor: str, day: str
) -> KnowledgeManifest:
    """The governed manifest the binding keeps; the person's Apply is its
    approval, and the live entry recomputes the digests when it first reads."""
    return KnowledgeManifest.model_validate(
        {
            "metadata": {
                "identity": asset.model_dump(mode="json"),
                "owner": {"type": "user", "id": actor},
                "visibility": "private",
                "lifecycle": "published",
                "business_approval": {
                    "status": "approved",
                    "reviewer": actor,
                    "evidence": f"bound-by-{actor}-{day}",
                },
                "validation_refs": [f"{REF_PREFIX}{asset.name}-{day}"],
            },
            "domain": asset.namespace,
            "vault_ref": str(repo.local / wiki_repos.PUBLISHED_DIR / wiki_repos.VIEW_DIR),
            "raw_sha256": "0" * 64,
            "decisions_sha256": "0" * 64,
            "content_sha256": "0" * 64,
            "purpose": values.get("purpose"),
            **({"boundaries": values["boundaries"]} if values.get("boundaries") else {}),
        }
    )


# -- whether the chat can ask ------------------------------------------------------------


def _reason(code: str) -> dict[str, Any]:
    message, fix = REASONS[code]
    return {"code": code, "message": message, "fix": fix, "blocks": code not in NOTES}


def _entry(kind: str, item_id: str, title: str, reads: Any, codes: list[str]) -> dict[str, Any]:
    reasons = [_reason(code) for code in codes]
    return {
        "kind": kind,
        "id": item_id,
        "title": title,
        "askable": not any(reason["blocks"] for reason in reasons),
        "reads": reads,
        "reasons": reasons,
    }


def _wiki_reads(repo: Any) -> dict[str, Any] | None:
    """What the Agent reads, or None when neither the shared folder nor a copy
    built on this PC can be read."""
    root = repo.local / wiki_repos.PUBLISHED_DIR
    try:
        repo.sync()
        return wiki_repos.reads(repo)
    except RepoError:
        if not (root / wiki_repos.VIEW_DIR / wiki.READ_ONLY_NOTE).is_file():
            return None
    try:
        built: dict[str, Any] = json.loads((root / wiki_repos.MARKER).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return built


def _granted(web: Any, spec: Any) -> bool:
    runtime = web.runtime
    context = RequestContext(
        trace=TraceIdentifiers(trace_id="askable", request_id="askable", span_id="askable"),
        actor=str(runtime.actor),
        namespace=runtime.config.namespace or "engineering",
        message="askable",
        channel="local",
    )
    return bool(runtime.agent.gateway.bridge.policy.authorize(context, spec).allowed)


def _bindings(web: Any) -> list[Any]:
    path = web.config_path
    return list(_config(Path(path)).knowledge if path else web.runtime.config.knowledge)


def _permitted(web: Any, asset: AssetIdentity) -> bool:
    runtime = web.runtime
    try:
        profile = load_active_profile(
            runtime.config,
            runtime.layout,
            None,
            actor=runtime.config.device.registered_by,
        )
    except ProfileError:
        return True  # the host reports an invalid profile itself
    return profile is None or asset.key in {item.key for item in profile.knowledge}


def _wiki_entry(web: Any, item: Mapping[str, Any], bindings: list[Any]) -> dict[str, Any]:
    gateway = web.runtime.agent.gateway
    workspace = Path(web.runtime.layout.workspace_root)
    repo_id = str(item["id"])
    title = str(item.get("title") or repo_id)
    installed = gateway.bridge.installed.get(KNOWLEDGE_QUERY_SPEC.identity)
    catalog = getattr(getattr(installed, "handler", None), "catalog", None)
    codes: list[str] = []
    bound = next((b for b in bindings if b.repo == repo_id), None)
    if bound is None:
        codes.append("not_bound")
    elif not _permitted(web, bound.asset):
        codes.append("profile_excludes")
    elif web.runtime.config.models is None:
        codes.append("no_model")
    elif catalog is None or not any(
        m.metadata.identity == bound.asset for m in catalog.manifests()
    ):
        codes.append("restart_pending")
    if installed is not None:
        if not _granted(web, KNOWLEDGE_QUERY_SPEC):
            codes.append("not_granted")
        namespace = web.runtime.config.namespace or "engineering"
        skills = gateway.router.commands.skills.discover(namespace)
        if not any(
            command.kind == "capability" and command.target == KNOWLEDGE_QUERY_SPEC.identity
            for skill in skills
            for command in skill.commands
        ):
            codes.append("skill_off")
    try:
        repo = wiki_repos.repository(workspace, repo_id)
    except RepoError:
        return _entry("wiki", repo_id, title, None, [*codes, "unreachable"])
    reads = _wiki_reads(repo)
    if reads is None:
        codes.append("unreachable")
    elif not reads["commit"] or all(c["kind"] == "schema" for c in repo.history(limit=10**9)):
        codes.append("nothing_pushed")
    elif not reads["tag"]:
        codes.append("never_published")
    return _entry("wiki", repo_id, title, reads, codes)


def _bi_entry(web: Any, item: Mapping[str, Any]) -> dict[str, Any]:
    gateway = web.runtime.agent.gateway
    workspace = Path(web.runtime.layout.workspace_root)
    vault_id = str(item["id"])
    codes: list[str] = []
    if gateway.bridge.installed.get(QUERY_SPEC.identity) is None:
        codes.append("capability_missing")
    else:
        if not bi_skill_on(gateway):
            codes.append("skill_off")
        if not _granted(web, QUERY_SPEC):
            codes.append("not_granted")
    folder = Path(str(item.get("path") or ""))
    try:
        vault = bi_vault.Vault(workspace, vault_id)
    except (BiStoreError, RepoError):
        vault = None
    if vault is None or not vault.reachable:
        built = vault is not None and (vault.local / bi_vault.PUBLISHED_DIR / DB_FILE).is_file()
        if built:
            return _entry("bi", vault_id, vault_id, None, codes)
        code = "unreadable_format" if folder.is_dir() else "unreachable"
        return _entry("bi", vault_id, vault_id, None, [*codes, code])
    try:
        vault.repo.sync()
        reads = vault.reads()
        store = bi_vault.reading_store(workspace, vault.dataset)
        cards = len(store.card_rows())
    except (BiStoreError, RepoError):
        return _entry("bi", vault_id, vault_id, None, [*codes, "unreachable"])
    if not reads["commit"] or not cards:
        codes.append("nothing_pushed")
    elif not reads["tag"]:
        codes.append("never_published")
    return _entry("bi", vault_id, str(vault.repo.document["title"]), reads, codes)


def askable(web: Any) -> dict[str, Any]:
    """Each vault on this PC and whether the general chat can ask it."""
    workspace = Path(web.runtime.layout.workspace_root)
    bindings = _bindings(web)
    notes = [_reason("several_vaults")] if len(bindings) > 1 else []
    return {
        "repos": [_wiki_entry(web, item, bindings) for item in wiki_repos.listing(workspace)],
        "vaults": [_bi_entry(web, item) for item in vault_registry(workspace)],
        "notes": notes,
    }


# -- the routes --------------------------------------------------------------------------


def route(web: Any, method: str, path: str, given: Any) -> tuple[int, dict[str, Any]]:
    if method == "GET" and path == PREFIX:
        return 200, {"ok": True, **askable(web)}
    if method == "POST" and path == f"{PREFIX}/propose":
        body = given if isinstance(given, dict) else {}
        # Local import: change_proposals is built on what the web module holds.
        from host_runtime.change_proposals import ProposalRefused

        try:
            card = web.proposals.propose(
                "knowledge_binding",
                {key: body[key] for key in FIELDS if key in body},
                "按下知識庫頁面上的按鈕",
                session_id=PAGE_SESSION,
                actor=str(web.runtime.actor),
                channel="local",
            )
        except ProposalRefused as refused:
            return 409, {"ok": False, "code": "proposal_refused", "message": refused.message}
        return 200, {"ok": True, "card": card.model_dump(mode="json")}
    return 404, {"ok": False, "code": "route_unknown", "message": "沒有這個路徑"}


def handle(handler: Any, method: str, parsed: ParseResult) -> bool:
    """Serve an `/api/knowledge/askable` request on `handler` (already
    token-checked); False when the path is not ours."""
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
            handler._refuse_unread(413, {"ok": False, "code": "too_large", "message": "內容太大"})
            return True
        try:
            body = json.loads(handler.rfile.read(length) or b"{}")
        except (ValueError, TypeError):
            handler._json(400, {"ok": False, "code": "json_invalid", "message": "不是有效的 JSON"})
            return True
    try:
        status, payload = route(handler.server.web, method, parsed.path, body)
    except Exception as failure:  # noqa: BLE001 - the page shows every failure
        status, payload = (
            500,
            {
                "ok": False,
                "code": "askable_error",
                "message": f"內部錯誤（{type(failure).__name__}）",
            },
        )
    handler._json(status, payload)
    return True
