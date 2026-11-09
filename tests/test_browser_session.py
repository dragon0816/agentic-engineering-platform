"""`browser/operate` (lab gap L1): one Edge kept for a task, on allowed sites only."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable
from pathlib import Path
from typing import Any, TypeVar

import pytest
from pydantic import JsonValue

from capabilities.browser_session.handlers import (
    SPEC,
    BrowserRequest,
    BrowserResult,
    BrowserSessionHandler,
)
from capabilities.runtime import (
    CapabilityExecutionFailed,
    CapabilityGrant,
    CapabilityRefused,
    InstalledCapabilities,
    LocalPolicy,
)
from common.assets import ExecutionDependencies
from common.execution import RequestContext, TraceIdentifiers
from host_runtime.bridge_tools import bridge_tools
from integrations.browser import PageView
from workflow.dispatch import BridgeExecutor

SITE = "http://127.0.0.1:8810"
T = TypeVar("T")


async def _settled(pending: Awaitable[T]) -> T:
    """Await a tool handler's result; asyncio.run needs a coroutine, not any Awaitable."""
    return await pending


class FakeBrowser:
    """Answers the few page expressions the runner and the handler use."""

    def __init__(self) -> None:
        self.url = "about:blank"
        self.started = 0
        self.visited: list[str] = []

    def start(self) -> None:
        self.started += 1

    def close(self) -> None:
        pass

    def navigate(self, url: str) -> None:
        self.url = url
        self.visited.append(url)

    def evaluate(self, expression: str) -> Any:
        if expression == "1":
            return 1
        if expression == "document.readyState":
            return "complete"
        if expression == "document.location.href":
            return self.url
        if "inspection:" in expression:
            return json.dumps(
                {
                    "inspection": {
                        "scope": "body",
                        "offset": 0,
                        "next_offset": None,
                        "elements": [
                            {
                                "index": 0,
                                "parent": None,
                                "depth": 0,
                                "tag": "body",
                                "path": "body",
                                "text": "hello",
                                "attributes": {},
                            }
                        ],
                    }
                }
            )
        if "record" in expression and "querySelectorAll('tr')" in expression:
            return json.dumps({"ok": True, "record": {"Page": self.url.rsplit("/", 1)[1]}})
        return json.dumps({"ok": True})

    def look(self) -> PageView:
        return PageView(url=self.url, title="Fake", text="hello")

    def page(self) -> Any:
        return self


def handler(tmp_path: Path, browser: FakeBrowser) -> BrowserSessionHandler:
    return BrowserSessionHandler(
        (SITE,),
        tmp_path / "profile",
        headless=True,
        timeout_s=5,
        workspace_roots=(str(tmp_path / "tasks"),),
        browser_factory=lambda: browser,
    )


def test_one_browser_serves_every_call_and_for_each_keeps_each_item(tmp_path: Path) -> None:
    browser = FakeBrowser()
    run = handler(tmp_path, browser)
    opened = {"actions": [{"do": "open", "url": SITE + "/x"}]}
    first = run.run(BrowserRequest.model_validate(opened))
    assert first.url == SITE + "/x" and "hello" in first.page
    second = run.run(
        BrowserRequest.model_validate(
            {
                "actions": [
                    {"do": "open", "url": SITE + "/orders/{item}"},
                    {"do": "read_record", "table": "#header", "save_as": "head"},
                ],
                "for_each": ["A1", "B2"],
                "look": False,
            }
        )
    )
    assert second.items == {"A1": {"head": {"Page": "A1"}}, "B2": {"head": {"Page": "B2"}}}
    assert second.page == "" and browser.started == 1


def test_other_sites_and_downloads_outside_a_task_workspace_are_refused(tmp_path: Path) -> None:
    run = handler(tmp_path, FakeBrowser())
    with pytest.raises(CapabilityExecutionFailed) as failed:
        run.run(
            BrowserRequest.model_validate(
                {"actions": [{"do": "open", "url": "https://x.example/"}]}
            )
        )
    assert failed.value.code == "web_origin_not_allowed"
    download = {"do": "download", "target": {"css": "#export"}, "save_as": "rows.csv"}
    for workspace, code in (
        (None, "browser_workspace_missing"),
        (str(tmp_path / "elsewhere"), "browser_workspace_not_allowed"),
    ):
        with pytest.raises(CapabilityRefused) as refused:
            run.run(BrowserRequest.model_validate({"actions": [download], "workspace": workspace}))
        assert refused.value.code == code


