"""The Knowledge page's Skill assistant (owner, 2026-10-12)."""

from collections.abc import Iterator
from typing import Any

import pytest

from common.execution import Failure, TraceIdentifiers
from host_runtime.skill_assist import Turn, assist, proposal_of
from host_runtime.web_page import PAGE
from models.contracts import ModelRequest, ModelResponse, ModelStreamEvent

TRACE = TraceIdentifiers(trace_id="t", request_id="r", span_id="s")
PROPOSAL = ("---\nname: ingest-market\nmode: procedure\napplies_to: raw/Market\n---\n\n"
            "# ingest-market\n")


class _Model:
    def __init__(self, text: str = "", fail: bool = False) -> None:
        self.text, self.fail = text, fail
        self.requests: list[ModelRequest] = []

    def generate(self, request: ModelRequest) -> ModelResponse:
        self.requests.append(request)
        if self.fail:
            return ModelResponse(trace=request.trace, model_alias=request.model_alias,
                                 failure=Failure(code="model_http_error", message="503"))
        return ModelResponse(trace=request.trace, model_alias=request.model_alias, text=self.text)

    def stream(self, request: ModelRequest) -> Iterator[ModelStreamEvent]:
        raise NotImplementedError


def _assist(model: Any, turns: list[Turn]) -> Any:
    return assist(model, "company", guide="GUIDE {braces}", template="TEMPLATE",
                  path="skills/ingest-market/SKILL.md", current="old rules",
                  sample="a market deck", turns=turns, trace=TRACE)


def test_the_assistant_sees_guide_template_file_and_sample_and_proposes() -> None:
    model = _Model(f"I added a date rule.\n\n```markdown\n{PROPOSAL}```\n")
    reply = _assist(model, [Turn(role="user", text="每條市場說法都要有日期")])
    assert reply.proposal == PROPOSAL
    messages = model.requests[0].messages
    assert "GUIDE {braces}" in messages[0].text and "TEMPLATE" in messages[0].text
    assert "old rules" in messages[1].text and "a market deck" in messages[1].text
    assert messages[-1].text == "每條市場說法都要有日期"


def test_a_question_back_has_no_proposal_and_failures_are_reported() -> None:
    assert _assist(_Model("沒有日期時要寫什麼？"), [Turn(role="user", text="x")]).proposal is None
    with pytest.raises(RuntimeError, match="model_http_error"):
        _assist(_Model(fail=True), [Turn(role="user", text="x")])
    with pytest.raises(ValueError):
        _assist(_Model("x"), [Turn(role="assistant", text="x")])
    assert proposal_of("```python\nprint(1)\n```") is None  # only a SKILL.md with frontmatter


def test_the_page_offers_the_assistant() -> None:
    for hook in ('id="kp-assist-send"', "/api/knowledge/skill-assist", "Use this version"):
        assert hook in PAGE
