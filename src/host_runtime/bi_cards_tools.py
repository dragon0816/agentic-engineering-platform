"""The `bi__query` conversation tool (BI Knowledge Case A, owner 2026-10-21).

Offered only while some version of the `engineering/bi-knowledge` Skill is
switched on and `bi-cards/query` is installed; the tool carries the Skill's
procedure, and names the vaults this PC uses with their stated purpose so the
model picks the one that fits the question (BI vaults V6, `BI_VAULT.md` §9).
Every call is a `CapabilityInvocation` through the Bridge with `origin:
model`, under the actor's grants (read only, no approval).

After the turn, `with_bi_sources` adds the source line of each subscribed
dataset the turn queried when the model's answer left it out (live test
2026-10-24): a factual citation copied from the tool result, like a chart's
legend, never a change to what the model said.

Each answered call also writes one self-contained chart page (the sections
drawn by the Dashboard tab's renderer, or the cards as a table) and attaches
it, so Agent Web shows the chart in the conversation (`bi_chart_files`;
`docs/phases/BI_CHAT_CHARTS_AND_DASHBOARD_SOURCES.md` C2).
"""

from __future__ import annotations

import secrets
from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from agent.gateway import HostTool, HostToolOutcome
from capabilities.bi_cards import analyses, vault
from capabilities.bi_cards.capability import QUERY_SPEC, QueryHandler, QueryRequest, source_note
from capabilities.bi_cards.manifest import BI_SKILL, bi_question
from capabilities.bi_cards.packs import SECTIONS as PACK_SECTIONS
from capabilities.runtime import CapabilityInvocation, CapabilityRefused
from common.execution import Failure, RequestContext
from host_runtime import bi_chart_html
from knowledge.repo import repository as repo_engine
from models.contracts import ModelTool

__all__ = [
    "bi_cards_tools",
    "bi_chart_files",
    "bi_question",
    "bi_skill_on",
    "bi_sources",
    "with_bi_sources",
]

