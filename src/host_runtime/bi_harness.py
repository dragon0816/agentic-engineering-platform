"""One BI turn on the Agent harness (BI T1–T3).

The benchmark's questions, the skill AI and the analysis AI each run a Host
sub-run of `Gateway.converse` (no memory, no session) with Host tools offered
for that turn only (`agent.gateway.turn_host_tools`) and nothing else.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Sequence
from typing import Any

from agent.backend_contracts import ConversationLimits
from agent.delegation_scope import running_sub_run
from agent.gateway import GatewayConversationResult, HostTool, turn_host_tools
from common.execution import RequestContext, TraceIdentifiers
from models.contracts import ModelMessage


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


def tools_used(result: GatewayConversationResult) -> list[dict[str, Any]]:
    return [
        {"name": item.name, "ok": item.host is not None and item.host.status == "succeeded"}
        for item in result.tools
    ]
