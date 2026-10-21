"""`bi-cards/query@1.0.0`: the chat's read-only search of BI cards.

The Host offers it as the `bi__query` tool while some version of the
`engineering/bi-knowledge` Skill is switched on (`host_runtime.bi_cards_tools`).
Each card comes back with every field's source (`kind:ref`), so the answer
can cite `[卡片 <type>:<key>]`; previews and proposals are never searched.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from pydantic import Field

from capabilities.bi_cards import dashboard, service
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
    dataset: str = Field(default=DEFAULT_DATASET, max_length=40)
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


class QueryHandler:
    def __init__(self, workspace_root: Path) -> None:
        self.workspace_root = workspace_root

    async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
        request = QueryRequest.model_validate(inputs)

        if request.analysis and request.analysis not in (*dashboard.ANALYSES, "all"):
            raise CapabilityRefused("invalid_input")

        def work() -> Contract:
            store = BiStore(self.workspace_root, request.dataset)
            if request.analysis:
                sections = dashboard.analysis(
                    store, request.analysis, (request.domain or "robotics").lower()
                )
                return QueryResult(
                    dataset=request.dataset,
                    total=sum(len(section["rows"]) for section in sections),
                    cards=(),
                    scope_note=f"在這份資料集（{request.dataset}）中計算",
                    analysis=tuple(sections),
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
                scope_note=answer["scope_note"],
            )

        try:
            return await asyncio.to_thread(work)
        except BiStoreError as error:
            raise CapabilityRefused(error.code) from None


def bindings(
    workspace_root: Path,
) -> tuple[tuple[CapabilitySpec, Any, type[Contract], type[Contract]], ...]:
    return ((QUERY_SPEC, QueryHandler(workspace_root), QueryRequest, QueryResult),)
