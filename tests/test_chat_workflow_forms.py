"""A person's "run X" in a chat is the Workflow's form (owner 2026-10-15).

Agent Web answered "我要執行rs-wmt-package-release" in prose, asking for
settings and run values; Telegram answered "我要執行rs-wmt-package-release
workflow" with nothing but its "Done" status line. Here the request becomes
the generated form (Web) or question flow (Telegram), with given values as
prefill, a notice for missing settings, and never a silent Telegram turn.
See docs/phases/CHAT_WORKFLOW_FORMS.md.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from test_agent_tool_schema import _declared_gateway
from test_gateway import Handler, request
from test_routing import FakeModel

from capabilities.release_package.manifest import (
    commit_workflow,
    prepare_workflow,
    preview_workflow,
    push_workflow,
    release_workflow,
)
from common.assets import WorkflowManifest
from common.execution import RequestContext, TraceIdentifiers
from common.workflow_run_form import (
    FORM_TOOL,
    OFFER_KEY,
    agent_prefill,
    form_offer,
    missing_settings,
    offer_in,
    run_intent,
)
from models.contracts import ModelMessage, ModelRequest, ModelResponse, ModelToolCall

RELEASE_SETTINGS = {
    "release_repo_url": "C:/isolated/origin.git",
    "work_root": "C:/isolated/work",
    "inbox_path": "C:/isolated/inbox",
    "allowed_root": "C:/isolated",
}


def _catalog() -> list[WorkflowManifest]:
    return [
        release_workflow(),
        preview_workflow(),
        prepare_workflow(),
        commit_workflow(),
        push_workflow(),
        _plain("nightly-check"),
        _plain("push"),
        _plain("package-release"),
    ]


def _plain(name: str, parameters: list[dict[str, Any]] | None = None) -> WorkflowManifest:
    """A read-only Workflow (weekly report preview) under another name."""
    from capabilities.weekly_report.manifest import preview_workflow as weekly

    data = weekly().model_dump(mode="json")
    data["metadata"]["identity"]["name"] = name
    data["run_alias"] = None
    data["parameters"] = parameters or []
    return WorkflowManifest.model_validate(data)


# -- recognizing a run request ------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "我要執行rs-wmt-package-release",
        "我要執行rs-wmt-package-release workflow",
        "run rs-wmt-package-release",
        "幫我跑一下 engineering/rs-wmt-package-release",
        "rs-wmt-package-release 執行",
    ],
)
def test_an_explicit_run_of_the_release_workflow_is_recognized(text: str) -> None:
    intent = run_intent(text, _catalog())
    assert intent is not None
    assert intent.manifest.metadata.identity.name == "rs-wmt-package-release"
    assert intent.prefill == {}


@pytest.mark.parametrize(
    "text",
    [
        "rs-wmt-package-release 怎麼執行?",
        "為什麼 rs-wmt-package-release 執行失敗",
        "rs-wmt-package-release 是什麼",
        "不要執行 rs-wmt-package-release",
        "tell me about rs-wmt-package-release",
        "run the tests and then push the branch",  # `push` is a word, not a request
        "執行 something-not-installed",
        "",
    ],
)
def test_questions_refusals_and_unknown_names_are_left_to_the_model(text: str) -> None:
    assert run_intent(text, _catalog()) is None


def test_plain_word_names_need_the_verb_right_before_them_and_no_params_works() -> None:
    push = run_intent("run push", _catalog())
    assert push is not None and push.manifest.metadata.identity.name == "push"
    step = run_intent("執行 release-package-push", _catalog())
    assert step is not None and step.manifest.metadata.identity.name == "release-package-push"
    # `package-release` inside `rs-wmt-package-release` is not a second Workflow.
    whole = run_intent("我要執行rs-wmt-package-release", _catalog())
    assert whole is not None and whole.manifest.metadata.identity.name == ("rs-wmt-package-release")
    nightly = run_intent("請執行 nightly-check", _catalog())
    assert nightly is not None and nightly.manifest.parameters == ()


def test_values_typed_with_the_request_are_prefill_but_settings_never_are() -> None:
    intent = run_intent(
        "執行 rs-wmt-package-release companyName=Foxconn cmpKtOption=kt161 dryRun=no "
        'push=yes testPlans=a.json|b.json release_repo_url=C:/x notes="two words"',
        _catalog(),
    )
    assert intent is not None
    assert intent.prefill == {
        "companyName": "Foxconn",
        "cmpKtOption": "KT161",
        "dryRun": False,
        "push": True,
        "testPlans": ["a.json", "b.json"],
        "notes": "two words",
    }


def test_a_model_may_prefill_only_its_own_fields() -> None:
    manifest = release_workflow()
    given = {
        "companyName": "Foxconn",
        "push": True,
        "release_repo_url": "C:/x",
        "testPlanUploads": ["C:/anything.json"],
        "cmpKtOption": "not-a-choice",
    }
    assert agent_prefill(manifest, given) == {"companyName": "Foxconn"}


def test_missing_settings_are_named_and_the_message_points_to_the_settings_page() -> None:
    manifest = release_workflow()
    names = {item["name"] for item in missing_settings(manifest, {})}
    assert {"release_repo_url", "work_root", "inbox_path", "allowed_root"} <= names
    offer = form_offer(manifest, {}, lambda _m: {})
    assert offer["kind"] == OFFER_KEY and offer["missing_settings"]
    assert "settings page" in offer["message"] and "not in the chat" in offer["message"]
    ready = form_offer(manifest, {"companyName": "Foxconn"}, lambda _m: RELEASE_SETTINGS)
    assert ready["missing_settings"] == [] and "fill in the form" in ready["message"]
    broken = form_offer(manifest, {}, lambda _m: (_ for _ in ()).throw(OSError("locked")))
    assert broken["missing_settings"]  # unreadable store: shown as not set


# -- the Gateway hands over the form ------------------------------------------


def _session_request(message: str) -> RequestContext:
    return RequestContext(
        trace=TraceIdentifiers(trace_id="trace-1", request_id="request-1", span_id="span-1"),
        actor="engineer",
        namespace="engineering",
        channel="local",
        message=message,
        session_id="session-1",
    )


class _Calls(FakeModel):
    def __init__(self, name: str, arguments: dict[str, Any]) -> None:
        super().__init__()
        self.name, self.arguments = name, arguments

    def generate(self, item: ModelRequest) -> ModelResponse:
        self.calls.append(item)
        if len(self.calls) == 1:
            return ModelResponse(
                trace=item.trace,
                model_alias=item.model_alias,
                tool_calls=(
                    ModelToolCall(call_id="call-1", name=self.name, arguments=self.arguments),
                ),
            )
        return ModelResponse(
            trace=item.trace,
            model_alias=item.model_alias,
            text="Please give companyName and chipsetId.",
        )


def test_the_form_tool_ends_the_turn_with_the_offer_and_the_prompt_says_so() -> None:
    from host_runtime.workflow_form_tool import workflow_form_tools

    model = _Calls(
        FORM_TOOL,
        {"workflow": "rs-wmt-package-release", "values": {"companyName": "Foxconn", "push": True}},
    )
    gateway = _declared_gateway(Handler(), model)
    gateway.engine.workflows.register(release_workflow())
    gateway.host_tools = lambda: workflow_form_tools(gateway.engine)
    result = asyncio.run(
        gateway.converse(
            _session_request("release for Foxconn"),
            (ModelMessage(role="user", text="release for Foxconn"),),
        )
    )
    assert result.status == "answered" and len(model.calls) == 1
    offer = offer_in(result.tools)
    assert offer is not None and offer["workflow"]["name"] == "rs-wmt-package-release"
    assert offer["prefill"] == {"companyName": "Foxconn"}  # push is the person's choice
    assert offer["origin"] == "agent" and result.text == offer["message"]
    tool = next(t for t in model.calls[0].tools if t.name == FORM_TOOL)
    assert tool.input_schema is not None
    properties = tool.input_schema["properties"]
    assert isinstance(properties, dict)
    workflow_field = properties["workflow"]
    assert isinstance(workflow_field, dict)
    enum = workflow_field["enum"]
    assert isinstance(enum, list) and "rs-wmt-package-release" in enum
    assert FORM_TOOL in model.calls[0].messages[0].text


def test_the_form_tool_is_not_offered_without_a_person_to_fill_it() -> None:
    from host_runtime.workflow_form_tool import workflow_form_tools

    model = _Calls("nothing", {})
    gateway = _declared_gateway(Handler(), model)
    gateway.host_tools = lambda: workflow_form_tools(gateway.engine)
    asyncio.run(gateway.converse(request("check"), (ModelMessage(role="user", text="check"),)))
    assert FORM_TOOL not in {tool.name for tool in model.calls[0].tools}


def test_an_incomplete_workflow_tool_call_in_a_conversation_becomes_the_form() -> None:
    handler = Handler()
    model = _Calls("release__package", {"args": "NOT-VALID"})
    result = asyncio.run(
        _declared_gateway(handler, model).converse(
            _session_request("package the release"),
            (ModelMessage(role="user", text="package the release"),),
        )
    )
    offer = offer_in(result.tools)
    assert offer is not None and offer["prefill"] == {} and handler.calls == 0
    assert result.status == "answered" and len(model.calls) == 1
    # A valid call still runs: the Agent-tool path for orchestration stays.
    valid = _Calls("release__package", {"args": "quick"})
    ran = asyncio.run(
        _declared_gateway(handler, valid).converse(
            _session_request("package the release"),
            (ModelMessage(role="user", text="package the release"),),
        )
    )
    assert ran.tools[0].workflow is not None and handler.calls == 1
