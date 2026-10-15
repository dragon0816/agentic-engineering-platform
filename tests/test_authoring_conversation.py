"""One SOP to Workflow discussion turn (SOP_TO_WORKFLOW W6), with a scripted model."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from test_workflow_preview import LOCAL, shipment_workflow

from capabilities.excel_blocks.handlers import (
    UPSERT_SPEC,
    UpsertHandler,
    UpsertRequest,
    UpsertResult,
)
from capabilities.runtime import InstalledCapabilities
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
from capabilities.workflow_author.conversation import AuthoringTurn, author_turn
from common.execution import Failure, TraceIdentifiers
from integrations.web_script import WebScript, WebScriptResult
from models.contracts import ModelRequest, ModelResponse

TRACE = TraceIdentifiers(trace_id="a", request_id="a", span_id="a")
SOP = "每日出貨追蹤：打開出貨查詢網站，輸入客戶代碼查詢，把結果更新到出貨追蹤.xlsx。"


def installed() -> InstalledCapabilities:
    blocks = InstalledCapabilities()
    binding = WebHostBinding(allowed_origins=("http://127.0.0.1:1",))
    blocks.register(
        READ_SPEC, WebScriptHandler(binding, Path("p"), "read"), WebScript, WebScriptResult, LOCAL
    )
    blocks.register(
        ACT_SPEC, WebScriptHandler(binding, Path("p"), "act"), WebScript, WebScriptResult, LOCAL
    )
    blocks.register(SELECT_SPEC, SelectHandler(), SelectRequest, SelectResult, LOCAL)
    blocks.register(UPSERT_SPEC, UpsertHandler(Path("b")), UpsertRequest, UpsertResult, LOCAL)
    return blocks


class Scripted:
    def __init__(self, *answers: Any) -> None:
        self.answers = list(answers)
        self.requests: list[ModelRequest] = []

    def generate(self, request: ModelRequest) -> ModelResponse:
        self.requests.append(request)
        answer = self.answers.pop(0)
        if isinstance(answer, Failure):
            return ModelResponse(
                trace=request.trace, model_alias=request.model_alias, failure=answer
            )
        if isinstance(answer, str):
            return ModelResponse(trace=request.trace, model_alias=request.model_alias, text=answer)
        return ModelResponse(
            trace=request.trace,
            model_alias=request.model_alias,
            text=json.dumps(answer, ensure_ascii=False),
            structured_output=answer,
        )


def turn(model: Scripted, turns: tuple[AuthoringTurn, ...] = ()) -> Any:
    return author_turn(
        SOP,
        turns,
        None,
        installed(),
        model=model,
        model_alias="gateway",
        trace=TRACE,
        namespace="engineering",
    )


def test_a_question_comes_back_without_a_workflow() -> None:
    model = Scripted(
        {"reply": "需要網站網址", "questions": ["出貨查詢網站的網址是？"], "workflow": None}
    )
    answer = turn(model)
    assert answer.workflow is None and answer.questions == ("出貨查詢網站的網址是？",)
    prompt = model.requests[0].messages
    assert "web/read@1.0.0" in prompt[0].text and SOP in prompt[1].text
    assert '"name": "web.read"' in prompt[1].text  # the installed catalogue


def test_a_draft_that_would_not_run_goes_back_with_its_problems() -> None:
    broken = shipment_workflow().model_dump(mode="json")
    broken["steps"][0]["capability"]["name"] = "browse"
    good = shipment_workflow().model_dump(mode="json")
    model = Scripted(
        {"reply": "草稿", "questions": [], "workflow": broken},
        {"reply": "修好了", "questions": [], "workflow": good},
    )
    answer = turn(model, (AuthoringTurn(role="owner", text="網址是 http://127.0.0.1:1"),))
    assert answer.workflow is not None and answer.attempts == 2 and answer.reply == "修好了"
    assert "would not run here" in model.requests[1].messages[1].text
    assert "owner: 網址是" in model.requests[0].messages[1].text


def test_an_unusable_model_stops_with_the_problems_named() -> None:
    answer = turn(Scripted("not json", "still not", "nope"))
    assert answer.workflow is None and answer.attempts == 3 and answer.problems
    failed = turn(Scripted(Failure(code="model_unavailable", message="down")))
    assert failed.problems == ("model_unavailable",)


def test_the_host_fills_in_what_the_model_may_not_decide() -> None:
    from capabilities.workflow_author.conversation import assemble

    raw = {
        "name": "Daily Shipment Tracking",
        "description": "追蹤出貨",
        "metadata": {
            "visibility": "public",
            "lifecycle": "published",
            "owner": {"type": "team", "id": "everyone"},
        },
        "parameters": [
            {
                "name": "customer",
                "label": "哪個客戶？",
                "kind": "text",
                "scope": "runtime",
                "required": True,
            }
        ],
        "steps": [
            {
                "capability": "web/read@1.0.0",
                "name": "ignored",
                "inputs": {
                    "actions": {"source": "fixed", "value": [{"do": "open", "url": "{site}/"}]},
                    "values": {"source": "run", "path": []},
                },
            }
        ],
    }
    built = assemble(raw, namespace="engineering", owner="leo.chi", installed=installed())
    from common.assets import WorkflowManifest

    workflow = WorkflowManifest.model_validate(built)
    assert workflow.metadata.identity.name == "daily-shipment-tracking"
    assert workflow.metadata.visibility == "private" and workflow.metadata.lifecycle == "draft"
    assert workflow.metadata.owner.id == "leo.chi"
    assert workflow.dependencies.local_capabilities == ("web.read",)
    model = Scripted({"reply": "好了", "questions": [], "workflow": raw})
    answer = turn(model)
    assert answer.workflow is not None and answer.attempts == 1
