"""A `ChangeAuthor` backed by the configured model (the internal Gateway).

The model proposes; it decides nothing. Scope comes from the request: the
plan always names exactly the declared artifact and every declared command,
whatever the model says, so it cannot narrow validation or widen the files it
may write. Each answer is one JSON object; a whole file comes back, never a
patch, so a malformed hunk cannot half-apply. Read-only context (the golden
tests and the current file) is given by the host, not chosen by the model.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from common.execution import TraceIdentifiers
from harness.contracts import (
    CandidateChange,
    CodingHarnessRequest,
    CommandOutcome,
    HarnessPlan,
    PlannedChange,
)
from harness.workspace import WorkspaceRefused
from models.contracts import ModelClient, ModelMessage, ModelRequest, ModelRequirements

OUTPUT_CONTRACT = "coding.change-author.v1"
MAX_CONTEXT_FILE_CHARS = 20_000
SYSTEM = (
    "You are the change author inside a bounded coding harness. You edit exactly one "
    "file and the harness validates it with tests you cannot change. Answer with a "
    "single JSON object and nothing else. Never claim tests pass; the harness runs them."
)


class AuthorUnavailable(WorkspaceRefused):
    """The model gave no usable answer; the run stops with this code."""


class ModelChangeAuthor:
    def __init__(
        self,
        model: ModelClient,
        model_alias: str,
        trace: TraceIdentifiers,
        context: Mapping[str, str],
        *,
        local_only: bool = False,
        max_output_tokens: int = 8_000,
    ) -> None:
        self.model = model
        self.model_alias = model_alias
        self.trace = trace
        self.context = dict(context)
        self.local_only = local_only
        self.max_output_tokens = max_output_tokens

    def plan(self, request: CodingHarnessRequest) -> HarnessPlan:
        answer = self._ask(
            request,
            "First, plan. Return {\"summary\": one sentence on what you will change, "
            "\"purpose\": what the change to the file achieves}.",
            max_output_tokens=600,
        )
        summary = _text(answer, "summary")
        purpose = _text(answer, "purpose")
        return HarnessPlan(
            summary=summary,
            changes=(PlannedChange(path=request.artifact_path, purpose=purpose),),
            validation_commands=request.allowed_commands,
        )

    def initial_change(self, request: CodingHarnessRequest, plan: HarnessPlan) -> CandidateChange:
        answer = self._ask(
            request,
            f"Plan: {plan.summary}\nNow write the change. Return {{\"content\": the complete "
            f"new text of {request.artifact_path}}}.",
        )
        return CandidateChange(path=request.artifact_path, content=_text(answer, "content"))

    def repair(
        self, request: CodingHarnessRequest, plan: HarnessPlan, failure: CommandOutcome,
        attempt: int,
    ) -> CandidateChange:
        failures = "\n\n".join(
            f"[{item.case} {item.code}] {item.message}" for item in failure.failures
        )
        answer = self._ask(
            request,
            f"Plan: {plan.summary}\nYour last version failed `{failure.command}` "
            f"(repair attempt {attempt}):\n{failures}\n\nFix the file. Return "
            f"{{\"content\": the complete corrected text of {request.artifact_path}}}.",
        )
        return CandidateChange(path=request.artifact_path, content=_text(answer, "content"))

    def _ask(
        self, request: CodingHarnessRequest, instruction: str, *, max_output_tokens: int = 0
    ) -> dict[str, Any]:
        files = "\n\n".join(
            f"--- {path} ---\n{text[:MAX_CONTEXT_FILE_CHARS]}"
            for path, text in self.context.items()
        )
        prompt = (
            f"Requirement:\n{request.requirement}\n\n"
            f"File you may write: {request.artifact_path}\n\n"
            f"Read-only context (current files):\n{files or '(none)'}\n\n{instruction}"
        )
        reply = self.model.generate(ModelRequest(
            trace=self.trace,
            model_alias=self.model_alias,
            messages=(ModelMessage(role="system", text=SYSTEM),
                      ModelMessage(role="user", text=prompt)),
            requirements=ModelRequirements(structured_output=True, local_only=self.local_only),
            output_contract=OUTPUT_CONTRACT,
            max_output_tokens=max_output_tokens or self.max_output_tokens,
        ))
        if reply.failure is not None:
            raise AuthorUnavailable("author_model_failed")
        answer: object = reply.structured_output
        if answer is None:
            answer = _salvage(reply.text)
        if not isinstance(answer, dict):
            raise AuthorUnavailable("author_answer_unparseable")
        return answer


def _text(answer: Mapping[str, Any], field: str) -> str:
    value = answer.get(field)
    if not isinstance(value, str) or not value.strip():
        raise AuthorUnavailable("author_answer_incomplete")
    return value


def _salvage(text: str) -> object:
    """A fenced or prefixed JSON object, which some models return anyway."""
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        return json.loads(text[start:end + 1])
    except ValueError:
        return None
