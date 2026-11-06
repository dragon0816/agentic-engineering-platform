"""One BI turn on the Agent harness (BI T1–T3, `docs/phases/BI_BUILD_FLOW.md`).

The benchmark's questions and the schema, skill, analysis and question AIs each
run a Host sub-run of `Gateway.converse` (no memory, no session) with Host tools
offered for that turn only (`agent.gateway.turn_host_tools`) and nothing else.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from agent.backend_contracts import ConversationLimits
from agent.delegation_scope import running_sub_run
from agent.gateway import GatewayConversationResult, HostTool, HostToolOutcome, turn_host_tools
from capabilities.bi_cards import ai_runs, sessions
from capabilities.bi_cards.staging import Staging
from capabilities.bi_cards.store import BiStoreError
from common.execution import Failure, RequestContext, TraceIdentifiers
from models.approved import ApprovedModelClient
from models.contracts import ModelMessage, ModelTool

MAX_SOURCE_PIECE = 6000


def converse(
    gateway: Any,
    *,
    profile: str,
    actor: str,
    namespace: str,
    history: Sequence[ModelMessage],
    tools: Sequence[HostTool],
    role: str,
    limits: ConversationLimits | None = None,
) -> GatewayConversationResult:
    value = uuid.uuid4().hex
    request = RequestContext(
        trace=TraceIdentifiers(
            trace_id=f"trace-{value}", request_id=f"request-{value}", span_id=f"span-{value}"
        ),
        actor=actor,
        namespace=namespace,
        message=history[-1].text[:4000] or "-",
        channel="local",
    )
    with running_sub_run(profile), turn_host_tools(tools):
        result: GatewayConversationResult = asyncio.run(
            gateway.converse(
                request,
                tuple(history),
                allowed_tools=frozenset(t.tool.name for t in tools),
                role_guidance=role,
                limits=limits,
            )
        )
    return result


def turn_ai(gateway: Any, ai: ai_runs.AiRuntime) -> ai_runs.AiRuntime:
    """The runtime for trial runs inside a BI AI turn: run at once, on the conversation's
    model client, so a call has the conversation's timeout (`call_timeout_seconds`, 180 s by
    default) rather than batch extraction's (orchestrator 2026-11-06); the host's
    extraction client when the conversation has no approved one."""
    router = getattr(gateway, "router", None)
    chat = getattr(router, "model", None)

    def model() -> Any:
        if isinstance(chat, ApprovedModelClient):
            return chat, str(getattr(router, "model_alias", ""))
        return ai.model()

    return ai_runs.AiRuntime(
        model=model, background=lambda _title, work: work(), approved=ai.approved
    )


def tools_used(result: GatewayConversationResult) -> list[dict[str, Any]]:
    return [
        {"name": item.name, "ok": item.host is not None and item.host.status == "succeeded"}
        for item in result.tools
    ]


def tool(name: str, description: str, properties: dict[str, Any], required: list[str]) -> ModelTool:
    return ModelTool(
        name=name,
        description=description,
        input_contract=f"host.{name}.v1",
        input_schema={
            "type": "object",
            "properties": properties,
            "required": required,
            "additionalProperties": False,
        },
    )


def failed(code: str, message: str) -> HostToolOutcome:
    return HostToolOutcome(status="failed", failure=Failure(code=code, message=message))


def source_tools(
    prefix: str, workspace: Path, dataset: str, ai: ai_runs.AiRuntime
) -> list[HostTool]:
    """`<prefix>__sources` and `<prefix>__read_source`: the dataset's sources, read
    as data and under the same classification check as a run."""

    async def list_sources(_c: RequestContext, _a: dict[str, Any]) -> HostToolOutcome:
        staging = Staging(workspace, dataset)
        rows = [
            {"id": s["id"], "name": s["name"], "classification": s["classification"]}
            for s in staging.sources()[:40]
        ]
        return HostToolOutcome(status="succeeded", data={"sources": rows})

    async def read_source(_c: RequestContext, args: dict[str, Any]) -> HostToolOutcome:
        staging = Staging(workspace, dataset)
        source = staging.source(str(args.get("source_id") or ""))
        if source is None:
            return failed("source_unknown", "沒有這個來源")
        try:
            ai_runs.check_classification(ai, source["classification"])
        except BiStoreError as error:
            return failed(error.code, error.message)
        text = sessions._source_text(staging, source)
        start = max(0, int(args.get("start") or 0))
        piece = text[start : start + MAX_SOURCE_PIECE]
        return HostToolOutcome(
            status="succeeded",
            data={
                "name": source["name"],
                "chars": len(text),
                "start": start,
                "text": sessions.fenced("Source text:", piece),
            },
        )

    return [
        HostTool(
            tool(f"{prefix}__sources", "List the knowledge base's sources.", {}, []), list_sources
        ),
        HostTool(
            tool(
                f"{prefix}__read_source",
                f"Read part of a source's Markdown ({MAX_SOURCE_PIECE} characters from `start`).",
                {"source_id": {"type": "string"}, "start": {"type": "integer"}},
                ["source_id"],
            ),
            read_source,
        ),
    ]
