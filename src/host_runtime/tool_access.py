"""Common tool discovery and invocation; execution belongs to the Bridge.

No Skill selection, member grant or approval determines which installed target
can be called. Technical contracts, actual environment errors and model/data
routing remain independent. External authoring adapters use status_only rather
than forwarding arbitrary tool output into an ineligible model route.
"""

from __future__ import annotations

import asyncio
import uuid
from contextlib import nullcontext
from typing import Any

from pydantic import Field, JsonValue, ValidationError

from agent.gateway import HostTool, HostToolOutcome, ToolEffect, capability_effect
from agent.turn_effects import TurnEffects, effect_key
from agent.turn_effects import current as current_effects
from capabilities.runtime import CapabilityInvocation
from common.assets import AssetIdentity
from common.base import Contract
from common.execution import Failure, RequestContext, TraceIdentifiers
from host_runtime.mcp_servers import McpHub, McpServerConfig
from models.contracts import ModelTool
from workflow.dispatch import BridgeExecutor


class CatalogRequest(Contract):
    query: str = ""
    cursor: int = Field(default=0, ge=0)
    limit: int = Field(default=40, ge=1, le=100)


class DescribeRequest(Contract):
    target: str


class InvokeRequest(DescribeRequest):
    arguments: dict[str, JsonValue] = Field(default_factory=dict)


class InstallMcpRequest(Contract):
    config: McpServerConfig


def mcp_definitions() -> dict[str, tuple[str, dict[str, Any]]]:
    return {
        "aep_tools_catalog": (
            "Find all installed Bridge/MCP tools, with pagination.",
            CatalogRequest.model_json_schema(),
        ),
        "aep_tools_describe": (
            "Read the input/output schema of one installed tool.",
            DescribeRequest.model_json_schema(),
        ),
        "aep_tools_invoke": (
            "Invoke an installed tool under the execution environment; return actual status. "
            "Native routes without established result eligibility withhold result contents.",
            InvokeRequest.model_json_schema(),
        ),
        "aep_tools_install_mcp": (
            "Save/connect an MCP server and use its tools in this session. "
            "Use IT-provisioned environment credential references; never put secrets in config.",
            InstallMcpRequest.model_json_schema(),
        ),
    }


def tool_context(actor: str, namespace: str, session_id: str | None = None) -> RequestContext:
    ident = f"tool-{uuid.uuid4().hex}"
    return RequestContext(
        trace=TraceIdentifiers(trace_id=ident, request_id=ident, span_id=ident),
        actor=actor,
        namespace=namespace,
        channel="mcp",
        session_id=session_id,
        message="Invoke an AEP tool",
    )


def _identity(target: str) -> AssetIdentity:
    path, version = target.rsplit("@", 1)
    namespace, name = path.split("/", 1)
    return AssetIdentity(namespace=namespace, name=name, version=version)


def _target(identity: AssetIdentity) -> str:
    return f"{identity.namespace}/{identity.name}@{identity.version}"


def status_only(outcome: HostToolOutcome) -> dict[str, JsonValue]:
    """Preserve the external authoring endpoint's metadata-only data boundary."""
    data = outcome.data if isinstance(outcome.data, dict) else {}
    return {
        "ok": outcome.status == "succeeded",
        "status": outcome.status,
        "target": data.get("target"),
        "failure_code": None if outcome.failure is None else outcome.failure.code,
        "handler_invoked": bool(data.get("handler_invoked")),
        "replayed": bool(data.get("replayed")),
    }


