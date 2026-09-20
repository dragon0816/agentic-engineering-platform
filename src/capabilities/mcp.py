"""MCP list/call adapter over an injected client; no transport or credentials here."""

import asyncio
import math
from typing import Protocol

from pydantic import Field, JsonValue, StrictBool, TypeAdapter

from capabilities.contracts import CapabilitySpec
from capabilities.runtime import InstalledCapabilities
from common.assets import ExecutionDependencies
from common.base import Contract, Text
from common.execution import Failure, RequestContext


class MCPTool(Contract):
    name: Text
    description: str = ""
    input_schema: dict[str, JsonValue] = Field(default_factory=dict)


class MCPCallResult(Contract):
    data: JsonValue
    is_error: StrictBool = False


class MCPClient(Protocol):
    """A configured session normalizes MCP wire responses into these contracts."""

    async def list_tools(self) -> tuple[MCPTool, ...]: ...

    async def call_tool(self, name: str, arguments: dict[str, JsonValue]) -> MCPCallResult: ...


class MCPDiscovery(Contract):
    tools: tuple[MCPTool, ...] = ()
    failure: Failure | None = None


class MCPAdapter:
    def __init__(self, client: MCPClient, *, timeout_seconds: float = 10) -> None:
        if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise ValueError("timeout must be finite and positive")
        self.client = client
        self.timeout_seconds = timeout_seconds

    async def discover(self) -> MCPDiscovery:
        try:
            tools = await asyncio.wait_for(self.client.list_tools(), self.timeout_seconds)
            checked = TypeAdapter(tuple[MCPTool, ...]).validate_python(tools)
            if len({tool.name for tool in checked}) != len(checked):
                raise ValueError("duplicate remote tool names")
            return MCPDiscovery(tools=checked)
        except TimeoutError:
            return MCPDiscovery(
                failure=Failure(code="mcp_discovery_timeout", message="MCP discovery timed out")
            )
        except Exception:
            return MCPDiscovery(
                failure=Failure(
                    code="mcp_discovery_failed", message="MCP discovery did not complete"
                )
            )

    async def install(
        self,
        installed: InstalledCapabilities,
        tool_name: str,
        spec: CapabilitySpec,
        input_model: type[Contract],
        output_model: type[Contract],
        dependencies: ExecutionDependencies,
    ) -> None:
        """Explicit trusted host binding. Discovery never supplies permissions or code."""
        discovery = await self.discover()
        if discovery.failure is not None:
            raise ValueError("cannot bind a tool after failed discovery")
        if not any(tool.name == tool_name for tool in discovery.tools):
            raise ValueError("MCP tool is not advertised")

        async def invoke(context: RequestContext, inputs: Contract) -> Contract:
            result = MCPCallResult.model_validate(
                await self.client.call_tool(tool_name, inputs.model_dump(mode="json"))
            )
            if result.is_error:
                raise ValueError("MCP tool reported failure")
            return output_model.model_validate(result.data, strict=True)

        installed.register(spec, invoke, input_model, output_model, dependencies)
