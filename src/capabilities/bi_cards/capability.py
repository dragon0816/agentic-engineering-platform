"""`bi-cards/query@1.0.0`: the chat's read-only search of BI cards.

The Host offers it as the `bi__query` tool while some version of the
`engineering/bi-knowledge` Skill is switched on (`host_runtime.bi_cards_tools`).
Each card comes back with every field's source (`kind:ref`), so the answer
can cite `[卡片 <type>:<key>]`; previews and proposals are never searched.

The chat is BI-specific (owner 2026-10-21): a dataset bound to a schema that
is not `bi.schema/*` is refused with `schema_not_bi`.

A dataset subscribed from the Shared Platform (`<namespace>/<name>`, BI
dataset sharing slice 1) is queried the same way; its result carries
`source` (version, publisher, status) so the answer can name the version it
came from, and say when that copy no longer updates (owner Q2).
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pydantic import Field

from capabilities.bi_cards import dashboard, service, subscriptions
from capabilities.bi_cards.catalog import for_store
from capabilities.bi_cards.store import DEFAULT_DATASET, BiStore, BiStoreError
from capabilities.contracts import CapabilitySpec
from capabilities.runtime import CapabilityRefused
from common.base import Contract
from common.execution import RequestContext

NAMESPACE = "bi-cards"
VERSION = "1.0.0"

QUERY_SPEC = CapabilitySpec.model_validate(
    {
        "identity": {"namespace": NAMESPACE, "name": "query", "version": VERSION},
        "name": f"{NAMESPACE}.query",
        "description": "Search BI knowledge cards by type, text, field and domain, follow "
        "links, and return each card with per-field source evidence; read only",
        "input_contract": f"{NAMESPACE}.query.input.v1",
        "output_contract": f"{NAMESPACE}.query.output.v1",
        "side_effect": "read",
        "policy": {
            "risk": "low",
            "approval_required": False,
            "required_permissions": [f"{NAMESPACE}.query"],
            "policy_refs": ["bi-internal-data-policy"],
        },
    }
)


class QueryRequest(Contract):
    #: A local dataset, or a subscribed `<namespace>/<name>`.
    dataset: str = Field(default=DEFAULT_DATASET, max_length=81)
    entity_type: str = Field(default="", max_length=40)
    text: str = Field(default="", max_length=200)
    domain: str = Field(default="", max_length=20)
    field: str = Field(default="", max_length=60)
    value: str = Field(default="", max_length=200)
    follow_links: bool = True
    limit: int = Field(default=20, ge=1, le=100)
    #: A whole-dataset analysis computed like the page's dashboard (gaps,
    #: coverage, funnel …), so a "which applications lack …" answer covers
    #: every card instead of what a search happened to return.
    analysis: str = Field(default="", max_length=40)


class QueryResult(Contract):
    dataset: str
    total: int
    cards: tuple[dict[str, Any], ...]
    scope_note: str
    analysis: tuple[dict[str, Any], ...] = ()
    #: A subscribed dataset's version and publisher; None for a local one.
    source: dict[str, Any] | None = None


def source_note(source: dict[str, Any] | None) -> str:
    if source is None:
        return ""
    by = f"（發佈者 {source['published_by']}）" if source.get("published_by") else ""
    note = f"資料來源：{source['dataset']} v{source['version']}{by}"
    if source.get("stopped"):
        note += "；這份副本已停止更新（無權限），內容停在這個版本"
    elif source.get("latest"):
        note += f"；平台上有 v{source['latest']}，尚未更新"
    return note


class QueryHandler:
    def __init__(
        self,
        workspace_root: Path,
        store_for: Callable[[str], tuple[BiStore, str] | None] | None = None,
    ) -> None:
        self.workspace_root = workspace_root
        #: For a benchmark (BI T1): the store a dataset is read from and the
        #: note saying which version that is, in place of the published one;
        #: None for a dataset it does not cover. Nothing is synced then.
        self.store_for = store_for

    async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
        request = QueryRequest.model_validate(inputs)

        if request.analysis and request.analysis not in (*dashboard.analysis_names(), "all"):
            raise CapabilityRefused("invalid_input")

        def work() -> Contract:
            store = BiStore(self.workspace_root, request.dataset)
            source = subscriptions.source(self.workspace_root, request.dataset)
            if store.read_only and source is None:
                raise BiStoreError("dataset_unknown")
            published = ""
            chosen = self.store_for(request.dataset) if self.store_for is not None else None
            if chosen is not None:
                store, published = chosen
            elif store.vault_id is not None:
                # A vault is answered from its published version only, never
                # from this PC's unpushed work (knowledge repositories,
                # decision 8). Syncing first picks up a new publication; it
                # writes nothing to the shared folder.
                from capabilities.bi_cards import vault

                try:
                    vault.sync(self.workspace_root, store.vault_id)
                except BiStoreError:
                    pass  # the shared folder is not reachable now: answer from this PC
                vault_id = store.vault_id
                store = vault.reading_store(self.workspace_root, request.dataset)
                reads = vault.Vault(self.workspace_root, vault_id).reads()
                published = (
                    f"內容來自發佈版本 {reads['tag']}"
                    if reads["tag"]
                    else "這個知識庫還沒有發佈過，內容來自已 push 的最新版本"
                )
            if not for_store(store).is_bi:
                raise BiStoreError("schema_not_bi")
            cited = "；".join(n for n in (source_note(source), published) if n)
            if request.analysis:
                sections = dashboard.analysis(
                    store, request.analysis, (request.domain or "robotics").lower()
                )
                return QueryResult(
                    dataset=request.dataset,
                    total=sum(len(section["rows"]) for section in sections),
                    cards=(),
                    scope_note=f"在這份資料集（{request.dataset}）中計算"
                    + (f"。{cited}" if cited else ""),
                    analysis=tuple(sections),
                    source=source,
                )
            answer = service.query_cards(
                store,
                entity_type=request.entity_type or None,
                text=request.text or None,
                domain=request.domain or None,
                field=request.field or None,
                value=request.value or None,
                follow_links=request.follow_links,
                limit=request.limit,
            )
            return QueryResult(
                dataset=answer["dataset"],
                total=answer["total"],
                cards=tuple(answer["cards"]),
                scope_note=answer["scope_note"] + (cited and f"{cited}。"),
                source=source,
            )

        try:
            return await asyncio.to_thread(work)
        except BiStoreError as error:
            raise CapabilityRefused(error.code) from None


def bindings(
    workspace_root: Path,
) -> tuple[tuple[CapabilitySpec, Any, type[Contract], type[Contract]], ...]:
    return ((QUERY_SPEC, QueryHandler(workspace_root), QueryRequest, QueryResult),)
