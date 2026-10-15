"""The Gateway-backed change author (CODING_ON_BRIDGE C4)."""

import json
from collections.abc import Iterator
from typing import Any

import pytest

from common.execution import Failure, TraceIdentifiers
from harness.contracts import (
    CodingHarnessRequest,
    CommandOutcome,
    HarnessPlan,
    PlannedChange,
    ValidationFailure,
    WorkspaceSnapshot,
)
from harness.model_author import AuthorUnavailable, ModelChangeAuthor
from harness.pytest_commands import NEW_COMMAND, SUITE_COMMAND, new_cases, suite_case
from models.contracts import ModelRequest, ModelResponse, ModelStreamEvent

TRACE = TraceIdentifiers(trace_id="c", request_id="c", span_id="c")
REQUEST = CodingHarnessRequest(
    workspace=WorkspaceSnapshot(root="C:/work", starting_revision="0" * 64),
    requirement="Add double(value).",
    artifact_path="src/calc/double.py",
    allowed_paths=("src/calc/double.py",),
    allowed_commands=(NEW_COMMAND, SUITE_COMMAND),
    cases=(*new_cases(("tests/test_double.py",)), suite_case()),
    skill_versions=("coding@1.0.0",),
)


class Replies:
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
        text = answer if isinstance(answer, str) else json.dumps(answer)
        return ModelResponse(
            trace=request.trace,
            model_alias=request.model_alias,
            text=text,
            structured_output=None if isinstance(answer, str) else answer,
        )

    def stream(self, request: ModelRequest) -> Iterator[ModelStreamEvent]:
        raise NotImplementedError


def author(model: Replies) -> ModelChangeAuthor:
    return ModelChangeAuthor(
        model, "gateway", TRACE, {"tests/test_double.py": "def test_double(): ..."}
    )


def test_the_plan_keeps_the_declared_scope_whatever_the_model_says() -> None:
    model = Replies(
        {
            "summary": "add it",
            "purpose": "implement double",
            "validation_commands": ["nothing"],
            "changes": ["tests/test_double.py"],
        }
    )
    plan = author(model).plan(REQUEST)
    assert [change.path for change in plan.changes] == ["src/calc/double.py"]
    assert plan.validation_commands == (NEW_COMMAND, SUITE_COMMAND)
    request = model.requests[0]
    assert request.output_contract and request.requirements.structured_output
    assert "def test_double" in request.messages[1].text  # golden tests are context


def test_change_and_repair_return_whole_files_and_repair_sees_the_failure() -> None:
    model = Replies(
        {"content": "def double(v):\n    return v + 2\n"},
        '```json\n{"content": "def double(v):\\n    return v * 2\\n"}\n```',
    )
    writer = author(model)
    plan = HarnessPlan(
        summary="s",
        changes=(PlannedChange(path=REQUEST.artifact_path, purpose="p"),),
        validation_commands=REQUEST.allowed_commands,
    )
    first = writer.initial_change(REQUEST, plan)
    assert first.path == REQUEST.artifact_path and "v + 2" in first.content
    failure = CommandOutcome(
        command=NEW_COMMAND,
        status="failed",
        failures=(ValidationFailure(case="new-1", code="test_failed", message="assert 6 == 8"),),
    )
    repaired = writer.repair(REQUEST, plan, failure, 1)
    assert "v * 2" in repaired.content  # fenced JSON salvaged
    assert "assert 6 == 8" in model.requests[1].messages[1].text
    assert "return v + 2" in model.requests[1].messages[1].text  # repairs its own last version


@pytest.mark.parametrize(
    ("answer", "code"),
    [
        (Failure(code="model_unavailable", message="down"), "author_model_failed"),
        ("not json at all", "author_answer_unparseable"),
        ({"summary": "", "purpose": "x"}, "author_answer_incomplete"),
    ],
)
def test_an_unusable_answer_is_a_typed_stop(answer: Any, code: str) -> None:
    with pytest.raises(AuthorUnavailable) as stopped:
        author(Replies(answer)).plan(REQUEST)
    assert stopped.value.code == code
