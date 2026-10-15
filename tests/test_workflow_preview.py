"""Preview runs (owner design A, 2026-10-06; SOP_TO_WORKFLOW W4).

A preview runs read steps for real and dispatches nothing else; it shows what
write steps would receive and, where a handler can say, what they would do.
"""

from __future__ import annotations

import asyncio
import json
import sys
import urllib.request
from pathlib import Path
from typing import Any

import pytest
from test_gateway import request

from capabilities.contracts import CapabilitySpec
from capabilities.excel_blocks.handlers import (
    UPSERT_SPEC,
    UpsertHandler,
    UpsertRequest,
    UpsertResult,
)
from capabilities.runtime import CapabilityGrant, InstalledCapabilities, LocalPolicy
from capabilities.web.handlers import (
    ACT_SPEC,
    READ_SPEC,
    SELECT_SPEC,
    SelectHandler,
    SelectRequest,
    SelectResult,
    WebHostBinding,
    WebScriptHandler,
)
from common.assets import ExecutionDependencies, WorkflowManifest
from common.base import Contract
from common.execution import RequestContext
from evaluation.sop_practice import SHEET_NAME, PracticeSite, write_workbook
from integrations.web_script import WebScript, WebScriptResult
from workflow.dispatch import BridgeExecutor
from workflow.engine import InstalledWorkflows, WorkflowEngine

LOCAL = ExecutionDependencies(central_required=False)


def spec(name: str, effect: str) -> CapabilitySpec:
    policy: dict[str, Any] = {"required_permissions": [f"t.{name}"], "policy_refs": ["t"]}
    if effect != "read":
        policy["approval_required"] = True
    return CapabilitySpec.model_validate(
        {
            "identity": {"namespace": "t", "name": name, "version": "1.0.0"},
            "name": f"t.{name}",
            "description": name,
            "input_contract": "t.in",
            "output_contract": "t.out",
            "side_effect": effect,
            "policy": policy,
        }
    )


class Value(Contract):
    value: str = ""


class Calls:
    def __init__(self) -> None:
        self.ran: list[str] = []


class Echo:
    def __init__(self, name: str, calls: Calls) -> None:
        self.name, self.calls = name, calls

    async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
        self.calls.ran.append(self.name)
        return Value(value=f"{self.name}:{Value.model_validate(inputs).value}")


class Plans(Echo):
    def preview(self, inputs: Contract) -> Contract:
        return Value(value=f"would write {Value.model_validate(inputs).value}")


def manifest(steps: list[dict[str, Any]]) -> WorkflowManifest:
    return WorkflowManifest.model_validate(
        {
            "metadata": {
                "identity": {"namespace": "engineering", "name": "p", "version": "1.0.0"},
                "owner": {"type": "team", "id": "engineering"},
                "visibility": "private",
            },
            "kind": "workflow",
            "description": "preview",
            "execution": {"mode": "local"},
            "dependencies": {"central_required": False},
            "input_contract": "t.in",
            "output_contract": "t.out",
            "steps": steps,
        }
    )


def step(name: str, inputs: dict[str, Any]) -> dict[str, Any]:
    return {"capability": {"namespace": "t", "name": name, "version": "1.0.0"}, "inputs": inputs}


def engine(workflow: WorkflowManifest, *, grant_write: bool = True) -> tuple[WorkflowEngine, Calls]:
    calls = Calls()
    installed = InstalledCapabilities()
    grants = []
    for name, effect, handler in (
        ("read", "read", Echo("read", calls)),
        ("write", "write", Plans("write", calls)),
        ("send", "external_side_effect", Echo("send", calls)),
    ):
        made = spec(name, effect)
        installed.register(made, handler, Value, Value, LOCAL)
        if effect == "read" or grant_write:
            grants.append(
                CapabilityGrant(
                    actor="engineer",
                    asset=made.identity,
                    permissions=made.policy.required_permissions,
                    policy_refs=made.policy.policy_refs,
                    approval_ref="ok",
                )
            )
    bridge = BridgeExecutor(installed, LocalPolicy(tuple(grants)))
    workflows = InstalledWorkflows()
    workflows.register(workflow)
    return WorkflowEngine(workflows, bridge), calls


