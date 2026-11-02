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

from capabilities.bi_cards import analyses, board, quality, service, subscriptions
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
    #: In a vault: a saved analysis of the published version (its slug) or `all`
    #: (BI P4); the coded names keep working until they are removed.
    analysis: str = Field(default="", max_length=60)
    #: The analysis's parameters (`domain` may also come from `domain`).
    params: dict[str, Any] = Field(default_factory=dict)
    #: Guarded read-only ad-hoc SQL (BI C1b, owner 2026-11-01): one statement on
    #: the data `analysis` reads (a vault's published version), never a script.
    sql: str = Field(default="", max_length=analyses.MAX_CODE)
    #: The chart the model wants for `sql`'s result; checked against its columns.
    chart: dict[str, Any] | None = None


#: Rows a chat query returns (the rows the Dashboard tab's table shows); the
#: time limit is the analyses' `SQL_SECONDS`.
CHAT_SQL_ROWS = 200


def _sql_refusal(error: BiStoreError) -> CapabilityRefused:
    """A failed chat query as a code the model can act on (a refusal carries
    no message off the Bridge: SQLite's text may quote the data)."""
    message = error.message
    if "not authorized" in message:
        return CapabilityRefused("sql_not_allowed")
    if "one statement" in message:
        return CapabilityRefused("sql_one_statement")
    if "超過" in message or "interrupted" in message:
        return CapabilityRefused("timeout")
    return CapabilityRefused("sql_failed")


def _sql_section(store: BiStore, request: QueryRequest) -> dict[str, Any]:
    try:
        table = analyses.run_sql(
            store.path, request.sql, seconds=analyses.SQL_SECONDS, max_rows=CHAT_SQL_ROWS
        )
    except BiStoreError as error:
        if error.code == "analysis_failed":
            raise _sql_refusal(error) from None
        raise
    return {
        "id": "query",
        "title": "查詢結果",
        "kind": "table",
        "chart": analyses.chart_for(request.chart, table["columns"], table["rows"]),
        "columns": table["columns"],
        "rows": table["rows"],
        "flags": [],
        "note": "",
        "analysis": False,
        "truncated": table["truncated"],
        "sql": request.sql,
    }


class QueryResult(Contract):
    dataset: str
    total: int
    cards: tuple[dict[str, Any], ...]
    scope_note: str
    analysis: tuple[dict[str, Any], ...] = ()
    #: A subscribed dataset's version and publisher; None for a local one.
    source: dict[str, Any] | None = None
    #: A vault's answer: the dataset and the version read (`{dataset, tag, commit}`).
    vault: dict[str, Any] | None = None


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

        # A slug, `all`, `quality`, or a coded section's old name (`trend_coverage`).
        if request.analysis and not analyses.NAME_RE.match(request.analysis.replace("_", "-")):
            raise CapabilityRefused("invalid_input")
        if request.sql.strip() and request.analysis:
            raise CapabilityRefused("invalid_input")  # either SQL or a saved analysis

        def work() -> Contract:
            store = BiStore(self.workspace_root, request.dataset)
            source = subscriptions.source(self.workspace_root, request.dataset)
            if store.read_only and source is None:
                raise BiStoreError("dataset_unknown")
            published = ""
            read_version: dict[str, Any] | None = None
            vault_id = store.vault_id
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
                read_version = {"dataset": request.dataset, **reads}
                published = (
                    f"內容來自發佈版本 {reads['tag']}"
                    if reads["tag"]
                    else "這個知識庫還沒有發佈過，內容來自已 push 的最新版本"
                )
            if not for_store(store).is_bi:
                raise BiStoreError("schema_not_bi")
            cited = "；".join(n for n in (source_note(source), published) if n)
            if request.sql.strip():
                section = _sql_section(store, request)
                return QueryResult(
                    dataset=request.dataset,
                    total=len(section["rows"]),
                    cards=(),
                    scope_note=f"在這份資料集（{request.dataset}）中查詢"
                    + (f"。{cited}" if cited else ""),
                    analysis=(section,),
                    source=source,
                    vault=read_version,
                )
            if request.analysis:
                given = {**request.params}
                if request.domain and "domain" not in given:
                    given["domain"] = request.domain
                if request.analysis == "quality":
                    sections = [quality.section(quality.check(store, for_store(store)))]
                elif vault_id is not None and chosen is None:
                    saved = board.saved_name(self.workspace_root, vault_id, request.analysis)
                    if saved is None:
                        raise BiStoreError("analysis_unknown")
                    sections = board.published_sections(
                        self.workspace_root, str(vault_id), saved, given
                    )
                else:
                    sections = board.pack_sections(
                        self.workspace_root, store, request.analysis, given
                    )
                return QueryResult(
                    dataset=request.dataset,
                    total=sum(len(section["rows"]) for section in sections),
                    cards=(),
                    scope_note=f"在這份資料集（{request.dataset}）中計算"
                    + (f"。{cited}" if cited else ""),
                    analysis=tuple(sections),
                    source=source,
                    vault=read_version,
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
                vault=read_version,
            )

        try:
            return await asyncio.to_thread(work)
        except BiStoreError as error:
            raise CapabilityRefused(error.code) from None


def bindings(
    workspace_root: Path,
) -> tuple[tuple[CapabilitySpec, Any, type[Contract], type[Contract]], ...]:
    return ((QUERY_SPEC, QueryHandler(workspace_root), QueryRequest, QueryResult),)