TOOL_NAME = "bi__query"
#: Where the chat's chart pages are written, under the workspace.
CHARTS_DIR = "bi-chat-charts"
FAILURE_TEXT = {
    "dataset_invalid": "資料集名稱不正確",
    "dataset_unknown": "這台電腦沒有訂閱這個資料集",
    "permission_denied": "BI 卡片查詢沒有授權給你（在 Agent Web 的 Capabilities 選取）",
    "invalid_input": "工具參數不正確",
    "analysis_unknown": "這個知識庫的發佈版本沒有這個分析",
    "param_invalid": "分析的參數不正確",
    "timeout": "這次查詢逾時",
    "schema_not_bi": "這個資料集用的不是 BI schema（bi.schema/*），對話的 BI 查詢只支援 BI 資料集；"
    "請在 Agent Web 的 BI 卡片頁查看它的卡片",
    "schema_missing": "這個資料集的 schema 不在這台電腦上",
    "sql_not_allowed": "SQL 只能讀取（SELECT 或 WITH）；寫入、ATTACH、PRAGMA 之類都不允許",
    "sql_one_statement": "SQL 一次只能一個敘述",
    "sql_failed": "SQL 沒有成功；檢查表與欄位名稱（card_values 的欄位：card_id、entity_type、"
    "card、field、value）",
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
            "description": "a whole-dataset analysis instead of a search. In a knowledge base "
            "(vault-<id>): the slug of one of its saved analyses (its Dashboard; the published "
            "version is read), e.g. gaps, trend-coverage, funnel, or all. Elsewhere one of the "
            "built-in analyses: "
            + ", ".join([*(slug for slug, *_ in PACK_SECTIONS), "quality", "all"]),
        },
        "params": {
            "type": "object",
            "description": 'the analysis\'s parameters, e.g. {"domain": "AIDC", '
            '"include_sample": false}',
        },
        "sql": {
            "type": "string",
            "description": "instead of analysis or a search: ONE read-only SQLite statement "
            "(SELECT or WITH) on the dataset's published data, for a question no saved "
            "analysis answers. Read the view card_values(card_id, entity_type, card, field, "
            "value): one row per card field; a list value is JSON text, read it with "
            "json_each(value). At most 200 rows and 10 seconds; the result is shown to the "
            "person as a chart. Nothing is saved",
        },
        "chart": {
            "type": "object",
            "description": 'with sql: how to draw the result, {"type": "table"|"bar"|"line"|'
            '"scatter", "x": column, "y": column}; omitted, one label and one number column '
            "become a bar, anything else a table",
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
            data = result.data
            workspace = _workspace(gateway)
            if isinstance(data, dict) and workspace is not None:
                written = chart_page(workspace, data, arguments)
                if written is not None:
                    data = {**data, "chart_file": written["filename"], "attach": [written]}
            return HostToolOutcome(status="succeeded", data=data)
        failure = result.failure or Failure(code=result.status, message="")
        text = FAILURE_TEXT.get(failure.code, "BI 卡片查詢沒有完成")
        return HostToolOutcome(
            status="failed",
            data=result.data,
            failure=failure.model_copy(update={"message": f"{text}（{failure.code}）"}),
        )

    return [HostTool(_model_tool(gateway, found), call)]


def _workspace(gateway: Any) -> Path | None:
    installed = gateway.bridge.installed.get(QUERY_SPEC.identity)
    workspace = getattr(getattr(installed, "handler", None), "workspace_root", None)
    return Path(workspace) if workspace is not None else None


def chart_page(
    workspace: Path, data: Mapping[str, Any], arguments: Mapping[str, Any]
) -> dict[str, str] | None:
    """Write the chart page of one answered `bi__query` call under the
    workspace; None when it answered nothing to draw."""
    sections = [
        {
            **s,
            "chart": analyses.chart_for(
                s.get("chart"), s.get("columns") or [], s.get("rows") or []
            ),
        }
        for s in data.get("analysis") or ()
        if isinstance(s, dict)
    ]
    dataset = str(data.get("dataset") or arguments.get("dataset") or "demo")
    if sections:
        name = sections[0]["id"] if len(sections) == 1 else "all"
        title = sections[0]["title"] if len(sections) == 1 else f"BI 分析：{dataset}"
    else:
        cards = [c for c in data.get("cards") or () if isinstance(c, dict)]
        if not cards:
            return None
        name, title = "cards", f"BI 卡片：{dataset}（{len(cards)} 張）"
        sections = [{"title": title, **bi_chart_html.cards_table(cards)}]
    about = " · ".join(
        part
        for part in (dataset, str(data.get("scope_note") or "").strip(), _params(sections))
        if part
    )
    folder = workspace / CHARTS_DIR
    folder.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = folder / f"bi-{name}-{stamp}-{secrets.token_hex(2)}.html"
    path.write_text(bi_chart_html.page(str(title), sections, about), encoding="utf-8")
    return {"path": str(path), "filename": path.name, "media_type": "text/html"}


def _params(sections: list[dict[str, Any]]) -> str:
    given = sections[0].get("params") if len(sections) == 1 else None
    if not isinstance(given, dict) or not given:
        return ""
    return "參數 " + "、".join(f"{k}={v}" for k, v in given.items())


def bi_chart_files(result: Any) -> list[dict[str, str]]:
    """The chart pages the turn's answered `bi__query` calls wrote, in order,
    as Agent Web shows files in an answer (an HTML page in a sandboxed frame)."""
    files: list[dict[str, str]] = []
    for item in getattr(result, "tools", None) or ():
        host = getattr(item, "host", None)
        if getattr(item, "name", "") != TOOL_NAME or host is None or host.status != "succeeded":
            continue
        data = host.data if isinstance(host.data, dict) else {}
        for entry in data.get("attach") or ():
            path = entry.get("path") if isinstance(entry, dict) else None
            if isinstance(path, str) and Path(path).is_file():
                files.append({"filename": str(entry.get("filename") or Path(path).name),
                              "kind": "html", "path": path})  # fmt: skip
    return files


def _model_tool(gateway: Any, found: list[Any]) -> ModelTool:
    description = (
        "Search the BI knowledge cards (read only); each card returns its fields with "
        "their sources. Use THIS tool, not a knowledge vault query, for questions about "
        "客戶產品 customer products, 商機 opportunities, 客戶 accounts, 應用 applications, "
        "測試方案 test solutions, 競品 competitors, 趨勢 trends, 技術, 節點, 生態系 and 缺口 "
        f"gaps. PROCEDURE: {found[-1].instructions}"
    ) + _vaults_note(gateway)
    return ModelTool(
        name=TOOL_NAME,
        description=description,
        input_contract=f"host.{TOOL_NAME}.v1",
        input_schema=SCHEMA,
    )


def reading_tool(gateway: Any, handler: QueryHandler) -> HostTool | None:
    """`bi__query` as the Agent knows it, answered by `handler` (one that reads
    a chosen version, BI T1) for one turn (`agent.gateway.turn_host_tools`).
    None when the BI Skill is off, as the Agent would have no such tool."""
    found = _switched_on(gateway)
    if not found or gateway.bridge.installed.get(QUERY_SPEC.identity) is None:
        return None

    async def call(context: RequestContext, arguments: dict[str, Any]) -> HostToolOutcome:
        try:
            request = QueryRequest.model_validate(arguments)
            result = await handler(context, request)
        except ValidationError:
            failure = Failure(code="invalid_input", message="")
        except CapabilityRefused as refused:
            failure = Failure(code=refused.code, message="")
        else:
            return HostToolOutcome(status="succeeded", data=result.model_dump(mode="json"))
        text = FAILURE_TEXT.get(failure.code, "BI 卡片查詢沒有完成")
        return HostToolOutcome(
            status="failed",
            failure=failure.model_copy(update={"message": f"{text}（{failure.code}）"}),
        )

    return HostTool(_model_tool(gateway, found), call)


def _vaults_note(gateway: Any) -> str:
    """The shared knowledge bases (vaults) on this PC, by purpose; empty when none."""
    workspace = _workspace(gateway)
    if workspace is None:
        return ""
    lines = [
        f"- dataset {item['dataset']}: 「{item.get('title') or item['id']}」"
        + (f" — {item['purpose']}" if item.get("purpose") else "")
        for item in vault.listing(workspace)
    ]
    if not lines:
        return ""
    return (
        " SHARED KNOWLEDGE BASES on this PC (pass the dataset whose purpose fits the "
        "question; say which one you used):\n" + "\n".join(lines)
    )


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


def _vault_lines(result: Any) -> list[str]:
    """The source line of each vault version a succeeded `bi__query` call of
    this turn read, once each, in the order first used."""
    found: dict[tuple[str, str], str] = {}
    for item in getattr(result, "tools", None) or ():
        host = getattr(item, "host", None)
        if getattr(item, "name", "") != TOOL_NAME or host is None or host.status != "succeeded":
            continue
        read = host.data.get("vault") if isinstance(host.data, dict) else None
        if isinstance(read, dict):
            key = (str(read.get("dataset")), str(read.get("commit")))
            found.setdefault(key, repo_engine.source_line(str(read.get("dataset")), read))
    return list(found.values())


def with_bi_sources(answer: str, result: Any) -> str:
    """The answer with the source line of every subscribed dataset the turn
    queried that the answer does not already name (dataset and version on
    one line); only for an answered turn. The line is the tool result's own
    (`資料來源：<ns>/<name> v<version>（發佈者 <account>）` plus the stopped
    or update-available status), so nothing the model claimed is changed."""
    if getattr(result, "status", None) != "answered" or not answer.strip():
        return answer
    missing = [source_note(item) for item in bi_sources(result) if not _cited(answer, item)]
    missing += [line for line in _vault_lines(result) if line not in answer]
    if not missing:
        return answer
    lines = "\n".join(missing)
    return f"{answer.rstrip()}\n\n{lines}"
