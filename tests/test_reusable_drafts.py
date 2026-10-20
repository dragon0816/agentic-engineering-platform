"""Reusable means a Workflow draft (owner 2026-10-20).

Live test 2026-10-20: the owner asked for an interactive org chart and expected
something to apply again, but the Agent only ran one-off code (`coding__run`):
no draft, no install card, nothing in Capabilities. When the person asks for
something reusable, the Agent drafts a Workflow (a `coding/run-python` step
with the script fixed and typed parameters), the in-chat install card appears,
and nothing is installed until the person presses Install. The Host's
`reusable_request_drafted` check sends a turn that only ran code back once.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from pydantic import JsonValue
from test_chat_workflow_forms_telegram import _Scripted
from test_draft_install_cards import DRAFT, _draft_cards, _stored
from test_draft_install_cards import served as served  # noqa: F401 - the fixture
from test_gateway import _call, _host_gateway, _text, request

from agent.conversation_harness import check_reuse
from agent.gateway import REUSABLE_GUIDANCE, ConversationToolExecution, HostTool, HostToolOutcome
from capabilities.contracts import CapabilitySpec
from common.assets import ExecutionDependencies
from common.base import Contract
from common.execution import RequestContext
from host_runtime.conversations import ConversationTurnRequest
from models.contracts import ModelRequest, ModelResponse, ModelTool

ASK = "這個組織圖做成可重複使用的 workflow，以後都用這個"


def _ok(name: str) -> HostTool:
    async def run(context: RequestContext, args: dict[str, Any]) -> HostToolOutcome:
        return HostToolOutcome(status="succeeded", data={"ok": True})

    return HostTool(
        ModelTool(name=name, description=name, input_contract="x.v1", input_schema={}), run
    )


def _done(name: str) -> ConversationToolExecution:
    return ConversationToolExecution(
        call_id="c", name=name, host=HostToolOutcome(status="succeeded")
    )


def test_the_check_wants_a_draft_only_for_a_reusable_request_that_ran_code() -> None:
    for asked in (
        ASK,
        "幫我做成可以重複用的",
        "把它做成 workflow",
        "以後都用這個",
        "建立一個工具來產生組織圖",
        "Make it reusable please",
        "save this as a workflow",
    ):
        check, reason = check_reuse(asked, (_done("coding__run"),), True)
        assert check.status == "failed" and reason is not None, asked
        assert "authoring__draft_workflow" in reason
        # A draft in the same turn is the answer.
        check, _ = check_reuse(asked, (_done("coding__run"), _done(DRAFT)), True)
        assert check.status == "passed", asked
        # No code ran (a question back, a draft alone): nothing to send back.
        assert check_reuse(asked, (), True)[0].status == "passed"
        # No draft tool offered on this turn: nothing the model could do.
        assert check_reuse(asked, (_done("coding__run"),), False)[0].status == "passed"
    for one_off in ("幫我現在產生一次組織圖", "畫一個流程圖", "run it now", "做一個 HTML 組織圖"):
        assert check_reuse(one_off, (_done("coding__run"),), True)[0].status == "passed", one_off


def test_a_reusable_request_answered_with_one_off_code_is_sent_back_to_draft() -> None:
    built, model = _host_gateway(
        [_ok("coding__run"), _ok(DRAFT)],
        [
            _call("coding__run", {"workspace": "C:/x", "script": "print(1)"}),
            _text("組織圖已經產生在 output 資料夾。"),
            _call(DRAFT, {"title": "組織圖", "workflow": {}}),
            _text("已起草 Workflow，請在卡片上按安裝。"),
        ],
    )
    result = asyncio.run(built.converse(request(ASK), ()))
    assert result.text == "已起草 Workflow，請在卡片上按安裝。"
    assert "Host 檢查未通過" not in result.text
    assert len(model.calls) == 4
    feedback = model.calls[2].messages[-1].text
    assert feedback.startswith("[Host check failed]") and "reusable" in feedback
    assert REUSABLE_GUIDANCE in model.calls[0].messages[0].text


def test_a_one_off_request_may_use_run_alone_and_the_rule_needs_the_draft_tool() -> None:
    built, model = _host_gateway(
        [_ok("coding__run"), _ok(DRAFT)],
        [_call("coding__run", {}), _text("組織圖已經產生在 output 資料夾。")],
    )
    result = asyncio.run(built.converse(request("幫我現在產生一次組織圖"), ()))
    assert result.text == "組織圖已經產生在 output 資料夾。" and len(model.calls) == 2
    bare, bare_model = _host_gateway(
        [_ok("coding__run")], [_call("coding__run", {}), _text("組織圖已經產生。")]
    )
    result = asyncio.run(bare.converse(request(ASK), ()))
    assert result.text == "組織圖已經產生。" and len(bare_model.calls) == 2
    assert REUSABLE_GUIDANCE not in bare_model.calls[0].messages[0].text


# -- through Agent Web: the draft's card, and nothing installed without the press ----


class _Anything(Contract):
    request: dict[str, JsonValue] | None = None
    arguments: dict[str, JsonValue] | None = None


class _Done(Contract):
    exit_code: int = 0


class _Runs:
    def __init__(self) -> None:
        self.calls = 0

    async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
        self.calls += 1
        return _Done()


class _Recording(_Scripted):
    def __init__(self, *replies: dict[str, Any]) -> None:
        super().__init__(*replies)
        self.requests: list[ModelRequest] = []

    def generate(self, item: ModelRequest) -> ModelResponse:
        self.requests.append(item)
        return super().generate(item)


RUN_PYTHON = CapabilitySpec.model_validate(
    {
        "identity": {"namespace": "coding", "name": "run-python", "version": "1.0.0"},
        "name": "coding.run_python",
        "description": "run a script",
        "input_contract": "coding.run-python.input.v1",
        "output_contract": "coding.run-python.output.v1",
        "side_effect": "execute",
        "policy": {
            "risk": "medium",
            "approval_required": True,
            "required_permissions": ["coding.run-python"],
            "policy_refs": ["coding-restricted-execution-policy"],
        },
    }
)


@pytest.fixture
def web_with_run_python(served: Any, tmp_path: Path) -> Iterator[tuple[Any, _Runs, Path]]:  # noqa: F811
    web = served[0]
    runs = _Runs()
    installed = web.runtime.agent.gateway.bridge.installed
    if installed.get(RUN_PYTHON.identity) is None:
        installed.register(
            RUN_PYTHON, runs, _Anything, _Done, ExecutionDependencies(central_required=False)
        )
    root = tmp_path / "aep-workflows"
    root.mkdir()
    web.runtime.chat_authoring.coding_workspace_roots = (str(root),)
    yield web, runs, root


def _org_chart_workflow(root: Path) -> dict[str, Any]:
    return {
        "name": "org-chart-html",
        "description": "Make the interactive HTML org chart.",
        "parameters": [
            {
                "name": "include_former_staff",
                "label": "Include people who have left?",
                "kind": "boolean",
                "scope": "runtime",
                "required": False,
            }
        ],
        "steps": [
            {
                "capability": "coding/run-python@1.0.0",
                "inputs": {
                    "request": {
                        "source": "fixed",
                        "value": {
                            "workspace": str(root / "org-chart"),
                            "script": (
                                "import json, os\n"
                                "params = json.load(open(os.environ['AEP_WORKFLOW_PARAMS']))\n"
                                "open('output/org-chart.html', 'w').write('<html></html>')\n"
                            ),
                        },
                    },
                    "arguments": {"source": "run", "path": []},
                },
            }
        ],
    }


def test_a_reusable_request_drafts_a_workflow_with_its_card_and_installs_only_on_the_press(
    web_with_run_python: Any,
) -> None:
    web, runs, root = web_with_run_python
    session = web.create_conversation()["conversation"]["session_id"]
    model = _Recording(
        {"tools": [(DRAFT, {"title": "互動組織圖", "workflow": _org_chart_workflow(root)})]},
        {"text": "已起草「互動組織圖」Workflow，請在下方卡片按安裝。"},
    )
    web.runtime.agent.gateway.router.model = model
    replied = web.conversation_turn(ConversationTurnRequest(session_id=session, message=ASK))
    assert REUSABLE_GUIDANCE in model.requests[0].messages[0].text
    (card,) = _draft_cards(replied["answer"])
    assert card["kind"] == "draft_install" and card["status"] == "pending"
    assert "install" in [button["action"] for button in card["buttons"]]
    assert "coding/run-python@1.0.0" in card["preview"]
    # Drafted, not installed, not run: the model never installs.
    assert runs.calls == 0
    assert not list(web.runtime.layout.workflows.glob("*org-chart-html*"))
    assert _stored(web, session)[-1]["action_cards"][0]["card_id"] == card["card_id"]
    # The person's press installs it.
    decided = web.decide_card(card["card_id"], "install")
    assert decided["ok"] and decided["card"]["status"] == "installed"
    assert (web.runtime.layout.workflows / "engineering__org-chart-html__1.0.0.json").is_file()
    assert runs.calls == 0
