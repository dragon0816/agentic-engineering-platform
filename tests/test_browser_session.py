"""`browser/operate` (lab gap L1): one Edge kept for a task, on allowed sites only."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest

from capabilities.browser_session.handlers import (
    SPEC,
    BrowserRequest,
    BrowserResult,
    BrowserSessionHandler,
)
from capabilities.runtime import (
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
    with pytest.raises(CapabilityRefused) as refused:
        run.run(
            BrowserRequest.model_validate(
                {"actions": [{"do": "open", "url": "https://x.example/"}]}
            )
        )
    assert refused.value.code == "web_origin_not_allowed"
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
    args = {"actions": [{"do": "open", "url": SITE + "/orders"}]}
    ungranted = bridge_tools(BridgeExecutor(installed, LocalPolicy(())))
    (tool,) = ungranted
    assert tool.tool.name == "browser__operate"
    refused = asyncio.run(tool.handler(context, args))
    assert refused.status == "failed" and browser.visited == []
    grant = CapabilityGrant(
        actor="owner",
        asset=SPEC.identity,
        permissions=SPEC.policy.required_permissions,
        policy_refs=SPEC.policy.policy_refs,
        approval_ref="owner-approved",
    )
    (granted,) = bridge_tools(BridgeExecutor(installed, LocalPolicy((grant,))))
    done = asyncio.run(granted.handler(context, args))
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