def preview(workflow: WorkflowManifest, **kwargs: Any) -> tuple[Any, Calls]:
    running, calls = engine(workflow, **kwargs)
    return asyncio.run(
        running.preview(request("x"), workflow.metadata.identity, {"v": "go"})
    ), calls


CHAIN = manifest(
    [
        step("read", {"value": {"source": "run", "path": ["v"]}}),
        step("write", {"value": {"source": "step", "step_index": 0, "path": ["value"]}}),
        step("send", {"value": {"source": "fixed", "value": "hello"}}),
        step("read", {"value": {"source": "step", "step_index": 1, "path": ["value"]}}),
    ]
)


def test_reads_run_writes_are_planned_and_nothing_else_is_dispatched() -> None:
    result, calls = preview(CHAIN)
    assert result.status == "previewed" and calls.ran == ["read"]
    states = [(item.state, item.side_effect) for item in result.steps]
    assert states == [
        ("ran", "read"),
        ("planned", "write"),
        ("planned", "external_side_effect"),
        ("blocked", "read"),
    ]
    assert result.steps[0].output == {"value": "read:go"}
    assert result.steps[1].inputs == {"value": "read:go"}
    assert result.steps[1].output == {"value": "would write read:go"}
    assert result.steps[2].inputs == {"value": "hello"} and result.steps[2].output is None
    assert result.steps[3].failure.code == "preview_input_from_unrun_step"


def test_a_step_the_actor_may_not_run_is_shown_as_not_permitted() -> None:
    result, calls = preview(CHAIN, grant_write=False)
    assert result.status == "failed" and result.steps[1].state == "not_permitted"
    assert calls.ran == ["read"]


def test_a_workflow_with_nothing_to_read_has_nothing_to_preview() -> None:
    result, calls = preview(manifest([step("send", {"value": {"source": "fixed", "value": "x"}})]))
    assert result.status == "unavailable" and result.failure.code == "preview_has_no_read_step"
    assert calls.ran == []


# -- the practice SOP as a Workflow, previewed and then run -----------------

SEARCH = [
    {"do": "open", "url": "{site}/"},
    {"do": "fill", "target": {"label": "客戶代碼", "kind": "field"}, "value": "{customer}"},
    {"do": "click", "target": {"label": "查詢", "kind": "button"}},
    {"do": "read_table", "table": "#orders", "save_as": "orders"},
]
NOTIFY = [
    {"do": "open", "url": "{site}/orders?customer={customer}"},
    {
        "do": "click",
        "target": {"label": "標記已通知", "kind": "button"},
        "row": {"table": "#orders", "column": "訂單號", "equals": "{item}"},
    },
]
COLUMNS = ["訂單號", "品項", "數量", "預計出貨日", "狀態"]


def ref(index: int, *path: str) -> dict[str, Any]:
    return {"source": "step", "step_index": index, "path": list(path)}


def fixed(value: Any) -> dict[str, Any]:
    return {"source": "fixed", "value": value}


