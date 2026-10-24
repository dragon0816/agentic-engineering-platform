"""The `bi__query` conversation tool (BI Knowledge Case A, owner 2026-10-21).

Offered only while some version of the `engineering/bi-knowledge` Skill is
switched on and `bi-cards/query` is installed; the tool carries the Skill's
procedure. Every call is a `CapabilityInvocation` through the Bridge with
`origin: model`, under the actor's grants (read only, no approval).

After the turn, `with_bi_sources` adds the source line of each subscribed
dataset the turn queried when the model's answer left it out (live test
2026-10-24): a factual citation copied from the tool result, like a chart's
legend, never a change to what the model said.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from agent.gateway import HostTool, HostToolOutcome
from capabilities.bi_cards.capability import QUERY_SPEC, source_note
from capabilities.bi_cards.dashboard import ANALYSES
from capabilities.bi_cards.manifest import BI_SKILL, bi_question
from capabilities.runtime import CapabilityInvocation
from common.execution import Failure, RequestContext
from models.contracts import ModelTool

__all__ = ["bi_cards_tools", "bi_question", "bi_skill_on", "bi_sources", "with_bi_sources"]

TOOL_NAME = "bi__query"
FAILURE_TEXT = {
    "dataset_invalid": "資料集名稱不正確",
    "dataset_unknown": "這台電腦沒有訂閱這個資料集",
    "permission_denied": "BI 卡片查詢沒有授權給你（在 Agent Web 的 Capabilities 選取）",
    "invalid_input": "工具參數不正確",
    "timeout": "這次查詢逾時",
    "schema_not_bi": "這個資料集用的不是 BI schema（bi.schema/*），對話的 BI 查詢只支援 BI 資料集；"
    "請在 Agent Web 的 BI 卡片頁查看它的卡片",
    "schema_missing": "這個資料集的 schema 不在這台電腦上",
}

SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "dataset": {
            "type": "string",
            "description": "the dataset; demo by default, or a subscribed <namespace>/<name> "
            "(a read-only copy from the Shared Platform; its result carries `source` with the "
            "version to cite). Only datasets using a bi.schema/* schema can be queried; any "
            "other is refused with schema_not_bi",
        },
        "entity_type": {
            "type": "string",
            "description": "Trend, Technology, Node, Ecosystem, Account, CustomerProduct, "
            "Application, TestSolution, Competitor, Opportunity, Signal or Concept",
        },
        "text": {"type": "string", "description": "words to find in names and field values"},
        "domain": {"type": "string", "description": "wireless, AIDC or robotics"},
        "field": {"type": "string", "description": "only cards with this field set"},
        "value": {"type": "string", "description": "with field: the field contains this"},
        "follow_links": {"type": "boolean", "description": "include each card's links"},
        "limit": {"type": "integer", "minimum": 1, "maximum": 100},
        "analysis": {
            "type": "string",
            "enum": [*ANALYSES, "all"],
            "description": "a whole-dataset analysis instead of a search: gaps (applications "
            "where competitors have a solution and we do not), trend_coverage, "
            "demand_without_opportunity, solutions_vs_opportunities, funnel, "
            "technologies_without_concept, product_completeness, trend_priority, … or all",
        },
    },
    "required": [],
}


def _switched_on(gateway: Any) -> list[Any]:
    try:
        manifests = gateway.router.commands.skills.manifests()
    except AttributeError:
        return []
    return [
        item
        for item in manifests
        if item.metadata.identity.namespace == BI_SKILL.namespace
        and item.metadata.identity.name == BI_SKILL.name
    ]


def bi_skill_on(gateway: Any) -> bool:
    """Whether some version of the BI Skill is switched on and its query installed."""
    installed = gateway.bridge.installed.get(QUERY_SPEC.identity) is not None
    return installed and bool(_switched_on(gateway))


def bi_cards_tools(gateway: Any) -> Sequence[HostTool]:
    found = _switched_on(gateway)
    if not found or gateway.bridge.installed.get(QUERY_SPEC.identity) is None:
        return []

    async def call(context: RequestContext, arguments: dict[str, Any]) -> HostToolOutcome:
        result = await gateway.bridge.execute(
            CapabilityInvocation(
                context=context, origin="model", target=QUERY_SPEC.identity, arguments=arguments
            )
        )
        if result.status == "succeeded":
            return HostToolOutcome(status="succeeded", data=result.data)
        failure = result.failure or Failure(code=result.status, message="")
        text = FAILURE_TEXT.get(failure.code, "BI 卡片查詢沒有完成")
        return HostToolOutcome(
            status="failed",
            data=result.data,
            failure=failure.model_copy(update={"message": f"{text}（{failure.code}）"}),
        )

    description = (
        "Search the BI knowledge cards (read only); each card returns its fields with "
        "their sources. Use THIS tool, not a knowledge vault query, for questions about "
        "客戶產品 customer products, 商機 opportunities, 客戶 accounts, 應用 applications, "
        "測試方案 test solutions, 競品 competitors, 趨勢 trends, 技術, 節點, 生態系 and 缺口 "
        f"gaps. PROCEDURE: {found[-1].instructions}"
    )
    return [
        HostTool(
            ModelTool(
                name=TOOL_NAME,
                description=description,
                input_contract=f"host.{TOOL_NAME}.v1",
                input_schema=SCHEMA,
            ),
            call,
        )
    ]


def bi_sources(result: Any) -> list[dict[str, Any]]:
    """The `source` of each subscribed dataset a succeeded `bi__query` call
    of this turn read, once per dataset and version, in the order first
    used. A local dataset's result has no source and adds nothing."""
    found: dict[tuple[str, str], dict[str, Any]] = {}
    for item in getattr(result, "tools", None) or ():
        host = getattr(item, "host", None)
        if getattr(item, "name", "") != TOOL_NAME or host is None or host.status != "succeeded":
            continue
        source = host.data.get("source") if isinstance(host.data, dict) else None
        if not isinstance(source, dict):
            continue
        dataset, version = source.get("dataset"), source.get("version")
        if isinstance(dataset, str) and dataset and isinstance(version, str) and version:
            found.setdefault((dataset, version), source)
    return list(found.values())


def _cited(answer: str, source: dict[str, Any]) -> bool:
    """Whether one line of the answer names this dataset and its version."""
    dataset, version = str(source["dataset"]), str(source["version"])
    return any(dataset in line and version in line for line in answer.splitlines())


def with_bi_sources(answer: str, result: Any) -> str:
    """The answer with the source line of every subscribed dataset the turn
    queried that the answer does not already name (dataset and version on
    one line); only for an answered turn. The line is the tool result's own
    (`資料來源：<ns>/<name> v<version>（發佈者 <account>）` plus the stopped
    or update-available status), so nothing the model claimed is changed."""
    if getattr(result, "status", None) != "answered" or not answer.strip():
        return answer
    missing = [source_note(item) for item in bi_sources(result) if not _cited(answer, item)]
    if not missing:
        return answer
    lines = "\n".join(missing)
    return f"{answer.rstrip()}\n\n{lines}"
