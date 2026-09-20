import asyncio

import pytest
from pydantic import JsonValue
from test_dispatch import Input, Output, grant, invocation, spec

from capabilities.mcp import MCPAdapter, MCPCallResult, MCPTool
from capabilities.runtime import InstalledCapabilities, LocalPolicy
from common.assets import ExecutionDependencies
from workflow.dispatch import BridgeExecutor


class FakeMCP:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, JsonValue]]] = []
        self.is_error = False

    async def list_tools(self) -> tuple[MCPTool, ...]:
        return (MCPTool(name="count", description="Pure remote fixture", input_schema={}),)

    async def call_tool(self, name: str, arguments: dict[str, JsonValue]) -> MCPCallResult:
        self.calls.append((name, arguments))
        return MCPCallResult(data={"count": 2}, is_error=self.is_error)


def install(client: FakeMCP) -> InstalledCapabilities:
    registry = InstalledCapabilities()
    asyncio.run(
        MCPAdapter(client).install(
            registry,
            "count",
            spec(),
            Input,
            Output,
            ExecutionDependencies(central_required=False),
        )
    )
    return registry


def test_discovery_and_installation_do_not_authorize_execution() -> None:
    client = FakeMCP()
    registry = install(client)
    assert len(registry.discover()) == 1
    denied = asyncio.run(BridgeExecutor(registry).execute(invocation()))
    assert denied.status == "failed"
    assert client.calls == []
    bridge = BridgeExecutor(registry, LocalPolicy((grant(),)))
    allowed = asyncio.run(bridge.execute(invocation()))
    assert allowed.status == "succeeded"
    assert client.calls == [("count", {"count": 1})]


def test_missing_mcp_tool_cannot_be_bound() -> None:
    with pytest.raises(ValueError, match="not advertised"):
        asyncio.run(
            MCPAdapter(FakeMCP()).install(
                InstalledCapabilities(),
                "missing",
                spec(),
                Input,
                Output,
                ExecutionDependencies(central_required=False),
            )
        )


def test_discovery_failure_is_not_an_empty_success() -> None:
    class Broken(FakeMCP):
        async def list_tools(self) -> tuple[MCPTool, ...]:
            raise RuntimeError("password=synthetic")

    result = asyncio.run(MCPAdapter(Broken()).discover())
    assert result.failure is not None
    assert "synthetic" not in result.model_dump_json()


def test_mcp_error_is_a_failed_capability_result() -> None:
    client = FakeMCP()
    client.is_error = True
    bridge = BridgeExecutor(install(client), LocalPolicy((grant(),)))
    assert asyncio.run(bridge.execute(invocation())).status == "failed"


def test_duplicate_advertised_tool_names_are_a_distinct_failure() -> None:
    class Duplicated(FakeMCP):
        async def list_tools(self) -> tuple[MCPTool, ...]:
            tool = MCPTool(name="count", description="Pure remote fixture", input_schema={})
            return (tool, tool)

    result = asyncio.run(MCPAdapter(Duplicated()).discover())
    assert result.failure is not None and result.failure.code == "mcp_duplicate_tool_names"


def test_discovery_timeout_is_bounded() -> None:
    class Slow(FakeMCP):
        async def list_tools(self) -> tuple[MCPTool, ...]:
            await asyncio.Event().wait()
            return ()

    result = asyncio.run(MCPAdapter(Slow(), timeout_seconds=0.01).discover())
    assert result.failure is not None and result.failure.code == "mcp_discovery_timeout"