def shipment_workflow() -> WorkflowManifest:
    return WorkflowManifest.model_validate(
        {
            "metadata": {
                "identity": {
                    "namespace": "engineering",
                    "name": "shipment-tracking",
                    "version": "1.0.0",
                },
                "owner": {"type": "team", "id": "engineering"},
                "visibility": "private",
            },
            "kind": "workflow",
            "description": "每日出貨追蹤 SOP",
            "execution": {"mode": "local"},
            "dependencies": {
                "central_required": False,
                "local_capabilities": ["web.read", "data.select", "excel.upsert_rows", "web.act"],
            },
            "input_contract": "t.in",
            "output_contract": "t.out",
            "steps": [
                {
                    "capability": READ_SPEC.identity.model_dump(),
                    "inputs": {"actions": fixed(SEARCH), "values": {"source": "run", "path": []}},
                },
                {
                    "capability": SELECT_SPEC.identity.model_dump(),
                    "inputs": {
                        "rows": ref(0, "data", "orders"),
                        "where": fixed({"狀態": "延遲", "通知": "標記已通知"}),
                        "take": fixed("訂單號"),
                    },
                },
                {
                    "capability": UPSERT_SPEC.identity.model_dump(),
                    "inputs": {
                        "workbook": {"source": "run", "path": ["workbook"]},
                        "sheet": fixed(SHEET_NAME),
                        "key": fixed("訂單號"),
                        "rows": ref(0, "data", "orders"),
                        "columns": fixed(COLUMNS),
                    },
                },
                {
                    "capability": ACT_SPEC.identity.model_dump(),
                    "inputs": {
                        "actions": fixed(NOTIFY),
                        "values": {"source": "run", "path": []},
                        "for_each": ref(1, "values"),
                    },
                },
            ],
        }
    )


@pytest.mark.skipif(sys.platform != "win32", reason="drives the installed Edge")
def test_the_practice_sop_previews_without_changes_then_runs(tmp_path: Path) -> None:
    from integrations.browser import browser_path

    if browser_path() is None:
        pytest.skip("no Chromium browser installed")
    site = PracticeSite()
    site.start()
    try:
        book = write_workbook(tmp_path / "出貨追蹤.xlsx")
        binding = WebHostBinding(allowed_origins=(site.url,))
        installed = InstalledCapabilities()
        installed.register(
            READ_SPEC,
            WebScriptHandler(binding, tmp_path / "p", "read"),
            WebScript,
            WebScriptResult,
            LOCAL,
        )
        installed.register(
            ACT_SPEC,
            WebScriptHandler(binding, tmp_path / "p", "act"),
            WebScript,
            WebScriptResult,
            LOCAL,
        )
        installed.register(SELECT_SPEC, SelectHandler(), SelectRequest, SelectResult, LOCAL)
        installed.register(
            UPSERT_SPEC, UpsertHandler(tmp_path / "backups"), UpsertRequest, UpsertResult, LOCAL
        )
        grants = tuple(
            CapabilityGrant(
                actor="engineer",
                asset=item.identity,
                permissions=item.policy.required_permissions,
                policy_refs=item.policy.policy_refs,
                approval_ref="owner",
            )
            for item in (READ_SPEC, ACT_SPEC, SELECT_SPEC, UPSERT_SPEC)
        )
        bridge = BridgeExecutor(installed, LocalPolicy(grants))
        workflows = InstalledWorkflows()
        workflow = shipment_workflow()
        workflows.register(workflow)
        running = WorkflowEngine(workflows, bridge)
        arguments = {"site": site.url, "customer": "C001", "workbook": str(book)}
        before = book.read_bytes()

        shown = asyncio.run(running.preview(request("x"), workflow.metadata.identity, arguments))
        assert [item.state for item in shown.steps] == ["ran", "ran", "planned", "planned"]
        assert shown.steps[1].output["values"] == ["SO-1002", "SO-1004"]
        assert shown.steps[2].output["added"] == ["SO-1002", "SO-1003", "SO-1004"]
        assert shown.steps[3].inputs["for_each"] == ["SO-1002", "SO-1004"]
        assert book.read_bytes() == before and site.notified == set()

        run = asyncio.run(
            running.execute(
                request("x"), workflow.metadata.identity, arguments, timeout_seconds=120
            )
        )
        assert run.run.status == "succeeded", run.run.failure
        with urllib.request.urlopen(site.url + "/state.json") as reply:
            assert json.loads(reply.read())["notified"] == ["SO-1002", "SO-1004"]
        assert book.read_bytes() != before
    finally:
        site.close()