def test_the_conversation_tool_goes_through_the_bridge_and_its_grants(tmp_path: Path) -> None:
    browser = FakeBrowser()
    installed = InstalledCapabilities()
    installed.register(
        SPEC,
        handler(tmp_path, browser),
        BrowserRequest,
        BrowserResult,
        ExecutionDependencies(central_required=False),
    )
    context = RequestContext(
        trace=TraceIdentifiers(trace_id="t", request_id="r", span_id="s"),
        actor="owner",
        namespace="engineering",
        channel="local",
        message="x",
    )
    args: dict[str, JsonValue] = {"actions": [{"do": "open", "url": SITE + "/orders"}]}
    ungranted = bridge_tools(BridgeExecutor(installed, LocalPolicy(())))
    tool = next(tool for tool in ungranted if tool.tool.name == "browser__operate")
    assert tool.tool.name == "browser__operate"
    refused = asyncio.run(_settled(tool.handler(context, args)))
    assert refused.status == "failed" and browser.visited == []
    grant = CapabilityGrant(
        actor="owner",
        asset=SPEC.identity,
        permissions=SPEC.policy.required_permissions,
        policy_refs=SPEC.policy.policy_refs,
        approval_ref="owner-approved",
    )
    granted = next(
        tool
        for tool in bridge_tools(BridgeExecutor(installed, LocalPolicy((grant,))))
        if tool.tool.name == "browser__operate"
    )
    done = asyncio.run(_settled(granted.handler(context, args)))
    assert done.status == "succeeded" and browser.visited == [SITE + "/orders"]
    assert bridge_tools(BridgeExecutor(InstalledCapabilities(), LocalPolicy(()))) == []


def test_a_browser_left_on_the_agents_profile_is_asked_to_close_then_replaced(
    tmp_path: Path,
) -> None:
    """Lab fix-003: a host stopped hard left Edge holding the profile."""

    class Held(Exception):
        code = "profile_in_use"

    made: list[FakeBrowser] = []
    closed: list[bool] = []

    class Leftover(FakeBrowser):
        def start(self) -> None:
            if not made[1:]:
                raise Held()
            super().start()

        def close_leftover(self) -> bool:
            closed.append(True)
            return True

    def factory() -> FakeBrowser:
        made.append(Leftover())
        return made[-1]

    run = BrowserSessionHandler(
        (SITE,),
        tmp_path / "profile",
        headless=True,
        timeout_s=5,
        workspace_roots=(),
        browser_factory=factory,
    )
    run.run(BrowserRequest.model_validate({"actions": [], "look": False}))
    assert closed == [True] and len(made) == 2 and made[1].started == 1


def test_conversation_browser_schema_is_the_actual_bounded_action_contract() -> None:
    from host_runtime.bridge_tools import _schema

    schema = _schema()
    assert schema == BrowserRequest.model_json_schema()
    actions = schema["$defs"]["WebAction"]["properties"]
    assert "inspect_dom" in actions["do"]["enum"]
    assert actions["limit"]["maximum"] == 200
    assert "WebPagination" in schema["$defs"]


def test_inspect_dom_rejects_unbounded_or_executable_arguments() -> None:
    from pydantic import ValidationError

    for override in (
        {"limit": 201},
        {"offset": -1},
        {"offset": 100001},
        {"javascript": "fetch('/')"},
    ):
        with pytest.raises(ValidationError):
            BrowserRequest.model_validate(
                {"actions": [{"do": "inspect_dom", "save_as": "dom", **override}]}
            )


def test_failed_browser_action_keeps_fresh_diagnostics_through_bridge(tmp_path: Path) -> None:
    class FailedBrowser(FakeBrowser):
        def evaluate(self, expression: str) -> Any:
            if "const hit = find(spec)" in expression:
                return json.dumps({"error": "web_target_missing"})
            if "inspection:" in expression:
                return json.dumps(
                    {
                        "inspection": {
                            "scope": "body",
                            "offset": 0,
                            "next_offset": None,
                            "elements": [
                                {
                                    "index": 0,
                                    "parent": None,
                                    "depth": 0,
                                    "tag": "body",
                                    "path": "body:nth-child(1)",
                                    "text": "Current failure page",
                                    "attributes": {},
                                }
                            ],
                        }
                    }
                )
            return super().evaluate(expression)

    browser = FailedBrowser()
    installed = InstalledCapabilities()
    installed.register(
        SPEC,
        handler(tmp_path, browser),
        BrowserRequest,
        BrowserResult,
        ExecutionDependencies(central_required=False),
    )
    grant = CapabilityGrant(
        actor="owner",
        asset=SPEC.identity,
        permissions=SPEC.policy.required_permissions,
        policy_refs=SPEC.policy.policy_refs,
        approval_ref="owner-approved",
    )
    tool = next(
        tool
        for tool in bridge_tools(BridgeExecutor(installed, LocalPolicy((grant,))))
        if tool.tool.name == "browser__operate"
    )
    context = RequestContext(
        trace=TraceIdentifiers(trace_id="t", request_id="r", span_id="s"),
        actor="owner",
        namespace="engineering",
        channel="local",
        message="x",
    )
    result = asyncio.run(
        _settled(
            tool.handler(
                context,
                {
                    "actions": [
                        {"do": "open", "url": SITE + "/fresh"},
                        {"do": "click", "target": {"css": "#gone"}},
                    ],
                    "look": False,
                },
            )
        )
    )
    assert result.status == "failed" and result.failure is not None
    assert result.failure.code == "web_target_missing"
    assert "actions[1]" in result.failure.message
    assert isinstance(result.data, dict)
    assert result.data["failed_action_index"] == 1 and result.data["failed_action_kind"] == "click"
    assert "Current failure page" in json.dumps(result.data["diagnostics"])
    assert result.data["url"] == SITE + "/fresh"


