"""All executable tools share discovery/invocation, independently of procedures."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from test_dispatch import Handler, Input, Output, invocation, spec
from test_gateway import Handler as ProbeHandler
from test_gateway import gateway, request
from test_turn_effects import Scripted, _reply

from agent.skills import SkillManifest
from capabilities.contracts import CapabilitySpec
from capabilities.runtime import InstalledCapabilities
from common.assets import ExecutionDependencies
from host_runtime.tool_access import ToolAccess, status_only
from models.contracts import ModelMessage
from workflow.dispatch import BridgeExecutor


def _access(effect: str = "read") -> tuple[ToolAccess, Handler]:
    handler = Handler()
    raw = spec().model_dump(mode="json")
    raw["side_effect"] = effect
    registry = InstalledCapabilities()
    registry.register(
        CapabilitySpec.model_validate(raw),
        handler,
        Input,
        Output,
        ExecutionDependencies(central_required=False),
    )
    return ToolAccess(BridgeExecutor(registry)), handler


def test_catalog_description_and_call_need_no_skill_or_grant() -> None:
    access, handler = _access()
    catalog = access.catalog(query="count", limit=1)
    assert catalog["ok"] and catalog["total"] == 1
    assert catalog["next_cursor"] is None
    assert catalog["tools"][0]["target"] == "sample/count@1.0.0"
    described = access.describe("sample/count@1.0.0")
    assert described["ok"]
    assert "count" in described["tool"]["input_schema"]["properties"]
    assert handler.calls == []  # discovery has no execution

    result = asyncio.run(access.invoke(invocation().context, "sample/count@1.0.0", {"count": 4}))
    assert result.status == "succeeded"
    assert isinstance(result.data, dict) and result.data["result"] == {"count": 5}
    assert handler.calls == [invocation().context]


def test_paging_does_not_make_other_tools_unreachable() -> None:
    access, _ = _access()
    raw = spec().model_dump(mode="json")
    raw["identity"]["name"] = "another"
    raw["name"] = "sample.another"
    access.bridge.installed.register(
        CapabilitySpec.model_validate(raw),
        Handler(),
        Input,
        Output,
        ExecutionDependencies(central_required=False),
    )
    first = access.catalog(limit=1)
    second = access.catalog(limit=1, cursor=first["next_cursor"])
    targets = {first["tools"][0]["target"], second["tools"][0]["target"]}
    assert targets == {"sample/another@1.0.0", "sample/count@1.0.0"}
    assert second["next_cursor"] is None and second["total"] == 2
    for target in targets:
        assert access.describe(target)["ok"]


def test_unknown_target_and_invalid_arguments_are_real_failures() -> None:
    access, handler = _access()
    missing = asyncio.run(access.invoke(invocation().context, "sample/missing@1.0.0", {}))
    bad = asyncio.run(access.invoke(invocation().context, "sample/count@1.0.0", {"count": -1}))
    assert (
        missing.status == "failed"
        and missing.failure
        and missing.failure.code == "capability_not_installed"
    )
    assert bad.status == "failed" and bad.failure and bad.failure.code == "invalid_input"
    assert handler.calls == []


def test_known_unconfigured_tools_are_setup_requirements_not_permission_denials() -> None:
    access, handler = _access()
    raw = spec().model_dump(mode="json")
    raw["identity"]["name"] = "configured-only"
    raw["name"] = "sample.configured_only"
    offered = CapabilitySpec.model_validate(raw)
    access.bridge.installed.offer(offered)
    catalog = access.catalog(query="configured-only")
    assert catalog["tools"][0]["status"] == "needs_setup"
    described = access.describe("sample/configured-only@1.0.0")
    assert described["tool"]["status"] == "needs_setup"
    result = asyncio.run(access.invoke(invocation().context, "sample/configured-only@1.0.0", {}))
    assert result.failure and result.failure.code == "needs_setup"
    assert handler.calls == []


def test_external_authoring_projection_does_not_forward_tool_content() -> None:
    access, _ = _access()
    outcome = asyncio.run(access.invoke(invocation().context, "sample/count@1.0.0", {"count": 4}))
    projection = status_only(outcome)
    assert projection["ok"] and projection["target"] == "sample/count@1.0.0"
    assert "result" not in projection and "data" not in projection
    assert set(projection) <= {
        "ok",
        "status",
        "target",
        "failure_code",
        "handler_invoked",
        "replayed",
    }


def _conversation(effect: str, calls: list[tuple[str, dict[str, Any]]]) -> tuple[Any, Handler]:
    model = Scripted([*[_reply(call) for call in calls], _reply(text="done")])
    built = gateway(ProbeHandler(), model)
    handler = Handler()
    raw = spec().model_dump(mode="json")
    raw["side_effect"] = effect
    capability = CapabilitySpec.model_validate(raw)
    built.bridge.installed.register(
        capability, handler, Input, Output, ExecutionDependencies(central_required=False)
    )
    access = ToolAccess(built.bridge)
    built.host_tools = access.tools
    built.router.commands.skills.register(
        SkillManifest.model_validate(
            {
                "metadata": {
                    "identity": {"namespace": "engineering", "name": "counter", "version": "1.0.0"},
                    "owner": {"type": "user", "id": "engineer"},
                    "visibility": "private",
                    "lifecycle": "draft",
                },
                "alias": "counter",
                "instructions": "Run the fixture counter.",
                "commands": [{"name": "run", "kind": "capability", "target": capability.identity}],
                "default_command": "run",
            }
        )
    )
    message = "run the fixture tools"
    history = (ModelMessage(role="user", text=message),)
    return asyncio.run(built.converse(request(message), history)), handler


def test_writes_through_generic_and_skill_aliases_happen_once() -> None:
    result, handler = _conversation(
        "write",
        [
            ("tools__invoke", {"target": "sample/count@1.0.0", "arguments": {"count": 1}}),
            ("counter__run", {"count": 1}),
        ],
    )
    assert result.status == "answered" and result.text == "done"
    assert len(handler.calls) == 1
    assert result.tools[1].replayed


def test_generic_reads_are_not_memoized_as_side_effects() -> None:
    result, handler = _conversation(
        "read",
        [
            ("tools__invoke", {"target": "sample/count@1.0.0", "arguments": {"count": 1}}),
            ("tools__invoke", {"target": "sample/count@1.0.0", "arguments": {"count": 1}}),
        ],
    )
    assert result.status == "answered" and len(handler.calls) == 2
    assert not any(tool.replayed for tool in result.tools)


def test_reconnecting_same_target_cannot_reset_a_successful_effect_identity() -> None:
    from agent.gateway import capability_effect

    access, handler = _access("write")
    context = invocation().context
    target = spec().identity
    before = capability_effect(access.bridge, context, target, {"count": 1})
    access.bridge.installed.unregister(target)
    access.bridge.installed.register(
        spec().model_copy(update={"side_effect": "write"}),
        handler,
        Input,
        Output,
        ExecutionDependencies(central_required=False),
    )
    after = capability_effect(access.bridge, context, target, {"count": 1})
    assert before is not None and after is not None
    assert before.key == after.key


def test_external_mcp_uses_same_target_and_metadata_boundary(tmp_path: Path) -> None:
    from test_external_authoring import _items, _obj, desk

    from host_runtime.mcp_server import TOOLS, dispatch

    authoring, recorder = desk(tmp_path)
    assert {"aep_tools_catalog", "aep_tools_describe", "aep_tools_invoke"} <= set(TOOLS)
    catalog = dispatch(authoring, "aep_tools_catalog", {"query": "read-it"})
    assert catalog["ok"] and catalog["total"] == 1
    target = _obj(_items(catalog["tools"])[0])["target"]
    described = dispatch(authoring, "aep_tools_describe", {"target": target})
    assert _obj(_obj(described["tool"])["input_schema"])["properties"]
    result = dispatch(
        authoring, "aep_tools_invoke", {"target": target, "arguments": {"value": "fixture"}}
    )
    assert result["ok"] and result["handler_invoked"]
    assert "fixture" not in str(result)
    assert recorder.calls == ["fixture"]