class ToolAccess:
    def __init__(self, bridge: BridgeExecutor, *, mcp: McpHub | None = None) -> None:
        self.bridge = bridge
        self.mcp = mcp

    async def install_mcp(self, context: RequestContext, config: dict[str, Any]) -> HostToolOutcome:
        if self.mcp is None:
            return HostToolOutcome(
                status="failed",
                failure=Failure(
                    code="mcp_manager_unavailable", message="This execution host has no MCP manager"
                ),
            )
        try:
            checked = McpServerConfig.model_validate(config)
        except ValidationError:
            return _invalid()
        return await asyncio.to_thread(self._install_mcp, context, checked, current_effects())

    def _install_mcp(
        self, context: RequestContext, checked: McpServerConfig, effects: TurnEffects | None
    ) -> HostToolOutcome:
        assert self.mcp is not None
        key = effect_key(
            "mcp-install",
            {
                "manager": str(self.mcp.path.resolve()),
                "actor": context.actor,
                "namespace": context.namespace,
                "config": checked.model_dump(mode="json"),
            },
        )
        with effects.operations_lock if effects is not None else nullcontext():
            earlier = effects.replay_operation(key) if effects is not None else None
            if earlier is not None:
                data = earlier.data if isinstance(earlier.data, dict) else {}
                return HostToolOutcome(status="succeeded", data={**data, "replayed": True})
            result = self._configure_mcp(checked)
            if effects is not None and result.status == "succeeded":
                effects.record_operation(key, result)
            return result

    def _configure_mcp(self, checked: McpServerConfig) -> HostToolOutcome:
        hub = self.mcp
        assert hub is not None
        try:
            hub.save(checked, {}, connect=False)
            if checked.enabled:
                hub.connect(checked.name)
        except OSError:
            return HostToolOutcome(
                status="failed",
                failure=Failure(
                    code="mcp_configuration_write_failed",
                    message="The environment could not save/connect this server",
                ),
            )
        state = next(
            (item for item in hub.status() if item["config"]["name"] == checked.name), None
        )
        if state is None or state["status"] not in {"connected", "disabled"}:
            code = (
                "mcp_connection_failed"
                if state is None
                else str(state["error"] or "mcp_connection_failed")
            )
            return HostToolOutcome(
                status="failed",
                data={"server": checked.name, "connected": False},
                failure=Failure(code=code, message="The MCP server did not connect"),
            )
        return HostToolOutcome(
            status="succeeded",
            data={
                "server": checked.name,
                "connected": state["status"] == "connected",
                "tools": state["tools"],
            },
        )

    def call(
        self,
        name: str,
        args: dict[str, Any],
        context: RequestContext,
        *,
        metadata_only: bool = False,
    ) -> dict[str, JsonValue]:
        """Synchronous MCP adapter; identical schemas and execution contracts."""
        try:
            if name == "aep_tools_catalog":
                asked = CatalogRequest.model_validate(args)
                return self.catalog(**asked.model_dump())
            if name == "aep_tools_describe":
                return self.describe(DescribeRequest.model_validate(args).target)
            if name == "aep_tools_invoke":
                invoke = InvokeRequest.model_validate(args)
                result = asyncio.run(self.invoke(context, invoke.target, invoke.arguments))
                if metadata_only:
                    return status_only(result)
                return {"ok": result.status == "succeeded", **result.model_dump(mode="json")}
            if name == "aep_tools_install_mcp":
                config = InstallMcpRequest.model_validate(args).config
                result = asyncio.run(self.install_mcp(context, config.model_dump(mode="json")))
                return {"ok": result.status == "succeeded", **result.model_dump(mode="json")}
        except ValidationError:
            return {"ok": False, "code": "invalid_input"}
        return {"ok": False, "code": "unknown_tool"}

    def native_call(
        self, name: str, args: dict[str, Any], context: RequestContext, backend: str | None
    ) -> dict[str, JsonValue]:
        """Execute without treating unknown result classification as public data.

        Native initial-history eligibility does not classify subsequent tool outputs.
        Keep tools executable, but use the existing authoring status boundary until
        this route has evidence that the receiving model is eligible for the result.
        """
        result = self.call(name, args, context, metadata_only=True)
        if name == "aep_tools_invoke":
            result["data_route"] = {
                "backend": backend or "unknown",
                "result_data_withheld": True,
                "code": "result_eligibility_not_established",
                "message": "Execution status only. Use an eligible company Gateway route "
                "to analyze source contents.",
            }
        return result

    def catalog(self, query: str = "", cursor: int = 0, limit: int = 40) -> dict[str, Any]:
        asked = CatalogRequest(query=query, cursor=cursor, limit=limit)
        terms = asked.query.casefold().split()
        found = [
            {
                "target": _target(spec.identity),
                "purpose": spec.description,
                "side_effect": spec.side_effect,
                "status": "installed"
                if self.bridge.installed.get(spec.identity)
                else "needs_setup",
            }
            for spec in (*self.bridge.installed.discover(), *self.bridge.installed.offered())
            if all(
                term in f"{_target(spec.identity)} {spec.description}".casefold() for term in terms
            )
        ]
        end = min(asked.cursor + asked.limit, len(found))
        return {
            "ok": True,
            "tools": found[asked.cursor : end],
            "total": len(found),
            "next_cursor": end if end < len(found) else None,
        }

    def describe(self, target: str) -> dict[str, Any]:
        try:
            identity = _identity(target)
        except (ValueError, ValidationError):
            return {"ok": False, "code": "invalid_tool_reference"}
        binding = self.bridge.installed.get(identity)
        if binding is None:
            offered = next(
                (spec for spec in self.bridge.installed.offered() if spec.identity == identity),
                None,
            )
            if offered is not None:
                return {
                    "ok": True,
                    "tool": {
                        "target": target,
                        "purpose": offered.description,
                        "side_effect": offered.side_effect,
                        "status": "needs_setup",
                        "input_contract": offered.input_contract,
                        "output_contract": offered.output_contract,
                        "environment_checked": False,
                    },
                }
            return {"ok": False, "code": "capability_not_installed", "target": target}
        return {
            "ok": True,
            "tool": {
                "target": _target(identity),
                "purpose": binding.spec.description,
                "side_effect": binding.spec.side_effect,
                "input_schema": binding.input_model.model_json_schema(),
                "output_schema": binding.output_model.model_json_schema(),
                "status": "installed",
                "environment_checked": False,
            },
        }

    async def invoke(
        self, context: RequestContext, target: str, arguments: dict[str, JsonValue]
    ) -> HostToolOutcome:
        try:
            identity = _identity(target)
        except (ValueError, ValidationError):
            return HostToolOutcome(
                status="failed",
                failure=Failure(code="invalid_tool_reference", message="Invalid tool reference"),
            )
        if self.bridge.installed.get(identity) is None and any(
            spec.identity == identity for spec in self.bridge.installed.offered()
        ):
            return HostToolOutcome(
                status="failed",
                data={"target": target, "handler_invoked": False},
                failure=Failure(
                    code="needs_setup", message="Configure this integration before invoking it"
                ),
            )
        result = await self.bridge.execute(
            CapabilityInvocation(
                context=context, target=identity, arguments=arguments, origin="model"
            )
        )
        return HostToolOutcome(
            status="succeeded" if result.status == "succeeded" else "failed",
            data={
                "target": _target(identity),
                "execution_status": result.status,
                "result": result.data,
                "handler_invoked": result.handler_invoked,
                "replayed": "capability_replayed" in result.warnings,
            },
            failure=result.failure,
        )

    def tools(self) -> list[HostTool]:
        def effect(context: RequestContext, args: dict[str, JsonValue]) -> ToolEffect | None:
            try:
                asked = InvokeRequest.model_validate(args)
                identity = _identity(asked.target)
            except (ValueError, ValidationError):
                return None
            return capability_effect(self.bridge, context, identity, asked.arguments)

        async def catalog(_context: RequestContext, args: dict[str, JsonValue]) -> HostToolOutcome:
            try:
                asked = CatalogRequest.model_validate(args)
            except ValidationError:
                return _invalid()
            return HostToolOutcome(status="succeeded", data=self.catalog(**asked.model_dump()))

        async def describe(_context: RequestContext, args: dict[str, JsonValue]) -> HostToolOutcome:
            try:
                asked = DescribeRequest.model_validate(args)
            except ValidationError:
                return _invalid()
            data = self.describe(asked.target)
            if not data["ok"]:
                return HostToolOutcome(
                    status="failed",
                    data=data,
                    failure=Failure(code=data["code"], message="Tool description unavailable"),
                )
            return HostToolOutcome(status="succeeded", data=data)

        async def invoke(context: RequestContext, args: dict[str, JsonValue]) -> HostToolOutcome:
            try:
                asked = InvokeRequest.model_validate(args)
            except ValidationError:
                return _invalid()
            return await self.invoke(context, asked.target, asked.arguments)

        async def install_mcp(
            context: RequestContext, args: dict[str, JsonValue]
        ) -> HostToolOutcome:
            try:
                asked = InstallMcpRequest.model_validate(args)
            except ValidationError:
                return _invalid()
            return await self.install_mcp(context, asked.config.model_dump(mode="json"))

        return [
            HostTool(
                ModelTool(
                    name="tools__install_mcp",
                    description=mcp_definitions()["aep_tools_install_mcp"][0],
                    input_contract="host.tools.install-mcp.v1",
                    input_schema=InstallMcpRequest.model_json_schema(),
                ),
                install_mcp,
                side_effect="execute",
                records_effect=True,
            ),
            HostTool(
                ModelTool(
                    name="tools__catalog",
                    description=(
                        "Find all installed AEP/Bridge/MCP tools. Page until next_cursor "
                        "is null; no selected Skill is required."
                    ),
                    input_contract="host.tools.catalog.v1",
                    input_schema=CatalogRequest.model_json_schema(),
                ),
                catalog,
                side_effect="read",
            ),
            HostTool(
                ModelTool(
                    name="tools__describe",
                    description="Read one tool's exact input/output schema before invoking it.",
                    input_contract="host.tools.describe.v1",
                    input_schema=DescribeRequest.model_json_schema(),
                ),
                describe,
                side_effect="read",
            ),
            HostTool(
                ModelTool(
                    name="tools__invoke",
                    description=(
                        "Invoke any installed tool through the Bridge under the actual "
                        "execution environment. Return real output or technical failure; "
                        "no AEP tool grant/approval is needed."
                    ),
                    input_contract="host.tools.invoke.v1",
                    input_schema=InvokeRequest.model_json_schema(),
                ),
                invoke,
                side_effect="execute",
                effect=effect,
            ),
        ]


def _invalid() -> HostToolOutcome:
    return HostToolOutcome(
        status="failed",
        failure=Failure(code="invalid_input", message="Tool arguments do not match the contract"),
    )