def test_browser_observation_preserves_nonsecret_query_and_navigation_fragment(
    tmp_path: Path,
) -> None:
    browser = FakeBrowser()
    browser.url = SITE + "/report?customer=C001&view=All#app.component=orders&Nav=report"
    result = handler(tmp_path, browser).run(BrowserRequest())
    assert result.url == browser.url


def test_browser_observation_redacts_secret_query_fields_without_losing_navigation(
    tmp_path: Path,
) -> None:
    browser = FakeBrowser()
    browser.url = (
        SITE + "/report?password=query-secret&view=All&token=opaque-token"
        "#access_token=fragment-secret&Nav=report"
    )
    result = handler(tmp_path, browser).run(BrowserRequest())
    assert "query-secret" not in result.url and "fragment-secret" not in result.url
    assert "opaque-token" not in result.url
    assert "view=All" in result.url and "Nav=report" in result.url


def test_read_only_inspection_alias_has_closed_schema_and_still_requires_bridge_grant(
    tmp_path: Path,
) -> None:
    browser = FakeBrowser()
    installed = InstalledCapabilities()
    installed.register(
        SPEC,
        handler(tmp_path, browser),
        BrowserRequest,
        BrowserResult,
        ExecutionDependencies(central_required=False),
    )
    tools = {
        tool.tool.name: tool for tool in bridge_tools(BridgeExecutor(installed, LocalPolicy(())))
    }
    tool = tools["browser__inspect"]
    assert tool.side_effect == "read" and tools["browser__operate"].side_effect == SPEC.side_effect
    schema = tool.tool.input_schema
    assert schema is not None and schema["additionalProperties"] is False
    assert isinstance(schema["properties"], dict)
    assert set(schema["properties"]) == {"scope", "offset", "limit"}
    context = RequestContext(
        trace=TraceIdentifiers(trace_id="t", request_id="r", span_id="s"),
        actor="owner",
        namespace="engineering",
        channel="local",
        message="inspect",
    )
    result = asyncio.run(_settled(tool.handler(context, {})))
    assert result.status == "failed" and result.failure is not None
    assert browser.started == 0


def test_read_only_inspection_alias_rejects_extra_keys_before_bridge_dispatch(
    tmp_path: Path,
) -> None:
    from capabilities.runtime import CapabilityInvocation
    from common.execution import CapabilityResult

    class RecordingBridge(BridgeExecutor):
        def __init__(self, installed: InstalledCapabilities) -> None:
            super().__init__(installed, LocalPolicy(()))
            self.calls: list[CapabilityInvocation] = []

        async def execute(self, call: CapabilityInvocation) -> CapabilityResult:
            self.calls.append(call)
            return await super().execute(call)

    installed = InstalledCapabilities()
    installed.register(
        SPEC,
        handler(tmp_path, FakeBrowser()),
        BrowserRequest,
        BrowserResult,
        ExecutionDependencies(central_required=False),
    )
    bridge = RecordingBridge(installed)
    tool = next(tool for tool in bridge_tools(bridge) if tool.tool.name == "browser__inspect")
    context = RequestContext(
        trace=TraceIdentifiers(trace_id="t", request_id="r", span_id="s"),
        actor="owner",
        namespace="engineering",
        channel="local",
        message="inspect",
    )
    for extra in ("actions", "url", "javascript", "do", "values", "look", "save_as"):
        result = asyncio.run(_settled(tool.handler(context, {extra: "rejected"})))
        assert result.status == "failed" and result.failure is not None
        assert result.failure.code == "invalid_input"
    invalid_arguments: tuple[dict[str, JsonValue], ...] = (
        {"limit": 201},
        {"offset": -1},
        {"offset": 100001},
        {"limit": True},
        {"scope": ""},
    )
    for arguments in invalid_arguments:
        result = asyncio.run(_settled(tool.handler(context, arguments)))
        assert result.status == "failed" and result.failure is not None
        assert result.failure.code == "invalid_input"
    assert bridge.calls == []
    asyncio.run(_settled(tool.handler(context, {"scope": "#report", "offset": 80, "limit": 20})))
    assert len(bridge.calls) == 1
    assert bridge.calls[0].target == SPEC.identity
    assert bridge.calls[0].arguments == {
        "actions": [
            {
                "do": "inspect_dom",
                "save_as": "inspection",
                "scope": "#report",
                "offset": 80,
                "limit": 20,
            }
        ],
        "look": False,
    }
